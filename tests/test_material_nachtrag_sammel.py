"""Nachträge zum Sammelstand aus der Faktenprüfung des Strömipedia-Artikels (01.11.2026,
planung/material-phase4/auftrag_nachtrag_sammel.md):
python tests/test_material_nachtrag_sammel.py  oder  pytest tests/test_material_nachtrag_sammel.py

  1. Materialbaum (Ordnerleiste und Kategorien): Seit dem Seitenbaum der Strömipedia zeichnet app.css kein „▸/▾“ mehr –
     die Klappknöpfe tragen jetzt dasselbe gezeichnete Klappzeichen wie der Seitenbaum (sichtbar, mit Node.js gerendert).
     Die übrigen Folgen der Seitenbaum-Regeln sind für .mat-tree zurückgenommen bzw. ergänzt: Einzug mit Führungslinie
     schon ab der zweiten Ebene, Namen als Block (… am Finger), am Finger kein Überstand in den Innenrand, Klappknopf
     nicht über dem Namen, Zähler mittig.
  2. CHANGELOG „Suchzeile“: Fokus-Rückkehr nur nach Zurück, Esc und „✕“ – wie leisteZu im Code.
  4. README: Nacharbeit mit dem Knopf „Als CSV herunterladen“ (kein Menü „Mehr“ mehr).
Lage, Tippflächen und Tastatur im Browser sind gemessen (bericht_nachtrag_sammel.md). Keine Konten, keine Mails."""
import json
import os
import re
import shutil
import subprocess

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = ("'<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" focusable=\"false\">"
       "<path d=\"M6 3.5L10.5 8 6 12.5\"/></svg>'")


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


def test_klappzeichen_wie_im_seitenbaum():
    js = lies("app/material/static/material.js")
    # Dasselbe Zeichen wie wiki.js und public.js – Zeichen für Zeichen.
    for datei in ("app/static/js/wiki.js", "app/static/js/public.js", "app/material/static/material.js"):
        assert f"const KLAPPZEICHEN = {SVG};" in lies(datei), datei
    zeichnen = js[js.index("  const KLAPPZEICHEN"):js.index("  async function leisteLaden()")]
    # Mit Unterordnern: Zeichen im Knopf, Name und aria-expanded wie bisher; ohne: leerer, unsichtbarer Platzhalter.
    assert ('aria-label="${LEISTE_KATALOG ? "Unterkategorien" : "Unterordner"} von ${esc(o.name)}">${KLAPPZEICHEN}</button>`'
            in zeichnen)
    assert ': `<button class="tg" type="button" data-klapp="${o.id}" tabindex="-1" aria-hidden="true"></button>`;' in zeichnen
    # Das Schriftzeichen aus CSS gibt es nicht mehr – ohne SVG bliebe der Knopf leer.
    app_css = lies("app/static/css/app.css")
    assert '.tg::before { content: "▸"; }' not in app_css and '.tg::before { content: "▾"; }' not in app_css
    assert not re.search(r"\.mat-tree[^{}]*::?before", lies("app/material/static/material.css"))


