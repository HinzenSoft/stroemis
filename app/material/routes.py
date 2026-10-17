"""Routen des Moduls Material.

Seiten (/material/…, /m/<token>) sind dünne Hüllen: Sie prüfen das Recht, nennen die Ansicht und
überlassen den Inhalt material.js, das ihn über die Schnittstelle (/api/material/…) holt – dasselbe
Muster wie im Prüfungsbereich. Jede Route prüft ihr Recht selbst; ein ausgeblendeter Knopf ist kein
Schutz. Fachregeln stehen in services/, hier wird nur gelesen, aufgerufen und geantwortet."""
import json
import os
import sqlite3

from flask import (Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, send_file,
                   send_from_directory, url_for)

from .. import db
from ..auth import attempts_exceeded, current_user, eingabefehler_abfangen, json_body, note_attempt
from . import models
from .services import (Abgelehnt, anhang, bestand, durchgang, journal, katalog, kennung, meldung, protokoll, pruefung,
                       search, unterschrift)
from .services import status as st
from .services.rechte import _ordner_aus_anfrage, darf, darf_alles, ist_katalogpfleger, katalog_required, requires_folder

seiten = Blueprint("material", __name__, template_folder="templates", static_folder="static",
                   static_url_path="/static/material", cli_group="material")
api = Blueprint("material_api", __name__, url_prefix="/api/material")
eingabefehler_abfangen(api)

# Was die Uploadrouten höchstens annehmen (size_guard in app/__init__.py liest das). Ein wenig Luft
# für den Rahmen der Multipart-Anfrage.
UPLOAD_GRENZEN = {
    "material_api.produkt_bild": katalog.BILD_MAX_BYTES + 1024 * 1024,
    "material_api.ordner_foto": katalog.BILD_MAX_BYTES + 1024 * 1024,
    "material_api.dokument_neu": katalog.DOK_MAX_BYTES + 1024 * 1024,
    "material_api.dokument_version": katalog.DOK_MAX_BYTES + 1024 * 1024,
    "material_api.kategorie_dokument_neu": katalog.DOK_MAX_BYTES + 1024 * 1024,
    "material_api.punkt_foto": katalog.BILD_MAX_BYTES + 1024 * 1024,
    "material_api.anhang_neu": anhang.MAX_BYTES + 1024 * 1024,
    "material_api.meldung_anlegen": meldung.MAX_FOTOS * katalog.BILD_MAX_BYTES + 1024 * 1024,
    # Unterschriften kommen als data:-URL im JSON (Signatur-Pad) – mehr als die übliche Grenze von 1 MB.
    "material_api.unterschrift_setzen": unterschrift.MAX_ZEICHEN + 64 * 1024,
    "material_api.punkt_setzen": unterschrift.MAX_ZEICHEN + 64 * 1024,
    # Die Prüfseite nimmt ein ganzes Protokoll samt angefügter Anhänge an – ohne Anmeldung, daher gebremst
    # (PRUEFEN_JE_VIERTELSTUNDE) und nicht unbegrenzt.
    "material_api.pruefen": 200 * 1024 * 1024,
}
PRUEFEN_JE_VIERTELSTUNDE = 20


@api.errorhandler(Abgelehnt)
def _abgelehnt(exc):
    return jsonify(error=str(exc)), exc.code


@api.errorhandler(sqlite3.IntegrityError)
def _integritaet(exc):
    """Zwei Leute ändern dasselbe gleichzeitig – kein Serverfehler, sondern ein Hinweis zum Neuladen."""
    current_app.logger.warning("Integritätsfehler an %s %s: %s", request.method, request.path, exc)
    return jsonify(error="Das wurde zwischenzeitlich anderswo geändert. Bitte neu laden."), 409


def _eingabe():
    """JSON-Body oder – bei Dateiuploads – die Formularfelder der Multipart-Anfrage."""
    if request.files or (request.content_type or "").startswith("multipart/"):
        return request.form
    return json_body()


def _seite_args(maxi=search.PRO_SEITE_MAX):
    """Seite und Seitengröße aus der Anfrage – geklemmt: eine negative oder riesige Seitengröße hieße
    sonst „alles auf einmal“."""
    seite, pro_seite = search.seiten(request.args.get("seite", 1), request.args.get("pro_seite", 50))
    return seite, min(pro_seite, maxi)


def _sortier_args():
    """(Spalte, Richtung) aus der Anfrage – geprüft wird in search.sortierung gegen die Liste der Spalten."""
    return (request.args.get("sort") or None), (request.args.get("richtung") or "auf")


# --- Seiten ------------------------------------------------------------------------------------------

