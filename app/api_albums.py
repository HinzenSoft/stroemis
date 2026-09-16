"""Alben, Bilder und Kartendaten."""
import http.client
import json
import math
import os
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from . import db
from .auth import current_user, darf_inhalte, eingabefehler_abfangen, is_admin, json_body, login_required
from .images import delete_photo_files, store_upload

bp = Blueprint("albums", __name__, url_prefix="/api")
eingabefehler_abfangen(bp)

CATEGORIES = ("seil", "wasser", "sonstiges")
ALBUM_FIELDS = ("title", "category", "description", "contact_name", "contact_org",
                "contact_phone", "contact_email", "contact_notes")
# Ein Album, dessen Bilder im Mittel näher liegen als das, ist "in der Nähe": Wer dort Bilder
# einwirft, wird gefragt, ob sie nicht dorthin gehören. Zwei Kilometer fassen ein Übungsgewässer
# samt Zufahrt, ohne dass die nächste Stadt schon dazuzählt.
NAHE_M = 2000


def _abstand_m(lat1, lon1, lat2, lon2):
    """Großkreisabstand in Metern (Haversine) – auf zwei Kilometer kommt es auf Meter nicht an."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --- Adresssuche -------------------------------------------------------------
# Der Browser darf den Kartendienst nicht selbst fragen: Die CSP lässt nur Verbindungen zur
# eigenen Adresse zu (connect-src 'self'), und der Dienst erführe sonst die IP jedes Mitglieds
# samt gesuchter Adresse. Also fragt der Server – einmal, und merkt sich die Antwort.
_geo_sperre = threading.Lock()
_geo_zuletzt = [0.0]                      # Zeitpunkt der letzten Anfrage nach außen
_geo_merker = {}                          # Suchwort -> (Zeitpunkt, Treffer)
GEO_ABSTAND_SEK = 1.1                     # Nominatim erlaubt höchstens eine Anfrage je Sekunde
GEO_MERKER_SEK = 60 * 60
GEO_MERKER_MAX = 200


def _key(file):
    return os.path.splitext(file)[0]


def photo_json(p):
    key = _key(p["file"])
    out = {k: p[k] for k in ("id", "album_id", "owner_id", "original_name", "width", "height", "lat", "lon",
                             "altitude", "geo_source", "taken_at", "title", "note", "height_m", "details",
                             "sort", "created_at", "kind")}
    out["thumb"] = f"/media/thumb/{key}.jpg"
    out["web"] = f"/media/web/{key}.jpg"
    out["orig"] = f"/media/orig/{p['file']}"
    return out


def album_json(a, photos):
    out = dict(a)
    out["photos"] = [photo_json(p) for p in photos]
    located = [p for p in photos if p["lat"] is not None]
    out["photo_count"] = len(photos)
    out["unlocated_count"] = len(photos) - len(located)
    if located:
        out["lat"] = sum(p["lat"] for p in located) / len(located)
        out["lon"] = sum(p["lon"] for p in located) / len(located)
    else:
        out["lat"] = out["lon"] = None
    return out


def can_edit(owner_id):
    """Ein Album führt, wer es angelegt hat – dazu Administratoren und Redakteure."""
    u = current_user()
    return darf_inhalte(u) or u["id"] == owner_id


def can_edit_photo(p):
    """Ein Bild darf ändern, wer es hochgeladen hat – und wer das Album führt, in dem es liegt.
    (Der Albumbesitzer kann ohnehin das ganze Album samt Bildern löschen.)"""
    if can_edit(p["owner_id"]):
        return True
    a = db.query("SELECT owner_id FROM albums WHERE id = ?", (p["album_id"],), one=True)
    return bool(a and can_edit(a["owner_id"]))


def _get_album(aid):
    return db.query(
        "SELECT a.*, u.name AS owner_name, u.gliederung AS owner_gliederung "
        "FROM albums a JOIN users u ON u.id = a.owner_id WHERE a.id = ?", (aid,), one=True)


def _album_photos(aid):
    return db.query("SELECT * FROM photos WHERE album_id = ? ORDER BY sort, taken_at, id", (aid,))


def _clean_album(d, existing=None):
    vals = {}
    for f in ALBUM_FIELDS:
        if existing is None or f in d:
            v = d.get(f)
            vals[f] = str(v).strip() if v is not None else ""
    if "category" in vals and vals["category"] not in CATEGORIES:
        vals["category"] = "sonstiges"
    if existing is None and not vals.get("title"):
        raise ValueError("Bitte einen Titel für das Album angeben.")
    if "title" in vals and not vals["title"]:
        raise ValueError("Der Titel darf nicht leer sein.")
    return vals


# --- Karte -------------------------------------------------------------------

@bp.get("/map")
@login_required
def map_data():
    rows = db.query(
        "SELECT p.id, p.album_id, p.file, p.lat, p.lon, p.title, p.kind, a.title AS album_title, a.category, "
        "       (p.id = a.cover_photo_id) AS ist_deckblatt "
        "FROM photos p JOIN albums a ON a.id = p.album_id WHERE p.lat IS NOT NULL AND p.lon IS NOT NULL")
    return jsonify(photos=[{
        "id": r["id"], "album_id": r["album_id"], "lat": r["lat"], "lon": r["lon"],
        "title": r["title"], "album_title": r["album_title"], "category": r["category"], "kind": r["kind"],
        # Das Deckblatt liegt im Bilderstapel eines Haufens obenauf.
        "cover": bool(r["ist_deckblatt"]),
        "thumb": f"/media/thumb/{_key(r['file'])}.jpg"} for r in rows])


def _kennung():
    """Erkennbare Kennung für fremde Dienste – rein in ASCII.

    HTTP-Kopfzeilen vertragen nur ASCII. Der Seitenname trägt aber ein „ö“, und manche Dienste
    weisen eine Anfrage mit einem Umlaut im User-Agent rundheraus ab (gemessen: HTTP 403).
    Umlaute werden deshalb ausgeschrieben, alles Übrige fällt weg."""
    cfg = current_app.config
    roh = f"{cfg.get('SITE_NAME', 'wiki')} ({cfg.get('BASE_URL', '')})"
    for zeichen, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"),
                            ("Ü", "Ue"), ("ß", "ss")):
        roh = roh.replace(zeichen, ersatz)
    return unicodedata.normalize("NFKD", roh).encode("ascii", "ignore").decode("ascii").strip() or "wiki"
@bp.get("/geocode")
@login_required
def geocode():
    """Adresse oder Ortsname zu Koordinaten – zum Anfahren der Stelle beim Platzieren von Bildern."""
    dienst = current_app.config.get("GEOCODE_URL")
    if not dienst:
        return jsonify(error="Die Adresssuche ist nicht eingerichtet."), 501
    frage = (request.args.get("q") or "").strip()
    if len(frage) < 3:
        return jsonify(results=[])
    frage = frage[:120]

    jetzt = time.time()
    with _geo_sperre:
        merk = _geo_merker.get(frage.lower())
        if merk and jetzt - merk[0] < GEO_MERKER_SEK:
            return jsonify(results=merk[1])
        # Der Dienst verträgt eine Anfrage je Sekunde. Wer schneller tippt, wartet kurz –
        # das ist immer noch freundlicher, als abgewiesen zu werden.
        warten = GEO_ABSTAND_SEK - (jetzt - _geo_zuletzt[0])
        if warten > 0:
            time.sleep(min(warten, GEO_ABSTAND_SEK))
        _geo_zuletzt[0] = time.time()

    ziel = dienst + "?" + urllib.parse.urlencode({
        "q": frage, "format": "jsonv2", "limit": "5", "accept-language": "de"})
    # Nominatim verlangt eine erkennbare Kennung mit Kontakt; ohne sie wird gesperrt.
    kennung = _kennung()
    try:
        anfrage = urllib.request.Request(ziel, headers={"User-Agent": kennung})
        with urllib.request.urlopen(anfrage, timeout=6) as antwort:
            roh = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        # OSError deckt Zeitüberschreitung und abgerissene Verbindung ab, HTTPException den vom
        # Dienst geschlossenen Socket (RemoteDisconnected) – beides kam ohne URLError-Hülle.
        current_app.logger.warning("Adresssuche fehlgeschlagen: %s", exc)
        return jsonify(error="Die Adresssuche ist gerade nicht erreichbar."), 503

    treffer = []
    for eintrag in roh if isinstance(roh, list) else []:
        try:
            treffer.append({"name": str(eintrag.get("display_name", ""))[:200],
                            "lat": float(eintrag["lat"]), "lon": float(eintrag["lon"])})
        except (KeyError, TypeError, ValueError):
            continue
    with _geo_sperre:
        if len(_geo_merker) > GEO_MERKER_MAX:
            _geo_merker.clear()
        _geo_merker[frage.lower()] = (time.time(), treffer)
    return jsonify(results=treffer)


# --- Alben -------------------------------------------------------------------

@bp.get("/albums")
@login_required
def list_albums():
    rows = db.query(
        "SELECT a.*, u.name AS owner_name, "
        "  (SELECT COUNT(*) FROM photos p WHERE p.album_id = a.id) AS photo_count, "
        "  (SELECT COUNT(*) FROM photos p WHERE p.album_id = a.id AND p.lat IS NULL) AS unlocated_count, "
        "  (SELECT AVG(lat) FROM photos p WHERE p.album_id = a.id) AS lat, "
        "  (SELECT AVG(lon) FROM photos p WHERE p.album_id = a.id) AS lon, "
        # Erst das gewählte Deckblatt, sonst das erste Bild der Sortierung – so hat jedes Album
        # ein Titelbild. Zwei getrennte Unterabfragen, weil SQLite einen Verweis nach außen
        # (a.cover_photo_id) in der ORDER BY einer Unterabfrage nicht auflöst.
        "  COALESCE("
        "    (SELECT p.file FROM photos p WHERE p.id = a.cover_photo_id AND p.album_id = a.id), "
        "    (SELECT p.file FROM photos p WHERE p.album_id = a.id ORDER BY p.sort, p.id LIMIT 1)) AS cover "
        "FROM albums a JOIN users u ON u.id = a.owner_id ORDER BY a.updated_at DESC")
    for r in rows:
        r["cover"] = f"/media/thumb/{_key(r['cover'])}.jpg" if r["cover"] else None
    return jsonify(albums=rows)


@bp.post("/albums")
@login_required
def create_album():
    try:
        vals = _clean_album(json_body())
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    ts = db.now()
    aid = db.execute(
        "INSERT INTO albums (title, category, description, contact_name, contact_org, contact_phone, "
        "contact_email, contact_notes, owner_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (vals["title"], vals["category"], vals["description"], vals["contact_name"], vals["contact_org"],
         vals["contact_phone"], vals["contact_email"], vals["contact_notes"], current_user()["id"], ts, ts))
    return jsonify(album=album_json(_get_album(aid), [])), 201


@bp.get("/albums/<int:aid>")
@login_required
def get_album(aid):
    a = _get_album(aid)
    if not a:
        return jsonify(error="Album nicht gefunden"), 404
    out = album_json(a, _album_photos(aid))
    out["can_edit"] = can_edit(a["owner_id"])
    return jsonify(album=out)


@bp.put("/albums/<int:aid>/cover")
@login_required
def set_album_cover(aid):
    """Deckblatt des Albums festlegen – oder mit photo_id null wieder dem ersten Bild überlassen."""
    a = _get_album(aid)
    if not a:
        return jsonify(error="Album nicht gefunden"), 404
    if not can_edit(a["owner_id"]):
        return jsonify(error="Keine Berechtigung"), 403
    pid = json_body().get("photo_id")
    if pid is not None:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return jsonify(error="Ungültiges Bild"), 400
        # Nur Bilder aus diesem Album: sonst zeigte das Deckblatt auf ein fremdes, womöglich
        # gar nicht sichtbares Album.
        if not db.query("SELECT 1 FROM photos WHERE id = ? AND album_id = ?", (pid, aid), one=True):
            return jsonify(error="Dieses Bild gehört nicht zum Album."), 400
    db.execute("UPDATE albums SET cover_photo_id = ?, updated_at = ? WHERE id = ?", (pid, db.now(), aid))
    return jsonify(ok=True, cover_photo_id=pid)


@bp.put("/albums/<int:aid>")
@login_required
def update_album(aid):
    a = _get_album(aid)
    if not a:
        return jsonify(error="Album nicht gefunden"), 404
    if not can_edit(a["owner_id"]):
        return jsonify(error="Keine Berechtigung"), 403
    try:
        vals = _clean_album(json_body(), existing=a)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals) + ", updated_at = ?"
        db.execute(f"UPDATE albums SET {sets} WHERE id = ?", (*vals.values(), db.now(), aid))
    out = album_json(_get_album(aid), _album_photos(aid))
    out["can_edit"] = True
    return jsonify(album=out)


@bp.delete("/albums/<int:aid>")
@login_required
def delete_album(aid):
    a = _get_album(aid)
    if not a:
        return jsonify(error="Album nicht gefunden"), 404
    if not can_edit(a["owner_id"]):
        return jsonify(error="Keine Berechtigung"), 403
    photos = _album_photos(aid)
    with db.transaction():
        db.execute("DELETE FROM albums WHERE id = ?", (aid,))
    # Dateien erst löschen, wenn die Zeilen wirklich weg sind – sonst bliebe ein Album voller kaputter Bilder
    for p in photos:
        delete_photo_files(current_app.config["MEDIA_DIR"], p["file"])
    return jsonify(ok=True)


# --- Bilder ------------------------------------------------------------------

def _bilder_ablegen(aid, files, posters):
    """Die Dateien eines Hochladevorgangs verarbeiten und dem Album anhängen.
    Liefert (angelegte Bilder als JSON, Fehlermeldungen je gescheiterter Datei)."""
    created, errors = [], []
    ts = db.now()
    sort_base = (db.query("SELECT COALESCE(MAX(sort), 0) AS m FROM photos WHERE album_id = ?", (aid,), one=True)["m"]) + 1
    for i, f in enumerate(files):
        try:
            # Standbilder zu Videos, vom Browser erzeugt (gleiche Reihenfolge wie die Dateien)
            poster = posters[i] if i < len(posters) and posters[i].filename else None
            meta = store_upload(f, current_app.config["MEDIA_DIR"], poster=poster)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        except Exception as exc:
            # Eine kaputte Datei darf den ganzen Hochladevorgang nicht abbrechen.
            current_app.logger.exception("Upload von %s fehlgeschlagen", f.filename)
            errors.append(f"Die Datei „{f.filename or '?'}“ konnte nicht verarbeitet werden ({exc}).")
            continue
        pid = db.execute(
            "INSERT INTO photos (album_id, owner_id, file, original_name, width, height, lat, lon, altitude, "
            "geo_source, taken_at, sort, created_at, kind) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, current_user()["id"], meta["file"], meta["original_name"], meta["width"], meta["height"],
             meta["lat"], meta["lon"], meta["altitude"], "exif" if meta["lat"] is not None else None,
             meta["taken_at"], sort_base + i, ts, meta["kind"]))
        neu = db.query("SELECT * FROM photos WHERE id = ?", (pid,), one=True)
        created.append(photo_json(neu))
    db.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (ts, aid))
    return created, errors


@bp.post("/albums/<int:aid>/photos")
@login_required
def upload_photos(aid):
    a = _get_album(aid)
    if not a:
        return jsonify(error="Album nicht gefunden"), 404
    if not can_edit(a["owner_id"]):
        return jsonify(error="Keine Berechtigung"), 403
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="Keine Dateien empfangen."), 400
    created, errors = _bilder_ablegen(aid, files, request.files.getlist("posters"))
    return jsonify(photos=created, unlocated=[p["id"] for p in created if p["lat"] is None], errors=errors), 201


def _alben_in_der_naehe(lat, lon, ausser):
    """Alben, deren Bildmittelpunkt höchstens NAHE_M von (lat, lon) entfernt liegt – nächstes zuerst.
    Die Bildmittel rechnet die Datenbank, den Abstand Python: Alben sind wenige, Bilder viele."""
    rows = db.query(
        "SELECT a.id, a.title, a.category, u.name AS owner_name, a.owner_id, "
        "  AVG(p.lat) AS lat, AVG(p.lon) AS lon, COUNT(*) AS photo_count "
        "FROM albums a JOIN users u ON u.id = a.owner_id "
        "JOIN photos p ON p.album_id = a.id AND p.lat IS NOT NULL "
        "WHERE a.id != ? GROUP BY a.id", (ausser,))
    nahe = []
    for r in rows:
        d = _abstand_m(lat, lon, r["lat"], r["lon"])
        if d <= NAHE_M:
            nahe.append({"id": r["id"], "title": r["title"], "category": r["category"],
                         "owner_name": r["owner_name"], "photo_count": r["photo_count"],
                         "abstand_m": round(d), "can_edit": can_edit(r["owner_id"])})
    nahe.sort(key=lambda n: n["abstand_m"])
    return nahe


@bp.post("/albums/einwurf")
@login_required
def einwurf():
    """Dateien, die auf die Karte gezogen wurden: Sie werden zu einem neuen Album. Liegt der
    Mittelpunkt ihrer Geotags nahe an einem vorhandenen Album, sagt die Antwort das – und der
    Browser fragt, ob die Bilder nicht dorthin gehören (dann: zusammenlegen).
    Das neue Album entsteht in jedem Fall zuerst: Die Geotags kennt der Server erst, wenn die
    Dateien verarbeitet sind, und verarbeitete Bilder brauchen ein Album. Es ist die Antwort auf
    „neues Album“, und beim Zusammenlegen löst es sich wieder auf."""
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="Keine Dateien empfangen."), 400
    try:
        vals = _clean_album({"title": request.form.get("title"), "category": request.form.get("category")})
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    ts = db.now()
    aid = db.execute(
        "INSERT INTO albums (title, category, description, contact_name, contact_org, contact_phone, "
        "contact_email, contact_notes, owner_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (vals["title"], vals["category"], "", "", "", "", "", "", current_user()["id"], ts, ts))
    created, errors = _bilder_ablegen(aid, files, request.files.getlist("posters"))
    if not created:
        # Kein einziges brauchbares Bild: Ein leeres Album bliebe als Leiche in der Liste stehen.
        db.execute("DELETE FROM albums WHERE id = ?", (aid,))
        return jsonify(error=" ".join(errors) or "Keine der Dateien ließ sich verarbeiten.", errors=errors), 400
    verortet = [p for p in created if p["lat"] is not None]
    nahe = []
    if verortet:
        lat = sum(p["lat"] for p in verortet) / len(verortet)
        lon = sum(p["lon"] for p in verortet) / len(verortet)
        nahe = _alben_in_der_naehe(lat, lon, ausser=aid)
    out = album_json(_get_album(aid), _album_photos(aid))
    out["can_edit"] = True
    return jsonify(album=out, photos=created, unlocated=[p["id"] for p in created if p["lat"] is None],
                   errors=errors, nahe=nahe), 201


@bp.post("/albums/<int:aid>/zusammenlegen")
@login_required
def zusammenlegen(aid):
    """Alle Bilder dieses Albums in ein anderes übernehmen; das dann leere Album verschwindet.
    Gedacht für den Einwurf, dessen Bilder doch zu einem vorhandenen Album gehören."""
    quelle = _get_album(aid)
    if not quelle:
        return jsonify(error="Album nicht gefunden"), 404
    try:
        ziel_id = int(json_body().get("ziel"))
    except (TypeError, ValueError):
        return jsonify(error="Ungültiges Zielalbum"), 400
    if ziel_id == aid:
        return jsonify(error="Ein Album lässt sich nicht mit sich selbst zusammenlegen."), 400
    ziel = _get_album(ziel_id)
    if not ziel:
        return jsonify(error="Zielalbum nicht gefunden"), 404
    if not can_edit(quelle["owner_id"]) or not can_edit(ziel["owner_id"]):
        return jsonify(error="Keine Berechtigung"), 403
    ts = db.now()
    with db.transaction():
        # Hinten anhängen, in der bisherigen Reihenfolge: Die Sortierwerte der Quelle rücken
        # geschlossen hinter den größten des Ziels.
        versatz = (db.query("SELECT COALESCE(MAX(sort), 0) AS m FROM photos WHERE album_id = ?", (ziel_id,), one=True)["m"]
                   - db.query("SELECT COALESCE(MIN(sort), 0) AS m FROM photos WHERE album_id = ?", (aid,), one=True)["m"] + 1)
        db.execute("UPDATE photos SET album_id = ?, sort = sort + ? WHERE album_id = ?", (ziel_id, versatz, aid))
        db.execute("DELETE FROM albums WHERE id = ?", (aid,))
        db.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (ts, ziel_id))
    out = album_json(_get_album(ziel_id), _album_photos(ziel_id))
    out["can_edit"] = True
    return jsonify(album=out)


def _get_photo(pid):
    return db.query("SELECT * FROM photos WHERE id = ?", (pid,), one=True)


@bp.get("/photos/<int:pid>")
@login_required
def get_photo(pid):
    p = _get_photo(pid)
    if not p:
        return jsonify(error="Bild nicht gefunden"), 404
    out = photo_json(p)
    out["can_edit"] = can_edit_photo(p)
    return jsonify(photo=out)


@bp.put("/photos/<int:pid>")
@login_required
def update_photo(pid):
    p = _get_photo(pid)
    if not p:
        return jsonify(error="Bild nicht gefunden"), 404
    if not can_edit_photo(p):
        return jsonify(error="Keine Berechtigung"), 403
    d = json_body()
    vals = {}
    for f in ("title", "note", "details", "taken_at"):
        if f in d:
            v = d.get(f)
            if v is not None and not isinstance(v, str):
                return jsonify(error=f"„{f}“ muss Text sein."), 400
            vals[f] = (v or "").strip()
    if vals.get("taken_at"):
        # Nur ein echter Zeitpunkt – sonst stünde beliebiger Text in der Bildbeschreibung.
        try:
            datetime.fromisoformat(vals["taken_at"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify(error="„Aufnahmezeit“ muss ein Zeitpunkt sein."), 400
    for f in ("height_m", "altitude"):
        if f in d:
            v = d.get(f)
            if v in (None, ""):
                vals[f] = None
            else:
                try:
                    n = float(str(v).replace(",", "."))
                    if not math.isfinite(n):
                        # inf/nan schreibt jsonify als nacktes Infinity/NaN – der Album-Abruf wäre für immer kaputt
                        raise ValueError
                except ValueError:
                    return jsonify(error=f"„{v}“ ist keine gültige Zahl."), 400
                vals[f] = n
    if "lat" in d or "lon" in d:
        lat, lon = d.get("lat"), d.get("lon")
        if lat in (None, "") and lon in (None, ""):
            vals["lat"] = vals["lon"] = None
            vals["geo_source"] = None
        else:
            try:
                lat, lon = float(lat), float(lon)
            except (TypeError, ValueError):
                return jsonify(error="Ungültige Koordinaten."), 400
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return jsonify(error="Koordinaten außerhalb des gültigen Bereichs."), 400
            vals["lat"], vals["lon"], vals["geo_source"] = lat, lon, "manual"
    if "sort" in d:
        try:
            vals["sort"] = int(d["sort"])
            if abs(vals["sort"]) > 10 ** 9:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            return jsonify(error="„sort“ ist keine gültige Zahl."), 400
    if "album_id" in d:
        try:
            target = _get_album(int(d["album_id"]))
        except (TypeError, ValueError, OverflowError):
            target = None
        if not target or not can_edit(target["owner_id"]):
            return jsonify(error="Zielalbum nicht gefunden oder keine Berechtigung."), 400
        vals["album_id"] = target["id"]
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        ts = db.now()
        with db.transaction():
            db.execute(f"UPDATE photos SET {sets} WHERE id = ?", (*vals.values(), pid))
            # Beim Verschieben muss auch das Zielalbum nach oben rutschen, nicht nur das Herkunftsalbum
            for a_id in {p["album_id"], vals.get("album_id", p["album_id"])}:
                db.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (ts, a_id))
            # War das Bild das Deckblatt seines alten Albums, zeigt das jetzt auf ein fremdes Bild.
            if vals.get("album_id", p["album_id"]) != p["album_id"]:
                db.execute("UPDATE albums SET cover_photo_id = NULL WHERE id = ? AND cover_photo_id = ?",
                           (p["album_id"], pid))
    out = photo_json(_get_photo(pid))
    out["can_edit"] = True
    return jsonify(photo=out)


@bp.delete("/photos/<int:pid>")
@login_required
def delete_photo(pid):
    p = _get_photo(pid)
    if not p:
        return jsonify(error="Bild nicht gefunden"), 404
    if not can_edit_photo(p):
        return jsonify(error="Keine Berechtigung"), 403
    with db.transaction():
        db.execute("DELETE FROM photos WHERE id = ?", (pid,))
        # SQLite vergibt Zeilennummern gelöschter Zeilen wieder: ein stehengebliebener Verweis
        # zeigte sonst irgendwann auf ein ganz anderes Bild.
        db.execute("UPDATE albums SET cover_photo_id = NULL WHERE cover_photo_id = ?", (pid,))
        db.execute("UPDATE albums SET updated_at = ? WHERE id = ?", (db.now(), p["album_id"]))
    delete_photo_files(current_app.config["MEDIA_DIR"], p["file"])
    return jsonify(ok=True)
