"""Interaktive Einführung – Übung der Materialablage mit Produkten und Prüfformularen aus dem Katalog (Wunsch vom
04.11.2026, app/einfuehrung.py katalog_material):
python tests/test_einfuehrung_katalog.py  oder  pytest tests/test_einfuehrung_katalog.py

1. Auswahl: je Rolle (Gurt, Seil, Helm – ohne Helm ein Karabiner) das passende Produkt – nicht DEMO, ohne laufenden
   Rückruf, mit geltendem, echtem Formular (katalog.formular_fuer_produkt), Bild zuerst, sonst kleinste Kennung; dieselbe
   Auswahl bei jedem Aufruf; ohne Katalog bzw. ohne passendes Produkt der Platzhalter (null).
2. Übungsseite: STROEMIS.einfuehrung.katalog trägt nur Katalogfelder – keine Kennung, kein Artikel, keine Bestandszahl,
   keine Person, kein Journal; Prüfpunkte mit Absätzen und „optional“ wie im Formular; ohne Übung kein Katalog.
3. Sperre und CSP: Aus der Übung laden genau die Bilder der Auswahl (Web- und Vorschaufassung, nur GET); ein fremdes
   Bild, das Original, ein Herstellerdokument, eine andere Methode → gesperrt. Die CSP der Übungsseite nennt genau diese
   Bilder; die Datenbank bleibt unverändert.
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
    nur DEMO-Formular, ohne Bild). Formulare: generisch für Gurte (mit Absatz, optionalem Punkt, Zahl- und Fotopunkt),
    spezifisch für ein Seil, DEMO-spezifisch für ein anderes, generisch für Karabiner. Liefert die Kennungen."""
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
            fid = katalog.formular_anlegen(dict(ziel, titel=titel, punkte=punkte), demo=demo)
            katalog.formular_aktivieren(fid)
            return fid

        ids = {
            "gurt_ohne_bild": produkt("Gurt ohne Bild", "Gurte", "textil"),
            "gurt_demo": produkt("Gurt DEMO", "Gurte", "textil", bild=True, demo=True),
            "gurt_rueckruf": produkt("Gurt Rückruf", "Gurte", "textil", bild=True),
            "gurt": produkt("Gurt mit Bild", "Gurte", "textil", bild=True, article_no="PH-1", description="Platzhalter",
                            interval_months=12),
            "gurt_metall": produkt("Gurt Metall", "Gurte", "metall_hardware", bild=True),
            "seil_ohne_formular": produkt("Seil ohne Formular", "Seile", "textil", bild=True),
            "seil_demo_formular": produkt("Seil DEMO-Formular", "Seile", "textil", bild=True),
            "seil": produkt("Seil mit Formular", "Seile", "textil"),
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
        # Gurt: mit Bild vor ohne, DEMO und Rückruf nicht, Materialart passend; Seil: das mit (echtem) Formular; Helm: der
        # Katalog hat keine Helme – ein Karabiner.
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
        # Formulare je Produkt einmal, mit Stelle der Kategorie im Pfad (None: spezifisch); Absatz und „optional“ bleiben.
        f = a["formulare"]
        assert [x["titel"] for x in f] == ["Platzhalter Gurte", "Platzhalter Seil", "Platzhalter Karabiner"]
        assert [g["formular"], s["formular"], h["formular"]] == [0, 1, 2]
        assert f[0]["kategorie"] == 1 and f[1]["kategorie"] is None and f[0]["quelle"] == "Kategorie „Gurte“"
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
        # Die eine Stelle für das geltende Formular: Gilt für den Gurt keins mehr, nimmt die Auswahl den nächsten.
        from app.material.services import katalog
        echt = katalog.formular_fuer_produkt
        try:
            katalog.formular_fuer_produkt = lambda pid: None if pid == ids["gurt"] else echt(pid)
            assert modelle(auswahl(app))["gurt"] == "Gurt ohne Bild"
        finally:
            katalog.formular_fuer_produkt = echt
        # Ohne echtes aktives Formular: nur Platzhalter.
        with app.test_request_context():
            from app import db
            db.execute("UPDATE mat_form SET active = 0")
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


if __name__ == "__main__":
    test_auswahl()
    test_uebungsseite()
    test_sperre_und_csp()
