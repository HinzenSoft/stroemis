"""UI/UX vor dem Merge, Teil U2 „Materialablage“ (27.10.2026, Auftrag planung/material-phase4/auftrag_uiux_bau.md):
python tests/test_material_uiux_u2.py  oder  pytest tests/test_material_uiux_u2.py

  A10 Ultrawide: Ordnerleiste und Inhalt eine zentrierte Gruppe (2100 px), Inhalt beginnt neben der Leiste.
  B1  Ausgegraute Hauptknöpfe: aria-disabled statt disabled, Grund als Satz direkt über der Knopfzeile.
  B2  Abschlussleiste der Prüfung: Grund und „Nächste Prüfung“ im Dialog „Prüfung festschreiben“; gewählt = Rand + fett.
  B3  Ordnerleiste bricht Namen auch am Rechner um.
  B4  Katalogliste: Kategorie in der engen Tabelle unter dem Produkt.
  B5  Mangel melden: eine Quittung, Texte je Rolle.
  B6  Knöpfe: Herstellerdokumente, Prüfformular-Kopf, Artikelkopf des Prüfers, Berichtigen, Durchgang abbrechen.
  B7  „Aussonderung empfohlen“ im roten Banner.
  B8  Journal der Artikelseite: letzte fünf, „Alle n Einträge anzeigen“.
  B9  Prüfhinweis auf „Prüfungen“ nur für, wer handeln kann.
  B10 Seite „Echtheit prüfen“.
  B11 Befund- und Ergebniswahl als Radiogruppe, Sprunglink „Zum Abschluss“.
  B12 Fehlerzustand mit „Neu laden“.
  B13 Kleinigkeiten.
  B14 Klappknöpfe der Ordnerleiste mit Bezug und aria-expanded; Mangel-Dialog am gesperrten Artikel.
Messungen im Browser: planung/material-phase4/bericht_uiux_bau_u2.md. Alle Inhalte sind Platzhalter."""
import os
import re
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_smoke import make_app  # noqa: E402

MAT = "app/material/static/material.js"
CSS = "app/material/static/material.css"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i)]


def test_a10_ultrawide():
    css = lies(CSS)
    assert ".mat-shell.mit-leiste { max-width: 2100px; margin: 0 auto; }" in css
    assert ".mat-shell.mit-leiste > .page { margin-left: 0; }" in css
    assert "@media (min-width: 2101px) { .mat-shell.mit-leiste > .mat-side { border-left: 1px solid var(--linie); } }" in css
    print("A10 bestanden.")


def test_b1_ausgegraute_hauptknoepfe():
    js = lies(MAT)
    assert "const grundSatz = (id, grund) =>" in js and "function knopfGrund(knopf, grund, satz)" in js
    # Klick-Abfang im Einfangen, vor jeder Aktion; der Satz wird hervorgehoben und erneut vorgelesen.
    abfang = abschnitt(js, "document.addEventListener(\"click\", (e) => {\n    const k = e.target.closest && e.target.closest('.btn[aria-disabled=\"true\"]');", "}, true);")
    assert "e.stopImmediatePropagation();" in abfang and 'classList.add("betont")' in abfang
    # Die sieben Knöpfe: kein disabled mehr im Markup.
    for knopf in ('id="zp-ok"', 'id="ww-ok"', 'id="zu-ok"', 'id="nz-ok"', 'id="pr-ok"'):
        zeile = next(z for z in js.splitlines() if knopf in z and "<button" in z)
        assert "disabled>" not in zeile and ("knopfAus(" in zeile or 'aria-disabled="true"' in zeile), zeile
    assert 'data-act="schliessen"${knopfAus("dg-abschluss", abschlussGrund)}>Durchgang abschließen' in js
    assert '${grundSatz("dg-abschluss", abschlussGrund)}' in js and 'Noch ${plural(rest, "Artikel", "Artikel")} offen oder in Prüfung.' in js
    assert 'knopfGrund($("#pr-ok", box), ergebnis ? "" : "Wähle ein Ergebnis.");' in js
    assert 'if (!ergebnis) teile.push("Wähle ein Ergebnis.");' in js
    us = lies("app/material/static/unterschrift.js")
    assert 'data-us="ok" aria-disabled="true"' in us and "Unterschreibe zuerst im Feld." in us and 'data-us="ok" disabled' not in us
    pr = lies("app/material/templates/material/pruefen.html")
    assert 'id="pr-los" aria-disabled="true" aria-describedby="pr-grund"' in pr and "Wähle zuerst eine PDF-Datei." in pr
    assert "los.disabled = !datei" not in lies("app/material/static/pruefen.js")
    css = lies(CSS)
    assert '.btn[aria-disabled="true"], .btn[aria-disabled="true"]:hover { opacity: .55;' in css
    assert ".mat-knopfgrund.betont { font-weight: 700; color: var(--rot-auf-flaeche); }" in css
    print("B1 bestanden.")


