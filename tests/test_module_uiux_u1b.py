"""UI/UX vor dem Merge, Teil U1b „Aussehen“ (27.10.2026, Auftrag planung/material-phase4/auftrag_uiux_bau.md):
python tests/test_module_uiux_u1b.py  oder  pytest tests/test_module_uiux_u1b.py

  A5  Text auf hellen Flächen: Rot und Grau auf --rot-hell/--grau-hell im dunklen Rot bzw. Anthrazit (app-weite Regel),
      Fokusrahmen in Menüeinträgen, Merklisten-Stern mit Kontur.
  A6  Dialoge am Telefon: overflow-wrap break-word statt anywhere.
  A7  Anlegen-Knöpfe: .k-text ist der Bezugsrahmen des nur vorgelesenen „ anlegen“.
  A8  Tippflächen am Finger: Felder/Knöpfe im Inhalt, Mängel-Filter, Ebenen der Karte, „alle Werte“, Listenlinks.
  A9  Große Systemschrift: Reiter brechen um, lange Überschriften brechen.
  A14 Auswahlpunkte und Kästchen in Anthrazit.
  A15 44-px-Regeln nur unter pointer: coarse (Ausnahmen: bewusst große Bedienelemente, Bild- und Griffmaße).
  D4  Ein Menübaustein (details.menue, .menue-liste, .menue-schwebend) – mat-menue/zeilenmenue/tree-menu sehen gleich aus.
  D5  Ein Abschnittskopf (.abschnittskopf), auch Profil „Unterschrift“.
  D6  Ein Leerzustand (.leerzustand), Strömipedia „Seite nicht gefunden“ mit h1.
  D7  Ein Farbsystem für Statusmarken, eine Umbruchregel.
  D8  Seitenreiter als Linie, Reiterzahl als Marke.
  D9  Ein Textknopf .lnk (44 px am Finger ohne höhere Zeile).
  D10 Namen als Einheit app-weit.
  D11 Tokens statt freier Werte.
  D12 Keine toten Überschreibungen, wiederkehrende Abstände als Klassen, Hinweisbreite der Riegenkarten.
Messungen im Browser: planung/material-phase4/bericht_uiux_bau_u1b.md. Alle Inhalte sind Platzhalter."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_CSS = "app/static/css/app.css"
MAT_CSS = "app/material/static/material.css"
RK_CSS = "app/static/css/pruefungen.css"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def ohne_kommentare(css):
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), css, flags=re.S)


def tokens():
    root = lies(APP_CSS)
    root = root[root.index(":root {"):root.index("\n}\n", root.index(":root {"))]
    werte = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", root))
    def aufloesen(w):
        while w.startswith("var("):
            w = werte[w[4:-1]].strip()
        return w
    return {k: aufloesen(v.strip()) for k, v in werte.items()}


def kontrast(a, b):
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    x, y = lum(a), lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


def test_a5_text_auf_hellen_flaechen():
    t = tokens()
    for flaeche in ("--rot-hell", "--grau-hell", "--co-info-fl", "--co-success-fl", "--co-warning-fl"):
        assert kontrast(t["--rot-auf-flaeche"], t[flaeche]) >= 4.5, flaeche
        assert kontrast(t["--anthrazit"], t[flaeche]) >= 4.5, flaeche
    # Das Hausrot und das Grau reichen dort nicht – deshalb die Regel.
    assert kontrast(t["--rot"], t["--rot-hell"]) < 4.5 and kontrast(t["--grau"], t["--rot-hell"]) < 4.5
    css, rk, mat = lies(APP_CSS), lies(RK_CSS), lies(MAT_CSS)
    regel = css[css.index("/* Text auf hellen Flächen (UI/UX A5"):]
    regel = regel[:regel.index("{ color: var(--anthrazit); }")]
    for flaeche in (".notice", ".callout", "table.list tr:hover td", ".zelle.st-mangelhaft", ".tn-karte.offen",
                    ".mat-mangelzeile", ".mat-importhinweis", ".mat-rr-kasten"):
        assert flaeche in regel, flaeche
    assert ":is(a:not(.btn), .lnk) { color: var(--rot-auf-flaeche); }" in regel
    assert ":is(.muted, .help, .sub, small)" in regel
    # Die 13 Stellen: Avatare, Matrix, „hier gesetzt“, Diff, Editorleiste, Kopfleiste „Mehr“, btn danger beim Überfahren.
    for stelle in (".btn.danger:hover { background: var(--rot-hell); color: var(--rot-auf-flaeche); }",
                   ".einst-quelle.q-gespeichert { border-color: var(--rot); color: var(--rot-auf-flaeche);",
                   ".diff del { background: var(--rot-hell); color: var(--rot-auf-flaeche); }",
                   ".ed-bubble button.on, .ed-ctx button.on { background: var(--rot-hell); color: var(--rot-auf-flaeche); }",
                   ".ed-bubble button:hover, .ed-ctx button:hover { background: var(--grau-hell); color: var(--rot-auf-flaeche); }",
                   "button:hover { background: var(--grau-hell); color: var(--rot-auf-flaeche); }",
                   ".rundknopf.on { border-color: var(--rot); background: var(--rot-hell); color: var(--rot-auf-flaeche); }"):
        assert stelle in css, stelle
    assert css.count("background: var(--rot-hell); color: var(--rot-auf-flaeche); font-size") == 3   # Avatare, Profilbild
    assert "background: var(--rot-hell); color: var(--rot-auf-flaeche); font-size: 1.7rem" in css      # Profilbild
    assert ".zelle.st-mangelhaft .txt, .zelle.st-nachpruefung_mangelhaft .txt { color: var(--rot-auf-flaeche); }" in rk
    assert "background: var(--rot-hell); color: var(--rot-auf-flaeche); font-size: var(--fs-marke)" in rk     # .tn-bild
    # Kein Rot auf Rot-hell mehr als Schrift.
    for datei in (css, rk, mat):
        assert not re.search(r"background: var\(--rot-hell\); color: var\(--rot\);", ohne_kommentare(datei))
    # Fokus in Menüeinträgen: Rahmen bleibt (kein outline: none), Stern mit anthrazitfarbener Kontur.
    assert ".mat-menue-liste a:hover, .mat-menue-liste a:focus-visible { background: var(--grau-hell); outline: none; }" not in mat
    assert "outline-offset: -3px; box-shadow: none; }" in css
    assert ".tree .fav { color: var(--gelb); -webkit-text-stroke: 1px var(--anthrazit); paint-order: stroke fill; }" in css
    assert kontrast(t["--anthrazit"], t["--grau-hell"]) >= 3
    print("A5 bestanden.")


def test_a6_a7_a14_einzeiler():
    css = lies(APP_CSS)
    assert "dialog .dlg-body { max-height: calc(100dvh - 22px); overflow-wrap: break-word; overscroll-behavior: contain; }" in css
    assert "overflow-wrap: anywhere; overscroll-behavior" not in css
    assert ".k-text { position: relative; }" in css
    assert "input[type=radio], input[type=checkbox] { accent-color: var(--anthrazit); }" in css
    # Ausnahme: die Häkchen der Riegenkarten-Voraussetzungen bleiben grün.
    assert lies(RK_CSS).count("accent-color: var(--ok);") == 2
    print("A6, A7, A14 bestanden.")


def coarse_bloecke(css):
    """Text aller @media-Blöcke mit pointer: coarse (Klammern gezählt)."""
    css = ohne_kommentare(css)
    teile = []
    for m in re.finditer(r"@media[^{]*pointer: coarse[^{]*\{", css):
        tiefe, i = 1, m.end()
        while tiefe:
            tiefe += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        teile.append(css[m.end():i])
    return "\n".join(teile)


def test_a8_tippflaechen():
    css, rk, mat = lies(APP_CSS), lies(RK_CSS), lies(MAT_CSS)
    touch = coarse_bloecke(css)
    assert (":where(main) :where(input:not([type=checkbox], [type=radio], [type=file], [type=hidden], [type=range], [type=color]),\n"
            "    select, .btn):not(:where(.ed-bubble, .ed-ctx, .toastui-editor-defaultUI) *) { min-height: 44px; }") in touch
    assert ".map-shell .leaflet-control-layers label { display: flex; align-items: center; min-height: 44px; margin: 0; }" in touch
    assert ".map-shell .leaflet-control-layers-expanded .leaflet-control-layers-toggle { display: block; }" in touch
    assert ".pruef table.list td a.titel::after { content: \"\"; position: absolute; inset: -14px -4px; }" in touch
    assert ".home-baum li > a { display: block; }" in touch and ".home-cols li > a::after" in touch
    assert ".maengel-filter label.inline { min-height: 44px; }" in coarse_bloecke(rk)
    assert ".mat-na-werte > summary { display: flex; align-items: center; min-height: 44px;" in coarse_bloecke(mat)
    print("A8 bestanden.")


def test_a9_grosse_schrift():
    css = lies(APP_CSS)
    assert "h1 { font-size: 1.7rem; font-weight: 700; color: var(--rot); overflow-wrap: anywhere; }" in css
    assert ".c-tabs.reiter-linie { flex-wrap: wrap;" in css
    assert "color: var(--anthrazit); background: none; white-space: nowrap; }" in css
    print("A9 bestanden.")


# 44-px-Regeln, die bewusst ohne pointer: coarse gelten (Bericht U1b, A15): Prüf- und Bewertungsdialog, Bild- und Griffmaße,
# Leisten- und Schubladenknöpfe in schmalen Fenstern (auch mit Maus), Karten-Häkchen und Kacheln in Container-Abfragen.
A15_BEWUSST = {
    MAT_CSS: (".mat-suchzeile > .mat-side-auf", ".mat-abschluss-zeile .btn", ".mat-us-feld .btn", ".mat-lb-pfeil",
              ".mat-nav.eng .mat-side-auf", ".mat-side-zu", ".mat-ergebnis button", "td.mat-k-wahl .mat-wahl-feld",
              ".mat-kachel.null"),
    RK_CSS: (".erg-knopf", ".vk-zeile", ".zelle-zeile .zelle", ".stoppuhr .su-knoepfe .btn", ".krit-zeile", ".medien-wahl li .btn",
             ".medien-knopf", ".bew-wahl button"),
    APP_CSS: (".maskottchen img", ".locate-banner img", ".ed-resize", ".lb-side .close"),
}


def test_a15_touchregeln():
    for datei, erlaubt in A15_BEWUSST.items():
        css = ohne_kommentare(lies(datei))
        touch = coarse_bloecke(lies(datei))
        rest = css
        for teil in touch.split("\n"):
            if teil.strip():
                rest = rest.replace(teil, "", 1)
        for kopf, rumpf in re.findall(r"([^{}]+)\{([^{}]*)\}", rest):
            if re.search(r"(min-)?(height|width):\s*4[48]px", rumpf):
                assert any(e in kopf for e in erlaubt), (datei, kopf.strip()[-80:])
    css = lies(APP_CSS)
    assert "@media (pointer: coarse) { .nav .nav-mehr-liste a, .nav .nav-mehr-liste button { min-height: 44px; } }" in css
    assert "@media (pointer: coarse) { .mv-alle a { min-height: 44px; } }" in lies(MAT_CSS)
    assert "@media (pointer: coarse) { .tn-karte .tn-kopf .linkbtn { min-height: 44px; } }" in lies(RK_CSS)
    print("A15 bestanden.")


def test_d4_ein_menue():
    css, mat = lies(APP_CSS), lies(MAT_CSS)
    assert "details:is(.menue, .mat-menue, .zeilenmenue) { position: relative; display: inline-block; }" in css
    assert ":is(.menue-liste, .mat-menue-liste, .zeilenmenue-liste) { position: absolute; right: 0; top: calc(100% + 6px); z-index: 60; }" in css
    assert ":is(.menue-schwebend, .tree-menu) { position: absolute; z-index: 1400; }" in css
    assert "font-weight: 700;\n  color: var(--rot); text-align: left;" in css
    # Die alten Einzelbausteine sind weg.
    assert ".zeilenmenue-liste button {" not in css and ".tree-menu button.danger" not in css and ".tree-menu {" not in css
    assert ".mat-menue-liste {" not in mat and ".mat-menue-liste a {" not in mat
    print("D4 bestanden.")


def test_d5_abschnittskopf():
    css, mat, rk = lies(APP_CSS), lies("app/material/static/material.js"), lies("app/static/js/pruefungen.js")
    assert ".abschnittskopf { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;" in css
    assert mat.count('<div class="abschnittskopf">') == 7 and "mat-kastenkopf" not in mat
    assert rk.count('<div class="abschnittskopf">') == 5 and "reiter-kopf" not in rk
    assert ".mat-kastenkopf {" not in lies(MAT_CSS) and ".reiter-kopf {" not in lies(RK_CSS)
    profil = lies("app/templates/profil.html")
    assert '<div class="abschnittskopf"><h3 class="us-titel">Unterschrift</h3>{{ us_knoepfe }}</div>' in profil
    assert '<div class="abschnittskopf"><h2>Unterschrift</h2>{{ us_knoepfe }}</div>' in profil
    assert profil.count('id="us-zeichnen"') == 1
    print("D5 bestanden.")


def test_d6_leerzustand():
    css = lies(APP_CSS)
    assert ".leerzustand { color: var(--grau); padding: 14px 0; }" in css
    assert ".empty {" not in css and ".mat-leer {" not in lies(MAT_CSS) and ".pruef .leer {" not in lies(RK_CSS)
    for datei in ("app/material/static/material.js", "app/static/js/pruefungen.js", "app/static/js/map.js",
                  "app/static/js/wiki.js", "app/static/js/public.js", "app/material/static/freigaben.js"):
        js = lies(datei)
        assert 'class="empty"' not in js and 'class="mat-leer"' not in js and '<div class="leer">' not in js, datei
        assert "leerzustand" in js, datei
    for datei in ("app/static/js/wiki.js", "app/static/js/public.js"):
        assert '<div class="wiki-head"><h1>Seite nicht gefunden</h1></div><p class="leerzustand">' in lies(datei)
    print("D6 bestanden.")


def test_d7_statusmarken():
    css = lies(APP_CSS)
    assert ".badge.gruen, .status-ok { background: var(--ok); color: var(--weiss); }" in css
    assert ".badge.rot, .status-danger { background: var(--rot); color: var(--weiss); }" in css
    assert ".badge.grey, .status-grau { background: var(--grau-hell); color: var(--grau); box-shadow: inset 0 0 0 1px var(--linie); }" in css
    assert ".badge.rot {" not in lies(RK_CSS)
    t = tokens()
    for flaeche in ("--ok", "--rot", "--wasser"):
        assert kontrast(t["--weiss"], t[flaeche]) >= 4.5
    # Eine Umbruchregel: --radius-gross, kein freier Radius.
    assert "#u-freigaben .badge {\n  border-radius: var(--radius-gross); line-height: 1.3; }" in css
    assert "border-radius: 9px" not in lies(MAT_CSS)
    print("D7 bestanden.")


def test_d8_reiter():
    css, rk = lies(APP_CSS), lies("app/static/js/pruefungen.js")
    assert '<div class="c-tabs reiter reiter-linie" role="tablist">' in rk
    assert 'Teilnehmende<span class="reiter-zahl">${lg.tn_anzahl}</span>' in rk
    assert '<span class="reiter-zahl offen" title="offene Mängel">' in rk and "badge rot\">${lg.offene_maengel}" not in rk
    assert ".reiter-zahl.offen { background: var(--rot); color: var(--weiss); }" in css
    mat = lies("app/material/static/material.js")
    assert mat.count('<div class="c-tabs reiter-linie mat-reiter" role="tablist"') == 2
    print("D8 bestanden.")


def test_d9_textknopf():
    css = lies(APP_CSS)
    assert ("@media (pointer: coarse) { .lnk { padding-top: 14px; padding-bottom: 14px; margin-top: -14px; margin-bottom: -14px; } }"
            in css)
    assert ".lnk { min-height" not in css and ".lnk { min-height: 44px; }" not in lies(MAT_CSS)
    print("D9 bestanden.")


def test_d10_namen():
    css = lies(APP_CSS)
    assert ".name-einheit, .mat-name { display: inline-block; max-width: 100%; overflow-wrap: anywhere; }" in css
    assert '["Angelegt von", `<span class="name-einheit">' in lies("app/static/js/wiki.js")
    rk = lies(RK_CSS)
    assert ".tn-kopfzeile .tn-name, .tn-kopfzeile .linkbtn { min-width: 0; overflow-wrap: break-word; }" in rk
    assert not re.search(r"tn-name[^{]*\{[^}]*anywhere", rk)
    print("D10 bestanden.")


def test_d11_tokens():
    t = tokens()
    for name in ("--abdunkeln-leicht", "--abdunkeln", "--abdunkeln-stark", "--fokus-hof", "--markierung", "--ok-hell"):
        assert name in t, name
    for datei in (APP_CSS, MAT_CSS, RK_CSS):
        css = ohne_kommentare(lies(datei))
        if datei == APP_CSS:
            css = css[css.index("\n}\n", css.index(":root {")):]
        # Schriftgrößen von .7 bis .93rem nur als Token
        assert not re.search(r"font-size: *\.(7|7\d|8\d?|9[0-3]?)rem", css), datei
        # keine freien Hex-Farben außer den DEMO-Streifen (bewusst nicht) und den Masken (#000 = deckend)
        hex_ = [h for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", css) if h.lower() not in ("#fff8a6", "#000")]
        assert not hex_, (datei, hex_)
        assert not re.search(r"border-radius: *[0-9]+px", css.replace("50%", "")), datei
    css = lies(APP_CSS)
    assert "p.coz-warning { --co-flaeche: var(--co-warning-fl); --co-kante: var(--co-warning-ka); }" in css
    assert "dialog::backdrop { background: var(--abdunkeln); }" in css
    print("D11 bestanden.")


def teile_oben(kopf):
    """Selektorliste an den Kommas der obersten Ebene teilen (nicht in :is()/:not())."""
    teile, tiefe, akt = [], 0, ""
    for c in kopf:
        tiefe += {"(": 1, ")": -1}.get(c, 0)
        if c == "," and not tiefe:
            teile.append(akt.strip()); akt = ""
        else:
            akt += c
    return teile + [akt.strip()]


def test_d12_hygiene():
    css = ohne_kommentare(lies(APP_CSS))
    # Tote spätere Überschreibungen: derselbe Selektor in derselben Umgebung setzt dieselbe Eigenschaft neu.
    stapel, puffer, gesehen, ueber = [], "", {}, []
    for c in css:
        if c == "{":
            stapel.append(puffer.strip()); puffer = ""; continue
        if c == "}":
            if stapel:
                kopf = stapel.pop()
                if puffer.strip() and not kopf.startswith("@"):
                    umg = tuple(k for k in stapel if k.startswith("@"))
                    props = dict((a.strip(), b.strip()) for a, b in (x.split(":", 1) for x in puffer.split(";") if ":" in x))
                    for sel in teile_oben(kopf):
                        for alt in gesehen.get((sel, umg), []):
                            ueber += [(sel, k) for k in set(alt) & set(props) if alt[k] != props[k]]
                        gesehen.setdefault((sel, umg), []).append(props)
            puffer = ""; continue
        puffer += c
    # Bleiben: gemeinsame Regel + Abweichung (Einfügemenü, Ausrichtung, h1 im Editor, Abschnittsblock im Editor).
    assert len(ueber) <= 5, ueber
    js = lies("app/static/js/map.js") + lies("app/static/js/wiki.js") + lies("app/templates/profil.html") + lies("app/templates/wiki.html")
    for alt in ('style="margin-top:14px"', 'style="margin-top:18px"', 'style="white-space:pre-wrap', 'style="margin-bottom:10px"',
                'style="margin-top:8px"', 'style="margin-top:10px"', 'style="justify-content:center'):
        assert alt not in js, alt
    assert ".abgesetzt { margin-top: 14px; }" in lies(APP_CSS)
    assert ".pruef :is(.help, .notice) { max-width: 100ch; }" in lies(RK_CSS)
    print("D12 bestanden.")


if __name__ == "__main__":
    test_a5_text_auf_hellen_flaechen()
    test_a6_a7_a14_einzeiler()
    test_a8_tippflaechen()
    test_a9_grosse_schrift()
    test_a15_touchregeln()
    test_d4_ein_menue()
    test_d5_abschnittskopf()
    test_d6_leerzustand()
    test_d7_statusmarken()
    test_d8_reiter()
    test_d9_textknopf()
    test_d10_namen()
    test_d11_tokens()
    test_d12_hygiene()
