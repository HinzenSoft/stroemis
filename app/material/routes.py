"""Routen des Moduls Material.

Seiten (/material/…, /m/<token>) sind dünne Hüllen: Sie prüfen das Recht, nennen die Ansicht und
überlassen den Inhalt material.js, das ihn über die Schnittstelle (/api/material/…) holt – dasselbe
Muster wie im Prüfungsbereich. Jede Route prüft ihr Recht selbst; ein ausgeblendeter Knopf ist kein
Schutz. Fachregeln stehen in services/, hier wird nur gelesen, aufgerufen und geantwortet."""
import json
import os
import sqlite3

from flask import (Blueprint, abort, current_app, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from .. import db
from ..auth import current_user, eingabefehler_abfangen, json_body
from . import models
from .services import Abgelehnt, bestand, journal, katalog, kennung, search
from .services import status as st
from .services.rechte import darf, darf_alles, ist_katalogpfleger, katalog_required, requires_folder

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
}


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


@seiten.get("/material/katalog")
def katalog_seite():
    return _seite("katalog", katalog_seite=True, kategorie=request.args.get("kategorie", type=int))


@seiten.get("/material/katalog/produkt/<int:pid>")
def produkt_seite(pid):
    return _seite("produkt", katalog_seite=True, id=pid)


@seiten.get("/material/katalog/formular/<int:fid>")
def formular_seite(fid):
    return _seite("formular", katalog_seite=True, id=fid)


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
    if art not in ("orig", "web", "thumb", "dok"):
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
                   schwelle_tage=st.schwelle_tage(), status_text=st.LABEL)


@api.get("/suche")
@requires_folder("lesen")
def suche():
    seite, pro_seite = _seite_args()
    rows, gesamt = search.artikel(request.args.get("q", ""), seite, pro_seite)
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
    stati = tuple(s for s in nur.split(",") if s in st.STATUS) or ("ueberfaellig", "bald_faellig")
    seite, pro_seite = _seite_args()
    ordner_id = request.args.get("ordner", type=int)
    if ordner_id:
        bestand.ordner(ordner_id)
    liste, gesamt = bestand.faellige(ordner_id, stati, seite, pro_seite)
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
    rows, gesamt = search.produkte(request.args.get("q", ""), kid, seite, pro_seite)
    seite, pro_seite = search.seiten(seite, pro_seite)
    return jsonify(produkte=[katalog.produkt_json(r) for r in rows], gesamt=gesamt, seite=seite, pro_seite=pro_seite)


@api.post("/produkte")
@katalog_required
def produkt_anlegen():
    pid = katalog.produkt_anlegen(json_body())
    return jsonify(produkt=katalog.produkt_json(katalog.produkt(pid), voll=True)), 201


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


@api.post("/dokumente/<int:did>/version")
@katalog_required
def dokument_version(did):
    neu = katalog.dokument_neue_version(did, _eingabe(), request.files.get("file"))
    return jsonify(dokument_id=neu, dokumente=katalog.dokumente(katalog.dokument(neu)["product_id"])), 201


@api.post("/dokumente/<int:did>/zurueckziehen")
@katalog_required
def dokument_zurueckziehen(did):
    katalog.dokument_zurueckziehen(did, json_body())
    return jsonify(dokumente=katalog.dokumente(katalog.dokument(did)["product_id"]))


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
    return jsonify(ordner=bestand.ordner_inhalt(fid, request.args.get("status") or None, seite, pro_seite))


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
