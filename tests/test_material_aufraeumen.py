"""Aufräumen – Schritt 37 und Reste entfernter Funktionen (Wunsch vom 04.11.2026):  python tests/test_material_aufraeumen.py
oder  pytest tests/test_material_aufraeumen.py

Grundlage: planung/aufraeumen/bestand.md (Bauentwurf, „Schritt 36“ dort = Schritt 37 hier) und auftrag_bau.md.
  - Schema frisch: keine der elf Spalten (models.SPALTEN_WEG_37), kein idx_mat_form_wiki, keine Wächter
    mat_item_kein_teil*; alles Übrige gleicht einem Lauf bis 36 (bis auf die Tabellen ohne die Spalten); was als
    Nachweis bleibt (mat_product.is_set, Set-Spalten der Bestandteil-Liste, mat_inspection.set_lauf_id, mat_set_*,
    mat_inspection_result.is_critical), steht da.
  - 36 → 37 mit Altbestand (Werte in allen elf Spalten, festgeschriebene Prüfung mit Protokoll, Journal, Antrag,
    Mangelmeldung, Produktmeldung): Zeilen, Kennungen, sqlite_sequence und alle übrigen Spalten gleich (Hash je Tabelle),
    Integrität, Fremdschlüssel, Volltext, Protokoll byteweise gleich (Prüfseite „unverändert“); Startprotokoll nennt je
    Spalte die Zahl der Zeilen mit Wert; zweiter Lauf und zweiter Start ändern nichts und legen mat_katalog nicht neu an;
    der Schutz festgeschriebener Prüfungen, der Stammdaten geprüfter Artikel und des Journals greift weiter.
  - SQLite < 3.35: Der Schritt läuft durch, die Spalten bleiben, das Startprotokoll sagt es.
  - Schnittstelle je Rolle: Produkt ohne wiki_page_id, Meldung ohne set_teile; Häkchen mat_katalog weiter 400;
    POST …/pruefungen/<id>/abschliessen und GET /api/wiki/watches antworten wie unbekannte Wege, …/festschreiben und
    PUT …/watch bleiben.
  - Statisch: rechte.urkunde_fehlt, die Übungsbilder im Wurzelordner, die Klassen komm-kopf/erg-kopf und „Teile laut
    Meldung“ sind weg; scripts/uebungsdateien.py legt ohne --ziel keine Bilder mehr ab.
Eine Sicherung aus Phase 1 mit mat_katalog = 1 (Schritt 10 macht daraus Verwaltung, danach fällt die Spalte) prüfen
test_material_stufen.test_migration_9_10 und test_material_trennung.test_migration_7_8. Alle Namen, Nummern und Texte hier
sind Platzhalter."""
import contextlib
import hashlib
import io
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, festschreiben, gliederung, jpeg, katalog_grund, mails_abfangen,  # noqa: E402
                           mails_zurueck, make_app, neuer_artikel, protokoll_zeile, pruef_formulare, starten, umgebung)
from test_material_trennung import bis_schritt, gleich_wie_unbekannt, sql, zeilen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "/api/material"
ENTFERNT = (("mat_form", "wiki_page_id"), ("mat_product", "wiki_page_id"), ("mat_folder", "owner_user_id"),
            ("mat_item", "parent_item_id"), ("mat_item", "lock_cause"), ("mat_item", "set_lock_origin"),
            ("mat_item", "set_pruefen"), ("mat_product_request", "is_set"), ("mat_product_request", "set_teile"),
            ("mat_checklist_item", "is_critical"), ("users", "mat_katalog"))
OBJEKTE_WEG = {("index", "idx_mat_form_wiki"), ("trigger", "mat_item_kein_teil"), ("trigger", "mat_item_kein_teil_aendern")}


def lies(rel):
    with open(os.path.join(WURZEL, rel), encoding="utf-8") as fh:
        return fh.read()


def _spalten(conn, tabelle):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]


