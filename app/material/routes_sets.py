"""Routen für Hersteller-Sets (Phase 4 · Lieferung 2, Paket K2): Set prüfen und Teile entnehmen, tauschen, einsetzen.

Alle hängen am Set-Artikel (<iid>); die Rechte prüft requires_folder an seiner Heimat – Teile haben dieselbe. Ein Teil
nennt die Anfrage mit „teil_id“: Gehört es nicht zu diesem Set (fremd oder unbekannt), antwortet der Dienst 404 wie für
Unbekanntes (Entwurf H). Set prüfen eröffnet, wer prüfen darf; abbrechen darf, wer die Set-Prüfung eröffnet hat, und der
Materialwart (verwalten – wie eine Reservierung aufheben), andere bekommen 403. Teile entnimmt, tauscht und setzt ein,
wer verwaltet. Festschreiben, Set aussondern und Teil
löschen laufen über die vorhandenen Routen (pruefung_abschliessen, artikel_aussondern mit „verbleib“, artikel_loeschen).
Die Regeln stehen in services/setlauf.py und services/setaustausch.py.

Dazu die Seite „Set prüfen“ (Oberfläche O2): /material/artikel/<iid>/set-pruefung zeigt den Prüfumfang je Teil und führt
von Prüfung zu Prüfung; sehen genügt (wie bei „Prüfung starten“), die Knöpfe richten sich nach „darf“.

Seit P4-L2b (KERN A): vorhandenen Artikel einsetzen („item_id“ an teil-einsetzen; beim Anlegen „teile[].item_id“ an
POST /artikel), die Auswahl dafür (kandidaten am Set bzw. am Ablageordner des neuen Sets – verwalten), Set auflösen und
„Bestandteil ersetzt“ – beide verwalten am Set. Eine Kennung im Inhalt („item_id“), die das Konto nicht verwaltet, und
eine Position, die nicht zu diesem Set gehört, antworten wie Unbekanntes mit 404."""
from flask import g, jsonify, request

from ..auth import current_user, json_body
from .routes import _pruefer, _seite, api, seiten
from .services import Abgelehnt, bestand, kennung, setaustausch, setlauf, sets
from .services.rechte import darf_artikel, requires_folder


@seiten.get("/material/artikel/<int:iid>/set-pruefung")
def set_lauf_seite(iid):
    """Die Seite „Set prüfen“: ?durchgang= aus dem Ordner-Durchgang (der Lauf setzt dann round_id), ?lauf= eine frühere
    Set-Prüfung dieses Sets ansehen. Ein fremder Artikel antwortet wie Unbekanntes mit 404."""
    return _seite("set_lauf", bezug=("artikel", iid), id=iid, durchgang=request.args.get("durchgang", type=int),
                  lauf=request.args.get("lauf", type=int))


def _set_antwort(iid, **mehr):
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True), **mehr)


@api.get("/artikel/<int:iid>/set-lauf")
@requires_folder("lesen", "iid")
def set_lauf_lesen(iid):
    """Die offene Set-Prüfung voll (setlauf.lauf_json) oder null, dazu die Läufe des Sets (kurz, neueste zuerst). ?lauf=
    eine andere Set-Prüfung dieses Sets voll (404, wenn sie nicht zu ihm gehört). Ein Artikel, der kein Set ist: null
    und [] – wie ein Set ohne Prüfung."""
    a = bestand.artikel(iid)
    if a["parent_item_id"] or not sets.ist_set_artikel(a):
        return jsonify(lauf=None, laeufe=[])
    lid = kennung(request.args.get("lauf"), "Set-Prüfung", leer_erlaubt=True)
    if lid is not None:
        lf = setlauf.lauf(lid)
        if lf["set_item_id"] != iid:
            raise Abgelehnt("Set-Prüfung nicht gefunden.", 404)
    else:
        lf = setlauf.offener(iid)
    return jsonify(lauf=setlauf.lauf_json(lf, current_user()["id"]) if lf else None, laeufe=setlauf.laeufe(iid))


@api.post("/artikel/<int:iid>/set-lauf")
@requires_folder("pruefen", "iid")
def set_lauf_eroeffnen(iid):
    """„Set prüfen“: {"durchgang_id": Kennung | null} – eröffnet die Set-Prüfung (201) oder liefert die offene (200)."""
    rid = kennung(json_body().get("durchgang_id"), "Prüfdurchgang", leer_erlaubt=True)
    lid, neu = setlauf.eroeffnen(iid, _pruefer(), rid)
    return _set_antwort(iid, lauf=setlauf.lauf_json(setlauf.lauf(lid), current_user()["id"])), 201 if neu else 200


