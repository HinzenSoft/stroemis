"""Set-Protokolle im Prüfdurchgang (Schritt 27, Wunsch vom 25.10.2026):  python tests/test_material_setprotokolle.py  oder
pytest

Eine Gliederung G mit Fahrzeug › Set A (darin „Tasche“ und das innere Set B), Set C, Lager › Set D (nur Ausgenommenes)
und Set E (leer); dazu ein gesperrter Artikel mit Herkunft A und einer, der während des Durchgangs in eine andere
Gliederung wandert. Durchgang über G regulär abschließen → 1 S + 3 T (A, B, C; F1 b: A enthält auch B; F2 b: D ohne
Geprüftes, E leer, kein T). Inhalt je PDF, Nummern, Prüfer, Haupt-PDF mit Zwischenzeilen und Verzeichnis (SHA-256 =
file_sha256), Journal; Durchgang für Set A → S + T(B); Abbruch → kein T; Fehler beim Rendern → nichts festgeschrieben,
keine Datei übrig. Schritt 27 (Tabelle, Trigger, wiederholbar, frisch = migriert), Ordner löschen 409, Prüfseite,
Nummernschutz, verwaiste_beiseite; Rechte (F4 a) je Rolle; Ordnerseite; ZIP des Durchgangs (F5 a) und Ordner-Export.

Alle Namen, Nummern und Ergebnisse hier sind Platzhalter."""
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, festschreiben, freigeben, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           neues_konto, pruef_formulare, starten, umgebung)
from test_material_antrag import _pdf_text  # noqa: E402
from test_material_set_rueckbau import _schema, _unterschied, abgewiesen, roh  # noqa: E402
from test_material_trennung import bis_schritt, endversion, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post, ordner_neu  # noqa: E402

API = "/api/material"


def pruefen(c, iid, rid):
    r = starten(c, iid, durchgang_id=rid)
    assert r.status_code in (200, 201), r.get_json()
    pr = r.json["pruefung"]
    r = festschreiben(c, pr["id"], ergebnis="einsatzbereit", maengel_gesehen=[m["id"] for m in pr["maengel"]])
    assert r.status_code == 200, r.get_json()


def ausnehmen(c, rid, iid, grund="Platzhalter nicht auffindbar"):
    r = c.post(f"{API}/durchgaenge/{rid}/ausnehmen", json={"item_id": iid, "grund": grund})
    assert r.status_code == 200, r.get_json()


def aufbau(tmp):
    app, k = umgebung(tmp)
    adm, w, p = k["adm"], k["wart"], k["pruefer"]
    ids = katalog_grund(adm)
    pruef_formulare(k["katalog"], ids)
    g, sys_g = gliederung(adm, "OG Setstadt")
    g2, _ = gliederung(adm, "OG Nachbarort")
    fz = ordner_neu(w, g, "Fahrzeug", "fahrzeug")
    a = ordner_neu(w, fz, "Rucksack A", "set")
    tasche = ordner_neu(w, a, "Tasche", "sonstiges")
    b = ordner_neu(w, a, "Beutel B", "set")
    c = ordner_neu(w, g, "Kiste C", "set")
    lager = ordner_neu(w, g, "Lager", "standort")
    d = ordner_neu(w, lager, "Kiste D", "set")
    e = ordner_neu(w, g, "Kiste E", "set")
    n = iter(range(1, 100))

    def art(fid):
        return neuer_artikel(w, ids["hms"], fid, serial_no=f"SP-{next(n):03d}")
    t = SimpleNamespace(app=app, k=k, adm=adm, w=w, p=p, ids=ids, g=g, sys_g=sys_g, g2=g2, fz=fz, a=a, tasche=tasche,
                        b=b, c=c, lager=lager, d=d, e=e)
    t.a1, t.a2, t.b1, t.c1, t.l1, t.d1, t.a3, t.a4 = (art(x) for x in (a, tasche, b, c, lager, d, a, a))
    # a4: gesperrt vor dem Durchgang – liegt in „Gesperrt“, Heimat bleibt A.
    r = p.post(f"{API}/artikel/{t.a4['id']}/sperren", json={"grund": "beschaedigung", "text": "Platzhalter"})
    assert r.status_code == 200, r.get_json()
    return t