def _schema(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return {(r[0], r[1]): " ".join((r[2] or "").split()) for r in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
    finally:
        conn.close()


def _tabellen(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                                       "ORDER BY name")]


def _hash(conn, tabelle, spalten):
    """Prüfsumme über alle Zeilen einer Tabelle (Kennung und die genannten Spalten)."""
    liste = ", ".join(f'"{s}"' for s in spalten)
    try:
        zeilen_ = conn.execute(f"SELECT rowid, {liste} FROM {tabelle} ORDER BY rowid").fetchall()
    except sqlite3.OperationalError:                     # ohne rowid (WITHOUT ROWID, manche virtuellen Tabellen)
        zeilen_ = sorted(conn.execute(f"SELECT {liste} FROM {tabelle}").fetchall(), key=repr)
    return hashlib.sha256(repr(zeilen_).encode()).hexdigest(), len(zeilen_)


def _bestand(conn, spalten_je_tabelle):
    """Prüfsumme und Zeilenzahl je Tabelle; mat_meta ohne die Schemaversion (sie zählt der Schritt hoch)."""
    out = {t: _hash(conn, t, s) for t, s in spalten_je_tabelle.items() if t != "mat_meta"}
    out["mat_meta"] = conn.execute("SELECT schluessel, wert FROM mat_meta WHERE schluessel <> 'schema_version' "
                                   "ORDER BY schluessel").fetchall()
    return out


@contextlib.contextmanager
def ohne_mails():
    """Mails von Antrag, Mangel und Meldung abfangen (verworfen) – echte Mails gehen ohnehin nie hinaus."""
    from app.material.services import antrag, mangel, meldung
    alt = [mails_abfangen(d, lambda an, betreff, text: True) for d in (antrag, mangel, meldung)]
    try:
        yield
    finally:
        for a in reversed(alt):
            mails_zurueck(a)


@contextlib.contextmanager
def startprotokoll():
    """Die Warnungen der Migration (models._NACH_DEM_FESTSCHREIBEN) mitschreiben."""
    out = []
    h = logging.Handler()
    h.emit = lambda r: out.append(r.getMessage())
    log = logging.getLogger("app.material.models")
    log.addHandler(h)
    try:
        yield out
    finally:
        log.removeHandler(h)


def _altbestand(tmp):
    """Auf Stand 36: Katalog, Gliederung mit Lager, Artikel A (festgeschrieben geprüft, mit Protokoll), B und C, eine
    Wiki-Seite, eine Produktmeldung, ein offener Antrag an A, eine Mangelmeldung an C. Danach Werte in allen elf
    Spalten, die Schritt 37 entfernt – an B (nicht geprüft) und am Formular, wie sie ein älterer Stand hinterließ;
    parent_item_id unter Umgehung des Wächters aus Schritt 26 (sonst gäbe es keinen Wert zu verlieren), mat_katalog wie
    die Zeile, die db.MIGRATIONS bis Schritt 37 anlegte."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    formulare = pruef_formulare(k["katalog"], ids)
    gid, _ = gliederung(k["wart"])
    a = neuer_artikel(k["wart"], ids["hms"], gid, serial_no="AUF-0001")["id"]
    b = neuer_artikel(k["wart"], ids["hms"], gid, serial_no="AUF-0002")["id"]
    c = neuer_artikel(k["wart"], ids["hms"], gid, serial_no="AUF-0003")["id"]
    r = starten(k["pruefer"], a)
    assert r.status_code == 201, r.get_json()
    pid = r.json["pruefung"]["id"]
    r = festschreiben(k["pruefer"], pid, ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()
    seite = k["adm"].post("/api/wiki/pages", json={"title": "Platzhalter Seite", "content": "Platzhalter"})
    assert seite.status_code == 201, seite.get_json()
    seite = seite.json["page"]["id"]
    r = k["wart"].post(f"{API}/meldungen", json={"manufacturer": "Testwerk", "model": "Platzhalter gemeldet",
                                                  "folder_id": gid})
    assert r.status_code == 201, r.get_json()
    mid = r.json["meldung"]["id"]
    r = k["wart"].post(f"{API}/artikel/{a}/antrag", headers=H, json={"serial_no": "AUF-0001-NEU",
                                                                      "begruendung": "Platzhalter Begründung"})
    assert r.status_code == 201, r.get_json()
    r = k["fuehrung"].post(f"{API}/artikel/{c}/mangel", headers=H, content_type="multipart/form-data",
                           data={"beschreibung": "Platzhalter Mangel", "fotos": [(jpeg(), "m.jpg")]})
    assert r.status_code == 201, r.get_json()
    # Werte in den Spalten, die Schritt 37 entfernt.
    sql(app, "UPDATE mat_form SET wiki_page_id = ? WHERE id = ?", (seite, formulare["karabiner"]))
    sql(app, "UPDATE mat_product SET wiki_page_id = ? WHERE id = ?", (seite, ids["hms"]))
    sql(app, "UPDATE mat_folder SET owner_user_id = ? WHERE id = ?", (k["wart_id"], gid))
    sql(app, "DROP TRIGGER mat_item_kein_teil_aendern")
    sql(app, "UPDATE mat_item SET parent_item_id = ?, lock_cause = 'eigen', set_lock_origin = 'teil', set_pruefen = 1 "
             "WHERE id = ?", (c, b))
    sql(app, "UPDATE mat_product_request SET is_set = 1, set_teile = 'Platzhalter Teil 1' WHERE id = ?", (mid,))
    sql(app, "UPDATE mat_checklist_item SET is_critical = 1 WHERE form_id = ?", (formulare["karabiner"],))
    sql(app, "ALTER TABLE users ADD COLUMN mat_katalog INTEGER NOT NULL DEFAULT 0")
    sql(app, "UPDATE users SET mat_katalog = 1 WHERE id = ?", (k["katalog_id"],))
    punkte = zeilen(app, "SELECT COUNT(*) AS n FROM mat_checklist_item WHERE form_id = ?", (formulare["karabiner"],))[0]["n"]
    return SimpleNamespace(app=app, k=k, ids=ids, gid=gid, a=a, b=b, c=c, pid=pid, seite=seite, mid=mid, punkte=punkte)


# --- Schema -------------------------------------------------------------------------------------------------------------

def test_frisch():
    """Frisch → Ende: die Spalten und drei Objekte fehlen, alles andere gleicht dem Stand 36."""
    from app.material import models
    assert models.SCHEMA_VERSION >= 37 and models.SPALTEN_WEG_37 == ENTFERNT
    with tempfile.TemporaryDirectory() as t36, tempfile.TemporaryDirectory() as t37:
        bis_schritt(36)(make_app, t36)
        bis_schritt(37)(make_app, t37)                     # seit Schritt 38 ist 37 nicht mehr das Ende
        s36, s37 = _schema(os.path.join(t36, "stroemis.db")), _schema(os.path.join(t37, "stroemis.db"))
        conn36, conn37 = sqlite3.connect(os.path.join(t36, "stroemis.db")), sqlite3.connect(os.path.join(t37, "stroemis.db"))
        try:
            # Stand 36 (frisch) hat mat_katalog nicht mehr (db.MIGRATIONS) – alle übrigen Spalten schon.
            for tabelle, spalte in ENTFERNT:
                assert spalte not in _spalten(conn37, tabelle), (tabelle, spalte)
                assert (spalte in _spalten(conn36, tabelle)) is (tabelle != "users"), (tabelle, spalte)
            assert set(s36) - set(s37) == OBJEKTE_WEG and not set(s37) - set(s36), (set(s36) ^ set(s37))
            geaendert = {k_ for k_ in s37 if s36[k_] != s37[k_]}
            assert geaendert == {("table", t) for t, _ in ENTFERNT if t != "users"}, geaendert
            for _, tabelle in geaendert:
                assert [s for s in _spalten(conn36, tabelle) if (tabelle, s) not in ENTFERNT] == _spalten(conn37, tabelle)
            # Was als Nachweis bzw. mit Schutz-Triggern bleibt.
            assert "is_set" in _spalten(conn37, "mat_product")
            assert {"einzeln", "component_product_id", "austausch"} <= set(_spalten(conn37, "mat_product_component"))
            assert "set_lauf_id" in _spalten(conn37, "mat_inspection")
            assert "is_critical" in _spalten(conn37, "mat_inspection_result")
            for objekt in (("table", "mat_set_lauf"), ("table", "mat_set_protokoll_zeile"),
                           ("index", "idx_mat_inspection_set_lauf"), ("trigger", "mat_result_aendern"),
                           ("trigger", "mat_teilnummer_position"), ("trigger", "mat_product_kein_set"),
                           ("trigger", "mat_inspection_festgeschrieben")):
                assert objekt in s37, objekt
            assert "is_critical" in s37[("trigger", "mat_result_aendern")]
            assert conn37.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn37.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn36.close()
            conn37.close()
    print("Frisch bestanden.")


def test_altbestand_36_37():
    """36 → 37 mit Werten in allen elf Spalten: nur die Spalten gehen, alles andere bleibt; Startprotokoll, zweiter Lauf,
    zweiter Start, Schutz."""
    from app.material import models
    with ohne_mails(), tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(36)(_altbestand, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "36"
        bleibt = {tb: [s for s in _spalten(conn, tb) if (tb, s) not in ENTFERNT] for tb in _tabellen(conn)}
        vorher = _bestand(conn, bleibt)
        seq = conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        schema36 = _schema(pfad)
        # Es gibt etwas zu verlieren – in jeder Spalte mindestens eine Zeile.
        werte = {(tb, s): conn.execute(f"SELECT COUNT(*) FROM {tb} WHERE {s} IS NOT NULL AND {s} NOT IN (0, '')"
                                       ).fetchone()[0] for tb, s in ENTFERNT}
        assert all(werte.values()), werte
        assert werte[("mat_checklist_item", "is_critical")] == t.punkte
        conn.close()
        pdf_pfad = protokoll_zeile(t.app, t.pid)["pdf_path"]
        with open(os.path.join(tmp, pdf_pfad), "rb") as fh:
            original = fh.read()

        with startprotokoll() as protokoll:
            app = bis_schritt(37)(make_app, tmp)               # seit Schritt 38 ist 37 nicht mehr das Ende
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == "37"
        for (tb, s), n in werte.items():
            assert f"Schritt 37 (Materialablage): Spalte {tb}.{s} entfernt – {n} Zeile(n) trugen einen Wert." in protokoll, \
                (tb, s, protokoll)
        conn = sqlite3.connect(pfad)
        try:
            for tb, s in ENTFERNT:
                assert s not in _spalten(conn, tb), (tb, s)
            nachher = _bestand(conn, bleibt)
            assert nachher == vorher, {tb: (vorher[tb], nachher[tb]) for tb in vorher if vorher[tb] != nachher[tb]}
            assert conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall() == seq
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            if conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'volltext'").fetchone()[0] == "1":
                for fts in ("mat_product_fts", "mat_item_fts"):
                    conn.execute(f"INSERT INTO {fts}({fts}) VALUES ('integrity-check')")
            schema37 = _schema(pfad)
            # Der Wächter mat_item_kein_teil_aendern fehlte schon (Altbestand oben), die anderen beiden nimmt der Schritt.
            assert set(schema36) - set(schema37) == OBJEKTE_WEG - {("trigger", "mat_item_kein_teil_aendern")}
            assert not set(schema37) - set(schema36)
            # Zweiter Lauf: nichts ändert sich (auch Schritt 37 für sich nicht).
            assert bis_schritt(37)(models.migrieren, conn) == 37
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_37(conn)
            assert conn.total_changes == n
            conn.rollback()
            assert _schema(pfad) == schema37
        finally:
            conn.close()
        # Zweiter Start: legt mat_katalog nicht neu an, ändert nichts.
        with startprotokoll() as protokoll:
            app = bis_schritt(37)(make_app, tmp)
        assert not [z for z in protokoll if "Schritt 37" in z], protokoll
        conn = sqlite3.connect(pfad)
        try:
            assert "mat_katalog" not in _spalten(conn, "users")
            assert _schema(pfad) == schema37 and _bestand(conn, bleibt) == vorher
        finally:
            conn.close()
        # Protokoll: unverändert auf der Platte und auf der Prüfseite.
        with open(os.path.join(tmp, pdf_pfad), "rb") as fh:
            assert fh.read() == original
        r = app.test_client().post(f"{API}/pruefen", data={"datei": (io.BytesIO(original), "protokoll.pdf")}, headers=H,
                                   content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["ergebnis"] == "unveraendert", r.json
        # Schutz greift weiter: festgeschriebene Prüfung samt Befundzeilen, Stammdaten des geprüften Artikels, Journal,
        # Mangelmeldung.
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_defect_report WHERE item_id = ?", (t.c,))[0]["n"] == 1
        conn = sqlite3.connect(pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA recursive_triggers = ON")
        try:
            for befehl, args in (("UPDATE mat_inspection SET remarks = 'geändert' WHERE id = ?", (t.pid,)),
                                 ("UPDATE mat_inspection_result SET is_critical = 1 WHERE inspection_id = ?", (t.pid,)),
                                 ("DELETE FROM mat_inspection WHERE id = ?", (t.pid,)),
                                 ("UPDATE mat_item SET serial_no = 'AUF-ANDERS' WHERE id = ?", (t.a,)),
                                 ("DELETE FROM mat_audit WHERE id = (SELECT MIN(id) FROM mat_audit)", ()),
                                 ("DELETE FROM mat_defect_report WHERE item_id = ?", (t.c,)),
                                 ("UPDATE mat_audit SET action = 'x' WHERE id = (SELECT MIN(id) FROM mat_audit)", ())):
                try:
                    conn.execute(befehl, args)
                    raise AssertionError(f"nicht abgewiesen: {befehl}")
                except sqlite3.IntegrityError:
                    conn.rollback()
        finally:
            conn.close()
        # Die App arbeitet mit dem Bestand: Artikel, Produkt, Formular, Meldung, Antrag, Prüfung.
        k = t.k
        for iid in (t.a, t.b, t.c):
            r = k["wart"].get(f"{API}/artikel/{iid}")
            assert r.status_code == 200, r.get_json()
        assert k["katalog"].get(f"{API}/produkte/{t.ids['hms']}").status_code == 200
        assert k["katalog"].get(f"{API}/meldungen?status=alle").status_code == 200
        assert k["wart"].get(f"{API}/antraege").status_code == 200
        r = starten(k["pruefer"], t.b)
        assert r.status_code == 201, r.get_json()
        assert festschreiben(k["pruefer"], r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
    print("Altbestand 36 → 37 bestanden.")


def test_sqlite_alt():
    """SQLite < 3.35 kennt kein DROP COLUMN: Schritt 37 läuft durch (Version 37), die Spalten bleiben stehen."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(36)(make_app, tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        alt = sqlite3.sqlite_version_info
        sqlite3.sqlite_version_info = (3, 34, 1)
        try:
            with startprotokoll() as protokoll:
                assert models.migrieren(conn) == models.SCHEMA_VERSION
        finally:
            sqlite3.sqlite_version_info = alt
        try:
            assert "wiki_page_id" in _spalten(conn, "mat_form") and "is_critical" in _spalten(conn, "mat_checklist_item")
            assert any("kennt kein DROP COLUMN" in z for z in protokoll), protokoll
        finally:
            conn.close()
    print("SQLite vor 3.35 bestanden.")


# --- Schnittstelle --------------------------------------------------------------------------------------------------

def test_schnittstelle():
    with ohne_mails(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["wart"])
        # Produkt-JSON je Rolle ohne wiki_page_id (Verwaltung, Material-Verwaltung, Materialwart, Prüfer, Mitglied).
        for rolle in ("adm", "katalog", "wart", "pruefer", "fuehrung"):
            r = k[rolle].get(f"{API}/produkte/{ids['hms']}")
            assert r.status_code == 200 and "wiki_page_id" not in r.json["produkt"], (rolle, r.status_code)
            r = k[rolle].get(f"{API}/produkte", query_string={"kategorie_id": ids["karabiner"]})
            assert r.status_code == 200 and "wiki_page_id" not in r.get_data(as_text=True), rolle
        # Meldung ohne set_teile – auch wenn eine Anfrage es mitschickt.
        r = k["wart"].post(f"{API}/meldungen", json={"manufacturer": "Testwerk", "model": "Platzhalter neu",
                                                     "folder_id": gid, "is_set": True, "set_teile": "x"})
        assert r.status_code == 201 and not {"set_teile", "is_set"} & set(r.json["meldung"]), r.get_json()
        for rolle in ("katalog", "wart"):
            text = k[rolle].get(f"{API}/meldungen?status=alle").get_data(as_text=True)
            assert "set_teile" not in text, rolle
        # Nutzerverwaltung: das Häkchen „Produktkatalogpfleger“ bleibt eine klare Absage.
        r = k["adm"].put(f"/api/admin/users/{k['nutzer_id']}", json={"mat_katalog": True})
        assert r.status_code == 400 and "Verwaltung" in r.json["error"], r.get_json()
        assert "mat_katalog" not in k["adm"].get("/api/admin/users").get_data(as_text=True)
        # Der alte Pfad …/abschliessen ist weg (wie ein unbekannter Weg), …/festschreiben bleibt.
        a = neuer_artikel(k["wart"], ids["hms"], gid)["id"]
        pid = starten(k["pruefer"], a).json["pruefung"]["id"]
        gleich_wie_unbekannt(k["pruefer"].post(f"{API}/pruefungen/{pid}/abschliessen", json={"ergebnis": "einsatzbereit"}),
                             k["pruefer"].post(f"{API}/pruefungen/{pid}/gibtesnicht", json={"ergebnis": "einsatzbereit"}))
        assert festschreiben(k["pruefer"], pid, ergebnis="einsatzbereit").status_code == 200
        assert not [r_.rule for r_ in app.url_map.iter_rules() if r_.rule.endswith("/abschliessen")
                    and "/pruefungen/" in r_.rule]
        # Wiki: die Liste der beobachteten Seiten ist weg, Beobachten selbst bleibt.
        seite = k["adm"].post("/api/wiki/pages", json={"title": "Platzhalter beobachtet", "content": "x"}).json["page"]
        assert k["adm"].put(f"/api/wiki/pages/{seite['id']}/watch", json={"watch": True}).json["watch"] is True
        assert k["adm"].get(f"/api/wiki/pages/{seite['slug']}").json["page"]["watch"] is True
        alt, unbekannt = k["adm"].get("/api/wiki/watches"), k["adm"].get("/api/wiki/gibtesnicht")
        assert alt.status_code == unbekannt.status_code == 404 and alt.get_data() == unbekannt.get_data()
    print("Schnittstelle bestanden.")


# --- Statisch -----------------------------------------------------------------------------------------------------------

def test_statisch():
    from app import db
    from app.material.services import rechte
    assert not hasattr(rechte, "urkunde_fehlt")
    assert not [m for m in db.MIGRATIONS if m[1] == "mat_katalog"]
    assert not [m for m in db.OBSOLETE_COLUMNS if m[1] == "mat_katalog"]       # nicht vor Schritt 10 einer Sicherung
    uebung = os.path.join(WURZEL, "app", "static", "uebung")
    assert not [d for d in os.listdir(uebung) if d.endswith(".jpg")], os.listdir(uebung)
    assert os.path.isfile(os.path.join(uebung, "uebungsdatei.pdf"))
    for n in (1, 2, 3):
        assert os.path.isfile(os.path.join(uebung, "karte", f"uebungsbild-{n}.jpg"))
    for pfad in ("app/static/css/pruefungen.css", "app/static/js/pruefungen.js"):
        assert "komm-kopf" not in lies(pfad) and "erg-kopf" not in lies(pfad), pfad
    js = lies("app/material/static/material.js")
    assert "Teile laut Meldung" not in js and "m.set_teile" not in js
    assert "wiki_page_id" not in lies("app/static/js/uebung/material.js")
    assert "wiki_page_id" not in lies("app/material/services/katalog.py")
    assert '"set_teile"]' not in lies("app/material/services/meldung.py")
    assert "/abschliessen\")" not in lies("app/material/routes.py").split("def pruefung_abschliessen")[0][-200:]
    assert '@bp.get("/watches")' not in lies("app/api_wiki.py")
    # Die Journal-Beschriftungen alter Einträge bleiben (beschriftung.py und material.js).
    from app.material.services import beschriftung
    assert beschriftung.FELD["mat_katalog"] == "Katalogpfleger" and beschriftung.FELD["set_teile"] == "Teile des Sets"
    assert 'mat_katalog: "Katalogpfleger"' in js and 'set_teile: "Teile des Sets"' in js
    print("Statisch bestanden.")


def test_uebungsdateien_skript():
    """Ohne --ziel nur die Übungsdatei (keine Bilder im Wurzelordner); Bilder nur mit --ziel."""
    skript = os.path.join(WURZEL, "scripts", "uebungsdateien.py")
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-S", skript, "--von", "1", "--bis", "1"], capture_output=True, text=True,
                           timeout=60, env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
        assert r.returncode == 2 and "--ziel" in r.stderr, (r.returncode, r.stderr)
        r = subprocess.run([sys.executable, "-S", skript, "--ziel", tmp, "--von", "2", "--bis", "2", "--ohne-pdf"],
                           capture_output=True, text=True, timeout=60, env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
        assert r.returncode == 0, r.stderr
        assert os.listdir(tmp) == ["uebungsbild-2.jpg"], os.listdir(tmp)
    print("Übungsdateien-Skript bestanden.")


if __name__ == "__main__":
    test_frisch()
    test_altbestand_36_37()
    test_sqlite_alt()
    test_schnittstelle()
    test_statisch()
    test_uebungsdateien_skript()
    print("Alle Tests zum Aufräumen (Schritt 37) bestanden.")
