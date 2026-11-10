"""„Typische Fehler“ einspaltig (Nutzer 02.11.2026: „Entferne die leere Spalte in der Fehlertabelle“).

Der Baustein im „/“-Menü und die Hilfeseite des Editors setzen die Tabelle ohne die leere zweite Spalte ein – wie die
Strömipedia-Artikel. Statisch geprüft; dass der Editor einspaltige Tabellen mit Kästen beim Speichern hält, ist im
Browser belegt (wiki-stroemipedia/bericht-bilder/einspaltig/editorprobe/). Die Hilfeseite hat als App-Anleitung keinen
Abschnitt „Quellen“ (Nachzug 10.11.2026) – die Tabelle reicht bis zum Ende.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lies(pfad):
    return (ROOT / pfad).read_text(encoding="utf-8")


def test_baustein_typische_fehler_einspaltig():
    js = lies("app/static/js/editor-format.js")
    assert 'fehler: "## Typische Fehler\\n\\n| Fehler |\\n| --- |\\n| **Fehlername** – Erklärung des Fehlers und seiner Folgen. |\\n",' in js
    assert "Fehlerbild" not in js
    print("Baustein einspaltig.")


def test_hilfeseite_typische_fehler_einspaltig():
    md = lies("docs/Editor - Bedienung und Kuerzel.md")
    # App-Anleitung ohne Abschnitt „Quellen“ (Nachzug 10.11.2026): „Typische Fehler“ ist der letzte Abschnitt.
    assert "## Quellen" not in md
    teil = md[md.index("## Typische Fehler"):]
    zeilen = [z for z in teil.splitlines() if z.startswith("|")]
    assert zeilen[:2] == ["| Fehler |", "| --- |"], zeilen[:2]
    assert len(zeilen) == 6 and all(z.endswith("::: |") for z in zeilen[2:]), zeilen
    print("Hilfeseite einspaltig.")


if __name__ == "__main__":
    test_baustein_typische_fehler_einspaltig()
    test_hilfeseite_typische_fehler_einspaltig()
