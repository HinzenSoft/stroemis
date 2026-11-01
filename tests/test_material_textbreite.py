"""Zeilenlänge der Hinweis- und Hilfetexte: python tests/test_material_textbreite.py  oder  pytest

Hilfe- und Erklärtexte ohne Kasten (.help, p.small, p.muted) und die Fußsätze des Jahresberichts in der Materialablage
haben genau eine Höchstbreite: 100ch (Entscheidung des Nutzers vom 27.10.2026, V10 – gemessen rund 120 Zeichen je
Zeile; ch ist die Breite der Ziffer „0“, Text ist im Schnitt schmaler) – keine andere Regel setzt eine eigene. Die
Hilfetexte der Leitstelle ebenso. Der lange Fließtext im Wiki behält seine Lesebreite (app.css, --lesebreite).

Hinweiskästen (.notice, die Zeile zur Prüfanleitung .mat-wikizeile) laufen seit dem 01.11.2026 über die ganze Breite
ihrer Spalte (Entscheidung des Nutzers, ersetzt „der Kasten darf schmaler sein als Felder und Tabellen“ aus V10): Kein
Kasten hat eine Höchstbreite, sein Inhalt bleibt höchstens 100ch breit – über EINE Regel in app.css, die den
Innenabstand rechts aus der Breite der Spalte rechnet. Damit sie wirkt, setzt keine spätere Regel den Innenabstand
rechts eines Kastens selbst (eigenes Mindestmaß über --kasten-rand)."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTKLASSEN = re.compile(r"\.(notice|help|muted|mat-text|mat-wikizeile)\b|p\.small\b|\.mat-bericht-fuss\b")
REGEL_120 = ":where(#mat-inhalt, #mat-side) :is(.help, p.small, p.muted, .mat-bericht-fuss):not(.notice) { max-width: 100ch; }"
REGEL_KASTEN = ":is(.notice, .mat-wikizeile):not(dialog *) { padding-right: max(var(--kasten-rand, 12px), calc(100% - 100ch)); }"
KASTEN = re.compile(r"\.(notice|mat-wikizeile|mat-anleitung-hinweis)\b")
# Alle Stylesheets, die auf Seiten mit Hinweiskästen geladen werden (app.css zuerst, dann die der Module).
BLAETTER = ("app/static/css/app.css", "app/static/css/pruefungen.css", "app/material/static/material.css",
            "app/material/static/freigaben.css", "app/material/static/global.css")


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _regeln(css):
    """(Selektor, Block) je Regel – auch in @media/@container (eine Ebene tief genügt hier)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def _oben(text, zeichen):
    """text an zeichen zerlegen, aber nicht innerhalb von Klammern (:is(a, b), :not(x y))."""
    teile, tiefe, puffer = [], 0, ""
    for c in text:
        tiefe += (c == "(") - (c == ")")
        if tiefe == 0 and c in zeichen:
            teile.append(puffer)
            puffer = ""
        else:
            puffer += c
    return [t for t in teile + [puffer] if t.strip()]


def _trifft_kasten(selektor):
    """Wählt der Selektor (ein Teil der Liste) den Kasten SELBST – nicht ein Element darin? Maßgeblich ist der letzte
    Teil nach dem letzten Kombinator; was in :not(…) steht, schließt aus und zählt nicht."""
    letzter = _oben(selektor.strip(), " >+~")[-1]
    return bool(KASTEN.search(re.sub(r":not\((?:[^()]|\([^()]*\))*\)", "", letzter)))


def test_texte_hoechstens_120_zeichen():
    for datei in ("app/material/static/material.css", "app/material/static/global.css"):
        css = lesen(datei)
        for selektor, block in _regeln(css):
            if TEXTKLASSEN.search(selektor) and re.search(r"(^|;|\s)max-width\s*:", block):
                regel = f"{selektor.strip()} {{ {block.strip()} }}"
                assert regel == REGEL_120, f"{datei}: {regel}"
        assert "--mat-kastenmass" not in css
    assert lesen("app/material/static/material.css").count(REGEL_120) == 1
    app_css = lesen("app/static/css/app.css")
    assert ".leitstelle-hilfe .accordion-body, #bereich-nutzer > p.help, #bereich-einstellungen > p.help { max-width: 100ch; }" in app_css
    # Riegenkarten: nur die Hilfetexte (auch div.help) – der Hinweiskasten nicht mehr.
    assert ".pruef .help { max-width: 100ch; }" in lesen("app/static/css/pruefungen.css")
    # Der Wiki-Fließtext behält seine Lesebreite.
    assert "--lesebreite: 690px;" in app_css and "max-width: calc(var(--lesebreite) + 2 * var(--lesepad));" in app_css
    print("Texte höchstens 120 Zeichen bestanden.")


def test_kaesten_ganze_breite_inhalt_100ch():
    """Ein Kasten hat keine Höchstbreite (und keine feste Breite), sein Inhalt höchstens 100ch – über die eine Regel."""
    app_css = lesen("app/static/css/app.css")
    assert app_css.count(REGEL_KASTEN) == 1
    # Die Regel steht direkt hinter der Grundregel des Kastens; nur die setzt den Innenabstand als Kurzform.
    grund = ".notice { background: var(--grau-hell); border-left: 4px solid var(--gelb); padding: 10px 12px; margin: 12px 0; }"
    assert app_css.index(grund) < app_css.index(REGEL_KASTEN)
    for datei in BLAETTER:
        for selektor, block in _regeln(lesen(datei)):
            regel = f"{selektor.strip()} {{ {block.strip()} }}"
            if regel in (REGEL_KASTEN, grund) or not any(_trifft_kasten(s) for s in _oben(selektor, ",")):
                continue
            eigenschaften = [e.split(":", 1)[0].strip() for e in block.split(";") if ":" in e]
            for verboten in ("max-width", "width", "max-inline-size", "inline-size"):
                assert verboten not in eigenschaften, f"{datei}: {regel}"
            # Kein späterer Innenabstand rechts – er überstimmte die Regel (die Kurzform „padding“ setzt ihn mit).
            for verboten in ("padding", "padding-right", "padding-inline", "padding-inline-end"):
                assert verboten not in eigenschaften, f"{datei}: {regel}"
    # Der Anleitungshinweis (eigener Rahmen) gibt nur sein Mindestmaß an – am Rechner wie am Telefon.
    css = lesen("app/material/static/material.css")
    regel = css[css.index(".notice.mat-anleitung-hinweis {"):css.index("}", css.index(".notice.mat-anleitung-hinweis {"))]
    assert "padding-block: 14px; padding-left: 16px; --kasten-rand: 16px;" in regel
    assert ".notice.mat-anleitung-hinweis { padding-block: 10px; padding-left: 12px; --kasten-rand: 12px; }" in css
    # Gegenprobe der Prüfung selbst: Diese Regeln wären Verstöße bzw. keine.
    assert _trifft_kasten(".notice.mat-anleitung-hinweis") and _trifft_kasten("#mat-inhalt p.notice")
    assert not _trifft_kasten("#mat-inhalt :is(.notice, .mat-wikizeile) :is(a:not(.btn), .lnk)")
    assert not _trifft_kasten(":where(#mat-inhalt, #mat-side) :is(.help, p.small, p.muted, .mat-bericht-fuss):not(.notice)")
    print("Kästen über die ganze Breite bestanden.")


if __name__ == "__main__":
    test_texte_hoechstens_120_zeichen()
    test_kaesten_ganze_breite_inhalt_100ch()
