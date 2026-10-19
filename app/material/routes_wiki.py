"""Routen der Prüfanleitung aus dem Wiki (Phase 2 · Lieferung 3): Seitenwahl und Verknüpfung am Prüfformular.

Verknüpfen darf nur die Material-Verwaltung (die Plattform-Verwaltung zählt mit) – und seit der Entscheidung vom
19.10.2026 nur mit Stufe Mitglied im Wiki; ohne sie 403 mit Klartext. Den Inhalt einer Seite liefert keine Route hier:
Der Browser holt ihn über die Endpunkte des Wikis selbst (mit dessen Rechten). Die Regeln stehen in
services/wikiverweis.py."""
from functools import wraps

from flask import jsonify, request

from ..auth import json_body
from .routes import api
from .services import Abgelehnt, katalog, wikiverweis
from .services.rechte import katalog_required


def wiki_stufe_required(f):
    """Nach katalog_required: dazu die Stufe Mitglied im Wiki – sonst 403 mit dem Weg dorthin."""
    @wraps(f)
    def wrapper(*a, **kw):
        if not wikiverweis.darf_verknuepfen():
            raise Abgelehnt(wikiverweis.NUR_MIT_WIKI, 403)
        return f(*a, **kw)
    return wrapper


@api.get("/wiki/seiten")
@katalog_required
@wiki_stufe_required
def wiki_seiten():
    """Seitenwahl: Titelsuche über die Seiten, die dieses Konto im Wiki lesen darf (ohne Papierkorb und Vorlagen)."""
    return jsonify(wikiverweis.seiten(request.args.get("q", "")))


@api.put("/formulare/<int:fid>/wiki")
@katalog_required
@wiki_stufe_required
def formular_wiki(fid):
    """{"seite": id | null} – auch an benutzten Formularen; geschrieben wird nur die Verknüpfung."""
    wikiverweis.setzen(fid, json_body())
    return jsonify(formular=katalog.formular_json(katalog.formular(fid)))
