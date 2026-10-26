"""Artikellänge und Prüfpunkt „Länge“ (Schritt 20, Wunsch und Entscheidungen des Nutzers vom 22.10.2026):
  python tests/test_material_laenge.py  oder  pytest tests/test_material_laenge.py

Migration 19 → 20 (wiederholbar, Umbau von mat_checklist_item mit allen Zeilen), Häkchen „Artikel haben eine Länge“ an
der Kategorie mit Vererbung, Katalogdatei (Format 2) mit „artikel_laenge“, Artikel mit Länge (Anlegen, Bearbeiten,
Rundung, Grenzen, 409 ohne vorgesehene Länge, Journal), CSV-Spalte, Bestandsimport-Spalte, Formular mit Prüfpunkt
„Länge“, Prüfung vorbelegt, Festschreiben übernimmt einen abweichenden Wert in den Artikel (Journal, Protokoll),
Berichtigung, Lebenslauf und Meine PSA, Trennung. Alle Namen, Hersteller, Längen und Prüfpunkte sind Platzhalter."""
import csv
import io
import json
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, _flach, _heute, festschreiben, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, neues_konto, pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung)
from test_material_import import csv_bytes, nach_nr, ok, probelauf, uebernehmen  # noqa: E402
from test_material_katalog import exportieren, importieren  # noqa: E402
from test_material_trennung import bis_schritt, endversion, zeilen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

ART = "/api/material/artikel"


def kategorie_neu(c, **d):
    r = c.post("/api/material/kategorien", json=d)
    assert r.status_code == 201, r.get_json()
    return r.json["kategorie"]


def formular_neu(c, ziel, titel, punkte, aktivieren=True):
    r = c.post("/api/material/formulare", json=dict(ziel, titel=titel, punkte=punkte))
    assert r.status_code == 201, r.get_json()
    fid = r.json["formular"]["id"]
    if aktivieren:
        assert c.post(f"/api/material/formulare/{fid}/aktivieren", json={}).status_code == 200
    return fid


