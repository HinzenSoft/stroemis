"""Modulstufe im Modul Material (Phase 2 · Lieferung 1, Nachbesserung vom 18.10.2026):  python tests/test_material_stufen.py

Die Stufe der Nutzerverwaltung (users.recht_material) wirkt wieder: Mitglied = Modulzugang (Katalog, Suche, Profil –
Bestand nur über Freigaben je Ordner), Verwaltung = Material-Verwaltung (Produktkatalog, alle Bestände, Gliederungen,
jede Freigabe – prüfen nur mit Häkchen, Urkundennummer und Prüffreigabe). Ohne Stufe wirken weder Freigaben noch das
Häkchen „Prüfer“. Migration Schritt 10, Vorgabe neuer Konten (nur Material „Mitglied“), Personensuche je Zweck, Mails an
die Material-Verwaltung. Alle Namen, Nummern und Konten hier sind erfunden und nur für den Test da."""
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, abschluss, anmelden, freigeben, gliederung, jpeg, katalog_grund,  # noqa: E402
                           make_app, neuer_artikel, neues_konto, pruef_formulare, starten, umgebung, unterschreiben)
from test_material_rueckruf import post_abfangen, post_zurueck  # noqa: E402
from test_material_trennung import endversion, gleich_wie_unbekannt, sql, trennung_aufbau, zeilen  # noqa: E402
from test_material_ueberblick import MULTIPART, _stand, _url, ohne_post, ordner_neu  # noqa: E402
from test_material_zuordnung import post_der_meldungen  # noqa: E402

ZU = "/api/material/artikel/{}/zuordnung"
RR = "/api/material/produkte/{}/rueckrufe"


