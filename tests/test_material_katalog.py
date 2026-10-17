"""Rauchtest für den Katalogaustausch des Moduls „Material“ (Lieferung 4, ohne Browser):
python tests/test_material_katalog.py  oder  pytest tests/test_material_katalog.py

Katalog-Export als ZIP (Format 2) aus Instanz A, Import in Instanz B: Rundlauf, Wiederholung ohne Änderung,
Umbenennen und Verschieben über die Katalogkennung, Probelauf ohne jede Datei, DEMO bleibt draußen, Nebenwirkungen
auf vorhandene Artikel, Sicherheit beim ZIP (Zip-Slip, Größen, Dateitypen, kaputte Einträge), Format 1 weiter,
Rechte. Alle Namen, Hersteller und Prüfpunkte hier sind erfunden und nur für den Test da."""
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import warnings
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import H, KATALOG, PDF, anmelden, jpeg, katalog_grund, make_app, umgebung  # noqa: E402


def png(farbe=(20, 120, 200)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), farbe).save(buf, "PNG")
    return buf.getvalue()


def sha(daten):
    return hashlib.sha256(daten).hexdigest()


def hoch(c, url, inhalt, name, **felder):
    return c.post(url, data=dict(felder, file=(io.BytesIO(inhalt), name)), headers=H, content_type="multipart/form-data")


def importieren(c, inhalt, trocken, name="katalog.zip"):
    r = hoch(c, "/api/material/katalog/import", inhalt, name, trocken="1" if trocken else "0")
    assert r.status_code == 200, r.get_json()
    return r.json["bericht"]


def exportieren(c):
    r = c.get("/api/material/katalog/export")
    assert r.status_code == 200, r.get_data()[:300]
    assert r.mimetype == "application/zip"
    return r.get_data()


def dateien_zaehlen(tmp):
    """Alle Dateien unter media/material – jede abgelegte Datei zählt."""
    n = 0
    for _wurzel, _ordner, namen in os.walk(os.path.join(tmp, "media", "material")):
        n += len(namen)
    return n


def zahlen(app, *tabellen):
    with app.app_context():
        from app import db
        return {t: db.query(f"SELECT COUNT(*) AS n FROM {t}", one=True)["n"] for t in tabellen}


TABELLEN = ("mat_category", "mat_product", "mat_form", "mat_checklist_item", "mat_product_document", "mat_audit")


