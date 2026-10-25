"""Prüfdurchgänge: die Jahresprüfung eines Ordners mit mehreren Prüfern zugleich.

Ein Materialwart oder Prüfer eröffnet den Durchgang für einen Ordner. Alle Artikel darin und in den
Unterordnern kommen auf eine gemeinsame Liste (mat_round_item) – auch gesperrte, die aus diesem Zweig
nach „Gesperrt“ gewandert sind (Herkunftsordner im Zweig), ausgesonderte nicht. Die Liste steht fest ab
der Eröffnung, auch wenn ein Artikel währenddessen gesperrt und damit verschoben wird. Ein Entwurf, der
vor der Eröffnung begonnen wurde, zählt mit. Je Artikel gilt:

  erledigt       eine im Durchgang abgeschlossene Prüfung (gleich mit welchem Ergebnis)
  ausgenommen    mit Grund herausgenommen („nicht auffindbar“, „in Reparatur beim Hersteller“ …)
  in Prüfung     jemand hat ihn geöffnet: Der offene Entwurf ist die Reservierung (höchstens einer
                 je Artikel, siehe pruefung.py) – die anderen sehen „in Prüfung bei …“
  offen          sonst

Abschließen lässt sich der Durchgang erst, wenn jeder Artikel erledigt oder ausgenommen ist und kein
Entwurf des Durchgangs mehr offen ist. Dann wird mit dem Schließen das Sammelprotokoll festgeschrieben
(protokoll.py): alle Artikel mit Ergebnis, Ausnahmen mit Grund, alle beteiligten Prüfer mit Urkundennummer
und Unterschrift, die Einzelprotokolle mit ihrer Prüfsumme – festgeschrieben wie jedes Protokoll; danach
ist der Durchgang unveränderlich. Ein Artikel steht höchstens in einem offenen Durchgang.

Seit Schritt 27 bekommt beim regulären Abschluss jeder Ordner der Art „Set“ unterhalb des Durchgangsordners, in dem
mindestens ein Artikel geprüft wurde, zusätzlich sein Set-Protokoll (protokoll.durchgang_festschreiben, set_protokoll_json).
Seit der Prüfung vom 25.10.2026 entstehen die PDFs vor der Schreibtransaktion (_beenden).

Abbrechen beendet ihn vorzeitig: Offene Prüfungen darin laufen als einzelne Prüfungen weiter. Wurde noch
nichts abgeschlossen, verschwindet er ganz; sonst endet er als „abgebrochen“ – Geprüftes und
Ausgenommenes bleibt ihm zugeordnet, jeder andere Artikel steht darin als „nicht geprüft“ – auch im
Sammelprotokoll, das ein abgebrochener Durchgang ebenso bekommt.

Seit Phase 2 gehört ein Artikel über seine Heimat (bestand.heimat) zum Zweig eines Durchgangs. Verlässt er ihn durch
ein Verschieben, nimmt nach_verschieben ihn mit Grund heraus; geprüft wird in einem Durchgang nur, was dort zu Hause ist
(offene_runde_fuer, runde_fuer_start). Sehen darf einen Durchgang, wer seinen Ordner sehen darf – vollständig: Zeilen
mit Artikeln, die das Konto nicht sieht, stehen ohne Link da („sichtbar“: false)."""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import date

from flask import current_app, g

from ... import db
from . import Abgelehnt, heute, text
from . import bestand, journal, protokoll, rechte

# Bedingung für Abfragen über mat_inspection: ohne Prüfungen, deren Berichtigung im selben Durchgang abgeschlossen ist.
OHNE_BERICHTIGTE = ("AND NOT EXISTS (SELECT 1 FROM mat_inspection b WHERE b.corrects_inspection_id = mat_inspection.id "
                    "AND b.round_id = mat_inspection.round_id AND b.completed_at IS NOT NULL) ")

ZUSTAND_TEXT = {"offen": "offen", "in_pruefung": "in Prüfung", "erledigt": "erledigt", "ausgenommen": "ausgenommen",
                "nicht_geprueft": "nicht geprüft"}
# Ordnerspalte eines Artikels, dessen Heimat den Zweig verlassen hat (1.7 Nr. 7) – nie ein Pfad aus einem fremden Bereich.
AUS_DEM_BEREICH = "(aus dem Bereich des Durchgangs verschoben)"
NICHT_IM_BEREICH = "Der Artikel liegt nicht mehr im Bereich dieses Durchgangs – er bleibt ausgenommen."


