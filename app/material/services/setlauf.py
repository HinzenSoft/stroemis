"""Set prüfen (Phase 4 · Lieferung 2, Entwurf E und D, Paket K2): die Set-Prüfung als kleiner Ablauf (mat_set_lauf) und
der eine Freigabe-Übergang eines gesperrten Sets.

Ablauf: „Set prüfen“ an der Set-Seite eröffnet einen Lauf (eroeffnen – höchstens einer je Set, ein zweiter Aufruf liefert
den offenen). Offene Entwürfe an Set-Artikel und Teilen (keine Berichtigungen) zählen ab dann im Lauf, jede neue Prüfung
an ihnen ebenso (pruefung.starten setzt set_lauf_id). Jedes Teil hat seine eigene Prüfung mit eigenem Formular und
eigenem P-Protokoll (dort „Teil von Set …“ als Kopie). Den Set-Artikel prüft man NUR im Lauf – mit dem Formular seines
Produkts, ergänzt um je eine Ja/Nein-Zeile „… vorhanden“ je nicht einzeln geführtem Bestandteil (Gruppe SET_GRUPPE,
ohne Formularpunkt). Sein Festschreiben schließt den Lauf:
  - vorher (vorbereiten, 409): kein anderer Entwurf im Lauf; jedes Teil im Prüfumfang hat eine im Lauf abgeschlossene
    Prüfung. Prüfumfang (umfang): ein freies Set – alle Teile (periodisch); ein Set, das selbst noch nie geprüft wurde –
    alle Teile (L2b); ein gesperrtes – ging die Sperre vom Set-Artikel aus (set_lock_origin „set“), alle Teile, sonst die
    Teile mit set_pruefen (neu eingesetzt oder seit der Sperre mit eigenem Grund; Entscheidung vom 23.10.2026). Die übrigen zählen mit ihrer letzten gültigen Prüfung
    („übernommen“). Weitere Teile darf man im Lauf trotzdem prüfen („auch prüfen“) – dann zählt diese Prüfung.
  - die Teiletabelle (zeilen_schreiben, mat_set_protokoll_zeile) als Kopie vor dem Abschluss – je Teil die jüngste
    Prüfung im Lauf einschließlich Berichtigung oder die übernommene, je fehlender Position „fehlt“, je Bestandteil
    „vorhanden“ aus seiner Ja/Nein-Zeile, je im Lauf entnommenem Teil seine Prüfung.
  - Wirkung (wirkung): „einsatzbereit“ an einem gesperrten Set gibt frei – in derselben BEGIN-IMMEDIATE-Transaktion
    frisch gelesen (freigabe_gruende): kein Artikel mit eigener Sperre, verloren, mit offener (oder wieder offener)
    Meldung, offenem Entwurf, Status „neu“, „überfällig“ oder „Lebensdauer erreicht“ (Status ohne die Sperre gerechnet);
    das Set vollständig laut Kopie der Stückliste; jedes Teil im Prüfumfang im Lauf „einsatzbereit“, jedes übrige mit
    einer gültigen Prüfung „einsatzbereit“; keine Ausnahme zählt als geprüft. Dann EIN UPDATE über Set und Teile
    (sets.freigeben), zurück in die Heimat des Sets. Sonst bleibt es gesperrt, mit Gründen. „instandsetzen“ sperrt das
    Set (Kaskade), „aussondern“ ist „Set aussondern“ mit der Wahl je Teil (setaustausch.set_aussondern).
  - Gesamtergebnis: „einsatzbereit“, wenn das Set danach frei ist, sonst „gesperrt“ bzw. „ausgesondert“ – im Protokoll,
    im Journal am Set („set_geprueft“) und im Sammelprotokoll.
Berichtigungen geben nie frei (pruefung._wirkung_im_set); die Berichtigung der Set-Artikel-Prüfung übernimmt die
Teiletabelle des Originals (berichtigung_zeilen). Abbrechen (abbrechen): offene Teil-Entwürfe laufen als Einzelprüfungen
weiter, ein Lauf ohne Prüfung verschwindet; ein offener Entwurf am Set-Artikel muss vorher weg (verwerfen oder die
Reservierung aufheben). Hinweis, wenn zwischen der ersten Teilprüfung und dem Abschluss mehr als HINWEIS_TAGE liegen;
Prüftag des Set-Protokolls ist der Tag des Abschlusses.

Im Ordner-Durchgang (Entwurf E, A19): Set und Teile bleiben eigene Durchgangszeilen; „Set prüfen“ von dort setzt
round_id, die Prüfungen tragen wie jede ihren Durchgang. Ein offener Lauf hält keinen Durchgang auf und umgekehrt."""
import json
from datetime import date

from ... import db
from ..models import ERGEBNISSE
from . import Abgelehnt, auswahl, heute, kennung
from . import bestand, journal, katalog, sets
from . import status as st

SET_GRUPPE = "Bestandteile des Sets"
BESTANDTEIL_POS = 9000               # Position der Ja/Nein-Zeilen hinter den Formularpunkten
HINWEIS_TAGE = 7
GESAMT = {"einsatzbereit": "einsatzbereit", "gesperrt": "nicht einsatzbereit – Set gesperrt",
          "ausgesondert": "Set ausgesondert"}
NUR_IM_LAUF = ("Den Set-Artikel prüfst du über „Set prüfen“ – zusammen mit den Teilen in einer Set-Prüfung. Sie "
               "eröffnet, wer prüfen darf, an der Set-Seite.")
KEIN_LAUF = "Für dieses Set läuft keine Set-Prüfung."
NUR_SET = "„Set prüfen“ gibt es nur am Set-Artikel eines Hersteller-Sets."
VORHANDEN = {1: "vorhanden", 0: "fehlt", None: "nicht zutreffend"}
FREI_TROTZ_ERGEBNIS = ("In dieser Set-Prüfung wurde {nummern} nicht mit „einsatzbereit“ geprüft, das Set ist aber frei – "
                       "„einsatzbereit“ lässt sich so nicht festschreiben. Erst {nummern} sperren („Sperren“ am Teil), "
                       "dann das Set festschreiben.")