def _seite(ansicht, katalog_seite=False, **daten):
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.full_path.rstrip("?")))
    if not (darf("lesen") or (katalog_seite and ist_katalogpfleger())):
        abort(403)
    return render_template("material/seite.html", user=u, active="material", ansicht=ansicht,
                           daten=json.dumps(daten, ensure_ascii=False), darf=json.dumps(darf_alles()))


@seiten.get("/material")
def dashboard():
    return _seite("dashboard")


@seiten.get("/material/pruefungen")
def pruefungen():
    return _seite("pruefungen", ordner=request.args.get("ordner", type=int))


@seiten.get("/material/bestand")
def bestand_seite():
    return _seite("bestand")


@seiten.get("/material/ordner/<int:fid>")
def ordner_seite(fid):
    return _seite("ordner", id=fid)


@seiten.get("/material/artikel/neu")
def artikel_neu():
    return _seite("artikel_neu", ordner=request.args.get("ordner", type=int),
                  produkt=request.args.get("produkt", type=int))


@seiten.get("/material/artikel/<int:iid>")
def artikel_seite(iid):
    return _seite("artikel", id=iid)


@seiten.get("/material/artikel/<int:iid>/pruefung/neu")
def pruefung_neu(iid):
    return _seite("pruefung_neu", id=iid, durchgang=request.args.get("durchgang", type=int))


@seiten.get("/material/pruefung/<int:pid>")
def pruefung_seite(pid):
    return _seite("pruefung", id=pid)


@seiten.get("/material/durchgang/<int:rid>")
def durchgang_seite(rid):
    return _seite("durchgang", id=rid)


def _protokoll_senden(row, quelle, kennung_wert, inventarnummer=None):
    """Ein festgeschriebenes Protokoll ausliefern – nur an Angemeldete mit Leserecht im Ordner und nur, wenn die
    Datei noch genau die festgeschriebene ist (Prüfsumme). Im Browser geöffnet, nicht heruntergeladen."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.path))
    if not darf("lesen"):
        abort(403)
    try:
        if not darf("lesen", _ordner_aus_anfrage(quelle, {quelle: kennung_wert})):
            abort(403)
        if not row:
            abort(404)
        pfad = protokoll.datei(row)
    except Abgelehnt as exc:
        return render_template("error.html", user=u, code=exc.code, message=str(exc)), exc.code
    resp = send_file(pfad, mimetype="application/pdf", download_name=protokoll.dateiname(row, inventarnummer),
                     max_age=60 * 60 * 24, conditional=True)
    resp.cache_control.public = None
    resp.cache_control.private = True
    # Kein „sandbox“ wie bei Anhängen: Damit zeigt der PDF-Betrachter von Chrome die Datei nicht an. Ein Protokoll
    # enthält weder Skripte noch Formulare – auch angefügte Anhänge kommen entschärft hinein (stempel.anhaengen).
    resp.headers["Content-Security-Policy"] = "default-src 'none'; object-src 'self'; img-src 'self' data:"
    return resp


@seiten.get("/material/pruefung/<int:pid>/pdf")
def pruefung_pdf(pid):
    row = db.query("SELECT x.*, i.inventory_no FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id "
                   "WHERE x.id = ? AND x.locked_at IS NOT NULL", (pid,), one=True)
    return _protokoll_senden(row, "pid", pid, row["inventory_no"] if row else None)


@seiten.get("/material/durchgang/<int:rid>/sammelprotokoll")
def sammelprotokoll(rid):
    row = db.query("SELECT * FROM mat_round WHERE id = ? AND locked_at IS NOT NULL", (rid,), one=True)
    return _protokoll_senden(row, "rid", rid)


@seiten.get("/material/pruefen")
def pruefseite():
    """Prüfseite: Jeder – auch ohne Anmeldung – lädt ein Protokoll hoch und erfährt, ob es unverändert ist.
    Sie zeigt nur das Ergebnis und die Protokoll-ID, keine Personendaten."""
    u = current_user()
    return render_template("material/pruefen.html", user=u, active="material" if u else None,
                           angemeldet=bool(u and darf("lesen")))


@seiten.get("/material/katalog")
def katalog_seite():
    return _seite("katalog", katalog_seite=True, kategorie=request.args.get("kategorie", type=int))


@seiten.get("/material/katalog/produkt/<int:pid>")
def produkt_seite(pid):
    return _seite("produkt", katalog_seite=True, id=pid)


@seiten.get("/material/katalog/formular/<int:fid>")
def formular_seite(fid):
    return _seite("formular", katalog_seite=True, id=fid)


@seiten.get("/material/katalog/meldungen")
def meldungen_seite():
    """Katalogpfleger arbeiten hier die Meldungen fehlender Produkte ab; Materialwarte sehen ihre eigenen."""
    return _seite("meldungen", katalog_seite=True, status=request.args.get("status"))


@seiten.get("/material/suche")
def suche_seite():
    """Ein eindeutiger Treffer öffnet den Artikel direkt; sonst zeigt die Seite die Trefferliste."""
    q = (request.args.get("q") or "").strip()
    if current_user() and darf("lesen") and q:
        try:
            treffer, gesamt = search.artikel(q, 1, 2)
        except Abgelehnt:
            treffer, gesamt = [], 0
        if gesamt == 1:
            return redirect(url_for("material.artikel_seite", iid=treffer[0]["id"]))
    return _seite("suche", q=q)


@seiten.get("/m/<token>")
def qr_ziel(token):
    """Ziel des QR-Codes: über die Anmeldung zum Artikel. Wer das Modul nicht sehen darf, bekommt
    nichts über den Artikel zu wissen – auch nicht, ob es ihn gibt."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=f"/m/{token}"))
    if not darf("lesen"):
        abort(403)
    i = db.query("SELECT id FROM mat_item WHERE qr_token = ?", (token,), one=True)
    if not i:
        abort(404)
    return redirect(url_for("material.artikel_seite", iid=i["id"]))


