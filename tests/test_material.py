"""Rauchtest für das Modul „Material“ (ohne Browser):  python tests/test_material.py  oder  pytest tests/test_material.py

Lieferung 1 – Fundament: Migration, Rollen, Katalog mit Dokumenten und Formularen, Ordnerbaum mit
Systemordnern, Artikel mit vergebenen Nummern, Suche, Journal und Katalogimport. Alle Namen, Hersteller
und Prüfpunkte hier sind erfunden und nur für den Test da."""
import io
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

H = {"X-Requested-With": "XMLHttpRequest"}


def _heute():
    """Der Kalendertag, mit dem der Server rechnet (deutsche Zeit) – nicht der des Testrechners."""
    from app.material.services import heute
    return heute()


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def make_app(tmp):
    os.environ.update({
        "DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "https://strömis.de",
        "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123", "VIDEOPFLEGE": "0",
    })
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


def jpeg(breite=320, hoehe=240):
    buf = io.BytesIO()
    Image.new("RGB", (breite, hoehe), (200, 30, 30)).save(buf, "JPEG")
    buf.seek(0)
    return buf


def unterschrift_daten(text="T", breite=420, hoehe=160):
    """Eine gezeichnete Unterschrift als data:-URL, wie sie das Signatur-Pad liefert (PNG mit Alpha)."""
    import base64
    from PIL import ImageDraw
    bild = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
    zeichnen = ImageDraw.Draw(bild)
    zeichnen.line([(20, 120), (80, 40), (140, 110), (200, 50), (260, 115), (330, 60)], fill=(10, 20, 90, 255), width=6)
    zeichnen.text((30, 130), text, fill=(10, 20, 90, 255))
    buf = io.BytesIO()
    bild.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def unterschreiben(c):
    """Eigene Unterschrift im Profil hinterlegen – ohne sie lässt sich nichts festschreiben (Lieferung 3)."""
    r = c.put("/api/material/unterschrift", json={"bild": unterschrift_daten()})
    assert r.status_code == 200 and r.json["unterschrift"].startswith("data:image/png;base64,"), r.get_json()


def anmelden(app, mail, pw):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": mail, "password": pw})
    assert r.status_code == 200, (mail, r.get_json())
    return c


def umgebung(tmp):
    """Admin plus je ein Konto für jede Rolle des Moduls. Rollen werden über die Nutzerverwaltung
    vergeben – so ist dieser Weg mitgeprüft."""
    app = make_app(tmp)
    adm = anmelden(app, "admin@example.org", "geheim123")

    def konto(mail, **felder):
        r = adm.post("/api/admin/users", json=dict({"email": mail, "password": "passwort1", "name": mail.split("@")[0]},
                                                   **felder))
        assert r.status_code == 201, (mail, r.get_json())
        return anmelden(app, mail, "passwort1"), r.json["user"]["id"]

    k = {"adm": adm}
    k["katalog"], _ = konto("katalog@example.org", mat_katalog=True)
    k["wart"], _ = konto("wart@example.org", rechte={"material": 2})
    k["fuehrung"], _ = konto("fuehrung@example.org", rechte={"material": 1})
    k["pruefer"], k["pruefer_id"] = konto("pruefer@example.org", mat_pruefer=True, urkundennummer="1012-4711")
    k["nutzer"], _ = konto("nutzer@example.org")
    # Prüfer und Materialwart hinterlegen ihre Unterschrift: Festschreiben und Aussondern brauchen sie.
    unterschreiben(k["pruefer"])
    unterschreiben(k["wart"])
    return app, k


def katalog_grund(adm):
    """Zwei Kategorien und drei Produkte (textil, Metall, sonstiges) für die Tests."""
    r = adm.post("/api/material/kategorien", json={"name": "PSA gegen Absturz"})
    assert r.status_code == 201, r.get_json()
    psa = r.json["kategorie"]["id"]
    r = adm.post("/api/material/kategorien", json={"name": "Gurte", "parent_id": psa, "norm": "EN 361",
                                                   "default_material_kind": "textil", "default_interval_months": 12})
    assert r.status_code == 201, r.get_json()
    gurte = r.json["kategorie"]["id"]
    r = adm.post("/api/material/kategorien", json={"name": "Karabiner", "parent_id": psa, "norm": "EN 362",
                                                   "default_material_kind": "metall_hardware"})
    karabiner = r.json["kategorie"]["id"]
    r = adm.post("/api/material/produkte", json={"category_id": gurte, "manufacturer": "Testwerk", "model": "Gurt Alpha",
                                                 "article_no": "GA-100", "material_kind": "textil", "lifetime_years": 10})
    assert r.status_code == 201, r.get_json()
    gurt = r.json["produkt"]["id"]
    r = adm.post("/api/material/produkte", json={"category_id": karabiner, "manufacturer": "Testwerk",
                                                 "model": "HMS Beta", "article_no": "HB-7", "material_kind": "metall_hardware",
                                                 "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    hms = r.json["produkt"]["id"]
    return {"psa": psa, "gurte": gurte, "karabiner": karabiner, "gurt": gurt, "hms": hms}


def gliederung(c, name="OG Musterstadt"):
    r = c.post("/api/material/ordner", json={"name": name, "kind": "gliederung"})
    assert r.status_code == 201, r.get_json()
    gid = r.json["ordner"]["id"]
    baum = {o["id"]: o for o in c.get("/api/material/ordner").json["ordner"]}
    system = {o["system_kind"]: o["id"] for o in baum.values() if o["parent_id"] == gid and o["system_kind"]}
    return gid, system


# --- 1. Migration -----------------------------------------------------------------------------------

def test_migration():
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        make_app(tmp)                                   # zweiter Start: nichts doppelt, kein Fehler
        from app.material import models
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        assert models.migrieren(conn) == models.SCHEMA_VERSION
        assert models.migrieren(conn) == models.SCHEMA_VERSION          # direkt zweimal hintereinander
        meta = dict(conn.execute("SELECT schluessel, wert FROM mat_meta"))
        assert meta["schema_version"] == str(models.SCHEMA_VERSION) and meta["inventar_zaehler"] == "0", meta
        tabellen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        erwartet = {"mat_meta", "mat_category", "mat_product", "mat_product_document", "mat_form", "mat_checklist_item",
                    "mat_folder", "mat_item", "mat_inspection", "mat_inspection_result", "mat_inspection_attachment",
                    "mat_round", "mat_round_item", "mat_folder_grant", "mat_reminder_log", "mat_audit",
                    "mat_product_request", "mat_recall"}
        assert erwartet <= tabellen, erwartet - tabellen
        # Schritt 7: Kategorien und Produkte tragen eine dauerhafte Kennung für den Katalogaustausch.
        for tabelle in ("mat_category", "mat_product"):
            assert "uid" in {r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")}, tabelle
        spalten = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        assert {"recht_material", "mat_pruefer", "mat_katalog", "urkundennummer", "signature_png"} <= spalten
        # Eine Datenbank aus der Zeit vor dem Modul (ohne mat_*-Tabellen) wird beim Start ergänzt.
        for t in sorted(tabellen):
            if t.startswith("mat_") and not t.endswith(("_data", "_idx", "_config", "_docsize", "_content")):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.execute("DROP TABLE IF EXISTS mat_meta")
        conn.commit()
        assert not {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'mat_%' AND type = 'table' "
                                                "AND name NOT LIKE '%fts%'")}
        conn.close()
        make_app(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        assert erwartet <= {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == str(models.SCHEMA_VERSION)
    print("Migrationstest bestanden.")


# --- 2. Rollen und Rechte ------------------------------------------------------------------------------

def test_rollen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        # Ohne Urkundennummer keine Prüferrolle – weder beim Anlegen noch beim Ändern.
        r = adm.post("/api/admin/users", json={"email": "ohne@example.org", "password": "passwort1", "mat_pruefer": True})
        assert r.status_code == 400 and "Urkundennummer" in r.json["error"], r.get_json()
        nutzer_id = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "nutzer@example.org"][0]["id"]
        r = adm.put(f"/api/admin/users/{nutzer_id}", json={"mat_pruefer": True})
        assert r.status_code == 400 and "Urkundennummer" in r.json["error"]
        r = adm.put(f"/api/admin/users/{nutzer_id}", json={"mat_pruefer": True, "urkundennummer": "   "})
        assert r.status_code == 400
        r = adm.put(f"/api/admin/users/{k['pruefer_id']}", json={"urkundennummer": ""})        # Prüfer bleibt → 400
        assert r.status_code == 400 and "Urkundennummer" in r.json["error"]
        # Mit Urkundennummer: Prüfer – und damit mindestens Leserecht im Modul.
        r = adm.put(f"/api/admin/users/{nutzer_id}", json={"mat_pruefer": True, "urkundennummer": "1012-0815"})
        assert r.status_code == 200 and r.json["user"]["rechte"]["material"] == 1 and r.json["user"]["mat_pruefer"], r.get_json()
        # Wer das Modul ausdrücklich abschaltet, während das Kennzeichen bleibt, bekommt eine Meldung.
        r = adm.put(f"/api/admin/users/{nutzer_id}", json={"rechte": {"material": 0}})
        assert r.status_code == 400
        assert adm.put(f"/api/admin/users/{nutzer_id}", json={"mat_pruefer": False, "rechte": {"material": 0}}).status_code == 200
        # Die Rollenänderungen stehen im Journal des Moduls.
        with app.app_context():
            from app import db
            eintraege = db.query("SELECT * FROM mat_audit WHERE entity = 'user' AND entity_id = ? ORDER BY id", (nutzer_id,))
        assert [json.loads(e["after_json"]).get("mat_pruefer") for e in eintraege] == [1, 0], eintraege
        assert json.loads(eintraege[0]["after_json"])["urkundennummer"] == "1012-0815"

        # Was jede Rolle in der Oberfläche angeboten bekommt (der Server prüft trotzdem jede Aktion).
        def darf(c):
            r = c.get("/api/material/start")
            if r.status_code != 200:
                return r.status_code
            d = dict(r.json["darf"])
            assert isinstance(d.pop("uid"), int)          # eigene Kennung: „meine Prüfung“, „in Prüfung bei mir“
            return d
        assert darf(k["fuehrung"]) == {"lesen": True, "verwalten": False, "pruefen": False, "katalog": False,
                                       "urkundennummer": "", "unterschrift": False}
        assert darf(k["wart"])["verwalten"] and not darf(k["wart"])["pruefen"]
        assert darf(k["pruefer"])["pruefen"] and not darf(k["pruefer"])["verwalten"]
        assert darf(k["katalog"])["katalog"] and darf(k["katalog"])["lesen"] and not darf(k["katalog"])["verwalten"]
        # Admin: überall Materialwart und Katalogpfleger – Prüfer aber nie von selbst.
        assert darf(adm) == {"lesen": True, "verwalten": True, "pruefen": False, "katalog": True,
                             "urkundennummer": "", "unterschrift": False}
        assert darf(k["nutzer"]) == 403
        # Seiten: Modul nur mit Recht; der Reiter erscheint nur dann.
        assert k["fuehrung"].get("/material").status_code == 200
        assert 'href="/material"' in k["fuehrung"].get("/material").get_data(as_text=True)
        assert k["nutzer"].get("/material").status_code == 403
        assert 'href="/material"' not in k["nutzer"].get("/profil").get_data(as_text=True)
        r = app.test_client().get("/material")
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    print("Rollentest bestanden.")


# --- 3. Katalog: Rechte, Dubletten, Lebensdauer -------------------------------------------------------------

def test_katalog():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        neu = {"category_id": ids["karabiner"], "manufacturer": "Andere AG", "model": "Delta", "material_kind": "metall_hardware",
               "interval_months": 12}
        # Nur Admin und Produktkatalogpfleger ändern den Katalog; alle anderen bekommen 403.
        for wer in ("wart", "fuehrung", "pruefer", "nutzer"):
            c = k[wer]
            assert c.post("/api/material/produkte", json=neu).status_code == 403, wer
            assert c.put(f"/api/material/produkte/{ids['gurt']}", json={"model": "x"}).status_code == 403, wer
            assert c.post("/api/material/kategorien", json={"name": "X"}).status_code == 403, wer
            assert c.put(f"/api/material/kategorien/{ids['gurte']}", json={"norm": "x"}).status_code == 403, wer
            assert c.delete(f"/api/material/kategorien/{ids['karabiner']}", headers=H).status_code == 403, wer
            assert c.post("/api/material/formulare", json={"kategorie_id": ids["gurte"]}).status_code == 403, wer
            assert c.post(f"/api/material/produkte/{ids['gurt']}/dokumente", data={"kind": "datenblatt", "file": (io.BytesIO(PDF), "d.pdf")},
                          headers=H, content_type="multipart/form-data").status_code == 403, wer
            assert c.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "b.jpg")}, headers=H,
                          content_type="multipart/form-data").status_code == 403, wer
        r = k["katalog"].post("/api/material/produkte", json=neu)
        assert r.status_code == 201, r.get_json()
        # Lesen dürfen alle mit Zugang zum Modul, ohne Zugang niemand.
        assert k["fuehrung"].get("/api/material/produkte?q=Delta").json["gesamt"] == 1
        assert k["nutzer"].get("/api/material/produkte").status_code == 403

        # Dublette Hersteller + Modell + Artikelnummer – auch in anderer Schreibweise.
        for variante in ({"manufacturer": "Testwerk", "model": "Gurt Alpha", "article_no": "GA-100"},
                         {"manufacturer": "testwerk ", "model": "GURT-ALPHA", "article_no": "ga 100"}):
            r = k["adm"].post("/api/material/produkte", json=dict(variante, category_id=ids["gurte"], material_kind="textil",
                                                                   lifetime_years=10))
            assert r.status_code == 409 and "schon im Katalog" in r.json["error"], r.get_json()
        # „-“ als Artikelnummer zählt als keine: zweimal „ohne Nummer“ ist eine Dublette.
        assert k["adm"].post("/api/material/produkte", json=dict(neu, model="Ohne", article_no="-")).status_code == 201
        assert k["adm"].post("/api/material/produkte", json=dict(neu, model="ohne", article_no=".")).status_code == 409
        # Auch beim Ändern: Ein Produkt darf nicht zur Dublette eines anderen werden.
        r = k["adm"].put(f"/api/material/produkte/{ids['hms']}", json={"manufacturer": "Testwerk", "model": "Gurt Alpha",
                                                                       "article_no": "GA-100"})
        assert r.status_code == 409

        # Lebensdauer: Pflicht bei textil, verboten bei Metall, bei „sonstiges“ nur mit Herstellerangabe.
        textil = {"category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Gurt Gamma", "material_kind": "textil"}
        r = k["adm"].post("/api/material/produkte", json=textil)
        assert r.status_code == 400 and "Lebensdauer" in r.json["error"], r.get_json()
        r = k["adm"].post("/api/material/produkte", json=dict(neu, model="Epsilon", lifetime_years=10))
        assert r.status_code == 400 and "Metall" in r.json["error"], r.get_json()
        sonst = dict(neu, model="Helm Zeta", material_kind="sonstiges", lifetime_years=10)
        r = k["adm"].post("/api/material/produkte", json=sonst)
        assert r.status_code == 400 and "Herstellerangabe" in r.json["error"]
        r = k["adm"].post("/api/material/produkte", json=dict(sonst, lifetime_source="Gebrauchsanleitung, Abschnitt 8"))
        assert r.status_code == 201, r.get_json()
        # Auch nachträglich: Ein Metallprodukt bekommt keine Lebensdauer.
        assert k["adm"].put(f"/api/material/produkte/{ids['hms']}", json={"lifetime_years": 5}).status_code == 400
        # Ohne Intervall am Produkt und in der Kategorie gibt es kein Produkt.
        r = k["adm"].post("/api/material/produkte", json=dict(neu, model="Kein Intervall", interval_months=None))
        assert r.status_code == 400 and "Prüfintervall" in r.json["error"]
        # Lebensdauer an einer Kategorie nur bei textil.
        r = k["adm"].post("/api/material/kategorien", json={"name": "Seile", "default_lifetime_years": 10})
        assert r.status_code == 400

        # Katalogsuche serverseitig mit Seiten; „Gurt“ findet auch Teilwörter, die Kategorie filtert mit Unterkategorien.
        r = k["fuehrung"].get("/api/material/produkte?q=urt&pro_seite=1&seite=1")
        assert r.json["gesamt"] == 1 and len(r.json["produkte"]) == 1, r.get_json()
        r = k["fuehrung"].get(f"/api/material/produkte?kategorie={ids['psa']}&pro_seite=2&seite=2")
        assert r.json["gesamt"] == 5 and len(r.json["produkte"]) == 2 and r.json["seite"] == 2, r.get_json()
    print("Katalogtest bestanden.")


# --- 4. Ordnerbaum und Systemordner --------------------------------------------------------------------

def test_ordner():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, system = gliederung(w)
        assert set(system) == {"gesperrt", "ausgesondert"}, system
        for sid in system.values():
            assert w.delete(f"/api/material/ordner/{sid}", headers=H).status_code == 409
            assert w.put(f"/api/material/ordner/{sid}", json={"name": "Umbenannt"}).status_code == 409
            assert w.post(f"/api/material/ordner/{sid}/verschieben", json={"parent_id": None}).status_code == 409
            assert w.post("/api/material/ordner", json={"name": "Darin", "parent_id": sid}).status_code == 409
            r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": sid})
            assert r.status_code == 409, r.get_json()
        # Oben stehen nur Gliederungen.
        assert w.post("/api/material/ordner", json={"name": "Lose", "kind": "standort"}).status_code == 400
        r = w.post("/api/material/ordner", json={"name": "Fahrzeug GW-W", "kind": "fahrzeug", "parent_id": gid})
        assert r.status_code == 201
        fz = r.json["ordner"]["id"]
        assert w.post(f"/api/material/ordner/{fz}/verschieben", json={"parent_id": None}).status_code == 400
        assert w.post(f"/api/material/ordner/{gid}/verschieben", json={"parent_id": fz}).status_code == 400   # in sich selbst
        # Eine Gliederung bleibt eine Gliederung.
        assert w.put(f"/api/material/ordner/{gid}", json={"kind": "standort"}).status_code == 409
        # Ein Ordner, der zur Gliederung wird, bekommt seine Systemordner.
        r = w.post("/api/material/ordner", json={"name": "Bezirk", "kind": "standort", "parent_id": gid})
        bez = r.json["ordner"]["id"]
        assert w.put(f"/api/material/ordner/{bez}", json={"kind": "gliederung"}).status_code == 200
        kinder = [o for o in w.get("/api/material/ordner").json["ordner"] if o["parent_id"] == bez]
        assert sorted(o["system_kind"] for o in kinder) == ["ausgesondert", "gesperrt"]
        # Lesen ja, ändern nein: Führungskraft und Prüfer verwalten keine Ordner.
        for wer in ("fuehrung", "pruefer"):
            assert k[wer].get(f"/api/material/ordner/{gid}").status_code == 200
            assert k[wer].post("/api/material/ordner", json={"name": "X", "kind": "gliederung"}).status_code == 403
            assert k[wer].put(f"/api/material/ordner/{fz}", json={"name": "X"}).status_code == 403
        # Löschen nur leer; die Gliederung nimmt ihre leeren Systemordner mit.
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": fz})
        assert r.status_code == 201, r.get_json()
        assert w.delete(f"/api/material/ordner/{fz}", headers=H).status_code == 409
        assert w.delete(f"/api/material/artikel/{r.json['artikel']['id']}", headers=H).status_code == 200
        assert w.delete(f"/api/material/ordner/{fz}", headers=H).status_code == 200
        assert w.delete(f"/api/material/ordner/{gid}", headers=H).status_code == 409            # Bezirk liegt darin
        assert w.delete(f"/api/material/ordner/{bez}", headers=H).status_code == 200
        assert w.delete(f"/api/material/ordner/{gid}", headers=H).status_code == 200
        assert not [o for o in w.get("/api/material/ordner").json["ordner"]]
    print("Ordnertest bestanden.")


# --- 5. Artikel: Nummern, Lebensende, Fälligkeit, Verschieben ------------------------------------------------

def test_artikel():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, system = gliederung(w)
        heute = _heute()
        # Ohne Herstellernummer: eindeutige Inventar- und Seriennummer vom System.
        nummern = []
        for _ in range(3):
            r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid})
            assert r.status_code == 201, r.get_json()
            a = r.json["artikel"]
            nummern.append((a["inventory_no"], a["serial_no"], a["serial_generated"]))
        assert [n[0] for n in nummern] == ["M-000001", "M-000002", "M-000003"], nummern
        assert [n[1] for n in nummern] == ["STR-000001", "STR-000002", "STR-000003"] and all(n[2] for n in nummern)
        # Mit Herstellernummer bleibt sie; dieselbe Nummer beim selben Produkt ist eine Dublette.
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "serial_no": "HB7-0001"})
        assert r.status_code == 201 and r.json["artikel"]["serial_no"] == "HB7-0001" and not r.json["artikel"]["serial_generated"]
        hms_mit = r.json["artikel"]
        assert w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "serial_no": "hb7-0001"}).status_code == 409
        # Das Muster der vergebenen Nummern ist für Herstellernummern gesperrt.
        assert w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "serial_no": "STR-999999"}).status_code == 400
        # Eine gelöschte Inventarnummer wird nie wieder vergeben.
        assert w.delete(f"/api/material/artikel/{hms_mit['id']}", headers=H).status_code == 200
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid})
        assert r.json["artikel"]["inventory_no"] == "M-000005", r.json["artikel"]["inventory_no"]

        # retire_by nur bei textil: Herstelldatum (Monat genügt) + Lebensdauer; bei Metall leer.
        r = w.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid})
        assert r.status_code == 400 and "Herstelldatum" in r.json["error"]
        r = w.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2020-03"})
        assert r.status_code == 201 and r.json["artikel"]["retire_by"] == "2030-03-01", r.get_json()
        gurt = r.json["artikel"]
        assert gurt["lebensdauer"]["festgeschrieben"] and gurt["lebensdauer"]["jahre"] == 10
        metall = w.get(f"/api/material/artikel/{nummern and 1}").json["artikel"]
        assert metall["retire_by"] is None and metall["lebensdauer"] is None
        assert w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid,
                                                     "retire_by": "2030-01-01"}).status_code == 400
        assert w.put("/api/material/artikel/1", json={"retire_by": "2030-01-01"}).status_code == 400
        # Lebensende nur vorziehen, nie verschieben.
        r = w.put(f"/api/material/artikel/{gurt['id']}", json={"retire_by": "2031-01-01"})
        assert r.status_code == 400 and "vorziehen" in r.json["error"]
        r = w.put(f"/api/material/artikel/{gurt['id']}", json={"retire_by": "2029-06-30"})
        assert r.status_code == 200 and r.json["artikel"]["retire_by"] == "2029-06-30"
        # Eine textile Probe mit abgelaufener Lebensdauer: Status „Lebensdauer erreicht“.
        r = w.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2010-05"})
        assert r.json["artikel"]["status"] == "lebensdauer", r.json["artikel"]["status"]

        # Fälligkeit: Vorschlag = Beginn der Nutzung + Intervall; ohne Prüfung höchstens heute + Intervall;
        # danach nur vorziehen.
        erst = (heute - timedelta(days=30)).isoformat()
        v = w.get(f"/api/material/artikel/vorschlag?product_id={ids['hms']}&folder_id={gid}&first_use_on={erst}").json["vorschlag"]
        assert v["intervall"]["monate"] == 12 and v["retire_by"] is None
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "first_use_on": erst})
        a = r.json["artikel"]
        assert a["next_due_on"] == v["next_due_on"], (a["next_due_on"], v)
        zu_spaet = (heute + timedelta(days=400)).isoformat()
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "next_due_on": zu_spaet})
        assert r.status_code == 400 and "höchstens ein Intervall" in r.json["error"]
        frueher = (date.fromisoformat(a["next_due_on"]) - timedelta(days=60)).isoformat()
        r = w.put(f"/api/material/artikel/{a['id']}", json={"next_due_on": frueher})
        assert r.status_code == 200 and r.json["artikel"]["next_due_on"] == frueher
        r = w.put(f"/api/material/artikel/{a['id']}", json={"next_due_on": a["next_due_on"]})
        assert r.status_code == 400 and "vorziehen" in r.json["error"]
        # Intervall: Die Organisation kann verschärfen, nicht verlängern.
        assert w.put(f"/api/material/artikel/{a['id']}", json={"interval_months": 18}).status_code == 400
        r = w.post("/api/material/ordner", json={"name": "Fahrzeug", "kind": "fahrzeug", "parent_id": gid, "interval_months": 6})
        fz = r.json["ordner"]["id"]
        assert w.post("/api/material/artikel/verschieben", json={"ids": [a["id"]], "folder_id": fz}).status_code == 200
        iv = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["intervall"]
        assert iv["monate"] == 6 and "Fahrzeug" in iv["quelle"], iv
        assert w.put(f"/api/material/ordner/{fz}", json={"interval_months": 24}).status_code == 200
        iv = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["intervall"]
        assert iv["monate"] == 12 and iv["organisation"][0] == 24, iv

        # Mehrfachauswahl: mehrere Artikel auf einmal verschieben; nie in einen Systemordner.
        alle = [x["id"] for x in w.get(f"/api/material/ordner/{gid}").json["ordner"]["artikel"]]
        assert w.post("/api/material/artikel/verschieben", json={"ids": alle, "folder_id": system["gesperrt"]}).status_code == 409
        r = w.post("/api/material/artikel/verschieben", json={"ids": alle, "folder_id": fz})
        assert r.status_code == 200 and r.json["verschoben"] == len(alle)
        assert w.get(f"/api/material/ordner/{gid}").json["ordner"]["artikel_gesamt"] == 0
        # Ein gesperrter Artikel bleibt, wo er ist (hier von Hand gesetzt; die Sperre selbst prüft test_pruefung).
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET lock_state = 'gesperrt', folder_id = ?, origin_folder_id = ? WHERE id = ?",
                       (system["gesperrt"], fz, alle[0]))
        r = w.post("/api/material/artikel/verschieben", json={"ids": [alle[0]], "folder_id": fz})
        assert r.status_code == 409 and "Freiprüfung" in r.json["error"]
        # Nur der Materialwart legt an und verschiebt.
        for wer in ("fuehrung", "pruefer", "katalog"):
            assert k[wer].post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": fz}).status_code == 403
            assert k[wer].post("/api/material/artikel/verschieben", json={"ids": alle[1:2], "folder_id": gid}).status_code == 403
        # Die QR-Adresse führt über die Anmeldung zum Artikel.
        art = w.get(f"/api/material/artikel/{alle[1]}").json["artikel"]
        assert art["qr_adresse"].startswith("https://xn--strmis-yxa.de/m/"), art["qr_adresse"]
        token = art["qr_adresse"].rsplit("/", 1)[1]
        r = app.test_client().get(f"/m/{token}")
        assert r.status_code == 302 and "/login" in r.headers["Location"]
        r = k["fuehrung"].get(f"/m/{token}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/material/artikel/{alle[1]}")
        assert k["nutzer"].get(f"/m/{token}").status_code == 403
        assert k["fuehrung"].get("/m/gibt-es-nicht").status_code == 404
    print("Artikeltest bestanden.")


