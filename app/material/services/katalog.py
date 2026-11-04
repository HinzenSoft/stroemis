"""Katalog: Kategorien, Produkte, Dokumente (am Produkt oder für alle Produkte einer Kategorie) und
Prüfformulare.

Pflegen darf ihn nur die Material-Verwaltung – Stufe Verwaltung in der Materialablage (routes.py prüft das an jeder
Route). Die
Regeln stehen hier, weil der Katalogimport (importer.py) dieselben braucht wie die Oberfläche.

Fachliche Grenzen aus dem Konzept:
  - Dublette = Hersteller + Modell + Artikelnummer (vereinheitlicht, siehe dedupe_key). Dazu gibt es jede
    Artikelnummer je Hersteller nur einmal (gleich vereinheitlicht; leer zählt nicht), siehe artikelnummer_vergeben –
    nicht mehr katalogweit (Entscheidung vom 22.10.2026): Echte Herstellernummern kollidieren zwischen Herstellern
    (Petzl MICRO TRAXION = P53, Rock Exotica Omni-Block 2.0 Single = P53).
  - Lebensdauer: Pflicht bei textilem Material, verboten bei Metall, bei „sonstiges“ nur mit
    Herstellerangabe (Fundstelle).
  - Prüfformulare (seit Schritt 38 ein Pool je Kategorie): Ein Formular steht im Pool seiner Kategorie und gilt als
    Standard einer Kategorie (auch in Unterkategorien ohne eigenen) oder einem Produkt zugewiesen. Versioniert; eine
    benutzte Version wird nie mehr geändert, sondern durch eine neue ersetzt.
  - Fotos und Herstellerdokumente hängen am Produkt, nie am einzelnen Artikel. Allgemeine Dokumente
    (Pflegehinweise, Anleitungen) können an einer Kategorie hängen und gelten dann für alle Produkte
    darin und in ihren Unterkategorien.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3

from flask import current_app, g, has_request_context

from ... import db
from ...images import ALLOWED_EXT, delete_photo_files, store_upload
from ..models import DEMO_KATEGORIEN, DOKUMENTARTEN, EDITOREN, MATERIALARTEN, geltend_je_produkt
from . import Abgelehnt, akteur, auswahl, datum, ganzzahl, heute, kennung, text, wahr
from . import faelligkeit, journal
from .interval import herstellerseite, lebensende

FORMULAR_BENUTZT = ("Diese Formularversion wurde schon für Prüfungen benutzt und bleibt deshalb unverändert. "
                    "Lege eine neue Version an.")
TITEL_PFLICHT = "Ein Prüfformular braucht einen Titel."
NUR_AKTIV_ZUWEISEN = "Zuweisen lässt sich nur ein Formular mit aktiver Version – erst eine Version aktivieren."
LEBENSDAUER_TEXTIL = "Bei textilem Material ist die Lebensdauer Pflicht (Herstellerangabe in Jahren)."
LEBENSDAUER_METALL = "Metall hat keine festgeschriebene Lebensdauer – das Feld bleibt leer."
LEBENSDAUER_SONSTIGES = "Bei „sonstiges“ gibt es eine Lebensdauer nur mit Herstellerangabe (Fundstelle angeben)."
KEIN_INTERVALL = "Kein Prüfintervall: am Produkt angeben oder in der Kategorie als Vorgabe hinterlegen."
# Ein Prüfpunkt ist oft eine ganze Prüfanweisung („Kontrolle des Zustands der Verriegelungshülse (z. B. …)“).
PUNKT_TEXT_MAX = 1000
# Die Beschreibung eines Produkts ist ein kurzer Zusatz hinter dem Modell – etwa die Verschlussart eines Karabiners – und
# steht überall direkt hinter dem Modell vor der Artikelnummer, ohne Strich, in Oberfläche und PDF grau (Nachbesserungen
# vom 18.10.2026; produkt_teile und produktname hier, produktZusatz und produktName in material.js). Sichtbar heißt sie
# seit dem Wunsch vom 18.10.2026 „Bemerkung“ (Dialog, Meldungen, Produktseite, CSV, Importbericht); Spalte description,
# Schnittstelle und der Schlüssel „beschreibung“ im Katalogformat bleiben, die Namen im Code auch. Eine Zeile,
# höchstens so lang wie eine Artikelnummer: Das reicht für zwei Angaben („Twistlock, Aluminium“) und passt mit dem
# Modell noch in eine Listenzeile, ein Absatz passt nicht hinein – Ausführliches gehört in ein Dokument am Produkt. Bis
# dahin war das Feld mehrzeilig, bis 4000 Zeichen. Solche älteren Beschreibungen bleiben, wie sie sind: Der
# Katalogimport übernimmt sie unverändert (der Austausch dev → Produktion soll nicht an Altbeständen scheitern), die
# Anzeige kürzt sie auf eine Zeile mit „…“, und wer das Produkt über die Oberfläche speichert, kürzt sie selbst – der
# Dialog zeigt dazu den vollen Text.
BESCHREIBUNG_MAX = 80

# Herstellerdokumente: PDF und Bilder, unverändert abgelegt. Der Inhalt muss zur Endung passen – eine
# HTML-Datei mit .pdf-Endung wird nicht angenommen, auch wenn die Medienroute sie ohnehin nur mit
# strenger CSP ausliefert.
DOK_TYPEN = {".pdf": ("application/pdf", (b"%PDF-",)),
             ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)), ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
             ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
             ".webp": ("image/webp", (b"RIFF",))}
DOK_MAX_BYTES = 50 * 1024 * 1024
BILD_MAX_BYTES = 30 * 1024 * 1024


def medien_dir():
    """media/material: orig/web/thumb für Produkt- und Ordnerfotos (store_upload), dok/ für Dokumente.
    Ausgeliefert über /media/material/… nur an Angemeldete mit Zugang zum Modul."""
    return os.path.join(current_app.config["MEDIA_DIR"], "material")


def dok_dir():
    d = os.path.join(medien_dir(), "dok")
    os.makedirs(d, exist_ok=True)
    return d


def _mischen(alt, d, felder):
    """Für Änderungen: Was die Anfrage nicht nennt, bleibt, wie es war."""
    eingabe = {f: alt.get(f) for f in felder} if alt else {}
    eingabe.update({f: d[f] for f in felder if f in d})
    return eingabe


# --- Kategorien -------------------------------------------------------------------------------------

KATEGORIE_FELDER = ("name", "parent_id", "norm", "default_material_kind", "default_interval_months",
                    "default_lifetime_years", "position", "items_have_length")
KEINE_LAENGE = ("Für Artikel dieser Kategorie ist keine Länge vorgesehen – das Häkchen „Artikel haben eine Länge“ setzt "
                "die Material-Verwaltung an der Kategorie (es gilt auch für Unterkategorien).")


def kategorie(kid):
    k = db.query("SELECT * FROM mat_category WHERE id = ?", (kid,), one=True)
    if not k:
        raise Abgelehnt("Kategorie nicht gefunden.", 404)
    return k


def laenge_kategorien():
    """Die Kennungen aller Kategorien, deren Artikel eine Länge haben (Schritt 20): das Häkchen „Artikel haben eine
    Länge“ an der Kategorie selbst oder an einem Vorfahren. Eine Abfrage je Anfrage (g), denn Produktlisten fragen das
    für jedes Produkt."""
    speicher = g if has_request_context() else None
    if speicher is not None and "mat_laenge_kategorien" in speicher:
        return speicher.mat_laenge_kategorien
    alle = {k["id"]: k for k in db.query("SELECT id, parent_id, items_have_length FROM mat_category")}
    out = set()
    for kid in alle:
        x, gesehen = kid, set()
        while x in alle and x not in gesehen:
            gesehen.add(x)
            if alle[x]["items_have_length"]:
                out.add(kid)
                break
            x = alle[x]["parent_id"]
    if speicher is not None:
        speicher.mat_laenge_kategorien = out
    return out


def laenge_wirksam(category_id):
    """Haben die Artikel der Produkte dieser Kategorie eine Länge – durch das Häkchen an ihr oder einem Vorfahren?"""
    return category_id in laenge_kategorien()


def _laenge_vergessen():
    """Nach einer Änderung an Kategorien: den Zwischenspeicher der Anfrage leeren."""
    if has_request_context():
        g.pop("mat_laenge_kategorien", None)


def _unterkategorien(kid):
    return {r["id"] for r in db.query(
        "WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT c.id FROM mat_category c JOIN baum b ON c.parent_id = b.id) "
        "SELECT id FROM baum", (kid,))}


def kategorie_werte(d, alt=None):
    e = _mischen(alt, d, KATEGORIE_FELDER)
    w = {
        "name": text(e, "name", "Name", 120, pflicht=True),
        "parent_id": kennung(e.get("parent_id"), "Oberkategorie", leer_erlaubt=True),
        "norm": text(e, "norm", "Norm", 200),
        "default_material_kind": auswahl(e.get("default_material_kind"), MATERIALARTEN, "Materialart", leer_erlaubt=True),
        "default_interval_months": ganzzahl(e.get("default_interval_months"), "Prüfintervall (Monate)", 1, 120),
        "default_lifetime_years": ganzzahl(e.get("default_lifetime_years"), "Lebensdauer (Jahre)", 1, 50),
        "position": ganzzahl(e.get("position"), "Position", 0, 100000) or 0,
        # „Artikel haben eine Länge“ (Schritt 20) – wirkt auf den ganzen Teilbaum (laenge_wirksam).
        "items_have_length": int(wahr(e, "items_have_length", "Artikel haben eine Länge")),
    }
    if w["default_lifetime_years"] and w["default_material_kind"] != "textil":
        raise Abgelehnt("Eine Lebensdauer gibt es nur bei textilen Kategorien (Materialart „textil“).")
    if w["parent_id"]:
        kategorie(w["parent_id"])
        if alt and w["parent_id"] in _unterkategorien(alt["id"]):
            raise Abgelehnt("Eine Kategorie kann nicht unter sich selbst hängen.")
    gleich = db.query("SELECT id FROM mat_category WHERE COALESCE(parent_id, 0) = ? AND name = ? COLLATE NOCASE",
                      (w["parent_id"] or 0, w["name"]), one=True)
    if gleich and (not alt or gleich["id"] != alt["id"]):
        raise Abgelehnt(f"Die Kategorie „{w['name']}“ gibt es an dieser Stelle schon.", 409)
    return w


def kategorie_anlegen(d, demo=False):
    w = kategorie_werte(d)
    ts = db.now()
    with db.transaction():
        kid = db.execute(
            "INSERT INTO mat_category (parent_id, name, norm, default_material_kind, default_interval_months, "
            "default_lifetime_years, position, items_have_length, demo, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (w["parent_id"], w["name"], w["norm"], w["default_material_kind"], w["default_interval_months"],
             w["default_lifetime_years"], w["position"], w["items_have_length"], int(bool(demo)), ts, ts))
        journal.eintragen("category", kid, "angelegt", None, w)
    _laenge_vergessen()
    return kid


def ohne_intervall_meldung(namen):
    """Abgelehnt für Produkte, die nach einer Kategorieänderung kein Prüfintervall mehr hätten – auch für den Import,
    der diese Prüfung ans Ende seines Durchgangs legt (importer._intervalle_pruefen)."""
    return Abgelehnt("Danach hätten diese Produkte kein Prüfintervall mehr: " + ", ".join(namen[:5])
                     + (" …" if len(namen) > 5 else "") + ". Erst am Produkt ein Intervall eintragen.", 409)


def _ohne_intervall(kid, w):
    """Produkte im Teilbaum von kid, die mit den neuen Werten w der Kategorie kein Prüfintervall mehr hätten – ermittelt,
    bevor etwas geschrieben ist. Wie herstellerseite, nur gelten für kid schon Vorgabe und Oberkategorie aus w."""
    unterbaum = ("(WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT c.id FROM mat_category c JOIN baum b "
                 "ON c.parent_id = b.id) SELECT id FROM baum)")
    baum = {k["id"]: k for k in db.query(
        f"SELECT id, parent_id, default_interval_months FROM mat_category WHERE id IN {unterbaum}", (kid,))}
    # Oberhalb von kid erbt der ganze Teilbaum dasselbe: die Vorgabe der neuen Oberkategorie (oder ihrer Vorfahren).
    oben = herstellerseite({"category_id": w["parent_id"]})[0] if w["parent_id"] else None
    ohne = []
    for p in db.query(f"SELECT * FROM mat_product WHERE category_id IN {unterbaum}", (kid,)):
        if p["interval_months"]:
            continue
        monate, k, gesehen = None, baum.get(p["category_id"]), set()
        while k and k["id"] not in gesehen:
            gesehen.add(k["id"])
            if k["id"] == kid:
                monate = w["default_interval_months"] or oben
                break
            if k["default_interval_months"]:
                monate = k["default_interval_months"]
                break
            k = baum.get(k["parent_id"])
        if not monate:
            ohne.append(produktname(p))
    return ohne


def kategorie_aendern(kid, d, intervall_pruefen=True):
    """Eine Kategorie ändern. intervall_pruefen=False nur für den Katalogimport: Er übernimmt die Produkte erst nach
    den Kategorien und prüft „jedes Produkt hat ein Prüfintervall“ deshalb selbst am Ende seines Durchgangs – ein
    Produkt kann in derselben Datei ein eigenes Intervall bekommen, während seine Kategorie die Vorgabe verliert."""
    # Prüfen und Schreiben unter einer Schreibsperre: Zwei gleichzeitige Umhängungen ergäben sonst
    # einen Zyklus.
    with db.transaction(sofort=True):
        alt = kategorie(kid)
        w = kategorie_werte(d, alt)
        # Produkte ohne eigenes Intervall erben es aus der Kategorie. Fiele es durch die Änderung weg,
        # hätte ein Produkt keins mehr – das darf es so wenig wie beim Anlegen. Geprüft vor dem Schreiben:
        # In einer äußeren Transaktion (Import) bliebe sonst ein halber Stand stehen.
        if intervall_pruefen:
            ohne = _ohne_intervall(kid, w)
            if ohne:
                raise ohne_intervall_meldung(ohne)
        # Zuweisungen, die danach nicht mehr unter der Heimat ihres Prüfformulars lägen, werden gelöst (Entscheidung
        # Z6; der Dialog nennt sie vorher, verschieben_folgen) – sonst nähme der Trigger aus Schritt 38 die Änderung zurück.
        if w["parent_id"] != alt["parent_id"]:
            _verschieben_loesen(_eltern(kid, w["parent_id"]), {}, f"Kategorie „{w['name']}“ verschoben")
        db.execute("UPDATE mat_category SET parent_id = ?, name = ?, norm = ?, default_material_kind = ?, "
                   "default_interval_months = ?, default_lifetime_years = ?, position = ?, items_have_length = ?, "
                   "updated_at = ? WHERE id = ?",
                   (w["parent_id"], w["name"], w["norm"], w["default_material_kind"], w["default_interval_months"],
                    w["default_lifetime_years"], w["position"], w["items_have_length"], db.now(), kid))
        journal.aenderung("category", kid, alt, w)
        if (w["default_interval_months"], w["parent_id"]) != (alt["default_interval_months"], alt["parent_id"]):
            faelligkeit.kappen(*faelligkeit.in_kategorie(kid))
    _laenge_vergessen()
    return kid


DOKUMENT_IM_PROTOKOLL = "Ein Dokument dieser Kategorie steht in Prüfprotokollen und bleibt – damit auch die Kategorie."


def kategorie_loeschen(kid):
    dateien = []
    with db.transaction(sofort=True):              # prüfen und löschen unter einer Sperre
        alt = kategorie(kid)
        if db.query("SELECT 1 FROM mat_category WHERE parent_id = ? LIMIT 1", (kid,), one=True):
            raise Abgelehnt("Die Kategorie hat Unterkategorien – erst diese verschieben oder löschen.", 409)
        if db.query("SELECT 1 FROM mat_product WHERE category_id = ? LIMIT 1", (kid,), one=True):
            raise Abgelehnt("In der Kategorie stehen noch Produkte.", 409)
        if db.query("SELECT 1 FROM mat_inspection i JOIN mat_form f ON f.id = i.form_id JOIN mat_formular p "
                    "ON p.id = f.formular_id WHERE p.category_id = ? LIMIT 1", (kid,), one=True):
            raise Abgelehnt("Ein Prüfformular dieser Kategorie wurde schon für Prüfungen benutzt.", 409)
        # Eine Prüfung nennt die damals gültigen Dokumente mit Version und Prüfsumme (documents_json) – auch die einer
        # Kategorie, aus der das Produkt inzwischen fortgezogen ist. Prüfnachweise werden unbefristet aufbewahrt
        # (Entscheidung des Betreibers vom 18.10.2026), also bleibt ein solches Dokument samt Datei – und mit ihm die
        # Kategorie.
        if db.query("SELECT 1 FROM mat_product_document d WHERE d.category_id = ? AND EXISTS (SELECT 1 FROM mat_inspection "
                    "x, json_each(CASE WHEN json_valid(x.documents_json) THEN x.documents_json ELSE '[]' END) j "
                    "WHERE x.completed_at IS NOT NULL AND json_extract(j.value, '$.id') = d.id) LIMIT 1",
                    (kid,), one=True):
            raise Abgelehnt(DOKUMENT_IM_PROTOKOLL, 409)
        # Ein Standard hier aus dem Pool einer Oberkategorie geht mit der Kategorie (ON DELETE CASCADE), die Formulare
        # ihres Pools samt Versionen ebenso – je mit Journal (eine leere Kategorie hat keine Produkte, die sie bräuchten).
        for z in db.query("SELECT * FROM mat_formular_zuweisung WHERE category_id = ?", (kid,)):
            _zuweisung_loesen(z, f"Kategorie „{alt['name']}“ gelöscht")
        for pf in db.query("SELECT id FROM mat_formular WHERE category_id = ?", (kid,)):
            for f in db.query("SELECT id FROM mat_form WHERE formular_id = ?", (pf["id"],)):
                journal.eintragen("form", f["id"], "geloescht", {"kategorie": alt["name"]}, None)
            journal.eintragen("formular", pf["id"], "geloescht", {"titel": _anzeige_titel(pf["id"]),
                                                                  "heimat": alt["name"]}, None)
            db.execute("DELETE FROM mat_formular WHERE id = ?", (pf["id"],))
        # Dokumente der Kategorie gehen mit (eine leere Kategorie hat keine Produkte, die sie bräuchten);
        # ihr Journal bekommt das Ende vermerkt.
        for dok in db.query("SELECT id, title, file_path FROM mat_product_document WHERE category_id = ?", (kid,)):
            journal.eintragen("document", dok["id"], "geloescht", {"kategorie": alt["name"], "title": dok["title"]}, None)
            if dok["file_path"]:
                dateien.append(dok["file_path"])
        db.execute("DELETE FROM mat_product_document WHERE category_id = ?", (kid,))
        db.execute("DELETE FROM mat_category WHERE id = ?", (kid,))
        journal.eintragen("category", kid, "geloescht", alt, None)
    for name in dateien:
        _datei_freigeben(name)


def kategorien():
    """Alle Kategorien flach, mit Produktzahl, eigenem Standard-Prüfformular (Formular und aktive Version – geerbt wird
    in der Oberfläche über den Pfad, Entscheidung S1) und Zahl der Formulare im eigenen Pool – den Baum baut die
    Oberfläche."""
    standard = {r["category_id"]: {"formular_id": r["formular_id"], "version_id": r["id"], "version": r["version"],
                                   "titel": r["title"]} for r in db.query(
        "SELECT z.category_id, z.formular_id, f.id, f.version, f.title FROM mat_formular_zuweisung z "
        "JOIN mat_form f ON f.formular_id = z.formular_id AND f.active = 1 WHERE z.category_id IS NOT NULL")}
    rows = db.query(
        "SELECT c.*, (SELECT COUNT(*) FROM mat_product p WHERE p.category_id = c.id) AS produkte, "
        "(SELECT COUNT(*) FROM mat_formular f WHERE f.category_id = c.id) AS formulare "
        "FROM mat_category c ORDER BY c.position, c.name COLLATE NOCASE")
    return [kategorie_json(dict(r, standard_formular=standard.get(r["id"]))) for r in rows]


def kategorie_json(k):
    out = {f: k.get(f) for f in ("id", "parent_id", "name", "norm", "default_material_kind",
                                 "default_interval_months", "default_lifetime_years", "position")}
    out["demo"] = bool(k.get("demo"))
    # Das Häkchen selbst und ob es hier wirkt (auch von einer Oberkategorie geerbt).
    out["items_have_length"] = bool(k.get("items_have_length"))
    out["laenge_wirksam"] = laenge_wirksam(k["id"])
    for f in ("produkte", "standard_formular", "formulare"):
        if f in k:
            out[f] = k[f]
    return out


def kategorie_pfad(kid):
    pfad, gesehen = [], set()
    while kid and kid not in gesehen:
        gesehen.add(kid)
        k = db.query("SELECT id, parent_id, name FROM mat_category WHERE id = ?", (kid,), one=True)
        if not k:
            break
        pfad.insert(0, {"id": k["id"], "name": k["name"]})
        kid = k["parent_id"]
    return pfad


# --- DEMO-Regel des Katalogs (Sicherheitsprüfung vom 04.11.2026, Befund 4) ---------------------------------------------
# Wie im Katalog-Export: DEMO ist eine Kategorie mit Kennzeichen samt Teilbaum, ein Produkt mit Kennzeichen oder in einer
# solchen Kategorie, ein Formular mit Kennzeichen oder im Pool einer solchen Kategorie (SQL: models.DEMO_KATEGORIEN).
# Genutzt von Export und Übung der Einführung (einfuehrung._katalog_auswahl). kategorien: das Ergebnis von
# demo_kategorien(), wenn es schon da ist (mehrere Fragen nacheinander).

def demo_kategorien():
    """Die Kennungen aller Kategorien, die als DEMO zählen."""
    return {r["id"] for r in db.query(DEMO_KATEGORIEN)}


def produkt_ist_demo(p, kategorien=None):
    kategorien = demo_kategorien() if kategorien is None else kategorien
    return bool(p["demo"]) or p["category_id"] in kategorien


def formular_ist_demo(f, kategorien=None):
    """f: eine Version (mat_form) – DEMO mit eigenem Kennzeichen oder im Pool einer DEMO-Kategorie."""
    if f["demo"]:
        return True
    kategorien = demo_kategorien() if kategorien is None else kategorien
    heimat = db.query("SELECT category_id FROM mat_formular WHERE id = ?", (f["formular_id"],), one=True)
    return not heimat or heimat["category_id"] in kategorien


# --- Produkte ------------------------------------------------------------------------------------

PRODUKT_FELDER = ("category_id", "manufacturer", "model", "article_no", "norm", "material_kind",
                  "interval_months", "lifetime_years", "lifetime_source", "description")


def _einheitlich(s):
    """Für den Vergleich zählen nur Buchstaben und Ziffern: „Rescue-Harness 2“, „rescue harness 2“
    und „RescueHarness2“ sind dasselbe Modell, „123-45“ und „12345“ dieselbe Artikelnummer."""
    return re.sub(r"[\W_]+", "", (s or "").casefold())


def artikelnummer(s):
    """Eine Artikelnummer, die nur aus Strichen und Punkten besteht („-“, „.“, „/“), ist keine – so
    tippen Leute „unbekannt“. Sie wird leer gespeichert und zählt für die Dublettenprüfung als leer."""
    s = (s or "").strip()
    return s if re.search(r"\w", s) else ""


def dedupe_key(hersteller, modell, artikel_nr):
    return f"{_einheitlich(hersteller)}|{_einheitlich(modell)}|{_einheitlich(artikelnummer(artikel_nr))}"


def produkt(pid):
    p = db.query("SELECT * FROM mat_product WHERE id = ?", (pid,), one=True)
    if not p:
        raise Abgelehnt("Produkt nicht gefunden.", 404)
    return p


def beschreibung(d):
    """Die Beschreibung aus einer Eingabe über die Oberfläche (Anlegen, Bearbeiten, Variante, Produkt aus einer
    Meldung): eine Zeile, höchstens BESCHREIBUNG_MAX Zeichen. Länger ist ein Fehler mit Klartext, nie eine stille
    Kürzung – auch für eine ältere Beschreibung, die unverändert zurückkommt (der Dialog sagt das vorher)."""
    v = text(d, "description", "Bemerkung", 1 << 30)       # die Länge prüft die Meldung hier, mit dem Grund
    if len(v) > BESCHREIBUNG_MAX:
        raise Abgelehnt(f"Die Bemerkung ist ein kurzer Zusatz hinter dem Namen, etwa die Verschlussart – höchstens "
                        f"{BESCHREIBUNG_MAX} Zeichen, hier sind es {len(v)}. Bitte kürzen; Ausführliches gehört in ein "
                        "Dokument am Produkt.")
    return v


def modell_teile(modell):
    """Der Modellname, zerlegt an „|“ – dieselbe Regel wie modellTeile in material.js: vorn der Name, dahinter ein
    Zusatz von Hand („D Classic | Screwlock“ → „D Classic“, [„Screwlock“]); leere Teile fallen weg. Nur für die
    Anzeige – im Katalog bleibt der Modellname, wie er gepflegt ist."""
    teile = [" ".join(t.split()) for t in (modell or "").split("|")]
    extra = [t for t in teile[1:] if t]
    name = teile[0] or (extra.pop(0) if extra else "")
    return name, extra


def zusatz(modell, beschr):
    """Der Zusatz hinter dem Namen, wie ihn die Anzeige zeigt – dieselbe Regel wie produktZusatz in material.js: ein
    Zusatz von Hand im Modellnamen (der Teil hinter „|“) und die Beschreibung in einer Zeile, zwei verschiedene mit
    Komma („Screwlock, Aluminium“); dieselbe Angabe in beiden nur einmal („D Classic | Screwlock“ mit der Beschreibung
    „Screwlock“). Leer, wenn es keins von beiden gibt. Eine ältere, längere Beschreibung endet nach BESCHREIBUNG_MAX
    Zeichen (am Wortende, wenn eins in der zweiten Hälfte liegt) mit „…“."""
    _, extra = modell_teile(modell)
    z = " ".join((beschr or "").split())
    if z.casefold() in [t.casefold() for t in extra]:
        z = ""
    if len(z) > BESCHREIBUNG_MAX:
        z = z[:BESCHREIBUNG_MAX - 1]
        if " " in z[BESCHREIBUNG_MAX // 2:]:
            z = z[:z.rindex(" ")]
        z = z.rstrip(" ,;:–-") + "…"
    return ", ".join(t for t in [*extra, z] if t)


def produkt_teile(p, beschr=None):
    """(Name, Zusatz) eines Produkts: „Hersteller Modell“ – vom Modell der Teil vor einem „|“ – und der Zusatz
    dahinter (zusatz()), getrennt für Ausgaben, die ihn grau setzen (PDF). p: Zeile mit manufacturer, model und
    description; beschr statt p["description"], wo die Abfrage sie unter anderem Namen liefert (product_description
    in den Artikellisten)."""
    name, _ = modell_teile(p.get("model"))
    return (f"{p.get('manufacturer') or ''} {name}".strip(),
            zusatz(p.get("model"), p.get("description") if beschr is None else beschr))


def produktname(p, beschr=None):
    """Der Name eines Produkts als Text in Protokollen, Exporten, Mails, Rückfragen und Meldungen: „Hersteller Modell
    Beschreibung“ – Name und Zusatz durch ein Leerzeichen getrennt, ohne Strich (Wunsch vom 18.10.2026: „Entferne den
    |“), wie die Oberfläche sie zeigt, nur ohne das Grau. Argumente wie produkt_teile."""
    return " ".join(t for t in produkt_teile(p, beschr) if t)


def produkt_werte(d, alt=None, importiert=False):
    """Die Stammdaten aus d (bei einer Änderung über alt ergänzt) nach den Regeln des Katalogs. importiert: aus dem
    Katalogimport – die Beschreibung kommt wie bisher herein (mehrzeilig, bis 4000 Zeichen), siehe BESCHREIBUNG_MAX.
    Sonst gilt beschreibung() für jede Beschreibung, die d mitschickt; eine ältere, die d nicht nennt, bleibt stehen."""
    e = _mischen(alt, d, PRODUKT_FELDER)
    w = {
        "category_id": kennung(e.get("category_id"), "Kategorie"),
        "manufacturer": text(e, "manufacturer", "Hersteller", 120, pflicht=True),
        "model": text(e, "model", "Modell", 160, pflicht=True),
        "article_no": artikelnummer(text(e, "article_no", "Artikelnummer", 80)),
        "norm": text(e, "norm", "Norm", 200),
        "material_kind": auswahl(e.get("material_kind"), MATERIALARTEN, "Materialart"),
        "interval_months": ganzzahl(e.get("interval_months"), "Prüfintervall (Monate)", 1, 120),
        "lifetime_years": ganzzahl(e.get("lifetime_years"), "Lebensdauer (Jahre)", 1, 50),
        "lifetime_source": text(e, "lifetime_source", "Fundstelle der Lebensdauer", 300),
        "description": text(e, "description", "Bemerkung", 4000, einzeilig=False),
    }
    if not importiert and "description" in d:
        w["description"] = beschreibung(d)
    kategorie(w["category_id"])
    if w["material_kind"] == "textil" and not w["lifetime_years"]:
        raise Abgelehnt(LEBENSDAUER_TEXTIL)
    if w["material_kind"] == "metall_hardware" and w["lifetime_years"]:
        raise Abgelehnt(LEBENSDAUER_METALL)
    if w["material_kind"] == "sonstiges" and w["lifetime_years"] and not w["lifetime_source"]:
        raise Abgelehnt(LEBENSDAUER_SONSTIGES)
    if herstellerseite(w)[0] is None:
        raise Abgelehnt(KEIN_INTERVALL)
    return w


def _dublette_pruefen(key, ausser=None):
    andere = db.query("SELECT id, manufacturer, model, description, article_no FROM mat_product WHERE dedupe_key = ?",
                      (key,), one=True)
    if andere and andere["id"] != ausser:
        nr = f" ({andere['article_no']})" if andere["article_no"] else ""
        raise Abgelehnt(f"Dieses Produkt steht schon im Katalog: {produktname(andere)}{nr}.", 409)


def _nummer_muster(article_no):
    """Das LIKE-Muster hinter dem letzten „|“ des dedupe_key: genau die vereinheitlichte Artikelnummer. Hersteller und
    Modell enthalten vereinheitlicht weder „|“ noch die Platzhalter von LIKE („%“, „_“) – _einheitlich lässt nur
    Buchstaben und Ziffern stehen. Leer: None (keine Nummer zählt nicht)."""
    nr = _einheitlich(artikelnummer(article_no))
    return "|" + nr if nr else None


def artikelnummer_vergeben(article_no, hersteller, ausser=None):
    """Das Produkt DIESES Herstellers (Schreibweise egal, wie in der Dublette), das die Artikelnummer schon trägt –
    leer zählt nicht. Seit dem 22.10.2026 nur je Hersteller: Dieselbe Nummer bei einem anderen Hersteller ist kein
    Treffer (produkte_mit_artikelnummer findet sie)."""
    muster = _nummer_muster(article_no)
    if not muster:
        return None
    return db.query("SELECT id, manufacturer, model, description, article_no FROM mat_product WHERE dedupe_key LIKE ? "
                    "AND id <> ? ORDER BY id LIMIT 1", (_einheitlich(hersteller) + "|%" + muster, ausser or 0), one=True)


def produkte_mit_artikelnummer(article_no):
    """Alle Produkte mit dieser Artikelnummer, gleich bei welchem Hersteller (nach Kennung) – für Aufrufer, die ein
    Produkt nur über die Nummer suchen (Bestandsimport, Meldung) und selbst entscheiden, ob der Hersteller passt."""
    muster = _nummer_muster(article_no)
    if not muster:
        return []
    return db.query("SELECT * FROM mat_product WHERE dedupe_key LIKE ? ORDER BY id", ("%" + muster,))


def _artikelnummer_pruefen(article_no, hersteller, ausser=None):
    da = artikelnummer_vergeben(article_no, hersteller, ausser)
    if da:
        raise Abgelehnt(f"Die Artikelnummer „{article_no}“ ist bei {da['manufacturer']} schon vergeben: {produktname(da)} "
                        f"({da['article_no']}).", 409)


def produkt_anlegen(d, demo=False, importiert=False, bestandteile=None):
    """Ein neues Produkt – mit bestandteile (rohe Liste, stueckliste.eintraege_lesen) samt seiner Bestandteil-Liste (nur
    Text, Schritt 25) in EINER Transaktion: Scheitert eine Position („Position n: …“), entsteht kein Produkt. „is_set“
    aus d (Set-Funktion bis Schritt 26) liest der Dienst nicht. Der Katalogimport legt Produkte ohne bestandteile an und
    ersetzt die Liste danach (stueckliste.ersetzen)."""
    from . import stueckliste
    w = produkt_werte(d, importiert=importiert)
    key = dedupe_key(w["manufacturer"], w["model"], w["article_no"])
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        _dublette_pruefen(key)
        _artikelnummer_pruefen(w["article_no"], w["manufacturer"])
        try:
            pid = db.execute(
                "INSERT INTO mat_product (category_id, manufacturer, model, article_no, dedupe_key, norm, material_kind, "
                "interval_months, lifetime_years, lifetime_source, description, demo, created_by, created_at, "
                "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w["category_id"], w["manufacturer"], w["model"], w["article_no"], key, w["norm"], w["material_kind"],
                 w["interval_months"], w["lifetime_years"], w["lifetime_source"], w["description"],
                 int(bool(demo)), uid, ts, ts))
        except sqlite3.IntegrityError:
            raise Abgelehnt("Dieses Produkt steht schon im Katalog.", 409)
        journal.eintragen("product", pid, "angelegt", None, w)
        if bestandteile:
            stueckliste._ersetzen(produkt(pid), stueckliste.eintraege_lesen(bestandteile))
    return pid


def produkt_variante(pid, d):
    """Kopie eines Produkts als neue Variante. Die Stammdaten kommen aus d (der Dialog schickt sie vorbelegt mit),
    eine eigene Artikelnummer ist Pflicht. Auf Wunsch die aktuellen Dokumente des Produkts dazu – je Dokument die
    neueste, nicht zurückgezogene Version; die neue Zeile nennt dieselbe Datei (seit Schritt 18 heißt sie nach ihrem
    Inhalt und bleibt, bis keine Zeile sie mehr nennt – bis dahin wurde sie kopiert, damit das Löschen des einen
    Produkts die Dokumente des anderen nicht mitnimmt). Das Produktbild nie, eine Formularzuweisung auch nicht. Die
    Bestandteil-Liste: „bestandteile“ (die im Dialog bearbeitete Liste, nur Text; [] ohne Liste) oder ohne sie die Liste
    des Vorbilds (Schritt 25)."""
    from . import stueckliste
    quelle = produkt(pid)
    if not artikelnummer(text(d, "article_no", "Artikelnummer", 80)):
        raise Abgelehnt("Eine Variante braucht eine eigene Artikelnummer.")
    liste = d.get("bestandteile")
    if liste is not None and not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    wahl = d.get("dokumente") or []
    if not isinstance(wahl, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in wahl):
        raise Abgelehnt("„dokumente“ muss eine Liste von Dokumentkennungen sein.")
    aktuelle = {r["id"]: r for r in db.query(
        "SELECT * FROM mat_product_document d WHERE product_id = ? AND (withdrawn_on IS NULL OR withdrawn_on > ?) "
        "AND NOT EXISTS (SELECT 1 FROM mat_product_document n WHERE n.replaces_id = d.id)", (pid, heute().isoformat()))}
    if any(x not in aktuelle for x in wahl):
        raise Abgelehnt("Übernehmen lassen sich nur die aktuellen Dokumente dieses Produkts.")
    kopien = [aktuelle[x] for x in dict.fromkeys(wahl)]
    uid, uname = akteur()
    with db.transaction(sofort=True):
        if liste is None:
            # Die Bestandteil-Liste des Vorbilds (Schritt 25) – nur Text.
            liste = [{"bezeichnung": r["bezeichnung"], "anzahl": r["anzahl"]} for r in stueckliste.kurzliste(pid)]
            kopiert = bool(liste)
        else:
            kopiert = False
        neu = produkt_anlegen(d, demo=bool(quelle["demo"]), bestandteile=liste)
        for doc in kopien:
            _datei_sichern(doc["file_path"], doc["title"])      # unter der Sperre: seit dem Lesen oben nicht freigegeben
            did = db.execute(
                "INSERT INTO mat_product_document (product_id, kind, title, file_path, url, mime, size, sha256, version, "
                "valid_from, uploaded_by, uploaded_by_name, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (neu, doc["kind"], doc["title"], doc["file_path"], doc["url"], doc["mime"], doc["size"], doc["sha256"],
                 doc["version"], doc["valid_from"], uid, uname, db.now()))
            journal.eintragen("document", did, "angelegt", None,
                              {"product_id": neu, "kind": doc["kind"], "title": doc["title"], "version": doc["version"],
                               "valid_from": doc["valid_from"], "kopie_von": doc["id"]})
        # Der Name der Quelle mit ihrem Zusatz: Varianten unterscheiden sich oft nur in der Beschreibung.
        journal.eintragen("product", neu, "variante", None, dict({"von": pid, "name": produktname(quelle),
                                                                  "dokumente": len(kopien)},
                                                                 **({"bestandteile": True} if kopiert else {})))
    return neu


def produkt_aendern(pid, d, importiert=False):
    """Stammdaten ändern. „is_set“ (Set-Funktion bis Schritt 26) wird übergangen."""
    alt = produkt(pid)
    w = produkt_werte(d, alt, importiert=importiert)
    key = dedupe_key(w["manufacturer"], w["model"], w["article_no"])
    artikel = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ?", (pid,), one=True)["n"]
    if artikel and w["material_kind"] != alt["material_kind"]:
        raise Abgelehnt("Die Materialart lässt sich nur ändern, solange es keine Artikel dieses Produkts gibt – "
                        "an ihr hängen Lebensdauer und Aussonderung.", 409)
    with db.transaction(sofort=True):
        _dublette_pruefen(key, ausser=pid)
        # Geprüft, wenn sich die Nummer oder der Hersteller ändert: Eine Dopplung aus der Zeit vor dieser Regel soll
        # nicht jede andere Änderung am Produkt blockieren.
        if (_einheitlich(w["article_no"]), _einheitlich(w["manufacturer"])) != \
                (_einheitlich(artikelnummer(alt["article_no"])), _einheitlich(alt["manufacturer"])):
            _artikelnummer_pruefen(w["article_no"], w["manufacturer"], ausser=pid)
        # Eine Zuweisung, die in der neuen Kategorie nicht mehr unter der Heimat ihres Prüfformulars läge, wird gelöst
        # (Entscheidung Z6; der Dialog nennt sie vorher, verschieben_folgen).
        if w["category_id"] != alt["category_id"]:
            _verschieben_loesen(_eltern(), {pid: w["category_id"]}, "Produkt in eine andere Kategorie verschoben")
        db.execute("UPDATE mat_product SET category_id = ?, manufacturer = ?, model = ?, article_no = ?, dedupe_key = ?, "
                   "norm = ?, material_kind = ?, interval_months = ?, lifetime_years = ?, lifetime_source = ?, "
                   "description = ?, updated_at = ? WHERE id = ?",
                   (w["category_id"], w["manufacturer"], w["model"], w["article_no"], key, w["norm"], w["material_kind"],
                    w["interval_months"], w["lifetime_years"], w["lifetime_source"], w["description"], db.now(), pid))
        journal.aenderung("product", pid, alt, w)
        if (w["interval_months"], w["category_id"]) != (alt["interval_months"], alt["category_id"]):
            faelligkeit.kappen("i.product_id = ?", (pid,))
        # Ein festgeschriebenes Lebensende (retire_by) gibt es nur bei textilem Material.
        if w["lifetime_years"] != alt["lifetime_years"] and w["material_kind"] == "textil":
            lebensende_nachziehen(pid, alt["lifetime_years"], w["lifetime_years"])
    return pid


def lebensende_nachziehen(pid, alt_jahre, neu_jahre):
    """Ändert sich die Lebensdauer eines textilen Produkts (etwa eine korrigierte Herstellerangabe),
    ziehen die Artikel mit. Ein am Artikel vorgezogenes Datum (retire_by_manual) gilt weiter, solange es
    früher liegt – vorgezogen bleibt vorgezogen, auch nach einer Korrektur hin und zurück. Ausgesonderte
    Artikel bleiben, wie sie sind. Jede Änderung steht im Journal des Artikels."""
    for i in db.query("SELECT id, manufactured_on, retire_by, retire_by_manual FROM mat_item "
                      "WHERE product_id = ? AND lock_state <> 'ausgesondert'", (pid,)):
        rechnung = lebensende(i["manufactured_on"], neu_jahre)
        neu = min(rechnung, i["retire_by_manual"]) if rechnung and i["retire_by_manual"] else rechnung
        if neu != i["retire_by"]:
            db.execute("UPDATE mat_item SET retire_by = ?, updated_at = ? WHERE id = ?", (neu, db.now(), i["id"]))
            journal.eintragen("item", i["id"], "lebensende", {"retire_by": i["retire_by"]}, {"retire_by": neu})


def produkt_loeschen(pid):
    """Nur ein Produkt ohne Artikel; seine Bestandteil-Liste geht mit (ON DELETE CASCADE, im Journal „geloescht“ als Zahl
    der Bestandteile), eine Formularzuweisung ebenso (Journal am Formular). Prüfformulare hängen seit Schritt 38 nicht
    mehr am Produkt – sie bleiben im Pool."""
    with db.transaction(sofort=True):
        alt = produkt(pid)
        if db.query("SELECT 1 FROM mat_item WHERE product_id = ? LIMIT 1", (pid,), one=True):
            raise Abgelehnt("Von diesem Produkt gibt es Artikel – es bleibt im Katalog.", 409)
        bestandteile = db.query("SELECT COUNT(*) AS n FROM mat_product_component WHERE set_product_id = ?", (pid,),
                                one=True)["n"]
        if bestandteile:
            alt = dict(alt, bestandteile=bestandteile)
        dateien = [r["file_path"] for r in db.query(
            "SELECT file_path FROM mat_product_document WHERE product_id = ? AND file_path IS NOT NULL", (pid,))]
        for z in db.query("SELECT * FROM mat_formular_zuweisung WHERE product_id = ?", (pid,)):
            _zuweisung_loesen(z, "Produkt gelöscht")
        # Die Dokumente gehen mit dem Produkt (ON DELETE CASCADE) – ihr Journal bekommt das Ende vermerkt,
        # damit eine später wieder vergebene Kennung nicht ihre Geschichte erbt (journal.LOESCHUNG).
        for dok in db.query("SELECT id, title FROM mat_product_document WHERE product_id = ?", (pid,)):
            journal.eintragen("document", dok["id"], "geloescht", {"produkt": pid, "title": dok["title"]}, None)
        db.execute("DELETE FROM mat_product WHERE id = ?", (pid,))
        journal.eintragen("product", pid, "geloescht", alt, None)
    for name in dateien:
        _datei_freigeben(name)
    if alt["image"]:
        delete_photo_files(medien_dir(), alt["image"])


def _entfernen(pfad):
    """Nur für Zwischendateien und über _datei_freigeben – eine Dokumentdatei nie direkt."""
    try:
        os.remove(pfad)
    except OSError:
        pass


def bild_url(datei, art="web"):
    if not datei:
        return None
    key = os.path.splitext(datei)[0]
    return f"/media/material/{art}/{key + '.jpg' if art != 'orig' else datei}"


def foto_ablegen(file_storage, vorschau_ganz=False):
    """Ein Foto durch die vorhandene Pipeline (EXIF-Drehung, HEIC, Web- und Vorschaufassung).
    vorschau_ganz für Produktbilder: Der quadratische Ausschnitt aus der Mitte schnitte einem
    hochkant fotografierten Produkt oben und unten ein Stück ab."""
    if not file_storage or not file_storage.filename:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise Abgelehnt(f"Dateityp {ext or '(ohne Endung)'} ist kein Foto (JPEG, PNG, WebP, HEIC, TIFF).")
    try:
        return store_upload(file_storage, medien_dir(), vorschau_ganz=vorschau_ganz)["file"]
    except ValueError as exc:                # BildFehler und die Meldungen von store_upload sind für Nutzer
        raise Abgelehnt(str(exc))


def produkt_bild_setzen(pid, file_storage):
    alt = produkt(pid)
    neu = foto_ablegen(file_storage, vorschau_ganz=True)
    with db.transaction():
        if not db.execute_zeilen("UPDATE mat_product SET image = ?, updated_at = ? WHERE id = ? AND image = ?",
                                 (neu, db.now(), pid, alt["image"])):
            delete_photo_files(medien_dir(), neu)
            raise Abgelehnt("Das Produktbild wurde zwischenzeitlich anderswo geändert. Bitte neu laden.", 409)
        journal.eintragen("product", pid, "bild", {"image": alt["image"]}, {"image": neu})
    if alt["image"]:
        delete_photo_files(medien_dir(), alt["image"])


def produkt_bild_entfernen(pid):
    alt = produkt(pid)
    if not alt["image"]:
        return
    with db.transaction():
        if db.execute_zeilen("UPDATE mat_product SET image = '', updated_at = ? WHERE id = ? AND image = ?",
                             (db.now(), pid, alt["image"])):
            journal.eintragen("product", pid, "bild", {"image": alt["image"]}, {"image": ""})
        else:
            return
    delete_photo_files(medien_dir(), alt["image"])


def produkt_json(p, voll=False):
    out = {f: p.get(f) for f in ("id", "category_id", "manufacturer", "model", "article_no", "norm", "material_kind",
                                 "interval_months", "lifetime_years", "lifetime_source", "description",
                                 "created_at", "updated_at")}
    out["demo"] = bool(p.get("demo"))
    out["bild"] = bild_url(p.get("image"))
    out["vorschau"] = bild_url(p.get("image"), "thumb")
    out["original"] = bild_url(p.get("image"), "orig")
    hm, hq = herstellerseite(p)
    out["intervall"] = {"monate": hm, "quelle": hq}
    # Haben Artikel dieses Produkts eine Länge (Häkchen an der Kategorie oder einem Vorfahren)? Für die Artikeldialoge.
    out["laenge_moeglich"] = laenge_wirksam(p["category_id"])
    if "category_name" in p:
        out["category_name"] = p["category_name"]
    if "bestand" in p:
        out["bestand"] = p["bestand"]
    # Bestandteil-Liste (Schritt 25), nur voll.
    from .stueckliste import produkt_json_ergaenzen
    produkt_json_ergaenzen(out, p, voll)
    if voll:
        # Der Katalog ist global, der Bestand nicht: Die Zahlen zählen nur, was das Konto sieht. Ob sich das Produkt
        # löschen lässt, hängt dagegen an allen Artikeln – „loeschbar“ verrät nur ja oder nein (produkt_loeschen).
        from .rechte import artikel_filter
        out["kategorie_pfad"] = kategorie_pfad(p["category_id"])
        out["bestand"] = db.query(f"SELECT COUNT(*) AS n FROM mat_item i WHERE i.product_id = ? AND i.lock_state <> "
                                  f"'ausgesondert' AND {artikel_filter('i')}", (p["id"],), one=True)["n"]
        out["artikel_gesamt"] = db.query(f"SELECT COUNT(*) AS n FROM mat_item i WHERE i.product_id = ? "
                                         f"AND {artikel_filter('i')}", (p["id"],), one=True)["n"]
        out["loeschbar"] = not db.query("SELECT 1 FROM mat_item WHERE product_id = ? LIMIT 1", (p["id"],), one=True)
        out["dokumente"] = dokumente(p["id"])
        out["kategorie_dokumente"] = geerbte_dokumente(p["id"])
        # Das geltende Prüfformular – nur zur Anzeige; welches gilt, legt die Material-Verwaltung unter „Prüfformulare“
        # fest (Schritt 38).
        f = formular_fuer_produkt(p["id"])
        out["formular"] = ({"id": f["id"], "version": f["version"], "title": f["title"], "quelle": f["quelle"],
                            "art": f["art"], "punkte": f["punkte_anzahl"], "formular": f["formular"],
                            "standard_von": f["standard_von"]} if f else None)
    return out


# --- Produktdokumente ---------------------------------------------------------------------------------

def dokument(did):
    doc = db.query("SELECT * FROM mat_product_document WHERE id = ?", (did,), one=True)
    if not doc:
        raise Abgelehnt("Dokument nicht gefunden.", 404)
    return doc


def inhaltsname(sha, ext):
    """Der Dateiname eines Dokuments seit Schritt 18: die SHA-256 seines Inhalts mit der Endung – derselbe Inhalt heißt
    immer gleich und liegt deshalb nur einmal unter media/material/dok, egal wie viele Dokumente (Produkte, Varianten,
    Kategorien) ihn nennen. Vor Schritt 18 trug jede Datei einen Zufallsnamen; dokablage.zusammenfuehren bringt den
    Altbestand einmal auf die neuen Namen."""
    return sha + ext


def _datei_schreiben(file_storage):
    """Datei unverändert in eine Zwischendatei unter media/material/dok schreiben (Name mit Punkt davor – die Medienroute
    liefert so etwas nie aus), dabei zählen und hashen; liefert (Zwischendatei, Inhaltsname, MIME, Größe, SHA-256).
    Ihren Inhaltsnamen (inhaltsname) bekommt die Datei erst mit _einordnen – beim Hochladen unter der Schreibsperre, in
    derselben Transaktion wie die Zeile (dokument_anlegen): So kann kein _datei_freigeben eines anderen Arbeitsprozesses
    zwischen Datei und Zeile treffen (Befund 1 der Prüfung vom 22.10.2026)."""
    if not file_storage or not file_storage.filename:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in DOK_TYPEN:
        raise Abgelehnt("Herstellerdokumente bitte als PDF oder Bild (JPEG, PNG, WebP) hochladen.")
    mime, kennungen = DOK_TYPEN[ext]
    stream = file_storage.stream
    kopf = stream.read(16)
    if not any(kopf.startswith(k) for k in kennungen) or (ext == ".webp" and kopf[8:12] != b"WEBP"):
        raise Abgelehnt(f"Der Inhalt von „{file_storage.filename}“ passt nicht zur Endung {ext}.")
    zwischen = os.path.join(dok_dir(), ".neu-" + secrets.token_hex(10) + ext)
    summe, groesse = hashlib.sha256(), 0
    try:
        with open(zwischen, "wb") as fh:
            stueck = kopf
            while stueck:
                groesse += len(stueck)
                if groesse > DOK_MAX_BYTES:
                    raise Abgelehnt(f"Das Dokument ist größer als {DOK_MAX_BYTES // (1024 * 1024)} MB.", 413)
                summe.update(stueck)
                fh.write(stueck)
                stueck = stream.read(1024 * 1024)
    except Abgelehnt:
        _entfernen(zwischen)
        raise
    except OSError as exc:
        _entfernen(zwischen)
        current_app.logger.warning("Dokument „%s“ ließ sich nicht ablegen: %s", file_storage.filename, exc)
        raise Abgelehnt("Das Dokument ließ sich nicht speichern. Bitte später erneut versuchen.", 500)
    return zwischen, inhaltsname(summe.hexdigest(), ext), mime, groesse, summe.hexdigest()


def _datei_ablegen(file_storage):
    """Schreiben und gleich einordnen; liefert (Name, MIME, Größe, SHA-256). Für den Katalogimport, der seine Dateien
    vor der Transaktion ablegt (minutenlang bei einer großen Lieferung) und beim Schreiben jeder Zeile unter der
    Schreibsperre prüft, ob die Datei noch liegt – sonst legt er sie aus dem Archiv nach (importer._Lauf.ablegen)."""
    zwischen, name, mime, groesse, sha = _datei_schreiben(file_storage)
    _einordnen(zwischen, os.path.join(dok_dir(), name), groesse)
    return name, mime, groesse, sha


def _einordnen(zwischen, ziel, groesse):
    """Die fertig geschriebene Zwischendatei unter ihren Inhaltsnamen bringen. Gibt es den schon in derselben Größe,
    ist es derselbe Inhalt (gleiche SHA-256) – die Zwischendatei geht weg. Eine andere Größe hieße, die vorhandene
    Datei ist beschädigt (etwa abgebrochen kopiert); dann ersetzt die eben geprüfte sie – mit Vermerk im Log.
    Scheitert das Dateisystem, geht die Zwischendatei weg und der Aufrufer bekommt Abgelehnt (500)."""
    try:
        vorhanden = os.path.getsize(ziel)
    except OSError:
        vorhanden = None
    try:
        if vorhanden == groesse:
            _entfernen(zwischen)
            return
        if vorhanden is not None:
            current_app.logger.warning("Dokumentdatei %s hatte %d statt %d Bytes – durch die neue Fassung ersetzt.",
                                       os.path.basename(ziel), vorhanden, groesse)
        os.replace(zwischen, ziel)
    except OSError as exc:
        _entfernen(zwischen)
        current_app.logger.warning("Dokumentdatei %s ließ sich nicht ablegen: %s", os.path.basename(ziel), exc)
        raise Abgelehnt("Das Dokument ließ sich nicht speichern. Bitte später erneut versuchen.", 500)


def _datei_sichern(name, titel):
    """Vor dem Einfügen einer Zeile, die eine schon liegende Datei nennt (produkt_variante), unter der Schreibsperre
    prüfen, dass die Datei da ist – sonst Abgelehnt (409). Zwischen dem Nachsehen außerhalb der Sperre und der eigenen
    Transaktion kann ein anderer das letzte Dokument mit diesem Inhalt gelöscht und die Datei freigegeben haben; eine
    Zeile ohne Datei soll daraus nie entstehen. Der Katalogimport prüft dasselbe in importer._Lauf.ablegen und legt die
    Datei aus dem Archiv nach, statt abzubrechen."""
    if name and not os.path.isfile(os.path.join(dok_dir(), name)):
        raise Abgelehnt(f"Die Datei des Dokuments „{titel}“ liegt nicht mehr unter media/material/dok – das Dokument "
                        "wurde inzwischen gelöscht oder seine Datei fehlt. Bitte die Seite neu laden.", 409)


def _datei_freigeben(name):
    """Eine Dokumentdatei nach dem Ende ihrer Zeile entfernen – aber nur, wenn kein Dokument sie mehr nennt. Seit
    Schritt 18 heißt eine Datei nach ihrem Inhalt und gehört allen Dokumenten mit diesem Inhalt zugleich (Varianten,
    Katalogimport mit einer Anleitung für viele Produkte). Aufgerufen nach dem Commit, der die eigene Zeile entfernt
    hat, bzw. nach dem Rollback, der sie nie entstehen ließ – nie innerhalb einer Transaktion, denn das Entfernen
    ließe sich nicht zurückrollen. Die Regel, dass ein Dokument aus einem festgeschriebenen Prüfprotokoll seine Zeile
    nie verliert (kategorie_loeschen; produkt_loeschen scheitert an den Artikeln), hält damit auch seine Datei: Solange
    die Zeile steht, wird die Datei nicht angerührt. Jede Stelle, die Dokumentdateien entfernt, geht hier durch – kein
    os.remove sonst.

    Abfrage und Entfernen stehen unter der Schreibsperre (BEGIN IMMEDIATE), und wer eine Zeile mit dieser Datei anlegt,
    tut das in seiner eigenen Transaktion unter derselben Sperre – dokument_anlegen ordnet die Datei dort erst ein,
    produkt_variante (_datei_sichern) und der Katalogimport (_Lauf.ablegen) prüfen dort, dass sie liegt. So gibt es
    nur zwei Ausgänge:
    Die Zeile steht schon und die Datei bleibt, oder die Datei ist weg und der andere legt sie nach bzw. bricht ab
    (Befund 1 der Prüfung vom 22.10.2026; vorher lag zwischen „liegt schon“ und der Zeile ein Fenster, beim Import
    minutenlang)."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return
    with db.transaction(sofort=True):
        if db.query("SELECT 1 FROM mat_product_document WHERE file_path = ? LIMIT 1", (name,), one=True):
            return
        _entfernen(os.path.join(dok_dir(), name))


