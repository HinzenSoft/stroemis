"""Verweise auf die Anleitung in der Strömipedia (Wunsch vom 28.10.2026): Links aus der Materialablage auf den Artikel
„Materialablage“ und seine Unterseiten – am Ende einer Info („i“), als „Anleitung“ im Seitenkopf, als Hinweis auf der
Übersicht und im Willkommen beim allerersten Besuch der Übersicht.

Gefunden wird eine Seite über ihren TITEL im Teilbaum unter der obersten Artikelseite (Titel WURZEL), nicht über ihre
Adresse: Der Artikel kommt per ZIP-Import, und der Import bildet die Adresse aus dem Titel (api_wiki.unique_slug – bei
einer Doppelung „-2“). Die Tabelle THEMEN steht nur hier; die Oberfläche fragt nach dem Schlüssel. Ein Anker kommt nur
an die Adresse, wenn die Seite eine Überschrift mit genau dieser Kennung hat (wie markdown.js buildToc sie bildet) –
sonst führt der Link an den Anfang der Seite.

Rechte (Entscheidung des Nutzers vom 28.10.2026, „Nur wer lesen darf“): Jede Seite einzeln mit den Regeln der
Strömipedia (wikiverweis.darf_lesen – Stufe in der Strömipedia: can_read samt Lesebeschränkung; Lesemodus: nur
öffentliche Seiten). Gibt es die Seite nicht, liegt sie im Papierkorb oder darf das Konto sie nicht lesen, fehlt der
Schlüssel – kein Link, kein Titel, keine Meldung. An den Rechten der Strömipedia ändert sich nichts.

Willkommen: je Konto einmal, gemerkt in mat_meta (Schlüssel „willkommen:<Konto>“, Wert der Zeitpunkt) – ohne
Schemaschritt; die Zeile geht mit dem Konto (loeschung.konto_loeschen_vorbereiten), ein Zurücksetzen des Moduls auf dev
(zuruecksetzen.py) leert sie mit. Gemerkt wird, wenn die Übersicht mit dem Dialog gezeichnet wird: Wer die Anleitung
(noch) nicht lesen darf, bekommt ihn erst, sobald er es darf."""
import re
import sqlite3
from urllib.parse import quote

from flask import current_app, g, has_request_context

from ... import db
from . import wikiverweis

WURZEL = "Materialablage"
TIEFE_MAX = 6             # Ebenen unter der Wurzel, die gesucht werden (der Artikel hat zwei)
SEITEN_MAX = 500          # Seiten im Teilbaum, die höchstens gelesen werden

# Thema → (Titel der Seite, Kennung der Überschrift oder ""). Die Liste der Stellen steht in README („Verweise auf die
# Anleitung“) und planung/material-phase4/wikiverweise_tabelle.md; Titel und Überschriften dürfen sich im Artikel nicht
# unbemerkt ändern – fehlt eine Überschrift, führt der Link an den Anfang der Seite, fehlt die Seite, gibt es keinen.
THEMEN = {
    # Übersicht: Hinweis und Willkommen – die oberste Artikelseite
    "uebersicht": (WURZEL, ""),
    # „Anleitung“ hinter der Überschrift bzw. im „i“ an der Überschrift – je Ansicht (material.js, anleitungKopf)
    "pruefungen": ("Prüfung", ""),
    "durchgaenge": ("Prüfdurchgang", "abgeschlossene-pruefdurchgaenge"),
    "durchgang": ("Prüfdurchgang", ""),
    "bestand": ("Bestand", ""),
    "ordner": ("Bestand", "artikelliste-des-ordners"),
    "ordner_system": ("Bestand", "systemordner-gesperrt-und-ausgesondert"),
    "artikel": ("Artikelseite und Lebenslauf", ""),
    "artikel_neu": ("Artikel anlegen", ""),
    "pruefung_neu": ("Prüfung", "pruefung-starten"),
    "pruefung": ("Prüfung", ""),
    "antraege": ("Änderungsanträge", ""),
    "katalog": ("Katalog", ""),
    "produkt": ("Katalog", "produktseite"),
    "formular": ("Prüfformulare", ""),
    "meldungen": ("Produktmeldungen", ""),
    "suche": ("Suche, QR-Code und globale Suche", "nummernsuche"),
    "bestandsimport": ("Bestandsimport", ""),
    "bericht": ("Jahresbericht und Export", "jahresbericht"),
    "meine_psa": ("Meine PSA", ""),
    "echtheit": ("Nachweise und Protokolle", "seite-echtheit-pruefen"),
    # „Mehr dazu in der Strömipedia“ am Ende einer Info („i“)
    "faelligkeiten_je_ordner": ("Fälligkeiten und Erinnerungen", "uebersicht"),
    "mangel": ("Sperre, Mangel, Verlust und Aussonderung", "mangelmeldung"),
    "durchgaenge_laufend": ("Prüfdurchgang", ""),
    "zu_pruefen": ("Fälligkeiten und Erinnerungen", "status"),
    "offene_pruefungen": ("Prüfung", "speichern-und-reservierung"),
    "ordnerarten": ("Bestand", "ordnerarten"),
    "pruefintervall": ("Fälligkeiten und Erinnerungen", "pruefintervall"),
    "freigaben": ("Rechtesystem", "freigaben-je-ordner"),
    "qr_code": ("Suche, QR-Code und globale Suche", "qr-code-und-nfc"),
    "nummern": ("Bestand", "nummern"),
    "kategorie_dokumente": ("Katalog", "dokumente-an-kategorien"),
    "katalogimport": ("Katalogimport und -export", "was-der-import-tut"),
    "bestandteile": ("Katalog", "bestandteil-liste"),
    "pruefformular": ("Prüfformulare", "generisch-und-spezifisch"),
    "herstellerdokumente": ("Katalog", "herstellerdokumente"),
    "pruefanleitung": ("Prüfformulare", "pruefanleitung-aus-der-stroemipedia"),
    "pruefpunkte": ("Prüfformulare", "pruefpunkte"),
    "eingangspruefung": ("Prüfung", "pruefarten"),
    "kritisch": ("Prüfformulare", "pruefpunkte"),
    "pruefsumme": ("Nachweise und Protokolle", "pruefsumme-und-stempel"),
    "rueckruf": ("Rückrufe", "anlegen"),
    "import_spalten": ("Bestandsimport", "wie-werte-gelesen-werden"),
}