@seiten.get("/media/material/<art>/<path:dateiname>")
def medien(art, dateiname):
    """Produkt- und Ordnerfotos, Herstellerdokumente – nur für Angemeldete mit Zugang zum Modul, nie
    in einem gemeinsamen Zwischenspeicher. Skripte sind auch in einem PDF oder SVG wirkungslos."""
    if art not in ("orig", "web", "thumb", "dok", "anhang"):
        abort(404)
    if not current_user():
        abort(401)
    if not (darf("lesen") or ist_katalogpfleger()):
        abort(403)
    resp = send_from_directory(os.path.join(katalog.medien_dir(), art), dateiname, max_age=60 * 60 * 24 * 7)
    resp.cache_control.public = None
    resp.cache_control.private = True
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; sandbox"
    return resp


# --- Schnittstelle: Start und Suche --------------------------------------------------------------------

@api.get("/start")
@requires_folder("lesen")
def start():
    gliederungen = [o for o in bestand.baum() if o["kind"] == "gliederung" and not o["system_kind"]]
    naechste, faellig = bestand.faellige(pro_seite=10)
    z = bestand.zaehlung()
    return jsonify(darf=darf_alles(), zaehlung=z, bestand=sum(z[s] for s in st.BESTAND),
                   gliederungen=gliederungen, naechste=naechste, faellig_gesamt=faellig,
                   schwelle_tage=st.schwelle_tage(), status_text=st.LABEL,
                   meldungen_offen=meldung.anzahl_offen() if ist_katalogpfleger() else None)


@api.get("/suche")
@requires_folder("lesen")
def suche():
    seite, pro_seite = _seite_args()
    rows, gesamt = search.artikel(request.args.get("q", ""), seite, pro_seite, *_sortier_args())
    treffer = []
    for r in rows:
        k = bestand.artikel_kurz(r)
        k["pfad"] = " / ".join(o["name"] for o in bestand.pfad(r["folder_id"]))
        treffer.append(k)
    return jsonify(treffer=treffer, gesamt=gesamt, eindeutig=treffer[0]["id"] if gesamt == 1 and treffer else None)


@api.get("/faellig")
@requires_folder("lesen")
def faellig():
    nur = request.args.get("status") or ""
    stati = tuple(s for s in nur.split(",") if s in st.STATUS) or bestand.FAELLIG
    seite, pro_seite = _seite_args()
    ordner_id = request.args.get("ordner", type=int)
    if ordner_id:
        bestand.ordner(ordner_id)
    liste, gesamt = bestand.faellige(ordner_id, stati, seite, pro_seite, *_sortier_args())
    return jsonify(artikel=liste, gesamt=gesamt, schwelle_tage=st.schwelle_tage())


# --- Schnittstelle: Katalog ----------------------------------------------------------------------------

def _katalog_lesen():
    if not (darf("lesen") or ist_katalogpfleger()):
        raise Abgelehnt("Für dein Konto ist das Modul Material nicht freigeschaltet.", 403)


@api.get("/kategorien")
def kategorien():
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    return jsonify(kategorien=katalog.kategorien(), materialarten=models.MATERIALARTEN)


@api.post("/kategorien")
@katalog_required
def kategorie_anlegen():
    kid = katalog.kategorie_anlegen(json_body())
    return jsonify(kategorie=katalog.kategorie_json(katalog.kategorie(kid))), 201


