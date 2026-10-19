"""Routen des Moduls Material.

Seiten (/material/…, /m/<token>) sind dünne Hüllen: Sie prüfen das Recht, nennen die Ansicht und
überlassen den Inhalt material.js, das ihn über die Schnittstelle (/api/material/…) holt – dasselbe
Muster wie im Prüfungsbereich. Jede Route prüft ihr Recht selbst; ein ausgeblendeter Knopf ist kein
Schutz. Fachregeln stehen in services/, hier wird nur gelesen, aufgerufen und geantwortet.

Die Routen der Lieferung 4 stehen in eigenen Modulen an denselben Blueprints – routes_export.py (CSV, Protokoll-ZIP,
Lebenslauf), routes_katalog.py (Katalogaustausch) und routes_rueckruf.py –, eingebunden am Ende dieser Datei; ebenso die
der Phase 2 (Freigaben, globale Suche, Zuordnung, Erinnerungen, Bestandsimport).

Seit Phase 2 gelten Freigaben je Ordner (services/rechte.py): Lesende Routen über den ganzen Bestand tragen
requires_zugang und liefern nur, was das Konto sieht; Routen zu einem Gegenstand tragen requires_folder. Fremdes – auch
eine fremde Kennung im Inhalt einer Anfrage – antwortet wie Unbekanntes mit 404 und derselben Meldung, 403 nur, wenn
man den Gegenstand sieht, die Aktion aber nicht darf. Seiten zeigen dafür die Fehlerseite."""
import json
import os
import sqlite3

from flask import (Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, send_file,
                   send_from_directory, url_for)

from .. import db
from ..auth import attempts_exceeded, current_user, eingabefehler_abfangen, json_body, login_required, note_attempt
from . import models
from .services import (Abgelehnt, anhang, bestand, bestandsimport, durchgang, eingabe, globalprotokoll, globalsuche,
                       journal, katalog, kennung, medien as medien_dienst, meldung, protokoll, pruefung, search,
                       unterschrift)
from .services import erinnerung, rueckruf
from .services import status as st
from .services import ueberblick
from .services.bestand import FremdeDublette
from .services.rechte import (ARTIKEL_FEHLT, ORDNER_FEHLT, _bezug, darf, darf_alles, darf_artikel, darf_unterschreiben,
                              ist_material_verwaltung, katalog_required, qualifiziert, requires_folder, requires_zugang,
                              sicht,
                              sicht_verwerfen, urkunde_setzen, zugang, zugang_meldung)
from .services.importer import ZIP_MAX_BYTES as KATALOG_ZIP_MAX_BYTES

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
    # Katalogimport (routes_katalog.py): ZIP mit Bildern und Dokumenten – so groß, wie der Export werden darf.
    "material_api.katalog_importieren": KATALOG_ZIP_MAX_BYTES + 1024 * 1024,
    # Bestandsimport (routes_import.py): eine Liste von höchstens 5 MB; „Produkt melden“ aus der Nacharbeit wie die Meldung.
    "material_api.import_probelauf": bestandsimport.MAX_BYTES + 1024 * 1024,
    "material_api.import_uebernehmen": bestandsimport.MAX_BYTES + 1024 * 1024,
    "material_api.nacharbeit_melden": meldung.MAX_FOTOS * katalog.BILD_MAX_BYTES + 1024 * 1024,
}
PRUEFEN_JE_VIERTELSTUNDE = 20


@api.errorhandler(Abgelehnt)
def _abgelehnt(exc):
    return jsonify(error=str(exc)), exc.code


@api.errorhandler(FremdeDublette)
def _fremde_dublette(exc):
    """Die Seriennummer gibt es bei diesem Produkt schon – in einem fremden Bereich (Bauentwurf 3.7). Die Transaktion ist
    zurückgerollt; jetzt in eigener Transaktion ins selbe Protokoll wie die globale Suche, denn die Meldung verrät, dass
    es die Nummer gibt. Der Text nennt weder Gliederung noch Inventarnummer."""
    globalprotokoll.eintragen("dublette", globalsuche.normalform(exc.serie), [exc.item_id])
    return jsonify(error=str(exc)), exc.code


@api.errorhandler(sqlite3.IntegrityError)
def _integritaet(exc):
    """Zwei Leute ändern dasselbe gleichzeitig – kein Serverfehler, sondern ein Hinweis zum Neuladen."""
    current_app.logger.warning("Integritätsfehler an %s %s: %s", request.method, request.path, exc)
    return jsonify(error="Das wurde zwischenzeitlich anderswo geändert. Bitte neu laden."), 409


def _eingabe():
    """JSON-Body oder – bei Dateiuploads – die Formularfelder der Multipart-Anfrage (services.eingabe; dieselbe Regel
    liest requires_folder bei der Quelle „eingabe:“)."""
    return eingabe()


def _seite_args(maxi=search.PRO_SEITE_MAX):
    """Seite und Seitengröße aus der Anfrage – geklemmt: eine negative oder riesige Seitengröße hieße
    sonst „alles auf einmal“."""
    seite, pro_seite = search.seiten(request.args.get("seite", 1), request.args.get("pro_seite", 50))
    return seite, min(pro_seite, maxi)


def _sortier_args():
    """(Spalte, Richtung) aus der Anfrage – geprüft wird in search.sortierung gegen die Liste der Spalten."""
    return (request.args.get("sort") or None), (request.args.get("richtung") or "auf")


# --- Seiten ------------------------------------------------------------------------------------------

