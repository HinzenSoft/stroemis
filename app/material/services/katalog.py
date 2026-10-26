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
  - Formulare: je Kategorie ein generisches, je Produkt optional ein spezifisches, das das generische
    ersetzt. Versioniert; eine benutzte Version wird nie mehr geändert, sondern durch eine neue ersetzt.
  - Fotos und Herstellerdokumente hängen am Produkt, nie am einzelnen Artikel. Allgemeine Dokumente
    (Pflegehinweise, Anleitungen) können an einer Kategorie hängen und gelten dann für alle Produkte
    darin und in ihren Unterkategorien.
"""
import hashlib
import os
import re
import secrets
import sqlite3

from flask import current_app, g, has_request_context

from ... import db
from ...images import ALLOWED_EXT, delete_photo_files, store_upload
from ..models import DOKUMENTARTEN, EDITOREN, MATERIALARTEN
from . import Abgelehnt, akteur, auswahl, datum, ganzzahl, heute, kennung, text, wahr
from . import faelligkeit, journal
from .interval import herstellerseite, lebensende

FORMULAR_BENUTZT = ("Diese Formularversion wurde schon für Prüfungen benutzt und bleibt deshalb unverändert. "
                    "Lege eine neue Version an.")
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
        if db.query("SELECT 1 FROM mat_inspection i JOIN mat_form f ON f.id = i.form_id WHERE f.category_id = ? LIMIT 1",
                    (kid,), one=True):
            raise Abgelehnt("Ein Formular dieser Kategorie wurde schon für Prüfungen benutzt.", 409)
        # Eine Prüfung nennt die damals gültigen Dokumente mit Version und Prüfsumme (documents_json) – auch die einer
        # Kategorie, aus der das Produkt inzwischen fortgezogen ist. Prüfnachweise werden unbefristet aufbewahrt
        # (Entscheidung des Betreibers vom 18.10.2026), also bleibt ein solches Dokument samt Datei – und mit ihm die
        # Kategorie.
        if db.query("SELECT 1 FROM mat_product_document d WHERE d.category_id = ? AND EXISTS (SELECT 1 FROM mat_inspection "
                    "x, json_each(CASE WHEN json_valid(x.documents_json) THEN x.documents_json ELSE '[]' END) j "
                    "WHERE x.completed_at IS NOT NULL AND json_extract(j.value, '$.id') = d.id) LIMIT 1",
                    (kid,), one=True):
            raise Abgelehnt(DOKUMENT_IM_PROTOKOLL, 409)
        for f in db.query("SELECT id FROM mat_form WHERE category_id = ?", (kid,)):
            db.execute("DELETE FROM mat_form WHERE id = ?", (f["id"],))
            journal.eintragen("form", f["id"], "geloescht", {"kategorie": alt["name"]}, None)
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
    """Alle Kategorien flach, mit Produktzahl und Formularstand – den Baum baut die Oberfläche."""
    rows = db.query(
        "SELECT c.*, (SELECT COUNT(*) FROM mat_product p WHERE p.category_id = c.id) AS produkte, "
        "(SELECT f.id FROM mat_form f WHERE f.category_id = c.id AND f.active = 1) AS aktives_formular, "
        "(SELECT COUNT(*) FROM mat_form f WHERE f.category_id = c.id) AS formulare "
        "FROM mat_category c ORDER BY c.position, c.name COLLATE NOCASE")
    return [kategorie_json(r) for r in rows]


def kategorie_json(k):
    out = {f: k.get(f) for f in ("id", "parent_id", "name", "norm", "default_material_kind",
                                 "default_interval_months", "default_lifetime_years", "position")}
    out["demo"] = bool(k.get("demo"))
    # Das Häkchen selbst und ob es hier wirkt (auch von einer Oberkategorie geerbt).
    out["items_have_length"] = bool(k.get("items_have_length"))
    out["laenge_wirksam"] = laenge_wirksam(k["id"])
    for f in ("produkte", "aktives_formular", "formulare"):
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
    Produkts die Dokumente des anderen nicht mitnimmt). Das Produktbild nie, spezifische Formulare auch nicht. Die
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
    der Bestandteile)."""
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
        for f in db.query("SELECT id FROM mat_form WHERE product_id = ?", (pid,)):
            journal.eintragen("form", f["id"], "geloescht", {"produkt": pid}, None)
        # Die Dokumente gehen mit dem Produkt (ON DELETE CASCADE) – ihr Journal bekommt das Ende vermerkt,
        # damit eine später wieder vergebene Kennung nicht ihre Geschichte erbt (journal.LOESCHUNG).
        for dok in db.query("SELECT id, title FROM mat_product_document WHERE product_id = ?", (pid,)):
            journal.eintragen("document", dok["id"], "geloescht", {"produkt": pid, "title": dok["title"]}, None)
        db.execute("DELETE FROM mat_form WHERE product_id = ?", (pid,))
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
                                 "wiki_page_id", "created_at", "updated_at")}
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
        f = formular_fuer_produkt(p["id"])
        out["formular"] = ({"id": f["id"], "version": f["version"], "title": f["title"], "quelle": f["quelle"],
                            "punkte": f["punkte_anzahl"]} if f else None)
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


