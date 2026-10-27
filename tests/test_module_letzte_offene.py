"""Letzte offene Punkte (27.10.2026, Auftrag planung/material-phase4/auftrag_letzte_offene.md):
python tests/test_module_letzte_offene.py  oder  pytest tests/test_module_letzte_offene.py

  1. Datenschutz-Sonderfälle: Wo ein „i“ und ein sichtbarer Satz am selben Begriff stehen, bleibt der Datenschutz als
     eine Zeile sichtbar, der Rest steht im „i“ (Jahresbericht „Prüfer nennen“, Bestandsimport „Personen“, Prüfanleitung
     „wer sieht sie“).
  2. Strömipedia: über dem Seitenbaum „Neue Seite“ und „⋯“ (Papierkorb, Import) – die Zeile bricht nicht mehr um
     (Menü: test_wiki_import; Tippflächen gemessen, Bericht).
  3. „Angaben zur Seite“: ein gezeichnetes Blatt statt des kursiven „i“, das dem Info-„i“ glich.
  4. Fehlerart beim Ablegen von Dateien: test_wiki_fehlerart.
  6. Nachtrag: eine Abschnittsaktion rechts neben der Überschrift (.mat-kastenkopf) – Protokoll, Sammelprotokoll,
     Prüfformular und Herstellerdokumente.
  7. Nachtrag: Leitstelle – die Marken der Nutzerliste in der Box „Hilfe: Rechte je Modul“ statt im „i“ am Seitentitel
     (test_module_info_i, Marken je Liste).
Alle Inhalte sind Platzhalter."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


MAT = "app/material/static/material.js"


def test_datenschutz_eine_zeile():
    mat = lies(MAT)
    # Jahresbericht: sichtbar eine Zeile, die Einzelheiten im „i“ an „Prüfer nennen“.
    wahl = mat[mat.index('<div class="mat-bericht-wahl">'):mat.index('<div id="be-inhalt">')]
    assert 'Prüfer nennen${infoKnopf("Prüfer nennen", PRUEFER_NENNEN_INFO)}</label>' in wahl
    assert '<span class="help">Ohne Haken nennt keine Ausgabe einen Prüfer.</span>' in wahl
    assert "weder die Seite noch PDF oder CSV" not in mat
    assert ('const PRUEFER_NENNEN_INFO = "Mit Haken nennen die Seite, das PDF und die CSV die Prüfer mit Urkundennummer und '
            'wer ausgesondert hat.";') in mat
    # Bestandsimport: „Personen werden nicht übernommen.“ sichtbar, was danach zu tun ist, im „i“ an „Spalten“ – nur wenn
    # die Liste eine Personenspalte hat.
    assert 'const IMPORT_PERSONEN = "Personen werden nicht übernommen.";' in mat
    assert 'const IMPORT_PERSONEN_INFO = "Artikel ordnest du nach dem Import im Ordner über „Zuordnen“ einer Person zu.";' in mat
    assert ('${b.spalten.some((x) => x.gesperrt) ? `<span class="info-absatz">${esc(IMPORT_PERSONEN_INFO)}</span>` : ""}`)}'
            '</summary>') in mat
    assert '${b.spalten.some((x) => x.gesperrt) ? `<p class="help">${esc(IMPORT_PERSONEN)}</p>` : ""}</details>' in mat
    # Prüfanleitung: wer sie sieht, in einer Zeile; dass neue Konten keinen Zugang haben, im „i“ (Formular und Dialog).
    assert 'intern: "Prüfer ohne Zugang zur Strömipedia sehen nur, dass es eine Anleitung gibt.",' in mat
    assert "das sind alle neuen Konten" not in mat
    assert mat.count("${NEUE_KONTEN}") == 2
    # Jeder sichtbare Satz ist kurz genug für eine Zeile (höchstens 80 Zeichen).
    for satz in ("Ohne Haken nennt keine Ausgabe einen Prüfer.", "Personen werden nicht übernommen.",
                 "Prüfer ohne Zugang zur Strömipedia sehen nur, dass es eine Anleitung gibt."):
        assert len(satz) <= 80, satz
    print("Datenschutz eine Zeile bestanden.")


def test_baumknoepfe_einzeilig():
    html, css = lies("app/templates/wiki.html"), lies("app/static/css/app.css")
    zeile = html[html.index('<div class="btn-row" style="margin-bottom:10px">'):]
    zeile = zeile[:zeile.index("</div>")]
    # Zwei Knöpfe: die Hauptaktion rot, „⋯“ grau; am Finger je mindestens 44 px (bestehende Regel).
    assert re.findall(r'<button class="([^"]+)"', zeile) == ["btn small", "btn secondary small"]
    assert ".wiki-side .btn-row .btn.small, .wiki-menu-btn { min-height: 44px; min-width: 44px; padding: 9px 12px; }" in css
    print("Baumknöpfe einzeilig bestanden.")


def test_angaben_zur_seite_ohne_i():
    js, css = lies("app/static/js/wiki.js"), lies("app/static/css/app.css")
    assert ('<button type="button" class="rundknopf" id="pg-info" title="Angaben zur Seite" aria-label="Angaben zur Seite">'
            '${I.seite}</button>') in js
    assert re.search(r'seite: +ico\(\'<path d="M4 1\.5h5\.5l2\.5 2\.5v10\.5H4z"/>', js)
    assert 'aria-label="Angaben zur Seite">i</button>' not in js
    assert ".rundknopf svg {" in css and "stroke: currentColor;" in css[css.index(".rundknopf svg {"):]
    print("Angaben zur Seite ohne i bestanden.")


def test_abschnittsaktion_in_der_kopfzeile():
    mat = lies(MAT)
    # Prüfung: „Protokoll (PDF)“ neben „Protokoll“, die Kennung allein darunter.
    prot = mat[mat.index("function protokollHtml() {"):mat.index("function bearbeitenHtml() {")]
    assert ('<div class="mat-kastenkopf"><h2>Protokoll</h2>\n          <a class="btn secondary small" href="${esc(p.url)}" '
            'target="_blank" rel="noopener">Protokoll (PDF)</a></div>\n        <div class="mat-protokoll-kopf"><span '
            'class="mat-protokoll-id mat-hash">${esc(p.id)}</span></div>') in prot
    # Durchgang: „Sammelprotokoll (PDF)“ nicht mehr im Seitenkopf, sondern neben der Überschrift „Sammelprotokoll“.
    # Der Knopf heißt dort „Protokoll (PDF)“ – die Überschrift sagt „Sammelprotokoll“, und so passt beides am Telefon in eine Zeile.
    assert ('<div class="mat-kastenkopf"><h2>Sammelprotokoll</h2>\n          ${d.offen ? "" : `<a class="btn secondary small" '
            'href="${esc(d.protokoll.url)}" target="_blank" rel="noopener" title="Sammelprotokoll ${esc(d.protokoll.id)} öffnen">'
            'Protokoll (PDF)</a>`}</div>') in mat
    assert "Sammelprotokoll (PDF)</a>" not in mat
    # Produkt: Prüfformular und Herstellerdokumente – je eine Aktion neben der Überschrift.
    assert ('Ein aktives spezifisches Formular ersetzt das generische der Kategorie.")}</h2>\n          ${k ? \'<button class="btn '
            'secondary small" data-act="formular">Spezifisches Formular bearbeiten</button>\' : ""}</div>') in mat
    assert mat.count('data-act="formular">Spezifisches Formular bearbeiten</button>') == 1
    doks = mat[mat.index('<div class="mat-kastenkopf"><h2>Herstellerdokumente'):]
    doks = doks[:doks.index("</section>")]
    assert doks.index('data-act="dok-neu"') < doks.index("</div>") < doks.index("dokTabelle(p.dokumente, k)")
    # Das Muster in material.css (Linie unter Überschrift und Knopf) gilt für <button> und <a> mit .btn.
    mcss = lies("app/material/static/material.css")
    assert ".mat-kastenkopf:has(> .btn) { border-bottom: 1px solid var(--linie);" in mcss
    print("Abschnittsaktion in der Kopfzeile bestanden.")


if __name__ == "__main__":
    test_datenschutz_eine_zeile()
    test_baumknoepfe_einzeilig()
    test_angaben_zur_seite_ohne_i()
    test_abschnittsaktion_in_der_kopfzeile()
