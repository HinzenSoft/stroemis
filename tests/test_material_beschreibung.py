"""Rauchtest für die Produktbeschreibung als Zusatz hinter dem Namen (Nachbesserung vom 18.10.2026):
python tests/test_material_beschreibung.py  oder  pytest tests/test_material_beschreibung.py

Die Beschreibung eines Produkts ist ein kurzer Zusatz – etwa die Verschlussart – und steht überall direkt hinter dem
Modell vor der Artikelnummer: ohne Strich, in der Oberfläche und im PDF grau außerhalb von Link und Hervorhebung, als
Text durch ein Leerzeichen getrennt (zweiter Wunsch vom 18.10.2026: „Entferne den | und der Text der Beschreibung soll
so wie der Produktschlüssel in grau sein“). Ein Zusatz von Hand im Modellnamen („D Classic | Screwlock“) zeigt sich
genauso, der Katalog bleibt, wie er ist. Über die Oberfläche höchstens 80 Zeichen in einer Zeile: länger ist ein Fehler
mit Klartext, nie eine stille Kürzung, auch nicht für eine ältere Beschreibung. Der Katalogimport (Format 1 und 2, also
auch der Austausch dev → Produktion) übernimmt ältere, längere unverändert. Die Anzeige folgt einer Regel
(katalog.modell_teile, zusatz, produkt_teile und produktname hier, modellTeile und produktZusatz in material.js), die
Produktsuche findet auch über die Beschreibung. Sichtbar heißt das Feld seit dem Wunsch vom 18.10.2026 „Bemerkung“
(Dialog, Fehlermeldungen, Produktseite, CSV-Spalte „Bemerkung (Produkt)“, Platzhalter der Suche, Importbericht, Journal
am Produkt); Spalte description, Schnittstelle und der Schlüssel „beschreibung“ im Katalogformat bleiben, „bemerkung“
nimmt der Import gleichwertig an (test_bemerkung_heisst_so).
Alle Namen, Nummern und Texte hier sind erfunden und nur für den Test da."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, _flach, anmelden, festschreiben, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung, mails_abfangen, mails_zurueck)
from test_material_export import csv_lesen  # noqa: E402
from test_material_katalog import exportieren, importieren  # noqa: E402

# Eine ältere Beschreibung von vor der Grenze: lang und mehrzeilig – ein Platzhalter, kein echter Inhalt.
LANG = ("Platzhalter für eine ältere, lange Beschreibung aus der Zeit vor der Grenze von achtzig Zeichen, mit "
        "mehreren Sätzen.\nZweite Zeile des Platzhalters.")
FELDER = ("category_id", "manufacturer", "model", "article_no", "norm", "material_kind", "interval_months",
          "lifetime_years", "lifetime_source", "description")


def _db(app, sql, args=(), one=True):
    with app.app_context():
        from app import db
        return db.query(sql, args, one=one)


def test_laenge_beim_speichern():
    """Anlegen, Bearbeiten, Variante und Produkt aus einer Meldung: höchstens 80 Zeichen, eine Zeile. Eine ältere,
    lange Beschreibung bleibt bei einer Änderung, die sie nicht nennt; schickt der Dialog sie unverändert mit, ist das
    ein Fehler (der Dialog sagt vorher „Bitte kürzen“) – gespeichert wird nichts davon."""
    from app.material.services import meldung
    alt = mails_abfangen(meldung, lambda an, betreff, inhalt: True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            ids = katalog_grund(k["adm"])
            kp = k["katalog"]
            basis = {"category_id": ids["karabiner"], "manufacturer": "Testwerk", "material_kind": "metall_hardware",
                     "interval_months": 12}
            zahl = _db(app, "SELECT COUNT(*) AS n FROM mat_product")["n"]
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Zeta", article_no="KZ-1",
                                                            description="x" * 81))
            assert r.status_code == 400, r.get_json()
            assert "kurzer Zusatz" in r.json["error"] and "höchstens 80 Zeichen, hier sind es 81" in r.json["error"], r.json
            assert r.json["error"].startswith("Die Bemerkung ist ein kurzer Zusatz") and "Beschreibung" not in r.json["error"]
            assert _db(app, "SELECT COUNT(*) AS n FROM mat_product")["n"] == zahl
            # Genau 80 gehen; Zeilenumbrüche und doppelter Leerraum werden zu einem Leerzeichen (das Feld ist einzeilig).
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Zeta", article_no="KZ-1",
                                                            description="y" * 80))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "y" * 80, r.get_json()
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Eta", article_no="KE-1",
                                                            description="  Screwlock\n\t Alu  "))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Screwlock Alu", r.get_json()
            pid = r.json["produkt"]["id"]
            url = f"/api/material/produkte/{pid}"

            # Eine ältere, lange Beschreibung (von vor der Grenze – hier direkt in die Datenbank geschrieben).
            with app.app_context():
                from app import db
                db.execute("UPDATE mat_product SET description = ? WHERE id = ?", (LANG, pid))
            # Eine Änderung, die sie nicht nennt, lässt sie stehen.
            r = kp.put(url, json={"interval_months": 6})
            assert r.status_code == 200 and r.json["produkt"]["description"] == LANG, r.get_json()
            # Der Dialog schickt alle Felder – mit der unveränderten alten Beschreibung ist das ein Fehler, nichts
            # geändert (auch das Intervall nicht).
            p = kp.get(url).json["produkt"]
            dialog = {f: p[f] for f in FELDER}
            dialog["interval_months"] = 3
            r = kp.put(url, json=dialog)
            assert r.status_code == 400 and f"hier sind es {len(' '.join(LANG.split()))}" in r.json["error"], r.get_json()
            p = kp.get(url).json["produkt"]
            assert p["description"] == LANG and p["interval_months"] == 6, p
            # Gekürzt geht es.
            dialog["description"] = "Screwlock"
            r = kp.put(url, json=dialog)
            assert r.status_code == 200, r.get_json()
            assert r.json["produkt"]["description"] == "Screwlock" and r.json["produkt"]["interval_months"] == 3

            # Variante: dieselbe Grenze.
            r = kp.post(f"{url}/variante", json=dict(dialog, article_no="KE-2", description="z" * 81))
            assert r.status_code == 400 and "höchstens 80" in r.json["error"], r.get_json()
            r = kp.post(f"{url}/variante", json=dict(dialog, article_no="KE-2", description="Twistlock"))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Twistlock", r.get_json()

            # Produkt aus einer Meldung: ebenso – die Meldung bleibt offen, bis es klappt.
            gliederung(k["wart"])            # melden darf, wer irgendwo verwaltet
            r = k["wart"].post("/api/material/meldungen", json={"manufacturer": "Meldewerk", "model": "Karabiner Theta"},
                               headers=H)
            assert r.status_code == 201, r.get_json()
            mid = r.json["meldung"]["id"]
            d = dict(basis, manufacturer="Meldewerk", model="Karabiner Theta", description="w" * 81)
            r = kp.post(f"/api/material/meldungen/{mid}/produkt", json=d)
            assert r.status_code == 400 and "höchstens 80" in r.json["error"], r.get_json()
            assert kp.get(f"/api/material/meldungen/{mid}").json["meldung"]["status"] == "offen"
            d["description"] = "Ball-Lock"
            r = kp.post(f"/api/material/meldungen/{mid}/produkt", json=d)
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Ball-Lock", r.get_json()
    finally:
        mails_zurueck(alt)
    print("Länge beim Speichern bestanden.")


def test_import_lange_beschreibung():
    """Der Katalogimport scheitert nicht an einer langen, mehrzeiligen Beschreibung: Er übernimmt sie unverändert und
    sagt es im Bericht (ein Hinweis, kein Fehler); ein zweiter Lauf ändert nichts und meldet nichts. Der Austausch
    dev → Produktion (Katalog-Export als ZIP, Probelauf und Import in eine zweite Instanz) trägt sie ebenso unverändert."""
    katalog = {"format": "stroemis-material-katalog", "version": 1,
               "kategorien": [{"name": "Testkategorie", "materialart": "metall_hardware", "intervall_monate": 12}],
               "produkte": [{"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "Karabiner Lang",
                             "artikelnummer": "KL-1", "materialart": "metall_hardware", "beschreibung": LANG},
                            {"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "Karabiner Kurz",
                             "artikelnummer": "KK-1", "materialart": "metall_hardware", "beschreibung": "Screwlock"}]}
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app = make_app(tmp_a)
        c = anmelden(app, "admin@example.org", "geheim123")
        ber = importieren(c, json.dumps(katalog).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"] and ber["produkte"]["neu"] == 2, ber
        lang = [h for h in ber["hinweise"] if "Bemerkung" in h]
        assert len(lang) == 1 and "Karabiner Lang" in lang[0] and f"{len(LANG)} Zeichen" in lang[0], ber["hinweise"]
        assert _db(app, "SELECT description FROM mat_product WHERE model = 'Karabiner Lang'")["description"] == LANG
        # Wiederholt: unverändert, kein Hinweis.
        ber = importieren(c, json.dumps(katalog).encode(), False, "katalog.json")
        assert ber["produkte"] == {"neu": 0, "geaendert": 0, "unveraendert": 2}, ber
        assert not [h for h in ber["hinweise"] if "Bemerkung" in h], ber["hinweise"]

        # Austausch in eine zweite Instanz (Format 2): erst der Probelauf, dann der echte Lauf.
        roh = exportieren(c)
        app_b = make_app(tmp_b)
        c_b = anmelden(app_b, "admin@example.org", "geheim123")
        ber = importieren(c_b, roh, True)
        assert not ber["fehler"] and not ber["gespeichert"] and ber["produkte"]["neu"] == 2, ber
        ber = importieren(c_b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"] and ber["version"] == 2, ber
        assert any("Karabiner Lang" in h for h in ber["hinweise"]), ber["hinweise"]
        zeilen = {r["model"]: r["description"] for r in _db(app_b, "SELECT model, description FROM mat_product",
                                                            one=False)}
        assert zeilen == {"Karabiner Lang": LANG, "Karabiner Kurz": "Screwlock"}, zeilen
        # Zurück nach A: nichts zu tun.
        ber = importieren(c, exportieren(c_b), False)
        assert ber["produkte"]["geaendert"] == 0 and not ber["fehler"], ber
    print("Import mit langer Beschreibung bestanden.")


def test_bericht_und_journal_mit_zusatz():
    """Prüfung der Nachbesserung: Importbericht und Journal nennen ein Produkt wie überall „Hersteller Modell
    Beschreibung“ (ohne Strich) – zwei Varianten, die nur die Beschreibung trennt, sind im Bericht zu unterscheiden: neu
    (auch im Probelauf), geändert, als Ziel eines Formulars und in der Meldung „kein Prüfintervall mehr“; der
    Journaleintrag „als Variante angelegt“ nennt die Quelle mit ihrem Zusatz. Vorher stand zweimal „Produkt „Testwerk D
    Test“: neu“ da."""
    def katalog(zweite="Twistlock", intervall=12):
        return json.dumps({
            "format": "stroemis-material-katalog", "version": 1,
            "kategorien": [{"name": "Testkategorie", "materialart": "metall_hardware", "intervall_monate": intervall}],
            "produkte": [{"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "D Test",
                          "artikelnummer": f"DT-{i}", "materialart": "metall_hardware", "beschreibung": b}
                         for i, b in ((1, "Screwlock"), (2, zweite))],
            "formulare": [{"produkt": {"hersteller": "Testwerk", "modell": "D Test", "artikelnummer": "DT-1"},
                           "titel": "Testformular", "punkte": [{"gruppe": "Testgruppe", "text": "Testpunkt (Platzhalter)",
                                                                "art": "yesno", "soll": "ja", "kritisch": True}]}],
        }).encode()

    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        for trocken in (True, False):
            ber = importieren(c, katalog(), trocken, "katalog.json")
            assert not ber["fehler"] and ber["produkte"]["neu"] == 2, ber
            z = ber["aenderungen"]
            assert "Produkt „Testwerk D Test Screwlock“: neu" in z, z
            assert "Produkt „Testwerk D Test Twistlock“: neu" in z, z
            assert any(a.startswith("Formular „Testformular“ (Produkt „Testwerk D Test Screwlock“)") for a in z), z
            assert not [a for a in z if "|" in a], z
        ber = importieren(c, katalog(zweite="Ball-Lock"), False, "katalog.json")
        assert ber["produkte"]["geaendert"] == 1, ber
        assert [a for a in ber["aenderungen"] if a.startswith("Produkt „Testwerk D Test Ball-Lock“: geändert")], ber
        ber = importieren(c, katalog(zweite="Ball-Lock", intervall=None), True, "katalog.json")
        fehler = ber["fehler"]                             # Fehlerorte und die Meldung an der Kategorie
        assert fehler[0].startswith("produkte[0] (Testwerk D Test Screwlock): "), fehler
        assert fehler[1].startswith("produkte[1] (Testwerk D Test Ball-Lock): "), fehler
        assert ("kategorien[0] (Testkategorie): Danach hätten diese Produkte kein Prüfintervall mehr: Testwerk D Test "
                "Screwlock, Testwerk D Test Ball-Lock.") in fehler[2], fehler
        # Eine Variante über die Oberfläche: Der Journaleintrag nennt die Quelle mit ihrem Zusatz.
        pid = _db(app, "SELECT id FROM mat_product WHERE article_no = 'DT-1'")["id"]
        quelle = c.get(f"/api/material/produkte/{pid}").json["produkt"]
        stamm = {f: quelle[f] for f in FELDER}
        r = c.post(f"/api/material/produkte/{quelle['id']}/variante", headers=H,
                   json=dict(stamm, article_no="DT-3", description="Triact-Lock"))
        assert r.status_code == 201, r.get_json()
        journal = c.get(f"/api/material/produkte/{r.json['produkt']['id']}").json["produkt"]["journal"]
        eintrag = [e for e in journal if e["action"] == "variante"]
        assert len(eintrag) == 1 and eintrag[0]["nachher"]["name"] == "Testwerk D Test Screwlock", journal
    print("Bericht und Journal mit Zusatz bestanden.")


def test_demo_ohne_beschreibung():
    """Prüfung der Nachbesserung: Die DEMO-Produkte haben keine Beschreibung – den Hinweis „DEMO – nicht für echte
    Prüfungen“ trägt die DEMO-Marke, als Zusatz hinter dem Namen stand er doppelt („DEMO Gurt A | DEMO – nicht für echte
    Prüfungen“). Ein neuer Lauf des DEMO-Skripts leert ihn auch in einem älteren DEMO-Katalog; die DEMO-Gliederung
    behält ihn als Beschreibung."""
    import contextlib
    import importlib.util
    import io
    from app.material.services import katalog
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def laufen(frueher=False):
        spec = importlib.util.spec_from_file_location("material_demo_beschreibung",
                                                      os.path.join(wurzel, "scripts", "material_demo.py"))
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        if frueher:                                    # der Stand vor der Nachbesserung
            for p in modul.KATALOG["produkte"]:
                p["beschreibung"] = modul.HINWEIS
        argv, sys.argv = sys.argv, ["material_demo.py", "--demo"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                modul.main()
        finally:
            sys.argv = argv
        return modul

    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        modul = laufen(frueher=True)
        sql = "SELECT manufacturer, model, description FROM mat_product WHERE demo = 1"
        assert {z["description"] for z in _db(app, sql, one=False)} == {modul.HINWEIS}
        laufen()
        zeilen = _db(app, sql, one=False)
        # Fünf: das DEMO-Set-Produkt aus Phase 4 · L2 gibt es seit dem Rückbau (Schritt 26) nicht mehr.
        assert len(zeilen) == 5 and all(z["description"] == "" for z in zeilen), zeilen
        assert all(katalog.produktname(z) == f"{z['manufacturer']} {z['model']}" for z in zeilen), zeilen
        assert _db(app, "SELECT description FROM mat_folder WHERE name = ?", (modul.GLIEDERUNG,))["description"] \
            == modul.HINWEIS
    with tempfile.TemporaryDirectory() as tmp:                # ein frischer DEMO-Katalog ebenso
        app = make_app(tmp)
        laufen()
        assert {z["description"] for z in _db(app, "SELECT description FROM mat_product WHERE demo = 1", one=False)} \
            == {""}
    print("DEMO-Produkte ohne Beschreibung bestanden.")


def test_regel_produktname():
    """Die Regel für den Namen (katalog.modell_teile, zusatz, produkt_teile, produktname – dieselbe wie modellTeile und
    produktZusatz in material.js): ohne Beschreibung nur der Name; als Text „Modell Beschreibung“ ohne Strich, getrennt
    (produkt_teile) für die graue Ausgabe; ein Zusatz von Hand im Modellnamen („D Test | Screwlock“) gilt als Zusatz –
    angezeigt ohne Strich wie eine Beschreibung, nicht doppelt, mit einer anderen Beschreibung durch Komma getrennt;
    Leerraum und Zeilenumbrüche werden ein Leerzeichen; eine ältere, lange Beschreibung endet in einer Zeile nach
    höchstens 80 Zeichen am Wortende mit „…“."""
    from app.material.services import katalog
    assert katalog.BESCHREIBUNG_MAX == 80

    def p(modell, beschreibung):
        return {"manufacturer": "Testwerk", "model": modell, "description": beschreibung}

    def name(modell, beschreibung):
        return katalog.produktname(p(modell, beschreibung))

    assert name("D Test", "") == name("D Test", None) == "Testwerk D Test"
    assert name("D Test", "Screwlock") == "Testwerk D Test Screwlock"
    assert katalog.produkt_teile(p("D Test", "Screwlock")) == ("Testwerk D Test", "Screwlock")
    assert katalog.produkt_teile(p("D Test", "")) == ("Testwerk D Test", "")
    # Von Hand im Modellnamen: der Teil vor dem Strich ist der Name, der dahinter der Zusatz – wie eine Beschreibung.
    assert katalog.modell_teile("D Test | Screwlock") == ("D Test", ["Screwlock"])
    for modell, beschreibung in (("D Test | Screwlock", ""), ("D Test | Screwlock", " screwlock "),   # nicht doppelt
                                 ("D Test|Screwlock", None), ("D  Test |  Screwlock | ", "")):
        assert katalog.produkt_teile(p(modell, beschreibung)) == ("Testwerk D Test", "Screwlock"), modell
    assert katalog.produkt_teile(p("D Test | Screwlock", "Twistlock")) == ("Testwerk D Test", "Screwlock, Twistlock")
    assert name("D Test | Screwlock", "Twistlock") == "Testwerk D Test Screwlock, Twistlock"
    assert katalog.modell_teile("| Nur Zusatz") == ("Nur Zusatz", []) and katalog.modell_teile(None) == ("", [])
    assert name("D Test", "Screw\n  lock\tAlu") == "Testwerk D Test Screw lock Alu"
    assert katalog.produktname(p("D Test", "x"), "Ball-Lock") == "Testwerk D Test Ball-Lock"   # aus product_description
    assert katalog.produkt_teile(p("D Test", "x"), "") == ("Testwerk D Test", "")
    for modell in ("D Test", "D Test | Screwlock", "A | B | C"):
        for beschreibung in ("", "Twistlock", LANG):
            assert "|" not in name(modell, beschreibung), (modell, beschreibung)
    z = katalog.zusatz("D Test", LANG)
    flach = " ".join(LANG.split())
    assert len(z) <= 80 and z.endswith("…") and "\n" not in z, z
    assert flach.startswith(z[:-1]) and flach[len(z) - 1] == " ", z                  # am Wortende abgeschnitten
    assert katalog.zusatz("D Test", "y" * 80) == "y" * 80 and katalog.zusatz("D Test", "y" * 81) == "y" * 79 + "…"
    assert katalog.zusatz("D Test | Screwlock", LANG) == f"Screwlock, {z}"           # gekürzt wird nur die Beschreibung
    print("Regel für den Produktnamen bestanden.")


def test_darstellung():
    """Wo der Server den Produktnamen liefert oder druckt, steht der Zusatz dabei: Artikellisten (Ordner, Suche,
    offene Prüfungen) tragen die Beschreibung des Produkts, die Prüfung Name und Felder, das neue Prüfprotokoll und der
    Lebenslauf (PDF) „Hersteller Modell“ und dahinter grau die Beschreibung (im Text „Hersteller Modell Beschreibung“,
    kein Strich; das Feld „Modell“ ohne Zusatz), die CSV eine eigene Spalte „Bemerkung (Produkt)“ hinter „Modell“ (voll,
    ungekürzt; die „Bemerkung“ des Artikels weiter hinten bleibt), der Hinweis zur vergebenen Artikelnummer den Namen."""
    from app.material.services import export, pdf
    gesetzt = []                                       # das HTML jedes gesetzten PDFs, vor WeasyPrint
    setzen = pdf._setzen

    def mitschreiben(html):
        gesetzt.append(html)
        return setzen(html)
    pdf._setzen = mitschreiben
    try:
        _darstellung(export, gesetzt)
    finally:
        pdf._setzen = setzen
    print("Darstellung (Server, PDF, CSV) bestanden.")


def _darstellung(export, gesetzt):
    def zuletzt():                                     # das zuletzt gesetzte Dokument mit Artikel (nicht der Stempel)
        return next(h for h in reversed(gesetzt) if '<section class="artikel">' in h)

    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        assert kp.put(f"/api/material/produkte/{ids['hms']}", json={"description": "Twistlock"}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid, notes="Testnotiz am Artikel")
        g = neuer_artikel(w, ids["gurt"], gid, manufactured_on="2025-01")
        liste = {x["id"]: x for x in w.get(f"/api/material/ordner/{gid}").json["ordner"]["artikel"]}
        assert liste[a["id"]]["description"] == "Twistlock" and liste[g["id"]]["description"] == "", liste
        t = w.get("/api/material/suche", query_string={"q": a["inventory_no"]}).json["treffer"]
        assert t[0]["id"] == a["id"] and t[0]["description"] == "Twistlock" and t[0]["model"] == "HMS Beta", t
        pr = starten(p1, a["id"]).json["pruefung"]
        assert pr["produkt"]["name"] == "Testwerk HMS Beta Twistlock", pr["produkt"]
        assert (pr["produkt"]["model"], pr["produkt"]["description"]) == ("HMS Beta", "Twistlock"), pr["produkt"]
        offen = p1.get("/api/material/entwuerfe").json["entwuerfe"]
        assert offen[0]["artikel"]["description"] == "Twistlock", offen
        r = festschreiben(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pr["id"])["pdf_path"]))))
        assert "Testwerk HMS Beta Twistlock" in text and "Beta |" not in text, text[:600]
        # Im HTML des Protokolls: der Zusatz grau hinter dem Namen (Makro produkt_mit_zusatz), das Feld „Modell“ allein.
        html = zuletzt()
        assert '<div class="produkt">Testwerk HMS Beta <span class="zusatz">Twistlock</span></div>' in html, html[:3000]
        assert ".zusatz { color: var(--grau); font-weight: 400; }" in html
        assert '<div class="lbl">Modell</div><div class="wert">HMS Beta</div>' in html
        # Der Lebenslauf (PDF, Stand jetzt) ebenso.
        r = w.get(f"/material/artikel/{a['id']}/lebenslauf.pdf")
        assert r.status_code == 200, r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        assert "Testwerk HMS Beta Twistlock" in _flach(" ".join(pdf_seiten(pfad)))
        assert 'HMS Beta <span class="zusatz">Twistlock</span> · Status:' in zuletzt()            # Unterzeile im Kopf
        # Ein Zusatz von Hand im Modellnamen (Beschreibung leer): im PDF wie eine Beschreibung, ohne Strich; das Feld
        # „Modell“ nennt den Teil davor. Im Katalog bleibt der Modellname, wie er ist.
        r = kp.put(f"/api/material/produkte/{ids['gurt']}", json={"model": "Gurt Alpha | Platzhalter"})
        assert r.status_code == 200, r.get_json()
        r = w.get(f"/material/artikel/{g['id']}/lebenslauf.pdf")
        assert r.status_code == 200, r.status_code
        html = zuletzt()
        assert '<div class="produkt">Testwerk Gurt Alpha <span class="zusatz">Platzhalter</span></div>' in html
        # Die Änderung selbst nennt das Journal des Produkts im Lebenslauf (Entscheidung E8 vom 24.10.2026) – mit dem
        # Modellnamen, wie er im Katalog steht; Kopf und Stammdaten davor nennen ihn ohne Strich.
        kopf = html.split('<table class="liste ereignisse"')[0]
        assert '<div class="lbl">Modell</div><div class="wert">Gurt Alpha</div>' in html and "Alpha |" not in kopf
        assert "Produkt geändert" in html and "Gurt Alpha | Platzhalter" in html
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        assert "Testwerk Gurt Alpha Platzhalter" in _flach(" ".join(pdf_seiten(pfad)))
        modell = _db(app, "SELECT model FROM mat_product WHERE id = ?", (ids["gurt"],))["model"]
        assert modell == "Gurt Alpha | Platzhalter", modell
        # CSV: eigene Spalte hinter „Modell“; das Modell allein. Seit dem Wunsch vom 18.10.2026 heißt sie „Bemerkung
        # (Produkt)“ – die „Bemerkung“ des Artikels (notes) steht weiter hinten, jeder Spaltenkopf nur einmal.
        r = w.get(f"/material/export/{gid}.csv")
        assert r.status_code == 200, r.status_code
        kopf, zeilen = csv_lesen(r.data)
        assert kopf == list(export.ARTIKEL_SPALTEN) and kopf[kopf.index("Modell") + 1] == "Bemerkung (Produkt)", kopf
        assert len(set(kopf)) == len(kopf) and "Beschreibung" not in kopf, kopf
        assert kopf.index("Bemerkung") > kopf.index("Lebensende"), kopf
        z = {x["Inventarnummer"]: x for x in zeilen}
        assert z[a["inventory_no"]]["Modell"] == "HMS Beta", z
        assert z[a["inventory_no"]]["Bemerkung (Produkt)"] == "Twistlock", z
        assert z[a["inventory_no"]]["Bemerkung"] == "Testnotiz am Artikel" and z[g["inventory_no"]]["Bemerkung"] == "", z
        assert z[g["inventory_no"]]["Bemerkung (Produkt)"] == "", z
        r = kp.get("/api/material/produkte/artikelnummer", query_string={"nr": "HB-7", "hersteller": "Testwerk"})
        assert r.json["produkt"]["name"] == "Testwerk HMS Beta Twistlock", r.get_json()
        # Für den Hinweis „Schon vergeben“ auch die Teile: Die Oberfläche setzt den Zusatz grau hinter den Link
        # (Befund der Prüfung vom 18.10.2026: dort stand er noch im roten Link). Ein Zusatz von Hand kommt, wie er
        # gepflegt ist – zerlegt wird er erst in der Anzeige.
        p = r.json["produkt"]
        assert (p["manufacturer"], p["model"], p["description"]) == ("Testwerk", "HMS Beta", "Twistlock"), p
        p = kp.get("/api/material/produkte/artikelnummer", query_string={"nr": "GA-100", "hersteller": "Testwerk"}).json["produkt"]
        assert (p["name"], p["model"], p["description"]) == ("Testwerk Gurt Alpha Platzhalter",
                                                              "Gurt Alpha | Platzhalter", ""), p


def test_suche_ueber_beschreibung():
    """Die Produktsuche (Katalog, Artikel anlegen, Meldung zuordnen) findet auch über die Beschreibung – ganze und
    halbe Wörter, kurze (LIKE) wie lange (Trigrammindex), auch gemischt mit dem Modell; mit und ohne Volltextindex."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w = k["katalog"], k["wart"]
        r = kp.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                    "model": "D Classic", "article_no": "DC-1",
                                                    "material_kind": "metall_hardware", "interval_months": 12,
                                                    "description": "Screwlock"})
        assert r.status_code == 201, r.get_json()
        dc = r.json["produkt"]["id"]

        def treffer(c, q):
            r = c.get("/api/material/produkte", query_string={"q": q})
            assert r.status_code == 200, r.get_json()
            return [p["id"] for p in r.json["produkte"]]

        volltext = _db(app, "SELECT wert FROM mat_meta WHERE schluessel = 'volltext'")
        stufen = ["1", "0"] if volltext and volltext["wert"] == "1" else ["0"]
        for stufe in stufen:
            with app.app_context():
                from app import db
                db.execute("UPDATE mat_meta SET wert = ? WHERE schluessel = 'volltext'", (stufe,))
            for q in ("Screwlock", "screwl", "Classic Screwlock", "Testwerk crew", "D Screwlock DC-1"):
                assert treffer(kp, q) == [dc], (stufe, q, treffer(kp, q))
            assert dc in treffer(kp, "sc"), stufe
            assert treffer(kp, "Twistlock") == [] and treffer(kp, "Classic Twistlock") == [], stufe
            # Artikel anlegen (Materialwart) nutzt dieselbe Suche.
            assert treffer(w, "Screwlock") == [dc], stufe
    print("Suche über die Beschreibung bestanden.")