# --- Prüfformulare ------------------------------------------------------------------------------------

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
            "art": p["editor"], "pflicht": bool(p["mandatory"]), "soll": p["expected_value"],
            "kritisch": bool(p["is_critical"])}


def punkte_pruefen(roh):
    """Prüfpunkte eines Formulars aus der Anfrage. Ja/Nein-Punkte brauchen einen Sollwert („ja“ oder
    „nein“ – bei Schadensfragen „nein“); kritisch kann nur ein solcher Punkt sein: Weicht er ab, ist
    „einsatzbereit“ ausgeschlossen."""
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
        kritisch = wahr(p, "kritisch", f"kritisch (Prüfpunkt {n})")
        if kritisch and art != "yesno":
            raise Abgelehnt(f"Prüfpunkt {n}: Kritisch kann nur ein Ja/Nein-Punkt sein – er hat einen Sollwert, "
                            "an dem sich ein Mangel festmachen lässt.")
        out.append({"group_name": text(p, "gruppe", f"Gruppe von Prüfpunkt {n}", 80),
                    "label": text(p, "text", f"Text von Prüfpunkt {n}", PUNKT_TEXT_MAX, pflicht=True),
                    "editor": art, "mandatory": int(wahr(p, "pflicht", f"Pflicht (Prüfpunkt {n})") if "pflicht" in p else 1),
                    "expected_value": soll, "is_critical": int(kritisch), "position": n})
    return out


def _punkte_schreiben(fid, liste):
    db.execute("DELETE FROM mat_checklist_item WHERE form_id = ?", (fid,))
    for p in liste:
        db.execute("INSERT INTO mat_checklist_item (form_id, group_name, position, label, editor, mandatory, "
                   "expected_value, is_critical) VALUES (?,?,?,?,?,?,?,?)",
                   (fid, p["group_name"], p["position"], p["label"], p["editor"], p["mandatory"],
                    p["expected_value"], p["is_critical"]))


def _punkte_kurz(liste):
    """Für das Journal: die Prüfpunkte als lesbare Zeilen."""
    return [f"{p['group_name'] + ': ' if p['group_name'] else ''}{p['label']} [{p['editor']}"
            f"{', Soll ' + p['expected_value'] if p['expected_value'] else ''}"
            f"{', kritisch' if p['is_critical'] else ''}{'' if p['mandatory'] else ', optional'}]" for p in liste]


