"""Routen der Recherche per Claude API an einer Produktmeldung (services/recherche.py, app/ki.py; 21.11.2026).

Alles nur für die Material-Verwaltung (B1 A, B2 A – katalog_required). Ohne ANTHROPIC_API_KEY antworten nur Start und
Abbrechen mit 503 – was schon da ist (Stand, Vorschlag, Dateien, Übernahme, Nachladen), braucht keinen Aufruf der API
und bleibt erreichbar (Browserprüfung vom 21.11.2026, V2); GET /meldungen trägt dann „recherche“, aber kein
„recherche_moeglich“ (kein Knopf „Recherchieren lassen“). Unbekannte Meldungen: 404 wie überall. Die Dateien eines Vorschlags liefert
eine eigene Route aus (die Medienroute kennt nur Dateien mit Dokumentzeile) – mit denselben Kopfzeilen wie ein
Herstellerdokument (strenge CSP mit sandbox, nosniff, nie in einem gemeinsamen Zwischenspeicher).

Antworten (Beispiele im Bericht zum Bau):
  POST   /api/material/meldungen/<id>/recherche              {domains, fotos, bemerkung} → 202 {recherche, moeglich}
  GET    /api/material/meldungen/<id>/recherche              → {recherche (voll), moeglich, start}
  POST   /api/material/meldungen/<id>/recherche/abbrechen    → {recherche}
  GET    /api/material/meldungen/<id>/recherche/dateien/<n>  → die Datei
  POST   /api/material/meldungen/<id>/recherche/uebernehmen  {gemeinsam, ausfuehrungen, antwort} → 201
         {meldung, produkte, anhaengen, recherche}
  POST   /api/material/meldungen/<id>/recherche/nachladen    → {meldung, produkte, anhaengen, recherche}"""
from functools import wraps

from flask import jsonify, send_from_directory

from .. import ki
from ..auth import json_body
from .routes import api
from .services import Abgelehnt, recherche
from .services.rechte import katalog_required

NICHT_EINGERICHTET = "Die Recherche per Claude API ist nicht eingerichtet (kein API-Schlüssel)."


def _verfuegbar(f):
    """503 ohne Schlüssel – nach der Rechteprüfung (katalog_required steht außen), damit niemand sonst etwas erfährt.
    Nur an Start und Abbrechen: Nur sie hätten mit der API zu tun."""
    @wraps(f)
    def wrapper(*a, **kw):
        if not ki.verfuegbar():
            raise Abgelehnt(NICHT_EINGERICHTET, 503)
        return f(*a, **kw)
    return wrapper


@api.post("/meldungen/<int:mid>/recherche")
@katalog_required
@_verfuegbar
def recherche_starten(mid):
    """Start → 202. 409: Meldung erledigt oder es läuft schon eine Recherche; 429: Kontingent; 400: Domains."""
    z = recherche.starten(mid, json_body())
    return jsonify(recherche=recherche.status_json(z), moeglich=recherche.moeglich()), 202


@api.get("/meldungen/<int:mid>/recherche")
@katalog_required
def recherche_lesen(mid):
    return jsonify(recherche.lesen(mid))


@api.post("/meldungen/<int:mid>/recherche/abbrechen")
@katalog_required
@_verfuegbar
def recherche_abbrechen(mid):
    """Setzt das Abbruch-Kennzeichen; der Lauf endet „abgebrochen“, sobald er es liest (im selben Arbeitsprozess
    sofort, sonst mit dem nächsten Lebenszeichen). 409, wenn er nicht mehr läuft."""
    return jsonify(recherche=recherche.status_json(recherche.abbrechen(mid)))


@api.get("/meldungen/<int:mid>/recherche/dateien/<int:n>")
@katalog_required
def recherche_datei(mid, n):
    ordner, name, mime = recherche.datei(mid, n)
    resp = send_from_directory(ordner, name, mimetype=mime, as_attachment=False, download_name=name, max_age=0)
    resp.cache_control.public = None
    resp.cache_control.private = True
    resp.cache_control.no_store = True
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; sandbox"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@api.post("/meldungen/<int:mid>/recherche/uebernehmen")
@katalog_required
def recherche_uebernehmen(mid):
    """Legt die gewählten Ausführungen als Produkte an und erledigt die Meldung (201); schon übernommen: hängt nur
    fehlende Dateien an (200)."""
    schon = (recherche._lauf(mid) or {}).get("status") == "uebernommen"
    return jsonify(recherche.uebernehmen(mid, json_body())), 200 if schon else 201


@api.post("/meldungen/<int:mid>/recherche/nachladen")
@katalog_required
def recherche_nachladen(mid):
    return jsonify(recherche.nachladen(mid))
