"""Routen des Exports (Lieferung 4): Artikelliste eines Ordners als CSV, alle Protokolle eines Ordners als ZIP,
Lebenslauf eines Artikels als PDF. Das Konzept nennt dafür „Datenhoheit und Umzugsfähigkeit“.

Es sind Seiten (Blueprint „material“), keine Schnittstelle: Die Knöpfe sind Links, kein fetch. Deshalb wie bei
_protokoll_senden ohne Anmeldung zur Anmeldung, ohne Modulzugang 403 und jeden Fehler als Seite statt als JSON. Seit
Phase 2 braucht jeder Export das Grundrecht am Ordner (beim Lebenslauf an der Heimat des Artikels) – die Prüfsicht
allein gibt keinen Export. Fremdes antwortet wie Unbekanntes mit 404. Den Inhalt bauen services/export.py und
services/lebenslauf.py. Nichts davon wird zwischengespeichert: Die Antworten tragen Cache-Control no-store."""
import io

from flask import current_app, redirect, render_template, request, send_file, url_for

from .. import db
from ..auth import attempts_exceeded, current_user, note_attempt
from .routes import seiten
from .services import Abgelehnt, antwort_privat, export, lebenslauf, zeitstempel
from .services.rechte import NUR_GRUNDRECHT, _bezug, darf, zugang, zugang_meldung


# Abrufbremse je Konto für den Lebenslauf (wie an der Prüfseite, auth.ATTEMPT_WINDOW = eine Viertelstunde): Jeder Abruf
# kostet die Satzarbeit eines PDFs und schreibt eine unveränderliche Zeile in mat_lebenslauf (Prüfung nach dem Merge, V2).
LEBENSLAUF_JE_VIERTELSTUNDE = 60
ZU_VIELE_LEBENSLAEUFE = ("Du hast in kurzer Zeit sehr viele Lebensläufe abgerufen. Bitte in einer Viertelstunde noch "
                         "einmal.")


def _zugang(quelle, kennung_wert):
    """Angemeldet, Zugang zum Modul, Grundrecht am Ordner (bei Artikeln an der Heimat). None, wenn alles stimmt – sonst
    die Antwort (Anmeldung, Fehlerseite). Ohne Zugang zum Modul gibt es 403, bevor sich zeigt, ob es den Ordner gibt;
    was das Konto nicht sieht, antwortet wie Unbekanntes (404)."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.path))
    if not zugang(u):
        return _fehler(Abgelehnt(zugang_meldung(u), 403))
    try:
        bezug = _bezug(quelle, {quelle: kennung_wert})
        if not darf("lesen", bezug.ordner_id):
            raise Abgelehnt(bezug.meldung, 404)
        if not darf("grund", bezug.ordner_id):
            raise Abgelehnt(NUR_GRUNDRECHT, 403)
    except Abgelehnt as exc:
        return _fehler(exc)
    return None


def _fehler(exc):
    return render_template("error.html", user=current_user(), code=exc.code, message=str(exc)), exc.code


# Personenbezogene Daten (Prüfer, Urkundennummern): nie in einen Zwischenspeicher – seit P4-L1 in services
# (antwort_privat), weil der Jahresbericht (routes_bericht) dieselbe Regel braucht.
_privat = antwort_privat


def _download(daten, mimetype, name):
    """Datei zum Speichern – mit lesbarem ASCII-Ersatznamen („Jahrespruefung“ statt „Jahresprufung“)."""
    resp = send_file(daten, mimetype=mimetype, as_attachment=True, download_name=name)
    resp.headers["Content-Disposition"] = export.anhang_kopf(name)
    return _privat(resp)


@seiten.get("/materialablage/export/<int:fid>.csv")
def export_csv(fid):
    """Alle Artikel des Ordners und seiner Unterordner als CSV für Excel (services/export.py)."""
    nein = _zugang("fid", fid)
    if nein:
        return nein
    try:
        daten, name = export.artikel_csv(fid)
    except Abgelehnt as exc:
        return _fehler(exc)
    return _download(io.BytesIO(daten), "text/csv", name)


@seiten.get("/materialablage/export/<int:fid>-protokolle.zip")
def export_protokolle(fid):
    """Alle Protokolle der Artikel des Ordners, die Sammelprotokolle seiner Durchgänge und die Set-Protokolle der Sets im
    Zweig mit Verzeichnis.csv."""
    nein = _zugang("fid", fid)
    if nein:
        return nein
    try:
        buf, name, _ = export.protokolle_zip(fid)
    except Abgelehnt as exc:
        return _fehler(exc)
    return _download(buf, "application/zip", name)


@seiten.get("/materialablage/durchgang/<int:rid>/protokolle.zip")
def durchgang_protokolle(rid):
    """„Alle Protokolle“ eines Durchgangs (Schritt 27, F5 a): Sammelprotokoll, Set-Protokolle und Verzeichnis.csv – wer
    den Durchgang sieht (Leserecht an seinem Ordner, wie das Sammelprotokoll)."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.path))
    if not zugang(u):
        return _fehler(Abgelehnt(zugang_meldung(u), 403))
    try:
        bezug = _bezug("rid", {"rid": rid})
        if not darf("lesen", bezug.ordner_id):
            raise Abgelehnt(bezug.meldung, 404)
        buf, name = export.durchgang_zip(rid)
    except Abgelehnt as exc:
        return _fehler(exc)
    return _download(buf, "application/zip", name)


