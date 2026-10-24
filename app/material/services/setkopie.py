"""Stückliste übertragen (Sets anlegen und Stückliste übertragen, Wunsch vom 24.10.2026, Entwurf B; Entscheidungen S4–S7).

Angelegte Sets behalten die Stückliste, mit der sie angelegt wurden (Kopie mat_item_set_slot). Ändert die
Material-Verwaltung die Stückliste im Katalog, bringt „Stückliste übertragen“ sie auf vorhandene Sets – je Set gewählt,
alle vorbelegt (S4). Nur die Material-Verwaltung (Routen an katalog_required, S7); Materialwarte ändern die
Zusammensetzung nie, sie setzen nur physische Teile ein, entnehmen und tauschen (setaustausch.py).

Regeln, wie sie hier umgesetzt sind:
  - Vorschau (vorschau, GET …/stueckliste-uebertragen): die Sets des Produkts (Set-Artikel, auch in anderen
    Gliederungen – die Material-Verwaltung sieht den ganzen Bestand) mit einer anderen Kopie als der jetzigen
    Stückliste, gruppiert nach ihrer bisherigen Kopie; je Gruppe ein Vergleich Position | bisher | jetzt | Wirkung (nur
    zur Anzeige zugeordnet: einzeln geführte nach Produkt, die übrigen nach Bezeichnung), je Set Inventarnummer,
    Ordnerpfad, Zustand, Herstellungsdatum, Wirkung oder der Grund, warum es nicht geht. Ausgesonderte und Sets mit
    gleicher Kopie werden nur gezählt. Ganzer Vorgang 409: Produkt kein Set, Stückliste leer oder ohne einzeln
    geführtes Teil (S3 – ein Altbestand aus der Zeit vor der Regel).
  - Nicht übertragbar (mit Grund): offene Set-Prüfung (ihre Ja/Nein-Zeilen kamen aus der Kopie; die Trigger aus
    Schritt 22 verbieten es ebenso), offener Entwurf am Set-Artikel, danach fehlte ein Teil an einer Position mit
    „Austausch laut Hersteller: nein“ (einsetzen ginge dann nicht – das Set aussondern), der Systemordner „Gesperrt“ der
    Gliederung fehlt (nur, wenn das Set dabei sperren müsste). Kein Ausschluss: Sperre, Mangel, Rückruf, DEMO.
  - Wirkung (uebertragen, POST): die Kopie als Ganzes ersetzen (DELETE, sets.kopie_schreiben). Teil-Artikel bewegen
    sich nicht (S5). Danach zählt _zuteilen neu: Fehlt ein einzeln geführtes Teil oder ist eines übrig (keiner Position
    mehr zugeteilt – „steht nicht mehr in der Stückliste“), sperrt das Set (sets.sperren mit set_grund „stueckliste“;
    Kaskade wie beim Entnehmen, frei erst über „Set prüfen“). Bezeichnung, Austausch, Reihenfolge und Bestandteile ohne
    eigenen Artikel sperren nicht (S6) – an einem gesperrten Set zieht gruende_nachziehen die Gründe nach, die nächste
    Set-Prüfung fragt die Bestandteile nach der neuen Kopie ab. Ein übriges Teil nimmt der Ordner-Verwalter mit „Teil
    entnehmen“ heraus (weiterführen oder aussondern, er wählt das Stück); vorher gibt keine Set-Prüfung frei.
  - Journal: am Set „stueckliste_uebertragen“ (vorher die alte Kopie, nachher die neue, was fehlt und welche Teile
    nicht mehr in der Stückliste stehen; der Handelnde mit Namen), bei neuer Sperre die Kaskade („gesperrt“ mit
    set_grund „stueckliste“ – zählt im Jahresbericht einmal als Set-Sperre –, an den Teilen „set_gesperrt“ als „System“),
    an jedem übrigen Teil „nicht_in_stueckliste“. Kein Eintrag am Produkt (dessen Journal sieht jeder mit Modulzugang –
    dort stünden sonst Inventarnummern fremder Gliederungen). Keine Mail.
  - Eine Transaktion (BEGIN IMMEDIATE) über alle gewählten Sets: Die Vorschau liefert „stand“ (SHA-256 über die
    Stückliste und je Set Kopie, Teile mit Produkt, Sperre, offene Set-Prüfung und offenen Entwurf); POST rechnet unter
    der Sperre neu – anderer Stand → 409 „Inzwischen geändert“, ein Set außerhalb der übertragbaren → 409, nichts
    geschrieben. set_stimmig je Set; ein Fehler rollt alles zurück."""
