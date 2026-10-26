"""Nachbesserung vor dem Merge, Runde 3 – Tippflächen und Verbesserungen aus der Browserprüfung (26.10.2026):
python tests/test_vor_merge_3.py  oder  pytest tests/test_vor_merge_3.py

  B-1  Brotkrumen: Glieder unter Touch mindestens 44 × 44 px, der Schrägstrich hängt am folgenden Glied (pfadHtml).
  B-2  „Deine Meldungen (n)“ (Meine PSA) unter Touch mindestens 44 px hoch.
  V1   Katalog: Kategoriekopf kompakt (Bearbeiten-Menü mit „Löschen“, Dokumente einklappbar), nach der Wahl aus der
       Schublade steht die Liste oben.
  V2   Seitentitel je Ansicht („M-000123 – Materialablage – strömis.de“), auch in Leitstelle, Riegenkarten, Ankerplätze
       und für „Seite nicht gefunden“ in der Strömipedia.
  V3   Zurück aus der Produktseite: Suche, Sortierung, Nachgeladenes und Scrollhöhe kommen wieder; die Schublade
       schließt beim Verlassen (bfcache).
  V5   Leitstelle: Hilfe zugeklappt, E-Mail bricht am „@“, Zeilenaktionen grau bzw. im Zeilenmenü, Reiter als Linie.
  V6   Ankerplätze: „Album anlegen“ („+ Album“ am Telefon), Werkzeuge brechen um, Überschrift für Vorlesehilfen.
  V8   „☰“ nicht im zugänglichen Namen, ✕ im Katalog „Kategorien schließen“.
  V9   Eine graue Linie unter den Reitern (die klebende Reiterregel gilt nur den Reitern im Dialog).
  V11  Telefon quer: Die Reiter im Dialog kleben nicht.
  V13  Nebentext auf rotem Grund in den Riegenkarten in Anthrazit.

Die Browserproben (Messungen der Tippflächen, Zurück/Vor, Fotos) stehen im Bericht; hier die Server-Seite und die
Stellen im Code, an denen die Lösungen hängen. Alle Namen und Daten sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import umgebung  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _titel(html):
    t = re.findall(r"<title>(.*?)</title>", html, re.S)
    assert len(t) == 1, t
    return re.sub(r"\s+", " ", t[0]).strip()


def test_seitentitel_vom_server():
    """V2: Jede Ansicht der Materialablage trägt vorn ein festes Wort, bis material.js den Namen kennt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        c = k["katalog"]                                   # Material-Verwaltung: sieht alle Ansichten
        for pfad, titel in (("/materialablage", "Übersicht – Materialablage – strömis.de"),
                            ("/materialablage/pruefungen", "Prüfungen – Materialablage – strömis.de"),
                            ("/materialablage/bestand", "Bestand – Materialablage – strömis.de"),
                            ("/materialablage/katalog", "Katalog – Materialablage – strömis.de"),
                            ("/materialablage/katalog/meldungen", "Meldungen – Materialablage – strömis.de"),
                            ("/materialablage/suche?q=PLATZHALTER", "Suche – Materialablage – strömis.de")):
            r = c.get(pfad)
            assert r.status_code == 200, (pfad, r.status_code)
            assert _titel(r.text) == titel, (pfad, _titel(r.text))
        # Übrige Module: unverändert vom Server, die Ansicht setzt das Skript (S.titel).
        for pfad, titel in (("/ankerplaetze", "Ankerplätze – strömis.de"), ("/riegenkarten", "Riegenkarten – strömis.de"),
                            ("/leitstelle", "Leitstelle – strömis.de")):
            r = k["adm"].get(pfad)
            assert r.status_code == 200 and _titel(r.text) == titel, (pfad, r.status_code, _titel(r.text))
        # V6: Überschrift der Ankerplätze für Vorlesehilfen, Anlegen-Knopf nach dem Muster.
        karte = k["adm"].get("/ankerplaetze").text
        assert '<h1 class="nur-vorlesen">Ankerplätze</h1>' in karte
        assert ('<button class="btn" id="btn-new-album"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>'
                'Album<span class="k-anlegen"> anlegen</span></span></button>') in karte and "Neues Album" not in karte
        # V5: Leitstelle – Hilfe zugeklappt, Reiter als Linie, kein btn ghost mehr.
        leit = k["adm"].get("/leitstelle").text
        assert '<details class="accordion leitstelle-hilfe">' in leit and "<summary>Hilfe: Rechte je Modul</summary>" in leit
        assert '<div class="c-tabs reiter-linie" role="tablist">' in leit
        assert "ghost" not in leit
        # V8: „☰“ nur zum Ansehen – Materialablage und Strömipedia.
        mat = c.get("/materialablage/katalog").text
        assert '<span aria-hidden="true">☰</span><span class="mat-side-auf-text"> Ordner</span>' in mat
        wiki = k["adm"].get("/stroemipedia").text
        assert '<span aria-hidden="true">☰</span> Seiten' in wiki and ">☰ Seiten<" not in wiki
    print("Seitentitel und Vorlagen bestanden.")