@api.put("/kategorien/<int:kid>")
@katalog_required
def kategorie_aendern(kid):
    katalog.kategorie_aendern(kid, json_body())
    return jsonify(kategorie=katalog.kategorie_json(katalog.kategorie(kid)))


@api.delete("/kategorien/<int:kid>")
@katalog_required
def kategorie_loeschen(kid):
    katalog.kategorie_loeschen(kid)
    return jsonify(ok=True)


@api.get("/produkte")
def produkte():
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    seite, pro_seite = _seite_args()
    kid = request.args.get("kategorie", type=int)
    rows, gesamt = search.produkte(request.args.get("q", ""), kid, seite, pro_seite, *_sortier_args())
    seite, pro_seite = search.seiten(seite, pro_seite)
    return jsonify(produkte=[katalog.produkt_json(r) for r in rows], gesamt=gesamt, seite=seite, pro_seite=pro_seite)


@api.get("/produkte/artikelnummer")
def artikelnummer_pruefen():
    """Für den Hinweis beim Tippen: Wem gehört diese Artikelnummer schon? („ausser“: das Produkt, das man bearbeitet)"""
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    da = katalog.artikelnummer_vergeben(request.args.get("nr", ""), request.args.get("ausser", type=int))
    return jsonify(produkt={"id": da["id"], "name": f"{da['manufacturer']} {da['model']}", "article_no": da["article_no"]}
                   if da else None)


@api.post("/produkte")
@katalog_required
def produkt_anlegen():
    pid = katalog.produkt_anlegen(json_body())
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid), voll=True)), 201


@api.post("/produkte/<int:pid>/variante")
@katalog_required
def produkt_variante(pid):
    """Kopie als neue Variante: Felder wie POST /produkte (eigene Artikelnummer Pflicht), dazu „dokumente“ –
    die Kennungen der aktuellen Dokumente, die mitkommen sollen. Das Produktbild kommt nie mit."""
    neu = katalog.produkt_variante(pid, json_body())
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(neu), voll=True)), 201


@api.get("/produkte/<int:pid>")
def produkt_lesen(pid):
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    p = katalog.produkt_json(katalog.produkt(pid), voll=True)
    p["journal"] = journal.fuer_produkt(pid)
    p["formulare"] = katalog.formulare_fuer(produkt_id=pid)
    return jsonify(produkt=p)


@api.put("/produkte/<int:pid>")
@katalog_required
def produkt_aendern(pid):
    katalog.produkt_aendern(pid, json_body())
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid), voll=True))


@api.delete("/produkte/<int:pid>")
@katalog_required
def produkt_loeschen(pid):
    katalog.produkt_loeschen(pid)
    return jsonify(ok=True)


@api.post("/produkte/<int:pid>/bild")
@katalog_required
def produkt_bild(pid):
    katalog.produkt_bild_setzen(pid, request.files.get("file"))
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid)))


@api.delete("/produkte/<int:pid>/bild")
@katalog_required
def produkt_bild_entfernen(pid):
    katalog.produkt_bild_entfernen(pid)
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid)))


@api.post("/produkte/<int:pid>/dokumente")
@katalog_required
def dokument_neu(pid):
    did = katalog.dokument_anlegen(pid, _eingabe(), request.files.get("file"))
    return jsonify(dokument_id=did, dokumente=katalog.dokumente(pid)), 201


@api.get("/kategorien/<int:kid>/dokumente")
def kategorie_dokumente(kid):
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    katalog.kategorie(kid)
    return jsonify(dokumente=katalog.dokumente(kid=kid))


@api.post("/kategorien/<int:kid>/dokumente")
@katalog_required
def kategorie_dokument_neu(kid):
    """Ein Dokument für alle Produkte der Kategorie und ihrer Unterkategorien (Pflegehinweis, Anleitung)."""
    did = katalog.dokument_anlegen(None, _eingabe(), request.files.get("file"), kid=kid)
    return jsonify(dokument_id=did, dokumente=katalog.dokumente(kid=kid)), 201


@api.post("/dokumente/<int:did>/version")
@katalog_required
def dokument_version(did):
    neu = katalog.dokument_neue_version(did, _eingabe(), request.files.get("file"))
    return jsonify(dokument_id=neu, dokumente=katalog.dokumente_des(katalog.dokument(neu))), 201


@api.put("/dokumente/<int:did>")
@katalog_required
def dokument_umbenennen(did):
    katalog.dokument_umbenennen(did, json_body())
    return jsonify(dokumente=katalog.dokumente_des(katalog.dokument(did)))


