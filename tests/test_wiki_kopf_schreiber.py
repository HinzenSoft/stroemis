"""Rückmeldung des Nutzers zur Strömipedia vom 12.11.2026 (Telefon, Artikel „Knoten“): „Soll die Kopfzeile zweizeilig
sein?“
python tests/test_wiki_kopf_schreiber.py  oder  pytest tests/test_wiki_kopf_schreiber.py

Hatte jemand anderes die Seite im Editor offen, stand links in der Knopfreihe die gelbe Marke „✏ Name bearbeitet“. Am
Telefon passten dann Umschalter, 💬 und ⋯ nicht mehr daneben – „⋯“ brach allein in eine zweite Zeile. Jetzt trägt am
Telefon der gesperrte Knopf selbst den Hinweis (gelb „✏ Vorname“ statt des blassen „Bearbeiten“), die Marke davor
entfällt, und die Reihe bleibt einzeilig. Am Rechner bleibt es bei Marke und blassem Knopf. Geprüft in der echten App
(Server im Faden, angemeldet als Wiki-Verwaltung, den Schreibplatz hält ein zweiter Reiter) in Chromium; ohne Chromium
übersprungen."""
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

REITER = "fremder-reiter-kopf"
# Stand der Knopfreihe: Mitten der sichtbaren Knöpfe (eine Zeile = alle auf einer Höhe), Marke, Knopftext und -farbe
KOPF = r"""(() => { const reihe = document.querySelector('.wiki-head .btn-row'), ed = document.querySelector('#pg-edit');
  const zu = (e) => !e || getComputedStyle(e).display === 'none';
  const mitten = [...reihe.children].filter((e) => !zu(e)).map((e) => { const b = e.getBoundingClientRect();
    return Math.round(b.top + b.height / 2); });
  const marke = document.querySelector('#pg-praesenz');
  return { mitten, marke: marke && !zu(marke) ? marke.textContent : null, text: ed.innerText.trim(),
    gesperrt: ed.disabled, grund: getComputedStyle(ed).backgroundColor, vorlesen: ed.getAttribute('aria-label') }; })()"""


def _puls(u, slug_id, weg=False):
    body = {"reiter": REITER, "weg": True} if weg else {"reiter": REITER, "page_id": slug_id, "modus": "schreiben"}
    r = u.adm.post("/api/wiki/praesenz", json=body)
    assert r.status_code == 200, r.get_json()


def _ansehen(u, slug, breite, touch):
    s = u.seite("wikiverwaltung", breite, 900, touch=touch)
    try:
        s.oeffnen(f"/stroemipedia/{slug}", warten=1.5)
        assert s.warte("!!document.querySelector('#pg-edit') && document.querySelector('#pg-edit').disabled"), \
            f"Bearbeiten gesperrt ({breite} px)"
        s.ruhe(1.0)
        return s.js(KOPF)
    finally:
        s.schliessen()


def _lauf(u):
    r = u.adm.post("/api/wiki/pages", json={"title": "Kopfreihe", "content": "Text."})
    assert r.status_code in (200, 201), r.get_json()
    seite = r.get_json().get("page") or r.get_json()
    name = u.sql("SELECT name FROM users WHERE email = 'admin@example.org'")[0]["name"]
    vorname = name.split()[0]
    for breite in (344, 360, 390, 430):
        _puls(u, seite["id"])
        k = _ansehen(u, seite["slug"], breite, True)
        fall = (breite, k)
        # eine Zeile: Umschalter, 💬 und ⋯ auf einer Höhe
        assert max(k["mitten"]) - min(k["mitten"]) <= 2, fall
        # der Knopf sagt, wer schreibt – gelb, gesperrt; die Marke davor ist weg, die Vorlesehilfe hört den ganzen Satz
        assert k["marke"] is None and k["text"] == f"✏ {vorname}" and k["gesperrt"], fall
        assert k["grund"] == "rgb(255, 237, 0)", fall
        assert k["vorlesen"] == f"Bearbeiten – {name} bearbeitet gerade", fall
    # Am Rechner: Marke wie bisher, der Knopf blass mit „Bearbeiten“
    _puls(u, seite["id"])
    k = _ansehen(u, seite["slug"], 1280, False)
    assert k["marke"] == f"✏ {name} bearbeitet" and k["text"] == "Bearbeiten" and k["gesperrt"], k
    # Ist die Seite wieder frei, steht am Telefon wieder „Bearbeiten“ im Knopf
    _puls(u, seite["id"])
    s = u.seite("wikiverwaltung", 390, 900, touch=True)
    try:
        s.oeffnen(f"/stroemipedia/{seite['slug']}", warten=1.5)
        assert s.warte("document.querySelector('#pg-edit').disabled"), "gesperrt"
        _puls(u, seite["id"], weg=True)
        assert s.warte("!document.querySelector('#pg-edit').disabled", sek=20), "wieder frei"
        time.sleep(0.3)
        k = s.js(KOPF)
    finally:
        s.schliessen()
    assert k["marke"] is None and k["text"] == "Bearbeiten" and k["vorlesen"] is None, k
    assert max(k["mitten"]) - min(k["mitten"]) <= 2, k


def test_kopf_schreiber():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_kopf_schreiber()
    print("ok")
