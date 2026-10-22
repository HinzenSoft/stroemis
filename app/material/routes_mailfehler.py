"""Routen zum Mailfehler-Protokoll (Phase 4 · Lieferung 1, services/mailprotokoll.py).

Gelesen wird es im Block „mailfehler“ von GET /api/material/start (routes.start) – jeder in seiner Sicht: die
Material- und Plattform-Verwaltung alles, wer einen Zweig verwaltet, die Zeilen seiner Gliederungen ohne die Rollen, die
nur die Verwaltung angehen (mailprotokoll.sichtfilter). Hier nur das Abhaken: eine Zeile (unbekannt oder außerhalb der
Sicht: 404 wie unbekannt; schon erledigt: 200, nichts ändert sich) und alle Zeilen der eigenen Sicht. Wer abhakt, steht
mit Namen in der Zeile (Handelnder, wie im Löschkonzept). Kein „Erneut senden“: Mailtexte werden nicht gespeichert;
Erinnerungen holt der nächste Lauf nach."""
from flask import jsonify

from .routes import api
from .services import Abgelehnt, akteur, mailprotokoll
from .services.rechte import requires_zugang

FEHLT = "Mailfehler nicht gefunden."


@api.post("/mailfehler/<int:mfid>/erledigt")
@requires_zugang
def mailfehler_erledigt(mfid):
    """Eine Zeile abhaken → `zeile` (mit `erledigt_at`, `erledigt_von_name`). 404 für Unbekanntes und Fremdes."""
    _, name = akteur()
    z = mailprotokoll.erledigen(mfid, name)
    if not z:
        raise Abgelehnt(FEHLT, 404)
    return jsonify(zeile=z)


@api.post("/mailfehler/alle-erledigt")
@requires_zugang
def mailfehler_alle_erledigt():
    """Alle offenen Zeilen der eigenen Sicht abhaken → `anzahl`."""
    _, name = akteur()
    return jsonify(anzahl=mailprotokoll.alle_erledigen(name))