WILLKOMMEN = "willkommen:{uid}"           # Schlüssel in mat_meta


# --- Kennungen der Überschriften wie markdown.js buildToc -----------------------------------------------------------
# Kleinschreibung, ä/ö/ü/ß ausgeschrieben, alles andere als a–z und 0–9 wird „-“; trifft die Kennung einen Vorsatz des
# Rahmens der Strömipedia (RAHMEN_H in markdown.js), kommt „-abschnitt“ dazu; Doppelte zählen mit „-2“ … weiter.
_RAHMEN_H = re.compile(r"^(?:(?:dlg|toast|toc|comments|article|tree|map|favorites|editor|logout|ck)(?:-|$)|(?:wiki|pg|ed|"
                       r"lb|al|up|au|sh|ic|lk|be|ce|dr|loc|imp|btn|comment|search|seiten|info|em|fr|tb|eb|bs|alt|iw|ih|"
                       r"rev|home)-)")
_UEBERSCHRIFT = re.compile(r"^ {0,3}(#{1,5})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_ZAUN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# Was in der Leseansicht nicht als Text der Überschrift ankommt: Bilder ganz, von Links nur der Text, HTML-Marken, „*“
# und „`“, „_“ nur am Wortrand (mitten im Wort bleibt es Text wie in marked).
_AUSZEICHNUNG = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)|<[^>]*>|[*`]|(?<!\w)_+|_+(?!\w)")
_kennungen_speicher = {}                  # Seite → (updated_at, Kennungen) – je Arbeitsprozess


def kennungen(inhalt):
    """Die Kennungen aller Überschriften (h1–h5) eines Seitentexts in Markdown, außerhalb von Codeblöcken."""
    gesehen, zaun = set(), None
    for zeile in (inhalt or "").splitlines():
        m = _ZAUN.match(zeile)
        if m:
            if zaun is None:
                zaun = m.group(1)[0]
            elif m.group(1)[0] == zaun:
                zaun = None
            continue
        m = None if zaun else _UEBERSCHRIFT.match(zeile)
        if not m:
            continue
        text = _AUSZEICHNUNG.sub(lambda t: t.group(1) or "", m.group(2)).strip().lower()
        for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            text = text.replace(alt, neu)
        kennung = re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "abschnitt"
        if _RAHMEN_H.match(kennung):
            kennung += "-abschnitt"
        basis, n = kennung, 2
        while kennung in gesehen:
            kennung, n = f"{basis}-{n}", n + 1
        gesehen.add(kennung)
    return gesehen


def _hat_anker(seite, anker):
    stand = _kennungen_speicher.get(seite["id"])
    if not stand or stand[0] != seite["updated_at"]:
        zeile = db.query("SELECT content FROM wiki_pages WHERE id = ?", (seite["id"],), one=True)
        stand = (seite["updated_at"], kennungen(zeile["content"] if zeile else ""))
        _kennungen_speicher[seite["id"]] = stand
    return anker in stand[1]


# --- Seiten finden ----------------------------------------------------------------------------------------------------

_SPALTEN = "id, title, slug, parent_id, created_by, is_public, public_children, read_restricted, deleted_at, updated_at"


def _wurzeln():
    """Kandidaten für die oberste Artikelseite: Titel WURZEL, nicht im Papierkorb, keine Vorlage – zuerst die mit
    Unterseiten (ein gleichnamiger Einzelartikel ist nicht gemeint), dann die neueste (ein späterer Import)."""
    return db.query(f"SELECT {_SPALTEN}, EXISTS (SELECT 1 FROM wiki_pages k WHERE k.parent_id = p.id AND k.deleted_at IS NULL)"
                    " AS hat_kinder FROM wiki_pages p WHERE title = ? AND deleted_at IS NULL AND is_template = 0 "
                    "ORDER BY hat_kinder DESC, id DESC", (WURZEL,))


def _teilbaum(wurzel):
    """Titel → Seite im Teilbaum unter der Wurzel (ohne Papierkorb und Vorlagen); bei gleichem Titel die höhere Ebene,
    dann die vordere Stelle."""
    seiten, ebene, tiefe = {}, [wurzel["id"]], 0
    gelesen = 0
    while ebene and tiefe < TIEFE_MAX and gelesen < SEITEN_MAX:
        marken = ",".join("?" * len(ebene))
        zeilen = db.query(f"SELECT {_SPALTEN} FROM wiki_pages WHERE parent_id IN ({marken}) AND deleted_at IS NULL "
                          f"AND is_template = 0 ORDER BY position, id LIMIT ?", (*ebene, SEITEN_MAX - gelesen))
        gelesen += len(zeilen)
        for z in zeilen:
            seiten.setdefault(z["title"].strip(), z)
        ebene, tiefe = [z["id"] for z in zeilen], tiefe + 1
    return seiten


def _user(user=None):
    if user is not None:
        return user
    if not has_request_context():
        return None
    from ...auth import current_user
    return current_user()


def _url(seite, anker=""):
    url = f"/stroemipedia/{quote(seite['slug'], safe='')}"
    return f"{url}#{anker}" if anker and _hat_anker(seite, anker) else url


def verweise(user=None):
    """{Thema: Adresse} für alles aus THEMEN, was das Konto in der Strömipedia lesen darf – leer ohne Konto oder ohne
    Artikel. Je Anfrage einmal gerechnet (g)."""
    user = _user(user)
    if not user:
        return {}
    speicher = g.setdefault("material_anleitung", {}) if has_request_context() else {}
    if user["id"] in speicher:
        return speicher[user["id"]]
    out = {}
    # Die erste lesbare Wurzel; ist keine lesbar, trotzdem ihr Teilbaum – eine einzeln freigegebene Unterseite zählt
    # (die Wurzel selbst prüft die Schleife unten wie jede Seite).
    kandidaten = _wurzeln()
    wurzel = next((w for w in kandidaten if wikiverweis.darf_lesen(w, user)), kandidaten[0] if kandidaten else None)
    if wurzel:
        seiten = _teilbaum(wurzel)
        seiten[WURZEL] = wurzel             # eine gleichnamige Unterseite ist nicht die Wurzel
        lesbar = {}
        for thema, (titel, anker) in THEMEN.items():
            seite = seiten.get(titel)
            if not seite:
                continue
            if seite["id"] not in lesbar:
                lesbar[seite["id"]] = wikiverweis.darf_lesen(seite, user)
            if lesbar[seite["id"]]:
                out[thema] = _url(seite, anker)
    speicher[user["id"]] = out
    return out


def willkommen_einmal(user=None):
    """Für die Übersicht: die Adresse der Anleitung, wenn das Konto sie lesen darf und das Willkommen noch nie gesehen
    hat – und merkt es sich dann (genau einmal je Konto, auch bei zwei gleichzeitigen Aufrufen: INSERT OR IGNORE).
    Sonst None. Geschrieben wird nur beim ersten Mal; jeder spätere Besuch liest nur. Scheitert das Merken (Datenbank
    gesperrt), gibt es diesmal kein Willkommen – die Übersicht kommt trotzdem."""
    user = _user(user)
    url = verweise(user).get("uebersicht") if user else None
    if not url:
        return None
    schluessel = WILLKOMMEN.format(uid=int(user["id"]))
    if db.query("SELECT 1 FROM mat_meta WHERE schluessel = ?", (schluessel,), one=True):
        return None
    try:
        neu = db.execute_zeilen("INSERT OR IGNORE INTO mat_meta (schluessel, wert) VALUES (?, ?)", (schluessel, db.now()))
    except sqlite3.Error as exc:
        current_app.logger.warning("Willkommen in der Materialablage: nicht gemerkt (Konto %s) – %s", user["id"], exc)
        return None
    return url if neu == 1 else None


def konto_vergessen(uid):
    """Beim Löschen eines Kontos (loeschung.py): der Merker des Willkommens geht mit."""
    db.execute("DELETE FROM mat_meta WHERE schluessel = ?", (WILLKOMMEN.format(uid=int(uid)),))
