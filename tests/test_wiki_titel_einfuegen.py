"""Zwei Rückmeldungen des Nutzers zur Strömipedia vom 11.11.2026:
python tests/test_wiki_titel_einfuegen.py  oder  pytest tests/test_wiki_titel_einfuegen.py

1. Der Titel einer Klappbox ist im Editor ein gewöhnlicher Absatz und lässt sich fett setzen. Gespeichert steht das als
   ":::accordion **Quellen**", und die Leseansicht zeigte die Sternchen. Jetzt trägt der Titel seine Formatierung –
   gereinigt wie der übrige Artikel. Nachtrag 12.11.2026: Eine Überschrift als Titel („:::accordion #### Anfertigung“)
   verliert ihre Rauten – in der Leseansicht und beim Speichern.
2. Ein ":::warning", dessen ":::" am Ende der letzten Textzeile stand statt in einer eigenen, galt im Editor als
   Abschnitt bis zum Artikelende (EDMD.topLevelBlocks). Ein Spaltenabschnitt, eingefügt irgendwo darunter, landete
   deshalb ganz unten. Jetzt ist ":::" ohne Schlusszeile ein gewöhnlicher Absatz, wie in der Leseansicht.
Geprüft im echten Editor (Toast UI mit den Plugins der Strömipedia) in Chromium; ohne Chromium übersprungen."""
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import uebersprungen  # noqa: E402
from test_wiki_leerzeile import Editor  # noqa: E402

# Wie insertMarkdownAtCursor in wiki.js: Marke an den Schreibstrich, Markdown holen, umgebenden Block suchen.
# Ist er mehrzeilig, käme der neue Block hinter ihn.
EINFUEGESTELLE = """(() => {
  const T = "zzeinfuegestellezz"; ed.replaceSelection(T); const md = ed.getMarkdown();
  const zeilen = md.split("\\n"); const idx = zeilen.findIndex((l) => l.includes(T));
  const u = EDMD.topLevelBlocks(md).blocks.find((x) => idx >= x.start && idx < x.end);
  return u.end - u.start;
})()"""

KAPUTT = ("Davor.\n\n:::warning\nEin Halbmastwurf wird hinterlegt, bevor sich jemand darauf verlässt. :::\n\n"
          "**Bild Halbmastwurf**\n\n### Schleifknoten\n\nDer Schleifknoten hält.\n\n### Überhandknoten\n\nText.")


def _bloecke(e, md):
    return e.js(f"EDMD.topLevelBlocks({json.dumps(md)}).blocks.map((b) => [b.start, b.end])")


def _lauf(e):
    # 1. Klappbox-Titel mit Formatierung
    html = e.js("MD.render(':::accordion **Quellen** und *mehr*\\nInhalt\\n:::')")
    assert "<summary><strong>Quellen</strong> und <em>mehr</em></summary>" in html, html
    assert "**" not in html, html
    html = e.js("MD.render(':::accordion Titel mit `Code` und [Link](https://example.org)\\nInhalt\\n:::')")
    assert "<code>Code</code>" in html and '<a href="https://example.org"' in html, html
    # Ohne Titel bleibt „Details“, und Fremdes wird gereinigt wie im übrigen Artikel.
    assert "<summary>Details</summary>" in e.js("MD.render(':::accordion\\nInhalt\\n:::')")
    html = e.js("MD.render(':::accordion <img src=x onerror=alert(1)> Titel\\nInhalt\\n:::')")
    assert "onerror" not in html and "Titel</summary>" in html, html
    # Im Editor bleibt der Titel ein Absatz, die Sternchen gehen beim Speichern unverändert zurück.
    e.setze(":::accordion **Quellen**\nInhalt\n:::", 0)
    assert e.js("md()") == ":::accordion **Quellen**\nInhalt\n:::", e.js("md()")
    # Nachtrag 12.11.2026: Eine Überschrift als Titel („:::accordion #### Anfertigung“) zeigte die Rauten. Die
    # Leseansicht nimmt sie weg, das Speichern schreibt den Titel ohne sie; „#1“ und „C#“ sind keine Überschrift.
    for kopf, soll in (("#### Anfertigung", "Anfertigung"), ("## Titel ##", "Titel"), ("#### **Fett**", "<strong>Fett</strong>"),
                       ("#1 Fehler", "#1 Fehler"), ("C# Grundlagen", "C# Grundlagen"), ("####", "Details")):
        html = e.js(f"MD.render({json.dumps(':::accordion ' + kopf + chr(10) + 'Inhalt' + chr(10) + ':::')})")
        assert f"<summary>{soll}</summary>" in html, (kopf, html)
    e.setze(":::accordion #### Anfertigung\nInhalt\n:::", 0)
    assert e.js("bloecke()")[1] == "Anfertigung", e.js("bloecke()")
    assert e.js("md()") == ":::accordion Anfertigung\nInhalt\n:::", e.js("md()")
    assert e.js("EDMD.repariert()") is False, "kein Reparaturhinweis"

    # 2. ":::" ohne Schlusszeile
    e.setze(KAPUTT, 0)
    em = e.js("ed.getMarkdown()")
    bl = _bloecke(e, em)
    assert len(bl) == 8 and all(b - a == 1 for a, b in bl), (em, bl)          # vorher 2: „Davor.“ und der Rest
    e.setze(KAPUTT, e.js("bloecke()").index("Der Schleifknoten hält."), True)
    assert e.js(EINFUEGESTELLE) == 1                                   # vorher: der Rest des Artikels
    # Die Leseansicht zeigt den Text wie bisher als Absatz.
    assert '<div class="callout' not in e.js(f"MD.render({json.dumps(KAPUTT)})")
    # Ein vollständiger Abschnitt bleibt EIN Block – auch verschachtelt und mit ":::" im Codebeispiel.
    md = ":::info\nA\n:::warning\nB\n:::\n```\n:::\n```\nC\n:::\n\nDanach."
    assert _bloecke(e, md) == [[0, 10], [11, 12]], _bloecke(e, md)
    # Ein offener Abschnitt vor einem vollständigen schluckt ihn nicht mehr.
    md = ":::warning\nText :::\n\n:::info\nX\n:::\n\nDanach."
    assert _bloecke(e, md) == [[0, 1], [1, 2], [3, 6], [7, 8]], _bloecke(e, md)


def test_titel_und_einfuegen():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Editor() as e:
        _lauf(e)
        fehler = [f for f in e.b.fehler() if "favicon" not in f]
        assert not fehler, fehler


if __name__ == "__main__":
    test_titel_und_einfuegen()
    print("ok")