@seiten.get("/materialablage/artikel/<int:iid>/lebenslauf.pdf")
def lebenslauf_pdf(iid):
    """Lebenslauf eines Artikels als PDF – im Browser geöffnet wie die Protokolle, auf Abruf gesetzt, mit Kennung und
    Prüfsummen-Stempel; jeder Abruf ist in mat_lebenslauf verzeichnet, ohne das Konto (services/lebenslauf.py). HEAD
    antwortet nach der Rechteprüfung nur mit Kopfzeilen; je Konto höchstens LEBENSLAUF_JE_VIERTELSTUNDE Abrufe."""
    nein = _zugang("iid", iid)
    if nein:
        return nein
    if request.method == "HEAD":
        # Nach der Rechteprüfung nur die Kopfzeilen – ohne Kennung, ohne Eintrag in mat_lebenslauf, ohne Satzarbeit:
        # Vorabladen bekäme sonst einen Lebenslauf, den niemand sieht (Prüfung nach dem Merge, V1).
        resp = _privat(current_app.response_class(mimetype="application/pdf"))
        resp.automatically_set_content_length = False
        return resp
    bereich = [f"lebenslauf-konto:{current_user()['id']}"]
    if attempts_exceeded(bereich, LEBENSLAUF_JE_VIERTELSTUNDE):
        seite, code = _fehler(Abgelehnt(ZU_VIELE_LEBENSLAEUFE, 429))
        return seite, code, {"Retry-After": "900"}
    with db.transaction():
        note_attempt(bereich[0])
    try:
        daten, inventarnummer, kennung = lebenslauf.rendern(iid)
    except Abgelehnt as exc:
        return _fehler(exc)
    # Name mit Uhrzeit und Kennung, die Adresse trägt vom Knopf einen Zeitstempel (?stand=…, hier übergangen): Chrome auf
    # Android legt das PDF als Download ab und öffnete beim nächsten Tippen die alte Datei (Meldung vom 26.10.2026).
    resp = send_file(io.BytesIO(daten), mimetype="application/pdf",
                     download_name=f"Lebenslauf_{export.dateiname(inventarnummer)}_{zeitstempel()}_{kennung}.pdf")
    # Wie bei _protokoll_senden ohne „sandbox“ – sonst zeigt der PDF-Betrachter von Chrome die Datei nicht an.
    resp.headers["Content-Security-Policy"] = "default-src 'none'; object-src 'self'; img-src 'self' data:"
    return _privat(resp)