def _fmt(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return iso or ""


# --- Lesen ----------------------------------------------------------------------------------------------------------

def offener(set_id):
    return db.query("SELECT * FROM mat_set_lauf WHERE set_item_id = ? AND state = 'offen'", (set_id,), one=True)


def lauf(lid):
    r = db.query("SELECT * FROM mat_set_lauf WHERE id = ?", (lid,), one=True)
    if not r:
        raise Abgelehnt("Set-Prüfung nicht gefunden.", 404)
    return r


def _set_artikel(set_id):
    s = bestand.artikel(set_id)
    if s["parent_item_id"] or not sets.ist_set_artikel(s):
        raise Abgelehnt(NUR_SET, 409)
    return s


def uebernehmbar(t, lid=None, lp=None):
    """Zählt das Teil mit seiner letzten gültigen Prüfung außerhalb dieses Laufs (lid), ohne im Lauf geprüft zu werden?
    Nur mit einer solchen Prüfung „einsatzbereit“, die nicht überfällig ist – und, solange es im Lauf (lp) noch nicht
    geprüft ist, nicht „neu“ oder „überfällig“ (Status ohne die Sperre). Sonst gehört es von selbst zum Prüfumfang
    (Nachbesserung, Ablauf N1)."""
    alt = letzte_gueltige(t["id"], ohne_lauf=lid)
    if not alt or alt["result"] != "einsatzbereit" or not alt["next_due_on"] or alt["next_due_on"] < heute().isoformat():
        return False
    if lp is None or t["id"] not in lp:
        return st.status(dict(t, lock_state="frei")) not in ("neu", "ueberfaellig")
    return True


def umfang(s, teil_zeilen, lid=None, lp=None):
    """Die Teile (Kennungen), die im Lauf geprüft sein müssen – siehe Kopf; dazu jedes Teil ohne übernehmbare Prüfung
    (uebernehmbar). Ein Set, das selbst noch nie geprüft wurde, prüft alle Teile – auch wenn ein Teil es vorher gesperrt
    hat (L2b, Kritik U4): Sein erster Lauf sieht jeden Einbau, auch eingesetzte vorhandene Artikel mit gültiger Prüfung.
    lid/lp: der Lauf und seine Prüfungen (lauf_pruefungen) – ohne sie die Vorschau vor dem Eröffnen."""
    if s["lock_state"] == "frei" or s["set_lock_origin"] == "set" or not s["last_inspected_on"]:
        return [t["id"] for t in teil_zeilen]
    return [t["id"] for t in teil_zeilen if t["set_pruefen"] or not uebernehmbar(t, lid, lp)]


def lauf_pruefungen(lid):
    """{Artikel: jüngste im Lauf abgeschlossene Prüfung} – eine Berichtigung im Lauf ersetzt ihr Original."""
    out = {}
    for x in db.query("SELECT * FROM mat_inspection WHERE set_lauf_id = ? AND completed_at IS NOT NULL "
                      "AND kind <> 'aussonderung' ORDER BY completed_at, id", (lid,)):
        out[x["item_id"]] = x
    return out


def entwuerfe(lid):
    return db.query("SELECT * FROM mat_inspection WHERE set_lauf_id = ? AND completed_at IS NULL ORDER BY id", (lid,))


def letzte_gueltige(iid, ohne_lauf=None):
    """Die letzte gültige Prüfung eines Artikels: abgeschlossen, keine Aussonderung, nicht durch eine abgeschlossene
    Berichtigung ersetzt – die „übernommene“ im Set-Protokoll. ohne_lauf: Prüfungen dieses Laufs zählen nicht."""
    lauf_sql, args = ("AND (x.set_lauf_id IS NULL OR x.set_lauf_id <> ?) ", (iid, ohne_lauf)) if ohne_lauf else ("", (iid,))
    return db.query("SELECT x.* FROM mat_inspection x WHERE x.item_id = ? AND x.completed_at IS NOT NULL "
                    "AND x.kind <> 'aussonderung' " + lauf_sql + "AND NOT EXISTS (SELECT 1 FROM mat_inspection b WHERE "
                    "b.corrects_inspection_id = x.id AND b.completed_at IS NOT NULL) "
                    "ORDER BY x.completed_at DESC, x.id DESC LIMIT 1", args, one=True)


# Warum das Set (noch) nicht frei wird – je Grund ein ganzer Satz (Nachbesserung, Browser V4).
STATUS_SATZ = {"neu": "{nr} wurde noch nie geprüft – bitte jetzt prüfen.",
               "ueberfaellig": "Die Prüfung von {nr} ist überfällig – bitte jetzt prüfen.",
               "lebensdauer": "{nr} hat die Lebensdauer erreicht – das Teil tauschen oder das Set aussondern."}
NOCH_NICHT = "{nr} ist in dieser Set-Prüfung noch nicht geprüft."


def freigabe_gruende(s, teil_zeilen, lp, vorschau=False, lid=None):
    """Warum das Set (noch) nicht frei werden kann – leer heißt: Freigabe. Frisch gelesen in der Transaktion des Aufrufers
    (keine Zwischenspeicher der Anfrage wie mangel.offene_artikel). vorschau: vor dem Festschreiben des Set-Artikels –
    seine eigene Sperre, sein Mangel und sein Entwurf zählen dann nicht (die Prüfung, um die es geht, räumt sie ab).
    lid: der Lauf (für den Prüfumfang). Je Grund ein ganzer Satz."""
    from . import mangel, pruefung
    gruende = []
    umf = set(umfang(s, teil_zeilen, lid, lp))
    for x in [s] + list(teil_zeilen):
        nr, selbst = x["inventory_no"], x["id"] == s["id"]
        if not (vorschau and selbst):
            if x["lock_state"] == "verloren":
                gruende.append(f"{nr} ist verloren gemeldet.")
            elif sets._eigen_gesperrt(x):
                gruende.append(f"{nr} hat eine eigene Sperre ({x['lock_reason'] or 'ohne Angabe'}).")
            if mangel.offene_ids(x["id"]):
                gruende.append(f"An {nr} ist ein gemeldeter Mangel offen.")
            e = pruefung.offener_entwurf(x["id"])
            if e:
                gruende.append(f"{nr} ist in Prüfung bei {e['inspector_name'] or 'unbekannt'}.")
            status = st.status(dict(x, lock_state="frei"))
            if status in ("neu", "ueberfaellig", "lebensdauer"):
                gruende.append(STATUS_SATZ[status].format(nr=nr))
        elif x["retire_by"] and x["retire_by"] <= heute().isoformat():
            gruende.append(STATUS_SATZ["lebensdauer"].format(nr=nr))
    for t in teil_zeilen:
        x = lp.get(t["id"])
        if x and x["result"] != "einsatzbereit":
            gruende.append(f"{t['inventory_no']} wurde in der Set-Prüfung mit „{ERGEBNISSE.get(x['result'], x['result'])}“ "
                           "geprüft.")
        elif not x and t["id"] in umf:
            if st.status(dict(t, lock_state="frei")) not in ("neu", "ueberfaellig"):    # sonst sagt es der Satz oben
                gruende.append(NOCH_NICHT.format(nr=t["inventory_no"]))
        elif not x:
            alt = letzte_gueltige(t["id"])
            if not alt or alt["result"] != "einsatzbereit":
                gruende.append(f"{t['inventory_no']} hat keine gültige Prüfung mit „einsatzbereit“ – bitte jetzt prüfen.")
    voll, fehlend = sets.vollstaendigkeit(sets.slots(s["id"]), teil_zeilen)
    if not voll:
        gruende.append("Das Set ist unvollständig: " + ", ".join(f"„{f['bezeichnung']}“ fehlt" for f in fehlend) + ".")
    return gruende


# --- Eröffnen und abbrechen -------------------------------------------------------------------------------------------

def bestandteil_zeilen(pid, set_id):
    """Je nicht einzeln geführtem Bestandteil der Kopie eine Ja/Nein-Zeile „… vorhanden“ (Pflicht, nicht kritisch, ohne
    Formularpunkt) an der Prüfung des Set-Artikels – einmal (Entwurf E, A1). Was fehlt, ist ein Mangel wie jeder andere."""
    if db.query("SELECT 1 FROM mat_inspection_result WHERE inspection_id = ? AND checklist_item_id IS NULL "
                "AND group_name = ? LIMIT 1", (pid, SET_GRUPPE), one=True):
        return
    for n, z in enumerate(z for z in sets.slots(set_id) if not z["einzeln"]):
        text = z["bezeichnung"] + (f" ({z['anzahl']}×)" if z["anzahl"] > 1 else "") + " vorhanden"
        db.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_item_id, position, group_name, "
                   "checklist_text, editor, mandatory, expected_value, is_critical, finding, value) "
                   "VALUES (?, NULL, ?, ?, ?, 'yesno', 1, 'ja', 0, 'ok', 'ja')",
                   (pid, BESTANDTEIL_POS + n, SET_GRUPPE, text))


