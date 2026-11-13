"""Rückmeldung des Nutzers zur Strömipedia vom 12.11.2026 (Callout in der Klappbox „Anfertigung“ der Kara-8): Markierter
Text, über „Umwandeln in … → Callout“ zur Kiste gemacht, verlor seine Auszeichnung.
python tests/test_wiki_callout_umwandeln.py  oder  pytest tests/test_wiki_callout_umwandeln.py

Vorher kam nur der reine Text der Auswahl (getSelectedText) in die Kiste: aus „**Karabiner sofort schließen**“ wurde
gewöhnlicher Text, Kursiv, Links und Code gingen ebenso verloren. Jetzt fasst ein Markenpaar die markierten Absätze ein
(wie bei der Ausrichtung) – ihr Text bleibt Zeichen für Zeichen, wie er war, auch in
einer Klappbox. Eine Auswahl mitten im Absatz nimmt den ganzen Absatz, wie die übrigen Umwandlungen. Geprüft in der
echten App (Server im Faden, angemeldet als Wiki-Verwaltung) in Chromium, am gespeicherten Text; ohne Chromium
übersprungen."""
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

ABSATZ = ("**Karabiner sofort schließen** Nachdem beide Seile *eingeklickt* sind, siehe "
          "[Anleitung](https://example.org/anleitung).")
ZWEITER = "Zweiter Absatz mit `Code`."
FLIESS = "Davor im Fließtext. **Mitte** des Absatzes. Danach."
MD = (f"Anfang.\n\n:::accordion Anfertigung\nEinleitung.\n\n{ABSATZ}\n\n{ZWEITER}\n:::\n\n{FLIESS}\n\nEnde.")
SOLL = (f"Anfang.\n\n:::accordion Anfertigung\nEinleitung.\n\n:::warning ⚠️\n{ABSATZ}\n\n{ZWEITER}\n:::\n:::\n\n"
        f":::info 💡\n{FLIESS}\n:::\n\nEnde.")

# Bildschirmstellen eines Textstücks im Editor: Anfang des ersten und Ende des letzten Zeilenkastens
STELLE = r"""((anfang, ende, wort) => { const absaetze = [...document.querySelectorAll('.toastui-editor-ww-container .ProseMirror > p')];
  const kasten = (p, w) => { const r = document.createRange();
    if (w) { const t = [...p.querySelectorAll('*')].map((e) => e.firstChild).find((n) => n && n.nodeType === 3 && n.nodeValue === w);
      r.selectNodeContents(t); } else r.selectNodeContents(p);
    return [...r.getClientRects()].filter((q) => q.width); };
  const a = kasten(absaetze.find((p) => p.textContent.startsWith(anfang)), wort)[0];
  const e = kasten(absaetze.find((p) => p.textContent.startsWith(ende)), wort).pop();
  return [a.left + 1, a.top + a.height / 2, e.right - 1, e.top + e.height / 2]; })"""


def _ziehen(s, x1, y1, x2, y2):
    s.b.rufen("Input.dispatchMouseEvent", type="mousePressed", x=x1, y=y1, button="left", clickCount=1)
    s.b.rufen("Input.dispatchMouseEvent", type="mouseMoved", x=(x1 + x2) / 2, y=(y1 + y2) / 2, button="left")
    s.b.rufen("Input.dispatchMouseEvent", type="mouseMoved", x=x2, y=y2, button="left")
    s.b.rufen("Input.dispatchMouseEvent", type="mouseReleased", x=x2, y=y2, button="left", clickCount=1)
    time.sleep(0.6)


def _umwandeln(s, art):
    """„Umwandeln in … → Callout“ in der schwebenden Leiste, Art wählen, Einfügen."""
    assert s.js("(() => { const b = document.querySelector('.ed-bubble'); return !!b && !b.classList.contains('hidden'); })()"), \
        "Leiste zur Auswahl"
    s.js("(() => { const w = document.querySelector('.ed-bubble .ed-style'); w.value = 'callout'; "
         "w.dispatchEvent(new Event('change')); })()")
    assert s.warte("!!document.querySelector('dialog[open] #ck-ok')"), "Dialog"
    s.js(f"document.querySelector('dialog[open] #ck [data-k=\"{art}\"]').click()")
    s.js("document.querySelector('dialog[open] #ck-ok').click()")
    time.sleep(1.0)


def _lauf(u):
    r = u.adm.post("/api/wiki/pages", json={"title": "Umwandeln", "content": MD})
    assert r.status_code in (200, 201), r.get_json()
    slug = (r.get_json().get("page") or r.get_json())["slug"]
    s = u.seite("wikiverwaltung", 1000, 1400)
    try:
        s.oeffnen(f"/stroemipedia/{slug}", warten=1.5)
        s.ruhe(1.5)
        s.klick("#pg-edit")
        assert s.warte("!!document.querySelector('.toastui-editor-ww-container .ProseMirror .ak-titel')"), "Editor offen"
        s.ruhe(1.5)
        # Box aufklappen (Pfeil vor dem Titel)
        x, y = s.js("(() => { const b = document.querySelector('.ProseMirror > .ak-erst').getBoundingClientRect(); "
                    "return [b.left + 10, b.top + 12]; })()")
        for art in ("mousePressed", "mouseReleased"):
            s.b.rufen("Input.dispatchMouseEvent", type=art, x=x, y=y, button="left", clickCount=1)
        time.sleep(0.6)
        # 1. Zwei Absätze in der Box, vom Anfang des ersten bis ans Ende des zweiten
        _ziehen(s, *s.js(STELLE + "('Karabiner sofort', 'Zweiter Absatz', null)"))
        _umwandeln(s, "warning")
        # 2. Nur das Wort „Mitte“ im Fließtext – die Kiste nimmt den ganzen Absatz
        _ziehen(s, *s.js(STELLE + "('Davor im Fließtext', 'Davor im Fließtext', 'Mitte')"))
        _umwandeln(s, "info")
        # Der Editor speichert von selbst; gelesen wird der gespeicherte Text
        inhalt = ""
        for _ in range(40):
            seite = u.adm.get(f"/api/wiki/pages/{slug}").get_json()
            inhalt = (seite.get("page") or seite).get("content", "")
            if inhalt.count(":::warning") and inhalt.count(":::info"):
                break
            time.sleep(0.5)
    finally:
        s.schliessen()
    # Der Editor speichert den Seitentitel als erste Zeile mit
    inhalt = inhalt.strip()
    if inhalt.startswith("# Umwandeln\n\n"):
        inhalt = inhalt[len("# Umwandeln\n\n"):]
    assert inhalt == SOLL, inhalt


def test_callout_umwandeln():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_callout_umwandeln()
    print("ok")
