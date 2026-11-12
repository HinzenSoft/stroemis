"""Rückmeldung des Nutzers zur Strömipedia vom 12.11.2026: „Callouts haben etwas viel oberen Rand, halt ihn symmetrisch
zum unteren“ (Hinweis „Missinformationswelle“, darin eine Ausrichtung im Blocksatz).
python tests/test_wiki_callout_rand.py  oder  pytest tests/test_wiki_callout_rand.py

Im Editor trug die Marke der Ausrichtung in der Kiste den Abstand eines Absatzes (.kasten:not(.kasten-erst)): Der
Text darunter stand rund 14 px tiefer – oben 26 statt 12 px Rand. In der Leseansicht behielt der letzte Absatz einer
Ausrichtung am Kistenende seinen unteren Rand – unten 28 statt 14 px. Jetzt ist der Rand jeder Kiste oben und unten
gleich, und Editor und Leseansicht setzen jede Zeile auf denselben Pixel. Geprüft in der echten App (Server im Faden,
angemeldet als Wiki-Verwaltung) in Chromium; ohne Chromium übersprungen.

Nachtrag vom selben Tag: „Der Abstand zwischen Callouts kann ein normaler Zeilenabstand sein“. Zwei Kisten direkt
untereinander standen 2 × 1,1 em auseinander (im Raster fallen die Ränder nicht zusammen), jetzt so weit wie zwei
Absätze – in beiden Ansichten."""
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

KISTEN = [
    # wie im Artikel: die Ausrichtung ist der ganze Inhalt der Kiste
    ":::warning ⚠️\n:::align justify\n**Missinformationswelle**\n\nAuf Social Media gibt es eine Reihe an Videos.\n:::\n:::",
    ":::warning ⚠️\n**Titel**\n\n:::align justify\nText im Blocksatz.\n:::\n\nDanach im Kasten.\n:::",
    ":::warning ⚠️\n**Titel**\n\n:::align center\nZentriert am Ende.\n:::\n:::",
    ":::info 💡\n:::align center\nNur zentriert.\n:::\n:::",
    ":::warning ⚠️\n**Bremshandprinzip**\n\nEin Halbmastwurf bremst, er blockiert nicht.\n:::",
]
# zwei Kisten direkt untereinander (wie „KISS“ und „Grenzen (er)kennen“ im Artikel), danach zwei Absätze zum Vergleich
PAAR = [
    ":::success ✅\n**KISS**\n\nDie Kara-8 kommt mit Achter und HMS-Karabiner aus.\n:::",
    ":::warning ⚠️\n**Grenzen (er)kennen**\n\nDie Kara-8 funktioniert nur in eine Richtung.\n:::",
]
MD = ("Anfang.\n\n" + "\n\nZwischen.\n\n".join(KISTEN) + "\n\n" + "\n\n".join(PAAR)
      + "\n\nEnde eins.\n\nEnde zwei.")

# Zeilen eines Bereichs (oben, unten), ohne die Beschriftung der Marken; Teilstücke einer Zeile zählen einmal.
ZEILEN = r"""const zeilen = (els) => { const r = document.createRange(), q = [];
  els.forEach((el) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { if (!w.currentNode.textContent.trim() || w.currentNode.parentElement.closest('.sek-marke')) continue;
      r.selectNodeContents(w.currentNode); for (const x of r.getClientRects()) if (x.height) q.push([Math.round(x.top), Math.round(x.bottom)]); } });
  const u = []; q.sort((a, b) => a[0] - b[0]).forEach((z) => { if (!u.length || z[0] >= u[u.length - 1][1] - 2) u.push(z); }); return u; };"""
