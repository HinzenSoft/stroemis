"""Routen der Erinnerungen (Phase 2 · Lieferung 2).

Der Laufstand (Schalter, Sperre, Mailserver, letzter Lauf, Fehler) steht in GET /api/material/start unter
„erinnerungen“ – nur für die Material-Verwaltung (die Plattform-Verwaltung eingeschlossen). Hier nur der Probelauf: wer
beim nächsten Lauf welche Mail bekäme, mit Namen und Text, ohne Adressen. Er schreibt nichts. Mit ?demo=1 bezieht er
den DEMO-Bestand ein – nur zur Ansicht (auf dev ist alles DEMO); der echte Lauf lässt DEMO immer aus. Den Schalter je
Ordner nimmt PUT /api/material/ordner/<fid> (reminders_off). Die Regeln stehen in services/erinnerung.py."""
from flask import jsonify, request

from .routes import api
from .services import erinnerung, wahr
from .services.rechte import material_verwaltung_required


@api.get("/erinnerungen/probelauf")
@material_verwaltung_required
def erinnerungen_probelauf():
    """Der nächste echte Lauf (heute, wenn der Mailteil heute noch nicht lief, sonst morgen) – nichts wird verschickt
    oder vermerkt. demo=1: DEMO-Artikel, -Freigaben und -Konten zählen mit (nur Ansicht, Mails mit „demo“: true)."""
    demo = wahr(request.args, "demo", "DEMO-Bestand einbeziehen")
    return jsonify(erinnerung.probelauf(demo=demo))
