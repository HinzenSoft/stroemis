"""Interaktive Einführung – Übung der Materialablage mit Produkten und Prüfformularen aus dem Katalog (Wunsch vom
04.11.2026, app/einfuehrung.py katalog_material):
python tests/test_einfuehrung_katalog.py  oder  pytest tests/test_einfuehrung_katalog.py

1. Auswahl: je Rolle (Gurt, Seil, Helm – ohne Helm ein Karabiner) das passende Produkt – nicht DEMO, ohne laufenden
   Rückruf, mit geltendem Formular (katalog.formular_fuer_produkt; seit dem Formular-Pool, Schritt 38, gleich ob es das
   DEMO-Kennzeichen trägt – wie der Export), Bild zuerst, sonst kleinste Kennung; dieselbe Auswahl bei jedem Aufruf; ohne
   Katalog bzw. ohne passendes Produkt der Platzhalter (null).
2. Übungsseite: STROEMIS.einfuehrung.katalog trägt nur Katalogfelder – keine Kennung, kein Artikel, keine Bestandszahl,
   keine Person, kein Journal; Prüfpunkte mit Absätzen und „optional“ wie im Formular; ohne Übung kein Katalog.
3. Sperre und CSP: Aus der Übung laden genau die Bilder der Auswahl (Web- und Vorschaufassung, nur GET); ein fremdes
   Bild, das Original, ein Herstellerdokument, eine andere Methode → gesperrt. Die CSP der Übungsseite nennt genau diese
   Bilder; die Datenbank bleibt unverändert.
4. Nachbesserung nach der Sicherheitsprüfung vom 04.11.2026: Die Bildausnahme prüft erst Methode, Pfad, Dateiname und
   Anmeldung mit Modulzugang – ohne das rechnet keine Anfrage die Auswahl (Befund 1); die Auswahl liegt prozessweit im
   Zwischenspeicher und wird erst nach einer Änderung am Katalog oder nach Ablauf der Frist neu gerechnet. DEMO nach der
   Regel des Katalog-Exports: ein Produkt in einer DEMO-Kategorie zählt als DEMO, auch ohne eigenes Kennzeichen (Befund 4).
5. Nachtrag zum Formular-Pool: Der Schlüssel des Zwischenspeichers folgt dem Zähler mat_meta.katalog_stand – zwei
   Änderungen in derselben Sekunde (auch per SQL von Hand) rechnen jede neu, ohne dass der Test den Speicher leert.
Alle Inhalte sind Platzhalter (Hersteller „Platzhalter“, Kategorien nach den Rollen benannt)."""
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import jpeg, neues_konto, umgebung  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FELDER = {"hersteller", "modell", "beschreibung", "artikelnummer", "norm", "materialart", "kategorie", "intervall",
          "lebensdauer", "bild", "dokumente", "formular"}
SATZ = "In der Übung gesperrt – es wird nichts gespeichert."