@api.post("/dokumente/<int:did>/zurueckziehen")
@katalog_required
def dokument_zurueckziehen(did):
    katalog.dokument_zurueckziehen(did, json_body())
    return jsonify(dokumente=katalog.dokumente_des(katalog.dokument(did)))


# --- Schnittstelle: Meldungen fehlender Produkte -------------------------------------------------------

@api.get("/meldungen")
def meldungen():
    """Katalogpfleger sehen alle Meldungen (Standard: offene), Materialwarte ihre eigenen (Standard: alle)."""
    u = current_user()
    if not u:
        return jsonify(error="Nicht angemeldet"), 401
    alle = ist_katalogpfleger() and request.args.get("eigene") != "1"
    if not alle and not darf("verwalten"):
        raise Abgelehnt("Produktmeldungen sehen Katalogpfleger und Materialwarte (ihre eigenen).", 403)
    filter_ = request.args.get("status") if request.args.get("status") in meldung.FILTER else ("offen" if alle else "alle")
    rows = meldung.liste(filter_, None if alle else u["id"])
    return jsonify(meldungen=[meldung.meldung_json(r) for r in rows], alle=alle, filter=filter_,
                   offen=meldung.anzahl_offen() if alle else None)


@api.post("/meldungen")
@requires_folder("verwalten")
def meldung_anlegen():
    """Ein fehlendes Produkt melden – Felder als JSON oder, mit Fotos, als Formular (Feld „fotos“, mehrfach)."""
    mid = meldung.anlegen(_eingabe(), request.files.getlist("fotos"))
    return jsonify(meldung=meldung.meldung_json(meldung.meldung(mid))), 201


@api.get("/meldungen/<int:mid>")
def meldung_lesen(mid):
    u = current_user()
    if not u:
        return jsonify(error="Nicht angemeldet"), 401
    r = meldung.meldung(mid)
    if not (ist_katalogpfleger() or r["created_by"] == u["id"]):
        raise Abgelehnt("Diese Meldung sehen nur ihr Melder und die Katalogpfleger.", 403)
    return jsonify(meldung=meldung.meldung_json(r))


@api.delete("/meldungen/<int:mid>")
def meldung_loeschen(mid):
    """Nur der Melder selbst (meldung.loeschen prüft das)."""
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    meldung.loeschen(mid)
    return jsonify(ok=True)


@api.post("/meldungen/<int:mid>/produkt")
@katalog_required
def meldung_produkt(mid):
    """Produkt aus der Meldung anlegen (Felder wie POST /produkte, dazu „antwort“) – erledigt sie zugleich."""
    pid = meldung.produkt_anlegen(mid, json_body())
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid), voll=True),
                   meldung=meldung.meldung_json(meldung.meldung(mid))), 201


@api.post("/meldungen/<int:mid>/zuordnen")
@katalog_required
def meldung_zuordnen(mid):
    meldung.zuordnen(mid, json_body())
    return jsonify(meldung=meldung.meldung_json(meldung.meldung(mid)))


@api.post("/meldungen/<int:mid>/ablehnen")
@katalog_required
def meldung_ablehnen(mid):
    meldung.ablehnen(mid, json_body())
    return jsonify(meldung=meldung.meldung_json(meldung.meldung(mid)))


@api.get("/formulare")
def formulare():
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    kid = request.args.get("kategorie", type=int)
    pid = request.args.get("produkt", type=int)
    if bool(kid) == bool(pid):
        raise Abgelehnt("Bitte genau eine Kategorie oder ein Produkt angeben.")
    if kid:
        katalog.kategorie(kid)
    else:
        katalog.produkt(pid)
    return jsonify(formulare=katalog.formulare_fuer(kid, pid), editoren=models.EDITOREN)


@api.post("/formulare")
@katalog_required
def formular_anlegen():
    fid = katalog.formular_anlegen(json_body())
    return jsonify(formular=katalog.formular_json(katalog.formular(fid))), 201


@api.get("/formulare/<int:fid>")
def formular_lesen(fid):
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    f = katalog.formular_json(katalog.formular(fid))
    f["journal"] = journal.lesen([("form", fid)], grenze=100)
    f["versionen"] = katalog.formulare_fuer(f["kategorie_id"], f["produkt_id"])
    return jsonify(formular=f, editoren=models.EDITOREN)


@api.put("/formulare/<int:fid>")
@katalog_required
def formular_speichern(fid):
    katalog.formular_speichern(fid, json_body())
    return jsonify(formular=katalog.formular_json(katalog.formular(fid)))


@api.post("/formulare/<int:fid>/aktivieren")
@katalog_required
def formular_aktivieren(fid):
    katalog.formular_aktivieren(fid)
    return jsonify(formular=katalog.formular_json(katalog.formular(fid)))