def _fmt(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return iso or ""


def _im_zweig(r, item):
    """Liegt die Heimat des Artikels im Zweig des Durchgangs (dessen Ordner oder darunter)?"""
    return r["folder_id"] in bestand.kette(bestand.heimat(item))


def runde(rid):
    r = db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
    if not r:
        raise Abgelehnt("Prüfdurchgang nicht gefunden.", 404)
    return r


def _erledigt(rid, iid):
    return db.query("SELECT 1 FROM mat_inspection WHERE round_id = ? AND item_id = ? AND completed_at IS NOT NULL "
                    "LIMIT 1", (rid, iid), one=True) is not None


def offene_runde_fuer(iid):
    """Der offene Durchgang, in dem der Artikel noch zu prüfen ist (nicht ausgenommen, nicht erledigt) – nur einer, in
    dessen Zweig seine Heimat liegt (1.7 Nr. 5). Nach nach_verschieben ist das eine Absicherung, kein Normalfall."""
    i = db.query("SELECT folder_id, origin_folder_id, lock_state FROM mat_item WHERE id = ?", (iid,), one=True)
    if not i:
        return None
    kette = json.dumps(sorted(bestand.kette(bestand.heimat(i))))
    r = db.query("SELECT r.id FROM mat_round r JOIN mat_round_item ri ON ri.round_id = r.id "
                 "WHERE r.closed_on IS NULL AND ri.item_id = ? AND ri.excluded_reason IS NULL "
                 "AND r.folder_id IN (SELECT value FROM json_each(?)) "
                 "AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.round_id = r.id AND x.item_id = ri.item_id "
                 "AND x.completed_at IS NOT NULL) ORDER BY r.id DESC LIMIT 1", (iid, kette), one=True)
    return r["id"] if r else None


def verweis(rid):
    """Ein Durchgang, wie er an Artikel und Prüfung steht – einheitlich {id, titel, ordner, sichtbar}. Titel und Ordner
    gehören zur Geschichte des Artikels und stehen immer da; „sichtbar“ sagt, ob das Konto den Durchgang öffnen darf
    (nur dann verlinkt die Oberfläche)."""
    r = db.query("SELECT id, title, folder_id FROM mat_round WHERE id = ?", (rid,), one=True)
    if not r:
        return None
    return {"id": r["id"], "titel": r["title"], "ordner": bestand._pfad_text(r["folder_id"]),
            "sichtbar": rechte.darf("lesen", r["folder_id"])}


def runde_des_artikels(rid, iid):
    """(Durchgang, Zeile) – nur, wenn der Artikel darin steht und seine Heimat im Zweig liegt. Unbekannt, der Artikel
    nicht darin oder die Heimat nicht im Zweig: überall dieselbe 404 wie „gibt es nicht“ (1.7 Nr. 5) – so verrät eine
    durchgang_id aus einem fremden Bereich nichts."""
    r = db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
    ri = db.query("SELECT * FROM mat_round_item WHERE round_id = ? AND item_id = ?", (rid, iid), one=True) if r else None
    if not ri or not _im_zweig(r, bestand.artikel(iid)):
        raise Abgelehnt(rechte.DURCHGANG_FEHLT, 404)
    return r, ri


def runde_fuer_start(rid, iid):
    """Prüfung ausdrücklich in diesem Durchgang beginnen – nur, wenn der Artikel dort noch offen ist (sonst 409);
    fremd oder unbekannt: 404 (runde_des_artikels)."""
    r, ri = runde_des_artikels(rid, iid)
    if r["closed_on"]:
        raise Abgelehnt("Der Durchgang ist abgeschlossen.", 409)
    if ri["excluded_reason"]:
        raise Abgelehnt("Der Artikel ist aus dem Durchgang ausgenommen – erst wieder einbeziehen.", 409)
    if _erledigt(rid, iid):
        raise Abgelehnt("Der Artikel ist in diesem Durchgang schon geprüft.", 409)
    return rid


def eroeffnen(fid, d, akteur):
    titel = text(d, "titel", "Titel", 160, pflicht=True)
    # Zu Hause im Zweig – gesperrte zählen bei ihrem Herkunftsordner, auch wenn sie in „Gesperrt“ liegen.
    bedingung, args = bestand.heimat_im_zweig(fid)
    with db.transaction(sofort=True):
        o = bestand.ordner(fid)
        if o["system_kind"]:
            raise Abgelehnt("Einen Prüfdurchgang gibt es für Ablageordner, nicht für „Gesperrt“ oder „Ausgesondert“.", 409)
        artikel = [r["id"] for r in db.query(
            f"SELECT i.id FROM mat_item i WHERE {bedingung} AND i.lock_state <> 'ausgesondert' ORDER BY i.inventory_no",
            args)]
        if not artikel:
            raise Abgelehnt("In diesem Ordner und darunter liegt kein Artikel im Bestand.", 409)
        # Ausgenommene und erledigte Zeilen zählen nicht (wie in einbeziehen und offene_runde_fuer): Nach einem
        # Verschieben eröffnet der neue Bereich seinen eigenen Durchgang, auch wenn der Artikel im alten schon geprüft
        # ist – die erledigte Zeile bleibt dort als Nachweis stehen (1.7 Nr. 4 und 6).
        konflikt = db.query(
            f"SELECT r.id, r.title FROM mat_round r JOIN mat_round_item ri ON ri.round_id = r.id "
            f"JOIN mat_item i ON i.id = ri.item_id WHERE r.closed_on IS NULL AND ri.excluded_reason IS NULL "
            f"AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.round_id = r.id AND x.item_id = ri.item_id "
            f"AND x.completed_at IS NOT NULL) AND {bedingung} LIMIT 1", args, one=True)
        if konflikt:
            raise Abgelehnt(f"Für Artikel hier läuft schon der Durchgang „{konflikt['title']}“ – ein Artikel steht "
                            "höchstens in einem offenen Durchgang.", 409)
        rid = db.execute("INSERT INTO mat_round (folder_id, title, opened_by, opened_by_name, opened_on) "
                         "VALUES (?,?,?,?,?)", (fid, titel, akteur.get("id"), akteur["name"], heute().isoformat()))
        for iid in artikel:
            db.execute("INSERT INTO mat_round_item (round_id, item_id) VALUES (?, ?)", (rid, iid))
        # Wer schon prüft, prüft jetzt im Durchgang: Sein Entwurf ist die Reservierung und zählt hier. Eine
        # Berichtigung nicht – sie trägt den Prüftag ihres Originals und gehört nur zu dessen Durchgang.
        uebernommen = db.execute_zeilen(
            "UPDATE mat_inspection SET round_id = ? WHERE completed_at IS NULL AND round_id IS NULL "
            "AND corrects_inspection_id IS NULL AND item_id IN (SELECT item_id FROM mat_round_item WHERE round_id = ?)",
            (rid, rid))
        journal.eintragen("round", rid, "eroeffnet", None,
                          {"title": titel, "folder_id": fid, "ordner": bestand._pfad_text(fid), "artikel": len(artikel),
                           "entwuerfe": uebernommen})
    return rid


def _zeilen(rid):
    """Je Artikel des Durchgangs: Ausnahme, letzte Prüfung im Durchgang, offener Entwurf."""
    return db.query(
        "SELECT ri.item_id, ri.excluded_reason, ri.excluded_by_name, ri.excluded_at, "
        "x.id AS pruefung_id, x.result AS ergebnis, x.inspector_name AS pruefer, x.inspector_certificate AS urkunde, "
        "x.inspected_on AS geprueft_am, "
        "e.id AS entwurf_id, e.inspector_name AS entwurf_pruefer, e.inspector_user_id AS entwurf_pruefer_id, "
        "e.created_at AS entwurf_seit, e.round_id AS entwurf_runde "
        "FROM mat_round_item ri "
        "LEFT JOIN mat_inspection x ON x.id = (SELECT y.id FROM mat_inspection y WHERE y.round_id = ri.round_id "
        "  AND y.item_id = ri.item_id AND y.completed_at IS NOT NULL ORDER BY y.completed_at DESC, y.id DESC LIMIT 1) "
        "LEFT JOIN mat_inspection e ON e.item_id = ri.item_id AND e.completed_at IS NULL "
        "WHERE ri.round_id = ?", (rid,))


def _zustand(z, geschlossen=False):
    if z["pruefung_id"]:
        return "erledigt"
    if z["excluded_reason"]:
        return "ausgenommen"
    if geschlossen:                  # nur nach einem Abbruch: Was bis dahin nicht geprüft war, bleibt es
        return "nicht_geprueft"
    if z["entwurf_id"]:
        return "in_pruefung"
    return "offen"


def _zaehlung(zeilen, geschlossen=False):
    out = {"gesamt": len(zeilen), "offen": 0, "in_pruefung": 0, "erledigt": 0, "ausgenommen": 0}
    if geschlossen:
        out["nicht_geprueft"] = 0
    for z in zeilen:
        out[_zustand(z, geschlossen)] += 1
    return out


def _offene_entwuerfe(rid):
    return db.query("SELECT * FROM mat_inspection WHERE round_id = ? AND completed_at IS NULL", (rid,))


def ordnerspalte(zweig, item, pfade, pfad_text=None):
    """Was in der Ordnerspalte von Durchgangsansicht und Sammelprotokoll steht (1.7 Nr. 7): der Pfad der Heimat, wenn
    sie im Zweig des Durchgangs liegt – sonst nur, dass der Artikel aus dem Bereich verschoben wurde, nie ein Pfad aus
    einem fremden Bereich. zweig: die Ordner des Zweigs (bestand.unterbaum); pfade: Zwischenspeicher je Ordner;
    pfad_text: wie der Pfad geschrieben wird (Vorgabe bestand._pfad_text, das Protokoll hat seine eigene Form)."""
    h = bestand.heimat(item)
    if h not in zweig:
        return AUS_DEM_BEREICH
    if h not in pfade:
        pfade[h] = (pfad_text or bestand._pfad_text)(h)
    return pfade[h]


def durchgang_json(r, voll=False, pruefer_id=None):
    """Ein Durchgang mit „darf“ an seinem Ordner. voll: alle Zeilen, nichts verdeckt – zu Artikeln, die das Konto nicht
    sieht (aus dem Bereich verschoben), nur Inventarnummer, Produkt, Zustand und Grund, ohne Kennung und Link
    („sichtbar“: false)."""
    zeilen = _zeilen(r["id"])
    geschlossen = r["closed_on"] is not None
    z = _zaehlung(zeilen, geschlossen)
    out = {"id": r["id"], "titel": r["title"], "folder_id": r["folder_id"], "ordner": bestand._pfad_text(r["folder_id"]),
           "eroeffnet_von": r["opened_by_name"], "eroeffnet_am": r["opened_on"], "geschlossen_am": r["closed_on"],
           "geschlossen_von": r["closed_by_name"], "offen": not geschlossen, "abgebrochen": bool(r["aborted"]), "zaehlung": z,
           "protokoll": protokoll.protokoll_json(r, f"/material/durchgang/{r['id']}/sammelprotokoll"),
           "darf": rechte.rechte_ordner(r["folder_id"])}
    if geschlossen:
        out["set_protokolle"] = [set_protokoll_json(s) for s in protokoll.set_protokolle(r["id"])]
    entwuerfe = _offene_entwuerfe(r["id"])
    out["abschliessbar"] = out["offen"] and z["offen"] == 0 and z["in_pruefung"] == 0 and not entwuerfe
    if not voll:
        return out
    out["pfad"] = bestand.pfad(r["folder_id"])
    ids = [x["item_id"] for x in zeilen]
    artikel = {}
    if ids:
        artikel = {a["id"]: a for a in db.query(
            bestand.ARTIKEL_LISTE_SQL + "WHERE i.id IN (SELECT item_id FROM mat_round_item WHERE round_id = ?)",
            (r["id"],))}
    zweig, pfade = bestand.unterbaum(r["folder_id"]), {}
    liste = []
    for x in zeilen:
        roh = artikel[x["item_id"]]
        zustand = _zustand(x, geschlossen)
        ausnahme = ({"grund": x["excluded_reason"], "von": x["excluded_by_name"], "am": x["excluded_at"]}
                    if x["excluded_reason"] else None)
        if not rechte.darf_artikel("lesen", roh):
            liste.append({"sichtbar": False, "inventory_no": roh["inventory_no"], "manufacturer": roh["manufacturer"],
                          "model": roh["model"], "description": roh["product_description"] or "",
                          "pfad": ordnerspalte(zweig, roh, pfade), "zustand": zustand,
                          "zustand_text": ZUSTAND_TEXT[zustand], "ausnahme": ausnahme,
                          "pruefung": ({"ergebnis": x["ergebnis"], "pruefer": x["pruefer"], "datum": x["geprueft_am"]}
                                       if x["pruefung_id"] else None)})
            continue
        a = bestand.artikel_kurz(roh)
        a["sichtbar"] = True
        a["pfad"] = ordnerspalte(zweig, roh, pfade)
        a["zustand"] = zustand
        a["zustand_text"] = ZUSTAND_TEXT[zustand]
        a["pruefung"] = ({"id": x["pruefung_id"], "ergebnis": x["ergebnis"], "pruefer": x["pruefer"],
                          "datum": x["geprueft_am"]} if x["pruefung_id"] else None)
        a["entwurf"] = ({"id": x["entwurf_id"], "pruefer": x["entwurf_pruefer"], "seit": x["entwurf_seit"],
                         "eigen": bool(pruefer_id) and x["entwurf_pruefer_id"] == pruefer_id}
                        if x["entwurf_id"] else None)
        a["ausnahme"] = ausnahme
        liste.append(a)
    reihe = {"in_pruefung": 0, "offen": 1, "nicht_geprueft": 1, "ausgenommen": 2, "erledigt": 3}
    liste.sort(key=lambda a: (reihe[a["zustand"]], a["pfad"], a["inventory_no"]))
    out["artikel"] = liste
    # Ein berichtigtes Original zählt nicht mit, wenn seine Berichtigung im selben Durchgang abgeschlossen ist –
    # sonst wären es mehr Prüfungen als geprüfte Artikel.
    out["pruefer"] = db.query(
        "SELECT inspector_name AS name, inspector_certificate AS urkunde, COUNT(*) AS anzahl FROM mat_inspection "
        "WHERE round_id = ? AND completed_at IS NOT NULL " + OHNE_BERICHTIGTE +
        "GROUP BY inspector_user_id, inspector_name, inspector_certificate ORDER BY inspector_name", (r["id"],))
    out["loeschbar"] = out["offen"] and not db.query(
        "SELECT 1 FROM mat_inspection WHERE round_id = ? LIMIT 1", (r["id"],), one=True)
    if out["offen"]:
        # Stand jetzt: Sets unterhalb des Durchgangsordners mit Zeilen – und mit Geprüftem (so viele Set-Protokolle
        # entstünden beim Abschließen).
        ketten, eintraege = {}, []
        for x in zeilen:
            h = bestand.heimat(artikel[x["item_id"]])
            if h in zweig and h not in ketten:
                ketten[h] = bestand.pfad(h)
            eintraege.append({"_kette": ketten.get(h), "zustand": _zustand(x, geschlossen),
                              "inventarnummer": artikel[x["item_id"]]["inventory_no"]})
        je_set = protokoll.set_ordner_von(eintraege, r["folder_id"])
        out["set_ordner"] = {"anzahl": len(je_set), "mit_pruefung": sum(1 for s in je_set.values() if s["geprueft"])}
    return out


def set_protokoll_json(s):
    """Ein Set-Protokoll (Zeile von mat_round_setprotokoll) für die Oberfläche; der Link zum Set-Ordner nur, wenn das
    Konto ihn sieht."""
    url = f"/material/durchgang/{s['round_id']}/set/{s['id']}.pdf"
    return {"id": s["id"], "protokoll": protokoll.protokoll_json(s, url), "ordner": s["ordner"], "folder_id": s["folder_id"],
            "ordner_sichtbar": rechte.sicht().sichtbar(s["folder_id"]), "artikel": s["artikel"]}


def liste(nur_offen=False, grenze=50):
    """Die Durchgänge, die das Konto sehen darf (Ordner des Durchgangs sichtbar), offene zuerst."""
    sql = f"SELECT r.* FROM mat_round r WHERE {rechte.ordner_filter('r.folder_id')}" + (
        " AND r.closed_on IS NULL" if nur_offen else "") + " ORDER BY r.closed_on IS NOT NULL, r.id DESC LIMIT ?"
    return [durchgang_json(r) for r in db.query(sql, (grenze,))]


def _runde_offen(rid):
    r = runde(rid)
    if r["closed_on"]:
        raise Abgelehnt("Der Durchgang ist abgeschlossen.", 409)
    return r


def _im_durchgang(rid, iid):
    ri = db.query("SELECT * FROM mat_round_item WHERE round_id = ? AND item_id = ?", (rid, iid), one=True)
    if not ri:
        raise Abgelehnt("Der Artikel gehört nicht zu diesem Durchgang.", 404)
    return ri


def ausnehmen(rid, iid, d, akteur):
    grund = text(d, "grund", "Grund", 200, pflicht=True)
    with db.transaction(sofort=True):
        _runde_offen(rid)
        ri = _im_durchgang(rid, iid)
        if _erledigt(rid, iid):
            raise Abgelehnt("Der Artikel ist in diesem Durchgang schon geprüft.", 409)
        if ri["excluded_reason"]:
            raise Abgelehnt("Der Artikel ist schon ausgenommen.", 409)
        e = db.query("SELECT inspector_name, created_at FROM mat_inspection WHERE item_id = ? AND completed_at IS NULL",
                     (iid,), one=True)
        if e:
            raise Abgelehnt(f"In Prüfung bei {e['inspector_name']} – erst abschließen oder die Reservierung aufheben.",
                            409)
        db.execute("UPDATE mat_round_item SET excluded_reason = ?, excluded_by = ?, excluded_by_name = ?, excluded_at = ? "
                   "WHERE round_id = ? AND item_id = ?", (grund, akteur.get("id"), akteur["name"], db.now(), rid, iid))
        journal.eintragen("round", rid, "ausgenommen", None, {"item_id": iid, "grund": grund})


def einbeziehen(rid, iid):
    """Einen ausgenommenen Artikel wieder einbeziehen – nicht, wenn seine Heimat den Zweig verlassen hat oder er in
    einem anderen offenen Durchgang noch zu prüfen ist (1.7 Nr. 6)."""
    with db.transaction(sofort=True):
        r = _runde_offen(rid)
        ri = _im_durchgang(rid, iid)
        if not ri["excluded_reason"]:
            return
        item = bestand.artikel(iid)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist ausgesondert und wird nicht mehr geprüft – er bleibt ausgenommen.", 409)
        if not _im_zweig(r, item):
            raise Abgelehnt(NICHT_IM_BEREICH, 409)
        anderer = db.query(
            "SELECT r.title FROM mat_round r JOIN mat_round_item ri ON ri.round_id = r.id WHERE r.closed_on IS NULL "
            "AND r.id <> ? AND ri.item_id = ? AND ri.excluded_reason IS NULL AND NOT EXISTS (SELECT 1 FROM mat_inspection x "
            "WHERE x.round_id = r.id AND x.item_id = ri.item_id AND x.completed_at IS NOT NULL) LIMIT 1", (rid, iid), one=True)
        if anderer:
            raise Abgelehnt(f"Der Artikel steht schon im offenen Durchgang „{anderer['title']}“ – ein Artikel steht "
                            "höchstens in einem offenen Durchgang.", 409)
        db.execute("UPDATE mat_round_item SET excluded_reason = NULL, excluded_by = NULL, excluded_by_name = '', "
                   "excluded_at = NULL WHERE round_id = ? AND item_id = ?", (rid, iid))
        # Prüft schon jemand (begonnen, als der Artikel ausgenommen war), zählt diese Prüfung jetzt hier – eine
        # Berichtigung nicht (siehe eroeffnen).
        db.execute("UPDATE mat_inspection SET round_id = ? WHERE item_id = ? AND completed_at IS NULL AND round_id IS NULL "
                   "AND corrects_inspection_id IS NULL", (rid, iid))
        journal.eintragen("round", rid, "einbezogen", {"item_id": iid, "grund": ri["excluded_reason"]}, None)


# Wie oft Abschließen bzw. Abbrechen neu rendert, wenn sich zwischen dem Rendern und dem Festschreiben etwas geändert hat.
VERSUCHE = 3
GEAENDERT = ("Während des Festschreibens wurde am Durchgang weitergearbeitet (etwa geprüft, ausgenommen oder ein Ordner "
             "geändert) oder gleichzeitig ein anderer Durchgang abgeschlossen – es wurde nichts festgeschrieben. Bitte "
             "noch einmal versuchen.")


@contextmanager
def _lesestand():
    """Ein Lesestand ohne Schreibsperre (WAL): alles, was darin gelesen wird, gehört zu einem Zeitpunkt. Schreiben darf
    darin niemand – rollt am Ende zurück."""
    conn = db.get_db()
    if conn.in_transaction or getattr(g, "tx_depth", 0):
        yield
        return
    conn.execute("BEGIN")
    try:
        yield
    finally:
        if conn.in_transaction:
            conn.rollback()


def _abschliessbar(rid):
    z = _zaehlung(_zeilen(rid))
    if z["offen"] or z["in_pruefung"]:
        raise Abgelehnt(f"Noch nicht fertig: {z['offen']} offen, {z['in_pruefung']} in Prüfung. Jeder Artikel muss "
                        "geprüft oder mit Grund ausgenommen sein.", 409)
    entwuerfe = _offene_entwuerfe(rid)
    if entwuerfe:
        raise Abgelehnt("Im Durchgang ist noch eine Prüfung offen (" + ", ".join(
            e["inspector_name"] for e in entwuerfe) + ").", 409)
    return z


def _schliessen(r, tag, akteur):
    """Unter der Schreibsperre: den Durchgang regulär schließen (danach festschreiben)."""
    z = _abschliessbar(r["id"])
    db.execute("UPDATE mat_round SET closed_on = ?, closed_by = ?, closed_by_name = ? WHERE id = ?",
               (tag, akteur.get("id"), akteur["name"], r["id"]))
    journal.eintragen("round", r["id"], "geschlossen", None, {"title": r["title"], "erledigt": z["erledigt"],
                                                              "ausgenommen": z["ausgenommen"]})
    return True


def _abbrechen(r, tag, akteur):
    """Unter der Schreibsperre: offene Entwürfe lösen; ohne Geprüftes den Durchgang entfernen (False), sonst als
    abgebrochen schließen (True, danach festschreiben)."""
    rid = r["id"]
    for e in _offene_entwuerfe(rid):
        db.execute("UPDATE mat_inspection SET round_id = NULL WHERE id = ?", (e["id"],))
        journal.eintragen("inspection", e["id"], "geaendert", {"round_id": rid}, {"round_id": None})
    if not db.query("SELECT 1 FROM mat_inspection WHERE round_id = ? LIMIT 1", (rid,), one=True):
        db.execute("DELETE FROM mat_round_item WHERE round_id = ?", (rid,))
        db.execute("DELETE FROM mat_round WHERE id = ?", (rid,))
        journal.eintragen("round", rid, "geloescht", {"title": r["title"], "folder_id": r["folder_id"]}, None)
        return False
    z = _zaehlung(_zeilen(rid), geschlossen=True)
    db.execute("UPDATE mat_round SET closed_on = ?, closed_by = ?, closed_by_name = ?, aborted = 1 WHERE id = ?",
               (tag, akteur.get("id"), akteur["name"], rid))
    journal.eintragen("round", rid, "abgebrochen", None, {"title": r["title"], "erledigt": z["erledigt"],
                                                          "ausgenommen": z["ausgenommen"],
                                                          "nicht_geprueft": z["nicht_geprueft"]})
    return True


def _beenden(rid, akteur, abbruch):
    """Abschließen bzw. abbrechen samt Sammel- und Set-Protokollen – zweistufig (Prüfung vom 25.10.2026): erst ohne
    Schreibsperre lesen und alle PDFs rendern (protokoll.durchgang_vorbereiten, durchgang_rendern), dann kurz unter der
    Sperre prüfen, schließen und ablegen (protokoll.durchgang_festschreiben). Vorher hielt das Rendern vieler
    Set-Protokolle die Sperre länger, als andere Anfragen warten (15 s) – die scheiterten dann mit 500. Hat sich
    dazwischen etwas geändert, das in den Protokollen stünde, verwirft es die Dateien und beginnt neu, höchstens VERSUCHE
    Mal, dann 409. Wer abschließt, wartet wie bisher, bis alles festgeschrieben ist. Liefert, ob der Durchgang bleibt
    (False nur beim Abbruch ohne Geprüftes: Er wird entfernt)."""
    for versuch in range(1, VERSUCHE + 1):
        tag, ts = heute().isoformat(), db.now()
        beginn = time.monotonic()
        with protokoll.zwischendateien():
            try:
                with _lesestand():
                    r = _runde_offen(rid)
                    if not abbruch:
                        _abschliessbar(rid)
                    geschlossen = dict(r, closed_on=tag, closed_by=akteur.get("id"), closed_by_name=akteur["name"],
                                       aborted=1 if abbruch else r["aborted"])
                    auswahl = None
                    if not abbruch or db.query("SELECT 1 FROM mat_inspection WHERE round_id = ? LIMIT 1", (rid,),
                                               one=True):
                        auswahl = protokoll.durchgang_auswahl(geschlossen)
                v = None
                if auswahl:
                    # Die T-Nummern vorab in einer eigenen kurzen Transaktion (N1): Ein gleichzeitiger Abschluss eines
                    # anderen Durchgangs verdrängt diesen Versuch dann nicht.
                    kennungen = protokoll.t_nummern_reservieren(len(auswahl["sets"]))
                    with _lesestand():
                        v = protokoll.durchgang_vorbereiten(geschlossen, ts, kennungen, auswahl["eintraege"])
                    protokoll.durchgang_rendern(v)
                gerendert = time.monotonic()
                with protokoll.dateien_sichern():
                    with db.transaction(sofort=True):
                        gesperrt = time.monotonic()
                        r = _runde_offen(rid)
                        if not (_abbrechen if abbruch else _schliessen)(r, tag, akteur):
                            return False
                        if v is None:
                            raise protokoll.Veraendert()
                        protokoll.durchgang_festschreiben(rid, v)
            except protokoll.Veraendert:
                current_app.logger.info("Durchgang %s: seit dem Rendern geändert – Versuch %d verworfen", rid, versuch)
                continue
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc):
                    raise
                raise Abgelehnt("Die Datenbank ist gerade ausgelastet – es wurde nichts festgeschrieben. Bitte gleich "
                                "noch einmal versuchen.", 503)
            current_app.logger.info("Durchgang %s festgeschrieben: %d Set-Protokolle, %.1f s ohne Sperre gerendert, "
                                    "Schreibsperre %.2f s (Versuch %d)", rid, len(v["je_set"]), gerendert - beginn,
                                    time.monotonic() - gesperrt, versuch)
            return True
    raise Abgelehnt(GEAENDERT, 409)