def katalog_platzhalter(app):
    """Ein kleiner Katalog mit Platzhaltern für die Auswahl: Kategorien „Platzhalter-Ausrüstung“ mit „Gurte“, „Seile“,
    „Karabiner“ (kein „Helme“; Prüfintervall 6 Monate als Vorgabe); je Rolle Produkte, die gewählt werden sollen bzw. nicht (DEMO, Rückruf, ohne Formular,
    mit DEMO-Formular, ohne Bild). Formulare (Pool, Schritt 38): Standard für Gurte (mit Absatz, optionalem Punkt, Zahl-
    und Fotopunkt), einem Seil zugewiesen, einem anderen ein DEMO-Formular, Standard für Karabiner. Liefert die
    Kennungen."""
    from werkzeug.datastructures import FileStorage
    with app.test_request_context():
        from app import db
        from app.material.services import katalog
        k = {}
        wurzel = katalog.kategorie_anlegen({"name": "Platzhalter-Ausrüstung"})
        for name in ("Gurte", "Seile", "Karabiner"):
            k[name] = katalog.kategorie_anlegen({"name": name, "parent_id": wurzel, "default_interval_months": 6})

        def produkt(name, kat, art, bild=False, demo=False, **mehr):
            d = dict({"category_id": k[kat], "manufacturer": "Platzhalter", "model": name, "material_kind": art,
                      "norm": "Platzhalter-Norm"}, **mehr)
            if art == "textil":
                d.setdefault("lifetime_years", 10)
            pid = katalog.produkt_anlegen(d, demo=demo)
            if bild:
                katalog.produkt_bild_setzen(pid, FileStorage(stream=jpeg(), filename=f"{pid}.jpg", content_type="image/jpeg"))
            return pid

        def formular(ziel, titel, punkte, demo=False):
            if "kategorie_id" in ziel:
                kid, wem = ziel["kategorie_id"], {"kategorien": [ziel["kategorie_id"]]}
            else:
                kid, wem = katalog.produkt(ziel["produkt_id"])["category_id"], {"produkte": [ziel["produkt_id"]]}
            pf, fid = katalog.pool_anlegen({"kategorie_id": kid, "titel": titel, "punkte": punkte}, demo=demo)
            katalog.formular_aktivieren(fid)
            katalog.zuweisung_setzen(pf, wem)
            return fid

        ids = {
            "gurt_ohne_bild": produkt("Gurt ohne Bild", "Gurte", "textil"),
            "gurt_demo": produkt("Gurt DEMO", "Gurte", "textil", bild=True, demo=True),
            "gurt_rueckruf": produkt("Gurt Rückruf", "Gurte", "textil", bild=True),
            "gurt": produkt("Gurt mit Bild", "Gurte", "textil", bild=True, article_no="PH-1", description="Platzhalter",
                            interval_months=12),
            "gurt_metall": produkt("Gurt Metall", "Gurte", "metall_hardware", bild=True),
            "seil_ohne_formular": produkt("Seil ohne Formular", "Seile", "textil", bild=True),
            "seil": produkt("Seil mit Formular", "Seile", "textil"),
            # Ohne Bild und nach „Seil mit Formular“ angelegt: gewählt nur, wenn jenes kein Formular mehr hat – sein
            # DEMO-Formular zählt seit dem Formular-Pool wie ein echtes (test_auswahl).
            "seil_demo_formular": produkt("Seil DEMO-Formular", "Seile", "textil"),
            "karabiner": produkt("Karabiner", "Karabiner", "metall_hardware", bild=True),
        }
        db.execute("INSERT INTO mat_recall (product_id, title, created_at) VALUES (?, 'Platzhalter-Rückruf', ?)",
                   (ids["gurt_rueckruf"], db.now()))
        db.execute("INSERT INTO mat_product_document (product_id, kind, title, url, valid_from, uploaded_at) "
                   "VALUES (?, 'gebrauchsanleitung', 'Platzhalter-Anleitung', 'https://example.invalid/a', '2026-01-01', ?)",
                   (ids["gurt"], db.now()))
        ids["form_gurte"] = formular({"kategorie_id": k["Gurte"]}, "Platzhalter Gurte", [
            {"gruppe": "Platzhalter A", "text": "Platzhalter Ja/Nein\nmit Absatz", "art": "yesno", "soll": "nein"},
            {"gruppe": "Platzhalter A", "text": "Platzhalter optional", "art": "text", "pflicht": False},
            {"gruppe": "Platzhalter B", "text": "Platzhalter Zahl", "art": "number"},
            {"gruppe": "Platzhalter B", "text": "Platzhalter Foto", "art": "photo"}])
        ids["form_seil"] = formular({"produkt_id": ids["seil"]}, "Platzhalter Seil", [
            {"text": "Platzhalter Text", "art": "text"}, {"text": "Platzhalter Datum", "art": "date"},
            {"text": "Platzhalter Unterschrift", "art": "signature"}])
        formular({"produkt_id": ids["seil_demo_formular"]}, "Platzhalter DEMO", [{"text": "x", "art": "yesno", "soll": "ja"}],
                 demo=True)
        ids["form_karabiner"] = formular({"kategorie_id": k["Karabiner"]}, "Platzhalter Karabiner", [
            {"text": "Platzhalter Verschluss", "art": "yesno", "soll": "ja"}])
        ids["kategorien"] = k
    return ids


