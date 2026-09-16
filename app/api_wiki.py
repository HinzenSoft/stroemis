"""Wiki: hierarchische Seiten als Markdown, Versionen, Bearbeitungsfreigaben, Kommentare
und öffentliche Freigabe."""
import io
import os
import re
import secrets
import unicodedata
import zipfile
from datetime import datetime, timedelta
from urllib.parse import unquote

from flask import Blueprint, current_app, jsonify, request

from . import db
from .auth import avatar_url, current_user, darf_inhalte, eingabefehler_abfangen, is_admin, json_body, login_required
from .images import WIKI_EXT, crop_wiki_image, rotate_wiki_image, store_wiki_file
from .mailer import send_mail

bp = Blueprint("wiki", __name__, url_prefix="/api/wiki")
eingabefehler_abfangen(bp)
public_bp = Blueprint("wiki_public", __name__, url_prefix="/api/public")

# Seiten sind Markdown. Das Feld "format" steht noch in der Datenbank (auch an jeder Fassung),
# damit alte Zeilen lesbar bleiben – geschrieben wird nur noch "markdown".
FORMAT = "markdown"
# Anhänge, die eine Seite einbindet: /media/wiki/<pfad>. Der Pfad endet erst am Trennzeichen –
# Dateinamen mit Umlaut dürfen nicht abgeschnitten werden. Fragment (#w=…) und Abfrage gehören nicht dazu.
_FILE_REF_RE = re.compile(r"/media/wiki/([^\s\"'<>)\]?#]+)")
# Konflikt beim Speichern: zwei Leute an derselben Seite.
CONFLICT = ("Die Seite wurde inzwischen von jemand anderem gespeichert. Bitte die Seite neu laden und die "
            "Änderung noch einmal eintragen – der Verlauf zeigt die zwischenzeitliche Fassung.")


def slugify(title):
    s = title.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "seite"


def unique_slug(title, exclude_id=None):
    """Freie Adresse für einen Titel – auch frühere Adressen anderer Seiten bleiben gesperrt,
    damit ein alter Link nicht plötzlich auf einer fremden Seite landet."""
    base = slugify(title)
    slug, n = base, 2
    while True:
        row = (db.query("SELECT id FROM wiki_pages WHERE slug = ?", (slug,), one=True)
               or db.query("SELECT page_id AS id FROM wiki_slugs WHERE slug = ?", (slug,), one=True))
        if not row or row["id"] == exclude_id:
            return slug
        slug = f"{base}-{n}"
        n += 1


def plain_text(content):
    return re.sub(r"\s+", " ", content or "").strip()


# --- Rechte ------------------------------------------------------------------

def _ancestor_ids(page):
    ids, cur, seen = [], page["parent_id"], set()
    while cur is not None and cur not in seen:
        ids.append(cur)
        seen.add(cur)
        row = db.query("SELECT parent_id FROM wiki_pages WHERE id = ?", (cur,), one=True)
        cur = row["parent_id"] if row else None
    return ids


def can_edit(page, user=None):
    """Bearbeiten dürfen Admins und Redakteure, der Ersteller und freigegebene Nutzer
    (Freigaben vererben sich auf Unterseiten)."""
    user = user or current_user()
    if not user:
        return False
    if darf_inhalte(user) or page["created_by"] == user["id"]:
        return True
    ids = [page["id"], *_ancestor_ids(page)]
    marks = ",".join("?" * len(ids))
    return bool(db.query(f"SELECT 1 FROM wiki_editors WHERE user_id = ? AND page_id IN ({marks})",
                         (user["id"], *ids), one=True))


def restricted_ids(page):
    """Die beschränkten Seiten in der Ahnenreihe (leer = frei lesbar)."""
    ids = [page["id"], *_ancestor_ids(page)]
    marks = ",".join("?" * len(ids))
    # Auch Seiten im Papierkorb zählen: sonst verlöre eine gelöschte Seite ihre Beschränkung,
    # und ihre Versionen wären für jeden Angemeldeten lesbar.
    rows = db.query(f"SELECT id FROM wiki_pages WHERE id IN ({marks}) AND read_restricted = 1", ids)
    return ids, [r["id"] for r in rows]


def can_read(page, user=None):
    """Lesen darf jeder Angemeldete – außer die Seite (oder ein Abschnitt darüber) ist beschränkt.
    Dann nur Admin und Redakteur, der Ersteller und die zum Bearbeiten freigegebenen Nutzer.
    Wer alles bearbeiten darf, muss alles lesen dürfen – sonst bearbeitete er blind."""
    user = user or current_user()
    if not user:
        return False
    if darf_inhalte(user):
        return True
    ids, restricted = restricted_ids(page)
    if not restricted:
        return True
    if page["created_by"] == user["id"]:
        return True
    marks = ",".join("?" * len(ids))
    if db.query(f"SELECT 1 FROM wiki_editors WHERE user_id = ? AND page_id IN ({marks})",
                (user["id"], *ids), one=True):
        return True
    # Wer den beschränkten Abschnitt selbst angelegt hat, darf ihn auch lesen.
    rmarks = ",".join("?" * len(restricted))
    return bool(db.query(f"SELECT 1 FROM wiki_pages WHERE id IN ({rmarks}) AND created_by = ?",
                         (*restricted, user["id"]), one=True))


def readable(rows):
    """Filtert eine Trefferliste auf das, was der angemeldete Nutzer lesen darf.
    Ohne beschränkte Seiten in der Datenbank ist das ein No-Op."""
    if not db.query("SELECT 1 FROM wiki_pages WHERE read_restricted = 1 LIMIT 1", one=True):
        return rows
    out = []
    for r in rows:
        page = r if "created_by" in r and "parent_id" in r else _get_page(int(r["id"]))
        if page and can_read(page):
            out.append(r)
    return out


def can_delete(page, user=None):
    user = user or current_user()
    return bool(user and (darf_inhalte(user) or page["created_by"] == user["id"]))


def is_public(page):
    """Öffentlich, wenn die Seite selbst freigegeben ist oder ein Vorfahre samt Unterseiten.
    Eine lesebeschränkte Seite bleibt in jedem Fall intern: die Beschränkung wiegt schwerer als
    die Freigabe eines Vorfahren, sonst käme sie durch eine spätere Freigabe ungefragt ins Netz."""
    # Die Beschränkung wird hier selbst nachgeschlagen – für die Seite UND ihre Vorfahren.
    # Früher galt nur die eigene Spalte, und auch die nur, wenn der Aufrufer sie mitgeladen
    # hatte: Die öffentliche Suche lud sie nicht und gab beschränkte Seiten preis.
    if restricted_ids(page)[1]:
        return False
    if page["is_public"]:
        return True
    ids = _ancestor_ids(page)
    if not ids:
        return False
    marks = ",".join("?" * len(ids))
    return bool(db.query(f"SELECT 1 FROM wiki_pages WHERE id IN ({marks}) AND is_public = 1 AND public_children = 1 "
                         "AND deleted_at IS NULL", ids, one=True))