def eroeffnen(set_id, pruefer, durchgang_id=None):
    """„Set prüfen“: den Lauf eröffnen – oder den offenen liefern. durchgang_id: aus dem Ordner-Durchgang (der Set-Artikel
    muss dort offen sein – sonst 404 bzw. 409 wie beim Prüfen im Durchgang). Ohne durchgang_id übernimmt der Lauf den
    offenen Durchgang, in dem der Set-Artikel noch zu prüfen ist – dieselbe Regel wie pruefung.starten (Nachbesserung,
    Ablauf M2): Die Prüfungen ordnet der Dienst ihm ohnehin zu, der Lauf folgt ihnen. Liefert (Kennung, neu?)."""
    from . import durchgang, pruefung
    if not pruefer.get("urkunde"):
        raise Abgelehnt(pruefung.URKUNDE_FEHLT, 403)
    with db.transaction(sofort=True):
        s = _set_artikel(set_id)
        if s["lock_state"] == "ausgesondert":
            raise Abgelehnt("Ein ausgesondertes Set wird nicht mehr geprüft.", 409)
        ausdruecklich = bool(durchgang_id)
        if durchgang_id:
            durchgang.runde_fuer_start(durchgang_id, set_id)
        offen = offener(set_id)
        if not offen and not durchgang_id:
            durchgang_id = durchgang.offene_runde_fuer(set_id)
        if offen:
            if ausdruecklich and offen["round_id"] != durchgang_id:
                raise Abgelehnt("Für dieses Set läuft schon eine Set-Prüfung " + (
                    "in einem anderen Durchgang" if offen["round_id"] else "außerhalb dieses Durchgangs") +
                    " – erst abschließen oder abbrechen.", 409)
            return offen["id"], False
        lid = db.execute("INSERT INTO mat_set_lauf (set_item_id, round_id, opened_at, opened_by, opened_by_name, state) "
                         "VALUES (?,?,?,?,?,'offen')", (set_id, durchgang_id, db.now(), pruefer.get("id"), pruefer["name"]))
        _, tz = sets.zeilen(set_id)
        ids = [set_id] + [t["id"] for t in tz]
        # Wer an Set oder Teil schon prüft, prüft jetzt im Lauf – eine Berichtigung nicht (sie gehört zu ihrem Original).
        for e in db.query(f"SELECT id, item_id FROM mat_inspection WHERE completed_at IS NULL AND set_lauf_id IS NULL "
                          f"AND corrects_inspection_id IS NULL AND item_id IN ({','.join('?' * len(ids))})", ids):
            db.execute("UPDATE mat_inspection SET set_lauf_id = ? WHERE id = ?", (lid, e["id"]))
            journal.eintragen("inspection", e["id"], "geaendert", {"set_lauf_id": None}, {"set_lauf_id": lid})
            if e["item_id"] == set_id:
                bestandteil_zeilen(e["id"], set_id)
        journal.eintragen("item", set_id, "set_lauf_eroeffnet", None, {"lauf": lid, "round_id": durchgang_id})
    return lid, True


