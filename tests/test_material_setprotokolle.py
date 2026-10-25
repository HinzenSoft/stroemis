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

from test_material import (H, anmelden, festschreiben, freigeben, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, neues_konto, pruef_formulare, starten, umgebung)
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
        assert e == {"ergebnis": "unveraendert", "protokoll_id": z["protocol_id"], "art": "Set-Protokoll",
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
        assert verzeichnis.count(";Set-Protokoll;") == 3 and "unverändert" in verzeichnis
        # Das Set steht in der eigenen Spalte „Set“, nicht unter „Grund“ (Browserprüfung vom 25.10.2026).
        import csv
        reihen = list(csv.DictReader(io.StringIO(verzeichnis), delimiter=";"))
        t_a = next(x for x in reihen if x["Protokoll-ID"] == s[t.a]["protocol_id"])
        assert t_a["Set"] == "OG Setstadt › Fahrzeug › Rucksack A" and t_a["Grund"] == "" and t_a["Art"] == "Set-Protokoll"
        assert all(x["Set"] == "" for x in reihen if x["Art"] == "Sammelprotokoll")
        assert sorted(n for n in namen if n.endswith(".pdf"))[0].startswith("Sammelprotokolle/")
        assert all(n.startswith("Set-Protokolle/") for n in namen if "/T-" in n)
        kopf = r.headers["Content-Disposition"]
        assert kopf.startswith('attachment; filename="Protokolle_Platzhalter-Durchgang_S-') and "filename*=UTF-8''" in kopf
        # Ordner-Export von A: T(A) und T(B).
        r = t.w.get(f"/material/export/{t.a}-protokolle.zip")
        z = zipfile.ZipFile(io.BytesIO(r.data))
        texte = " ".join(z.namelist())
        assert s[t.a]["protocol_id"] in texte and s[t.b]["protocol_id"] in texte and s[t.c]["protocol_id"] not in texte
        assert f"Set-Protokolle/{s[t.a]['protocol_id'].split('-')[1]}/{s[t.a]['protocol_id']}.pdf" in z.namelist()
        assert z.read("Verzeichnis.csv").decode("utf-8-sig").count(";Set-Protokoll;") == 2
        ziel = os.environ.get("SETPROTOKOLL_ABLAGE")              # für bin/st-vera (PDF/A) – nur, wenn angegeben
        if ziel:
            with open(ziel + "-T.pdf", "wb") as fh:
                fh.write(f.get(url[t.a]).data)
            with open(ziel + "-S.pdf", "wb") as fh:
                fh.write(f.get(haupt_url).data)
    print("Rechte, Ordnerseite und ZIP bestanden.")


def test_oberflaeche_statisch():
    """Durchgangsseite: „Alle Protokolle (ZIP)“ als grauer Knopf, Liste der Set-Protokolle, Satz und Rückfrage mit der
    Zahl der Sets; Ordnerseite mit „Set-Protokolle“ bzw. „Sammelprotokolle“; Beschriftung des Journalfelds in beiden
    Sprachen. Nachbesserung (25.10.2026): „bis zu n“, Abbruch-Rückfrage mit „Zurück“ und dem Satz zu den
    Set-Protokollen, PDF-Links mit eigenem Namen, Prüfsummen-Linie am Text."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    assert '<a class="btn secondary" href="/material/durchgang/${d.id}/protokolle.zip">Alle Protokolle (ZIP)</a>' in js
    assert "function setProtokolleHtml(liste)" in js and "function sammelprotokolleHtml(liste)" in js
    assert "<h2>Set-Protokolle</h2>" in js and "<h2>${sammelprotokolleTitel(d.sammelprotokolle)}</h2>" in js
    assert '"Set- und Sammelprotokolle" : arten.has("Set-Protokoll") ? "Set-Protokolle" : "Sammelprotokolle"' in js
    assert 'plural(sets, "Set-Protokoll", "Set-Protokolle")' in js
    assert "hier bis zu ${d.set_ordner.anzahl}" in js and "(hier ${plural(" not in js
    assert 'confirm(text + weiter, "Durchgang abbrechen", "Zurück")' in js
    assert "Set-Protokolle entstehen dabei keine – nur beim Abschließen." in js
    assert 'aria-label="Set-Protokoll ${esc(t.protokoll.id)} (PDF)"' in js
    assert "einzelner Stücke" in js and "einzelner Stück " not in js
    assert '<span class="mat-summe-text">' in js
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    assert ".mat-summe-text { border-bottom: 1px dashed var(--grau); }" in css
    common = open(os.path.join(wurzel, "app/static/js/common.js"), encoding="utf-8").read()
    assert "function confirm(text, okLabel, neinLabel)" in common and '${esc(neinLabel || "Abbrechen")}' in common
    from app.material.services import beschriftung
    assert f'set_protokolle: "{beschriftung.FELD["set_protokolle"]}"' in js
    print("Oberfläche (statisch) bestanden.")


def _zwischen(app, rid, wurzel=None):
    """Die Zwischenzeilen je Artikel (Inventarnummer → Liste der Texte) im Sammel- bzw. Set-Protokoll."""
    with app.test_request_context():
        from app import db
        from app.material.services import protokoll
        r = db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
        d = protokoll._sammelprotokoll(r, "X", r["locked_at"], wurzel=wurzel,
                                       haupt={"protokoll_id": "S", "ordner": "G"} if wurzel else None,
                                       je_set={z["folder_id"]: {"protokoll_id": z["protocol_id"], "kennung": z["id"]}
                                               for z in protokoll.set_protokolle(rid)})
        return [(a["inventarnummer"], a["zwischen"], a["im_set"]) for a in d["artikel"]]


def test_zwischenzeilen():
    """Ablauf B1 = Browser 1: Zwischenzeilen nach der ganzen Kette der Sets. Proben b3/b4 der Ablaufprüfung (Set nur mit
    innerem Set, erster Artikel im inneren Set über einen Unterordner, Artikel ohne Set nach einem Set-Block, dasselbe im
    Set-Protokoll des äußeren Sets) und der Fall aus Browser S-2.png (Artikel nach einem inneren Set); „n Artikel“ zählt
    genau die Zeilen darunter."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p = k["wart"], k["pruefer"]
        g, _ = gliederung(k["adm"], "OG Zeilen")
        f1 = ordner_neu(w, g, "Fahrzeug 1", "fahrzeug")
        rr = ordner_neu(w, f1, "Rucksack R", "set")
        rb = ordner_neu(w, rr, "Beutel RB", "set")
        f2 = ordner_neu(w, g, "Fahrzeug 2", "fahrzeug")
        a = ordner_neu(w, g, "Rucksack A", "set")
        t1 = ordner_neu(w, a, "Tasche1", "sonstiges")
        y = ordner_neu(w, t1, "Beutel Y", "set")
        t2 = ordner_neu(w, a, "Tasche2", "sonstiges")
        kk = ordner_neu(w, g, "Kiste K", "set")
        ee = ordner_neu(w, kk, "Etui E", "set")
        n = {name: neuer_artikel(w, ids["hms"], fid, serial_no=f"ZZ-{name}")["inventory_no"] for name, fid in
             (("r1", rr), ("rb1", rb), ("f2", f2), ("y1", y), ("t2", t2), ("e1", ee))}
        nach_nr = {v: k_ for k_, v in n.items()}
        rid = w.post(f"{API}/durchgaenge", json={"folder_id": g, "titel": "Platzhalter Zeilen"}).json["durchgang"]["id"]
        for iid in [x["item_id"] for x in zeilen(app, "SELECT item_id FROM mat_round_item WHERE round_id = ?", (rid,))]:
            pruefen(p, iid, rid)
        assert w.post(f"{API}/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
        t = {z["folder_id"]: z["protocol_id"] for z in zeilen(app, "SELECT folder_id, protocol_id FROM "
                                                              "mat_round_setprotokoll WHERE round_id = ?", (rid,))}
        assert set(t) == {rr, rb, a, y, kk, ee}
        G = "OG Zeilen"
        erwartet = [
            ("r1", [f"Set {G} › Fahrzeug 1 › Rucksack R · 1 Artikel, im ganzen Set 2 · Set-Protokoll {t[rr]}"], True),
            ("rb1", [f"Set {G} › Fahrzeug 1 › Rucksack R › Beutel RB · 1 Artikel · Set-Protokoll {t[rb]}"], True),
            # Browser S-2.png: der Artikel nach dem inneren Set steht nicht mehr unter dessen Zwischenzeile.
            ("f2", [f"Außerhalb von Sets · {G} › Fahrzeug 2 · 1 Artikel"], False),
            # b4: Kiste K hat nur das innere Set – trotzdem eine Zeile mit ihrem Set-Protokoll, vor der inneren.
            ("e1", [f"Set {G} › Kiste K · im ganzen Set 1 Artikel · Set-Protokoll {t[kk]}",
                    f"Set {G} › Kiste K › Etui E · 1 Artikel · Set-Protokoll {t[ee]}"], True),
            # b3: der erste Artikel von A liegt über Tasche1 im inneren Set Y – A steht davor, nicht dahinter.
            ("y1", [f"Set {G} › Rucksack A · im ganzen Set 2 Artikel · Set-Protokoll {t[a]}",
                    f"Set {G} › Rucksack A › Tasche1 › Beutel Y · 1 Artikel · Set-Protokoll {t[y]}"], True),
            ("t2", [f"Set {G} › Rucksack A (Fortsetzung) · 1 Artikel"], True),
        ]
        assert [(nach_nr[x], z, i) for x, z, i in _zwischen(app, rid)] == erwartet
        # Set-Protokoll von A: A ist die äußerste Ebene – nach Y „Rucksack A (Fortsetzung)“, nicht unter Y.
        assert [(nach_nr[x], z, i) for x, z, i in _zwischen(app, rid, a)] == [
            ("y1", [f"Set {G} › Rucksack A › Tasche1 › Beutel Y · 1 Artikel · Set-Protokoll {t[y]}"], True),
            ("t2", [f"Set {G} › Rucksack A (Fortsetzung) · 1 Artikel"], False)]
        assert [(nach_nr[x], z) for x, z, _ in _zwischen(app, rid, rr)] == [
            ("r1", []), ("rb1", [f"Set {G} › Fahrzeug 1 › Rucksack R › Beutel RB · 1 Artikel · Set-Protokoll {t[rb]}"])]
        # So steht es auch im PDF.
        pfad = zeilen(app, "SELECT pdf_path FROM mat_round WHERE id = ?", (rid,))[0]["pdf_path"]
        with open(os.path.join(tmp, pfad), "rb") as fh:
            haupt = " ".join(_pdf_text(fh.read()).split())
        for _, texte, _ in erwartet:
            for text in texte:
                assert text in haupt, text
        assert haupt.index(f"Set {G} › Kiste K · im ganzen") < haupt.index(f"Set {G} › Kiste K › Etui E")
        # Ein Durchgang direkt auf dem Set A: A als äußerste Ebene, wie im Set-Protokoll.
        rid2 = w.post(f"{API}/durchgaenge", json={"folder_id": a, "titel": "Platzhalter A"}).json["durchgang"]["id"]
        for name in ("y1", "t2"):
            iid = zeilen(app, "SELECT id FROM mat_item WHERE inventory_no = ?", (n[name],))[0]["id"]
            pruefen(p, iid, rid2)
        assert w.post(f"{API}/durchgaenge/{rid2}/abschliessen", json={}).status_code == 200
        assert [(nach_nr[x], z) for x, z, _ in _zwischen(app, rid2)][1] == \
            ("t2", [f"Set {G} › Rucksack A (Fortsetzung) · 1 Artikel"])
    print("Zwischenzeilen bestanden.")


def test_abschluss_zweistufig():
    """Ablauf B2 = Sicherheit 1 (Entscheidung „PDFs vorher erzeugen“): Die PDFs entstehen ohne Schreibsperre – während
    des Renderns schreibt eine andere Verbindung ohne zu warten. Ändert sich zwischen Rendern und Festschreiben etwas, das
    in den Protokollen stünde, wird verworfen und neu gerendert (keine Zwischendatei bleibt; die vorab reservierten
    Nummern des verworfenen Versuchs bleiben eine Lücke – N1);
    ändert es sich jedes Mal, 409 mit verständlicher Meldung und nichts festgeschrieben. verwaiste_beiseite löscht nur alte
    Zwischendateien."""
    from app.material.services import durchgang as durchgang_dienst
    from app.material.services import pdf, protokoll
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        rid = durchgang(t, t.g)
        for x in (t.a1, t.a2, t.b1, t.c1, t.l1):
            pruefen(t.p, x["id"], rid)
        for x in (t.d1, t.a3, t.a4):
            ausnehmen(t.w, rid, x["id"])
        echt_rendern, echt_vorab = pdf.rendern, protokoll.durchgang_rendern
        schreiber = []

        def rendern_mit_schreiber(vorlage, daten):
            # Eine andere Verbindung (wie eine Anmeldung) schreibt – ohne Wartezeit: Niemand hält die Sperre.
            conn = sqlite3.connect(t.app.config["DB_PATH"], timeout=0)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE users SET last_login = last_login WHERE id = 1")
                conn.commit()
                schreiber.append(vorlage)
            finally:
                conn.close()
            return echt_rendern(vorlage, daten)
        aufrufe = []

        def vorab_dann_umbenennen(v):
            echt_vorab(v)
            aufrufe.append(1)
            if len(aufrufe) == 1:
                # Nach dem Rendern, vor dem Festschreiben: Set C bekommt einen neuen Namen – steht in den Protokollen.
                conn = roh(t.app)
                with conn:
                    conn.execute("UPDATE mat_folder SET name = 'Kiste C neu' WHERE id = ?", (t.c,))
                conn.close()
        pdf.rendern, protokoll.durchgang_rendern = rendern_mit_schreiber, vorab_dann_umbenennen
        try:
            r = t.w.post(f"{API}/durchgaenge/{rid}/abschliessen", json={})
        finally:
            pdf.rendern, protokoll.durchgang_rendern = echt_rendern, echt_vorab
        assert r.status_code == 200, r.get_json()
        assert len(aufrufe) == 2 and schreiber.count("setprotokoll") == 6 and schreiber.count("sammelprotokoll") == 2
        s = _set_zeilen(t, rid)
        jahr = s[t.a]["protocol_id"].split("-")[1]
        assert sorted(z["protocol_id"] for z in s.values()) == [f"T-{jahr}-{n:06d}" for n in (4, 5, 6)]
        assert s[t.c]["ordner"] == "OG Setstadt › Kiste C neu"
        haupt = " ".join(_pdf_text(t.w.get(f"/material/durchgang/{rid}/sammelprotokoll").data).split())
        assert "Kiste C neu" in haupt
        ablage = os.path.join(tmp, "pdf", jahr)
        assert not [x for x in os.listdir(ablage) if x.endswith(protokoll.ZWISCHEN_ENDUNG)], os.listdir(ablage)
        for z in s.values():
            assert hashlib.sha256(_datei(t, z["pdf_path"])).hexdigest() == z["file_sha256"]
            assert oct(os.stat(os.path.join(tmp, z["pdf_path"])).st_mode & 0o777) == "0o444"
        assert len([x for x in os.listdir(ablage) if x.endswith(".pdf")]) == 5 + 3 + 1     # P ×5, T ×3, S

        # Ändert sich jedes Mal etwas: nach VERSUCHE Versuchen 409, nichts festgeschrieben, keine Datei.
        rid2 = durchgang(t, t.c, "Platzhalter immer anders")
        pruefen(t.p, t.c1["id"], rid2)
        vorher = sorted(os.listdir(ablage))
        zaehler = []

        def immer_anders(v):
            echt_vorab(v)
            zaehler.append(1)
            conn = roh(t.app)
            with conn:
                conn.execute("UPDATE mat_folder SET name = ? WHERE id = ?", (f"Kiste C {len(zaehler)}", t.c))
            conn.close()
        protokoll.durchgang_rendern = immer_anders
        try:
            r = t.w.post(f"{API}/durchgaenge/{rid2}/abschliessen", json={})
        finally:
            protokoll.durchgang_rendern = echt_vorab
        assert r.status_code == 409 and r.json["error"] == durchgang_dienst.GEAENDERT, r.get_json()
        assert len(zaehler) == durchgang_dienst.VERSUCHE
        assert sorted(os.listdir(ablage)) == vorher
        assert zeilen(t.app, "SELECT closed_on, locked_at FROM mat_round WHERE id = ?", (rid2,))[0] == \
            {"closed_on": None, "locked_at": None}
        assert t.w.post(f"{API}/durchgaenge/{rid2}/abschliessen", json={}).status_code == 200

        # Abbruch geht denselben Weg (nur das Sammelprotokoll).
        rid3 = durchgang(t, t.lager, "Platzhalter Abbruch")
        pruefen(t.p, t.l1["id"], rid3)
        r = t.w.post(f"{API}/durchgaenge/{rid3}/abbrechen", json={})
        assert r.status_code == 200 and r.json["durchgang"]["protokoll"] and r.json["durchgang"]["set_protokolle"] == []

        # verwaiste_beiseite: alte Zwischendateien weg, junge (ein anderer Prozess rendert vielleicht) bleiben.
        alt, jung = os.path.join(ablage, ".T-2026-000099.aaaa.teil"), os.path.join(ablage, ".T-2026-000098.bbbb.teil")
        for pfad in (alt, jung):
            with open(pfad, "wb") as fh:
                fh.write(b"%PDF-Platzhalter")
        os.utime(alt, (1, 1))
        with t.app.app_context():
            from app import db
            protokoll.verwaiste_beiseite(db.get_db())
        assert not os.path.exists(alt) and os.path.exists(jung)
        # Zwischennamen sind keine Protokolldateien: Sie heben den Zähler nicht (Durchgang auf Set C: kein weiteres T).
        assert zeilen(t.app, "SELECT seq FROM sqlite_sequence WHERE name = 'mat_round_setprotokoll'")[0]["seq"] == 6
        assert not os.path.isdir(os.path.join(tmp, "pdf", "verwaist"))
    print("Zweistufiger Abschluss bestanden.")


def test_dateiname_ascii():
    """Der ASCII-Ersatzname eines Downloads schreibt „ue“ statt das „ü“ zu verlieren; filename* trägt den echten Namen."""
    from app.material.services import export
    kopf = export.anhang_kopf("Protokolle_Jahresprüfung 2026_S-2026-000001.zip")
    assert kopf == ('attachment; filename="Protokolle_Jahrespruefung 2026_S-2026-000001.zip"; '
                    "filename*=UTF-8''Protokolle_Jahrespr%C3%BCfung%202026_S-2026-000001.zip"), kopf
    assert 'filename="Grosse_Oefen_Uebung.csv"' in export.anhang_kopf("Große_Öfen_Übung.csv")
    print("Dateiname bestanden.")


def test_gleichzeitige_abschluesse():
    """Nachprüfung vom 25.10.2026, N1: Vier Durchgänge in vier Gliederungen, gleichzeitig abgeschlossen (je zwei Sets):
    alle 200, jeder rendert genau einmal (die T-Nummern sind vorab reserviert – ein fremder Abschluss verdrängt keinen),
    acht verschiedene Nummern ohne Lücke. Die 409-Meldung nennt auch den gleichzeitigen Abschluss."""
    import threading
    from app.material.services import durchgang as durchgang_dienst
    from app.material.services import protokoll
    assert "gleichzeitig ein anderer Durchgang abgeschlossen" in durchgang_dienst.GEAENDERT
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p = k["wart"], k["pruefer"]
        runden = []
        for n in range(4):
            g, _ = gliederung(k["adm"], f"OG Parallel {n}")
            for m in range(2):
                fid = ordner_neu(w, g, f"Rucksack {n}-{m}", "set")
                neuer_artikel(w, ids["hms"], fid, serial_no=f"PAR-{n}-{m}")
            rid = w.post(f"{API}/durchgaenge", json={"folder_id": g, "titel": f"Platzhalter {n}"}).json["durchgang"]["id"]
            for x in zeilen(app, "SELECT item_id FROM mat_round_item WHERE round_id = ?", (rid,)):
                pruefen(p, x["item_id"], rid)
            runden.append(rid)
        echt, gerendert = protokoll.durchgang_rendern, []

        def zaehlen(v):
            gerendert.append(v["r"]["id"])
            echt(v)
        protokoll.durchgang_rendern = zaehlen
        ergebnis, start = {}, threading.Barrier(4)

        def abschliessen(rid):
            c = anmelden(app, "wart@example.org", "passwort1")
            start.wait()
            r = c.post(f"{API}/durchgaenge/{rid}/abschliessen", json={})
            ergebnis[rid] = (r.status_code, r.get_json())
        try:
            faeden = [threading.Thread(target=abschliessen, args=(rid,)) for rid in runden]
            for f in faeden:
                f.start()
            for f in faeden:
                f.join(timeout=600)
        finally:
            protokoll.durchgang_rendern = echt
        assert all(ergebnis[rid][0] == 200 for rid in runden), ergebnis
        assert sorted(gerendert) == sorted(runden), gerendert          # keiner verworfen
        nummern = sorted(z["protocol_id"] for z in zeilen(app, "SELECT protocol_id FROM mat_round_setprotokoll"))
        jahr = nummern[0].split("-")[1]
        assert nummern == [f"T-{jahr}-{n:06d}" for n in range(1, 9)], nummern
    print("Gleichzeitige Abschlüsse bestanden.")


if __name__ == "__main__":
    test_abschluss()
    test_set_als_durchgang_abbruch_und_fehler()
    test_schritt_27()
    test_pruefseite_und_ablage()
    test_rechte_ordnerseite_und_zip()
    test_oberflaeche_statisch()
    test_zwischenzeilen()
    test_abschluss_zweistufig()
    test_dateiname_ascii()
    test_gleichzeitige_abschluesse()
    print("Alle Tests der Set-Protokolle bestanden.")
