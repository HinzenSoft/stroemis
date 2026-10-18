"""Rauchtest für das Modul „Material“, Lieferung 5 – Urkundennummer im Profil:  python tests/test_material_profil.py

Das Häkchen „Prüfer“ setzt die Verwaltung (Nutzerverwaltung), die Urkundennummer trägt der Prüfer selbst im Profil ein
(PUT /api/material/urkundennummer). Ohne gültige Nummer darf er nicht prüfen. Alle Namen und Nummern hier sind erfunden
und nur für den Test da."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, anmelden, freigeben, gliederung, katalog_grund, neuer_artikel,  # noqa: E402
                           pruef_formulare, starten, umgebung, unterschrift_daten)

URL = "/api/material/urkundennummer"


def _darf(c):
    return c.get("/api/material/start").json["darf"]


def _journal(app, uid):
    with app.app_context():
        from app import db
        return [(e["action"], json.loads(e["before_json"]) if e["before_json"] else None,
                 json.loads(e["after_json"]) if e["after_json"] else None)
                for e in db.query("SELECT * FROM mat_audit WHERE entity = 'user' AND entity_id = ? ORDER BY id", (uid,))]


def _nummer(app, uid):
    with app.app_context():
        from app import db
        return db.query("SELECT urkundennummer FROM users WHERE id = ?", (uid,), one=True)["urkundennummer"]


def test_urkundennummer_im_profil():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["wart"])
        a = neuer_artikel(k["wart"], ids["hms"], gid)

        # 1. Die Verwaltung setzt nur das Häkchen – ohne Nummer geht das jetzt.
        r = adm.post("/api/admin/users", json={"email": "neu@example.org", "password": "passwort1", "name": "Neue Prüferin",
                                               "mat_pruefer": True})
        assert r.status_code == 201, r.get_json()
        neu_id = r.json["user"]["id"]
        # Seit Phase 2: Bestand und Prüfen über Freigaben am Ordner (die Prüffreigabe wirkt erst mit Urkundennummer).
        freigeben(adm, gid, neu_id, "lesen")
        freigeben(adm, gid, neu_id, "pruefen")
        assert r.json["user"]["mat_pruefer"] and r.json["user"]["urkundennummer"] == "" and not r.json["user"]["urkunde_gueltig"]
        liste = {u["id"]: u for u in adm.get("/api/admin/users").json["users"]}
        assert liste[neu_id]["mat_pruefer"] and not liste[neu_id]["urkunde_gueltig"]
        assert liste[k["pruefer_id"]]["urkunde_gueltig"]
        p = anmelden(app, "neu@example.org", "passwort1")

        # 2. Häkchen ohne Nummer: lesen ja, prüfen nein – und die Meldung sagt, wo die Nummer hingehört.
        d = _darf(p)
        assert d["lesen"] and d["pruefer_haekchen"] and d["pruefen"] is False and d["urkundennummer"] == "", d
        r = starten(p, a["id"])
        assert r.status_code == 403 and "Profil" in r.json["error"] and "Urkundennummer" in r.json["error"], r.get_json()
        r = p.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Test"})
        assert r.status_code == 403 and "Profil" in r.json["error"], r.get_json()
        # Die Unterschrift darf er schon hinterlegen – Urkundennummer und Unterschrift in beliebiger Reihenfolge.
        r = p.put("/api/material/unterschrift", json={"bild": unterschrift_daten()})
        assert r.status_code == 200, r.get_json()

        # 3. Profilseite: Reihenfolge Profilbild → Stammdaten → Urkundennummer und Unterschrift → Passwort; Feld und
        #    Hinweis sichtbar.
        html = p.get("/profil").get_data(as_text=True)
        stellen = [html.index(t) for t in ("<h2>Profilbild</h2>", "<h2>Stammdaten</h2>",
                                           "<h2>Urkundennummer und Unterschrift</h2>", "<h2>Passwort ändern</h2>")]
        assert stellen == sorted(stellen), stellen
        assert html.index('id="f-profile"') > html.index("<h2>Stammdaten</h2>")
        assert 'id="f-urkunde"' in html and 'id="urkundennummer"' in html
        assert 'class="notice" id="ur-hinweis"' in html, "Hinweis „noch keine Urkundennummer“ fehlt"

        # 4. Ungültige Eingaben: 400, nichts gespeichert, kein Journal.
        for falsch in (" - ", "​", "⁠ -", "__", "x" * 41, 1012, ["1012"]):
            r = p.put(URL, json={"urkundennummer": falsch})
            assert r.status_code == 400 and "Urkundennummer" in r.json["error"], (falsch, r.get_json())
        assert _nummer(app, neu_id) == ""
        assert [e for e in _journal(app, neu_id) if e[0] == "urkundennummer"] == []
        # CSRF wie überall: ohne JSON und ohne X-Requested-With abgewiesen.
        r = p.put(URL, data="urkundennummer=1012-1", content_type="application/x-www-form-urlencoded")
        assert r.status_code == 403 and "X-Requested-With" in r.json["error"], r.get_json()
        r = p.put(URL, json={"urkundennummer": "1012-1"}, headers={"Sec-Fetch-Site": "cross-site"})
        assert r.status_code == 403 and _nummer(app, neu_id) == ""

        # 5. Gültige Nummer (unsichtbare Zeichen fliegen raus) → darf prüfen; Journal am Konto mit vorher/nachher.
        r = p.put(URL, json={"urkundennummer": "​ 1012-0900 "})
        assert r.status_code == 200 and r.json == {"urkundennummer": "1012-0900", "pruefen": True}, r.get_json()
        assert _darf(p)["pruefen"] and _darf(p)["urkundennummer"] == "1012-0900"
        r = starten(p, a["id"])
        assert r.status_code == 201, r.get_json()
        pid = r.json["pruefung"]["id"]
        assert p.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 200
        eintraege = [e for e in _journal(app, neu_id) if e[0] == "urkundennummer"]
        assert eintraege == [("urkundennummer", {"urkundennummer": ""}, {"urkundennummer": "1012-0900"})], eintraege
        with app.app_context():
            from app import db
            e = db.query("SELECT user_id, user_name FROM mat_audit WHERE action = 'urkundennummer' ORDER BY id DESC", one=True)
        assert e["user_id"] == neu_id and e["user_name"] == "Neue Prüferin"
        # Das Journal am Konto liest die Oberfläche mit Beschriftung (wie im Lebenslauf-PDF).
        from app.material.services.beschriftung import AKTION
        assert AKTION["urkundennummer"] == "Urkundennummer geändert"
        # Die Verwaltung sieht sie (nur lesend) in der Nutzerliste.
        liste = {u["id"]: u for u in adm.get("/api/admin/users").json["users"]}
        assert liste[neu_id]["urkundennummer"] == "1012-0900" and liste[neu_id]["urkunde_gueltig"]
        html = p.get("/profil").get_data(as_text=True)
        assert 'class="notice hidden" id="ur-hinweis"' in html and 'value="1012-0900"' in html
        # Dieselbe Nummer noch einmal: kein zweiter Eintrag.
        assert p.put(URL, json={"urkundennummer": "1012-0900"}).status_code == 200
        assert len([e for e in _journal(app, neu_id) if e[0] == "urkundennummer"]) == 1

        # 6. Fremdes Konto: Die Route kennt keine Kennung – was in der Anfrage steht, ändert nur das eigene Konto.
        vorher_pruefer = _nummer(app, k["pruefer_id"])
        r = p.put(URL, json={"urkundennummer": "1012-0901", "id": k["pruefer_id"], "user_id": k["pruefer_id"]})
        assert r.status_code == 200 and _nummer(app, k["pruefer_id"]) == vorher_pruefer == "1012-4711"
        assert _nummer(app, neu_id) == "1012-0901"
        assert p.put(f"{URL}/{k['pruefer_id']}", json={"urkundennummer": "X1"}).status_code in (404, 405)

        # 7. Leer speichern entfernt sie – dann darf er nicht mehr prüfen, und das Profil zeigt den Hinweis wieder.
        r = p.put(URL, json={"urkundennummer": "  "})
        assert r.status_code == 200 and r.json == {"urkundennummer": "", "pruefen": False}, r.get_json()
        assert not _darf(p)["pruefen"] and starten(p, a["id"]).status_code == 403
        assert 'class="notice" id="ur-hinweis"' in p.get("/profil").get_data(as_text=True)
        assert _journal(app, neu_id)[-1] == ("urkundennummer", {"urkundennummer": "1012-0901"}, {"urkundennummer": ""})

        # 8. Ohne Häkchen „Prüfer“: 403 – Materialwart, Führungskraft, Katalogpfleger, Verwaltung; ohne Modul ebenso.
        for c in (k["wart"], k["fuehrung"], k["katalog"], adm, k["nutzer"]):
            r = c.put(URL, json={"urkundennummer": "1012-0999"})
            assert r.status_code == 403, r.get_json()
        r = k["wart"].put(URL, json={"urkundennummer": "1012-0999"})
        assert "Häkchen" in r.json["error"] and "Nutzerverwaltung" in r.json["error"], r.get_json()
        with app.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM users WHERE urkundennummer = '1012-0999'", one=True)["n"] == 0
        # Profil ohne Häkchen: kein Feld; ein Materialwart sieht nur „Unterschrift“.
        html = k["wart"].get("/profil").get_data(as_text=True)
        assert 'id="f-urkunde"' not in html and "<h2>Unterschrift</h2>" in html
        assert "<h2>Stammdaten</h2>" in html
        html = k["fuehrung"].get("/profil").get_data(as_text=True)
        assert 'id="f-urkunde"' not in html and 'id="unterschrift"' not in html

        # 9. Nimmt die Verwaltung das Häkchen, geht die Nummer mit – eintragen geht dann nicht mehr.
        assert p.put(URL, json={"urkundennummer": "1012-0902"}).status_code == 200
        assert adm.put(f"/api/admin/users/{neu_id}", json={"mat_pruefer": False}).status_code == 200
        assert p.put(URL, json={"urkundennummer": "1012-0903"}).status_code == 403
        assert _nummer(app, neu_id) == "" and not _darf(p)["pruefen"] and not _darf(p)["pruefer_haekchen"]
        assert 'id="f-urkunde"' not in p.get("/profil").get_data(as_text=True)
        # Häkchen wieder gesetzt: Erst mit einer neu eingetragenen Nummer darf er prüfen – nichts gilt ungefragt wieder.
        assert adm.put(f"/api/admin/users/{neu_id}", json={"mat_pruefer": True}).status_code == 200
        assert not _darf(p)["pruefen"] and _darf(p)["pruefer_haekchen"]
        assert p.put(URL, json={"urkundennummer": "1012-0902"}).status_code == 200 and _darf(p)["pruefen"]
    print("Urkundennummer im Profil bestanden.")


if __name__ == "__main__":
    test_urkundennummer_im_profil()