NUR_EROEFFNER = ("Eine Set-Prüfung bricht ab, wer sie begonnen hat ({name}), oder der Materialwart – sonst bitte dort "
                 "nachfragen.")


def abbrechen(set_id, akteur, darf_verwalten=False):
    """Den offenen Lauf beenden – nur, wer ihn eröffnet hat, oder wer den Ordner verwaltet (wie „Reservierung aufheben“;
    Nachbesserung, Sicherheit 1), sonst 403: Teil-Entwürfe darin laufen als Einzelprüfungen weiter; abgeschlossene
    Teilprüfungen bleiben Einzelprüfungen mit ihrem Protokoll. Ohne abgeschlossene Prüfung verschwindet der Lauf.
    Liefert, ob er bleibt."""
    with db.transaction(sofort=True):
        _set_artikel(set_id)
        lf = offener(set_id)
        if not lf:
            raise Abgelehnt(KEIN_LAUF, 409)
        if not darf_verwalten and not (akteur.get("id") and lf["opened_by"] == akteur.get("id")):
            raise Abgelehnt(NUR_EROEFFNER.format(name=lf["opened_by_name"] or "unbekannt"), 403)
        return beenden(lf)


def beenden(lf, grund=None):
    """Einen offenen Lauf abbrechen (in der Transaktion des Aufrufers) – siehe abbrechen; grund fürs Journal (etwa „Set
    ausgesondert“). Ein offener Entwurf am Set-Artikel muss vorher weg (409). Liefert, ob der Lauf bleibt."""
    set_id = lf["set_item_id"]
    e_set = db.query("SELECT * FROM mat_inspection WHERE set_lauf_id = ? AND item_id = ? AND completed_at IS NULL",
                     (lf["id"], set_id), one=True)
    if e_set:
        raise Abgelehnt(f"Die Prüfung des Set-Artikels ist offen (bei {e_set['inspector_name'] or 'unbekannt'}) – erst "
                        "verwerfen bzw. die Reservierung aufheben, dann die Set-Prüfung abbrechen.", 409)
    for e in entwuerfe(lf["id"]):
        db.execute("UPDATE mat_inspection SET set_lauf_id = NULL WHERE id = ?", (e["id"],))
        journal.eintragen("inspection", e["id"], "geaendert", {"set_lauf_id": lf["id"]}, {"set_lauf_id": None})
    n = db.query("SELECT COUNT(*) AS n FROM mat_inspection WHERE set_lauf_id = ?", (lf["id"],), one=True)["n"]
    zusatz = {"grund": grund} if grund else {}
    if not n:
        db.execute("DELETE FROM mat_set_lauf WHERE id = ?", (lf["id"],))
        journal.eintragen("item", set_id, "set_lauf_abgebrochen", None, dict({"lauf": lf["id"], "geprueft": 0}, **zusatz))
        return False
    db.execute("UPDATE mat_set_lauf SET state = 'abgebrochen', closed_at = ? WHERE id = ?", (db.now(), lf["id"]))
    journal.eintragen("item", set_id, "set_lauf_abgebrochen", None, dict({"lauf": lf["id"], "geprueft": n}, **zusatz))
    return True


# --- Abschluss: Festschreiben der Prüfung des Set-Artikels -------------------------------------------------------------

def _verbleib(roh, teil_zeilen):
    """„verbleib“ beim Ergebnis „aussondern“ und bei „Set aussondern“: [{"teil_id", "verbleib": "aussondern" |
    "weiterfuehren"}] – was fehlt, bekommt die Vorbelegung (sets.verbleib_vorschlag). Ein Teil, das nicht zu diesem Set
    gehört: 404 wie unbekannt. Liefert {Teil: Verbleib}."""
    vb = {t["id"]: sets.verbleib_vorschlag(t) for t in teil_zeilen}
    if roh is None:
        return vb
    if not isinstance(roh, list) or len(roh) > 200:
        raise Abgelehnt("„verbleib“ muss eine Liste aus {teil_id, verbleib} sein.")
    for n, e in enumerate(roh, start=1):
        if not isinstance(e, dict):
            raise Abgelehnt(f"„verbleib“, Eintrag {n}: kein Objekt.")
        tid = kennung(e.get("teil_id"), "Teil")
        if tid not in vb:
            raise Abgelehnt(sets.TEIL_FEHLT, 404)
        vb[tid] = auswahl(e.get("verbleib"), sets.VERBLEIB, "Verbleib")
    return vb


def vorbereiten(p, item, ergebnis, d, tag):
    """Vor dem Festschreiben der Set-Artikel-Prüfung, in deren Transaktion: Lauf offen, kein anderer Entwurf darin,
    Prüfumfang vollständig geprüft (sonst 409), „verbleib“ bei „aussondern“. Liefert den Stand für zeilen_schreiben und
    wirkung."""
    lf = lauf(p["set_lauf_id"])
    if lf["state"] != "offen" or lf["set_item_id"] != item["id"]:
        raise Abgelehnt("Diese Set-Prüfung ist schon beendet – den Set-Artikel prüft man in einer offenen Set-Prüfung.", 409)
    s, tz = sets.zeilen(item["id"])
    andere = [e for e in entwuerfe(lf["id"]) if e["id"] != p["id"]]
    if andere:
        nummern = {r["id"]: r["inventory_no"] for r in tz}
        raise Abgelehnt("In der Set-Prüfung ist noch eine Prüfung offen: " + ", ".join(
            f"{nummern.get(e['item_id'], 'Teil')} ({e['inspector_name'] or 'unbekannt'})" for e in andere) +
            " – erst festschreiben oder verwerfen.", 409)
    lp = lauf_pruefungen(lf["id"])
    umf = umfang(s, tz, lf["id"], lp)
    fehlen = [t["inventory_no"] for t in tz if t["id"] in umf and t["id"] not in lp]
    if fehlen:
        raise Abgelehnt("In der Set-Prüfung noch nicht geprüft: " + ", ".join(fehlen) + " – erst prüfen (oder das Teil "
                        "über „Teil entnehmen“ aus dem Set nehmen).", 409)
    teile_lp = [x["inspected_on"] for iid, x in lp.items() if iid != item["id"]]
    tage = (date.fromisoformat(tag) - date.fromisoformat(min(teile_lp))).days if teile_lp else 0
    hinweis = (f"Zwischen der ersten Teilprüfung ({_fmt(min(teile_lp))}) und dem Abschluss liegen {tage} Tage."
               if tage > HINWEIS_TAGE else "")
    return {"lauf": lf, "s": s, "tz": tz, "lp": lp, "umfang": umf, "tage": tage, "hinweis": hinweis,
            "verbleib": _verbleib(d.get("verbleib"), tz) if ergebnis == "aussondern" else None}