def pruefsumme(app):
    con = sqlite3.connect(app.config["DB_PATH"])
    try:
        return hashlib.sha256("\n".join(con.iterdump()).encode()).hexdigest()
    finally:
        con.close()


def einf(c, pfad, **kw):
    r = c.get(pfad, **kw)
    html = r.get_data(as_text=True)
    m = re.search(r"einfuehrung: (.*?), kontakt: ", html)
    assert m, (pfad, r.status_code, html[:300])
    return json.loads(m.group(1)), r, html


def auswahl(app):
    with app.test_request_context():
        from app import einfuehrung
        return einfuehrung.katalog_material()


def vergessen(app):
    with app.app_context():
        from app import einfuehrung
        einfuehrung.katalog_vergessen()


def modelle(a):
    return {r: (p["modell"] if p else None) for r, p in a["produkte"].items()}


# --- 1. Auswahl -----------------------------------------------------------------------------------------------------------

def test_auswahl():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        # Ohne Katalog: Platzhalter für jede Rolle.
        assert auswahl(app) == {"produkte": {"gurt": None, "seil": None, "helm": None}, "formulare": []}
        ids = katalog_platzhalter(app)
        a = auswahl(app)
        # Gurt: mit Bild vor ohne, DEMO und Rückruf nicht, Materialart passend; Seil: das mit Formular; Helm: der Katalog
        # hat keine Helme – ein Karabiner.
        assert modelle(a) == {"gurt": "Gurt mit Bild", "seil": "Seil mit Formular", "helm": "Karabiner"}, a
        assert a == auswahl(app), "dieselbe Auswahl bei jedem Aufruf"
        for p in a["produkte"].values():
            assert set(p) == FELDER, set(p) ^ FELDER
        g, s, h = (a["produkte"][r] for r in ("gurt", "seil", "helm"))
        assert g["kategorie"] == ["Platzhalter-Ausrüstung", "Gurte"] and g["artikelnummer"] == "PH-1"
        assert g["intervall"] == {"monate": 12, "quelle": "Produkt"} and g["lebensdauer"]["jahre"] == 10
        assert g["bild"]["web"].startswith("/media/material/web/") and g["bild"]["vorschau"].startswith("/media/material/thumb/")
        assert s["bild"] is None and s["intervall"] == {"monate": 6, "quelle": "Kategorie „Seile“"}
        assert g["dokumente"] == [{"titel": "Platzhalter-Anleitung", "art": "gebrauchsanleitung", "version": "",
                                   "gueltig_ab": "2026-01-01", "datei": False, "groesse": 0}]
        # Formulare je Produkt einmal, mit Stelle der Kategorie des Standards im Pfad (None: dem Produkt zugewiesen) und
        # der Heimat; Absatz und „optional“ bleiben.
        f = a["formulare"]
        assert [x["titel"] for x in f] == ["Platzhalter Gurte", "Platzhalter Seil", "Platzhalter Karabiner"]
        assert [g["formular"], s["formular"], h["formular"]] == [0, 1, 2]
        assert f[0]["kategorie"] == 1 and f[1]["kategorie"] is None and f[0]["quelle"] == "Standard der Kategorie „Gurte“"
        assert f[0]["heimat"] == 1 and f[1]["heimat"] == 1 and f[1]["quelle"] == "dem Produkt zugewiesen"
        assert f[0]["punkte"][0] == {"gruppe": "Platzhalter A", "text": "Platzhalter Ja/Nein\nmit Absatz", "art": "yesno",
                                     "pflicht": True, "soll": "nein"}
        assert f[0]["punkte"][1]["pflicht"] is False
        # Ein Produkt mit Helm-Kategorie geht dem Karabiner vor.
        with app.test_request_context():
            from app.material.services import katalog
            helme = katalog.kategorie_anlegen({"name": "Helme", "parent_id": ids["kategorien"]["Gurte"],
                                               "default_interval_months": 6})
            katalog.produkt_anlegen({"category_id": helme, "manufacturer": "Platzhalter", "model": "Helm",
                                     "material_kind": "sonstiges"})
        assert modelle(auswahl(app))["helm"] == "Helm"
        # Die eine Stelle für das geltende Formular: Gilt für den Gurt keins mehr, nimmt die Auswahl den nächsten. (Am
        # Katalog ändert sich dabei nichts – den Zwischenspeicher leert der Test selbst, ebenso nach SQL von Hand.)
        from app.material.services import katalog
        echt = katalog.formular_fuer_produkt
        try:
            katalog.formular_fuer_produkt = lambda pid: None if pid == ids["gurt"] else echt(pid)
            vergessen(app)
            assert modelle(auswahl(app))["gurt"] == "Gurt ohne Bild"
        finally:
            katalog.formular_fuer_produkt = echt
            vergessen(app)
        # Das DEMO-Kennzeichen eines Formulars zählt nicht (Entscheidung vom 04.11.2026, wie der Export): Gilt für das
        # Seil keins mehr, nimmt die Auswahl das Seil mit dem DEMO-Formular.
        try:
            katalog.formular_fuer_produkt = lambda pid: None if pid == ids["seil"] else echt(pid)
            vergessen(app)
            assert modelle(auswahl(app))["seil"] == "Seil DEMO-Formular"
        finally:
            katalog.formular_fuer_produkt = echt
            vergessen(app)
        # Ohne aktives Formular: nur Platzhalter.
        with app.test_request_context():
            from app import db
            db.execute("UPDATE mat_form SET active = 0")
        vergessen(app)
        assert modelle(auswahl(app)) == {"gurt": None, "seil": None, "helm": None}
    print("Auswahl bestanden.")