import hashlib
import json

from ... import db
from . import Abgelehnt, kennung
from . import bestand, journal, katalog, sets, stueckliste

INZWISCHEN = "Inzwischen geändert – bitte die Vorschau neu laden. Es wurde nichts übertragen."
NICHT_UEBERTRAGBAR = "{inv} lässt sich nicht übertragen{grund} – bitte die Vorschau neu laden."
KEINE_WAHL = "Bitte mindestens ein Set wählen."
LEER = "Die Stückliste ist leer – erst Positionen anlegen, dann übertragen."
SETS_MAX = 2000                       # so viele Kennungen nimmt eine Anfrage höchstens an


def _kopie_form(z, feld):
    """Eine Position als Vergleichswert – Stückliste (feld „component_product_id“) und Kopie („product_id“) gleich."""
    return (z["position"], z[feld], z["bezeichnung"], z["anzahl"], int(z["einzeln"]), z["austausch"])


def _kopien(pid):
    """{Set-Artikel: [Vergleichswerte seiner Kopie]} für alle Set-Artikel des Produkts – eine Abfrage, ohne Sets ohne
    Kopie zu verlieren (die zählen mit leerer Liste)."""
    out = {r["id"]: [] for r in db.query("SELECT id FROM mat_item WHERE product_id = ? AND parent_item_id IS NULL",
                                         (pid,))}
    for z in db.query("SELECT z.* FROM mat_item_set_slot z JOIN mat_item s ON s.id = z.set_item_id WHERE s.product_id = ? "
                      "ORDER BY z.set_item_id, z.position, z.id", (pid,)):
        out.setdefault(z["set_item_id"], []).append(_kopie_form(z, "product_id"))
    return out


def aelter(pid):
    """Wie viele nicht ausgesonderte Sets dieses Produkts eine andere Kopie haben als die jetzige Stückliste
    (produkt_json: „sets_aelter“; Hinweis und Knopf „Auf vorhandene Sets übertragen …“ auf der Produktseite)."""
    jetzt = [_kopie_form(z, "component_product_id") for z in stueckliste.zeilen(pid)]
    kopien = _kopien(pid)
    if not kopien:
        return 0
    aktiv = {r["id"] for r in db.query("SELECT id FROM mat_item WHERE product_id = ? AND parent_item_id IS NULL "
                                       "AND lock_state <> 'ausgesondert'", (pid,))}
    return sum(1 for sid, k in kopien.items() if sid in aktiv and k != jetzt)


# --- Vergleich (nur zur Anzeige) --------------------------------------------------------------------------------------

def _pos(z, feld):
    pid = z[feld]
    return {"position": z["position"], "produkt": pid, "bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"],
            "einzeln": bool(z["einzeln"]), "austausch": z["austausch"],
            "produkt_name": katalog.produktname(katalog.produkt(pid)) if pid else ""}


def _text(x):
    art = f"einzeln geführt ({x['produkt_name']})" if x["einzeln"] else "ohne eigenen Artikel"
    return f"{x['bezeichnung']} · {x['anzahl']}× · {art} · Austausch: {stueckliste.AUSTAUSCH[x['austausch']]}"


