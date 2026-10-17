"""Katalog: Kategorien, Produkte, Produktdokumente und Prüfformulare.

Pflegen dürfen ihn nur Admins und Produktkatalogpfleger (routes.py prüft das an jeder Route). Die
Regeln stehen hier, weil der Katalogimport (importer.py) dieselben braucht wie die Oberfläche.

Fachliche Grenzen aus dem Konzept:
  - Dublette = Hersteller + Modell + Artikelnummer (vereinheitlicht, siehe dedupe_key).
  - Lebensdauer: Pflicht bei textilem Material, verboten bei Metall/Hardware, bei „sonstiges“ nur mit
    Herstellerangabe (Fundstelle).
  - Formulare: je Kategorie ein generisches, je Produkt optional ein spezifisches, das das generische
    ersetzt. Versioniert; eine benutzte Version wird nie mehr geändert, sondern durch eine neue ersetzt.
  - Fotos und Herstellerdokumente hängen am Produkt, nie am einzelnen Artikel.
"""
import hashlib
import os
import re
import secrets
import sqlite3

from flask import current_app

from ... import db
from ...images import ALLOWED_EXT, delete_photo_files, store_upload
from ..models import DOKUMENTARTEN, EDITOREN, MATERIALARTEN
from . import Abgelehnt, akteur, auswahl, datum, ganzzahl, heute, kennung, text, wahr
from . import faelligkeit, journal
from .interval import herstellerseite, lebensende

FORMULAR_BENUTZT = ("Diese Formularversion wurde schon für Prüfungen benutzt und bleibt deshalb unverändert. "
                    "Lege eine neue Version an.")
LEBENSDAUER_TEXTIL = "Bei textilem Material ist die Lebensdauer Pflicht (Herstellerangabe in Jahren)."
LEBENSDAUER_METALL = "Metall und Hardware haben keine festgeschriebene Lebensdauer – das Feld bleibt leer."
LEBENSDAUER_SONSTIGES = "Bei „sonstiges“ gibt es eine Lebensdauer nur mit Herstellerangabe (Fundstelle angeben)."
KEIN_INTERVALL = "Kein Prüfintervall: am Produkt angeben oder in der Kategorie als Vorgabe hinterlegen."

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
                    "default_lifetime_years", "position")


def kategorie(kid):
    k = db.query("SELECT * FROM mat_category WHERE id = ?", (kid,), one=True)
    if not k:
        raise Abgelehnt("Kategorie nicht gefunden.", 404)
    return k


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
            "default_lifetime_years, position, demo, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (w["parent_id"], w["name"], w["norm"], w["default_material_kind"], w["default_interval_months"],
             w["default_lifetime_years"], w["position"], int(bool(demo)), ts, ts))
        journal.eintragen("category", kid, "angelegt", None, w)
    return kid


def kategorie_aendern(kid, d):
    # Prüfen und Schreiben unter einer Schreibsperre: Zwei gleichzeitige Umhängungen ergäben sonst
    # einen Zyklus.
    with db.transaction(sofort=True):
        alt = kategorie(kid)
        w = kategorie_werte(d, alt)
        db.execute("UPDATE mat_category SET parent_id = ?, name = ?, norm = ?, default_material_kind = ?, "
                   "default_interval_months = ?, default_lifetime_years = ?, position = ?, updated_at = ? WHERE id = ?",
                   (w["parent_id"], w["name"], w["norm"], w["default_material_kind"], w["default_interval_months"],
                    w["default_lifetime_years"], w["position"], db.now(), kid))
        # Produkte ohne eigenes Intervall erben es aus der Kategorie. Fiele es durch die Änderung weg,
        # hätte ein Produkt keins mehr – das darf es so wenig wie beim Anlegen.
        ohne = [f"{p['manufacturer']} {p['model']}" for p in db.query(
            "SELECT * FROM mat_product WHERE category_id IN (WITH RECURSIVE baum(id) AS (SELECT ? UNION "
            "SELECT c.id FROM mat_category c JOIN baum b ON c.parent_id = b.id) SELECT id FROM baum)", (kid,))
            if herstellerseite(p)[0] is None]
        if ohne:
            raise Abgelehnt("Danach hätten diese Produkte kein Prüfintervall mehr: " + ", ".join(ohne[:5])
                            + (" …" if len(ohne) > 5 else "") + ". Erst am Produkt ein Intervall eintragen.", 409)
        journal.aenderung("category", kid, alt, w)
        if (w["default_interval_months"], w["parent_id"]) != (alt["default_interval_months"], alt["parent_id"]):
            faelligkeit.kappen(*faelligkeit.in_kategorie(kid))
    return kid


