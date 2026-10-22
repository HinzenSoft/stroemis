"""Grenzen des Aussonderungsdatums (C2 in Phase 4 · Lieferung 1):  python tests/test_material_aussonderung_datum.py

Der Materialwart sondert mit Datum aus (TT.MM.JJJJ in der Oberfläche, ISO an den Server). Der Server weist ab: in der
Zukunft (400, wie bisher), vor der Erfassung des Artikels (400, wie bisher), vor der letzten abgeschlossenen Prüfung
(409 mit Klartext) und vor dem Herstelldatum (409 – auch bei einer Monatsangabe: der erste Tag des Monats zählt).
Ein Datum am Tag der letzten Prüfung geht durch (eine abgeschlossene Prüfung ist unveränderlich – geprüft wird
mit dem Prüftag heute). Alle Namen sind erfunden."""
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (_heute, festschreiben, gliederung, katalog_grund, neuer_artikel, pruef_formulare,  # noqa: E402
                           starten, umgebung)


def _sperren_nach_pruefung(p, iid):
    """Eine abgeschlossene Prüfung mit „instandsetzen“ (sperrt) – Prüftag ist heute; eine abgeschlossene Prüfung ist
    unveränderlich (Trigger), rückdatiert wird hier nichts."""
    r = starten(p, iid)
    assert r.status_code == 201, r.get_json()
    pid = r.json["pruefung"]["id"]
    r = festschreiben(p, pid, ergebnis="instandsetzen", grund="Platzhalter: Riss")
    assert r.status_code == 200, r.get_json()
    return pid


def test_grenzen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
        h = _heute()
        heute, gestern = h.isoformat(), (h - timedelta(days=1)).isoformat()
        # Metall, nach einer Prüfung gesperrt: die letzte Prüfung (heute) ist die Grenze.
        a = neuer_artikel(w, ids["hms"], lager, manufactured_on=f"{h.year - 2}-06")
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET created_at = ? WHERE id = ?", (f"{h.year - 2}-01-01T00:00:00+00:00", a["id"]))
        _sperren_nach_pruefung(p1, a["id"])
        aus = lambda datum: w.post(f"/api/material/artikel/{a['id']}/aussondern", json={"grund": "irreparabel", "datum": datum})  # noqa: E731
        # Zukunft und vor der Erfassung: wie bisher 400.
        assert aus((h + timedelta(days=1)).isoformat()).status_code == 400
        r = aus(f"{h.year - 3}-12-31")
        assert r.status_code == 400 and "Erfassung" in r.json["error"], r.get_json()
        # Vor der letzten abgeschlossenen Prüfung (heute): 409 mit beiden Daten im Klartext.
        r = aus(gestern)
        assert r.status_code == 409 and "letzten Prüfung" in r.json["error"], r.get_json()
        assert gestern[8:10] + "." in r.json["error"] and heute[8:10] + "." in r.json["error"], r.get_json()
        # Nichts davon hat ausgesondert.
        assert w.get(f"/api/material/artikel/{a['id']}").json["artikel"]["status"] == "gesperrt"
        # Am Tag der letzten Prüfung geht es.
        r = aus(heute)
        assert r.status_code == 200, r.get_json()
        assert r.json["artikel"]["status"] == "ausgesondert" and r.json["artikel"]["pruefungen"][0]["datum"] == heute, r.json["artikel"]["pruefungen"][0]
        # Metall ohne Prüfung, Herstelldatum als Monat (der erste Tag zählt): Verlust gemeldet, Aussonderung am Vortag 409.
        c = neuer_artikel(w, ids["hms"], lager, manufactured_on=f"{h.year - 2}-06", serial_no="C-1")
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET created_at = ? WHERE id = ?", (f"{h.year - 2}-01-01T00:00:00+00:00", c["id"]))
        assert p1.post(f"/api/material/artikel/{c['id']}/sperren", json={"grund": "verlust"}).status_code == 200
        r = w.post(f"/api/material/artikel/{c['id']}/aussondern", json={"grund": "verlust", "datum": f"{h.year - 2}-05-31"})
        assert r.status_code == 409 and "Herstelldatum" in r.json["error"] and f"01.06.{h.year - 2}" in r.json["error"], r.get_json()
        assert w.post(f"/api/material/artikel/{c['id']}/aussondern", json={"grund": "verlust", "datum": f"{h.year - 2}-06-01"}).status_code == 200
        # Textil ohne Prüfung, Herstelldatum als Tag: Verlust gemeldet, Aussonderung am Vortag der Herstellung 409, am Tag 200.
        b = neuer_artikel(w, ids["gurt"], lager, manufactured_on=f"{h.year - 1}-03-15")
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_item SET created_at = ? WHERE id = ?", (f"{h.year - 1}-01-01T00:00:00+00:00", b["id"]))
        assert p1.post(f"/api/material/artikel/{b['id']}/sperren", json={"grund": "verlust"}).status_code == 200
        r = w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "verlust", "datum": f"{h.year - 1}-03-14"})
        assert r.status_code == 409 and "Herstelldatum" in r.json["error"], r.get_json()
        r = w.post(f"/api/material/artikel/{b['id']}/aussondern", json={"grund": "verlust", "datum": f"{h.year - 1}-03-15"})
        assert r.status_code == 200, r.get_json()
    print("Aussonderungsdatum: Grenzen bestanden.")


if __name__ == "__main__":
    test_grenzen()
    print("Alle Tests zu den Grenzen des Aussonderungsdatums bestanden.")