def _fehlerseite(code, meldung):
    return render_template("error.html", user=current_user(), code=code, message=meldung), code


# Wie eine Seite ihren Gegenstand auflöst (rechte._bezug): Ordner, Artikel, Prüfung, Durchgang.
_SEITEN_QUELLE = {"ordner": "fid", "artikel": "iid", "pruefung": "pid", "durchgang": "rid"}


def _bezug_seite(art, kennung_wert):
    """None, wenn das Konto den Gegenstand der Seite sehen darf – sonst die Meldung für die Fehlerseite 404 (dieselbe
    wie für Unbekanntes). Ein Artikel zählt über seine Heimat; ein Ordner darf auch ein teilweise sichtbarer
    Systemordner sein, kein Pfad-Knoten."""
    quelle = _SEITEN_QUELLE[art]
    try:
        b = _bezug(quelle, {quelle: kennung_wert})
    except Abgelehnt as exc:
        return str(exc)
    s = sicht()
    sichtbar = s.darf("lesen", b.ordner_id) if b.art == "artikel" else s.sichtbar(b.ordner_id)
    return None if sichtbar else b.meldung


def _seite(ansicht, katalog_seite=False, warnung=None, bezug=None, **daten):
    """Eine Seite des Moduls. Ohne Anmeldung zur Anmeldung, ohne Modulzugang die Fehlerseite 403 mit dem Grund
    (zugang_meldung). bezug: („artikel“ | „ordner“ | „pruefung“ | „durchgang“, Kennung) – was das Konto nicht sehen
    darf, antwortet vor dem Zeichnen wie Unbekanntes mit der Fehlerseite 404, ohne Banner, ohne Daten. warnung: eine
    Funktion, die erst danach gefragt wird – ihr Hinweis steht schon im HTML. Katalogseiten brauchen nur den
    Modulzugang (katalog_seite)."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.full_path.rstrip("?")))
    if not zugang(u):
        return _fehlerseite(403, zugang_meldung(u))
    if bezug:
        fehlt = _bezug_seite(*bezug)
        if fehlt:
            return _fehlerseite(404, fehlt)
    return render_template("material/seite.html", user=u, active="material", ansicht=ansicht,
                           daten=json.dumps(daten, ensure_ascii=False), darf=json.dumps(darf_alles()),
                           warnung=warnung() if warnung else None)


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
    return _seite("ordner", bezug=("ordner", fid), id=fid)


@seiten.get("/material/artikel/neu")
def artikel_neu():
    """Artikel anlegen nur, wer irgendwo verwaltet; den Ordner aus der Adresse übernimmt die Seite nur, wenn das Konto
    ihn verwaltet."""
    u = current_user()
    if u and zugang(u) and not sicht(u).irgendwo("verwalten"):
        return _fehlerseite(403, "Artikel legen nur Materialwarte an – in einem Ordner, den sie verwalten.")
    ordner = request.args.get("ordner", type=int)
    return _seite("artikel_neu", ordner=ordner if ordner and u and darf("verwalten", ordner) else None,
                  produkt=request.args.get("produkt", type=int))


@seiten.get("/material/artikel/<int:iid>")
def artikel_seite(iid):
    """Ziel jedes QR-Scans: Ist der Artikel ausgesondert, gesperrt oder am Lebensende, steht das schon im HTML –
    sofort sichtbar, bevor material.js die Ansicht (mit eigenem Banner) zeichnet. Ein fremder Artikel antwortet vorher
    mit 404 – ohne Banner.

    ?q=: Hierher führt die Suche bei einem eindeutigen eigenen Treffer (suche_seite). Taugt die Anfrage für die
    globale Suche (globalsuche.angebot), bietet die Seite sie an – „suche“ in den Daten; sonst bleibt q unbeachtet."""
    q = (request.args.get("q") or "").strip()
    weiter = {"suche": q} if q and current_user() and zugang() and globalsuche.angebot(q) else {}
    return _seite("artikel", bezug=("artikel", iid), warnung=lambda: ueberblick.warnung(iid), id=iid, **weiter)


@seiten.get("/material/artikel/<int:iid>/pruefung/neu")
def pruefung_neu(iid):
    """Sehen genügt für die Seite; den Knopf zum Beginnen blendet die Oberfläche ohne Prüffreigabe aus, und die
    Schnittstelle prüft selbst."""
    return _seite("pruefung_neu", bezug=("artikel", iid), id=iid, durchgang=request.args.get("durchgang", type=int))


@seiten.get("/material/pruefung/<int:pid>")
def pruefung_seite(pid):
    return _seite("pruefung", bezug=("pruefung", pid), id=pid)


@seiten.get("/material/durchgang/<int:rid>")
def durchgang_seite(rid):
    return _seite("durchgang", bezug=("durchgang", rid), id=rid)


def _protokoll_senden(row, quelle, kennung_wert, inventarnummer=None):
    """Ein festgeschriebenes Protokoll ausliefern – nur an Angemeldete, die den Artikel (über seine Heimat) bzw. den
    Durchgang sehen dürfen, und nur, wenn die Datei noch genau die festgeschriebene ist (Prüfsumme). Fremdes antwortet
    wie Unbekanntes mit 404. Im Browser geöffnet, nicht heruntergeladen."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.path))
    if not zugang(u):
        return _fehlerseite(403, zugang_meldung(u))
    try:
        b = _bezug(quelle, {quelle: kennung_wert})
        if not darf("lesen", b.ordner_id):
            raise Abgelehnt(b.meldung, 404)
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
    Sie zeigt nur das Ergebnis und die Protokoll-ID, keine Personendaten; den Link zur Prüfung nur, wer sie sehen darf."""
    u = current_user()
    return render_template("material/pruefen.html", user=u, active="material" if u else None,
                           angemeldet=bool(u and zugang(u)))


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
    """Die Material-Verwaltung arbeitet hier die Meldungen fehlender Produkte ab; Materialwarte sehen ihre eigenen
    (oder alle), wer sonst Zugang zum Modul hat, liest alle."""
    return _seite("meldungen", katalog_seite=True, status=request.args.get("status"))


@seiten.get("/material/suche")
def suche_seite():
    """Ein eindeutiger Treffer öffnet den Artikel direkt; sonst zeigt die Seite die Trefferliste und darunter das
    Angebot der globalen Suche. Gezählt wird nur, was das Konto sieht (search.artikel filtert selbst) – die
    Weiterleitung führt nie zu Fremdem. Angeboten wird die globale Suche immer (Entscheidung vom 18.10.2026), also
    auch nach der Weiterleitung: Taugt die Anfrage dafür, nimmt die Weiterleitung sie mit (?q=), und die Artikelseite
    bietet sie unter dem Kopf an (artikel_seite)."""
    q = (request.args.get("q") or "").strip()
    if current_user() and zugang() and q:
        try:
            treffer, gesamt = search.artikel(q, 1, 2)
        except Abgelehnt:
            treffer, gesamt = [], 0
        if gesamt == 1:
            weiter = {"q": q} if globalsuche.angebot(q) else {}
            return redirect(url_for("material.artikel_seite", iid=treffer[0]["id"], **weiter))
    return _seite("suche", q=q)


@seiten.get("/m/<token>")
def qr_ziel(token):
    """Ziel des QR-Codes: über die Anmeldung zum Artikel. Wer das Modul nicht sehen darf, bekommt
    nichts über den Artikel zu wissen – auch nicht, ob es ihn gibt. Gehört der Artikel nicht zum eigenen Bereich,
    zeigt die Seite „fremd“ nur das (ohne Artikeldaten im HTML); den Steckbrief gibt es dort erst nach Bestätigung
    (POST /globalsuche/qr, protokolliert)."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=f"/m/{token}"))
    if not zugang(u):
        return _fehlerseite(403, zugang_meldung(u))
    i = db.query("SELECT id, folder_id, origin_folder_id, lock_state FROM mat_item WHERE qr_token = ?", (token,), one=True)
    if not i:
        abort(404)
    if darf_artikel("lesen", i):
        return redirect(url_for("material.artikel_seite", iid=i["id"]))
    return _seite("fremd", token=token)