def test_klappzeichen_sichtbar_gerendert():
    """leisteZeichnen aus material.js mit Node.js: Ordner mit Unterordnern bekommen ein SVG im Klappknopf (offen und zu),
    Blätter und „alle Kategorien“ einen leeren Platzhalter; die Stile zeigen das SVG (Größe, Strich in currentColor) und
    blenden es nirgends aus. Läuft mit Node.js, wenn es installiert ist (sonst übersprungen)."""
    node = shutil.which("node")
    css = lies("app/static/css/app.css") + lies("app/material/static/material.css")
    assert ".tree .tg svg {\n  width: 14px; height: 14px; display: block;" in css
    assert "fill: none; stroke: currentColor; stroke-width: 2;" in css
    assert ".tree li:not(.collapsed) > .row .tg svg { transform: rotate(90deg); }" in css
    for regel in re.findall(r"[^{}]*\.tg svg[^{}]*\{[^}]*\}", css):
        assert not re.search(r"display:\s*none|visibility:\s*hidden|opacity:\s*0[;\s}]|width:\s*0", regel), regel
    for regel in re.findall(r"[^{}]*\.mat-tree[^{}]*\.tg[^{}]*\{[^}]*\}", css):
        assert not re.search(r"display:\s*none|visibility:\s*hidden|font-size:\s*0", regel), regel
    if not node:
        print("Klappzeichen gerendert übersprungen (kein Node.js).")
        return
    skript = r"""
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const esc = new Function(`${fs.readFileSync(process.argv[2], "utf8").match(/const esc = .*;/)[0]} return esc;`)();
const teil = (a, b) => js.slice(js.indexOf(a), js.indexOf(b));
const baumKinder = new Function(teil("  function baumKinder(liste)", "  function zahlen(z)") + "; return baumKinder;")();
const ziel = { innerHTML: "" };
const ordner = [
  { id: 1, parent_id: null, name: "Platzhalter Gliederung", position: 0, zaehlung: {} },
  { id: 2, parent_id: 1, name: "Platzhalter Lager", position: 0, zaehlung: {} },
  { id: 3, parent_id: 2, name: "Platzhalter Regal <b>", position: 0, zaehlung: {} },
  { id: 4, parent_id: 1, name: "Platzhalter Fahrzeug", position: 1, zaehlung: {} }];
const lauf = (katalog, daten, klapp) => new Function("leisteDaten", "leisteAktiv", "LEISTE_KATALOG", "ANSICHT", "$", "leer",
  "baumKinder", "klappLesen", "esc", "schloss", "OHNE_FREIGABE",
  teil("  const KLAPPZEICHEN", "  async function leisteLaden()") + "; leisteZeichnen();")(
  daten, null, katalog, katalog ? "katalog" : "ordner", () => ziel, (t) => t, baumKinder, () => klapp, esc, () => "", "");
lauf(false, ordner, { 2: false });
const ordnerHtml = ziel.innerHTML;
lauf(true, ordner.map((o) => ({ ...o, produkte: 1 })), {});
console.log(JSON.stringify([ordnerHtml, ziel.innerHTML]));
"""
    aus = subprocess.run([node, "-e", skript, os.path.join(WURZEL, "app/material/static/material.js"),
                          os.path.join(WURZEL, "app/static/js/common.js")], capture_output=True, text=True, check=True).stdout
    ordner_html, katalog_html = json.loads(aus)
    svg = SVG.strip("'")
    knoepfe = re.findall(r'<button class="tg"[^>]*>(.*?)</button>', ordner_html)
    assert len(knoepfe) == 4, ordner_html
    # Gliederung (offen) und Lager (zugeklappt, gemerkt) mit Zeichen; Regal und Fahrzeug ohne Unterordner leer.
    assert knoepfe[0] == svg and knoepfe[1] == svg and knoepfe[2] == "" and knoepfe[3] == "", knoepfe
    assert 'aria-expanded="true" aria-label="Unterordner von Platzhalter Gliederung">' + svg in ordner_html
    assert 'aria-expanded="false" aria-label="Unterordner von Platzhalter Lager">' + svg in ordner_html
    assert '<li class="collapsed">' in ordner_html and "Platzhalter Regal &lt;b&gt;" in ordner_html
    assert ordner_html.startswith('<ul class="tree mat-tree">')
    # Kategorien: dasselbe Zeichen, „alle Kategorien“ als leerer Platzhalter.
    kat = re.findall(r'<button class="tg"[^>]*>(.*?)</button>', katalog_html)
    assert kat[0] == "" and kat[1] == svg and kat[2] == svg, kat
    assert 'aria-label="Unterkategorien von Platzhalter Gliederung">' + svg in katalog_html