# --- 2. Übungsseite ---------------------------------------------------------------------------------------------------------

def test_uebungsseite():
    from test_material import gliederung, neuer_artikel
    from test_material_ueberblick import ordner_neu
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_platzhalter(app)
        gid, _ = gliederung(k["adm"], name="Platzhalter-Gliederung")
        lager = ordner_neu(k["wart"], gid, "Platzhalter-Lager")
        a = neuer_artikel(k["wart"], ids["gurt"], lager, serial_no="GEHEIM-SN-1", manufactured_on="2025-01")
        mitglied, _ = neues_konto(app, "mitglied-katalog@example.invalid", name="Mitglied Platzhalter", stufe=1)
        vorher = pruefsumme(app)
        geheim = ("GEHEIM-SN-1", a["inventory_no"], "Platzhalter-Lager", "Platzhalter-Gliederung", "fuehrung@example.org",
                  "Platzhalter-Rückruf")
        for c, pfad in ((mitglied, "/materialablage?uebung=grund"), (k["pruefer"], "/materialablage/artikel/900000012?uebung=pruefer"),
                        (k["wart"], "/materialablage/artikel/neu?ordner=900000002&uebung=materialwart"),
                        (k["katalog"], "/materialablage/katalog?uebung=verwaltung")):
            e, r, html = einf(c, pfad)
            assert r.status_code == 200 and e["uebung"], (pfad, r.status_code)
            kat = e["katalog"]
            assert modelle(kat) == {"gurt": "Gurt mit Bild", "seil": "Seil mit Formular", "helm": "Karabiner"}, pfad
            # Nur Katalogfelder: keine Kennung, keine Zahl aus dem Bestand, kein Artikel, keine Person.
            text = json.dumps(kat, ensure_ascii=False)
            for wort in ('"id"', "bestand", "artikel_gesamt", "journal", "inventory", "serial", "uploaded", "created",
                         "demo", "rueckruf"):
                assert wort not in text, (pfad, wort)
            assert not any(x in html for x in geheim), pfad
            assert "Platzhalter Ja/Nein\\nmit Absatz" in html
        # Ohne Übung kein Katalog.
        e, r, html = einf(mitglied, "/materialablage")
        assert e and not e.get("uebung") and "katalog" not in e
        assert pruefsumme(app) == vorher
    print("Übungsseite bestanden.")