@api.post("/formulare/<int:fid>/deaktivieren")
@katalog_required
def formular_deaktivieren(fid):
    katalog.formular_deaktivieren(fid)
    return jsonify(formular=katalog.formular_json(katalog.formular(fid)))


@api.delete("/formulare/<int:fid>")
@katalog_required
def formular_loeschen(fid):
    katalog.formular_loeschen(fid)
    return jsonify(ok=True)


# --- Schnittstelle: Ordner -------------------------------------------------------------------------------

@api.get("/ordner")
@requires_folder("lesen")
def ordner_baum():
    return jsonify(ordner=bestand.baum(), ordnerarten=models.ORDNERARTEN)


@api.post("/ordner")
@requires_folder("verwalten", quelle="json:parent_id")
def ordner_anlegen():
    fid = bestand.ordner_anlegen(json_body())
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid))), 201


@api.get("/ordner/<int:fid>")
@requires_folder("lesen", quelle="fid")
def ordner_lesen(fid):
    # Ein Ordner zeigt bis zu 500 Artikel je Seite (Vorgabe 200) – mehr als die Suche, weil hier ganze
    # Lager durchgesehen werden.
    seite = search.seiten(request.args.get("seite", 1), 1)[0]
    pro_seite = max(1, min(500, request.args.get("pro_seite", 200, type=int) or 200))
    return jsonify(ordner=bestand.ordner_inhalt(fid, request.args.get("status") or None, seite, pro_seite,
                                                *_sortier_args()))


@api.put("/ordner/<int:fid>")
@requires_folder("verwalten", quelle="fid")
def ordner_aendern(fid):
    bestand.ordner_aendern(fid, json_body())
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


@api.post("/ordner/<int:fid>/verschieben")
@requires_folder("verwalten", quelle="fid")
def ordner_verschieben(fid):
    d = json_body()
    ziel = kennung(d.get("parent_id"), "Zielordner", leer_erlaubt=True)
    if ziel and not darf("verwalten", ziel):
        raise Abgelehnt("Im Zielordner darfst du nichts ablegen.", 403)
    bestand.ordner_verschieben(fid, ziel)
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


@api.delete("/ordner/<int:fid>")
@requires_folder("verwalten", quelle="fid")
def ordner_loeschen(fid):
    bestand.ordner_loeschen(fid)
    return jsonify(ok=True)


@api.post("/ordner/<int:fid>/foto")
@requires_folder("verwalten", quelle="fid")
def ordner_foto(fid):
    bestand.ordner_foto_setzen(fid, request.files.get("file"))
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


@api.delete("/ordner/<int:fid>/foto")
@requires_folder("verwalten", quelle="fid")
def ordner_foto_entfernen(fid):
    bestand.ordner_foto_entfernen(fid)
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


# --- Schnittstelle: Artikel -----------------------------------------------------------------------------

@api.get("/artikel/vorschlag")
@requires_folder("lesen")
def artikel_vorschlag():
    return jsonify(vorschlag=bestand.vorschlag(request.args))


@api.post("/artikel")
@requires_folder("verwalten", quelle="json:folder_id")
def artikel_anlegen():
    iid = bestand.artikel_anlegen(json_body())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True)), 201


@api.get("/artikel/<int:iid>")
@requires_folder("lesen", quelle="iid")
def artikel_lesen(iid):
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.put("/artikel/<int:iid>")
@requires_folder("verwalten", quelle="iid")
def artikel_aendern(iid):
    bestand.artikel_aendern(iid, json_body())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.delete("/artikel/<int:iid>")
@requires_folder("verwalten", quelle="iid")
def artikel_loeschen(iid):
    bestand.artikel_loeschen(iid)
    return jsonify(ok=True)


@api.post("/artikel/verschieben")
@requires_folder("verwalten", quelle="json:folder_id")
def artikel_verschieben():
    d = json_body()
    ziel = kennung(d.get("folder_id"), "Zielordner")
    ids = d.get("ids")
    if isinstance(ids, list):
        for iid in ids:
            row = db.query("SELECT folder_id FROM mat_item WHERE id = ?", (iid,), one=True) \
                if isinstance(iid, int) and not isinstance(iid, bool) else None
            if row and not darf("verwalten", row["folder_id"]):
                raise Abgelehnt("Mindestens einen der Artikel darfst du nicht verschieben.", 403)
    n = bestand.artikel_verschieben(ids, ziel)
    return jsonify(ok=True, verschoben=n)


# --- Schnittstelle: Prüfungen ------------------------------------------------------------------------------