# Je Kiste [Zeilenanfänge relativ zur Oberkante, Abstand der letzten Zeile zur Unterkante].
EDITOR = "(() => { " + ZEILEN + r"""
  const k = [...document.querySelector('.toastui-editor-ww-container .ProseMirror').children]; const erg = []; let s = -1;
  k.forEach((el, i) => { if (el.classList.contains('co-marke') && !el.classList.contains('co-schluss')) s = i;
    if (el.classList.contains('co-schluss') && s >= 0) { const els = k.slice(s, i + 1), z = zeilen(els.slice(1, -1));
      const o = Math.round(els[0].getBoundingClientRect().top), u = Math.round(els[els.length - 1].getBoundingClientRect().bottom);
      erg.push([z.map((x) => x[0] - o), u - z[z.length - 1][1]]); s = -1; } });
  return erg; })()"""
LESEN = "(() => { " + ZEILEN + r"""
  return [...document.querySelectorAll('.wiki-content .callout')].map((c) => { const b = c.getBoundingClientRect(), z = zeilen([c]);
    return [z.map((x) => x[0] - Math.round(b.top)), Math.round(b.bottom) - z[z.length - 1][1]]; }); })()"""
# Abstand zwischen den beiden letzten Kisten und zwischen den beiden letzten Absätzen (Kante zu Kante)
LUECKE = r"""const luecke = (a, b) => Math.round(b.getBoundingClientRect().top - a.getBoundingClientRect().bottom);"""
LUECKE_LESEN = "(() => { " + LUECKE + r""" const c = [...document.querySelectorAll('.wiki-content > .callout')],
  p = [...document.querySelectorAll('.wiki-content > p')]; return [luecke(c.at(-2), c.at(-1)), luecke(p.at(-2), p.at(-1))]; })()"""
LUECKE_EDITOR = "(() => { " + LUECKE + r""" const k = [...document.querySelector('.toastui-editor-ww-container .ProseMirror').children],
  zu = k.filter((e) => e.classList.contains('co-schluss')), auf = k.filter((e) => e.classList.contains('co-marke') && !e.classList.contains('co-schluss')),
  p = k.filter((e) => e.tagName === 'P' && /^Ende /.test(e.textContent)); return [luecke(zu.at(-2), auf.at(-1)), luecke(p.at(-2), p.at(-1))]; })()"""


def _lauf(u):
    r = u.adm.post("/api/wiki/pages", json={"title": "Kistenrand", "content": MD})
    assert r.status_code in (200, 201), r.get_json()
    slug = (r.get_json().get("page") or r.get_json())["slug"]
    s = u.seite("wikiverwaltung", 1000, 1600)
    try:
        s.oeffnen(f"/stroemipedia/{slug}", warten=1.5)
        s.ruhe(1.5)
        lesen = s.js(LESEN)
        luecke_lesen = s.js(LUECKE_LESEN)
        s.klick("#pg-edit")
        assert s.warte("!!document.querySelector('.toastui-editor-ww-container .ProseMirror .co-marke')"), "Editor offen"
        s.ruhe(1.5)
        s.js("(() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); })()")
        time.sleep(0.5)
        editor = s.js(EDITOR)
        luecke_editor = s.js(LUECKE_EDITOR)
    finally:
        s.schliessen()
    assert len(lesen) == len(editor) == len(KISTEN) + len(PAAR), (lesen, editor)
    for i, (le, ed) in enumerate(zip(lesen, editor)):
        fall = (i + 1, le, ed)
        # oben und unten gleich viel Rand (Zeilenkasten; ±2 px für die Rundung der Schrift)
        for zeilen, unten in (le, ed):
            assert abs(zeilen[0] - unten) <= 2, fall
        # Editor und Leseansicht: jede Zeile auf demselben Pixel (±1 px)
        assert len(le[0]) == len(ed[0]) and all(abs(a - b) <= 1 for a, b in zip(le[0], ed[0])), fall
        assert abs(le[1] - ed[1]) <= 1, fall
    # zwei Kisten untereinander: so weit auseinander wie zwei Absätze, im Editor wie in der Leseansicht
    for kisten, absaetze in (luecke_lesen, luecke_editor):
        assert absaetze > 8 and abs(kisten - absaetze) <= 1, (luecke_lesen, luecke_editor)
    assert abs(luecke_lesen[0] - luecke_editor[0]) <= 1, (luecke_lesen, luecke_editor)


def test_callout_rand():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_callout_rand()
    print("ok")