def _lesen(rel):
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, rel), encoding="utf-8") as fh:
        return fh.read()


def test_oberflaeche_statisch():
    """material.js: eine Regel für den Produktnamen (modellTeile und produktZusatz mit den Ausgaben produktName,
    nameHtml und zusatzHtml, für suche.js und global.js als window.MatProdukt) mit derselben Grenze wie der Server;
    das Feld im Produktdialog ist einzeilig wie die anderen, mit Höchstlänge, Hilfetext und dem Hinweis für ältere
    lange Beschreibungen. Listen, Seiten, Vorschläge und Steckbrief nehmen die Regel – keine eigene Verkettung von
    Hersteller und Modell mehr. Der Zusatz steht ohne Strich grau hinter dem Namen (class="muted", wie die
    Artikelnummer in der Katalogliste), außerhalb von Link und <strong>, nie fett."""
    from app.material.services import katalog
    js, suche, glob = (_lesen(f"app/material/static/{d}.js") for d in ("material", "suche", "global"))
    css = _lesen("app/material/static/material.css")
    assert f"const BESCHREIBUNG_MAX = {katalog.BESCHREIBUNG_MAX};" in js
    assert ("window.MatProdukt = { name: produktName, nameHtml, zusatzHtml, zusatz: produktZusatz, "
            "max: BESCHREIBUNG_MAX,") in js
    # Kein Strich mehr (zweiter Wunsch vom 18.10.2026: „Entferne den |“) – auch kein Wortverbinder, der ihn hielt.
    assert "&#x2060;" not in js and "| ${z.text}" not in js and "produktHtml" not in js + suche + glob
    # Der Zusatz: grau wie die Artikelnummer in der Katalogliste (muted), mit führendem Leerzeichen, voller Text einer
    # gekürzten älteren Beschreibung im title; nie fett (auch in der Überschrift und im halbfetten Steckbrief).
    assert ('return z ? ` <span class="muted mat-zusatz"${z.voll ? ` title="${esc(z.voll)}"` : ""}>'
            '${esc(z.text)}</span>` : "";') in js
    assert ".mat-zusatz { font-weight: 400; }" in css
    # Die Regel steht vor „if (!root) return;“ – suche.js und global.js finden sie auf jeder Modulseite.
    assert js.index("window.MatProdukt =") < js.index("if (!root) return;")
    # Der Dialog: ein einzeiliges Feld wie die anderen, Höchstlänge, Hilfetext, Hinweis mit dem bisherigen Text.
    feld = re.search(r'<input type="text" id="pd-desc"[^>]*>', js)
    assert feld and 'maxlength="${BESCHREIBUNG_MAX}"' in feld.group(0), feld
    assert '<textarea id="pd-desc"' not in js
    for haken in ("Kurzer Zusatz hinter dem Namen, z. B. die Verschlussart.", 'id="pd-desc-alt"', "Bitte kürzen:",
                  "if (laenge > BESCHREIBUNG_MAX)"):
        assert haken in js, haken
    # Jede Stelle mit dem Namen setzt den Zusatz dahinter – erst nach dem Schluss von Link und Hervorhebung.
    stellen = re.findall(r"\$\{nameHtml\(([^,)]+)(?:, true)?\)\}((?:</strong>|</a>)*)\$\{zusatzHtml\(([^)]+)\)\}", js)
    # 17 seit Phase 2 · L3: die Produktwahl der Nacharbeit (Bestandsimport) zeigt das gewählte Produkt ebenso; 19 seit
    # Phase 3 · L1: Kasten „Gemeldete Mängel“ der Übersicht und Karte in „Meine PSA“; 21 seit den Änderungsanträgen
    # (21.10.2026): Karte und Rückfrage „Änderung bestätigen“; 27 seit den Sets (P4-L2 O1): Stückliste der
    # Produktseite, Produktwahl im Reiter „Bestandteile“, Teilblock beim Anlegen, Teil und fehlende Position im Kasten
    # „Bestandteile“, Teil-Karte in „Meine PSA“; 28 seit dem Produktnamen als Link in Artikellisten (23.10.2026): mit
    # und ohne Link; 29 seit P4-L2 O2: Kopf der Seite „Set prüfen“; 30 seit dem Feintuning (23.10.2026): Produkt im
    # Dialog „Bearbeiten“; 31 seit den Anträgen an alle Stammdaten (24.10.2026): das feste Produkt im Antragsdialog
    # an Set und Teil; 24 seit dem Rückbau der Set-Funktion (Schritt 26): die sieben Stellen der Sets sind weg.
    assert len(stellen) == js.count("${nameHtml(") == 24, (len(stellen), js.count("${nameHtml("))
    assert all(name == zusatz for name, _, zusatz in stellen), stellen
    assert not re.search(r"\$\{zusatzHtml\([^)]*\)\}(</strong>|</a>)", js)      # nie im Link, nie in <strong>
    # Die Katalogliste wie im Bildschirmfoto: Name fett im roten Link, dann grau Zusatz und Artikelnummer.
    for stelle in ('<a href="/material/katalog/produkt/${x.id}"><strong>${nameHtml(x, true)}</strong></a>'
                   '${zusatzHtml(x)}${artNrKurz(x.article_no)}',
                   "${nameHtml(a, true)}${zusatzHtml(a)}${artNrKurz(a.article_no)}",
                   # Artikellisten (23.10.2026): der Name als roter Link auf den Artikel, Zusatz und Nummer grau dahinter.
                   '<a class="mat-produktname" href="/material/artikel/${a.id}" tabindex="-1">${nameHtml(a, true)}</a>'
                   '${zusatzHtml(a)}${artNrKurz(a.article_no)}',
                   '<h1>${nameHtml(p)}${zusatzHtml(p)} ${demoMarke(p.demo)}</h1>',
                   "<strong>${nameHtml(pr.produkt)}</strong>${zusatzHtml(pr.produkt)}${artNrHtml(",
                   '<a href="/material/katalog/produkt/${p.id}">${nameHtml(p)}</a>${zusatzHtml(p)}'
                   '${artNrHtml(p.article_no)}',
                   # Produktsuche (24.10.2026): Kategorie als Trennkopf statt in jeder Zeile.
                   '<strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${p.article_no ? ` <span class="muted"><span class="mat-ganz">${esc(p.article_no)}</span></span>` : ""}',
                   # Hinweis „Schon vergeben“ (Produkt- und Meldedialog) – bis zur Prüfung vom 18.10.2026 der ganze
                   # Name samt Zusatz im roten Link (esc(p.name)).
                   'target="_blank" rel="noopener">${nameHtml(p)}</a>${zusatzHtml(p)}${p.article_no ? ` <span class="mat-ganz">('):
        assert stelle in js, stelle
    assert 'rel="noopener">${esc(p.name)}</a>' not in js
    # Im Rückruf-Kasten der Übersicht (hellroter Grund) ein Viertel zum Textgrau hin – sonst 4,48:1, unter WCAG AA.
    assert ".mat-rr-kasten .mat-zusatz { color: color-mix(in srgb, var(--grau) 75%, var(--anthrazit)); }" in css
    for alt in ("esc(x.model", "esc(a.model", "esc(pr.produkt.name)", "const produktName = (p) =>"):
        assert alt not in js, alt
    # Vorschläge und Steckbrief: Name, dahinter der graue Zusatz, dann die Artikelnummer.
    assert ('<span class="mv-produkt">${name || "–"}${window.MatProdukt.zusatzHtml(a)}${trifft(a.article_no, q)'
            in suche) and "window.MatProdukt.nameHtml(a)" in suche and "a.model" not in suche
    assert "const p = { manufacturer: t.hersteller, model: t.modell, description: t.beschreibung };" in glob
    assert ('<p class="mg-produkt">${name || "–"}${window.MatProdukt.zusatzHtml(p)}${window.MatProdukt.artNr('
            't.artikelnummer)}</p>') in glob
    seite = _lesen("app/material/templates/material/seite.html")
    assert seite.index("material.js") < seite.index("suche.js") < seite.index("global.js")
    # „Art.-Nr. …“ und „Seriennummer …“ hinter dem Produkt als ein Stück (Gesamtprüfung: mit dem Zusatz brach die Zeile
    # sonst als „Art.-“ / „Nr. …“ oder „DEMO-K-“ / „1“) – an allen fünf Stellen über MatProdukt.artNr, keine eigene
    # Verkettung mehr; was breiter ist als die Zeile, bricht darin um (inline-block mit max-width).
    for datei in (js, suche, glob):
        assert "· Art.-Nr. ${" not in datei
    # Seit Phase 3 · L1 auch in der Karte „Meine PSA“ (artNrHtml, Seriennummer der Karte k); seit P4-L2 O1 auch in der
    # Teil-Karte eines Sets und im Kopf der Seite „Set prüfen“ (beide seit dem Rückbau, Schritt 26, weg).
    assert js.count("${artNrHtml(") == 4 and js.count('${nummerHtml("Seriennummer", a.serial_no)}') == 2
    assert js.count('${nummerHtml("Seriennummer", k.serial_no)}') == 1
    assert "window.MatProdukt.artNr(a.article_no, markiert(a.article_no, q))" in suche
    assert "window.MatProdukt.artNr(t.artikelnummer)" in glob
    assert ".mat-ganz { display: inline-block; max-width: 100%; }" in css
    # PDF: das Makro für Name und grauen Zusatz an allen drei Stellen (Artikelblock, Lebenslauf-Kopf, Sammelprotokoll).
    basis = _lesen("app/material/templates/material/pdf/basis.html")
    assert ('{{- x.produkt_name }}{% if x.produkt_zusatz %} <span class="zusatz">{{ x.produkt_zusatz }}</span>'
            '{% endif -%}') in basis and '<div class="produkt">{{ produkt_mit_zusatz(artikel) }}</div>' in basis
    lebenslauf = _lesen("app/material/templates/material/pdf/lebenslauf.html")
    assert "{{ produkt_mit_zusatz(artikel) }} · Status:" in lebenslauf
    assert '<div class="wert">{{ produkt_mit_zusatz(a) }}</div>' in _lesen(
        "app/material/templates/material/pdf/sammelprotokoll.html")
    print("Oberfläche (statisch) bestanden.")


