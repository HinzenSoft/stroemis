"""Routen der globalen Seriennummernsuche und des QR-Steckbriefs (Phase 2 · Lieferung 1, Abschnitt 3).

Suchen und den Steckbrief öffnen darf jeder mit Modulzugang – auch wer (noch) keinen Bestand sieht, etwa ein
Mitglied ohne Freigabe. Die Suche findet nur Artikel, die das Konto nicht sieht; die Material-Verwaltung sieht alles
und bekommt 409. Beides läuft nur nach Bestätigung, durch die gemeinsame Bremse und ins Protokoll; das Protokoll liest
nur die Plattform-Verwaltung (Abschnitt in der Nutzerverwaltung) – es ist eine Aufzeichnung über Personen; die
Material-Verwaltung sieht es nicht. Die Seite nach einem QR-Scan an einem fremden
Artikel (/m/<token>, Ansicht „fremd“) steht in routes.py. Die Fachregeln stehen in services/globalsuche.py, Bremse
und Protokoll in services/globalprotokoll.py."""
from flask import jsonify, request

from ..auth import current_user, is_admin, json_body
from .routes import api
from .services import ganzzahl, globalprotokoll, globalsuche
from .services.rechte import requires_zugang

NUR_VERWALTUNG = "Das Protokoll der globalen Suchen sieht nur die Plattform-Verwaltung."


@api.post("/globalsuche")
@requires_zugang
def globalsuche_starten():
    """{"q": Seriennummer, "bestaetigt": true} → {"treffer": [Steckbrief …], "mehr", "hinweis"} – nur Artikel, die das
    Konto nicht sieht."""
    return jsonify(globalsuche.suchen(json_body(), current_user()["id"]))


@api.post("/globalsuche/qr")
@requires_zugang
def globalsuche_qr():
    """{"token": QR-Token, "bestaetigt": true} → derselbe Steckbrief (ein Treffer) oder {"weiter": Adresse}, wenn der
    Artikel inzwischen im eigenen Bereich liegt."""
    return jsonify(globalsuche.steckbrief_qr(json_body(), current_user()["id"]))


@api.get("/globalsuche/protokoll")
def globalsuche_protokoll():
    """?seite= – neueste zuerst; vorher fällt heraus, was älter als die Aufbewahrungsfrist ist."""
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    if not is_admin():
        return jsonify(error=NUR_VERWALTUNG), 403
    seite = ganzzahl(request.args.get("seite"), "Seite", 1, 10 ** 6) or 1
    return jsonify(globalprotokoll.liste(seite))