def _dokument_werte(d, alt=None, datei=None):
    w = {
        "kind": auswahl(d.get("kind") or (alt or {}).get("kind"), DOKUMENTARTEN, "Dokumentart"),
        "title": text(d, "title", "Titel", 200) or (alt or {}).get("title") or "",
        "version": text(d, "version", "Versionsstand", 40),
        "valid_from": datum(d.get("valid_from"), "Gültig ab") or heute().isoformat(),
        "url": None,
    }
    if not datei:
        url = text(d, "url", "Adresse", 500)
        if not re.match(r"^https?://[^\s/]+", url or ""):
            raise Abgelehnt("Bitte eine Datei hochladen oder eine Adresse (https://…) angeben.")
        w["url"] = url
    if not w["title"]:
        w["title"] = (os.path.splitext(datei.filename)[0] if datei else w["url"])[:200]
    if alt and w["valid_from"] < alt["valid_from"]:
        raise Abgelehnt("Eine neue Version kann nicht vor der alten gültig werden.")
    return w


def dokument_anlegen(pid, d, datei=None, ersetzt=None, kid=None):
    """Ein Dokument am Produkt pid – oder an der Kategorie kid, dann gilt es für alle Produkte darin und in
    ihren Unterkategorien. Mit ersetzt: die neue Version eines vorhandenen (am selben Ziel)."""
    if ersetzt:
        pid, kid = ersetzt["product_id"], ersetzt["category_id"]
    if kid:
        kategorie(kid)
        pid = None
    else:
        produkt(pid)
    w = _dokument_werte(d, ersetzt, datei)
    zwischen = name = mime = sha = None
    groesse = 0
    if datei:
        # Geschrieben und gehasht außerhalb der Sperre (dauert bei 50 MB), eingeordnet erst unten in der Transaktion.
        zwischen, name, mime, groesse, sha = _datei_schreiben(datei)
    uid, uname = akteur()
    try:
        with db.transaction(sofort=True):
            if ersetzt and db.query("SELECT 1 FROM mat_product_document WHERE replaces_id = ? LIMIT 1",
                                    (ersetzt["id"],), one=True):
                raise Abgelehnt("Zu diesem Dokument gibt es schon eine neuere Version – bitte diese ersetzen.", 409)
            did = db.execute(
                "INSERT INTO mat_product_document (product_id, category_id, kind, title, file_path, url, mime, size, sha256, "
                "version, valid_from, replaces_id, uploaded_by, uploaded_by_name, uploaded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, kid, w["kind"], w["title"], name, w["url"], mime or "", groesse, sha or "", w["version"],
                 w["valid_from"], ersetzt["id"] if ersetzt else None, uid, uname, db.now()))
            if zwischen:
                # Zeile und Datei unter derselben Schreibsperre, die auch _datei_freigeben hält: Liegt der Inhalt
                # schon, gilt er und bleibt – die Zeile steht ja –, sonst kommt die Zwischendatei an seinen Platz.
                _einordnen(zwischen, os.path.join(dok_dir(), name), groesse)
                zwischen = None
            nachher = dict(w, file_path=name, sha256=sha, size=groesse)
            nachher.update({"category_id": kid} if kid else {"product_id": pid})
            journal.eintragen("document", did, "neue_version" if ersetzt else "angelegt",
                              {"ersetzt": ersetzt["id"]} if ersetzt else None, nachher)
    except BaseException:
        if zwischen:
            _entfernen(zwischen)
        if name:
            _datei_freigeben(name)
        raise
    return did