# --- 6. Suche ---------------------------------------------------------------------------------------------

def test_suche():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, _ = gliederung(w)
        for sn in ("AX-55501", "AX-55502", "QQ-777"):
            assert w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "serial_no": sn}).status_code == 201
        assert w.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2024-01"}).status_code == 201

        def treffer(c, q):
            r = c.get("/api/material/suche?q=" + q)
            assert r.status_code == 200, r.get_json()
            return sorted(t["serial_no"] for t in r.json["treffer"]), r.json["eindeutig"]

        for c in (w, k["fuehrung"]):
            assert treffer(c, "555")[0] == ["AX-55501", "AX-55502"]          # Teil der Seriennummer
            assert treffer(c, "55502") == (["AX-55502"], 2)                 # eindeutig → Kennung
            assert treffer(c, "qq")[0] == ["QQ-777"]                         # kurz: ohne Index, mit LIKE
            assert treffer(c, "M-000004")[0] == ["STR-000004"]               # Inventarnummer
            assert treffer(c, "m-4")[0] == ["STR-000004"]                    # … auch in Kurzform
            assert treffer(c, "000")[1] is None                              # Teil vieler Inventarnummern
            assert len(treffer(c, "HB-7")[0]) == 3                           # Herstellernummer (Artikelnummer)
            assert treffer(c, "B-7")[0] == ["AX-55501", "AX-55502", "QQ-777"]
        # Ein eindeutiger Treffer öffnet den Artikel direkt; sonst die Trefferliste.
        r = w.get("/material/suche?q=QQ-777")
        assert r.status_code == 302 and r.headers["Location"].endswith("/material/artikel/3"), r.headers.get("Location")
        assert w.get("/material/suche?q=AX").status_code == 200
        assert k["nutzer"].get("/api/material/suche?q=AX").status_code == 403
        # Ohne Volltextindex (altes SQLite) findet die Suche dasselbe über LIKE.
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_meta SET wert = '0' WHERE schluessel = 'volltext'")
        assert treffer(w, "555")[0] == ["AX-55501", "AX-55502"]
        assert treffer(w, "HB-7")[0] == ["AX-55501", "AX-55502", "QQ-777"] or len(treffer(w, "HB-7")[0]) == 3
        assert w.get("/api/material/produkte?q=Alpha").json["gesamt"] == 1
    print("Suchtest bestanden.")


# --- 7. Journal ------------------------------------------------------------------------------------------

def test_journal():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, _ = gliederung(w)
        r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "notes": "Neu"})
        iid = r.json["artikel"]["id"]
        assert k["katalog"].put(f"/api/material/produkte/{ids['hms']}", json={"model": "HMS Beta 2", "norm": "EN 362:2004"}).status_code == 200
        assert w.put(f"/api/material/artikel/{iid}", json={"notes": "Geändert", "serial_no": "HB7-9"}).status_code == 200
        p = k["fuehrung"].get(f"/api/material/produkte/{ids['hms']}").json["produkt"]
        e = [j for j in p["journal"] if j["action"] == "geaendert"][0]
        assert e["vorher"] == {"model": "HMS Beta", "norm": ""} and e["nachher"] == {"model": "HMS Beta 2", "norm": "EN 362:2004"}, e
        assert e["user_name"] == "katalog"
        a = k["fuehrung"].get(f"/api/material/artikel/{iid}").json["artikel"]
        aktionen = [(j["entity"], j["action"]) for j in a["journal"]]
        assert ("item", "angelegt") in aktionen and ("item", "geaendert") in aktionen and ("product", "geaendert") in aktionen, aktionen
        e = [j for j in a["journal"] if j["entity"] == "item" and j["action"] == "geaendert"][0]
        assert e["vorher"]["notes"] == "Neu" and e["nachher"]["notes"] == "Geändert"
        assert e["vorher"]["serial_no"] == "STR-000001" and e["nachher"]["serial_no"] == "HB7-9"
        assert e["nachher"]["serial_generated"] == 0 and e["user_name"] == "wart"
        # Eine Änderung ohne Unterschied schreibt keinen Eintrag.
        vorher = len(k["fuehrung"].get(f"/api/material/artikel/{iid}").json["artikel"]["journal"])
        assert w.put(f"/api/material/artikel/{iid}", json={"notes": "Geändert"}).status_code == 200
        assert len(k["fuehrung"].get(f"/api/material/artikel/{iid}").json["artikel"]["journal"]) == vorher
        # Das Journal ist unveränderlich – auch direkt in der Datenbank.
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        for sql in ("UPDATE mat_audit SET action = 'x'", "DELETE FROM mat_audit"):
            try:
                conn.execute(sql)
                raise AssertionError(sql + " ging durch")
            except sqlite3.IntegrityError as exc:
                assert "unveränderlich" in str(exc)
        conn.rollback()
        conn.close()
        # Ein gelöschtes Konto nimmt seine Einträge nicht mit – der Name bleibt stehen.
        wart_id = [u for u in k["adm"].get("/api/admin/users").json["users"] if u["email"] == "wart@example.org"][0]["id"]
        assert k["adm"].delete(f"/api/admin/users/{wart_id}", headers=H).status_code == 200
        a = k["fuehrung"].get(f"/api/material/artikel/{iid}").json["artikel"]
        assert "wart" in {j["user_name"] for j in a["journal"]}
    print("Journaltest bestanden.")


# --- 8. Formulare und Dokumente ------------------------------------------------------------------------------

