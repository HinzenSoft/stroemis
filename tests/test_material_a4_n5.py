"""A4 „Aussonderung empfohlen“ als Statusfilter und Übersichtszahl, N5 Mail an die Material-Verwaltung bei Anträgen
ohne Materialwart (Wünsche des Nutzers vom 25.10.2026):  python tests/test_material_a4_n5.py  oder pytest

A4: Zählung je Recht und Gliederung (Materialwart je Gliederung, Prüfer und Leser ohne, Material-Verwaltung alles), der
Filter im „Gesperrt“-Ordner samt Zahlen und Kategorien. N5: alle vier Auslöser (Freigabe entziehen, Ablauf über den
Tageslauf, Konto deactivieren, Konto löschen), Einmaligkeit und erneute Meldung nach einem neuen Wegfall, keine Mail ohne
offenen Antrag, nur an die Material-Verwaltung, kein Antragsinhalt; Schritt 29. Alles Platzhalter."""
import os
import sqlite3
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, freigeben, gliederung, katalog_grund, make_app,  # noqa: E402
                           mails_abfangen, mails_zurueck, neuer_artikel, neues_konto, pruef_formulare, starten,
                           umgebung)
from test_material_trennung import bis_schritt, endversion, zeilen  # noqa: E402
from test_material_set_rueckbau import _schema, _unterschied  # noqa: E402

API = "/api/material"


def _geprueft(t, iid, ergebnis="einsatzbereit", grund=""):
    r = starten(t.p, iid)
    assert r.status_code in (200, 201), r.get_json()
    d = {"ergebnis": ergebnis}
    if grund:
        d["grund"] = grund
    r = festschreiben(t.p, r.json["pruefung"]["id"], **d)
    assert r.status_code == 200, r.get_json()


class T:
    pass


def aufbau(tmp):
    t = T()
    t.app, k = umgebung(tmp)
    t.k, t.adm, t.w, t.p, t.mv = k, k["adm"], k["wart"], k["pruefer"], k["katalog"]
    t.ids = katalog_grund(t.adm)
    pruef_formulare(k["katalog"], t.ids)
    t.ga, t.sys_a = gliederung(t.adm, "OG Nordstadt")
    # Eine zweite Gliederung mit eigenem Materialwart (die Testkonten haben dort keine Freigaben).
    t.gb, t.sys_b = gliederung(t.adm, "OG Südstadt", standard=False)
    t.wart_b, t.wart_b_id = neues_konto(t.app, "wart_b@example.org")
    freigeben(t.adm, t.gb, t.wart_b_id, "verwalten")
    freigeben(t.adm, t.gb, k["pruefer_id"], "lesen")
    freigeben(t.adm, t.gb, k["pruefer_id"], "pruefen")
    return t


