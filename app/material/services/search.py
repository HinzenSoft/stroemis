"""Suche im Katalog und nach Artikelnummern – serverseitig, mit Index und Seiten.

Der Katalog wird nie als Ganzes an den Browser geschickt (bei homebase lief die Live-Suche über den
ganzen Katalog in Zeitüberschreitungen). Gesucht wird mit dem Trigramm-Volltextindex aus models.py:
Er findet Teilstücke ab drei Zeichen („234“ in „M-001234“) über einen Index. Kürzere Wörter und
Datenbanken ohne Index laufen über LIKE – bei ein, zwei Zeichen ist ohnehin fast alles ein Treffer.

Seit Phase 2 findet die Artikelsuche nur, was das Konto sieht (rechte.artikel_filter) – in den Treffern wie in der
Gesamtzahl; ebenso zählt die Spalte „Bestand“ im Katalog. Was darüber hinausgeht, ist die globale Suche nach der
exakten Herstellerseriennummer (globalsuche, mit Protokoll).
"""
import re
import sqlite3

from ... import db
from . import Abgelehnt
from .nummern import inventar_ziffern
from .rechte import artikel_filter

PRO_SEITE_MAX = 100

# Sortierbare Spalten der Listen: Name in der Anfrage → SQL-Ausdruck. Leere Werte stehen immer hinten; bei
# Gleichstand gilt die übliche Reihenfolge der Liste. „intervall“ im Katalog sortiert produkte() selbst, weil
# das wirksame Intervall von einer Oberkategorie geerbt sein kann.
PRODUKT_SORTIERUNG = {
    "hersteller": "p.manufacturer COLLATE NOCASE",
    "produkt": "p.model COLLATE NOCASE",
    "kategorie": "c.name COLLATE NOCASE",
    "materialart": "p.material_kind",
    "lebensdauer": "p.lifetime_years",
    "bestand": "bestand",
}
PRODUKT_STANDARD = "p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE, p.article_no COLLATE NOCASE"
RICHTUNGEN = ("auf", "ab")


def sortierung(sortierbar, feld, richtung, standard):
    """ORDER BY für eine sortierbare Spalte – oder die übliche Reihenfolge, wenn keine gewählt ist."""
    if not feld:
        return standard
    if feld not in sortierbar:
        raise Abgelehnt("Nach dieser Spalte lässt sich nicht sortieren.")
    if richtung not in RICHTUNGEN:
        raise Abgelehnt("Sortierrichtung ist „auf“ oder „ab“.")
    ausdruck = sortierbar[feld]
    return f"({ausdruck}) IS NULL, {ausdruck} {'DESC' if richtung == 'ab' else 'ASC'}, {standard}"


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


