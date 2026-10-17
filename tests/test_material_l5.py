"""Rauchtest für das Modul „Material“, Lieferung 5 (Feinschliff nach Pilot):  python tests/test_material_l5.py

Jeder Mangel braucht Foto UND Bemerkung; Korrekturen an der Urkundennummer im Profil (Häkchen weg → Nummer weg, keine
stille Löschung, die Verwaltung schreibt keinen alten Stand zurück, aufs Protokoll nur die Nummer eines Prüfers).
Alle Namen und Nummern hier sind erfunden und nur für den Test da."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, gliederung, jpeg, katalog_grund, neuer_artikel, pruef_formulare,  # noqa: E402
                           punkte_von, starten, umgebung)


def test_mangel_braucht_bemerkung():
    """Ein Mangel mit Foto, aber ohne Bemerkung lässt sich nicht festschreiben; mit Bemerkung schon."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on="2025-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        url = f"/api/material/pruefungen/{pr['id']}/punkte"
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "1"}).status_code == 200
        # Der kritische Punkt weicht ab → Mangel, mit Foto, aber ohne Bemerkung.
        r = p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"wert": "ja"})
        assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel", r.get_json()
        r = p1.post(f"{url}/{pk['Testpunkt kritisch']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        r = abschluss(p1, pr["id"], ergebnis="instandsetzen")
        assert r.status_code == 400 and "Bemerkung" in r.json["error"] and "Testpunkt kritisch" in r.json["error"], r.get_json()
        # Nur Leerraum zählt nicht als Bemerkung.
        assert p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"notiz": "   "}).status_code == 200
        assert abschluss(p1, pr["id"], ergebnis="instandsetzen").status_code == 400
        assert p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"notiz": "Schnitt im Band, 2 cm"}).status_code == 200
        r = abschluss(p1, pr["id"], ergebnis="instandsetzen")
        assert r.status_code == 200, r.get_json()
    print("Mangel braucht Bemerkung bestanden.")


def test_urkunde_korrekturen():
    """Häkchen weg → Nummer weg; PUT ohne Feld löscht nichts; die Verwaltung schreibt beim Speichern keinen alten
    Stand zurück; aufs Protokoll kommt die Nummer nur, wenn das Konto wirksam Prüfer ist."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, p1, pid = k["adm"], k["pruefer"], k["pruefer_id"]

        def nummer():
            with app.app_context():
                from app import db
                return db.query("SELECT urkundennummer FROM users WHERE id = ?", (pid,), one=True)["urkundennummer"]

        assert nummer() == "1012-4711"
        # PUT ohne das Feld: 400, die Nummer bleibt.
        for koerper in ({}, {"nummer": "1012-1"}):
            r = p1.put("/api/material/urkundennummer", json=koerper)
            assert r.status_code == 400, (koerper, r.get_json())
        assert nummer() == "1012-4711"
        # Der Prüfer ändert seine Nummer; die Verwaltung speichert danach nur die Rechte – die Nummer bleibt die neue.
        assert p1.put("/api/material/urkundennummer", json={"urkundennummer": "1012-0815"}).status_code == 200
        assert adm.put(f"/api/admin/users/{pid}", json={"gliederung": "OG Test", "rechte": {"material": 2}}).status_code == 200
        assert nummer() == "1012-0815"
        # Häkchen weg → Nummer weg; Häkchen wieder → ohne Nummer, also noch kein Prüfer.
        assert adm.put(f"/api/admin/users/{pid}", json={"mat_pruefer": False}).status_code == 200
        assert nummer() == ""
        assert adm.put(f"/api/admin/users/{pid}", json={"mat_pruefer": True}).status_code == 200
        assert nummer() == "" and not p1.get("/api/material/start").json["darf"]["pruefen"]
        # pruefer_aus: ohne Häkchen trägt das Protokoll keine (alte) Nummer.
        with app.app_context():
            from app.material.services import pruefung
            konto = {"id": 99, "name": "x", "email": "x@example.org", "mat_pruefer": 0, "urkundennummer": "1012-9999",
                     "signature_png": None}
            assert pruefung.pruefer_aus(konto)["urkunde"] == ""
            konto["mat_pruefer"] = 1
            assert pruefung.pruefer_aus(konto)["urkunde"] == "1012-9999"
    print("Urkunde-Korrekturen bestanden.")


if __name__ == "__main__":
    test_mangel_braucht_bemerkung()
    test_urkunde_korrekturen()