# --- 3. Sperre und CSP --------------------------------------------------------------------------------------------------------

def test_sperre_und_csp():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_platzhalter(app)
        mitglied, _ = neues_konto(app, "mitglied-katalog@example.invalid", name="Mitglied Platzhalter", stufe=1)
        a = auswahl(app)
        bilder = sorted(u for p in a["produkte"].values() if p["bild"] for u in p["bild"].values())
        assert len(bilder) == 4, bilder                  # Gurt und Karabiner, je Web- und Vorschaufassung
        with app.test_request_context():
            from app.material.services import katalog
            fremd = katalog.bild_url(katalog.produkt(ids["seil_ohne_formular"])["image"])
            demo = katalog.bild_url(katalog.produkt(ids["gurt_demo"])["image"], "thumb")
            original = katalog.bild_url(katalog.produkt(ids["gurt"])["image"], "orig")
        vorher = pruefsumme(app)
        ref = {"Referer": "http://localhost/materialablage/katalog/produkt/900000021?uebung=verwaltung"}
        for kopf in (ref, {"X-Uebung": "1"}):
            for url in bilder:
                r = mitglied.get(url, headers=kopf)
                assert r.status_code == 200 and r.mimetype == "image/jpeg", (url, kopf, r.status_code)
                for methode in ("head", "post", "put", "delete"):
                    r = getattr(mitglied, methode)(url, headers=kopf)
                    assert r.status_code == 403, (methode, url, r.status_code)
            for url in (fremd, demo, original, "/media/material/dok/x.pdf", bilder[0] + "x", bilder[0].replace("/material/", "/")):
                r = mitglied.get(url, headers=kopf)
                assert r.status_code == 403 and SATZ in r.get_data(as_text=True), (url, kopf, r.status_code)
        # Ohne Übung wie immer (Modulzugang genügt für Produktbilder).
        assert mitglied.get(fremd).status_code == 200
        # Die CSP der Übungsseite nennt genau diese Bilder – sonst bleibt es bei /static/.
        r = mitglied.get("/materialablage?uebung=grund")
        csp = r.headers["Content-Security-Policy"]
        img = re.search(r"img-src ([^;]*);", csp).group(1).split()
        assert sorted(q for q in img if "/media/" in q) == [f"localhost{u}" for u in bilder], img
        assert "localhost/static/" in img and re.search(r"media-src localhost/static/ blob:;", csp), csp
        assert "/media/" not in csp.replace(re.search(r"img-src [^;]*;", csp).group(0), "")
        r = mitglied.get("/materialablage")
        assert "/media/" not in r.headers["Content-Security-Policy"]
        # Andere Module: keine Ausnahme.
        assert pruefsumme(app) == vorher
    print("Sperre und CSP bestanden.")


# --- 4. Nachbesserung nach der Sicherheitsprüfung vom 04.11.2026 -------------------------------------------------------------