@seiten.get("/media/material/<art>/<path:dateiname>")
def medien(art, dateiname):
    """Fotos, Anhänge und Herstellerdokumente – nur für Angemeldete mit Zugang zum Modul und je Datei nur für die, die
    ihren Besitzer sehen dürfen (services/medien.py); sonst 404 wie für Unbekanntes. Nie in einem gemeinsamen
    Zwischenspeicher. Skripte sind auch in einem PDF oder SVG wirkungslos."""
    if art not in medien_dienst.ARTEN:
        abort(404)
    if not current_user():
        abort(401)
    if not zugang():
        abort(403)
    if not medien_dienst.darf_datei(art, dateiname):
        abort(404)
    resp = send_from_directory(os.path.join(katalog.medien_dir(), art), dateiname, max_age=60 * 60 * 24 * 7)
    resp.cache_control.public = None
    resp.cache_control.private = True
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; sandbox"
    return resp


# --- Schnittstelle: Start und Suche --------------------------------------------------------------------

@api.get("/start")
@requires_zugang
def start():
    """Die Übersicht – alle Zahlen über das, was das Konto sieht. „erinnerungen“: der Laufstand der Erinnerungsmails
    (erinnerung.stand) nur für die Material-Verwaltung (die Plattform-Verwaltung eingeschlossen), sonst null.
    „nacharbeit“: offene Nacharbeit aus Bestandsimporten je Zielordner, den das Konto verwaltet (sonst leer)."""
    alle = bestand.baum()
    gliederungen = [o for o in alle if o["kind"] == "gliederung" and not o["system_kind"] and not o.get("nur_pfad")]
    naechste, faellig = bestand.faellige(pro_seite=10)
    z = bestand.zaehlung()
    return jsonify(darf=darf_alles(), zaehlung=z, bestand=sum(z[s] for s in st.BESTAND),
                   ordner_uebersicht=ueberblick.ordner_uebersicht(alle),
                   gliederungen=gliederungen, naechste=naechste, faellig_gesamt=faellig,
                   schwelle_tage=st.schwelle_tage(), status_text=st.LABEL,
                   meldungen_offen=meldung.anzahl_offen() if ist_material_verwaltung() else None,
                   rueckrufe=rueckruf.uebersicht(),
                   erinnerungen=erinnerung.stand() if ist_material_verwaltung() else None,
                   nacharbeit=bestandsimport.offen_uebersicht())