def test_formulare_und_dokumente():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp = k["katalog"]
        punkte = [{"gruppe": "Kennzeichnung", "text": "Testpunkt A", "art": "yesno", "soll": "ja", "kritisch": True},
                  {"gruppe": "Zustand", "text": "Testpunkt B", "art": "yesno", "soll": "nein"},
                  {"text": "Bemerkung zum Test", "art": "text", "pflicht": False}]
        # Ja/Nein braucht einen Sollwert; kritisch kann nur ein Ja/Nein-Punkt sein.
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "punkte": [{"text": "x", "art": "yesno"}]})
        assert r.status_code == 400 and "Sollwert" in r.json["error"]
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "punkte": [{"text": "x", "art": "text", "kritisch": True}]})
        assert r.status_code == 400
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "titel": "Gurt generisch", "punkte": punkte})
        assert r.status_code == 201, r.get_json()
        generisch = r.json["formular"]
        assert generisch["version"] == 1 and not generisch["aktiv"] and len(generisch["punkte"]) == 3
        assert kp.post(f"/api/material/formulare/{generisch['id']}/aktivieren", json={}).status_code == 200
        # Gilt für jedes Produkt der Kategorie – bis ein spezifisches das generische ersetzt.
        p = kp.get(f"/api/material/produkte/{ids['gurt']}").json["produkt"]
        assert p["formular"]["id"] == generisch["id"] and "Gurte" in p["formular"]["quelle"], p["formular"]
        r = kp.post("/api/material/formulare", json={"produkt_id": ids["gurt"], "titel": "Gurt Alpha spezifisch",
                                                     "punkte": punkte[:1]})
        spezifisch = r.json["formular"]
        assert kp.post(f"/api/material/formulare/{spezifisch['id']}/aktivieren", json={}).status_code == 200
        p = kp.get(f"/api/material/produkte/{ids['gurt']}").json["produkt"]
        assert p["formular"]["id"] == spezifisch["id"] and p["formular"]["quelle"] == "Produkt"
        assert kp.post(f"/api/material/formulare/{spezifisch['id']}/deaktivieren", json={}).status_code == 200
        assert kp.get(f"/api/material/produkte/{ids['gurt']}").json["produkt"]["formular"]["id"] == generisch["id"]
        # Neue Version übernimmt die Punkte; Aktivieren löst die alte ab – höchstens eine aktiv.
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"]})
        v2 = r.json["formular"]
        assert v2["version"] == 2 and [x["text"] for x in v2["punkte"]] == ["Testpunkt A", "Testpunkt B", "Bemerkung zum Test"]
        assert kp.post(f"/api/material/formulare/{v2['id']}/aktivieren", json={}).status_code == 200
        versionen = kp.get(f"/api/material/formulare?kategorie={ids['gurte']}").json["formulare"]
        assert [(f["version"], f["aktiv"]) for f in versionen] == [(2, True), (1, False)]
        # Eine benutzte Version bleibt unverändert; geändert wird über eine neue.
        with app.app_context():
            from app import db
            db.execute("INSERT INTO mat_folder (name, kind, created_at, updated_at) VALUES ('G', 'gliederung', 'x', 'x')")
            db.execute("INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, qr_token, created_at, updated_at) "
                       "VALUES (?, 1, 'S', 'M-999999', 't', 'x', 'x')", (ids["hms"],))
            db.execute("INSERT INTO mat_inspection (item_id, form_id, form_version, inspected_on, kind, created_at, updated_at) "
                       "VALUES (1, ?, 2, '2026-10-01', 'periodisch', 'x', 'x')", (v2["id"],))
        r = kp.put(f"/api/material/formulare/{v2['id']}", json={"titel": "geändert"})
        assert r.status_code == 409 and "neue Version" in r.json["error"]
        assert kp.delete(f"/api/material/formulare/{v2['id']}", headers=H).status_code == 409
        assert kp.get(f"/api/material/formulare/{v2['id']}").json["formular"]["benutzt"] is True
        assert kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"]}).json["formular"]["version"] == 3
        # Unbenutzt und inaktiv: löschbar; die Formularpflege steht im Journal.
        assert kp.delete(f"/api/material/formulare/{generisch['id']}", headers=H).status_code == 200
        journal = kp.get(f"/api/material/formulare/{v2['id']}").json["formular"]["journal"]
        assert [j["action"] for j in journal][-2:] == ["aktiviert", "angelegt"], journal

        # Herstellerdokumente: PDF hochladen, neue Version, zurückziehen – am Produkt, für alle Artikel.
        def hoch(url, inhalt, name, **felder):
            return kp.post(url, data=dict(felder, file=(io.BytesIO(inhalt), name)), headers=H, content_type="multipart/form-data")
        r = hoch(f"/api/material/produkte/{ids['gurt']}/dokumente", PDF, "anleitung.pdf", kind="gebrauchsanleitung",
                 version="03/2024", valid_from="2024-03-01")
        assert r.status_code == 201, r.get_json()
        d1 = r.json["dokumente"][0]
        assert d1["gilt"] and d1["sha256"] and d1["datei"].startswith("/media/material/dok/")
        assert hoch(f"/api/material/produkte/{ids['gurt']}/dokumente", b"<html>x</html>", "boese.pdf", kind="datenblatt").status_code == 400
        assert hoch(f"/api/material/produkte/{ids['gurt']}/dokumente", b"MZ", "x.exe", kind="datenblatt").status_code == 400
        r = hoch(f"/api/material/dokumente/{d1['id']}/version", PDF + b"%v2", "anleitung-v2.pdf", version="09/2026")
        assert r.status_code == 201, r.get_json()
        docs = {d["id"]: d for d in r.json["dokumente"]}
        neu_id = r.json["dokument_id"]
        assert docs[neu_id]["gilt"] and not docs[d1["id"]]["gilt"] and docs[d1["id"]]["abgeloest_durch"] == neu_id
        assert docs[neu_id]["kind"] == "gebrauchsanleitung" and docs[neu_id]["title"] == "anleitung"
        assert hoch(f"/api/material/dokumente/{d1['id']}/version", PDF, "x.pdf").status_code == 409   # nur die neueste ersetzen
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/dokumente", json={"kind": "datenblatt", "title": "Online",
                                                                             "url": "https://hersteller.example/blatt"})
        assert r.status_code == 201
        url_doc = [d for d in r.json["dokumente"] if d["url"]][0]
        assert kp.post(f"/api/material/dokumente/{url_doc['id']}/zurueckziehen", json={}).status_code == 200
        assert kp.post(f"/api/material/dokumente/{url_doc['id']}/zurueckziehen", json={}).status_code == 409
        # Das am Prüftag gültige Dokument (für Protokolle): vor der neuen Version die alte.
        with app.app_context():
            from app.material.services import katalog
            alt = katalog.gueltige_dokumente(ids["gurt"], "2025-01-01")
            assert [d["id"] for d in alt] == [d1["id"]], alt
        # Auslieferung nur mit Zugang zum Modul.
        assert k["fuehrung"].get(docs[neu_id]["datei"]).status_code == 200
        assert k["fuehrung"].get(docs[neu_id]["datei"]).headers["Content-Security-Policy"].startswith("default-src 'none'")
        assert k["nutzer"].get(docs[neu_id]["datei"]).status_code == 403
        assert app.test_client().get(docs[neu_id]["datei"]).status_code in (302, 401)
        # Produktbild über die vorhandene Pipeline (Web- und Vorschaufassung).
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["produkt"]["vorschau"].endswith(".jpg"), r.get_json()
        assert k["fuehrung"].get(r.json["produkt"]["vorschau"]).status_code == 200
        assert kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (io.BytesIO(PDF), "x.pdf")}, headers=H,
                       content_type="multipart/form-data").status_code == 400
        # Die Vorschau eines Produktbilds zeigt das ganze Produkt, auch hochkant – kein Ausschnitt aus der
        # Mitte. Ordnerfotos bleiben beim quadratischen Ausschnitt (wie Karte und Alben).
        r = kp.post(f"/api/material/produkte/{ids['hms']}/bild", data={"file": (jpeg(200, 400), "hoch.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        assert Image.open(io.BytesIO(k["fuehrung"].get(r.json["produkt"]["vorschau"]).data)).size == (128, 256)
        gid, _ = gliederung(k["wart"])
        r = k["wart"].post(f"/api/material/ordner/{gid}/foto", data={"file": (jpeg(200, 400), "ordner.jpg")}, headers=H,
                           content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        assert Image.open(io.BytesIO(k["wart"].get(r.json["ordner"]["vorschau"]).data)).size == (256, 256)
    print("Formular- und Dokumenttest bestanden.")


# --- 9. Status: Python und SQL sagen dasselbe ---------------------------------------------------------------

def test_status_einheitlich():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from app import db
            from app.material.services import status as st
            h = date(2026, 10, 16)
            g = "2026-01-01"          # zuletzt geprüft; None = noch nie (Eingangsprüfung offen)
            faelle = [("frei", "2026-10-15", None, g, "ueberfaellig"), ("frei", "2026-10-16", None, g, "bald_faellig"),
                      ("frei", "2026-11-15", None, g, "bald_faellig"), ("frei", "2026-11-16", None, g, "einsatzbereit"),
                      ("frei", None, None, g, "ueberfaellig"), ("frei", "2027-01-01", "2026-10-16", g, "lebensdauer"),
                      ("frei", "2026-01-01", "2026-10-15", g, "lebensdauer"), ("frei", "2027-01-01", "2026-10-17", g, "einsatzbereit"),
                      ("gesperrt", "2027-01-01", None, g, "gesperrt"), ("verloren", "2020-01-01", "2020-01-01", g, "gesperrt"),
                      ("ausgesondert", "2020-01-01", "2020-01-01", g, "ausgesondert"),
                      # Ohne Prüfung ist ein Artikel „neu“ – auch mit Fälligkeit in der Zukunft oder schon überfällig.
                      ("frei", "2027-01-01", None, None, "neu"), ("frei", "2026-10-15", None, None, "neu"),
                      ("frei", None, None, None, "neu"), ("frei", "2027-01-01", "2026-10-17", None, "neu"),
                      # Schwerer als „neu“: Lebensende, Sperre, Aussonderung.
                      ("frei", "2027-01-01", "2026-10-16", None, "lebensdauer"), ("gesperrt", "2027-01-01", None, None, "gesperrt"),
                      ("verloren", None, None, None, "gesperrt"), ("ausgesondert", None, None, None, "ausgesondert")]
            sql = st.status_sql("x")
            for lock, due, retire, geprueft, soll in faelle:
                item = {"lock_state": lock, "next_due_on": due, "retire_by": retire, "last_inspected_on": geprueft}
                assert st.status(item, h, 30) == soll, (item, st.status(item, h, 30))
                r = db.query(f"SELECT {sql} AS s FROM (SELECT :l AS lock_state, :d AS next_due_on, :r AS retire_by, "
                             f":g AS last_inspected_on) x",
                             dict(st.parameter(h, 30), l=lock, d=due, r=retire, g=geprueft), one=True)
                assert r["s"] == soll, (item, r["s"])
    print("Statustest bestanden.")


# --- 10. Katalogimport ---------------------------------------------------------------------------------------

KATALOG = {
    "format": "stroemis-material-katalog", "version": 1,
    "kategorien": [{"name": "PSA gegen Absturz", "unterkategorien": [
        {"name": "Auffang- und Haltegurte", "norm": "EN 361, EN 12277, EN 813", "materialart": "textil", "intervall_monate": 12},
        {"name": "HMS-Karabiner", "norm": "EN 362, EN 12275", "materialart": "metall_hardware", "intervall_monate": 12}]},
        {"name": "Wasserrettung", "unterkategorien": [
            {"name": "Schwimmhilfen", "norm": "EN 12402-5", "materialart": "sonstiges", "intervall_monate": 12}]}],
    "produkte": [
        {"kategorie": ["PSA gegen Absturz", "Auffang- und Haltegurte"], "hersteller": "Importwerk", "modell": "Gurt I",
         "artikelnummer": "I-1", "materialart": "textil", "lebensdauer_jahre": 10, "lebensdauer_quelle": "Anleitung S. 3"},
        {"kategorie": "PSA gegen Absturz / HMS-Karabiner", "hersteller": "Importwerk", "modell": "HMS I",
         "materialart": "metall_hardware"}],
    "formulare": [
        {"kategorie": ["PSA gegen Absturz", "Auffang- und Haltegurte"], "titel": "Import generisch",
         "punkte": [{"gruppe": "G", "text": "Importpunkt", "art": "yesno", "soll": "nein", "kritisch": True}]},
        {"produkt": {"hersteller": "Importwerk", "modell": "HMS I"}, "titel": "Import spezifisch",
         "punkte": [{"text": "Importpunkt Karabiner", "art": "yesno", "soll": "ja"}]}],
}


def test_import():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        datei = os.path.join(tmp, "katalog.json")
        runner = app.test_cli_runner()

        def lauf(daten, *zusatz):
            with open(datei, "w", encoding="utf-8") as fh:
                json.dump(daten, fh, ensure_ascii=False)
            return runner.invoke(args=["material", "import-catalog", datei, *zusatz])

        def zahl(sql):
            with app.app_context():
                from app import db
                return db.query(sql, one=True)["n"]

        r = lauf(KATALOG, "--trocken")
        assert r.exit_code == 0 and "Trockenlauf" in r.output, r.output
        assert zahl("SELECT COUNT(*) AS n FROM mat_product") == 0
        r = lauf(KATALOG)
        assert r.exit_code == 0 and "Gespeichert" in r.output, r.output
        assert "Kategorien  neu 5" in r.output and "Produkte    neu 2" in r.output and "Formulare   neu 2" in r.output, r.output
        assert zahl("SELECT COUNT(*) AS n FROM mat_form WHERE active = 1") == 2
        assert zahl("SELECT COUNT(*) AS n FROM mat_audit WHERE user_name = 'Katalogimport (katalog.json)'") >= 9
        # Wiederholt: nichts doppelt, nichts neu.
        r = lauf(KATALOG)
        assert "Kategorien  neu 0, geaendert 0, unveraendert 5" in r.output and "Formulare   neu 0, unveraendert 2" in r.output, r.output
        # Eine Änderung in der Datei wird übernommen – ein geändertes Formular als neue Version.
        geaendert = json.loads(json.dumps(KATALOG))
        geaendert["produkte"][1]["norm"] = "EN 362"
        geaendert["formulare"][0]["punkte"].append({"text": "Zweiter Importpunkt", "art": "text"})
        r = lauf(geaendert)
        assert "Produkte    neu 0, geaendert 1" in r.output and "Formulare   neu 1, unveraendert 1" in r.output, r.output
        assert zahl("SELECT COUNT(*) AS n FROM mat_form WHERE active = 1") == 2
        # Ein Fehler irgendwo: nichts gespeichert, jeder Fehler mit seiner Stelle.
        kaputt = json.loads(json.dumps(KATALOG))
        kaputt["produkte"].append({"kategorie": ["PSA gegen Absturz", "Auffang- und Haltegurte"], "hersteller": "X",
                                   "modell": "Ohne Lebensdauer", "materialart": "textil"})
        kaputt["produkte"].append({"kategorie": ["Gibt", "Es nicht"], "hersteller": "X", "modell": "Y", "materialart": "textil"})
        r = lauf(kaputt)
        assert r.exit_code == 1 and "produkte[2]" in r.output and "produkte[3]" in r.output and "Nichts gespeichert" in r.output, r.output
        assert zahl("SELECT COUNT(*) AS n FROM mat_product") == 2
        assert lauf({"format": "etwas anderes"}).exit_code == 1
    print("Importtest bestanden.")


# --- 11. Befunde aus dem Review vom 16.10.2026 – jeder einmal nachgestellt -------------------------------

def test_review_befunde():
    import threading
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, adm = k["wart"], k["adm"]
        gid, system = gliederung(w)
        heute = _heute()
        morgen = (heute + timedelta(days=1)).isoformat()
        grenze12 = None

        # 1. Kauf und Erstgebrauch in der Zukunft gibt es nicht; der Vorschlag liegt nie hinter heute + Intervall.
        for feld in ("first_use_on", "purchased_on"):
            r = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, feld: morgen})
            assert r.status_code == 400 and "Zukunft" in r.json["error"], (feld, r.get_json())
            r = w.get(f"/api/material/artikel/vorschlag?product_id={ids['hms']}&folder_id={gid}&{feld}={morgen}")
            assert r.status_code == 400, r.get_json()
        v = w.get(f"/api/material/artikel/vorschlag?product_id={ids['hms']}&folder_id={gid}").json["vorschlag"]
        grenze12 = v["spaetestens"]
        assert v["next_due_on"] <= grenze12

        # 2. Kürzeres Intervall zieht die Fälligkeit nach – Produktwechsel, Artikelintervall, Ordner.
        r = adm.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                     "model": "Kurz", "material_kind": "metall_hardware", "interval_months": 3})
        kurz = r.json["produkt"]["id"]
        a = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid}).json["artikel"]
        assert a["next_due_on"] == grenze12
        r = w.put(f"/api/material/artikel/{a['id']}", json={"product_id": kurz})
        from app.material.services.interval import plus_monate
        assert r.status_code == 200 and r.json["artikel"]["next_due_on"] == plus_monate(heute, 3).isoformat(), r.get_json()
        assert any(j["action"] == "faelligkeit" for j in r.json["artikel"]["journal"])
        b = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid}).json["artikel"]
        r = w.put(f"/api/material/artikel/{b['id']}", json={"interval_months": 1})
        assert r.json["artikel"]["next_due_on"] == plus_monate(heute, 1).isoformat()
        c = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid}).json["artikel"]
        assert w.put(f"/api/material/ordner/{gid}", json={"interval_months": 2}).status_code == 200
        assert w.get(f"/api/material/artikel/{c['id']}").json["artikel"]["next_due_on"] == plus_monate(heute, 2).isoformat()
        assert w.put(f"/api/material/ordner/{gid}", json={"interval_months": None}).status_code == 200
        # … und auch eine kürzere Vorgabe im Katalog (Produktintervall).
        d = w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid}).json["artikel"]
        assert k["katalog"].put(f"/api/material/produkte/{ids['hms']}", json={"interval_months": 6}).status_code == 200
        assert w.get(f"/api/material/artikel/{d['id']}").json["artikel"]["next_due_on"] == plus_monate(heute, 6).isoformat()

        # 3. Eine Kategorie verliert ihr Intervall nicht, solange Produkte davon erben.
        r = adm.put(f"/api/material/kategorien/{ids['gurte']}", json={"default_interval_months": None})
        assert r.status_code == 409 and "Gurt Alpha" in r.json["error"], r.get_json()
        assert adm.put(f"/api/material/kategorien/{ids['gurte']}", json={"parent_id": None}).status_code == 200  # Umhängen geht
        # Ohne Fälligkeit (Altbestand) lässt sich keine beliebige setzen.
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET next_due_on = NULL WHERE id = ?", (d["id"],))
        assert w.put(f"/api/material/artikel/{d['id']}", json={"next_due_on": "2099-01-01"}).status_code == 400
        assert w.put(f"/api/material/artikel/{d['id']}", json={"next_due_on": heute.isoformat()}).status_code == 200

        # 4. + 5. Lebensende: vorgezogen bleibt vorgezogen – nicht zurückschiebbar, leer behält, Korrekturen
        # an der Lebensdauer hin und zurück ändern nichts daran.
        g = w.post("/api/material/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2020-03"}).json["artikel"]
        assert g["retire_by"] == "2030-03-01"
        assert w.put(f"/api/material/artikel/{g['id']}", json={"retire_by": "2029-01-01"}).json["artikel"]["retire_by"] == "2029-01-01"
        r = w.put(f"/api/material/artikel/{g['id']}", json={"retire_by": "2030-03-01"})
        assert r.status_code == 400 and "vorziehen" in r.json["error"]
        assert w.put(f"/api/material/artikel/{g['id']}", json={"retire_by": ""}).json["artikel"]["retire_by"] == "2029-01-01"
        kp = k["katalog"]
        assert kp.put(f"/api/material/produkte/{ids['gurt']}", json={"lifetime_years": 8}).status_code == 200
        assert w.get(f"/api/material/artikel/{g['id']}").json["artikel"]["retire_by"] == "2028-03-01"
        assert kp.put(f"/api/material/produkte/{ids['gurt']}", json={"lifetime_years": 10}).status_code == 200
        a2 = w.get(f"/api/material/artikel/{g['id']}").json["artikel"]
        assert a2["retire_by"] == "2029-01-01" and a2["lebensdauer"]["vorgezogen"], a2["lebensdauer"]
        # Herstelldatum hin und zurück: dasselbe.
        assert w.put(f"/api/material/artikel/{g['id']}", json={"manufactured_on": "2018-03"}).json["artikel"]["retire_by"] == "2028-03-01"
        assert w.put(f"/api/material/artikel/{g['id']}", json={"manufactured_on": "2020-03"}).json["artikel"]["retire_by"] == "2029-01-01"

        # 6. Ausgesonderte Artikel bleiben, wie sie sind – auch wenn sich die Lebensdauer am Produkt ändert.
        with app.app_context():
            db.execute("UPDATE mat_item SET lock_state = 'ausgesondert', folder_id = ? WHERE id = ?", (system["ausgesondert"], g["id"]))
        assert kp.put(f"/api/material/produkte/{ids['gurt']}", json={"lifetime_years": 12}).status_code == 200
        assert w.get(f"/api/material/artikel/{g['id']}").json["artikel"]["retire_by"] == "2029-01-01"

        # 8. Genau ein Treffer, aber Seite 2: leere Liste statt 500.
        r = w.get(f"/api/material/suche?q={a['inventory_no']}&seite=2")
        assert r.status_code == 200 and r.json["treffer"] == [] and r.json["eindeutig"] is None, r.get_json()
        # 9. Steuerzeichen im Suchbegriff: kein 500.
        for url in ("/api/material/suche?q=abc%00def", "/api/material/suche?q=ab%00", "/api/material/produkte?q=abc%00def",
                    "/material/suche?q=abc%00def"):
            assert w.get(url).status_code in (200, 400), url
        # 15. Negative Seitengröße wird geklemmt, nicht „alles“.
        assert len(w.get("/api/material/faellig?status=einsatzbereit,ueberfaellig,bald_faellig&pro_seite=-1").json["artikel"]) <= 1
        assert w.get(f"/api/material/ordner/{gid}?pro_seite=-5").status_code == 200

        # 10. Jede Dokumentversion hat höchstens einen Nachfolger – auch direkt in der Datenbank.
        r = kp.post(f"/api/material/produkte/{ids['hms']}/dokumente", json={"kind": "datenblatt", "title": "D", "url": "https://x.example/d"})
        doc = r.json["dokument_id"]
        assert kp.post(f"/api/material/dokumente/{doc}/version", json={"url": "https://x.example/d2"}).status_code == 201
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute("INSERT INTO mat_product_document (product_id, kind, title, url, valid_from, replaces_id, uploaded_at) "
                         "VALUES (?, 'datenblatt', 'Zweiter', 'https://x.example/d3', '2026-01-01', ?, 'x')", (ids["hms"], doc))
            raise AssertionError("zweiter Nachfolger ging durch")
        except sqlite3.IntegrityError:
            pass
        conn.rollback(); conn.close()

        # 11. Gleichzeitig A→B und B→A: nie ein Zyklus.
        fa = w.post("/api/material/ordner", json={"name": "A", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        fb = w.post("/api/material/ordner", json={"name": "B", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        c1, c2 = anmelden(app, "wart@example.org", "passwort1"), anmelden(app, "wart@example.org", "passwort1")
        for _ in range(8):
            t1 = threading.Thread(target=lambda: c1.post(f"/api/material/ordner/{fa}/verschieben", json={"parent_id": fb}))
            t2 = threading.Thread(target=lambda: c2.post(f"/api/material/ordner/{fb}/verschieben", json={"parent_id": fa}))
            t1.start(); t2.start(); t1.join(); t2.join()
            baum = {o["id"]: o["parent_id"] for o in w.get("/api/material/ordner").json["ordner"]}
            for start in (fa, fb):
                x, gesehen = start, set()
                while x is not None:
                    assert x not in gesehen, "Zyklus im Ordnerbaum"
                    gesehen.add(x); x = baum[x]
            for f in (fa, fb):
                w.post(f"/api/material/ordner/{f}/verschieben", json={"parent_id": gid})

        # 12. „Bald fällig“ ab 0 Tagen heißt: nur am Fälligkeitstag – nicht stillschweigend 30.
        assert adm.put("/api/admin/einstellungen", json={"werte": {"MATERIAL_BALD_FAELLIG_TAGE": "0"}}).status_code == 200
        assert w.get("/api/material/start").json["schwelle_tage"] == 0

        # 13. Ohne Zugang zum Modul verrät die Schnittstelle nicht, welche Artikel es gibt.
        assert k["nutzer"].get(f"/api/material/artikel/{a['id']}").status_code == 403
        assert k["nutzer"].get("/api/material/artikel/999999").status_code == 403

        # 14. Eine Urkundennummer aus unsichtbaren Zeichen ist keine.
        nid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "nutzer@example.org"][0]["id"]
        for unsichtbar in ("​", "﻿­", "⁠ -"):
            r = adm.put(f"/api/admin/users/{nid}", json={"mat_pruefer": True, "urkundennummer": unsichtbar})
            assert r.status_code == 400, (repr(unsichtbar), r.get_json())
        r = adm.put(f"/api/admin/users/{nid}", json={"mat_pruefer": True, "urkundennummer": "​1012-7​"})
        assert r.status_code == 200 and r.json["user"]["urkundennummer"] == "1012-7", r.get_json()

    # 7. Import: Namen werden vereinheitlicht wie beim Speichern – der zweite Lauf findet alles wieder.
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        datei = os.path.join(tmp, "k.json")
        daten = {"format": "stroemis-material-katalog", "version": 1,
                 "kategorien": [{"name": "PSA  gegen   Absturz", "unterkategorien": [{"name": "Gurte", "materialart": "textil", "intervall_monate": 12}]}],
                 "produkte": [{"kategorie": ["PSA gegen  Absturz", " Gurte"], "hersteller": "X", "modell": "Y", "materialart": "textil",
                               "lebensdauer_jahre": 10}],
                 "formulare": [{"kategorie": "PSA gegen Absturz / Gurte", "titel": "Doppelt  Leer", "punkte": [{"text": "P", "art": "yesno", "soll": "ja"}]}]}
        with open(datei, "w", encoding="utf-8") as fh:
            json.dump(daten, fh)
        runner = app.test_cli_runner()
        r1 = runner.invoke(args=["material", "import-catalog", datei])
        assert r1.exit_code == 0, r1.output
        r2 = runner.invoke(args=["material", "import-catalog", datei])
        assert r2.exit_code == 0 and "Kategorien  neu 0" in r2.output and "Formulare   neu 0, unveraendert 1" in r2.output, r2.output
    print("Review-Befunde nachgestellt und behoben.")


# --- Lieferung 2: Prüfung ---------------------------------------------------------------------------------

def pruef_formulare(kp, ids):
    """Aktive Formulare: generisch für Gurte, spezifisch für den Gurt Alpha (ersetzt das generische),
    generisch für Karabiner. Inhalte erfunden, nur für den Test."""
    def form(ziel, titel, punkte):
        r = kp.post("/api/material/formulare", json=dict(ziel, titel=titel, punkte=punkte))
        assert r.status_code == 201, r.get_json()
        fid = r.json["formular"]["id"]
        assert kp.post(f"/api/material/formulare/{fid}/aktivieren", json={}).status_code == 200
        return fid
    return {
        "generisch": form({"kategorie_id": ids["gurte"]}, "Gurt generisch", [
            {"gruppe": "Band", "text": "Testpunkt generisch", "art": "yesno", "soll": "nein", "kritisch": True}]),
        "spezifisch": form({"produkt_id": ids["gurt"]}, "Gurt spezifisch", [
            {"gruppe": "Band", "text": "Testpunkt kritisch", "art": "yesno", "soll": "nein", "kritisch": True},
            {"gruppe": "Band", "text": "Testpunkt Kennzeichnung", "art": "yesno", "soll": "ja"},
            {"text": "Testpunkt Messwert", "art": "number"},
            {"text": "Testpunkt Bemerkung", "art": "text", "pflicht": False}]),
        "karabiner": form({"kategorie_id": ids["karabiner"]}, "Karabiner generisch", [
            {"text": "Testpunkt Verschluss", "art": "yesno", "soll": "ja", "kritisch": True},
            {"text": "Testpunkt Verschleiß", "art": "yesno", "soll": "nein"}]),
    }


def neuer_artikel(c, produkt_id, ordner_id, **felder):
    r = c.post("/api/material/artikel", json=dict(felder, product_id=produkt_id, folder_id=ordner_id))
    assert r.status_code == 201, r.get_json()
    return r.json["artikel"]


def zweiter_pruefer(app, adm):
    r = adm.post("/api/admin/users", json={"email": "pruefer2@example.org", "password": "passwort1", "name": "Prüferin Zwei",
                                           "mat_pruefer": True, "urkundennummer": "1012-4712"})
    assert r.status_code == 201, r.get_json()
    c = anmelden(app, "pruefer2@example.org", "passwort1")
    unterschreiben(c)
    return c


def starten(c, iid, **d):
    return c.post(f"/api/material/artikel/{iid}/pruefungen", json=d)


def abschluss(c, pid, **d):
    return c.post(f"/api/material/pruefungen/{pid}/abschliessen", json=d)


def punkte_von(pr):
    return {x["text"]: x["id"] for x in pr["punkte"]}


def test_pruefung():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        f = pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        p2 = zweiter_pruefer(app, k["adm"])
        gid, system = gliederung(w)
        fahrzeug = w.post("/api/material/ordner", json={"name": "Fahrzeug 1", "kind": "fahrzeug", "parent_id": gid}).json["ordner"]["id"]
        h = _heute()
        a = neuer_artikel(w, ids["gurt"], fahrzeug, manufactured_on=f"{h.year - 2}-01")
        iid = a["id"]
        # Neu angelegt heißt „neu“, nicht einsatzbereit: Die Eingangsprüfung steht aus.
        assert a["status"] == "neu" and a["last_inspected_on"] is None, a
        assert a["pruefarten"] == {"arten": ["eingang"], "vorschlag": "eingang"}
        z = w.get("/api/material/start").json["zaehlung"]
        assert z["neu"] == 1 and z["einsatzbereit"] == 0, z
        assert [x["id"] for x in w.get("/api/material/faellig").json["artikel"]] == [iid]
        assert [x["id"] for x in w.get(f"/api/material/ordner/{fahrzeug}?status=neu").json["ordner"]["artikel"]] == [iid]
        # Prüfen dürfen nur Prüfer mit Urkundennummer.
        for c in (w, k["fuehrung"], k["katalog"], k["adm"]):
            assert starten(c, iid).status_code == 403
        assert starten(k["nutzer"], iid).status_code == 403
        # Die erste Prüfung ist die Eingangsprüfung – eine andere Art wird abgewiesen.
        r = starten(p1, iid, art="periodisch")
        assert r.status_code == 400 and "Eingangsprüfung" in r.json["error"], r.get_json()
        r = starten(p1, iid)
        assert r.status_code == 201, r.get_json()
        pr = r.json["pruefung"]
        assert pr["art"] == "eingang" and pr["entwurf"] and pr["eigen"] and pr["pruefer"] == "pruefer"
        # Das spezifische Formular des Produkts schlägt das generische der Kategorie.
        assert pr["formular"]["id"] == f["spezifisch"], pr["formular"]
        assert [x["text"] for x in pr["punkte"]] == ["Testpunkt kritisch", "Testpunkt Kennzeichnung", "Testpunkt Messwert",
                                                     "Testpunkt Bemerkung"]
        # Alle Punkte sind mit ihrem Sollwert vorbelegt – der Prüfer ändert nur Abweichungen.
        assert all(x["befund"] == "ok" for x in pr["punkte"])
        assert [x["wert"] for x in pr["punkte"] if x["art"] == "yesno"] == ["nein", "ja"]
        # Eine benutzte Formularversion bleibt, wie sie ist.
        assert k["katalog"].put(f"/api/material/formulare/{f['spezifisch']}", json={"titel": "x"}).status_code == 409
        # Noch einmal starten: derselbe Entwurf. Eine zweite Prüferin bekommt „in Prüfung bei …“.
        r = starten(p1, iid)
        assert r.status_code == 200 and r.json["pruefung"]["id"] == pr["id"]
        r = starten(p2, iid)
        assert r.status_code == 409 and "In Prüfung bei pruefer" in r.json["error"], r.get_json()
        assert w.get(f"/api/material/artikel/{iid}").json["artikel"]["entwurf"]["pruefer"] == "pruefer"
        pid, pk = pr["id"], punkte_von(pr)
        url = f"/api/material/pruefungen/{pid}/punkte"
        # Fremde ändern am Entwurf nichts – auch keine andere Prüferin.
        assert p2.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "1"}).status_code == 403
        # Ein Pflichtpunkt ohne Wert blockiert den Abschluss.
        r = abschluss(p1, pid, ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Testpunkt Messwert" in r.json["error"], r.get_json()
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "abc"}).status_code == 400
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "12,5"}).json["punkt"]["wert"] == "12,5"
        # Der kritische Punkt weicht ab → Mangel. Ohne Foto lässt sich nicht abschließen.
        r = p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"wert": "ja", "notiz": "Schnitt im Band"})
        assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel", r.get_json()
        r = abschluss(p1, pid, ergebnis="instandsetzen")
        assert r.status_code == 400 and "Foto" in r.json["error"], r.get_json()
        r = p1.post(f"{url}/{pk['Testpunkt kritisch']}/foto", data={"file": (jpeg(), "mangel.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["punkt"]["foto"]["vorschau"], r.get_json()
        assert k["fuehrung"].get(r.json["punkt"]["foto"]["vorschau"]).status_code == 200
        # Ein kritischer Mangel schließt „einsatzbereit“ aus.
        r = abschluss(p1, pid, ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Kritischer Mangel" in r.json["error"], r.get_json()
        assert p1.get(f"/api/material/pruefungen/{pid}").json["pruefung"]["einsatzbereit_gesperrt"]
        # „instandsetzen“ sperrt und verschiebt nach „Gesperrt“; der Herkunftsordner bleibt gemerkt.
        r = abschluss(p1, pid, ergebnis="instandsetzen", bemerkung="zum Hersteller")
        assert r.status_code == 200 and r.json["pruefung"]["ergebnis"] == "instandsetzen", r.get_json()
        assert not r.json["pruefung"]["entwurf"]
        a = w.get(f"/api/material/artikel/{iid}").json["artikel"]
        assert a["status"] == "gesperrt" and a["lock_state"] == "gesperrt", a
        assert a["folder_id"] == system["gesperrt"] and a["origin_folder_id"] == fahrzeug, a
        assert a["last_inspected_on"] == h.isoformat() and "instandsetzen" in a["lock_reason"]
        # Abgeschlossen heißt: nichts mehr zu ändern, nichts mehr zu verwerfen.
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "13"}).status_code == 409
        assert p1.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 409
        # Von Hand zurückverschieben scheitert – auch für den Materialwart.
        r = w.post("/api/material/artikel/verschieben", json={"ids": [iid], "folder_id": fahrzeug})
        assert r.status_code == 409 and "Freiprüfung" in r.json["error"], r.get_json()
        # Freiprüfung: Vorschlag „Reparatur“; „einsatzbereit“ bringt den Artikel zurück in den Herkunftsordner.
        assert a["pruefarten"]["vorschlag"] == "reparatur" and "eingang" not in a["pruefarten"]["arten"]
        r = starten(p2, iid)
        assert r.status_code == 201 and r.json["pruefung"]["art"] == "reparatur" and r.json["pruefung"]["freipruefung"]
        pr2 = r.json["pruefung"]
        pid2 = pr2["id"]
        p2.put(f"/api/material/pruefungen/{pid2}/punkte/{punkte_von(pr2)['Testpunkt Messwert']}", json={"wert": "12"})
        # Die nächste Prüfung lässt sich vorziehen, nicht verschieben.
        vorschlag = date.fromisoformat(pr2["vorschlag_naechste"])
        from app.material.services.interval import plus_monate
        assert pr2["vorschlag_naechste"] == plus_monate(h, 12).isoformat(), pr2["vorschlag_naechste"]   # Kategorie: 12 Monate
        r = abschluss(p2, pid2, ergebnis="einsatzbereit", next_due_on=(vorschlag + timedelta(days=1)).isoformat())
        assert r.status_code == 400 and "vorziehen" in r.json["error"], r.get_json()
        r = abschluss(p2, pid2, ergebnis="einsatzbereit", next_due_on=h.isoformat())
        assert r.status_code == 400
        frueher = (h + timedelta(days=90)).isoformat()
        r = abschluss(p2, pid2, ergebnis="einsatzbereit", next_due_on=frueher)
        assert r.status_code == 200, r.get_json()
        a = w.get(f"/api/material/artikel/{iid}").json["artikel"]
        assert a["status"] == "einsatzbereit" and a["lock_state"] == "frei", a
        assert a["folder_id"] == fahrzeug and a["origin_folder_id"] is None and a["next_due_on"] == frueher, a
        assert [x["art"] for x in a["pruefungen"]] == ["reparatur", "eingang"], a["pruefungen"]
        assert [x["ergebnis"] for x in a["pruefungen"]] == ["einsatzbereit", "instandsetzen"]
        aktionen = [e["action"] for e in a["journal"] if e["entity"] == "item"]
        assert "gesperrt" in aktionen and "freigeprueft" in aktionen, aktionen
        # Prüfen geht jederzeit, auch wenn nichts fällig ist – Vorschlag „außerplanmäßig“.
        assert a["pruefarten"]["vorschlag"] == "ausserplanmaessig", a["pruefarten"]
        r = starten(p1, iid)
        assert r.status_code == 201 and r.json["pruefung"]["art"] == "ausserplanmaessig"
        pid3 = r.json["pruefung"]["id"]
        # Die Prüfart lässt sich am Entwurf ändern – aber nicht in eine Eingangsprüfung.
        assert p1.put(f"/api/material/pruefungen/{pid3}", json={"art": "eingang"}).status_code == 400
        assert p1.put(f"/api/material/pruefungen/{pid3}", json={"art": "periodisch"}).json["pruefung"]["art"] == "periodisch"
        # Den eigenen Entwurf verwirft der Prüfer selbst; dann ist der Artikel wieder frei.
        assert p2.delete(f"/api/material/pruefungen/{pid3}", headers=H).status_code == 403
        assert p1.delete(f"/api/material/pruefungen/{pid3}", headers=H).status_code == 200
        assert w.get(f"/api/material/artikel/{iid}").json["artikel"]["entwurf"] is None
        assert p1.get(f"/api/material/pruefungen/{pid3}").status_code == 404
        # Lesen dürfen alle mit Zugang zum Modul, Nutzer ohne Recht nicht.
        assert k["fuehrung"].get(f"/api/material/pruefungen/{pid}").status_code == 200
        assert k["nutzer"].get(f"/api/material/pruefungen/{pid}").status_code == 403
        assert k["fuehrung"].get(f"/material/pruefung/{pid}").status_code == 200
        assert k["fuehrung"].get(f"/material/artikel/{iid}/pruefung/neu").status_code == 200
    print("Prüfungstest bestanden.")


def test_sperre_und_aussonderung():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, system = gliederung(w)
        lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        h = _heute()
        bestand_vorher = w.get("/api/material/start").json["bestand"]
        # Textil nach Ablauf der Lebensdauer: „einsatzbereit“ ist nicht mehr wählbar.
        alt = neuer_artikel(w, ids["gurt"], lager, manufactured_on=f"{h.year - 11}-01")
        assert alt["status"] == "lebensdauer"
        # Der Materialwart sondert nur aus, was ein Prüfer vorher gesperrt hat.
        r = w.post(f"/api/material/artikel/{alt['id']}/aussondern", json={"grund": "lebensdauer"})
        assert r.status_code == 409 and "gesperrte" in r.json["error"], r.get_json()
        pr = starten(p1, alt["id"]).json["pruefung"]
        assert pr["lebensdauer"]["erreicht"] and pr["einsatzbereit_gesperrt"], pr
        p1.put(f"/api/material/pruefungen/{pr['id']}/punkte/{punkte_von(pr)['Testpunkt Messwert']}", json={"wert": "1"})
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Lebensende" in r.json["error"], r.get_json()
        # Ohne Mangel braucht „aussondern“ einen Grund.
        r = abschluss(p1, pr["id"], ergebnis="aussondern")
        assert r.status_code == 400 and "Grund" in r.json["error"], r.get_json()
        r = abschluss(p1, pr["id"], ergebnis="aussondern", grund="Lebensdauer überschritten")
        assert r.status_code == 200, r.get_json()
        a = w.get(f"/api/material/artikel/{alt['id']}").json["artikel"]
        assert a["status"] == "ausgesondert" and a["folder_id"] == system["ausgesondert"], a
        # Die Aussonderung ist ein eigener Vorgang mit Verweis auf die Prüfung.
        assert [x["art"] for x in a["pruefungen"]] == ["aussonderung", "eingang"], a["pruefungen"]
        assert a["pruefungen"][0]["basis_id"] == pr["id"] and a["pruefungen"][0]["ergebnis"] == "aussondern"
        # Ausgesondert: zählt nicht mehr als Bestand, wird nicht mehr geprüft, gesperrt oder bearbeitet.
        assert w.get("/api/material/start").json["bestand"] == bestand_vorher
        assert starten(p1, alt["id"]).status_code == 409
        assert p1.post(f"/api/material/artikel/{alt['id']}/sperren", json={"grund": "sturz"}).status_code == 409
        assert w.put(f"/api/material/artikel/{alt['id']}", json={"notes": "x"}).status_code == 409

        # Metall: Sperre ohne Prüfung nur durch Prüfer, Aussonderung danach durch den Materialwart.
        b = neuer_artikel(w, ids["hms"], lager)
        assert w.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "beschaedigung"}).status_code == 403
        assert p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "unfug"}).status_code == 400
        r = p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "beschaedigung", "text": "Riss am Schnapper"})
        assert r.status_code == 200, r.get_json()
        a = r.json["artikel"]
        assert a["status"] == "gesperrt" and a["folder_id"] == system["gesperrt"] and a["origin_folder_id"] == lager, a
        assert a["lock_reason"] == "Beschädigung: Riss am Schnapper"
        assert p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "sturz"}).status_code == 409
        # Aussondern darf der Prüfer ohne Prüfung nicht – das ist Sache des Materialwarts.
        assert p1.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "irreparabel"}).status_code == 403
        morgen = (h + timedelta(days=1)).isoformat()
        assert w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "irreparabel", "datum": morgen}).status_code == 400
        r = w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "irreparabel", "bemerkung": "Bruch"})
        assert r.status_code == 200, r.get_json()
        a = r.json["artikel"]
        assert a["status"] == "ausgesondert" and a["folder_id"] == system["ausgesondert"] and a["origin_folder_id"] is None
        assert a["pruefungen"][0]["art"] == "aussonderung" and a["pruefungen"][0]["grund"] == "irreparabel"
        assert a["pruefungen"][0]["pruefer"] == "wart"
        # Verlust: Der Prüfer sperrt ohne Prüfung mit Grund „Verlust“, der Materialwart sondert aus.
        c = neuer_artikel(w, ids["hms"], lager, serial_no="V-1")
        a = p1.post(f"/api/material/artikel/{c['id']}/sperren", json={"grund": "verlust"}).json["artikel"]
        assert a["lock_state"] == "verloren" and a["status"] == "gesperrt", a
        a = w.post(f"/api/material/artikel/{c['id']}/aussondern", json={"grund": "verlust"}).json["artikel"]
        assert a["status"] == "ausgesondert"
        # Im Ordner „Ausgesondert“ liegen beide samt Lebenslauf; im Bestand zählen sie nicht.
        inhalt = w.get(f"/api/material/ordner/{system['ausgesondert']}").json["ordner"]
        assert {x["id"] for x in inhalt["artikel"]} == {alt["id"], b["id"], c["id"]}
        assert w.get("/api/material/start").json["bestand"] == bestand_vorher
        # Ein Entwurf blockiert Sperre und Aussonderung: Darüber entscheidet die laufende Prüfung.
        d = neuer_artikel(w, ids["hms"], lager, serial_no="E-1")
        starten(p1, d["id"])
        r = p1.post(f"/api/material/artikel/{d['id']}/sperren", json={"grund": "sturz"})
        assert r.status_code == 409 and "In Prüfung bei" in r.json["error"], r.get_json()
    print("Sperr- und Aussonderungstest bestanden.")