def dokument_neue_version(did, d, datei=None):
    alt = dokument(did)
    if db.query("SELECT 1 FROM mat_product_document WHERE replaces_id = ? LIMIT 1", (did,), one=True):
        raise Abgelehnt("Zu diesem Dokument gibt es schon eine neuere Version – bitte diese ersetzen.", 409)
    return dokument_anlegen(None, d, datei, ersetzt=alt)


def dokument_umbenennen(did, d):
    """Den Namen eines Dokuments ändern – jeder Version, auch einer alten. Datei und Prüfsumme bleiben; ein
    Protokoll trägt ohnehin den Namen, den das Dokument am Prüftag hatte (documents_json)."""
    titel = text(d, "title", "Titel", 200, pflicht=True)
    with db.transaction(sofort=True):
        alt = dokument(did)
        if titel == alt["title"]:
            return
        db.execute("UPDATE mat_product_document SET title = ? WHERE id = ?", (titel, did))
        journal.eintragen("document", did, "umbenannt", {"title": alt["title"]}, {"title": titel})


def dokument_zurueckziehen(did, d):
    alt = dokument(did)
    if alt["withdrawn_on"]:
        raise Abgelehnt("Das Dokument ist bereits zurückgezogen.", 409)
    tag = datum(d.get("datum"), "Zurückgezogen ab") or heute().isoformat()
    if tag < alt["valid_from"]:
        raise Abgelehnt("Ein Dokument kann nicht vor seiner Gültigkeit zurückgezogen werden.")
    with db.transaction():
        db.execute("UPDATE mat_product_document SET withdrawn_on = ? WHERE id = ?", (tag, did))
        journal.eintragen("document", did, "zurueckgezogen", {"withdrawn_on": None}, {"withdrawn_on": tag})