def produkte(q="", kategorie_id=None, seite=1, pro_seite=25, sort=None, richtung="auf"):
    """Katalogsuche über Hersteller, Modell, Artikelnummer, Norm und Beschreibung. Liefert (Zeilen, Gesamtzahl).
    Jedes Wort muss irgendwo vorkommen. Die Beschreibung (der Zusatz hinter dem Modell, etwa „Screwlock“) steht nicht
    im Volltextindex und wird mit LIKE durchsucht – sie ist kurz, und der Katalog hat Hunderte, nicht Millionen
    Produkte; den Index umzubauen hieße einen Schemaschritt."""
    seite, pro_seite = seiten(seite, pro_seite)
    if sort == "intervall":
        if richtung not in RICHTUNGEN:
            raise Abgelehnt("Sortierrichtung ist „auf“ oder „ab“.")
        ordnung = PRODUKT_STANDARD
    else:
        ordnung = sortierung(PRODUKT_SORTIERUNG, sort, richtung, PRODUKT_STANDARD)
    bedingungen, args = [], []
    fts = volltext_an()
    lang = [w for w in woerter(q) if len(w) >= 3] if fts else []
    kurz = [w for w in woerter(q) if w not in lang]
    for w in lang:
        bedingungen.append("(p.id IN (SELECT rowid FROM mat_product_fts WHERE mat_product_fts MATCH ?) "
                           "OR p.description LIKE ? ESCAPE '\\')")
        args += [_phrase(w), _like(w)]
    for w in kurz:
        bedingungen.append("(p.manufacturer LIKE ? ESCAPE '\\' OR p.model LIKE ? ESCAPE '\\' "
                           "OR p.article_no LIKE ? ESCAPE '\\' OR p.norm LIKE ? ESCAPE '\\' "
                           "OR p.description LIKE ? ESCAPE '\\')")
        args += [_like(w)] * 5
    if kategorie_id:
        ids = kategorie_und_unterkategorien(kategorie_id)
        bedingungen.append(f"p.category_id IN ({','.join('?' * len(ids))})")
        args += ids
    where = ("WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
    gesamt = _abfragen(f"SELECT COUNT(*) AS n FROM mat_product p {where}", tuple(args), one=True)["n"]
    auswahl = (f"SELECT p.*, c.name AS category_name, "
               f"(SELECT COUNT(*) FROM mat_item i WHERE i.product_id = p.id AND i.lock_state <> 'ausgesondert' "
               f"AND {artikel_filter('i')}) AS bestand "
               f"FROM mat_product p JOIN mat_category c ON c.id = p.category_id {where} ORDER BY {ordnung}")
    if sort == "intervall":
        # Das wirksame Intervall (Produkt, sonst Kategorie oder Oberkategorie) – in Python, dann die Seite.
        from .interval import herstellerseite
        alle = _abfragen(auswahl, tuple(args))
        mit = [(herstellerseite(r)[0], i, r) for i, r in enumerate(alle)]
        mit.sort(key=lambda x: (x[0] is None, -(x[0] or 0) if richtung == "ab" else (x[0] or 0), x[1]))
        start = (seite - 1) * pro_seite
        return [r for _, _, r in mit[start:start + pro_seite]], gesamt
    rows = _abfragen(f"{auswahl} LIMIT ? OFFSET ?", (*args, pro_seite, (seite - 1) * pro_seite))
    return rows, gesamt


# Seriennummer eines Bestandteils am Artikel (Schritt 25) – Teiltreffer wie bei der Seriennummer.
_TEILNUMMER = ("EXISTS (SELECT 1 FROM mat_item_component_serial s WHERE s.item_id = i.id "
               "AND s.serial_no LIKE ? ESCAPE '\\')")


def artikel(q, seite=1, pro_seite=25, sort=None, richtung="auf"):
    """Suche nach Serien-, Inventar- und Herstellernummer (Artikelnummer des Produkts), mit
    Teiltreffern. Liefert (Zeilen, Gesamtzahl); Zeilen tragen Produkt- und Ordnerangaben. Ohne gewählte
    Sortierung steht ein genauer Treffer oben. Seit Schritt 25 auch nach der Seriennummer eines Bestandteils (Treffer ist
    der Artikel, in dem das Teil steckt – sichtbar wie jeder Artikel; nicht im Volltextindex, die Tabelle ist klein)."""
    from .bestand import artikel_sortierung, demo_sql
    seite, pro_seite = seiten(seite, pro_seite)
    eigene = sortierung(artikel_sortierung(), sort, richtung, "i.inventory_no") if sort else None
    ws = woerter(q)
    if not ws:
        return [], 0
    fts = volltext_an()
    teile, args = [], []
    for w in ws:
        if fts and len(w) >= 3:
            teile.append("(i.id IN (SELECT rowid FROM mat_item_fts WHERE mat_item_fts MATCH ?) "
                         "OR i.product_id IN (SELECT rowid FROM mat_product_fts WHERE mat_product_fts MATCH ?) "
                         f"OR {_TEILNUMMER})")
            args += [_phrase(w), "article_no : " + _phrase(w), _like(w)]
        else:
            teile.append("(i.serial_no LIKE ? ESCAPE '\\' OR i.inventory_no LIKE ? ESCAPE '\\' "
                         f"OR p.article_no LIKE ? ESCAPE '\\' OR {_TEILNUMMER})")
            args += [_like(w)] * 4
    where = " AND ".join(teile)
    # „m-12“ oder „12“ meint oft genau die Inventarnummer M-000012 – die gehört auch dann in die
    # Treffer, wenn die Ziffern zu kurz für den Index sind, und steht ganz oben.
    ziffern = inventar_ziffern(" ".join(ws))
    genau = f"M-{ziffern:06d}" if ziffern is not None else ""
    if genau:
        where = f"(({where}) OR i.inventory_no = ?)"
        args.append(genau)
    basis = f"FROM mat_item i JOIN mat_product p ON p.id = i.product_id WHERE ({where}) AND {artikel_filter('i')}"
    gesamt = _abfragen(f"SELECT COUNT(*) AS n {basis}", tuple(args), one=True)["n"]
    rows = _abfragen(
        f"SELECT i.*, p.manufacturer, p.model, p.article_no, p.material_kind, p.image AS product_image, "
        f"p.description AS product_description, "
        f"{demo_sql('i', 'p')} AS artikel_demo, e.id AS entwurf_id, e.inspector_name AS entwurf_pruefer, "
        f"e.inspector_user_id AS entwurf_pruefer_id, zu.name AS zugeordnet_name "
        f"{basis.replace(' WHERE ', ' LEFT JOIN mat_inspection e ON e.item_id = i.id AND e.completed_at IS NULL '
                         'LEFT JOIN users zu ON zu.id = i.assigned_user_id WHERE ', 1)} "
        f"ORDER BY {eigene + ', ' if eigene else ''}(i.inventory_no = ?) DESC, (lower(i.serial_no) = lower(?)) DESC, "
        f"i.inventory_no LIMIT ? OFFSET ?", (*args, genau, " ".join(ws), pro_seite, (seite - 1) * pro_seite))
    return rows, gesamt


def exakt_lokal(q):
    """Hat ein Artikel, den das Konto sieht, genau diese Seriennummer (ohne Groß- und Kleinschreibung, Leerraum
    zusammengezogen wie in der globalen Suche)? Die Oberfläche sagt dann beim Angebot der globalen Suche, dass diese
    nur Artikel außerhalb des eigenen Bereichs zeigt."""
    from .globalsuche import normalform
    n = normalform(q)
    if not n:
        return False
    return db.query(f"SELECT 1 FROM mat_item i WHERE (i.serial_no = ? COLLATE NOCASE OR EXISTS (SELECT 1 FROM "
                    f"mat_item_component_serial s WHERE s.item_id = i.id AND s.serial_no = ? COLLATE NOCASE)) "
                    f"AND {artikel_filter('i')} LIMIT 1", (n, n), one=True) is not None
