"""Gerätetest 01.11.2026, Teil 5 – Ankerplätze, Leitstelle, Profil (Auftrag planung/geraetetest/auftrag_geraetetest.md):
python tests/test_module_geraetetest_t5.py  oder  pytest tests/test_module_geraetetest_t5.py

  B8  Suchfeld über der Karte und Liste „in der Nähe“ (Entfernung zum Standort, sonst alphabetisch mit Hinweis).
  FT2 Standort: Meldung erst mit der Antwort der Ortung, je Fall eigener Satz, 20 s, blockiert = sofortiger Hinweis.
  FT8 gelöschtes Album sofort aus der Liste, Satz für ein Album ohne Position.
  FT5 Ziffern-Dateinamen („48698.jpg“) nicht als Name – „Bild n von m“.
  FT4 Hochladen: Ergebnis im Dialog „ohne Geotag“ statt unter ihm; „Bild gelöscht“ nach dem Schließen der Großansicht.
  B6  Leitstelle: Suche (Name, E-Mail, Gliederung), Filter nach Rolle, zugeklappte Karten.  Q2 Spaltenköpfe mit
      weichen Trennstellen.  M4 Satz zur Prüffreigabe am Häkchen „Prüfer“.
Das Verhalten im Browser (Lage, Tippflächen, Sortierung, Ortung) ist gemessen (planung/geraetetest/bericht_teil5.md); hier
steht, dass die Stellen im Code hängen und die Server-Seite stimmt. Alle Konten und Inhalte sind Platzhalter, es geht keine
Mail hinaus."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP, ADM, CSS = "app/static/js/map.js", "app/static/js/admin.js", "app/static/css/app.css"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _app(tmp):
    os.environ.pop("SMTP_HOST", None)            # nie eine echte Mail
    app = make_app(tmp)
    from app import auth
    auth.send_mail = lambda *a, **k: None
    return app


def _anmelden(c, mail="admin@example.org", pw="geheim123"):
    r = c.post("/api/auth/login", json={"email": mail, "password": pw})
    assert r.status_code == 200, r.get_json()


def test_b8_suche_und_liste():
    m, idx = lies(MAP), lies("app/templates/index.html")
    # Suchfeld und „Alben“ als Gruppe vor den Filtern; „Alben“ schaltet die Leiste (aria-expanded).
    assert idx.index('<form class="karten-suche" id="karten-suche" role="search">') < idx.index('data-cat="">Alle</button>')
    assert 'id="alben-suche"' in idx and 'aria-label="Alben suchen: Name oder Ort"' in idx
    assert 'id="btn-albums" type="button" aria-controls="panel" aria-expanded="false">Alben</button>' in idx
    # Gesucht wird in Titel, Beschreibung und Gliederung; die Karte zeigt nur die Bilder der Treffer.
    assert "grund([a.title, a.description, a.contact_org].join(\" \"))" in m
    assert "(!treffer || treffer.has(p.album_id))" in m
    # Sortierung: mit Standort nach Entfernung (ohne Position zuletzt), sonst nach dem Namen – mit Hinweis und Angebot.
    assert "ort.distanceTo([a.lat, a.lon])" in m
    assert "In der Nähe: nach Entfernung zu deinem Standort sortiert." in m
    assert 'Ohne deinen Standort alphabetisch sortiert. <button type="button" class="lnk" id="al-standort">Standort verwenden</button>' in m
    # Liste als Knöpfe (Tastatur), Zahl als einzige Ansage, Leerzustand bei keinem Treffer.
    assert '<button type="button" class="album-wahl" data-id="${a.id}">' in m
    assert '<p class="meta" id="al-zahl" role="status"></p>' in m and 'id="al-liste" aria-live="off"' in m
    assert "<strong>Kein Album passt" in m
    # Zweiter Tipp auf „Alben“ schließt die Liste; mit freigegebenem Standort sortiert sie ohne Rückfrage.
    assert "if (state.liste && panel.classList.contains(\"open\")) closePanel();" in m
    assert '(await ortungsRecht()) === "granted") standortSuchen(false);' in m
    css = lies(CSS)
    assert ".map-shell:has(.panel.open) .map-tools { max-width: calc(100% - var(--panel-w) - 24px); }" in css
    assert ".album-list li:has(> .album-wahl) { padding: 0; }" in css
    print("B8 bestanden.")


def test_ft2_standort():
    m = lies(MAP)
    assert 'toast("Standort konnte nicht ermittelt werden.", true)' not in m
    assert "const ORTUNG_MS = 20000;" in m
    assert "timeout: ORTUNG_MS" in m and 'state.map.on("locationerror", ortungFehler);' in m
    # Fälle: verweigert, Zeitüberschreitung, nicht verfügbar; blockiert sofort; keine Antwort nach 30 s.
    assert 'e.code === 1 ? "Standort nicht freigegeben.' in m
    assert 'e.code === 3 ? "Kein Standort nach 20 Sekunden' in m
    assert 'e.code === 2 ? "Standort gerade nicht verfügbar' in m
    assert '(await ortungsRecht()) === "denied") return toast(BLOCKIERT, true);' in m
    assert "}, ORTUNG_MS + 10000);" in m
    # Alle Ortungen laufen über dieselbe Stelle (Knopf „◎“, „Mein Standort“ beim Positionieren, Liste).
    assert m.count("state.map.locate(") == 1
    assert '$("#loc-me").onclick = () => standortSuchen(true);' in m
    print("FT2 bestanden.")


def test_ft4_ft5_ft8_alben_und_bilder():
    m = lies(MAP)
    # FT8: nach dem Löschen die frische Liste; Satz für ein Album ohne Position (je nach Recht).
    teil = m[m.index("async function albumLoeschen(a, dlg) {"):m.index("/* --- Album anlegen / bearbeiten")]
    assert "state.alben = null;\n      await showAlbums();" in teil and "closePanel();" not in teil
    assert "Noch nicht auf der Karte – lade ein Bild mit Standort (GPS) hoch" in m
    assert "Noch nicht auf der Karte – das Album hat noch kein Bild mit Position." in m
    # FT5: Ziffern-Dateinamen sind kein Name; überall dieselbe Hilfe.
    assert "p.title || p.original_name" not in m
    assert 'const nurZiffern = (name) => /^[\\d\\s_-]+(\\.[a-z0-9]{1,5})?$/i.test(' in m
    assert m.count("bildName(") >= 4 and m.count("esc(name)") == 2
    # FT4: Ergebnis im Dialog „ohne Geotag“ (ein Toast läge unter ihm); „Bild gelöscht“ nach lb.close().
    assert "if (!d.unlocated.length && !gemeldet) toast(meldung, fehler);" in m
    assert '`<p><strong>${esc(meldung)}.</strong></p>`' in m
    assert m.index("        lb.close();\n        toast(\"Bild gelöscht\");") > 0
    print("FT4/FT5/FT8 bestanden.")


def test_nur_ziffern_regel():
    """Die Regel aus map.js in Python nachgebaut: Was sie als Ziffernnamen erkennt und was nicht."""
    m = lies(MAP)
    muster = re.search(r"const nurZiffern = \(name\) => /(.+?)/i\.test", m).group(1)
    regel = re.compile(muster, re.I)
    for name in ("48698.jpg", "1000012345.jpeg", "20261101_123456.JPG", "123", "4711-0815.webp"):
        assert regel.match(name), name
    for name in ("IMG_20261101_123456.jpg", "PXL_20261101.jpg", "Wehr Nord.jpg", "demo-0-1.jpg", "48698.jpg.heic.x"):
        assert not regel.match(name), name
    print("Ziffernregel bestanden.")


def test_leitstelle_b6_q2_m4():
    a, html, css = lies(ADM), lies("app/templates/admin.html"), lies(CSS)
    assert '<input type="search" id="u-suche" placeholder="Name, E-Mail oder Gliederung"' in html
    assert '<select id="u-rolle" aria-label="Nach Rolle filtern"><option value="">Alle Rollen</option></select>' in html
    assert '<p class="meta" id="u-zahl" role="status"></p>' in html and 'id="u-leer"' in html
    # Gefiltert wird im Browser über alle geladenen Konten – nichts seitenweise.
    assert "const text = grund([u.name, u.email, u.gliederung].join(\" \"));" in a
    assert 'tr.classList.toggle("hidden", !zeigen);' in a
    # Karten zugeklappt: Name als Aufklapper, Rollen als Marken, Auswahlfelder erst offen.
    assert '<button type="button" class="u-auf" aria-expanded="${aufgeklappt.has(u.id)}">' in a
    assert '<td class="u-rollen">${rollenMarken(u)}</td>' in a
    assert "main.leitstelle #users tr:not(.offen) > td:not(.u-name, .u-rollen, [data-l=Gliederung]) { display: none; }" in css
    assert "#users .u-auf, main.leitstelle #users td.u-rollen { display: none; }" in css
    # Q2: weiche Trennstellen, Namen ganz.
    assert '"Materialablage": "Material&shy;ablage"' in html and '"Riegenkarten": "Riegen&shy;karten"' in html
    # M4: Satz am Häkchen, entfällt mit gültiger Prüffreigabe.
    assert "Prüfen kann die Person erst mit einer Prüffreigabe am Ordner" in a
    assert 'liste.some((f) => f.recht === "pruefen" && f.gueltig)' in a
    print("Leitstelle bestanden.")


def test_seiten_und_schnittstelle():
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(tmp)
        c = app.test_client()
        _anmelden(c)
        html = c.get("/leitstelle").get_data(as_text=True)
        assert 'id="u-suche"' in html and "Material&shy;ablage</th>" in html
        # Kein Modulname ohne Spaltenkopf: alle fünf kommen (ohne Trennstellen gelesen) in der Reihenfolge der Kopfleiste.
        roh = html.replace("&shy;", "")
        stellen = [roh.index(f"<th>{n}</th>") for n in ("Strömipedia", "Ankerplätze", "Riegenkarten", "Materialablage",
                                                        "Leitstelle")]
        assert stellen == sorted(stellen)
        karte = c.get("/ankerplaetze").get_data(as_text=True)
        assert 'id="alben-suche"' in karte and 'id="btn-albums"' in karte
        # Die Liste braucht Beschreibung, Gliederung und Mittelpunkt aus /api/albums.
        r = c.post("/api/albums", json={"title": "Platzhalter-Wehr Nord", "category": "wasser",
                                        "description": "Zufahrt Platzhalterweg", "contact_org": "Platzhalter-OG"})
        assert r.status_code == 201, r.get_json()
        al = c.get("/api/albums").get_json()["albums"][0]
        for feld in ("title", "description", "contact_org", "lat", "lon", "category", "photo_count", "unlocated_count"):
            assert feld in al, feld
        assert al["lat"] is None and al["photo_count"] == 0
    print("Seiten bestanden.")


if __name__ == "__main__":
    test_b8_suche_und_liste()
    test_ft2_standort()
    test_ft4_ft5_ft8_alben_und_bilder()
    test_nur_ziffern_regel()
    test_leitstelle_b6_q2_m4()
    test_seiten_und_schnittstelle()
