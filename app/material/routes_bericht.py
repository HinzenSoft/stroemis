"""Routen des Jahresberichts je Zweig (Phase 4 · Lieferung 1): die Seite, die Daten (JSON), das PDF und die
CSV-Prüfungsliste – alle über EINE Rechtefunktion bericht_zugang in der Reihenfolge von routes_export._zugang:
401 ohne Anmeldung → 403 ohne Modulzugang → 404 nicht sichtbar oder Systemordner (ein Bericht über „Gesperrt“ oder
„Ausgesondert“ ist nach der Heimat-Logik leer und verriete nur, dass es sie gibt) → 403 ohne Grundrecht
(NUR_GRUNDRECHT – die Prüfsicht allein gibt keinen Bericht, wie beim Export). Führungskraft (lesen) und Materialwart
(verwalten) bekommen ihn, der externe Prüfer nicht; die Material-Verwaltung über ihre Allsicht.

Parameter: jahr als ganze Zahl 1990…2100 (400 bei Unsinn, fehlend = laufendes Jahr), pruefer über wahr() – der Haken
„Prüfer nennen“. Die Dateirouten tragen das Jahr im Pfad (bericht-<jahr>.pdf, -pruefungen-<jahr>.csv), die Fassung mit
Prüfern hat einen eigenen Pfad (-mit-pruefern), damit der Dateiname sagt, was weitergegeben wird. Jede Antwort trägt
Cache-Control no-store (antwort_privat); eine INFO-Zeile im Protokoll nennt Ordner, Jahr, Konto und Haken – keine
Namen; keine Journalzeile (der Bericht liest nur). Den Inhalt baut services/bericht.py."""
import io

from flask import current_app, jsonify, redirect, render_template, request, send_file, url_for

from ..auth import current_user
from .routes import _seite, api, seiten
from .services import Abgelehnt, antwort_privat, bericht, bestand, ganzzahl, heute, wahr
from .services.rechte import NUR_GRUNDRECHT, ORDNER_FEHLT, _bezug, sicht, zugang, zugang_meldung

# Wie _protokoll_senden ohne „sandbox“ – sonst zeigt der PDF-Betrachter von Chrome die Datei nicht an.
CSP_PDF = "default-src 'none'; object-src 'self'; img-src 'self' data:"


def bericht_zugang(fid, als_json=False):
    """None, wenn das Konto den Bericht über fid bekommt – sonst die Antwort (Anmeldung bzw. 401, Fehlerseite bzw.
    JSON-Fehler), siehe Kopf. Die Sicht wird hier einmal gerechnet und in g gehalten (rechte.sicht) – der Dienst nimmt
    dieselbe."""
    u = current_user()
    if not u:
        return (jsonify(error="Nicht angemeldet"), 401) if als_json else redirect(url_for("pages.login", next=request.path))
    if not zugang(u):
        return _fehler(Abgelehnt(zugang_meldung(u), 403), als_json)
    try:
        bezug = _bezug("fid", {"fid": fid})
        s = sicht(u)
        if not s.darf("lesen", bezug.ordner_id) or bestand.ordner(fid)["system_kind"]:
            raise Abgelehnt(ORDNER_FEHLT, 404)
        if not s.darf("grund", bezug.ordner_id):
            raise Abgelehnt(NUR_GRUNDRECHT, 403)
    except Abgelehnt as exc:
        return _fehler(exc, als_json)
    return None


def _fehler(exc, als_json):
    if als_json:
        return jsonify(error=str(exc)), exc.code
    return render_template("error.html", user=current_user(), code=exc.code, message=str(exc)), exc.code


def _jahr(wert):
    """Das Jahr aus Abfrage oder Pfad: ganze Zahl im erlaubten Bereich, fehlend = laufendes Jahr."""
    j = ganzzahl(wert, "Jahr", bericht.JAHR_MIN, bericht.JAHR_MAX)
    return heute().year if j is None else j