def kategorie_loeschen(kid):
    alt = kategorie(kid)
    if db.query("SELECT 1 FROM mat_category WHERE parent_id = ? LIMIT 1", (kid,), one=True):
        raise Abgelehnt("Die Kategorie hat Unterkategorien – erst diese verschieben oder löschen.", 409)
    if db.query("SELECT 1 FROM mat_product WHERE category_id = ? LIMIT 1", (kid,), one=True):
        raise Abgelehnt("In der Kategorie stehen noch Produkte.", 409)
    if db.query("SELECT 1 FROM mat_inspection i JOIN mat_form f ON f.id = i.form_id WHERE f.category_id = ? LIMIT 1",
                (kid,), one=True):
        raise Abgelehnt("Ein Formular dieser Kategorie wurde schon für Prüfungen benutzt.", 409)
    with db.transaction():
        for f in db.query("SELECT id FROM mat_form WHERE category_id = ?", (kid,)):
            db.execute("DELETE FROM mat_form WHERE id = ?", (f["id"],))
            journal.eintragen("form", f["id"], "geloescht", {"kategorie": alt["name"]}, None)
        db.execute("DELETE FROM mat_category WHERE id = ?", (kid,))
        journal.eintragen("category", kid, "geloescht", alt, None)


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


def produkt_werte(d, alt=None):
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
        "description": text(e, "description", "Beschreibung", 4000, einzeilig=False),
    }
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
    andere = db.query("SELECT id, manufacturer, model, article_no FROM mat_product WHERE dedupe_key = ?", (key,), one=True)
    if andere and andere["id"] != ausser:
        nr = f" ({andere['article_no']})" if andere["article_no"] else ""
        raise Abgelehnt(f"Dieses Produkt steht schon im Katalog: {andere['manufacturer']} {andere['model']}{nr}.", 409)


def produkt_anlegen(d, demo=False):
    w = produkt_werte(d)
    key = dedupe_key(w["manufacturer"], w["model"], w["article_no"])
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        _dublette_pruefen(key)
        try:
            pid = db.execute(
                "INSERT INTO mat_product (category_id, manufacturer, model, article_no, dedupe_key, norm, material_kind, "
                "interval_months, lifetime_years, lifetime_source, description, demo, created_by, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w["category_id"], w["manufacturer"], w["model"], w["article_no"], key, w["norm"], w["material_kind"],
                 w["interval_months"], w["lifetime_years"], w["lifetime_source"], w["description"], int(bool(demo)),
                 uid, ts, ts))
        except sqlite3.IntegrityError:
            raise Abgelehnt("Dieses Produkt steht schon im Katalog.", 409)
        journal.eintragen("product", pid, "angelegt", None, w)
    return pid


def produkt_aendern(pid, d):
    alt = produkt(pid)
    w = produkt_werte(d, alt)
    key = dedupe_key(w["manufacturer"], w["model"], w["article_no"])
    artikel = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ?", (pid,), one=True)["n"]
    if artikel and w["material_kind"] != alt["material_kind"]:
        raise Abgelehnt("Die Materialart lässt sich nur ändern, solange es keine Artikel dieses Produkts gibt – "
                        "an ihr hängen Lebensdauer und Aussonderung.", 409)
    with db.transaction(sofort=True):
        _dublette_pruefen(key, ausser=pid)
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
    alt = produkt(pid)
    if db.query("SELECT 1 FROM mat_item WHERE product_id = ? LIMIT 1", (pid,), one=True):
        raise Abgelehnt("Von diesem Produkt gibt es Artikel – es bleibt im Katalog.", 409)
    dateien = [r["file_path"] for r in db.query(
        "SELECT file_path FROM mat_product_document WHERE product_id = ? AND file_path IS NOT NULL", (pid,))]
    with db.transaction():
        for f in db.query("SELECT id FROM mat_form WHERE product_id = ?", (pid,)):
            journal.eintragen("form", f["id"], "geloescht", {"produkt": pid}, None)
        db.execute("DELETE FROM mat_form WHERE product_id = ?", (pid,))
        db.execute("DELETE FROM mat_product WHERE id = ?", (pid,))
        journal.eintragen("product", pid, "geloescht", alt, None)
    for name in dateien:
        _entfernen(os.path.join(dok_dir(), name))
    if alt["image"]:
        delete_photo_files(medien_dir(), alt["image"])


