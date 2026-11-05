"""Reiter „Prüfformulare“ neben „Katalog“ statt des Knopfs im Katalogkopf (Wunsch vom 05.11.2026, Bauauftrag
planung/tab-pruefformulare/auftrag.md):  python tests/test_material_reiter_formulare.py  oder
pytest tests/test_material_reiter_formulare.py

1. Markup: Den Reiter (rechts neben „Katalog“, Adresse /materialablage/katalog/formulare) liefert seite.html nur der
   Material-Verwaltung aus (Entscheidung O6: nur sie sieht die Seite) – auf jeder Seite des Moduls, auch in der Übung nach
   den Rechten des Teils. Der Knopf „Prüfformulare“ im Katalogkopf ist weg; „Prüfformulare (n)“ in der Kategoriezeile
   und „Standard-Prüfformular …“ bleiben.
2. Skript und Stil: Markiert ist der Reiter auf der Seite „Prüfformulare“ und auf den Formularseiten (ohne ihn markiert die
   Formularseite „Katalog“); passen fünf Reiter am Telefon nicht in eine Zeile, brechen sie um statt zu rollen
   (navAnordnen, .umbruch); die Übung „Prüfformulare zuweisen“ beginnt im Katalog mit einem Schritt auf den Reiter.
3. Im Browser (Chromium, ohne „übersprungen“ mit rc 0) bei 1280 (Maus), 820, 375, 360 und 344 px (Touch): alle Reiter
   sichtbar und treffbar, kein seitliches Rollen der Reiter und der Seite, am Finger 44 px hoch, die Markierung je Seite;
   der Reiter führt aus dem Katalog auf die Seite „Prüfformulare“, Zurück und Vor markieren wieder richtig.
Alle Namen und Prüfpunkte sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import gliederung, katalog_grund, umgebung  # noqa: E402
from test_material_formular_pool import pool_neu, produkt_neu  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REITER = '<a href="/materialablage/katalog/formulare" data-nav="formulare">Prüfformulare</a>'


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def navigation(html):
    m = re.search(r'<nav class="mat-nav" aria-label="Materialablage">(.*?)</nav>', html, re.S)
    assert m, html[:400]
    return m.group(1)


def test_markup():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        gliederung(k["adm"])
        ids = katalog_grund(k["adm"])
        produkt = produkt_neu(k["katalog"], ids["karabiner"], "Platzhalter Reiter", "PR-1")
        _, version = pool_neu(k["katalog"], ids["karabiner"], "Platzhalter Formular")
        seiten = ("/materialablage", "/materialablage/pruefungen", "/materialablage/bestand", "/materialablage/katalog",
                  f"/materialablage/katalog?kategorie={ids['karabiner']}", f"/materialablage/katalog/produkt/{produkt}",
                  f"/materialablage/katalog/formular/{version}", "/materialablage/katalog/meldungen",
                  "/materialablage/katalog/formulare", f"/materialablage/katalog/formulare?kategorie={ids['karabiner']}")
        # adm: Plattform-Verwaltung, katalog: Material-Verwaltung – beide sehen die Seite und den Reiter; die übrigen nicht.
        for konto, mit in (("adm", True), ("katalog", True), ("wart", False), ("fuehrung", False), ("pruefer", False)):
            for pfad in seiten:
                r = k[konto].get(pfad)
                if pfad.startswith("/materialablage/katalog/formulare"):
                    assert r.status_code == (200 if mit else 403), (konto, pfad, r.status_code)
                    if not mit:
                        continue
                assert r.status_code == 200, (konto, pfad, r.status_code)
                nav = navigation(r.get_data(as_text=True))
                assert (REITER in nav) is mit, (konto, pfad)
                assert nav.count('data-nav="formulare"') == (1 if mit else 0), (konto, pfad)
                if mit:
                    # Rechts neben „Katalog“, als letzter Reiter.
                    reiter = re.search(r'<div class="mat-reiter">(.*?)</div>', nav, re.S).group(1)
                    assert re.findall(r'data-nav="(\w+)"', reiter) == ["dashboard", "pruefungen", "bestand", "katalog", "formulare"], (konto, pfad)
        # Die Übung zeichnet nach den Rechten des Teils: nur der Teil „Material-Verwaltung“ hat den Reiter.
        for konto, pfad, mit in (("katalog", "/materialablage/katalog?uebung=verwaltung", True),
                                 ("katalog", "/materialablage/katalog/formulare?uebung=verwaltung", True),
                                 ("wart", "/materialablage/artikel/neu?ordner=900000002&uebung=materialwart", False)):
            r = k[konto].get(pfad)
            assert r.status_code == 200, (konto, pfad, r.status_code)
            assert (REITER in navigation(r.get_data(as_text=True))) is mit, (konto, pfad)
    print("Markup bestanden.")


def test_skript_und_stil():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    # Markierung: Seite „Prüfformulare“ immer, Formularseite nur, wo es den Reiter gibt.
    nav = js[js.index("const NAV = {"):js.index("};", js.index("const NAV = {"))]
    assert 'formular: DARF.katalog ? "formulare" : "katalog"' in nav and 'formulare: "formulare"' in nav, nav
    assert 'produkt: "katalog"' in nav and 'meldungen: "katalog"' in nav and 'katalog: "katalog"' in nav, nav
    # Kein Knopf „Prüfformulare“ mehr im Katalogkopf; Link in der Kategoriezeile und Standard-Prüfformular bleiben.
    assert '">Prüfformulare</a>${katalogMenue}' not in js
    assert '<a class="btn secondary" href="/materialablage/katalog/formulare' not in js
    assert '${DARF.katalog ? katalogMenue : ""}</div></div>' in js
    assert 'href="/materialablage/katalog/formulare?kategorie=${k.id}">Prüfformulare (${k.formulare || 0})</a>' in js
    # Kategorienbaum auf der Seite „Prüfformulare“ (und für die Verwaltung auf Formularseiten): Formulare der Ebene statt
    # zurück in den Katalog (Wunsch vom 05.11.2026).
    assert 'const LEISTE_POOL = ANSICHT === "formulare" || (ANSICHT === "formular" && DARF.katalog);' in js
    assert '<a href="${leisteZiel(o.id)}" data-kat="${o.id}"' in js and '<a href="${leisteZiel(null)}" data-kat=""' in js
    assert "if (kat && katalogWahl && !LEISTE_POOL &&" in js
    assert " · Standard-Prüfformular <a href=" in js
    # Suchzeile mit „☰ Kategorien“ auf Katalog und „Prüfformulare“ wie bisher.
    assert 'ANSICHT === "katalog" || ANSICHT === "formulare" ? $(".mat-suchzeile", inhalt)' in js
    # Umbruch statt Rollen, wenn fünf Reiter auch in der eigenen Zeile nicht passen.
    assert 'matNav.classList.remove("eng", "enger", "umbruch");' in js
    assert 'if (matNav.classList.contains("enger") && reiter.scrollWidth > reiter.clientWidth + 1) matNav.classList.add("umbruch");' in js
    for regel in (".mat-nav.umbruch .mat-reiter { display: contents; overflow: visible; }", ".mat-nav.umbruch .mat-reiter > a { order: 3; }",
                  ".mat-nav.umbruch .mat-lupe { order: 4; }", ".mat-nav.umbruch .mat-suche { order: 5; }"):
        assert regel in css, regel
    # Die Übung: Start im Katalog, erster Schritt auf den Reiter.
    ue = lies("app/static/js/uebung/material.js")
    assert "const reiterFormulare = '.mat-nav a[data-nav=\"formulare\"]';" in ue
    i = ue.index('{ titel: "Prüfformulare zuweisen", start: "/materialablage/katalog", schritte: [')
    erster = ue[i:ue.index("\n", ue.index("\n", i) + 1)]
    assert "ziel: reiterFormulare" in erster and "warten: { klick: reiterFormulare }" in erster, erster
    assert 'start: "/materialablage/katalog/formulare"' not in ue
    print("Skript und Stil bestanden.")


# --- 3. Im Browser ---------------------------------------------------------------------------------------------------

MESSEN = """(() => {
  const nav = document.querySelector('.mat-nav'), r = document.querySelector('.mat-reiter');
  const tabs = [...r.querySelectorAll('a')].map((a) => { const b = a.getBoundingClientRect();
    const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    return { name: a.dataset.nav, aktiv: a.classList.contains('aktiv'), links: b.left, rechts: b.right, hoehe: b.height,
             trifft: Boolean(e && (e === a || a.contains(e))) }; });
  return { tabs, umbruch: nav.classList.contains('umbruch'), reiterRollt: r.scrollWidth - r.clientWidth,
           seiteRollt: document.documentElement.scrollWidth - document.documentElement.clientWidth, breite: innerWidth,
           knopf: [...document.querySelectorAll('#mat-inhalt .page-head a, #mat-inhalt .page-head button')]
             .some((x) => x.textContent.trim() === 'Prüfformulare') };
})()"""
GROESSEN = ((1280, 900, False), (820, 1180, True), (375, 667, True), (360, 740, True), (344, 882, True))


def test_browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        r = u.adm.post("/api/material/kategorien", json={"name": "Platzhalter Kategorie"})
        assert r.status_code == 201, r.get_json()
        kat = r.json["kategorie"]["id"]
        produkt = produkt_neu(u.adm, kat, "Platzhalter Produkt", "PP-1")
        _, version = pool_neu(u.adm, kat, "Platzhalter Formular")
        markiert = {"/materialablage": "dashboard", "/materialablage/katalog": "katalog",
                    f"/materialablage/katalog/produkt/{produkt}": "katalog", "/materialablage/katalog/formulare": "formulare",
                    f"/materialablage/katalog/formular/{version}": "formulare"}
        for rolle, anzahl in (("matverwaltung", 5), ("materialwart", 4)):
            for breite, hoehe, touch in GROESSEN:
                s = u.seite(rolle, breite, hoehe, touch)
                try:
                    for pfad, soll in markiert.items():
                        if rolle == "materialwart":
                            if pfad == "/materialablage/katalog/formulare":
                                continue                       # 403 – die Seite sieht nur die Material-Verwaltung
                            soll = "katalog" if soll == "formulare" else soll
                        s.oeffnen(pfad, warten=0.8)
                        assert s.warte("Boolean(document.querySelector('#mat-inhalt h1'))", 10), (rolle, breite, pfad)
                        m = s.js(MESSEN)
                        wo = (rolle, breite, pfad)
                        assert len(m["tabs"]) == anzahl and m["seiteRollt"] <= 0 and m["reiterRollt"] <= 1, (wo, m)
                        assert [t["name"] for t in m["tabs"] if t["aktiv"]] == [soll], (wo, m["tabs"])
                        for t in m["tabs"]:
                            assert t["trifft"] and t["links"] >= 0 and t["rechts"] <= m["breite"], (wo, t)
                            assert not touch or t["hoehe"] >= 44, (wo, t)
                        assert not m["knopf"], wo
                        # Am Telefon brechen fünf Reiter um, vier passen wie bisher in die Zeile.
                        if breite <= 375:
                            assert m["umbruch"] is (anzahl == 5), (wo, m["umbruch"])
                    if rolle == "matverwaltung":
                        # Aus dem Katalog über den Reiter auf die Seite „Prüfformulare“, Zurück und Vor.
                        s.oeffnen("/materialablage/katalog", warten=0.8)
                        assert s.klick('.mat-nav a[data-nav="formulare"]') is None
                        assert s.warte("location.pathname === '/materialablage/katalog/formulare' && document.querySelector('.mat-nav a.aktiv')?.dataset.nav === 'formulare'", 10), breite
                        s.js("history.back()")
                        assert s.warte("location.pathname === '/materialablage/katalog' && document.querySelector('.mat-nav a.aktiv')?.dataset.nav === 'katalog'", 10), breite
                        s.js("history.forward()")
                        assert s.warte("location.pathname === '/materialablage/katalog/formulare' && document.querySelector('.mat-nav a.aktiv')?.dataset.nav === 'formulare'", 10), breite
                        if breite >= 1024:
                            # Baum links: die Kategorie zeigt die Formulare ihrer Ebene, „alle Kategorien“ alle.
                            assert s.klick(f'a[data-kat="{kat}"]') is None
                            assert s.warte(f"location.pathname === '/materialablage/katalog/formulare' && location.search === '?kategorie={kat}' && Boolean(document.querySelector('.mat-pool-nur'))", 10), breite
                            assert s.klick('a[data-kat=""]') is None
                            assert s.warte("location.pathname === '/materialablage/katalog/formulare' && location.search === '' && !document.querySelector('.mat-pool-nur')", 10), breite
                    s.sammeln()
                    assert not s.fehler, (rolle, breite, s.fehler)
                finally:
                    s.schliessen()
                print(f"{rolle} {breite}×{hoehe}{' Touch' if touch else ''}: bestanden")
    print("Browser bestanden.")


if __name__ == "__main__":
    test_markup()
    test_skript_und_stil()
    test_browser()