def _pruefer():
    return pruefung.pruefer_aus(current_user())


def _pruefung_antwort(pid, code=200):
    return jsonify(pruefung=pruefung.pruefung_json(pruefung.pruefung(pid), current_user()["id"])), code


@api.get("/artikel/<int:iid>/pruefungen")
@requires_folder("lesen", quelle="iid")
def artikel_pruefungen(iid):
    return jsonify(pruefungen=pruefung.fuer_artikel(iid))


@api.post("/artikel/<int:iid>/pruefungen")
@requires_folder("pruefen", quelle="iid")
def pruefung_starten(iid):
    d = json_body()
    rid = kennung(d.get("durchgang_id"), "Prüfdurchgang", leer_erlaubt=True)
    pid, neu = pruefung.starten(iid, _pruefer(), d.get("art") or None, rid)
    return _pruefung_antwort(pid, 201 if neu else 200)


@api.get("/pruefungen/<int:pid>")
@requires_folder("lesen", quelle="pid")
def pruefung_lesen(pid):
    return _pruefung_antwort(pid)


@api.put("/pruefungen/<int:pid>")
@requires_folder("pruefen", quelle="pid")
def pruefung_kopf(pid):
    pruefung.kopf_setzen(pid, json_body(), _pruefer())
    return _pruefung_antwort(pid)


@api.put("/pruefungen/<int:pid>/punkte/<int:rid>")
@requires_folder("pruefen", quelle="pid")
def punkt_setzen(pid, rid):
    return jsonify(punkt=pruefung.punkt_setzen(pid, rid, json_body(), _pruefer()))


@api.post("/pruefungen/<int:pid>/punkte/<int:rid>/foto")
@requires_folder("pruefen", quelle="pid")
def punkt_foto(pid, rid):
    return jsonify(punkt=pruefung.punkt_foto_setzen(pid, rid, request.files.get("file"), _pruefer()))


@api.delete("/pruefungen/<int:pid>/punkte/<int:rid>/foto")
@requires_folder("pruefen", quelle="pid")
def punkt_foto_entfernen(pid, rid):
    return jsonify(punkt=pruefung.punkt_foto_entfernen(pid, rid, _pruefer()))


@api.post("/pruefungen/<int:pid>/anhaenge")
@requires_folder("pruefen", quelle="pid")
def anhang_neu(pid):
    a = pruefung.anhang_hinzufuegen(pid, request.form, request.files.getlist("file"), _pruefer())
    return jsonify(anhang=a), 201


@api.delete("/pruefungen/<int:pid>/anhaenge/<int:aid>")
@requires_folder("pruefen", quelle="pid")
def anhang_entfernen(pid, aid):
    pruefung.anhang_entfernen(pid, aid, _pruefer())
    return jsonify(ok=True)


@api.post("/pruefungen/<int:pid>/festschreiben")
@api.post("/pruefungen/<int:pid>/abschliessen")
@requires_folder("pruefen", quelle="pid")
def pruefung_abschliessen(pid):
    """Abschließen heißt seit Lieferung 3 Festschreiben (der alte Pfad bleibt für offene Seiten gültig)."""
    pruefung.abschliessen(pid, json_body(), _pruefer())
    return _pruefung_antwort(pid)


@api.post("/pruefungen/<int:pid>/berichtigen")
@requires_folder("pruefen", quelle="pid")
def pruefung_berichtigen(pid):
    """Berichtigung einer abgeschlossenen Prüfung beginnen – liefert den neuen Entwurf."""
    neu = pruefung.berichtigen(pid, json_body(), _pruefer())
    return _pruefung_antwort(neu, 201)


@api.delete("/pruefungen/<int:pid>")
@requires_folder(("pruefen", "verwalten"), quelle="pid")
def pruefung_verwerfen(pid):
    """Den eigenen Entwurf verwerfen – oder als Materialwart eine liegen gebliebene Reservierung freigeben."""
    pruefung.verwerfen(pid, _pruefer(), darf_freigeben=darf("verwalten", g.mat_ordner_id))
    return jsonify(ok=True)


@api.get("/entwuerfe")
@requires_folder("lesen")
def entwuerfe():
    return jsonify(entwuerfe=pruefung.entwuerfe(current_user()["id"]))


@api.post("/artikel/<int:iid>/sperren")
@requires_folder("pruefen", quelle="iid")
def artikel_sperren(iid):
    pruefung.sperren(iid, json_body(), _pruefer())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.post("/artikel/<int:iid>/aussondern")
@requires_folder("verwalten", quelle="iid")
def artikel_aussondern(iid):
    aid = pruefung.aussondern(iid, json_body(), _pruefer())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True), aussonderung=aid)


