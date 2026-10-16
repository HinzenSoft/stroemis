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


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (200, 30, 30)).save(buf, "JPEG")
    buf.seek(0)
    return buf


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
                    "mat_round", "mat_round_item", "mat_folder_grant", "mat_reminder_log", "mat_audit"}
        assert erwartet <= tabellen, erwartet - tabellen
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
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "1"
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
            return r.json["darf"] if r.status_code == 200 else r.status_code
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
        heute = date.today()
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
        # Ein gesperrter Artikel bleibt, wo er ist (die Sperre selbst kommt mit Lieferung 2).
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
    print("Formular- und Dokumenttest bestanden.")


# --- 9. Status: Python und SQL sagen dasselbe ---------------------------------------------------------------

def test_status_einheitlich():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from app import db
            from app.material.services import status as st
            h = date(2026, 10, 16)
            faelle = [("frei", "2026-10-15", None, "ueberfaellig"), ("frei", "2026-10-16", None, "bald_faellig"),
                      ("frei", "2026-11-15", None, "bald_faellig"), ("frei", "2026-11-16", None, "einsatzbereit"),
                      ("frei", None, None, "ueberfaellig"), ("frei", "2027-01-01", "2026-10-16", "lebensdauer"),
                      ("frei", "2026-01-01", "2026-10-15", "lebensdauer"), ("frei", "2027-01-01", "2026-10-17", "einsatzbereit"),
                      ("gesperrt", "2027-01-01", None, "gesperrt"), ("verloren", "2020-01-01", "2020-01-01", "gesperrt"),
                      ("ausgesondert", "2020-01-01", "2020-01-01", "ausgesondert")]
            sql = st.status_sql("x")
            for lock, due, retire, soll in faelle:
                item = {"lock_state": lock, "next_due_on": due, "retire_by": retire}
                assert st.status(item, h, 30) == soll, (item, st.status(item, h, 30))
                r = db.query(f"SELECT {sql} AS s FROM (SELECT :l AS lock_state, :d AS next_due_on, :r AS retire_by) x",
                             dict(st.parameter(h, 30), l=lock, d=due, r=retire), one=True)
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
        heute = date.today()
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
