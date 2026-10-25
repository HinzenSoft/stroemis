"""Routen zu den Änderungsanträgen an Stammdaten (Entscheidungen vom 21.10.2026; seit dem 24.10.2026 an allen
Stammdaten, Freigabe durch die zuständigen Materialwarte – services/antrag.py).

Beantragen dürfen Materialwart und Prüfer des Artikels (requires_folder mit verwalten oder pruefen – fremd 404 wie
unbekannt); der Dienst prüft in der Transaktion noch einmal. Die Liste liest jeder mit Modulzugang – jeder seine eigenen
Anträge (solange er den Artikel liest) und die, die er entscheiden darf. Bestätigen und ablehnen die Materialwarte des
Ordners (eigene Freigabe „verwalten“ an der Heimat oder darüber; die Material-Verwaltung nur mit so einer Freigabe – E6),
den eigenen Antrag eingeschlossen (E5); der Dienst prüft das in der Transaktion: Wer den Artikel nicht liest, bekommt
404, wer ihn liest, aber nicht zuständig ist, 403. Zurückziehen nur der Antragsteller seinen eigenen offenen."""
from flask import jsonify, request

from ..auth import json_body
from .routes import api
from .services import antrag, bestand
from .services.rechte import requires_folder, requires_zugang


@api.post("/artikel/<int:iid>/antrag")
@requires_folder(("verwalten", "pruefen"), "iid")
def antrag_stellen(iid):
    """Einen Sammelantrag stellen: die Felder, die sich ändern sollen (`product_id`, `serial_no`, `manufactured_on`,
    `purchased_on`, `first_use_on`, `retire_by`, `interval_months` – nur Abweichungen zählen; leer entfernt Kauf,
    Erstgebrauch und Intervall), `begruendung` Pflicht → 201 `antrag` (mit `aenderungen`), `artikel`, `mail` (an die
    zuständigen Materialwarte unterwegs – ohne sie an die Material-Verwaltung; false bei DEMO, dev-Sperre, ohne
    Mailserver oder ohne Empfänger). 409, wenn am Artikel schon ein Antrag offen ist."""
    kid, mail = antrag.stellen(iid, json_body())
    item = bestand.artikel(iid)
    return jsonify(antrag=antrag.antrag_json(antrag.antrag(kid), item),
                   artikel=bestand.artikel_json(item, voll=True), mail=mail), 201


@api.get("/antraege")
@requires_zugang
def antraege():
    """Sammelanträge nach Stand (`status` offen | erledigt | alle; Vorgabe offen): die eigenen zu Artikeln, die das Konto
    liest, und die, die es entscheiden darf; je Antrag `entscheiden`. `zu_entscheiden`: offene, die das Konto
    entscheiden darf (die Zahl am Knopf „Änderungsanträge“). `?nur_zahl=1`: nur `zu_entscheiden` (die Blase im Bestand –
    ohne die ganze Liste zu rechnen)."""
    if request.args.get("nur_zahl") in ("1", "true", "ja"):
        return jsonify(zu_entscheiden=antrag.zu_entscheiden())
    filter_ = request.args.get("status") if request.args.get("status") in antrag.FILTER else "offen"
    return jsonify(antraege=antrag.liste(filter_), filter=filter_, zu_entscheiden=antrag.zu_entscheiden())


@api.post("/antraege/<int:anid>/bestaetigen")
@requires_zugang
def antrag_bestaetigen(anid):
    """Bestätigen (`antwort` freiwillig) – alle Änderungen stehen danach am Artikel. Nur die Materialwarte des Ordners."""
    kid = antrag.bestaetigen(anid, json_body())
    return jsonify(antrag=antrag.antrag_json(antrag.antrag(kid)))


@api.post("/antraege/<int:anid>/ablehnen")
@requires_zugang
def antrag_ablehnen(anid):
    """Ablehnen (`antwort` Pflicht) – am Artikel ändert sich nichts. Nur die Materialwarte des Ordners."""
    kid = antrag.ablehnen(anid, json_body())
    return jsonify(antrag=antrag.antrag_json(antrag.antrag(kid)))


@api.post("/antraege/<int:anid>/zurueckziehen")
@requires_zugang
def antrag_zurueckziehen(anid):
    """Den eigenen offenen Antrag zurückziehen – nur der Antragsteller, solange er den Artikel liest (sonst 404); 409,
    wenn er schon entschieden oder zurückgezogen ist. Keine Mail."""
    kid = antrag.zurueckziehen(anid)
    return jsonify(antrag=antrag.antrag_json(antrag.antrag(kid)))