def _gilt(doc, docs, stichtag):
    """Gilt das Dokument am Stichtag? Ab valid_from, bis es zurückgezogen oder von einer am Stichtag
    schon gültigen neueren Version abgelöst ist."""
    if doc["valid_from"] > stichtag or (doc["withdrawn_on"] and doc["withdrawn_on"] <= stichtag):
        return False
    return not any(n["replaces_id"] == doc["id"] and n["valid_from"] <= stichtag for n in docs)


def dokumente(pid=None, stichtag=None, kid=None):
    """Alle Dokumente (alle Versionen) eines Produkts – oder, mit kid, einer Kategorie."""
    stichtag = stichtag or heute().isoformat()
    spalte, ziel = ("category_id", kid) if kid else ("product_id", pid)
    docs = db.query(f"SELECT * FROM mat_product_document WHERE {spalte} = ? ORDER BY valid_from DESC, id DESC", (ziel,))
    out = []
    for doc in docs:
        out.append({"id": doc["id"], "product_id": doc["product_id"], "category_id": doc["category_id"],
                    "kind": doc["kind"], "title": doc["title"], "version": doc["version"],
                    "valid_from": doc["valid_from"], "withdrawn_on": doc["withdrawn_on"], "url": doc["url"],
                    "datei": f"/media/material/dok/{doc['file_path']}" if doc["file_path"] else None,
                    "mime": doc["mime"], "size": doc["size"], "sha256": doc["sha256"],
                    "replaces_id": doc["replaces_id"], "uploaded_by_name": doc["uploaded_by_name"],
                    "uploaded_at": doc["uploaded_at"],
                    "abgeloest_durch": next((n["id"] for n in docs if n["replaces_id"] == doc["id"]), None),
                    "gilt": _gilt(doc, docs, stichtag)})
    return out


