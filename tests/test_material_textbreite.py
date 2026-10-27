"""Zeilenlänge der Hinweis- und Hilfetexte (Entscheidung des Nutzers vom 27.10.2026, Nachtrag V10 vor dem Merge – löst
„volle Inhaltsbreite“ vom 25.10.2026 ab): python tests/test_material_textbreite.py  oder  pytest

Hinweiskästen (.notice, Zeile zur Prüfanleitung), Hilfe- und Erklärtexte (.help, p.small, p.muted) und die Fußsätze des
Jahresberichts in der Materialablage haben genau eine Höchstbreite: 100ch (gemessen rund 120 Zeichen je Zeile; ch ist
die Breite der Ziffer „0“, Text ist im Schnitt schmaler) – keine andere
Regel setzt eine eigene. Die Hilfetexte der Leitstelle ebenso. Der lange Fließtext im Wiki behält seine Lesebreite
(app.css, --lesebreite)."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTKLASSEN = re.compile(r"\.(notice|help|muted|mat-text|mat-wikizeile)\b|p\.small\b|\.mat-bericht-fuss\b")
REGEL_120 = ":where(#mat-inhalt, #mat-side) :is(.help, .notice, p.small, p.muted, .mat-wikizeile, .mat-bericht-fuss) { max-width: 100ch; }"


def _regeln(css):
    """(Selektor, Block) je Regel – auch in @media/@container (eine Ebene tief genügt hier)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def test_texte_hoechstens_120_zeichen():
    for datei in ("app/material/static/material.css", "app/material/static/global.css"):
        with open(os.path.join(WURZEL, datei), encoding="utf-8") as fh:
            css = fh.read()
        for selektor, block in _regeln(css):
            if TEXTKLASSEN.search(selektor) and re.search(r"(^|;|\s)max-width\s*:", block):
                regel = f"{selektor.strip()} {{ {block.strip()} }}"
                assert regel == REGEL_120, f"{datei}: {regel}"
        assert "--mat-kastenmass" not in css
    with open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8") as fh:
        assert fh.read().count(REGEL_120) == 1
    with open(os.path.join(WURZEL, "app/static/css/app.css"), encoding="utf-8") as fh:
        app_css = fh.read()
    assert ".leitstelle-hilfe .accordion-body, #bereich-nutzer > p.help, #bereich-einstellungen > p.help { max-width: 100ch; }" in app_css
    # Der Wiki-Fließtext behält seine Lesebreite.
    assert "--lesebreite: 690px;" in app_css and "max-width: calc(var(--lesebreite) + 2 * var(--lesepad));" in app_css
    print("Texte höchstens 120 Zeichen bestanden.")


if __name__ == "__main__":
    test_texte_hoechstens_120_zeichen()