@api.get("/suche")
@requires_zugang
def suche():
    """Lokale Suche über das, was das Konto sieht (Treffer, gesamt, eindeutig). exakt_lokal: ein sichtbarer Artikel hat
    genau diese Seriennummer (die Oberfläche sagt dann, dass die globale Suche nur die anderen zeigt); global_angebot:
    die Oberfläche bietet unter den eigenen Treffern die globale Suche an (globalsuche.angebot – zu jeder tauglichen
    Anfrage, nicht der Material-Verwaltung)."""
    q = request.args.get("q", "")
    seite, pro_seite = _seite_args()
    rows, gesamt = search.artikel(q, seite, pro_seite, *_sortier_args())
    treffer = []
    for r in rows:
        k = bestand.artikel_kurz(r)
        k["pfad"] = " / ".join(o["name"] for o in bestand.pfad(r["folder_id"]))
        treffer.append(k)
    exakt = search.exakt_lokal(q)
    return jsonify(treffer=treffer, gesamt=gesamt, eindeutig=treffer[0]["id"] if gesamt == 1 and treffer else None,
                   exakt_lokal=exakt, global_angebot=globalsuche.angebot(q))


def _zugeordnet_arg():
    """?zugeordnet=<Kontokennung> – der Filter „Zugeordnet an“; die Dienste wenden ihn nur an, wo das Grundrecht gilt."""
    return kennung(request.args.get("zugeordnet"), "Zugeordnet an", leer_erlaubt=True)


@api.get("/faellig")
@requires_zugang
def faellig():
    """Fällige Artikel über das, was das Konto sieht; ?ordner= nur für einen sichtbaren Ordner (sonst 404 wie für
    Unbekanntes)."""
    nur = request.args.get("status") or ""
    stati = tuple(s for s in nur.split(",") if s in st.STATUS) or bestand.FAELLIG
    seite, pro_seite = _seite_args()
    ordner_id = request.args.get("ordner", type=int)
    if ordner_id:
        bestand.ordner(ordner_id)
        if not sicht().sichtbar(ordner_id):
            raise Abgelehnt(ORDNER_FEHLT, 404)
    liste, gesamt = bestand.faellige(ordner_id, stati, seite, pro_seite, *_sortier_args(), zugeordnet=_zugeordnet_arg())
    # Mit Ordner (aus der Übersicht): sein Pfad für die Überschrift der Liste.
    return jsonify(artikel=liste, gesamt=gesamt, schwelle_tage=st.schwelle_tage(),
                   ordner={"id": ordner_id, "pfad": bestand.pfad(ordner_id)} if ordner_id else None)


# --- Schnittstelle: Katalog ----------------------------------------------------------------------------

def _katalog_lesen():
    """Der Katalog ist global: lesen darf jeder mit Modulzugang."""
    if not zugang():
        raise Abgelehnt(zugang_meldung(), 403)


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
    """Für den Hinweis beim Tippen: Wem gehört diese Artikelnummer schon? („ausser“: das Produkt, das man bearbeitet)
    name ist der Name als Text (katalog.produktname); manufacturer, model und description braucht die Oberfläche, um
    den Zusatz wie überall grau hinter den Link zu setzen (nameHtml/zusatzHtml in material.js)."""
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    da = katalog.artikelnummer_vergeben(request.args.get("nr", ""), request.args.get("ausser", type=int))
    return jsonify(produkt={"id": da["id"], "name": katalog.produktname(da), "manufacturer": da["manufacturer"],
                            "model": da["model"], "description": da["description"], "article_no": da["article_no"]}
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
    # Meldungen, über die das Produkt kam, nur soweit das Konto sie sehen darf (Melder, Ordner der Meldung …).
    p["journal"] = journal.fuer_produkt(pid, current_user())
    p["formulare"] = katalog.formulare_fuer(produkt_id=pid)
    p["rueckrufe"] = rueckruf.fuer_produkt(pid)
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
    """Lesen darf jeder mit Zugang zum Modul – jeder nur die Meldungen, die er sehen darf (rechte.darf_meldung):
    die Material-Verwaltung alle, sonst die eigenen und die aus Ordnern, die er sieht; „offen“ zählt ebenso.
    Standard: Material-Verwaltung und Lesende (Führungskraft) sehen alle davon (offene zuerst), Materialwarte ihre
    eigenen (alle Stände); „eigene=1“ bzw. „eigene=0“ wählt ausdrücklich. Abarbeiten („bearbeiten“) darf nur die
    Material-Verwaltung."""
    u = current_user()
    if not u:
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    eigene = request.args.get("eigene")
    if eigene in ("0", "1"):
        alle = eigene == "0"
    else:
        alle = ist_material_verwaltung() or not sicht().irgendwo("verwalten")
    filter_ = request.args.get("status") if request.args.get("status") in meldung.FILTER else ("offen" if alle else "alle")
    rows = meldung.liste(filter_, None if alle else u["id"])
    return jsonify(meldungen=[meldung.meldung_json(r) for r in rows], alle=alle, filter=filter_,
                   bearbeiten=alle and ist_material_verwaltung(), offen=meldung.anzahl_offen() if alle else None)


@api.post("/meldungen")
@requires_folder("verwalten", "eingabe:folder_id", leer="irgendwo")
def meldung_anlegen():
    """Ein fehlendes Produkt melden – Felder als JSON oder, mit Fotos, als Formular (Feld „fotos“, mehrfach)."""
    mid = meldung.anlegen(_eingabe(), request.files.getlist("fotos"))
    return jsonify(meldung=meldung.meldung_json(meldung.meldung(mid))), 201


@api.get("/meldungen/<int:mid>")
@requires_zugang
def meldung_lesen(mid):
    """Lesen darf, wer die Meldung sehen darf: die Material-Verwaltung, der Melder und wer den Ordner der Meldung
    sieht – alle nur mit Zugang zum Modul (sonst 403 vor der Frage nach der Meldung). Sonst dieselbe 404 wie für eine,
    die es nicht gibt."""
    return jsonify(meldung=meldung.meldung_json(meldung.lesbar(mid)))


@api.delete("/meldungen/<int:mid>")
def meldung_loeschen(mid):
    """Nur der Melder selbst (meldung.loeschen prüft das) – seine eigene auch ohne Zugang zum Modul. Wer eine fremde
    Meldung nicht sehen darf, bekommt dieselbe 404 wie für eine, die es nicht gibt – auch ohne Modulzugang."""
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
@requires_zugang
def ordner_baum():
    """Der Baum, wie ihn das Konto sieht: sichtbare Ordner mit Zahlen und „darf“, teilweise sichtbare Systemordner,
    Pfad-Knoten ohne Zahlen (bestand.baum)."""
    return jsonify(ordner=bestand.baum(), ordnerarten=models.ORDNERARTEN)


@api.post("/ordner")
@requires_folder("verwalten", "json:parent_id", leer="global")
def ordner_anlegen():
    """Ein Unterordner – wer den Oberordner verwaltet; eine Gliederung auf oberster Ebene nur die Verwaltung."""
    fid = bestand.ordner_anlegen(json_body())
    sicht_verwerfen()                                  # der neue Ordner gehört ab jetzt zur Sicht
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid))), 201