def dokumente_des(doc):
    """Die Dokumentliste des Ziels, an dem doc hängt (Produkt oder Kategorie)."""
    return dokumente(doc["product_id"], kid=doc["category_id"]) if doc["category_id"] else dokumente(doc["product_id"])


def geerbte_dokumente(pid, stichtag=None):
    """Die am Stichtag gültigen Dokumente der Kategorie eines Produkts und ihrer Oberkategorien – sie gelten
    für das Produkt mit (Pflegehinweise, allgemeine Anleitungen). Jedes trägt seine Herkunft."""
    p = produkt(pid)
    out = []
    for k in kategorie_pfad(p["category_id"]):
        for d in dokumente(kid=k["id"], stichtag=stichtag):
            if d["gilt"]:
                out.append(dict(d, herkunft={"id": k["id"], "name": k["name"]}))
    return out


def gueltige_dokumente(pid, stichtag):
    """Die am Stichtag gültigen Dokumente des Produkts samt denen seiner Kategorien – so verweist ein
    Protokoll auf den damaligen Stand."""
    return [d for d in dokumente(pid, stichtag) if d["gilt"]] + geerbte_dokumente(pid, stichtag)


# --- Prüfformulare: Formular-Pool je Kategorie (Schritt 38, Wunsch vom 04.11.2026) --------------------------------------
# Ein Formular (mat_formular) steht im Pool seiner Heimatkategorie und hat Versionen (mat_form): höchstens eine aktiv, eine
# benutzte bleibt unverändert, geändert wird über „Neue Version“. Es gilt für ein Produkt, wenn es ihm zugewiesen ist oder
# Standard seiner Kategorie bzw. der nächsten Oberkategorie mit einem ist (formular_fuer_produkt). Zuweisen lässt es sich
# nur im Teilbaum der Heimat (Entscheidung Z1), nur mit aktiver Version (Z4); ein Haken holt eine Zuweisung von einem
# anderen Formular her (Z5); Deaktivieren und Löschen sind gesperrt, solange es zugewiesen ist (Z4); fällt eine Zuweisung
# durch Verschieben aus dem Teilbaum, wird sie gelöst (Z6). Kein Verschieben eines Formulars (O7) – „Kopie anlegen“.
# Rechte (routes.py): Formularseiten liest jeder mit Modulzugang, die Seite „Prüfformulare“ und alles Schreiben nur die
# Material-Verwaltung (O6). „formular“ heißt hier wie bisher eine Version (mat_form), „pool_formular“ der Eintrag im Pool.

def formular(fid):
    f = db.query("SELECT * FROM mat_form WHERE id = ?", (fid,), one=True)
    if not f:
        raise Abgelehnt("Formular nicht gefunden.", 404)
    return f


def ist_benutzt(fid):
    return bool(db.query("SELECT 1 FROM mat_inspection WHERE form_id = ? LIMIT 1", (fid,), one=True))


def punkte(fid):
    return db.query("SELECT * FROM mat_checklist_item WHERE form_id = ? ORDER BY position, id", (fid,))


def punkt_json(p):
    return {"id": p["id"], "gruppe": p["group_name"], "position": p["position"], "text": p["label"],
            "art": p["editor"], "pflicht": bool(p["mandatory"]), "soll": p["expected_value"]}


def punkt_text(roh, n):
    """Der Text eines Prüfpunkts. Seit dem 04.11.2026 darf er Absätze haben (Wunsch des Nutzers: „Möglichkeit, Absätze
    in den Prüfpunkt einzufügen“): Zeilenumbrüche bleiben als „\n“ (\r\n und \r werden zu \n), je Zeile wie bisher
    Steuerzeichen und mehrfache Leerzeichen zu einem Leerzeichen und kein Rand; mehr als eine Leerzeile wird zu einer,
    Leerzeilen am Anfang und Ende fallen weg. Ein einzeiliger Text kommt genau so heraus wie vorher (einzeilig=True)."""
    if isinstance(roh, str):
        roh = roh.replace("\r\n", "\n").replace("\r", "\n")
        roh = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", " ", roh)
        zeilen = [re.sub(r"[^\S\n]{2,}", " ", z).strip() for z in roh.split("\n")]
        roh = re.sub(r"\n{3,}", "\n\n", "\n".join(zeilen)).strip()
    return text({"text": roh}, "text", f"Text von Prüfpunkt {n}", PUNKT_TEXT_MAX, pflicht=True, einzeilig=False)


