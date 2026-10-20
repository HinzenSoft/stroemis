"""Wer welche Datei unter /media/material/<art>/<datei> sehen darf (Phase 2 · L1, Abschnitt 2.4).

In orig/web/thumb liegen Produktbilder, Ordnerfotos, Befundfotos und Meldungsfotos gemischt, unter anhang die Anhänge
der Prüfungen, unter dok die Herstellerdokumente. Die Dateinamen sind zufällig – geschützt werden sie trotzdem je
Datei: Ein Name, der einmal in einer Antwort stand, öffnet sonst auch nach einem Entzug der Freigabe noch das Foto.

Gesucht wird über den Schlüssel des Namens (ohne Endung): Web- und Vorschaufassung heißen <schlüssel>.jpg, das Original
behält seine Endung. Der Bereich „>= schlüssel.“ und „< schlüssel/“ trifft genau die Namen mit diesem Schlüssel und
nutzt die Indizes aus Schritt 8. Was keinem Besitzer gehört oder wofür das Recht fehlt, antwortet wie Unbekanntes
(routes.medien: 404).

Seit Phase 3 · L1 kommen die Fotos der Mangelmeldungen dazu (nur Web- und Vorschaufassung – ein Original gibt es
nicht): für den Melder und wer den Artikel lesen darf. Ohne Modulzugang öffnet darf_datei_psa der zugeordneten Person
nur, was „Meine PSA“ zeigt: Produktbilder eigener Artikel (nie das Original mit den Aufnahmedaten), eigene Mangelfotos
und die Herstellerdokumente der Arten in psa.PSA_DOKUMENTARTEN (keine Prüfanweisung, nichts „Sonstiges“)."""
import json
import os

from ... import db
from ...auth import current_user
from . import heute, rechte

ARTEN = ("orig", "web", "thumb", "dok", "anhang")


def _bereich(spalte):
    return f"{spalte} >= ? AND {spalte} < ?"


def _schluessel(dateiname):
    key = os.path.splitext(dateiname)[0]
    return key, (key + ".", key + "/")


def _artikel_sichtbar(item_id):
    i = db.query("SELECT id, folder_id, origin_folder_id, lock_state FROM mat_item WHERE id = ?", (item_id,), one=True)
    return bool(i) and rechte.darf_artikel("lesen", i)


def _name_ok(art, dateiname):
    return art in ARTEN and bool(dateiname) and "/" not in dateiname and "\\" not in dateiname \
        and not dateiname.startswith(".")


def _muster(key):
    """LIKE-Muster für einen Schlüssel in einer JSON-Liste von Dateinamen (Meldungs- und Mangelfotos)."""
    return '%"' + key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + '.%'


def _mangelfotos(key):
    """Mangelmeldungen mit einem Foto dieses Schlüssels – LIKE, dann genau nachsehen."""
    return [d for d in db.query("SELECT id, item_id, reporter_id, photos_json FROM mat_defect_report "
                                "WHERE photos_json LIKE ? ESCAPE '\\'", (_muster(key),))
            if any(os.path.splitext(f)[0] == key for f in json.loads(d["photos_json"] or "[]"))]


def darf_datei_psa(art, dateiname, uid):
    """Ohne Modulzugang (routes.medien) – nur, was „Meine PSA“ der Person uid zeigt: das Produktbild eines Produkts, von
    dem ihr ein nicht ausgesonderter Artikel zugeordnet ist (nur web und thumb), ihre eigenen Mangelfotos (web, thumb)
    und Herstellerdokumente (dok), die katalog.gueltige_dokumente für eines dieser Produkte liefert und deren Art in
    psa.PSA_DOKUMENTARTEN liegt."""
    from . import katalog, psa
    if not _name_ok(art, dateiname) or art in ("orig", "anhang"):
        return False
    if art == "dok":
        if not db.query(f"SELECT 1 FROM mat_product_document WHERE file_path = ? AND kind IN "
                        f"({','.join('?' * len(psa.PSA_DOKUMENTARTEN))}) LIMIT 1",
                        (dateiname, *psa.PSA_DOKUMENTARTEN), one=True):
            return False
        tag = heute().isoformat()
        for r in db.query("SELECT DISTINCT product_id FROM mat_item WHERE assigned_user_id = ? "
                          "AND lock_state <> 'ausgesondert'", (uid,)):
            if any(d["kind"] in psa.PSA_DOKUMENTARTEN and d["datei"] == f"/media/material/dok/{dateiname}"
                   for d in katalog.gueltige_dokumente(r["product_id"], tag)):
                return True
        return False
    key, (von, bis) = _schluessel(dateiname)
    if not key:
        return False
    if db.query(f"SELECT 1 FROM mat_product p JOIN mat_item i ON i.product_id = p.id WHERE {_bereich('p.image')} "
                "AND i.assigned_user_id = ? AND i.lock_state <> 'ausgesondert' LIMIT 1", (von, bis, uid), one=True):
        return True
    return any(d["reporter_id"] == uid for d in _mangelfotos(key))


def darf_datei(art, dateiname):
    """Darf das angemeldete Konto diese Datei sehen? Herstellerdokumente und Produktbilder gehören zum Katalog
    (Modulzugang genügt – den prüft die Route vorher); Ordnerfotos brauchen das Leserecht am Ordner (nicht an einem
    Pfad-Knoten), Befundfotos und Anhänge das am Artikel, Meldungsfotos darf_meldung."""
    if not _name_ok(art, dateiname):
        return False
    if art == "dok":
        return db.query("SELECT 1 FROM mat_product_document WHERE file_path = ? LIMIT 1", (dateiname,), one=True) is not None
    if art == "anhang":
        return any(_artikel_sichtbar(r["item_id"]) for r in db.query(
            "SELECT x.item_id FROM mat_inspection_attachment a JOIN mat_inspection x ON x.id = a.inspection_id "
            "WHERE a.file_path = ?", (dateiname,)))
    key, (von, bis) = _schluessel(dateiname)
    if not key:
        return False
    if db.query(f"SELECT 1 FROM mat_product WHERE {_bereich('image')} LIMIT 1", (von, bis), one=True):
        return True
    for o in db.query(f"SELECT id FROM mat_folder WHERE {_bereich('photo')}", (von, bis)):
        if rechte.darf("lesen", o["id"]):
            return True
    for r in db.query(f"SELECT x.item_id FROM mat_inspection_result b JOIN mat_inspection x ON x.id = b.inspection_id "
                      f"WHERE {_bereich('b.photo')}", (von, bis)):
        if _artikel_sichtbar(r["item_id"]):
            return True
    # Meldungsfotos stehen als Liste im JSON der Meldung – LIKE über den Schlüssel mit Punkt, dann genau nachsehen.
    for m in db.query("SELECT id, created_by, folder_id, photos_json FROM mat_product_request "
                      "WHERE photos_json LIKE ? ESCAPE '\\'", (_muster(key),)):
        if any(os.path.splitext(f)[0] == key for f in json.loads(m["photos_json"] or "[]")) and rechte.darf_meldung(m):
            return True
    # Mangelfotos (Phase 3 · L1): der Melder und wer den Artikel lesen darf – ein Original gibt es nicht.
    if art != "orig":
        u = current_user()
        for d in _mangelfotos(key):
            if (u and d["reporter_id"] == u["id"]) or _artikel_sichtbar(d["item_id"]):
                return True
    return False