def public_root(page):
    """Die Seite, über die die Freigabe läuft (für den öffentlichen Seitenbaum)."""
    if page["is_public"]:
        return page
    for aid in _ancestor_ids(page):
        a = db.query("SELECT * FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (aid,), one=True)
        if a and a["is_public"] and a["public_children"]:
            return a
    return None


def inherits_public(parent_id):
    """Wäre eine Seite unter parent_id ohne Login sichtbar? Veröffentlichen darf nur ein Administrator –
    das gilt auch für den Umweg „Unterseite in einem freigegebenen Abschnitt anlegen“."""
    if not parent_id:
        return False
    parent = db.query("SELECT * FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (parent_id,), one=True)
    if not parent:
        return False
    ids = [parent["id"], *_ancestor_ids(parent)]
    marks = ",".join("?" * len(ids))
    return bool(db.query(f"SELECT 1 FROM wiki_pages WHERE id IN ({marks}) AND is_public = 1 AND public_children = 1 "
                         "AND deleted_at IS NULL", ids, one=True))


# --- Hilfen --------------------------------------------------------------------

def _get_page(slug_or_id):
    where = "p.id = ?" if isinstance(slug_or_id, int) else "p.slug = ?"
    row = db.query(
        f"SELECT p.*, c.name AS created_by_name, c.avatar AS created_by_avatar, "
        f"u.name AS updated_by_name FROM wiki_pages p "
        f"LEFT JOIN users c ON c.id = p.created_by LEFT JOIN users u ON u.id = p.updated_by "
        f"WHERE {where} AND p.deleted_at IS NULL",
        (slug_or_id,), one=True)
    if row is None and not isinstance(slug_or_id, int):
        # Frühere Adresse: nach dem Umbenennen bleiben alte Links und Lesezeichen gültig.
        alias = db.query("SELECT page_id FROM wiki_slugs WHERE slug = ?", (slug_or_id,), one=True)
        if alias:
            return _get_page(int(alias["page_id"]))
    return row


def file_refs(content):
    """Alle Anhänge, die ein Seiteninhalt einbindet – als Pfad hinter /media/wiki/."""
    out = set()
    for m in _FILE_REF_RE.finditer(content or ""):
        # Erst dekodieren, dann prüfen – sonst schlüpft ein %2e%2e als Verzeichniswechsel durch.
        ref = unquote(m.group(1)).strip("/")
        if ref and ".." not in ref.split("/"):
            out.add(ref)
    return out


def sync_page_files(pid, content):
    """Verknüpfung Seite ↔ Anhang nachführen (Grundlage für file_is_public)."""
    db.execute("DELETE FROM wiki_page_files WHERE page_id = ?", (pid,))
    for ref in file_refs(content):
        db.execute("INSERT OR IGNORE INTO wiki_page_files (page_id, file) VALUES (?, ?)", (pid, ref))


_LINK_REF_RE = re.compile(r"\]\(\s*/wiki/([A-Za-z0-9][A-Za-z0-9\-_]*)")
# Ein eingebundener Abschnitt (":::einbau seite#abschnitt") ist ein Verweis wie jeder andere –
# er zählt sogar schwerer: Wer den Abschnitt auf der Quellseite ändert, ändert ihn hier mit.
# Über die Rückverweise sieht man dort, wen das betrifft, bevor man ihn anfasst.
_EINBAU_REF_RE = re.compile(r"^:::[ \t]*einbau[ \t]+([A-Za-z0-9][A-Za-z0-9\-_]*)\s*#", re.MULTILINE)


def link_refs(content):
    """Alle Wiki-Seiten, auf die ein Inhalt verweist – als slug. Links und eingebundene Abschnitte."""
    text = content or ""
    return ({m.group(1).lower() for m in _LINK_REF_RE.finditer(text)}
            | {m.group(1).lower() for m in _EINBAU_REF_RE.finditer(text)})


def sync_page_links(pid, content):
    """Verknüpfung Seite → Seite nachführen (Grundlage für die Rückverweise)."""
    db.execute("DELETE FROM wiki_page_links WHERE page_id = ?", (pid,))
    for slug in link_refs(content):
        db.execute("INSERT OR IGNORE INTO wiki_page_links (page_id, target_slug) VALUES (?, ?)", (pid, slug))


# Die Verweistabelle hält fest, was im Text steht – also den Slug, der beim Schreiben galt. Nach
# einem Umbenennen ist das ein früherer Name der Seite, der nur noch in wiki_slugs steht. Aufgelöst
# wird deshalb erst beim Lesen, über alle Namen der Seite: genau so, wie auch der Link selbst beim
# Anklicken noch zur Seite führt. Die Tabelle umzuschreiben hielte nicht – sie ist aus den Texten
# abgeleitet, und das nächste Speichern der verweisenden Seite (oder ein Neuaufbau über
# db.DERIVED_VERSION) trüge wieder den alten Namen ein. Eindeutig ist das, weil unique_slug auch
# frühere Namen als vergeben behandelt: ein Name gehört immer genau einer Seite.
_ALLE_NAMEN = "SELECT slug FROM wiki_pages WHERE id = ? UNION SELECT slug FROM wiki_slugs WHERE page_id = ?"


def backfill_page_files():
    """Verknüpfungen aus vorhandenen Seiten aufbauen. Beliebig oft wiederholbar: die Tabelle ist
    vollständig aus den Seiteninhalten ableitbar und wird dabei komplett neu geschrieben.
    Ausgelöst über db.DERIVED_VERSION, sobald sich das Erkennen der Anhänge geändert hat."""
    with db.transaction():
        db.execute("DELETE FROM wiki_page_files")
        db.execute("DELETE FROM wiki_page_links")
        for p in db.query("SELECT id, content FROM wiki_pages"):
            sync_page_files(p["id"], p["content"])
            sync_page_links(p["id"], p["content"])


def _editors(pid):
    return db.query("SELECT u.id, u.name, u.email, u.gliederung FROM wiki_editors e JOIN users u ON u.id = e.user_id "
                    "WHERE e.page_id = ? ORDER BY u.name COLLATE NOCASE", (pid,))


def page_json(p):
    out = {k: p[k] for k in ("id", "title", "slug", "parent_id", "position", "created_by", "updated_by",
                             "created_at", "updated_at", "format", "is_public", "public_children", "version",
                             "icon", "is_template", "read_restricted")}
    for k in ("created_by_name", "updated_by_name"):
        if k in p:
            out[k] = p[k]
    if "created_by_avatar" in p:
        out["created_by_avatar"] = avatar_url(p["created_by_avatar"])
    out["effective_public"] = is_public(p)
    out["content"] = p["content"]
    out["can_edit"] = can_edit(p)
    out["can_delete"] = can_delete(p)
    out["can_share"] = can_delete(p)      # Freigabe zum Bearbeiten: Ersteller oder Admin
    out["can_publish"] = is_admin()       # Veröffentlichen: nur Admin
    if out["can_share"]:
        out["editors"] = _editors(p["id"])
    out["comment_count"] = db.query("SELECT COUNT(*) AS n FROM wiki_comments WHERE page_id = ? AND resolved = 0",
                                    (p["id"],), one=True)["n"]
    me = current_user()
    out["favorite"] = bool(me and db.query("SELECT 1 FROM wiki_favorites WHERE user_id = ? AND page_id = ?",
                                           (me["id"], p["id"]), one=True))
    out["watch"] = bool(me and db.query("SELECT 1 FROM wiki_watches WHERE user_id = ? AND page_id = ?",
                                        (me["id"], p["id"]), one=True))
    # Je verweisender Seite einmal: nennt ein Text die Seite unter altem und neuem Namen, zählt
    # sie trotzdem nur einmal – so wie in der Liste der Rückverweise.
    out["backlink_count"] = db.query(
        "SELECT COUNT(DISTINCT q.id) AS n FROM wiki_page_links l JOIN wiki_pages q ON q.id = l.page_id "
        f"WHERE l.target_slug IN ({_ALLE_NAMEN}) AND q.id != ? AND q.deleted_at IS NULL",
        (p["id"], p["id"], p["id"]), one=True)["n"]
    return out


def _is_descendant(page_id, candidate_parent):
    seen = set()
    cur = candidate_parent
    while cur is not None and cur not in seen:
        if cur == page_id:
            return True
        seen.add(cur)
        row = db.query("SELECT parent_id FROM wiki_pages WHERE id = ?", (cur,), one=True)
        cur = row["parent_id"] if row else None
    return False


# Kennzeichen einer Bearbeitung: Der Editor würfelt es beim Öffnen aus (16 Bytes Zufall, hexadezimal
# geschrieben) und schickt es bei jedem Speichern mit. Zeichenvorrat und Länge sind eng gefasst –
# alles andere gilt als kein Kennzeichen und bekommt damit eine eigene Fassung.
SITZUNG_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

# So lange bleibt es nach einer Änderung still: Wer dieselbe Seite kurz hintereinander mehrfach
# bearbeitet (Editor zu, Editor auf), schreibt zwar jedes Mal eine eigene Fassung, schickt den
# Beobachtern aber nur eine Nachricht. Der Verlauf und die Post folgen also verschiedenen Regeln –
# der Verlauf soll vollständig sein, die Post nicht lästig.
MELDUNG_RUHE_SEK = 10 * 60


def _sekunden_her(frueher, jetzt):
    """Abstand zweier Zeitstempel in Sekunden; bei unlesbaren Werten unendlich."""
    try:
        return abs((datetime.fromisoformat(jetzt) - datetime.fromisoformat(frueher)).total_seconds())
    except (TypeError, ValueError):
        return float("inf")


class _Fassungskonflikt(Exception):
    """Die Seite wurde zwischen Prüfung und Schreiben von jemand anderem gespeichert."""


def _sitzung(d):
    """Das Bearbeitungs-Kennzeichen aus dem Rumpf – oder None, wenn keines taugt."""
    s = d.get("sitzung")
    return s if isinstance(s, str) and SITZUNG_RE.match(s) else None


def _revision(pid, title, content, fmt, uid, ts, sitzung=None, alt_zwischenstand=False):
    """Legt eine Fassung im Verlauf an. Liefert True, wenn wirklich eine neue entstanden ist.

    Speichert der Editor mit Kennzeichen, wird die Fassung DERSELBEN Bearbeitung
    fortgeschrieben: der Verlauf zeigt eine Fassung je Bearbeitung, nicht je Tastendruck.
    Eine neue Bearbeitung bringt ein neues Kennzeichen mit und legt damit immer eine eigene
    Fassung an – der Stand von vorher bleibt also stehen, auch wenn beide kurz aufeinander
    folgen. Ohne Kennzeichen (Wiederherstellen, Anlegen, Zugriffe von außerhalb des Editors)
    entsteht ebenfalls immer eine eigene Fassung.

    alt_zwischenstand ist der Übergangsfall: Ein Browser, der die Anwendung vor der Umstellung
    geladen hat, kennt kein Kennzeichen und schickt stattdessen "still". Er behält die alte
    Regel (dieselbe Person, kurz hintereinander), denn sonst legte jeder seiner Zwischenstände
    eine eigene Fassung an und verdrängte über MAX_REVISIONS den ganzen Verlauf der Seite. Die
    Oberfläche lädt ihre Skripte ohne Versionsstempel und wechselt Seiten ohne Neuladen – ein
    offener Reiter läuft also mit den alten Skripten weiter, bis jemand neu lädt. Der Zweig darf
    weg, sobald es solche Reiter nicht mehr gibt."""
    if sitzung or alt_zwischenstand:
        letzte = db.query("SELECT id, user_id, sitzung, created_at FROM wiki_revisions WHERE page_id = ? "
                          "ORDER BY id DESC LIMIT 1", (pid,), one=True)
        gehoert_dazu = letzte and letzte["user_id"] == uid and (
            letzte["sitzung"] == sitzung if sitzung
            # Der alte Weg schreibt nur Fassungen fort, die selbst ohne Kennzeichen entstanden
            # sind: sonst könnte ein Reiter mit den alten Skripten die Fassung einer laufenden
            # Bearbeitung überschreiben – genau das, was hier abgeschafft werden soll.
            else letzte["sitzung"] is None
            and _sekunden_her(letzte["created_at"], ts) < MELDUNG_RUHE_SEK)
        if gehoert_dazu:
            db.execute("UPDATE wiki_revisions SET title = ?, content = ?, format = ?, created_at = ? WHERE id = ?",
                       (title, content, fmt, ts, letzte["id"]))
            return False
    db.execute("INSERT INTO wiki_revisions (page_id, title, content, format, user_id, created_at, sitzung) "
               "VALUES (?,?,?,?,?,?,?)",
               (pid, title, content, fmt, uid, ts, sitzung))
    # Jede Fassung wird vollständig gespeichert; ohne Obergrenze wächst der Verlauf einer viel
    # bearbeiteten Seite unbegrenzt. 0 in MAX_REVISIONS hebt die Grenze auf.
    keep = current_app.config.get("MAX_REVISIONS") or 0
    if keep > 0:
        db.execute("DELETE FROM wiki_revisions WHERE page_id = ? AND id NOT IN "
                   "(SELECT id FROM wiki_revisions WHERE page_id = ? ORDER BY id DESC LIMIT ?)",
                   (pid, pid, keep))
    return True


# --- Baum, Suche, Seiten --------------------------------------------------------

@bp.get("/tree")
@login_required
def tree():
    uid = current_user()["id"]
    rows = db.query(
        "SELECT p.id, p.title, p.slug, p.parent_id, p.position, p.updated_at, p.created_by, p.is_public, "
        "       p.public_children, p.icon, p.is_template, "
        "       (f.page_id IS NOT NULL) AS favorite "
        "FROM wiki_pages p LEFT JOIN wiki_favorites f ON f.page_id = p.id AND f.user_id = ? "
        "WHERE p.deleted_at IS NULL ORDER BY p.position, p.title COLLATE NOCASE", (uid,))
    return jsonify(pages=readable(rows))


def _like(term):
    r"""LIKE-Muster mit escapten Platzhaltern: „50 %“ soll nicht alles finden."""
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


@bp.get("/search")
@login_required
def search():
    """Mehrwortsuche: jedes Wort muss vorkommen (Titel oder Inhalt). Treffer im Titel zuerst,
    danach die mit den meisten Wörtern im Titel."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify(results=[])
    terms = [t for t in re.split(r"\s+", q) if t][:6]

    where = " AND ".join(["(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"] * len(terms))
    order = " + ".join(["(title LIKE ? ESCAPE '\\')"] * len(terms))
    args = []
    for t in terms:
        args += [_like(t), _like(t)]
    args += [_like(t) for t in terms]
    rows = db.query(
        f"SELECT id, title, slug, content, format, updated_at FROM wiki_pages "
        f"WHERE deleted_at IS NULL AND {where} "
        f"ORDER BY ({order}) DESC, updated_at DESC, title COLLATE NOCASE LIMIT 30", args)

    results = []
    for r in rows:
        text = plain_text(r["content"])
        low = text.lower()
        # Ausschnitt um den ersten Treffer, der im Text steht (sonst stand er nur im Titel).
        hit = min([i for i in (low.find(t.lower()) for t in terms) if i >= 0], default=-1)
        snippet = ""
        if hit >= 0:
            start = max(0, hit - 60)
            snippet = ("…" if start else "") + text[start:hit + 140] + ("…" if len(text) > hit + 140 else "")
        elif text:
            snippet = text[:160] + ("…" if len(text) > 160 else "")
        results.append({"id": r["id"], "title": r["title"], "slug": r["slug"],
                        "snippet": snippet, "terms": terms})
    return jsonify(results=readable(results), terms=terms)


@bp.get("/pages/<slug>")
@login_required
def get_page(slug):
    p = _get_page(slug)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    # Besuch vermerken – Grundlage für „Zuletzt besucht“ auf der Startseite.
    db.execute("INSERT INTO wiki_views (user_id, page_id, seen_at) VALUES (?,?,?) "
               "ON CONFLICT(user_id, page_id) DO UPDATE SET seen_at = excluded.seen_at",
               (current_user()["id"], p["id"], db.now()))
    return jsonify(page=page_json(p))


@bp.post("/pages")
@login_required
def create_page():
    d = json_body()
    title = (d.get("title") or "").strip()
    if not title:
        return jsonify(error="Bitte einen Titel angeben."), 400
    parent_id = d.get("parent_id") or None
    if parent_id and not db.query("SELECT 1 FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (parent_id,), one=True):
        return jsonify(error="Übergeordnete Seite nicht gefunden."), 400
    if inherits_public(parent_id) and not is_admin():
        return jsonify(error="Dieser Abschnitt ist ohne Anmeldung sichtbar. Seiten darin dürfen nur "
                             "Administratoren anlegen."), 403
    content = d.get("content") or ""
    ts = db.now()
    uid = current_user()["id"]
    with db.transaction():
        pid = db.execute(
            "INSERT INTO wiki_pages (title, slug, parent_id, content, format, position, created_by, updated_by, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (title, unique_slug(title), parent_id, content, FORMAT, int(d.get("position") or 0), uid, uid, ts, ts))
        _revision(pid, title, content, FORMAT, uid, ts)
        sync_page_files(pid, content)
        sync_page_links(pid, content)
    return jsonify(page=page_json(_get_page(pid))), 201


@bp.put("/pages/<int:pid>")
@login_required
def update_page(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_edit(p):
        return jsonify(error="Diese Seite darf nur der Ersteller oder ein freigegebener Nutzer bearbeiten."), 403
    d = json_body()
    # Zwei Leute an derselben Seite: wer die ältere Fassung geladen hat, überschreibt nicht stillschweigend.
    base = d.get("base_version")
    if isinstance(base, str) and base.isdigit():
        base = int(base)
    pruefe_fassung = isinstance(base, int) and ("content" in d or "title" in d)
    if pruefe_fassung and base != p["version"]:
        return jsonify(error=CONFLICT, page=page_json(p)), 409
    vals = {}
    if "title" in d:
        title = (d.get("title") or "").strip()
        if not title:
            return jsonify(error="Der Titel darf nicht leer sein."), 400
        vals["title"] = title
        if title != p["title"]:
            slug = unique_slug(title, exclude_id=pid)
            if slug != p["slug"]:
                vals["slug"] = slug
    if "content" in d:
        inhalt = d.get("content") or ""
        # Leerer Inhalt auf einer Seite, die Text hatte, ist fast immer ein Unfall: ein Strg+Z zu
        # viel im Editor, ein halber Import, ein Browser, der beim Öffnen stolpert. Weil der
        # Editor von allein schreibt, stünde die Seite leer da, bevor jemand hinsehen kann – und
        # zwar auch dann, wenn die Absicherung im Editor selbst einmal nicht greift. Wer wirklich
        # alles löschen will, sagt es mit "leeren" ausdrücklich; ganz weg kommt eine Seite über
        # das Löschen. Ältere Stände holt ohnehin der Verlauf zurück (restore_revision schreibt
        # auf eigenem Weg, eine leere Fassung bleibt also wiederherstellbar).
        if not inhalt.strip() and (p["content"] or "").strip() and not d.get("leeren"):
            return jsonify(error="Die Seite wäre danach leer. Das wird nicht von allein "
                                 "geschrieben – zum Leeren ausdrücklich bestätigen oder die "
                                 "Seite löschen."), 400
        vals["content"] = inhalt
        vals["format"] = FORMAT
    if "parent_id" in d:
        parent_id = d.get("parent_id") or None
        if parent_id is not None:
            parent_id = int(parent_id)
            if parent_id == pid or _is_descendant(pid, parent_id):
                return jsonify(error="Eine Seite kann nicht unter sich selbst einsortiert werden."), 400
            if not db.query("SELECT 1 FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (parent_id,), one=True):
                return jsonify(error="Übergeordnete Seite nicht gefunden."), 400
        if parent_id != p["parent_id"] and inherits_public(parent_id) and not is_admin():
            return jsonify(error="Dieser Abschnitt ist ohne Anmeldung sichtbar. Seiten dorthin verschieben "
                                 "dürfen nur Administratoren."), 403
        vals["parent_id"] = parent_id
    if "position" in d:
        vals["position"] = int(d.get("position") or 0)
    if not vals:
        return jsonify(page=page_json(p))
    uid = current_user()["id"]
    ts = db.now()
    # Das Kennzeichen schickt der Editor bei jedem Speichern derselben Bearbeitung mit:
    # Zwischenstände füllen dadurch weder den Verlauf noch lösen sie eine zweite
    # Benachrichtigung aus.
    sitzung = _sitzung(d)
    # "still" schickt nur ein Browser, der noch vor der Umstellung geladen wurde (siehe _revision).
    alt_zwischenstand = bool(d.get("still")) and not sitzung
    changed = ("content" in vals and (vals["content"] != p["content"] or vals["format"] != p["format"])) \
        or ("title" in vals and vals["title"] != p["title"])
    # Vor dem Schreiben nachsehen, wie lange die letzte Änderung her ist: danach richtet sich,
    # ob die Beobachter noch einmal Post bekommen (siehe MELDUNG_RUHE_SEK).
    vorige = db.query("SELECT user_id, created_at FROM wiki_revisions WHERE page_id = ? "
                      "ORDER BY id DESC LIMIT 1", (pid,), one=True) if changed else None
    schon_gemeldet = bool(vorige and vorige["user_id"] == uid
                          and _sekunden_her(vorige["created_at"], ts) < MELDUNG_RUHE_SEK)
    vals["updated_by"], vals["updated_at"] = uid, ts
    # Die Fassung zählt nur für Titel und Inhalt: Ein bloßes Verschieben im Baum ist keine
    # Änderung am Text, und ein gerade offener Editor bekäme sonst grundlos einen 409.
    if changed:
        vals["version"] = (p["version"] or 0) + 1
    sets = ", ".join(f"{k} = ?" for k in vals)
    try:
        with db.transaction():
            # Bedingt schreiben: Zwischen dem Lesen der Fassung weiter oben und diesem Schreibzugriff
            # liegen einige Millisekunden. Trafen zwei Speichervorgänge mit derselben base_version
            # darin zusammen, wurden beide angenommen und der erste still überschrieben – beide
            # Browser meldeten „Gespeichert“. Die Bedingung im UPDATE schließt das Fenster.
            if pruefe_fassung:
                zeilen = db.execute_zeilen(f"UPDATE wiki_pages SET {sets} WHERE id = ? AND version = ?",
                                           (*vals.values(), pid, base))
                if not zeilen:
                    raise _Fassungskonflikt()
            else:
                db.execute(f"UPDATE wiki_pages SET {sets} WHERE id = ?", (*vals.values(), pid))
            if "slug" in vals:
                # Die bisherige Adresse bleibt als Verweis bestehen, damit vorhandene Links weiter tragen.
                db.execute("DELETE FROM wiki_slugs WHERE slug = ?", (vals["slug"],))
                db.execute("INSERT OR REPLACE INTO wiki_slugs (slug, page_id) VALUES (?, ?)", (p["slug"], pid))
            if "content" in vals:
                sync_page_files(pid, vals["content"])
                sync_page_links(pid, vals["content"])
            neue_fassung = changed and _revision(
                pid, vals.get("title", p["title"]), vals.get("content", p["content"]),
                vals.get("format", p["format"]), uid, ts, sitzung=sitzung,
                alt_zwischenstand=alt_zwischenstand)
    except _Fassungskonflikt:
        return jsonify(error=CONFLICT, page=page_json(_get_page(pid))), 409
    fresh = _get_page(pid)
    # Benachrichtigt wird, wenn eine neue Fassung entstanden ist – beim automatischen Speichern
    # also einmal je Bearbeitung statt bei jedem Zwischenstand. Wer gerade eben schon an dieser
    # Seite war, schreibt still weiter: die Fassung entsteht, die Post nicht.
    if neue_fassung and not schon_gemeldet:
        notify_watchers(fresh, "Es gibt eine Änderung")
    return jsonify(page=page_json(fresh))


def _subtree_ids(pid):
    """Seite und alle Unterseiten – auch die bereits im Papierkorb liegenden."""
    out, stack, seen = [pid], [pid], {pid}
    while stack:
        cur = stack.pop()
        for k in db.query("SELECT id FROM wiki_pages WHERE parent_id = ?", (cur,)):
            if k["id"] in seen:
                continue
            seen.add(k["id"])
            out.append(k["id"])
            stack.append(k["id"])
    return out


@bp.delete("/pages/<int:pid>")
@login_required
def delete_page(pid):
    """In den Papierkorb legen – mitsamt Unterseiten, damit sich der Abschnitt geschlossen
    wiederherstellen lässt. Endgültig entfernt wird erst über den Papierkorb."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_delete(p):
        return jsonify(error="Nur der Ersteller oder ein Administrator kann diese Seite löschen."), 403
    ids = _subtree_ids(pid)
    marks = ",".join("?" * len(ids))
    ts = db.now()
    # Eine Kennung für diesen Löschvorgang: Sie hält zusammen, was gemeinsam in den Papierkorb
    # gewandert ist, und trennt es von dem, was schon vorher darin lag.
    gruppe = secrets.token_hex(8)
    with db.transaction():
        zahl = db.execute_zeilen(f"UPDATE wiki_pages SET deleted_at = ?, deleted_batch = ? "
                                 f"WHERE id IN ({marks}) AND deleted_at IS NULL", (ts, gruppe, *ids))
    return jsonify(ok=True, trashed=zahl)


@bp.get("/trash")
@login_required
def trash():
    """Papierkorb: nur die obersten gelöschten Seiten – Unterseiten hängen daran."""
    rows = db.query(
        "SELECT p.id, p.title, p.slug, p.icon, p.deleted_at, p.parent_id, u.name AS created_by_name, "
        "  (SELECT COUNT(*) FROM wiki_pages k WHERE k.parent_id = p.id AND k.deleted_at IS NOT NULL) AS children "
        "FROM wiki_pages p LEFT JOIN users u ON u.id = p.created_by "
        "WHERE p.deleted_at IS NOT NULL "
        "  AND (p.parent_id IS NULL OR p.parent_id NOT IN (SELECT id FROM wiki_pages WHERE deleted_at IS NOT NULL)) "
        "ORDER BY p.deleted_at DESC")
    me = current_user()
    # Titel beschränkter Seiten gehören nicht in jedermanns Papierkorb.
    rows = [r for r in rows if can_read(_trashed(r["id"]), me)]
    for r in rows:
        r["can_restore"] = bool(darf_inhalte(me) or db.query(
            "SELECT 1 FROM wiki_pages WHERE id = ? AND created_by = ?", (r["id"], me["id"]), one=True))
    return jsonify(pages=rows)


def _trashed(pid):
    return db.query("SELECT * FROM wiki_pages WHERE id = ? AND deleted_at IS NOT NULL", (pid,), one=True)


@bp.post("/pages/<int:pid>/restore")
@login_required
def restore_page(pid):
    p = _trashed(pid)
    if not p:
        return jsonify(error="Diese Seite liegt nicht im Papierkorb."), 404
    if not can_delete(p):
        return jsonify(error="Nur der Ersteller oder ein Administrator kann wiederherstellen."), 403
    # Liegt die frühere Elternseite noch im Papierkorb, kommt die Seite auf die oberste Ebene.
    parent = p["parent_id"]
    if parent and not db.query("SELECT 1 FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (parent,), one=True):
        parent = None
    # Ist der frühere Ort inzwischen öffentlich, wäre Wiederherstellen ein Veröffentlichen –
    # das dürfen nur Administratoren, genau wie Anlegen und Verschieben dorthin.
    if parent and inherits_public(parent) and not is_admin():
        return jsonify(error="Der frühere Ort dieser Seite ist inzwischen ohne Anmeldung sichtbar. "
                             "Dorthin wiederherstellen dürfen nur Administratoren."), 403
    ids = _subtree_ids(pid)
    marks = ",".join("?" * len(ids))
    with db.transaction():
        # Zurück kommt genau der Löschvorgang, zu dem diese Seite gehört. Eine Unterseite, die
        # schon vorher einzeln im Papierkorb lag, bleibt dort – und steht danach als eigener
        # Eintrag darin, weil ihr Elternteil wieder da ist. Seiten aus der Zeit vor dieser
        # Spalte (deleted_batch IS NULL) kommen wie früher zusammen zurück.
        if p["deleted_batch"]:
            zurueck = db.execute_zeilen(
                f"UPDATE wiki_pages SET deleted_at = NULL, deleted_batch = NULL "
                f"WHERE id IN ({marks}) AND deleted_batch = ?", (*ids, p["deleted_batch"]))
        else:
            zurueck = db.execute_zeilen(
                f"UPDATE wiki_pages SET deleted_at = NULL WHERE id IN ({marks}) AND deleted_batch IS NULL", ids)
        db.execute("UPDATE wiki_pages SET deleted_at = NULL, deleted_batch = NULL, parent_id = ? WHERE id = ?", (parent, pid))
    return jsonify(page=page_json(_get_page(pid)), restored=max(zurueck, 1))


@bp.delete("/trash/<int:pid>")
@login_required
def purge_page(pid):
    """Endgültig löschen – samt Unterseiten, Versionen, Kommentaren und Verknüpfungen."""
    p = _trashed(pid)
    if not p:
        return jsonify(error="Diese Seite liegt nicht im Papierkorb."), 404
    if not can_delete(p):
        return jsonify(error="Nur der Ersteller oder ein Administrator kann endgültig löschen."), 403
    ids = _subtree_ids(pid)
    marks = ",".join("?" * len(ids))
    with db.transaction():
        # Unterseiten zuerst, damit kein Fremdschlüssel bricht; der Rest hängt an ON DELETE CASCADE.
        db.execute(f"UPDATE wiki_pages SET parent_id = NULL WHERE id IN ({marks})", ids)
        db.execute(f"DELETE FROM wiki_pages WHERE id IN ({marks})", ids)
    return jsonify(ok=True, deleted=len(ids))


# --- Versionen ---------------------------------------------------------------------

def _revision_page(r):
    """Die Seite zu einer Fassung – ausdrücklich auch aus dem Papierkorb. _get_page blendet
    gelöschte Seiten aus; ohne Seite gäbe es nichts, woran die Rechte hängen."""
    return db.query("SELECT * FROM wiki_pages WHERE id = ?", (int(r["page_id"]),), one=True)


@bp.get("/pages/<int:pid>/revisions")
@login_required
def revisions(pid):
    # Auch im Papierkorb nachschlagen: _get_page blendet gelöschte Seiten aus, und ohne Seite
    # fiele die Rechteprüfung sonst einfach weg.
    p = db.query("SELECT * FROM wiki_pages WHERE id = ?", (pid,), one=True)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Keine Berechtigung"), 403
    rows = db.query(
        "SELECT r.id, r.title, r.format, r.created_at, r.user_id, u.name AS user_name, length(r.content) AS size "
        "FROM wiki_revisions r LEFT JOIN users u ON u.id = r.user_id WHERE r.page_id = ? ORDER BY r.id DESC", (pid,))
    return jsonify(revisions=rows)


@bp.get("/revisions/<int:rid>")
@login_required
def get_revision(rid):
    # Spalten einzeln: das Kennzeichen der Bearbeitung ist Innenleben des Verlaufs und hat
    # in der Antwort nichts verloren – wer es kennt, könnte damit eine fremde Fassung
    # fortschreiben lassen, statt eine eigene anzulegen.
    r = db.query("SELECT id, page_id, title, content, format, user_id, created_at "
                 "FROM wiki_revisions WHERE id = ?", (rid,), one=True)
    if not r:
        return jsonify(error="Version nicht gefunden"), 404
    page = _revision_page(r)
    if not page or not can_read(page):
        return jsonify(error="Keine Berechtigung"), 403
    return jsonify(revision=r)


@bp.post("/revisions/<int:rid>/restore")
@login_required
def restore_revision(rid):
    r = db.query("SELECT * FROM wiki_revisions WHERE id = ?", (rid,), one=True)
    if not r:
        return jsonify(error="Version nicht gefunden"), 404
    p = _revision_page(r)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_edit(p):
        return jsonify(error="Keine Berechtigung"), 403
    # Erst die Rechte, dann der Zustand: sonst verriete die Meldung Fremden, dass es die Seite
    # überhaupt gibt. Zurückrollen in eine gelöschte Seite gibt es nicht – die Fassung landete
    # unsichtbar im Papierkorb, und der Verlauf bekäme einen Eintrag zu einer Seite, die für
    # alle anderen nicht mehr da ist. Der Weg führt über den Papierkorb.
    if p["deleted_at"]:
        return jsonify(error="Diese Seite liegt im Papierkorb. Erst wiederherstellen, dann die Version zurückholen."), 409
    uid = current_user()["id"]
    ts = db.now()
    with db.transaction():
        db.execute("UPDATE wiki_pages SET title = ?, content = ?, format = ?, updated_by = ?, updated_at = ?, "
                   "version = version + 1 WHERE id = ?", (r["title"], r["content"], r["format"], uid, ts, r["page_id"]))
        sync_page_files(r["page_id"], r["content"])
        sync_page_links(r["page_id"], r["content"])
        _revision(r["page_id"], r["title"], r["content"], r["format"], uid, ts)
    return jsonify(page=page_json(_get_page(r["page_id"])))


# --- Seiteneigenschaften, Merkliste, Verlauf der Besuche ---------------------------------

@bp.put("/pages/<int:pid>/icon")
@login_required
def set_icon(pid):
    """Emoji vor dem Seitentitel. Leerer Wert entfernt es wieder."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_edit(p):
        return jsonify(error="Keine Berechtigung"), 403
    # Höchstens vier Zeichen: ein Emoji kann aus mehreren Codepoints bestehen (Hautton, ZWJ).
    icon = "".join(list((json_body().get("icon") or "").strip())[:4])
    db.execute("UPDATE wiki_pages SET icon = ? WHERE id = ?", (icon, pid))
    return jsonify(page=page_json(_get_page(pid)))


@bp.put("/pages/<int:pid>/options")
@login_required
def set_options(pid):
    """„Als Vorlage anbieten“."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_edit(p):
        return jsonify(error="Keine Berechtigung"), 403
    d = json_body()
    vals = {}
    if "is_template" in d:
        vals["is_template"] = 1 if d.get("is_template") else 0
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        db.execute(f"UPDATE wiki_pages SET {sets} WHERE id = ?", (*vals.values(), pid))
    return jsonify(page=page_json(_get_page(pid)))


@bp.put("/pages/<int:pid>/favorite")
@login_required
def set_favorite(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):      # wie beim Beobachten: keine Merkliste auf Fremdes
        return jsonify(error="Keine Berechtigung"), 403
    uid = current_user()["id"]
    if json_body().get("favorite"):
        db.execute("INSERT OR IGNORE INTO wiki_favorites (user_id, page_id, created_at) VALUES (?,?,?)",
                   (uid, pid, db.now()))
        return jsonify(favorite=True)
    db.execute("DELETE FROM wiki_favorites WHERE user_id = ? AND page_id = ?", (uid, pid))
    return jsonify(favorite=False)


@bp.get("/favorites")
@login_required
def favorites():
    rows = db.query(
        "SELECT p.id, p.title, p.slug, p.icon FROM wiki_favorites f JOIN wiki_pages p ON p.id = f.page_id "
        "WHERE f.user_id = ? AND p.deleted_at IS NULL ORDER BY f.created_at DESC", (current_user()["id"],))
    return jsonify(pages=readable(rows))


@bp.get("/recent")
@login_required
def recent():
    """Startseite: zuletzt besuchte und zuletzt geänderte Seiten."""
    uid = current_user()["id"]
    seen = db.query(
        "SELECT p.id, p.title, p.slug, p.icon, v.seen_at FROM wiki_views v JOIN wiki_pages p ON p.id = v.page_id "
        "WHERE v.user_id = ? AND p.deleted_at IS NULL ORDER BY v.seen_at DESC LIMIT 8", (uid,))
    changed = db.query(
        "SELECT p.id, p.title, p.slug, p.icon, p.updated_at, u.name AS updated_by_name FROM wiki_pages p "
        "LEFT JOIN users u ON u.id = p.updated_by WHERE p.deleted_at IS NULL ORDER BY p.updated_at DESC LIMIT 8")
    return jsonify(seen=readable(seen), changed=readable(changed))


@bp.get("/templates")
@login_required
def templates():
    rows = db.query("SELECT id, title, slug, icon FROM wiki_pages WHERE is_template = 1 AND deleted_at IS NULL "
                    "ORDER BY title COLLATE NOCASE")
    return jsonify(pages=readable(rows))


# --- Wer ist gerade an der Seite? --------------------------------------------
# Der Editor schreibt selbstständig, deshalb würde gleichzeitiges Bearbeiten still Arbeit
# vernichten: Wer als Zweiter speichert, bekommt eine Absage und steht mit seinem Text allein da.
# Also meldet jeder offene Reiter, woran er gerade ist. Genau einer darf schreiben; die anderen
# sehen, wer es ist, und lesen so lange mit.
PRAESENZ_TTL_SEK = 45          # doppelter Herzschlag plus Luft für ein langsames Netz
PRAESENZ_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _praesenz_aufraeumen(ts):
    """Meldungen, die zu lange her sind, zählen nicht mehr – der Reiter ist zu oder offline."""
    db.execute("DELETE FROM wiki_praesenz WHERE gesehen < ?",
               (_zeit_minus(ts, PRAESENZ_TTL_SEK),))


def _zeit_minus(ts, sekunden):
    try:
        return (datetime.fromisoformat(ts) - timedelta(seconds=sekunden)).isoformat()
    except (TypeError, ValueError):      # pragma: no cover – db.now() liefert immer ISO
        return ts


def _praesenz_liste(pid, ohne_reiter):
    return db.query(
        "SELECT p.reiter, p.user_id, p.modus, p.seit, u.name AS user_name FROM wiki_praesenz p "
        "JOIN users u ON u.id = p.user_id WHERE p.page_id = ? AND p.reiter != ? ORDER BY p.seit",
        (pid, ohne_reiter))


@bp.post("/praesenz")
@login_required
def praesenz():
    """Herzschlag eines offenen Reiters. Liefert zurück, ob er schreiben darf und wer sonst da ist."""
    d = json_body()
    reiter = d.get("reiter")
    if not isinstance(reiter, str) or not PRAESENZ_RE.match(reiter):
        return jsonify(error="Ungültige Reiterkennung"), 400
    ts = db.now()
    _praesenz_aufraeumen(ts)
    if d.get("weg"):                      # Reiter schließt sich oder wechselt die Seite
        db.execute("DELETE FROM wiki_praesenz WHERE reiter = ?", (reiter,))
        return jsonify(ok=True)

    p = _get_page(d.get("page_id"))
    if not p:
        db.execute("DELETE FROM wiki_praesenz WHERE reiter = ?", (reiter,))
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Keine Berechtigung"), 403
    uid = current_user()["id"]
    will_schreiben = d.get("modus") == "schreiben" and can_edit(p)

    modus = "lesen"
    if will_schreiben:
        # Der Schreibplatz gehört dem, der ihn zuerst hatte, bis er die Seite verlässt oder sich
        # PRAESENZ_TTL_SEK lang nicht mehr meldet. Entreißen kann ihn niemand: Der Editor
        # speichert von allein, und wer den Platz mitten im Satz verliert, merkt vom Verlust
        # seiner Arbeit nichts. Wer warten muss, sieht am Knopf, wer gerade schreibt.
        anderer = db.query(
            "SELECT reiter FROM wiki_praesenz WHERE page_id = ? AND modus = 'schreiben' AND reiter != ? "
            "ORDER BY seit LIMIT 1", (p["id"], reiter), one=True)
        if not anderer:
            modus = "schreiben"

    vorher = db.query("SELECT seit, modus FROM wiki_praesenz WHERE reiter = ?", (reiter,), one=True)
    seit = vorher["seit"] if vorher and vorher["modus"] == modus else ts
    db.execute(
        "INSERT INTO wiki_praesenz (reiter, page_id, user_id, modus, seit, gesehen) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(reiter) DO UPDATE SET page_id = excluded.page_id, user_id = excluded.user_id, "
        "modus = excluded.modus, seit = excluded.seit, gesehen = excluded.gesehen",
        (reiter, p["id"], uid, modus, seit, ts))

    andere = _praesenz_liste(p["id"], reiter)
    schreiber = next((a for a in andere if a["modus"] == "schreiben"), None)
    return jsonify(modus=modus, version=p["version"],
                   schreiber=None if not schreiber else {
                       "user_id": schreiber["user_id"], "name": schreiber["user_name"], "seit": schreiber["seit"]},
                   andere=[{"user_id": a["user_id"], "name": a["user_name"], "modus": a["modus"]}
                           for a in andere if a["user_id"] != uid])


@bp.get("/pages/<int:pid>/backlinks")
@login_required
def backlinks(pid):
    """Was verlinkt hierher – aus der beim Speichern gepflegten Verweistabelle."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    rows = db.query(
        "SELECT DISTINCT q.id, q.title, q.slug, q.icon FROM wiki_page_links l JOIN wiki_pages q ON q.id = l.page_id "
        f"WHERE l.target_slug IN ({_ALLE_NAMEN}) AND q.id != ? AND q.deleted_at IS NULL "
        "ORDER BY q.title COLLATE NOCASE", (pid, pid, pid))
    # Ausgehende Verweise stehen in derselben Tabelle, nur andersherum gelesen – die Angaben
    # zur Seite zeigen beide Richtungen. Ziel ist die Seite, die den Namen heute trägt oder
    # früher trug (siehe _ALLE_NAMEN).
    out = db.query(
        "SELECT DISTINCT q.id, q.title, q.slug, q.icon FROM wiki_page_links l "
        "LEFT JOIN wiki_slugs s ON s.slug = l.target_slug "
        "JOIN wiki_pages q ON q.slug = l.target_slug OR q.id = s.page_id "
        "WHERE l.page_id = ? AND q.id != ? AND q.deleted_at IS NULL ORDER BY q.title COLLATE NOCASE", (pid, pid))
    return jsonify(pages=readable(rows), outgoing=readable(out))


@bp.get("/pages/<int:pid>/contributors")
@login_required
def contributors(pid):
    """Wer an der Seite geschrieben hat: der Ersteller und alle, von denen eine Fassung im
    Verlauf steht – zuletzt Beteiligte zuerst. Mehr weiß die Anwendung nicht: gelöschte
    Fassungen (siehe MAX_REVISIONS) nehmen ihren Namen mit."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    rows = db.query(
        "SELECT u.id, u.name, u.email, u.avatar, MAX(r.created_at) AS zuletzt FROM wiki_revisions r "
        "JOIN users u ON u.id = r.user_id WHERE r.page_id = ? AND r.user_id != ? "
        "GROUP BY u.id ORDER BY zuletzt DESC", (pid, p["created_by"]))
    # Wer zuletzt gespeichert hat, gehört dazu, auch wenn seine Fassung inzwischen weggeräumt ist.
    kennt = {r["id"] for r in rows}
    if p["updated_by"] and p["updated_by"] != p["created_by"] and p["updated_by"] not in kennt:
        u = db.query("SELECT id, name, email, avatar FROM users WHERE id = ?", (p["updated_by"],), one=True)
        if u:
            rows = [{**dict(u), "zuletzt": p["updated_at"]}, *rows]
    ersteller = db.query("SELECT id, name, email, avatar FROM users WHERE id = ?", (p["created_by"],), one=True)

    def mit_bild(r):
        d = dict(r)
        d["avatar"] = avatar_url(d.get("avatar"))
        return d

    return jsonify(owner=mit_bild(ersteller) if ersteller else None,
                   contributors=[mit_bild(r) for r in rows])


@bp.put("/pages/<int:pid>/creator")
@login_required
def set_creator(pid):
    """Den Ersteller einer Seite auf einen anderen Nutzer umschreiben – nur für Administratoren.

    Gebraucht wird das, wenn eine Seite unter der falschen Kennung entstanden ist: beim Import
    trägt jede Seite den Namen dessen, der die Ausfuhr eingespielt hat, und wer die Gliederung
    verlässt, hinterlässt Seiten, die niemand mehr verwalten kann. Am Ersteller hängen Rechte
    (löschen, Bearbeiter freigeben), deshalb ist es kein bloßes Namensschild und deshalb darf es
    auch nicht jeder ändern."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not is_admin():
        return jsonify(error="Den Ersteller kann nur ein Administrator ändern."), 403
    d = json_body()
    uid = d.get("user_id")
    if not isinstance(uid, int) and not (isinstance(uid, str) and uid.isdigit()):
        return jsonify(error="Kein Nutzer angegeben."), 400
    # Nur freigeschaltete Konten: Eine offene Kontoanfrage soll keine Seite erben.
    neu_u = db.query("SELECT id, name FROM users WHERE id = ? AND active = 1 AND status = 'active'",
                     (int(uid),), one=True)
    if not neu_u:
        return jsonify(error="Unbekannter oder nicht freigeschalteter Nutzer."), 400
    if neu_u["id"] != p["created_by"]:
        with db.transaction():
            db.execute("UPDATE wiki_pages SET created_by = ? WHERE id = ?", (neu_u["id"], pid))
            # Als Ersteller darf er ohnehin alles; bliebe er daneben in der Bearbeiterliste stehen,
            # führte ein späterer Wechsel ihn dort als Bearbeiter zurück.
            db.execute("DELETE FROM wiki_editors WHERE page_id = ? AND user_id = ?", (pid, neu_u["id"]))
    return jsonify(page=page_json(_get_page(pid)))


@bp.get("/pages/<int:pid>/attachments")
@login_required
def attachments(pid):
    """Alle Dateien, die diese Seite einbindet – mit Originalname und Größe, soweit bekannt."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    rows = db.query(
        "SELECT pf.file, f.original_name, f.kind, f.size, f.created_at FROM wiki_page_files pf "
        "LEFT JOIN wiki_files f ON f.file = pf.file WHERE pf.page_id = ? ORDER BY pf.file", (pid,))
    for r in rows:
        r["url"] = "/media/wiki/" + r["file"]
    return jsonify(files=rows)


@bp.post("/pages/<int:pid>/duplicate")
@login_required
def duplicate_page(pid):
    """Seite kopieren (ohne Unterseiten, ohne Verlauf, ohne Freigaben)."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    if inherits_public(p["parent_id"]) and not is_admin():
        return jsonify(error="Dieser Abschnitt ist ohne Anmeldung sichtbar. Seiten darin dürfen nur "
                             "Administratoren anlegen."), 403
    title = f"{p['title']} (Kopie)"
    ts = db.now()
    uid = current_user()["id"]
    with db.transaction():
        new_id = db.execute(
            "INSERT INTO wiki_pages (title, slug, parent_id, content, format, position, icon, created_by, "
            "updated_by, created_at, updated_at, read_restricted) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, unique_slug(title), p["parent_id"], p["content"], p["format"], p["position"], p["icon"],
             uid, uid, ts, ts, p["read_restricted"]))
        _revision(new_id, title, p["content"], p["format"], uid, ts)
        sync_page_files(new_id, p["content"])
        sync_page_links(new_id, p["content"])
    return jsonify(page=page_json(_get_page(new_id))), 201


@bp.put("/reorder")
@login_required
def reorder():
    """Seitenbaum umsortieren: Liste aus {id, parent_id, position}.
    Verschieben darf nur, wer die jeweilige Seite bearbeiten darf."""
    items = json_body().get("items") or []
    if not isinstance(items, list) or len(items) > 500 or not all(isinstance(it, dict) for it in items):
        return jsonify(error="Ungültige Angaben."), 400
    prepared = []
    for it in items:
        try:
            cid = int(it.get("id"))
            parent_id = int(it["parent_id"]) if it.get("parent_id") else None
            position = int(it.get("position") or 0)
        except (TypeError, ValueError, KeyError):
            return jsonify(error="Ungültige Angaben."), 400
        page = _get_page(cid)
        if not page:
            return jsonify(error="Seite nicht gefunden."), 404
        if not can_edit(page):
            return jsonify(error=f"„{page['title']}“ darfst du nicht verschieben."), 403
        if parent_id is not None:
            if parent_id == cid or _is_descendant(cid, parent_id):
                return jsonify(error="Eine Seite kann nicht unter sich selbst einsortiert werden."), 400
            if not db.query("SELECT 1 FROM wiki_pages WHERE id = ? AND deleted_at IS NULL", (parent_id,), one=True):
                return jsonify(error="Übergeordnete Seite nicht gefunden."), 400
        # Verschieben in einen öffentlichen Abschnitt ist Veröffentlichen – nur für Administratoren.
        if parent_id != page["parent_id"] and inherits_public(parent_id) and not is_admin():
            return jsonify(error="Dieser Abschnitt ist ohne Anmeldung sichtbar. Dorthin dürfen nur "
                                 "Administratoren verschieben."), 403
        prepared.append((parent_id, position, cid))
    # Zyklen gegen den GEPLANTEN Stand prüfen: „A unter B“ und „B unter A“ bestehen einzeln
    # jede Prüfung und ergeben zusammen zwei Seiten, die im Baum nirgends mehr auftauchen.
    plan = {cid: parent_id for parent_id, _, cid in prepared}
    for cid in plan:
        cur, gesehen = plan[cid], set()
        while cur is not None:
            if cur == cid:
                return jsonify(error="Eine Seite kann nicht unter sich selbst einsortiert werden."), 400
            if cur in gesehen:
                break
            gesehen.add(cur)
            if cur in plan:
                cur = plan[cur]
            else:
                row = db.query("SELECT parent_id FROM wiki_pages WHERE id = ?", (cur,), one=True)
                cur = row["parent_id"] if row else None
    with db.transaction():
        for parent_id, position, cid in prepared:
            db.execute("UPDATE wiki_pages SET parent_id = ?, position = ? WHERE id = ?", (parent_id, position, cid))
    return jsonify(ok=True, moved=len(prepared))


@bp.put("/pages/<int:pid>/restrict")
@login_required
def set_restrict(pid):
    """Lesebeschränkung setzen. Wer darf lesen, steht dann in „Bearbeiten erlauben“ –
    plus Ersteller und Administratoren. Nur Ersteller oder Admin dürfen das umstellen."""
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_delete(p):
        return jsonify(error="Nur der Ersteller oder ein Administrator kann das umstellen."), 403
    on = 1 if json_body().get("read_restricted") else 0
    if on and (p["is_public"] or is_public(p)):
        return jsonify(error="Diese Seite ist öffentlich freigegeben. Bitte zuerst die "
                             "Veröffentlichung zurücknehmen."), 400
    if on:
        # Eine Beschränkung vererbt sich nach unten – eine öffentliche Unterseite darunter
        # wäre für Angemeldete gesperrt und für jedermann im Netz zu lesen.
        drin = db.query(
            "WITH RECURSIVE teil(id) AS (SELECT id FROM wiki_pages WHERE id = ? "
            "  UNION SELECT k.id FROM wiki_pages k JOIN teil ON k.parent_id = teil.id) "
            "SELECT title FROM wiki_pages WHERE id IN (SELECT id FROM teil) AND id != ? "
            "  AND is_public = 1 AND deleted_at IS NULL ORDER BY title LIMIT 5", (pid, pid))
        if drin:
            namen = ", ".join(f"„{r['title']}“" for r in drin)
            return jsonify(error="Darunter liegen öffentlich freigegebene Seiten: " + namen +
                                 ". Bitte erst deren Veröffentlichung zurücknehmen."), 400
    db.execute("UPDATE wiki_pages SET read_restricted = ? WHERE id = ?", (on, pid))
    return jsonify(page=page_json(_get_page(pid)))


# --- Seite beobachten -------------------------------------------------------------------

@bp.put("/pages/<int:pid>/watch")
@login_required
def set_watch(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Keine Berechtigung"), 403
    uid = current_user()["id"]
    if json_body().get("watch"):
        db.execute("INSERT OR IGNORE INTO wiki_watches (user_id, page_id, created_at) VALUES (?,?,?)",
                   (uid, pid, db.now()))
        return jsonify(watch=True)
    db.execute("DELETE FROM wiki_watches WHERE user_id = ? AND page_id = ?", (uid, pid))
    return jsonify(watch=False)


@bp.get("/watches")
@login_required
def watches():
    rows = db.query(
        "SELECT p.id, p.title, p.slug, p.icon FROM wiki_watches w JOIN wiki_pages p ON p.id = w.page_id "
        "WHERE w.user_id = ? AND p.deleted_at IS NULL ORDER BY p.title COLLATE NOCASE", (current_user()["id"],))
    return jsonify(pages=readable(rows))


def notify_watchers(page, what):
    """Beobachter einer Seite per E-Mail informieren. Fehler beim Versand dürfen das
    Speichern nie verhindern – deshalb ist alles hier eingepackt."""
    try:
        me = current_user()
        rows = db.query(
            "SELECT u.id, u.email, u.name, u.role FROM wiki_watches w JOIN users u ON u.id = w.user_id "
            "WHERE w.page_id = ? AND u.active = 1 AND u.id != ?", (page["id"], me["id"] if me else 0))
        if not rows:
            return
        cfg = current_app.config
        link = f"{cfg['BASE_URL'].rstrip('/')}/wiki/{page['slug']}"
        who = (me or {}).get("name") or (me or {}).get("email") or "jemand"
        for r in rows:
            # Wer die Seite inzwischen nicht mehr lesen darf, bekommt auch keine Nachricht.
            if not can_read(page, {"id": r["id"], "role": r["role"]}):
                continue
            try:
                send_mail(r["email"], f"{cfg['SITE_NAME']} – „{page['title']}“ wurde geändert",
                          f"Hallo {r['name'] or ''},\n\n{what} an der von dir beobachteten Seite "
                          f"„{page['title']}“ – geändert von {who}.\n\n{link}\n\n"
                          "Beobachtung beenden: auf der Seite auf „Beobachten“ tippen.\n")
            except Exception as exc:
                current_app.logger.error("Benachrichtigung an %s fehlgeschlagen: %s", r["email"], exc)
    except Exception as exc:  # pragma: no cover - Benachrichtigung ist Beiwerk
        current_app.logger.error("Benachrichtigung fehlgeschlagen: %s", exc)


# --- Export -------------------------------------------------------------------------------

def _export_name(title):
    """Dateiname aus einem Seitentitel – ohne Pfadtrenner und Sonderzeichen."""
    name = re.sub(r"[^\w .\-]+", "_", title, flags=re.UNICODE).strip(" .") or "seite"
    return name[:120]


def _descendants(pid):
    out, stack = [], [pid]
    seen = {pid}
    while stack:
        cur = stack.pop()
        for k in db.query("SELECT id, title, slug, content, format, parent_id FROM wiki_pages "
                          "WHERE parent_id = ? AND deleted_at IS NULL "
                          "ORDER BY position, title COLLATE NOCASE", (cur,)):
            if k["id"] in seen:
                continue
            seen.add(k["id"])
            out.append(k)
            stack.append(k["id"])
    return out


@bp.get("/pages/<int:pid>/export")
@login_required
def export_page(pid):
    """Seite als Markdown-Datei oder – mit children=1 – als ZIP samt Unterseiten und Anhängen."""
    from flask import Response, send_file

    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    with_children = request.args.get("children") == "1"

    if not with_children:
        # send_file schreibt den Namen RFC-5987-kodiert – eine rohe Kopfzeile mit „α“ oder
        # kyrillischen Buchstaben ließ gunicorn (latin-1) die Antwort abbrechen.
        body = (p["content"] or "").encode("utf-8")
        return send_file(io.BytesIO(body), mimetype="text/markdown; charset=utf-8", as_attachment=True,
                         download_name=f"{_export_name(p['title'])}.md")

    # Beschränkte Unterseiten gehören nicht in den Export.
    pages = [p, *[k for k in _descendants(pid) if can_read(_get_page(int(k["id"])) or k)]]
    media = os.path.join(current_app.config["MEDIA_DIR"], "wiki")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        by_id = {q["id"]: q for q in pages}
        vergeben = set()          # zwei Geschwister „Foo“ und „Foo.“ ergäben denselben Pfad
        for q in pages:
            # Ordnerpfad aus den Titeln der Elternseiten aufbauen
            parts, cur, guard = [], q, 0
            while cur is not None and guard < 40:
                parts.append(_export_name(cur["title"]))
                cur = by_id.get(cur["parent_id"])
                guard += 1
            rel = "/".join(reversed(parts))
            if rel.lower() in vergeben:
                rel = f"{rel}-{q['slug']}"
            vergeben.add(rel.lower())
            z.writestr(rel + ".md", q["content"] or "")
            for ref in file_refs(q["content"]):
                src = os.path.join(media, ref)
                if os.path.isfile(src) and os.path.commonpath([media, os.path.realpath(src)]) == media:
                    z.write(src, "media/" + ref)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"{_export_name(p['title'])}.zip")


# --- Bearbeitungsfreigabe und Veröffentlichung -----------------------------------------

@bp.get("/users")
@login_required
def users_for_sharing():
    rows = db.query("SELECT id, name, gliederung FROM users WHERE active = 1 AND status = 'active' "
                    "ORDER BY name COLLATE NOCASE")
    return jsonify(users=rows)


@bp.put("/pages/<int:pid>/editors")
@login_required
def set_editors(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_delete(p):
        return jsonify(error="Nur der Ersteller oder ein Administrator kann Bearbeiter freigeben."), 403
    roh = json_body().get("user_ids") or []
    if not isinstance(roh, list):
        return jsonify(error="user_ids muss eine Liste sein."), 400
    ids = {int(x) for x in roh if isinstance(x, int) or (isinstance(x, str) and x.isdigit())}
    ids.discard(p["created_by"])
    with db.transaction():
        db.execute("DELETE FROM wiki_editors WHERE page_id = ?", (pid,))
        for uid in ids:
            # Nur freigeschaltete Konten – eine offene Kontoanfrage bekommt keine Bearbeitungsrechte.
            if db.query("SELECT 1 FROM users WHERE id = ? AND active = 1 AND status = 'active'", (uid,), one=True):
                db.execute("INSERT OR IGNORE INTO wiki_editors (page_id, user_id) VALUES (?, ?)", (pid, uid))
    return jsonify(editors=_editors(pid))


@bp.put("/pages/<int:pid>/share")
@login_required
def set_share(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not is_admin():
        return jsonify(error="Veröffentlichen dürfen nur Administratoren."), 403
    d = json_body()
    if d.get("is_public") and restricted_ids(p)[1]:
        # Auch ein beschränkter Abschnitt darüber zählt: sonst läse jedermann im Netz, was
        # Angemeldete nicht sehen dürfen.
        return jsonify(error="Diese Seite liegt in einem lesebeschränkten Bereich und kann nicht "
                             "öffentlich freigegeben werden. Bitte zuerst die Beschränkung aufheben."), 400
    if d.get("is_public") and d.get("public_children"):
        # Sonst geriete eine beschränkte Unterseite durch die Freigabe des Abschnitts ins Netz.
        drin = db.query(
            "WITH RECURSIVE teil(id) AS (SELECT id FROM wiki_pages WHERE id = ? "
            "  UNION SELECT k.id FROM wiki_pages k JOIN teil ON k.parent_id = teil.id) "
            "SELECT title FROM wiki_pages WHERE id IN (SELECT id FROM teil) AND id != ? "
            "  AND read_restricted = 1 AND deleted_at IS NULL ORDER BY title LIMIT 5", (pid, pid))
        if drin:
            namen = ", ".join(f"„{r['title']}“" for r in drin)
            return jsonify(error="In diesem Abschnitt liegen lesebeschränkte Seiten: " + namen +
                                 ". Bitte erst deren Beschränkung aufheben oder sie herausnehmen."), 400
    pub = 1 if d.get("is_public") else 0
    kids = 1 if (pub and d.get("public_children")) else 0
    db.execute("UPDATE wiki_pages SET is_public = ?, public_children = ? WHERE id = ?", (pub, kids, pid))
    return jsonify(page=page_json(_get_page(pid)))


# --- Kommentare ------------------------------------------------------------------------
# Jeder Endpunkt hier prüft das Leserecht an der Seite, zu der der Kommentar gehört – auch die
# schreibenden: ein Kommentar gibt Text aus der Seite wieder (die Fundstelle) und meldet sich
# bei ihren Beobachtern. Wie bei Seiten und Fassungen bedeutet 404 „gibt es nicht“ und 403
# „gibt es, aber nicht für dich“; dass eine Kennung vergeben ist, verrät für sich genommen
# nichts über den Inhalt.

def _comment_json(c, page):
    me = current_user()
    out = dict(c)
    out["can_delete"] = bool(me and (darf_inhalte(me) or c["user_id"] == me["id"] or page["created_by"] == me["id"]))
    out["can_edit"] = bool(me and (is_admin(me) or c["user_id"] == me["id"]))
    return out


def _comment_page(c):
    """Die Seite zu einem Kommentar – ausdrücklich auch aus dem Papierkorb. _get_page blendet
    gelöschte Seiten aus; ohne Seite gäbe es nichts, woran die Rechte hängen."""
    return db.query("SELECT * FROM wiki_pages WHERE id = ?", (int(c["page_id"]),), one=True)


@bp.get("/pages/<int:pid>/comments")
@login_required
def list_comments(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    rows = db.query("SELECT c.*, u.name AS user_name FROM wiki_comments c LEFT JOIN users u ON u.id = c.user_id "
                    "WHERE c.page_id = ? ORDER BY c.id", (pid,))
    return jsonify(comments=[_comment_json(c, p) for c in rows])


@bp.post("/pages/<int:pid>/comments")
@login_required
def add_comment(pid):
    p = _get_page(pid)
    if not p:
        return jsonify(error="Seite nicht gefunden"), 404
    # Noch vor dem Rumpf: eine Antwort bekommt die geerbte Fundstelle zurückgeliefert (siehe
    # unten), und Kommentar-Kennungen sind durchzählbar. Ohne diese Prüfung ließe sich damit
    # Text aus einer beschränkten Seite herausziehen.
    if not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    d = json_body()
    body = (d.get("body") or "").strip()
    if not body:
        return jsonify(error="Der Kommentar ist leer."), 400
    parent_id = d.get("parent_id") or None
    quote = (d.get("quote") or "").strip()[:500]
    if parent_id:
        parent = db.query("SELECT * FROM wiki_comments WHERE id = ? AND page_id = ?", (parent_id, pid), one=True)
        if not parent:
            return jsonify(error="Kommentar nicht gefunden."), 400
        quote = parent["quote"]
    if parent_id:
        # Eine Antwort erbt die Fundstelle des Kommentars, an dem sie hängt.
        before = parent["quote_before"] if "quote_before" in parent else ""
        after = parent["quote_after"] if "quote_after" in parent else ""
    else:
        before = (d.get("quote_before") or "").strip()[:120]
        after = (d.get("quote_after") or "").strip()[:120]
    cid = db.execute(
        "INSERT INTO wiki_comments (page_id, parent_id, user_id, quote, quote_before, quote_after, body, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (pid, parent_id, current_user()["id"], quote, before, after, body[:5000], db.now()))
    c = db.query("SELECT c.*, u.name AS user_name FROM wiki_comments c LEFT JOIN users u ON u.id = c.user_id WHERE c.id = ?",
                 (cid,), one=True)
    notify_watchers(p, "Es gibt einen neuen Kommentar")
    return jsonify(comment=_comment_json(c, p)), 201


@bp.put("/comments/<int:cid>")
@login_required
def update_comment(cid):
    c = db.query("SELECT * FROM wiki_comments WHERE id = ?", (cid,), one=True)
    if not c:
        return jsonify(error="Kommentar nicht gefunden"), 404
    p = _comment_page(c)
    # Wer die Seite nicht lesen darf, rührt auch ihren Kommentarstrang nicht an: „erledigt“
    # wirkt auf alle Antworten mit und wäre sonst eine Fernsteuerung in einer fremden Seite.
    if not p or not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    if not _comment_json(c, p)["can_delete"]:
        return jsonify(error="Keine Berechtigung"), 403
    d = json_body()
    if "resolved" in d:
        db.execute("UPDATE wiki_comments SET resolved = ? WHERE id = ? OR parent_id = ?",
                   (1 if d["resolved"] else 0, cid, cid))
    if "body" in d:
        # Den Text ändern darf nur, wer ihn geschrieben hat – „erledigt“ dagegen auch der Seitenersteller.
        me = current_user()
        if c["user_id"] != me["id"] and not darf_inhalte(me):
            return jsonify(error="Nur der Verfasser kann seinen Kommentar ändern."), 403
        body = (d.get("body") or "").strip()
        if not body:
            return jsonify(error="Der Kommentar ist leer."), 400
        db.execute("UPDATE wiki_comments SET body = ? WHERE id = ?", (body[:5000], cid))
    return jsonify(ok=True)


@bp.delete("/comments/<int:cid>")
@login_required
def delete_comment(cid):
    c = db.query("SELECT * FROM wiki_comments WHERE id = ?", (cid,), one=True)
    if not c:
        return jsonify(error="Kommentar nicht gefunden"), 404
    p = _comment_page(c)
    if not p or not can_read(p):
        return jsonify(error="Diese Seite ist nur für freigegebene Nutzer sichtbar."), 403
    if not _comment_json(c, p)["can_delete"]:
        return jsonify(error="Nur der Kommentator, der Seitenersteller oder ein Administrator darf löschen."), 403
    db.execute("DELETE FROM wiki_comments WHERE id = ?", (cid,))
    return jsonify(ok=True)


# --- Dateien (Bilder, Videos) für Artikel -----------------------------------------------

@bp.post("/files")
@login_required
def upload_file():
    f = request.files.get("file") or request.files.get("image")
    if not f:
        return jsonify(error="Keine Datei empfangen."), 400
    try:
        name, kind = store_wiki_file(f, current_app.config["MEDIA_DIR"])
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        return jsonify(error=f"Datei konnte nicht verarbeitet werden ({exc})."), 400
    db.execute("INSERT INTO wiki_files (file, original_name, user_id, created_at) VALUES (?,?,?,?)",
               (name, f.filename or "", current_user()["id"], db.now()))
    url = f"/media/wiki/{name}"
    return jsonify(url=url, kind=kind, data={"filePath": url})


@bp.post("/files/drehung")
@login_required
def rotate_file():
    """Ein Artikelbild um eine Vierteldrehung kippen. Wie beim Zuschnitt entsteht eine neue
    Datei; das Ausgangsbild bleibt liegen."""
    d = request.get_json(silent=True) or {}
    name = str(d.get("file") or "").replace("/media/wiki/", "", 1)
    if not name:
        return jsonify(error="Kein Bild angegeben."), 400
    try:
        neu = rotate_wiki_image(current_app.config["MEDIA_DIR"], name, d.get("grad"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        return jsonify(error=f"Das Bild ließ sich nicht drehen ({exc})."), 400
    db.execute("INSERT INTO wiki_files (file, original_name, user_id, created_at) VALUES (?,?,?,?)",
               (neu, name, current_user()["id"], db.now()))
    return jsonify(url=f"/media/wiki/{neu}")


@bp.post("/files/zuschnitt")
@login_required
def crop_file():
    """Ausschnitt eines Artikelbildes. Das Ergebnis ist eine neue Datei – das Ausgangsbild
    bleibt liegen, damit ein Zuschnitt sich rückgängig machen lässt und ein Bild, das an
    zwei Stellen steht, nicht an beiden seine Ränder verliert."""
    d = request.get_json(silent=True) or {}
    name = str(d.get("file") or "").replace("/media/wiki/", "", 1)
    if not name:
        return jsonify(error="Kein Bild angegeben."), 400
    try:
        neu = crop_wiki_image(current_app.config["MEDIA_DIR"], name,
                              (d.get("x"), d.get("y"), d.get("w"), d.get("h")))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        return jsonify(error=f"Das Bild ließ sich nicht zuschneiden ({exc})."), 400
    db.execute("INSERT INTO wiki_files (file, original_name, user_id, created_at) VALUES (?,?,?,?)",
               (neu, name, current_user()["id"], db.now()))
    return jsonify(url=f"/media/wiki/{neu}")


# --- Öffentliche Seiten (ohne Login) ----------------------------------------------------------

def _public_page_json(p):
    return {k: p[k] for k in ("id", "title", "slug", "parent_id", "content", "format", "updated_at")}


@public_bp.get("/index")
def public_index():
    """Alle freigegebenen Einstiegsseiten (Seiten, die selbst freigegeben sind)."""
    rows = db.query("SELECT id, title, slug, public_children, updated_at FROM wiki_pages WHERE is_public = 1 AND deleted_at IS NULL "
                    "ORDER BY position, title COLLATE NOCASE")
    return jsonify(pages=rows)


@public_bp.get("/search")
def public_search():
    """Suche im öffentlichen Wiki – nur über freigegebene Seiten."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify(results=[])
    terms = [t for t in re.split(r"\s+", q) if t][:6]
    where = " AND ".join(["(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"] * len(terms))
    args = []
    for t in terms:
        args += [_like(t), _like(t)]
    rows = db.query(
        f"SELECT id, title, slug, content, format, parent_id, is_public, public_children FROM wiki_pages "
        f"WHERE deleted_at IS NULL AND {where} ORDER BY title COLLATE NOCASE LIMIT 500", args)
    results = []
    for r in rows:
        if not is_public(r):
            continue
        text = plain_text(r["content"])
        low = text.lower()
        hit = min([i for i in (low.find(t.lower()) for t in terms) if i >= 0], default=-1)
        snippet = ""
        if hit >= 0:
            start = max(0, hit - 60)
            snippet = ("…" if start else "") + text[start:hit + 140] + ("…" if len(text) > hit + 140 else "")
        results.append({"title": r["title"], "slug": r["slug"], "snippet": snippet})
        if len(results) >= 20:
            break
    return jsonify(results=results, terms=terms)


@public_bp.get("/pages/<slug>")
def public_page(slug):
    p = _get_page(slug)
    if not p or not is_public(p):
        return jsonify(error="Diese Seite ist nicht öffentlich."), 404
    root = public_root(p)
    tree_rows = []
    if root and root["public_children"]:
        def collect(pid):
            # Beschränkte Seiten samt allem darunter bleiben draußen – der Baum steht ohne Anmeldung.
            for k in db.query("SELECT id, title, slug, parent_id FROM wiki_pages "
                              "WHERE parent_id = ? AND deleted_at IS NULL AND read_restricted = 0 "
                              "ORDER BY position, title COLLATE NOCASE", (pid,)):
                tree_rows.append(k)
                collect(k["id"])
        tree_rows.append({"id": root["id"], "title": root["title"], "slug": root["slug"], "parent_id": None})
        collect(root["id"])
    else:
        tree_rows.append({"id": p["id"], "title": p["title"], "slug": p["slug"], "parent_id": None})
    return jsonify(page=_public_page_json(p), tree=tree_rows, root_slug=root["slug"] if root else p["slug"])


def file_is_public(filename):
    """Ein Wiki-Anhang darf ohne Login gezeigt werden, wenn ihn eine öffentliche Seite einbindet.
    Die Zuordnung steht indiziert in wiki_page_files – kein LIKE über alle Seiteninhalte."""
    # Genauso normalisiert wie beim Eintragen in file_refs, sonst passt ein kodierter Name nicht.
    ref = unquote(filename or "").strip("/")
    rows = db.query("SELECT p.* FROM wiki_page_files f JOIN wiki_pages p ON p.id = f.page_id "
                    "WHERE f.file = ? AND p.deleted_at IS NULL", (ref,))
    return any(is_public(p) for p in rows)