def _vorhanden(pid):
    """Die Ja/Nein-Zeilen der Bestandteile (SET_GRUPPE) in Reihenfolge: 1 vorhanden, 0 fehlt, None nicht zutreffend."""
    out = []
    for r in db.query("SELECT finding, value FROM mat_inspection_result WHERE inspection_id = ? AND checklist_item_id IS NULL "
                      "AND group_name = ? ORDER BY position, id", (pid, SET_GRUPPE)):
        out.append(None if r["finding"] == "nicht_zutreffend" else 1 if r["value"] == "ja" else 0)
    return out


def zeilen_schreiben(p, v):
    """Die Teiletabelle als Kopie (mat_set_protokoll_zeile) – vor dem Abschluss der Prüfung (die Trigger nehmen nur Zeilen
    am offenen Entwurf an). Siehe Kopf."""
    s, tz, lp = v["s"], v["tz"], v["lp"]
    sz = sets.slots(s["id"])
    zu, _ = sets._zuteilen(sz, tz)
    vorhanden = iter(_vorhanden(p["id"]))
    zeilen = []

    def teil(pos, bez, t):
        x, ueb = lp.get(t["id"]), 0
        if not x:
            x, ueb = letzte_gueltige(t["id"]), 1
        zeilen.append(("teil", pos, bez, t["serial_no"], t["inventory_no"], x["result"] if x else None,
                       x["protocol_id"] if x else None, x["file_sha256"] if x else None, None, ueb if x else 0))

    for z in sz:
        if not z["einzeln"]:
            zeilen.append(("bestandteil", z["position"], z["bezeichnung"] + (f" ({z['anzahl']}×)" if z["anzahl"] > 1 else ""),
                           "", "", None, None, None, next(vorhanden, None), 0))
            continue
        stuecke = [t for t in tz if zu.get(t["id"]) is z]
        for t in stuecke:
            teil(z["position"], z["bezeichnung"], t)
        for _ in range(z["anzahl"] - len(stuecke)):
            zeilen.append(("teil", z["position"], z["bezeichnung"], "", "", None, None, None, 0, 0))
    hinten = max([z["position"] for z in sz] or [0]) + 1
    for t in tz:
        if t["id"] not in zu:                                   # mehr Stücke als die Kopie nennt (Altbestand)
            teil(hinten, katalog.produktname(katalog.produkt(t["product_id"])), t)
    aktuell = {t["id"] for t in tz} | {s["id"]}
    for iid, x in lp.items():
        if iid not in aktuell:                                  # im Lauf geprüft, inzwischen entnommen
            a = bestand.artikel(iid)
            zeilen.append(("teil", hinten, katalog.produktname(katalog.produkt(a["product_id"])) + " – im Lauf entnommen",
                           a["serial_no"], a["inventory_no"], x["result"], x["protocol_id"], x["file_sha256"], None, 0))
    for z in zeilen:
        db.execute("INSERT INTO mat_set_protokoll_zeile (inspection_id, art, position, bezeichnung, seriennummer, "
                   "inventarnummer, ergebnis, protokoll_id, pruefsumme, vorhanden, uebernommen) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (p["id"],) + z)


def berichtigung_zeilen(neu, alt):
    """Berichtigung der Set-Artikel-Prüfung: die Teiletabelle des Originals unverändert übernehmen (Entwurf E, S19)."""
    db.execute("INSERT INTO mat_set_protokoll_zeile (inspection_id, art, position, bezeichnung, seriennummer, "
               "inventarnummer, ergebnis, protokoll_id, pruefsumme, vorhanden, uebernommen) "
               "SELECT ?, art, position, bezeichnung, seriennummer, inventarnummer, ergebnis, protokoll_id, pruefsumme, "
               "vorhanden, uebernommen FROM mat_set_protokoll_zeile WHERE inspection_id = ? ORDER BY id", (neu, alt))


def gesamt_von(s):
    return ("ausgesondert" if s["lock_state"] == "ausgesondert" else "einsatzbereit" if s["lock_state"] == "frei"
            else "gesperrt")


def wirkung(item, p, ergebnis, tag, naechste, grund, pruefer, ts, v):
    """Was das Festschreiben der Set-Artikel-Prüfung bewirkt (statt pruefung._wirkung) und der Abschluss des Laufs – in
    dessen Transaktion. Liefert {gesamt, freigegeben, gruende}."""
    from . import mangel, pruefung, setaustausch
    sid = item["id"]
    s0, _ = sets.zeilen(sid)
    freigegeben, gruende = False, None
    vorher = {"lock_state": s0["lock_state"], "lock_cause": s0["lock_cause"], "next_due_on": s0["next_due_on"],
              "last_inspected_on": s0["last_inspected_on"], "folder_id": s0["folder_id"],
              "ordner": bestand._pfad_text(s0["folder_id"])}
    zusatz = {"pruefung": p["id"], "ergebnis": ergebnis, "art": p["kind"], "lauf": v["lauf"]["id"]}
    if ergebnis == "einsatzbereit":
        db.execute("UPDATE mat_item SET next_due_on = ?, last_inspected_on = ?, updated_at = ? WHERE id = ?",
                   (naechste, tag, db.now(), sid))
        mangel.erledigen(sid, p["id"])
        if s0["lock_state"] == "frei":
            # Absicherung (Prüfung Sicherheit, H1): Ein freies Set mit einem Teil, das in diesem Lauf schlechter als
            # „einsatzbereit“ geprüft wurde, darf nicht „einsatzbereit“ heißen – dessen Ergebnis hätte das Set sperren
            # müssen. Kommt nur bei unstimmigen Daten vor; dann nichts festschreiben.
            _, tz0 = sets.zeilen(sid)
            lp0 = lauf_pruefungen(v["lauf"]["id"])
            schlecht = [t["inventory_no"] for t in tz0 if t["id"] in lp0 and lp0[t["id"]]["result"] != "einsatzbereit"]
            if schlecht:
                raise Abgelehnt(FREI_TROTZ_ERGEBNIS.format(nummern=", ".join(schlecht)), 409)
            alt, neu = journal.unterschied(vorher, dict(vorher, next_due_on=naechste, last_inspected_on=tag))
            journal.eintragen("item", sid, "geprueft", alt, dict(neu, **zusatz))
        else:
            if s0["lock_cause"] == "eigen" or s0["lock_state"] == "verloren":
                sets.eigen_aufheben(s0)
            s, tz = sets.zeilen(sid)
            gruende = freigabe_gruende(s, tz, lauf_pruefungen(v["lauf"]["id"]), lid=v["lauf"]["id"])
            if not gruende:
                ziel = pruefung._rueckweg(s)
                sets.freigeben(sid, ziel)
                journal.eintragen("item", sid, "freigeprueft", vorher,
                                  dict({"lock_state": "frei", "lock_cause": None, "next_due_on": naechste,
                                        "last_inspected_on": tag, "folder_id": ziel, "ordner": bestand._pfad_text(ziel),
                                        "teile": len(tz)}, **zusatz))
                freigegeben = True
            else:
                alt, neu = journal.unterschied(vorher, dict(vorher, lock_state=s["lock_state"], lock_cause=s["lock_cause"],
                                                            next_due_on=naechste, last_inspected_on=tag))
                journal.eintragen("item", sid, "geprueft", alt, dict(neu, **zusatz))
    elif ergebnis == "instandsetzen":
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), sid))
        if s0["lock_cause"] == "eigen":
            journal.eintragen("item", sid, "geprueft", {"last_inspected_on": s0["last_inspected_on"]},
                              dict({"last_inspected_on": tag}, **zusatz))
        else:
            sperrgrund = f"Prüfung vom {_fmt(tag)}: instandsetzen" + (f" – {grund}" if grund else "")
            sets.sperren(sid, eigen=sid, grund=sperrgrund, zusatz={"pruefung": p["id"]})
    else:
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), sid))
        setaustausch.set_aussondern(bestand.artikel(sid), "Prüfergebnis „aussondern“" + (f": {grund}" if grund else ""),
                                    "", tag, pruefer, v["verbleib"], basis_id=p["id"], ts=ts, ausser_lauf=v["lauf"]["id"])
    s, tz = sets.zeilen(sid)
    gesamt = gesamt_von(s)
    # Warum das Set gesperrt bleibt: nach „einsatzbereit“ die Gründe gegen die Freigabe, sonst die Sperrgründe.
    if gesamt != "gesperrt":
        gruende = []
    elif gruende is None:
        gruende = [g["text"] for g in sets.sperrgruende(s, tz) if g["art"] != "set_pruefung"]
    if not db.execute_zeilen("UPDATE mat_set_lauf SET state = 'abgeschlossen', closed_at = ?, set_inspection_id = ? "
                             "WHERE id = ? AND state = 'offen'", (ts, p["id"], v["lauf"]["id"])):
        raise Abgelehnt("Die Set-Prüfung wurde inzwischen beendet.", 409)
    journal.eintragen("item", sid, "set_geprueft", None,
                      {"lauf": v["lauf"]["id"], "pruefung": p["id"], "gesamtergebnis": gesamt, "freigegeben": freigegeben,
                       "gruende": gruende, "hinweis": v["hinweis"]})
    return {"gesamt": gesamt, "freigegeben": freigegeben, "gruende": gruende}


