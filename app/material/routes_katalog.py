"""Schnittstelle für den Katalogaustausch (Lieferung 4): Export des Katalogs als ZIP, Import aus ZIP oder JSON.

Nur Produktkatalogpfleger und die Verwaltung. Der Export enthält keine DEMO-Einträge, keinen Bestand und keine
Prüfungen (services/katalog_export.py); der Import gleicht ab statt doppelt anzulegen und löscht nie etwas
(services/importer.py). Die Oberfläche macht vor jedem Import einen Probelauf und zeigt dessen Bericht."""
import os
import tempfile

from flask import current_app, jsonify, request, send_file

from .routes import api
from .services import Abgelehnt, heute, importer, katalog_export, wahr
from .services.rechte import katalog_required


@api.get("/katalog/export")
@katalog_required
def katalog_exportieren():
    """Der Katalog ohne DEMO als ZIP (Format 2) – gebaut in einer Zwischendatei unter TMP_DIR, nicht im Speicher;
    sie verschwindet, sobald die Antwort geschrieben ist."""
    zwischen = tempfile.TemporaryFile(dir=current_app.config["TMP_DIR"])
    try:
        katalog_export.zip_bauen(zwischen)
    except BaseException:
        zwischen.close()
        raise
    zwischen.seek(0)
    resp = send_file(zwischen, mimetype="application/zip", as_attachment=True,
                     download_name=f"Katalog_{heute().isoformat()}.zip", max_age=0)
    resp.cache_control.no_store = True
    resp.cache_control.private = True
    return resp


@api.get("/katalog/export/vorschau")
@katalog_required
def katalog_export_vorschau():
    """Was der Export enthielte und was nicht (DEMO, fehlende Dateien) – für den Dialog vor dem Herunterladen."""
    return jsonify(export=katalog_export.sammeln(mit_dateien=False)[2])


@api.post("/katalog/import")
@katalog_required
def katalog_importieren():
    """Katalogdatei (ZIP oder JSON) im Feld „file“. „trocken“ (Standard: ja) prüft nur und berichtet; gespeichert
    wird nur mit trocken=0. Die Antwort ist immer der Bericht – Fehler stehen darin mit ihrer Fundstelle."""
    datei = request.files.get("file")
    if not datei or not datei.filename:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    trocken = wahr(request.form, "trocken", "Probelauf") if "trocken" in request.form else True
    quelle = os.path.basename(datei.filename.replace("\\", "/"))[:80] or "Datei"
    bericht = importer.datei_importieren(datei.stream, trocken=trocken, quelle=quelle)
    return jsonify(bericht=bericht)