def durchgang(t, fid, titel="Platzhalter-Durchgang"):
    r = t.w.post(f"{API}/durchgaenge", json={"folder_id": fid, "titel": titel})
    assert r.status_code == 201, r.get_json()
    return r.json["durchgang"]["id"]


def _haupt(tmp):
    """Der Durchgang über G, regulär abgeschlossen."""
    t = aufbau(tmp)
    rid = durchgang(t, t.g)
    for x in (t.a1, t.a2, t.b1, t.c1, t.l1):
        pruefen(t.p, x["id"], rid)
    ausnehmen(t.w, rid, t.d1["id"])
    ausnehmen(t.w, rid, t.a4["id"], "beim Hersteller (Platzhalter)")
    # a3 verlässt den Bereich (andere Gliederung) – nach_verschieben nimmt ihn mit Grund heraus.
    r = t.w.post(f"{API}/artikel/verschieben", json={"ids": [t.a3["id"]], "folder_id": t.g2})
    assert r.status_code == 200, r.get_json()
    d = t.w.get(f"{API}/durchgaenge/{rid}").json["durchgang"]
    assert d["set_ordner"] == {"anzahl": 4, "mit_pruefung": 3}, d["set_ordner"]
    r = t.w.post(f"{API}/durchgaenge/{rid}/abschliessen", json={})
    assert r.status_code == 200, r.get_json()
    t.rid, t.antwort = rid, r.json["durchgang"]
    return t


def _set_zeilen(t, rid):
    return {z["folder_id"]: z for z in zeilen(t.app, "SELECT * FROM mat_round_setprotokoll WHERE round_id = ? ORDER BY id",
                                               (rid,))}


def _datei(t, rel):
    with open(os.path.join(t.app.config["DATA_DIR"], rel), "rb") as fh:
        return fh.read()


