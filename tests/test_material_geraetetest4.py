"""Gerätetest vom 01.11.2026, Teil 4 „Materialablage“ (Auftrag planung/geraetetest/auftrag_geraetetest.md):
python tests/test_material_geraetetest4.py  oder  pytest tests/test_material_geraetetest4.py

  W3/M3 Prüfdurchgang: Suche (Nummer/Name) und „QR-Code scannen“ über der Liste, Vorgabe „offen“, eine Zählweise.
  FT4   Ausnehmen und Einbeziehen melden sich mit einem Toast.
  M1    Abschlussleiste der Prüfung beim Scrollen eingeklappt, am Ende des Formulars voll.
  FT10  Tipp auf das ausgegraute „Festschreiben“: Satz hervorgehoben und Sprung zum fehlenden Schritt.
  FT9   Filter der Prüfungen mit aria-pressed, Links der Übersicht springen zur Liste.
  B13   Bestandsbaum am Telefon: nur „überfällig“, keine Marken unter dem Namen.
  T2    Ein Platzhalter der Nummernsuche in Zeile und Navigation.
Das Verhalten im Browser (Messungen, Fotos) steht in planung/geraetetest/bericht_teil4.md. Die Prüfungen hier lesen nur
Skript, Stil und Vorlage – Inhalte gibt es keine."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAT = "app/material/static/material.js"
CSS = "app/material/static/material.css"
SEITE = "app/material/templates/material/seite.html"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i)]


def test_w3_durchgang_suche_und_vorgabe():
    js = lies(MAT)
    dg = abschnitt(js, "  async function durchgangAnsicht() {", "  /* --- Produktmeldungen")
    # Vorgabe „offen“ beim ersten Laden, solange es Offenes gibt; danach bleibt die Wahl.
    assert "let filter = null;" in dg
    assert 'if (filter === null) filter = d.offen && d.zaehlung.offen ? "offen" : "";' in dg
    # Suchfeld und Trefferzeile stehen fest, nur die Liste wird neu gezeichnet (Fokus bleibt im Feld).
    assert '<input type="search" id="dg-suche"' in dg and 'aria-describedby="dg-treffer"' in dg
    assert '<p class="small mat-dg-treffer" id="dg-treffer" aria-live="polite"></p>' in dg
    assert 'feld.addEventListener("input", () => { suche = feld.value; listeZeichnen(); });' in dg
    assert "function listeZeichnen()" in dg and '<div id="dg-liste"></div>' in dg
    # Jedes Wort muss vorkommen; Nummern ohne Bindestriche und Leerzeichen.
    assert "woerter.every((w) => text.includes(w) || dicht(text).includes(dicht(w)))" in dg
    for feld in ("a.inventory_no", "a.serial_no", "a.article_no", "a.manufacturer", "a.model", "a.description"):
        assert feld in abschnitt(dg, "function trifft(a, woerter)", "return woerter.every")
    # QR-Code: Foto mit capture, nur mit BarcodeDetector und Finger; Etikett über die eigene Adresse /m/<token>.
    assert 'const SCAN = "BarcodeDetector" in window && window.matchMedia("(pointer: coarse)").matches;' in dg
    assert '<input type="file" accept="image/*" capture="environment" id="dg-qr" class="mat-datei">' in dg
    assert "await new window.BarcodeDetector().detect(await createImageBitmap(datei))" in dg
    assert 'await fetch(`/m/${token}`, { method: "HEAD", credentials: "same-origin" })' in dg
    assert r"/^\/materialablage\/artikel\/(\d+)$/" in dg
    # Kein Kamerabild in der Seite – die Kamerafreigabe der App bleibt aus.
    assert "getUserMedia" not in js
    assert 'camera=()' in lies("app/__init__.py")
    # Filter als Umschalter mit aria-pressed und Zahl auch an „alle“.
    assert 'class="c-tabs mat-filter mat-dg-filter" role="group" aria-label="Stand"' in dg
    assert 'aria-pressed="${f === filter}">${esc(t)} (${z[f || "gesamt"]})</button>' in dg
    assert 'b.setAttribute("aria-pressed", String(an))' in dg
    print("W3 Durchgang bestanden.")


def test_m3_eine_zaehlweise():
    js = lies(MAT)
    f = abschnitt(js, "  function fortschritt(z, lang) {", "  /* Artikelliste als Tabelle")
    assert "`${z.erledigt} erledigt + ${z.ausgenommen} ausgenommen = ${fertig} von ${z.gesamt} fertig`" in f
    assert 'const restSatz = (z, und) => [z.offen ? `${z.offen} offen` : "", z.in_pruefung ? `${z.in_pruefung} in Prüfung` : ""]' in f
    # Kopf lang, Listen kurz; der Grund am ausgegrauten „Durchgang abschließen“ mit denselben Wörtern.
    assert "<p>${fortschritt(z, true)}</p>" in js and "${fortschritt(r.zaehlung)}" in js
    assert 'const rest = restSatz(z, " und ");' in js and "`Noch ${rest}.`" in js
    assert "${fertig}/${z.gesamt}" not in js and "offen oder in Prüfung." not in js
    print("M3 eine Zählweise bestanden.")


def test_ft4_ausnehmen_einbeziehen_melden_sich():
    js = lies(MAT)
    assert "dlg.close(); toast(`${b.dataset.nr} ausgenommen`); await neu();" in js
    assert "toast(`${b.dataset.nr} wieder einbezogen`); await neu();" in js
    assert 'data-act="einbeziehen" data-id="${a.id}" data-nr="${esc(a.inventory_no)}">Einbeziehen</button>' in js
    # Der Toast meldet Erfolg als role="status" (common.js; seit Teil 1 setzt toast() die Rolle nur bei einem Wechsel).
    common = lies("app/static/js/common.js")
    assert 'const rolle = isError ? "alert" : "status";' in common and 'el.setAttribute("role", rolle);' in common
    print("FT4 bestanden.")


def test_m1_leiste_eingeklappt():
    js = lies(MAT)
    css = lies(CSS)
    html = abschnitt(js, "    function abschlussHtml() {", "    function abschlussAktualisieren() {")
    assert '<button type="button" class="btn secondary small mat-abschluss-auf" data-act="zum-abschluss">Zum Abschluss</button>' in html
    assert '<div class="mat-abschluss-ende"></div>' in html and '<span class="mat-abschluss-stand" id="pr-stand-kurz"></span>' in html
    # Eingeklappt nur, solange die Leiste klebt (Marke am Ende nicht im Bild) und kein Fokus in Ergebnis/Festschreiben.
    assert "const kompakt = !amEnde && !fokusDrin;" in js
    assert "amEnde = eintraege[eintraege.length - 1].isIntersecting;" in js
    assert 'if (endeBeobachter) endeBeobachter.observe($(".mat-abschluss-ende", inhalt));' in js
    assert 'box.style.setProperty("--mat-leiste-weg", `${weg}px`);' in js
    assert 'document.documentElement.style.setProperty("--mat-leiste-h", `${box.offsetHeight - weg}px`);' in js
    # Klebt tiefer statt sich umzubauen; mit offener Tastatur (.tippt) gilt das nicht.
    assert ".mat-pruefung:not(.tippt) .mat-abschluss.kompakt { bottom: calc(-1 * var(--mat-leiste-weg, 0px)); }" in css
    assert ".mat-abschluss-stand, .mat-abschluss-auf { display: none; }" in css
    # „Zum Abschluss“ (Sprunglink und Knopf) rollt ans Ende und setzt den Fokus aufs Ergebnis.
    zum = abschnitt(js, '      "zum-abschluss": () => {', "      },")
    assert 'ende.scrollIntoView({ block: "end"' in zum and "r.focus({ preventScroll: true })" in zum
    # Der Sprunglink für die Tastatur bleibt (b115e2f).
    assert '<a class="mat-sprung" href="#pr-abschluss" data-act="zum-abschluss">Zum Abschluss</a>' in js
    print("M1 bestanden.")


def test_m2_radiogruppen():
    """M2 war auf dem Basisstand schon gebaut (UI/UX B11): Radiogruppe je Prüfpunkt mit dem Prüftext im Namen,
    role="radio" mit aria-checked – aria-pressed gehört nicht an role="radio"."""
    js = lies(MAT)
    assert 'role="radiogroup" aria-label="Befund zu ${esc(x.text)}"' in js
    assert 'const radioAttrs = (an, stopp) => ` role="radio" aria-checked="${an}"' in js
    assert '<div class="mat-ergebnis" role="radiogroup" aria-label="Ergebnis" aria-describedby="pr-hinweis">' in js
    assert not re.search(r'role="radio"[^>]*aria-pressed', js)
    print("M2 bestanden.")


def test_ft10_sprung_zum_fehlenden_schritt():
    js = lies(MAT)
    css = lies(CSS)
    abfang = abschnitt(js, "document.addEventListener(\"click\", (e) => {\n    const k = e.target.closest && e.target.closest('.btn[aria-disabled=\"true\"]');", "}, true);")
    assert 'const schritt = k.dataset.sprung && (k.closest("dialog, .mat-abschluss") || document).querySelector(k.dataset.sprung);' in abfang
    assert 'schritt.focus({ preventScroll: true });' in abfang and 'classList.add("betont")' in abfang
    # Leiste: zum Ergebnis; Dialog: zum ersten nicht abgehakten gemeldeten Mangel.
    assert 'data-sprung=".mat-ergebnis button:not(:disabled)">Festschreiben</button>' in js
    assert 'knopf.dataset.sprung = "input[data-mangel]:not(:checked)";' in js
    assert '#fs-maengel-hilfe.betont { color: var(--rot-auf-flaeche); font-weight: 700; }' in css
    # Fehlt ein Befund, Foto oder eine Bemerkung: zum Prüfpunkt rollen.
    assert "const zuPunkt = (x, feld) =>" in js and "zuPunkt(h.offen[0]); return;" in js and "zuPunkt(h.ohneFoto[0]); return;" in js
    print("FT10 bestanden.")


def test_ft9_filter_und_sprung():
    js = lies(MAT)
    pr = abschnitt(js, "  async function pruefungen() {", "  // Wie zeigen(), aber nur für einen Teil der Seite.")
    assert '<div class="c-tabs mat-filter" role="group" aria-label="Status">' in pr and 'aria-pressed="${f === filter}"' in pr
    assert '<section class="section" id="zu-pruefen"><h2 id="pr-zu-titel" tabindex="-1">' in pr
    assert 'if (location.hash === "#zu-pruefen") {' in pr and 'titel.scrollIntoView({ block: "start" });' in pr
    # Die Links der Übersicht (Kacheln, Fälligkeiten je Ordner, „… und n weitere“) tragen die Marke.
    assert 'href="/materialablage/pruefungen?status=${s}#zu-pruefen">' in js
    assert 'href="/materialablage/pruefungen?ordner=${o.id}&status=${s}#zu-pruefen"' in js
    assert 'href="/materialablage/pruefungen?status=gesperrt#zu-pruefen">' in js
    print("FT9 bestanden.")


def test_b13_bestandsbaum_am_telefon():
    css = lies(CSS)
    block = abschnitt(css, "@container mat-seite (max-width: 600px) {\n  .mat-knoten { display: flex;", "\n}\n")
    assert ".mat-baum .mat-knoten-zahlen > .mat-zahl:not(.s-ueberfaellig), .mat-baum .mat-art { display: none; }" in block
    assert ".mat-baum li:has(> .mat-knoten .mat-demo) li .mat-demo { display: none; }" in block
    js = lies(MAT)
    legende = abschnitt(js, "const ZAEHLER_LEGENDE", "const BESTAND_INFO")
    assert "Am Telefon steht im Baum nur" in legende and "alle Zahlen zeigt der Ordner selbst" in legende
    # Jede Zahl trägt ihre Bedeutung als title (schon vorher).
    assert '<span class="mat-zahl s-ueberfaellig" title="überfällig">' in js
    print("B13 bestanden.")


def test_t2_ein_platzhalter():
    seite = lies(SEITE)
    js = lies(MAT)
    assert 'placeholder="Inventar-, Serien-, Herstellernr."' in seite
    assert 'aria-label="Artikel suchen: Inventar-, Serien- oder Herstellernummer"' in seite
    assert 'placeholder="Nummer suchen"' not in seite
    # Kein zweiter Wortlaut im Skript, der beim Umhängen gesetzt würde.
    assert "Artikel: Inv.-, Serien-, Herst.-Nr." not in js and "sucheFeld.placeholder" not in js
    print("T2 bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
    print("Alle Prüfungen zum Gerätetest Teil 4 bestanden.")