def quellkatalog(k):
    """Instanz A: Kategorien, zwei Produkte (eins mit Bild), Dokumente als Datei und als Link an Produkt und Kategorie,
    ein generisches (aktiv) und ein spezifisches Formular (nur Entwurf), dazu ein DEMO-Teil."""
    kp = k["katalog"]
    ids = katalog_grund(k["adm"])
    assert hoch(kp, f"/api/material/produkte/{ids['gurt']}/bild", jpeg().getvalue(), "gurt.jpg").status_code == 200
    r = hoch(kp, f"/api/material/produkte/{ids['gurt']}/dokumente", PDF + b"%alpha", "anleitung.pdf",
             kind="gebrauchsanleitung", title="Anleitung Gurt Alpha", version="03/2024", valid_from="2024-03-01")
    assert r.status_code == 201, r.get_json()
    ids["gurt_dok"] = r.json["dokument_id"]
    r = kp.post(f"/api/material/produkte/{ids['hms']}/dokumente",
                json={"kind": "datenblatt", "title": "Datenblatt HMS Beta", "version": "2",
                      "url": "https://hersteller.example/hms-beta", "valid_from": "2025-01-01"})
    assert r.status_code == 201, r.get_json()
    # Abgelöst und zurückgezogen: beides kommt nicht mit.
    r = hoch(kp, f"/api/material/produkte/{ids['hms']}/dokumente", PDF + b"%alt", "alt.pdf", kind="konformitaetserklaerung",
             title="Konformität HMS", valid_from="2023-01-01")
    alt = r.json["dokument_id"]
    r = hoch(kp, f"/api/material/dokumente/{alt}/version", PDF + b"%neu", "neu.pdf", valid_from="2025-06-01")
    assert r.status_code == 201, r.get_json()
    r = kp.post(f"/api/material/produkte/{ids['hms']}/dokumente",
                json={"kind": "sonstiges", "title": "Rückzug", "url": "https://hersteller.example/weg"})
    weg = r.json["dokument_id"]
    assert kp.post(f"/api/material/dokumente/{weg}/zurueckziehen", json={}).status_code == 200
    r = hoch(kp, f"/api/material/kategorien/{ids['gurte']}/dokumente", PDF + b"%pflege", "pflege.pdf",
             kind="pflegehinweis", title="Pflegehinweis Gurte", valid_from="2024-01-01")
    assert r.status_code == 201, r.get_json()
    # Generisch für Gurte, aktiv; spezifisch für HMS Beta nur als Entwurf (nicht aktiv).
    r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "titel": "Gurtprüfung (Test)", "punkte": [
        {"gruppe": "Testgruppe", "text": "Testpunkt Gurt", "art": "yesno", "soll": "nein", "kritisch": True},
        {"text": "Testbemerkung", "art": "text", "pflicht": False}]})
    assert r.status_code == 201, r.get_json()
    assert kp.post(f"/api/material/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200
    r = kp.post("/api/material/formulare", json={"produkt_id": ids["hms"], "titel": "HMS Beta (Entwurf)", "punkte": [
        {"text": "Testpunkt Verschluss", "art": "yesno", "soll": "ja"}]})
    assert r.status_code == 201, r.get_json()
    ids["hms_formular"] = r.json["formular"]["id"]

    # DEMO: über den Import mit Kennzeichen …
    demo = {"format": "stroemis-material-katalog", "version": 1, "demo": True,
            "kategorien": [{"name": "DEMO Testbaum", "unterkategorien": [
                {"name": "DEMO Unterbaum", "materialart": "metall_hardware", "intervall_monate": 12}]}],
            "produkte": [{"kategorie": ["DEMO Testbaum", "DEMO Unterbaum"], "hersteller": "DEMO-Testwerk",
                          "modell": "DEMO Teil", "artikelnummer": "DEMO-T-1", "materialart": "metall_hardware"},
                         {"kategorie": ["PSA gegen Absturz", "Karabiner"], "hersteller": "DEMO-Testwerk",
                          "modell": "DEMO Karabiner", "artikelnummer": "DEMO-K-9", "materialart": "metall_hardware",
                          "intervall_monate": 12}],
            "formulare": [{"kategorie": ["DEMO Testbaum", "DEMO Unterbaum"], "titel": "DEMO-Formular",
                           "punkte": [{"text": "DEMO-Prüfpunkt", "art": "yesno", "soll": "ja"}]}]}
    assert importieren(kp, json.dumps(demo).encode(), False, "demo.json")["gespeichert"]
    # … und ohne: über die Oberfläche in einer DEMO-Kategorie angelegt (trägt selbst kein Kennzeichen).
    kats = {x["name"]: x for x in kp.get("/api/material/kategorien").json["kategorien"]}
    r = kp.post("/api/material/produkte", json={"category_id": kats["DEMO Unterbaum"]["id"], "manufacturer": "Testwerk",
                                                "model": "Im DEMO-Baum", "material_kind": "metall_hardware"})
    assert r.status_code == 201, r.get_json()
    assert not r.json["produkt"]["demo"]
    assert kp.post(f"/api/material/produkte/{r.json['produkt']['id']}/dokumente",
                   json={"kind": "datenblatt", "url": "https://hersteller.example/demo"}).status_code == 201
    return ids


# --- 1. Rundlauf A → B ------------------------------------------------------------------------------

def test_rundlauf():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app_a, k = umgebung(tmp_a)
        kp = k["katalog"]
        ids = quellkatalog(k)

        # Vorschau: was mitkommt und was nicht.
        v = kp.get("/api/material/katalog/export/vorschau").json["export"]
        assert v["enthalten"] == {"kategorien": 3, "produkte": 2, "bilder": 1, "formulare": 2, "dokumente": 4}, v
        assert v["ausgelassen"]["kategorien"] == 2 and v["ausgelassen"]["produkte"] == 3, v
        assert v["ausgelassen"]["formulare"] == 1 and v["ausgelassen"]["dokumente"] == 1, v
        assert v["ausgelassen"]["ohne_kennzeichen"] == 1 and "DEMO Testbaum" in v["ausgelassen"]["namen"], v

        r = kp.get("/api/material/katalog/export")
        assert r.status_code == 200 and r.mimetype == "application/zip"
        assert "attachment" in r.headers["Content-Disposition"] and "Katalog_" in r.headers["Content-Disposition"]
        assert "no-store" in r.headers["Cache-Control"]
        roh = r.get_data()
        with zipfile.ZipFile(io.BytesIO(roh)) as z:
            namen = z.namelist()
            daten = json.loads(z.read("katalog.json"))
            assert "bericht.txt" in namen and "Ausgelassen (DEMO)" in z.read("bericht.txt").decode()
            for n in namen:                                   # jede Datei heißt nach ihrer Prüfsumme
                if n.startswith("dateien/"):
                    assert os.path.splitext(n.rsplit("/", 1)[1])[0] == sha(z.read(n)), n
        assert daten["format"] == "stroemis-material-katalog" and daten["version"] == 2
        text = json.dumps(daten, ensure_ascii=False)
        assert "DEMO" not in text and "Im DEMO-Baum" not in text and "Rückzug" not in text, text
        gurt = next(p for p in daten["produkte"] if p["modell"] == "Gurt Alpha")
        hms = next(p for p in daten["produkte"] if p["modell"] == "HMS Beta")
        assert gurt["bild"].startswith("dateien/bilder/") and len(gurt["uid"]) == 32 and gurt["kategorie_uid"]
        assert [d["titel"] for d in hms["dokumente"]] == ["Datenblatt HMS Beta", "Konformität HMS"], hms["dokumente"]
        assert hms["dokumente"][1]["gueltig_ab"] == "2025-06-01" and hms["dokumente"][0]["url"]
        psa = daten["kategorien"][0]
        assert psa["name"] == "PSA gegen Absturz" and [u["name"] for u in psa["unterkategorien"]] == ["Gurte", "Karabiner"]
        assert psa["unterkategorien"][0]["dokumente"][0]["datei"].startswith("dateien/dokumente/")
        formulare = {(f.get("kategorie_uid") or f["produkt"]["uid"]): f for f in daten["formulare"]}
        assert formulare[psa["unterkategorien"][0]["uid"]]["aktivieren"] is True
        assert formulare[hms["uid"]]["aktivieren"] is False and formulare[hms["uid"]]["titel"] == "HMS Beta (Entwurf)"

        # Instanz B, leer: Probelauf schreibt nichts – weder Datenbank noch Dateien.
        app_b = make_app(tmp_b)
        b = anmelden(app_b, "admin@example.org", "geheim123")
        vorher, dateien_vorher = zahlen(app_b, *TABELLEN), dateien_zaehlen(tmp_b)
        ber = importieren(b, roh, True)
        assert not ber["gespeichert"] and not ber["fehler"] and ber["trocken"], ber
        assert ber["kategorien"]["neu"] == 3 and ber["produkte"]["neu"] == 2 and ber["formulare"]["neu"] == 2, ber
        assert ber["bilder"]["neu"] == 1 and ber["dokumente"]["neu"] == 4, ber
        assert zahlen(app_b, *TABELLEN) == vorher and dateien_zaehlen(tmp_b) == dateien_vorher
        assert ber["herkunft"]["quelle"] == "https://strömis.de"

        # Echter Lauf: alles da, Dateien mit gleicher Prüfsumme, gleiche Kennungen.
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["bilder"]["neu"] == 1 and ber["dokumente"]["neu"] == 4, ber
        assert dateien_zaehlen(tmp_b) == dateien_vorher + 3 + 3     # Bild (orig, web, thumb) und drei PDF
        with app_b.app_context():
            from app import db
            from app.material.services import katalog
            p = db.query("SELECT * FROM mat_product WHERE uid = ?", (gurt["uid"],), one=True)
            assert p and p["model"] == "Gurt Alpha" and p["demo"] == 0
            with open(os.path.join(katalog.medien_dir(), "orig", p["image"]), "rb") as fh:
                assert sha(fh.read()) == os.path.splitext(gurt["bild"].rsplit("/", 1)[1])[0]
            assert os.path.isfile(os.path.join(katalog.medien_dir(), "thumb", os.path.splitext(p["image"])[0] + ".jpg"))
            docs = db.query("SELECT * FROM mat_product_document ORDER BY id")
            assert len(docs) == 4 and all(d["sha256"] for d in docs if d["file_path"])
            for d in docs:
                if d["file_path"]:
                    with open(os.path.join(katalog.dok_dir(), d["file_path"]), "rb") as fh:
                        assert sha(fh.read()) == d["sha256"]
            assert {r["uid"] for r in db.query("SELECT uid FROM mat_category")} == \
                {psa["uid"]} | {u["uid"] for u in psa["unterkategorien"]}
            aktiv = {(f["category_id"] or 0, f["product_id"] or 0): f["active"] for f in db.query("SELECT * FROM mat_form")}
            assert sorted(aktiv.values()) == [0, 1], aktiv
            assert db.query("SELECT COUNT(*) AS n FROM mat_audit WHERE user_name = 'Katalogimport (katalog.zip)'",
                            one=True)["n"] == 0                       # in der Anfrage: der angemeldete Nutzer
        dateien_nach = dateien_zaehlen(tmp_b)

        # Zweiter Import derselben Datei: alles unverändert, keine Datei mehr.
        ber = importieren(b, roh, False)
        assert ber["gespeichert"], ber
        for teil in ("kategorien", "produkte", "bilder"):
            assert ber[teil]["neu"] == 0 and ber[teil]["geaendert"] == 0, (teil, ber)
        assert ber["formulare"] == {"neu": 0, "unveraendert": 2} and ber["dokumente"]["unveraendert"] == 4, ber
        assert not ber["aenderungen"] and dateien_zaehlen(tmp_b) == dateien_nach

        # In A: Produkt umbenennen, Kategorie umbenennen und verschieben, neues Bild, neue Dokumentversion.
        assert kp.put(f"/api/material/produkte/{ids['gurt']}", json={"model": "Gurt Alpha II"}).status_code == 200
        assert kp.put(f"/api/material/kategorien/{ids['karabiner']}", json={"name": "Verbindungsmittel",
                                                                              "parent_id": None}).status_code == 200
        assert hoch(kp, f"/api/material/produkte/{ids['gurt']}/bild", png(), "neu.png").status_code == 200
        r = hoch(kp, f"/api/material/dokumente/{ids['gurt_dok']}/version", PDF + b"%alpha2", "anleitung2.pdf",
                 version="09/2026", valid_from="2026-09-01")
        assert r.status_code == 201, r.get_json()
        roh2 = exportieren(kp)
        with app_b.app_context():
            altes_bild = db.query("SELECT image FROM mat_product WHERE uid = ?", (gurt["uid"],), one=True)["image"]
        ber = importieren(b, roh2, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["kategorien"] == {"neu": 0, "geaendert": 1, "unveraendert": 2}, ber
        assert ber["produkte"] == {"neu": 0, "geaendert": 1, "unveraendert": 1}, ber
        assert ber["bilder"] == {"neu": 0, "geaendert": 1, "unveraendert": 0}, ber
        assert ber["dokumente"] == {"neu": 0, "neue_version": 1, "unveraendert": 3}, ber
        assert any("Verbindungsmittel" in z and "Name, Oberkategorie" in z for z in ber["aenderungen"]), ber["aenderungen"]
        with app_b.app_context():
            assert db.query("SELECT COUNT(*) AS n FROM mat_product", one=True)["n"] == 2          # keine Dublette
            assert db.query("SELECT COUNT(*) AS n FROM mat_category", one=True)["n"] == 3
            p = db.query("SELECT * FROM mat_product WHERE uid = ?", (gurt["uid"],), one=True)
            assert p["model"] == "Gurt Alpha II" and p["image"] != altes_bild
            k2 = db.query("SELECT * FROM mat_category WHERE name = 'Verbindungsmittel'", one=True)
            assert k2 and k2["parent_id"] is None
            alt = db.query("SELECT * FROM mat_product_document WHERE title = 'Anleitung Gurt Alpha' ORDER BY id", one=True)
            assert db.query("SELECT replaces_id FROM mat_product_document WHERE replaces_id = ?", (alt["id"],), one=True)
            # Das alte Bild ist weg – erst nach dem Speichern gelöscht.
            assert not os.path.exists(os.path.join(katalog.medien_dir(), "orig", altes_bild))

        # Kommandozeile: export-catalog in A, import-catalog (ZIP an „PK“ erkannt) in B.
        ziel = os.path.join(tmp_a, "export.zip")
        r = app_a.test_cli_runner().invoke(args=["material", "export-catalog", ziel])
        assert r.exit_code == 0 and "Geschrieben" in r.output and "Ausgelassen (DEMO)" in r.output, r.output
        r = app_b.test_cli_runner().invoke(args=["material", "import-catalog", ziel, "--trocken"])
        assert r.exit_code == 0 and "Trockenlauf" in r.output, r.output
        assert "Kategorien  neu 0, geaendert 0, unveraendert 3" in r.output and "Bilder      neu 0" in r.output, r.output
    print("Rundlauftest bestanden.")


# --- 2. Umbenennen und neu mit altem Namen; Nebenwirkungen in der Zielinstanz -----------------------

def test_zuordnung_und_nebenwirkungen():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app_a, ka = umgebung(tmp_a)
        app_b, kb = umgebung(tmp_b)
        ids_a = katalog_grund(ka["adm"])
        ids_b = katalog_grund(kb["adm"])                  # gleiche Namen, aber eigene Kennungen
        # In B gibt es echte Artikel der beiden Produkte.
        w = kb["wart"]
        r = w.post("/api/material/ordner", json={"name": "OG Testdorf", "kind": "gliederung"})
        gid = r.json["ordner"]["id"]
        assert w.post("/api/material/artikel", json={"product_id": ids_b["hms"], "folder_id": gid}).status_code == 201
        r = w.post("/api/material/artikel", json={"product_id": ids_b["gurt"], "folder_id": gid, "manufactured_on": "2024-01"})
        assert r.status_code == 201, r.get_json()

        # Erster Austausch: über Name und Dublette zugeordnet, die Kennungen kommen aus A.
        ber = importieren(kb["katalog"], exportieren(ka["katalog"]), False)
        assert ber["gespeichert"] and ber["kategorien"]["neu"] == 0 and ber["produkte"]["neu"] == 0, ber
        assert any("3 Kategorien und 2 Produkte" in h for h in ber["hinweise"]), ber["hinweise"]
        with app_a.app_context():
            from app import db
            uids_a = {r["name"]: r["uid"] for r in db.query("SELECT name, uid FROM mat_category")}
        with app_b.app_context():
            uids_b = {r["name"]: r["uid"] for r in db.query("SELECT name, uid FROM mat_category")}
            assert db.query("SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'category' AND after_json LIKE '%uid%'",
                            one=True)["n"] == 3
        assert uids_a == uids_b

        # In A: „Karabiner“ heißt jetzt „Karabiner alt“, und eine neue Kategorie bekommt den alten Namen.
        kp = ka["katalog"]
        assert kp.put(f"/api/material/kategorien/{ids_a['karabiner']}", json={"name": "Karabiner alt"}).status_code == 200
        assert kp.post("/api/material/kategorien", json={"name": "Karabiner", "parent_id": ids_a["psa"]}).status_code == 201
        # … und Nebenwirkungen: kürzeres Intervall und andere Lebensdauer.
        assert kp.put(f"/api/material/produkte/{ids_a['hms']}", json={"interval_months": 6}).status_code == 200
        assert kp.put(f"/api/material/produkte/{ids_a['gurt']}", json={"lifetime_years": 8}).status_code == 200
        roh = exportieren(kp)
        vorher = zahlen(app_b, "mat_item", "mat_audit")
        with app_b.app_context():
            faellig_vorher = db.query("SELECT next_due_on FROM mat_item WHERE product_id = ?", (ids_b["hms"],), one=True)
        ber = importieren(kb["katalog"], roh, True)
        assert not ber["fehler"], ber
        assert ber["kategorien"] == {"neu": 1, "geaendert": 1, "unveraendert": 2}, ber
        warn = " | ".join(ber["warnungen"])
        assert "HMS Beta" in warn and "Prüfintervall 12 → 6 Monate" in warn and "bei 1 rückt die nächste Prüfung vor" in warn, warn
        assert "Gurt Alpha" in warn and "Lebensdauer 10 → 8 Jahre" in warn and "ändert sich das Lebensende" in warn, warn
        assert zahlen(app_b, "mat_item", "mat_audit") == vorher          # der Probelauf hat nichts geschrieben
        ber = importieren(kb["katalog"], roh, False)
        assert ber["gespeichert"], ber
        with app_b.app_context():
            assert db.query("SELECT next_due_on FROM mat_item WHERE product_id = ?", (ids_b["hms"],), one=True) != faellig_vorher
            assert {r["name"] for r in db.query("SELECT name FROM mat_category")} == \
                {"PSA gegen Absturz", "Gurte", "Karabiner", "Karabiner alt"}
            alt = db.query("SELECT * FROM mat_category WHERE name = 'Karabiner alt'", one=True)
            assert alt["id"] == ids_b["karabiner"]                 # die alte, mit ihrem Produkt
            assert db.query("SELECT category_id FROM mat_product WHERE id = ?", (ids_b["hms"],), one=True)["category_id"] == alt["id"]

        # Materialart wechselt in A, in B gibt es Artikel: klarer Fehler mit Produktnamen, nichts gespeichert.
        assert kp.put(f"/api/material/produkte/{ids_a['gurt']}", json={"material_kind": "sonstiges",
                                                                       "lifetime_source": "Testangabe"}).status_code == 200
        vorher = zahlen(app_b, *TABELLEN)
        ber = importieren(kb["katalog"], exportieren(kp), False)
        assert not ber["gespeichert"] and len(ber["fehler"]) == 1, ber
        assert "Gurt Alpha" in ber["fehler"][0] and "Materialart" in ber["fehler"][0] and "1 Artikel" in ber["fehler"][0], ber
        assert zahlen(app_b, *TABELLEN) == vorher
    print("Zuordnungs- und Nebenwirkungstest bestanden.")


# --- 3. Sicherheit beim ZIP --------------------------------------------------------------------------

def _zip(eintraege, katalog=None):
    """Ein Archiv aus {Name: Inhalt}; katalog wird katalog.json."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if katalog is not None:
            z.writestr("katalog.json", json.dumps(katalog))
        for name, inhalt in eintraege.items():
            z.writestr(name, inhalt)
    return buf.getvalue()


def _verschluesselt(roh, name):
    """Das Kennzeichen „verschlüsselt“ an einem Eintrag setzen (lokaler Kopf und Inhaltsverzeichnis) – zipfile
    schreibt selbst keine verschlüsselten Einträge."""
    roh = bytearray(roh)
    with zipfile.ZipFile(io.BytesIO(bytes(roh))) as z:
        kopf = z.getinfo(name).header_offset
    roh[kopf + 6] |= 0x1
    stelle = roh.find(b"PK\x01\x02")
    while stelle >= 0:
        laenge = struct.unpack("<H", roh[stelle + 28:stelle + 30])[0]
        if roh[stelle + 46:stelle + 46 + laenge] == name.encode():
            roh[stelle + 8] |= 0x1
        stelle = roh.find(b"PK\x01\x02", stelle + 4)
    return bytes(roh)


def _katalog(bild=None, dokument=None):
    produkt = {"uid": "a" * 32, "kategorie": ["Testkategorie"], "hersteller": "Zipwerk", "modell": "Probe",
               "artikelnummer": "ZW-1", "materialart": "metall_hardware", "intervall_monate": 12}
    if bild is not None:
        produkt["bild"] = bild
    if dokument is not None:
        produkt["dokumente"] = [{"art": "datenblatt", "titel": "Testblatt", "datei": dokument}]
    return {"format": "stroemis-material-katalog", "version": 2,
            "kategorien": [{"uid": "b" * 32, "name": "Testkategorie"}], "produkte": [produkt]}


def test_zip_sicherheit():
    from app.material.services import importer
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        bild = jpeg().getvalue()
        vorher, dateien_vorher = zahlen(app, *TABELLEN), dateien_zaehlen(tmp)

        def fehler(roh, *teile):
            ber = importieren(c, roh, False)
            text = " | ".join(ber["fehler"])
            assert not ber["gespeichert"] and all(t in text for t in teile), (teile, ber)
            assert zahlen(app, *TABELLEN) == vorher and dateien_zaehlen(tmp) == dateien_vorher

        def abgewiesen(roh, teil):
            r = hoch(c, "/api/material/katalog/import", roh, "katalog.zip", trocken="0")
            assert r.status_code == 400 and teil in r.json["error"], r.get_json()
            assert zahlen(app, *TABELLEN) == vorher and dateien_zaehlen(tmp) == dateien_vorher

        # Zip-Slip: Verweise nach oben, absolut oder mit Rückstrich – auch wenn der Eintrag so im Archiv steht.
        for pfad in ("../boese.jpg", "dateien/../../boese.jpg", "/tmp/boese.jpg", "dateien\\bilder\\boese.jpg"):
            fehler(_zip({pfad: bild}, _katalog(bild=pfad)), "produkte[0].bild", "Unzulässiger Dateiverweis")
        assert not os.path.exists(os.path.join(os.path.dirname(tmp), "boese.jpg"))
        # Verweis ins Leere.
        fehler(_zip({}, _katalog(bild="dateien/bilder/fehlt.jpg")), "fehlt im Archiv")
        # Falscher Dateityp: Endung, Inhalt, kein Bild.
        fehler(_zip({"dateien/bilder/x.exe": b"MZ"}, _katalog(bild="dateien/bilder/x.exe")), "kein Foto")
        fehler(_zip({"dateien/dokumente/x.pdf": b"<html>x</html>"}, _katalog(dokument="dateien/dokumente/x.pdf")),
               "produkte[0].dokumente[0]", "passt nicht zur Endung")
        fehler(_zip({"dateien/bilder/x.jpg": b"\xff\xd8\xffkein Bild"}, _katalog(bild="dateien/bilder/x.jpg")),
               "nicht als Bild lesen")
        # Übergröße: größer als die Grenze für Bilder – und eine Packbombe (stark gepackt) als Dokument.
        fehler(_zip({"dateien/bilder/gross.jpg": b"\0" * (31 * 1024 * 1024)}, _katalog(bild="dateien/bilder/gross.jpg")),
               "größer als 30 MB")
        fehler(_zip({"dateien/dokumente/bombe.pdf": b"%PDF-" + b"\0" * (8 * 1024 * 1024)},
                    _katalog(dokument="dateien/dokumente/bombe.pdf")), "ungewöhnlich stark gepackt")
        # Verschlüsselt (Kennzeichen im Eintrag) und beschädigt (Prüfsumme stimmt nicht).
        fehler(_verschluesselt(_zip({"dateien/bilder/v.jpg": bild}, _katalog(bild="dateien/bilder/v.jpg")),
                               "dateien/bilder/v.jpg"), "verschlüsselt")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            z.writestr("katalog.json", json.dumps(_katalog(bild="dateien/bilder/k.jpg")))
            z.writestr("dateien/bilder/k.jpg", bild)
        roh = bytearray(buf.getvalue())
        stelle = roh.find(bild[200:240])
        roh[stelle] ^= 0xFF
        fehler(bytes(roh), "beschädigt")
        # Reine JSON-Datei mit Dateiverweis.
        fehler(json.dumps(_katalog(bild="dateien/bilder/x.jpg")).encode(), "reine JSON-Datei")

        # Das Archiv als Ganzes: doppelte Namen, zu viele Einträge, zu groß entpackt, ohne katalog.json, kaputt.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("katalog.json", json.dumps(_katalog()))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                z.writestr("katalog.json", json.dumps(_katalog()))
        abgewiesen(buf.getvalue(), "doppelt")
        abgewiesen(_zip({"leer.txt": b"x"}), "katalog.json")
        abgewiesen(b"PK\x03\x04kaputt", "beschädigt")
        abgewiesen(_zip({}, {"x": "y" * (6 * 1024 * 1024)}), "größer als 5 MB")
        grenzen = importer.MAX_EINTRAEGE, importer.MAX_ENTPACKT
        try:
            importer.MAX_EINTRAEGE = 3
            abgewiesen(_zip({f"f{i}": b"x" for i in range(5)}, _katalog()), "Einträge")
            importer.MAX_EINTRAEGE, importer.MAX_ENTPACKT = grenzen[0], 1024
            abgewiesen(_zip({"f": b"x" * 4096}, _katalog()), "entpackt")
        finally:
            importer.MAX_EINTRAEGE, importer.MAX_ENTPACKT = grenzen
        r = hoch(c, "/api/material/katalog/import", b"{kein json", "katalog.json", trocken="1")
        assert r.status_code == 400 and "JSON" in r.json["error"], r.get_json()
        assert c.post("/api/material/katalog/import", data={"trocken": "1"}, headers=H,
                      content_type="multipart/form-data").status_code == 400

        # Die Gegenprobe: dasselbe Archiv in Ordnung wird angenommen.
        ber = importieren(c, _zip({"dateien/bilder/ok.jpg": bild, "dateien/dokumente/ok.pdf": PDF},
                                  _katalog(bild="dateien/bilder/ok.jpg", dokument="dateien/dokumente/ok.pdf")), False)
        assert ber["gespeichert"] and ber["bilder"]["neu"] == 1 and ber["dokumente"]["neu"] == 1, ber
        # Ohne „trocken“ ist es ein Probelauf.
        r = hoch(c, "/api/material/katalog/import", _zip({}, _katalog()), "katalog.zip")
        assert r.status_code == 200 and r.json["bericht"]["trocken"] and not r.json["bericht"]["gespeichert"]
    print("ZIP-Sicherheitstest bestanden.")


# --- 4. Format 1 weiter, Format 2 als reine JSON --------------------------------------------------------

def test_format1_und_json():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        ber = importieren(c, json.dumps(KATALOG).encode(), False, "katalog.json")
        assert ber["gespeichert"] and ber["version"] == 1, ber
        assert ber["kategorien"]["neu"] == 5 and ber["produkte"]["neu"] == 2 and ber["formulare"]["neu"] == 2, ber
        ber = importieren(c, json.dumps(KATALOG).encode(), False, "katalog.json")
        assert ber["kategorien"]["unveraendert"] == 5 and ber["formulare"]["unveraendert"] == 2, ber
        # Format 2 ohne Dateien (Links) geht auch als reine JSON-Datei; eine ungültige Kennung ist ein Fehler.
        k2 = _katalog()
        k2["produkte"][0]["dokumente"] = [{"art": "datenblatt", "titel": "Online", "url": "https://hersteller.example/zw"}]
        ber = importieren(c, json.dumps(k2).encode(), False, "katalog.json")
        assert ber["gespeichert"] and ber["dokumente"]["neu"] == 1 and ber["version"] == 2, ber
        k2["produkte"][0]["uid"] = "nicht-hex"
        ber = importieren(c, json.dumps(k2).encode(), False, "katalog.json")
        assert not ber["gespeichert"] and "Katalogkennung" in ber["fehler"][0], ber
        k2["produkte"][0]["uid"] = k2["kategorien"][0]["uid"] = "c" * 32
        k2["produkte"].append(dict(k2["produkte"][0], modell="Zwilling", artikelnummer="ZW-2"))
        ber = importieren(c, json.dumps(k2).encode(), False, "katalog.json")
        assert "mehrfach" in ber["fehler"][0] and "produkte[0], produkte[1]" in ber["fehler"][0], ber
        assert importieren(c, json.dumps({"format": "stroemis-material-katalog", "version": 3}).encode(), True,
                           "x.json")["fehler"]

        # Über die Kennung: Ober- und Unterkategorie tauschen die Plätze – ohne Zyklus, ohne neue Kategorie.
        def baum(aussen, innen):
            return {"format": "stroemis-material-katalog", "version": 2, "kategorien": [
                {"uid": aussen[0], "name": aussen[1], "unterkategorien": [{"uid": innen[0], "name": innen[1]}]}]}
        ober, unter = ("d" * 32, "Tauschober"), ("e" * 32, "Tauschunter")
        assert importieren(c, json.dumps(baum(ober, unter)).encode(), False, "k.json")["kategorien"]["neu"] == 2
        ber = importieren(c, json.dumps(baum(unter, ober)).encode(), False, "k.json")
        assert ber["gespeichert"] and ber["kategorien"] == {"neu": 0, "geaendert": 2, "unveraendert": 0}, ber
        with app.app_context():
            from app import db
            k = {r["uid"]: r for r in db.query("SELECT * FROM mat_category WHERE uid IN (?, ?)", (ober[0], unter[0]))}
            assert k[unter[0]]["parent_id"] is None and k[ober[0]]["parent_id"] == k[unter[0]]["id"]
        # Eine Kategorie in ihrem eigenen Teilbaum ginge nur mit derselben Kennung zweimal – abgewiesen.
        zyklus = baum(ober, (ober[0], "Noch einmal"))
        ber = importieren(c, json.dumps(zyklus).encode(), False, "k.json")
        assert not ber["gespeichert"] and "mehrfach" in ber["fehler"][0], ber
    print("Format-1-Test bestanden.")


# --- 5. Rechte ---------------------------------------------------------------------------------------

def test_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        roh = json.dumps(KATALOG).encode()
        for rolle in ("fuehrung", "wart", "pruefer", "nutzer"):
            c = k[rolle]
            assert c.get("/api/material/katalog/export").status_code == 403, rolle
            assert c.get("/api/material/katalog/export/vorschau").status_code == 403, rolle
            assert hoch(c, "/api/material/katalog/import", roh, "k.json", trocken="1").status_code == 403, rolle
        anonym = app.test_client()
        assert anonym.get("/api/material/katalog/export").status_code == 401
        assert hoch(anonym, "/api/material/katalog/import", roh, "k.json", trocken="1").status_code == 401
        # Ohne X-Requested-With kein Upload (CSRF), auch nicht für Katalogpfleger.
        r = k["katalog"].post("/api/material/katalog/import", data={"file": (io.BytesIO(roh), "k.json")},
                              content_type="multipart/form-data")
        assert r.status_code == 403
        assert k["katalog"].get("/api/material/katalog/export").status_code == 200
        assert hoch(k["katalog"], "/api/material/katalog/import", roh, "k.json", trocken="1").status_code == 200
        assert hoch(k["adm"], "/api/material/katalog/import", roh, "k.json", trocken="1").status_code == 200
        # Die Grenze der Route steht in UPLOAD_GRENZEN (sonst gälte 1 MB).
        from app.material.routes import UPLOAD_GRENZEN
        assert UPLOAD_GRENZEN["material_api.katalog_importieren"] > 1024 ** 3
    print("Rechtetest bestanden.")


if __name__ == "__main__":
    test_rundlauf()
    test_zuordnung_und_nebenwirkungen()
    test_zip_sicherheit()
    test_format1_und_json()
    test_rechte()