def _entfernen(pfad):
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
    if "category_name" in p:
        out["category_name"] = p["category_name"]
    if "bestand" in p:
        out["bestand"] = p["bestand"]
    if voll:
        out["kategorie_pfad"] = kategorie_pfad(p["category_id"])
        out["bestand"] = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ? AND lock_state <> 'ausgesondert'",
                                  (p["id"],), one=True)["n"]
        out["artikel_gesamt"] = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ?", (p["id"],),
                                         one=True)["n"]
        out["dokumente"] = dokumente(p["id"])
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


def _datei_ablegen(file_storage):
    """Datei unverändert unter media/material/dok ablegen; liefert (Name, MIME, Größe, SHA-256)."""
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
    name = secrets.token_hex(10) + ext
    pfad = os.path.join(dok_dir(), name)
    summe, groesse = hashlib.sha256(), 0
    try:
        with open(pfad, "wb") as fh:
            stueck = kopf
            while stueck:
                groesse += len(stueck)
                if groesse > DOK_MAX_BYTES:
                    raise Abgelehnt(f"Das Dokument ist größer als {DOK_MAX_BYTES // (1024 * 1024)} MB.", 413)
                summe.update(stueck)
                fh.write(stueck)
                stueck = stream.read(1024 * 1024)
    except Abgelehnt:
        _entfernen(pfad)
        raise
    except OSError as exc:
        _entfernen(pfad)
        current_app.logger.warning("Dokument „%s“ ließ sich nicht ablegen: %s", file_storage.filename, exc)
        raise Abgelehnt("Das Dokument ließ sich nicht speichern. Bitte später erneut versuchen.", 500)
    return name, mime, groesse, summe.hexdigest()


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


def dokument_anlegen(pid, d, datei=None, ersetzt=None):
    """Ein Dokument am Produkt – oder, mit ersetzt, die neue Version eines vorhandenen."""
    produkt(pid)
    w = _dokument_werte(d, ersetzt, datei)
    name = mime = sha = None
    groesse = 0
    if datei:
        name, mime, groesse, sha = _datei_ablegen(datei)
    uid, uname = akteur()
    try:
        with db.transaction(sofort=True):
            if ersetzt and db.query("SELECT 1 FROM mat_product_document WHERE replaces_id = ? LIMIT 1",
                                    (ersetzt["id"],), one=True):
                raise Abgelehnt("Zu diesem Dokument gibt es schon eine neuere Version – bitte diese ersetzen.", 409)
            did = db.execute(
                "INSERT INTO mat_product_document (product_id, kind, title, file_path, url, mime, size, sha256, version, "
                "valid_from, replaces_id, uploaded_by, uploaded_by_name, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, w["kind"], w["title"], name, w["url"], mime or "", groesse, sha or "", w["version"],
                 w["valid_from"], ersetzt["id"] if ersetzt else None, uid, uname, db.now()))
            nachher = dict(w, file_path=name, sha256=sha, size=groesse, product_id=pid)
            journal.eintragen("document", did, "neue_version" if ersetzt else "angelegt",
                              {"ersetzt": ersetzt["id"]} if ersetzt else None, nachher)
    except BaseException:
        if name:
            _entfernen(os.path.join(dok_dir(), name))
        raise
    return did