@api.get("/ordner/<int:fid>")
@requires_folder("lesen", "fid")
def ordner_lesen(fid):
    """Auch ein teilweise sichtbarer Systemordner (nur die eigenen Artikel); Journal nur mit Grundrecht."""
    # Ein Ordner zeigt bis zu 500 Artikel je Seite (Vorgabe 200) – mehr als die Suche, weil hier ganze
    # Lager durchgesehen werden.
    seite = search.seiten(request.args.get("seite", 1), 1)[0]
    pro_seite = max(1, min(500, request.args.get("pro_seite", 200, type=int) or 200))
    return jsonify(ordner=bestand.ordner_inhalt(fid, request.args.get("status") or None, seite, pro_seite,
                                                *_sortier_args(), zugeordnet=_zugeordnet_arg()))


ZWISCHEN_GLIEDERUNGEN = ("Zwischen Gliederungen verschiebt nur, wer beide Gliederungen verwaltet – oder die "
                         "Material-Verwaltung.")
ZUR_GLIEDERUNG = ("Zur Gliederung macht einen Ordner nur, wer die Gliederung darüber verwaltet – oder die "
                  "Material-Verwaltung.")


@api.put("/ordner/<int:fid>")
@requires_folder("verwalten", "fid")
def ordner_aendern(fid):
    """Bearbeiten darf, wer den Ordner verwaltet. Wird er dabei zur Gliederung, wechselt alles darin die Gliederung –
    wie beim Verschieben über Gliederungsgrenzen braucht das Verwalten an der bisherigen Gliederung (1.7 Nr. 2). Sonst
    machte, wer nur einen Unterordner verwaltet, ihn zur eigenen Gliederung und zöge danach von dort ab."""
    d = json_body()
    o = bestand.ordner(fid)
    if d.get("kind") == "gliederung" and o["kind"] != "gliederung" and not o["system_kind"]:
        bisher = bestand.gliederung_von(o["parent_id"])
        if not darf("verwalten", bisher["id"] if bisher else None):
            raise Abgelehnt(ZUR_GLIEDERUNG, 403)
    bestand.ordner_aendern(fid, d)
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


def _ziel_pruefen(ziel, ausser=()):
    """Ein Zielordner aus dem Inhalt der Anfrage: gibt es ihn nicht oder sieht das Konto ihn nicht, 404 wie für
    Unbekanntes; liegt er im verschobenen Zweig (ausser), 400; ohne Verwalten dort 403."""
    if not db.query("SELECT 1 FROM mat_folder WHERE id = ?", (ziel,), one=True) or not sicht().sichtbar(ziel):
        raise Abgelehnt(ORDNER_FEHLT, 404)
    if ziel in ausser:
        raise Abgelehnt("Ein Ordner kann nicht in sich selbst liegen.")
    if not darf("verwalten", ziel):
        raise Abgelehnt("Im Zielordner darfst du nichts ablegen.", 403)


def _gliederungswechsel(quelle, ziel):
    """Über Gliederungsgrenzen (nächste Gliederung, der Ordner selbst eingeschlossen) nur mit Verwalten an beiden
    Gliederungen (1.7 Nr. 2) – mit geliehenem Recht an einem Unterordner lässt sich nichts abziehen. Ohne Gliederung
    (oberste Ebene) zählt das globale Recht, also nur die Verwaltung."""
    gq, gz = bestand.gliederung_von(quelle), bestand.gliederung_von(ziel)
    q, z = (gq["id"] if gq else None), (gz["id"] if gz else None)
    if q != z and not (darf("verwalten", q) and darf("verwalten", z)):
        raise Abgelehnt(ZWISCHEN_GLIEDERUNGEN, 403)


