"""Routen des Bestandsimports (Phase 2 · Lieferung 3): Probelauf und Übernehmen einer Bestandsliste (CSV oder .xlsx)
in einen Zielordner, die Nacharbeit dieses Ordners samt CSV und die Seite /material/ordner/<fid>/import.

Alles nur mit „verwalten“ am Zielordner (die Material-Verwaltung überall) – requires_folder mit der Kennung aus dem
Pfad. Zeilenkennungen im Inhalt (zeilen) prüft der Dienst gegen genau diesen Zielordner: Eine fremde antwortet wie eine
unbekannte (404). Antworten mit Listendaten tragen Cache-Control no-store (wie der Export). Die Regeln stehen in
services/bestandsimport.py, das Lesen der Datei in services/tabelle.py."""
import io
import json

from flask import jsonify, redirect, render_template, request, send_file, url_for

from ..auth import current_user, json_body
from .routes import _bezug_seite, _fehlerseite, _seite, api, seiten
from .services import Abgelehnt, bestand, bestandsimport, eingabe, kennung, wahr
from .services.rechte import _bezug, darf, requires_folder, zugang, zugang_meldung

NUR_VERWALTER = "Bestandslisten importiert, wer den Ordner verwaltet."


def _privat(resp, code=200):
    """Listendaten aus fremden Dateien: nie in einen Zwischenspeicher."""
    resp.status_code = code
    resp.cache_control.no_store = True
    resp.cache_control.private = True
    return resp


def _datei_und_zuordnung():
    """Datei („file“) und Spaltenzuordnung („zuordnung“, JSON {"<index>": feld}) aus dem Multipart-Formular."""
    f = request.files.get("file")
    if not f or not f.filename:
        raise Abgelehnt("Bitte eine Datei wählen (Excel-Arbeitsmappe .xlsx oder CSV).")
    roh = f.stream.read(bestandsimport.MAX_BYTES + 1)
    zuordnung = None
    text = (eingabe().get("zuordnung") or "").strip()
    if text:
        try:
            zuordnung = json.loads(text)
        except (ValueError, RecursionError):
            raise Abgelehnt("Die Spaltenzuordnung ist kein gültiges JSON.")
        if not isinstance(zuordnung, dict) or not all(isinstance(v, str) for v in zuordnung.values()):
            raise Abgelehnt("Die Spaltenzuordnung muss ein Objekt {Spaltenindex: Feld} sein.")
    return roh, f.filename, zuordnung


# --- Seite --------------------------------------------------------------------------------------------------------

@seiten.get("/material/ordner/<int:fid>/import", endpoint="bestandsimport")
def bestandsimport_seite(fid):
    """Import und Nacharbeit dieses Zielordners. Wer den Ordner nicht sieht: 404 wie für Unbekanntes; wer ihn sieht,
    aber nicht verwaltet: 403; ein Systemordner: 409. Den Inhalt zeichnet material.js (Ansicht „bestandsimport“)."""
    u = current_user()
    if u and zugang(u) and not _bezug_seite("ordner", fid):
        if not darf("verwalten", fid):
            return _fehlerseite(403, NUR_VERWALTER)
        if bestand.ordner(fid)["system_kind"]:
            return _fehlerseite(409, bestandsimport.NUR_SYSTEM)
    return _seite("bestandsimport", bezug=("ordner", fid), id=fid)