# --- Antworten --------------------------------------------------------------------------------------------------------

def _abschluss(lid):
    """Der Journaleintrag „set_geprueft“ eines Laufs: {gesamtergebnis, freigegeben, gruende, hinweis, pruefung} – oder {}."""
    r = db.query("SELECT a.after_json FROM mat_audit a JOIN mat_set_lauf l ON l.set_item_id = a.entity_id "
                 "WHERE l.id = ? AND a.entity = 'item' AND a.action = 'set_geprueft' "
                 "AND json_extract(a.after_json, '$.lauf') = l.id ORDER BY a.id DESC LIMIT 1", (lid,), one=True)
    return json.loads(r["after_json"]) if r else {}


def kurz(lf):
    """Ein Lauf für Listen und den Set-Block: {id, state, round_id, durchgang, opened_at, opened_by_name, closed_at,
    set_inspection_id, gesamtergebnis, gesamt_text, protokoll_id} – die letzten drei nur beim abgeschlossenen Lauf (sonst
    None; für „Frühere Set-Prüfungen“). None ohne Lauf."""
    if not lf:
        return None
    from . import durchgang
    gesamt, protokoll_id = None, None
    if lf["state"] == "abgeschlossen":
        gesamt = _abschluss(lf["id"]).get("gesamtergebnis")
        if lf["set_inspection_id"]:
            x = db.query("SELECT protocol_id FROM mat_inspection WHERE id = ?", (lf["set_inspection_id"],), one=True)
            protokoll_id = x["protocol_id"] if x else None
    return {"id": lf["id"], "state": lf["state"], "round_id": lf["round_id"],
            "durchgang": durchgang.verweis(lf["round_id"]) if lf["round_id"] else None, "opened_at": lf["opened_at"],
            "opened_by_name": lf["opened_by_name"], "closed_at": lf["closed_at"],
            "set_inspection_id": lf["set_inspection_id"], "gesamtergebnis": gesamt,
            "gesamt_text": GESAMT.get(gesamt) if gesamt else None, "protokoll_id": protokoll_id}