def test_b2_abschlussleiste():
    js = lies(MAT)
    leiste = abschnitt(js, "function abschlussHtml() {", "\n    }")
    assert 'id="pr-grund"' not in leiste and 'id="pr-due"' not in leiste and "datumFeld(" not in leiste
    assert 'id="pr-grund"' not in js and '"#pr-due"' not in js and "grundPlatzhalter" not in js
    fs = abschnitt(js, "async function festschreibDialog(", "aktionen = {")
    assert 'id="fs-grund"' in fs and 'datumFeld("fs-due"' in fs
    assert "S.feldFehler(grundFeld, `Ohne Mangel braucht" in fs and "S.feldFehler(dueFeld, " in fs
    assert "const abschlussEntwurf = { grund: pr.grund || \"\", faellig: \"\" };" in js
    assert "instand&shy;setzen" in js
    css = lies(CSS)
    # Gewählt: nicht gefüllt (kein --ok/--rot als Fläche), Rand + fett.
    for alt in ('.mat-wahl3 button.abw[aria-pressed="true"] { background: var(--rot)', ".e-aussondern_empfohlen)[aria-pressed=\"true\"] { background: var(--mat-lebensdauer)"):
        assert alt not in css
    assert '.mat-wahl3 button.abw[aria-checked="true"] { color: var(--rot-auf-flaeche); box-shadow: inset 0 0 0 3px var(--rot-dunkel); }' in css
    assert re.search(r"\.mat-wahl3 button \{[^}]*font-weight: 400;", css) and re.search(r"\.mat-ergebnis button \{[^}]*font-weight: 400;", css)
    print("B2 bestanden.")


def test_b3_b4_leiste_und_katalog():
    css = lies(CSS)
    assert "\n.mat-tree a { white-space: normal; overflow-wrap: break-word;" in css
    js = lies(MAT)
    assert '<td data-l="Kategorie" class="mat-eng-weg">' in js and 'sortKopf("Kategorie", "kategorie", s, { klasse: "mat-eng-weg" })' in js
    assert '${x.category_name ? `<div class="mat-eng-zusatz small muted">${esc(x.category_name)}</div>` : ""}' in js
    print("B3/B4 bestanden.")