def vergleich(alt, neu):
    """Position | bisher | jetzt | Wirkung – zugeordnet nur zur Anzeige: erst einzeln geführte nach Produkt, dann alle
    übrigen nach Bezeichnung (Groß-/Kleinschreibung egal), was dann ohne eigenen Artikel übrig ist, der Reihe nach. alt,
    neu: Listen aus _pos. Liefert Zeilen {position, bisher,
    jetzt, wirkung} in der neuen Reihenfolge, entfallene dahinter."""
    rest = list(alt)
    paar = {}
    for i, n in enumerate(neu):
        if n["einzeln"]:
            a = next((a for a in rest if a["einzeln"] and a["produkt"] == n["produkt"]), None)
            if a:
                paar[i] = a
                rest.remove(a)
    for i, n in enumerate(neu):
        if i in paar:
            continue
        a = next((a for a in rest if a["bezeichnung"].casefold() == n["bezeichnung"].casefold()), None)
        if a:
            paar[i] = a
            rest.remove(a)
    # Was dann noch übrig ist an Bestandteilen ohne eigenen Artikel, der Reihe nach – so erscheint eine umbenannte Tasche
    # als „Bezeichnung“, nicht als „neu“ und „entfällt“.
    for i, a in zip([i for i, n in enumerate(neu) if i not in paar and not n["einzeln"]],
                    [a for a in rest if not a["einzeln"]]):
        paar[i] = a
        rest.remove(a)
    zeilen = []
    for i, n in enumerate(neu):
        a = paar.get(i)
        if not a:
            zeilen.append({"position": n["position"], "bisher": "", "jetzt": _text(n), "wirkung": "neu"})
            continue
        w = []
        if a["einzeln"] != n["einzeln"]:
            w.append("jetzt einzeln geführt" if n["einzeln"] else "jetzt ohne eigenen Artikel")
        elif n["einzeln"] and a["produkt"] != n["produkt"]:
            w.append("anderes Produkt")
        if a["anzahl"] != n["anzahl"]:
            w.append(f"Anzahl {a['anzahl']} → {n['anzahl']}")
        if a["bezeichnung"] != n["bezeichnung"]:
            w.append("Bezeichnung")
        if a["austausch"] != n["austausch"]:
            w.append(f"Austausch {stueckliste.AUSTAUSCH[a['austausch']]} → {stueckliste.AUSTAUSCH[n['austausch']]}")
        if a["position"] != n["position"]:
            w.append("Reihenfolge")
        zeilen.append({"position": n["position"], "bisher": _text(a), "jetzt": _text(n),
                       "wirkung": ", ".join(w) or "unverändert"})
    for a in rest:
        zeilen.append({"position": None, "bisher": _text(a), "jetzt": "", "wirkung": "entfällt"})
    return zeilen


# --- Rechnen: je Set Wirkung und Hindernis ----------------------------------------------------------------------------

def _neue_slots(stueck):
    """Die Stückliste in der Form der Kopie (für sets._zuteilen) – ohne Kennungen der Datenbank."""
    return [{"id": f"neu-{z['position']}-{n}", "position": z["position"], "product_id": z["component_product_id"],
             "bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"], "einzeln": z["einzeln"], "austausch": z["austausch"]}
            for n, z in enumerate(stueck)]


def _fehlt_text(fehlend):
    return "; ".join(f"„{f['bezeichnung']}“ fehlt {f['fehlt']}×" for f in fehlend)


def _set_rechnen(s, tz, neu_slots):
    """Was das Übertragen an diesem Set bewirkte: {fehlend, uebrig, sperrt, grund (Hindernis oder None), wirkung}."""
    from . import pruefung, setlauf
    _, fehlend = sets.vollstaendigkeit(neu_slots, tz)
    uebrig = sets.ueberzaehlig(neu_slots, tz)
    sperrt = bool(fehlend or uebrig)
    grund = None
    lf = setlauf.offener(s["id"])
    entwurf = pruefung.offener_entwurf(s["id"])
    _, vorhanden = sets._zuteilen(neu_slots, tz)
    nein = [z for z in neu_slots if z["einzeln"] and z["austausch"] == "nein" and vorhanden.get(z["id"], 0) < z["anzahl"]]
    if lf:
        grund = (f"Die Set-Prüfung läuft (begonnen am {setlauf._fmt(lf['opened_at'])} von {lf['opened_by_name'] or 'unbekannt'})"
                 " – erst abschließen oder abbrechen.")
    elif entwurf:
        grund = pruefung.reserviert_text(entwurf) + " Erst festschreiben oder verwerfen."
    elif nein:
        grund = (f"Danach fehlte „{nein[0]['bezeichnung']}“ – laut Hersteller nicht austauschbar, ein Teil ließe sich nicht "
                 "einsetzen.")
    elif sperrt and s["lock_state"] == "frei":
        gl = bestand.gliederung_von(s["folder_id"])
        if not (gl and bestand.systemordner(gl["id"], "gesperrt")):
            grund = "Der Systemordner „Gesperrt“ der Gliederung fehlt – bitte den Ordnerbaum prüfen."
    teile_text = [_fehlt_text(fehlend)] if fehlend else []
    teile_text += [f"{t['inventory_no']} steht nicht mehr in der Stückliste" for t in uebrig]
    if sperrt:
        wirkung = ("bleibt gesperrt bis zur Set-Prüfung: " if s["lock_state"] != "frei" else "gesperrt bis zur Set-Prüfung: ") \
            + "; ".join(teile_text)
    else:
        wirkung = "bleibt frei – nur Angaben" if s["lock_state"] == "frei" else "bleibt gesperrt – nur Angaben"
    return {"fehlend": fehlend, "uebrig": uebrig, "sperrt": sperrt, "grund": grund, "wirkung": wirkung}