def test_bemerkung_heisst_so():
    """Wunsch vom 18.10.2026 („Benenne ‚Beschreibung‘ in Bemerkung um.“): Sichtbar heißt das Produktfeld „Bemerkung“ –
    im Produktdialog (auch Variante und Produkt aus Meldung) samt Hinweis und Fehlermeldung, auf der Produktseite, in den
    Platzhaltern der Produktsuche, im Importbericht und im Journal am Produkt; in der CSV „Bemerkung (Produkt)“
    (test_darstellung). Wo zwei gleiche Wörter in einer Ansicht stünden, ist das andere genauer: die Bemerkung der
    Meldung im Dialog „Produkt aus Meldung anlegen“ heißt „Bemerkung des Melders“. Unverändert bleiben die Beschreibung
    von Ordnern und Rückrufen, Spalte, Schnittstelle (description) und der Schlüssel „beschreibung“ im Katalogformat;
    „bemerkung“ nimmt der Import gleichwertig an, beide mit verschiedenen Werten sind ein Fehler."""
    import shutil
    import subprocess
    from app.material.services import beschriftung, importer
    js = _lesen("app/material/static/material.js")
    # Der Produktdialog: Feld „Bemerkung“, Hinweis und Meldung vor dem Senden mit demselben Wort, kein „Beschreibung“.
    a = js.index("async function produktDialog(p, opt)")
    # Seit P4-L2 O1 stehen die Felder in „formular“ (für den Reiter „Produkt“), dialog(`…`) setzt sie ein.
    dialog = js[js.index("const formular = `", a):js.index("(dlg, body) =>", a)]
    assert '<label for="pd-desc">Bemerkung</label><input type="text" id="pd-desc"' in dialog, dialog[:2000]
    assert "Die bisherige Bemerkung hat ${beschreibung.length} Zeichen" in dialog
    assert "Beschreibung" not in dialog, dialog
    for haken in ("toast(`Die Bemerkung ist ein kurzer Zusatz hinter dem Namen – höchstens ${BESCHREIBUNG_MAX} Zeichen",
                  'zeile("Bemerkung", `<span class="mat-text">${esc(p.description)}</span>',      # Produktseite
                  'placeholder="Hersteller, Modell, Bemerkung, Artikelnummer …"',                  # Artikel anlegen
                  # Katalog: voller Text als Beschriftung und Platzhalter am Rechner (am Telefon kürzer, seit der
                  # Geräte-Prüfung vom 21.10.2026)
                  'const KAT_SUCHE = "Produkte suchen: Hersteller, Modell, Bemerkung, Artikelnummer, Norm";',
                  '${meldeDetails(m, "Bemerkung des Melders")}</div>`;'):                         # Produkt aus Meldung
        assert haken in js, haken
    for alt in ('<label for="pd-desc">Beschreibung', "Die bisherige Beschreibung", "Die Beschreibung ist ein kurzer",
                'zeile("Beschreibung"', "Modell, Beschreibung, Artikelnummer"):
        assert alt not in js, alt
    # Bleibt: die Beschreibung eines Ordners und der Platzhalter am Rückruf.
    assert '<label for="od-desc">Beschreibung</label>' in js
    assert 'placeholder="Beschreibung und Empfehlung des Herstellers"' in js

    # Journal: am Produkt „Bemerkung“, an Ordnern und in Rückrufeinträgen weiter „Beschreibung“ – Server (PDF) und
    # Oberfläche (feldName, mit Node.js, wenn es da ist) gleich.
    faelle = [({"entity": "product", "action": "geaendert"}, "Bemerkung"),
              ({"entity": "product", "action": "variante"}, "Bemerkung"),
              ({"entity": "product", "action": "rueckruf"}, "Beschreibung"),
              ({"entity": "product", "action": "rueckruf_beendet"}, "Beschreibung"),
              ({"entity": "folder", "action": "geaendert"}, "Beschreibung"),
              ({"entity": "item", "action": "geaendert"}, "Beschreibung")]
    for eintrag, erwartet in faelle:
        assert beschriftung.feld_name("description", eintrag) == erwartet, eintrag
    assert beschriftung.feld_name("notes", {"entity": "item", "action": "geaendert"}) == "Bemerkung"
    assert beschriftung.feld_name("model", {"entity": "product", "action": "geaendert"}) == "Modell"
    assert "${esc(feldName(f, j))}" in js and "esc(FELD[f] || f)" not in js
    node = shutil.which("node")
    if node:
        skript = """
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const a = js.indexOf("  const FELD = {"), b = js.indexOf("  const AKTION = {");
const feldName = new Function(js.slice(a, b) + "; return feldName;")();
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(([f, j]) => feldName(f, j))));
"""
        eingaben = [["description", e] for e, _ in faelle] + [["notes", {"entity": "item", "action": "geaendert"}],
                                                              ["model", {"entity": "product", "action": "geaendert"}]]
        wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        aus = subprocess.run([node, "-e", skript, os.path.join(wurzel, "app/material/static/material.js"),
                              json.dumps(eingaben)], capture_output=True, text=True, check=True).stdout
        assert json.loads(aus) == [w for _, w in faelle] + ["Bemerkung", "Modell"], aus

    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp = k["katalog"]
        # Fehlermeldung des Servers mit dem neuen Wort (auch „muss Text sein“).
        r = kp.put(f"/api/material/produkte/{ids['hms']}", json={"description": "x" * 81})
        assert r.status_code == 400 and r.json["error"].startswith("Die Bemerkung ist ein kurzer Zusatz"), r.get_json()
        r = kp.put(f"/api/material/produkte/{ids['hms']}", json={"description": 5})
        assert r.status_code == 400 and r.json["error"] == "„Bemerkung“ muss Text sein.", r.get_json()
        # Journal am Produkt: die Änderung heißt „Bemerkung“ – in der Schnittstelle bleibt der Schlüssel description.
        assert kp.put(f"/api/material/produkte/{ids['hms']}", json={"description": "Screwlock"}).status_code == 200
        journal = kp.get(f"/api/material/produkte/{ids['hms']}").json["produkt"]["journal"]
        eintrag = next(j for j in journal if j["action"] == "geaendert" and "description" in (j["nachher"] or {}))
        zeilen = beschriftung.journal_zeilen([eintrag])
        assert {"feld": "Bemerkung", "vorher": "–", "nachher": "Screwlock", "nur_nachher": False} \
            in zeilen[0]["felder"], zeilen

    # Katalogimport: „beschreibung“ wie bisher, „bemerkung“ gleichwertig; beide gleich geht, verschieden ist ein Fehler.
    # Bericht (Änderungsliste, Hinweis zur langen) mit dem neuen Wort; der Export schreibt weiter „beschreibung“.
    assert importer._FELDNAMEN["description"] == "Bemerkung"

    def datei(*eintraege):
        return json.dumps({"format": "stroemis-material-katalog", "version": 1,
                           "kategorien": [{"name": "Testkategorie", "materialart": "metall_hardware",
                                           "intervall_monate": 12}],
                           "produkte": [dict({"kategorie": ["Testkategorie"], "hersteller": "Testwerk",
                                              "materialart": "metall_hardware"}, **e) for e in eintraege]}).encode()
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        ber = importieren(c, datei({"modell": "D Neu", "artikelnummer": "DN-1", "bemerkung": "Screwlock"},
                                   {"modell": "D Alt", "artikelnummer": "DA-1", "beschreibung": "Twistlock"},
                                   {"modell": "D Beide", "artikelnummer": "DB-1", "beschreibung": "Ball-Lock",
                                    "bemerkung": "Ball-Lock"}), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"] and ber["produkte"]["neu"] == 3, ber
        zeilen = {r["model"]: r["description"] for r in _db(app, "SELECT model, description FROM mat_product",
                                                            one=False)}
        assert zeilen == {"D Neu": "Screwlock", "D Alt": "Twistlock", "D Beide": "Ball-Lock"}, zeilen
        assert "Produkt „Testwerk D Neu Screwlock“: neu" in ber["aenderungen"], ber["aenderungen"]
        # Verschieden: ein Fehler mit Ort, nichts gespeichert (ganz oder gar nicht).
        ber = importieren(c, datei({"modell": "D Neu", "artikelnummer": "DN-1", "bemerkung": "Twistlock",
                                    "beschreibung": "Screwlock"}), False, "katalog.json")
        assert not ber["gespeichert"] and len(ber["fehler"]) == 1, ber
        assert ber["fehler"][0].startswith("produkte[0] (Testwerk D Neu Screwlock): „beschreibung“ und „bemerkung“ "
                                           "meinen dasselbe Feld"), ber["fehler"]
        assert _db(app, "SELECT description FROM mat_product WHERE model = 'D Neu'")["description"] == "Screwlock"
        # Geändert über „bemerkung“: die Änderungsliste nennt „Bemerkung“; eine lange bekommt den Hinweis.
        ber = importieren(c, datei({"modell": "D Neu", "artikelnummer": "DN-1", "bemerkung": LANG}), False,
                          "katalog.json")
        assert ber["gespeichert"] and ber["produkte"]["geaendert"] == 1, ber
        assert [z for z in ber["aenderungen"] if z.startswith("Produkt „Testwerk D Neu ") and z.endswith(
            ": geändert (Bemerkung)")], ber["aenderungen"]
        assert [h for h in ber["hinweise"] if f"Die Bemerkung hat {len(LANG)} Zeichen" in h], ber["hinweise"]
        # (hinter dem Produktnamen – der Platzhalter LANG selbst enthält das alte Wort)
        assert not [t for t in ber["aenderungen"] + ber["hinweise"] if "Beschreibung" in t.split("“: ", 1)[1]], ber
        # Der Export bleibt beim Schlüssel „beschreibung“ – vorhandene Katalog-ZIPs und ältere Instanzen lesen ihn.
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(exportieren(c))) as z:
            produkte = json.loads(z.read("katalog.json"))["produkte"]
        neu = next(p for p in produkte if p["modell"] == "D Neu")
        assert neu["beschreibung"] == LANG and "bemerkung" not in neu, neu
    print("Bemerkung statt Beschreibung bestanden.")


