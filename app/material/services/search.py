"""Suche im Katalog und nach Artikelnummern – serverseitig, mit Index und Seiten.

Der Katalog wird nie als Ganzes an den Browser geschickt (bei homebase lief die Live-Suche über den
ganzen Katalog in Zeitüberschreitungen). Gesucht wird mit dem Trigramm-Volltextindex aus models.py:
Er findet Teilstücke ab drei Zeichen („234“ in „M-001234“) über einen Index. Kürzere Wörter und
Datenbanken ohne Index laufen über LIKE – bei ein, zwei Zeichen ist ohnehin fast alles ein Treffer.
"""
import re
import sqlite3

from ... import db
from . import Abgelehnt
from .nummern import inventar_ziffern

PRO_SEITE_MAX = 100


def volltext_an():
    row = db.query("SELECT wert FROM mat_meta WHERE schluessel = 'volltext'", one=True)
    return bool(row and row["wert"] == "1")


def _phrase(wort):
    return '"' + wort.replace('"', '""') + '"'


def _like(wort):
    return "%" + wort.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def woerter(q):
    # Steuerzeichen (auch NUL) gehören in keine Nummer – FTS5 hielte sie für ein offenes Anführungszeichen.
    q = re.sub(r"[\x00-\x1f\x7f]+", " ", q or "").strip()
    if len(q) > 200:
        raise Abgelehnt("Der Suchbegriff ist zu lang.")
    return [w for w in q.split() if w][:8]


def _abfragen(sql, args, one=False):
    """Eine Suchabfrage; was der Volltextindex nicht versteht, ist eine unbrauchbare Eingabe (400)."""
    try:
        return db.query(sql, args, one=one)
    except sqlite3.OperationalError as exc:
        if "fts5" in str(exc).lower() or "unterminated" in str(exc).lower() or "syntax" in str(exc).lower():
            raise Abgelehnt("Dieser Suchbegriff lässt sich nicht verarbeiten.")
        raise


def seiten(seite, pro_seite):
    try:
        seite = max(1, int(seite or 1))
        pro_seite = min(PRO_SEITE_MAX, max(1, int(pro_seite or 25)))
    except (TypeError, ValueError):
        raise Abgelehnt("Seite und Seitengröße müssen Zahlen sein.")
    return seite, pro_seite


def kategorie_und_unterkategorien(kid):
    return [r["id"] for r in db.query(
        "WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT c.id FROM mat_category c JOIN baum b ON c.parent_id = b.id) "
        "SELECT id FROM baum", (kid,))]


def produkte(q="", kategorie_id=None, seite=1, pro_seite=25):
    """Katalogsuche über Hersteller, Modell, Artikelnummer und Norm. Liefert (Zeilen, Gesamtzahl)."""
    seite, pro_seite = seiten(seite, pro_seite)
    bedingungen, args = [], []
    fts = volltext_an()
    lang = [w for w in woerter(q) if len(w) >= 3] if fts else []
    kurz = [w for w in woerter(q) if w not in lang]
    if lang:
        bedingungen.append("p.id IN (SELECT rowid FROM mat_product_fts WHERE mat_product_fts MATCH ?)")
        args.append(" ".join(_phrase(w) for w in lang))
    for w in kurz:
        bedingungen.append("(p.manufacturer LIKE ? ESCAPE '\\' OR p.model LIKE ? ESCAPE '\\' "
                           "OR p.article_no LIKE ? ESCAPE '\\' OR p.norm LIKE ? ESCAPE '\\')")
        args += [_like(w)] * 4
    if kategorie_id:
        ids = kategorie_und_unterkategorien(kategorie_id)
        bedingungen.append(f"p.category_id IN ({','.join('?' * len(ids))})")
        args += ids
    where = ("WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
    gesamt = _abfragen(f"SELECT COUNT(*) AS n FROM mat_product p {where}", tuple(args), one=True)["n"]
    rows = _abfragen(
        f"SELECT p.*, c.name AS category_name, "
        f"(SELECT COUNT(*) FROM mat_item i WHERE i.product_id = p.id AND i.lock_state <> 'ausgesondert') AS bestand "
        f"FROM mat_product p JOIN mat_category c ON c.id = p.category_id {where} "
        f"ORDER BY p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE, p.article_no COLLATE NOCASE "
        f"LIMIT ? OFFSET ?", (*args, pro_seite, (seite - 1) * pro_seite))
    return rows, gesamt


def artikel(q, seite=1, pro_seite=25):
    """Suche nach Serien-, Inventar- und Herstellernummer (Artikelnummer des Produkts), mit
    Teiltreffern. Liefert (Zeilen, Gesamtzahl); Zeilen tragen Produkt- und Ordnerangaben."""
    seite, pro_seite = seiten(seite, pro_seite)
    ws = woerter(q)
    if not ws:
        return [], 0
    fts = volltext_an()
    teile, args = [], []
    for w in ws:
        if fts and len(w) >= 3:
            teile.append("(i.id IN (SELECT rowid FROM mat_item_fts WHERE mat_item_fts MATCH ?) "
                         "OR i.product_id IN (SELECT rowid FROM mat_product_fts WHERE mat_product_fts MATCH ?))")
            args += [_phrase(w), "article_no : " + _phrase(w)]
        else:
            teile.append("(i.serial_no LIKE ? ESCAPE '\\' OR i.inventory_no LIKE ? ESCAPE '\\' "
                         "OR p.article_no LIKE ? ESCAPE '\\')")
            args += [_like(w)] * 3
    where = " AND ".join(teile)
    # „m-12“ oder „12“ meint oft genau die Inventarnummer M-000012 – die gehört auch dann in die
    # Treffer, wenn die Ziffern zu kurz für den Index sind, und steht ganz oben.
    ziffern = inventar_ziffern(" ".join(ws))
    genau = f"M-{ziffern:06d}" if ziffern is not None else ""
    if genau:
        where = f"(({where}) OR i.inventory_no = ?)"
        args.append(genau)
    basis = f"FROM mat_item i JOIN mat_product p ON p.id = i.product_id WHERE {where}"
    gesamt = _abfragen(f"SELECT COUNT(*) AS n {basis}", tuple(args), one=True)["n"]
    rows = _abfragen(
        f"SELECT i.*, p.manufacturer, p.model, p.article_no, p.material_kind, p.image AS product_image, "
        f"p.demo AS product_demo, e.id AS entwurf_id, e.inspector_name AS entwurf_pruefer, "
        f"e.inspector_user_id AS entwurf_pruefer_id "
        f"{basis.replace(' WHERE ', ' LEFT JOIN mat_inspection e ON e.item_id = i.id AND e.completed_at IS NULL WHERE ', 1)} "
        f"ORDER BY (i.inventory_no = ?) DESC, (lower(i.serial_no) = lower(?)) DESC, i.inventory_no "
        f"LIMIT ? OFFSET ?", (*args, genau, " ".join(ws), pro_seite, (seite - 1) * pro_seite))
    return rows, gesamt