def _konto_sql(app, mail, name="", **spalten):
    """Ein Konto direkt in der Datenbank (wie es eine ältere Datenbank hinterlassen hat) – Passwort „passwort1“."""
    from werkzeug.security import generate_password_hash
    werte = dict({"email": mail, "password_hash": generate_password_hash("passwort1"), "name": name,
                  "created_at": "2026-10-01T00:00:00+00:00"}, **spalten)
    with app.app_context():
        from app import db
        return db.execute(f"INSERT INTO users ({', '.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                          tuple(werte.values()))


# --- Migration Schritt 10 ----------------------------------------------------------------------------------------

def test_migration_9_10():
    """Eine Datenbank im Stand von Schritt 9 (Stufen aus Phase 1 in recht_material, Katalog-Häkchen, Freigaben aus
    Schritt 8): Schritt 10 setzt die Stufe – 2 für bisherige Katalogpfleger und die Plattform-Verwaltung, 1 für eine
    Stufe aus Phase 1 (auch den Materialwart mit 2), eine Freigabe (auch abgelaufen) oder das Häkchen Prüfer, sonst 0.
    Name, Aktivität und Status zählen nicht. mat_katalog und mat_pruefer bleiben. Je geänderter Stufe und je
    aufgelöstem Katalog-Häkchen ein Journaleintrag „rollen“ am Konto, das Konto nur als Verweis. Ein zweiter Start und
    ein direkter zweiter Aufruf ändern nichts."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        r = adm.post("/api/material/ordner", json={"name": "OG Migration", "kind": "gliederung"})
        assert r.status_code == 201, r.get_json()
        gid = r.json["ordner"]["id"]
        gestern = (_heute() - timedelta(days=1)).isoformat()
        faelle = {  # Name: (Spalten, Freigabe (Recht, bis) oder None, Stufe nach Schritt 10, Journal?)
            "phase1_mitglied": ({"recht_material": 1}, ("lesen", None), 1, False),
            "phase1_wart": ({"recht_material": 2}, ("verwalten", None), 1, True),
            "katalog_1": ({"recht_material": 1, "mat_katalog": 1}, ("lesen", None), 2, True),
            "katalog_0": ({"mat_katalog": 1}, None, 2, True),
            "haekchen": ({"mat_pruefer": 1, "urkundennummer": "1012-1010"}, None, 1, True),
            "freigabe": ({}, ("lesen", None), 1, True),
            "abgelaufen": ({}, ("lesen", gestern), 1, True),
            "nichts": ({}, None, 0, False),
            "pv": ({"recht_verwaltung": 2, "recht_material": 2}, None, 2, False),
            "pv_ohne": ({"recht_verwaltung": 2, "recht_material": 0}, None, 2, True),
            "ohne_namen": ({"name": ""}, ("lesen", None), 1, True),
            "deaktiviert": ({"recht_material": 1, "active": 0}, None, 1, False),
            "wartend": ({"status": "pending", "active": 0}, None, 0, False),
        }
        ids = {}
        for n, (spalten, freigabe, _, _) in faelle.items():
            spalten = dict({"name": f"Test {n}", "recht_material": 0}, **spalten)
            ids[n] = _konto_sql(app, f"{n}@example.org", **spalten)
            if freigabe:
                freigeben(adm, gid, ids[n], freigabe[0], bis=freigabe[1])
        admin_id = zeilen(app, "SELECT id FROM users WHERE email = 'admin@example.org'")[0]["id"]
        # Stand 9: Die Schemaversion zurück, kein Eintrag von Schritt 10, Kontoverweise nur teilweise.
        sql(app, "UPDATE mat_meta SET wert = '9' WHERE schluessel = 'schema_version'")
        sql(app, "UPDATE users SET mat_ref = NULL WHERE email LIKE 'katalog%' OR email LIKE 'phase1%'")
        vorher = {u["id"]: u for u in zeilen(app, "SELECT * FROM users")}
        journal_vorher = zeilen(app, "SELECT MAX(id) AS m FROM mat_audit")[0]["m"] or 0

        app = make_app(tmp)                                    # Neustart: Schritt 10 läuft
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        nachher = {u["id"]: u for u in zeilen(app, "SELECT * FROM users")}
        assert {n: nachher[ids[n]]["recht_material"] for n in faelle} == {n: f[2] for n, f in faelle.items()}
        assert nachher[admin_id]["recht_material"] == 2
        # Nur die Stufe ändert sich: Häkchen, mat_katalog, Urkundennummer, Name, Aktivität bleiben.
        for uid, u in nachher.items():
            assert {k_: v for k_, v in u.items() if k_ not in ("recht_material", "mat_ref")} == \
                {k_: v for k_, v in vorher[uid].items() if k_ not in ("recht_material", "mat_ref")}, u
        # Journal: je Konto mit geänderter Stufe oder aufgelöstem Katalog-Häkchen genau ein Eintrag – ohne E-Mail und
        # ohne Namen, das Konto als Verweis; keiner für 2 → 2, 1 → 1 und 0 → 0.
        e = zeilen(app, "SELECT * FROM mat_audit WHERE id > ? ORDER BY id", (journal_vorher,))
        assert all((x["entity"], x["action"], x["user_id"], x["user_name"]) == ("user", "rollen", None,
                                                                                "Migration Schritt 10") for x in e), e
        assert sorted(x["entity_id"] for x in e) == sorted(ids[n] for n, f in faelle.items() if f[3]), e
        for x in e:
            n = next(n for n, uid in ids.items() if uid == x["entity_id"])
            v, nach = json.loads(x["before_json"]), json.loads(x["after_json"])
            alt = dict({"recht_material": 0}, **faelle[n][0]).get("recht_material", 0)
            assert v == dict({"recht_material": alt}, **({"mat_katalog": 1} if "katalog" in n else {})), (n, v)
            assert nach == {"recht_material": faelle[n][2], "konto": {"ref": nachher[x["entity_id"]]["mat_ref"]},
                            "grund": "Modulstufe Material (Schritt 10)"}, (n, nach)
            assert len(nach["konto"]["ref"]) == 32
            assert "@" not in x["before_json"] + x["after_json"] and "Test " not in x["after_json"]

        # Wirkung: der bisherige Katalogpfleger ist Material-Verwaltung (alles, Katalog, Gliederungen); der Materialwart
        # aus Phase 1 verwaltet weiter nur über seine Freigabe; ohne Namen und ohne alles kein Zugang.
        kp = anmelden(app, "katalog_1@example.org", "passwort1")
        d = kp.get("/api/material/start").json["darf"]
        assert d["alles"] and d["katalog"] and d["gliederung_anlegen"] and not d["pruefen"], d
        wart = anmelden(app, "phase1_wart@example.org", "passwort1")
        d = wart.get("/api/material/start").json["darf"]
        assert d["verwalten"] and not d["alles"] and not d["katalog"], d
        assert wart.post("/api/material/ordner", json={"name": "OG Eigen", "kind": "gliederung"}).status_code == 403
        r = anmelden(app, "ohne_namen@example.org", "passwort1").get("/api/material/start")
        assert r.status_code == 403 and "Namen" in r.json["error"], r.get_json()
        r = anmelden(app, "nichts@example.org", "passwort1").get("/api/material/start")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        # Ohne Namen und ohne Stufe: zuerst die Stufe – der Name allein hülfe nicht (sonst zwei Runden).
        sql(app, "UPDATE users SET name = '' WHERE email = 'nichts@example.org'")
        r = anmelden(app, "nichts@example.org", "passwort1").get("/api/material/start")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        sql(app, "UPDATE users SET name = 'Test nichts' WHERE email = 'nichts@example.org'")
        r = anmelden(app, "abgelaufen@example.org", "passwort1").get("/api/material/start")
        assert r.status_code == 200 and not r.json["darf"]["lesen"], r.get_json()     # Zugang, kein Bestand

        # Ein zweiter Start ändert nichts – und Schritt 10 selbst ist wiederholbar.
        def stand():
            return {t: zeilen(app, f"SELECT * FROM {t} ORDER BY rowid") for t in ("users", "mat_audit", "mat_folder_grant")}
        vorher = stand()
        app = make_app(tmp)
        assert stand() == vorher
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_10(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
    print("Migration 9 → 10 bestanden.")


def test_migration_produktion():
    """Eine Datenbank ohne Modul Material (wie main): Die Spalte recht_material entsteht mit der Plattform-Verwaltung
    auf 2, alle anderen 0 – Schritt 10 ändert daran nichts und schreibt nichts ins Journal."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        alt = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        alt.executescript(db_mod.SCHEMA)
        for mail, verwaltung in (("admin@example.org", 2), ("mitglied@example.org", 0), ("gast@example.org", 0)):
            alt.execute("INSERT INTO users (email, password_hash, name, recht_verwaltung, created_at) VALUES (?,?,?,?,?)",
                        (mail, "x", mail.split("@")[0], verwaltung, "2026-01-01T00:00:00"))
        alt.commit()
        alt.close()
        app = make_app(tmp)
        stufen = {u["email"]: u["recht_material"] for u in zeilen(app, "SELECT email, recht_material FROM users")}
        assert stufen == {"admin@example.org": 2, "mitglied@example.org": 0, "gast@example.org": 0}, stufen
        assert not zeilen(app, "SELECT 1 FROM mat_audit WHERE user_name = 'Migration Schritt 10'")
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
    print("Migration ohne Modul (Produktion) bestanden.")


# --- Zugang: ohne Stufe wirkt nichts -------------------------------------------------------------------------------

# Routen, die ein Konto ohne Stufe nicht mit 403 beantworten – und warum.
OHNE_STUFE_ERLAUBT = {
    "material.static": 200,                      # die Skripte des Moduls (keine Daten)
    "material.pruefseite": 200,                  # die Prüfseite für Protokolle ist öffentlich
    ("POST", "material_api.pruefen"): 400,       # ebenso ihre Schnittstelle (ohne Datei: 400)
    "material_api.meine_freigaben": 200,         # „Meine Freigaben“ – sagt, warum keine wirkt
    "material_api.unterschrift_lesen": 200,      # die eigene Unterschrift – im Profil nur zum Entfernen
    ("DELETE", "material_api.unterschrift_entfernen"): 200,   # seine Daten (hier ist keine da)
    # Die eigene Meldung löschen darf der Melder auch ohne Stufe (test_meldung_ohne_stufe) – eine fremde antwortet wie
    # eine unbekannte.
    ("DELETE", "material_api.meldung_loeschen"): 404,
    # „Meine PSA“ (Phase 3 · L1) für jedes aktive Konto mit Namen: die Seite und die Liste öffnen sich (hier leer), ein
    # Artikel, der nicht zugeordnet ist, antwortet wie ein unbekannter; die eigene Einstellung ohne „an“ 400. Mangel
    # melden ohne Stufe nur an der eigenen PSA – sonst 403 „nicht freigeschaltet“ wie jede Route.
    "material.meine_psa": 200,
    "material.meine_psa_artikel": 404,
    "material_api.psa_liste": 200,
    ("PUT", "material_api.psa_mails"): 400,
}


# Gehören zur Nutzerverwaltung (Plattform-Verwaltung) – 403 mit eigenem Text, unabhängig von der Stufe.
NUR_PLATTFORM_VERWALTUNG = {"material_api.konto_freigaben", "material_api.globalsuche_protokoll"}


def test_ohne_stufe_rundum():
    """Ein Konto mit Verwalter- und Prüffreigabe in B, Häkchen und Urkundennummer, aber ohne Stufe im Modul Material:
    Jede Route der Material-Blueprints (über app.url_map) antwortet 403 – vor jeder Frage nach dem Gegenstand –, außer
    den wenigen in OHNE_STUFE_ERLAUBT; nichts ändert sich. Kein Reiter, Seiten und Medien 403. Mit Stufe Mitglied
    wirken dieselben Freigaben sofort."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t, b = trennung_aufbau(tmp)
        app, ids = t.app, t.ids
        c, uid = neues_konto(app, "stufenlos@example.org", name="Stufenlos Test", stufe=0, mat_pruefer=True,
                             urkundennummer="1012-5555")
        freigeben(t.adm, t.b, uid, "verwalten")
        freigeben(t.adm, t.b, uid, "pruefen")
        form = zeilen(app, "SELECT id FROM mat_form ORDER BY id LIMIT 1")[0]["id"]
        kennungen = {"iid": t.art_b["id"], "mid": b.meldung, "aid": b.anhang_id, "token": b.token, "gid": b.freigabe,
                     "kid": ids["karabiner"], "did": 999999, "ruid": 999999, "anid": 999999, "mfid": 999999,
                     "filename": "material.js",
                     "art": "web", "dateiname": b.ordnerfoto[0].rsplit("/", 1)[1],
                     "jahr": _heute().year,                 # Jahresbericht (P4-L1) über („ordner“/„export“, fid)
                     ("produkte", "pid"): ids["hms"], ("produkt", "pid"): ids["hms"],
                     ("pruefungen", "pid"): t.entwurf_b, ("pruefung", "pid"): t.entwurf_b, ("punkte", "rid"): b.punkt,
                     ("ordner", "fid"): t.lager_b, ("export", "fid"): t.lager_b, ("formulare", "fid"): form,
                     ("formular", "fid"): form, ("durchgaenge", "rid"): t.durchgang_b, ("durchgang", "rid"): t.durchgang_b,
                     ("import", "kennung"): "0" * 32}       # Katalogimport im Hintergrund (24.10.2026)
        regeln = [r for r in app.url_map.iter_rules() if r.endpoint.split(".")[0] in ("material", "material_api")]
        vorher = _stand(app)
        gezaehlt = 0
        for regel in regeln:
            url = _url(regel, kennungen)
            for methode in sorted(regel.methods - {"HEAD", "OPTIONS"}):
                if methode == "GET":
                    r = c.get(url)
                elif regel.endpoint in MULTIPART:
                    r = c.open(url, method=methode, headers=H, content_type="multipart/form-data",
                               data={"file": (jpeg(), "x.jpg"), "titel": "x"})
                else:
                    r = c.open(url, method=methode, headers=H, json={})
                soll = OHNE_STUFE_ERLAUBT.get((methode, regel.endpoint), OHNE_STUFE_ERLAUBT.get(regel.endpoint, 403))
                assert r.status_code == soll, (methode, url, r.status_code, r.get_json(silent=True))
                if soll == 403 and r.is_json and regel.endpoint not in NUR_PLATTFORM_VERWALTUNG:
                    assert "nicht freigeschaltet" in r.json["error"], (methode, url, r.get_json())
                gezaehlt += 1
        assert gezaehlt >= 120, gezaehlt
        assert _stand(app) == vorher, "Ein Konto ohne Stufe hat etwas geändert."
        # Medien aus B (Ordnerfoto) und die Seiten: 403; kein Reiter in der Kopfleiste.
        for url in b.ordnerfoto + ["/material", f"/material/ordner/{t.lager_b}", f"/m/{b.token}"]:
            assert c.get(url).status_code == 403, url
        assert 'href="/material"' not in c.get("/profil").get_data(as_text=True)
        assert c.get("/api/me").json["user"]["rechte"]["material"] == 0
        # „Meine Freigaben“ und die Liste am Ordner sagen, warum nichts wirkt.
        m = c.get("/api/material/freigaben/meine").json
        assert not m["zugang"] and {f["wirkt_nicht"] for f in m["freigaben"]} == {"kein Zugang zum Modul Material"}, m
        liste = t.wart_b.get(f"/api/material/ordner/{t.b}/freigaben").json["direkt"]
        z = [f for f in liste if f["konto"]["id"] == uid]
        assert {(f["recht"], f["wirkt"], f["wirkt_nicht"]) for f in z} == {
            ("verwalten", False, "kein Zugang zum Modul Material"), ("pruefen", False, "kein Zugang zum Modul Material")}
        # Mit Stufe Mitglied wirken dieselben Freigaben sofort – Verwalten und Prüfen in B.
        assert t.adm.put(f"/api/admin/users/{uid}", json={"rechte": {"material": 1}}).status_code == 200
        d = c.get("/api/material/start").json["darf"]
        assert d["verwalten"] and d["pruefen"] and d["qualifiziert"] and not d["alles"], d
        assert c.get(f"/api/material/ordner/{t.lager_b}").status_code == 200
        assert 'href="/material"' in c.get("/profil").get_data(as_text=True)
    print("Ohne Stufe rundum bestanden.")


# --- Mitglied, Material-Verwaltung ------------------------------------------------------------------------------

def test_mitglied_und_material_verwaltung():
    """Mitglied ohne Freigabe: Katalog lesen, Suche, keine Bestände, Katalog pflegen 403, keine Gliederung. Die
    Material-Verwaltung ohne Plattform-Verwaltung: sieht alle Bestände, pflegt den Katalog, legt Gliederungen und
    Rückrufe an, vergibt Freigaben überall (mit Notiz) – aber Nutzerverwaltung und Protokoll der globalen Suchen bleiben
    der Plattform-Verwaltung, und prüfen kann sie nur mit Häkchen, Urkundennummer und eigener Prüffreigabe."""
    pa = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            adm, mv = k["adm"], k["katalog"]
            ids = katalog_grund(adm)
            pruef_formulare(mv, ids)
            gid, _ = gliederung(adm)
            lager = ordner_neu(k["wart"], gid, "Lager")
            art = neuer_artikel(k["wart"], ids["hms"], lager, serial_no="ST-0001")["id"]
            mg, mg_id = neues_konto(app, "mitglied@example.org", name="Mitglied Test")
            r = mg.get("/api/material/start")
            assert r.status_code == 200 and r.json["bestand"] == 0, r.get_json()
            assert not any(v for x, v in r.json["darf"].items() if x in ("lesen", "verwalten", "pruefen", "katalog", "alles"))
            assert mg.get("/api/material/kategorien").status_code == 200
            assert mg.get(f"/api/material/produkte/{ids['hms']}").status_code == 200
            assert mg.get("/api/material/suche", query_string={"q": "ST-0001"}).json["gesamt"] == 0
            assert mg.get("/api/material/ordner").json["ordner"] == []
            gleich_wie_unbekannt(mg.get(f"/api/material/artikel/{art}"), mg.get("/api/material/artikel/999999"))
            r = mg.post("/api/material/kategorien", json={"name": "Neue Kategorie"})
            assert r.status_code == 403 and "Material-Verwaltung" in r.json["error"], r.get_json()
            r = mg.post("/api/material/ordner", json={"name": "OG Eigen", "kind": "gliederung"})
            assert r.status_code == 403 and "Material-Verwaltung" in r.json["error"], r.get_json()
            assert mg.post(RR.format(ids["hms"]), json={"title": "x"}).status_code == 403

            # Material-Verwaltung ohne Plattform-Verwaltung.
            assert zeilen(app, "SELECT recht_verwaltung FROM users WHERE id = ?", (k["katalog_id"],))[0][
                "recht_verwaltung"] == 0
            sql(app, "DELETE FROM mat_folder_grant WHERE user_id = ?", (k["katalog_id"],))   # ganz ohne Freigabe
            assert mv.get(f"/api/material/artikel/{art}").status_code == 200
            assert mv.get("/api/material/suche", query_string={"q": "ST-0001"}).json["gesamt"] == 1
            assert mv.post("/api/material/kategorien", json={"name": "Neue Kategorie"}).status_code == 201
            r = mv.post("/api/material/ordner", json={"name": "OG Neu", "kind": "gliederung"})
            assert r.status_code == 201, r.get_json()
            neu = r.json["ordner"]["id"]
            # Den ersten Materialwart der neuen Gliederung setzt sie selbst ein – an ein Mitglied, mit Notiz.
            r = mv.post(f"/api/material/ordner/{neu}/freigaben", json={"user_id": mg_id, "grundrecht": "verwalten",
                                                                         "notiz": "erster Materialwart"})
            assert r.status_code == 201 and r.json["liste"]["direkt"][0]["notiz"] == "erster Materialwart", r.get_json()
            assert mg.get("/api/material/start").json["darf"]["verwalten"]
            assert mg.post(f"/api/material/ordner/{neu}/freigaben",
                           json={"user_id": k["fuehrung_id"], "grundrecht": "lesen"}).status_code == 201
            r = mv.post(RR.format(ids["hms"]), json={"title": "Testrückruf", "mail": False})
            assert r.status_code == 201 and r.json["betroffen"] == 1 and "empfaenger" in r.json, r.get_json()
            assert mv.get("/api/admin/users").status_code == 403 and mv.get("/admin").status_code == 403
            assert mv.get("/api/material/globalsuche/protokoll").status_code == 403
            assert mv.get("/api/material/freigaben", query_string={"user_id": mg_id}).status_code == 403
            # Prüfen: nicht von selbst – erst mit Häkchen, Urkundennummer und eigener Prüffreigabe.
            r = starten(mv, art)
            assert r.status_code == 403 and "Prüfer" in r.json["error"], r.get_json()
            assert adm.put(f"/api/admin/users/{k['katalog_id']}", json={"mat_pruefer": True,
                                                                         "urkundennummer": "1012-2020"}).status_code == 200
            assert starten(mv, art).status_code == 403
            # Die Prüffreigabe gibt sie sich selbst (Regel 1.6 Nr. 1, wie bisher die Plattform-Verwaltung) – dauerhaft
            # auch ohne Zeile für lesen oder verwalten, denn das Grundrecht hat sie überall.
            r = mv.post(f"/api/material/ordner/{gid}/freigaben", json={"user_id": k["katalog_id"], "pruefen": True})
            assert r.status_code == 201 and r.json["freigaben"][0]["bis"] is None and r.json["freigaben"][0]["wirkt"], \
                r.get_json()
            r = starten(mv, art)
            assert r.status_code == 201, r.get_json()
    finally:
        post_zurueck(pa[1])
    print("Mitglied und Material-Verwaltung bestanden.")


# --- Häkchen ohne Stufe, Personensuche, Verwalter --------------------------------------------------------------

def test_haekchen_ohne_stufe():
    """Häkchen „Prüfer“ und Urkundennummer ohne Stufe: kein Zugang, die Prüffreigabe wirkt nicht („kein Zugang zum Modul
    Material“), keine Rückrufmail, die Personensuche für Freigaben findet das Konto nicht, die Urkundennummer lässt sich
    nicht eintragen, neu unterschreiben auch nicht – die hinterlegte Unterschrift zeigt das Profil nur zum Entfernen."""
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            adm, w = k["adm"], k["wart"]
            ids = katalog_grund(adm)
            pruef_formulare(k["katalog"], ids)
            gid, _ = gliederung(adm)
            art = neuer_artikel(w, ids["hms"], gid, serial_no="HK-0001")["id"]
            p, pid = neues_konto(app, "haken@example.org", name="Haken Test", mat_pruefer=True, urkundennummer="1012-3030")
            freigeben(adm, gid, pid, "lesen")
            freigeben(adm, gid, pid, "pruefen")
            unterschreiben(p)
            # Mit Stufe geprüft – danach nimmt die Verwaltung die Stufe (Häkchen und Nummer bleiben, wirken aber nicht).
            r = starten(p, art)
            assert r.status_code == 201, r.get_json()
            assert abschluss(p, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
            assert adm.put(f"/api/admin/users/{pid}", json={"rechte": {"material": 0}}).status_code == 200
            u = {x["id"]: x for x in adm.get("/api/admin/users").json["users"]}[pid]
            assert u["mat_pruefer"] and u["urkunde_gueltig"] and u["rechte"]["material"] == 0 and u["mat_freigaben"] == 2
            r = p.get("/api/material/start")
            assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
            liste = {f["recht"]: f for f in w.get(f"/api/material/ordner/{gid}/freigaben").json["direkt"]
                     if f["konto"]["id"] == pid}
            assert {r_: (f["wirkt"], f["wirkt_nicht"], f["konto"]["qualifiziert"], f["konto"]["zugang"])
                    for r_, f in liste.items()} == {"lesen": (False, "kein Zugang zum Modul Material", False, False),
                                                   "pruefen": (False, "kein Zugang zum Modul Material", False, False)}
            # Eine neue Prüffreigabe gibt es dafür nicht (409), die Personensuche für Freigaben kennt das Konto nicht.
            r = w.post(f"/api/material/ordner/{gid}/freigaben", json={"user_id": pid, "pruefen": True,
                                                                       "pruefen_bis": (_heute() + timedelta(days=30)).isoformat()})
            assert r.status_code == 409 and "keinen Zugang zum Modul Material" in r.json["error"], r.get_json()
            assert w.get("/api/material/nutzer", query_string={"q": "Haken"}).json["nutzer"] == []
            assert [x["id"] for x in w.get("/api/material/nutzer", query_string={"q": "Haken", "zweck": "zuordnung"})
                    .json["nutzer"]] == [pid]
            # Keine Rückrufmail – er sieht den Artikel nicht mehr; der Verwalter schon.
            del post[:]
            assert k["katalog"].post(RR.format(ids["hms"]), json={"title": "Testrückruf"}).status_code == 201
            assert sorted(an for an, _, _ in post) == ["wart@example.org"], post
            # Profil: Urkundennummer 403, neu unterschreiben 403. Die hinterlegte Unterschrift zeigt der Abschnitt
            # trotzdem – nur zum Entfernen (ihre eigenen Daten, auch ohne Zugang); danach ist er weg.
            html = p.get("/profil").get_data(as_text=True)
            assert 'id="unterschrift" data-setzen="0"' in html and 'id="f-urkunde"' not in html, html
            assert "<h2>Unterschrift</h2>" in html and "keinen Zugang zum Modul Material" in html
            assert p.put("/api/material/urkundennummer", json={"urkundennummer": "1012-3031"}).status_code == 403
            from test_material import unterschrift_daten
            assert p.put("/api/material/unterschrift", json={"bild": unterschrift_daten()}).status_code == 403
            r = p.get("/api/material/unterschrift")
            assert r.status_code == 200 and r.json["unterschrift"].startswith("data:image/png"), r.get_json()
            assert p.delete("/api/material/unterschrift", headers=H).status_code == 200
            assert zeilen(app, "SELECT signature_png FROM users WHERE id = ?", (pid,)) == [{"signature_png": None}]
            assert zeilen(app, "SELECT action, user_id FROM mat_audit WHERE entity = 'user' AND entity_id = ? "
                               "ORDER BY id DESC LIMIT 1", (pid,)) == [{"action": "unterschrift", "user_id": pid}]
            assert 'id="unterschrift"' not in p.get("/profil").get_data(as_text=True)
    finally:
        post_zurueck(alt)
    print("Häkchen ohne Stufe bestanden.")


def test_personensuche_zweck():
    """Ein aktives Konto mit Namen, aber ohne Stufe: Freigabe erteilen 409 mit Klartext (und die Suche für Freigaben
    findet es nicht), einen Artikel zuordnen geht (Personen mit PSA brauchen keinen Modulzugang)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        ids = katalog_grund(adm)
        gid, _ = gliederung(adm)
        art = neuer_artikel(w, ids["hms"], gid, serial_no="PS-0001")["id"]
        _, uid = neues_konto(app, "psa@example.org", name="Psa Träger", stufe=0)
        r = w.post(f"/api/material/ordner/{gid}/freigaben", json={"user_id": uid, "grundrecht": "lesen"})
        assert r.status_code == 409 and "keinen Zugang zum Modul Material" in r.json["error"], r.get_json()
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE user_id = ?", (uid,))
        for zweck, gefunden in ((None, []), ("freigabe", []), ("zuordnung", [uid])):
            q = {"q": "Träger", **({"zweck": zweck} if zweck else {})}
            assert [x["id"] for x in w.get("/api/material/nutzer", query_string=q).json["nutzer"]] == gefunden, zweck
        r = w.put(ZU.format(art), json={"user_id": uid})
        assert r.status_code == 200, r.get_json()
        # Ein Mitglied findet die Suche für beides, und erteilen geht.
        _, mg = neues_konto(app, "mitglied@example.org", name="Mitglied Träger")
        assert [x["id"] for x in w.get("/api/material/nutzer", query_string={"q": "Mitglied Tr"}).json["nutzer"]] == [mg]
        assert w.post(f"/api/material/ordner/{gid}/freigaben", json={"user_id": mg, "grundrecht": "lesen"}).status_code == 201
    print("Personensuche je Zweck bestanden.")


def test_meldung_ohne_stufe():
    """Ein Melder, dem die Verwaltung die Stufe nimmt, liest seine Meldung nicht mehr (403 „nicht freigeschaltet“ wie
    jede Route des Moduls – sie zeigt Katalog und Antwort der Material-Verwaltung), die Liste und die Fotos auch nicht.
    Löschen darf er seine eigene weiter (seine Angaben); eine fremde antwortet wie eine unbekannte. Mit Stufe liest er
    sie wieder."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        anderer, _ = neues_konto(app, "wart2@example.org", "verwalten", name="Wart Zwei")
        gid, _ = gliederung(adm)

        def melden(c, modell):
            r = c.post("/api/material/meldungen", headers=H, content_type="multipart/form-data",
                       data={"manufacturer": "Meldewerk", "model": modell, "folder_id": str(gid),
                             "fotos": [(jpeg(), "foto.jpg")]})
            assert r.status_code == 201, r.get_json()
            return r.json["meldung"]
        eigene, behalten = melden(w, "Modell Eigen"), melden(w, "Modell Bleibt")
        fremde = melden(anderer, "Modell Fremd")
        foto = eigene["fotos"][0]["web"]
        assert w.get(f"/api/material/meldungen/{eigene['id']}").status_code == 200 and w.get(foto).status_code == 200
        assert adm.put(f"/api/admin/users/{k['wart_id']}", json={"rechte": {"material": 0}}).status_code == 200
        for url in (f"/api/material/meldungen/{eigene['id']}", f"/api/material/meldungen/{fremde['id']}",
                    "/api/material/meldungen/999999", "/api/material/meldungen"):
            r = w.get(url)
            assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], (url, r.get_json())
        assert w.get(foto).status_code == 403
        gleich_wie_unbekannt(w.delete(f"/api/material/meldungen/{fremde['id']}", headers=H),
                             w.delete("/api/material/meldungen/999999", headers=H))
        assert w.delete(f"/api/material/meldungen/{eigene['id']}", headers=H).status_code == 200
        assert [m["id"] for m in zeilen(app, "SELECT id FROM mat_product_request ORDER BY id")] == [behalten["id"],
                                                                                                    fremde["id"]]
        assert adm.put(f"/api/admin/users/{k['wart_id']}", json={"rechte": {"material": 1}}).status_code == 200
        assert w.get(f"/api/material/meldungen/{behalten['id']}").status_code == 200
    print("Meldung ohne Stufe bestanden.")


def test_namenlos_startseite():
    """Ein namenloses Konto von früher mit Stufe Mitglied (Schritt 10 setzt auch solche auf 1): Die Startseite führt
    nicht in die Fehlerseite des Moduls, sondern in den Lesemodus des Wikis, und die Kopfleiste zeigt „Material“ nicht –
    beides erst mit Namen. /material selbst sagt, was fehlt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        uid = _konto_sql(app, "namenlos@example.org", name="", recht_material=1, recht_wiki=0, recht_karte=0)
        c = anmelden(app, "namenlos@example.org", "passwort1")
        r = c.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/wiki"), (r.status_code, r.headers)
        assert 'href="/material"' not in c.get("/profil").get_data(as_text=True)
        r = c.get("/material")
        assert r.status_code == 403 and "braucht dein Konto einen Namen" in r.get_data(as_text=True)
        sql(app, "UPDATE users SET name = 'Namenlos Test' WHERE id = ?", (uid,))
        r = c.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/material"), (r.status_code, r.headers)
        assert 'href="/material"' in c.get("/profil").get_data(as_text=True)
        assert c.get("/material").status_code == 200
    print("Namenloses Konto: Startseite bestanden.")


def test_ruhende_freigabe_nicht_hochstufen():
    """Eine Freigabe, die ruht, weil das Konto keine Stufe hat (1.6 Nr. 12): Hochstufen (lesen → verwalten), ein
    späteres Ende oder aus lesen ein dauerhaftes Grundrecht machen geht per PUT so wenig wie beim Erteilen – 409 mit
    demselben Klartext, nichts geschrieben, auch nicht durch die Material-Verwaltung. Kürzen, Herabsetzen, die Notiz und
    Entziehen gehen weiter. Mit Stufe Mitglied geht das Hochstufen wieder."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w, mv = k["adm"], k["wart"], k["katalog"]
        gid, _ = gliederung(adm)
        _, uid = neues_konto(app, "ruhend@example.org", name="Ruhend Test")
        _, uid2 = neues_konto(app, "ruhend2@example.org", name="Ruhend Zwei")
        bis = (_heute() + timedelta(days=30)).isoformat()
        lesen = freigeben(adm, gid, uid, "lesen", bis=bis)
        verwalten = freigeben(adm, gid, uid2, "verwalten")
        for x in (uid, uid2):
            assert adm.put(f"/api/admin/users/{x}", json={"rechte": {"material": 0}}).status_code == 200

        def zeile(gid_):
            return zeilen(app, "SELECT permission, valid_until, note FROM mat_folder_grant WHERE id = ?", (gid_,))[0]
        vorher = zeile(lesen)
        spaeter = (_heute() + timedelta(days=60)).isoformat()
        for c in (w, mv, adm):
            for d in ({"recht": "verwalten"}, {"bis": spaeter}, {"bis": None}, {"recht": "verwalten", "bis": bis}):
                r = c.put(f"/api/material/freigaben/{lesen}", headers=H, json=d)
                assert r.status_code == 409 and "keinen Zugang zum Modul Material" in r.json["error"], (d, r.get_json())
        assert zeile(lesen) == vorher
        # Kürzen und die Notiz gehen, ebenso Herabsetzen und Kürzen der dauerhaften Verwalterzeile – und Entziehen.
        kuerzer = (_heute() + timedelta(days=10)).isoformat()
        r = w.put(f"/api/material/freigaben/{lesen}", headers=H, json={"bis": kuerzer, "notiz": "ruht"})
        assert r.status_code == 200, r.get_json()
        assert zeile(lesen) == {"permission": "lesen", "valid_until": kuerzer, "note": "ruht"}
        r = w.put(f"/api/material/freigaben/{verwalten}", headers=H, json={"recht": "lesen", "bis": bis})
        assert r.status_code == 200, r.get_json()
        assert zeile(verwalten)["permission"] == "lesen" and zeile(verwalten)["valid_until"] == bis
        assert w.delete(f"/api/material/freigaben/{verwalten}", headers=H).status_code == 200
        # Mit Stufe Mitglied ist es eine gewöhnliche Zeile.
        assert adm.put(f"/api/admin/users/{uid}", json={"rechte": {"material": 1}}).status_code == 200
        r = w.put(f"/api/material/freigaben/{lesen}", headers=H, json={"recht": "verwalten"})
        assert r.status_code == 200 and zeile(lesen)["permission"] == "verwalten", r.get_json()
    print("Ruhende Freigabe nicht hochstufen bestanden.")


def test_verwalter_ohne_stufe():
    """verwalter_von zählt nur Konten mit Stufe Mitglied und Namen – nicht die Material-Verwaltung, nicht ein Verwalter
    ohne Stufe oder ohne Namen. Regel 1.6 Nr. 7 rechnet damit: Der einzige wirksame Verwalter entzieht sich nicht. Ein
    Rückruf an einem Artikel, dessen einziger Verwalter keine Stufe hat, geht an die Material-Verwaltung."""
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            adm, w = k["adm"], k["wart"]
            ids = katalog_grund(adm)
            gid, _ = gliederung(adm)
            neuer_artikel(w, ids["hms"], gid, serial_no="VW-0001")
            _, ohne_stufe = neues_konto(app, "vw0@example.org", name="Verwalter ohne Stufe", stufe=0)
            _, ohne_name = neues_konto(app, "vwn@example.org", name="Verwalter ohne Namen")
            freigeben(adm, gid, ohne_stufe, "verwalten")
            freigeben(adm, gid, ohne_name, "verwalten")
            freigeben(adm, gid, k["katalog_id"], "verwalten")
            sql(app, "UPDATE users SET name = '' WHERE id = ?", (ohne_name,))
            with app.app_context():
                from app.material.services import rechte
                assert [v["id"] for v in rechte.verwalter_von(gid)] == [k["wart_id"]]
            # Nr. 7: Der Materialwart ist der einzige wirksame Verwalter – entziehen kann er sich nicht.
            eigene = zeilen(app, "SELECT id FROM mat_folder_grant WHERE user_id = ? AND folder_id = ? AND "
                                 "permission = 'verwalten'", (k["wart_id"], gid))[0]["id"]
            r = w.delete(f"/api/material/freigaben/{eigene}", headers=H)
            assert r.status_code == 409 and "Material-Verwaltung" in r.json["error"], r.get_json()
            # Hat der Materialwart keine Stufe mehr, verwaltet niemand wirksam: Der Rückruf geht an die Material-Verwaltung.
            assert adm.put(f"/api/admin/users/{k['wart_id']}", json={"rechte": {"material": 0}}).status_code == 200
            del post[:]
            r = adm.post(RR.format(ids["hms"]), json={"title": "Testrückruf"})
            assert r.status_code == 201, r.get_json()
            assert sorted(an for an, _, _ in post) == ["katalog@example.org"], post
            # „Verlängern kann …“ nennt dann die Material-Verwaltung (freigaben.js) – die Liste der Verwalter ist leer.
            m = k["fuehrung"].get("/api/material/freigaben/meine").json["freigaben"]
            assert m and all(f["verwalter"] == [] for f in m), m
    finally:
        post_zurueck(alt)
    print("Verwalter ohne Stufe bestanden.")


def test_letzter_materialwart():
    """Feld „letzter_materialwart“ von GET /api/admin/users/<uid>/material-folgen (Entscheidung des Betreibers vom
    18.10.2026: Die Nutzerverwaltung fragt nach, bevor sie den einzigen Materialwart einer Gliederung auf Material „–“
    stellt oder deaktiviert; der Dialog „Löschen“ nennt es). Darin stehen die Gliederungen, deren einziger wirksamer
    Verwalter das Konto heute ist – mit verwalten an der Gliederung oder geerbt von oben, auch eine verschachtelte. Nicht
    mitgezählt: die Material-Verwaltung, ein Mitverwalter mit abgelaufener Freigabe, ein deaktivierter und einer ohne
    Stufe. Eine eigene abgelaufene Freigabe oder eine nur unterhalb der Gliederung macht niemanden zum Materialwart. Nur
    die Plattform-Verwaltung liest das Feld; gesperrt wird nichts."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, wart_id = k["adm"], k["wart_id"]
        gid, _ = gliederung(adm)                                    # der Materialwart verwaltet dort (Grundrecht)
        ot = ordner_neu(adm, gid, "OT Nord", kind="gliederung")     # verschachtelt: verwaltet geerbt von oben
        lager = ordner_neu(adm, gid, "Lager")
        nachbar, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
        gestern = _heute() - timedelta(days=1)

        def folgen(uid):
            r = adm.get(f"/api/admin/users/{uid}/material-folgen")
            assert r.status_code == 200, r.get_json()
            assert set(r.json) == {"freigaben", "zuordnungen", "entwuerfe", "pruefungen", "maengel", "antraege",
                                   "letzter_materialwart"}, r.json
            return [(x["id"], x["name"], x["pfad"]) for x in r.json["letzter_materialwart"]]

        beide = [(gid, "OG Musterstadt", "OG Musterstadt"), (ot, "OT Nord", "OG Musterstadt / OT Nord")]
        assert folgen(wart_id) == beide
        assert folgen(k["fuehrung_id"]) == [] and folgen(k["nutzer_id"]) == []
        # Die Material-Verwaltung zählt nicht als Materialwart – weder neben ihm noch selbst.
        freigeben(adm, gid, k["katalog_id"], "verwalten")
        assert folgen(wart_id) == beide and folgen(k["katalog_id"]) == []
        # Eine Mitverwalterin mit abgelaufener Freigabe zählt nicht; verwaltet sie die verschachtelte Gliederung gültig,
        # hat die zwei Materialwarte, die obere weiter einen.
        _, zweit = neues_konto(app, "zweit@example.org", name="Zweite Verwalterin")
        freigeben(adm, gid, zweit, "verwalten", bis=gestern)
        assert folgen(wart_id) == beide and folgen(zweit) == []
        freigeben(adm, ot, zweit, "verwalten")
        assert folgen(wart_id) == beide[:1] and folgen(zweit) == []
        # Verwalten nur unterhalb der Gliederung (Lager) macht niemanden zu ihrem Materialwart.
        _, lagerwart = neues_konto(app, "lagerwart@example.org", name="Lagerwart")
        freigeben(adm, lager, lagerwart, "verwalten")
        assert folgen(lagerwart) == [] and folgen(wart_id) == beide[:1]
        # Zwei wirksame Materialwarte an der Gliederung: keiner ist der einzige.
        freigeben(adm, gid, zweit, "verwalten")
        assert folgen(wart_id) == [] and folgen(zweit) == []
        # Deaktiviert zählt die Mitverwalterin nicht, ohne Stufe auch nicht.
        assert adm.put(f"/api/admin/users/{zweit}", json={"active": False}).status_code == 200
        assert folgen(wart_id) == beide and folgen(zweit) == []
        assert adm.put(f"/api/admin/users/{zweit}", json={"active": True}).status_code == 200
        assert folgen(wart_id) == []
        assert adm.put(f"/api/admin/users/{zweit}", json={"rechte": {"material": 0}}).status_code == 200
        assert folgen(wart_id) == beide
        # Die eigene abgelaufene Freigabe an einer Gliederung ohne Verwalter zählt nicht.
        freigeben(adm, nachbar, wart_id, "verwalten", bis=gestern)
        assert folgen(wart_id) == beide
        # Nur die Plattform-Verwaltung liest das – die Material-Verwaltung und der Materialwart selbst nicht.
        for c in (k["katalog"], k["wart"], k["fuehrung"]):
            assert c.get(f"/api/admin/users/{wart_id}/material-folgen").status_code == 403
        # Nur eine Warnung: Material „–“ und Deaktivieren speichern trotzdem; danach ist er kein Materialwart mehr.
        assert adm.put(f"/api/admin/users/{wart_id}", json={"rechte": {"material": 0}}).status_code == 200
        assert folgen(wart_id) == []
        with app.app_context():
            from app.material.services import rechte
            assert rechte.verwalter_von(gid) == [] and rechte.verwalter_von(ot) == []
        assert adm.put(f"/api/admin/users/{wart_id}", json={"rechte": {"material": 1}}).status_code == 200
        assert folgen(wart_id) == beide
        assert adm.put(f"/api/admin/users/{wart_id}", json={"active": False}).status_code == 200
        assert folgen(wart_id) == []
    print("Letzter Materialwart bestanden.")


def test_letzter_materialwart_oberflaeche():
    """Nutzerverwaltung (statisch): Material auf „–“ – in der Tabelle wie im Dialog „Bearbeiten“ – und Deaktivieren
    fragen beim einzigen Materialwart einer Gliederung erst nach (materialwartBleibt); die Rückfrage nennt die
    Gliederungen, hat „Abbrechen“ grau vorn mit dem Fokus und „Trotzdem speichern“ als roten Hauptknopf – kein Knopf für
    Endgültiges, denn gelöscht wird nichts. Nach dem Abbrechen steht der Fokus wieder auf „Speichern“ bzw. der Auswahl in
    der Tabelle (der Browser fand beim Schließen nur den gesperrten Knopf und ließ ihn auf der Seite). Der Dialog
    „Löschen“ nennt dieselbe Folge."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, "app", "static", "js", "admin.js"), encoding="utf-8") as f:
        js = f.read()

    def funktion(name):
        return re.search(r"\n  (?:async )?function " + name + r"\(.*?\n  \}\n", js, re.S).group(0)

    rueck = funktion("rueckfrage")
    assert '<button class="btn secondary" id="rf-nein" type="button">Abbrechen</button>' in rueck
    assert '<button class="btn" id="rf-ja" type="button">' in rueck and "danger" not in rueck and "ghost" not in rueck
    assert rueck.index("rf-nein") < rueck.index("rf-ja") and 'dlg.querySelector("#rf-nein").focus();' in rueck
    bleibt = funktion("materialwartBleibt")
    for da in ("letzter_materialwart", "/material-folgen", "(material | 0) === 0", "aktiv === false",
               "gliederungenText(gl)", "nur noch die Material-Verwaltung", '"Trotzdem speichern"',
               "if (!gl.length) return true;"):
        assert da in bleibt, da
    # Beide Wege, Material zu senken: die Tabelle (nur das Modul Material) und der Dialog (dazu „Konto aktiv“).
    assert 'sel.dataset.modul !== "material" || await materialwartBleibt(u, +sel.value)' in js
    assert "if (!(await materialwartBleibt(u, d.rechte.material, d.active))) return;" in js
    # Fokus nach dem Abbrechen (oder einem Fehler): Im Dialog kommt er auf „Speichern“ zurück, sobald der Knopf wieder
    # frei ist; in der Tabelle auf die neu gezeichnete Auswahl desselben Moduls – beides nur, wenn er nicht woanders steht.
    speichern = js[js.index('if (btn.dataset.act === "edit")'):js.index('btn.dataset.act === "reset"')]
    frei = speichern.index("finally {\n              knopf.disabled = false;")
    assert speichern.index("if (dlg.open && !dlg.contains(document.activeElement)) knopf.focus();") > frei
    tabelle = js[js.index('tbody.addEventListener("change"'):js.index('tbody.addEventListener("click"')]
    assert tabelle.index("zeichneRechte(tr, u);") < tabelle.index("neu.focus();")
    assert 'tr.querySelector(`select[data-modul="${sel.dataset.modul}"]`)' in tabelle
    assert "document.activeElement === document.body)) neu.focus();" in tabelle
    loesch = funktion("loeschDialog")
    assert "letzter_materialwart" in loesch and "gliederungenText(gl)" in loesch
    assert "nur noch die Material-Verwaltung" in loesch
    print("Letzter Materialwart (Oberfläche) bestanden.")


# --- Mails, Profil, Vorgabe ------------------------------------------------------------------------------------

def test_mail_meldung():
    """Eine neue Produktmeldung geht an die Material-Verwaltung ohne Plattform-Verwaltung – nicht an deaktivierte und
    namenlose Konten der Stufe Verwaltung; gibt es keine, an die Plattform-Verwaltung."""
    with post_der_meldungen() as post, tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        gid, _ = gliederung(k["adm"])
        _, weg = neues_konto(app, "mv-weg@example.org", name="MV Deaktiviert", rechte={"material": 2})
        _, leer = neues_konto(app, "mv-leer@example.org", name="MV Leer", rechte={"material": 2})
        assert k["adm"].put(f"/api/admin/users/{weg}", json={"active": False}).status_code == 200
        sql(app, "UPDATE users SET name = '' WHERE id = ?", (leer,))

        def melden(modell):
            del post[:]
            r = k["wart"].post("/api/material/meldungen", headers=H, json={"manufacturer": "Meldewerk", "model": modell,
                                                                           "folder_id": gid})
            assert r.status_code == 201, r.get_json()
            return sorted(an for an, _, _ in post)
        assert melden("Modell Eins") == ["katalog@example.org"]
        sql(app, "UPDATE users SET recht_material = 1 WHERE id = ?", (k["katalog_id"],))
        assert melden("Modell Zwei") == ["admin@example.org"]
    print("Mail zur Meldung bestanden.")


def test_profil_unterschrift():
    """Den Abschnitt „Unterschrift“ im Profil und PUT /unterschrift hat, wer mit Zugang festschreibt oder aussondert:
    der Materialwart mit Stufe Mitglied (er verwaltet über seine Freigabe), die Material-Verwaltung, der Prüfer. Ein
    Mitglied, das nichts verwaltet und kein Häkchen hat, nicht."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        gid, _ = gliederung(k["adm"])
        from test_material import unterschrift_daten
        for wer in ("wart", "katalog", "pruefer"):
            c = k[wer]
            html = c.get("/profil").get_data(as_text=True)
            assert 'id="unterschrift" data-setzen="1"' in html, wer
            assert c.put("/api/material/unterschrift", json={"bild": unterschrift_daten()}).status_code == 200, wer
        assert zeilen(app, "SELECT recht_material FROM users WHERE id = ?", (k["wart_id"],))[0]["recht_material"] == 1
        html = k["fuehrung"].get("/profil").get_data(as_text=True)
        assert 'id="unterschrift"' not in html
        r = k["fuehrung"].put("/api/material/unterschrift", json={"bild": unterschrift_daten()})
        assert r.status_code == 403, r.get_json()
    print("Profil: Unterschrift bestanden.")


def test_vorgabe_neue_konten():
    """Neue Konten (Kontoanfrage und Nutzerverwaltung ohne Angabe) bekommen Mitglied im Modul Material und sonst nichts;
    der allererste Nutzer weiter überall Verwaltung. Vorhandene Konten bleiben, wie sie sind. Mit der Freigabe einer
    Kontoanfrage steht die Stufe im Journal des Moduls („rollen“)."""
    keys = ("ADMIN_EMAIL", "ADMIN_PASSWORD")
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as leer:
        make_app(tmp)                                          # setzt die Umgebung wie alle Tests
        alt = {x: os.environ.get(x) for x in keys + ("DATA_DIR",)}
        os.environ.update({x: "" for x in keys})
        os.environ["DATA_DIR"] = leer                          # eine leere Datenbank ohne Administrator aus der .env
        try:
            from app import create_app
            app = create_app()
            app.config["TESTING"] = True
            erst = app.test_client()
            r = erst.post("/api/auth/register", json={"email": "erst@example.org", "password": "passwort1",
                                                      "name": "Erste Person", "gliederung": "OG Test"})
            assert r.status_code == 201 and r.json["pending"] is False, r.get_json()
            assert r.json["user"]["rechte"] == {m: 2 for m in ("karte", "wiki", "pruefungen", "material", "verwaltung")}
            zweit = app.test_client()
            r = zweit.post("/api/auth/register", json={"email": "zweit@example.org", "password": "passwort1",
                                                       "name": "Zweite Person", "gliederung": "OG Test"})
            assert r.status_code == 201 and r.json["pending"] is True, r.get_json()
            u = [x for x in erst.get("/api/admin/users").json["users"] if x["email"] == "zweit@example.org"][0]
            assert u["rechte"] == {"karte": 0, "wiki": 0, "pruefungen": 0, "material": 1, "verwaltung": 0}, u
            assert zeilen(app, "SELECT recht_karte, recht_wiki, recht_material FROM users WHERE id = ?", (u["id"],)) == [
                {"recht_karte": 0, "recht_wiki": 0, "recht_material": 1}]
            # Die Stufe steht im Journal des Moduls, sobald sie wirkt – mit der Freigabe der Anfrage, die freigebende
            # Verwaltung als Handelnde (wie beim Anlegen in der Nutzerverwaltung). Vorher und für eine abgelehnte
            # Anfrage nichts.
            def rollen(uid):
                return zeilen(app, "SELECT user_id, user_name, before_json, after_json FROM mat_audit WHERE entity = 'user' "
                                   "AND entity_id = ? AND action = 'rollen'", (uid,))
            assert rollen(u["id"]) == []
            dritt = app.test_client().post("/api/auth/register", json={
                "email": "dritt@example.org", "password": "passwort1", "name": "Dritte Person", "gliederung": "OG Test"})
            assert dritt.status_code == 201
            d_id = [x for x in erst.get("/api/admin/users").json["users"] if x["email"] == "dritt@example.org"][0]["id"]
            assert erst.post(f"/api/admin/users/{d_id}/reject", headers=H, json={}).status_code == 200
            assert rollen(d_id) == []
            r = erst.post(f"/api/admin/users/{u['id']}/approve", headers=H, json={})
            assert r.status_code == 200, r.get_json()
            erst_id = zeilen(app, "SELECT id FROM users WHERE email = 'erst@example.org'")[0]["id"]
            e = rollen(u["id"])
            assert len(e) == 1 and e[0]["user_id"] == erst_id and e[0]["user_name"] == "Erste Person", e
            assert e[0]["before_json"] is None and json.loads(e[0]["after_json"]) == {
                "recht_material": 1, "mat_pruefer": 0, "grund": "Kontoanfrage freigegeben"}, e
            # Gesamtprüfung: Das Profil eines neuen Kontos (Wiki im Lesemodus, Material Mitglied) erklärt das Profilbild
            # mit Wiki-Seiten – „Artikel“ heißt im Modul Material der Ausrüstungsgegenstand.
            neu = app.test_client()
            assert neu.post("/api/auth/login", json={"email": "zweit@example.org", "password": "passwort1"}).status_code == 200
            profil = neu.get("/profil").get_data(as_text=True)
            assert "neben deinem Namen an jeder Wiki-Seite, die du erstellt oder bearbeitet hast" in profil
            assert "an jedem Artikel" not in profil
            # Eine Kontoanfrage, der die Verwaltung vor der Freigabe Material „–“ gibt, hinterlässt beim Freigeben nichts.
            assert app.test_client().post("/api/auth/register", json={
                "email": "viert@example.org", "password": "passwort1", "name": "Vierte Person",
                "gliederung": "OG Test"}).status_code == 201
            v_id = [x for x in erst.get("/api/admin/users").json["users"] if x["email"] == "viert@example.org"][0]["id"]
            assert erst.put(f"/api/admin/users/{v_id}", json={"rechte": {"material": 0}}).status_code == 200
            n = len(rollen(v_id))
            assert erst.post(f"/api/admin/users/{v_id}/approve", headers=H, json={}).status_code == 200
            assert len(rollen(v_id)) == n
        finally:
            for x, v in alt.items():
                os.environ[x] = v or ""
    # Die Vorgabe steht an einer Stelle (auth.VORGABE_NEU) – Nutzerverwaltung und Oberfläche nennen dieselbe.
    from app import api_admin, auth
    assert api_admin.VORGABE == auth.VORGABE_NEU == {"karte": 0, "wiki": 0, "pruefungen": 0, "material": 1,
                                                     "verwaltung": 0}
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, "app", "static", "js", "admin.js"), encoding="utf-8") as f:
        assert "const VORGABE = { karte: 0, wiki: 0, pruefungen: 0, material: 1, verwaltung: 0 };" in f.read()
    print("Vorgabe neuer Konten bestanden.")