def test_regel_gleich_in_material_js():
    """Die Regel in material.js liefert dasselbe wie der Server (katalog.produktname, produkt_teile) – auch für einen
    Zusatz von Hand im Modellnamen, eine ältere lange Beschreibung und maskierte Zeichen; nameHtml und zusatzHtml
    ergeben zusammen den Namen mit grauem Zusatz. Läuft mit Node.js, wenn es installiert ist (sonst übersprungen)."""
    import shutil
    import subprocess
    from app.material.services import katalog
    node = shutil.which("node")
    if not node:
        print("Regel gleich in material.js übersprungen (kein Node.js).")
        return
    faelle = [["D Classic", ""], ["D Classic", None], ["D Classic", "Screwlock"], ["D Classic | Screwlock", ""],
              ["D Classic | Screwlock", " screwlock "], ["D Classic | Screwlock", "Twistlock"],
              ["D Classic", "Screw\n  lock\tAlu"], ["A | B | C", ""], ["| Nur", ""], ["A |", "x"], ["A||B", ""],
              ["D Test", LANG], ["D Test | Screwlock", LANG], ['D <b>', 'a&b "c"'], ["D", "y" * 84]]
    skript = """
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const a = js.indexOf("  const BESCHREIBUNG_MAX"), b = js.indexOf("  /* Nummern im Fließtext");
const esc = new Function(`${fs.readFileSync(process.argv[2], "utf8").match(/const esc = .*;/)[0]} return esc;`)();
const f = new Function("esc", js.slice(a, b) + "; return { produktName, nameHtml, zusatzHtml };")(esc);
const faelle = JSON.parse(process.argv[3]);
console.log(JSON.stringify(faelle.map(([m, d]) => { const p = { manufacturer: "Testwerk", model: m, description: d };
  return [f.produktName(p), f.nameHtml(p), f.zusatzHtml(p)]; })));
"""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    aus = subprocess.run([node, "-e", skript, os.path.join(wurzel, "app/material/static/material.js"),
                          os.path.join(wurzel, "app/static/js/common.js"), json.dumps(faelle)],
                         capture_output=True, text=True, check=True).stdout

    zeichen = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}

    def escape(t):                                     # wie esc in common.js
        return re.sub("[&<>\"']", lambda m: zeichen[m[0]], t)
    for (modell, beschr), (text, name_html, zusatz_html) in zip(faelle, json.loads(aus)):
        p = {"manufacturer": "Testwerk", "model": modell, "description": beschr}
        name, zusatz = katalog.produkt_teile(p)
        assert text == katalog.produktname(p) and "|" not in text, (modell, beschr, text)
        assert name_html == escape(name), (modell, name_html)
        if zusatz:
            assert zusatz_html.startswith(' <span class="muted mat-zusatz"') and zusatz_html.endswith(
                f">{escape(zusatz)}</span>"), (modell, zusatz_html)
            assert ("title=" in zusatz_html) == (beschr == LANG or len(beschr or "") > 80), zusatz_html
        else:
            assert zusatz_html == "", (modell, zusatz_html)
    print("Regel gleich in material.js bestanden.")


if __name__ == "__main__":
    test_laenge_beim_speichern()
    test_import_lange_beschreibung()
    test_bericht_und_journal_mit_zusatz()
    test_demo_ohne_beschreibung()
    test_regel_produktname()
    test_darstellung()
    test_suche_ueber_beschreibung()
    test_oberflaeche_statisch()
    test_bemerkung_heisst_so()
    test_regel_gleich_in_material_js()
