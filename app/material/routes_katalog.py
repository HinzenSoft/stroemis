"""Schnittstelle für den Katalogaustausch (Lieferung 4): Export des Katalogs als ZIP, Import aus ZIP oder JSON.

Nur die Material-Verwaltung (Stufe Verwaltung im Modul Material). Der Export enthält keine DEMO-Einträge, keinen
Bestand und keine Prüfungen (services/katalog_export.py); der Import gleicht ab statt doppelt anzulegen und löscht nie
etwas (services/importer.py). Die Oberfläche macht vor jedem Import einen Probelauf und zeigt dessen Bericht.

Seit dem 24.10.2026 läuft der Import im Hintergrund (services/importauftrag.py): POST speichert die Datei und antwortet
202 mit dem Auftrag, GET …/import/<kennung> liefert Zustand, Phase, Fortschritt und am Ende den Bericht, „Übernehmen“
startet den echten Lauf mit der Datei des Probelaufs. Kein Warten mehr auf die Antwort – der Reverse-Proxy schnitt die
große Lieferung sonst nach seiner Zeitgrenze ab (504)."""
import os
import tempfile

from flask import current_app, jsonify, request, send_file

from .routes import api
from .services import Abgelehnt, akteur, heute, importauftrag, katalog_export, wahr
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
    wird nur mit trocken=0. Die Datei wird abgelegt und der Import im Hintergrund gestartet: 202 mit „auftrag“, 409 mit
    dem laufenden, wenn schon einer läuft, 507, wenn auf dem Server der Platz für die Datei nicht reicht.
    Größengrenze: UPLOAD_GRENZEN (routes.py) wie bisher."""
    datei = request.files.get("file")
    if not datei or not datei.filename:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    trocken = wahr(request.form, "trocken", "Probelauf") if "trocken" in request.form else True
    quelle = os.path.basename(datei.filename.replace("\\", "/"))[:80] or "Datei"
    try:
        auftrag = importauftrag.starten(datei, trocken, quelle, akteur())
    except importauftrag.Belegt as exc:
        return jsonify(error=str(exc), auftrag=exc.auftrag), 409
    return jsonify(auftrag=auftrag), 202


@api.get("/katalog/import/aktuell")
@katalog_required
def katalog_import_aktuell():
    """Der laufende oder zuletzt (vor höchstens einem Tag) beendete Import – für den Hinweis auf der Katalogseite;
    „auftrag“ ist null, wenn es keinen gibt. Ohne Bericht."""
    return jsonify(auftrag=importauftrag.aktuell(akteur()[0]))


@api.get("/katalog/import/<kennung>")
@katalog_required
def katalog_import_stand(kennung):
    """Zustand (wartet, laeuft, fertig, fehlgeschlagen, abgebrochen), Phase, Fortschritt und – sobald er zu Ende ist –
    der Bericht im bisherigen Format. Unbekannte Kennung: 404."""
    return jsonify(auftrag=importauftrag.lesen(kennung, akteur()[0]))


@api.post("/katalog/import/<kennung>/uebernehmen")
@katalog_required
def katalog_import_uebernehmen(kennung):
    """Nach einem Probelauf ohne Fehler: derselbe Import echt, mit der Datei des Probelaufs (sie bleibt eine Stunde) –
    ohne neuen Upload. Nur wer den Probelauf gestartet hat. Auch mit der Kennung eines abgebrochenen „Übernehmen“,
    dessen Probelauf seine Datei zurückbekam. 202 mit dem neuen Auftrag, 507, wenn der Platz nicht reicht."""
    try:
        auftrag = importauftrag.uebernehmen(kennung, akteur())
    except importauftrag.Belegt as exc:
        return jsonify(error=str(exc), auftrag=exc.auftrag), 409
    return jsonify(auftrag=auftrag), 202
