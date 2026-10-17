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
Entwurf des Durchgangs mehr offen ist. Das Sammelprotokoll mit allen Prüfern folgt mit Lieferung 3.
Ein Artikel steht höchstens in einem offenen Durchgang."""
from datetime import date

from ... import db
from . import Abgelehnt, heute, text
from . import bestand, journal
from .faelligkeit import im_unterbaum

ZUSTAND_TEXT = {"offen": "offen", "in_pruefung": "in Prüfung", "erledigt": "erledigt", "ausgenommen": "ausgenommen"}


def _fmt(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return iso or ""


def runde(rid):
    r = db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
    if not r:
        raise Abgelehnt("Prüfdurchgang nicht gefunden.", 404)
    return r


def _erledigt(rid, iid):
    return db.query("SELECT 1 FROM mat_inspection WHERE round_id = ? AND item_id = ? AND completed_at IS NOT NULL "
                    "LIMIT 1", (rid, iid), one=True) is not None


def offene_runde_fuer(iid):
    """Der offene Durchgang, in dem der Artikel noch zu prüfen ist (nicht ausgenommen, nicht erledigt)."""
    r = db.query("SELECT r.id FROM mat_round r JOIN mat_round_item ri ON ri.round_id = r.id "
                 "WHERE r.closed_on IS NULL AND ri.item_id = ? AND ri.excluded_reason IS NULL "
                 "AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.round_id = r.id AND x.item_id = ri.item_id "
                 "AND x.completed_at IS NOT NULL) ORDER BY r.id DESC LIMIT 1", (iid,), one=True)
    return r["id"] if r else None


def runde_fuer_start(rid, iid):
    """Prüfung ausdrücklich in diesem Durchgang beginnen – nur, wenn der Artikel dort noch offen ist."""
    r = runde(rid)
    if r["closed_on"]:
        raise Abgelehnt("Der Durchgang ist abgeschlossen.", 409)
    ri = db.query("SELECT * FROM mat_round_item WHERE round_id = ? AND item_id = ?", (rid, iid), one=True)
    if not ri:
        raise Abgelehnt("Der Artikel gehört nicht zu diesem Durchgang.", 409)
    if ri["excluded_reason"]:
        raise Abgelehnt("Der Artikel ist aus dem Durchgang ausgenommen – erst wieder einbeziehen.", 409)
    if _erledigt(rid, iid):
        raise Abgelehnt("Der Artikel ist in diesem Durchgang schon geprüft.", 409)
    return rid


def eroeffnen(fid, d, akteur):
    titel = text(d, "titel", "Titel", 160, pflicht=True)
    zweig, args = im_unterbaum(fid)
    # Im Zweig liegen – oder aus ihm nach „Gesperrt“ gewandert sein (Herkunftsordner im Zweig).
    herkunft = zweig.replace("i.folder_id IN", "i.origin_folder_id IN", 1)
    bedingung = f"(({zweig}) OR (i.lock_state IN ('gesperrt', 'verloren') AND {herkunft}))"
    args = args + args
    with db.transaction(sofort=True):
        o = bestand.ordner(fid)
        if o["system_kind"]:
            raise Abgelehnt("Einen Prüfdurchgang gibt es für Ablageordner, nicht für „Gesperrt“ oder „Ausgesondert“.", 409)
        artikel = [r["id"] for r in db.query(
            f"SELECT i.id FROM mat_item i WHERE {bedingung} AND i.lock_state <> 'ausgesondert' ORDER BY i.inventory_no",
            args)]
        if not artikel:
            raise Abgelehnt("In diesem Ordner und darunter liegt kein Artikel im Bestand.", 409)
        konflikt = db.query(
            f"SELECT r.id, r.title FROM mat_round r JOIN mat_round_item ri ON ri.round_id = r.id "
            f"JOIN mat_item i ON i.id = ri.item_id WHERE r.closed_on IS NULL AND {bedingung} LIMIT 1", args, one=True)
        if konflikt:
            raise Abgelehnt(f"Für Artikel hier läuft schon der Durchgang „{konflikt['title']}“ – ein Artikel steht "
                            "höchstens in einem offenen Durchgang.", 409)
        rid = db.execute("INSERT INTO mat_round (folder_id, title, opened_by, opened_by_name, opened_on) "
                         "VALUES (?,?,?,?,?)", (fid, titel, akteur.get("id"), akteur["name"], heute().isoformat()))
        for iid in artikel:
            db.execute("INSERT INTO mat_round_item (round_id, item_id) VALUES (?, ?)", (rid, iid))
        # Wer schon prüft, prüft jetzt im Durchgang: Sein Entwurf ist die Reservierung und zählt hier.
        uebernommen = db.execute_zeilen(
            "UPDATE mat_inspection SET round_id = ? WHERE completed_at IS NULL AND round_id IS NULL "
            "AND item_id IN (SELECT item_id FROM mat_round_item WHERE round_id = ?)", (rid, rid))
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


def _zustand(z):
    if z["pruefung_id"]:
        return "erledigt"
    if z["excluded_reason"]:
        return "ausgenommen"
    if z["entwurf_id"]:
        return "in_pruefung"
    return "offen"


def _zaehlung(zeilen):
    out = {"gesamt": len(zeilen), "offen": 0, "in_pruefung": 0, "erledigt": 0, "ausgenommen": 0}
    for z in zeilen:
        out[_zustand(z)] += 1
    return out


def _offene_entwuerfe(rid):
    return db.query("SELECT * FROM mat_inspection WHERE round_id = ? AND completed_at IS NULL", (rid,))


def durchgang_json(r, voll=False, pruefer_id=None):
    zeilen = _zeilen(r["id"])
    z = _zaehlung(zeilen)
    out = {"id": r["id"], "titel": r["title"], "folder_id": r["folder_id"], "ordner": bestand._pfad_text(r["folder_id"]),
           "eroeffnet_von": r["opened_by_name"], "eroeffnet_am": r["opened_on"], "geschlossen_am": r["closed_on"],
           "geschlossen_von": r["closed_by_name"], "offen": r["closed_on"] is None, "zaehlung": z}
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
    liste = []
    for x in zeilen:
        a = bestand.artikel_kurz(artikel[x["item_id"]])
        a["pfad"] = bestand._pfad_text(artikel[x["item_id"]]["folder_id"])
        a["zustand"] = _zustand(x)
        a["zustand_text"] = ZUSTAND_TEXT[a["zustand"]]
        a["pruefung"] = ({"id": x["pruefung_id"], "ergebnis": x["ergebnis"], "pruefer": x["pruefer"],
                          "datum": x["geprueft_am"]} if x["pruefung_id"] else None)
        a["entwurf"] = ({"id": x["entwurf_id"], "pruefer": x["entwurf_pruefer"], "seit": x["entwurf_seit"],
                         "eigen": bool(pruefer_id) and x["entwurf_pruefer_id"] == pruefer_id}
                        if x["entwurf_id"] else None)
        a["ausnahme"] = ({"grund": x["excluded_reason"], "von": x["excluded_by_name"], "am": x["excluded_at"]}
                         if x["excluded_reason"] else None)
        liste.append(a)
    reihe = {"in_pruefung": 0, "offen": 1, "ausgenommen": 2, "erledigt": 3}
    liste.sort(key=lambda a: (reihe[a["zustand"]], a["pfad"], a["inventory_no"]))
    out["artikel"] = liste
    out["pruefer"] = db.query(
        "SELECT inspector_name AS name, inspector_certificate AS urkunde, COUNT(*) AS anzahl FROM mat_inspection "
        "WHERE round_id = ? AND completed_at IS NOT NULL GROUP BY inspector_user_id, inspector_name, "
        "inspector_certificate ORDER BY inspector_name", (r["id"],))
    out["loeschbar"] = out["offen"] and not db.query(
        "SELECT 1 FROM mat_inspection WHERE round_id = ? LIMIT 1", (r["id"],), one=True)
    return out


def liste(nur_offen=False, grenze=50):
    sql = "SELECT * FROM mat_round" + (" WHERE closed_on IS NULL" if nur_offen else "") + \
          " ORDER BY closed_on IS NOT NULL, id DESC LIMIT ?"
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
            raise Abgelehnt(f"In Prüfung bei {e['inspector_name']} – erst abschließen oder die Reservierung freigeben.",
                            409)
        db.execute("UPDATE mat_round_item SET excluded_reason = ?, excluded_by = ?, excluded_by_name = ?, excluded_at = ? "
                   "WHERE round_id = ? AND item_id = ?", (grund, akteur.get("id"), akteur["name"], db.now(), rid, iid))
        journal.eintragen("round", rid, "ausgenommen", None, {"item_id": iid, "grund": grund})


def einbeziehen(rid, iid):
    with db.transaction(sofort=True):
        _runde_offen(rid)
        ri = _im_durchgang(rid, iid)
        if not ri["excluded_reason"]:
            return
        if bestand.artikel(iid)["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist ausgesondert und wird nicht mehr geprüft – er bleibt ausgenommen.", 409)
        db.execute("UPDATE mat_round_item SET excluded_reason = NULL, excluded_by = NULL, excluded_by_name = '', "
                   "excluded_at = NULL WHERE round_id = ? AND item_id = ?", (rid, iid))
        # Prüft schon jemand (begonnen, als der Artikel ausgenommen war), zählt diese Prüfung jetzt hier.
        db.execute("UPDATE mat_inspection SET round_id = ? WHERE item_id = ? AND completed_at IS NULL AND round_id IS NULL",
                   (rid, iid))
        journal.eintragen("round", rid, "einbezogen", {"item_id": iid, "grund": ri["excluded_reason"]}, None)


def abschliessen(rid, akteur):
    with db.transaction(sofort=True):
        r = _runde_offen(rid)
        zeilen = _zeilen(rid)
        z = _zaehlung(zeilen)
        if z["offen"] or z["in_pruefung"]:
            raise Abgelehnt(f"Noch nicht fertig: {z['offen']} offen, {z['in_pruefung']} in Prüfung. Jeder Artikel muss "
                            "geprüft oder mit Grund ausgenommen sein.", 409)
        entwuerfe = _offene_entwuerfe(rid)
        if entwuerfe:
            raise Abgelehnt("Im Durchgang ist noch eine Prüfung offen (" + ", ".join(
                e["inspector_name"] for e in entwuerfe) + ").", 409)
        db.execute("UPDATE mat_round SET closed_on = ?, closed_by = ?, closed_by_name = ? WHERE id = ?",
                   (heute().isoformat(), akteur.get("id"), akteur["name"], rid))
        journal.eintragen("round", rid, "geschlossen", None, {"title": r["title"], "erledigt": z["erledigt"],
                                                              "ausgenommen": z["ausgenommen"]})


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