def _pruefung_kurz(x):
    return {"id": x["id"], "ergebnis": x["result"], "ergebnis_text": ERGEBNISSE.get(x["result"], ""),
            "datum": x["inspected_on"], "pruefer": x["inspector_name"], "protokoll_id": x["protocol_id"]}


def lauf_json(lf, pruefer_id=None):
    """Ein Lauf voll – für „Set prüfen“: kurz() und
      umfang      je aktuellem Teil (soweit sichtbar) {teil {id, inventory_no, serial_no, bestandteil}, zu_pruefen,
                  pruefung (im Lauf, die jüngste) | null, entwurf {id, pruefer, eigen} | null, uebernommen (letzte gültige
                  Prüfung, wenn nicht im Lauf geprüft) | null}
      set_pruefung  die Prüfung des Set-Artikels im Lauf {id, entwurf, pruefer, eigen} | null
      fortschritt {geprueft, zu_pruefen, teile}; bereit: der Set-Artikel lässt sich jetzt festschreiben (alles im Umfang
                  geprüft, kein Teil-Entwurf offen)
      freigabe_gruende  was eine Freigabe jetzt noch verhindert (nur bei gesperrtem Set; Vorschau ohne den Set-Artikel)
      hinweis_tage      Tage seit der ersten Teilprüfung im Lauf, wenn mehr als HINWEIS_TAGE – sonst 0
      abschluss         beim beendeten Lauf: {gesamtergebnis, gesamt_text, freigegeben, gruende, hinweis} | null"""
    out = kurz(lf)
    out["eigen"] = bool(pruefer_id) and lf["opened_by"] == pruefer_id        # eröffnet von diesem Konto (abbrechen)
    s, tz_alle = sets.zeilen(lf["set_item_id"])
    sichtbar = {t["id"] for t in sets.teile(s["id"])}
    tz = [t for t in tz_alle if t["id"] in sichtbar]
    lp = lauf_pruefungen(lf["id"])
    umf = set(umfang(s, tz_alle, lf["id"], lp))
    zu, _ = sets._zuteilen(sets.slots(s["id"]), tz_alle)
    offen = {e["item_id"]: e for e in entwuerfe(lf["id"])}
    liste = []
    for t in tz:
        x = lp.get(t["id"])
        ueb = None if x else letzte_gueltige(t["id"])
        e = offen.get(t["id"])
        z = zu.get(t["id"])
        liste.append({"teil": {"id": t["id"], "inventory_no": t["inventory_no"], "serial_no": t["serial_no"],
                               "bestandteil": z["bezeichnung"] if z else None},
                      "zu_pruefen": t["id"] in umf, "pruefung": _pruefung_kurz(x) if x else None,
                      "entwurf": ({"id": e["id"], "pruefer": e["inspector_name"],
                                   "eigen": bool(pruefer_id) and e["inspector_user_id"] == pruefer_id} if e else None),
                      "uebernommen": _pruefung_kurz(ueb) if ueb else None})
    out["umfang"] = liste
    xs = lp.get(s["id"]) or offen.get(s["id"])
    out["set_pruefung"] = ({"id": xs["id"], "entwurf": xs["completed_at"] is None, "pruefer": xs["inspector_name"],
                            "eigen": bool(pruefer_id) and xs["inspector_user_id"] == pruefer_id} if xs else None)
    geprueft = sum(1 for t in tz_alle if t["id"] in umf and t["id"] in lp)
    out["fortschritt"] = {"geprueft": geprueft, "zu_pruefen": len(umf), "teile": len(tz_alle)}
    out["bereit"] = lf["state"] == "offen" and geprueft == len(umf) and not [e for i, e in offen.items() if i != s["id"]]
    out["freigabe_gruende"] = (freigabe_gruende(s, tz_alle, lp, vorschau=True, lid=lf["id"])
                               if lf["state"] == "offen" and s["lock_state"] != "frei" else [])
    teile_lp = [x["inspected_on"] for iid, x in lp.items() if iid != s["id"]]
    tage = (heute() - date.fromisoformat(min(teile_lp))).days if teile_lp else 0
    out["hinweis_tage"] = tage if tage > HINWEIS_TAGE else 0
    a = _abschluss(lf["id"]) if lf["state"] == "abgeschlossen" else {}
    out["abschluss"] = (dict({k: a.get(k) for k in ("gesamtergebnis", "freigegeben", "gruende", "hinweis")},
                             gesamt_text=GESAMT.get(a.get("gesamtergebnis"), "")) if a else None)
    return out


def laeufe(set_id, grenze=20):
    """Die Läufe eines Sets, neueste zuerst (kurz)."""
    return [kurz(r) for r in db.query("SELECT * FROM mat_set_lauf WHERE set_item_id = ? ORDER BY id DESC LIMIT ?",
                                      (set_id, grenze))]


def letzte(set_id):
    """Die zuletzt abgeschlossene Set-Prüfung für den Set-Block: {lauf, pruefung_id, protokoll_id, datum, gesamtergebnis,
    gesamt_text, freigegeben, berichtigt_durch (der Set-Artikel-Prüfung), berichtigte_teile [{inventarnummer,
    protokoll_id, durch}] – Teilprüfungen aus der Tabelle, die nach dem Protokoll berichtigt wurden (S19)} – oder None."""
    lf = db.query("SELECT * FROM mat_set_lauf WHERE set_item_id = ? AND state = 'abgeschlossen' ORDER BY id DESC LIMIT 1",
                  (set_id,), one=True)
    if not lf or not lf["set_inspection_id"]:
        return None
    x = db.query("SELECT id, protocol_id, inspected_on FROM mat_inspection WHERE id = ?", (lf["set_inspection_id"],),
                 one=True)
    a = _abschluss(lf["id"])
    durch = db.query("SELECT protocol_id FROM mat_inspection WHERE corrects_inspection_id = ? AND completed_at IS NOT NULL",
                     (x["id"],), one=True)
    berichtigt = []
    for r in db.query("SELECT z.inventarnummer, z.protokoll_id, b.protocol_id AS durch FROM mat_set_protokoll_zeile z "
                      "JOIN mat_inspection o ON o.protocol_id = z.protokoll_id "
                      "JOIN mat_inspection b ON b.corrects_inspection_id = o.id AND b.completed_at IS NOT NULL "
                      "WHERE z.inspection_id = ? AND z.art = 'teil' AND z.protokoll_id IS NOT NULL ORDER BY z.id", (x["id"],)):
        berichtigt.append({"inventarnummer": r["inventarnummer"], "protokoll_id": r["protokoll_id"], "durch": r["durch"]})
    return {"lauf": lf["id"], "pruefung_id": x["id"], "protokoll_id": x["protocol_id"], "datum": x["inspected_on"],
            "gesamtergebnis": a.get("gesamtergebnis"), "gesamt_text": GESAMT.get(a.get("gesamtergebnis"), ""),
            "freigegeben": a.get("freigegeben"), "berichtigt_durch": durch["protocol_id"] if durch else None,
            "berichtigte_teile": berichtigt}