@api.post("/ordner/<int:fid>/verschieben")
@requires_folder("verwalten", "fid")
def ordner_verschieben(fid):
    """Verwalten am alten Oberordner und am Ziel (auf oberster Ebene: nur die Material-Verwaltung), bei einem Wechsel der
    Gliederung an beiden Gliederungen. Gesperrte und ausgesonderte Artikel wandern mit, offene Durchgänge nehmen, was
    ihren Zweig verlässt, mit Grund heraus (bestand.ordner_verschieben)."""
    d = json_body()
    ziel = kennung(d.get("parent_id"), "Zielordner", leer_erlaubt=True)
    o = bestand.ordner(fid)
    # Was ohnehin nicht geht, sagt der Dienst – hier vorweg, damit die Antwort nicht vom Recht abhängt.
    if o["system_kind"]:
        raise Abgelehnt(bestand.SYSTEMORDNER_FEST, 409)
    if ziel is None:
        if o["kind"] != "gliederung":
            raise Abgelehnt(bestand.NUR_GLIEDERUNG_OBEN)
        if not darf("verwalten", None):
            raise Abgelehnt("Auf die oberste Ebene verschiebt nur die Material-Verwaltung.", 403)
    else:
        _ziel_pruefen(ziel, ausser=bestand.unterbaum(fid))
    alt = o["parent_id"]
    if not darf("verwalten", alt):
        raise Abgelehnt("Verschieben darf nur, wer den Ordner darüber verwaltet – eine Gliederung auf oberster Ebene "
                        "nur die Material-Verwaltung.", 403)
    if ziel != alt:
        _gliederungswechsel(alt, ziel)
    bestand.ordner_verschieben(fid, ziel)
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


@api.delete("/ordner/<int:fid>")
@requires_folder("verwalten", "fid")
def ordner_loeschen(fid):
    """Löschen darf, wer den Oberordner verwaltet – eine Gliederung auf oberster Ebene nur die Material-Verwaltung."""
    if not darf("verwalten", bestand.ordner(fid)["parent_id"]):
        raise Abgelehnt("Diesen Ordner löscht nur, wer den Ordner darüber verwaltet – eine Gliederung auf oberster "
                        "Ebene nur die Material-Verwaltung.", 403)
    bestand.ordner_loeschen(fid)
    return jsonify(ok=True)


@api.post("/ordner/<int:fid>/foto")
@requires_folder("verwalten", "fid")
def ordner_foto(fid):
    bestand.ordner_foto_setzen(fid, request.files.get("file"))
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


@api.delete("/ordner/<int:fid>/foto")
@requires_folder("verwalten", "fid")
def ordner_foto_entfernen(fid):
    bestand.ordner_foto_entfernen(fid)
    return jsonify(ordner=bestand.ordner_json(bestand.ordner(fid)))


# --- Schnittstelle: Artikel -----------------------------------------------------------------------------

@api.get("/artikel/vorschlag")
@requires_folder("lesen", "arg:folder_id", leer="zugang")
def artikel_vorschlag():
    """Vorschlag für einen neuen Artikel – mit Ordner nur für einen, den das Konto sieht (sonst 404)."""
    return jsonify(vorschlag=bestand.vorschlag(request.args))


@api.post("/artikel")
@requires_folder("verwalten", "json:folder_id", leer="global")
def artikel_anlegen():
    """Anlegen im Ordner, den das Konto verwaltet. Gibt es die Seriennummer bei diesem Produkt schon in einem fremden
    Bereich, antwortet _fremde_dublette (protokolliert, ohne Inventarnummer)."""
    iid = bestand.artikel_anlegen(json_body())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True)), 201


@api.get("/artikel/<int:iid>")
@requires_folder("lesen", "iid")
def artikel_lesen(iid):
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.put("/artikel/<int:iid>")
@requires_folder("verwalten", "iid")
def artikel_aendern(iid):
    bestand.artikel_aendern(iid, json_body())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.delete("/artikel/<int:iid>")
@requires_folder("verwalten", "iid")
def artikel_loeschen(iid):
    bestand.artikel_loeschen(iid)
    return jsonify(ok=True)


@api.post("/artikel/verschieben")
@requires_folder("verwalten", "json:folder_id", leer="global")
def artikel_verschieben():
    """Mehrere Artikel in einen Ordner, den das Konto verwaltet (der Decorator prüft das Ziel). Je Artikel: Kennung wie
    im Dienst (kennung – „7“ und 7.0 gelten), nicht sichtbar → 404 wie für Unbekanntes, ohne Verwalten → 403; bei einem
    Wechsel der Gliederung Verwalten an beiden (1.7 Nr. 2)."""
    d = json_body()
    ziel = kennung(d.get("folder_id"), "Zielordner")
    ids = d.get("ids")
    if isinstance(ids, list) and 1 <= len(ids) <= 500:
        zeilen = []
        for wert in ids:
            row = db.query("SELECT * FROM mat_item WHERE id = ?", (kennung(wert, "Artikel"),), one=True)
            if not row or not darf_artikel("lesen", row):
                raise Abgelehnt(ARTIKEL_FEHLT, 404)
            zeilen.append(row)
        if any(not darf_artikel("verwalten", row) for row in zeilen):
            raise Abgelehnt("Mindestens einen der Artikel darfst du nicht verschieben.", 403)
        for heimat in {bestand.heimat(row) for row in zeilen}:
            _gliederungswechsel(heimat, ziel)
    n = bestand.artikel_verschieben(ids, ziel)
    return jsonify(ok=True, verschoben=n)


# --- Schnittstelle: Prüfungen ------------------------------------------------------------------------------

def _pruefer():
    return pruefung.pruefer_aus(current_user())


def _pruefung_antwort(pid, code=200):
    return jsonify(pruefung=pruefung.pruefung_json(pruefung.pruefung(pid), current_user()["id"])), code