def test_anhang_scan():
    from pypdf import PdfReader, PdfWriter
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, a["id"]).json["pruefung"]["id"]
        url = f"/api/material/pruefungen/{pid}/anhaenge"

        def hochladen(c, dateien, **felder):
            return c.post(url, data=dict(felder, file=dateien), headers=H, content_type="multipart/form-data")

        # Ein mehrseitiger Scan (drei Fotos) wird ein PDF mit drei Seiten.
        r = hochladen(p1, [(jpeg(), "seite1.jpg"), (jpeg(240, 320), "seite2.jpg"), (jpeg(), "seite3.jpg")],
                      art="externes_pruefformular", titel="Prüfkarte des Herstellers", im_protokoll="ja")
        assert r.status_code == 201, r.get_json()
        scan = r.json["anhang"]
        assert scan["seiten"] == 3 and scan["im_protokoll"] and scan["titel"] == "Prüfkarte des Herstellers"
        datei = k["fuehrung"].get(scan["datei"])
        assert datei.status_code == 200 and datei.data.startswith(b"%PDF-")
        assert len(PdfReader(io.BytesIO(datei.data)).pages) == 3
        import hashlib
        assert hashlib.sha256(datei.data).hexdigest() == scan["sha256"]
        assert k["nutzer"].get(scan["datei"]).status_code == 403
        # Ein einzelnes PDF bleibt Byte für Byte, wie es ist; Fotos und PDFs zusammen werden ein PDF.
        schreiber = PdfWriter()
        schreiber.add_blank_page(595, 842)
        schreiber.add_blank_page(595, 842)
        puffer = io.BytesIO()
        schreiber.write(puffer)
        pdf = puffer.getvalue()
        r = hochladen(p1, [(io.BytesIO(pdf), "bericht.pdf")], art="pruefbericht")
        assert r.status_code == 201 and r.json["anhang"]["seiten"] == 2, r.get_json()
        assert r.json["anhang"]["sha256"] == hashlib.sha256(pdf).hexdigest()
        r = hochladen(p1, [(jpeg(), "foto.jpg"), (io.BytesIO(pdf), "bericht.pdf")], art="sonstiges")
        assert r.status_code == 201 and r.json["anhang"]["seiten"] == 3, r.get_json()
        # Was weder PDF noch Foto ist, wird abgewiesen; ebenso ein kaputtes PDF.
        assert hochladen(p1, [(io.BytesIO(b"hallo"), "notiz.txt")]).status_code == 400
        assert hochladen(p1, [(io.BytesIO(b"%PDF-1.4 kaputt"), "kaputt.pdf")]).status_code == 400
        assert hochladen(p1, [], art="sonstiges").status_code == 400
        # Anhängen und Entfernen darf nur der Prüfer des Entwurfs.
        p2 = zweiter_pruefer(app, k["adm"])
        assert hochladen(p2, [(jpeg(), "x.jpg")]).status_code == 403
        pr = k["fuehrung"].get(f"/api/material/pruefungen/{pid}").json["pruefung"]
        assert [x["seiten"] for x in pr["anhaenge"]] == [3, 2, 3]
        assert p1.delete(f"{url}/{scan['id']}", headers=H).status_code == 200
        assert k["fuehrung"].get(scan["datei"]).status_code == 404
        assert len(k["fuehrung"].get(f"/api/material/pruefungen/{pid}").json["pruefung"]["anhaenge"]) == 2
        # Wer den Entwurf verwirft, verwirft seine Anhänge mit.
        rest = [x["datei"] for x in k["fuehrung"].get(f"/api/material/pruefungen/{pid}").json["pruefung"]["anhaenge"]]
        assert p1.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 200
        assert all(k["fuehrung"].get(x).status_code == 404 for x in rest)
    print("Anhangtest bestanden.")


def test_durchgang():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        p2 = zweiter_pruefer(app, k["adm"])
        gid, system = gliederung(w)
        fahrzeug = w.post("/api/material/ordner", json={"name": "Fahrzeug", "kind": "fahrzeug", "parent_id": gid}).json["ordner"]["id"]
        a = neuer_artikel(w, ids["hms"], fahrzeug, serial_no="A")
        b = neuer_artikel(w, ids["hms"], fahrzeug, serial_no="B")
        c = neuer_artikel(w, ids["hms"], gid, serial_no="C")
        # Eröffnen: Materialwart oder Prüfer – nicht Führungskraft oder Nutzer.
        for x in (k["fuehrung"], k["nutzer"], k["katalog"]):
            assert x.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Jahresprüfung"}).status_code == 403
        assert w.post("/api/material/durchgaenge", json={"folder_id": gid}).status_code == 400
        assert w.post("/api/material/durchgaenge", json={"folder_id": system["gesperrt"], "titel": "x"}).status_code == 409
        r = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Jahresprüfung 2027"})
        assert r.status_code == 201, r.get_json()
        rid = r.json["durchgang"]["id"]
        assert r.json["durchgang"]["zaehlung"] == {"gesamt": 3, "offen": 3, "in_pruefung": 0, "erledigt": 0, "ausgenommen": 0}
        # Ein Artikel steht höchstens in einem offenen Durchgang.
        r = p1.post("/api/material/durchgaenge", json={"folder_id": fahrzeug, "titel": "Fahrzeugcheck"})
        assert r.status_code == 409 and "Jahresprüfung 2027" in r.json["error"], r.get_json()
        # Wer einen Artikel öffnet, reserviert ihn; die anderen sehen „in Prüfung bei …“.
        r = starten(p1, a["id"], durchgang_id=rid)
        assert r.status_code == 201 and r.json["pruefung"]["round_id"] == rid
        pid_a = r.json["pruefung"]["id"]
        r = starten(p2, a["id"], durchgang_id=rid)
        assert r.status_code == 409 and "In Prüfung bei pruefer" in r.json["error"], r.get_json()
        d = k["fuehrung"].get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        zeile = {x["id"]: x for x in d["artikel"]}
        assert zeile[a["id"]]["zustand"] == "in_pruefung" and zeile[a["id"]]["entwurf"]["pruefer"] == "pruefer"
        assert d["zaehlung"]["in_pruefung"] == 1 and not d["abschliessbar"]
        # Abschließen geht erst, wenn alles geprüft oder ausgenommen ist.
        r = w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={})
        assert r.status_code == 409 and "offen" in r.json["error"], r.get_json()
        # Eine liegen gebliebene Reservierung gibt der Materialwart frei – nicht die andere Prüferin,
        # nicht die Führungskraft.
        assert p2.delete(f"/api/material/pruefungen/{pid_a}", headers=H).status_code == 403
        assert k["fuehrung"].delete(f"/api/material/pruefungen/{pid_a}", headers=H).status_code == 403
        assert w.delete(f"/api/material/pruefungen/{pid_a}", headers=H).status_code == 200
        journal_a = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["journal"]
        assert any(e["action"] == "reservierung_freigegeben" for e in journal_a)
        r = starten(p2, a["id"], durchgang_id=rid)
        assert r.status_code == 201, r.get_json()
        assert abschluss(p2, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        # Ausnehmen braucht einen Grund; ein geprüfter Artikel lässt sich nicht mehr ausnehmen.
        aus = f"/api/material/durchgaenge/{rid}/ausnehmen"
        assert w.post(aus, json={"item_id": b["id"]}).status_code == 400
        assert w.post(aus, json={"item_id": a["id"], "grund": "x"}).status_code == 409
        assert k["fuehrung"].post(aus, json={"item_id": b["id"], "grund": "x"}).status_code == 403
        assert w.post(aus, json={"item_id": b["id"], "grund": "nicht auffindbar"}).status_code == 200
        # Ausgenommen heißt: nicht in diesem Durchgang prüfen – bis er wieder einbezogen ist.
        assert starten(p1, b["id"], durchgang_id=rid).status_code == 409
        assert w.post(f"/api/material/durchgaenge/{rid}/einbeziehen", json={"item_id": b["id"]}).status_code == 200
        assert w.post(aus, json={"item_id": b["id"], "grund": "nicht auffindbar"}).status_code == 200
        # Ohne Angabe des Durchgangs ordnet das System eine Prüfung dem offenen Durchgang des Artikels zu.
        r = starten(p1, c["id"])
        assert r.json["pruefung"]["round_id"] == rid, r.get_json()
        pid_c = r.json["pruefung"]["id"]
        d = w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        assert d["zaehlung"] == {"gesamt": 3, "offen": 0, "in_pruefung": 1, "erledigt": 1, "ausgenommen": 1}
        assert w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 409
        assert abschluss(p1, pid_c, ergebnis="einsatzbereit").status_code == 200
        d = w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        assert d["abschliessbar"] and {x["name"] for x in d["pruefer"]} == {"pruefer", "Prüferin Zwei"}
        assert {x["urkunde"] for x in d["pruefer"]} == {"1012-4711", "1012-4712"}
        assert not d["loeschbar"]
        r = p1.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={})
        assert r.status_code == 200 and not r.json["durchgang"]["offen"], r.get_json()
        assert w.post(aus, json={"item_id": a["id"], "grund": "x"}).status_code == 409
        # Danach ist der Weg frei für den nächsten Durchgang; ein leerer lässt sich wieder löschen.
        r = p1.post("/api/material/durchgaenge", json={"folder_id": fahrzeug, "titel": "Nachprüfung"})
        assert r.status_code == 201, r.get_json()
        rid2 = r.json["durchgang"]["id"]
        assert r.json["durchgang"]["zaehlung"]["gesamt"] == 2
        assert {x["id"] for x in w.get("/api/material/durchgaenge").json["durchgaenge"]} == {rid, rid2}
        assert w.delete(f"/api/material/durchgaenge/{rid2}", headers=H).status_code == 200
        assert w.get(f"/api/material/durchgaenge/{rid2}").status_code == 404
        assert w.delete(f"/api/material/durchgaenge/{rid}", headers=H).status_code == 409
        assert k["fuehrung"].get(f"/material/durchgang/{rid}").status_code == 200
        # Wird ein Artikel eines offenen Durchgangs ausgesondert, nimmt das System ihn mit Grund heraus.
        rid3 = w.post("/api/material/durchgaenge", json={"folder_id": fahrzeug, "titel": "Dritter"}).json["durchgang"]["id"]
        assert p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "verlust"}).status_code == 200
        assert w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "verlust"}).status_code == 200
        d = w.get(f"/api/material/durchgaenge/{rid3}").json["durchgang"]
        zeile = {x["id"]: x for x in d["artikel"]}
        assert zeile[b["id"]]["zustand"] == "ausgenommen" and "ausgesondert" in zeile[b["id"]]["ausnahme"]["grund"]
    print("Durchgangstest bestanden.")