def formular_anlegen(d, demo=False):
    """Neue Version für eine Kategorie (generisch) oder ein Produkt (spezifisch). Ohne Vorlage
    übernimmt sie die Prüfpunkte der letzten Version desselben Ziels – der Normalfall ist „ändern“. Die Verknüpfung
    mit einer Wiki-Seite (Prüfanleitung) kommt von der Vorlage mit."""
    kid = kennung(d.get("kategorie_id"), "Kategorie", leer_erlaubt=True)
    pid = kennung(d.get("produkt_id"), "Produkt", leer_erlaubt=True)
    if bool(kid) == bool(pid):
        raise Abgelehnt("Ein Formular gehört entweder zu einer Kategorie oder zu einem Produkt.")
    if kid:
        kategorie(kid)
    else:
        produkt(pid)
    spalte, ziel = ("category_id", kid) if kid else ("product_id", pid)
    vorlage_id = kennung(d.get("vorlage_id"), "Vorlage", leer_erlaubt=True)
    titel = text(d, "titel", "Titel", 160)
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        letzte = db.query(f"SELECT * FROM mat_form WHERE {spalte} = ? ORDER BY version DESC LIMIT 1", (ziel,), one=True)
        vorlage = formular(vorlage_id) if vorlage_id else letzte
        version = (letzte["version"] + 1) if letzte else 1
        if not titel:
            titel = vorlage["title"] if vorlage else ""
        # Übernimmt die neue Version die Prüfpunkte einer DEMO-Vorlage, bleibt sie DEMO – sonst kämen deren Punkte über
        # „Neue Version“ in den Katalog-Export (Sicherheitsprüfung vom 25.10.2026, Befund 5). Mit eigenen Punkten
        # (Katalogimport) zählt nur der Parameter.
        demo = demo or bool("punkte" not in d and vorlage and vorlage["demo"])
        # Die Prüfanleitung aus dem Wiki erbt die neue Version von der Vorlage – wie den Titel (Phase 2 · L3); d setzt
        # sie nie (Katalogimport und „Neue Version“ gleich).
        fid = db.execute(f"INSERT INTO mat_form ({spalte}, version, title, active, demo, wiki_page_id, created_by, "
                         "created_at, updated_at) VALUES (?,?,?,0,?,?,?,?,?)",
                         (ziel, version, titel, int(bool(demo)), vorlage.get("wiki_page_id") if vorlage else None, uid,
                          ts, ts))
        if "punkte" in d:
            liste = punkte_pruefen(d.get("punkte"))
        elif vorlage:
            liste = [dict(p) for p in punkte(vorlage["id"])]
        else:
            liste = []
        _punkte_schreiben(fid, liste)
        journal.eintragen("form", fid, "angelegt", None,
                          {spalte: ziel, "version": version, "title": titel,
                           "vorlage": vorlage["id"] if vorlage else None, "punkte": _punkte_kurz(liste)})
    return fid


def formular_speichern(fid, d):
    alt = formular(fid)
    titel = text(d, "titel", "Titel", 160) if "titel" in d else alt["title"]
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
    f = formular(fid)
    if not punkte(fid):
        raise Abgelehnt("Ein Formular ohne Prüfpunkte lässt sich nicht aktivieren.")
    spalte, ziel = ("category_id", f["category_id"]) if f["category_id"] else ("product_id", f["product_id"])
    with db.transaction(sofort=True):
        for anderes in db.query(f"SELECT id FROM mat_form WHERE {spalte} = ? AND active = 1 AND id <> ?", (ziel, fid)):
            db.execute("UPDATE mat_form SET active = 0, updated_at = ? WHERE id = ?", (db.now(), anderes["id"]))
            journal.eintragen("form", anderes["id"], "deaktiviert", {"active": 1}, {"active": 0, "ersetzt_durch": fid})
        db.execute("UPDATE mat_form SET active = 1, valid_from = COALESCE(valid_from, ?), updated_at = ? WHERE id = ?",
                   (heute().isoformat(), db.now(), fid))
        journal.eintragen("form", fid, "aktiviert", {"active": f["active"]}, {"active": 1})


