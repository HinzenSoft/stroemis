"""Routen der Erinnerungen (Phase 2 · Lieferung 2).

Der Laufstand (Schalter, Sperre, Mailserver, letzter Lauf, Fehler) steht in GET /api/material/start unter
„erinnerungen“ – nur für die Material-Verwaltung (die Plattform-Verwaltung eingeschlossen). Hier nur der Probelauf: wer
beim nächsten Lauf welche Mail bekäme, mit Namen und Text, ohne Adressen. Er schreibt nichts. Den Schalter je Ordner
nimmt PUT /api/material/ordner/<fid> (reminders_off). Die Regeln stehen in services/erinnerung.py."""
from flask import jsonify

from .routes import api
from .services import erinnerung
from .services.rechte import material_verwaltung_required


@api.get("/erinnerungen/probelauf")
@material_verwaltung_required
def erinnerungen_probelauf():
    """Der nächste echte Lauf (heute, wenn der Mailteil heute noch nicht lief, sonst morgen) – nichts wird verschickt
    oder vermerkt."""
    return jsonify(erinnerung.probelauf())