def punkte_pruefen(roh):
    """Prüfpunkte eines Formulars aus der Anfrage. Ja/Nein-Punkte brauchen einen Sollwert („ja“ oder
    „nein“ – bei Schadensfragen „nein“). Ein Feld „kritisch“ (Formular-Editor und Katalogdateien bis 03.11.2026) wird
    ohne Prüfung übergangen: Die Funktion ist entfallen, die Spalte is_critical seit Schritt 37 auch."""
    if not isinstance(roh, list):
        raise Abgelehnt("„punkte“ muss eine Liste sein.")
    if len(roh) > 200:
        raise Abgelehnt("Ein Formular hat höchstens 200 Prüfpunkte.")
    out = []
    for n, p in enumerate(roh, 1):
        if not isinstance(p, dict):
            raise Abgelehnt(f"Prüfpunkt {n} ist unbrauchbar.")
        art = auswahl(p.get("art"), EDITOREN, f"Art von Prüfpunkt {n}")
        # Höchstens ein Längenpunkt je Formular – mit zweien gewönne beim Festschreiben still der letzte.
        if art == "laenge" and any(x["editor"] == "laenge" for x in out):
            raise Abgelehnt(f"Prüfpunkt {n}: Ein Formular hat höchstens einen Prüfpunkt „Länge“.")
        soll = text(p, "soll", f"Sollwert von Prüfpunkt {n}", 60)
        if art == "yesno":
            soll = soll.lower()
            if soll not in ("ja", "nein"):
                raise Abgelehnt(f"Prüfpunkt {n} (Ja/Nein) braucht den Sollwert „ja“ oder „nein“.")
        elif art in ("photo", "signature", "date", "laenge"):
            soll = ""                   # bei „Länge“ ist das Soll die Artikellänge zum Prüfzeitpunkt (pruefung.starten)
        out.append({"group_name": text(p, "gruppe", f"Gruppe von Prüfpunkt {n}", 80),
                    "label": punkt_text(p.get("text"), n),
                    "editor": art, "mandatory": int(wahr(p, "pflicht", f"Pflicht (Prüfpunkt {n})") if "pflicht" in p else 1),
                    "expected_value": soll, "position": n})
    return out


def _punkte_schreiben(fid, liste):
    db.execute("DELETE FROM mat_checklist_item WHERE form_id = ?", (fid,))
    for p in liste:
        db.execute("INSERT INTO mat_checklist_item (form_id, group_name, position, label, editor, mandatory, "
                   "expected_value) VALUES (?,?,?,?,?,?,?)",
                   (fid, p["group_name"], p["position"], p["label"], p["editor"], p["mandatory"],
                    p["expected_value"]))


def _punkte_kurz(liste):
    """Für das Journal: die Prüfpunkte als lesbare Zeilen."""
    return [f"{p['group_name'] + ': ' if p['group_name'] else ''}{p['label']} [{p['editor']}"
            f"{', Soll ' + p['expected_value'] if p['expected_value'] else ''}"
            f"{'' if p['mandatory'] else ', optional'}]" for p in liste]


def _titel(d, pflicht=True):
    """Der Titel aus d – seit dem Formular-Pool Pflicht für neue Formulare und Versionen (Entscheidung O5): Im Pool
    stehen mehrere Formulare nebeneinander."""
    titel = text(d, "titel", "Titel", 160)
    if pflicht and not titel:
        raise Abgelehnt(TITEL_PFLICHT)
    return titel


def _demo_nachziehen(pf):
    """mat_formular.demo: 1, wenn jede Version das DEMO-Kennzeichen trägt."""
    db.execute("UPDATE mat_formular SET demo = NOT EXISTS (SELECT 1 FROM mat_form WHERE formular_id = ? AND demo = 0), "
               "updated_at = ? WHERE id = ?", (pf, db.now(), pf))


def pool_anlegen(d, demo=False):
    """Ein neues Formular im Pool der Kategorie d["kategorie_id"] mit Version 1 als Entwurf; Titel Pflicht (O5). Die
    Prüfpunkte aus d["punkte"] (Katalogimport, Schnittstelle), sonst aus der Version d["vorlage_id"] („Prüfpunkte
    übernehmen von …“ im Anlegedialog, „Kopie anlegen“ auf der Formularseite – Entscheidung O4), sonst keine. Übernimmt
    es die Punkte einer DEMO-Vorlage, bleibt es DEMO (wie bei „Neue Version“). Liefert (Formular, Version)."""
    kid = kennung(d.get("kategorie_id"), "Kategorie")
    vorlage_id = kennung(d.get("vorlage_id"), "Vorlage", leer_erlaubt=True)
    titel = _titel(d)
    eigene = punkte_pruefen(d.get("punkte")) if "punkte" in d else None
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        kategorie(kid)
        vorlage = formular(vorlage_id) if vorlage_id else None
        demo = demo or bool(eigene is None and vorlage and vorlage["demo"])
        pf = db.execute("INSERT INTO mat_formular (category_id, demo, created_by, created_at, updated_at) "
                        "VALUES (?,?,?,?,?)", (kid, int(bool(demo)), uid, ts, ts))
        vid = db.execute("INSERT INTO mat_form (formular_id, version, title, active, demo, created_by, created_at, "
                         "updated_at) VALUES (?,1,?,0,?,?,?,?)", (pf, titel, int(bool(demo)), uid, ts, ts))
        liste = eigene if eigene is not None else [dict(p) for p in punkte(vorlage["id"])] if vorlage else []
        _punkte_schreiben(vid, liste)
        journal.eintragen("formular", pf, "angelegt", None,
                          {"heimat": _pfad_text(kid), "titel": titel, "vorlage": vorlage_id})
        journal.eintragen("form", vid, "angelegt", None,
                          {"formular_id": pf, "version": 1, "title": titel, "vorlage": vorlage_id,
                           "punkte": _punkte_kurz(liste)})
    return pf, vid


def formular_anlegen(d, demo=False):
    """Eine neue Version des Formulars d["formular_id"]. Ohne Vorlage übernimmt sie die Prüfpunkte seiner letzten Version
    – der Normalfall ist „ändern“; mit d["vorlage_id"] die dieser Version, mit d["punkte"] eigene. Titel aus d, sonst der
    der Vorlage; leer geht nicht (O5). Bis Schema 37 nannte die Anfrage ein Ziel (kategorie_id bzw. produkt_id) – das
    lehnt der Dienst mit dem neuen Weg ab. Liefert die Kennung der Version."""
    if d.get("formular_id") in (None, "") and (d.get("kategorie_id") or d.get("produkt_id")):
        raise Abgelehnt("Prüfformulare stehen seit dem Formular-Pool im Pool einer Kategorie: ein neues über "
                        "„Prüfformular anlegen“ (POST /api/material/formular-pool), eine neue Version mit „formular_id“.")
    pf = kennung(d.get("formular_id"), "Formular")
    vorlage_id = kennung(d.get("vorlage_id"), "Vorlage", leer_erlaubt=True)
    titel = _titel(d, pflicht=False)
    eigene = punkte_pruefen(d.get("punkte")) if "punkte" in d else None
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        pool_formular(pf)
        letzte = db.query("SELECT * FROM mat_form WHERE formular_id = ? ORDER BY version DESC LIMIT 1", (pf,), one=True)
        vorlage = formular(vorlage_id) if vorlage_id else letzte
        version = (letzte["version"] + 1) if letzte else 1
        titel = titel or (vorlage["title"] if vorlage else "")
        if not titel:
            raise Abgelehnt(TITEL_PFLICHT)
        # Übernimmt die neue Version die Prüfpunkte einer DEMO-Vorlage, bleibt sie DEMO (Sicherheitsprüfung vom
        # 25.10.2026, Befund 5). Mit eigenen Punkten (Katalogimport) zählt nur der Parameter.
        demo = demo or bool(eigene is None and vorlage and vorlage["demo"])
        vid = db.execute("INSERT INTO mat_form (formular_id, version, title, active, demo, created_by, created_at, "
                         "updated_at) VALUES (?,?,?,0,?,?,?,?)", (pf, version, titel, int(bool(demo)), uid, ts, ts))
        liste = eigene if eigene is not None else [dict(p) for p in punkte(vorlage["id"])] if vorlage else []
        _punkte_schreiben(vid, liste)
        _demo_nachziehen(pf)
        journal.eintragen("form", vid, "angelegt", None,
                          {"formular_id": pf, "version": version, "title": titel,
                           "vorlage": vorlage["id"] if vorlage else None, "punkte": _punkte_kurz(liste)})
    return vid


def formular_speichern(fid, d):
    alt = formular(fid)
    titel = _titel(d) if "titel" in d else alt["title"]
    liste_neu = punkte_pruefen(d.get("punkte")) if "punkte" in d else None
    # „Benutzt?“ und Schreiben unter einer Sperre: Eine Prüfung, die gleichzeitig beginnt, kopierte sonst
    # Punkte, die gleich darauf unter derselben Versionsnummer andere werden.
    with db.transaction(sofort=True):
        alt = formular(fid)
        if ist_benutzt(fid):
            raise Abgelehnt(FORMULAR_BENUTZT, 409)
        alte_punkte = [dict(p) for p in punkte(fid)]
        liste = liste_neu if liste_neu is not None else alte_punkte
        if alt["active"] and not liste:
            raise Abgelehnt("Ein aktives Formular braucht mindestens einen Prüfpunkt.")
        db.execute("UPDATE mat_form SET title = ?, updated_at = ? WHERE id = ?", (titel, db.now(), fid))
        _punkte_schreiben(fid, liste)
        journal.aenderung("form", fid, {"title": alt["title"], "punkte": _punkte_kurz(alte_punkte)},
                          {"title": titel, "punkte": _punkte_kurz(liste)})


def formular_aktivieren(fid):
    """Diese Version wird die aktive ihres Formulars – sie gilt sofort für alle Zuweisungen und Standards."""
    with db.transaction(sofort=True):
        f = formular(fid)
        if not punkte(fid):
            raise Abgelehnt("Ein Formular ohne Prüfpunkte lässt sich nicht aktivieren.")
        for anderes in db.query("SELECT id FROM mat_form WHERE formular_id = ? AND active = 1 AND id <> ?",
                                (f["formular_id"], fid)):
            db.execute("UPDATE mat_form SET active = 0, updated_at = ? WHERE id = ?", (db.now(), anderes["id"]))
            journal.eintragen("form", anderes["id"], "deaktiviert", {"active": 1}, {"active": 0, "ersetzt_durch": fid})
        db.execute("UPDATE mat_form SET active = 1, valid_from = COALESCE(valid_from, ?), updated_at = ? WHERE id = ?",
                   (heute().isoformat(), db.now(), fid))
        journal.eintragen("form", fid, "aktiviert", {"active": f["active"]}, {"active": 1})


def _zugewiesen_sperre(pf, was):
    """Abgelehnt (409), solange das Formular zugewiesen ist (Entscheidung Z4) – die Meldung nennt, wo."""
    ziele = _ziele_text(pf)
    if ziele:
        raise Abgelehnt(f"{was} geht erst, wenn das Formular nirgends mehr gilt – es ist {ziele}. Die Zuweisungen löst "
                        "„Zuweisen“ (Seite „Prüfformulare“).", 409)


def formular_deaktivieren(fid):
    with db.transaction(sofort=True):
        f = formular(fid)
        if not f["active"]:
            return
        _zugewiesen_sperre(f["formular_id"], "Deaktivieren")
        db.execute("UPDATE mat_form SET active = 0, updated_at = ? WHERE id = ?", (db.now(), fid))
        journal.eintragen("form", fid, "deaktiviert", {"active": 1}, {"active": 0})


def formular_loeschen(fid):
    """Eine nie benutzte, nicht aktive Version löschen. War es die letzte, geht das Formular mit aus dem Pool (gesperrt,
    solange es zugewiesen ist – ohne aktive Version ist es das nie). Liefert, ob das Formular ganz weg ist."""
    with db.transaction(sofort=True):
        f = formular(fid)
        if ist_benutzt(fid):
            raise Abgelehnt(FORMULAR_BENUTZT, 409)
        if f["active"]:
            raise Abgelehnt("Das aktive Formular lässt sich nicht löschen – erst eine andere Version aktivieren "
                            "oder dieses deaktivieren.", 409)
        pf = f["formular_id"]
        letzte = not db.query("SELECT 1 FROM mat_form WHERE formular_id = ? AND id <> ? LIMIT 1", (pf, fid), one=True)
        if letzte:
            _zugewiesen_sperre(pf, "Löschen")
        db.execute("DELETE FROM mat_form WHERE id = ?", (fid,))
        journal.eintragen("form", fid, "geloescht", {"title": f["title"], "version": f["version"]}, None)
        if letzte:
            heimat = pool_formular(pf)["category_id"]
            db.execute("DELETE FROM mat_formular WHERE id = ?", (pf,))
            journal.eintragen("formular", pf, "geloescht", {"titel": f["title"], "heimat": _pfad_text(heimat)}, None)
        else:
            _demo_nachziehen(pf)
    return letzte


