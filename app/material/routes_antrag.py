"""Routen zu den Änderungsanträgen an festen Stammdaten (Entscheidungen vom 21.10.2026, services/antrag.py).

Beantragen dürfen Materialwart und Prüfer des Artikels (requires_folder mit verwalten oder pruefen – fremd 404 wie
unbekannt); der Dienst prüft in der Transaktion noch einmal. Die Liste liest jeder mit Modulzugang – die
Material-Verwaltung alle Anträge, jedes andere Konto seine eigenen; bestätigen und ablehnen nur die Material-Verwaltung
(die Plattform-Verwaltung eingeschlossen)."""
from flask import jsonify, request

from ..auth import json_body
from .routes import api
from .services import antrag, bestand, meldung
from .services.rechte import ist_material_verwaltung, material_verwaltung_required, requires_folder, requires_zugang


@api.post("/artikel/<int:iid>/antrag")
@requires_folder(("verwalten", "pruefen"), "iid")
def antrag_stellen(iid):
    """Änderung von Seriennummer und/oder Herstelldatum beantragen (`serial_no`, `manufactured_on` oder
    `herstellung_entfernen`, `begruendung` Pflicht) → 201 `antraege` (je Feld einer), `artikel`, `mail` (an die
    Material-Verwaltung unterwegs; false bei DEMO, dev-Sperre, ohne Mailserver oder ohne Empfänger)."""
    ids, mail = antrag.stellen(iid, json_body())
    item = bestand.artikel(iid)
    return jsonify(antraege=[antrag.antrag_json(antrag.antrag(a), item) for a in ids],
                   artikel=bestand.artikel_json(item, voll=True), mail=mail), 201


@api.get("/antraege")
@requires_zugang
def antraege():
    """Anträge nach Stand (`status` offen | erledigt | alle; Vorgabe offen für die Material-Verwaltung, sonst alle):
    die Material-Verwaltung alle, sonst die eigenen zu Artikeln, die das Konto liest. `bearbeiten`: darf entscheiden;
    `offen`: Zahl der offenen, die das Konto sieht; `meldungen_offen` (nur Material-Verwaltung): offene Produktmeldungen
    für den Reiter daneben."""
    mv = ist_material_verwaltung()
    filter_ = request.args.get("status") if request.args.get("status") in antrag.FILTER else ("offen" if mv else "alle")
    return jsonify(antraege=antrag.liste(filter_), filter=filter_, alle=mv, bearbeiten=mv, offen=antrag.anzahl_offen(),
                   meldungen_offen=meldung.anzahl_offen() if mv else None)


@api.post("/antraege/<int:anid>/bestaetigen")
@material_verwaltung_required
def antrag_bestaetigen(anid):
    """Bestätigen (`antwort` freiwillig) – die Änderung steht danach am Artikel."""
    antrag.bestaetigen(anid, json_body())
    r = antrag.antrag(anid)
    return jsonify(antrag=antrag.antrag_json(r))


@api.post("/antraege/<int:anid>/ablehnen")
@material_verwaltung_required
def antrag_ablehnen(anid):
    """Ablehnen (`antwort` Pflicht) – am Artikel ändert sich nichts."""
    antrag.ablehnen(anid, json_body())
    return jsonify(antrag=antrag.antrag_json(antrag.antrag(anid)))