# --- Schnittstelle: eigene Unterschrift und Prüfseite --------------------------------------------------------

@api.get("/unterschrift")
@requires_folder("lesen")
def unterschrift_lesen():
    return jsonify(unterschrift=unterschrift.daten_uri(unterschrift.von(current_user()["id"])))


@api.put("/unterschrift")
@requires_folder("lesen")
def unterschrift_setzen():
    """Die eigene Unterschrift hinterlegen (data:-URL vom Signatur-Pad) – Grundlage jedes Festschreibens."""
    return jsonify(unterschrift=unterschrift.setzen(current_user(), json_body().get("bild")))


@api.delete("/unterschrift")
@requires_folder("lesen")
def unterschrift_entfernen():
    unterschrift.entfernen(current_user())
    return jsonify(unterschrift=None)


@api.post("/pruefen")
def pruefen():
    """Prüfseite ohne Anmeldung: ein hochgeladenes PDF gegen die gespeicherten Prüfsummen. Gespeichert wird nichts."""
    bereich = [f"pruefen-ip:{request.remote_addr or '?'}"]
    if attempts_exceeded(bereich, PRUEFEN_JE_VIERTELSTUNDE):
        return jsonify(error="Zu viele Prüfungen in kurzer Zeit. Bitte in einer Viertelstunde noch einmal."), 429
    with db.transaction():
        note_attempt(bereich[0])
    datei = request.files.get("datei")
    if not datei or not datei.filename:
        return jsonify(error="Bitte eine PDF-Datei wählen."), 400
    ergebnis = protokoll.pruefen(datei.stream)
    u = current_user()
    if u and darf("lesen") and ergebnis.get("protokoll_id"):
        ergebnis["link"] = _protokoll_link(ergebnis["protokoll_id"])
    return jsonify(ergebnis)


def _protokoll_link(pid):
    """Für Angemeldete mit Zugang: wohin das Protokoll in der Oberfläche gehört."""
    if pid.startswith("S-"):
        r = db.query("SELECT id FROM mat_round WHERE protocol_id = ?", (pid,), one=True)
        return f"/material/durchgang/{r['id']}" if r else None
    r = db.query("SELECT id FROM mat_inspection WHERE protocol_id = ?", (pid,), one=True)
    return f"/material/pruefung/{r['id']}" if r else None


# --- Schnittstelle: Prüfdurchgänge ---------------------------------------------------------------------------

@api.get("/durchgaenge")
@requires_folder("lesen")
def durchgaenge():
    return jsonify(durchgaenge=durchgang.liste(nur_offen=request.args.get("offen") == "1"))


@api.post("/durchgaenge")
@requires_folder(("verwalten", "pruefen"), quelle="json:folder_id")
def durchgang_eroeffnen():
    d = json_body()
    rid = durchgang.eroeffnen(kennung(d.get("folder_id"), "Ordner"), d, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid))), 201


@api.get("/durchgaenge/<int:rid>")
@requires_folder("lesen", quelle="rid")
def durchgang_lesen(rid):
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid), voll=True, pruefer_id=current_user()["id"]))


@api.post("/durchgaenge/<int:rid>/ausnehmen")
@requires_folder(("verwalten", "pruefen"), quelle="rid")
def durchgang_ausnehmen(rid):
    d = json_body()
    durchgang.ausnehmen(rid, kennung(d.get("item_id"), "Artikel"), d, _pruefer())
    return jsonify(ok=True)


@api.post("/durchgaenge/<int:rid>/einbeziehen")
@requires_folder(("verwalten", "pruefen"), quelle="rid")
def durchgang_einbeziehen(rid):
    durchgang.einbeziehen(rid, kennung(json_body().get("item_id"), "Artikel"))
    return jsonify(ok=True)


@api.post("/durchgaenge/<int:rid>/abschliessen")
@requires_folder(("verwalten", "pruefen"), quelle="rid")
def durchgang_abschliessen(rid):
    durchgang.abschliessen(rid, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid)))


@api.post("/durchgaenge/<int:rid>/abbrechen")
@requires_folder(("verwalten", "pruefen"), quelle="rid")
def durchgang_abbrechen(rid):
    """Vorzeitig beenden; „durchgang“ ist null, wenn er mangels Geprüftem ganz entfernt wurde."""
    bleibt = durchgang.abbrechen(rid, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid)) if bleibt else None)


@api.delete("/durchgaenge/<int:rid>")
@requires_folder(("verwalten", "pruefen"), quelle="rid")
def durchgang_loeschen(rid):
    durchgang.loeschen(rid)
    return jsonify(ok=True)