def _aktive_version(pf):
    return db.query("SELECT * FROM mat_form WHERE formular_id = ? AND active = 1", (pf,), one=True) if pf else None


def formular_fuer_produkt(pid):
    """Das Formular, nach dem ein Artikel dieses Produkts geprüft wird – die eine Stelle für Prüfung, Produkt- und
    Artikelseite, Übersichten, Übung und Beispielbestand (für alle Produkte auf einmal: models.geltend_je_produkt, gleiche
    Regel). Der Reihe nach: die aktive Version des dem Produkt zugewiesenen Formulars, sonst die des Standards seiner
    Kategorie oder der nächsten Oberkategorie mit einem (Entscheidung S1). Die Versionszeile mit „art“ (zugewiesen,
    standard), „quelle“ (in Worten), „standard_von“ (die Kategorie des Standards), „formular“ (Kennung, Titel, Heimat) und
    „punkte_anzahl“ – oder None (S2: dann ist das Produkt nicht prüfbar, Produkt- und Kategorieseite warnen)."""
    p = produkt(pid)
    z = db.query("SELECT formular_id FROM mat_formular_zuweisung WHERE product_id = ?", (pid,), one=True)
    f = _aktive_version(z["formular_id"]) if z else None
    if f:
        f["art"], f["quelle"], f["standard_von"] = "zugewiesen", "dem Produkt zugewiesen", None
    else:
        for k in reversed(kategorie_pfad(p["category_id"])):
            z = db.query("SELECT formular_id FROM mat_formular_zuweisung WHERE category_id = ?", (k["id"],), one=True)
            f = _aktive_version(z["formular_id"]) if z else None
            if f:
                f["art"], f["quelle"] = "standard", f"Standard der Kategorie „{k['name']}“"
                f["standard_von"] = {"id": k["id"], "name": k["name"]}
                break
    if f:
        f["punkte_anzahl"] = db.query("SELECT COUNT(*) AS n FROM mat_checklist_item WHERE form_id = ?",
                                      (f["id"],), one=True)["n"]
        heimat = pool_formular(f["formular_id"])["category_id"]
        f["formular"] = {"id": f["formular_id"], "titel": f["title"],
                         "heimat": {"id": heimat, "name": _pfad_text(heimat)}}
    return f


# --- Zuweisungen ---------------------------------------------------------------------------------------------------------

def _kurz(p):
    """Ein Produkt für Listen und Links der Oberfläche (nameHtml/zusatzHtml in material.js)."""
    return {"id": p["id"], "name": produktname(p), "manufacturer": p["manufacturer"], "model": p["model"],
            "description": p["description"], "article_no": p.get("article_no", ""), "demo": bool(p.get("demo")),
            "category_id": p.get("category_id")}


def _pfad_text(kid):
    return " / ".join(k["name"] for k in kategorie_pfad(kid))


def _hat_laengenpunkt(fid):
    return bool(db.query("SELECT 1 FROM mat_checklist_item WHERE form_id = ? AND editor = 'laenge' LIMIT 1", (fid,),
                         one=True))


def _anzeige_titel(pf):
    """Der Titel eines Formulars: der seiner aktiven Version, sonst der neuesten."""
    v = db.query("SELECT title FROM mat_form WHERE formular_id = ? ORDER BY active DESC, version DESC LIMIT 1", (pf,),
                 one=True)
    return v["title"] if v else ""


def _ziele_text(pf):
    """Wo das Formular zugewiesen ist, in Worten („Standard für „Gurte“, zugewiesen an „Testwerk X““) – leer, wenn
    nirgends."""
    kats = [f"„{_pfad_text(r['category_id'])}“" for r in db.query(
        "SELECT category_id FROM mat_formular_zuweisung WHERE formular_id = ? AND category_id IS NOT NULL ORDER BY id",
        (pf,))]
    prods = [f"„{produktname(r)}“" for r in db.query(
        "SELECT p.manufacturer, p.model, p.description FROM mat_formular_zuweisung z JOIN mat_product p "
        "ON p.id = z.product_id WHERE z.formular_id = ? ORDER BY p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE",
        (pf,))]
    teile = []
    if kats:
        teile.append("Standard für " + ", ".join(kats[:5]) + (" …" if len(kats) > 5 else ""))
    if prods:
        teile.append("zugewiesen an " + ", ".join(prods[:5]) + (f" und {len(prods) - 5} weitere" if len(prods) > 5
                                                                 else ""))
    return " und ".join(teile)


def _ziel_name(spalte, ziel):
    if spalte == "category_id":
        return {"kategorie": _pfad_text(ziel)}
    p = db.query("SELECT manufacturer, model, description FROM mat_product WHERE id = ?", (ziel,), one=True)
    return {"produkt": produktname(p) if p else f"Nr. {ziel}"}


def _zuweisung_loesen(z, grund):
    """Eine Zuweisung (Zeile aus mat_formular_zuweisung) löschen – Journal am Formular und am Produkt bzw. an der
    Kategorie. grund steht im Journal (etwa „Produkt in eine andere Kategorie verschoben“)."""
    spalte, ziel = ("category_id", z["category_id"]) if z["category_id"] else ("product_id", z["product_id"])
    titel = _anzeige_titel(z["formular_id"])
    db.execute("DELETE FROM mat_formular_zuweisung WHERE id = ?", (z["id"],))
    journal.eintragen("formular", z["formular_id"], "zuweisung_geloest", _ziel_name(spalte, ziel),
                      {"grund": grund} if grund else None)
    journal.eintragen("category" if spalte == "category_id" else "product", ziel,
                      "standard_geloest" if spalte == "category_id" else "formular_zuweisung_geloest",
                      {"formular": titel, "formular_id": z["formular_id"]}, {"grund": grund} if grund else None)


def _zuweisen(pf, spalte, ziel, titel, uid):
    """pf an ein Produkt bzw. als Standard an eine Kategorie – hängt dort ein anderes, wechselt es hierher (Z5)."""
    alt = db.query(f"SELECT * FROM mat_formular_zuweisung WHERE {spalte} = ?", (ziel,), one=True)
    vorher = None
    if alt:
        vorher = {"formular": _anzeige_titel(alt["formular_id"]), "formular_id": alt["formular_id"]}
        db.execute("DELETE FROM mat_formular_zuweisung WHERE id = ?", (alt["id"],))
        journal.eintragen("formular", alt["formular_id"], "zuweisung_geloest", _ziel_name(spalte, ziel),
                          {"grund": f"jetzt „{titel}“"})
    db.execute(f"INSERT INTO mat_formular_zuweisung (formular_id, {spalte}, created_by, created_at) VALUES (?,?,?,?)",
               (pf, ziel, uid, db.now()))
    journal.eintragen("formular", pf, "zugewiesen", {"bisher": vorher["formular"]} if vorher else None,
                      _ziel_name(spalte, ziel))
    journal.eintragen("category" if spalte == "category_id" else "product", ziel,
                      "standard_gesetzt" if spalte == "category_id" else "formular_zugewiesen", vorher,
                      {"formular": titel, "formular_id": pf})


def _kennungen(d, feld, name):
    wert = d.get(feld)
    if wert is None:
        return set()
    if not isinstance(wert, list):
        raise Abgelehnt(f"„{feld}“ muss eine Liste sein.")
    return {kennung(x, name) for x in wert}


def laenge_grund(p, mit_laenge):
    """Warum ein Formular mit Prüfpunkt „Länge (m)“ (mit_laenge) Produkt p nicht zugewiesen werden kann – oder ""."""
    if mit_laenge and not laenge_wirksam(p["category_id"]):
        return f"Das Formular hat einen Prüfpunkt „Länge (m)“, Artikel von „{produktname(p)}“ haben aber keine Länge."
    return ""


def zuweisung_setzen(pf, d):
    """Die Zuweisungen von Formular pf als vollständige Menge: d["kategorien"] (Standard dieser Kategorien) und
    d["produkte"]. Was dazukommt, muss im Teilbaum der Heimat liegen (Z1) und braucht eine aktive Version (Z4); ein
    Produkt dazu Artikel mit Länge, wenn das Formular den Prüfpunkt „Länge (m)“ hat. Hängt dort schon ein anderes
    Formular, wechselt die Zuweisung hierher (Z5). Was wegfällt, wird gelöst – das Produkt bzw. die Kategorie fällt auf
    den Standard darüber zurück. Unter einer Schreibsperre, Journal je Änderung. Liefert die Zahl der Änderungen."""
    kats = _kennungen(d, "kategorien", "Kategorie")
    prods = _kennungen(d, "produkte", "Produkt")
    uid, _ = akteur()
    n = 0
    with db.transaction(sofort=True):
        f = pool_formular(pf)
        teil = _unterkategorien(f["category_id"])
        heimat = _pfad_text(f["category_id"])
        alt = db.query("SELECT * FROM mat_formular_zuweisung WHERE formular_id = ?", (pf,))
        alt_k = {z["category_id"]: z for z in alt if z["category_id"]}
        alt_p = {z["product_id"]: z for z in alt if z["product_id"]}
        aktiv = _aktive_version(pf)
        if (kats - set(alt_k) or prods - set(alt_p)) and not aktiv:
            raise Abgelehnt(NUR_AKTIV_ZUWEISEN, 409)
        for kid in sorted(kats - set(alt_k)):
            k = kategorie(kid)
            if kid not in teil:
                raise Abgelehnt(f"„{k['name']}“ liegt nicht unter „{heimat}“ – das Formular lässt sich nur dort zuweisen, "
                                "wo es im Pool steht (und darunter).", 409)
        mit_laenge = _hat_laengenpunkt(aktiv["id"]) if aktiv else False
        for pid in sorted(prods - set(alt_p)):
            p = produkt(pid)
            if p["category_id"] not in teil:
                raise Abgelehnt(f"„{produktname(p)}“ liegt nicht unter „{heimat}“ – das Formular lässt sich nur dort "
                                "zuweisen, wo es im Pool steht (und darunter).", 409)
            grund = laenge_grund(p, mit_laenge)
            if grund:
                raise Abgelehnt(grund, 409)
        for kid in sorted(set(alt_k) - kats):
            _zuweisung_loesen(alt_k[kid], None)
            n += 1
        for pid in sorted(set(alt_p) - prods):
            _zuweisung_loesen(alt_p[pid], None)
            n += 1
        titel = aktiv["title"] if aktiv else ""
        for kid in sorted(kats - set(alt_k)):
            _zuweisen(pf, "category_id", kid, titel, uid)
            n += 1
        for pid in sorted(prods - set(alt_p)):
            _zuweisen(pf, "product_id", pid, titel, uid)
            n += 1
    return n


def _ungueltige_zuweisungen(eltern, produkt_kategorie):
    """Zuweisungen, deren Ziel mit dieser Ordnung (eltern: {Kategorie: Oberkategorie}, produkt_kategorie: {Produkt:
    Kategorie} – nur Abweichungen von heute) nicht mehr unter der Heimat ihres Formulars läge."""
    out = []
    for z in db.query("SELECT z.*, f.category_id AS heimat, p.category_id AS produkt_kategorie "
                      "FROM mat_formular_zuweisung z JOIN mat_formular f ON f.id = z.formular_id "
                      "LEFT JOIN mat_product p ON p.id = z.product_id ORDER BY z.id"):
        x = z["category_id"] or produkt_kategorie.get(z["product_id"], z["produkt_kategorie"])
        gesehen = set()
        while x is not None and x != z["heimat"] and x not in gesehen:
            gesehen.add(x)
            x = eltern.get(x)
        if x != z["heimat"]:
            out.append(z)
    return out


def _eltern(kid=None, parent_id=None):
    eltern = {k["id"]: k["parent_id"] for k in db.query("SELECT id, parent_id FROM mat_category")}
    if kid:
        eltern[kid] = parent_id
    return eltern


def verschieben_folgen(kategorie_id=None, parent_id=None, produkt_id=None, category_id=None):
    """Was ein Verschieben lösen würde (Entscheidung Z6) – für den Satz im Dialog, bevor gespeichert wird: eine Kategorie
    unter parent_id (None: oberste Ebene) oder ein Produkt in category_id. [{formular_id, formular, ziel}]."""
    if produkt_id:
        liste = _ungueltige_zuweisungen(_eltern(), {produkt_id: category_id})
        liste = [z for z in liste if z["product_id"] == produkt_id]
    else:
        liste = _ungueltige_zuweisungen(_eltern(kategorie_id, parent_id), {})
    out = []
    for z in liste:
        spalte, ziel = ("category_id", z["category_id"]) if z["category_id"] else ("product_id", z["product_id"])
        name = _ziel_name(spalte, ziel)
        out.append({"formular_id": z["formular_id"], "formular": _anzeige_titel(z["formular_id"]),
                    "ziel": f"Kategorie „{name['kategorie']}“" if "kategorie" in name else f"„{name['produkt']}“"})
    return out


def _verschieben_loesen(eltern, produkt_kategorie, grund):
    """Vor dem Verschieben, in derselben Transaktion: Zuweisungen lösen, die danach außerhalb des Teilbaums lägen (Z6)."""
    liste = _ungueltige_zuweisungen(eltern, produkt_kategorie)
    for z in liste:
        _zuweisung_loesen(z, grund)
    return len(liste)


# --- Lesen: Formularseite, Pool-Seite, Dialog „Zuweisen“ ----------------------------------------------------------------

def pool_formular(pf):
    row = db.query("SELECT * FROM mat_formular WHERE id = ?", (pf,), one=True)
    if not row:
        raise Abgelehnt("Prüfformular nicht gefunden.", 404)
    return row