def test_a4_zaehlung_und_filter():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="A4-1")["id"]
        a2 = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="A4-2")["id"]
        a3 = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="A4-3")["id"]
        b1 = neuer_artikel(t.wart_b, t.ids["hms"], t.gb, serial_no="A4-B1")["id"]
        _geprueft(t, a1, "aussondern_empfohlen", "Platzhalter")
        _geprueft(t, a2, "instandsetzen", "Platzhalter")              # gesperrt, aber keine Empfehlung
        _geprueft(t, a3, "aussondern_empfohlen", "Platzhalter")
        _geprueft(t, b1, "aussondern_empfohlen", "Platzhalter")

        def zahl(c):
            return [(x["ordner_id"], x["gliederung"], x["anzahl"]) for x in c.get(f"{API}/start").json["aussonderung_empfohlen"]]
        assert zahl(t.w) == [(t.sys_a["gesperrt"], "OG Nordstadt", 2)]
        assert zahl(t.wart_b) == [(t.sys_b["gesperrt"], "OG Südstadt", 1)]
        assert zahl(t.mv) == [(t.sys_a["gesperrt"], "OG Nordstadt", 2), (t.sys_b["gesperrt"], "OG Südstadt", 1)]
        assert zahl(t.p) == [] and zahl(t.k["fuehrung"]) == []            # prüfen bzw. lesen: kein Aussondern
        # Filter im „Gesperrt“-Ordner: nur die Empfehlungen, mit Zahl und Kategorien unter dem Filter.
        url = f"{API}/ordner/{t.sys_a['gesperrt']}"
        o = t.w.get(url).json["ordner"]
        assert o["empfohlen"] == 2 and o["artikel_gesamt"] == 3, o["artikel_gesamt"]
        o = t.w.get(f"{url}?status=aussonderung_empfohlen").json["ordner"]
        assert sorted(x["id"] for x in o["artikel"]) == [a1, a3] and o["artikel_gesamt"] == 2
        assert all(x["aussonderung_empfohlen"] for x in o["artikel"])
        assert sum(k["n"] for k in o["kategorien"]) == 2
        (kat_hms,) = [k["id"] for k in t.w.get(url).json["ordner"]["kategorien"]]               # alle Karabiner
        o = t.w.get(f"{url}?status=aussonderung_empfohlen&kategorie={kat_hms}").json["ordner"]
        assert sorted(x["id"] for x in o["artikel"]) == [a1, a3] and o["empfohlen"] == 2
        o = t.w.get(f"{url}?status=aussonderung_empfohlen&kategorie={kat_hms + 999}").json["ordner"]
        assert o["artikel"] == [] and o["empfohlen"] == 0
        assert t.w.get(f"{url}?status=unsinn").status_code == 400
        # Der Leser sieht den Filter auch (Zahl wie die Liste), aussondern darf er nicht – auf der Übersicht nichts.
        assert t.k["fuehrung"].get(url).json["ordner"]["empfohlen"] == 2
        # Nach dem Aussondern fällt der Artikel heraus.
        assert t.w.post(f"{API}/artikel/{a1}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        assert zahl(t.w) == [(t.sys_a["gesperrt"], "OG Nordstadt", 1)]
    print("A4 bestanden.")


def _antrag(t, iid, c=None):
    r = (c or t.p).post(f"{API}/artikel/{iid}/antrag", json={"serial_no": f"NEU-{iid}", "begruendung": "Geheimgrund Platzhalter"})
    assert r.status_code == 201, r.get_json()
    return r.json


def _grant(t, fid, uid, recht="verwalten"):
    return zeilen(t.app, "SELECT id FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = ?",
                  (fid, uid, recht))[0]["id"]


def test_n5_ausloeser_und_einmaligkeit():
    from app.material.services import antrag, erinnerung
    post = []
    alt = mails_abfangen(antrag, lambda an, betreff, text: post.append((an, betreff, text)) or True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            t = aufbau(tmp)
            mv_mail = "katalog@example.org"
            fach = t.w.post(f"{API}/ordner", json={"name": "Fach Platzhalter", "kind": "standort", "parent_id": t.ga})
            fach = fach.json["ordner"]["id"]
            a1 = neuer_artikel(t.w, t.ids["hms"], fach, serial_no="N5-1")["id"]
            a2 = neuer_artikel(t.w, t.ids["hms"], fach, serial_no="N5-2")["id"]
            _geprueft(t, a1)
            _geprueft(t, a2)
            # Ein zweiter Materialwart nur am Fach – er ist der letzte, wenn die Gliederung keinen mehr hat.
            fw, fw_id = neues_konto(t.app, "fachwart@example.org")
            freigeben(t.adm, fach, fw_id, "verwalten")
            _antrag(t, a1)
            _antrag(t, a2)
            post.clear()
            # Entziehen: die Gliederungsfreigabe des Materialwarts – das Fach hat noch einen, keine Mail.
            r = t.adm.delete(f"{API}/freigaben/{_grant(t, t.ga, t.k['wart_id'])}", headers=H)
            assert r.status_code == 200 and r.json["mail"] is False and post == [], (r.get_json(), post)
            # Die letzte (am Fach): Mail an die Material-Verwaltung – einmal, mit Ordner und Zahl, ohne Inhalte.
            r = t.adm.delete(f"{API}/freigaben/{_grant(t, fach, fw_id)}", headers=H)
            assert r.status_code == 200 and r.json["mail"] is True, r.get_json()
            assert [x[0] for x in post] == [mv_mail], post
            betreff, text = post[0][1], post[0][2]
            assert "ohne Materialwart" in betreff and "OG Nordstadt / Fach Platzhalter" in text
            assert "2 offene Änderungsanträge" in text and "NEU-" not in text and "Geheimgrund" not in text
            assert "pruefer" not in text and "fachwart" not in text
            # Einmaligkeit: ein weiterer Vorgang meldet nichts neu.
            post.clear()
            r = t.adm.delete(f"{API}/freigaben/{_grant(t, t.ga, t.k['fuehrung_id'], 'lesen')}", headers=H)
            assert r.json["mail"] is False and post == []
            # Wieder ein Verwalter, dann deaktiviert: erneut eine Mail.
            freigeben(t.adm, fach, fw_id, "verwalten")
            r = t.adm.post(f"{API}/ordner/{fach}/freigaben", json={"user_id": fw_id, "grundrecht": "verwalten"})
            assert r.status_code == 201 and r.json["mail"] is False, r.get_json()   # meldet nichts, räumt die Zeile ab
            assert not zeilen(t.app, "SELECT 1 FROM mat_antrag_ohne_verwalter")
            r = t.adm.put(f"/api/admin/users/{fw_id}", json={"active": False})
            assert r.status_code == 200 and r.json["mail"] is True and len(post) == 1, (r.get_json(), post)
            # Wieder aktiv, dann gelöscht: erneut.
            post.clear()
            r = t.adm.put(f"/api/admin/users/{fw_id}", json={"active": True})
            assert r.json["mail"] is False
            assert not zeilen(t.app, "SELECT 1 FROM mat_antrag_ohne_verwalter")
            r = t.adm.delete(f"/api/admin/users/{fw_id}", headers=H)
            assert r.status_code == 200 and r.json["mail"] is True and len(post) == 1, (r.get_json(), post)
            # Ablauf einer befristeten Freigabe: über den Tageslauf.
            post.clear()
            neu, neu_id = neues_konto(t.app, "fachwart2@example.org")
            gestern = (_heute() - timedelta(days=1)).isoformat()
            r = t.adm.post(f"{API}/ordner/{fach}/freigaben", json={"user_id": neu_id, "grundrecht": "verwalten",
                                                                   "grund_bis": (_heute() + timedelta(days=5)).isoformat()})
            assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
            sql = sqlite3.connect(t.app.config["DB_PATH"])
            with sql:
                sql.execute("UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ?", (gestern, neu_id))
            sql.close()
            with t.app.app_context():
                out = erinnerung.tageslauf(ausloeser="Test")
            assert out["pflege"]["ohne_verwalter"] is True and len(post) == 1, (out, post)
            with t.app.app_context():
                assert antrag.ohne_verwalter_melden() is False                 # zweiter Lauf: nichts
            assert len(post) == 1
            # Kein Versand ohne offenen Antrag: in Gliederung B ohne Antrag die einzige Verwalterfreigabe entziehen.
            post.clear()
            r = t.adm.delete(f"{API}/freigaben/{_grant(t, t.gb, t.wart_b_id)}", headers=H)
            assert r.json["mail"] is False and post == []
    finally:
        mails_zurueck(alt)
    print("N5 bestanden.")


def test_n5_antrag_ohne_zustaendige_einmal():
    """Ein Antrag, für den es schon beim Stellen keinen Materialwart gibt, geht mit seiner Mail an die
    Material-Verwaltung – das zählt als Meldung: Ein späterer Vorgang meldet den Ordner nicht ein zweites Mal."""
    from app.material.services import antrag
    post = []
    alt = mails_abfangen(antrag, lambda an, betreff, text: post.append((an, betreff)) or True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            t = aufbau(tmp)
            b1 = neuer_artikel(t.wart_b, t.ids["hms"], t.gb, serial_no="N5-B1")["id"]
            _geprueft(t, b1)
            assert t.adm.delete(f"{API}/freigaben/{_grant(t, t.gb, t.wart_b_id)}", headers=H).json["mail"] is False
            post.clear()
            _antrag(t, b1)
            assert [x[0] for x in post] == ["katalog@example.org"] and "Änderungsantrag" in post[0][1], post
            post.clear()
            r = t.adm.delete(f"{API}/freigaben/{_grant(t, t.gb, t.k['pruefer_id'], 'lesen')}", headers=H)
            assert r.json["mail"] is False and post == []
    finally:
        mails_zurueck(alt)
    print("Antrag ohne Zuständige bestanden.")


def test_schritt_29():
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("table", "mat_antrag_ohne_verwalter") in schema_frisch
    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(28)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_antrag_ohne_verwalter'").fetchone()
        conn.close()
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        from app.material import models
        conn = sqlite3.connect(pfad)
        n = conn.total_changes
        for sql in models.SCHRITT_29:
            conn.execute(sql)
        assert conn.total_changes == n
        conn.close()
    print("Schritt 29 bestanden.")


def test_oberflaeche_statisch():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    assert 'const EMPFOHLEN = "aussonderung_empfohlen";' in js
    assert ".concat(d.empfohlen || filter === EMPFOHLEN ? [EMPFOHLEN] : [])" in js
    assert "${empfohlenHinweis(d.aussonderung_empfohlen)}" in js and "function empfohlenHinweis(liste)" in js
    assert '`<a href="/material/ordner/${Number(x.ordner_id)}?status=${EMPFOHLEN}">${text}</a>`' in js
    assert "vorgabeStatus === EMPFOHLEN" in js
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_a4_zaehlung_und_filter()
    test_n5_ausloeser_und_einmaligkeit()
    test_n5_antrag_ohne_zustaendige_einmal()
    test_schritt_29()
    test_oberflaeche_statisch()
    print("Alle Tests zu A4 und N5 bestanden.")
