"""Wer welche Datei unter /media/material/<art>/<datei> sehen darf (Phase 2 · L1, Abschnitt 2.4).

In orig/web/thumb liegen Produktbilder, Ordnerfotos, Befundfotos und Meldungsfotos gemischt, unter anhang die Anhänge
der Prüfungen, unter dok die Herstellerdokumente. Die Dateinamen sind zufällig – geschützt werden sie trotzdem je
Datei: Ein Name, der einmal in einer Antwort stand, öffnet sonst auch nach einem Entzug der Freigabe noch das Foto.

Gesucht wird über den Schlüssel des Namens (ohne Endung): Web- und Vorschaufassung heißen <schlüssel>.jpg, das Original
behält seine Endung. Der Bereich „>= schlüssel.“ und „< schlüssel/“ trifft genau die Namen mit diesem Schlüssel und
nutzt die Indizes aus Schritt 8. Was keinem Besitzer gehört oder wofür das Recht fehlt, antwortet wie Unbekanntes
(routes.medien: 404)."""
import json
import os

from ... import db
from . import rechte

ARTEN = ("orig", "web", "thumb", "dok", "anhang")


def _bereich(spalte):
    return f"{spalte} >= ? AND {spalte} < ?"


def _schluessel(dateiname):
    key = os.path.splitext(dateiname)[0]
    return key, (key + ".", key + "/")


def _artikel_sichtbar(item_id):
    i = db.query("SELECT id, folder_id, origin_folder_id, lock_state FROM mat_item WHERE id = ?", (item_id,), one=True)
    return bool(i) and rechte.darf_artikel("lesen", i)


def darf_datei(art, dateiname):
    """Darf das angemeldete Konto diese Datei sehen? Herstellerdokumente und Produktbilder gehören zum Katalog
    (Modulzugang genügt – den prüft die Route vorher); Ordnerfotos brauchen das Leserecht am Ordner (nicht an einem
    Pfad-Knoten), Befundfotos und Anhänge das am Artikel, Meldungsfotos darf_meldung."""
    if art not in ARTEN or not dateiname or "/" in dateiname or "\\" in dateiname or dateiname.startswith("."):
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
    muster = '%"' + key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + '.%'
    for m in db.query("SELECT id, created_by, folder_id, photos_json FROM mat_product_request "
                      "WHERE photos_json LIKE ? ESCAPE '\\'", (muster,)):
        if any(os.path.splitext(f)[0] == key for f in json.loads(m["photos_json"] or "[]")) and rechte.darf_meldung(m):
            return True
    return False
