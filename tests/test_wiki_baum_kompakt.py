"""Seitenbaum der Strömipedia am Finger kompakter (Nutzer 02.11.2026, planung/seitenbaum-kompakt/auftrag.md):
python tests/test_wiki_baum_kompakt.py  oder  pytest tests/test_wiki_baum_kompakt.py

  1. Nur unter (pointer: coarse): Zeilen 36 statt 44 px, Klappzeichen und „⋯“ 44 × 36 px, Titel mit Zeilenhöhe 1,25 und
     6 px Polster (einzeilig mittig in genau 36 px).
  2. Trennlinien statt Abstand: feine Linie zwischen allen Zeilen (unter einer aufgeklappten Elternzeile statt über
     ihrer ersten Unterseite), vor jedem weiteren Abschnitt der obersten Ebene eine kräftigere statt 6 px Luft.
  3. „⋯“ nur in der Zeile der geöffneten Seite; sonst unsichtbar, aber für Tastatur und Vorlesehilfe erreichbar, mit dem
     Tastaturfokus wieder da. Mit der Maus unverändert (beim Darüberfahren).
  4. Der Ordnerbaum der Materialablage (ul.tree.mat-tree ohne innere <ul>) bleibt bei 44 px und ohne Linien.
Gemessen im Browser (planung/seitenbaum-kompakt/bericht.md). Reine Textprüfung, keine Daten, keine Mail."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_wiki_seitenbaum import lies, umgebung  # noqa: E402

FINGER = "@media (pointer: coarse)"


def test_regeln_im_finger_block():
    css = lies("app/static/css/app.css")
    regeln = [
        ".tree .row { min-height: 36px; }",
        ".tree .row-add, .tree .row-menu { width: 44px; height: 36px; margin-left: 0; }",
        ".tree .tg { width: 44px; height: 36px; margin: 0 -10px; position: relative; z-index: 1; }",
        ".tree a { padding-top: 6px; padding-bottom: 6px; padding-left: 8px; }",
        ".tree .baum-titel { white-space: normal; text-overflow: clip; overflow-wrap: break-word; hyphens: auto; flex-basis: 0; }",
        ".tree > ul a { min-height: 36px; line-height: 1.25; flex-wrap: wrap; align-content: center; }",
        ".tree > ul li, .tree > ul > li + li { margin: 0; }",
        ".tree > ul li + li > .row { border-top: 1px solid var(--linie); }",
        ".tree > ul li:not(.leaf, .collapsed) > .row { border-bottom: 1px solid var(--linie); }",
        ".tree > ul > li + li > .row { border-top: 2px solid var(--linie); }",
        ".tree .row:not(:has(> a.active, :focus-visible)) > .row-menu { position: absolute; width: 1px; height: 1px; margin: -1px;\n"
        "    overflow: hidden; clip-path: inset(50%); opacity: 0; }",
    ]
    for r in regeln:
        assert css.count(r) == 1, r
        assert umgebung(css, r) == FINGER, (r, umgebung(css, r))
    # Keine 44-px-Höhe mehr für Zeile, Klappzeichen und „⋯“ des Seitenbaums (die Breite bleibt 44 px).
    for alt in (".tree .row { min-height: 44px; }", ".tree .row-add, .tree .row-menu { width: 44px; height: 44px;",
                ".tree .tg { width: 44px; height: 44px;", ".tree a { padding-top: 12px; padding-bottom: 12px;"):
        assert alt not in css, alt
    # Die kräftigere Linie steht nach der feinen (gleiche Spezifität, die spätere gewinnt).
    assert css.index(".tree > ul > li + li > .row { border-top: 2px") > css.index(".tree > ul li + li > .row { border-top: 1px")


def test_keine_linie_durch_das_klappzeichen():
    css = lies("app/static/css/app.css")
    # Linien hängen nur an der Zeile (.row), nie am Klappzeichen; das Klappzeichen beginnt unter der Linie seiner Zeile.
    assert not re.search(r"\.tg[^{}]*\{[^}]*solid", css), "Linie am Klappzeichen"
    for treffer in re.finditer(r"([^{}]*)\{[^}]*border-(?:top|bottom): \d+px solid var\(--linie\)", css):
        selektor = treffer.group(1).strip().split("\n")[-1]
        if selektor.startswith(".tree > ul"):
            assert selektor.endswith("> .row"), selektor


def test_menue_nur_an_der_offenen_seite():
    css = lies("app/static/css/app.css")
    js = lies("app/static/js/wiki.js")
    # Die offene Seite trägt im Baum die Klasse active am Titel-Link, und „⋯“ steht in derselben Zeile dahinter –
    # nur so greift .row:has(> a.active) > .row-menu. Die Seite wird beim Wechsel neu gezeichnet: „⋯“ wandert mit.
    zweig = js[js.index("function branch(pid, depth)"):js.index("function renderTree()")]
    zeile = zweig[zweig.index('<div class="row"'):zweig.index("</div>${sub}")]
    assert zeile.index('<a href="/stroemipedia/') < zeile.index('<button class="row-menu"')
    assert 'class="${state.current && state.current.id === p.id ? "active" : ""}"' in zeile
    # Unsichtbar heißt nicht display: none – sonst erreichte die Tastatur „⋯“ anderer Seiten nicht mehr.
    verstecken = css[css.index(".tree .row:not(:has(> a.active, :focus-visible)) > .row-menu {"):]
    verstecken = verstecken[:verstecken.index("}")]
    assert "display: none" not in verstecken and "visibility" not in verstecken
    # Mit der Maus unverändert: „⋯“ erscheint beim Darüberfahren und mit dem Tastaturfokus.
    maus = "@media (hover: hover) and (pointer: fine)"
    assert umgebung(css, ".tree .row:hover .row-add, .tree .row:hover .row-menu { opacity: 1; }") == maus
    assert umgebung(css, ".tree .row:has(:focus-visible) :is(.row-add, .row-menu) { opacity: 1; }") == ""
    assert umgebung(css, ".tree .row-add, .tree .row-menu, .code-copy { opacity: 1; }") == "@media (hover: none), (pointer: coarse)"


def test_maus_unveraendert():
    css = lies("app/static/css/app.css")
    for r in (".tree li { margin: 1px 0; }", ".tree > ul > li + li { margin-top: 6px; }",
              ".tree .row { display: flex; align-items: center; gap: 2px; min-width: 0; }",
              "opacity: 0; flex: none; width: 20px; height: 20px; padding: 0; margin-left: 2px;",
              "flex: 1 1 auto; min-width: 0; display: flex; align-items: baseline; padding: 4px 6px; color: var(--anthrazit);",
              "width: var(--baum-spalte); height: 28px;"):
        assert r in css and umgebung(css, r) == "", r


def test_materialbaum_bleibt():
    css = lies("app/static/css/app.css")
    mat = lies("app/material/static/material.css")
    # Die neuen Regeln (Linien, Zeilenhöhe, Ränder) treffen nur den Seitenbaum der Strömipedia: Dort liegt die Liste in
    # einer eigenen <ul> unter .tree, im Ordnerbaum ist die Liste selbst .tree.
    assert '<ul class="tree mat-tree">${alle}${zweig(0, 0)}</ul>' in lies("app/material/static/material.js")
    for vorlage in ("app/templates/wiki.html", "app/templates/wiki_lesemodus.html", "app/templates/public.html"):
        assert '<ul class="tree" id="tree"></ul>' in lies(vorlage), vorlage
    for r in (".tree > ul a {", ".tree > ul li, .tree > ul > li + li {", ".tree > ul li + li > .row {",
              ".tree > ul li:not(.leaf, .collapsed) > .row {", ".tree > ul > li + li > .row {"):
        assert r in css, r
    # Was für beide gilt, fängt material.css (später geladen, gleiche Spezifität) mit 44 px auf.
    finger = mat[mat.index("@media (pointer: coarse) {\n  .mat-tree a { padding-top: 11px;"):]
    finger = finger[:finger.index("}\n}") + 3]
    assert ".mat-tree a { padding-top: 11px; padding-bottom: 11px; min-height: 44px; }" in finger
    assert ".mat-tree .tg { width: 44px; height: auto; min-height: 44px; align-self: stretch; }" in finger


def test_doku():
    log = lies("CHANGELOG-Material.md")
    kopf = log[:log.index("\n## ")]
    assert "Seitenbaum am Finger kompakter" in kopf
    abschnitt = log[log.index("## Seitenbaum am Finger kompakter"):]
    abschnitt = abschnitt[:abschnitt.index("\n## ", 5)]
    assert "gebaut 02.11.2026 (kein Schemaschritt)" in abschnitt
    assert "36 px mit Trennlinien" in abschnitt and "⋯ nur an der offenen Seite" in abschnitt
    readme = lies("README.md")
    assert "36 px" in readme[readme.index("Seitenbaum"):]


if __name__ == "__main__":
    test_regeln_im_finger_block()
    test_keine_linie_durch_das_klappzeichen()
    test_menue_nur_an_der_offenen_seite()
    test_maus_unveraendert()
    test_materialbaum_bleibt()
    test_doku()
    print("Seitenbaum kompakt bestanden.")