def abschliessen(rid, akteur):
    """Regulär abschließen: jeder Artikel geprüft oder ausgenommen, kein Entwurf mehr offen – dann Sammelprotokoll und
    Set-Protokolle (_beenden)."""
    _beenden(rid, akteur, abbruch=False)


def abbrechen(rid, akteur):
    """Den Durchgang vorzeitig beenden (siehe oben). Liefert, ob er bleibt – False: Er wurde entfernt, weil
    darin noch nichts abgeschlossen war."""
    return _beenden(rid, akteur, abbruch=True)


def loeschen(rid):
    """Einen versehentlich eröffneten Durchgang entfernen – nur solange darin nichts geprüft wurde."""
    with db.transaction(sofort=True):
        r = _runde_offen(rid)
        if db.query("SELECT 1 FROM mat_inspection WHERE round_id = ? LIMIT 1", (rid,), one=True):
            raise Abgelehnt("Im Durchgang wurde schon geprüft – er bleibt und wird abgeschlossen.", 409)
        db.execute("DELETE FROM mat_round_item WHERE round_id = ?", (rid,))
        db.execute("DELETE FROM mat_round WHERE id = ?", (rid,))
        journal.eintragen("round", rid, "geloescht", {"title": r["title"], "folder_id": r["folder_id"]}, None)


