"""Suchzeile in der Strömipedia wie in der Materialablage (02.11.2026, planung/wiki-suchzeile/auftrag.md):
python tests/test_wiki_suchzeile.py  oder  pytest tests/test_wiki_suchzeile.py

  1. Aufbau: oben im Inhalt eine Zeile mit „☰“ (sichtbar nur das Zeichen, Name „Seiten“, aria-controls/expanded) und dem
     Feld „Artikel suchen“; die Treffer als Liste darunter. Der Knopf „☰ Seiten“ und das „☰“ der Artikel-Leiste der
     Leseansicht entfallen; im Editor bleibt sein „☰“. Seit dem 02.11.2026 (planung/wiki-suchzeile/auftrag_lesemodus.md,
     Nutzer: „ja“) dieselbe Zeile im Lesemodus und in public.html (derselbe Leser public.js) statt „☰ Seiten“.
  2. Regeln: nur unter 1024 px und nicht im Editor; klebend unter der Kopfleiste, die Artikel-Leiste direkt darunter
     (gemessene Höhe), Sprungziele unter beiden; in der Schublade kein zweites Suchfeld; 44 px am Finger nur unter
     (pointer: coarse); wenig Höhe wie in der Materialablage; Druck ohne Zeile.
  3. Suchlogik: eine Funktion für Seitenleiste und Zeile (ab 2 Zeichen, 250 ms, Enter, Pfeile, Esc, Tippen daneben,
     Zurück) in markdown.js, die wiki.js (/api/wiki/search) und public.js (/api/public/search) teilen; Suchbegriff der
     Startseite unter 1024 px in die Zeile – in beiden Lesern.
  4. Schnittstellen /api/wiki/search und /api/public/search unverändert; /stroemipedia liefert die Zeile für Mitglied,
     Redakteur und Lesemodus; die frühere öffentliche Ansicht leitet weiter, ihre Vorlage hat die Zeile ebenfalls.
Statisch über die Quelltexte plus Schnittstelle; Verhalten und Maße im Browser gemessen (planung/wiki-suchzeile/bericht.md).
Alle Inhalte sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rechte_redakteur import MITGLIED, REDAKTEUR, anmelden, konto, make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i)]


# --- 1. Aufbau --------------------------------------------------------------------------------------------------------

def test_aufbau():
    html = lies("app/templates/wiki.html")
    main = abschnitt(html, '<main class="wiki-main" id="wiki-main">', "</main>")
    zeile = abschnitt(main, '<div class="wiki-suchzeile" id="wiki-suchzeile" role="search">', "\n    </div>")
    # Zuerst die Zeile, dann der Inhalt; links „☰“, rechts das Feld, darunter die Liste.
    assert main.index("wiki-suchzeile") < main.index('<div id="wiki-content">')
    assert zeile.index('id="wiki-menu"') < zeile.index('id="zeilen-suche"') < zeile.index('id="zeilen-treffer"')
    assert ('<button class="btn secondary small wiki-menu-btn" type="button" aria-controls="wiki-side" aria-expanded="false" '
            'id="wiki-menu"><span aria-hidden="true">☰</span><span class="nur-vorlesen">Seiten</span></button>') in zeile
    assert ('<input type="search" id="zeilen-suche" placeholder="Artikel suchen" aria-label="Artikel suchen" autocomplete="off" '
            'enterkeyhint="search" aria-controls="zeilen-treffer">') in zeile
    assert '<ul class="search-results zeilen-treffer hidden" id="zeilen-treffer" aria-label="Gefundene Artikel"></ul>' in zeile
    # Keine Lupe, kein Absendeknopf, kein „…“; der alte Knopf „☰ Seiten“ ist weg (genau ein #wiki-menu).
    assert "<form" not in zeile and 'type="submit"' not in zeile and "…" not in zeile and "🔍" not in zeile
    assert html.count('id="wiki-menu"') == 1 and "☰</span> Seiten" not in html
    # Das Feld über dem Baum bleibt (ab 1024 px) – genau eins je Ort.
    assert html.count('id="wiki-search"') == 1 and html.count('type="search"') == 2
    # Leseansicht ohne eigenes „☰“ in der Artikel-Leiste, der Editor behält seins.
    js = lies("app/static/js/wiki.js")
    lesen = abschnitt(js, "  async function renderPage() {", "\n  }\n")
    assert "baum-knopf" not in lesen and "#pg-baum" not in lesen
    editor = abschnitt(js, '      <div class="wiki-head editing-head">', "</div>")
    assert 'class="btn secondary small kopfknopf baum-knopf" id="pg-baum"' in editor
    assert js.count('id="pg-baum"') == 1
    assert 'S.schubladeZustand(side, "#wiki-menu, #pg-baum");' in js
    print("Aufbau bestanden.")


def test_aufbau_lesemodus_und_oeffentlich():
    """Lesemodus (wiki_lesemodus.html) und frühere öffentliche Ansicht (public.html): dieselbe Zeile, Zeichen für Zeichen
    wie in wiki.html; „☰ Seiten“ ist weg, das Feld über dem Baum bleibt (ab 1024 px)."""
    intern = abschnitt(lies("app/templates/wiki.html"), '<div class="wiki-suchzeile" id="wiki-suchzeile" role="search">',
                       "\n    </div>")
    for vorlage in ("app/templates/wiki_lesemodus.html", "app/templates/public.html"):
        html = lies(vorlage)
        main = abschnitt(html, '<main class="wiki-main" id="wiki-main">', "</main>")
        zeile = abschnitt(main, '<div class="wiki-suchzeile" id="wiki-suchzeile" role="search">', "\n    </div>")
        assert zeile == intern, vorlage
        # Die Zeile steht zuoberst im Inhalt (sie klebt bündig unter der Kopfleiste), erst dann Hinweis und Text.
        vor = main[main.index(">") + 1:main.index('<div class="wiki-suchzeile"')]
        assert re.sub(r"\{#.*?#\}", "", vor, flags=re.S).strip() == "", vorlage
        assert main.index("wiki-suchzeile") < main.index('<div id="wiki-content">')
        assert html.count('id="wiki-menu"') == 1 and "☰</span> Seiten" not in html, vorlage
        assert html.count('id="wiki-search"') == 1 and html.count('type="search"') == 2, vorlage
        # Ohne Stufe kein Editor: nur der Leser public.js nach markdown.js (dort steht die Suchlogik).
        assert html.index("js/markdown.js") < html.index("js/public.js") and "js/wiki.js" not in html, vorlage
    lese = lies("app/templates/wiki_lesemodus.html")
    assert lese.index('id="wiki-suchzeile"') < lese.index('class="lesemodus-hinweis"')
    print("Aufbau Lesemodus und öffentliche Ansicht bestanden.")


# --- 2. Regeln ---------------------------------------------------------------------------------------------------------

def test_regeln():
    css = lies("app/static/css/app.css")
    teil = abschnitt(css, "/* Suchzeile (Wunsch vom 02.11.2026", "@media (max-width: 640px) {")
    # Ab 1024 px nicht da; darunter nur außerhalb des Editors, klebend unter der Kopfleiste, weißer Grund.
    assert ".wiki-suchzeile { display: none; }\n@media (max-width: 1023px) {\n  body:not(.editing) .wiki-suchzeile {" in teil
    regel = abschnitt(teil, "  body:not(.editing) .wiki-suchzeile {", "}")
    for teilregel in ("display: flex;", "position: sticky; top: var(--topbar);", "background: var(--weiss);", "z-index: 45;"):
        assert teilregel in regel, teilregel
    # Das Feld füllt den Rest, „☰“ wächst nicht mit (44 × 44 px nur am Finger, Regel für .wiki-menu-btn unten).
    assert ".wiki-suchzeile > input[type=search] { flex: 1 1 auto; min-width: 0; margin: 0; }" in teil
    assert ".wiki-suchzeile > .wiki-menu-btn { flex: none; padding-left: 12px; padding-right: 12px;" in teil
    # Kein doppeltes Suchfeld: In der Schublade fällt das Feld über dem Baum weg, solange die Zeile steht.
    assert ("body:not(.editing) .wiki-shell:has(.wiki-suchzeile) .wiki-side > :is(#wiki-search, #search-results) "
            "{ display: none; }") in teil
    # Artikel-Leiste direkt darunter (gemessene Höhe), Treffer über dem Text mit eigenem Bildlauf.
    assert "body:not(.editing) .wiki-head { top: calc(var(--topbar) + var(--wiki-suchzeile, 0px)); }" in teil
    liste = abschnitt(teil, ".wiki-suchzeile > .zeilen-treffer {", "}")
    for teilregel in ("position: absolute; top: 100%;", "max-height: var(--treffer-hoehe, 60vh);", "overflow-y: auto;",
                      "box-shadow: var(--schatten-menue);"):
        assert teilregel in liste, teilregel
    # Wenig Höhe: Die Zeile klebt weiter (--topbar ist dort 0), nur mit weniger Luft; die Artikel-Leiste rollt mit.
    assert "@media (max-height: 500px) and (max-width: 1023px) {\n  body:not(.editing) .wiki-suchzeile { padding: 4px 0; }" in teil
    hoehe = abschnitt(css, "@media (max-height: 500px) {\n  .wiki-head", "\n}")
    assert "position: static;" in hoehe
    assert ".wiki-content [id] { scroll-margin-top: calc(var(--topbar) + var(--wiki-suchzeile, 0px) + 8px); }" in hoehe
    # Sprungziele der Leseansicht unter Kopfleiste, Suchzeile und Artikel-Leiste; der Editor wie bisher.
    assert (".wiki-content h5, .wiki-content h6, .wiki-content [id] { scroll-margin-top: calc(var(--topbar) + "
            "var(--wiki-suchzeile, 0px) + 72px); }") in css
    assert ".wiki-editor .toastui-editor-contents :is(h1, h2, h3, h4, h5, h6) { scroll-margin-top: calc(var(--topbar) + 72px); }" in css
    # Der alte Ausweg „☰ Seiten“ ausblenden, sobald die Leiste ein „☰“ hat, gibt es nicht mehr.
    assert ".wiki-main:has(.wiki-head .baum-knopf)" not in css
    # 44 px am Finger nur unter (pointer: coarse); keine Hover-Regel für die Zeile.
    touch = abschnitt(css, "  .tree { margin-right: -12px; }", "  details.accordion")
    assert ".wiki-side input[type=search], .wiki-suchzeile > input[type=search] { min-height: 44px; }" in touch
    assert ".wiki-side .btn-row .btn.small, .wiki-menu-btn { min-height: 44px; min-width: 44px; padding: 9px 12px; }" in css
    assert ":hover" not in teil and "min-height: 44px" not in teil
    # Keine freien Farbwerte.
    assert "#" not in re.sub(r"/\*.*?\*/", "", teil, flags=re.S).replace("#wiki-search", "").replace("#search-results", "")
    # Druck ohne Zeile.
    druck = abschnitt(css, "@media print {\n  .bauchbinde", "{ display: none !important; }")
    assert ".wiki-suchzeile" in druck
    print("Regeln bestanden.")


# --- 3. Suchlogik ------------------------------------------------------------------------------------------------------

def test_suchlogik():
    md = lies("app/static/js/markdown.js")
    js = lies("app/static/js/wiki.js")
    pub = lies("app/static/js/public.js")
    such = abschnitt(md, "  function sucheVerdrahten(feld, liste, { zeile = null, suchen: holen, adresse, oeffnen: seiteOeffnen, "
                         "fehler = () => {} } = {}) {", "\n  }\n")
    assert "sucheVerdrahten, suchzeileEinrichten," in md
    # Eine Funktion für beide Felder und beide Leser – keine zweite Suchlogik; jeder Leser sagt nur, woher die Treffer
    # kommen (wiki.js: alle Seiten mit Stufe, public.js: nur freigegebene) und wie ein Treffer aufgeht.
    for quelle, schnittstelle in ((js, "api(`/api/wiki/search?q=${encodeURIComponent(q)}`)"),
                                  (pub, "get(`/api/public/search?q=${encodeURIComponent(q)}`)")):
        assert "  MD.sucheVerdrahten(searchInput, searchResults, artikelsuche);\n" in quelle
        assert ('const zeilenSuche = suchzeile && MD.sucheVerdrahten($("#zeilen-suche"), $("#zeilen-treffer"), '
                '{ ...artikelsuche, zeile: suchzeile });') in quelle
        assert "const zeileSteht = MD.suchzeileEinrichten(shell, suchzeile, zeilenSuche, searchInput);" in quelle
        assert quelle.count("/search?q=") == 1 and schnittstelle in quelle
        assert "function sucheVerdrahten" not in quelle and "setTimeout" not in abschnitt(quelle, "const artikelsuche", "};")
    assert "/search?q=" not in md
    assert 'oeffnen: (href) => { side.classList.remove("open"); navigate(slugAus(href)); },' in js
    assert "oeffnen: (href) => navigate(href.slice(prefix.length))," in pub
    assert "fehler: (text) => { if (window.S && S.toast) S.toast(text, true); }," in pub
    # public.js: Ein Schritt im Verlauf auf eine andere Seite schließt die Liste; ohne common.js (public.html) folgt
    # aria-expanded des „☰“ der Schublade über einen eigenen Beobachter.
    assert 'window.addEventListener("popstate", () => {\n    if (zeilenSuche) zeilenSuche.schliessen();\n    show(slugAusPfad());' in pub
    assert ('new MutationObserver(() => $("#wiki-menu").setAttribute("aria-expanded", String(side.classList.contains("open"))))'
            in pub)
    # Ab 2 Zeichen, 250 ms; „Keine Treffer.“; Titel und Ausschnitt mit esc.
    assert "if (q.length < 2) { leeren(); return; }" in such
    assert "lauf = setTimeout(() => suchen(q).catch((e) => fehler(e.message)), 250);" in such
    assert "'<li class=\"muted\">Keine Treffer.</li>'" in such
    assert ('<a href="${esc(adresse(r.slug))}">${esc(r.title)}</a>${r.snippet ? `<div class="snip">${esc(r.snippet)}</div>` '
            ': ""}') in such
    # Enter öffnet den ersten Treffer, auch wenn die Suche noch unterwegs ist; ↓ in die Liste, ↑/↓ darin, Esc zurück.
    assert 'if (e.key === "Enter") {' in such and "if (stand !== q && !(await suchen(q))) return;" in such
    assert 'const a = liste.querySelector("a");\n        if (a) oeffnen(a);' in such
    assert 'e.key === "ArrowDown" && offen()' in such and 'if (e.key === "ArrowDown" || e.key === "ArrowUp") {' in such
    assert "if (n < 0) feld.focus(); else if (links[n]) links[n].focus();" in such
    # Tippen öffnet die Seite und schließt Liste und Tastatur; Esc, Tippen daneben, Tab hinaus und Zurück schließen.
    oeffnen = abschnitt(such, "const oeffnen = (a) => {", "};")
    assert "if (zeile) { zeigen(false); feld.blur(); }" in oeffnen and 'seiteOeffnen(a.getAttribute("href"));' in oeffnen
    assert 'e.key === "Escape" && zeile && offen()' in such
    assert 'document.addEventListener("pointerdown", (e) => {' in such
    assert 'zeile.addEventListener("focusout", (e) => {' in such
    # Zurück schließt die Liste, wo common.js geladen ist (Strömipedia, Lesemodus; public.html lädt es nicht).
    assert ('if (window.S && S.klassenVerlauf) {\n        S.klassenVerlauf(zeile, "treffer-auf", () => zeigen(false), '
            '() => zeile.getClientRects().length > 0);') in such
    # Höhe der Liste bis zur Unterkante des sichtbaren Bereichs (auch mit Tastatur).
    assert 'zeile.style.setProperty("--treffer-hoehe", Math.max(120, Math.floor(unten - zeile.getBoundingClientRect().bottom - 8)) + "px");' in such
    # Höhe der Zeile für die Artikel-Leiste, gemessen (Drehen, Schriftgröße).
    einrichten = abschnitt(md, "  function suchzeileEinrichten(shell, zeile, zeilenSuche, seitenfeld) {", "\n  }\n")
    assert 'const hoehe = () => shell.style.setProperty("--wiki-suchzeile", zeile.getBoundingClientRect().height + "px");' in einrichten
    assert 'new ResizeObserver(hoehe).observe(zeile, { box: "border-box" });' in einrichten
    # Über die Grenze gedreht: Begriff ins sichtbare Feld, Liste zu.
    assert 'const grenze = window.matchMedia("(max-width: 1023px)");' in einrichten
    assert "zeilenSuche.schliessen();" in einrichten
    assert "if (!zeilenSuche) return () => false;" in einrichten
    # Startseite: Suchbegriff unter 1024 px in die Zeile statt in die aufgeklappte Schublade – in beiden Lesern.
    for quelle in (js, pub):
        adresse = abschnitt(quelle, "  function sucheAusAdresse() {", "\n  }\n")
        assert adresse.index("if (zeileSteht()) {") < adresse.index("searchInput.value = q.trim();")
        assert 'zeilenSuche.feld.dispatchEvent(new Event("input"));' in adresse
    # Klebende Leisten für Cursor und „/“-Menü: die Zeile zählt mit.
    assert 'document.querySelectorAll(".bauchbinde, .wiki-suchzeile, .wiki-head").forEach((el) => {' in js
    # Ohne Zeile (Prüfstände unter tests/ bauen die Seite ohne Vorlage) läuft wiki.js weiter.
    assert "if (!feld || !liste) return null;" in such
    print("Suchlogik bestanden.")


# --- 4. Schnittstelle und Seiten ---------------------------------------------------------------------------------------

def test_schnittstelle_und_seiten():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        mitglied, _ = konto(app, adm, "mitglied@example.org", "Platzhalter Mitglied", {"wiki": MITGLIED})
        redakteur, _ = konto(app, adm, "redakteur@example.org", "Platzhalter Redakteur", {"wiki": REDAKTEUR})
        leser, _ = konto(app, adm, "leser@example.org", "Platzhalter Leser", {"material": 1})
        seiten = {}
        for titel, inhalt in (("Platzhalter Alpha", "Text mit SUCHMARKE darin"), ("Platzhalter Beta", "anderer Text")):
            r = adm.post("/api/wiki/pages", json={"title": titel, "content": inhalt})
            assert r.status_code == 201, r.get_json()
            seiten[titel] = r.get_json()["page"]
        for c in (mitglied, redakteur):
            # Unter zwei Zeichen keine Suche; Treffer mit Titel, Adresse und Ausschnitt wie bisher.
            assert c.get("/api/wiki/search?q=S").json == {"results": []}
            treffer = c.get("/api/wiki/search?q=SUCHMARKE").json["results"]
            assert [t["title"] for t in treffer] == ["Platzhalter Alpha"]
            assert treffer[0]["slug"] and "SUCHMARKE" in treffer[0]["snippet"]
            assert len(c.get("/api/wiki/search?q=Platzhalter").json["results"]) == 2
            html = c.get("/stroemipedia").get_data(as_text=True)
            assert 'id="wiki-suchzeile"' in html and 'placeholder="Artikel suchen"' in html and 'id="wiki-search"' in html
        # Lesemodus (ohne Stufe): dieselbe Zeile auf Übersicht und Seite, ohne „☰ Seiten“; gesucht wird über
        # /api/public/search – nur freigegebene Seiten, die interne Suche bleibt zu.
        alpha = seiten["Platzhalter Alpha"]
        for adresse in ("/stroemipedia", f"/stroemipedia/{alpha['slug']}", "/stroemipedia?suche=SUCHMARKE"):
            html = leser.get(adresse).get_data(as_text=True)
            assert 'data-modus="lesemodus"' in html and 'id="wiki-suchzeile"' in html, adresse
            assert 'placeholder="Artikel suchen"' in html and 'id="wiki-search"' in html and "☰</span> Seiten" not in html
            assert "js/public.js" in html and "js/wiki.js" not in html
        assert leser.get("/api/wiki/search?q=SUCHMARKE").status_code == 403
        assert leser.get("/api/public/search?q=SUCHMARKE").json["results"] == []
        r = adm.put(f"/api/wiki/pages/{alpha['id']}/share", json={"is_public": True, "public_children": False})
        assert r.status_code == 200, r.get_json()
        assert leser.get("/api/public/search?q=S").json["results"] == []
        treffer = leser.get("/api/public/search?q=SUCHMARKE").json["results"]
        assert [t["title"] for t in treffer] == ["Platzhalter Alpha"] and treffer[0]["slug"] == alpha["slug"]
        assert [t["title"] for t in leser.get("/api/public/search?q=Platzhalter").json["results"]] == ["Platzhalter Alpha"]
        # Frühere öffentliche Ansicht: ohne Anmeldung zur Anmeldung, mit dem Lesemodus-Konto in die Strömipedia; die
        # Vorlage public.html (nicht mehr gezeichnet) hat dieselbe Zeile, gerendert wie früher.
        anon = app.test_client()
        r = anon.get("/oeffentlich/")
        assert r.status_code == 302 and r.headers["Location"].startswith("/login"), r.headers
        assert leser.get(f"/oeffentlich/{alpha['slug']}").headers["Location"] == f"/stroemipedia/{alpha['slug']}"
        from flask import render_template
        with app.test_request_context("/oeffentlich/"):
            html = render_template("public.html", slug="")
        assert 'id="wiki-suchzeile"' in html and 'placeholder="Artikel suchen"' in html and "☰</span> Seiten" not in html
    print("Schnittstelle und Seiten bestanden.")


if __name__ == "__main__":
    test_aufbau()
    test_aufbau_lesemodus_und_oeffentlich()
    test_regeln()
    test_suchlogik()
    test_schnittstelle_und_seiten()