@api.delete("/artikel/<int:iid>/set-lauf")
@requires_folder(("pruefen", "verwalten"), "iid")
def set_lauf_abbrechen(iid):
    """Die offene Set-Prüfung abbrechen (wer sie eröffnet hat oder der Materialwart, sonst 403) – „bleibt“: false, wenn sie
    mangels Prüfung ganz entfernt wurde."""
    bleibt = setlauf.abbrechen(iid, _pruefer(), darf_verwalten=darf_artikel("verwalten", g.mat_artikel))
    return _set_antwort(iid, bleibt=bleibt)


@api.post("/artikel/<int:iid>/teil-entnehmen")
@requires_folder("verwalten", "iid")
def teil_entnehmen(iid):
    """{"teil_id", "verbleib": "weiterfuehren" | "aussondern", bei „aussondern“ "grund", "bemerkung", "datum"} – liefert
    das Set („artikel“) und das entnommene Teil („teil“)."""
    tid = setaustausch.entnehmen(iid, json_body(), _pruefer())
    return _set_antwort(iid, teil=bestand.artikel_json(bestand.artikel(tid), voll=True))


@api.post("/artikel/<int:iid>/teil-tauschen")
@requires_folder("verwalten", "iid")
def teil_tauschen(iid):
    """{"teil_id" (das alte), "verbleib" wie beim Entnehmen, Felder des neuen Teils ("serial_no", "manufactured_on",
    "purchased_on", "first_use_on", "length_m"), "bestaetigt"} – 201 mit Set, neuem Teil und „hinweise“."""
    neu, hinweise = setaustausch.einsetzen(iid, json_body(), _pruefer(), tausch=True)
    return _set_antwort(iid, teil=bestand.artikel_json(bestand.artikel(neu), voll=True), hinweise=hinweise), 201


@api.post("/artikel/<int:iid>/teil-einsetzen")
@requires_folder("verwalten", "iid")
def teil_einsetzen(iid):
    """{"slot_id" (Position der Kopie, an der ein Teil fehlt – bei genau einer darf es fehlen), Felder des neuen Teils
    oder "item_id" (vorhandenen Artikel einsetzen, L2b), "bestaetigt"} – 201 mit Set, neuem bzw. eingesetztem Teil und
    „hinweise“."""
    neu, hinweise = setaustausch.einsetzen(iid, json_body(), _pruefer(), tausch=False)
    return _set_antwort(iid, teil=bestand.artikel_json(bestand.artikel(neu), voll=True), hinweise=hinweise), 201


@api.get("/artikel/<int:iid>/kandidaten")
@requires_folder("verwalten", "iid")
def set_kandidaten(iid):
    """Auswahl „aus dem Bestand wählen“ für „Teil einsetzen“: ?slot_id= (einzeln geführte Position dieses Sets), ?q=
    (mindestens 2 Zeichen) – {treffer, weitere}; ohne Treffer 404, bei genau passender Nummer mit anderem Produkt 409
    (setaustausch.kandidaten)."""
    return jsonify(setaustausch.kandidaten_am_set(iid, request.args.get("slot_id"), request.args.get("q")))


@api.get("/ordner/<int:fid>/kandidaten")
@requires_folder("verwalten", "fid")
def ordner_kandidaten(fid):
    """Dieselbe Auswahl für „Artikel anlegen“ mit Set-Produkt: ?product_id= (Produkt der Position), ?q= – im Ordner, in
    dem das Set entsteht."""
    return jsonify(setaustausch.kandidaten_im_ordner(fid, request.args.get("product_id"), request.args.get("q")))


@api.post("/artikel/<int:iid>/aufloesen")
@requires_folder("verwalten", "iid")
def set_aufloesen(iid):
    """„Set auflösen“ (nur ein freies Set, das allein löschbar ist – sonst 409 mit Grund): die Teile bleiben frei im Ordner,
    der Set-Artikel wird gelöscht. {} – liefert {ok, teile: [{id, inventory_no}]}."""
    return jsonify(ok=True, teile=setaustausch.aufloesen(iid))


@api.post("/artikel/<int:iid>/bestandteil-ersetzt")
@requires_folder("verwalten", "iid")
def bestandteil_ersetzt(iid):
    """{"slot_id" (nicht einzeln geführte Position), "datum", "bemerkung", "bestaetigt"} – sperrt das Set bis zur
    Set-Prüfung; liefert das Set („artikel“)."""
    setaustausch.bestandteil_ersetzt(iid, json_body())
    return _set_antwort(iid)
