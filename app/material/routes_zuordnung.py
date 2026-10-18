"""Routen der Personenzuordnung (Phase 2 · Lieferung 1, Abschnitt 6.2).

Zuordnen, ändern und lösen darf, wer den Artikel verwaltet (an seiner Heimat); die Personen mit Zuordnungen in einem
Ordner (für den Filter) liest, wer dort ein Grundrecht hat – die Prüfsicht allein zeigt keine Personen. Fremdes
antwortet 404 wie Unbekanntes. Die Regeln stehen in services/zuordnung.py; die Personensuche für den Dialog ist
GET /api/material/nutzer (routes_freigaben.py)."""
from flask import jsonify

from ..auth import json_body
from .routes import api
from .services import Abgelehnt, bestand, zuordnung
from .services.rechte import requires_folder, requires_zugang, sicht


@api.put("/artikel/<int:iid>/zuordnung")
@requires_folder("verwalten", "iid")
def artikel_zuordnung(iid):
    """{"user_id": 17} ordnet den Artikel der Person zu, {"user_id": null} löst die Zuordnung."""
    return jsonify(artikel=bestand.artikel_json(zuordnung.setzen(iid, json_body()), voll=True))


@api.post("/artikel/zuordnen")
@requires_zugang
def artikel_zuordnen():
    """Mehrere Artikel auf einmal: {"ids": [...], "user_id": 17 | null} – ganz oder gar nicht. Wer nirgends verwaltet,
    bekommt 403, bevor die Kennungen gelesen werden."""
    if not sicht().irgendwo("verwalten"):
        raise Abgelehnt(zuordnung.NUR_VERWALTER, 403)
    return jsonify(geaendert=zuordnung.sammeln(json_body()))


@api.get("/ordner/<int:fid>/zugeordnete")
@requires_folder("grund", "fid")
def ordner_zugeordnete(fid):
    return jsonify(zugeordnete=zuordnung.zugeordnete(fid))
