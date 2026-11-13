"""Wunsch des Nutzers zur Strömipedia vom 13.11.2026 (Seite „Anleitungen“, nur Unterseiten): „Bei ‚leeren‘ Seiten soll ein
detailliertes Inhaltsverzeichnis der einzelnen Unterseiten angezeigt werden“.
python tests/test_wiki_verzeichnis.py  oder  pytest tests/test_wiki_verzeichnis.py

Vorher stand unter einer Seite ohne Text nur die Liste der direkten Unterseiten. Jetzt (Entscheidungen des Nutzers: „Baum +
Abschnitte“, „nur ohne eigenen Text“) zeigt sie alle Unterseiten über alle Ebenen, je Seite ihre Hauptabschnitte als
Sprungziele; eine Seite mit Text behält die kurze Liste. Geprüft in der echten App (Server im Faden) in Chromium: Baum und
Abschnitte, Überschriften in Codeblöcken und tiefere Ebenen zählen nicht, ein doppelter Abschnittsname springt an die
richtige Stelle, eine beschränkte Unterseite sieht nur, wer sie lesen darf. Ohne Chromium übersprungen."""
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

RIEGEN = ("# Riegenkarten\n\n## Erste Schritte\n\nText.\n\n## Hinweise\n\nEins.\n\n### Tiefer\n\nZwei.\n\n"
          "## Hinweise\n\nDrei.\n\n" + "\n\n".join(["Fülltext, damit die Überschrift nach oben rollen kann."] * 30))
LEHRGAENGE = "## Die Lehrgangsseite\n\nText.\n\n```\n## Kein Abschnitt\n```\n\n## **Teilnehmende**\n\nText."
VERZEICHNIS = r"""(() => { const v = document.querySelector('.children-list.verzeichnis');
  if (!v) return null;
  const zweig = (ul) => [...ul.children].map((li) => ({ seite: li.querySelector(':scope > .vz-seite').textContent.trim(),
    abschnitte: [...li.querySelectorAll(':scope > .vz-abschnitte a')].map((a) => [a.textContent, a.getAttribute('href')]),
    unter: li.querySelector(':scope > ul:not(.vz-abschnitte)') ? zweig(li.querySelector(':scope > ul:not(.vz-abschnitte)')) : [] }));
  return zweig(v.querySelector(':scope > ul')); })()"""


def _seite(u, titel, inhalt, eltern=None):
    r = u.adm.post("/api/wiki/pages", json={"title": titel, "content": inhalt, "parent_id": eltern})
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json().get("page") or r.get_json()


def _lauf(u):
    wurzel = _seite(u, "Anleitungen", "")
    riegen = _seite(u, "Riegenkarten", RIEGEN, wurzel["id"])
    _seite(u, "Lehrgänge", LEHRGAENGE, riegen["id"])
    _seite(u, "Materialablage", "Nur Text, keine Überschrift.", wurzel["id"])
    geheim = _seite(u, "Geheim", "## Verborgen\n\nText.", wurzel["id"])
    u.sql("UPDATE wiki_pages SET read_restricted = 1 WHERE id = ?", (geheim["id"],))
    mit_text = _seite(u, "Mit Text", "Hier steht etwas.")
    _seite(u, "Kind", "## Abschnitt\n\nText.", mit_text["id"])

    lehrgang_soll = {"seite": "Lehrgänge", "unter": [], "abschnitte": [
        ["Die Lehrgangsseite", "/stroemipedia/lehrgaenge#die-lehrgangsseite"],
        ["Teilnehmende", "/stroemipedia/lehrgaenge#teilnehmende"]]}
    riegen_soll = {"seite": "Riegenkarten", "unter": [lehrgang_soll], "abschnitte": [
        ["Erste Schritte", "/stroemipedia/riegenkarten#erste-schritte"],
        ["Hinweise", "/stroemipedia/riegenkarten#hinweise"],
        ["Hinweise", "/stroemipedia/riegenkarten#hinweise-2"]]}
    material_soll = {"seite": "Materialablage", "unter": [], "abschnitte": []}
    geheim_soll = {"seite": "Geheim", "unter": [], "abschnitte": [["Verborgen", "/stroemipedia/geheim#verborgen"]]}

    for rolle, soll in (("wikiverwaltung", [riegen_soll, material_soll, geheim_soll]), ("mitglied", [riegen_soll, material_soll])):
        s = u.seite(rolle, 1100, 900)
        try:
            s.oeffnen(f"/stroemipedia/{wurzel['slug']}", warten=1.5)
            assert s.warte("!!document.querySelector('.verzeichnis .vz-abschnitte')", sek=10), (rolle, "Verzeichnis mit Abschnitten")
            time.sleep(0.3)
            ist = s.js(VERZEICHNIS)
            ordnung = lambda baum: sorted(baum, key=lambda x: x["seite"])  # noqa: E731
            assert ordnung(ist) == ordnung(soll), (rolle, ist)
            # Der zweite „Hinweise“ springt auf die zweite Überschrift der Unterseite
            s.js("[...document.querySelectorAll('.vz-abschnitte a')].find((a) => a.getAttribute('href').endsWith('#hinweise-2')).click()")
            assert s.warte("location.pathname === '/stroemipedia/riegenkarten' && !!document.getElementById('hinweise-2')", sek=10), rolle
            assert s.warte("(() => { const h = document.getElementById('hinweise-2'); const r = h.getBoundingClientRect();"
                           " return h.tagName === 'H2' && h.nextElementSibling.textContent === 'Drei.' && r.top >= 0 && r.top < innerHeight / 2; })()",
                           sek=10), (rolle, "an die Stelle gesprungen")
            # Eine Seite mit Text behält die kurze Liste der direkten Unterseiten
            s.oeffnen(f"/stroemipedia/{mit_text['slug']}", warten=1.5)
            s.ruhe(1.0)
            assert s.js("!document.querySelector('.verzeichnis') && document.querySelector('#pg-unterseiten').textContent.includes('Kind')"), rolle
        finally:
            s.schliessen()
    # Der Server liefert nur Lesbares, und eine beschränkte Wurzel bleibt zu
    assert u.adm.get(f"/api/wiki/pages/{wurzel['id']}/verzeichnis").status_code == 200
    assert u.adm.get("/api/wiki/pages/999999/verzeichnis").status_code == 404


def test_verzeichnis():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_verzeichnis()
    print("ok")