def aufbau(tmp):
    """Umgebung mit Katalog (katalog_grund: Gurte textil, Karabiner Metall) plus Kategorie „Seile“ (Häkchen „Artikel
    haben eine Länge“) mit Unterkategorie „Statikseile“ (ohne eigenes Häkchen) und dem Produkt „Seil Gamma“ darin;
    generisches Formular der Seile mit einem Längenpunkt und einem Ja/Nein-Punkt; Gliederung mit Lager."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    kp = k["katalog"]
    seile = kategorie_neu(kp, name="Seile", parent_id=ids["psa"], default_material_kind="textil",
                          default_interval_months=12, items_have_length=True)["id"]
    statik = kategorie_neu(kp, name="Statikseile", parent_id=seile)["id"]
    r = kp.post("/api/material/produkte", json={"category_id": statik, "manufacturer": "Testwerk", "model": "Seil Gamma",
                                                "article_no": "SG-1", "material_kind": "textil", "lifetime_years": 10})
    assert r.status_code == 201, r.get_json()
    seil = r.json["produkt"]["id"]
    form = formular_neu(kp, {"kategorie_id": seile}, "Seilprüfung Platzhalter", [
        {"gruppe": "Maße", "text": "Testpunkt Seillänge", "art": "laenge"},
        {"gruppe": "Mantel", "text": "Testpunkt Mantel", "art": "yesno", "soll": "nein"}])
    f = pruef_formulare(kp, ids)
    gid, system = gliederung(k["adm"])
    lager = ordner_neu(k["wart"], gid, "Lager Platzhalter")
    h = _heute()
    return SimpleNamespace(app=app, k=k, ids=ids, kp=kp, seile=seile, statik=statik, seil=seil, form=form, formulare=f,
                           gid=gid, system=system, lager=lager, w=k["wart"], p=k["pruefer"], adm=k["adm"],
                           herst=f"{h.year - 1}-03")


def artikel(c, iid):
    r = c.get(f"{ART}/{iid}")
    assert r.status_code == 200, r.get_json()
    return r.json["artikel"]


def punkt(pr, text):
    return next(x for x in pr["punkte"] if x["text"] == text)


def setzen(c, pid, rid, **d):
    return c.put(f"/api/material/pruefungen/{pid}/punkte/{rid}", json=d)


def fest(c, pid):
    r = festschreiben(c, pid, ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()
    return r


def journal_laenge(app, iid):
    return [(json.loads(r["before_json"]), json.loads(r["after_json"])) for r in zeilen(
        app, "SELECT before_json, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
             "AND action = 'laenge_geaendert' ORDER BY id", (iid,))]


def protokoll_text(app, tmp, pid):
    zeile = protokoll_zeile(app, pid)
    return _flach(" ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"]))))


def csv_lesen(daten):
    text = daten.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    return rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]


# --- 1. Migration 19 → 20 ----------------------------------------------------------------------------------------------

def _tabelle_sql(pfad, name):
    conn = sqlite3.connect(pfad)
    try:
        return conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()[0]
    finally:
        conn.close()


def _spalten(pfad, tabelle):
    conn = sqlite3.connect(pfad)
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
    finally:
        conn.close()


def _schema(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return {(r[0], r[1]): r[2] for r in conn.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE "
                                                           "'sqlite_%' ORDER BY type, name")}
    finally:
        conn.close()


def _auf_stand_19(pfad):
    """Eine Datenbank auf Stand 20 so zurückbauen, wie Stand 19 sie hatte: beide Spalten weg, mat_checklist_item mit dem
    CHECK aus Schritt 1 (ohne „laenge“), Schemaversion 19 – Zeilen und Kennungen bleiben. Über die Schnittstelle lässt
    sich auf Stand 19 nichts mehr anlegen (der Code schreibt die neuen Spalten), deshalb entsteht der Bestand vorher."""
    from app.material import models
    conn = sqlite3.connect(pfad)
    conn.execute("PRAGMA foreign_keys = OFF")
    with conn:
        conn.execute("ALTER TABLE mat_item DROP COLUMN length_m")
        conn.execute("ALTER TABLE mat_category DROP COLUMN items_have_length")
        alt = next(x for x in models.SCHRITT_1 if "mat_checklist_item (" in x)
        conn.execute(alt.replace("IF NOT EXISTS mat_checklist_item", "mat_checklist_item_alt"))
        conn.execute("INSERT INTO mat_checklist_item_alt SELECT * FROM mat_checklist_item")
        conn.execute("DROP TABLE mat_checklist_item")
        conn.execute("ALTER TABLE mat_checklist_item_alt RENAME TO mat_checklist_item")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mat_checklist_form ON mat_checklist_item(form_id, position)")
        conn.execute("UPDATE mat_meta SET wert = '19' WHERE schluessel = 'schema_version'")
    conn.close()


def test_migration_20():
    """19 → 20 an einem Datenordner mit Bestand (Kategorien, Produkte, Formulare mit Prüfpunkten, Artikel, festgeschriebene
    Prüfung mit Ergebniszeilen): beide Spalten kommen dazu, mat_checklist_item wird mit dem CHECK neu aufgebaut – alle
    Zeilen, Kennungen und der Index bleiben, die Ergebniszeilen zeigen weiter auf ihre Prüfpunkte, kein Fremdschlüssel
    bricht; Tabellen, Indizes und Trigger danach genau wie auf einer frisch angelegten Datenbank; zweiter Lauf und
    Schritt 20 für sich ändern nichts; bis Schritt 19 fehlen Spalten und „laenge“ im CHECK; die CHECKs greifen."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app19 = bis_schritt(19, nachruesten=False)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        assert zeilen(app19, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == "19"
        assert "items_have_length" not in _spalten(pfad, "mat_category") and "length_m" not in _spalten(pfad, "mat_item")
        assert "'laenge'" not in _tabelle_sql(pfad, "mat_checklist_item")
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "stroemis.db")
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["adm"])
        lager = ordner_neu(k["wart"], gid, "Lager")
        a = neuer_artikel(k["wart"], ids["hms"], lager, serial_no="MIG-20")
        pid = starten(k["pruefer"], a["id"]).json["pruefung"]["id"]
        assert festschreiben(k["pruefer"], pid, ergebnis="einsatzbereit").status_code == 200
        punkte_vorher = zeilen(app, "SELECT * FROM mat_checklist_item ORDER BY id")
        ergebnisse_vorher = zeilen(app, "SELECT id, checklist_item_id FROM mat_inspection_result ORDER BY id")
        schema_20 = _schema(pfad)
        spalten_item_20 = _spalten(pfad, "mat_item")
        tabellen = ("mat_checklist_item", "mat_inspection_result", "mat_item", "mat_category", "mat_form", "mat_audit")
        zahlen_vorher = {t: zeilen(app, f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in tabellen}
        assert len(punkte_vorher) >= 7 and any(r["checklist_item_id"] for r in ergebnisse_vorher)
        _auf_stand_19(pfad)
        assert "items_have_length" not in _spalten(pfad, "mat_category") and "length_m" not in _spalten(pfad, "mat_item")
        assert "'laenge'" not in _tabelle_sql(pfad, "mat_checklist_item")

        app = make_app(tmp)
        # Seit Schritt 21 (Sets) läuft die Migration weiter – 19 → 20 → 21; Schritt 20 prüft dieser Test.
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        assert int(endversion()) >= 20
        assert "items_have_length" in _spalten(pfad, "mat_category") and "length_m" in _spalten(pfad, "mat_item")
        sql = _tabelle_sql(pfad, "mat_checklist_item")
        assert "'laenge'" in sql and "_neu" not in sql and "_alt" not in sql, sql
        assert zeilen(app, "SELECT * FROM mat_checklist_item ORDER BY id") == punkte_vorher
        assert zeilen(app, "SELECT id, checklist_item_id FROM mat_inspection_result ORDER BY id") == ergebnisse_vorher
        assert {t: zeilen(app, f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in tabellen} == zahlen_vorher
        # Tabellen, Indizes und Trigger genau wie auf der frisch angelegten Datenbank (vor dem Rückbau). Seit Schritt 21
        # steht length_m nach dem Rückbau hinter dessen Spalten (ADD COLUMN hängt an) – bei mat_item zählen die Spalten.
        schema = _schema(pfad)
        assert sorted(_spalten(pfad, "mat_item")) == sorted(spalten_item_20)
        schema.pop(("table", "mat_item"))
        schema_20.pop(("table", "mat_item"))
        assert schema == schema_20, {k: (schema.get(k), schema_20.get(k)) for k in set(schema) | set(schema_20)
                                     if schema.get(k) != schema_20.get(k)}
        assert ("index", "idx_mat_checklist_form") in schema
        conn = sqlite3.connect(pfad)
        try:
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert conn.execute("SELECT COUNT(*) FROM mat_category WHERE items_have_length <> 0").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM mat_item WHERE length_m IS NOT NULL").fetchone()[0] == 0
            # CHECKs greifen: Länge 0 und 10000, Häkchen 2, unbekannte Prüfpunktart; „laenge“ geht.
            for befehl in ("UPDATE mat_item SET length_m = 0", "UPDATE mat_item SET length_m = 10000",
                           "UPDATE mat_category SET items_have_length = 2", "UPDATE mat_checklist_item SET editor = 'x'"):
                try:
                    conn.execute(befehl)
                    raise AssertionError(befehl)
                except sqlite3.IntegrityError:
                    conn.rollback()
            conn.execute("UPDATE mat_checklist_item SET editor = 'laenge'")
            conn.execute("UPDATE mat_item SET length_m = 9999.9")
            conn.rollback()
            # Zweiter Lauf und Schritt 20 für sich: keine Änderung.
            assert models.migrieren(conn) == models.SCHEMA_VERSION >= 20
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_20(conn)
            assert conn.total_changes == n
            conn.rollback()
        finally:
            conn.close()
        make_app(tmp)
        schema = _schema(pfad)
        schema.pop(("table", "mat_item"))                 # Spaltenreihenfolge seit Schritt 21, siehe oben
        assert schema == schema_20
        # Der Bestand arbeitet weiter: eine Länge am Artikel, eine neue Prüfung mit den alten Prüfpunkten.
        assert k["wart"].put(f"{ART}/{a['id']}", json={"notes": "nach der Migration"}).status_code == 200
        pid2 = starten(k["pruefer"], a["id"]).json["pruefung"]["id"]
        assert festschreiben(k["pruefer"], pid2, ergebnis="einsatzbereit").status_code == 200
        assert models.SCHRITTE[20] is models._schritt_20 and "laenge" in models.EDITOREN and "laenge" not in models.EDITOREN_1
    print("Migration 19 → 20 bestanden.")


# --- 2. Kategorie-Häkchen mit Vererbung --------------------------------------------------------------------------------

def test_haekchen_vererbt():
    """Das Häkchen steht an der Kategorie und wirkt auf Unterkategorien (laenge_wirksam); die Produkte darin tragen
    laenge_moeglich; nur die Katalogpflege setzt es; es steht im Journal; weg ist weg – auch für die Unterkategorie."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kats = {k["id"]: k for k in t.kp.get("/api/material/kategorien").json["kategorien"]}
        assert kats[t.seile]["items_have_length"] is True and kats[t.seile]["laenge_wirksam"] is True
        assert kats[t.statik]["items_have_length"] is False and kats[t.statik]["laenge_wirksam"] is True
        assert kats[t.ids["gurte"]]["items_have_length"] is False and kats[t.ids["gurte"]]["laenge_wirksam"] is False
        assert t.kp.get(f"/api/material/produkte/{t.seil}").json["produkt"]["laenge_moeglich"] is True
        assert t.kp.get(f"/api/material/produkte/{t.ids['gurt']}").json["produkt"]["laenge_moeglich"] is False
        with t.app.app_context():
            from app.material.services import katalog
            assert katalog.laenge_wirksam(t.statik) and not katalog.laenge_wirksam(t.ids["karabiner"])
        # Nur die Katalogpflege; der Materialwart nicht.
        assert t.w.put(f"/api/material/kategorien/{t.seile}", json={"items_have_length": False}).status_code == 403
        # Journal und Wahrheitswerte („ja“, 1, true).
        j = zeilen(t.app, "SELECT after_json FROM mat_audit WHERE entity = 'category' AND entity_id = ? AND action = 'angelegt'",
                   (t.seile,))
        assert json.loads(j[0]["after_json"])["items_have_length"] == 1
        assert t.kp.put(f"/api/material/kategorien/{t.statik}", json={"items_have_length": "ja"}).json["kategorie"]["items_have_length"] is True
        assert t.kp.put(f"/api/material/kategorien/{t.statik}", json={"items_have_length": "vielleicht"}).status_code == 400
        assert t.kp.put(f"/api/material/kategorien/{t.statik}", json={"items_have_length": 0}).json["kategorie"]["items_have_length"] is False
        j = zeilen(t.app, "SELECT before_json, after_json FROM mat_audit WHERE entity = 'category' AND entity_id = ? "
                          "AND action = 'geaendert' ORDER BY id", (t.statik,))
        assert [json.loads(x["after_json"])["items_have_length"] for x in j] == [1, 0]
        # Häkchen an der Oberkategorie weg: die Unterkategorie verliert es mit.
        r = t.kp.put(f"/api/material/kategorien/{t.seile}", json={"items_have_length": False})
        assert r.status_code == 200 and r.json["kategorie"]["laenge_wirksam"] is False
        kats = {k["id"]: k for k in t.kp.get("/api/material/kategorien").json["kategorien"]}
        assert kats[t.statik]["laenge_wirksam"] is False
        assert t.kp.get(f"/api/material/produkte/{t.seil}").json["produkt"]["laenge_moeglich"] is False
    print("Häkchen mit Vererbung bestanden.")


# --- 3. Katalogdatei (Format 2) ----------------------------------------------------------------------------------------

def _katalog_json(roh):
    import zipfile
    with zipfile.ZipFile(io.BytesIO(roh)) as z:
        return json.loads(z.read("katalog.json"))


def _kat(daten, *pfad):
    liste = daten["kategorien"]
    k = None
    for name in pfad:
        k = next(x for x in liste if x["name"] == name)
        liste = k.get("unterkategorien", [])
    return k


def test_katalogformat():
    """Der Export schreibt „artikel_laenge“ an jede Kategorie; der Import liest es: true setzt, false nimmt weg, ein
    fehlender Schlüssel lässt es, wie es war (neu: false). Auch in einer reinen JSON-Datei."""
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        t = aufbau(tmp_a)
        daten = _katalog_json(exportieren(t.kp))
        assert daten["version"] == 2
        assert _kat(daten, "PSA gegen Absturz", "Seile")["artikel_laenge"] is True
        assert _kat(daten, "PSA gegen Absturz", "Seile", "Statikseile")["artikel_laenge"] is False
        assert _kat(daten, "PSA gegen Absturz", "Gurte")["artikel_laenge"] is False
        # Instanz B: der Export von A kommt an – mit dem Häkchen.
        app_b = make_app(tmp_b)
        from test_material import anmelden
        b = anmelden(app_b, "admin@example.org", "geheim123")
        roh = exportieren(t.kp)
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        kats = {k["name"]: k for k in b.get("/api/material/kategorien").json["kategorien"]}
        assert kats["Seile"]["items_have_length"] is True and kats["Statikseile"]["laenge_wirksam"] is True
        assert kats["Gurte"]["items_have_length"] is False
        # Fehlender Schlüssel: unverändert (Seile behält es), neue Kategorie ohne Schlüssel: false.
        j = {"format": "stroemis-material-katalog", "version": 2, "kategorien": [
            {"name": "PSA gegen Absturz", "unterkategorien": [{"name": "Seile", "norm": "Platzhalter-Norm"},
                                                              {"name": "Bandschlingen Platzhalter"}]}],
             "produkte": [], "formulare": []}
        ber = importieren(b, json.dumps(j).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        kats = {k["name"]: k for k in b.get("/api/material/kategorien").json["kategorien"]}
        assert kats["Seile"]["items_have_length"] is True and kats["Seile"]["norm"] == "Platzhalter-Norm"
        assert kats["Bandschlingen Platzhalter"]["items_have_length"] is False
        # false nimmt es weg, true setzt es (auch an der Unterkategorie).
        j["kategorien"][0]["unterkategorien"] = [{"name": "Seile", "artikel_laenge": False,
                                                 "unterkategorien": [{"name": "Statikseile", "artikel_laenge": True}]}]
        ber = importieren(b, json.dumps(j).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"] and ber["kategorien"]["geaendert"] == 2, ber
        kats = {k["name"]: k for k in b.get("/api/material/kategorien").json["kategorien"]}
        assert kats["Seile"]["items_have_length"] is False and kats["Statikseile"]["items_have_length"] is True
        assert kats["Seile"]["laenge_wirksam"] is False and kats["Statikseile"]["laenge_wirksam"] is True
        # null wie ein fehlender Schlüssel (Prüfung der Länge, V8): Statikseile behält das Häkchen.
        j["kategorien"][0]["unterkategorien"] = [{"name": "Seile", "unterkategorien": [
            {"name": "Statikseile", "artikel_laenge": None}]}]
        ber = importieren(b, json.dumps(j).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        kats = {k["name"]: k for k in b.get("/api/material/kategorien").json["kategorien"]}
        assert kats["Statikseile"]["items_have_length"] is True
        # Ein Wert, der kein Wahrheitswert ist: Fehlerzeile, nichts gespeichert.
        j["kategorien"][0]["unterkategorien"] = [{"name": "Seile", "artikel_laenge": "lang"}]
        ber = importieren(b, json.dumps(j).encode(), False, "katalog.json")
        assert not ber["gespeichert"] and any("Artikel haben eine Länge" in f for f in ber["fehler"]), ber
    print("Katalogformat bestanden.")


# --- 4. Artikel mit Länge ----------------------------------------------------------------------------------------------

def test_artikel_laenge():
    """Anlegen und Bearbeiten mit „57,5“ oder „57.5“, Rundung auf eine Nachkommastelle, Grenzen 0,1 bis 9999,9, 409 ohne
    vorgesehene Länge (Kategorie), Journal „geaendert“ mit length_m, Steckbrief-Felder, Listen tragen die Länge; weg ist
    das Häkchen, bleibt die Länge – nur ein anderer Wert ist dann 409."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a = neuer_artikel(t.w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-1", length_m="57,5")
        assert a["length_m"] == 57.5 and a["laenge_text"] == "57,5 m" and a["laenge_moeglich"] is True, a
        b = neuer_artikel(t.w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-2", length_m="57.56")
        assert b["length_m"] == 57.6, b
        c = neuer_artikel(t.w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-3", length_m=30)
        assert c["length_m"] == 30.0 and c["laenge_text"] == "30,0 m"
        ohne = neuer_artikel(t.w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-4")
        assert ohne["length_m"] is None and ohne["laenge_text"] == "" and ohne["laenge_moeglich"] is True
        for wert, text in (("0", "zwischen 0,1 und 9999,9"), ("0,04", "zwischen"), ("10000", "zwischen"), ("abc", "keine Zahl"),
                           (True, "keine Zahl"), ("-5", "zwischen")):
            r = t.w.post(ART, json={"product_id": t.seil, "folder_id": t.lager, "manufactured_on": t.herst,
                                    "serial_no": "SL-X", "length_m": wert})
            assert r.status_code == 400 and text in r.json["error"], (wert, r.get_json())
        # Ohne vorgesehene Länge (Karabiner): 409 mit Klartext – ohne Länge geht es.
        r = t.w.post(ART, json={"product_id": t.ids["hms"], "folder_id": t.lager, "serial_no": "HB-1", "length_m": "1,5"})
        assert r.status_code == 409 and "keine Länge vorgesehen" in r.json["error"], r.get_json()
        hms = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="HB-1")
        assert hms["length_m"] is None and hms["laenge_moeglich"] is False
        assert t.w.put(f"{ART}/{hms['id']}", json={"length_m": "2"}).status_code == 409
        assert t.w.put(f"{ART}/{hms['id']}", json={"length_m": None}).status_code == 200
        # Bearbeiten: Komma oder Punkt, Journal „geaendert“ mit length_m; weggelassen bleibt; null leert.
        r = t.w.put(f"{ART}/{a['id']}", json={"stand": a["stand"], "length_m": "60.0"})
        assert r.status_code == 200 and r.json["artikel"]["length_m"] == 60.0, r.get_json()
        j = zeilen(t.app, "SELECT before_json, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                          "AND action = 'geaendert' ORDER BY id DESC LIMIT 1", (a["id"],))[0]
        assert json.loads(j["before_json"]) == {"length_m": 57.5} and json.loads(j["after_json"]) == {"length_m": 60.0}, j
        assert t.w.put(f"{ART}/{a['id']}", json={"notes": "Platzhalter"}).json["artikel"]["length_m"] == 60.0
        assert t.w.put(f"{ART}/{a['id']}", json={"length_m": "60,0"}).status_code == 200
        assert zeilen(t.app, "SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'geaendert'",
                      (a["id"],))[0]["n"] == 2                                   # derselbe Wert: kein neuer Eintrag
        assert t.w.put(f"{ART}/{a['id']}", json={"length_m": None}).json["artikel"]["length_m"] is None
        assert t.w.put(f"{ART}/{a['id']}", json={"length_m": "57,5"}).json["artikel"]["length_m"] == 57.5
        assert artikel(t.w, a["id"])["journal"][0]["action"] == "geaendert"
        # Listen: die Ordneransicht trägt die Länge je Artikel.
        liste = {x["id"]: x for x in t.w.get(f"/api/material/ordner/{t.lager}").json["ordner"]["artikel"]}
        assert liste[a["id"]]["length_m"] == 57.5 and liste[a["id"]]["laenge_text"] == "57,5 m" and liste[hms["id"]]["length_m"] is None
        # Häkchen weg: die Länge bleibt lesbar und unverändert speicherbar, ein anderer Wert ist 409, leeren geht.
        assert t.kp.put(f"/api/material/kategorien/{t.seile}", json={"items_have_length": False}).status_code == 200
        x = artikel(t.w, a["id"])
        assert x["length_m"] == 57.5 and x["laenge_moeglich"] is False
        assert t.w.put(f"{ART}/{a['id']}", json={"notes": "bleibt"}).status_code == 200
        assert t.w.put(f"{ART}/{a['id']}", json={"length_m": "57,5"}).status_code == 200
        assert t.w.put(f"{ART}/{a['id']}", json={"length_m": "58"}).status_code == 409
        assert t.w.put(f"{ART}/{c['id']}", json={"length_m": None}).json["artikel"]["length_m"] is None
        assert t.w.put(f"{ART}/{c['id']}", json={"length_m": "30"}).status_code == 409
        # Datenbank: ein Wert außerhalb der Grenzen kommt nicht hinein (CHECK).
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute("UPDATE mat_item SET length_m = 12000 WHERE id = ?", (a["id"],))
            raise AssertionError("CHECK fehlt")
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    print("Artikel mit Länge bestanden.")


# --- 5. CSV-Export und Bestandsimport ----------------------------------------------------------------------------------

def test_csv_und_import():
    """CSV: Spalte „Länge (m)“ hinter „Lebensende“ mit „57,5“ (leer ohne Länge). Bestandsimport: Spalte „Länge“ wird
    erkannt (Feld laenge), „60,5“ und „12.0“ kommen an, bei einer Kategorie ohne Länge nur als Hinweis und in der
    Bemerkung, Unlesbares ebenso; die Nacharbeits-CSV führt die Spalte."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        from app.material.services import export
        a = neuer_artikel(t.w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-1", length_m="57,5")
        hms = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="HB-1")
        r = t.w.get(f"/materialablage/export/{t.lager}.csv")
        assert r.status_code == 200
        kopf, rows = csv_lesen(r.data)
        assert kopf == list(export.ARTIKEL_SPALTEN) and kopf[kopf.index("Lebensende") + 1] == "Länge (m)", kopf
        assert kopf[kopf.index("Länge (m)") + 1] == "Bemerkung"
        z = {x["Inventarnummer"]: x for x in rows}
        assert z[a["inventory_no"]]["Länge (m)"] == "57,5" and z[hms["inventory_no"]]["Länge (m)"] == "", z
        # Bestandsimport.
        kopfzeile = ["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Herstelldatum", "Länge"]
        daten = csv_bytes([kopfzeile,
                           ["Testwerk", "Seil Gamma", "SG-1", "IM-1", "03/2024", "60,5"],
                           ["Testwerk", "Seil Gamma", "SG-1", "IM-2", "03/2024", "12.0"],
                           ["Testwerk", "Seil Gamma", "SG-1", "IM-3", "03/2024", "lang"],
                           ["Testwerk", "HMS Beta", "HB-7", "IM-4", "", "3"],
                           ["Testwerk", "Seil Gamma", "SG-1", "IM-5", "03/2024", ""]])
        b = ok(probelauf(t.w, t.lager, daten, "laengen.csv"))
        assert [s["zuordnung"] for s in b["spalten"]][-1] == "laenge", b["spalten"]
        assert any(f["feld"] == "laenge" and f["text"] == "Länge (m)" for f in b["felder"])
        z = nach_nr(b)
        assert all(z[n]["status"] == "uebernehmbar" for n in (2, 3, 4, 5, 6)), {n: z[n]["status"] for n in z}
        assert any("unlesbar" in h for h in z[4]["hinweise"]), z[4]
        assert any("keine Länge vorgesehen" in h for h in z[5]["hinweise"]), z[5]
        assert not z[2]["hinweise"] or not any("Länge" in h for h in z[2]["hinweise"]), z[2]
        b = ok(uebernehmen(t.w, t.lager, daten, "laengen.csv"), 201)
        assert b["import"]["angelegt"] == 5 and b["zahlen"]["angelegt"] == 5, b["zahlen"]
        nach_serie = {r["serial_no"]: r for r in zeilen(t.app, "SELECT serial_no, length_m, notes FROM mat_item")}
        assert nach_serie["IM-1"]["length_m"] == 60.5 and nach_serie["IM-2"]["length_m"] == 12.0
        assert nach_serie["IM-3"]["length_m"] is None and "Länge laut Liste: lang" in nach_serie["IM-3"]["notes"]
        assert nach_serie["IM-4"]["length_m"] is None and "Länge laut Liste: 3" in nach_serie["IM-4"]["notes"]
        assert nach_serie["IM-5"]["length_m"] is None and "Länge" not in nach_serie["IM-5"]["notes"]
        # „Länge: …“ landet nicht mehr als Bemerkungstitel; „Seillänge (m)“ wird ebenso erkannt.
        from app.material.services import bestandsimport
        assert bestandsimport.erkennen("Seillänge (m)")[0] == "laenge" and bestandsimport.erkennen("Länge")[0] == "laenge"
        assert bestandsimport.erkennen("Farbe")[0] == "bemerkung"
        assert ("Länge (m)", "laenge") in bestandsimport.NACHARBEIT_SPALTEN
    print("CSV und Bestandsimport bestanden.")


# --- 6. Prüfung mit Längenpunkt ----------------------------------------------------------------------------------------

def test_pruefung_laenge():
    """Formular-Editor: Art „laenge“ ohne Sollwert, nie kritisch. Prüfung: vorbelegt mit der Artikellänge; „55“ wird
    „55,0“; Festschreiben übernimmt den abweichenden Wert (Journal „laenge_geaendert“ mit Verweis, Protokoll
    „57,5 m → 55,0 m“); unverändert → kein Journal, Protokoll „(unverändert)“; ohne Länge am Artikel: leer und Pflicht;
    Berichtigung übernimmt ebenso; ohne vorgesehene Länge (Karabiner): „nicht zutreffend“, Wert 409; Ergebniszeilen
    festgeschrieben unveränderlich; Lebenslauf und Meine PSA zeigen die Länge."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kp, w, p = t.kp, t.w, t.p
        f = kp.get(f"/api/material/formulare/{t.form}").json
        assert f["editoren"]["laenge"] == "Länge (m)"
        pl = next(x for x in f["formular"]["punkte"] if x["art"] == "laenge")
        assert pl["soll"] == "" and pl["pflicht"] is True and pl["kritisch"] is False
        r = kp.post("/api/material/formulare", json={"kategorie_id": t.statik, "titel": "x", "punkte": [
            {"text": "Testpunkt Länge", "art": "laenge", "soll": "50", "kritisch": True}]})
        assert r.status_code == 400 and "Kritisch" in r.json["error"], r.get_json()
        fid = formular_neu(kp, {"kategorie_id": t.statik}, "Statik Platzhalter",
                           [{"text": "Testpunkt Länge", "art": "laenge", "soll": "50"}], aktivieren=False)
        assert kp.get(f"/api/material/formulare/{fid}").json["formular"]["punkte"][0]["soll"] == ""
        assert kp.delete(f"/api/material/formulare/{fid}", headers=H).status_code == 200

        a = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-1", length_m="57,5")
        r = starten(p, a["id"])
        assert r.status_code == 201, r.get_json()
        pr = r.json["pruefung"]
        assert pr["laenge"] == {"wert": 57.5, "text": "57,5 m", "moeglich": True}, pr["laenge"]
        x = punkt(pr, "Testpunkt Seillänge")
        assert (x["befund"], x["wert"], x["soll"], x["art"]) == ("ok", "57,5", "57,5", "laenge"), x
        assert setzen(p, pr["id"], x["id"], wert="abc").status_code == 400
        assert setzen(p, pr["id"], x["id"], wert="0").status_code == 400
        r = setzen(p, pr["id"], x["id"], wert="55")
        assert r.status_code == 200 and r.json["punkt"]["wert"] == "55,0", r.get_json()
        assert setzen(p, pr["id"], x["id"], wert="55.04").json["punkt"]["wert"] == "55,0"
        assert artikel(w, a["id"])["length_m"] == 57.5                     # bis zum Festschreiben unverändert
        fest(p, pr["id"])
        assert artikel(w, a["id"])["length_m"] == 55.0
        j = journal_laenge(t.app, a["id"])
        assert j == [({"length_m": 57.5}, {"length_m": 55.0, "pruefung": pr["id"], "art": "eingang"})], j
        erg = zeilen(t.app, "SELECT expected_value, value, finding FROM mat_inspection_result WHERE inspection_id = ? "
                            "AND editor = 'laenge'", (pr["id"],))[0]
        assert (erg["expected_value"], erg["value"], erg["finding"]) == ("57,5", "55,0", "ok")
        text = protokoll_text(t.app, tmp, pr["id"])
        assert "57,5 m → 55,0 m" in text, text[:2000]
        lese = p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        assert punkt(lese, "Testpunkt Seillänge")["wert"] == "55,0"
        # Festgeschrieben: die Ergebniszeile lässt sich nicht mehr ändern (Trigger aus Schritt 6).
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute("UPDATE mat_inspection_result SET value = '99,0' WHERE inspection_id = ? AND editor = 'laenge'",
                         (pr["id"],))
            raise AssertionError("festgeschriebene Ergebniszeile geändert")
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
        # Der Steckbrief trägt die neue Länge und den Journaleintrag mit Beschriftung.
        st = artikel(w, a["id"])
        assert st["laenge_text"] == "55,0 m" and any(e["action"] == "laenge_geaendert" for e in st["journal"])
        # Zweite Prüfung: vorbelegt mit 55,0; unverändert festgeschrieben → kein Journal, „(unverändert)“ im Protokoll.
        pr2 = starten(p, a["id"]).json["pruefung"]
        x2 = punkt(pr2, "Testpunkt Seillänge")
        assert (x2["wert"], x2["soll"]) == ("55,0", "55,0")
        fest(p, pr2["id"])
        assert len(journal_laenge(t.app, a["id"])) == 1 and artikel(w, a["id"])["length_m"] == 55.0
        assert "55,0 m (unverändert)" in protokoll_text(t.app, tmp, pr2["id"])
        # Berichtigung der zweiten Prüfung mit anderer Länge: gleiche Logik, die neue Länge gilt.
        r = p.post(f"/api/material/pruefungen/{pr2['id']}/berichtigen", json={"grund": "Platzhalter: falsch gemessen"})
        assert r.status_code == 201, r.get_json()
        ber = r.json["pruefung"]
        xb = punkt(ber, "Testpunkt Seillänge")
        assert xb["wert"] == "55,0"
        assert setzen(p, ber["id"], xb["id"], wert="54,5").status_code == 200
        fest(p, ber["id"])
        assert artikel(w, a["id"])["length_m"] == 54.5
        j = journal_laenge(t.app, a["id"])
        assert len(j) == 2 and j[1] == ({"length_m": 55.0}, {"length_m": 54.5, "pruefung": ber["id"], "art": pr2["art"]}), j
        assert "55,0 m → 54,5 m" in protokoll_text(t.app, tmp, ber["id"])
        # Artikel ohne Länge: leer vorbelegt, Pflicht – „Noch ohne Befund“; „n. z.“ geht; ein Wert trägt die Länge ein.
        o = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-2")
        pro = starten(p, o["id"]).json["pruefung"]
        assert pro["laenge"] == {"wert": None, "text": "", "moeglich": True}
        xo = punkt(pro, "Testpunkt Seillänge")
        assert (xo["befund"], xo["wert"], xo["soll"]) == ("ok", "", "")
        r = festschreiben(p, pro["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Testpunkt Seillänge" in r.json["error"], r.get_json()
        assert setzen(p, pro["id"], xo["id"], wert="30").status_code == 200
        fest(p, pro["id"])
        assert artikel(w, o["id"])["length_m"] == 30.0
        assert journal_laenge(t.app, o["id"]) == [({"length_m": None}, {"length_m": 30.0, "pruefung": pro["id"], "art": "eingang"})]
        assert "30,0 m" in protokoll_text(t.app, tmp, pro["id"]) and "→" not in protokoll_text(t.app, tmp, pro["id"])
        # „nicht zutreffend“ ändert nichts am Artikel.
        o2 = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="SL-3", length_m="20")
        pro2 = starten(p, o2["id"]).json["pruefung"]
        xo2 = punkt(pro2, "Testpunkt Seillänge")
        assert setzen(p, pro2["id"], xo2["id"], befund="nicht_zutreffend").status_code == 200
        fest(p, pro2["id"])
        assert artikel(w, o2["id"])["length_m"] == 20.0 and not journal_laenge(t.app, o2["id"])
        # Ohne vorgesehene Länge (Karabiner mit Längenpunkt im Formular): „nicht zutreffend“, ein Wert ist 409.
        formular_neu(kp, {"kategorie_id": t.ids["karabiner"]}, "Karabiner mit Länge", [
            {"text": "Testpunkt Verschluss", "art": "yesno", "soll": "ja"}, {"text": "Testpunkt Länge", "art": "laenge"}])
        hms = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="HB-1")
        prh = starten(p, hms["id"]).json["pruefung"]
        assert prh["laenge"]["moeglich"] is False
        xh = punkt(prh, "Testpunkt Länge")
        assert (xh["befund"], xh["wert"], xh["soll"]) == ("nicht_zutreffend", "", "")
        r = setzen(p, prh["id"], xh["id"], wert="1")
        assert r.status_code == 409 and "keine Länge vorgesehen" in r.json["error"], r.get_json()
        fest(p, prh["id"])
        assert artikel(w, hms["id"])["length_m"] is None and not journal_laenge(t.app, hms["id"])
        assert "nicht zutreffend" in protokoll_text(t.app, tmp, prh["id"])
        # Lebenslauf-PDF und Meine PSA zeigen die Länge.
        r = w.get(f"/materialablage/artikel/{a['id']}/lebenslauf.pdf")
        assert r.status_code == 200
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "Länge 54,5 m" in text and "Länge geändert" in text and "57,5 m" in text, text[:3000]
        person, person_id = neues_konto(t.app, "person@example.org", name="Person Platzhalter", stufe=0)
        assert w.put(f"{ART}/{a['id']}/zuordnung", json={"user_id": person_id}).status_code == 200
        karte = person.get("/api/material/meine-psa").json["artikel"][0]
        assert karte["id"] == a["id"] and karte["length_m"] == 54.5 and karte["laenge_text"] == "54,5 m", karte
    print("Prüfung mit Längenpunkt bestanden.")


# --- 6b. Nachbesserungen nach der Prüfung vom 22.10.2026 -----------------------------------------------------------------

def test_nachbesserung_pruefung():
    """B1: Länge während der Prüfung geändert → 409, der Längenpunkt bekommt die neue Länge (ein eigener Messwert
    bleibt), danach geht das Festschreiben ohne Rückschreiben der alten Länge. B2: NaN, Infinity und „1e309“ → 400, kein
    Journal mit NaN. B3: Berichtigung behält das Soll des Originals; Tippfehler 57,5 → 5,0 berichtigt auf 57,5 →
    „57,5 m (unverändert)“, Artikel wieder 57,5; echte Kürzung 50,0 und Berichtigung eines anderen Punkts →
    „57,5 m → 50,0 m“, Artikel 50,0. B4: ohne vorgesehene Länge nur „nicht zutreffend“ (ok/Mangel 409); ein
    Mangel, der vor dem Entfernen des Häkchens gesetzt war, zählt beim Festschreiben nicht mehr und der Messwert
    steht in der Bemerkung (V5). V1: Zahl 0 ist 400, nicht leer. V3: höchstens ein Längenpunkt je Formular. V4:
    Produktwechsel auf ein Produkt ohne Länge leert sie."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kp, w, p = t.kp, t.w, t.p
        # B2: NaN/Unendlich – roh als JSON-Text, wie eine handgemachte Anfrage.
        a = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="NB-1", length_m="57,5")
        for roh in ('NaN', 'Infinity', '-Infinity', '1e309', '"1e309"', '"NaN"'):
            r = w.put(f"{ART}/{a['id']}", data='{"length_m": %s}' % roh, content_type="application/json")
            assert r.status_code == 400, (roh, r.status_code, r.get_data()[:200])
            r = w.post(ART, data='{"product_id": %d, "folder_id": %d, "serial_no": "NB-X", "length_m": %s}'
                       % (t.seil, t.lager, roh), content_type="application/json")
            assert r.status_code == 400, (roh, r.status_code, r.get_data()[:200])
        assert all("NaN" not in (x["after_json"] or "") and "Infinity" not in (x["after_json"] or "")
                   for x in zeilen(t.app, "SELECT after_json FROM mat_audit"))
        st = w.get(f"{ART}/{a['id']}")
        assert st.status_code == 200 and b"NaN" not in st.data and st.json["artikel"]["length_m"] == 57.5
        with t.app.app_context():
            from app.material.services import journal
            try:
                journal.eintragen("item", a["id"], "geaendert", {"length_m": 1.0}, {"length_m": float("nan")}, name="Test")
                raise AssertionError("NaN im Journal angenommen")
            except ValueError:
                pass

        # B1: Vorbelegung 57,5; der Materialwart trägt währenddessen 60,0 ein; der Prüfer fasst den Punkt nicht an.
        pr = starten(p, a["id"]).json["pruefung"]
        x = punkt(pr, "Testpunkt Seillänge")
        assert (x["wert"], x["soll"]) == ("57,5", "57,5")
        assert w.put(f"{ART}/{a['id']}", json={"length_m": "60"}).status_code == 200
        r = festschreiben(p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 409 and "60,0 m geändert" in r.json["error"], r.get_json()
        assert artikel(w, a["id"])["length_m"] == 60.0
        x = punkt(p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"], "Testpunkt Seillänge")
        assert (x["wert"], x["soll"]) == ("60,0", "60,0"), x
        fest(p, pr["id"])
        assert artikel(w, a["id"])["length_m"] == 60.0
        assert [j for j in journal_laenge(t.app, a["id"])] == [], journal_laenge(t.app, a["id"])
        assert "60,0 m (unverändert)" in protokoll_text(t.app, tmp, pr["id"])
        # B1 mit eigenem Messwert: 55,0 gemessen, währenddessen 58,0 eingetragen → 409, der Messwert bleibt, Soll 58,0.
        pr = starten(p, a["id"]).json["pruefung"]
        x = punkt(pr, "Testpunkt Seillänge")
        assert setzen(p, pr["id"], x["id"], wert="55").status_code == 200
        assert w.put(f"{ART}/{a['id']}", json={"length_m": "58"}).status_code == 200
        r = festschreiben(p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 409, r.get_json()
        x = punkt(p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"], "Testpunkt Seillänge")
        assert (x["wert"], x["soll"]) == ("55,0", "58,0"), x
        fest(p, pr["id"])
        assert artikel(w, a["id"])["length_m"] == 55.0
        assert journal_laenge(t.app, a["id"])[-1] == ({"length_m": 58.0}, {"length_m": 55.0, "pruefung": pr["id"],
                                                                           "art": pr["art"]})
        assert "58,0 m → 55,0 m" in protokoll_text(t.app, tmp, pr["id"])

        # B3, Tippfehler: Original 57,5 → 5,0, berichtigt auf 57,5.
        b = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="NB-2", length_m="57,5")
        pr = starten(p, b["id"]).json["pruefung"]
        assert setzen(p, pr["id"], punkt(pr, "Testpunkt Seillänge")["id"], wert="5").status_code == 200
        fest(p, pr["id"])
        assert artikel(w, b["id"])["length_m"] == 5.0
        r = p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter: Tippfehler"})
        assert r.status_code == 201, r.get_json()
        ber = r.json["pruefung"]
        assert setzen(p, ber["id"], punkt(ber, "Testpunkt Seillänge")["id"], wert="57,5").status_code == 200
        fest(p, ber["id"])
        assert artikel(w, b["id"])["length_m"] == 57.5
        text = protokoll_text(t.app, tmp, ber["id"])
        assert "57,5 m (unverändert)" in text and "5,0 m → 57,5 m" not in text, text[:2000]
        assert journal_laenge(t.app, b["id"])[-1][1]["length_m"] == 57.5
        # B3, echte Kürzung: Original 57,5 → 50,0; die Berichtigung ändert nur den Mantel-Punkt.
        c = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="NB-3", length_m="57,5")
        pr = starten(p, c["id"]).json["pruefung"]
        assert setzen(p, pr["id"], punkt(pr, "Testpunkt Seillänge")["id"], wert="50").status_code == 200
        fest(p, pr["id"])
        r = p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter: Mantel"})
        ber = r.json["pruefung"]
        assert setzen(p, ber["id"], punkt(ber, "Testpunkt Mantel")["id"], notiz="Platzhalter").status_code == 200
        fest(p, ber["id"])
        assert artikel(w, c["id"])["length_m"] == 50.0 and len(journal_laenge(t.app, c["id"])) == 1
        assert "57,5 m → 50,0 m" in protokoll_text(t.app, tmp, ber["id"])

        # V1: die Zahl 0 ist 400 (nicht „leer“), V2: Unicode-Ziffern sind keine Länge.
        d = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="NB-4", length_m="20")
        pr = starten(p, d["id"]).json["pruefung"]
        xd = punkt(pr, "Testpunkt Seillänge")
        assert setzen(p, pr["id"], xd["id"], wert=0).status_code == 400
        assert setzen(p, pr["id"], xd["id"], wert="０５７").status_code == 400
        assert punkt(p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"], "Testpunkt Seillänge")["wert"] == "20,0"
        # B4 + V5: Mangel und Messwert gesetzt, dann nimmt die Verwaltung das Häkchen weg.
        assert setzen(p, pr["id"], xd["id"], wert="12").status_code == 200
        assert setzen(p, pr["id"], xd["id"], befund="mangel", notiz="Platzhalter: Mantel offen").status_code == 200
        assert kp.put(f"/api/material/kategorien/{t.seile}", json={"items_have_length": False}).status_code == 200
        for befund in ("ok", "mangel"):
            r = setzen(p, pr["id"], xd["id"], befund=befund)
            assert r.status_code == 409 and "nicht zutreffend" in r.json["error"], r.get_json()
        # Festschreiben „instandsetzen“ ohne Grund: der Längenpunkt ist kein Mangel mehr → 400 (Grund fehlt).
        r = festschreiben(p, pr["id"], ergebnis="instandsetzen")
        assert r.status_code == 400 and "Grund" in r.json["error"], r.get_json()
        fest(p, pr["id"])
        z = zeilen(t.app, "SELECT finding, value, note FROM mat_inspection_result WHERE inspection_id = ? "
                          "AND editor = 'laenge'", (pr["id"],))[0]
        assert z["finding"] == "nicht_zutreffend" and z["value"] == "" and "Gemessen: 12,0 m" in z["note"], dict(z)
        assert artikel(w, d["id"])["length_m"] == 20.0
        # Ohne Häkchen: „n. z.“ geht weiter, ok/Mangel sind 409 schon beim Setzen.
        pr = starten(p, d["id"]).json["pruefung"]
        xd = punkt(pr, "Testpunkt Seillänge")
        assert setzen(p, pr["id"], xd["id"], befund="nicht_zutreffend").status_code == 200
        assert setzen(p, pr["id"], xd["id"], befund="ok").status_code == 409
        assert kp.put(f"/api/material/kategorien/{t.seile}", json={"items_have_length": True}).status_code == 200

        # V3: zwei Längenpunkte in einem Formular → 400.
        r = kp.post("/api/material/formulare", json={"kategorie_id": t.statik, "titel": "Zwei Längen", "punkte": [
            {"text": "Testpunkt Länge A", "art": "laenge"}, {"text": "Testpunkt Länge B", "art": "laenge"}]})
        assert r.status_code == 400 and "höchstens einen" in r.json["error"], r.get_json()
        # V4: Produktwechsel eines ungeprüften Artikels auf ein Produkt ohne Länge leert sie.
        e = neuer_artikel(w, t.seil, t.lager, manufactured_on=t.herst, serial_no="NB-5", length_m="40")
        r = w.put(f"{ART}/{e['id']}", json={"product_id": t.ids["hms"], "length_m": "40", "manufactured_on": ""})
        assert r.status_code == 200, r.get_json()
        assert artikel(w, e["id"])["length_m"] is None
    print("Nachbesserungen nach der Prüfung bestanden.")


def test_import_einheiten():
    """B5/V6: „Länge (cm)“ und andere Einheiten werden nicht als Meter gelesen (Hinweis, Bemerkung), „1.200“ ist
    mehrdeutig (Hinweis), „50 m“ und „50m“ sind Meter."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        from app.material.services import bestandsimport
        assert bestandsimport.erkennen("Länge (cm)")[0] == "laenge"
        assert [bestandsimport.laenge_einheit(x) for x in ("Länge (cm)", "Länge [mm]", "Länge in ft", "Länge (Fuß)",
                                                             "Länge in m", "Länge (m)", "Seillänge")] == \
            ["cm", "mm", "ft", "Fuß", None, None, None]
        daten = csv_bytes([["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Herstelldatum", "Länge (cm)"],
                           ["Testwerk", "Seil Gamma", "SG-1", "EH-1", "03/2024", "3000"]])
        z = nach_nr(ok(probelauf(t.w, t.lager, daten, "cm.csv")))
        assert any("in cm – bitte in Metern" in h for h in z[2]["hinweise"]), z[2]
        daten = csv_bytes([["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Herstelldatum", "Länge"],
                           ["Testwerk", "Seil Gamma", "SG-1", "EH-2", "03/2024", "1.200"],
                           ["Testwerk", "Seil Gamma", "SG-1", "EH-3", "03/2024", "50 m"],
                           ["Testwerk", "Seil Gamma", "SG-1", "EH-4", "03/2024", "50,5m"],
                           ["Testwerk", "Seil Gamma", "SG-1", "EH-5", "03/2024", "12 ft"]])
        z = nach_nr(ok(probelauf(t.w, t.lager, daten, "m.csv")))
        assert any("mehrdeutig" in h for h in z[2]["hinweise"]), z[2]
        assert not any("Länge" in h for h in z[3]["hinweise"] + z[4]["hinweise"]), (z[3], z[4])
        assert any("in ft" in h for h in z[5]["hinweise"]), z[5]
        b = ok(uebernehmen(t.w, t.lager, daten, "m.csv"), 201)
        assert b["import"]["angelegt"] == 4, b
        nach_serie = {r["serial_no"]: r for r in zeilen(t.app, "SELECT serial_no, length_m, notes FROM mat_item")}
        assert nach_serie["EH-2"]["length_m"] is None and "Länge laut Liste: 1.200" in nach_serie["EH-2"]["notes"]
        assert nach_serie["EH-3"]["length_m"] == 50.0 and nach_serie["EH-4"]["length_m"] == 50.5
        assert nach_serie["EH-5"]["length_m"] is None and "Länge laut Liste: 12 ft" in nach_serie["EH-5"]["notes"]
    print("Einheiten im Bestandsimport bestanden.")


# --- 7. Trennung -------------------------------------------------------------------------------------------------------

def test_trennung():
    """Fremde Artikel antworten wie unbekannte (404), auch beim Setzen einer Länge; die Länge eines fremden Artikels
    steht in keiner Antwort."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        fremd_gid, _ = gliederung(t.adm, "OG Nachbarstadt", standard=False)
        fremd = neuer_artikel(t.adm, t.seil, fremd_gid, manufactured_on=t.herst, serial_no="FR-1", length_m="40")
        unbekannt = t.w.put(f"{ART}/999999", json={"length_m": "41"})
        r = t.w.put(f"{ART}/{fremd['id']}", json={"length_m": "41"})
        assert r.status_code == unbekannt.status_code == 404 and r.get_json() == unbekannt.get_json(), r.get_json()
        assert t.w.get(f"{ART}/{fremd['id']}").status_code == 404
        assert zeilen(t.app, "SELECT length_m FROM mat_item WHERE id = ?", (fremd["id"],))[0]["length_m"] == 40.0
        assert "40,0" not in t.w.get(f"/materialablage/export/{t.lager}.csv").get_data(as_text=True)
    print("Trennung bestanden.")


if __name__ == "__main__":
    test_migration_20()
    test_haekchen_vererbt()
    test_katalogformat()
    test_artikel_laenge()
    test_csv_und_import()
    test_pruefung_laenge()
    test_nachbesserung_pruefung()
    test_import_einheiten()
    test_trennung()
    print("Alle Tests zur Artikellänge bestanden.")