def test_materialablage_statisch():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    seite = lies("app/material/templates/material/seite.html")
    # B-1: Brotkrumen nur noch über pfadHtml – keine Glieder mehr mit „ / “ aneinandergehängt.
    assert 'const pfadHtml = (glieder) => glieder.filter(Boolean).map((g, i) => (i ? `<span class="mat-pfad-glied">/ ${g}</span>` : g)).join(" ");' in js
    for m in re.finditer(r'<div class="mat-pfad">(.*)', js):
        zeile = m.group(1)
        assert zeile.startswith("${pfadHtml(") or zeile.startswith("${bc}"), zeile[:80]
    assert '.map(pfadGlied).join(" / ")' not in js and "</a> / " not in js
    assert "const bc = pfadHtml(a.pfad.map(pfadGlied));" in js
    assert ("  .mat-pfad a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; "
            "min-width: 44px; padding: 0 2px; }") in css
    assert "  .mat-pfad-glied { display: inline-flex; align-items: center; gap: 0 6px; min-width: 0; }" in css
    pruefen = lies("app/material/templates/material/pruefen.html")
    assert '<span class="mat-pfad-glied">/ <a href="/materialablage/pruefungen">Prüfungen</a></span>' in pruefen
    # B-2
    assert ".mat-psa-meldungen > summary, .mat-mangel-alt > summary { padding: 10px 0; min-height: 44px; box-sizing: border-box; }" in css
    # V1: Bearbeiten-Menü mit „Löschen …“, kein eigener Löschen-Knopf; Dokumente einklappbar, als Schublade zu.
    assert 'data-act="kat-loeschen">Löschen</button>' not in js
    menue = js[js.index("const kategorieMenue = "):js.index("</details>`;", js.index("const kategorieMenue = "))]
    assert 'data-act="kat-bearbeiten"' in menue and 'data-act="kat-loeschen"><strong>Löschen …</strong>' in menue
    assert '<details class="mat-katdoks mat-auf"${alsSchublade() ? "" : " open"}><summary>Dokumente für alle Produkte dieser Kategorie<span id="kat-doks-zahl"></span></summary>' in js
    assert "katalogWahl(kat.dataset.kat ? +kat.dataset.kat : null, alsSchublade());" in js
    assert "window.scrollTo(0, ziel.getBoundingClientRect().top + window.scrollY - such.offsetHeight - oben);" in js
    # V2: Titel je Ansicht.
    assert 'const seitenTitel = (...teile) => S.titel(teile, OHNE_MODUL ? "" : "material");' in js
    for aufruf in ('seitenTitel("Übersicht");', 'seitenTitel("Prüfungen");', 'seitenTitel("Bestand");', "seitenTitel(d.name);",
                   "seitenTitel(a.inventory_no);", "seitenTitel(produktName(p));", 'seitenTitel(f.titel || "Prüfformular");',
                   'seitenTitel(k ? k.name : "", "Katalog");', "seitenTitel(d.titel);", 'seitenTitel("Änderungsanträge");',
                   "seitenTitel(`Prüfung ${a.inventory_no}`);", "seitenTitel(`Jahresbericht ${k.ordner} ${k.jahr}`)"):
        assert aufruf in js, aufruf
    assert "document.title" not in js
    for ansicht in ("dashboard", "pruefungen", "bestand", "ordner", "artikel", "katalog", "produkt", "formular", "meldungen",
                    "suche", "pruefung", "durchgang", "bericht", "meine_psa", "fremd"):
        assert f'"{ansicht}": "' in seite, ansicht
    # V3: Stand der Liste im Verlauf, kein eigenes Rollen des Browsers; Schublade zu beim Verlassen.
    assert "const gemerkt = history.state && history.state.katalog;" in js
    assert 'if ("scrollRestoration" in history) history.scrollRestoration = "manual";' in js
    assert 'window.addEventListener("pagehide", merken);' in js
    assert 'window.addEventListener("pagehide", () => leisteZu());' in js
    assert "while (geladen < Math.min(zurueck.geladen || 0, gesamt, PRO_SEITE * 20))" in js
    # V8
    assert '$("#mat-side-zu").setAttribute("aria-label", "Kategorien schließen");' in js
    # V9/V11: Die klebende Reiterregel gilt nur den Reitern im Dialog; quer klebt sie nicht.
    assert ".c-tabs.mat-reiter { position: sticky; top: -18px;" in css
    assert not re.search(r"^\.mat-reiter \{ position: sticky", css, re.M)
    assert "@media (max-height: 500px) { .c-tabs.mat-reiter { position: static; } }" in css
    print("Materialablage (statisch) bestanden.")