def test_zwischenspeicher_und_bildausnahme():
    """Befund 1: Ohne Anmeldung, ohne Modulzugang, mit anderer Methode oder an einem anderen Pfad rechnet keine
    Übungsanfrage die Auswahl; mit Anmeldung rechnet sie einmal je Katalog-Stand – nicht je Seite und Bild."""
    import time
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_platzhalter(app)
        mitglied, _ = neues_konto(app, "mitglied-katalog@example.invalid", name="Mitglied Platzhalter", stufe=1)
        ohne_zugang, _ = neues_konto(app, "ohne-zugang@example.invalid", name="Ohne Zugang", stufe=0)
        bilder = sorted(u for p in auswahl(app)["produkte"].values() if p["bild"] for u in p["bild"].values())
        assert len(bilder) == 4, bilder
        vergessen(app)
        from app import einfuehrung
        echt, aufrufe = einfuehrung._katalog_rechnen, []

        def zaehlen():
            aufrufe.append(1)
            return echt()

        anon = app.test_client()
        ref = {"Referer": "http://localhost/materialablage?uebung=grund"}
        einfuehrung._katalog_rechnen = zaehlen
        try:
            for c in (anon, ohne_zugang):
                for kopf in ({"X-Uebung": "1"}, ref):
                    for url in bilder + ["/media/material/web/x.jpg", "/media/material/orig/x.jpg", "/media/web/x.jpg"]:
                        r = c.get(url, headers=kopf)
                        assert r.status_code == 403 and SATZ in r.get_data(as_text=True), (url, r.status_code)
            for methode in ("head", "post", "put", "delete"):
                assert getattr(mitglied, methode)(bilder[0], headers={"X-Uebung": "1"}).status_code == 403, methode
            for url in ("/media/material/web/x y.jpg", "/media/material/dok/x.pdf", "/media/material/web/"):
                assert mitglied.get(url, headers={"X-Uebung": "1"}).status_code == 403, url
            assert aufrufe == [], "Auswahl ohne Anmeldung, Zugang, mit anderer Methode oder an anderem Pfad gerechnet"
            # Zeit: ohne Anmeldung kostet die Anfrage mit X-Uebung nicht mehr als ohne (kein Rechnen; großzügige Grenze).
            def dauer(**kw):
                t = time.perf_counter()
                for _ in range(20):
                    anon.get(bilder[0], **kw)
                return (time.perf_counter() - t) / 20
            assert dauer(headers={"X-Uebung": "1"}) < dauer() * 3 + 0.01
            # Angemeldet mit Zugang: zwei Übungsseiten und alle Bilder – einmal gerechnet.
            for _ in range(2):
                e, r, _html = einf(mitglied, "/materialablage?uebung=grund")
                assert modelle(e["katalog"])["gurt"] == "Gurt mit Bild"
                for url in bilder:
                    assert mitglied.get(url, headers={"X-Uebung": "1"}).status_code == 200, url
            assert len(aufrufe) == 1, aufrufe
            # Eine Änderung über die Dienste (Standard der Gurte gelöst) rechnet sofort neu.
            pf = k["katalog"].get(f"/api/material/formulare/{ids['form_gurte']}").json["formular"]["formular_id"]
            assert k["katalog"].put(f"/api/material/formular-pool/{pf}/zuweisung",
                                    json={"kategorien": [], "produkte": []}).status_code == 200
            e, r, _html = einf(mitglied, "/materialablage?uebung=grund")
            assert len(aufrufe) == 2 and modelle(e["katalog"])["gurt"] is None, (aufrufe, modelle(e["katalog"]))
            assert mitglied.get(bilder[0], headers={"X-Uebung": "1"}).status_code in (200, 403)
            assert len(aufrufe) == 2
            # Nach Ablauf der Frist rechnet die nächste Anfrage neu, auch ohne erkannte Änderung.
            frist = einfuehrung.KATALOG_FRIST
            einfuehrung.KATALOG_FRIST = 0
            try:
                einf(mitglied, "/materialablage?uebung=grund")
            finally:
                einfuehrung.KATALOG_FRIST = frist
            assert len(aufrufe) == 3
        finally:
            einfuehrung._katalog_rechnen = echt
    print("Zwischenspeicher und Bildausnahme bestanden.")