def _rechnen(pid):
    """Der ganze Stand für Vorschau und Übertragen – frisch gelesen (in der Transaktion des Aufrufers)."""
    from . import pruefung, setlauf
    p = katalog.produkt(pid)
    if not p["is_set"]:
        raise Abgelehnt(stueckliste.NUR_SET, 409)
    stueck = stueckliste.zeilen(pid)
    if not stueck:
        raise Abgelehnt(LEER, 409)
    if not any(z["einzeln"] for z in stueck):
        raise Abgelehnt(stueckliste.EINZELN_PFLICHT + " Erst die Stückliste ergänzen, dann übertragen.", 409)
    jetzt = [_kopie_form(z, "component_product_id") for z in stueck]
    neu_slots = _neue_slots(stueck)
    neu_pos = [_pos(z, "component_product_id") for z in stueck]
    kopien = _kopien(pid)
    stand = {"stueckliste": jetzt, "sets": []}
    gruppen, ausgesondert, gleich = {}, 0, 0
    for sid in sorted(kopien):
        s, tz = sets.zeilen(sid)
        lf, e = setlauf.offener(sid), pruefung.offener_entwurf(sid)
        stand["sets"].append([sid, s["lock_state"], s["lock_cause"], kopien[sid], [(t["id"], t["product_id"]) for t in tz],
                              lf["id"] if lf else None, e["id"] if e else None])
        if kopien[sid] == jetzt:
            gleich += 1
            continue
        if s["lock_state"] == "ausgesondert":
            ausgesondert += 1
            continue
        r = _set_rechnen(s, tz, neu_slots)
        gruppe = gruppen.setdefault(json.dumps(kopien[sid]), {"alt": sets.slots(sid), "sets": []})
        gruppe["sets"].append((s, tz, r))
    summe = hashlib.sha256(json.dumps(stand, sort_keys=True, default=str).encode()).hexdigest()
    return {"p": p, "stueck": stueck, "neu_pos": neu_pos, "gruppen": list(gruppen.values()), "ausgesondert": ausgesondert,
            "gleich": gleich, "stand": summe}


def _set_json(s, tz, r):
    w = sets.werte(s, tz)
    return {"id": s["id"], "inventory_no": s["inventory_no"], "ordner": bestand._pfad_text(bestand.heimat(s)),
            "status": w["status"], "status_text": w["status_text"], "lock_state": s["lock_state"],
            "manufactured_on": s["manufactured_on"], "demo": bool(bestand.ordner_ist_demo(bestand.heimat(s))),
            "uebertragbar": r["grund"] is None, "grund": r["grund"], "sperrt": r["sperrt"], "wirkung": r["wirkung"]}


def vorschau(pid):
    """GET /produkte/<pid>/stueckliste-uebertragen: {produkt {id, name}, stand, gruppen [{vergleich [Zeilen],
    sets [{id, inventory_no, ordner, status(_text), lock_state, manufactured_on, demo, uebertragbar, grund, sperrt,
    wirkung}]}], ausgesondert, gleich, uebertragbar, sperrt} – siehe Kopf."""
    v = _rechnen(pid)
    gruppen = []
    for g in v["gruppen"]:
        alt = [_pos(z, "product_id") for z in g["alt"]]
        gruppen.append({"vergleich": vergleich(alt, v["neu_pos"]),
                        "sets": [_set_json(s, tz, r) for s, tz, r in sorted(g["sets"], key=lambda x: x[0]["inventory_no"])]})
    alle = [x for g in gruppen for x in g["sets"]]
    return {"produkt": {"id": v["p"]["id"], "name": katalog.produktname(v["p"])}, "stand": v["stand"], "gruppen": gruppen,
            "ausgesondert": v["ausgesondert"], "gleich": v["gleich"],
            "uebertragbar": sum(1 for x in alle if x["uebertragbar"]),
            "sperrt": sum(1 for x in alle if x["uebertragbar"] and x["sperrt"])}