def test_review_lieferung2():
    """Befunde aus dem Review vor der Auslieferung von Lieferung 2, nachgestellt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        gid, system = gliederung(w)
        fahrzeug = w.post("/api/material/ordner", json={"name": "Fahrzeug", "kind": "fahrzeug", "parent_id": gid}).json["ordner"]["id"]
        lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["karabiner"], "titel": "Zahlen", "punkte": [
            {"text": "Öffnungsweite", "art": "number", "soll": "max. 22 mm"}, {"text": "Bandbreite", "art": "number", "soll": "45"},
            {"text": "Zustand", "art": "text", "soll": "Hinweis für den Prüfer", "pflicht": False}]})
        assert kp.post(f"/api/material/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200

        # 1. Bei Zahl und Text ist das Soll ein Hinweis, kein Messwert – nur eine reine Zahl wird vorbelegt.
        a = neuer_artikel(w, ids["hms"], fahrzeug, serial_no="A")
        pr = starten(p1, a["id"]).json["pruefung"]
        assert {x["text"]: x["wert"] for x in pr["punkte"]} == {"Öffnungsweite": "", "Bandbreite": "45", "Zustand": ""}
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Öffnungsweite" in r.json["error"], r.get_json()
        p1.put(f"/api/material/pruefungen/{pr['id']}/punkte/{punkte_von(pr)['Öffnungsweite']}", json={"wert": "21"})
        assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200

        # 2. Ein Entwurf, der vor der Eröffnung eines Durchgangs begann, zählt dort.
        b = neuer_artikel(w, ids["hms"], fahrzeug, serial_no="B")
        pb = starten(p1, b["id"]).json["pruefung"]
        assert pb["round_id"] is None
        rid = w.post("/api/material/durchgaenge", json={"folder_id": fahrzeug, "titel": "Fahrzeug"}).json["durchgang"]["id"]
        assert p1.get(f"/api/material/pruefungen/{pb['id']}").json["pruefung"]["round_id"] == rid
        p1.put(f"/api/material/pruefungen/{pb['id']}/punkte/{punkte_von(pb)['Öffnungsweite']}", json={"wert": "20"})
        assert abschluss(p1, pb["id"], ergebnis="einsatzbereit").status_code == 200
        zeilen = {x["id"]: x for x in w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]["artikel"]}
        assert zeilen[b["id"]]["zustand"] == "erledigt", zeilen[b["id"]]

        # 3. Ein Durchgang für einen Unterordner erfasst auch, was aus ihm nach „Gesperrt“ gewandert ist.
        c = neuer_artikel(w, ids["hms"], lager, serial_no="C")
        d = neuer_artikel(w, ids["hms"], lager, serial_no="D")
        assert p1.post(f"/api/material/artikel/{c['id']}/sperren", json={"grund": "beschaedigung"}).status_code == 200
        r = w.post("/api/material/durchgaenge", json={"folder_id": lager, "titel": "Lager"})
        assert r.status_code == 201 and r.json["durchgang"]["zaehlung"]["gesamt"] == 2, r.get_json()
        rid2 = r.json["durchgang"]["id"]

        # 4. Ein ausgesonderter Artikel bleibt ausgenommen – „wieder einbeziehen“ geht nicht.
        assert w.post(f"/api/material/artikel/{c['id']}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        zeilen = {x["id"]: x for x in w.get(f"/api/material/durchgaenge/{rid2}").json["durchgang"]["artikel"]}
        assert zeilen[c["id"]]["zustand"] == "ausgenommen"
        r = w.post(f"/api/material/durchgaenge/{rid2}/einbeziehen", json={"item_id": c["id"]})
        assert r.status_code == 409 and "ausgesondert" in r.json["error"], r.get_json()
        assert d["id"] in zeilen

        # 5. Wird das Intervall kürzer, gilt „letzte Prüfung + neues Intervall“ (ohne Prüfung: heute + Intervall).
        from app.material.services.interval import plus_monate
        h = _heute()
        vor = (h - timedelta(days=200)).isoformat()
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET last_inspected_on = ?, next_due_on = ? WHERE id = ?",
                       (vor, plus_monate(date.fromisoformat(vor), 12).isoformat(), a["id"]))
        assert w.put(f"/api/material/ordner/{fahrzeug}", json={"interval_months": 6}).status_code == 200
        a = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]
        assert a["next_due_on"] == plus_monate(date.fromisoformat(vor), 6).isoformat(), a["next_due_on"]
        assert a["status"] == "ueberfaellig", a["status"]
        assert any(e["action"] == "faelligkeit" and "letzten Prüfung" in (e["nachher"] or {}).get("grund", "")
                   for e in a["journal"])
    print("Review-Befunde Lieferung 2 nachgestellt und behoben.")


def pdf_roh(objekte):
    """Ein PDF aus {Nummer: Inhalt} mit gültiger Querverweistabelle – für absichtlich kaputte Anhänge."""
    aus = bytearray(b"%PDF-1.7\n")
    lage = {}
    for n in sorted(objekte):
        lage[n] = len(aus)
        aus += f"{n} 0 obj\n{objekte[n]}\nendobj\n".encode("latin-1")
    xref, groesse = len(aus), max(objekte) + 1
    aus += f"xref\n0 {groesse}\n0000000000 65535 f \n".encode()
    for n in range(1, groesse):
        aus += (f"{lage[n]:010d} 00000 n \n" if n in lage else "0000000000 65535 f \n").encode()
    aus += f"trailer\n<< /Size {groesse} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(aus)


def test_review_lieferung2_robust():
    """Weitere Befunde aus dem Review von Lieferung 2: Kennungen, veraltete Dialoge, Durchgang, Anhänge."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        a = neuer_artikel(w, ids["hms"], lager, serial_no="A")
        b = neuer_artikel(w, ids["hms"], lager, serial_no="B")

        # Eine verworfene Prüfung gibt ihre Kennung nicht weiter – ihr Journal bliebe sonst am falschen Vorgang.
        pa = starten(p1, a["id"]).json["pruefung"]["id"]
        assert p1.delete(f"/api/material/pruefungen/{pa}", headers=H).status_code == 200
        pb = starten(p1, b["id"]).json["pruefung"]["id"]
        assert pb > pa, (pa, pb)
        assert p1.delete(f"/api/material/pruefungen/{pb}", headers=H).status_code == 200
        # Ebenso ein gelöschter (leerer) Prüfdurchgang.
        r1 = w.post("/api/material/durchgaenge", json={"folder_id": lager, "titel": "eins"}).json["durchgang"]["id"]
        assert w.delete(f"/api/material/durchgaenge/{r1}", headers=H).status_code == 200
        r2 = w.post("/api/material/durchgaenge", json={"folder_id": lager, "titel": "zwei"}).json["durchgang"]["id"]
        assert r2 > r1, (r1, r2)
        assert w.delete(f"/api/material/durchgaenge/{r2}", headers=H).status_code == 200
        # Ein gelöschter Artikel darf seine Kennung abgeben – seine Geschichte aber nicht.
        c = neuer_artikel(w, ids["hms"], lager, serial_no="C")
        assert w.delete(f"/api/material/artikel/{c['id']}", headers=H).status_code == 200
        d = neuer_artikel(w, ids["hms"], lager, serial_no="D")
        eigene = [e for e in d["journal"] if e["entity"] == "item"]
        assert [e["action"] for e in eigene] == ["angelegt"] and eigene[0]["nachher"]["serial_no"] == "D", eigene

        # Ein veralteter Bearbeiten-Dialog überschreibt keine Prüfung; eine Fälligkeit liegt nie vor der letzten Prüfung.
        stand = d["stand"]
        assert abschluss(p1, starten(p1, d["id"]).json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        r = w.put(f"/api/material/artikel/{d['id']}", json={"stand": stand, "notes": "aus altem Dialog", "next_due_on": "2020-01-01"})
        assert r.status_code == 409 and "neu laden" in r.json["error"], r.get_json()
        d = w.get(f"/api/material/artikel/{d['id']}").json["artikel"]
        r = w.put(f"/api/material/artikel/{d['id']}", json={"stand": d["stand"], "next_due_on": d["last_inspected_on"]})
        assert r.status_code == 400 and "nach der letzten Prüfung" in r.json["error"], r.get_json()
        r = w.put(f"/api/material/artikel/{d['id']}", json={"stand": d["stand"], "notes": "neu geladen"})
        assert r.status_code == 200, r.get_json()

        # „Wieder einbeziehen“: Eine Prüfung, die begann, während der Artikel ausgenommen war, zählt danach hier.
        rid = w.post("/api/material/durchgaenge", json={"folder_id": lager, "titel": "drei"}).json["durchgang"]["id"]
        assert w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": b["id"], "grund": "verliehen"}).status_code == 200
        pr = starten(p1, b["id"]).json["pruefung"]
        assert pr["round_id"] is None
        assert w.post(f"/api/material/durchgaenge/{rid}/einbeziehen", json={"item_id": b["id"]}).status_code == 200
        assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200
        zeilen = {x["id"]: x for x in w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]["artikel"]}
        assert zeilen[b["id"]]["zustand"] == "erledigt", zeilen[b["id"]]

        # Anhänge: zu viele Seiten scheitern, bevor sie zusammengefügt werden; ein PDF, das sich nicht anfügen
        # lässt (kaputte Anmerkung), wird auch allein abgewiesen – Lieferung 3 hängt es ans Protokoll.
        pid = starten(p1, a["id"]).json["pruefung"]["id"]
        url = f"/api/material/pruefungen/{pid}/anhaenge"
        seiten = " ".join("3 0 R" for _ in range(300))
        viele = pdf_roh({1: "<< /Type /Catalog /Pages 2 0 R >>", 2: f"<< /Type /Pages /Kids [{seiten}] /Count 300 >>",
                         3: "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 9 9] >>"})
        r = p1.post(url, data={"file": [(io.BytesIO(viele), "viele.pdf"), (jpeg(), "x.jpg")]}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 400 and "Seiten" in r.json["error"], r.get_json()
        kaputt = pdf_roh({1: "<< /Type /Catalog /Pages 2 0 R >>", 2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                          3: "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 9 9] /Annots [5 0 R] >>",
                          5: "<< /Subtype /Link /Dest [99 0 R /XYZ] /A 77 0 R"})
        r = p1.post(url, data={"file": [(io.BytesIO(kaputt), "kaputt.pdf")]}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 400, (r.status_code, r.get_json())
        ablage = os.path.join(tmp, "media", "material", "anhang")
        assert not os.path.isdir(ablage) or not os.listdir(ablage)        # nichts Halbes liegen geblieben
    print("Review-Befunde Lieferung 2 (Kennungen, Dialoge, Anhänge) nachgestellt und behoben.")


def test_listen_und_formular():
    """Wünsche aus der Durchsicht von Lieferung 2: lange Prüfanweisungen, sortierbare Listen."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, kp, w, p1 = k["adm"], k["katalog"], k["wart"], k["pruefer"]
        ids = katalog_grund(adm)
        pruef_formulare(kp, ids)
        # Ein Prüfpunkt darf eine ganze Prüfanweisung sein (bis 1000 Zeichen) – im Editor wie im Import.
        anweisung = "Kontrolle des Zustands der Verriegelungshülse (z. B. Deformierungen, Risse, Korrosion). " * 10
        assert 800 < len(anweisung.strip()) <= 1000
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "punkte": [
            {"text": anweisung, "art": "yesno", "soll": "nein"}]})
        assert r.status_code == 201 and r.json["formular"]["punkte"][0]["text"] == anweisung.strip(), r.get_json()
        r = kp.post("/api/material/formulare", json={"kategorie_id": ids["gurte"], "punkte": [
            {"text": "x" * 1001, "art": "yesno", "soll": "nein"}]})
        assert r.status_code == 400 and "1000" in r.json["error"], r.get_json()
        # Das Formular eines Produkts nennt dessen Kategorie (die Leiste links markiert sie).
        spez = kp.get(f"/api/material/formulare?produkt={ids['gurt']}").json["formulare"][0]["id"]
        assert kp.get(f"/api/material/formulare/{spez}").json["formular"]["ziel"]["kategorie_id"] == ids["gurte"]

        # Katalog: sortierbar nach Hersteller, Intervall (auch geerbt), Bestand – auf dem Server, über alle Seiten.
        r = adm.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Alpenwerk",
                                                     "model": "HMS Zeta", "material_kind": "metall_hardware", "interval_months": 6})
        assert r.status_code == 201, r.get_json()
        zeta = r.json["produkt"]["id"]
        def produkte(**a):
            r = kp.get("/api/material/produkte", query_string=dict(a, pro_seite=2))
            assert r.status_code == 200, r.get_json()
            return [x["id"] for x in r.json["produkte"]], r.json["gesamt"]
        assert produkte(sort="hersteller") == ([zeta, ids["gurt"]], 3)
        assert produkte(sort="hersteller", richtung="ab")[0][0] in (ids["gurt"], ids["hms"])
        assert produkte(sort="intervall", seite=1)[0][0] == zeta                   # 6 Monate vor 12
        assert produkte(sort="intervall", richtung="ab", seite=2)[0] == [zeta]      # absteigend: zuletzt
        gid, _ = gliederung(w)
        neuer_artikel(w, ids["hms"], gid, serial_no="H1")
        neuer_artikel(w, ids["hms"], gid, serial_no="H2")
        assert produkte(sort="bestand", richtung="ab")[0][0] == ids["hms"]
        for falsch in ({"sort": "passwort"}, {"sort": "hersteller", "richtung": "quer"}):
            assert kp.get("/api/material/produkte", query_string=falsch).status_code == 400

        # Artikellisten: Ordner, Fälligkeiten und Suche sortieren nach Spalte, Status nach Dringlichkeit.
        z = neuer_artikel(w, zeta, gid, serial_no="Z1")
        assert abschluss(p1, starten(p1, z["id"]).json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        def ordner(**a):
            r = w.get(f"/api/material/ordner/{gid}", query_string=a)
            assert r.status_code == 200, r.get_json()
            return [x["serial_no"] for x in r.json["ordner"]["artikel"]]
        assert ordner(sort="hersteller") == ["Z1", "H1", "H2"]
        assert ordner(sort="serie", richtung="ab") == ["Z1", "H2", "H1"]
        assert ordner(sort="status")[-1] == "Z1"                                    # neu vor einsatzbereit
        assert ordner(sort="faellig")[:2] == ["H1", "H2"]                           # Eingangsprüfung zuerst
        r = w.get("/api/material/faellig", query_string={"status": "neu,einsatzbereit", "sort": "hersteller"})
        assert [x["serial_no"] for x in r.json["artikel"]] == ["Z1", "H1", "H2"], r.get_json()
        r = w.get("/api/material/suche", query_string={"q": "M-0", "sort": "serie", "richtung": "ab"})
        assert [x["serial_no"] for x in r.json["treffer"]] == ["Z1", "H2", "H1"], r.get_json()
        assert w.get(f"/api/material/ordner/{gid}", query_string={"sort": "ablage; DROP TABLE mat_item"}).status_code == 400

        # Den Namen eines Herstellerdokuments ändert der Katalogpfleger nachträglich – nur den Namen.
        r = kp.post(f"/api/material/produkte/{ids['hms']}/dokumente", data={"kind": "gebrauchsanleitung", "title": "scan_0815",
                    "url": "https://example.org/anleitung.pdf"}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        did = r.json["dokument_id"]
        assert w.put(f"/api/material/dokumente/{did}", json={"title": "x"}).status_code == 403
        assert kp.put(f"/api/material/dokumente/{did}", json={"title": "  "}).status_code == 400
        r = kp.put(f"/api/material/dokumente/{did}", json={"title": "Gebrauchsanleitung HMS Beta"})
        assert r.status_code == 200, r.get_json()
        dok = next(x for x in r.json["dokumente"] if x["id"] == did)
        assert dok["title"] == "Gebrauchsanleitung HMS Beta" and dok["url"] == "https://example.org/anleitung.pdf"
        eintrag = next(e for e in kp.get(f"/api/material/produkte/{ids['hms']}").json["produkt"]["journal"] if e["action"] == "umbenannt")
        assert eintrag["vorher"] == {"title": "scan_0815"} and eintrag["nachher"] == {"title": "Gebrauchsanleitung HMS Beta"}

        # Dokumente an einer Kategorie gelten für alle Produkte darin und in den Unterkategorien.
        kat_url = f"/api/material/kategorien/{ids['psa']}/dokumente"
        assert w.post(kat_url, json={"kind": "pflegehinweis", "url": "https://example.org/pflege.pdf"}).status_code == 403
        r = kp.post(kat_url, data={"kind": "pflegehinweis", "title": "Pflegehinweise PSA", "url": "https://example.org/pflege.pdf"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        kdid = r.json["dokument_id"]
        assert [d["title"] for d in kp.get(kat_url).json["dokumente"]] == ["Pflegehinweise PSA"]
        geerbt = kp.get(f"/api/material/produkte/{ids['hms']}").json["produkt"]["kategorie_dokumente"]   # HMS: Unterkategorie
        assert [(d["title"], d["herkunft"]["id"]) for d in geerbt] == [("Pflegehinweise PSA", ids["psa"])], geerbt
        h1 = next(x for x in w.get(f"/api/material/ordner/{gid}").json["ordner"]["artikel"] if x["serial_no"] == "H1")
        assert "Pflegehinweise PSA" in [d["title"] for d in w.get(f"/api/material/artikel/{h1['id']}").json["artikel"]["dokumente"]]
        # Umbenennen, neue Version, zurückziehen wie am Produkt; die Prüfung merkt sich, was am Prüftag galt.
        assert kp.put(f"/api/material/dokumente/{kdid}", json={"title": "Pflegehinweise PSA (Hersteller)"}).status_code == 200
        r = kp.post(f"/api/material/dokumente/{kdid}/version", data={"title": "Pflegehinweise PSA 2026", "url": "https://example.org/pflege2.pdf"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201 and [d["title"] for d in r.json["dokumente"] if d["gilt"]] == ["Pflegehinweise PSA 2026"], r.get_json()
        pr = starten(p1, h1["id"]).json["pruefung"]
        assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200
        doks = p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["dokumente"]
        assert any(d["title"] == "Pflegehinweise PSA 2026" and d["kategorie"] == "PSA gegen Absturz" for d in doks), doks
        # Eine leere Kategorie lässt sich samt ihren Dokumenten löschen; das Journal vermerkt es.
        leer_id = adm.post("/api/material/kategorien", json={"name": "Leer"}).json["kategorie"]["id"]
        r = kp.post(f"/api/material/kategorien/{leer_id}/dokumente", data={"kind": "sonstiges", "url": "https://example.org/x.pdf"},
                    headers=H, content_type="multipart/form-data")
        leer_dok = r.json["dokument_id"]
        assert kp.delete(f"/api/material/kategorien/{leer_id}", headers=H).status_code == 200
        with app.app_context():
            from app import db
            assert db.query("SELECT 1 FROM mat_product_document WHERE id = ?", (leer_dok,), one=True) is None
            assert db.query("SELECT 1 FROM mat_audit WHERE entity = 'document' AND entity_id = ? AND action = 'geloescht'",
                            (leer_dok,), one=True)
    print("Listen- und Formulartest bestanden.")


def test_migration_lieferung2():
    """Eine Datenbank aus Lieferung 1 (Schemaversion 1) kommt mit allen Zeilen auf Version 2."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        for t in sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")):
            if t.startswith("mat_") and not t.endswith(("_data", "_idx", "_config", "_docsize", "_content")):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.execute("DROP TABLE IF EXISTS mat_meta")
        conn.execute("CREATE TABLE mat_meta (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)")
        for sql in models.SCHRITT_1:
            conn.execute(sql)
        conn.executemany("INSERT INTO mat_meta VALUES (?, ?)", [("schema_version", "1"), ("inventar_zaehler", "2"),
                                                               ("volltext", "0")])
        ts = "2026-10-16T08:00:00+00:00"
        conn.execute("INSERT INTO mat_category (id, name, created_at, updated_at) VALUES (1, 'K', ?, ?)", (ts, ts))
        conn.execute("INSERT INTO mat_product (id, category_id, manufacturer, model, dedupe_key, material_kind, interval_months, "
                     "created_at, updated_at) VALUES (1, 1, 'H', 'M', 'hm', 'metall_hardware', 12, ?, ?)", (ts, ts))
        conn.execute("INSERT INTO mat_folder (id, name, kind, created_at, updated_at) VALUES (1, 'G', 'gliederung', ?, ?)", (ts, ts))
        for iid in (1, 2):
            conn.execute("INSERT INTO mat_item (id, product_id, folder_id, serial_no, inventory_no, next_due_on, qr_token, "
                         "created_at, updated_at) VALUES (?, 1, 1, ?, ?, '2027-01-01', ?, ?, ?)",
                         (iid, f"S{iid}", f"M-00000{iid}", f"tok{iid}", ts, ts))
        conn.execute("INSERT INTO mat_inspection (id, item_id, inspected_on, kind, result, completed_at, created_at, updated_at) "
                     "VALUES (1, 1, '2026-05-01', 'periodisch', 'einsatzbereit', ?, ?, ?)", (ts, ts, ts))
        conn.execute("INSERT INTO mat_inspection (id, item_id, inspected_on, kind, created_at, updated_at) "
                     "VALUES (2, 2, '2026-06-01', 'periodisch', ?, ?)", (ts, ts))
        conn.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_text, editor) VALUES (1, 'a', 'yesno'), "
                     "(2, 'b', 'yesno')")
        conn.execute("INSERT INTO mat_inspection_attachment (inspection_id, kind, file_path, sha256, uploaded_at) "
                     "VALUES (1, 'sonstiges', 'x.pdf', '00', ?)", (ts,))
        conn.execute("INSERT INTO mat_product_document (id, product_id, kind, title, url, valid_from, uploaded_at) "
                     "VALUES (7, 1, 'gebrauchsanleitung', 'Anleitung', 'https://example.org/a.pdf', '2026-01-01', ?)", (ts,))
        conn.commit()
        conn.close()
        app = make_app(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == str(models.SCHEMA_VERSION)
        # Schritt 3: Dokumente bleiben; eins hängt jetzt an Produkt oder Kategorie, nie an beidem oder keinem.
        assert conn.execute("SELECT id, product_id, category_id, title FROM mat_product_document").fetchall() == \
            [(7, 1, None, "Anleitung")]
        conn.execute("INSERT INTO mat_product_document (category_id, kind, title, url, valid_from, uploaded_at) "
                     "VALUES (1, 'pflegehinweis', 'Pflege', 'https://example.org/p.pdf', '2026-01-01', ?)", (ts,))
        for falsch in ("NULL, NULL", "1, 1"):
            try:
                conn.execute(f"INSERT INTO mat_product_document (product_id, category_id, kind, title, url, valid_from, "
                             f"uploaded_at) VALUES ({falsch}, 'sonstiges', 'x', 'https://example.org/x', '2026-01-01', ?)", (ts,))
                raise AssertionError("Dokument ohne bzw. mit zwei Zielen angenommen: " + falsch)
            except sqlite3.IntegrityError:
                pass
        conn.rollback()
        assert conn.execute("SELECT id, item_id, kind, result FROM mat_inspection ORDER BY id").fetchall() == \
            [(1, 1, "periodisch", "einsatzbereit"), (2, 2, "periodisch", None)]
        assert conn.execute("SELECT COUNT(*) FROM mat_inspection_result").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM mat_inspection_attachment").fetchone()[0] == 1
        # Wer schon geprüft wurde, ist nicht „neu“; wer nur einen Entwurf hat, schon.
        assert conn.execute("SELECT id, last_inspected_on FROM mat_item ORDER BY id").fetchall() == [(1, "2026-05-01"), (2, None)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Schritt 4: die Tabelle für Produktmeldungen; eine Ablehnung braucht eine Begründung.
        assert conn.execute("SELECT COUNT(*) FROM mat_product_request").fetchone()[0] == 0
        # Schritt 5: Durchgänge lassen sich abbrechen.
        assert "aborted" in {r[1] for r in conn.execute("PRAGMA table_info(mat_round)")}
        try:
            conn.execute("INSERT INTO mat_product_request (manufacturer, model, dedupe_key, status, created_at, resolved_at) "
                         "VALUES ('H', 'M', 'h|m|', 'abgelehnt', ?, ?)", (ts, ts))
            raise AssertionError("Ablehnung ohne Begründung angenommen")
        except sqlite3.IntegrityError:
            pass
        conn.rollback()              # sonst bliebe die Transaktion offen, und das Pragma unten wirkte nicht
        # Die Eingangsprüfung ist jetzt eine erlaubte Art; der Entwurf je Artikel bleibt einzig.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, created_at, updated_at) "
                     "VALUES (1, '2026-10-17', 'eingang', ?, ?)", (ts, ts))
        try:
            conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, created_at, updated_at) "
                         "VALUES (1, '2026-10-17', 'periodisch', ?, ?)", (ts, ts))
            raise AssertionError("zweiter offener Entwurf angenommen")
        except sqlite3.IntegrityError:
            pass
        # Seit Schritt 6 (Lieferung 3) ist eine abgeschlossene Prüfung unlöschbar – auch per SQL; ihre Befunde und
        # Anhänge ebenso. Ein Entwurf nimmt beim Löschen seine Befunde mit.
        for sql in ("DELETE FROM mat_inspection WHERE id = 1", "DELETE FROM mat_inspection_result WHERE inspection_id = 1",
                    "DELETE FROM mat_inspection_attachment WHERE inspection_id = 1",
                    "UPDATE mat_inspection SET remarks = 'nachträglich' WHERE id = 1"):
            try:
                conn.execute(sql)
                raise AssertionError("abgeschlossene Prüfung geändert: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "unveränderlich" in str(exc), exc
        conn.execute("DELETE FROM mat_inspection WHERE id = 2")
        assert conn.execute("SELECT COUNT(*) FROM mat_inspection_result WHERE inspection_id = 2").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM mat_inspection_attachment").fetchone()[0] == 1
        conn.rollback()
        conn.close()
        # Ein zweiter Start ändert nichts mehr.
        make_app(tmp)
        with app.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM mat_inspection", one=True)["n"] == 2
    print("Migrationstest Lieferung 2 bestanden.")


# --- Meldungen fehlender Produkte ----------------------------------------------------------------------

def test_produktmeldung():
    """Ein Materialwart meldet ein Produkt, das im Katalog fehlt; ein Katalogpfleger pflegt es ein (neu oder
    vorhanden) oder lehnt ab. Die Katalogpfleger bekommen die Meldung, der Melder den Bescheid per Mail."""
    from app.material.services import meldung
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    post = []
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            ids = katalog_grund(k["adm"])
            gid, _ = gliederung(k["wart"])

            def melden(c, **f):
                return c.post("/api/material/meldungen", json=dict({"manufacturer": "Irgendwer", "model": "Ding"}, **f), headers=H)

            # Melden mit Foto, Links (doppelt, ohne Schema, Leerzeile), Kategorie und Ordner – als Formular.
            r = k["wart"].post("/api/material/meldungen", headers=H, data={
                "manufacturer": "Bergwerk", "model": "Rettungsgurt Gamma", "article_no": "RG-3", "norm": "EN 813",
                "category_id": str(ids["gurte"]), "folder_id": str(gid),
                "links": "https://example.org/gamma\nwww.example.org/gamma.pdf\n\nhttps://example.org/gamma",
                "note": "Größe M/L\nfür die Strömungsretter", "fotos": (jpeg(), "etikett.jpg")})
            assert r.status_code == 201, r.get_json()
            m = r.json["meldung"]
            assert m["status"] == "offen" and m["eigen"] and m["note"] == "Größe M/L\nfür die Strömungsretter", m
            assert m["links"] == ["https://example.org/gamma", "https://www.example.org/gamma.pdf"], m["links"]
            assert len(m["fotos"]) == 1 and m["fotos"][0]["vorschau"].startswith("/media/material/thumb/"), m["fotos"]
            assert m["kategorie"]["pfad"] == "PSA gegen Absturz / Gurte" and m["ordner"]["pfad"] == "OG Musterstadt", m
            assert k["wart"].get(m["fotos"][0]["vorschau"]).status_code == 200
            assert [p[0] for p in post] == ["katalog@example.org"], post
            assert "Rettungsgurt Gamma" in post[0][1] and "https://www.example.org/gamma.pdf" in post[0][2] \
                and "https://strömis.de/material/katalog/meldungen" in post[0][2] and "OG Musterstadt" in post[0][2], post[0]

            # Eingaben: Pflichtfelder, nur http(s)-Links, höchstens fünf, Kategorie muss es geben.
            for falsch, teil in (({"manufacturer": " "}, "Hersteller"), ({"links": "javascript:alert(1)"}, "http"),
                                 ({"links": "ftp://example.org/x"}, "http"), ({"links": ["https://example.org/a", 3]}, "Text"),
                                 ({"links": "\n".join(f"https://example.org/{i}" for i in range(6))}, "Höchstens"),
                                 ({"links": "https://example.org/" + "x" * 500}, "zu lang"), ({"category_id": 99999}, "Kategorie"),
                                 ({"folder_id": 99999}, "Ordner"), ({"note": "x" * 2001}, "Bemerkung")):
                r = melden(k["wart"], **falsch)
                assert r.status_code in (400, 404) and teil in r.json["error"], (falsch, r.get_json())
            # Fotos: höchstens drei, nur Bilder – und ein abgewiesenes lässt keine Datei zurück.
            orig = os.path.join(app.config["MEDIA_DIR"], "material", "orig")
            vorher = sorted(os.listdir(orig))
            r = k["wart"].post("/api/material/meldungen", headers=H, data={
                "manufacturer": "X", "model": "Y", "fotos": [(jpeg(), "a.jpg"), (io.BytesIO(PDF), "b.pdf")]})
            assert r.status_code == 400 and "kein Foto" in r.json["error"] and sorted(os.listdir(orig)) == vorher, r.get_json()
            r = k["wart"].post("/api/material/meldungen", headers=H, data={
                "manufacturer": "X", "model": "Y", "fotos": [(jpeg(), f"{i}.jpg") for i in range(4)]})
            assert r.status_code == 400 and "Höchstens 3 Fotos" in r.json["error"] and sorted(os.listdir(orig)) == vorher
            # Was schon im Katalog steht (gleiche Dublette, andere Schreibweise), wird nicht gemeldet.
            r = melden(k["wart"], manufacturer="testwerk", model="Gurt-Alpha", article_no="GA 100")
            assert r.status_code == 409 and "steht schon im Katalog" in r.json["error"], r.get_json()
            # Melden dürfen Materialwarte (die Verwaltung ist überall Materialwart), sonst niemand.
            for wer in ("fuehrung", "pruefer", "nutzer", "katalog"):
                assert melden(k[wer]).status_code == 403, wer
            r = melden(k["adm"], manufacturer="Adminwerk", model="Seil Delta")
            assert r.status_code == 201
            m2 = r.json["meldung"]["id"]
            assert post[-1][0] == "katalog@example.org"

            # Sehen: der Materialwart standardmäßig seine, der Katalogpfleger alle offenen (älteste zuerst). Lesen darf
            # jeder mit Zugang zum Modul (Lieferung 4) – abarbeiten („bearbeiten“) nur der Katalogpfleger.
            r = k["wart"].get("/api/material/meldungen")
            assert r.status_code == 200 and not r.json["alle"] and [x["id"] for x in r.json["meldungen"]] == [m["id"]]
            assert k["wart"].get(f"/api/material/meldungen/{m2}").status_code == 200
            r = k["katalog"].get("/api/material/meldungen")
            assert r.json["alle"] and r.json["bearbeiten"] and [x["id"] for x in r.json["meldungen"]] == [m["id"], m2] \
                and r.json["offen"] == 2
            for wer in ("fuehrung", "wart"):
                r = k[wer].get("/api/material/meldungen", query_string={} if wer == "fuehrung" else {"eigene": "0"})
                assert r.status_code == 200 and r.json["alle"] and not r.json["bearbeiten"], (wer, r.get_json())
                assert [x["id"] for x in r.json["meldungen"]] == [m["id"], m2], wer
            assert k["nutzer"].get("/api/material/meldungen").status_code == 403
            assert k["katalog"].get("/api/material/start").json["meldungen_offen"] == 2
            assert k["wart"].get("/api/material/start").json["meldungen_offen"] is None
            assert k["katalog"].get("/material/katalog/meldungen").status_code == 200
            assert k["wart"].get("/material/katalog/meldungen").status_code == 200
            assert k["nutzer"].get("/material/katalog/meldungen").status_code == 403

            # Einpflegen als neues Produkt: Produkt und erledigte Meldung in einem Zug, Bescheid an den Melder.
            post.clear()
            daten = {"category_id": ids["gurte"], "manufacturer": "Bergwerk", "model": "Rettungsgurt Gamma", "article_no": "RG-3",
                     "material_kind": "textil", "lifetime_years": 10, "antwort": "Mit Gebrauchsanleitung angelegt."}
            assert k["wart"].post(f"/api/material/meldungen/{m['id']}/produkt", json=daten, headers=H).status_code == 403
            r = k["katalog"].post(f"/api/material/meldungen/{m['id']}/produkt", json=daten, headers=H)
            assert r.status_code == 201, r.get_json()
            pid = r.json["produkt"]["id"]
            assert r.json["meldung"]["status"] == "eingepflegt" and r.json["meldung"]["produkt"]["id"] == pid
            assert [p[0] for p in post] == ["wart@example.org"], post
            assert f"https://strömis.de/material/artikel/neu?produkt={pid}&ordner={gid}" in post[0][2] \
                and "Mit Gebrauchsanleitung angelegt." in post[0][2] and "ist im Katalog" in post[0][1], post[0]
            with app.app_context():
                from app import db
                anzahl = db.query("SELECT COUNT(*) AS n FROM mat_product", one=True)["n"]
            r = k["katalog"].post(f"/api/material/meldungen/{m['id']}/produkt", json=dict(daten, model="Gurt Gamma 2"), headers=H)
            assert r.status_code == 409 and "schon erledigt" in r.json["error"], r.get_json()
            with app.app_context():
                assert db.query("SELECT COUNT(*) AS n FROM mat_product", one=True)["n"] == anzahl
            journal = k["katalog"].get(f"/api/material/produkte/{pid}").json["produkt"]["journal"]
            assert {("request", "angelegt"), ("request", "eingepflegt"), ("product", "angelegt")} <= \
                {(e["entity"], e["action"]) for e in journal}, journal
            # Eine Meldung, deren Produkt inzwischen anders in den Katalog kam, zeigt es als Treffer – ein Klick ordnet zu.
            r = k["katalog"].post("/api/material/produkte", headers=H, json={
                "category_id": ids["karabiner"], "manufacturer": "Adminwerk", "model": "Seil-Delta", "material_kind": "metall_hardware",
                "interval_months": 12})
            p2 = r.json["produkt"]["id"]
            treffer = {x["id"]: x["treffer"] for x in k["katalog"].get("/api/material/meldungen").json["meldungen"]}
            assert treffer == {m2: treffer[m2]} and treffer[m2]["id"] == p2, treffer
            post.clear()
            r = k["katalog"].post(f"/api/material/meldungen/{m2}/zuordnen", json={"product_id": p2}, headers=H)
            assert r.status_code == 200 and r.json["meldung"]["status"] == "eingepflegt" and r.json["meldung"]["treffer"] is None
            assert [p[0] for p in post] == ["admin@example.org"], post

            # Ablehnen nur mit Begründung; danach ist die Meldung zu.
            m3 = melden(k["wart"], manufacturer="Leuchtwerk", model="Stirnlampe").json["meldung"]["id"]
            assert k["katalog"].post(f"/api/material/meldungen/{m3}/ablehnen", json={"antwort": "  "}, headers=H).status_code == 400
            post.clear()
            r = k["katalog"].post(f"/api/material/meldungen/{m3}/ablehnen", json={"antwort": "Lampen gehören nicht ins Modul."},
                                  headers=H)
            assert r.status_code == 200 and r.json["meldung"]["status"] == "abgelehnt", r.get_json()
            assert [p[0] for p in post] == ["wart@example.org"] and "nicht aufgenommen" in post[0][1] \
                and "Lampen gehören nicht ins Modul." in post[0][2], post
            assert k["katalog"].post(f"/api/material/meldungen/{m3}/zuordnen", json={"product_id": p2}, headers=H).status_code == 409
            eigene = k["wart"].get("/api/material/meldungen").json
            assert eigene["filter"] == "alle" and [(x["id"], x["status"]) for x in eigene["meldungen"]] == \
                [(m3, "abgelehnt"), (m["id"], "eingepflegt")], eigene
            assert {x["id"] for x in k["katalog"].get("/api/material/meldungen?status=erledigt").json["meldungen"]} == {m["id"], m2, m3}
            assert k["katalog"].get("/api/material/meldungen").json["meldungen"] == []

            # Wird das Produkt gelöscht, bleibt die Meldung eingepflegt – ohne Produkt.
            assert k["katalog"].delete(f"/api/material/produkte/{pid}", headers=H).status_code == 200
            x = k["wart"].get(f"/api/material/meldungen/{m['id']}").json["meldung"]
            assert x["status"] == "eingepflegt" and x["produkt"] is None and x["produkt_geloescht"], x
            # Ohne Katalogpfleger geht die Meldung an die Verwaltung.
            with app.app_context():
                db.execute("UPDATE users SET mat_katalog = 0")
            post.clear()
            assert melden(k["wart"], manufacturer="Helmwerk", model="Helm Epsilon").status_code == 201
            assert [p[0] for p in post] == ["admin@example.org"], post
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt
    print("Meldungstest bestanden.")


def test_produktmeldung_loeschen():
    """Wer eine Meldung gemacht hat, löscht sie – offen oder erledigt; sonst niemand. Ein Produkt aus der Meldung
    bleibt, ihre Fotos gehen mit, das Journal vermerkt die Löschung."""
    from app.material.services import meldung
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            ids = katalog_grund(k["adm"])
            orig = os.path.join(app.config["MEDIA_DIR"], "material", "orig")
            vorher = sorted(os.listdir(orig)) if os.path.isdir(orig) else []
            r = k["wart"].post("/api/material/meldungen", headers=H, data={"manufacturer": "Bergwerk", "model": "Gurt Zeta",
                                                                          "fotos": (jpeg(), "etikett.jpg")})
            assert r.status_code == 201, r.get_json()
            m1 = r.json["meldung"]["id"]
            assert len(os.listdir(orig)) == len(vorher) + 1
            for wer in ("katalog", "adm", "fuehrung", "nutzer"):
                assert k[wer].delete(f"/api/material/meldungen/{m1}", headers=H).status_code == 403, wer
            assert app.test_client().delete(f"/api/material/meldungen/{m1}", headers=H).status_code == 401
            assert k["wart"].delete(f"/api/material/meldungen/{m1}", headers=H).status_code == 200
            assert k["wart"].get(f"/api/material/meldungen/{m1}").status_code == 404
            assert sorted(os.listdir(orig)) == vorher
            # Wer die Meldung gerade abarbeiten wollte, erfährt, dass sie weg ist – und es entsteht kein Produkt.
            gamma = {"category_id": ids["gurte"], "manufacturer": "Bergwerk", "model": "Gurt Zeta", "material_kind": "textil",
                     "lifetime_years": 10}
            assert k["katalog"].post(f"/api/material/meldungen/{m1}/produkt", headers=H, json=gamma).status_code == 404
            assert k["katalog"].get("/api/material/produkte?q=Zeta").json["gesamt"] == 0
            # Eine erledigte Meldung löschen: Das Produkt aus ihr bleibt.
            m2 = k["wart"].post("/api/material/meldungen", headers=H, json={"manufacturer": "Bergwerk", "model": "Gurt Eta"}).json["meldung"]["id"]
            r = k["katalog"].post(f"/api/material/meldungen/{m2}/produkt", headers=H, json=dict(gamma, model="Gurt Eta"))
            assert r.status_code == 201, r.get_json()
            pid = r.json["produkt"]["id"]
            assert k["wart"].delete(f"/api/material/meldungen/{m2}", headers=H).status_code == 200
            assert k["katalog"].get(f"/api/material/produkte/{pid}").status_code == 200
            assert k["wart"].get("/api/material/meldungen").json["meldungen"] == []
            with app.app_context():
                from app import db
                aktionen = [x["action"] for x in db.query("SELECT action FROM mat_audit WHERE entity = 'request' AND entity_id = ? "
                                                          "ORDER BY id", (m2,))]
            assert aktionen == ["angelegt", "eingepflegt", "geloescht"], aktionen
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt
    print("Meldungs-Löschtest bestanden.")


def test_durchgang_abbrechen():
    """Ein Durchgang lässt sich vorzeitig beenden: Ohne Abgeschlossenes verschwindet er, sonst endet er als
    „abgebrochen“. Offene Prüfungen darin laufen als einzelne Prüfungen weiter."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid, serial_no="A")
        b = neuer_artikel(w, ids["hms"], gid, serial_no="B")
        c = neuer_artikel(w, ids["hms"], gid, serial_no="C")
        # Nur ein Entwurf darin: Abbrechen entfernt den Durchgang, der Entwurf läuft einzeln weiter.
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Versehen"}).json["durchgang"]["id"]
        pid_a = starten(p1, a["id"], durchgang_id=rid).json["pruefung"]["id"]
        for x in (k["fuehrung"], k["nutzer"], k["katalog"]):
            assert x.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={}).status_code == 403
        r = w.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={})
        assert r.status_code == 200 and r.json["durchgang"] is None, r.get_json()
        assert w.get(f"/api/material/durchgaenge/{rid}").status_code == 404
        assert p1.get(f"/api/material/pruefungen/{pid_a}").json["pruefung"]["round_id"] is None
        # Mit Geprüftem endet er als abgebrochen: Geprüftes bleibt, der Rest steht darin als nicht geprüft.
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Jahresprüfung"}).json["durchgang"]["id"]
        assert p1.get(f"/api/material/pruefungen/{pid_a}").json["pruefung"]["round_id"] == rid   # übernommen
        r = starten(p1, b["id"], durchgang_id=rid)
        assert abschluss(p1, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        r = p1.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={})
        assert r.status_code == 200, r.get_json()
        d = r.json["durchgang"]
        assert not d["offen"] and d["abgebrochen"] and d["zaehlung"] == {
            "gesamt": 3, "offen": 0, "in_pruefung": 0, "erledigt": 1, "ausgenommen": 0, "nicht_geprueft": 2}, d
        zustand = {x["id"]: x["zustand"] for x in w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]["artikel"]}
        assert zustand == {a["id"]: "nicht_geprueft", b["id"]: "erledigt", c["id"]: "nicht_geprueft"}, zustand
        # Der Entwurf ist wieder eine einzelne Prüfung: abschließbar, zählt aber nicht mehr zum Durchgang.
        assert p1.get(f"/api/material/pruefungen/{pid_a}").json["pruefung"]["round_id"] is None
        assert abschluss(p1, pid_a, ergebnis="einsatzbereit").status_code == 200
        d = w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        assert d["zaehlung"]["erledigt"] == 1 and d["zaehlung"]["nicht_geprueft"] == 2, d["zaehlung"]
        # Vorbei ist vorbei; ein normal abgeschlossener Durchgang heißt weiter nicht „abgebrochen“.
        assert w.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={}).status_code == 409
        assert w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 409
        assert w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": c["id"], "grund": "x"}).status_code == 409
        with app.app_context():
            from app import db
            aktionen = [x["action"] for x in db.query("SELECT action FROM mat_audit WHERE entity = 'round' AND entity_id = ? "
                                                      "ORDER BY id", (rid,))]
            entwurf = [x["action"] for x in db.query("SELECT action FROM mat_audit WHERE entity = 'inspection' AND entity_id = ? "
                                                     "ORDER BY id", (pid_a,))]
        # Seit Lieferung 3 bekommt auch ein abgebrochener Durchgang sein Sammelprotokoll („festgeschrieben“).
        assert aktionen[0] == "eroeffnet" and aktionen[-2:] == ["abgebrochen", "festgeschrieben"], aktionen
        assert entwurf.count("geaendert") == 2, entwurf
        rid2 = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Neu"}).json["durchgang"]["id"]
        for x in (a, b, c):
            pid = starten(p1, x["id"], durchgang_id=rid2).json["pruefung"]["id"]
            assert abschluss(p1, pid, ergebnis="einsatzbereit").status_code == 200
        d = w.post(f"/api/material/durchgaenge/{rid2}/abschliessen", json={}).json["durchgang"]
        assert not d["offen"] and not d["abgebrochen"] and d["zaehlung"]["nicht_geprueft"] == 0, d
    print("Abbruchtest bestanden.")


def test_artikelnummer_eindeutig():
    """Eine Artikelnummer gibt es im Katalog nur einmal – Schreibweise egal, leer zählt nicht. Geprüft beim Anlegen,
    beim Ändern der Nummer, im Katalogimport und bei Meldungen; die Oberfläche fragt schon beim Tippen nach."""
    from app.material.services import meldung
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            ids = katalog_grund(k["adm"])
            kp = k["katalog"]

            def neu(**f):
                return kp.post("/api/material/produkte", json=dict({"category_id": ids["karabiner"], "manufacturer": "Anderwerk",
                                                                   "model": "Karabiner X", "material_kind": "metall_hardware",
                                                                   "interval_months": 12}, **f))
            # Anlegen: dieselbe Nummer bei anderem Hersteller und Modell – auch anders geschrieben – wird abgewiesen.
            for nr in ("GA-100", "ga 100", "GA100"):
                r = neu(article_no=nr)
                assert r.status_code == 409 and "schon vergeben" in r.json["error"] and "Gurt Alpha" in r.json["error"], r.get_json()
            # Ohne Artikelnummer (auch „-“ oder „/“) beliebig oft.
            for i, nr in enumerate(("", "-", "", "/")):
                assert neu(model=f"Ohne Nummer {i}", article_no=nr).status_code == 201, nr
            r = neu(article_no="AX-1")
            assert r.status_code == 201
            ax = r.json["produkt"]["id"]
            # Ändern: auf eine vergebene Nummer nicht; die eigene (anders geschrieben) behalten schon.
            r = kp.put(f"/api/material/produkte/{ax}", json={"article_no": "HB 7"})
            assert r.status_code == 409 and "HMS Beta" in r.json["error"], r.get_json()
            assert kp.put(f"/api/material/produkte/{ax}", json={"article_no": "ax1", "description": "neu"}).status_code == 200
            # Eine Dopplung aus der Zeit vor der Regel blockiert andere Änderungen nicht – nur eine neue vergebene Nummer.
            with app.app_context():
                from app import db
                from app.material.services import katalog as kat
                ts = "2026-01-01T00:00:00+00:00"
                db.execute("INSERT INTO mat_product (category_id, manufacturer, model, article_no, dedupe_key, material_kind, "
                           "interval_months, created_at, updated_at) VALUES (?, 'Altwerk', 'Altmodell', 'GA-100', ?, "
                           "'metall_hardware', 12, ?, ?)", (ids["karabiner"], kat.dedupe_key("Altwerk", "Altmodell", "GA-100"), ts, ts))
                altid = db.query("SELECT id FROM mat_product WHERE manufacturer = 'Altwerk'", one=True)["id"]
            assert kp.put(f"/api/material/produkte/{altid}", json={"description": "geändert"}).status_code == 200
            assert kp.put(f"/api/material/produkte/{altid}", json={"article_no": "HB-7"}).status_code == 409
            # Hinweis beim Tippen: wem die Nummer gehört (ohne das gerade bearbeitete Produkt).
            r = kp.get("/api/material/produkte/artikelnummer?nr=ga%20100")
            assert r.status_code == 200 and r.json["produkt"]["name"] == "Testwerk Gurt Alpha", r.get_json()
            assert kp.get(f"/api/material/produkte/artikelnummer?nr=GA-100&ausser={ids['gurt']}").json["produkt"]["name"] == "Altwerk Altmodell"
            for nr in ("-", "ZZ-9", ""):
                assert kp.get(f"/api/material/produkte/artikelnummer?nr={nr}").json["produkt"] is None, nr
            assert k["wart"].get("/api/material/produkte/artikelnummer?nr=GA-100").status_code == 200
            assert k["nutzer"].get("/api/material/produkte/artikelnummer?nr=GA-100").status_code == 403
            # Meldungen: Gehört die Nummer schon einem Produkt, gibt es nichts zu melden.
            r = k["wart"].post("/api/material/meldungen", headers=H, json={"manufacturer": "Fremdwerk", "model": "Irgendwas",
                                                                          "article_no": "hb-7"})
            assert r.status_code == 409 and "HMS Beta" in r.json["error"], r.get_json()
            # Katalogimport: dieselbe Regel, mit Fehlerzeile – und nichts gespeichert.
            with app.app_context():
                from app.material.services import importer
                bericht = importer.importieren({"format": "stroemis-material-katalog", "version": 1, "produkte": [
                    {"kategorie": ["PSA gegen Absturz", "Karabiner"], "hersteller": "Importwerk", "modell": "Kopie",
                     "artikelnummer": "GA 100", "materialart": "metall_hardware", "intervall_monate": 12}]})
            assert not bericht["gespeichert"] and any("schon vergeben" in f for f in bericht["fehler"]), bericht
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt
    print("Artikelnummerntest bestanden.")


def test_produkt_variante():
    """Ein Produkt als neue Variante kopieren: Stammdaten ja, eine eigene Artikelnummer Pflicht, Dokumente nach
    Wahl (nur aktuelle, Dateien kopiert), Produktbild und spezifische Formulare nie."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)                 # u. a. ein spezifisches Formular für den Gurt Alpha
        kp, gurt = k["katalog"], ids["gurt"]
        assert kp.post(f"/api/material/produkte/{gurt}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H).status_code == 200
        dok = f"/api/material/produkte/{gurt}/dokumente"
        r = kp.post(dok, headers=H, data={"kind": "gebrauchsanleitung", "title": "Anleitung", "valid_from": "2026-01-01",
                                          "file": (io.BytesIO(PDF), "anleitung.pdf")})
        alt_v1 = r.json["dokument_id"]
        r = kp.post(f"/api/material/dokumente/{alt_v1}/version", headers=H, data={"title": "Anleitung", "version": "2026",
                                                                                 "valid_from": "2026-02-01",
                                                                                 "file": (io.BytesIO(PDF + b"%v2"), "anleitung2.pdf")})
        assert r.status_code == 201, r.get_json()
        v2 = r.json["dokument_id"]
        link = kp.post(dok, headers=H, json={"kind": "datenblatt", "title": "Datenblatt", "url": "https://example.org/gurt"}).json["dokument_id"]
        weg = kp.post(dok, headers=H, json={"kind": "sonstiges", "title": "Alt", "url": "https://example.org/alt"}).json["dokument_id"]
        assert kp.post(f"/api/material/dokumente/{weg}/zurueckziehen", headers=H, json={}).status_code == 200
        quelle = kp.get(f"/api/material/produkte/{gurt}").json["produkt"]
        stamm = {f: quelle[f] for f in ("category_id", "manufacturer", "model", "norm", "material_kind", "interval_months",
                                        "lifetime_years", "lifetime_source", "description")}
        url = f"/api/material/produkte/{gurt}/variante"
        assert k["wart"].post(url, json=dict(stamm, article_no="GA-200"), headers=H).status_code == 403
        r = kp.post(url, json=dict(stamm, article_no=" - "), headers=H)
        assert r.status_code == 400 and "eigene Artikelnummer" in r.json["error"], r.get_json()
        r = kp.post(url, json=dict(stamm, article_no="ga 100"), headers=H)            # die alte Nummer: dasselbe Produkt
        assert r.status_code == 409 and "Gurt Alpha" in r.json["error"], r.get_json()
        r = kp.post(url, json=dict(stamm, model="Gurt Alpha L", article_no="HB-7"), headers=H)   # vergeben an HMS Beta
        assert r.status_code == 409 and "schon vergeben" in r.json["error"], r.get_json()
        for falsch in ([alt_v1], [weg], [999999], ["x"]):
            r = kp.post(url, json=dict(stamm, article_no="GA-200", dokumente=falsch), headers=H)
            assert r.status_code == 400, (falsch, r.get_json())
        orig = os.path.join(app.config["MEDIA_DIR"], "material", "dok")
        vorher = set(os.listdir(orig))
        r = kp.post(url, json=dict(stamm, article_no="GA-200", model="Gurt Alpha L", dokumente=[v2, link]), headers=H)
        assert r.status_code == 201, r.get_json()
        neu = r.json["produkt"]
        assert neu["article_no"] == "GA-200" and neu["model"] == "Gurt Alpha L" and neu["lifetime_years"] == quelle["lifetime_years"]
        assert neu["bild"] is None, neu["bild"]
        docs = {d["title"]: d for d in neu["dokumente"]}
        assert set(docs) == {"Anleitung", "Datenblatt"} and docs["Anleitung"]["version"] == "2026", docs
        alt_v2 = next(d for d in quelle["dokumente"] if d["id"] == v2)
        assert docs["Anleitung"]["sha256"] == alt_v2["sha256"] and docs["Anleitung"]["datei"] != alt_v2["datei"]
        assert docs["Datenblatt"]["url"] == "https://example.org/gurt" and not docs["Datenblatt"]["datei"]
        assert len(set(os.listdir(orig)) - vorher) == 1                        # eine Datei kopiert, der Link nicht
        assert kp.get(f"/api/material/formulare?produkt={neu['id']}").json["formulare"] == []
        journal = kp.get(f"/api/material/produkte/{neu['id']}").json["produkt"]["journal"]
        assert any(e["action"] == "variante" and e["nachher"]["von"] == gurt for e in journal), journal
        # Ohne Dokumente geht es auch; und das Löschen der Variante nimmt nur ihre eigenen Dateien mit.
        r = kp.post(url, json=dict(stamm, article_no="GA-300", model="Gurt Alpha XL"), headers=H)
        assert r.status_code == 201 and r.json["produkt"]["dokumente"] == [], r.get_json()
        assert kp.delete(f"/api/material/produkte/{neu['id']}", headers=H).status_code == 200
        assert set(os.listdir(orig)) == vorher
        assert kp.get(f"/api/material/produkte/{gurt}").json["produkt"]["bild"]
    print("Variantentest bestanden.")


def test_monatsangaben():
    """Kauf und Erstgebrauch wie die Herstellung auch als Monat: gespeichert wie eingegeben, gerechnet ab dem
    Monatsersten; der laufende Monat liegt nicht in der Zukunft, der Monat der Herstellung nicht davor."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, _ = gliederung(w)
        dieser = _heute().strftime("%Y-%m")
        naechster = (_heute().replace(day=28) + timedelta(days=5)).strftime("%Y-%m")

        def anlegen(**f):
            return w.post("/api/material/artikel", json=dict({"product_id": ids["hms"], "folder_id": gid}, **f))
        r = w.get(f"/api/material/artikel/vorschlag?product_id={ids['hms']}&folder_id={gid}&first_use_on=2025-04")
        assert r.status_code == 200 and r.json["vorschlag"]["next_due_on"] == "2026-04-01", r.get_json()
        r = anlegen(manufactured_on="2025-01", purchased_on="2025-03", first_use_on="2025-04")
        assert r.status_code == 201, r.get_json()
        a = r.json["artikel"]
        assert (a["purchased_on"], a["first_use_on"], a["next_due_on"]) == ("2025-03", "2025-04", "2026-04-01"), a
        # Der laufende Monat ist erlaubt, der nächste liegt in der Zukunft.
        assert anlegen(purchased_on=dieser).status_code == 201
        r = anlegen(first_use_on=naechster)
        assert r.status_code == 400 and "Zukunft" in r.json["error"], r.get_json()
        r = w.get(f"/api/material/artikel/vorschlag?product_id={ids['hms']}&folder_id={gid}&purchased_on={naechster}")
        assert r.status_code == 400 and "Zukunft" in r.json["error"], r.get_json()
        # Vor der Herstellung nicht – im selben Monat schon, auch neben einem Tagesdatum der Herstellung.
        r = anlegen(manufactured_on="2025-05", first_use_on="2025-04")
        assert r.status_code == 400 and "vor dem Herstelldatum" in r.json["error"], r.get_json()
        assert anlegen(manufactured_on="2025-05-20", first_use_on="2025-05").status_code == 201
        for falsch in ("2025-13", "05/2025", "2025-5"):
            assert anlegen(purchased_on=falsch).status_code == 400, falsch
        # Ändern: ein Monat statt eines Tagesdatums und zurück.
        stand = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["stand"]
        r = w.put(f"/api/material/artikel/{a['id']}", json={"stand": stand, "purchased_on": "2025-02-14"})
        assert r.status_code == 200 and r.json["artikel"]["purchased_on"] == "2025-02-14", r.get_json()
        r = w.put(f"/api/material/artikel/{a['id']}", json={"stand": r.json["artikel"]["stand"], "purchased_on": "2025-02"})
        assert r.status_code == 200 and r.json["artikel"]["purchased_on"] == "2025-02", r.get_json()
    print("Monatstest bestanden.")


# --- Lieferung 3: Nachweis ----------------------------------------------------------------------------------

def pdf_seiten(pfad):
    """Text je Seite – mit pdftotext (poppler-utils), wie im Auftrag; fehlt es, mit pypdf."""
    import shutil
    import subprocess
    if shutil.which("pdftotext"):
        return [subprocess.run(["pdftotext", "-q", "-f", str(i), "-l", str(i), pfad, "-"], capture_output=True,
                               check=True).stdout.decode("utf-8", "replace") for i in range(1, _seitenzahl(pfad) + 1)]
    from pypdf import PdfReader
    return [s.extract_text() or "" for s in PdfReader(pfad).pages]


def _seitenzahl(pfad):
    from pypdf import PdfReader
    return len(PdfReader(pfad).pages)


def _flach(text):
    return " ".join(text.split())


def protokoll_zeile(app, pid=None, rid=None):
    with app.app_context():
        from app import db
        if rid:
            return db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
        return db.query("SELECT * FROM mat_inspection WHERE id = ?", (pid,), one=True)


def festschreiben(c, pid, **d):
    return c.post(f"/api/material/pruefungen/{pid}/festschreiben", json=d)


def test_festschreiben():
    """Die Smoke-Tests aus dem Auftrag zu Lieferung 3: Unterschrift und Urkundennummer, Unveränderlichkeit,
    aufgedruckte Prüfsumme gegen head -c N und Datenbank, file_sha256, Stempel auf jeder Seite, Anhänge mit
    Prüfsumme im Protokoll."""
    import hashlib
    import subprocess
    from pypdf import PdfWriter
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, a["id"]).json["pruefung"]["id"]
        # Ohne Unterschrift im Profil scheitert das Festschreiben – mit Hinweis, wo sie hingehört.
        assert p1.delete("/api/material/unterschrift", headers=H).status_code == 200
        r = festschreiben(p1, pid, ergebnis="einsatzbereit")
        assert r.status_code == 403 and "Unterschrift" in r.json["error"], r.get_json()
        # Ohne Urkundennummer ebenso (die Prüferrolle hängt daran; der Dienst prüft es selbst noch einmal).
        with app.test_request_context():
            from app.material.services import Abgelehnt, pruefung
            try:
                pruefung.abschliessen(pid, {"ergebnis": "einsatzbereit"},
                                      {"id": k["pruefer_id"], "name": "pruefer", "urkunde": "", "unterschrift": b"x"})
                raise AssertionError("ohne Urkundennummer festgeschrieben")
            except Abgelehnt as exc:
                assert exc.code == 403 and "Urkundennummer" in str(exc)
        assert festschreiben(w, pid, ergebnis="einsatzbereit").status_code == 403        # Materialwart ist kein Prüfer
        unterschreiben(p1)
        # Zwei Anhänge: einer kommt hinten ans Protokoll, der andere steht nur im Verzeichnis.
        url = f"/api/material/pruefungen/{pid}/anhaenge"
        ah1 = p1.post(url, data={"file": [(jpeg(800, 1100), "karte.jpg")], "art": "externes_pruefformular",
                                 "titel": "Prüfkarte des Herstellers", "im_protokoll": "ja"},
                      headers=H, content_type="multipart/form-data").json["anhang"]
        schreiber = PdfWriter()
        schreiber.add_blank_page(595, 842)
        schreiber.add_blank_page(842, 595)
        buf = io.BytesIO()
        schreiber.write(buf)
        buf.seek(0)
        ah2 = p1.post(url, data={"file": [(buf, "bericht.pdf")], "art": "pruefbericht", "titel": "Bericht Dienstleister",
                                 "im_protokoll": "nein"}, headers=H, content_type="multipart/form-data").json["anhang"]
        r = festschreiben(p1, pid, ergebnis="einsatzbereit", bemerkung="Alles in Ordnung – äöü ß")
        assert r.status_code == 200, r.get_json()
        pr = r.json["pruefung"]
        jahr = _heute().year
        assert pr["protokoll"]["id"] == f"P-{jahr}-{pid:06d}", pr["protokoll"]
        assert pr["protokoll"]["url"] == f"/material/pruefung/{pid}/pdf" and pr["unterschrift"].startswith("data:image/png")
        zeile = protokoll_zeile(app, pid)
        assert zeile["locked_at"] and zeile["signature_png"] and zeile["locked_login"] == "pruefer@example.org"
        assert zeile["pdf_path"] == f"pdf/{jahr}/P-{jahr}-{pid:06d}.pdf"

        # Nach dem Festschreiben ist jede Änderung abgewiesen.
        rid = pr["punkte"][0]["id"]
        assert p1.put(f"/api/material/pruefungen/{pid}/punkte/{rid}", json={"wert": "nein"}).status_code == 409
        assert p1.put(f"/api/material/pruefungen/{pid}", json={"bemerkung": "später"}).status_code == 409
        assert p1.post(url, data={"file": [(jpeg(), "x.jpg")]}, headers=H,
                       content_type="multipart/form-data").status_code == 409
        assert p1.delete(f"{url}/{ah1['id']}", headers=H).status_code == 409
        assert p1.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 409
        assert w.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 409
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 409
        # … auch an der Schnittstelle vorbei, direkt in der Datenbank (Trigger).
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        for sql in (f"UPDATE mat_inspection SET result = 'instandsetzen' WHERE id = {pid}",
                    f"UPDATE mat_inspection SET pdf_sha256 = 'x' WHERE id = {pid}",
                    f"DELETE FROM mat_inspection WHERE id = {pid}",
                    f"UPDATE mat_inspection_result SET finding = 'mangel' WHERE inspection_id = {pid}",
                    f"DELETE FROM mat_inspection_attachment WHERE inspection_id = {pid}"):
            try:
                conn.execute(sql)
                raise AssertionError("festgeschriebene Prüfung geändert: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "unveränderlich" in str(exc), exc
        conn.close()

        # head -c N über die Datei ergibt den aufgedruckten Wert und den in der Datenbank.
        pfad = os.path.join(tmp, zeile["pdf_path"])
        with open(pfad, "rb") as fh:
            daten = fh.read()
        n = zeile["pdf_hashed_bytes"]
        kopf = subprocess.run(f"head -c {n} '{pfad}' | sha256sum", shell=True, capture_output=True,
                              text=True).stdout.split()[0]
        assert kopf == zeile["pdf_sha256"] == hashlib.sha256(daten[:n]).hexdigest() == pr["protokoll"]["sha256"]
        # file_sha256 passt zur abgelegten Datei; sie ist schreibgeschützt.
        assert hashlib.sha256(daten).hexdigest() == zeile["file_sha256"]
        assert not os.access(pfad, os.W_OK) or os.geteuid() == 0
        # Der Stempeltext steht auf jeder Seite – auch auf der hinten angefügten Anhangseite.
        seiten = pdf_seiten(pfad)
        stempel = f"SHA-256 (erste {n} Bytes): {zeile['pdf_sha256']}"
        assert len(seiten) >= 2 and all(stempel in _flach(s) for s in seiten), [s[-300:] for s in seiten]
        # Anhänge stehen mit Prüfsumme im Protokoll; nur der angefügte kommt als Seite dazu.
        text = _flach(" ".join(seiten))
        for ah in (ah1, ah2):
            assert ah["titel"] in text and ah["sha256"] in text.replace(" ", ""), ah
        assert "pruefer" in text and "1012-4711" in text and f"P-{jahr}-{pid:06d}" in text and a["inventory_no"] in text
        # Ausliefern: nur mit Leserecht, nur unverändert.
        r = k["fuehrung"].get(f"/material/pruefung/{pid}/pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data == daten
        assert f"P-{jahr}-{pid:06d}_{a['inventory_no']}.pdf" in r.headers["Content-Disposition"]
        assert "sandbox" not in r.headers["Content-Security-Policy"]
        assert k["nutzer"].get(f"/material/pruefung/{pid}/pdf").status_code == 403
        r = app.test_client().get(f"/material/pruefung/{pid}/pdf")
        assert r.status_code == 302 and "/login" in r.headers["Location"]
        assert k["fuehrung"].get(f"/material/pruefung/{pid + 99}/pdf").status_code == 404
        # Im Lebenslauf: Protokoll-ID und Link.
        lauf = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["pruefungen"]
        assert lauf[0]["protokoll"]["id"] == f"P-{jahr}-{pid:06d}", lauf
        # Eine nachträglich veränderte Datei liefert der Server nicht mehr aus.
        os.chmod(pfad, 0o644)
        with open(pfad, "r+b") as fh:
            fh.seek(n // 2)
            b = fh.read(1)
            fh.seek(n // 2)
            fh.write(bytes([b[0] ^ 1]))
        r = k["fuehrung"].get(f"/material/pruefung/{pid}/pdf")
        assert r.status_code == 409 and b"Pr\xc3\xbcfsumme" in r.data, r.status_code
    print("Festschreibtest bestanden.")


def test_berichtigung():
    """Eine Korrektur entsteht als neue Prüfung mit Verweis; das Original bleibt Byte für Byte, wie es war."""
    import hashlib
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        p2 = zweiter_pruefer(app, k["adm"])
        gid, system = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        p1.put(f"/api/material/pruefungen/{pr['id']}/punkte/{pk['Testpunkt Verschleiß']}", json={"wert": "ja",
                                                                                           "notiz": "Kerbe"})
        p1.post(f"/api/material/pruefungen/{pr['id']}/punkte/{pk['Testpunkt Verschleiß']}/foto",
                data={"file": (jpeg(), "kerbe.jpg")}, headers=H, content_type="multipart/form-data")
        assert festschreiben(p1, pr["id"], ergebnis="instandsetzen").status_code == 200
        alt = protokoll_zeile(app, pr["id"])
        with open(os.path.join(tmp, alt["pdf_path"]), "rb") as fh:
            alt_summe = hashlib.sha256(fh.read()).hexdigest()
        url = f"/api/material/pruefungen/{pr['id']}/berichtigen"
        # Nur wer geprüft hat, berichtigt – und nur mit Grund.
        assert p2.post(url, json={"grund": "x"}).status_code == 403
        assert w.post(url, json={"grund": "x"}).status_code == 403
        r = p1.post(url, json={})
        assert r.status_code == 400 and "Grund" in r.json["error"]
        r = p1.post(url, json={"grund": "Kerbe war Schmutz – Befund falsch"})
        assert r.status_code == 201, r.get_json()
        b = r.json["pruefung"]
        assert b["entwurf"] and b["berichtigt"]["id"] == pr["id"] and b["art"] == pr["art"], b
        assert b["datum"] == alt["inspected_on"] and b["grund_berichtigung"].startswith("Kerbe war")
        kopie = {x["text"]: x for x in b["punkte"]}
        assert kopie["Testpunkt Verschleiß"]["befund"] == "mangel" and kopie["Testpunkt Verschleiß"]["foto"]
        assert kopie["Testpunkt Verschleiß"]["foto"]["web"] != [x for x in pr["punkte"]][0].get("foto")
        # Das Original zeigt die laufende Berichtigung; ein zweiter Versuch scheitert.
        o = p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        assert o["berichtigt_durch"]["entwurf"] and not o["berichtigbar"]["ok"], o["berichtigbar"]
        assert p1.post(url, json={"grund": "nochmal"}).status_code == 409
        # Die Prüfart einer Berichtigung steht fest.
        assert p1.put(f"/api/material/pruefungen/{b['id']}", json={"art": "periodisch"}).status_code == 409
        # Verwerfen gibt das Original wieder frei – seine Fotos bleiben.
        assert p1.delete(f"/api/material/pruefungen/{b['id']}", headers=H).status_code == 200
        foto_alt = [x for x in p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["punkte"] if x["foto"]][0]
        assert p1.get(foto_alt["foto"]["web"]).status_code == 200
        b = p1.post(url, json={"grund": "Kerbe war Schmutz – Befund falsch"}).json["pruefung"]
        kb = punkte_von(b)
        assert p1.put(f"/api/material/pruefungen/{b['id']}/punkte/{kb['Testpunkt Verschleiß']}",
                      json={"wert": "nein"}).status_code == 200
        r = festschreiben(p1, b["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        b = r.json["pruefung"]
        jahr = _heute().year
        assert b["protokoll"]["id"] == f"P-{jahr}-{b['id']:06d}" and b["datum"] == alt["inspected_on"]
        # Die Berichtigung wirkt am Artikel: Freiprüfung aus „Gesperrt“ zurück.
        art = w.get(f"/api/material/artikel/{a['id']}").json["artikel"]
        assert art["status"] != "gesperrt" and art["folder_id"] == gid, art
        # Das Original: unverändert, mit Verweis auf die Berichtigung.
        neu = protokoll_zeile(app, pr["id"])
        assert {kk: neu[kk] for kk in ("result", "pdf_sha256", "file_sha256", "locked_at")} == \
            {kk: alt[kk] for kk in ("result", "pdf_sha256", "file_sha256", "locked_at")}
        with open(os.path.join(tmp, neu["pdf_path"]), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == alt_summe
        o = p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        assert o["berichtigt_durch"]["protokoll_id"] == b["protokoll"]["id"] and not o["berichtigt_durch"]["entwurf"]
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, b["id"])["pdf_path"]))))
        assert "Berichtigung" in text and alt["protocol_id"] in text and "Kerbe war Schmutz" in text, text[:600]
        # Berichtigen lässt sich nur die letzte Prüfung des Artikels.
        assert p1.post(f"/api/material/pruefungen/{b['id']}/berichtigen", json={"grund": "x"}).status_code == 201
        assert p1.delete(f"/api/material/pruefungen/{b['id'] + 1}", headers=H).status_code == 200
        p3 = starten(p1, a["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, p3, ergebnis="einsatzbereit").status_code == 200
        r = p1.post(f"/api/material/pruefungen/{b['id']}/berichtigen", json={"grund": "x"})
        assert r.status_code == 409 and "letzte Prüfung" in r.json["error"], r.get_json()
        with app.app_context():
            from app import db
            aktionen = [x["action"] for x in db.query("SELECT action FROM mat_audit WHERE entity = 'inspection' "
                                                      "AND entity_id = ? ORDER BY id", (pr["id"],))]
        assert aktionen[-1] == "berichtigt" and "festgeschrieben" in aktionen, aktionen
    print("Berichtigungstest bestanden.")


def test_pruefseite():
    """/material/pruefen meldet das Original als unverändert und eine um ein Byte geänderte Kopie als verändert –
    ohne Anmeldung und ohne Personendaten."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, a["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        zeile = protokoll_zeile(app, pid)
        with open(os.path.join(tmp, zeile["pdf_path"]), "rb") as fh:
            original = fh.read()
        n = zeile["pdf_hashed_bytes"]
        anon = app.test_client()
        assert anon.get("/material/pruefen").status_code == 200

        def pruefen(daten, c=anon):
            r = c.post("/api/material/pruefen", data={"datei": (io.BytesIO(daten), "protokoll.pdf")}, headers=H,
                       content_type="multipart/form-data")
            assert r.status_code == 200, r.get_json()
            return r.json

        e = pruefen(original)
        assert e["ergebnis"] == "unveraendert" and e["protokoll_id"] == zeile["protocol_id"], e
        # Keine Personendaten: nur Ergebnis, Protokoll-ID, Art und ein Hinweis.
        assert set(e) <= {"ergebnis", "protokoll_id", "art", "hinweis"}, e
        assert "pruefer" not in json.dumps(e) and "1012" not in json.dumps(e)
        # Ein Byte im Protokoll geändert → verändert.
        kopie = bytearray(original)
        kopie[n // 2] ^= 1
        e = pruefen(bytes(kopie))
        assert e["ergebnis"] == "veraendert" and e["protokoll_id"] == zeile["protocol_id"], e
        # Ein Byte hinter den ersten N geändert: Inhalt intakt, Datei trotzdem nicht die ausgegebene.
        kopie = bytearray(original)
        kopie[-5] ^= 1
        e = pruefen(bytes(kopie))
        assert e["ergebnis"] == "veraendert" and f"ersten {n} Bytes" in e["hinweis"], e
        # Ohne Stempel (nur die ersten N Bytes) ebenso.
        e = pruefen(original[:n])
        assert e["ergebnis"] == "veraendert" and "Stempel" in e["hinweis"], e
        # Ein fremdes PDF ist kein Protokoll von strömis.de.
        assert pruefen(PDF)["ergebnis"] == "unbekannt"
        # Angemeldet mit Zugang zum Modul: dazu der Weg zum Vorgang.
        assert pruefen(original, k["fuehrung"])["link"] == f"/material/pruefung/{pid}"
        assert "link" not in pruefen(original, k["nutzer"])
        r = anon.post("/api/material/pruefen", data={}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 400
        # Gebremst: zu viele Prüfungen in einer Viertelstunde von einer Adresse.
        codes = [anon.post("/api/material/pruefen", data={"datei": (io.BytesIO(PDF), "x.pdf")}, headers=H,
                           content_type="multipart/form-data").status_code for _ in range(25)]
        assert 429 in codes, codes
    print("Prüfseitentest bestanden.")


def test_aussonderungsprotokoll():
    """Jede Aussonderung hat ihr eigenes festgeschriebenes Protokoll – aus der Prüfung und durch den Materialwart."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, system = gliederung(w)
        h = _heute()
        alt = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{h.year - 11}-01")
        pr = starten(p1, alt["id"]).json["pruefung"]
        p1.put(f"/api/material/pruefungen/{pr['id']}/punkte/{punkte_von(pr)['Testpunkt Messwert']}", json={"wert": "1"})
        r = festschreiben(p1, pr["id"], ergebnis="aussondern", grund="Lebensdauer überschritten")
        assert r.status_code == 200, r.get_json()
        lauf = w.get(f"/api/material/artikel/{alt['id']}").json["artikel"]["pruefungen"]
        aus, pruef = lauf[0], lauf[1]
        jahr = h.year
        assert aus["art"] == "aussonderung" and aus["protokoll"]["id"] == f"A-{jahr}-{aus['id']:06d}", aus
        assert pruef["protokoll"]["id"] == f"P-{jahr}-{pr['id']:06d}"
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, aus["id"])["pdf_path"]))))
        assert "Aussonderungsprotokoll" in text and pruef["protokoll"]["id"] in text and "Lebensdauer überschritten" in text
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pr["id"])["pdf_path"]))))
        assert aus["protokoll"]["id"] in text, text[:800]
        # Eine Aussonderung lässt sich nicht berichtigen.
        assert p1.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "x"}).status_code == 409
        # Durch den Materialwart: nur mit hinterlegter Unterschrift.
        b = neuer_artikel(w, ids["hms"], gid)
        assert p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "verlust"}).status_code == 200
        assert w.delete("/api/material/unterschrift", headers=H).status_code == 200
        r = w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "verlust", "bemerkung": "Seit Übung weg"})
        assert r.status_code == 403 and "Unterschrift" in r.json["error"], r.get_json()
        unterschreiben(w)
        r = w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "verlust", "bemerkung": "Seit Übung weg"})
        assert r.status_code == 200, r.get_json()
        aid = r.json["aussonderung"]
        zeile = protokoll_zeile(app, aid)
        assert zeile["protocol_id"] == f"A-{jahr}-{aid:06d}" and zeile["locked_login"] == "wart@example.org"
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"]))))
        assert "Verlust" in text and "Seit Übung weg" in text and "Materialwart" in text and b["inventory_no"] in text
        assert "verloren" in text, text[:900]
        r = k["fuehrung"].get(f"/material/pruefung/{aid}/pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
    print("Aussonderungsprotokolltest bestanden.")


def test_sammelprotokoll():
    """Abschluss eines Durchgangs: Sammelprotokoll mit allen Artikeln, Ausnahmen, Prüfern samt Urkundennummer
    und den Einzelprotokollen; danach ist der Durchgang unveränderlich. Auch ein Abbruch bekommt eins."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        p2 = zweiter_pruefer(app, k["adm"])
        gid, _ = gliederung(w)
        artikel = [neuer_artikel(w, ids["hms"], gid) for _ in range(3)]
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Jahresprüfung Test"}).json["durchgang"]["id"]
        einzel = []
        for c, x in ((p1, artikel[0]), (p2, artikel[1])):
            pid = starten(c, x["id"], durchgang_id=rid).json["pruefung"]["id"]
            assert festschreiben(c, pid, ergebnis="einsatzbereit").status_code == 200
            einzel.append(protokoll_zeile(app, pid))
        assert w.post(f"/api/material/durchgaenge/{rid}/ausnehmen",
                      json={"item_id": artikel[2]["id"], "grund": "nicht auffindbar"}).status_code == 200
        r = w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={})
        assert r.status_code == 200, r.get_json()
        d = r.json["durchgang"]
        jahr = _heute().year
        assert d["protokoll"]["id"] == f"S-{jahr}-{rid:06d}" and d["protokoll"]["url"] == f"/material/durchgang/{rid}/sammelprotokoll"
        zeile = protokoll_zeile(app, rid=rid)
        pfad = os.path.join(tmp, zeile["pdf_path"])
        seiten = pdf_seiten(pfad)
        stempel = f"SHA-256 (erste {zeile['pdf_hashed_bytes']} Bytes): {zeile['pdf_sha256']}"
        assert all(stempel in _flach(s) for s in seiten)
        text = _flach(" ".join(seiten))
        for x in artikel:
            assert x["inventory_no"] in text, x["inventory_no"]
        for e in einzel:
            assert e["protocol_id"] in text and e["file_sha256"] in text.replace(" ", ""), e["protocol_id"]
        assert "pruefer" in text and "1012-4711" in text and "Prüferin Zwei" in text and "1012-4712" in text
        assert "nicht auffindbar" in text and "Jahresprüfung Test" in text
        r = k["fuehrung"].get(f"/material/durchgang/{rid}/sammelprotokoll")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        # Abgeschlossen heißt unveränderlich – auch in der Datenbank.
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        for sql in (f"UPDATE mat_round SET title = 'x' WHERE id = {rid}", f"DELETE FROM mat_round WHERE id = {rid}",
                    f"DELETE FROM mat_round_item WHERE round_id = {rid}",
                    f"UPDATE mat_round_item SET excluded_reason = 'y' WHERE round_id = {rid}"):
            try:
                conn.execute(sql)
                raise AssertionError("abgeschlossenen Durchgang geändert: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "unveränderlich" in str(exc), exc
        conn.close()
        # Ein abgebrochener Durchgang: Sammelprotokoll mit „nicht geprüft“.
        rid2 = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Abbruch Test"}).json["durchgang"]["id"]
        pid = starten(p1, artikel[0]["id"], durchgang_id=rid2).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        r = w.post(f"/api/material/durchgaenge/{rid2}/abbrechen", json={})
        assert r.status_code == 200 and r.json["durchgang"]["protokoll"]["id"] == f"S-{jahr}-{rid2:06d}", r.get_json()
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, rid=rid2)["pdf_path"]))))
        assert "abgebrochen" in text and "nicht geprüft" in text, text[:800]
    print("Sammelprotokolltest bestanden.")