def dokument_neue_version(did, d, datei=None):
    alt = dokument(did)
    if db.query("SELECT 1 FROM mat_product_document WHERE replaces_id = ? LIMIT 1", (did,), one=True):
        raise Abgelehnt("Zu diesem Dokument gibt es schon eine neuere Version – bitte diese ersetzen.", 409)
    return dokument_anlegen(alt["product_id"], d, datei, ersetzt=alt)


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


def dokumente(pid, stichtag=None):
    stichtag = stichtag or heute().isoformat()
    docs = db.query("SELECT * FROM mat_product_document WHERE product_id = ? ORDER BY valid_from DESC, id DESC", (pid,))
    out = []
    for doc in docs:
        out.append({"id": doc["id"], "kind": doc["kind"], "title": doc["title"], "version": doc["version"],
                    "valid_from": doc["valid_from"], "withdrawn_on": doc["withdrawn_on"], "url": doc["url"],
                    "datei": f"/media/material/dok/{doc['file_path']}" if doc["file_path"] else None,
                    "mime": doc["mime"], "size": doc["size"], "sha256": doc["sha256"],
                    "replaces_id": doc["replaces_id"], "uploaded_by_name": doc["uploaded_by_name"],
                    "uploaded_at": doc["uploaded_at"],
                    "abgeloest_durch": next((n["id"] for n in docs if n["replaces_id"] == doc["id"]), None),
                    "gilt": _gilt(doc, docs, stichtag)})
    return out


def gueltige_dokumente(pid, stichtag):
    """Die am Stichtag gültigen Dokumente – so verweist ein Protokoll auf den damaligen Stand."""
    return [d for d in dokumente(pid, stichtag) if d["gilt"]]


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
        soll = text(p, "soll", f"Sollwert von Prüfpunkt {n}", 60)
        if art == "yesno":
            soll = soll.lower()
            if soll not in ("ja", "nein"):
                raise Abgelehnt(f"Prüfpunkt {n} (Ja/Nein) braucht den Sollwert „ja“ oder „nein“.")
        elif art in ("photo", "signature", "date"):
            soll = ""
        kritisch = wahr(p, "kritisch", f"kritisch (Prüfpunkt {n})")
        if kritisch and art != "yesno":
            raise Abgelehnt(f"Prüfpunkt {n}: Kritisch kann nur ein Ja/Nein-Punkt sein – er hat einen Sollwert, "
                            "an dem sich ein Mangel festmachen lässt.")
        out.append({"group_name": text(p, "gruppe", f"Gruppe von Prüfpunkt {n}", 80),
                    "label": text(p, "text", f"Text von Prüfpunkt {n}", 300, pflicht=True),
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
    übernimmt sie die Prüfpunkte der letzten Version desselben Ziels – der Normalfall ist „ändern“."""
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
        fid = db.execute(f"INSERT INTO mat_form ({spalte}, version, title, active, demo, created_by, created_at, updated_at) "
                         "VALUES (?,?,?,0,?,?,?,?)", (ziel, version, titel, int(bool(demo)), uid, ts, ts))
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
    if ist_benutzt(fid):
        raise Abgelehnt(FORMULAR_BENUTZT, 409)
    titel = text(d, "titel", "Titel", 160) if "titel" in d else alt["title"]
    alte_punkte = [dict(p) for p in punkte(fid)]
    liste = punkte_pruefen(d.get("punkte")) if "punkte" in d else alte_punkte
    if alt["active"] and not liste:
        raise Abgelehnt("Ein aktives Formular braucht mindestens einen Prüfpunkt.")
    with db.transaction():
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
    f = formular(fid)
    if ist_benutzt(fid):
        raise Abgelehnt(FORMULAR_BENUTZT, 409)
    if f["active"]:
        raise Abgelehnt("Das aktive Formular lässt sich nicht löschen – erst eine andere Version aktivieren "
                        "oder dieses deaktivieren.", 409)
    with db.transaction():
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
        p = db.query("SELECT id, manufacturer, model, article_no FROM mat_product WHERE id = ?", (f["product_id"],), one=True)
        out["ziel"] = {"art": "produkt", "id": f["product_id"],
                       "name": f"{p['manufacturer']} {p['model']}" if p else "?"}
    if mit_punkten:
        out["punkte"] = [punkt_json(p) for p in punkte(f["id"])]
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
