"""Suchzeile wie im Katalog auf Übersicht und Prüfungen (Wunsch vom 28.10.2026):  python tests/test_material_suchzeile.py

„Bei der Übersicht und den Prüfungen soll der Suchbalken und das linke Burgermenü sich genauso verhalten wie im Katalog.
Nur entsprechend dort als Artikelsuche.“ Solange die Leiste eine Schublade ist, hängt material.js (leisteKnopfSetzen)
„☰ Ordner“ und das Formular der Nummernsuche aus der Modulnavigation in die klebende Suchzeile #mat-suchzeile – dasselbe
Formular, kein zweites; die Lupe entfällt dort. Breiter (Leiste daneben, Doppelbildschirm) bleibt alles wie bisher.
Katalog und alle übrigen Seiten sind unverändert. Die Bedienung (Kleben, Schublade, Zurück, Vorschläge, Enter) ist im
Browser geprüft; hier stehen Markup und die Stellen in Skript und Stil fest. Alle Namen hier sind erfunden."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import gliederung, katalog_grund, neuer_artikel, pruef_formulare, starten, umgebung  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


JS = _lesen("app/material/static/material.js")
CSS = _lesen("app/material/static/material.css")
ZEILE = '<div class="mat-suchzeile mat-suchzeile-oben" id="mat-suchzeile" hidden></div>'


def _seiten(k, ids, gid, artikel, pruefung):
    """(Pfad, mit Suchzeile oben?, mit Nummernsuche in der Navigation?) – Katalogseiten ohne Nummernsuche (26.10.2026)."""
    return [("/materialablage", True, True), ("/materialablage/pruefungen", True, True),
            ("/materialablage/pruefungen?status=ueberfaellig", True, True),
            ("/materialablage/bestand", False, True), (f"/materialablage/ordner/{gid}", False, True),
            (f"/materialablage/artikel/{artikel}", False, True), ("/materialablage/suche?q=QQ-NICHTS", False, True),
            ("/materialablage/durchgaenge", False, True), ("/materialablage/bestand/antraege", False, True),
            (f"/materialablage/pruefung/{pruefung}", False, True),
            ("/materialablage/katalog", False, False), (f"/materialablage/katalog/produkt/{ids['gurt']}", False, False),
            ("/materialablage/katalog/meldungen", False, False)]


def test_markup_je_ansicht():
    """Übersicht und Prüfungen liefern die leere, verborgene Zeile zwischen Modulnavigation und Inhalt aus; das Formular
    steht genau einmal im Dokument – in der Navigation, mit Lupe, Reitern und „☰“ wie bisher (material.js hängt um).
    Alle übrigen Seiten haben keine Zeile, der Katalog weiterhin weder Nummernsuche noch Lupe."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["wart"])
        a = neuer_artikel(k["wart"], ids["hms"], gid, serial_no="MUSTER-0001")
        r = starten(k["pruefer"], a["id"])
        assert r.status_code in (200, 201), r.get_json()
        pruefung = r.json["pruefung"]["id"]
        for konto in ("adm", "wart", "pruefer"):
            for pfad, oben, mit_suche in _seiten(k, ids, gid, a["id"], pruefung):
                r = k[konto].get(pfad)
                if r.status_code != 200:            # z. B. die offene Prüfung eines anderen: dort zählt nur das Gerüst
                    assert pfad.startswith("/materialablage/pruefung/"), (konto, pfad, r.status_code)
                    continue
                html = r.get_data(as_text=True)
                assert (ZEILE in html) is oben, (konto, pfad)
                assert html.count('id="mat-suchzeile"') == (1 if oben else 0), (konto, pfad)
                assert html.count('<form class="mat-suche"') == (1 if mit_suche else 0), (konto, pfad)
                mnav = re.search(r'<nav class="mat-nav" aria-label="Materialablage">(.*?)</nav>', html, re.S)
                assert mnav, (konto, pfad)
                mnav = mnav.group(1)
                assert ('id="mat-lupe"' in mnav) is mit_suche and ('name="q"' in mnav) is mit_suche, (konto, pfad)
                assert 'id="mat-side-auf"' in mnav and mnav.count('data-nav="') == 4, (konto, pfad)
                if oben:
                    # Zwischen Navigation und Inhalt – oben im Inhalt, unter den Reitern.
                    assert html.index("</nav>") < html.index(ZEILE) < html.index('<div id="mat-inhalt">'), (konto, pfad)
                    assert 'placeholder="Nummer suchen"' in mnav, (konto, pfad)    # breit unverändert
    print("Markup je Ansicht bestanden.")