def test_unterschrift():
    """Unterschrift im Profil: nur PNG vom Signatur-Pad, nicht leer; normalisiert gespeichert; im Journal."""
    import base64
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        p1 = k["pruefer"]
        r = p1.get("/api/material/unterschrift")
        assert r.status_code == 200 and r.json["unterschrift"].startswith("data:image/png;base64,")
        gespeichert = Image.open(io.BytesIO(base64.b64decode(r.json["unterschrift"].split(",", 1)[1])))
        assert gespeichert.mode == "RGBA" and gespeichert.width < 420           # leerer Rand abgeschnitten

        def setzen(bild):
            return p1.put("/api/material/unterschrift", json={"bild": bild})
        assert setzen("kein Bild").status_code == 400
        buf = io.BytesIO()
        Image.new("RGB", (50, 50), (0, 0, 0)).save(buf, "JPEG")
        assert setzen("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()).status_code == 400
        assert setzen("data:image/png;base64,@@@").status_code == 400
        buf = io.BytesIO()
        Image.new("RGBA", (400, 150), (0, 0, 0, 0)).save(buf, "PNG")
        r = setzen("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
        assert r.status_code == 400 and "leer" in r.json["error"], r.get_json()
        # Auch ein Bild mit weißem Hintergrund (ohne Alpha) taugt: Tinte ist, was dunkel ist.
        buf = io.BytesIO()
        weiss = Image.new("RGB", (400, 150), (255, 255, 255))
        from PIL import ImageDraw
        ImageDraw.Draw(weiss).line([(20, 100), (200, 30), (380, 110)], fill=(0, 0, 0), width=5)
        weiss.save(buf, "PNG")
        r = setzen("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
        assert r.status_code == 200, r.get_json()
        assert k["nutzer"].put("/api/material/unterschrift", json={"bild": unterschrift_daten()}).status_code == 403
        assert app.test_client().get("/api/material/unterschrift").status_code == 401
        with app.app_context():
            from app import db
            eintraege = db.query("SELECT * FROM mat_audit WHERE entity = 'user' AND action = 'unterschrift'")
        assert len(eintraege) >= 3 and all("signature" not in (e["after_json"] or "") for e in eintraege)
        assert p1.delete("/api/material/unterschrift", headers=H).json["unterschrift"] is None
        assert p1.get("/api/material/start").json["darf"]["unterschrift"] is False
    print("Unterschrifttest bestanden.")


def test_unterschriftsfeld():
    """Unterschriftsfelder eines Formulars: auf dem Signatur-Pad zu füllen, Pflicht wie andere Punkte."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        r = kp.post("/api/material/formulare", json={"produkt_id": ids["hms"], "titel": "HMS mit Unterschrift", "punkte": [
            {"text": "Testpunkt Sicht", "art": "yesno", "soll": "ja"},
            {"text": "Unterschrift Gerätewart", "art": "signature"}]})
        assert r.status_code == 201, r.get_json()
        assert kp.post(f"/api/material/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        pr = starten(p1, a["id"]).json["pruefung"]
        sig = punkte_von(pr)["Unterschrift Gerätewart"]
        r = festschreiben(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Unterschrift Gerätewart" in r.json["error"], r.get_json()
        url = f"/api/material/pruefungen/{pr['id']}/punkte/{sig}"
        assert p1.put(url, json={"wert": "x"}).status_code == 400
        assert p1.post(url + "/foto", data={"file": (jpeg(), "x.jpg")}, headers=H,
                       content_type="multipart/form-data").status_code == 400
        assert p1.put(url, json={"unterschrift": "data:image/png;base64,AAAA"}).status_code == 400
        r = p1.put(url, json={"unterschrift": unterschrift_daten("G")})
        assert r.status_code == 200 and r.json["punkt"]["unterschrift"].startswith("data:image/png"), r.get_json()
        r = p1.put(url, json={"befund": "nicht_zutreffend"})
        assert r.json["punkt"]["befund"] == "nicht_zutreffend" and r.json["punkt"]["unterschrift"] is None
        assert p1.put(url, json={"unterschrift": unterschrift_daten("G")}).json["punkt"]["befund"] == "ok"
        r = festschreiben(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            from app import db
            zeile = db.query("SELECT signature_png FROM mat_inspection_result WHERE id = ?", (sig,), one=True)
        assert zeile["signature_png"].startswith(b"\x89PNG")
        assert p1.put(url, json={"unterschrift": None}).status_code == 409
    print("Unterschriftsfeldtest bestanden.")


def test_lieferung2_bestand():
    """Prüfungen, die vor Lieferung 3 abgeschlossen wurden, haben kein Protokoll und bleiben trotzdem
    unveränderlich; berichtigen lassen sie sich wie jede abgeschlossene Prüfung."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        with app.app_context():
            from app import db
            ts = db.now()
            pid = db.execute("INSERT INTO mat_inspection (item_id, inspector_user_id, inspector_name, inspector_certificate, "
                             "inspected_on, kind, result, next_due_on, completed_at, created_at, updated_at) "
                             "VALUES (?, ?, 'pruefer', '1012-4711', ?, 'eingang', 'einsatzbereit', ?, ?, ?, ?)",
                             (a["id"], k["pruefer_id"], _heute().isoformat(),
                              (_heute() + timedelta(days=300)).isoformat(), ts, ts, ts))
        pr = p1.get(f"/api/material/pruefungen/{pid}").json["pruefung"]
        assert pr["protokoll"] is None and pr["berichtigbar"]["ok"], pr
        assert k["fuehrung"].get(f"/material/pruefung/{pid}/pdf").status_code == 404
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute(f"UPDATE mat_inspection SET result = 'instandsetzen' WHERE id = {pid}")
            raise AssertionError("abgeschlossene Prüfung geändert")
        except sqlite3.IntegrityError:
            pass
        conn.close()
        r = p1.post(f"/api/material/pruefungen/{pid}/berichtigen", json={"grund": "Protokoll fehlte"})
        assert r.status_code == 201, r.get_json()
        b = r.json["pruefung"]
        r = festschreiben(p1, b["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200 and r.json["pruefung"]["protokoll"], r.get_json()
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, b["id"])["pdf_path"]))))
        assert "ohne Protokoll" in text, text[:600]
    print("Bestandstest Lieferung 2 bestanden.")


