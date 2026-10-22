"""Routen des Exports (Lieferung 4): Artikelliste eines Ordners als CSV, alle Protokolle eines Ordners als ZIP,
Lebenslauf eines Artikels als PDF. Das Konzept nennt dafür „Datenhoheit und Umzugsfähigkeit“.

Es sind Seiten (Blueprint „material“), keine Schnittstelle: Die Knöpfe sind Links, kein fetch. Deshalb wie bei
_protokoll_senden ohne Anmeldung zur Anmeldung, ohne Modulzugang 403 und jeden Fehler als Seite statt als JSON. Seit
Phase 2 braucht jeder Export das Grundrecht am Ordner (beim Lebenslauf an der Heimat des Artikels) – die Prüfsicht
allein gibt keinen Export. Fremdes antwortet wie Unbekanntes mit 404. Den Inhalt bauen services/export.py und
services/lebenslauf.py. Nichts davon wird zwischengespeichert: Die Antworten tragen Cache-Control no-store."""
import io

from flask import redirect, render_template, request, send_file, url_for

from ..auth import current_user
from .routes import seiten
from .services import Abgelehnt, antwort_privat, export, heute, lebenslauf
from .services.rechte import NUR_GRUNDRECHT, _bezug, darf, zugang, zugang_meldung


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


@seiten.get("/material/export/<int:fid>.csv")
def export_csv(fid):
    """Alle Artikel des Ordners und seiner Unterordner als CSV für Excel (services/export.py)."""
    nein = _zugang("fid", fid)
    if nein:
        return nein
    try:
        daten, name = export.artikel_csv(fid)
    except Abgelehnt as exc:
        return _fehler(exc)
    return _privat(send_file(io.BytesIO(daten), mimetype="text/csv", as_attachment=True,
                             download_name=name))


@seiten.get("/material/export/<int:fid>-protokolle.zip")
def export_protokolle(fid):
    """Alle Protokolle der Artikel des Ordners und die Sammelprotokolle seiner Durchgänge mit Verzeichnis.csv."""
    nein = _zugang("fid", fid)
    if nein:
        return nein
    try:
        buf, name, _ = export.protokolle_zip(fid)
    except Abgelehnt as exc:
        return _fehler(exc)
    return _privat(send_file(buf, mimetype="application/zip", as_attachment=True, download_name=name))


@seiten.get("/material/artikel/<int:iid>/lebenslauf.pdf")
def lebenslauf_pdf(iid):
    """Lebenslauf eines Artikels als PDF – im Browser geöffnet wie die Protokolle, aber auf Abruf gesetzt und nicht
    festgeschrieben (services/lebenslauf.py)."""
    nein = _zugang("iid", iid)
    if nein:
        return nein
    try:
        daten, inventarnummer = lebenslauf.rendern(iid)
    except Abgelehnt as exc:
        return _fehler(exc)
    resp = send_file(io.BytesIO(daten), mimetype="application/pdf",
                     download_name=f"Lebenslauf_{export.dateiname(inventarnummer)}_{heute().isoformat()}.pdf")
    # Wie bei _protokoll_senden ohne „sandbox“ – sonst zeigt der PDF-Betrachter von Chrome die Datei nicht an.
    resp.headers["Content-Security-Policy"] = "default-src 'none'; object-src 'self'; img-src 'self' data:"
    return _privat(resp)
