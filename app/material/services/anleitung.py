"""Verweise auf die Anleitung in der Strömipedia (Wunsch vom 28.10.2026): Links aus der Materialablage auf den Artikel
„Materialablage“ und seine Unterseiten – am Ende einer Info („i“), als „Anleitung“ im Seitenkopf, als Hinweis auf der
Übersicht und im Willkommen beim allerersten Besuch der Übersicht.

Gefunden wird eine Seite über ihren TITEL im Teilbaum unter der obersten Artikelseite (Titel WURZEL), nicht über ihre
Adresse: Der Artikel kommt per ZIP-Import, und der Import bildet die Adresse aus dem Titel (api_wiki.unique_slug – bei
einer Doppelung „-2“). Die Tabelle THEMEN steht nur hier; die Oberfläche fragt nach dem Schlüssel. Ein Anker kommt nur
an die Adresse, wenn die Seite eine Überschrift mit genau dieser Kennung hat (wie markdown.js buildToc sie bildet) –
sonst führt der Link an den Anfang der Seite.

Rechte (Entscheidung des Nutzers vom 28.10.2026, „Nur wer lesen darf“): Jede Seite einzeln mit den Regeln der
Strömipedia (app/anleitung.py darf_lesen – Stufe in der Strömipedia: can_read samt Lesebeschränkung; Lesemodus: nur
öffentliche Seiten). Gibt es die Seite nicht, liegt sie im Papierkorb oder darf das Konto sie nicht lesen, fehlt der
Schlüssel – kein Link, kein Titel, keine Meldung. An den Rechten der Strömipedia ändert sich nichts.

Seit dem 01.11.2026 (Entscheidung des Nutzers nach der Sicherheitsprüfung) zählen nur Seiten, die für alle Angemeldeten
freigegeben sind – die Wurzel und jede Themenseite, auch für Willkommen und Hinweis; vorher konnte jeder Redakteur die
Verweise mit einer eigenen Seite „Materialablage“ umlenken. Einzelheiten in app/anleitung.py.

Die Suche (Titel im Teilbaum, Anker, Freigabe, Leserecht) ist seit dem 01.11.2026 allgemein für alle Module mit eigenem Artikel
(app/anleitung.py, aufloesen); hier stehen nur Wurzel, Themen-Tabelle und das Willkommen der Materialablage.

Willkommen: je Konto einmal, gemerkt in mat_meta (Schlüssel „willkommen:<Konto>“, Wert der Zeitpunkt) – ohne
Schemaschritt; die Zeile geht mit dem Konto (loeschung.konto_loeschen_vorbereiten), ein Zurücksetzen des Moduls auf dev
(zuruecksetzen.py) leert sie mit. Gemerkt wird, wenn die Übersicht mit dem Dialog gezeichnet wird: Wer die Anleitung
(noch) nicht lesen darf, bekommt ihn erst, sobald er es darf."""
import sqlite3

from flask import current_app

from ... import anleitung as allgemein
from ... import db
from ...anleitung import kennungen

__all__ = ["WURZEL", "THEMEN", "kennungen", "verweise", "willkommen_einmal", "konto_vergessen"]  # kennungen: wie bisher von hier

WURZEL = "Materialablage"

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
    "formulare": ("Prüfformulare", "seite-pruefformulare"),
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
    "pruefformular": ("Prüfformulare", "formular-pool-standard-und-zuweisung"),
    "herstellerdokumente": ("Katalog", "herstellerdokumente"),
    "pruefpunkte": ("Prüfformulare", "pruefpunkte"),
    "eingangspruefung": ("Prüfung", "pruefarten"),
    "pruefsumme": ("Nachweise und Protokolle", "pruefsumme-und-stempel"),
    "rueckruf": ("Rückrufe", "anlegen"),
    "import_spalten": ("Bestandsimport", "wie-werte-gelesen-werden"),
}

WILLKOMMEN = "willkommen:{uid}"           # Schlüssel in mat_meta


def verweise(user=None):
    """{Thema: Adresse} für alles aus THEMEN, was das Konto in der Strömipedia lesen darf – leer ohne Konto oder ohne
    Artikel (app/anleitung.py, je Anfrage einmal gerechnet)."""
    return allgemein.aufloesen(WURZEL, THEMEN, user)


def willkommen_einmal(user=None):
    """Für die Übersicht: die Adresse der Anleitung, wenn das Konto sie lesen darf und das Willkommen noch nie gesehen
    hat – und merkt es sich dann (genau einmal je Konto, auch bei zwei gleichzeitigen Aufrufen: INSERT OR IGNORE).
    Sonst None. Geschrieben wird nur beim ersten Mal; jeder spätere Besuch liest nur. Scheitert das Merken (Datenbank
    gesperrt), gibt es diesmal kein Willkommen – die Übersicht kommt trotzdem."""
    user = allgemein._user(user)
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