def pdf_mit_skript():
    """Ein PDF mit Seitenaktion (JavaScript), einem Launch-Verweis, einem JavaScript-Verweis, einem normalen Verweis
    und einem ausgefüllten Formularfeld mit Tastenaktion – so etwas soll nie ins Protokoll gelangen."""
    from pypdf import PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject,
                               TextStringObject)
    w = PdfWriter()
    seite = w.add_blank_page(595, 842)

    def objekt(d):
        return w._add_object(DictionaryObject(d))

    def js():
        return objekt({NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("app.alert(1)")})

    def verweis(aktion, x):
        return objekt({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Link"),
                       NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (x, 10, x + 30, 30)]),
                       NameObject("/A"): aktion, NameObject("/F"): NumberObject(4)})
    seite[NameObject("/AA")] = DictionaryObject({NameObject("/O"): js()})
    uri = objekt({NameObject("/S"): NameObject("/URI"), NameObject("/URI"): TextStringObject("https://example.org/")})
    launch = objekt({NameObject("/S"): NameObject("/Launch"), NameObject("/F"): TextStringObject("calc.exe")})
    bild = DecodedStreamObject()
    bild.set_data(b"0 0 1 rg 0 0 50 20 re f")
    bild.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                 NameObject("/BBox"): ArrayObject([FloatObject(v) for v in (0, 0, 50, 20)])})
    feld = objekt({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                   NameObject("/FT"): NameObject("/Tx"), NameObject("/T"): TextStringObject("feld"),
                   NameObject("/V"): TextStringObject("ausgefuellt"), NameObject("/F"): NumberObject(4),
                   NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (100, 100, 150, 120)]),
                   NameObject("/AP"): DictionaryObject({NameObject("/N"): w._add_object(bild)}),
                   NameObject("/AA"): DictionaryObject({NameObject("/K"): js()})})
    seite[NameObject("/Annots")] = ArrayObject([verweis(uri, 10), verweis(launch, 60), verweis(js(), 110), feld])
    w._root_object[NameObject("/AcroForm")] = DictionaryObject({NameObject("/Fields"): ArrayObject([feld])})
    w._root_object[NameObject("/OpenAction")] = js()
    puffer = io.BytesIO()
    w.write(puffer)
    puffer.seek(0)
    return puffer