def formular_json(f, mit_punkten=True):
    """Eine Version für die Schnittstelle (die Formularseite hängt formular_info und die Versionen an)."""
    out = {"id": f["id"], "formular_id": f["formular_id"], "version": f["version"], "titel": f["title"],
           "gueltig_ab": f["valid_from"], "aktiv": bool(f["active"]), "demo": bool(f["demo"]),
           "created_at": f["created_at"], "updated_at": f["updated_at"], "benutzt": ist_benutzt(f["id"])}
    out["aenderbar"] = not out["benutzt"]
    if mit_punkten:
        out["punkte"] = [punkt_json(p) for p in punkte(f["id"])]
    return out


def formulare_fuer(pf):
    """Die Versionen eines Formulars, neueste zuerst, mit Zahl der Prüfpunkte."""
    out = []
    for f in db.query("SELECT f.*, (SELECT COUNT(*) FROM mat_checklist_item c WHERE c.form_id = f.id) AS punkte_anzahl "
                      "FROM mat_form f WHERE f.formular_id = ? ORDER BY f.version DESC", (pf,)):
        j = formular_json(f, mit_punkten=False)
        j["punkte_anzahl"] = f["punkte_anzahl"]
        out.append(j)
    return out


def _geltend():
    """models.geltend_je_produkt über die Verbindung der Anfrage: {Produkt: (Version, Formular, Standard-Kategorie)}."""
    return geltend_je_produkt(db.get_db())


def wirksam_fuer(pf, geltend=None):
    """Die Produkte, für die das Formular gerade gilt – zugewiesen oder über einen Standard –, nach Namen."""
    geltend = _geltend() if geltend is None else geltend
    ids = [pid for pid, (_v, f, _k) in geltend.items() if f == pf]
    if not ids:
        return []
    rows = db.query("SELECT id, category_id, manufacturer, model, description, article_no, demo FROM mat_product "
                    "WHERE id IN (SELECT value FROM json_each(?)) ORDER BY manufacturer COLLATE NOCASE, "
                    "model COLLATE NOCASE, id", (json.dumps(ids),))
    return [_kurz(r) for r in rows]


def formular_info(pf, geltend=None):
    """Das Formular zu einer Version für die Formularseite (Abschnitt „Gilt für“): Kennung, Titel (der aktiven, sonst der
    neuesten Version), Heimat mit Pfad, Standard für welche Kategorien, welchen Produkten zugewiesen, für wie viele
    Produkte es insgesamt gilt."""
    f = pool_formular(pf)
    geltend = _geltend() if geltend is None else geltend
    kats = db.query("SELECT category_id FROM mat_formular_zuweisung WHERE formular_id = ? AND category_id IS NOT NULL",
                    (pf,))
    prods = db.query("SELECT p.id, p.category_id, p.manufacturer, p.model, p.description, p.article_no, p.demo "
                     "FROM mat_formular_zuweisung z JOIN mat_product p ON p.id = z.product_id WHERE z.formular_id = ? "
                     "ORDER BY p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE, p.id", (pf,))
    aktiv = _aktive_version(pf)
    return {"id": pf, "titel": _anzeige_titel(pf), "herkunft": f["herkunft"], "demo": bool(f["demo"]),
            "heimat": {"id": f["category_id"], "name": kategorie(f["category_id"])["name"],
                       "pfad": kategorie_pfad(f["category_id"])},
            "aktive_version": {"id": aktiv["id"], "version": aktiv["version"]} if aktiv else None,
            "standard_fuer": sorted(({"id": r["category_id"], "name": _pfad_text(r["category_id"])} for r in kats),
                                    key=lambda x: x["name"].casefold()),
            "zugewiesen": [_kurz(p) for p in prods],
            "wirksam_n": sum(1 for _v, x, _k in geltend.values() if x == pf)}


def pool(kategorie_id=None):
    """Für die Seite „Prüfformulare“ (nur Material-Verwaltung, Entscheidung O6): alle Kategorien in Baumreihenfolge – mit
    kategorie_id nur deren Teilbaum –, je Kategorie ihr Standard (eigener oder geerbt, S1) und die Formulare ihres Pools:
    Titel, aktive und neueste Version, Versionen, Standard für, zugewiesen an, für wie viele Produkte es gilt."""
    kats = db.query("SELECT id, parent_id, name, demo FROM mat_category ORDER BY position, name COLLATE NOCASE, id")
    nach_id = {k["id"]: k for k in kats}
    kinder = {}
    for k in kats:
        kinder.setdefault(k["parent_id"] if k["parent_id"] in nach_id else None, []).append(k)
    versionen = {}
    for v in db.query("SELECT f.id, f.formular_id, f.version, f.title, f.active, f.demo, "
                      "EXISTS (SELECT 1 FROM mat_inspection x WHERE x.form_id = f.id) AS benutzt "
                      "FROM mat_form f ORDER BY f.version DESC"):
        versionen.setdefault(v["formular_id"], []).append(v)
    standard = {}                                  # Kategorie → Formular
    zugewiesen = {}                                # Formular → [Produkt]
    standard_fuer = {}                             # Formular → [Kategorie]
    for z in db.query("SELECT z.formular_id, z.category_id, p.id AS pid, p.category_id AS pkat, p.manufacturer, "
                      "p.model, p.description, p.article_no, p.demo FROM mat_formular_zuweisung z "
                      "LEFT JOIN mat_product p ON p.id = z.product_id ORDER BY p.manufacturer COLLATE NOCASE, "
                      "p.model COLLATE NOCASE, z.id"):
        if z["category_id"]:
            standard[z["category_id"]] = z["formular_id"]
            standard_fuer.setdefault(z["formular_id"], []).append(z["category_id"])
        else:
            zugewiesen.setdefault(z["formular_id"], []).append(_kurz(dict(z, id=z["pid"], category_id=z["pkat"])))
    wirksam = {}
    for _v, pf, _k in _geltend().values():
        wirksam[pf] = wirksam.get(pf, 0) + 1
    formulare = {}
    for r in db.query("SELECT * FROM mat_formular ORDER BY id"):
        formulare.setdefault(r["category_id"], []).append(r)

    def pfad(kid):
        teile, gesehen = [], set()
        while kid in nach_id and kid not in gesehen:
            gesehen.add(kid)
            teile.insert(0, nach_id[kid]["name"])
            kid = nach_id[kid]["parent_id"]
        return teile

    def kopf(pf):
        """Titel und Versionen eines Formulars für Standardzeilen."""
        liste = versionen.get(pf, [])
        aktiv = next((v for v in liste if v["active"]), None)
        return aktiv, (aktiv or (liste[0] if liste else None))

    def eintrag(r):
        liste = versionen.get(r["id"], [])
        aktiv, zeige = kopf(r["id"])
        neueste = liste[0] if liste else None
        return {"id": r["id"], "titel": zeige["title"] if zeige else "", "herkunft": r["herkunft"], "demo": bool(r["demo"]),
                "aktive_version": {"id": aktiv["id"], "version": aktiv["version"]} if aktiv else None,
                "neueste_version": {"id": neueste["id"], "version": neueste["version"],
                                    "entwurf": not neueste["active"] and not neueste["benutzt"]} if neueste else None,
                "link": zeige["id"] if zeige else None, "versionen": len(liste),
                "standard_fuer": [{"id": k, "name": " / ".join(pfad(k))} for k in standard_fuer.get(r["id"], [])],
                "zugewiesen": zugewiesen.get(r["id"], []), "wirksam_n": wirksam.get(r["id"], 0)}

    out = []

    def baum(parent, tiefe, geerbt):
        """geerbt: der Standard, der von oben kommt (mit „geerbt_von“) – oder None."""
        for k in kinder.get(parent, []):
            eigen = standard.get(k["id"])
            aktiv = kopf(eigen)[0] if eigen else None
            std = ({"formular_id": eigen, "titel": aktiv["title"], "version": aktiv["version"], "version_id": aktiv["id"],
                    "geerbt_von": None} if aktiv else geerbt)
            out.append({"id": k["id"], "parent_id": k["parent_id"], "name": k["name"], "pfad": pfad(k["id"]),
                        "tiefe": tiefe, "demo": bool(k["demo"]), "standard": std,
                        "formulare": [eintrag(r) for r in formulare.get(k["id"], [])]})
            baum(k["id"], tiefe + 1, dict(std, geerbt_von={"id": k["id"], "name": k["name"]}) if aktiv else geerbt)

    baum(None, 0, None)
    if kategorie_id:
        kategorie(kategorie_id)
        teil = _unterkategorien(kategorie_id)
        out = [k for k in out if k["id"] in teil]
    return {"kategorien": out, "formulare": sum(len(k["formulare"]) for k in out)}


def kandidaten(pf):
    """Für den Dialog „Zuweisen“ (Entscheidungen Z1–Z5): die Kategorien und Produkte im Teilbaum der Heimat – je Zeile
    „gewaehlt“ (gilt hier ausdrücklich), „bisher“ (ein anderes Formular hängt dort; ein Haken holt es her), bei Produkten
    „standard“ (das Formular, das ohne Zuweisung über einen Standard gälte – „ueber_standard“, wenn es dieses ist) und
    „grund“, wenn sich ein neuer Haken nicht setzen lässt (Länge). Ohne aktive Version „grund“ am Ganzen."""
    f = pool_formular(pf)
    heimat = f["category_id"]
    teil = _unterkategorien(heimat)
    aktiv = _aktive_version(pf)
    mit_laenge = _hat_laengenpunkt(aktiv["id"]) if aktiv else False
    zuw = db.query("SELECT * FROM mat_formular_zuweisung")
    std = {z["category_id"]: z["formular_id"] for z in zuw if z["category_id"]}
    prod = {z["product_id"]: z["formular_id"] for z in zuw if z["product_id"]}
    titel = {}

    def titel_von(x):
        if x not in titel:
            titel[x] = _anzeige_titel(x)
        return titel[x]

    def bisher(x):
        return {"id": x, "titel": titel_von(x)} if x and x != pf else None

    kats = [k for k in pool(heimat)["kategorien"]]
    geltend = _geltend()
    kategorien = [{"id": k["id"], "name": k["name"], "pfad": k["pfad"], "tiefe": k["tiefe"],
                   "gewaehlt": std.get(k["id"]) == pf, "bisher": bisher(std.get(k["id"])),
                   "standard": None if std.get(k["id"]) or not k["standard"] else
                   {"id": k["standard"]["formular_id"], "titel": k["standard"]["titel"]}} for k in kats]
    produkte = []
    for p in db.query("SELECT p.*, c.name AS category_name FROM mat_product p JOIN mat_category c ON c.id = p.category_id "
                      "WHERE p.category_id IN (SELECT value FROM json_each(?)) "
                      "ORDER BY p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE, p.id", (json.dumps(sorted(teil)),)):
        j = _kurz(p)
        j["category_name"] = p["category_name"]
        j["gewaehlt"] = prod.get(p["id"]) == pf
        j["bisher"] = bisher(prod.get(p["id"]))
        g = geltend.get(p["id"])
        j["standard"] = ({"id": g[1], "titel": titel_von(g[1])} if g and g[2] is not None else None)
        j["ueber_standard"] = bool(g and g[2] is not None and g[1] == pf)
        j["grund"] = "" if j["gewaehlt"] else laenge_grund(p, mit_laenge)
        produkte.append(j)
    return {"formular": formular_info(pf, geltend), "kategorien": kategorien, "produkte": produkte,
            "laenge": mit_laenge, "grund": "" if aktiv else NUR_AKTIV_ZUWEISEN}


def durchsichtige_bilder_reparieren(conn):
    """Einmalige Reparatur beim Start (Kennzeichen in mat_meta): Bis zum 17.10.2026 wurden durchsichtige Flächen
    in Produkt-, Ordner-, Mangel- und Meldungsfotos beim Umwandeln nach JPEG schwarz. Die Originale sind erhalten –
    aus ihnen entstehen Web- und Vorschaufassung neu, mit weißem Grund. Unter der Schreibsperre, damit es nur ein
    Arbeitsprozess tut."""
    import json
    import logging

    from ...images import varianten_erneuern
    pfad = conn.execute("PRAGMA database_list").fetchone()[2]
    if not pfad:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT 1 FROM mat_meta WHERE schluessel = 'bilder_weiss'").fetchone():
            return
        dateien = [(r[0], True) for r in conn.execute("SELECT image FROM mat_product WHERE image <> ''")]
        dateien += [(r[0], True) for r in conn.execute("SELECT photo FROM mat_inspection_result WHERE photo <> ''")]
        dateien += [(r[0], False) for r in conn.execute("SELECT photo FROM mat_folder WHERE photo <> ''")]
        for (fotos,) in conn.execute("SELECT photos_json FROM mat_product_request"):
            dateien += [(f, False) for f in json.loads(fotos or "[]") if isinstance(f, str)]
        medien = os.path.join(os.path.dirname(pfad), "media", "material")
        neu = sum(varianten_erneuern(medien, name, ganz) for name, ganz in dateien
                  if os.path.splitext(name)[1].lower() in (".png", ".webp", ".tif", ".tiff", ".gif"))
        conn.execute("INSERT INTO mat_meta (schluessel, wert) VALUES ('bilder_weiss', '1')")
        conn.commit()
        if neu:
            logging.getLogger(__name__).info("%d Bilder mit durchsichtigem Hintergrund neu auf Weiß erzeugt.", neu)
    finally:
        if conn.in_transaction:
            conn.rollback()