@api.get("/artikel/<int:iid>/pruefungen")
@requires_folder("lesen", "iid")
def artikel_pruefungen(iid):
    return jsonify(pruefungen=pruefung.fuer_artikel(iid))


@api.post("/artikel/<int:iid>/pruefungen")
@requires_folder("pruefen", "iid")
def pruefung_starten(iid):
    """Prüfung beginnen; durchgang_id nur für einen Durchgang, in dem der Artikel steht und in dessen Zweig seine Heimat
    liegt – sonst 404 wie für einen unbekannten Durchgang (durchgang.runde_fuer_start)."""
    d = json_body()
    rid = kennung(d.get("durchgang_id"), "Prüfdurchgang", leer_erlaubt=True)
    pid, neu = pruefung.starten(iid, _pruefer(), d.get("art") or None, rid)
    return _pruefung_antwort(pid, 201 if neu else 200)


@api.get("/pruefungen/<int:pid>")
@requires_folder("lesen", "pid")
def pruefung_lesen(pid):
    return _pruefung_antwort(pid)


@api.put("/pruefungen/<int:pid>")
@requires_folder("pruefen", "pid")
def pruefung_kopf(pid):
    pruefung.kopf_setzen(pid, json_body(), _pruefer())
    return _pruefung_antwort(pid)


@api.put("/pruefungen/<int:pid>/punkte/<int:rid>")
@requires_folder("pruefen", "pid")
def punkt_setzen(pid, rid):
    return jsonify(punkt=pruefung.punkt_setzen(pid, rid, json_body(), _pruefer()))


@api.post("/pruefungen/<int:pid>/punkte/<int:rid>/foto")
@requires_folder("pruefen", "pid")
def punkt_foto(pid, rid):
    return jsonify(punkt=pruefung.punkt_foto_setzen(pid, rid, request.files.get("file"), _pruefer()))


@api.delete("/pruefungen/<int:pid>/punkte/<int:rid>/foto")
@requires_folder("pruefen", "pid")
def punkt_foto_entfernen(pid, rid):
    return jsonify(punkt=pruefung.punkt_foto_entfernen(pid, rid, _pruefer()))


@api.post("/pruefungen/<int:pid>/anhaenge")
@requires_folder("pruefen", "pid")
def anhang_neu(pid):
    a = pruefung.anhang_hinzufuegen(pid, request.form, request.files.getlist("file"), _pruefer())
    return jsonify(anhang=a), 201


@api.delete("/pruefungen/<int:pid>/anhaenge/<int:aid>")
@requires_folder("pruefen", "pid")
def anhang_entfernen(pid, aid):
    pruefung.anhang_entfernen(pid, aid, _pruefer())
    return jsonify(ok=True)


@api.post("/pruefungen/<int:pid>/festschreiben")
@api.post("/pruefungen/<int:pid>/abschliessen")
@requires_folder("pruefen", "pid")
def pruefung_abschliessen(pid):
    """Abschließen heißt seit Lieferung 3 Festschreiben (der alte Pfad bleibt für offene Seiten gültig)."""
    pruefung.abschliessen(pid, json_body(), _pruefer())
    return _pruefung_antwort(pid)


@api.post("/pruefungen/<int:pid>/berichtigen")
@requires_folder("pruefen", "pid")
def pruefung_berichtigen(pid):
    """Berichtigung einer abgeschlossenen Prüfung beginnen – liefert den neuen Entwurf."""
    neu = pruefung.berichtigen(pid, json_body(), _pruefer())
    return _pruefung_antwort(neu, 201)


@api.delete("/pruefungen/<int:pid>")
@requires_folder(("pruefen", "verwalten"), "pid")
def pruefung_verwerfen(pid):
    """Den eigenen Entwurf verwerfen (prüfen) – oder als Materialwart eine liegen gebliebene Reservierung freigeben
    (verwalten am Artikel)."""
    pruefung.verwerfen(pid, _pruefer(), darf_freigeben=darf_artikel("verwalten", g.mat_artikel))
    return jsonify(ok=True)


@api.get("/entwuerfe")
@requires_zugang
def entwuerfe():
    """Offene Prüfungen zu Artikeln, die das Konto sieht."""
    return jsonify(entwuerfe=pruefung.entwuerfe(current_user()["id"]))


@api.post("/artikel/<int:iid>/sperren")
@requires_folder("pruefen", "iid")
def artikel_sperren(iid):
    pruefung.sperren(iid, json_body(), _pruefer())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True))


@api.post("/artikel/<int:iid>/aussondern")
@requires_folder("verwalten", "iid")
def artikel_aussondern(iid):
    aid = pruefung.aussondern(iid, json_body(), _pruefer())
    return jsonify(artikel=bestand.artikel_json(bestand.artikel(iid), voll=True), aussonderung=aid)


# --- Schnittstelle: eigene Urkundennummer und Unterschrift, Prüfseite --------------------------------------------

@api.put("/urkundennummer")
@requires_zugang
def urkundennummer_setzen():
    """Die eigene Urkundennummer im Profil eintragen, ändern oder leer entfernen – nur mit dem Häkchen „Prüfer“ aus der
    Nutzerverwaltung, nur fürs eigene Konto (eine Kennung in der Anfrage gibt es nicht). Erst mit ihr darf er prüfen."""
    nummer = urkunde_setzen(current_user(), json_body())
    u = db.query("SELECT * FROM users WHERE id = ?", (current_user()["id"],), one=True)
    return jsonify(urkundennummer=nummer, pruefen=qualifiziert(u))


