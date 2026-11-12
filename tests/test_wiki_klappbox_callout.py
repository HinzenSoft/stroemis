"""Rückmeldung des Nutzers zur Strömipedia vom 12.11.2026: „Callouts in Klappboxen funktionieren nicht im Editor“.
python tests/test_wiki_klappbox_callout.py  oder  pytest tests/test_wiki_klappbox_callout.py

Ein Callout im Inhalt einer Klappbox bekam im Editor die Klassen beider Kästen (ak und co). Die Regeln der Box stehen
später im Stylesheet und nahmen der Kiste Fläche, Kante und Einzug: kein Farbfeld, das Symbol lag über dem ersten
Buchstaben, und der Rand der Kiste riss den Rahmen der Box auf. Jetzt liegt die Kiste im Rahmen der Box, eingerückt
wie in der Leseansicht. Geprüft in der echten App (Server im Faden, angemeldet als Wiki-Verwaltung) in Chromium:
Zeilen und Farbflächen beider Ansichten auf ±1 px, gemessen ab der Titelzeile der Box (darüber steht im Editor die
Marke der Box, das war schon vorher so). Ohne Chromium übersprungen."""
import base64
import io
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

BOXEN = [
    # Text davor und danach
    ":::accordion Mit Text drumherum\nInhalt vor dem Hinweis.\n\n:::warning ⚠️\n**Achtung**\n\nHinweistext in der Box.\n:::"
    "\n\nInhalt danach.\n:::",
    # die Kiste ist der ganze Inhalt der Box
    ":::accordion Nur Hinweis\n:::info 💡\nNur ein Hinweis in der Box.\n:::\n:::",
    # zwei Kisten untereinander, danach Text
    ":::accordion Zwei Hinweise\n:::warning ⚠️\nErster Hinweis.\n:::\n\n:::success ✅\nZweiter Hinweis.\n:::\n\nText danach.\n:::",
]
MD = "Anfang.\n\n" + "\n\nZwischen.\n\n".join(BOXEN) + "\n\nEnde."

# Zeilen eines Bereichs als [oben, links], ohne die Beschriftung der Marken; Teilstücke einer Zeile zählen einmal.
ZEILEN = r"""const zeilen = (els) => { const r = document.createRange(), q = [];
  els.forEach((el) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const t = w.currentNode; if (!t.textContent.trim() || t.parentElement.closest('.sek-marke')) continue;
      r.selectNodeContents(t); for (const x of r.getClientRects()) if (x.height) q.push([Math.round(x.top), Math.round(x.left)]); } });
  const u = []; q.sort((a, b) => a[0] - b[0] || a[1] - b[1]).forEach((z) => { if (!u.length || z[0] >= u[u.length - 1][0] + 4) u.push(z); });
  return u; };"""
LESEN = "(() => { " + ZEILEN + r""" document.querySelectorAll('.wiki-content details.accordion').forEach((d) => { d.open = true; });
  return [...document.querySelectorAll('.wiki-content > details.accordion')].map((d) => { const b = d.getBoundingClientRect();
    return { box: [b.left, b.top, b.right, b.bottom].map(Math.round), zeilen: zeilen([d]) }; }); })()"""
EDITOR = "(() => { " + ZEILEN + r""" const k = [...document.querySelector('.toastui-editor-ww-container .ProseMirror').children];
  const erg = []; let s = -1;
  k.forEach((el, i) => { if (el.classList.contains('ak-auf')) s = i;
    if (el.classList.contains('ak-schluss') && s >= 0) { const els = k.slice(s, i + 1), o = els[0].getBoundingClientRect(),
      u = els[els.length - 1].getBoundingClientRect();
      erg.push({ box: [o.left, o.top, o.right, u.bottom].map(Math.round), zeilen: zeilen(els.slice(1, -1)) }); s = -1; } });
  return erg; })()"""
# Flächenfarbe je Hinweisart, wie die Leseansicht sie malt
FARBEN = r"""(() => { const d = document.createElement('div'); document.body.appendChild(d); const f = {};
  for (const n of ['warning', 'info', 'success']) { d.className = 'callout callout-' + n; f[n] = getComputedStyle(d).backgroundColor; }
  d.remove(); return f; })()"""