def test_folgen_der_seitenbaum_regeln_auf_den_materialbaum():
    css = lies("app/material/static/material.css")
    # Einzug und Führungslinie schon ab der zweiten Ebene (die Liste ist selbst .tree), mit den Spalten des Seitenbaums.
    einzug = (".mat-tree ul { margin-left: calc(var(--baum-spalte) / 2 - 1px); padding-left: calc(var(--baum-einzug) - "
              "var(--baum-spalte) / 2);\n  border-left: 1px solid var(--linie); }")
    assert einzug in css and umgebung(css, einzug) == ""
    # Namen als Block wie vor dem Seitenbaum (sonst kein … am Finger, sondern abgeschnittener Text).
    block = ".mat-tree a { display: block; white-space: normal;"
    assert block in css and umgebung(css, block) == ""
    # Am Finger: kein Überstand in den Innenrand, Zähler mittig, Klappknopf nicht über dem Namen, Zeichen rechts im Knopf.
    for regel in (".mat-tree { margin-right: 0; }", ".mat-tree .row { align-items: center; }",
                  ".mat-tree a { padding-left: 6px; }",
                  ".mat-tree .tg { margin-left: -14px; margin-right: 0; padding: 0 3px 0 0; justify-content: flex-end; }"):
        assert regel in css, regel
        assert umgebung(css, regel) == "@media (pointer: coarse)", regel
    # Die Regeln stehen nach denen in app.css (gleiche Spezifität, material.css kommt später) – die Seite lädt beide.
    seite = lies("app/material/templates/material/seite.html")
    assert "url_for('material.static', filename='material.css')" in seite
    # Der Seitenbaum der Strömipedia bleibt unverändert.
    app_css = lies("app/static/css/app.css")
    for regel in (".tree { margin-right: -12px; }", ".tree .tg { width: 44px; height: 44px; margin: 0 -10px;",
                  ".tree .row { align-items: flex-start; }", ".tree > ul > li > .row > a { font-weight: 600;"):
        assert regel in app_css, regel


def test_changelog_fokus_und_readme_csv():
    log = lies("CHANGELOG-Material.md")
    abschnitt = log[log.index("### Nachtrag: auf alle Seiten ausgeweitet"):log.index("## Letzte offene Punkte")]
    assert "Zurück, Esc und Tippen daneben schließen\n  sie, der Fokus kehrt zu dem Knopf zurück" not in abschnitt
    assert ("Nach Zurück, Esc und „✕“ kehrt der Fokus zu dem Knopf zurück, der sie geöffnet hat, nach Tippen daneben\n"
            "  nicht") in abschnitt
    # Der Code dazu: Tippen daneben ruft leisteZu() ohne Fokus-Rückkehr, Esc und ✕ mit.
    js = lies("app/material/static/material.js")
    assert '&& !e.target.closest("[data-leiste-auf]")) leisteZu();' in js
    assert 'document.addEventListener("keydown", (e) => { if (e.key === "Escape") leisteZu(true); });' in js
    assert '$("#mat-side-zu").addEventListener("click", () => leisteZu(true));' in js
    assert 'S.klassenVerlauf(leiste, "open", () => leisteZu(true), alsSchublade);' in js
    readme = lies("README.md")
    assert "Mehr → Als CSV herunterladen" not in readme
    assert "Werte korrigiert man in der CSV (Knopf „Als CSV herunterladen“, Spalte „Nacharbeit-Nr.“ nicht ändern)" in readme
    # Der Knopf selbst: ein Eintrag im Menü-Baustein wird ein grauer Knopf.
    assert 'eintraege: [{ text: "Als CSV herunterladen", href: `/materialablage/ordner/${fid}/nacharbeit.csv`,' in js


if __name__ == "__main__":
    test_klappzeichen_wie_im_seitenbaum()
    test_klappzeichen_sichtbar_gerendert()
    test_folgen_der_seitenbaum_regeln_auf_den_materialbaum()
    test_changelog_fokus_und_readme_csv()
    print("OK")
