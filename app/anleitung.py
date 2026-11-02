"""Verweise auf die Anleitung in der Strömipedia – für jedes Modul mit eigenem Artikel (Wunsch vom 28.10.2026 für die
Materialablage, seit dem 01.11.2026 auch Strömipedia, Ankerplätze und Riegenkarten; plan_anleitungsverweise.md).

Jedes Modul hat EINE Wurzel (Titel der obersten Artikelseite) und EINE Themen-Tabelle Thema → (Titel der Seite, Kennung
der Überschrift oder ""). Die Oberfläche fragt nach dem Thema; der Server gibt jeder Seite nur die Adressen mit, die das
Konto lesen darf (data-anleitung am Rahmen der Seite).

Gefunden wird eine Seite über ihren TITEL im Teilbaum unter der Wurzel, nicht über ihre Adresse: Die Artikel kommen per
ZIP-Import, und der Import bildet die Adresse aus dem Titel (api_wiki.unique_slug – bei einer Doppelung „-2“). Ein Anker
kommt nur an die Adresse, wenn die Seite eine Überschrift mit genau dieser Kennung hat (wie markdown.js buildToc sie
bildet) – sonst führt der Link an den Anfang der Seite.

Rechte (Entscheidung des Nutzers vom 28.10.2026, „Nur wer lesen darf“): Jede Seite einzeln mit den Regeln der
Strömipedia (wikiverweis.darf_lesen – Stufe in der Strömipedia: can_read samt Lesebeschränkung; Lesemodus: nur
freigegebene Seiten). Gibt es die Seite nicht, liegt sie im Papierkorb oder darf das Konto sie nicht lesen, fehlt der
Schlüssel – kein Link, kein Titel, keine Meldung. An den Rechten der Strömipedia ändert sich nichts.

Die Materialablage hat ihre Tabelle samt Willkommen weiter in app/material/services/anleitung.py; die Tabellen der drei
übrigen Module stehen hier (TABELLEN). Titel und Überschriften der Tabellen dürfen sich in den Artikeln nicht unbemerkt
ändern – README „Verweise auf die Anleitung“ nennt sie, tests/test_module_anleitung.py gleicht sie mit den Artikeln ab,
wenn sie auf dem Rechner liegen."""
import re
from urllib.parse import quote

from flask import g, has_request_context

from . import db

TIEFE_MAX = 6             # Ebenen unter der Wurzel, die gesucht werden (die Artikel haben zwei)
SEITEN_MAX = 500          # Seiten im Teilbaum, die höchstens gelesen werden

# Modul → (Wurzel, Themen). Die Stellen in der Oberfläche: wiki.js, map.js und pruefungen.js über S.anleitung
# (common.js); „Anleitung“ steht im Seitenkopf, „Mehr dazu in der Strömipedia“ am Ende einer vorhandenen Info („i“).
TABELLEN = {
    "wiki": ("Strömipedia", {
        # „Anleitung“ im Kopf der Übersicht – nie auf der Seite, auf die sie zeigt (wiki.js anleitungFuer)
        "uebersicht": ("Strömipedia", ""),
        # „Anleitung zur Strömipedia“ im Menü „⋯“ einer Seite und „Anleitung zum Editor“ im „⋯“ des Editors
        "seite": ("Lesen und Finden", "kopfzeile-einer-seite"),
        "editor": ("Der Editor", ""),
        # „Mehr dazu in der Strömipedia“ am Ende einer Info („i“)
        "papierkorb": ("Papierkorb, Export und Import", "papierkorb"),
        "bearbeiten_erlauben": ("Teilen und Freigaben", "bearbeiten-erlauben"),
        "textfarbe": ("Der Editor", "auswahlleiste"),
        "abschnitt_einbinden": ("Der Editor", "synchronisierte-abschnitte"),
        "spalten": ("Der Editor", "callouts-spalten-und-boxen"),
    }),
    "karte": ("Ankerplätze", {
        # „Anleitung“ im Kopf der Seitenleiste: Liste der Alben und ein Album
        "uebersicht": ("Ankerplätze", ""),
        "album": ("Alben", "album-in-der-seitenleiste"),
        # „Mehr dazu“ in der Info „Album“ der Dialoge
        "album_neu": ("Alben", "album-anlegen"),
        "album_bearbeiten": ("Alben", "album-bearbeiten"),
    }),
    "pruefungen": ("Riegenkarten", {
        # „Anleitung“ hinter der Überschrift: Lehrgangsliste, Lehrgangsseite, Katalogseite (die Katalogliste trägt
        # den Link in ihrem „i“ an der Überschrift)
        "uebersicht": ("Riegenkarten", ""),
        "lehrgang": ("Lehrgänge", "die-lehrgangsseite"),
        "katalog": ("Prüfungsleistungen und Kataloge", "katalogseite"),
        # „Mehr dazu“ am Ende einer Info („i“)
        "kataloge_info": ("Prüfungsleistungen und Kataloge", "pruefungsleistungskataloge"),
        "ausbilder": ("Lehrgänge", "leitung-und-referierende-eintragen"),
        "katalog_vorlage": ("Lehrgänge", "pruefungsleistungen-aus-einem-katalog"),
        "zeitansatz": ("Bewertung", "stoppuhr"),
        "kriterienliste": ("Prüfungsleistungen und Kataloge", "kriterienliste"),
        "import_datei": ("Teilnehmerliste importieren", "was-der-import-erkennt"),
        "eingefroren": ("Mängel, Druckansichten und Lehrgangsergebnis", "eingefroren"),
    }),
}


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
    # Gültig, solange Stand und Adresse der Seite gleich sind – die Adresse dazu, weil eine Kennung nach dem endgültigen
    # Löschen wieder vergeben werden kann (und in den Tests jede Datenbank bei 1 beginnt).
    marke = (seite["updated_at"], seite["slug"])
    stand = _kennungen_speicher.get(seite["id"])
    if not stand or stand[0] != marke:
        zeile = db.query("SELECT content FROM wiki_pages WHERE id = ?", (seite["id"],), one=True)
        stand = (marke, kennungen(zeile["content"] if zeile else ""))
        _kennungen_speicher[seite["id"]] = stand
    return anker in stand[1]