def _bild(s):
    from PIL import Image
    d = s.b.rufen("Page.captureScreenshot", format="png")
    return Image.open(io.BytesIO(base64.b64decode(d["data"]))).convert("RGB")


def _flaechen(img, box, farben):
    """Je Farbfläche in der Box: (Art, Abstand links, oben, Abstand rechts, unten) – oben/unten absolut."""
    l, o, r, u = box
    px = img.load()
    erg = []
    for name, rgb in farben.items():
        zeilen = [y for y in range(o, u) if sum(1 for x in range(l, r) if px[x, y] == rgb) > 40]
        if not zeilen:
            continue
        anf = vor = zeilen[0]
        for y in zeilen[1:] + [None]:
            if y is None or y != vor + 1:
                xs = [x for x in range(l, r) if px[x, (anf + vor) // 2] == rgb]
                erg.append((name, xs[0] - l, anf, r - 1 - xs[-1], vor + 1))
                if y is None:
                    break
                anf = y
            vor = y
    return sorted(erg, key=lambda f: f[2])


def _relativ(messung, flaechen):
    """Alles ab der Titelzeile der Box: Zeilen [oben, links], Flächen, Unterkante."""
    l, _, _, u = messung["box"]
    t = messung["zeilen"][0][0]
    return ([[y - t, x - l] for y, x in messung["zeilen"]],
            [(n, a, o - t, b, w - t) for n, a, o, b, w in flaechen], u - t)


def _nah(a, b):
    return all(abs(x - y) <= 1 for x, y in zip(a, b))


def _lauf(u):
    r = u.adm.post("/api/wiki/pages", json={"title": "Klappbox mit Callout", "content": MD})
    assert r.status_code in (200, 201), r.get_json()
    slug = (r.get_json().get("page") or r.get_json())["slug"]
    s = u.seite("wikiverwaltung", 1000, 2200)
    try:
        s.oeffnen(f"/stroemipedia/{slug}", warten=1.5)
        s.ruhe(1.5)
        farben = {k: tuple(int(x) for x in v[v.index("(") + 1:-1].split(",")[:3]) for k, v in s.js(FARBEN).items()}
        lesen = s.js(LESEN)
        time.sleep(0.5)
        img = _bild(s)
        lesen = [_relativ(m, _flaechen(img, m["box"], farben)) for m in lesen]
        s.klick("#pg-edit")
        assert s.warte("!!document.querySelector('.toastui-editor-ww-container .ProseMirror .ak-titel')"), "Editor offen"
        s.ruhe(1.5)
        # Boxen aufklappen: Klick auf den Pfeil vor dem Titel
        for n in range(len(BOXEN)):
            x, y = s.js(f"""(() => {{ const t = [...document.querySelectorAll('.ProseMirror > .ak-erst')][{n}];
              const b = t.getBoundingClientRect(); return [b.left + 10, b.top + 12]; }})()""")
            for art in ("mousePressed", "mouseReleased"):
                s.b.rufen("Input.dispatchMouseEvent", type=art, x=x, y=y, button="left", clickCount=1)
            time.sleep(0.4)
        assert s.js("!document.querySelector('.ProseMirror > .ak-zu')"), "alle Boxen aufgeklappt"
        s.js("(() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); })()")
        time.sleep(0.6)
        editor = s.js(EDITOR)
        img = _bild(s)
        editor = [_relativ(m, _flaechen(img, m["box"], farben)) for m in editor]
    finally:
        s.schliessen()
    assert len(lesen) == len(editor) == len(BOXEN), (lesen, editor)
    for i, ((zl, fl, ul), (ze, fe, ue)) in enumerate(zip(lesen, editor)):
        fall = (i + 1, (zl, fl, ul), (ze, fe, ue))
        # jede Kiste hat in beiden Ansichten ihre Farbfläche, an derselben Stelle (links, oben, rechts, unten)
        assert fl and len(fl) == len(fe), fall
        for a, b in zip(fl, fe):
            assert a[0] == b[0] and _nah(a[1:], b[1:]), fall
        # jede Zeile auf demselben Pixel, eingerückt wie in der Leseansicht; die Box gleich hoch
        assert len(zl) == len(ze) and all(_nah(a, b) for a, b in zip(zl, ze)), fall
        assert abs(ul - ue) <= 1, fall


def test_klappbox_callout():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_klappbox_callout()
    print("ok")