def test_abschluss():
    """1 S + 3 T, Inhalt je PDF nach F1 b, Nummern T-<jahr>-<nr>, Prüfer je Set, Haupt-PDF mit Zwischenzeilen und
    Verzeichnis, Journal, Antwort der Schnittstelle."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = _haupt(tmp)
        s = _set_zeilen(t, t.rid)
        assert set(s) == {t.a, t.b, t.c}, s
        assert (s[t.a]["artikel"], s[t.b]["artikel"], s[t.c]["artikel"]) == (4, 1, 1)
        jahr = s[t.a]["protocol_id"].split("-")[1]
        assert [z["protocol_id"] for z in sorted(s.values(), key=lambda z: z["id"])] == \
            [f"T-{jahr}-{n:06d}" for n in (1, 2, 3)]
        runde = zeilen(t.app, "SELECT * FROM mat_round WHERE id = ?", (t.rid,))[0]
        for z in s.values():
            daten = _datei(t, z["pdf_path"])
            assert hashlib.sha256(daten).hexdigest() == z["file_sha256"]
        text_a = _pdf_text(_datei(t, s[t.a]["pdf_path"]))
        for x in (t.a1, t.a2, t.b1, t.a4):
            assert x["inventory_no"] in text_a, x["inventory_no"]
        for x in (t.c1, t.l1, t.d1, t.a3):
            assert x["inventory_no"] not in text_a, x["inventory_no"]
        flach = " ".join(text_a.split())
        assert f"Teil von Sammelprotokoll {runde['protocol_id']}" in flach and "Prüfer in diesem Set" in flach, flach[:600]
        assert "Artikel im Set" in flach and "Set Rucksack A" in flach
        # Innere Sets haben in A eine Zwischenzeile mit ihrem Protokoll.
        assert f"Beutel B · 1 Artikel · Set-Protokoll {s[t.b]['protocol_id']}" in flach, flach
        text_b = " ".join(_pdf_text(_datei(t, s[t.b]["pdf_path"])).split())
        assert t.b1["inventory_no"] in text_b and t.a1["inventory_no"] not in text_b
        # Haupt-PDF: alle Artikel, Zwischenzeilen, Verzeichnis der Set-Protokolle mit SHA-256.
        haupt = " ".join(_pdf_text(_datei(t, runde["pdf_path"])).split())
        for x in (t.a1, t.a2, t.b1, t.c1, t.l1, t.d1, t.a3, t.a4):
            assert x["inventory_no"] in haupt, x["inventory_no"]
        assert "Set-Protokolle dieses Durchgangs" in haupt
        for z in s.values():
            assert z["protocol_id"] in haupt and z["file_sha256"][:20] in haupt.replace(" ", ""), z["protocol_id"]
        assert "Kiste D · 1 Artikel · kein Set-Protokoll (nichts geprüft)" in haupt, haupt
        # Zusammenhängend: die Zeilen des Sets A (mit Tasche und B) stehen hintereinander.
        pos = sorted((haupt.index(x["inventory_no"]), x["inventory_no"]) for x in (t.a1, t.a2, t.b1, t.a4, t.c1, t.l1))
        block = [nr for _, nr in pos]
        a_nrn = {x["inventory_no"] for x in (t.a1, t.a2, t.b1, t.a4)}
        innen = [i for i, nr in enumerate(block) if nr in a_nrn]
        assert innen == list(range(innen[0], innen[0] + 4)), block
        # Journal und Schnittstelle.
        j = zeilen(t.app, "SELECT after_json FROM mat_audit WHERE entity = 'round' AND entity_id = ? "
                          "AND action = 'festgeschrieben'", (t.rid,))
        nachher = json.loads(j[0]["after_json"])
        assert {x["protocol_id"] for x in nachher["set_protokolle"]} == {z["protocol_id"] for z in s.values()}
        assert len(t.antwort["set_protokolle"]) == 3
        d = t.w.get(f"{API}/durchgaenge/{t.rid}").json["durchgang"]
        x = next(x for x in d["set_protokolle"] if x["folder_id"] == t.a)
        assert x["artikel"] == 4 and x["ordner_sichtbar"] is True and x["protokoll"]["id"] == s[t.a]["protocol_id"]
        assert x["protokoll"]["url"] == f"/material/durchgang/{t.rid}/set/{s[t.a]['id']}.pdf"
        assert t.w.get(x["protokoll"]["url"]).status_code == 200
    print("Abschluss mit Set-Protokollen bestanden.")


def test_set_als_durchgang_abbruch_und_fehler():
    """Ein Durchgang für Set A: S + T(B) (A selbst hat sein Sammelprotokoll). Abbruch: kein T. Fehler beim Rendern eines
    T: nichts festgeschrieben, keine neue Datei."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        rid = durchgang(t, t.a, "Platzhalter Set A")
        for x in (t.a1, t.a2, t.b1):
            pruefen(t.p, x["id"], rid)
        ausnehmen(t.w, rid, t.a3["id"])
        ausnehmen(t.w, rid, t.a4["id"])
        assert t.w.post(f"{API}/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
        assert set(_set_zeilen(t, rid)) == {t.b}
        # Abbruch nach einer Prüfung in C: das Sammelprotokoll ja, ein Set-Protokoll nicht (F2 b).
        rid2 = durchgang(t, t.g, "Platzhalter Abbruch")
        pruefen(t.p, t.c1["id"], rid2)
        r = t.w.post(f"{API}/durchgaenge/{rid2}/abbrechen", json={})
        assert r.status_code == 200 and r.json["durchgang"]["protokoll"], r.get_json()
        assert _set_zeilen(t, rid2) == {} and r.json["durchgang"]["set_protokolle"] == []
        haupt = " ".join(_pdf_text(t.w.get(f"/material/durchgang/{rid2}/sammelprotokoll").data).split())
        assert "kein Set-Protokoll (Durchgang abgebrochen)" in haupt
        # Fehler beim Rendern eines Set-Protokolls.
        rid4 = durchgang(t, t.lager, "Platzhalter Lager")
        pruefen(t.p, t.l1["id"], rid4)
        pruefen(t.p, t.d1["id"], rid4)
        from app.material.services import pdf
        echt = pdf.rendern

        def kaputt(vorlage, daten):
            if vorlage == "setprotokoll":
                raise RuntimeError("Platzhalter-Fehler")
            return echt(vorlage, daten)
        vorher = sorted(os.listdir(os.path.join(tmp, "pdf", os.listdir(os.path.join(tmp, "pdf"))[0])))
        pdf.rendern = kaputt
        try:
            r = t.w.post(f"{API}/durchgaenge/{rid4}/abschliessen", json={})
        finally:
            pdf.rendern = echt
        assert r.status_code == 500 and "nichts wurde festgeschrieben" in r.json["error"], r.get_json()
        nachher = sorted(os.listdir(os.path.join(tmp, "pdf", os.listdir(os.path.join(tmp, "pdf"))[0])))
        assert nachher == vorher
        runde = zeilen(t.app, "SELECT closed_on, locked_at FROM mat_round WHERE id = ?", (rid4,))[0]
        assert runde == {"closed_on": None, "locked_at": None} and _set_zeilen(t, rid4) == {}
        assert t.w.post(f"{API}/durchgaenge/{rid4}/abschliessen", json={}).status_code == 200
        assert set(_set_zeilen(t, rid4)) == {t.d}
    print("Set als Durchgang, Abbruch und Fehler bestanden.")


def test_schritt_27():
    """Frisch: Tabelle, Index, Trigger. 26 → 27: die Tabelle kommt dazu, sonst nichts; zweiter Lauf ändert nichts; frisch
    = migriert. Trigger: Einfügen nur beim Festschreiben eines regulär abgeschlossenen Durchgangs, nie ändern, löschen
    oder ersetzen."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("table", "mat_round_setprotokoll") in schema_frisch
    for name in ("mat_setprotokoll_neu", "mat_setprotokoll_aendern", "mat_setprotokoll_loeschen"):
        assert ("trigger", name) in schema_frisch, name
    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(26)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "26"
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_round_setprotokoll'").fetchone()
        conn.close()
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        conn = sqlite3.connect(pfad)
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_27(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = _haupt(tmp)
        offen = durchgang(t, t.c, "Platzhalter offen")
        z = _set_zeilen(t, t.rid)[t.a]
        conn = roh(t.app)
        try:
            text = "Set-Protokoll entsteht nur"
            einfuegen = ("INSERT INTO mat_round_setprotokoll (round_id, folder_id, ordner, artikel, protocol_id, locked_at, "
                         "pdf_path, pdf_sha256, pdf_hashed_bytes, file_sha256) VALUES (?, ?, 'x', 1, ?, 'x', 'x', 'x', 1, 'x')")
            abgewiesen(conn, einfuegen, (offen, t.c, "T-2099-000099"), text)
            abgewiesen(conn, einfuegen, (t.rid, t.e, "T-2099-000098"), text)          # schon festgeschrieben
            abgewiesen(conn, "UPDATE mat_round_setprotokoll SET artikel = 9 WHERE id = ?", (z["id"],), text)
            abgewiesen(conn, "DELETE FROM mat_round_setprotokoll WHERE id = ?", (z["id"],), text)
            abgewiesen(conn, "INSERT OR REPLACE INTO mat_round_setprotokoll (id, round_id, folder_id, ordner, artikel, "
                       "protocol_id, locked_at, pdf_path, pdf_sha256, pdf_hashed_bytes, file_sha256) VALUES "
                       "(?, ?, ?, 'x', 1, 'T-2099-000097', 'x', 'x', 'x', 1, 'x')", (z["id"], t.rid, t.a), text)
        finally:
            conn.close()
        # Ordner löschen: ein Set mit Set-Protokoll bleibt (409), auch leer.
        r = t.w.post(f"{API}/artikel/verschieben", json={"ids": [t.c1["id"]], "folder_id": t.lager})
        assert r.status_code == 200, r.get_json()
        assert t.w.delete(f"{API}/durchgaenge/{offen}", headers=H).status_code == 200
        r = t.w.delete(f"{API}/ordner/{t.c}", headers=H)
        assert r.status_code == 409 and "Set-Protokolle" in r.json["error"], r.get_json()
        assert t.w.delete(f"{API}/ordner/{t.e}", headers=H).status_code == 200      # ohne Protokoll geht es
    print("Schritt 27 bestanden.")


def test_pruefseite_und_ablage():
    """Prüfseite erkennt T (unverändert, verändert); _nummern_schuetzen hebt den Zähler der Tabelle; verwaiste_beiseite
    lässt T-Dateien liegen."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = _haupt(tmp)
        z = _set_zeilen(t, t.rid)[t.a]
        original = _datei(t, z["pdf_path"])
        anon = t.app.test_client()

        def pruefen_(daten):
            r = anon.post(f"{API}/pruefen", data={"datei": (io.BytesIO(daten), "protokoll.pdf")}, headers=H,
                          content_type="multipart/form-data")
            assert r.status_code == 200, r.get_json()
            return r.json
        e = pruefen_(original)
        assert e == {"ergebnis": "unveraendert", "protokoll_id": z["protocol_id"], "art": "Sammelprotokoll (Set)",
                     "hinweis": e["hinweis"]}, e
        kopie = bytearray(original)
        kopie[len(kopie) // 3] ^= 1
        e = pruefen_(bytes(kopie))
        assert e["ergebnis"] == "veraendert" and e["protokoll_id"] == z["protocol_id"], e
        # Zähler zurückgesetzt (Sicherung zurückgespielt) → der Start hebt ihn; die Dateien bleiben liegen.
        conn = sqlite3.connect(t.app.config["DB_PATH"])
        with conn:
            conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'mat_round_setprotokoll'")
        conn.close()
        with t.app.app_context():
            from app import db
            from app.material.services import protokoll
            protokoll.verwaiste_beiseite(db.get_db())
        assert zeilen(t.app, "SELECT seq FROM sqlite_sequence WHERE name = 'mat_round_setprotokoll'")[0]["seq"] == 3
        assert _datei(t, z["pdf_path"]) == original
        assert not os.path.isdir(os.path.join(tmp, "pdf", "verwaist"))
    print("Prüfseite und Ablage bestanden.")


def test_rechte_ordnerseite_und_zip():
    """F4 a: Leser nur am Set A → T(A) und T(B) (B liegt in A) ja, T(C), S und ZIP 404; Leser am Durchgang → alles;
    fremde Gliederung 404; ohne Modul 403. Ordnerseite des Sets: „sammelprotokolle“. ZIP des Durchgangs (F5 a): S, alle
    T, Verzeichnis.csv; Ordner-Export von A mit T(A) und T(B)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = _haupt(tmp)
        s = _set_zeilen(t, t.rid)
        url = {fid: f"/material/durchgang/{t.rid}/set/{z['id']}.pdf" for fid, z in s.items()}
        haupt_url, zip_url = f"/material/durchgang/{t.rid}/sammelprotokoll", f"/material/durchgang/{t.rid}/protokolle.zip"
        leser, leser_id = neues_konto(t.app, "leser_set@example.org", name="Leser Set")
        freigeben(t.adm, t.a, leser_id, "lesen")
        assert leser.get(url[t.a]).status_code == 200 and leser.get(url[t.b]).status_code == 200
        for u in (url[t.c], haupt_url, zip_url, f"/material/durchgang/{t.rid}/set/{s[t.a]['id'] + 99}.pdf",
                  f"/material/durchgang/{t.rid + 1}/set/{s[t.a]['id']}.pdf"):
            assert leser.get(u).status_code == 404, u
        assert leser.get(f"{API}/durchgaenge/{t.rid}").status_code == 404
        f = t.k["fuehrung"]
        for u in list(url.values()) + [haupt_url, zip_url]:
            assert f.get(u).status_code == 200, u
        fremd, fremd_id = neues_konto(t.app, "fremd_set@example.org", name="Fremd")
        freigeben(t.adm, t.g2, fremd_id, "lesen")
        for u in list(url.values()) + [zip_url]:
            assert fremd.get(u).status_code == 404, u
        assert t.k["nutzer"].get(url[t.a]).status_code == 403
        # Ordnerseite des Sets A (als Leser): sein Set-Protokoll; ohne Link zum Durchgang.
        o = leser.get(f"{API}/ordner/{t.a}").json["ordner"]
        assert [(x["art"], x["protokoll"]["id"], x["durchgang"]["sichtbar"]) for x in o["sammelprotokolle"]] == \
            [("set", s[t.a]["protocol_id"], False)], o["sammelprotokolle"]
        assert "sammelprotokolle" not in t.w.get(f"{API}/ordner/{t.lager}").json["ordner"]
        # ZIP des Durchgangs.
        r = f.get(zip_url)
        z = zipfile.ZipFile(io.BytesIO(r.data))
        namen = z.namelist()
        assert "Verzeichnis.csv" in namen and len([n for n in namen if n.endswith(".pdf")]) == 4, namen
        verzeichnis = z.read("Verzeichnis.csv").decode("utf-8-sig")
        assert verzeichnis.count("Sammelprotokoll (Set)") == 3 and "unverändert" in verzeichnis
        # Ordner-Export von A: T(A) und T(B).
        r = t.w.get(f"/material/export/{t.a}-protokolle.zip")
        z = zipfile.ZipFile(io.BytesIO(r.data))
        texte = " ".join(z.namelist())
        assert s[t.a]["protocol_id"] in texte and s[t.b]["protocol_id"] in texte and s[t.c]["protocol_id"] not in texte
        assert z.read("Verzeichnis.csv").decode("utf-8-sig").count("Sammelprotokoll (Set)") == 2
        ziel = os.environ.get("SETPROTOKOLL_ABLAGE")              # für bin/st-vera (PDF/A) – nur, wenn angegeben
        if ziel:
            with open(ziel + "-T.pdf", "wb") as fh:
                fh.write(f.get(url[t.a]).data)
            with open(ziel + "-S.pdf", "wb") as fh:
                fh.write(f.get(haupt_url).data)
    print("Rechte, Ordnerseite und ZIP bestanden.")


def test_oberflaeche_statisch():
    """Durchgangsseite: „Alle Protokolle (ZIP)“ als grauer Knopf, Liste der Set-Protokolle, Satz und Rückfrage mit der
    Zahl der Sets; Ordnerseite mit „Sammelprotokolle“; Beschriftung des Journalfelds in beiden Sprachen."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    assert '<a class="btn secondary" href="/material/durchgang/${d.id}/protokolle.zip">Alle Protokolle (ZIP)</a>' in js
    assert "function setProtokolleHtml(liste)" in js and "function sammelprotokolleHtml(liste)" in js
    assert "<h2>Set-Protokolle</h2>" in js and "<h2>Sammelprotokolle</h2>" in js
    assert 'plural(sets, "Set-Protokoll", "Set-Protokolle")' in js
    from app.material.services import beschriftung
    assert f'set_protokolle: "{beschriftung.FELD["set_protokolle"]}"' in js
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_abschluss()
    test_set_als_durchgang_abbruch_und_fehler()
    test_schritt_27()
    test_pruefseite_und_ablage()
    test_rechte_ordnerseite_und_zip()
    test_oberflaeche_statisch()
    print("Alle Tests der Set-Protokolle bestanden.")
