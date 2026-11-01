"""Seitenbaum der Strömipedia (Auftrag Seitenbaum, 28.10.2026, planung/material-phase4/auftrag_seitenbaum.md):
python tests/test_wiki_seitenbaum.py  oder  pytest tests/test_wiki_seitenbaum.py

  1. „Seiten aus ZIP importieren“ steht nur noch im Menü „⋯“ über dem Baum (Wiki-Verwaltung), nicht im „⋯“ jeder Seite.
  2. Klappknopf: gezeichneter Winkel (Inline-SVG, aria-hidden) statt „▸/▾“, Name und aria-expanded wie seit C12, ohne
     Unterseiten leer, unsichtbar und nicht erreichbar; der öffentliche Baum zeigt dasselbe Zeichen.
  3. CSS: feste Spalte und gleichmäßiger Einzug je Ebene mit Führungslinie, oberste Ebene fett ohne Einzug, Titel in
     eigener Spanne (… am Rechner, hängender Umbruch am Finger), „⋯“ am Rechner bei Hover und Tastaturfokus; unter Touch
     44 × 44 px Tippfläche über einer 24-px-Spalte, Schublade bis 360 px breit; Drehung abschaltbar (Bewegung reduzieren).
  4. Gerenderte Seite: Knopfzeile über dem Baum je Recht unverändert (Wiki-Verwaltung „⋯“, sonst „Papierkorb“).
Lage, Tippflächen und Tastatur im Browser sind gemessen (bericht_seitenbaum.md). Alle Konten und Inhalte sind
Platzhalter, es geht keine Mail hinaus."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def umgebung(css, stelle):
    """Kopf des innersten @media-Blocks, in dem `stelle` steht (oder "" auf oberster Ebene)."""
    i = css.index(stelle)
    tiefe = 0
    while i > 0:
        i -= 1
        if css[i] == "}":
            tiefe += 1
        elif css[i] == "{":
            if tiefe == 0:
                kopf = css[css.rfind("}", 0, i) + 1:i].strip()
                kopf = kopf[kopf.rfind("*/") + 2:].strip() if "*/" in kopf else kopf
                if kopf.startswith("@media"):
                    return kopf
            else:
                tiefe -= 1
    return ""


def test_import_nur_oben():
    js = lies("app/static/js/wiki.js")
    zeile = js[js.index("function treeRowMenu(anchor, page)"):js.index("function wireTreeDrag()")]
    eintraege = re.findall(r'data-a="(\w+)"', zeile[:zeile.index("S.menueSchwebend")])
    assert eintraege == ["child", "fav", "icon", "dup", "export", "del"], eintraege
    assert "import" not in zeile and "darfImportieren" not in zeile
    oben = js[js.index("function baumMenu(anchor)"):js.index("function treeRowMenu(anchor, page)")]
    assert re.findall(r'data-a="(\w+)"', oben[:oben.index("S.menueSchwebend")]) == ["trash", "import"]
    # Rechte unverändert über das vorhandene Flag (Wiki-Verwaltung); der Dialog bekommt kein Ziel mehr mit.
    assert "${darfImportieren() ? " in oben and "importDialog();" in oben
    assert "function importDialog() {" in js and "importDialog(page)" not in js and "importDialog(null)" not in js


def test_klappknopf_markup():
    js = lies("app/static/js/wiki.js")
    assert ("const KLAPPZEICHEN = '<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" focusable=\"false\">"
            "<path d=\"M6 3.5L10.5 8 6 12.5\"/></svg>';") in js
    zweig = js[js.index("function branch(pid, depth)"):js.index("function renderTree()")]
    assert '<button class="tg" type="button" ${tg}>${sub ? KLAPPZEICHEN : ""}</button>' in zweig
    # C12: Name mit Seite, aria-expanded; ohne Unterseiten versteckt und nicht per Tab erreichbar.
    assert '`aria-label="${esc(p.title)} ${collapsed ? "aufklappen" : "zuklappen"}" aria-expanded="${!collapsed}"`' in zweig
    assert ": 'aria-hidden=\"true\" tabindex=\"-1\"';" in zweig
    # Titel in eigener Spanne (Ellipse bzw. hängender Umbruch), Symbol davor, Zusätze darin; Text immer mit esc.
    assert ('<span class="baum-titel">${esc(p.title)}${p.is_public ? \' <span class="pub" title="öffentlich freigegeben">🌐</span>\' : ""}'
            '${p.favorite ? \' <span class="fav" title="auf der Merkliste">★</span>\' : ""}</span></a>') in zweig
    assert 'title="${esc(p.title)}"' in zweig
    # Aufklappen schreibt Zustand und Namen nach.
    baum = js[js.index("function renderTree()"):js.index("function baumMenu(anchor)")]
    assert 'b.setAttribute("aria-expanded", String(!zu));' in baum
    assert 'b.setAttribute("aria-label", `${seite.title} ${zu ? "aufklappen" : "zuklappen"}`);' in baum
    pub = lies("app/static/js/public.js")
    assert "const KLAPPZEICHEN = '<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" focusable=\"false\">" in pub
    assert '<span class="tg">${kids(r.id).length ? KLAPPZEICHEN : ""}</span>' in pub
    assert pub.count('<span class="baum-titel">') == 2


def test_css_regeln():
    css = lies("app/static/css/app.css")
    # Kein Schriftzeichen mehr als Klappzeichen.
    assert 'content: "▸"' not in css and 'content: "▾"' not in css
    grund = [
        ".tree { --baum-spalte: 20px; --baum-einzug: 20px; }",
        ".tree ul ul { margin-left: calc(var(--baum-spalte) / 2 - 1px); padding-left: calc(var(--baum-einzug) - var(--baum-spalte) / 2);\n"
        "  border-left: 1px solid var(--linie); }",
        ".tree > ul > li + li { margin-top: 6px; }",
        ".tree > ul > li > .row > a { font-weight: 600; color: var(--schwarz); }",
        ".tree .baum-titel { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
        ".tree a.active { background: var(--weiss); border-left: 3px solid var(--rot); font-weight: 600; }",
        "width: var(--baum-spalte); height: 28px;",
        "width: 14px; height: 14px; display: block; pointer-events: none; transition: transform .15s;",
        ".tree li:not(.collapsed) > .row .tg svg { transform: rotate(90deg); }",
        ".tree button.tg:hover { background: var(--linie); color: var(--anthrazit); }",
        ".tree li.leaf > .row .tg { visibility: hidden; }",
        ".tree .row:has(:focus-visible) :is(.row-add, .row-menu) { opacity: 1; }",
    ]
    for r in grund:
        assert r in css, r
        assert umgebung(css, r) == "", (r, umgebung(css, r))
    # „⋯“ am Rechner erst bei Hover (unverändert), ohne Maus immer.
    assert ".tree .row:hover .row-add, .tree .row:hover .row-menu," in css
    assert umgebung(css, ".tree .row-add, .tree .row-menu, .code-copy { opacity: 1; }") == "@media (hover: none)"
    finger = [
        ".tree { --baum-spalte: 24px; --baum-einzug: 18px; }",
        ".tree .row { align-items: flex-start; }",
        ".tree .tg { width: 44px; height: 44px; margin: 0 -10px; position: relative; z-index: 1; }",
        ".tree .row-menu { margin-right: -12px; }",
        ".tree a { padding-top: 12px; padding-bottom: 12px; padding-left: 8px; }",
        ".tree .baum-titel { white-space: normal; text-overflow: clip; overflow-wrap: break-word; hyphens: auto; }",
        ".tree .row-add, .tree .row-menu { width: 44px; height: 44px; margin-left: 0; }",
        ".tree .row { min-height: 44px; }",
    ]
    for r in finger:
        assert r in css, r
        assert umgebung(css, r) == "@media (pointer: coarse)", (r, umgebung(css, r))
    # Schublade bis 360 px (vorher 320), weiter unter 1024 px.
    schublade = ".wiki-side { position: fixed; left: 0; top: var(--topbar); bottom: 0; width: min(360px, 90vw);"
    assert schublade in css and umgebung(css, schublade) == "@media (max-width: 1023px)"
    # Bewegung reduzieren schaltet alle Übergänge ab – auch die Drehung des Klappzeichens.
    assert "@media (prefers-reduced-motion: reduce) {\n  * { transition: none !important; }\n}" in css


def test_knopfzeile_je_recht():
    with tempfile.TemporaryDirectory() as tmp:
        knopfzeile_pruefen(make_app(tmp))


def knopfzeile_pruefen(app):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
    html = c.get("/stroemipedia").get_data(as_text=True)
    assert 'id="btn-baum-mehr"' in html and 'title="Papierkorb, Seiten aus ZIP importieren">⋯</button>' in html
    assert '<ul class="tree" id="tree"></ul>' in html
    r = c.post("/api/admin/users", json={"email": "mitglied-baum@example.org", "name": "Mitglied Platzhalter",
                                         "password": "geheim123", "rechte": {"wiki": 1}})
    assert r.status_code in (200, 201), r.json
    m = app.test_client()
    assert m.post("/api/auth/login", json={"email": "mitglied-baum@example.org", "password": "geheim123"}).status_code == 200
    mh = m.get("/stroemipedia").get_data(as_text=True)
    assert 'id="btn-baum-mehr"' not in mh and 'id="btn-papierkorb" type="button">Papierkorb</button>' in mh
    assert "Seiten aus ZIP importieren" not in mh


if __name__ == "__main__":
    test_import_nur_oben()
    test_klappknopf_markup()
    test_css_regeln()
    test_knopfzeile_je_recht()
    print("Seitenbaum bestanden.")