def test_nutzerverwaltung_oberflaeche():
    """Die Nutzerverwaltung zeigt Material als gewöhnliche Auswahl: keine Marke „Katalog“, kein Häkchen
    „Produktkatalogpfleger“, kein „alles“ und keine „Stufe aus Phase 1“ mehr; das Häkchen „Prüfer“ hebt „–“ auf
    „Mitglied“; die kleinen Marken „n Freigaben“ und „wirkt nicht – kein Zugang“."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, "app", "static", "js", "admin.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(wurzel, "app", "templates", "admin.html"), encoding="utf-8") as f:
        html = f.read()
    for weg in ("nurAnzeige", "materialAnzeige", "mat_katalog", "mat_stufe_alt", "Produktkatalogpfleger", "Stufe aus Phase 1",
                '"alles"', "u-mat-katalog"):
        assert weg not in js, weg
    assert "Produktkatalogpfleger" not in html and "Spalte Material ist nur Anzeige" not in html
    # Die Hebung auch nach einem Hin und Her der Verwaltung (Häkchen gesetzt, während Material überdeckt war); der
    # Hinweis nur, solange Material nicht überdeckt ist (im Chromium nachgeprüft, Prüfung der Modulstufen Nr. 8).
    for da in ("wirkt nicht – kein Zugang", "Frei&shy;gabe", 'material.value === "0"', 'material.value = "1"',
               "Material steht jetzt auf „Mitglied“", "if (!voll && offen)", "auto.hidden = !gehoben || material.disabled"):
        assert da in js, da
    # Gesamtprüfung: Die Zeile zur Urkundennummer nennt nur den Zustand – dass der Prüfer sie selbst im Profil einträgt,
    # steht einmal, im Hilfetext darunter (vorher zweimal untereinander).
    urkunde = re.search(r"function urkundeLesend\(u\) \{(.*?)\n  \}", js, re.S).group(1)
    assert "Profil" not in urkunde and "Urkundennummer: noch keine – solange darf er nicht prüfen." in urkunde, urkunde
    assert js.count("trägt der Prüfer selbst in seinem Profil ein") == 1
    print("Nutzerverwaltung (Oberfläche) bestanden.")


if __name__ == "__main__":
    test_migration_9_10()
    test_migration_produktion()
    test_ohne_stufe_rundum()
    test_mitglied_und_material_verwaltung()
    test_haekchen_ohne_stufe()
    test_personensuche_zweck()
    test_namenlos_startseite()
    test_ruhende_freigabe_nicht_hochstufen()
    test_meldung_ohne_stufe()
    test_verwalter_ohne_stufe()
    test_letzter_materialwart()
    test_letzter_materialwart_oberflaeche()
    test_mail_meldung()
    test_profil_unterschrift()
    test_vorgabe_neue_konten()
    test_nutzerverwaltung_oberflaeche()
    print("Alle Tests zur Modulstufe bestanden.")