def formular_deaktivieren(fid):
    f = formular(fid)
    if not f["active"]:
        return
    with db.transaction():
        db.execute("UPDATE mat_form SET active = 0, updated_at = ? WHERE id = ?", (db.now(), fid))
        journal.eintragen("form", fid, "deaktiviert", {"active": 1}, {"active": 0})


def formular_loeschen(fid):
    with db.transaction(sofort=True):
        f = formular(fid)
        if ist_benutzt(fid):
            raise Abgelehnt(FORMULAR_BENUTZT, 409)
        if f["active"]:
            raise Abgelehnt("Das aktive Formular lässt sich nicht löschen – erst eine andere Version aktivieren "
                            "oder dieses deaktivieren.", 409)
        db.execute("DELETE FROM mat_form WHERE id = ?", (fid,))
        journal.eintragen("form", fid, "geloescht", {"title": f["title"], "version": f["version"]}, None)


def formular_fuer_produkt(pid):
    """Das Formular, nach dem ein Artikel dieses Produkts geprüft wird: das aktive spezifische des
    Produkts, sonst das aktive generische der Kategorie – oder der nächsten Oberkategorie mit einem."""
    p = produkt(pid)
    f = db.query("SELECT * FROM mat_form WHERE product_id = ? AND active = 1", (pid,), one=True)
    if f:
        f["quelle"] = "Produkt"
    else:
        for k in reversed(kategorie_pfad(p["category_id"])):
            f = db.query("SELECT * FROM mat_form WHERE category_id = ? AND active = 1", (k["id"],), one=True)
            if f:
                f["quelle"] = f"Kategorie „{k['name']}“"
                break
    if f:
        f["punkte_anzahl"] = db.query("SELECT COUNT(*) AS n FROM mat_checklist_item WHERE form_id = ?",
                                      (f["id"],), one=True)["n"]
    return f


def formular_json(f, mit_punkten=True):
    out = {"id": f["id"], "kategorie_id": f["category_id"], "produkt_id": f["product_id"], "version": f["version"],
           "titel": f["title"], "gueltig_ab": f["valid_from"], "aktiv": bool(f["active"]), "demo": bool(f["demo"]),
           "created_at": f["created_at"], "updated_at": f["updated_at"], "benutzt": ist_benutzt(f["id"])}
    out["aenderbar"] = not out["benutzt"]
    if f["category_id"]:
        out["ziel"] = {"art": "kategorie", "id": f["category_id"], "pfad": kategorie_pfad(f["category_id"])}
    else:
        p = db.query("SELECT id, manufacturer, model, description, article_no, category_id FROM mat_product WHERE id = ?",
                     (f["product_id"],), one=True)
        out["ziel"] = {"art": "produkt", "id": f["product_id"], "kategorie_id": p["category_id"] if p else None,
                       "name": produktname(p) if p else "?"}
    if mit_punkten:
        out["punkte"] = [punkt_json(p) for p in punkte(f["id"])]
    # Prüfanleitung aus dem Wiki (Phase 2 · L3): nur für die Material-Verwaltung; wiki_aendern: darf sie ändern (dazu
    # gehört die Stufe Mitglied im Wiki).
    from . import wikiverweis
    from .rechte import ist_material_verwaltung
    mv = has_request_context() and ist_material_verwaltung()
    out["wiki"] = wikiverweis.editor_json(f.get("wiki_page_id")) if mv else None
    out["wiki_aendern"] = bool(mv and wikiverweis.darf_verknuepfen())
    return out


def formulare_fuer(kategorie_id=None, produkt_id=None):
    spalte, ziel = ("category_id", kategorie_id) if kategorie_id else ("product_id", produkt_id)
    rows = db.query(f"SELECT * FROM mat_form WHERE {spalte} = ? ORDER BY version DESC", (ziel,))
    out = []
    for f in rows:
        j = formular_json(f, mit_punkten=False)
        j["punkte_anzahl"] = db.query("SELECT COUNT(*) AS n FROM mat_checklist_item WHERE form_id = ?",
                                      (f["id"],), one=True)["n"]
        out.append(j)
    return out


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