@api.get("/unterschrift")
@login_required
def unterschrift_lesen():
    """Die eigene Unterschrift – auch ohne Zugang zum Modul: Es sind die eigenen Daten, und das Profil zeigt sie dann zum
    Entfernen (nach einem Wechsel der Stufe auf „–“)."""
    return jsonify(unterschrift=unterschrift.daten_uri(unterschrift.von(current_user()["id"])))


@api.put("/unterschrift")
@requires_zugang
def unterschrift_setzen():
    """Die eigene Unterschrift hinterlegen (data:-URL vom Signatur-Pad) – Grundlage jedes Festschreibens. Nur wer
    festschreibt (Prüfer, schon mit dem Häkchen – die Urkundennummer darf noch fehlen) oder aussondert (Materialwart),
    braucht eine; entfernen darf jeder seine eigene."""
    if not darf_unterschreiben():
        return jsonify(error="Nur für Materialwarte und Prüfer."), 403
    return jsonify(unterschrift=unterschrift.setzen(current_user(), json_body().get("bild")))


@api.delete("/unterschrift")
@login_required
def unterschrift_entfernen():
    """Die eigene Unterschrift entfernen darf jeder, auch ohne Zugang zum Modul – sie gehört ihm."""
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
    if u and zugang(u) and ergebnis.get("protokoll_id"):
        link = _protokoll_link(ergebnis["protokoll_id"])
        if link:
            ergebnis["link"] = link
    return jsonify(ergebnis)


def _protokoll_link(pid):
    """Für Angemeldete, die den Artikel bzw. den Durchgang sehen dürfen: wohin das Protokoll in der Oberfläche gehört –
    sonst None (ein fremdes Protokoll prüft die Seite trotzdem, sie verlinkt nur nicht)."""
    if pid.startswith("S-"):
        r = db.query("SELECT id, folder_id FROM mat_round WHERE protocol_id = ?", (pid,), one=True)
        return f"/material/durchgang/{r['id']}" if r and darf("lesen", r["folder_id"]) else None
    r = db.query("SELECT x.id, i.folder_id, i.origin_folder_id, i.lock_state FROM mat_inspection x "
                 "JOIN mat_item i ON i.id = x.item_id WHERE x.protocol_id = ?", (pid,), one=True)
    return f"/material/pruefung/{r['id']}" if r and darf_artikel("lesen", r) else None


# --- Schnittstelle: Prüfdurchgänge ---------------------------------------------------------------------------

@api.get("/durchgaenge")
@requires_zugang
def durchgaenge():
    """Die Durchgänge, deren Ordner das Konto sieht."""
    return jsonify(durchgaenge=durchgang.liste(nur_offen=request.args.get("offen") == "1"))


@api.post("/durchgaenge")
@requires_folder(("verwalten", "pruefen"), "json:folder_id", leer="global")
def durchgang_eroeffnen():
    d = json_body()
    rid = durchgang.eroeffnen(kennung(d.get("folder_id"), "Ordner"), d, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid))), 201


@api.get("/durchgaenge/<int:rid>")
@requires_folder("lesen", "rid")
def durchgang_lesen(rid):
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid), voll=True, pruefer_id=current_user()["id"]))


@api.post("/durchgaenge/<int:rid>/ausnehmen")
@requires_folder(("verwalten", "pruefen"), "rid")
def durchgang_ausnehmen(rid):
    d = json_body()
    durchgang.ausnehmen(rid, kennung(d.get("item_id"), "Artikel"), d, _pruefer())
    return jsonify(ok=True)


@api.post("/durchgaenge/<int:rid>/einbeziehen")
@requires_folder(("verwalten", "pruefen"), "rid")
def durchgang_einbeziehen(rid):
    """item_id nicht im Durchgang: 404; hat seine Heimat den Zweig verlassen oder steht er in einem anderen offenen
    Durchgang offen: 409 (durchgang.einbeziehen)."""
    durchgang.einbeziehen(rid, kennung(json_body().get("item_id"), "Artikel"))
    return jsonify(ok=True)


@api.post("/durchgaenge/<int:rid>/abschliessen")
@requires_folder(("verwalten", "pruefen"), "rid")
def durchgang_abschliessen(rid):
    durchgang.abschliessen(rid, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid)))


@api.post("/durchgaenge/<int:rid>/abbrechen")
@requires_folder(("verwalten", "pruefen"), "rid")
def durchgang_abbrechen(rid):
    """Vorzeitig beenden; „durchgang“ ist null, wenn er mangels Geprüftem ganz entfernt wurde."""
    bleibt = durchgang.abbrechen(rid, _pruefer())
    return jsonify(durchgang=durchgang.durchgang_json(durchgang.runde(rid)) if bleibt else None)


@api.delete("/durchgaenge/<int:rid>")
@requires_folder(("verwalten", "pruefen"), "rid")
def durchgang_loeschen(rid):
    durchgang.loeschen(rid)
    return jsonify(ok=True)


from . import routes_rueckruf  # noqa: E402,F401
from . import routes_export  # noqa: E402,F401
from . import routes_katalog  # noqa: E402,F401
from . import routes_freigaben  # noqa: E402,F401
from . import routes_global  # noqa: E402,F401
from . import routes_zuordnung  # noqa: E402,F401
from . import routes_erinnerung  # noqa: E402,F401
from . import routes_import  # noqa: E402,F401