def test_skript_haengt_um():
    """material.js: derselbe Knopf und dasselbe Formular wandern (umhaengen), nur als Schublade; die Zeile ist nur dann
    sichtbar; Platzhalter, Name und Titel als Artikelsuche und zurück; die Lupe bleibt aus, solange das Feld in der Zeile
    steht; Esc klappt dort nichts ein; Übersicht und Prüfungen rufen das gleich beim Start, alle beim Umschalten."""
    assert 'const zeile = !schmal ? null : ANSICHT === "katalog" ? $(".mat-suchzeile", inhalt) : sucheZeileOben;' in JS
    assert 'const sucheZeileOben = $("#mat-suchzeile");' in JS
    assert "if (leiste) umhaengen(leisteAuf, zeile || matNav, true);" in JS
    assert "umhaengen(sucheForm, zeile || matNav, false);" in JS and "sucheZeileOben.hidden = !zeile;" in JS
    # Kein zweites Formular, kein zweites Feld: Das Skript baut keine Nummernsuche nach.
    assert 'class="mat-suche"' not in JS and 'name="q"' not in JS
    assert 'const ARTIKEL_SUCHE = "Artikel suchen: Inventar-, Serien- oder Herstellernummer";' in JS
    assert '"Artikel: Inv.-, Serien-, Herst.-Nr." : "Artikel suchen: Inventar-, Serien-, Herstellernr."' in JS
    assert 'sucheFeld.placeholder = zeile ? artikelPlatzhalter() : NAV_SUCHE.platzhalter;' in JS
    assert 'SUCHE_SCHMAL.addEventListener("change", sucheBeschriften);' in JS
    assert "if (lupe && !sucheInZeile()) lupe.hidden = false;" in JS
    assert "if (lupe) lupe.hidden = false;" not in JS
    assert '!matNav.classList.contains("eng") || !lupe || sucheInZeile()) return;' in JS
    assert "if (sucheZeileOben) leisteKnopfSetzen();" in JS
    assert "const umschalten = () => { leisteZu(); leisteInert(); leisteKnopfSetzen(); };" in JS
    # Der Fokus geht beim Umhängen nicht verloren (Drehen mit offener Tastatur).
    assert "const fokus = el.contains(document.activeElement) ? document.activeElement : null;" in JS
    # Der Fokus kehrt nach Wischen/Kategorie in die klebende Zeile zurück – wie im Katalog.
    assert "leisteZu(knopfInSuchzeile())" in JS
    print("Skript bestanden.")


def test_stil():
    """material.css: Zeile als Flex-Reihe (verborgen ohne Inhalt), das Formular füllt sie, „Suchen“ nur in der
    Navigation sichtbar; Bildlauf-Abstand nur bei sichtbarer Zeile; 44 px für „☰“ nur unter Touch."""
    for regel in (".mat-suchzeile-oben { display: flex; align-items: stretch; margin: -8px 0 10px; }",
                  ".mat-suchzeile-oben[hidden] { display: none; }",
                  ".mat-suchzeile > .mat-suche { flex: 1 1 auto; align-self: flex-start; max-width: none; min-width: 0; margin: 0 0 10px; }",
                  '.mat-suchzeile > .mat-suche > button[type="submit"] { display: none; }',
                  "html:has(.mat-suchzeile:not([hidden])) { scroll-padding-top: calc(var(--topbar) + 74px); }",
                  "  html:has(.mat-suchzeile:not([hidden])) { scroll-padding-top: 68px; }"):
        assert regel in CSS, regel
    assert "html:has(.mat-suchzeile) {" not in CSS
    # Die Zeile klebt wie im Katalog (dieselbe Klasse), quer am oberen Rand.
    assert ".mat-suchzeile { position: sticky; top: var(--topbar); z-index: 30;" in CSS
    assert "  .mat-suchzeile { top: 0; padding: 4px 0; }" in CSS
    touch = CSS[CSS.index("  .mat-nav .btn, .mat-nav .mat-suche input, .mat-nav.eng .mat-side-auf"):]
    assert touch.split("\n")[1].startswith("  .mat-suchzeile > .mat-side-auf { min-height: 44px; }")
    print("Stil bestanden.")


def test_katalog_unveraendert():
    """Die Katalogzeile entsteht weiter im Inhalt (kat-q), ohne Nummernsuche."""
    assert '<div class="mat-suchzeile"><input type="search" id="kat-q" placeholder="${katPlatzhalter()}"' in JS
    assert JS.index('<div id="kat-liste"></div>`;') < JS.index("leisteKnopfSetzen();             //")
    seite = _lesen("app/material/templates/material/seite.html")
    # Nur mit Modulzugang (innerhalb von „if not nur_psa“, wie die Navigation).
    assert '{% if ansicht in ("dashboard", "pruefungen") %}' + ZEILE + "{% endif %}{% endif %}" in seite
    print("Katalog unverändert bestanden.")


if __name__ == "__main__":
    test_markup_je_ansicht()
    test_skript_haengt_um()
    test_stil()
    test_katalog_unveraendert()