def test_b5_b14_mangel():
    js = lies(MAT)
    dlg = abschnitt(js, "function mangelDialog(", "function mangelBanner(")
    assert "if (danach) await danach(r, q);\n          else toast(q);" in dlg
    assert 'const knopfText = opt.gesperrt ? "Melden" : "Melden und sperren";' in dlg
    assert "Der Artikel ist schon gesperrt." in dlg and 'opt.verwaltet ? "Leg ihn sofort beiseite (aus Fahrzeug oder Lager)." : BEISEITE' in dlg
    assert "function mangelQuittung(r, verwaltet)" in js and "Leg ihn beiseite, bis ein Prüfer ihn ansieht." in js
    assert '${verwaltet ? "beiseitelegen" : "beiseitelegen und beim Materialwart abgeben"}' in js
    assert '{ verwaltet: Boolean(darf.verwalten), gesperrt: a.lock_state !== "frei" }' in js
    assert "{ gesperrt: Boolean(k.gesperrt || k.mangel) }" in js
    # B14 Ordnerleiste: Klappknöpfe mit Bezug und aria-expanded, Blätter ohne Namen.
    assert 'aria-expanded="${auf}" aria-label="${LEISTE_KATALOG ? "Unterkategorien" : "Unterordner"} von ${esc(o.name)}"' in js
    assert 'tabindex="-1" aria-hidden="true"></button>' in js and 'b.setAttribute("aria-expanded", String(auf));' in js
    assert '"zuklappen" : "aufklappen"' not in js
    print("B5/B14 bestanden.")


def test_b6_knoepfe():
    js = lies(MAT)
    dok = abschnitt(js, "function dokKnoepfe(d) {", "\n  }")
    assert 'data-act="dok-version"' in dok and 'text: "Umbenennen"' in dok and 'text: "Zurückziehen"' in dok and "Mehr zu ${esc(d.title)}" in dok
    form = abschnitt(js, "function formularKnoepfe() {", "\n    }")
    assert form.count("S.menue(") == 1 and 'text: "Löschen"' in form and 'text: "Deaktivieren"' in form
    assert 'const klasse = bearbeitbar ? "btn secondary small" : "btn small";' in form
    # Prüfer: „Sperren“ und „Mangel melden“ im Menü „Mehr“, sonst Knöpfe.
    assert 'pruefKnopf && sperrKnopf ? "sperren" : "", pruefKnopf && darfMelden && !schonGemeldet ? "mangel" : ""' in js
    assert "${sperrKnopf && !pruefKnopf ?" in js and "${darfMelden && !pruefKnopf ?" in js
    # Berichtigen: grauer Knopf (einzige Aktion), ausgegraut mit Satz statt title.
    assert 'disabled title="${esc(pr.berichtigbar.grund)}">Berichtigen' not in js and 'grundSatz("pr-ber-grund", berGrund)' in js
    print("B6 bestanden.")


def test_b7_b8_b9_artikel_und_pruefungen():
    js = lies(MAT)
    assert 'class="notice mat-empfehlung"><strong>Aussonderung empfohlen</strong> – ' not in js
    assert 'const empfZeile = empf ? `<p class="mat-banner-zeile">Empfohlen von ' in js
    assert '<h1><span class="mat-inv">${esc(a.inventory_no)}</span> ${statusMarke(a.status, true)}</h1>' in js
    assert "const JOURNAL_KURZ = 5;" in js and "journalHtml(a.journal, true, JOURNAL_KURZ)" in js
    assert 'aria-expanded="false" aria-controls="mat-journal">Alle ${eintraege.length} Einträge anzeigen</button>' in js
    seite = abschnitt(js, "const prueferHinweisSeite = () =>", ";\n")
    assert "DARF.qualifiziert || DARF.pruefer_haekchen" in seite and "DARF.verwalten ?" in seite and ': "")' in seite
    assert '${!DARF.pruefen ? `<p class="notice">${pruefHinweis()}</p>` : ""}' not in js
    print("B7/B8/B9 bestanden.")


def test_b10_echtheit_pruefen():
    pr = lies("app/material/templates/material/pruefen.html")
    assert "{% block title %}Echtheit prüfen – {{ modul.name.material }} – strömis.de{% endblock %}" in pr
    assert "<h1>Echtheit prüfen</h1>" in pr and "<summary>Wie funktioniert das?</summary>" in pr and "<summary>Selbst nachrechnen</summary>" in pr
    assert pr.index('id="pr-form"') < pr.index("Wie funktioniert das?") < pr.index("head -c N")
    js = lies(MAT)
    assert "Prüfseite" not in re.sub(r"/\*.*?\*/|//[^\n]*", "", js, flags=re.S)
    assert '>Echtheit prüfen</a>' in js
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        r = app.test_client().get("/materialablage/pruefen")
        html = r.get_data(as_text=True)
        assert r.status_code == 200 and "<title>Echtheit prüfen – Materialablage – strömis.de</title>" in html, html[:300]
    print("B10 bestanden.")