@seiten.get("/material/ordner/<int:fid>/nacharbeit.csv")
def nacharbeit_csv(fid):
    """Die offenen Zeilen der Nacharbeit als CSV – eine Seite wie der Export: ohne Anmeldung zur Anmeldung, ohne
    Modulzugang 403, Fremdes 404, ohne Verwalten 403; Fehler als Seite."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.path))
    if not zugang(u):
        return _fehlerseite(403, zugang_meldung(u))
    try:
        b = _bezug("fid", {"fid": fid})
        if not darf("lesen", b.ordner_id):
            raise Abgelehnt(b.meldung, 404)
        if not darf("verwalten", b.ordner_id):
            raise Abgelehnt(NUR_VERWALTER, 403)
        daten, name = bestandsimport.nacharbeit_csv(fid)
    except Abgelehnt as exc:
        return render_template("error.html", user=u, code=exc.code, message=str(exc)), exc.code
    return _privat(send_file(io.BytesIO(daten), mimetype="text/csv", as_attachment=True, download_name=name))


# --- Import -------------------------------------------------------------------------------------------------------

@api.post("/ordner/<int:fid>/import/probelauf")
@requires_folder("verwalten", "fid")
def import_probelauf(fid):
    """Probelauf: prüft die Datei mit der (automatischen oder mitgeschickten) Spaltenzuordnung und schreibt nichts –
    außer einer Zeile im Protokoll der globalen Suche, wenn er fremde Dubletten nennt. Bericht nach 8.5."""
    roh, name, zuordnung = _datei_und_zuordnung()
    b = bestandsimport.probelauf(fid, roh, name, zuordnung)
    return _privat(jsonify(bestandsimport.bericht_json(b)))


@api.post("/ordner/<int:fid>/import")
@requires_folder("verwalten", "fid")
def import_uebernehmen(fid):
    """Übernehmen: dieselbe Prüfung, dann in einer Transaktion – Artikel anlegen, Nacharbeit schreiben. Zeilen ohne
    Herstellerseriennummer bekommen eine STR-Nummer. Ist keine Spalte als Seriennummer zugeordnet (der Probelauf sagt
    es mit „ohne_seriennummern_bestaetigen“), braucht es das Feld „ohne_seriennummern“ = true – sonst 409 (Entscheidung
    vom 20.10.2026). Das alte Feld „ohne_serie“ wird übergangen."""
    roh, name, zuordnung = _datei_und_zuordnung()
    ohne = wahr(eingabe(), "ohne_seriennummern", "Ohne Seriennummern")
    b, _ = bestandsimport.uebernehmen(fid, roh, name, zuordnung, ohne_seriennummern=ohne)
    return _privat(jsonify(bestandsimport.bericht_json(b)), 201)


# --- Nacharbeit ---------------------------------------------------------------------------------------------------

@api.get("/ordner/<int:fid>/nacharbeit")
@requires_folder("verwalten", "fid")
def nacharbeit(fid):
    seite = kennung(request.args.get("seite") or 1, "Seite")
    return _privat(jsonify(bestandsimport.nacharbeit_json(fid, request.args.get("gruppe"), seite)))


@api.post("/ordner/<int:fid>/nacharbeit/produkt")
@requires_folder("verwalten", "fid")
def nacharbeit_produkt(fid):
    """Produkt zuordnen – {"angabe": …} (alle offenen Zeilen der Angabe) oder {"zeilen": [Nacharbeit-Nr.]}, dazu
    „product_id“ (null nimmt die Wahl zurück)."""
    d = json_body()
    n = bestandsimport.produkt_setzen(fid, d.get("product_id"), angabe=d.get("angabe"),
                                      zeilen=d.get("zeilen") if "zeilen" in d else None)
    return jsonify(gesetzt=n)


@api.post("/ordner/<int:fid>/nacharbeit/melden")
@requires_folder("verwalten", "fid")
def nacharbeit_melden(fid):
    """Produkt melden aus der Nacharbeit – Felder wie POST /meldungen (ohne folder_id: Ziel ist dieser Ordner), dazu
    „angabe“; mit Fotos als Formular (Feld „fotos“, mehrfach)."""
    from .services import meldung
    d = eingabe()
    mid = bestandsimport.melden(fid, d.get("angabe"), d, request.files.getlist("fotos"))
    return jsonify(meldung=meldung.meldung_json(meldung.meldung(mid))), 201


@api.post("/ordner/<int:fid>/nacharbeit/pruefen")
@requires_folder("verwalten", "fid")
def nacharbeit_pruefen(fid):
    """Erneut prüfen ({"zeilen": [Nacharbeit-Nr.] | "alle", "uebernehmen": bool}) – ohne uebernehmen nur der Bericht,
    mit uebernehmen werden übernehmbare Zeilen Artikel."""
    d = json_body()
    ergebnis = bestandsimport.nachpruefen(fid, d.get("zeilen"),
                                          uebernehmen=wahr(d, "uebernehmen", "Übernehmen"))
    return _privat(jsonify(ergebnis))


@api.post("/ordner/<int:fid>/nacharbeit/verwerfen")
@requires_folder("verwalten", "fid")
def nacharbeit_verwerfen(fid):
    n = bestandsimport.verwerfen(fid, json_body().get("zeilen"))
    return jsonify(verworfen=n)