def test_uebrige_module_statisch():
    co = lies("app/static/js/common.js")
    assert "function titel(teile, modul) {" in co and "return { esc, api, toast, dialog, confirm, fmtDate, fmtCoord, CAT, titel };" in co
    admin = lies("app/static/js/admin.js")
    assert 'S.titel(name === "nutzer" ? "Nutzerverwaltung" : "Einstellungen", "verwaltung");' in admin
    assert "ghost" not in admin.replace("(btn ghost)", "")
    assert '<details class="zeilenmenue"><summary class="btn secondary small" aria-haspopup="true">Mehr</summary>' in admin
    assert '<button type="button" data-act="reset">Reset-Mail senden</button>' in admin
    assert 'const mailUmbruch = (mail) => S.esc(mail).replace(/@/, "<wbr>@").replace(/\\.(?=[^@]*$)/g, "<wbr>.");' in admin
    assert '<td class="mail" data-l="E-Mail">${mailUmbruch(u.email)}</td>' in admin
    app_css = lies("app/static/css/app.css")
    assert "#users td.mail { overflow-wrap: break-word; }" in app_css
    assert ".c-tabs.reiter-linie button.sel { background: none; border-bottom-color: var(--rot); color: var(--rot); }" in app_css
    assert "#users .recht-wahl, .zeilenmenue-liste button { min-height: 44px; }" in app_css
    assert "  .krumen a.krume { min-height: 44px; min-width: 44px; }" in app_css
    # V6: Werkzeuge der Karte rollen nicht mehr seitlich, sie brechen um.
    assert ".map-tools { flex-wrap: nowrap; overflow-x: auto;" not in app_css
    assert ".nur-vorlesen { position: absolute;" in app_css
    karte = lies("app/static/js/map.js")
    assert 'S.titel(title, "karte");' in karte and 'S.titel([], "karte");' in karte and '"Album anlegen"' in karte
    pr = lies("app/static/js/pruefungen.js")
    for aufruf in ('S.titel(lg.titel, "pruefungen");', 'S.titel(k.titel, "pruefungen");',
                   'S.titel("Prüfungsleistungskataloge", "pruefungen");', 'S.titel([], "pruefungen");'):
        assert aufruf in pr, aufruf
    pcss = lies("app/static/css/pruefungen.css")
    assert ".pruef .table-scroll tr.offen .tn-sub, .tn-karte.offen .muted { color: var(--anthrazit); }" in pcss
    wiki = lies("app/static/js/wiki.js")
    assert wiki.count('document.title = "Seite nicht gefunden – Strömipedia – strömis.de";') == 1
    assert 'if (isNew) document.title = "Neue Seite – Strömipedia – strömis.de";' in wiki
    # Das Zeichen steht jetzt in einem eigenen <span>: „Tippen daneben“ fragt closest, nicht die id des Ziels.
    for datei in ("app/static/js/wiki.js", "app/static/js/public.js"):
        t = lies(datei)
        assert '!e.target.closest("#wiki-menu")' in t and 'e.target.id !== "wiki-menu"' not in t, datei
    for vorlage in ("app/templates/wiki.html", "app/templates/wiki_lesemodus.html", "app/templates/public.html"):
        assert 'id="wiki-menu"><span aria-hidden="true">☰</span> Seiten</button>' in lies(vorlage), vorlage
    print("Übrige Module (statisch) bestanden.")


if __name__ == "__main__":
    test_seitentitel_vom_server()
    test_materialablage_statisch()
    test_uebrige_module_statisch()
