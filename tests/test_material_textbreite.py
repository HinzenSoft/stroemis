"""Texte über die volle Breite (Wunsch des Nutzers vom 25.10.2026, „Die Texte gehen nicht über die vorgesehene Breite“):
python tests/test_material_textbreite.py  oder  pytest

Hinweiskästen (.notice) und Hilfe- bzw. Erklärtexte (.help, .muted, p.small, p.mat-text) im Modul Material haben keine
eigene Höchstbreite mehr – sie laufen so breit wie die Felder und Tabellen ihres Abschnitts, auf allen Seiten des Moduls.
Der lange Fließtext im Wiki behält seine Lesebreite (app.css, --lesebreite)."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTKLASSEN = re.compile(r"\.(notice|help|muted|mat-text|mat-wikizeile)\b|p\.small\b|\.mat-bericht-fuss\b")


def _regeln(css):
    """(Selektor, Block) je Regel – auch in @media/@container (eine Ebene tief genügt hier)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def test_texte_ohne_hoechstbreite():
    for datei in ("app/material/static/material.css", "app/material/static/global.css"):
        with open(os.path.join(WURZEL, datei), encoding="utf-8") as fh:
            css = fh.read()
        for selektor, block in _regeln(css):
            if TEXTKLASSEN.search(selektor) and re.search(r"(^|;|\s)max-width\s*:", block):
                raise AssertionError(f"{datei}: {selektor.strip()} {{ {block.strip()} }}")
        assert "--mat-kastenmass" not in css
    # Der Wiki-Fließtext behält seine Lesebreite.
    with open(os.path.join(WURZEL, "app/static/css/app.css"), encoding="utf-8") as fh:
        app_css = fh.read()
    assert "--lesebreite: 690px;" in app_css and "max-width: calc(var(--lesebreite) + 2 * var(--lesepad));" in app_css
    print("Texte über die volle Breite bestanden.")


if __name__ == "__main__":
    test_texte_ohne_hoechstbreite()
