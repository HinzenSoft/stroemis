"""Prüfformular-Editor mit Gruppen als Zwischenzeile, Ziehgriff und Menü „⋯“ (Wunsch vom 04.11.2026, Bauauftrag
planung/formular-editor/auftrag.md): python tests/test_material_formular_editor.py  oder  pytest

1. Statisch: keine Pfeile und kein ✕ mehr an den Prüfpunkten (die übrigen Nutzer von S.reihenfolgeKnoepfe bleiben),
   Griff mit touch-action: none nur am Griff, Tippflächen nur unter (pointer: coarse), Menütexte ohne „…“.
2. Browser bei 1280×900 (Maus) und 360×740 (Touch) mit der Hilfe tests/einfuehrung_browser.py: Ziehen innerhalb einer
   Gruppe und in eine andere (echte Maus- bzw. Touch-Ereignisse), Bildlauf am Rand, Esc bricht ab; Menü „Nach oben“/„Nach
   unten“ (auch über die Gruppengrenze), „In Gruppe verschieben“ (bestehende und neue Gruppe), „Entfernen“; Gruppe
   umbenennen, nach oben/unten, entfernen (mit Rückfrage samt Anzahl, leer ohne); „+ Prüfpunkt“ je Gruppe; „+ Gruppe“;
   ein Name mit 80 Zeichen ganz sichtbar; Getipptes (Titel, Gruppenname, Prüfpunkt) überlebt jedes Neuzeichnen;
   „Speichern“ schickt Reihenfolge und Gruppe richtig (geprüft in der Datenbank, leere Gruppe fällt weg); die
   Nur-Lese-Ansicht zeigt dieselben Zwischenzeilen ohne Griff und Menü. Am Finger sind Griff, „⋯“, „+ Prüfpunkt“, die
   Menüeinträge und die Gruppenwahl im Dialog mindestens 44 × 44 px (gemessen, nicht nur die Regel), ein Tipp auf ihre
   Mitte trifft sie; keine Konsolenfehler, kein waagerechter Bildlauf. Ohne Chromium „übersprungen“ mit rc 0.
3. Absätze im Prüfpunkt (Zusatz vom 04.11.2026): Enter fügt im Prüfpunkt einen Umbruch ein (im Gruppennamen nicht), das
   Feld wächst, gespeichert wird „\n“; Nur-Lese-Ansicht und offene Prüfung zeigen ihn (pre-line), HTML im Punkttext
   bleibt Text (Formular und Prüfung). Server, Import/Export und PDF: tests/test_material_pruefpunkt_absatz.py.
4. Häkchen „optional“ statt „Pflicht“ (Zusatz vom 04.11.2026): leer bei Pflichtpunkten, gesetzt = pflicht false beim
   Speichern (Datenbank); ohne Bearbeiten nur bei optionalen Punkten die Marke „optional“, sonst nichts.
5. Gruppen per Griff ⠿ am Kopf ziehen (Bauauftrag planung/gruppe-ziehen/auftrag.md): echte Maus- bzw. Touch-Ereignisse,
   beim Ziehen rückt keine Zeile, Einfügemarke an einer Grenze zwischen Gruppen, Esc bricht ab, an den Anfang (auch mit
   Bildlauf am Rand) und ans Ende, Getipptes zieht mit, Reihenfolge in der Datenbank nach dem Speichern; Griff in der Flucht
   der Punktgriffe, Namensfeld mit dem Rest der Zeile, am Finger ≥ 44 px (gemessen); bei nur einer Gruppe kein Griff.
Alle Inhalte sind Platzhalter."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROESSEN = ((1280, 900, False), (360, 740, True))
LANG = ("Platzhalter-Gruppe mit einem sehr langen Namen, der in der Zwischenzeile ganz zu lesen ist" + "x" * 80)[:80]


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i + len(anfang))]


# --- 1. Statisch ---------------------------------------------------------------------------------------------------------

def test_statisch():
    js = lies("app/material/static/material.js")
    editor = abschnitt(js, "  async function formular() {", "\n  }\n")
    # Keine Pfeile und kein ✕ mehr an den Punkten; die Positionen (Bestandteile) behalten ihre.
    assert "reihenfolgeKnoepfe" not in editor and "entfernenKnopf" not in editor
    assert js.count("S.reihenfolgeKnoepfe(") == 1 and 'data-bt="hoch"' in js
    assert "S.reihenfolgeKnoepfe(i, n, hoch, runter)" in lies("app/static/js/pruefungen.js")
    # Menü „⋯“ über S.menue, Einträge ohne Auslassungspunkte; die Gruppe als Zwischenzeile mit Feld (80 Zeichen).
    assert 'S.menue({ text: "⋯", art: "mat-menue", eintraege })' in editor
    for text in ("Nach oben", "Nach unten", "In Gruppe verschieben", "Entfernen", "Gruppe nach oben", "Gruppe nach unten",
                 "Gruppe entfernen"):
        assert f'text: "{text}"' in editor, text
    assert not re.search(r'text: "[^"]*…"', editor)
    assert '<textarea class="fp-gruppenname" rows="1" maxlength="80" aria-label="Gruppe" placeholder="ohne Gruppe – Name eintragen">' in editor
    assert "fp-gruppe\"" not in editor and 'data-l="Gruppe"' not in editor
    # „optional“ statt „Pflicht“: Häkchen leer = Pflicht; ohne Bearbeiten nur die Marke „optional“.
    assert '<input type="checkbox" class="fp-optional" ${p.pflicht ? "" : "checked"}> optional</label>' in editor
    assert 'p.pflicht = !$(".fp-optional", tr).checked;' in editor and "fp-pflicht\"" not in editor
    assert '${p.pflicht ? "" : \'<span class="badge grey">optional</span>\'}' in editor and '"Pflicht" : "optional"' not in editor
    assert 'const neuerPunkt = () => ({ text: "", art: "yesno", soll: "nein", pflicht: true });' in editor
    # Schnittstelle unverändert: die flache Liste mit „gruppe“ je Punkt.
    assert editor.count("punkte: flach()") == 2 and 'Object.assign({}, p, { gruppe: g.name })' in editor
    css = lies("app/material/static/material.css")
    assert "touch-action: none" in abschnitt(css, ".mat-formtabelle .fp-griff {", "}")
    assert ".mat-formtabelle .btn-row .btn.small" not in css
    coarse = [m.start() for m in re.finditer(r"@media \(pointer: coarse\) \{", css)]
    for regel in (".mat-formtabelle .fp-griff { width: 44px; height: 44px; }",
                  ".mat-formtabelle .fp-menue :is(summary.btn, .btn) { min-width: 44px; min-height: 44px;"):
        i = css.index(regel)
        assert any(c < i for c in coarse) and css.rfind("@media (pointer: coarse)", 0, i) > css.rfind("\n}\n", 0, i), regel
    # Gruppe ziehen (Wunsch vom 04.11.2026): Griff am Kopf nur bei mehr als einer Gruppe, der Block mit Einfügemarke.
    assert """${gruppen.length > 1 ? '<span class="fp-griff" aria-hidden="true" title="Gruppe zum Verschieben ziehen">⠿</span>' : ""}""" in editor
    assert 'const block = zeile.classList.contains("fp-gruppenzeile") ? zeile.parentElement : null;' in editor
    assert 'marke.className = "fp-einfuegemarke"' in editor and "marke.remove()" in editor
    assert "pointer-events: none" in abschnitt(css, ".fp-einfuegemarke {", "}")
    assert "var(--wasser)" in abschnitt(css, ".fp-einfuegemarke {", "}")
    # Die Einführung kennt den neuen Editor.
    uebung = lies("app/static/js/uebung/material.js")
    assert 'const neuerPunkt = "#fp-tabelle tr.fp-punkt:has(+ tr.fp-fuss) .fp-text";' in uebung
    assert "tbody tr:last-child" not in uebung
    print("Statisch bestanden.")


# --- 2. Browser ------------------------------------------------------------------------------------------------------

STRUKTUR = """JSON.stringify([...document.querySelectorAll('#fp-tabelle tbody')].map((tb) => [
  (tb.querySelector('.fp-gruppenname') || {}).value, [...tb.querySelectorAll('tr.fp-punkt .fp-text')].map((t) => t.value),
  Boolean(tb.querySelector('tr.fp-leer'))]))"""


def struktur(s):
    return json.loads(s.js(STRUKTUR))


def zeile(gi, pi):
    return f'#fp-tabelle tr.fp-punkt[data-g="{gi}"][data-i="{pi}"]'


def kopf(gi):
    return f'#fp-tabelle tr.fp-gruppenzeile[data-g="{gi}"]'


def klick(s, sel):
    befund = s.klick(sel)
    assert not befund, befund
    s.b.warten(0.25)


def tippen(s, sel, text):
    """Text am Ende eines Felds tippen (echte Eingabe; focus() setzt die Marke in einem Textfeld an den Anfang)."""
    ok = s.js(f"""(() => {{ const el = document.querySelector({json.dumps(sel)}); if (!el) return false; el.focus();
      el.setSelectionRange(el.value.length, el.value.length); return true; }})()""")
    assert ok, f"Feld „{sel}“ nicht gefunden"
    s.b.rufen("Input.insertText", text=text)


def enter(s):
    s.b.rufen("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r")
    s.b.rufen("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)


def menue(s, zeilen_sel, act):
    """„⋯“ einer Zeile öffnen und einen Eintrag wählen – beides als echter Klick bzw. Tipp."""
    klick(s, f"{zeilen_sel} .fp-menue summary")
    assert s.js("Boolean(document.querySelector('#fp-tabelle details.menue[open]'))"), "Menü nicht offen"
    klick(s, f'#fp-tabelle details.menue[open] [data-act="{act}"]')


def mitte(s, sel, anteil=0.5):
    return s.js(f"""(() => {{ const el = document.querySelector({json.dumps(sel)}); el.scrollIntoView({{ block: 'nearest' }});
      const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height * {anteil}]; }})()""")


def lage(s, sel, anteil=0.5):
    return s.js(f"""(() => {{ const r = document.querySelector({json.dumps(sel)}).getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height * {anteil}]; }})()""")


def ziehen(s, von, nach, anteil=0.75, halten=0.0, esc=False, waehrend=None):
    """Am Griff der Zeile von bis auf die Stelle anteil (0 oben, 1 unten) der Zeile nach ziehen – echte Maus- bzw.
    Touch-Ereignisse. Liegt das Ziel unter dem Bild (Karten am Telefon), bleibt der Finger am unteren Rand, bis der
    Bildlauf es heraufholt. nach als (x, y): dorthin, ohne Ziel. waehrend(s) prüft vor dem Loslassen (Finger liegt noch)."""
    # Start und Ziel mittig ins Bild, wenn beide hineinpassen, sonst die gezogene Zeile ins obere Viertel (Ziel darunter)
    # bzw. tief ins Bild (Ziel darüber); dann messen –
    # ohne weiteren Bildlauf (sonst stimmte der Start nicht).
    s.js(f"""(() => {{ const a = document.querySelector({json.dumps(von)}).getBoundingClientRect();
      const z = {json.dumps(nach)}; const b = typeof z === 'string' ? document.querySelector(z).getBoundingClientRect() : a;
      const oben = Math.min(a.top, b.top), unten = Math.max(a.bottom, b.bottom);
      window.scrollBy(0, unten - oben < innerHeight - 160 ? (oben + unten) / 2 - innerHeight / 2
        : b.top < a.top ? a.top - innerHeight * 0.7 : a.top - innerHeight * 0.25); }})()""")
    x0, y0 = lage(s, f"{von} .fp-griff")
    stand = [x0, y0]

    def hin(x, y, schritte=12):
        xa, ya = stand
        for k in range(1, schritte + 1):
            xk, yk = xa + (x - xa) * k / schritte, ya + (y - ya) * k / schritte
            if s.touch:
                s.b.rufen("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": xk, "y": yk}])
            else:
                s.b.rufen("Input.dispatchMouseEvent", type="mouseMoved", x=xk, y=yk, button="left", buttons=1)
            s.b.warten(0.02)
        stand[:] = [x, y]

    if s.touch:
        s.b.rufen("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x0, "y": y0}])
    else:
        s.b.rufen("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
        s.b.rufen("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
    if isinstance(nach, str):
        x1, y1 = lage(s, nach, anteil)
        kopf = s.js("Math.max(0, document.querySelector('header.bauchbinde').getBoundingClientRect().bottom)")
        if y1 > s.hoehe - 80 or y1 < kopf + 80:
            runter = y1 > s.hoehe - 80
            hin(x0, s.hoehe - 8 if runter else kopf + 8)
            ende = time.time() + 10
            im_bild = lambda y: s.hoehe * 0.3 <= y <= s.hoehe * 0.6   # noqa: E731
            while time.time() < ende and not im_bild(lage(s, nach, anteil)[1]):
                s.b.warten(0.03)
            assert im_bild(lage(s, nach, anteil)[1]), ("Bildlauf am Rand holt das Ziel nicht ins Bild", nach)
            hin(x0, s.hoehe * 0.5, 2)            # aus dem Randbereich, dann aufs Ziel
            x1, y1 = lage(s, nach, anteil)
        assert 60 < y1 < s.hoehe - 60, ("Ziel nicht im Bild", nach, y1)
        hin(x1, y1)
        x1, y1 = lage(s, nach, anteil)           # die gezogene Zeile hat die Lage verschoben – einmal nachfassen
        hin(x1, y1, 3)
    else:
        hin(*nach)
    if halten:
        s.b.warten(halten)
    if waehrend:
        waehrend(s)
    if esc:
        s.taste()
    if s.touch:
        s.b.rufen("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    else:
        s.b.rufen("Input.dispatchMouseEvent", type="mouseReleased", x=stand[0], y=stand[1], button="left", buttons=0, clickCount=1)
    s.b.warten(0.3)


def flaeche(s, sel):
    """Breite, Höhe und ob ein Tipp auf die Mitte das Element trifft – für alle sichtbaren Treffer, das kleinste zuerst."""
    return s.js(f"""(() => [...document.querySelectorAll({json.dumps(sel)})].filter((e) => e.getClientRects().length).map((e) => {{
      e.scrollIntoView({{ block: 'nearest' }}); const r = e.getBoundingClientRect();
      const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return [Math.round(r.width), Math.round(r.height), Boolean(t && (t === e || e.contains(t)))]; }})
      .sort((a, b) => Math.min(a[0], a[1]) - Math.min(b[0], b[1])))()""")


def tippflaechen(s, sel):
    werte = flaeche(s, sel)
    assert werte, f"„{sel}“ nicht gefunden"
    b, h, trifft = werte[0]
    assert b >= 44 and h >= 44 and trifft, (sel, werte[0])


def gruppe_ziehen(s, touch):
    """Gruppen per Griff am Kopf ziehen (Wunsch vom 04.11.2026): Beim Ziehen bleibt jede Zeile stehen, der Block ist blau
    hinterlegt und eine Einfügemarke steht an einer Grenze zwischen Gruppen (nie mitten in einer); Esc bricht ab; der Block
    kommt an den Anfang und wieder ans Ende – mit seinen Punkten und dem eben getippten Namen."""
    tippen(s, f"{kopf(2)} .fp-gruppenname", " gezogen")
    vorher = struktur(s)
    assert [g[0] for g in vorher] == ["Gruppe C", "Gruppe A neu", "Gruppe B gezogen"], vorher
    assert s.js("[...document.querySelectorAll('#fp-tabelle tr.fp-gruppenzeile')].map((tr) => tr.querySelectorAll('.fp-griff').length)") == [1, 1, 1]
    assert s.js("[...document.querySelectorAll('#fp-tabelle tr.fp-gruppenzeile .fp-griff')].every((g) => g.getAttribute('aria-hidden') === 'true')")
    # Der Griff steht vorn in der Flucht der Griffe darunter, das Namensfeld behält den Rest der Zeile.
    lage_kopf = s.js("""(() => { const tr = document.querySelector('#fp-tabelle tr.fp-gruppenzeile'); const g = tr.querySelector('.fp-griff').getBoundingClientRect();
      const n = tr.querySelector('.fp-gruppenname').getBoundingClientRect(), m = tr.querySelector('.fp-menue').getBoundingClientRect();
      const p = document.querySelector('#fp-tabelle tr.fp-punkt .fp-griff').getBoundingClientRect();
      return [g.left - p.left, n.left - g.right, m.left - n.right, n.width / tr.getBoundingClientRect().width]; })()""")
    assert abs(lage_kopf[0]) <= 10 and 0 <= lage_kopf[1] <= 12 and 0 <= lage_kopf[2] <= 12 and lage_kopf[3] > 0.6, lage_kopf

    def mitten(s):
        assert struktur(s) == vorher, struktur(s)
        assert s.js("document.querySelector('#fp-tabelle tbody.fp-zieht') === document.querySelectorAll('#fp-tabelle tbody')[2]")
        marke = s.js("""(() => { const m = document.querySelector('.fp-einfuegemarke'); if (!m || m.hidden) return null;
          const r = m.getBoundingClientRect(); return [r.top + r.height / 2, r.width, r.height, getComputedStyle(m).backgroundColor]; })()""")
        assert marke and marke[1] > 200 and marke[2] >= 3, ("keine Einfügemarke", marke)
        grenzen = s.js("""(() => { const r = [...document.querySelectorAll('#fp-tabelle tbody')].map((tb) => tb.getBoundingClientRect());
          return r.map((x, i) => (i ? (r[i - 1].bottom + x.top) / 2 : x.top)).concat(r[r.length - 1].bottom); })()""")
        # Über dem ersten Punkt von „Gruppe A neu“: die Marke steht an deren Anfang (Grenze 1), nicht zwischen den Punkten.
        assert abs(marke[0] - grenzen[1]) <= 2, (marke, grenzen)

    # Esc bricht ab: der Zeiger steht über einem Punkt einer anderen Gruppe – nichts rückt, die Marke steht an der Grenze.
    ziehen(s, kopf(2), zeile(1, 0), anteil=0.5, esc=True, waehrend=mitten)
    assert struktur(s) == vorher
    assert not s.js("document.querySelector('.fp-einfuegemarke, #fp-tabelle .fp-zieht, #fp-tabelle.fp-ziehen')")
    # An den Anfang …
    ziehen(s, kopf(2), kopf(0), anteil=0.1)
    assert struktur(s) == [vorher[2], vorher[0], vorher[1]], struktur(s)
    assert not s.js("document.querySelector('.fp-einfuegemarke')")
    assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter Editor getippt"
    # … und wieder ans Ende (unter „+ Prüfpunkt“ der letzten Gruppe).
    ziehen(s, kopf(0), "#fp-tabelle tbody:last-of-type tr.fp-fuss", anteil=0.9)
    assert struktur(s) == vorher, struktur(s)
    # Das Menü „⋯“ der Gruppe bleibt (Tastatur).
    klick(s, f"{kopf(1)} .fp-menue summary")
    assert s.js("[...document.querySelectorAll('#fp-tabelle details.menue[open] .menue-liste button')].map((b) => b.textContent.trim())") == [
        "Gruppe nach oben", "Gruppe nach unten", "Gruppe entfernen"]
    s.taste()
    s.b.warten(0.2)


def eine_gruppe(u, kategorie, breite, hoehe, touch):
    """Bei nur einer Gruppe kein Griff am Kopf (die Punkte behalten ihren); mit „+ Gruppe“ haben beide Köpfe einen."""
    r = u.adm.post("/api/material/formulare", json={"kategorie_id": kategorie, "titel": "Platzhalter eine Gruppe", "punkte": [
        {"gruppe": "Gruppe A", "text": "Platzhalter 1", "art": "yesno", "soll": "nein"},
        {"gruppe": "Gruppe A", "text": "Platzhalter 2", "art": "yesno", "soll": "ja"}]})
    assert r.status_code == 201, r.get_json()
    s = u.seite("matverwaltung", breite, hoehe, touch)
    try:
        oeffnen(s, r.json["formular"]["id"])
        assert s.js("document.querySelectorAll('#fp-tabelle tr.fp-gruppenzeile').length") == 1
        assert not s.js("document.querySelector('#fp-tabelle tr.fp-gruppenzeile .fp-griff')")
        assert s.js("document.querySelectorAll('#fp-tabelle tr.fp-punkt .fp-griff').length") == 2
        klick(s, '[data-act="gruppe-neu"]')
        assert s.js("document.querySelectorAll('#fp-tabelle tr.fp-gruppenzeile .fp-griff').length") == 2
        if touch:
            tippflaechen(s, "#fp-tabelle tr.fp-gruppenzeile .fp-griff")
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()


def formular_anlegen(u, kategorie):
    r = u.adm.post("/api/material/formulare", json={"kategorie_id": kategorie, "titel": "Platzhalter Editor", "punkte": [
        {"gruppe": "Gruppe A", "text": "Platzhalter 1", "art": "yesno", "soll": "nein"},
        {"gruppe": "Gruppe A", "text": "Platzhalter 2", "art": "yesno", "soll": "ja"},
        {"gruppe": "Gruppe B", "text": "Platzhalter 3", "art": "text"},
        {"gruppe": "Gruppe B", "text": "Platzhalter 4", "art": "number", "pflicht": False},
        {"gruppe": "", "text": "Platzhalter 5", "art": "date"}]})
    assert r.status_code == 201, r.get_json()
    return r.json["formular"]["id"]


def oeffnen(s, fid):
    s.oeffnen(f"/materialablage/katalog/formular/{fid}", warten=0.6)
    s.warte("!!document.querySelector('#fp-tabelle')")
    # Angebot der Einführung und Hinweise beiseite – sie liegen sonst über Zeilen.
    s.js("""(() => { const k = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Nicht jetzt');
      if (k) k.click(); document.querySelectorAll('dialog[open]').forEach((d) => d.close()); })()""")
    s.b.warten(0.3)


def ablauf(u, kategorie, breite, hoehe, touch):
    fid = formular_anlegen(u, kategorie)
    s = u.seite("matverwaltung", breite, hoehe, touch)
    try:
        oeffnen(s, fid)
        assert struktur(s) == [["Gruppe A", ["Platzhalter 1", "Platzhalter 2"], False],
                               ["Gruppe B", ["Platzhalter 3", "Platzhalter 4"], False], ["", ["Platzhalter 5"], False]]
        assert not s.js("document.querySelector('#fp-tabelle .zeichenknopf, #fp-tabelle [data-act=hoch]')")
        # Häkchen „optional“ (Zusatz vom 04.11.2026): leer bei Pflichtpunkten, gesetzt nur bei Platzhalter 4.
        assert s.js("[...document.querySelectorAll('#fp-tabelle tr.fp-punkt .fp-optional')].map((x) => x.checked)") == [
            False, False, False, True, False]
        assert s.js("[...document.querySelectorAll('#fp-tabelle .fp-z-pflicht label')].every((l) => l.textContent.trim() === 'optional')")
        assert "Pflicht" not in s.js("document.querySelector('#fp-tabelle').innerText")
        assert s.js("document.querySelector(" + json.dumps(kopf(2) + " .fp-gruppenname") + ").placeholder") == "ohne Gruppe – Name eintragen"

        # Getipptes: Titel, Gruppenname und Prüfpunkt – überlebt die folgenden Neuzeichnungen.
        tippen(s, "#fp-titel", " getippt")
        tippen(s, f"{kopf(0)} .fp-gruppenname", " neu")
        tippen(s, f"{zeile(1, 0)} .fp-text", " getippt")

        # Menü: „Nach unten“ über die Grenze (letzter von A → erster von B), „Nach oben“ zurück, innerhalb der Gruppe.
        menue(s, zeile(0, 1), "punkt-runter")
        assert struktur(s)[:2] == [["Gruppe A neu", ["Platzhalter 1"], False],
                                   ["Gruppe B", ["Platzhalter 2", "Platzhalter 3 getippt", "Platzhalter 4"], False]]
        assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter Editor getippt"
        if not touch:   # Der Fokus folgt dem Punkt (am Finger ebenso, dort ohne sichtbaren Ring).
            assert s.js("document.activeElement.matches(" + json.dumps(f"{zeile(1, 0)} .fp-menue summary") + ")")
        menue(s, zeile(1, 0), "punkt-hoch")
        assert struktur(s)[0][1] == ["Platzhalter 1", "Platzhalter 2"]
        menue(s, zeile(0, 1), "punkt-hoch")
        assert struktur(s)[0][1] == ["Platzhalter 2", "Platzhalter 1"]
        # Der erste Punkt hat kein „Nach oben“, der letzte kein „Nach unten“.
        klick(s, f"{zeile(0, 0)} .fp-menue summary")
        assert not s.js("document.querySelector('#fp-tabelle details.menue[open] [data-act=punkt-hoch]')")
        if touch:
            tippflaechen(s, "#fp-tabelle details.menue[open] .menue-liste button")
        s.taste()
        s.b.warten(0.2)

        # Ziehen: innerhalb der Gruppe (Platzhalter 1 vor Platzhalter 2), dann in eine andere (ans Ende von B).
        ziehen(s, zeile(0, 1), zeile(0, 0), anteil=0.2)
        assert struktur(s)[0][1] == ["Platzhalter 1", "Platzhalter 2"], struktur(s)
        ziehen(s, zeile(0, 0), zeile(1, 1), anteil=0.8)
        assert struktur(s)[:2] == [["Gruppe A neu", ["Platzhalter 2"], False],
                                   ["Gruppe B", ["Platzhalter 3 getippt", "Platzhalter 4", "Platzhalter 1"], False]]
        # Über die untere Hälfte eines Gruppenkopfs: an den Anfang dieser Gruppe.
        ziehen(s, zeile(1, 2), kopf(1), anteil=0.8)
        assert struktur(s)[1][1] == ["Platzhalter 1", "Platzhalter 3 getippt", "Platzhalter 4"]
        # Esc bricht ab – alles bleibt.
        vorher = struktur(s)
        ziehen(s, zeile(1, 0), zeile(2, 0), anteil=0.8, esc=True)
        assert struktur(s) == vorher
        assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter Editor getippt"
        # Bildlauf am Rand: Mit dem Finger bzw. der Maus am unteren Rand rollt die Seite.
        s.js("window.scrollTo(0, 0)")
        s.js("document.querySelector(" + json.dumps(f"{zeile(0, 0)}") + ").scrollIntoView({ block: 'start' })")
        s.js("window.scrollBy(0, -120)")
        y_vorher = s.js("scrollY")
        ziehen(s, zeile(0, 0), (breite / 2, hoehe - 6), halten=0.6, esc=True)
        assert s.js("scrollY") > y_vorher + 20, ("kein Bildlauf am Rand", y_vorher, s.js("scrollY"))
        assert struktur(s) == vorher

        # „In Gruppe verschieben“: Platzhalter 5 (ohne Gruppe) ans Ende von „Gruppe A neu“, Platzhalter 4 in eine neue Gruppe.
        menue(s, zeile(2, 0), "punkt-gruppe")
        assert s.warte("!!document.querySelector('#dlg[open] .fp-gruppenwahl')")
        if touch:
            tippflaechen(s, "#dlg[open] .fp-wahl:not(.fp-wahl-weg)")
        assert s.js("document.querySelector('#dlg[open] input[name=fp-ziel][value=\"2\"]').disabled")
        klick(s, '#dlg[open] .fp-wahl:has(input[value="0"])')
        klick(s, "#fp-gruppe-ok")
        assert struktur(s) == [["Gruppe A neu", ["Platzhalter 2", "Platzhalter 5"], False],
                               ["Gruppe B", ["Platzhalter 1", "Platzhalter 3 getippt", "Platzhalter 4"], False],
                               ["", [], True]]
        menue(s, zeile(1, 2), "punkt-gruppe")
        assert s.warte("!!document.querySelector('#dlg[open] .fp-gruppenwahl')")
        tippen(s, "#fp-neue-gruppe", "Gruppe C")
        assert s.js("document.querySelector('#dlg[open] input[name=fp-ziel][value=neu]').checked")
        klick(s, "#fp-gruppe-ok")
        st = struktur(s)
        assert st[3] == ["Gruppe C", ["Platzhalter 4"], False] and st[2] == ["", [], True], st
        assert s.js("document.querySelector('#fp-tabelle tr.fp-leer').textContent").strip().startswith("Die Gruppe ist leer")

        # Gruppe: leer ohne Rückfrage entfernen; nach oben/unten; mit Punkten nur nach Rückfrage mit Anzahl.
        menue(s, kopf(2), "gruppe-weg")
        assert not s.js("document.querySelector('dialog[open]')")
        assert [g[0] for g in struktur(s)] == ["Gruppe A neu", "Gruppe B", "Gruppe C"]
        menue(s, kopf(2), "gruppe-hoch")
        assert [g[0] for g in struktur(s)] == ["Gruppe A neu", "Gruppe C", "Gruppe B"]
        menue(s, kopf(0), "gruppe-runter")
        assert [g[0] for g in struktur(s)] == ["Gruppe C", "Gruppe A neu", "Gruppe B"]
        menue(s, kopf(1), "gruppe-weg")
        assert s.warte("!!document.querySelector('dialog[open] #c-titel')")
        assert s.js("document.querySelector('dialog[open] #c-titel').textContent") == "Gruppe „Gruppe A neu“ mit 2 Prüfpunkten entfernen?"
        klick(s, "dialog[open] #c-no")
        assert [g[0] for g in struktur(s)] == ["Gruppe C", "Gruppe A neu", "Gruppe B"]

        # Gruppe ziehen (Wunsch vom 04.11.2026): am Griff des Kopfs der ganze Block, nur zwischen Gruppen; Getipptes bleibt.
        gruppe_ziehen(s, touch)

        # Punkt entfernen (Menü), „+ Prüfpunkt“ in Gruppe C (am Ende der Gruppe), „+ Gruppe“ mit Fokus aufs Namensfeld.
        menue(s, zeile(2, 0), "punkt-weg")
        assert struktur(s)[2][1] == ["Platzhalter 3 getippt"]
        if touch:
            tippflaechen(s, "#fp-tabelle tr.fp-fuss .btn")
        klick(s, '#fp-tabelle tr.fp-fuss [data-act="punkt-neu"][data-g="0"]')
        assert struktur(s)[0][1] == ["Platzhalter 4", ""]
        tippen(s, f"{zeile(0, 1)} .fp-text", "Platzhalter neu")
        # Absatz im Prüfpunkt (Zusatz vom 04.11.2026): Enter fügt einen Zeilenumbruch ein, das Feld wächst mit.
        hoehe_vorher = s.js("document.querySelector(" + json.dumps(f"{zeile(0, 1)} .fp-text") + ").offsetHeight")
        enter(s)
        s.b.rufen("Input.insertText", text="Absatz zwei")
        feld = s.js("(() => { const t = document.querySelector(" + json.dumps(f"{zeile(0, 1)} .fp-text") + ");"
                    " return [t.value, t.offsetHeight]; })()")
        assert feld[0] == "Platzhalter neu\nAbsatz zwei" and feld[1] > hoehe_vorher, (feld, hoehe_vorher)
        # Der neue Punkt wird optional (echter Klick bzw. Tipp aufs Häkchen) – das überlebt die folgenden Neuzeichnungen.
        klick(s, f"{zeile(0, 1)} .fp-z-pflicht label")
        assert s.js("document.querySelector(" + json.dumps(f"{zeile(0, 1)} .fp-optional") + ").checked")
        # Im Gruppennamen bleibt Enter ohne Absatz.
        tippen(s, f"{kopf(0)} .fp-gruppenname", "")
        enter(s)
        assert "\n" not in s.js("document.querySelector(" + json.dumps(f"{kopf(0)} .fp-gruppenname") + ").value")
        klick(s, '[data-act="gruppe-neu"]')
        st = struktur(s)
        assert st[3] == ["", [""], False], st
        if not touch:
            assert s.js("document.activeElement.matches(" + json.dumps(f"{kopf(3)} .fp-gruppenname") + ")")
        tippen(s, f"{kopf(3)} .fp-gruppenname", LANG)
        tippen(s, f"{zeile(3, 0)} .fp-text", "Platzhalter lang")
        # Die neue Gruppe gleich nach dem Tippen am Griff an den Anfang ziehen – das Getippte zieht mit.
        ziehen(s, kopf(3), kopf(0), anteil=0.1)
        assert struktur(s) == [[LANG, ["Platzhalter lang"], False], ["Gruppe C", ["Platzhalter 4", "Platzhalter neu\nAbsatz zwei"], False],
                               ["Gruppe A neu", ["Platzhalter 2", "Platzhalter 5"], False],
                               ["Gruppe B gezogen", ["Platzhalter 3 getippt"], False]], struktur(s)
        assert s.js("document.querySelector(" + json.dumps(f"{zeile(1, 1)} .fp-optional") + ").checked")
        # Ein Neuzeichnen (Art ändern) – der lange Name steht danach ganz da (Feld bricht um, nichts abgeschnitten).
        s.js("(() => { const a = document.querySelector(" + json.dumps(f"{zeile(0, 0)} .fp-art") + "); a.value = 'text';"
             " a.dispatchEvent(new Event('change', { bubbles: true })); })()")
        s.b.warten(0.2)
        lang = s.js("(() => { const t = document.querySelector(" + json.dumps(f"{kopf(0)} .fp-gruppenname") + ");"
                    " return [t.value, t.scrollHeight - t.clientHeight, t.scrollWidth - t.clientWidth]; })()")
        assert lang[0] == LANG and len(LANG) == 80 and lang[1] <= 1 and lang[2] <= 1, lang
        assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter Editor getippt"

        # Tippflächen am Finger (Griff, „⋯“ an Punkt und Gruppe) – gemessen; kein waagerechter Bildlauf.
        if touch:
            for sel in ("#fp-tabelle .fp-griff", "#fp-tabelle tr.fp-gruppenzeile .fp-griff", "#fp-tabelle tr.fp-punkt .fp-menue summary",
                        "#fp-tabelle tr.fp-gruppenzeile .fp-menue summary",
                        "#fp-tabelle .fp-z-pflicht label"):
                tippflaechen(s, sel)
            assert s.js("getComputedStyle(document.querySelector('#fp-tabelle .fp-griff')).touchAction") == "none"
            assert s.js("getComputedStyle(document.querySelector('#fp-tabelle tr.fp-punkt')).touchAction") == "auto"
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        # Speichern: Reihenfolge und Gruppe je Punkt in der Datenbank.
        klick(s, '[data-act="speichern"]')
        assert s.warte("!document.querySelector('#fp-tabelle .fp-text') || document.querySelector('#fp-titel').value === 'Platzhalter Editor getippt'")
        s.b.warten(0.8)
        zeilen = u.sql("SELECT group_name, label, editor, mandatory FROM mat_checklist_item WHERE form_id = ? ORDER BY position", (fid,))
        assert [(z["group_name"], z["label"]) for z in zeilen] == [
            (LANG, "Platzhalter lang"), ("Gruppe C", "Platzhalter 4"), ("Gruppe C", "Platzhalter neu\nAbsatz zwei"),
            ("Gruppe A neu", "Platzhalter 2"), ("Gruppe A neu", "Platzhalter 5"),
            ("Gruppe B gezogen", "Platzhalter 3 getippt")], zeilen
        assert zeilen[0]["editor"] == "text"
        # Häkchen „optional“ ↔ pflicht: nur Platzhalter 4 und der neue Punkt sind optional.
        assert [z["mandatory"] for z in zeilen] == [1, 0, 0, 1, 1, 1], zeilen
        assert u.sql("SELECT title FROM mat_form WHERE id = ?", (fid,))[0]["title"] == "Platzhalter Editor getippt"
        assert struktur(s)[0][0] == LANG
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()

    # Nur lesen (Mitglied): dieselben Zwischenzeilen, ohne Griff, Menü und Felder.
    m = u.seite("mitglied", breite, hoehe, touch)
    try:
        oeffnen(m, fid)
        koepfe = m.js("[...document.querySelectorAll('#fp-tabelle tr.fp-gruppenzeile th')].map((t) => t.textContent.trim())")
        assert koepfe == [LANG, "Gruppe C", "Gruppe A neu", "Gruppe B gezogen"], koepfe
        assert not m.js("document.querySelector('#fp-tabelle .fp-griff, #fp-tabelle .fp-menue, #fp-tabelle textarea, [data-act=speichern]')")
        assert m.js("document.querySelectorAll('#fp-tabelle tbody tr:not(.fp-gruppenzeile)').length") == 6
        hoch = m.js("(() => { const t = document.querySelector('#fp-tabelle tr.fp-gruppenzeile th');"
                    " return t.scrollWidth <= t.clientWidth; })()")
        assert hoch, "langer Gruppenname abgeschnitten"
        # Der Absatz steht als Umbruch da (pre-line), nicht als eine Zeile.
        absatz = m.js("""(() => { const t = [...document.querySelectorAll('#fp-tabelle .mat-mehrzeilig')].find((x) => x.textContent.includes('Absatz zwei'));
          return t && [t.innerText, getComputedStyle(t).whiteSpace, t.getClientRects().length]; })()""")
        assert absatz and absatz[0] == "Platzhalter neu\nAbsatz zwei" and absatz[1] == "pre-line", absatz
        # Nur optionale Punkte tragen eine Marke, Pflichtpunkte nichts.
        marken = m.js("""[...document.querySelectorAll('#fp-tabelle tbody tr:not(.fp-gruppenzeile)')].map((tr) =>
          [tr.querySelector('.mat-mehrzeilig').textContent, tr.lastElementChild.innerText.trim()])""")
        assert marken == [["Platzhalter lang", ""], ["Platzhalter 4", "optional"], ["Platzhalter neu\nAbsatz zwei", "optional"],
                          ["Platzhalter 2", ""], ["Platzhalter 5", ""], ["Platzhalter 3 getippt", ""]], marken
        assert m.js("document.querySelectorAll('#fp-tabelle .badge').length") == 2
        assert "Pflicht" not in m.js("document.querySelector('#fp-tabelle').innerText")
        assert m.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        m.sammeln()
        assert not m.fehler, m.fehler
    finally:
        m.schliessen()
    return fid


def pruefung_und_xss(u, ids, fid):
    """Prüfungsansicht (offener Entwurf) zeigt den Absatz; HTML im Punkttext bleibt Text – im Formular wie in der Prüfung."""
    from einfuehrung_browser import PASSWORT, mail
    from test_material import freigeben
    # Das zuletzt gespeicherte Formular bekommt einen Punkt mit HTML und Umbruch und gilt für die Kategorie.
    r = u.adm.get(f"/api/material/formulare/{fid}")
    punkte = r.json["formular"]["punkte"] + [{"gruppe": "", "text": "<img src=x onerror=\"window.__xss=1\">\n<b>fett</b>",
                                              "art": "yesno", "soll": "nein"}]
    assert u.adm.put(f"/api/material/formulare/{fid}", json={"punkte": punkte}).status_code == 200
    assert u.adm.post(f"/api/material/formulare/{fid}/aktivieren", json={}).status_code == 200
    gid = u.sql("SELECT id FROM mat_folder WHERE name = 'Übung Gliederung'")[0]["id"]
    freigeben(u.adm, gid, u.ids["pruefer"], "lesen")
    freigeben(u.adm, gid, u.ids["pruefer"], "pruefen")
    r = u.adm.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2025-01"})
    assert r.status_code == 201, r.get_json()
    p = u._anmelden(mail("pruefer"), PASSWORT)
    r = p.post(f"/api/material/artikel/{r.json['artikel']['id']}/pruefungen", json={})
    assert r.status_code == 201, r.get_json()
    pid = r.json["pruefung"]["id"]
    assert "Platzhalter neu\nAbsatz zwei" in [x["text"] for x in r.json["pruefung"]["punkte"]]
    for breite, hoehe, touch in GROESSEN:
        s = u.seite("pruefer", breite, hoehe, touch)
        try:
            s.oeffnen(f"/materialablage/pruefung/{pid}", warten=0.6)
            assert s.warte("!!document.querySelector('.mat-punkt-text')")
            texte = s.js("[...document.querySelectorAll('.mat-punkt-text')].map((t) => [t.innerText, getComputedStyle(t).whiteSpace])")
            assert ["Platzhalter neu\nAbsatz zwei", "pre-line"] in texte, texte
            assert ['<img src=x onerror="window.__xss=1">\n<b>fett</b>', "pre-line"] in texte, texte
            assert not s.js("window.__xss || document.querySelector('.mat-punkt-text img, .mat-punkt-text b')")
            s.oeffnen(f"/materialablage/katalog/formular/{fid}", warten=0.6)
            assert s.warte("!!document.querySelector('#fp-tabelle')")
            assert not s.js("window.__xss || document.querySelector('#fp-tabelle img, #fp-tabelle b')")
            assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            s.sammeln()
            assert not s.fehler, s.fehler
        finally:
            s.schliessen()


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_material import katalog_grund
    with Umgebung() as u:
        ids = katalog_grund(u.adm)
        for breite, hoehe, touch in GROESSEN:
            los = time.time()
            fid = ablauf(u, ids["gurte"], breite, hoehe, touch)
            print(f"Editor {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({time.time() - los:.1f} s)")
            eine_gruppe(u, ids["gurte"], breite, hoehe, touch)
            print(f"Eine Gruppe ohne Griff {breite}×{hoehe}: bestanden")
        pruefung_und_xss(u, ids, fid)
        print("Absatz in der Prüfung, HTML bleibt Text: bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_browser()
