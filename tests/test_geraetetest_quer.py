"""Gerätetest 01.11.2026 – Teil X Querschnitt (Auftrag planung/geraetetest/auftrag_teil_x.md):
python tests/test_geraetetest_quer.py  oder  pytest tests/test_geraetetest_quer.py

  B4   Jede :hover-Regel aller Stylesheets steht in @media (hover: hover) and (pointer: fine); am Finger :active.
  B12  Hilfe-, Neben- und Meta-Texte 14 px (--fs-klein), Hauptnavigation 15 px in allen Breiten, Zwischentitel der Leisten.
  F1   Listen der Leitstelle und Riegenkarten ab 760 px Inhalt als Tabelle; Nutzertabelle im Rahmen, Menüs bleiben darin.
  M    Abschlussleiste der Prüfung ohne negative Ränder (.mat-pruefung nicht breiter als ihr Kasten).
  Q3   Bewertungsmatrix bis 500 px Höhe kompakt, Zellen 44 px.
Das Verhalten im Browser (Zustand nach dem Tipp, Umbrüche, Tippflächen, Lage der Leisten) ist gemessen
(planung/geraetetest/bericht_teilx.md); hier steht, dass die Stellen im Code hängen."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP, MAT, RK = "app/static/css/app.css", "app/material/static/material.css", "app/static/css/pruefungen.css"
STYLESHEETS = [APP, MAT, RK, "app/material/static/freigaben.css", "app/material/static/global.css"]
MAUS = "(hover: hover) and (pointer: fine)"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def regeln(css):
    """(Kette der umgebenden @-Köpfe, Selektor) je Regel – kleiner Zerleger ohne Kommentare und Zeichenketten."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r'"(?:[^"\\]|\\.)*"', '""', css)
    aus, stapel, start = [], [], 0
    for i, c in enumerate(css):
        if c == "{":
            kopf = css[start:i].strip()
            stapel.append(kopf)
            if not kopf.startswith("@"):
                aus.append((tuple(stapel[:-1]), kopf))
            start = i + 1
        elif c == "}":
            stapel.pop()
            start = i + 1
        elif c == ";":
            start = i + 1
    assert not stapel
    return aus


def test_b4_hover_nur_mit_maus():
    for pfad in STYLESHEETS + ["app/templates/offline.html"]:
        text = lies(pfad)
        if pfad.endswith(".html"):
            text = text[text.index("<style>") + 7:text.index("</style>")]
        for koepfe, sel in regeln(text):
            if ":hover" in sel:
                assert any(MAUS in k for k in koepfe), (pfad, sel)
    # Gemischte Listen sind geteilt: der Grundzustand bleibt ohne Medienabfrage.
    app = lies(APP)
    assert ".btn:disabled { opacity: .55;" in app and ".btn.secondary:disabled { background: var(--weiss);" in app
    assert ":is(.menue-liste, .mat-menue-liste, .zeilenmenue-liste, .menue-schwebend, .tree-menu) > :is(a, button):focus-visible {\n  background: var(--grau-hell);" in app
    assert "table.list tr:hover td :is(a:not(.btn), .lnk) { color: var(--rot-auf-flaeche); }" in app
    # Am Finger: :active statt des festhängenden :hover.
    finger = app[app.index("/* Überfahren nur mit der Maus (Gerätetest B4)"):]
    finger = finger[:finger.index("\n}\n")]
    assert "@media (pointer: coarse) {" in finger
    assert '.btn:active:not(:disabled, [aria-disabled="true"]) { background: var(--rot-dunkel);' in finger
    assert ".nav a:active, .nav button:active" in finger and ".chip:active" in finger
    # Was am Rechner erst beim Überfahren erscheint, steht ohne feinen Zeiger immer da.
    assert "@media (hover: none), (pointer: coarse) {\n  .tree .row-add, .tree .row-menu, .code-copy { opacity: 1; }" in app
    assert "@media (hover: none), (pointer: coarse) {\n  .erg-knopf" in lies(RK)
    assert "@media (hover: none) { table.list.mat-tabelle tr:hover td" not in lies(MAT)


def test_b12_schriftgroessen():
    app = lies(APP)
    assert "--fs-klein: .875rem;" in app and "--fs-klein: .82rem" not in app
    assert "--fs-klein: .875rem;" in lies("app/templates/offline.html")
    # Navigation: keine kleinere Schrift mehr am Telefon, „Mehr“ erbt die 15 px der Leiste.
    assert "font-size: var(--fs-klein); }" not in app[app.index("@media (max-width: 480px) {\n  .nav a"):][:200]
    assert ".nav a, .nav button { padding: 0 9px; }" in app
    assert "  font: inherit; font-weight: 600; text-decoration: none; cursor: pointer; }" in app
    zwischentitel = app[app.index(".rail-title, .panel-body h3, .side-title"):][:200]
    assert "font-size: var(--fs-klein);" in zwischentitel
    mat = lies(MAT)
    assert ".mat-side-kopf a { font-weight: 700; color: var(--anthrazit); text-decoration: none; font-size: var(--fs-klein);" in mat
    rk = lies(RK)
    assert ".vk-stempel { background: none; border: 0; padding: 0; font: inherit; font-size: var(--fs-klein);" in rk
    assert ".pruef .c-tabs.reiter button { padding: 10px 2px; font-size: var(--fs-klein); }" in rk


def test_f1_listen_ab_760_px_inhalt():
    app = lies(APP)
    assert "@container liste (max-width: 820px)" not in app
    assert app.count("@container liste (max-width: 759px) {") == 2
    assert "@container liste (min-width: 760px) and (max-width: 1099px) {" in app
    assert "main.leitstelle .nutzer-rahmen { overflow-x: auto;" in app
    assert "main.leitstelle #users { min-width: 1100px; }" in app
    assert "main.leitstelle #users :is(th, td):first-child { position: sticky; left: 0;" in app
    adm = lies("app/templates/admin.html")
    assert '<div class="nutzer-rahmen">\n  <table class="list" id="users">' in adm
    # Menüs in einem abschneidenden Rahmen öffnen nach oben bzw. rollen in sich.
    common = lies("app/static/js/common.js")
    assert "function menueRahmen(knopf, el) {" in common and "const r = menueRahmen(knopf, m);" in common
    assert 'if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;' in common
    js = lies("app/static/js/pruefungen.js")
    assert "<th>Teil&shy;nehmende</th>" in js and '<col style="width:13%">' in js


def test_mat_pruefung_ohne_ueberbreite():
    mat = lies(MAT)
    assert ".mat-abschluss { margin-left: -12px; margin-right: -12px;" not in mat
    assert "border-image: linear-gradient(var(--anthrazit), var(--anthrazit)) 1 / 2px 0 0 / 0 12px;" in mat
    assert "box-shadow: -12px 0 0 var(--weiss), 12px 0 0 var(--weiss), var(--schatten-leiste); }" in mat


def test_q3_matrix_bei_wenig_hoehe():
    rk = lies(RK)
    teil = rk[rk.index("/* Matrix bei wenig Höhe (Gerätetest Q3, Teil X)"):]
    assert "@media (max-height: 500px) {" in teil
    assert ".bew-matrix .zelle { min-height: 44px;" in teil
    assert ".pruef .bew-matrix .tn-sub, .bew-matrix .zelle .sub { display: none; }" in teil
    assert '.bew-matrix .linkbtn::after { content: ""; position: absolute; inset: -12px -4px; }' in teil


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(name, "bestanden.")