def test_b11_radiogruppe():
    js = lies(MAT)
    assert 'const radioAttrs = (an, stopp) => ` role="radio" aria-checked="${an}" tabindex="${an || stopp ? 0 : -1}"`;' in js
    assert js.count('class="mat-wahl3" role="radiogroup"') == 2 and 'class="mat-wahl3" role="group"' not in js
    assert '<div class="mat-ergebnis" role="radiogroup" aria-label="Ergebnis"' in js
    tasten = abschnitt(js, "inhalt.addEventListener(\"keydown\", (e) => {\n    const k = e.target.closest && e.target.closest('.mat-wahl3", "\n  });")
    for t in ("ArrowRight", "ArrowLeft", "Home", "End", "neu.click()"):
        assert t in tasten
    assert '<a class="mat-sprung" href="#pr-abschluss" data-act="zum-abschluss">Zum Abschluss</a>' in js
    assert ".mat-sprung:not(:focus) { position: absolute;" in lies(CSS)
    print("B11 bestanden.")


def test_b12_fehlerzustand():
    js = lies(MAT)
    assert "const keinServer = (e) => !e || !e.status || e.status >= 500;" in js
    kasten = abschnitt(js, "function fehlerKasten(e) {", "\n  }")
    assert 'data-neu-laden>Neu laden</button>' in kasten and "location.reload()" in kasten and 'setAttribute("role", "alert")' in kasten
    assert "if (keinServer(e)) { if (el) el.innerHTML = \"\"; fehlerKasten(e); return; }" in js
    print("B12 bestanden.")


def test_b13_kleinigkeiten():
    js = lies(MAT)
    assert ">Anlegen und nächsten Artikel</button>" in js
    assert 'seitenTitel(`Prüfformular ${f.ziel.art === "kategorie"' in js
    assert '<span class="mat-ganz">(Urkundennummer ${esc(pr.urkunde)})</span>' in js
    assert "Ihre Befunde" not in js and "Die Seiten der Anhänge zählen nicht" in lies("app/material/templates/material/pdf/pruefprotokoll.html")
    assert 'pr.art === "aussonderung" ? "" : ergebnisMarke(pr.ergebnis)' in js
    assert '>Protokoll (PDF)</a></li>' in js and '>Bericht (PDF)</a>' in js
    assert js.count('<span class="mat-nowrap">SHA-256</span>') == 3
    assert ".mat-erinnerungen { margin: 24px 0 20px;" in lies(CSS)
    assert "Den Zugang zur Strömipedia vergibt die Plattform-Verwaltung in der Leitstelle." in js
    assert "const letztesGlied = (pfad) =>" in js and '${esc(letztesGlied(a.pfad))}</td>' in js
    assert '<span class="mat-knoten-zahlen">' in js and ".mat-knoten-zahlen { flex: none; white-space: nowrap; }" in lies(CSS)
    assert "DARF.verwalten && !d.alle && !d.bearbeiten ?" in js
    assert "Erst ein Probelauf (speichert nichts)" in js
    assert "Prüfer in diesem Prüfdurchgang" in js and "Den Prüfdurchgang „${d.titel}“ abschließen?" in js
    ex = lies("app/material/services/export.py")
    assert "f\"Protokolle_{titel}_{r['protocol_id']}_{zeitstempel()}.zip\"" in ex
    print("B13 bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
    print("Alle U2-Prüfungen bestanden.")