def test_demo_kategorie():
    """Befund 4: Ein Produkt ohne eigenes Kennzeichen in einer Kategorie unter einer DEMO-Kategorie (so legt es die
    Oberfläche an) mit einem Standardformular ohne Kennzeichen – die Übung nimmt es nicht, wie der Export."""
    from werkzeug.datastructures import FileStorage
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        with app.test_request_context():
            from app.material.services import katalog
            wurzel = katalog.kategorie_anlegen({"name": "DEMO-Beispiel (Platzhalter)"}, demo=True)
            gurte = katalog.kategorie_anlegen({"name": "Gurte", "parent_id": wurzel, "default_interval_months": 6})
            # Zuerst angelegt (kleinste Kennung) und mit Bild – ohne die DEMO-Regel stünde es vorn.
            pid = katalog.produkt_anlegen({"category_id": gurte, "manufacturer": "Platzhalter", "model": "Gurt in DEMO",
                                           "material_kind": "textil", "lifetime_years": 10})
            katalog.produkt_bild_setzen(pid, FileStorage(stream=jpeg(), filename=f"{pid}.jpg", content_type="image/jpeg"))
            pf, fid = katalog.pool_anlegen({"kategorie_id": gurte, "titel": "Platzhalter DEMO-Kategorie",
                                            "punkte": [{"text": "Platzhalter", "art": "yesno", "soll": "ja"}]})
            katalog.formular_aktivieren(fid)
            katalog.zuweisung_setzen(pf, {"kategorien": [gurte]})
            assert katalog.produkt_ist_demo(katalog.produkt(pid)) and katalog.formular_ist_demo(katalog.formular(fid))
        assert modelle(auswahl(app))["gurt"] is None
        katalog_platzhalter(app)
        a = auswahl(app)
        assert modelle(a)["gurt"] == "Gurt mit Bild", modelle(a)
        assert "Platzhalter DEMO-Kategorie" not in [f["titel"] for f in a["formulare"]]
    print("DEMO-Kategorie bestanden.")


def test_zwei_aenderungen_in_einer_sekunde():
    """Nachtrag: Zwei Änderungen in derselben Sekunde – per SQL von Hand, ohne updated_at und ohne den Speicher zu leeren
    – sieht die Auswahl beide (Zähler mat_meta.katalog_stand); Lesen allein zählt nicht hoch."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_platzhalter(app)
        assert modelle(auswahl(app))["gurt"] == "Gurt mit Bild"
        with app.test_request_context():
            from app import db
            stand = db.query("SELECT wert FROM mat_meta WHERE schluessel = 'katalog_stand'", one=True)["wert"]
            auswahl(app)
            assert db.query("SELECT wert FROM mat_meta WHERE schluessel = 'katalog_stand'", one=True)["wert"] == stand
            pf = db.query("SELECT formular_id FROM mat_form WHERE id = ?", (ids["form_gurte"],), one=True)["formular_id"]
            zeile = db.query("SELECT * FROM mat_formular_zuweisung WHERE formular_id = ?", (pf,), one=True)
            # Erste Änderung: der Standard der Gurte fällt – gleich danach (dieselbe Sekunde) die zweite.
            with db.transaction():
                db.execute("DELETE FROM mat_formular_zuweisung WHERE id = ?", (zeile["id"],))
        assert modelle(auswahl(app))["gurt"] is None
        with app.test_request_context():
            from app import db
            with db.transaction():
                db.execute("INSERT INTO mat_formular_zuweisung (formular_id, category_id, created_at) VALUES (?, ?, ?)",
                           (pf, zeile["category_id"], zeile["created_at"]))
        assert modelle(auswahl(app))["gurt"] == "Gurt mit Bild"
        with app.test_request_context():
            from app import db
            with db.transaction():
                db.execute("UPDATE mat_checklist_item SET label = 'Platzhalter geändert' WHERE form_id = ? AND position = 1",
                           (ids["form_gurte"],))
        assert auswahl(app)["formulare"][0]["punkte"][0]["text"] == "Platzhalter geändert"
    print("Zwei Änderungen in einer Sekunde bestanden.")


if __name__ == "__main__":
    test_auswahl()
    test_uebungsseite()
    test_sperre_und_csp()
    test_zwischenspeicher_und_bildausnahme()
    test_demo_kategorie()
    test_zwei_aenderungen_in_einer_sekunde()