def protokoll_zeilen(pid):
    """Die Teiletabelle einer Prüfung fürs Protokoll und die Schnittstelle – leer, wenn sie kein Set-Protokoll ist."""
    return [{"art": r["art"], "bezeichnung": r["bezeichnung"], "inventarnummer": r["inventarnummer"],
             "seriennummer": r["seriennummer"], "ergebnis": r["ergebnis"],
             "ergebnis_text": ERGEBNISSE.get(r["ergebnis"], "") if r["ergebnis"] else "",
             "protokoll_id": r["protokoll_id"] or "", "pruefsumme": r["pruefsumme"] or "",
             "vorhanden": None if r["vorhanden"] is None else bool(r["vorhanden"]),
             "vorhanden_text": (VORHANDEN[r["vorhanden"]] if r["art"] == "bestandteil" or r["vorhanden"] == 0 else ""),
             "uebernommen": bool(r["uebernommen"])}
            for r in db.query("SELECT * FROM mat_set_protokoll_zeile WHERE inspection_id = ? ORDER BY position, id", (pid,))]


def protokoll_daten(p):
    """Der Set-Teil des P-Protokolls der Set-Artikel-Prüfung (pruefprotokoll.html) – None für jede andere Prüfung:
    {zeilen, gesamt, gesamt_text, freigegeben, gruende, hinweis, berichtigung}. Beim Abschluss eines Laufs aus seinem
    Journaleintrag „set_geprueft“ (in derselben Transaktion geschrieben); bei einer Berichtigung aus dem Stand des Sets
    (sie gibt nie frei)."""
    zeilen = protokoll_zeilen(p["id"])
    if not zeilen:
        return None
    a = _abschluss(p["set_lauf_id"]) if p["set_lauf_id"] else {}
    if a and a.get("pruefung") == p["id"]:
        gesamt, gruende = a["gesamtergebnis"], a.get("gruende") or []
        return {"zeilen": zeilen, "gesamt": gesamt, "gesamt_text": GESAMT[gesamt], "freigegeben": bool(a.get("freigegeben")),
                "gruende": gruende, "hinweis": a.get("hinweis") or "", "berichtigung": False}
    s, tz = sets.zeilen(p["item_id"])
    gesamt = gesamt_von(s)
    gruende = [g["text"] for g in sets.sperrgruende(s, tz) if g["art"] != "set_pruefung"] if gesamt == "gesperrt" else []
    return {"zeilen": zeilen, "gesamt": gesamt, "gesamt_text": GESAMT[gesamt], "freigegeben": False, "gruende": gruende,
            "hinweis": "Die Teiletabelle ist die des berichtigten Protokolls; eine Berichtigung gibt das Set nie frei.",
            "berichtigung": True}


def pruefung_teil(p, item):
    """Für pruefung.pruefung_json: {set_lauf (kurz, mit rolle „set“ | „teil“ und dem Set {id, inventory_no}) | None,
    set_abschluss (am Entwurf des Set-Artikels: lauf_json des Laufs und verbleib_vorschlag je Teil) | None,
    set_protokoll (abgeschlossen: protokoll_zeilen und Gesamtergebnis) | None}."""
    out = {"set_lauf": None, "set_abschluss": None, "set_protokoll": None}
    if p["set_lauf_id"]:
        lf = lauf(p["set_lauf_id"])
        s = sets.set_zeile(lf["set_item_id"], gefiltert=False)
        out["set_lauf"] = dict(kurz(lf), rolle="set" if item["id"] == lf["set_item_id"] else "teil",
                               set={"id": s["id"], "inventory_no": s["inventory_no"]})
        if p["completed_at"] is None and item["id"] == lf["set_item_id"] and lf["state"] == "offen":
            _, tz = sets.zeilen(s["id"])
            out["set_abschluss"] = dict(lauf_json(lf), verbleib_vorschlag=[
                {"teil_id": t["id"], "inventory_no": t["inventory_no"], "verbleib": sets.verbleib_vorschlag(t)} for t in tz])
    if p["completed_at"]:
        d = protokoll_daten(p)
        if d:
            out["set_protokoll"] = d
    return out


def sammel(rid):
    """Für das Sammelprotokoll eines Durchgangs: {Set-Artikel: Gesamtergebnis-Text} der in diesem Durchgang
    abgeschlossenen Set-Prüfungen (die jüngste je Set) – auch einer, die außerhalb begonnen wurde, deren Prüfung des
    Set-Artikels aber im Durchgang zählt (Nachbesserung, Ablauf M2)."""
    out = {}
    for lf in db.query("SELECT l.* FROM mat_set_lauf l WHERE l.state = 'abgeschlossen' AND (l.round_id = ? OR EXISTS "
                       "(SELECT 1 FROM mat_inspection x WHERE x.id = l.set_inspection_id AND x.round_id = ?)) "
                       "ORDER BY l.id", (rid, rid)):
        a = _abschluss(lf["id"])
        if a:
            out[lf["set_item_id"]] = GESAMT.get(a.get("gesamtergebnis"), "")
    return out