def _journal_form(z, feld):
    return {"bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"], "einzeln": bool(z["einzeln"]),
            "austausch": z["austausch"], "produkt": z[feld]}


def _uebertragen_an(s, tz, stueck):
    """Ein Set: die Kopie ersetzen, Journal, bei Bedarf sperren (siehe Kopf) – in der Transaktion des Aufrufers. Liefert,
    ob das Set danach wegen der Stückliste gesperrt ist."""
    sid = s["id"]
    alt = sets.slots(sid)
    zu_alt, _ = sets._zuteilen(alt, tz)
    db.execute("DELETE FROM mat_item_set_slot WHERE set_item_id = ?", (sid,))
    sets.kopie_schreiben(sid, stueck)
    sz = sets.slots(sid)
    _, fehlend = sets.vollstaendigkeit(sz, tz)
    uebrig = sets.ueberzaehlig(sz, tz)
    journal.eintragen("item", sid, "stueckliste_uebertragen",
                      {"bestandteile": [_journal_form(z, "product_id") for z in alt]},
                      {"bestandteile": [_journal_form(z, "component_product_id") for z in stueck],
                       "fehlt": [{"bezeichnung": f["bezeichnung"], "anzahl": f["fehlt"]} for f in fehlend],
                       "nicht_in_stueckliste": [t["inventory_no"] for t in uebrig]})
    for t in uebrig:
        z = zu_alt.get(t["id"])
        journal.eintragen("item", t["id"], "nicht_in_stueckliste", None,
                          {"set": sid, "set_inventar": s["inventory_no"],
                           "bestandteil": z["bezeichnung"] if z else katalog.produktname(katalog.produkt(t["product_id"]))})
    if fehlend or uebrig:
        teile = ([sets.UNVOLLSTAENDIG.format(bez=", ".join(f"„{f['bezeichnung']}“" for f in fehlend), was="fehlt")]
                 if fehlend else [])
        if uebrig:
            teile.append(sets.NICHT_IN_STUECKLISTE.format(nummern=", ".join(t["inventory_no"] for t in uebrig)))
        sets.sperren(sid, set_grund="stueckliste", anlass="; ".join(teile))
    else:
        sets.gruende_nachziehen(sid)
    sets.set_stimmig(sid)
    return bool(fehlend or uebrig)


def uebertragen(pid, d):
    """POST /produkte/<pid>/stueckliste-uebertragen {"stand", "set_ids": [Kennungen]} – siehe Kopf. Liefert
    {uebertragen, gesperrt}."""
    stand = d.get("stand") if isinstance(d, dict) else None
    if not isinstance(stand, str) or not stand:
        raise Abgelehnt("„stand“ fehlt – bitte die Vorschau laden.")
    roh = d.get("set_ids")
    if not isinstance(roh, list) or len(roh) > SETS_MAX:
        raise Abgelehnt("„set_ids“ muss eine Liste von Set-Kennungen sein.")
    ids = sorted({kennung(x, "Set") for x in roh})
    if not ids:
        raise Abgelehnt(KEINE_WAHL)
    with db.transaction(sofort=True):
        v = _rechnen(pid)
        if v["stand"] != stand:
            raise Abgelehnt(INZWISCHEN, 409)
        kandidaten = {s["id"]: (s, tz, r) for g in v["gruppen"] for s, tz, r in g["sets"]}
        for sid in ids:
            x = kandidaten.get(sid)
            if not x or x[2]["grund"]:
                inv = x[0]["inventory_no"] if x else f"Nr. {sid}"
                raise Abgelehnt(NICHT_UEBERTRAGBAR.format(inv=inv, grund=f" ({x[2]['grund']})" if x else ""), 409)
        gesperrt = sum(_uebertragen_an(kandidaten[sid][0], kandidaten[sid][1], v["stueck"]) for sid in ids)
    return {"uebertragen": len(ids), "gesperrt": gesperrt}