def nach_aussonderung(iid, tag, basis_id=None):
    """Ein ausgesonderter Artikel wird in keinem offenen Durchgang mehr geprüft: Wo er noch offen steht,
    nimmt das System ihn mit Grund heraus. Kam die Aussonderung aus einer Prüfung des Durchgangs, ist er
    dort ohnehin erledigt. Läuft in der Transaktion des Aufrufers."""
    for r in db.query("SELECT ri.round_id FROM mat_round_item ri JOIN mat_round r ON r.id = ri.round_id "
                      "WHERE ri.item_id = ? AND r.closed_on IS NULL AND ri.excluded_reason IS NULL", (iid,)):
        if _erledigt(r["round_id"], iid):
            continue
        grund = f"ausgesondert am {_fmt(tag)}"
        db.execute("UPDATE mat_round_item SET excluded_reason = ?, excluded_by = NULL, excluded_by_name = 'System', "
                   "excluded_at = ? WHERE round_id = ? AND item_id = ?", (grund, db.now(), r["round_id"], iid))
        journal.eintragen("round", r["round_id"], "ausgenommen", None, {"item_id": iid, "grund": grund}, name="System")


def nach_verschieben(item_ids, tag):
    """Verschobene Artikel, deren Heimat den Zweig eines offenen Durchgangs verlassen hat, nimmt das System dort mit
    Grund heraus (1.7 Nr. 4) – bei jedem Verschieben, auch innerhalb einer Gliederung: Ein Prüfer mit Freigabe nur für
    den alten Zweig dürfte sie dort ohnehin nicht mehr prüfen. Ein offener Entwurf dazu verliert seinen Durchgang (wie
    beim Abbrechen); erledigte Zeilen bleiben stehen, sie sind der Nachweis. Läuft in der Transaktion des Aufrufers."""
    if not item_ids:
        return
    tag = tag.isoformat() if hasattr(tag, "isoformat") else tag
    grund = f"verschoben am {_fmt(tag)} – nicht mehr im Bereich des Durchgangs"
    ketten = {}
    for z in db.query("SELECT ri.round_id, ri.item_id, r.folder_id FROM mat_round_item ri JOIN mat_round r ON r.id = "
                      "ri.round_id WHERE r.closed_on IS NULL AND ri.excluded_reason IS NULL AND ri.item_id IN "
                      "(SELECT value FROM json_each(?)) ORDER BY ri.round_id, ri.item_id",
                      (json.dumps(sorted({int(i) for i in item_ids})),)):
        rid, iid = z["round_id"], z["item_id"]
        if _erledigt(rid, iid):
            continue
        if iid not in ketten:
            ketten[iid] = bestand.kette(bestand.heimat(bestand.artikel(iid)))
        if z["folder_id"] in ketten[iid]:
            continue
        db.execute("UPDATE mat_round_item SET excluded_reason = ?, excluded_by = NULL, excluded_by_name = 'System', "
                   "excluded_at = ? WHERE round_id = ? AND item_id = ?", (grund, db.now(), rid, iid))
        journal.eintragen("round", rid, "ausgenommen", None, {"item_id": iid, "grund": grund}, name="System")
        for e in db.query("SELECT id FROM mat_inspection WHERE item_id = ? AND round_id = ? AND completed_at IS NULL",
                          (iid, rid)):
            db.execute("UPDATE mat_inspection SET round_id = NULL WHERE id = ?", (e["id"],))
            journal.eintragen("inspection", e["id"], "geaendert", {"round_id": rid}, {"round_id": None}, name="System")