# --- Seiten finden ----------------------------------------------------------------------------------------------------

_SPALTEN = "id, title, slug, parent_id, created_by, is_public, public_children, read_restricted, deleted_at, updated_at"


def _wurzeln(wurzel):
    """Kandidaten für die oberste Artikelseite: Titel wurzel, nicht im Papierkorb, keine Vorlage – zuerst die mit
    Unterseiten (ein gleichnamiger Einzelartikel ist nicht gemeint), dann die neueste (ein späterer Import)."""
    return db.query(f"SELECT {_SPALTEN}, EXISTS (SELECT 1 FROM wiki_pages k WHERE k.parent_id = p.id AND k.deleted_at IS NULL)"
                    " AS hat_kinder FROM wiki_pages p WHERE title = ? AND deleted_at IS NULL AND is_template = 0 "
                    "ORDER BY hat_kinder DESC, id DESC", (wurzel,))


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
    from .auth import current_user
    return current_user()


def _url(seite, anker=""):
    url = f"/stroemipedia/{quote(seite['slug'], safe='')}"
    return f"{url}#{anker}" if anker and _hat_anker(seite, anker) else url


def aufloesen(wurzel_titel, themen, user=None):
    """{Thema: Adresse} für alles aus themen, was das Konto in der Strömipedia lesen darf – leer ohne Konto oder ohne
    Artikel. Je Anfrage und Wurzel einmal gerechnet (g)."""
    # Die Leseregel der Strömipedia steht an einer Stelle (Prüfanleitung der Materialablage, Phase 2 · L3).
    from .material.services.wikiverweis import darf_lesen
    user = _user(user)
    if not user:
        return {}
    speicher = g.setdefault("anleitung", {}) if has_request_context() else {}
    schluessel = (wurzel_titel, user["id"])
    if schluessel in speicher:
        return speicher[schluessel]
    out = {}
    # Die erste lesbare Wurzel; ist keine lesbar, trotzdem ihr Teilbaum – eine einzeln freigegebene Unterseite zählt
    # (die Wurzel selbst prüft die Schleife unten wie jede Seite).
    kandidaten = _wurzeln(wurzel_titel)
    wurzel = next((w for w in kandidaten if darf_lesen(w, user)), kandidaten[0] if kandidaten else None)
    if wurzel:
        seiten = _teilbaum(wurzel)
        seiten[wurzel_titel] = wurzel       # eine gleichnamige Unterseite ist nicht die Wurzel
        lesbar = {}
        for thema, (titel, anker) in themen.items():
            seite = seiten.get(titel)
            if not seite:
                continue
            if seite["id"] not in lesbar:
                lesbar[seite["id"]] = darf_lesen(seite, user)
            if lesbar[seite["id"]]:
                out[thema] = _url(seite, anker)
    speicher[schluessel] = out
    return out


def verweise(modul, user=None):
    """Die Adressen der Anleitung eines Moduls aus TABELLEN (wiki, karte, pruefungen) für das Konto."""
    wurzel, themen = TABELLEN[modul]
    return aufloesen(wurzel, themen, user)