def _protokollieren(fid, jahr, pruefer_nennen, was):
    current_app.logger.info("Bericht Ordner %s Jahr %s Konto %s pruefer=%d (%s)", fid, jahr, current_user()["id"],
                            int(bool(pruefer_nennen)), was)


# --- Seite und Daten ------------------------------------------------------------------------------------------------

@seiten.get("/material/ordner/<int:fid>/bericht")
def bericht_seite(fid):
    """Die Seite mit Jahr-Auswahl und Haken; den Inhalt zeichnet material.js (Ansicht „bericht“) aus den Daten unten."""
    nein = bericht_zugang(fid)
    if nein:
        return nein
    return _seite("bericht", bezug=("ordner", fid), id=fid)


@api.get("/ordner/<int:fid>/bericht")
def bericht_daten(fid):
    """Alle Blöcke des Berichts als JSON (services/bericht.daten) – ?jahr=, ?pruefer=."""
    nein = bericht_zugang(fid, als_json=True)
    if nein:
        return nein
    jahr = _jahr(request.args.get("jahr"))
    pruefer_nennen = wahr(request.args, "pruefer", "Prüfer nennen")
    _protokollieren(fid, jahr, pruefer_nennen, "JSON")
    return antwort_privat(jsonify(bericht=bericht.daten(fid, jahr, sicht(), pruefer_nennen)))


# --- PDF und CSV ----------------------------------------------------------------------------------------------------

@seiten.get("/material/ordner/<int:fid>/bericht-<int:jahr>.pdf")
def bericht_pdf(fid, jahr):
    """Der Bericht als PDF/A-3b – im Browser geöffnet wie der Lebenslauf, nicht festgeschrieben; ohne Prüfernamen."""
    return _pdf(fid, jahr, False)


@seiten.get("/material/ordner/<int:fid>/bericht-<int:jahr>-mit-pruefern.pdf")
def bericht_pdf_mit_pruefern(fid, jahr):
    """Dasselbe mit dem Block „Prüfer im Jahr“ und den Namen der Aussondernden (Haken „Prüfer nennen“)."""
    return _pdf(fid, jahr, True)


def _pdf(fid, jahr, pruefer_nennen):
    nein = bericht_zugang(fid)
    if nein:
        return nein
    try:
        jahr = _jahr(jahr)
        daten, name = bericht.pdf(fid, jahr, sicht(), pruefer_nennen)
    except Abgelehnt as exc:
        return _fehler(exc, False)
    _protokollieren(fid, jahr, pruefer_nennen, "PDF")
    resp = send_file(io.BytesIO(daten), mimetype="application/pdf", download_name=name)
    resp.headers["Content-Security-Policy"] = CSP_PDF
    return antwort_privat(resp)


@seiten.get("/material/export/<int:fid>-pruefungen-<int:jahr>.csv")
def bericht_csv(fid, jahr):
    """Die Prüfungen und Aussonderungen des Jahres im Zweig als CSV für Excel – ohne Kappung, ohne Prüfernamen."""
    return _csv(fid, jahr, False)


@seiten.get("/material/export/<int:fid>-pruefungen-<int:jahr>-mit-pruefern.csv")
def bericht_csv_mit_pruefern(fid, jahr):
    """Dasselbe mit den Spalten Prüfer und Urkundennummer gefüllt."""
    return _csv(fid, jahr, True)


def _csv(fid, jahr, pruefer_nennen):
    nein = bericht_zugang(fid)
    if nein:
        return nein
    try:
        jahr = _jahr(jahr)
        daten, name = bericht.csv(fid, jahr, sicht(), pruefer_nennen)
    except Abgelehnt as exc:
        return _fehler(exc, False)
    _protokollieren(fid, jahr, pruefer_nennen, "CSV")
    return antwort_privat(send_file(io.BytesIO(daten), mimetype="text/csv", as_attachment=True, download_name=name))