def test_review_lieferung3():
    """Befunde aus der Durchsicht von Lieferung 3, je als Regressionstest."""
    import base64
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        db_pfad = os.path.join(tmp, "stroemis.db")

        # 1. Eine Berichtigung hebt keine spätere Sperre auf (sonst gäbe ein Protokoll mit dem alten Prüftag den
        #    Artikel nach einem Sturz wieder frei).
        a = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, a["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        assert p1.post(f"/api/material/artikel/{a['id']}/sperren", json={"grund": "sturz"}).status_code == 200
        r = p1.post(f"/api/material/pruefungen/{pid}/berichtigen", json={"grund": "x"})
        assert r.status_code == 409 and "gesperrt" in r.json["error"], r.get_json()

        # 2. Ein neuer Durchgang übernimmt keinen offenen Berichtigungsentwurf.
        b = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, b["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        ber = p1.post(f"/api/material/pruefungen/{pid}/berichtigen", json={"grund": "Tippfehler"}).json["pruefung"]
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Jahresprüfung"}).json["durchgang"]["id"]
        assert p1.get(f"/api/material/pruefungen/{ber['id']}").json["pruefung"]["round_id"] is None
        assert festschreiben(p1, ber["id"], ergebnis="einsatzbereit").status_code == 200
        zeile = [x for x in w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]["artikel"] if x["id"] == b["id"]][0]
        assert zeile["zustand"] == "offen", zeile
        assert w.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={}).json["durchgang"] is None

        # 3. Eine im Durchgang berichtigte Prüfung zählt bei den Prüfern nur einmal.
        c = neuer_artikel(w, ids["hms"], gid)
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Zählung"}).json["durchgang"]["id"]
        pid = starten(p1, c["id"], durchgang_id=rid).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        ber = p1.post(f"/api/material/pruefungen/{pid}/berichtigen", json={"grund": "Tippfehler"}).json["pruefung"]
        assert ber["round_id"] == rid
        assert festschreiben(p1, ber["id"], ergebnis="einsatzbereit").status_code == 200
        d = w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        assert [x["anzahl"] for x in d["pruefer"]] == [1], d["pruefer"]

        # 4. Die Trigger halten auch INSERT OR REPLACE, Umhängen und Nachschieben stand.
        fest = protokoll_zeile(app, pid)
        conn = sqlite3.connect(db_pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        entwurf = starten(p1, c["id"]).json["pruefung"]["id"]
        befund_entwurf = conn.execute("SELECT id FROM mat_inspection_result WHERE inspection_id = ?", (entwurf,)).fetchone()[0]
        befund_fest = conn.execute("SELECT id FROM mat_inspection_result WHERE inspection_id = ?", (pid,)).fetchone()[0]
        for sql, args in [
            ("INSERT OR REPLACE INTO mat_inspection (id, item_id, inspected_on, kind, result, created_at, updated_at) "
             "VALUES (?, ?, '2026-01-01', 'periodisch', 'instandsetzen', 'x', 'x')", (pid, c["id"])),
            ("UPDATE mat_inspection_result SET inspection_id = ? WHERE id = ?", (pid, befund_entwurf)),
            ("INSERT OR REPLACE INTO mat_inspection_result (id, inspection_id, checklist_text, editor) VALUES (?, ?, 'x', 'yesno')",
             (befund_fest, entwurf)),
            ("UPDATE mat_inspection SET round_id = ? WHERE id = ?", (rid, entwurf)),
            # REPLACE über eine eindeutige Spalte löschte sonst die andere Prüfung ohne Lösch-Trigger.
            ("UPDATE OR REPLACE mat_inspection SET protocol_id = ? WHERE id = ?", (fest["protocol_id"], entwurf)),
            ("INSERT OR REPLACE INTO mat_inspection (item_id, protocol_id, inspected_on, kind, created_at, updated_at) "
             "VALUES (?, ?, '2026-01-01', 'periodisch', 'x', 'x')", (a["id"], fest["protocol_id"])),
            ("INSERT INTO mat_inspection (item_id, round_id, inspected_on, kind, created_at, updated_at) "
             "VALUES (?, ?, '2026-01-01', 'periodisch', 'x', 'x')", (a["id"], rid)),
        ]:
            if "round_id = ?" in sql or "round_id, inspected_on" in sql:
                conn.execute("UPDATE mat_round SET closed_on = '2026-10-17' WHERE id = ? AND closed_on IS NULL", (rid,))
            try:
                conn.execute(sql, args)
                raise AssertionError("an den Triggern vorbei: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "unveränderlich" in str(exc), exc
        # Die Kontokennung des Prüfers geht beim Löschen eines Kontos auf NULL – auf ein anderes Konto nie.
        anderer = conn.execute("SELECT id FROM users WHERE email = 'wart@example.org'").fetchone()[0]
        try:
            conn.execute("UPDATE mat_inspection SET inspector_user_id = ? WHERE id = ?", (anderer, pid))
            raise AssertionError("Prüfer einer festgeschriebenen Prüfung umgeschrieben")
        except sqlite3.IntegrityError:
            pass
        conn.execute("UPDATE mat_inspection SET inspector_user_id = NULL WHERE id = ?", (pid,))
        # Ein abgeschlossener Durchgang (hier ohne Sammelprotokoll, wie aus Lieferung 2) lässt sich nicht wieder öffnen.
        try:
            conn.execute("UPDATE mat_round SET closed_on = NULL WHERE id = ?", (rid,))
            raise AssertionError("abgeschlossenen Durchgang wieder geöffnet")
        except sqlite3.IntegrityError:
            pass
        conn.rollback()
        conn.close()
        assert protokoll_zeile(app, pid)["result"] == fest["result"]

        # 5. Die Prüfseite nennt keine Protokoll-ID zu einer erfundenen Kennung.
        falsch = (b"%PDF-1.4\n%Stroemis-Protokoll " + fest["protocol_id"].encode() + b" N=1 SHA-256=" + b"0" * 64 + b"\n")
        r = app.test_client().post("/api/material/pruefen", data={"datei": (io.BytesIO(falsch), "x.pdf")}, headers=H,
                                   content_type="multipart/form-data")
        assert r.json["ergebnis"] == "unbekannt" and r.json["protokoll_id"] is None, r.get_json()

        # 6. Skripte und ausführende Aktionen eines Anhangs kommen nicht ins Protokoll; Verweise und Felder bleiben.
        assert p1.delete(f"/api/material/pruefungen/{entwurf}", headers=H).status_code == 200
        e = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, e["id"]).json["pruefung"]["id"]
        r = p1.post(f"/api/material/pruefungen/{pid}/anhaenge", data={"file": [(pdf_mit_skript(), "karte.pdf")],
                                                                       "im_protokoll": "ja"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        with open(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]), "rb") as fh:
            daten = fh.read()
        assert b"/JavaScript" not in daten and b"/Launch" not in daten and b"/OpenAction" not in daten
        assert b"/URI" in daten and b"/AP" in daten

        # 7. Riesige Unterschriften werden abgewiesen (Speicher), bevor sie dekodiert werden.
        buf = io.BytesIO()
        Image.new("RGBA", (2500, 2000), (0, 0, 0, 0)).save(buf, "PNG")
        r = p1.put("/api/material/unterschrift", json={"bild": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()})
        assert r.status_code == 400, r.get_json()

        # 8. Zeichen, die der fette Schnitt von DLRG Univers nicht hat, kommen richtig ins Protokoll (und als PDF/A).
        r = k["katalog"].post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Łukasz",
                                                               "model": "Ŝpezial −5 μm", "material_kind": "metall_hardware",
                                                               "interval_months": 12})
        assert r.status_code == 201, r.get_json()
        f = neuer_artikel(w, r.json["produkt"]["id"], gid)
        pid = starten(p1, f["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]))))
        assert "Łukasz" in text and "−5 μm" in text, text[:400]

        # 10. Ein geändertes Byte in der Kennung des Stempels: weiter „verändert“ mit Protokoll-ID (über die %%EOF-Grenzen).
        zeile = protokoll_zeile(app, pid)
        with open(os.path.join(tmp, zeile["pdf_path"]), "rb") as fh:
            kopie = bytearray(fh.read())
        stelle = kopie.index(b"%Stroemis-Protokoll") + 25
        kopie[stelle] ^= 1
        r = app.test_client().post("/api/material/pruefen", data={"datei": (io.BytesIO(bytes(kopie)), "x.pdf")}, headers=H,
                                   content_type="multipart/form-data")
        assert r.json["ergebnis"] == "veraendert" and r.json["protokoll_id"] == zeile["protocol_id"], r.get_json()

        # 11. Angefügte Seiten bekommen unten einen eigenen Streifen für den Stempel – er verdeckt nichts vom Anhang.
        from pypdf import PdfReader
        zeile = protokoll_zeile(app, protokoll_zeile(app, pid)["id"] - 1)      # die Prüfung mit dem Skript-Anhang (6.)
        angefuegt = PdfReader(os.path.join(tmp, zeile["pdf_path"])).pages[-1]
        assert float(angefuegt.mediabox.bottom) < -39 and float(angefuegt.mediabox.top) == 842, angefuegt.mediabox

        # 12. Ohne Fälligkeit (instandsetzen) sagt das Protokoll, warum – die EN-365-Karte nennt sie immer.
        g2 = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, g2["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="instandsetzen", grund="Feder lahm").status_code == 200
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]))))
        assert "Nächste Prüfung" in text and "Freiprüfung nötig" in text, text[:900]

        # 13. Ein schon gestempeltes Protokoll als Anhang behält auf seinen Seiten den eigenen Stempel.
        alt = protokoll_zeile(app, pid)
        with open(os.path.join(tmp, alt["pdf_path"]), "rb") as fh:
            alt_daten = fh.read()
        h2 = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, h2["id"]).json["pruefung"]["id"]
        r = p1.post(f"/api/material/pruefungen/{pid}/anhaenge", data={"file": [(io.BytesIO(alt_daten), "alt.pdf")],
                                                                       "im_protokoll": "ja"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        neu = protokoll_zeile(app, pid)
        seiten = pdf_seiten(os.path.join(tmp, neu["pdf_path"]))
        alter_stempel = f"SHA-256 (erste {alt['pdf_hashed_bytes']} Bytes): {alt['pdf_sha256']}"
        neuer_stempel = f"SHA-256 (erste {neu['pdf_hashed_bytes']} Bytes): {neu['pdf_sha256']}"
        assert alter_stempel in _flach(seiten[-1]) and neuer_stempel in _flach(seiten[-1]), seiten[-1][-500:]

        # 14. Mit AES verschlüsselte Anhänge (leeres Benutzerkennwort, wie bei Herstellern üblich) lassen sich anhängen.
        from pypdf import PdfWriter
        geschuetzt = PdfWriter()
        geschuetzt.add_blank_page(595, 842)
        geschuetzt.encrypt(user_password="", owner_password="hersteller", algorithm="AES-128")
        buf = io.BytesIO()
        geschuetzt.write(buf)
        buf.seek(0)
        i2 = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, i2["id"]).json["pruefung"]["id"]
        r = p1.post(f"/api/material/pruefungen/{pid}/anhaenge", data={"file": [(buf, "geschuetzt.pdf")], "im_protokoll": "ja"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        seiten = pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]))
        assert "SHA-256 (erste" in _flach(seiten[-1]) and len(seiten) >= 2

        # 15. Liegt unter einer ID schon ein Protokoll (nach dem Zurückspielen einer Sicherung wieder offener Entwurf,
        #     sein ausgehändigtes Protokoll in pdf/verwaist/), bekommt das neue eine Folgenummer – nie dieselbe ID.
        j2 = neuer_artikel(w, ids["hms"], gid)
        pid = starten(p1, j2["id"]).json["pruefung"]["id"]
        jahr = _heute().year
        os.makedirs(os.path.join(tmp, "pdf", "verwaist"), exist_ok=True)
        with open(os.path.join(tmp, "pdf", "verwaist", f"P-{jahr}-{pid:06d}-20260101000000.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.7\n")
        r = festschreiben(p1, pid, ergebnis="einsatzbereit")
        assert r.status_code == 200 and r.json["pruefung"]["protokoll"]["id"] == f"P-{jahr}-{pid:06d}-2", r.get_json()
        with open(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]), "rb") as fh:
            e = app.test_client().post("/api/material/pruefen", data={"datei": (io.BytesIO(fh.read()), "x.pdf")}, headers=H,
                                       content_type="multipart/form-data").json
        assert e["ergebnis"] == "unveraendert" and e["protokoll_id"] == f"P-{jahr}-{pid:06d}-2", e

        # 9. Eine Protokolldatei ohne Datenbankzeile (Absturz vor dem Commit) wird beim Start beiseitegelegt.
        waise = os.path.join(tmp, "pdf", str(_heute().year), f"A-{_heute().year}-999999.pdf")
        with open(waise, "wb") as fh:
            fh.write(b"%PDF-1.7\n")
        make_app(tmp)
        assert not os.path.exists(waise) and os.listdir(os.path.join(tmp, "pdf", "verwaist")), os.listdir(os.path.join(tmp, "pdf"))
        # … und ihre Nummer wird nicht noch einmal vergeben (etwa nach dem Zurückspielen einer älteren Sicherung).
        conn = sqlite3.connect(db_pfad)
        assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'mat_inspection'").fetchone()[0] >= 999999
        conn.close()
        assert os.path.exists(os.path.join(tmp, protokoll_zeile(app, pid)["pdf_path"]))
    print("Review-Befunde Lieferung 3 nachgestellt und behoben.")


def test_durchsichtige_bilder():
    """Produktbilder mit durchsichtigem Hintergrund (freigestellte PNGs) stehen auf Weiß, nicht auf Schwarz – neu
    hochgeladene sofort, schon vorhandene nach der einmaligen Reparatur beim Start."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        frei = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
        from PIL import ImageDraw
        ImageDraw.Draw(frei).ellipse([150, 80, 450, 320], fill=(220, 120, 20, 255))
        for modus in ("RGBA", "P", "LA"):
            buf = io.BytesIO()
            (frei if modus == "RGBA" else frei.convert(modus)).save(buf, "PNG", **({"transparency": 0} if modus == "P" else {}))
            buf.seek(0)
            r = k["katalog"].post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (buf, "frei.png")}, headers=H,
                                  content_type="multipart/form-data")
            assert r.status_code == 200, r.get_json()
            p = r.json["produkt"]
            for url in (p["bild"], p["vorschau"]):
                bild = Image.open(io.BytesIO(k["katalog"].get(url).data)).convert("RGB")
                assert min(bild.getpixel((1, 1))) > 240, (modus, url, bild.getpixel((1, 1)))
        # Ein Bild aus der Zeit davor (Vorschau schwarz) wird beim nächsten Start aus dem Original neu erzeugt.
        medien = os.path.join(tmp, "media", "material")
        key = os.path.splitext(p["original"].rsplit("/", 1)[1])[0]
        for art in ("web", "thumb"):
            Image.new("RGB", (60, 40), (0, 0, 0)).save(os.path.join(medien, art, key + ".jpg"), "JPEG")
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("DELETE FROM mat_meta WHERE schluessel = 'bilder_weiss'")
        conn.commit()
        conn.close()
        make_app(tmp)
        for art in ("web", "thumb"):
            bild = Image.open(os.path.join(medien, art, key + ".jpg")).convert("RGB")
            assert bild.size != (60, 40) and min(bild.getpixel((1, 1))) > 240, (art, bild.size, bild.getpixel((1, 1)))
    print("Bildtest (durchsichtiger Hintergrund) bestanden.")


if __name__ == "__main__":
    test_migration()
    test_rollen()
    test_katalog()
    test_ordner()
    test_artikel()
    test_suche()
    test_journal()
    test_formulare_und_dokumente()
    test_status_einheitlich()
    test_import()
    test_review_befunde()
    test_pruefung()
    test_sperre_und_aussonderung()
    test_anhang_scan()
    test_durchgang()
    test_review_lieferung2()
    test_review_lieferung2_robust()
    test_listen_und_formular()
    test_migration_lieferung2()
    test_produktmeldung()
    test_produktmeldung_loeschen()
    test_durchgang_abbrechen()
    test_artikelnummer_eindeutig()
    test_produkt_variante()
    test_monatsangaben()
    test_festschreiben()
    test_berichtigung()
    test_pruefseite()
    test_aussonderungsprotokoll()
    test_sammelprotokoll()
    test_unterschrift()
    test_unterschriftsfeld()
    test_lieferung2_bestand()
    test_review_lieferung3()
    test_durchsichtige_bilder()
