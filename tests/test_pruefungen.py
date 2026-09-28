"""Rauchtest für den Bereich „Prüfungen“ (ohne Browser): python tests/test_pruefungen.py  oder  pytest tests/test_pruefungen.py

Geprüft werden die Abnahmekriterien 1–13 des Auftrags, soweit sie ohne Browser prüfbar sind: Rechte und
Zusatzrecht „Prüfer“, Lehrgänge, Excel-Import mit einer im Test erzeugten, strukturgleichen Datei,
Voraussetzungen mit Verlauf, Kopieren, Leistungen mit Zeitansatz, Pflichtkommentar, Medien, Nachvollziehbarkeit,
Nachprüfungen und die Mängelübersicht. Die Datei arbeitet nur mit erfundenen Namen."""
import io
import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402
from PIL import Image  # noqa: E402

H = {"X-Requested-With": "XMLHttpRequest"}
MP4 = b"\x00\x00\x00\x18ftypmp42"          # kleinster Anfang einer MP4-Datei – genügt der Typerkennung


def make_app(tmp):
    os.environ.update({
        "DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "http://localhost",
        "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123",
        # Der Hintergrundlauf für Videos würde im Test nur stören: kein ffmpeg, keine Wartezeit.
        "VIDEOPFLEGE": "0",
    })
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


def jpeg():
    """Ein kleines rotes JPEG – reicht für Original, Web-Fassung und Thumb."""
    img = Image.new("RGB", (640, 480), (200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    buf.seek(0)
    return buf


def hat_felder(obj, *felder):
    """Alle in der Spezifikation genannten Feldnamen müssen vorhanden sein – ein umbenanntes Feld
    bricht das Frontend, ohne dass ein Statuscode es verrät."""
    fehlt = [f for f in felder if f not in obj]
    assert not fehlt, f"Felder fehlen: {fehlt} in {sorted(obj)}"


LEHRGANG_KURZ = ("id", "titel", "nummer", "datum_von", "datum_bis", "ort", "status", "created_by_name", "created_at",
                 "updated_at", "tn_anzahl", "leistungen_anzahl", "zellen_gesamt", "zellen_abgenommen", "offene_maengel",
                 "voraussetzungen_offen")
LEHRGANG_DETAIL = LEHRGANG_KURZ + ("beschreibung", "ausbilder", "voraussetzungen", "leistungen", "teilnehmer")
TN_FELDER = ("id", "name", "vorname", "geburtsdatum", "gliederung", "email", "bemerkung", "extra", "sortierung",
             "voraussetzungen", "voraussetzungen_offen", "leistungen")
VERSUCH_FELDER = ("id", "teilnehmer_id", "leistung_id", "versuch_nr", "ist_nachpruefung", "ergebnis", "zeit_sekunden",
                  "kommentar", "geprueft_von_name", "geprueft_am", "bearbeitet_von_name", "bearbeitet_am", "medien",
                  "verlauf", "leistung_bezeichnung", "teilnehmer_name")
MEDIUM_FELDER = ("id", "versuch_id", "kind", "original_name", "width", "height", "hochgeladen_von_name",
                 "hochgeladen_am", "thumb", "web", "orig")


def umgebung(tmp):
    """App plus drei angemeldete Klienten: Administration (ohne Prüferrecht), eine Prüferin und ein
    Redakteur ohne das Recht. Das Recht wird bewusst NACH dem Anlegen vergeben – so ist auch der Weg
    über PUT /api/admin/users geprüft, nicht nur das Feld beim Anlegen."""
    app = make_app(tmp)
    adm = app.test_client()
    r = adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"})
    assert r.status_code == 200 and r.json["user"]["role"] == "admin"

    def konto(mail, name):
        r = adm.post("/api/admin/users", json={"email": mail, "password": "passwort1", "name": name,
                                               "gliederung": "OG Musterstadt", "role": "editor"})
        assert r.status_code == 201, r.json
        c = app.test_client()
        assert c.post("/api/auth/login", json={"email": mail, "password": "passwort1"}).status_code == 200
        return c, r.json["user"]["id"]

    pr, pr_id = konto("pruefer@example.org", "Petra Prüferin")
    nix, nix_id = konto("redakteur@example.org", "Rainer Redakteur")
    return app, adm, pr, pr_id, nix, nix_id


def medien_dateien(tmp, medium):
    """Die drei Dateien eines Mediums auf dem Datenträger – abgeleitet aus den URLs der Antwort,
    damit der Test den Dateinamen nicht raten muss."""
    orig = medium["orig"].rsplit("/", 1)[1]
    thumb = medium["thumb"].rsplit("/", 1)[1]
    web = medium["web"].rsplit("/", 1)[1]
    wurzel = os.path.join(tmp, "media", "pruefungen")
    return [os.path.join(wurzel, "orig", orig), os.path.join(wurzel, "web", web), os.path.join(wurzel, "thumb", thumb)]


def lade_medien(client, versuch_id, dateiname_bild="foto.jpg"):
    """JPEG und MP4 (mit Standbild) an einen Versuch hängen; liefert die beiden Medien."""
    data = {"files": [(jpeg(), dateiname_bild), (io.BytesIO(MP4), "clip.mp4")],
            "posters": [(io.BytesIO(b""), ""), (jpeg(), "poster.jpg")]}
    r = client.post(f"/api/pruefungen/versuche/{versuch_id}/medien", data=data, headers=H,
                    content_type="multipart/form-data")
    assert r.status_code == 201, (r.status_code, r.get_json())
    assert r.json["errors"] == [], r.json
    medien = r.json["medien"]
    assert len(medien) == 2 and {m["kind"] for m in medien} == {"image", "video"}, medien
    for m in medien:
        hat_felder(m, *MEDIUM_FELDER)
        assert m["versuch_id"] == versuch_id
        assert m["thumb"].startswith("/media/pruefung/thumb/") and m["thumb"].endswith(".jpg"), m
        assert m["web"].startswith("/media/pruefung/web/") and m["web"].endswith(".jpg"), m
        assert m["orig"].startswith("/media/pruefung/orig/"), m
    return medien


def test_pruefungen():
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        anon = app.test_client()

        # --- 1./2. Rechte: nur das Zusatzrecht zählt, auch für die Administration ---------------
        for client, wer in ((adm, "Admin ohne Recht"), (nix, "Redakteur ohne Recht")):
            r = client.get("/pruefungen")
            assert r.status_code == 403 and "text/html" in r.content_type, (wer, r.status_code, r.content_type)
            assert client.get("/pruefungen/1").status_code == 403, wer
            assert client.get("/pruefungen/1/druck").status_code == 403, wer
            r = client.get("/api/pruefungen/lehrgaenge")
            assert r.status_code == 403 and "Prüfer" in r.json["error"], (wer, r.status_code, r.get_json())
            assert client.get("/api/pruefungen/nutzer").status_code == 403, wer
            assert client.post("/api/pruefungen/lehrgaenge", json={"titel": "Hack"}).status_code == 403, wer
            assert client.get("/media/pruefung/thumb/gibtesnicht.jpg").status_code == 403, wer
            assert 'href="/pruefungen"' not in client.get("/").text, f"{wer} sieht den Reiter"
            assert client.get("/api/me").json["user"]["is_pruefer"] is False
        # Ohne Anmeldung: Seiten und Medien führen zur Anmeldung, die Schnittstelle sagt 401.
        r = anon.get("/pruefungen")
        assert r.status_code == 302 and r.headers["Location"].startswith("/login?next="), (r.status_code, r.headers)
        assert anon.get("/api/pruefungen/lehrgaenge").status_code == 401
        r = anon.get("/media/pruefung/thumb/gibtesnicht.jpg")
        assert r.status_code in (302, 401), r.status_code
        # Ein Nichtadministrator darf das Recht nicht vergeben; die Administration schon – ohne die Rolle anzufassen.
        assert nix.put(f"/api/admin/users/{pr_id}", json={"is_pruefer": True}).status_code == 403
        r = adm.put(f"/api/admin/users/{pr_id}", json={"is_pruefer": True})
        assert r.status_code == 200, r.json
        petra = [u for u in adm.get("/api/admin/users").json["users"] if u["id"] == pr_id][0]
        assert petra["is_pruefer"] is True and petra["role"] == "editor", petra
        assert pr.get("/api/me").json["user"]["is_pruefer"] is True
        assert pr.get("/pruefungen").status_code == 200
        assert 'href="/pruefungen"' in pr.get("/").text, "Prüferin muss den Reiter sehen"
        r = pr.get("/api/pruefungen/lehrgaenge")
        assert r.status_code == 200 and r.json["lehrgaenge"] == [], r.get_json()
        # Entzug wirkt sofort: dem Redakteur kurz geben und wieder nehmen.
        assert adm.put(f"/api/admin/users/{nix_id}", json={"is_pruefer": True}).status_code == 200
        assert nix.get("/api/pruefungen/lehrgaenge").status_code == 200
        assert 'href="/pruefungen"' in nix.get("/").text
        assert adm.put(f"/api/admin/users/{nix_id}", json={"is_pruefer": False}).status_code == 200
        assert nix.get("/api/pruefungen/lehrgaenge").status_code == 403
        assert nix.get("/pruefungen").status_code == 403
        assert 'href="/pruefungen"' not in nix.get("/").text
        assert nix.get("/api/me").json["user"]["is_pruefer"] is False
        assert nix.get("/api/me").json["user"]["role"] == "editor"

        # --- 4.1 Nutzerliste für die Ausbilder-Auswahl ------------------------------------------
        r = pr.get("/api/pruefungen/nutzer")
        assert r.status_code == 200
        nutzer = r.json["nutzer"]
        for n in nutzer:
            hat_felder(n, "id", "name", "gliederung")
        namen = [n["name"] for n in nutzer]
        assert "Petra Prüferin" in namen and namen == sorted(namen, key=str.lower), namen

        # --- 3. Lehrgang anlegen: Validierung ---------------------------------------------------
        r = pr.post("/api/pruefungen/lehrgaenge", json={"nummer": "2026-0001"})
        assert r.status_code == 400 and "Titel" in r.json["error"], (r.status_code, r.get_json())
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "   "})
        assert r.status_code == 400, r.get_json()
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Falsch", "datum_von": "2026-05-10", "datum_bis": "2026-05-01"})
        assert r.status_code == 400, (r.status_code, r.get_json())
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Falsch", "datum_von": "10.05.2026x"})
        assert r.status_code == 400, (r.status_code, r.get_json())
        assert pr.post("/api/pruefungen/lehrgaenge", json={"titel": 12}).status_code == 400
        assert pr.get("/api/pruefungen/lehrgaenge/999999").status_code == 404

        # Anlegen mit Ausbildern: einer aus den Nutzern (Name kommt aus `users`), einer als Freitext,
        # einer mit erfundener user_id (wird Freitext).
        r = pr.post("/api/pruefungen/lehrgaenge", json={
            "titel": "Strömungsretter 2", "nummer": "2026-0011", "datum_von": "2026-05-01", "datum_bis": "2026-05-03",
            "ort": "Musterstadt", "beschreibung": "Aufbaulehrgang", "status": "laufend",
            "ausbilder": [{"user_id": pr_id, "funktion": "Lehrgangsleitung"},
                          {"user_id": None, "name": "Erwin Extern", "funktion": "Ausbilder"},
                          {"user_id": 999999, "name": "Frieda Fremd", "funktion": "Referentin"}]})
        assert r.status_code == 201, (r.status_code, r.get_json())
        lg = r.json["lehrgang"]
        hat_felder(lg, *LEHRGANG_DETAIL)
        lid = lg["id"]
        assert lg["titel"] == "Strömungsretter 2" and lg["status"] == "laufend" and lg["ort"] == "Musterstadt"
        assert lg["datum_von"] == "2026-05-01" and lg["datum_bis"] == "2026-05-03"
        assert lg["created_by_name"] == "Petra Prüferin" and lg["created_at"] and lg["updated_at"]
        assert lg["tn_anzahl"] == 0 and lg["leistungen_anzahl"] == 0 and lg["zellen_gesamt"] == 0
        assert lg["teilnehmer"] == [] and lg["voraussetzungen"] == [] and lg["leistungen"] == []
        ausb = lg["ausbilder"]
        assert len(ausb) == 3, ausb
        for a in ausb:
            hat_felder(a, "id", "user_id", "name", "funktion")
        assert ausb[0]["user_id"] == pr_id and ausb[0]["name"] == "Petra Prüferin" and ausb[0]["funktion"] == "Lehrgangsleitung", ausb
        assert ausb[1]["user_id"] is None and ausb[1]["name"] == "Erwin Extern", ausb
        assert ausb[2]["user_id"] is None and ausb[2]["name"] == "Frieda Fremd", ausb
        # Ein unbekannter Status wird zu „geplant“.
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Ohne Datum", "status": "irgendwas"})
        assert r.status_code == 201 and r.json["lehrgang"]["status"] == "geplant", r.get_json()
        ohne_datum = r.json["lehrgang"]["id"]
        assert r.json["lehrgang"]["datum_von"] is None and r.json["lehrgang"]["nummer"] == ""

        # Bearbeiten: nur mitgeschickte Felder ändern, Ausbilder-Liste wird komplett ersetzt.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"status": "geplant", "ort": "Neustadt",
                                                              "ausbilder": [{"name": "Nur Einer", "funktion": ""}]})
        assert r.status_code == 200, (r.status_code, r.get_json())
        lg = r.json["lehrgang"]
        assert lg["status"] == "geplant" and lg["ort"] == "Neustadt" and lg["titel"] == "Strömungsretter 2"
        # Die bearbeitende Leitung bleibt eingetragen (sonst sperrte sie sich mit dieser Liste selbst aus).
        assert [a["name"] for a in lg["ausbilder"]] == ["Petra Prüferin", "Nur Einer"], lg["ausbilder"]
        assert lg["ausbilder"][0]["user_id"] == pr_id and lg["ausbilder"][0]["funktion"] == "Lehrgangsleitung"
        assert lg["beschreibung"] == "Aufbaulehrgang"
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"datum_bis": "2026-04-01"}).status_code == 400  # vor datum_von
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"titel": ""}).status_code == 400
        assert pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["ort"] == "Neustadt"

        # Liste: Form, Sortierung (Datum absteigend, ohne Datum zuletzt), Suche und Jahr.
        liste = pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]
        assert len(liste) == 2
        for eintrag in liste:
            hat_felder(eintrag, *LEHRGANG_KURZ)
        assert [e["id"] for e in liste] == [lid, ohne_datum], liste
        assert [e["id"] for e in pr.get("/api/pruefungen/lehrgaenge?q=NEUSTADT").json["lehrgaenge"]] == [lid]
        assert [e["id"] for e in pr.get("/api/pruefungen/lehrgaenge?q=0011").json["lehrgaenge"]] == [lid]
        assert [e["id"] for e in pr.get("/api/pruefungen/lehrgaenge?q=ohne").json["lehrgaenge"]] == [ohne_datum]
        assert pr.get("/api/pruefungen/lehrgaenge?q=gibtsnicht").json["lehrgaenge"] == []
        assert [e["id"] for e in pr.get("/api/pruefungen/lehrgaenge?jahr=2026").json["lehrgaenge"]] == [lid]
        assert pr.get("/api/pruefungen/lehrgaenge?jahr=2019").json["lehrgaenge"] == []
        # CSRF: DELETE ohne Header wird abgewiesen, der Lehrgang bleibt.
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{ohne_datum}").status_code == 403
        assert pr.get(f"/api/pruefungen/lehrgaenge/{ohne_datum}").status_code == 200
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{ohne_datum}", headers=H).json["ok"] is True
        assert pr.get(f"/api/pruefungen/lehrgaenge/{ohne_datum}").status_code == 404
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{ohne_datum}", headers=H).status_code == 404

        # --- 4.4 Voraussetzungen: anlegen, umbenennen, sortieren, löschen ------------------------
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": ""}).status_code == 400
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={}).status_code == 400
        vids = []
        for bez in ("Mindestalter 16 Jahre", "DRSA Silber", "Erste Hilfe"):
            r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": bez})
            assert r.status_code == 201, (r.status_code, r.get_json())
            hat_felder(r.json["voraussetzung"], "id", "bezeichnung", "sortierung")
            assert r.json["voraussetzung"]["bezeichnung"] == bez
            vids.append(r.json["voraussetzung"]["id"])
        r = pr.put(f"/api/pruefungen/voraussetzungen/{vids[2]}", json={"bezeichnung": "Erste Hilfe (9 UE)"})
        assert r.status_code == 200 and r.json["voraussetzung"]["bezeichnung"] == "Erste Hilfe (9 UE)", r.get_json()
        assert pr.put(f"/api/pruefungen/voraussetzungen/{vids[2]}", json={"bezeichnung": ""}).status_code == 400
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [v["id"] for v in detail["voraussetzungen"]] == vids, detail["voraussetzungen"]
        # Reihenfolge umkehren; eine fremde ID in der Liste darf nichts anrichten.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen/reihenfolge", json={"ids": list(reversed(vids)) + [999999]})
        assert r.status_code == 200 and r.json["ok"] is True, r.get_json()
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [v["id"] for v in detail["voraussetzungen"]] == list(reversed(vids)), detail["voraussetzungen"]
        assert [v["sortierung"] for v in detail["voraussetzungen"]] == [0, 1, 2], detail["voraussetzungen"]
        assert pr.delete(f"/api/pruefungen/voraussetzungen/{vids[2]}", headers=H).json["ok"] is True
        vids = vids[:2]
        assert [v["id"] for v in pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["voraussetzungen"]] == [vids[1], vids[0]]

        # --- 4.3 Teilnehmende ----------------------------------------------------------------------
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"vorname": "Ohne"}).status_code == 400  # Nachname Pflicht
        assert pr.post(f"/api/pruefungen/lehrgaenge/999999/teilnehmer", json={"name": "X"}).status_code == 404
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer",
                    json={"name": "Beispiel", "vorname": "Anna", "geburtsdatum": "2001-02-03", "gliederung": "OG Nord",
                          "email": "anna@example.org", "bemerkung": "Linkshänderin"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        anna = r.json["teilnehmer"]
        hat_felder(anna, *TN_FELDER)
        assert anna["name"] == "Beispiel" and anna["vorname"] == "Anna" and anna["geburtsdatum"] == "2001-02-03"
        assert anna["gliederung"] == "OG Nord" and anna["email"] == "anna@example.org" and anna["bemerkung"] == "Linkshänderin"
        assert anna["extra"] == {} and anna["voraussetzungen"] == {} and anna["leistungen"] == {}
        assert anna["voraussetzungen_offen"] == 2, anna     # zwei Voraussetzungen, keine erfüllt
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Muster", "vorname": "Bert"})
        assert r.status_code == 201
        bert = r.json["teilnehmer"]
        assert bert["geburtsdatum"] is None and bert["gliederung"] == ""
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Falsch", "geburtsdatum": "gestern"}).status_code == 400
        r = pr.put(f"/api/pruefungen/teilnehmer/{bert['id']}", json={"vorname": "Berthold", "gliederung": "OG Süd", "sortierung": 5})
        assert r.status_code == 200 and r.json["teilnehmer"]["vorname"] == "Berthold" and r.json["teilnehmer"]["gliederung"] == "OG Süd", r.get_json()
        assert r.json["teilnehmer"]["sortierung"] == 5 and r.json["teilnehmer"]["name"] == "Muster"
        assert pr.put(f"/api/pruefungen/teilnehmer/{bert['id']}", json={"name": ""}).status_code == 400
        assert pr.put("/api/pruefungen/teilnehmer/999999", json={"name": "X"}).status_code == 404
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [t["id"] for t in detail["teilnehmer"]] == [anna["id"], bert["id"]] and detail["tn_anzahl"] == 2

        # --- 5. Voraussetzung abhaken: wer, wann, Verlauf --------------------------------------------
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vids[0]}", json={"erfuellt": True})
        assert r.status_code == 200, (r.status_code, r.get_json())
        st = r.json["status"]
        hat_felder(st, "erfuellt", "gesetzt_von_name", "gesetzt_am", "quelle")
        assert st["erfuellt"] is True and st["gesetzt_von_name"] == "Petra Prüferin" and st["quelle"] == "manuell", st
        assert st["gesetzt_am"] and datetime.fromisoformat(st["gesetzt_am"].replace("Z", "+00:00")), st
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        tn = {t["id"]: t for t in detail["teilnehmer"]}
        zelle = tn[anna["id"]]["voraussetzungen"][str(vids[0])]
        assert zelle["erfuellt"] is True and zelle["gesetzt_von_name"] == "Petra Prüferin" and zelle["gesetzt_am"] == st["gesetzt_am"], zelle
        assert str(vids[1]) not in tn[anna["id"]]["voraussetzungen"], "nicht gesetzte Voraussetzungen fehlen im Objekt"
        assert tn[anna["id"]]["voraussetzungen_offen"] == 1 and tn[bert["id"]]["voraussetzungen_offen"] == 2
        assert detail["voraussetzungen_offen"] == 2          # beide TN haben noch etwas offen
        # Entfernen bleibt nachvollziehbar: zwei Einträge im Verlauf, der neueste zuerst.
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vids[0]}", json={"erfuellt": False})
        assert r.status_code == 200 and r.json["status"]["erfuellt"] is False
        r = pr.get(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vids[0]}/verlauf")
        assert r.status_code == 200
        verlauf = r.json["verlauf"]
        assert len(verlauf) == 2, verlauf
        for v in verlauf:
            hat_felder(v, "erfuellt", "user_name", "zeit", "quelle")
        assert verlauf[0]["erfuellt"] is False and verlauf[1]["erfuellt"] is True, verlauf
        assert all(v["user_name"] == "Petra Prüferin" and v["quelle"] == "manuell" for v in verlauf), verlauf
        zelle = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["teilnehmer"][0]["voraussetzungen"][str(vids[0])]
        assert zelle["erfuellt"] is False and zelle["gesetzt_von_name"] == "Petra Prüferin"  # „✗ …“ bleibt sichtbar
        # Anna erfüllt beide → nichts mehr offen; Bert eine → weiter offen.
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vids[0]}", json={"erfuellt": True}).status_code == 200
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vids[1]}", json={"erfuellt": True}).status_code == 200
        assert pr.put(f"/api/pruefungen/teilnehmer/{bert['id']}/voraussetzungen/{vids[1]}", json={"erfuellt": True}).status_code == 200
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert detail["voraussetzungen_offen"] == 1, detail["voraussetzungen_offen"]
        assert {t["id"]: t["voraussetzungen_offen"] for t in detail["teilnehmer"]} == {anna["id"]: 0, bert["id"]: 1}
        # TN und Voraussetzung müssen zum selben Lehrgang gehören.
        fremd = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Fremder Lehrgang"}).json["lehrgang"]["id"]
        fv = pr.post(f"/api/pruefungen/lehrgaenge/{fremd}/voraussetzungen", json={"bezeichnung": "Fremd"}).json["voraussetzung"]["id"]
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{fv}", json={"erfuellt": True}).status_code == 400
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen/reihenfolge", json={"ids": [fv]}).status_code == 200
        assert [v["id"] for v in pr.get(f"/api/pruefungen/lehrgaenge/{fremd}").json["lehrgang"]["voraussetzungen"]] == [fv]  # unberührt

        # --- 7./8. Leistungen: Zeitansatz als „mm:ss“ oder Sekunden, null bleibt null --------------
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": ""}).status_code == 400
        for schlecht in ("abc", "3:xx", -5, "-1:00", [180]):
            r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Falsch", "zeitansatz_sekunden": schlecht})
            assert r.status_code == 400, (schlecht, r.status_code, r.get_json())
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen",
                    json={"bezeichnung": "Wurfsackwurf auf Ziel", "beschreibung_md": "# Ablauf\n\n3 Würfe", "zeitansatz_sekunden": "03:00"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        wurf = r.json["leistung"]
        hat_felder(wurf, "id", "bezeichnung", "beschreibung_md", "zeitansatz_sekunden", "sortierung")
        assert wurf["zeitansatz_sekunden"] == 180 and wurf["beschreibung_md"] == "# Ablauf\n\n3 Würfe", wurf
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Aufbau Flaschenzug 3:1", "zeitansatz_sekunden": None})
        assert r.status_code == 201 and r.json["leistung"]["zeitansatz_sekunden"] is None, r.get_json()
        flaschenzug = r.json["leistung"]
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Schwimmen 100 m", "zeitansatz_sekunden": 150})
        assert r.status_code == 201 and r.json["leistung"]["zeitansatz_sekunden"] == 150
        schwimmen = r.json["leistung"]
        r = pr.put(f"/api/pruefungen/leistungen/{schwimmen['id']}", json={"zeitansatz_sekunden": "02:15", "bezeichnung": "Schwimmen 100 m (Strömung)"})
        assert r.status_code == 200 and r.json["leistung"]["zeitansatz_sekunden"] == 135, r.get_json()
        assert r.json["leistung"]["bezeichnung"] == "Schwimmen 100 m (Strömung)"
        r = pr.put(f"/api/pruefungen/leistungen/{schwimmen['id']}", json={"zeitansatz_sekunden": None})
        assert r.status_code == 200 and r.json["leistung"]["zeitansatz_sekunden"] is None
        assert pr.put(f"/api/pruefungen/leistungen/{schwimmen['id']}", json={"zeitansatz_sekunden": "x"}).status_code == 400
        assert pr.put("/api/pruefungen/leistungen/999999", json={"bezeichnung": "X"}).status_code == 404
        lids = [wurf["id"], flaschenzug["id"], schwimmen["id"]]
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [l["id"] for l in detail["leistungen"]] == lids
        assert detail["leistungen_anzahl"] == 3 and detail["zellen_gesamt"] == 6 and detail["zellen_abgenommen"] == 0
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}/leistungen/reihenfolge", json={"ids": [lids[2], lids[0], lids[1]]})
        assert r.status_code == 200 and r.json["ok"] is True
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [l["id"] for l in detail["leistungen"]] == [lids[2], lids[0], lids[1]], detail["leistungen"]
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}/leistungen/reihenfolge", json={"ids": lids}).status_code == 200

        # --- 9./11. Bewertung: Pflichtkommentar, Prüfer und Zeitpunkt ------------------------------
        basis = f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{wurf['id']}/versuche"
        r = pr.get(basis)
        assert r.status_code == 200, (r.status_code, r.get_json())
        hat_felder(r.json, "versuche", "status", "teilnehmer", "leistung")
        assert r.json["versuche"] == [] and r.json["status"] == "offen" and r.json["leistung"]["id"] == wurf["id"]
        assert r.json["teilnehmer"]["id"] == anna["id"]
        r = pr.post(basis, json={"ergebnis": "mangelhaft", "kommentar": "   "})
        assert r.status_code == 400 and "Kommentar" in r.json["error"], (r.status_code, r.get_json())
        assert pr.post(basis, json={"ergebnis": "mangelhaft"}).status_code == 400
        assert pr.post(basis, json={"ergebnis": "geht so", "kommentar": "x"}).status_code == 400
        assert pr.post(basis, json={"kommentar": "x"}).status_code == 400
        assert pr.post(basis, json={"ergebnis": "bestanden", "zeit_sekunden": "abc"}).status_code == 400
        assert pr.post(basis, json={"ergebnis": "bestanden", "zeit_sekunden": -3}).status_code == 400
        assert pr.get(basis).json["versuche"] == [], "abgewiesene Bewertungen dürfen nichts hinterlassen"
        r = pr.post(basis, json={"ergebnis": "mangelhaft", "kommentar": "Zwei Würfe zu kurz, Seil nicht aufgeschossen.",
                                 "zeit_sekunden": "03:20", "nachpruefung": True})
        assert r.status_code == 201, (r.status_code, r.get_json())
        v1 = r.json["versuch"]
        hat_felder(v1, *VERSUCH_FELDER)
        assert v1["versuch_nr"] == 1 and not v1["ist_nachpruefung"], v1     # beim ersten Versuch wird nachpruefung ignoriert
        assert v1["ergebnis"] == "mangelhaft" and v1["zeit_sekunden"] == 200
        assert v1["kommentar"] == "Zwei Würfe zu kurz, Seil nicht aufgeschossen."
        assert v1["geprueft_von_name"] == "Petra Prüferin" and v1["geprueft_am"], v1
        assert v1["bearbeitet_am"] is None and (v1["bearbeitet_von_name"] or "") == "", v1
        assert v1["medien"] == [] and v1["verlauf"] == []
        assert v1["teilnehmer_name"] == "Anna Beispiel" and v1["leistung_bezeichnung"] == "Wurfsackwurf auf Ziel", v1
        assert v1["teilnehmer_id"] == anna["id"] and v1["leistung_id"] == wurf["id"]
        r = pr.get(basis)
        assert r.json["status"] == "mangelhaft" and [v["id"] for v in r.json["versuche"]] == [v1["id"]]
        # bestanden ohne Kommentar geht; Zeit ohne Zeitansatz ist erlaubt (Flaschenzug hat keinen).
        r = pr.post(f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{flaschenzug['id']}/versuche",
                    json={"ergebnis": "bestanden", "zeit_sekunden": "01:05"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        anna_fz = r.json["versuch"]
        assert anna_fz["zeit_sekunden"] == 65 and anna_fz["kommentar"] == "" and anna_fz["ergebnis"] == "bestanden"
        r = pr.post(f"/api/pruefungen/teilnehmer/{bert['id']}/leistungen/{flaschenzug['id']}/versuche",
                    json={"ergebnis": "bestanden", "zeit_sekunden": None, "kommentar": "Sauber aufgebaut."})
        assert r.status_code == 201 and r.json["versuch"]["zeit_sekunden"] is None
        bert_fz = r.json["versuch"]
        # Zellen in der Detailansicht: nur bewertete Zellen stehen im Objekt.
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        tn = {t["id"]: t for t in detail["teilnehmer"]}
        zelle = tn[anna["id"]]["leistungen"][str(wurf["id"])]
        hat_felder(zelle, "status", "versuche", "letzter_versuch_id", "letztes_ergebnis", "letzte_zeit_sekunden",
                   "geprueft_von_name", "geprueft_am")
        assert zelle["status"] == "mangelhaft" and zelle["versuche"] == 1 and zelle["letzter_versuch_id"] == v1["id"]
        assert zelle["letztes_ergebnis"] == "mangelhaft" and zelle["letzte_zeit_sekunden"] == 200
        assert zelle["geprueft_von_name"] == "Petra Prüferin" and zelle["geprueft_am"] == v1["geprueft_am"]
        assert str(schwimmen["id"]) not in tn[anna["id"]]["leistungen"], "unbewertete Zelle darf nicht im Objekt stehen"
        assert tn[anna["id"]]["leistungen"][str(flaschenzug["id"])]["status"] == "bestanden"
        assert set(tn[bert["id"]]["leistungen"]) == {str(flaschenzug["id"])}
        # Fortschritt: 3 von 6 Zellen abgenommen, ein offener Mangel.
        assert detail["zellen_gesamt"] == 6 and detail["zellen_abgenommen"] == 3 and detail["offene_maengel"] == 1, detail
        kurz = [e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid][0]
        assert (kurz["tn_anzahl"], kurz["leistungen_anzahl"], kurz["zellen_gesamt"], kurz["zellen_abgenommen"],
                kurz["offene_maengel"], kurz["voraussetzungen_offen"]) == (2, 3, 6, 3, 1, 1), kurz

        # --- 11. Bearbeiten: alter Stand wandert in den Verlauf ---------------------------------------
        assert pr.put(f"/api/pruefungen/versuche/{v1['id']}", json={"ergebnis": "mangelhaft", "kommentar": ""}).status_code == 400
        assert pr.put(f"/api/pruefungen/versuche/{v1['id']}", json={"ergebnis": "unklar"}).status_code == 400
        assert pr.put("/api/pruefungen/versuche/999999", json={"kommentar": "x"}).status_code == 404
        r = pr.put(f"/api/pruefungen/versuche/{v1['id']}",
                   json={"ergebnis": "mangelhaft", "kommentar": "Zwei Würfe zu kurz.", "zeit_sekunden": 190})
        assert r.status_code == 200, (r.status_code, r.get_json())
        v1b = r.json["versuch"]
        assert v1b["kommentar"] == "Zwei Würfe zu kurz." and v1b["zeit_sekunden"] == 190 and v1b["ergebnis"] == "mangelhaft"
        assert v1b["bearbeitet_von_name"] == "Petra Prüferin" and v1b["bearbeitet_am"], v1b
        assert v1b["geprueft_von_name"] == "Petra Prüferin" and v1b["geprueft_am"] == v1["geprueft_am"]  # unverändert
        assert len(v1b["verlauf"]) == 1, v1b["verlauf"]
        alt = v1b["verlauf"][0]
        hat_felder(alt, "ergebnis", "zeit_sekunden", "kommentar", "von_name", "stand_ab", "ersetzt_am")
        assert alt["kommentar"] == "Zwei Würfe zu kurz, Seil nicht aufgeschossen." and alt["zeit_sekunden"] == 200
        assert alt["ergebnis"] == "mangelhaft" and alt["von_name"] == "Petra Prüferin"
        assert alt["stand_ab"] == v1["geprueft_am"] and alt["ersetzt_am"] == v1b["bearbeitet_am"], (alt, v1b)
        # Ohne Änderung kein neuer Verlaufseintrag.
        r = pr.put(f"/api/pruefungen/versuche/{v1['id']}",
                   json={"ergebnis": "mangelhaft", "kommentar": "Zwei Würfe zu kurz.", "zeit_sekunden": 190})
        assert r.status_code == 200 and len(r.json["versuch"]["verlauf"]) == 1, r.get_json()
        # Zweite Änderung: der Verlauf nennt als Urheber des ersetzten Stands die Bearbeiterin.
        r = pr.put(f"/api/pruefungen/versuche/{v1['id']}",
                   json={"ergebnis": "mangelhaft", "kommentar": "Zwei Würfe zu kurz.", "zeit_sekunden": "03:05"})
        assert r.status_code == 200 and r.json["versuch"]["zeit_sekunden"] == 185
        assert len(r.json["versuch"]["verlauf"]) == 2, r.json["versuch"]["verlauf"]
        neuester = [e for e in r.json["versuch"]["verlauf"] if e["zeit_sekunden"] == 190][0]
        assert neuester["stand_ab"] == v1b["bearbeitet_am"] and neuester["von_name"] == "Petra Prüferin", neuester

        # --- 12. Nachprüfung ---------------------------------------------------------------------------
        r = pr.post(basis, json={"ergebnis": "bestanden"})
        assert r.status_code == 409 and "Nachprüfung" in r.json["error"], (r.status_code, r.get_json())
        r = pr.post(basis, json={"ergebnis": "bestanden", "nachpruefung": False})
        assert r.status_code == 409
        # Nach einem bestandenen Versuch gibt es keine Nachprüfung.
        r = pr.post(f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{flaschenzug['id']}/versuche",
                    json={"ergebnis": "bestanden", "nachpruefung": True})
        assert r.status_code == 409 and "mangelhaft" in r.json["error"], (r.status_code, r.get_json())
        assert pr.post(basis, json={"ergebnis": "mangelhaft", "nachpruefung": True}).status_code == 400  # Pflichtkommentar gilt auch hier
        r = pr.post(basis, json={"ergebnis": "bestanden", "nachpruefung": True, "zeit_sekunden": "02:40", "kommentar": "Deutlich besser."})
        assert r.status_code == 201, (r.status_code, r.get_json())
        v2 = r.json["versuch"]
        assert v2["versuch_nr"] == 2 and v2["ist_nachpruefung"] and v2["ergebnis"] == "bestanden" and v2["zeit_sekunden"] == 160, v2
        assert v2["geprueft_von_name"] == "Petra Prüferin"
        r = pr.get(basis)
        assert r.json["status"] == "nachpruefung_bestanden", r.json["status"]
        versuche = r.json["versuche"]
        assert [v["versuch_nr"] for v in versuche] == [1, 2]
        erst = versuche[0]
        assert erst["id"] == v1["id"] and erst["ergebnis"] == "mangelhaft" and erst["zeit_sekunden"] == 185, erst  # Erstversuch unverändert
        assert erst["kommentar"] == "Zwei Würfe zu kurz." and len(erst["verlauf"]) == 2
        zelle = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["teilnehmer"][0]["leistungen"][str(wurf["id"])]
        assert zelle["status"] == "nachpruefung_bestanden" and zelle["versuche"] == 2 and zelle["letzter_versuch_id"] == v2["id"]
        assert zelle["letztes_ergebnis"] == "bestanden" and zelle["letzte_zeit_sekunden"] == 160
        # Nach bestandener Nachprüfung keine weitere.
        assert pr.post(basis, json={"ergebnis": "bestanden", "nachpruefung": True}).status_code == 409
        # Bert am Wurfsack: mangelhaft, Nachprüfung erneut mangelhaft, dritte Nachprüfung bestanden.
        bert_basis = f"/api/pruefungen/teilnehmer/{bert['id']}/leistungen/{wurf['id']}/versuche"
        b1 = pr.post(bert_basis, json={"ergebnis": "mangelhaft", "kommentar": "Ziel verfehlt."}).json["versuch"]
        r = pr.post(bert_basis, json={"ergebnis": "mangelhaft", "kommentar": "Wieder verfehlt.", "nachpruefung": True})
        assert r.status_code == 201 and r.json["versuch"]["versuch_nr"] == 2, r.get_json()
        b2 = r.json["versuch"]
        assert pr.get(bert_basis).json["status"] == "nachpruefung_mangelhaft"
        kurz = [e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid][0]
        assert kurz["zellen_abgenommen"] == 4 and kurz["offene_maengel"] == 1, kurz   # Annas Mangel ist behoben, Berts offen
        # Versuch löschen: nur der letzte einer Zelle.
        r = pr.delete(f"/api/pruefungen/versuche/{b1['id']}", headers=H)
        assert r.status_code == 409, (r.status_code, r.get_json())
        assert pr.delete(f"/api/pruefungen/versuche/{b2['id']}").status_code == 403            # CSRF
        r = pr.delete(f"/api/pruefungen/versuche/{b2['id']}", headers=H)
        assert r.status_code == 200 and r.json["ok"] is True, r.get_json()
        assert [v["id"] for v in pr.get(bert_basis).json["versuche"]] == [b1["id"]]
        assert pr.get(bert_basis).json["status"] == "mangelhaft"
        r = pr.post(bert_basis, json={"ergebnis": "mangelhaft", "kommentar": "Wieder verfehlt.", "nachpruefung": True})
        assert r.status_code == 201 and r.json["versuch"]["versuch_nr"] == 2
        b2 = r.json["versuch"]
        r = pr.post(bert_basis, json={"ergebnis": "bestanden", "nachpruefung": True})
        assert r.status_code == 201 and r.json["versuch"]["versuch_nr"] == 3 and r.json["versuch"]["ist_nachpruefung"], r.get_json()
        b3 = r.json["versuch"]
        assert pr.get(bert_basis).json["status"] == "nachpruefung_bestanden"
        assert pr.delete(f"/api/pruefungen/versuche/{b3['id']}", headers=H).status_code == 200
        assert pr.get(bert_basis).json["status"] == "nachpruefung_mangelhaft"

        # --- 10. Medien: hochladen, abrufen (nur Prüfer), löschen räumt den Datenträger ------------
        medien = lade_medien(pr, b2["id"])
        bild = [m for m in medien if m["kind"] == "image"][0]
        film = [m for m in medien if m["kind"] == "video"][0]
        assert bild["original_name"] == "foto.jpg" and bild["width"] == 640 and bild["height"] == 480, bild
        assert bild["hochgeladen_von_name"] == "Petra Prüferin" and bild["hochgeladen_am"], bild
        assert film["original_name"] == "clip.mp4" and film["orig"].endswith(".mp4"), film
        for m in medien:
            for url in (m["thumb"], m["web"], m["orig"]):
                assert pr.get(url).status_code == 200, url
                assert nix.get(url).status_code == 403, url
                assert adm.get(url).status_code == 403, url
                assert anon.get(url).status_code in (302, 401), url
            for pfad in medien_dateien(tmp, m):
                assert os.path.isfile(pfad), pfad
        with Image.open(os.path.join(tmp, "media", "pruefungen", "thumb", bild["thumb"].rsplit("/", 1)[1])) as th:
            assert max(th.size) <= 256, th.size
        # Die Antwort auf GET trägt die Medien mit.
        r = pr.get(bert_basis)
        b2_neu = [v for v in r.json["versuche"] if v["id"] == b2["id"]][0]
        assert {m["id"] for m in b2_neu["medien"]} == {bild["id"], film["id"]}, b2_neu["medien"]
        # Unbrauchbare Dateien werden je Datei gemeldet, der Rest kommt durch.
        r = pr.post(f"/api/pruefungen/versuche/{b2['id']}/medien", headers=H, content_type="multipart/form-data",
                    data={"files": [(io.BytesIO(b"nix"), "liste.txt"), (jpeg(), "zweites.jpg")]})
        assert r.status_code == 201, (r.status_code, r.get_json())
        assert len(r.json["medien"]) == 1 and len(r.json["errors"]) == 1 and ".txt" in r.json["errors"][0], r.json
        zweites = r.json["medien"][0]
        assert pr.post("/api/pruefungen/versuche/999999/medien", headers=H, content_type="multipart/form-data",
                       data={"files": [(jpeg(), "x.jpg")]}).status_code == 404
        # Nichtprüfer dürfen nichts hochladen.
        assert nix.post(f"/api/pruefungen/versuche/{b2['id']}/medien", headers=H, content_type="multipart/form-data",
                        data={"files": [(jpeg(), "x.jpg")]}).status_code == 403
        # Medium löschen: Zeile und Dateien weg.
        assert pr.delete(f"/api/pruefungen/medien/{zweites['id']}").status_code == 403          # CSRF
        r = pr.delete(f"/api/pruefungen/medien/{zweites['id']}", headers=H)
        assert r.status_code == 200 and r.json["ok"] is True
        assert pr.get(zweites["thumb"]).status_code == 404
        assert not any(os.path.exists(p) for p in medien_dateien(tmp, zweites)), medien_dateien(tmp, zweites)
        assert pr.delete(f"/api/pruefungen/medien/{zweites['id']}", headers=H).status_code == 404
        assert all(os.path.isfile(p) for m in medien for p in medien_dateien(tmp, m)), "andere Medien bleiben"

        # --- 13. Mängel / Feedback ---------------------------------------------------------------------
        # Lage: Anna/Wurf mangelhaft → NP bestanden (Status „bestanden“); Bert/Wurf mangelhaft → NP mangelhaft
        # („erneut_mangelhaft“ + „offen“); dazu Bert/Schwimmen mangelhaft (offen).
        bs = pr.post(f"/api/pruefungen/teilnehmer/{bert['id']}/leistungen/{schwimmen['id']}/versuche",
                     json={"ergebnis": "mangelhaft", "kommentar": "Zu langsam.", "zeit_sekunden": 200}).json["versuch"]
        r = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel")
        assert r.status_code == 200, (r.status_code, r.get_json())
        hat_felder(r.json, "maengel", "teilnehmer", "leistungen")
        assert {t["id"] for t in r.json["teilnehmer"]} == {anna["id"], bert["id"]}
        for t in r.json["teilnehmer"]:
            hat_felder(t, "id", "name", "vorname")
        assert [l["id"] for l in r.json["leistungen"]] == lids
        for l in r.json["leistungen"]:
            hat_felder(l, "id", "bezeichnung")
        maengel = r.json["maengel"]
        for m in maengel:
            hat_felder(m, "versuch", "teilnehmer", "leistung", "nachpruefung_status", "zellstatus")
            hat_felder(m["versuch"], *VERSUCH_FELDER)
            hat_felder(m["teilnehmer"], "id", "name", "vorname", "gliederung")
            hat_felder(m["leistung"], "id", "bezeichnung", "zeitansatz_sekunden")
            assert m["versuch"]["ergebnis"] == "mangelhaft"
        # Sortierung: TN nach Name (Beispiel vor Muster), dann Leistung, dann Versuch.
        assert [(m["versuch"]["id"]) for m in maengel] == [v1["id"], b1["id"], b2["id"], bs["id"]], [m["versuch"]["id"] for m in maengel]
        status = {m["versuch"]["id"]: m["nachpruefung_status"] for m in maengel}
        assert status == {v1["id"]: "bestanden", b1["id"]: "erneut_mangelhaft", b2["id"]: "offen", bs["id"]: "offen"}, status
        zell = {m["versuch"]["id"]: m["zellstatus"] for m in maengel}
        assert zell == {v1["id"]: "nachpruefung_bestanden", b1["id"]: "nachpruefung_mangelhaft",
                        b2["id"]: "nachpruefung_mangelhaft", bs["id"]: "mangelhaft"}, zell
        b2_m = [m for m in maengel if m["versuch"]["id"] == b2["id"]][0]
        assert {x["id"] for x in b2_m["versuch"]["medien"]} == {bild["id"], film["id"]}
        assert b2_m["teilnehmer"]["gliederung"] == "OG Süd" and b2_m["leistung"]["zeitansatz_sekunden"] == 180
        # nur_offen: nur der letzte Versuch einer derzeit mangelhaften Zelle.
        offen = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?nur_offen=1").json["maengel"]
        assert [m["versuch"]["id"] for m in offen] == [b2["id"], bs["id"]], [m["versuch"]["id"] for m in offen]
        # Filter TN und Leistung, einzeln und kombiniert.
        r = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?teilnehmer={anna['id']}").json["maengel"]
        assert [m["versuch"]["id"] for m in r] == [v1["id"]]
        assert pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?teilnehmer={anna['id']}&nur_offen=1").json["maengel"] == []
        r = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?leistung={wurf['id']}").json["maengel"]
        assert [m["versuch"]["id"] for m in r] == [v1["id"], b1["id"], b2["id"]]
        r = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?leistung={schwimmen['id']}&teilnehmer={bert['id']}").json["maengel"]
        assert [m["versuch"]["id"] for m in r] == [bs["id"]]
        r = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?teilnehmer={bert['id']}&leistung={wurf['id']}&nur_offen=1").json["maengel"]
        assert [m["versuch"]["id"] for m in r] == [b2["id"]]
        assert pr.get("/api/pruefungen/lehrgaenge/999999/maengel").status_code == 404
        # Alle Bewertungen eines TN, sortiert nach Leistung-Reihenfolge und Versuch-Nr.
        r = pr.get(f"/api/pruefungen/teilnehmer/{bert['id']}/versuche")
        assert r.status_code == 200
        hat_felder(r.json, "teilnehmer", "versuche")
        assert r.json["teilnehmer"]["id"] == bert["id"]
        assert [(v["leistung_id"], v["versuch_nr"]) for v in r.json["versuche"]] == \
            [(wurf["id"], 1), (wurf["id"], 2), (flaschenzug["id"], 1), (schwimmen["id"], 1)], r.json["versuche"]
        assert any(v["ergebnis"] == "bestanden" and v["kommentar"] == "Sauber aufgebaut." for v in r.json["versuche"])
        # Fortschritt nach allem: 5 von 6 Zellen abgenommen, zwei offene Mängel (Bert/Wurf, Bert/Schwimmen).
        kurz = [e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid][0]
        assert (kurz["zellen_gesamt"], kurz["zellen_abgenommen"], kurz["offene_maengel"]) == (6, 5, 2), kurz

        # --- 6. Kopieren -----------------------------------------------------------------------------
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={"titel": "", "datum_von": "2027-05-07", "datum_bis": "2027-05-09"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        kopie = r.json["lehrgang"]
        hat_felder(kopie, *LEHRGANG_DETAIL)
        assert kopie["id"] != lid and kopie["titel"] == "Strömungsretter 2 (Kopie)", kopie["titel"]
        assert kopie["datum_von"] == "2027-05-07" and kopie["datum_bis"] == "2027-05-09"
        assert kopie["nummer"] == "" and kopie["status"] == "geplant" and kopie["ort"] == "Neustadt"
        assert kopie["beschreibung"] == "Aufbaulehrgang"
        assert [a["name"] for a in kopie["ausbilder"]] == ["Petra Prüferin", "Nur Einer"]   # Leitung bleibt in der Kopie
        assert [(l["bezeichnung"], l["zeitansatz_sekunden"], l["beschreibung_md"]) for l in kopie["leistungen"]] == \
            [("Wurfsackwurf auf Ziel", 180, "# Ablauf\n\n3 Würfe"), ("Aufbau Flaschenzug 3:1", None, ""),
             ("Schwimmen 100 m (Strömung)", None, "")], kopie["leistungen"]
        assert all(l["id"] not in lids for l in kopie["leistungen"]), "Leistungen der Kopie sind eigene Zeilen"
        assert [v["bezeichnung"] for v in kopie["voraussetzungen"]] == ["DRSA Silber", "Mindestalter 16 Jahre"]
        assert kopie["teilnehmer"] == [] and kopie["tn_anzahl"] == 0 and kopie["zellen_abgenommen"] == 0 and kopie["offene_maengel"] == 0
        assert pr.get(f"/api/pruefungen/lehrgaenge/{kopie['id']}/maengel").json["maengel"] == []
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={"titel": "SR2 Herbst", "datum_von": "2027-10-01"})
        assert r.status_code == 201 and r.json["lehrgang"]["titel"] == "SR2 Herbst" and r.json["lehrgang"]["datum_bis"] is None
        assert pr.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={"datum_von": "2027-10-05", "datum_bis": "2027-10-01"}).status_code == 400
        assert pr.post("/api/pruefungen/lehrgaenge/999999/kopieren", json={}).status_code == 404
        # Das Original ist von der Kopie unberührt.
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert detail["tn_anzahl"] == 2 and detail["zellen_abgenommen"] == 5

        # --- Löschen räumt Dateien weg: Leistung, TN, Lehrgang ------------------------------------------
        # Leistung „Schwimmen“ mit Medium an Berts Versuch löschen.
        schwimm_medien = lade_medien(pr, bs["id"], "schwimmen.jpg")
        assert pr.delete(f"/api/pruefungen/leistungen/{schwimmen['id']}", headers=H).json["ok"] is True
        assert not any(os.path.exists(p) for m in schwimm_medien for p in medien_dateien(tmp, m)), "Leistung löschen muss Medien wegräumen"
        assert all(os.path.isfile(p) for m in medien for p in medien_dateien(tmp, m)), "fremde Medien bleiben"
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert detail["leistungen_anzahl"] == 2 and detail["zellen_gesamt"] == 4 and detail["offene_maengel"] == 1
        # TN Bert löschen: seine Medien (an b2) verschwinden.
        assert pr.delete(f"/api/pruefungen/teilnehmer/{bert['id']}").status_code == 403                      # CSRF
        assert pr.delete(f"/api/pruefungen/teilnehmer/{bert['id']}", headers=H).json["ok"] is True
        assert not any(os.path.exists(p) for m in medien for p in medien_dateien(tmp, m)), "TN löschen muss Medien wegräumen"
        assert pr.get(bild["thumb"]).status_code == 404
        assert pr.get(f"/api/pruefungen/teilnehmer/{bert['id']}/versuche").status_code == 404
        detail = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert [t["id"] for t in detail["teilnehmer"]] == [anna["id"]] and detail["offene_maengel"] == 0
        assert detail["zellen_gesamt"] == 2 and detail["zellen_abgenommen"] == 2
        # Lehrgang löschen: alles weg, auch Dateien.
        anna_medien = lade_medien(pr, v2["id"], "anna.jpg")
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{lid}", headers=H).json["ok"] is True
        assert not any(os.path.exists(p) for m in anna_medien for p in medien_dateien(tmp, m)), "Lehrgang löschen muss Medien wegräumen"
        assert pr.get(f"/api/pruefungen/lehrgaenge/{lid}").status_code == 404
        assert pr.get(f"/api/pruefungen/teilnehmer/{anna['id']}/versuche").status_code == 404
        wurzel =os.path.join(tmp, "media", "pruefungen")
        uebrig = [f for sub in ("orig", "web", "thumb") if os.path.isdir(os.path.join(wurzel, sub))
                  for f in os.listdir(os.path.join(wurzel, sub))]
        assert uebrig == [], f"Dateien ohne Datenbankzeile bleiben liegen: {uebrig}"
        # Die Kopien und der Fremdlehrgang sind noch da.
        assert {e["id"] for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]} >= {kopie["id"], fremd}
        print("Rauchtest Prüfungen bestanden.")


# ----------------------------------------------------------------------------------------------------
# Excel-Import
# ----------------------------------------------------------------------------------------------------

VERWALTUNG = ("Bestätigung TN", "Bestätigung Gliederung", "Kostenübernahme", "Zahlung")
VORAUSSETZUNGEN = (
    "Mindestalter 16 Jahre zu Beginn der Veranstaltung",
    "Deutsches Rettungsschwimmabzeichen Silber (152),\nnicht älter als 2 Jahre zu Beginn der Veranstaltung",
    "Sanitätsausbildung A (331)\noder gleichwertig",
    "Ärztliche Tauglichkeitsbescheinigung",
    "Mitgliedschaft in der DLRG",
    "Schwimmnachweis 300 m Kleiderschwimmen",
    "Erste-Hilfe-Ausbildung (9 UE)",
    "Vorlehrgang Wasserrettungsdienst (411)",
    "Sprechfunkunterweisung",
    "Einweisung Rettungsboot",
    "Knotenkunde bestanden",
    "Ausrüstung vollständig",
    "Haftungsausschluss unterschrieben",
    "Datenschutzerklärung unterschrieben",
    "Teilnahmebestätigung Gliederung",
)
KOPF = ("Vorname", "Nachname", "Alter", "Rolle", "Gliederung", "Status") + VERWALTUNG + VORAUSSETZUNGEN

# Erfundene Teilnehmende: (Vorname, Nachname, Alter, Rolle, Gliederung, Status, 4 Verwaltungswerte, 15 Voraussetzungen)
DATEN = [
    ("Anna", "Beispiel", "2002-10-03 00:00:00", "Teilnehmender", "OG Nord", "aktiv",
     ("ja", "ja", "ja", "ja"), ("ja",) * 15),
    ("Bert", "Muster", datetime(2004, 5, 6), "Teilnehmender", "OG Süd", "aktiv",
     ("ja", "nein", "ja", None), ("ja", "nein") * 7 + ("ja",)),
    ("Clara", "Probe", "1999-01-15 00:00:00", "Teilnehmender", "OG West", "aktiv",
     ("ja", "ja", "nein", "nein"), (None,) * 15),
    ("Dario", "Test", "2005-12-24 00:00:00", "Teilnehmender", "OG Ost", "aktiv",
     ("nein", "nein", "nein", "nein"), ("nein",) * 15),
    ("Emil", "Fiktiv", "2001-07-07 00:00:00", "Teilnehmender", "OG Nord", "aktiv",
     ("ja", "ja", "ja", "ja"), ("ja",) * 14 + ("nein",)),
    ("Frida", "Erdacht", "2003-03-30 00:00:00", "Teilnehmender", "OG Mitte", "aktiv",
     ("ja", "ja", "ja", "ja"), ("ja",) * 15),
    ("Lena", "Leitung", "1985-06-01 00:00:00", "Lehrgangsleitung", "OG Mitte", "aktiv",
     ("ja", "ja", "ja", "ja"), (None,) * 15),
    ("Anna", "Beispiel", "2002-10-03 00:00:00", "Teilnehmender", "OG Nord", "aktiv",       # Duplikat
     ("ja", "ja", "ja", "ja"), ("ja",) * 15),
]
TN_ERWARTET = 6          # sechs Teilnehmende – ohne Lehrgangsleitung und ohne das Duplikat


def excel_bauen(kopf=True):
    """Erzeugt eine .xlsx mit derselben Struktur wie die Beispieldatei des Auftrags: fünf Kopfpaare in
    A/B (B:G verbunden), eine Leerzeile, Kopfzeile in Zeile 7, Datenzeilen, zwei „leere“ Zeilen mit
    leeren Zeichenketten am Ende (sie erhöhen max_row, genau wie in echten Exporten)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teilnehmer"
    if kopf:
        paare = (("Nr.", "2026-0042"), ("Titel", "Strömungsretter 1 (SR1)"),
                 ("Zeitraum", "04.12.2026 18:00 Uhr bis 13.12.2026 19:00 Uhr"),
                 ("Ort", "Rheinisch-Bergischer Kreis"), ("Stand", "27.09.2026 14:45"))
        for zeile, (bez, wert) in enumerate(paare, start=1):
            ws.cell(row=zeile, column=1, value=bez)
            ws.cell(row=zeile, column=2, value=wert)
            ws.merge_cells(start_row=zeile, start_column=2, end_row=zeile, end_column=7)
    for spalte, titel in enumerate(KOPF, start=1):
        ws.cell(row=7, column=spalte, value=titel)
    zeile = 8
    for vorname, name, alter, rolle, glied, status, verwaltung, voraus in DATEN:
        werte = (vorname, name, alter, rolle, glied, status) + tuple(verwaltung) + tuple(voraus)
        for spalte, wert in enumerate(werte, start=1):
            if wert is not None:
                ws.cell(row=zeile, column=spalte, value=wert)
        zeile += 1
    for _ in range(2):
        for spalte in range(1, len(KOPF) + 1):
            ws.cell(row=zeile, column=spalte, value="")
        zeile += 1
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_import():
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        assert adm.put(f"/api/admin/users/{pr_id}", json={"is_pruefer": True}).status_code == 200

        def vorschau(client=pr, **felder):
            data = {"file": (excel_bauen(), "2026-0042 - Strömungsretter 1.xlsx")}
            data.update(felder)
            return client.post("/api/pruefungen/import/vorschau", data=data, headers=H, content_type="multipart/form-data")

        def uebernehmen(client=pr, dateiname="2026-0042 - Strömungsretter 1.xlsx", **felder):
            data = {"file": (excel_bauen(), dateiname)}
            data.update(felder)
            return client.post("/api/pruefungen/import", data=data, headers=H, content_type="multipart/form-data")

        # Rechte und Dateityp
        assert vorschau(nix).status_code == 403
        assert uebernehmen(nix).status_code == 403
        assert pr.post("/api/pruefungen/import/vorschau", data={}, headers=H, content_type="multipart/form-data").status_code == 400
        r = pr.post("/api/pruefungen/import/vorschau", data={"file": (io.BytesIO(b"Vorname;Nachname\n"), "liste.csv")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 400 and r.json["error"], (r.status_code, r.get_json())
        r = pr.post("/api/pruefungen/import/vorschau", data={"file": (io.BytesIO(b"kein zip"), "kaputt.xlsx")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 400 and r.json["error"], (r.status_code, r.get_json())
        assert pr.post("/api/pruefungen/import", data={"file": (io.BytesIO(b"kein zip"), "kaputt.xlsx")},
                       headers=H, content_type="multipart/form-data").status_code == 400
        assert pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] == [], "eine abgewiesene Datei darf keinen Lehrgang anlegen"

        # --- Vorschau: Kopfzeile, Lehrgangsdaten, Spaltenzuordnung -----------------------------------
        r = vorschau()
        assert r.status_code == 200, (r.status_code, r.get_json())
        v = r.json
        hat_felder(v, "spalten", "lehrgang", "teilnehmer", "ausbilder", "voraussetzungen", "warnungen", "kopfzeile")
        assert v["kopfzeile"] == 7, v["kopfzeile"]
        assert v["lehrgang"] == {"titel": "Strömungsretter 1 (SR1)", "nummer": "2026-0042", "datum_von": "2026-12-04",
                                 "datum_bis": "2026-12-13", "ort": "Rheinisch-Bergischer Kreis"}, v["lehrgang"]
        spalten = {s["titel"].replace("\n", " "): s for s in v["spalten"]}
        for s in v["spalten"]:
            hat_felder(s, "index", "titel", "zuordnung", "beispiele")
            assert isinstance(s["beispiele"], list) and len(s["beispiele"]) <= 3 and all(isinstance(b, str) for b in s["beispiele"]), s
        assert len(v["spalten"]) == len(KOPF), [s["titel"] for s in v["spalten"]]
        erwartet = {"Vorname": "vorname", "Nachname": "name", "Alter": "geburtsdatum", "Rolle": "rolle",
                    "Gliederung": "gliederung", "Status": "extra"}
        for titel, zu in erwartet.items():
            assert spalten[titel]["zuordnung"] == zu, (titel, spalten[titel])
        assert spalten["Vorname"]["index"] == 0 and spalten["Nachname"]["index"] == 1 and spalten["Alter"]["index"] == 2
        for titel in VERWALTUNG + tuple(t.replace("\n", " ") for t in VORAUSSETZUNGEN):
            assert spalten[titel]["zuordnung"] == "voraussetzung", (titel, spalten[titel])
        assert "Anna" in spalten["Vorname"]["beispiele"]
        # Voraussetzungs-Liste: die 4 Verwaltungsspalten + 15 Titel, Umbrüche zu Leerzeichen, Reihenfolge wie in der Datei
        for vs in v["voraussetzungen"]:
            hat_felder(vs, "spaltenindex", "bezeichnung", "vorhanden")
            assert vs["vorhanden"] is False
        assert [vs["bezeichnung"] for vs in v["voraussetzungen"]] == \
            list(VERWALTUNG) + [t.replace("\n", " ") for t in VORAUSSETZUNGEN], [vs["bezeichnung"] for vs in v["voraussetzungen"]]
        assert [vs["spaltenindex"] for vs in v["voraussetzungen"]] == list(range(6, 6 + 19))
        # Teilnehmende: sechs, Leitung als Ausbilder, Duplikat übersprungen, Leerzeilen gemeldet
        tn = {(t["vorname"], t["name"]): t for t in v["teilnehmer"]}
        assert len(v["teilnehmer"]) == TN_ERWARTET and len(tn) == TN_ERWARTET, [(t["vorname"], t["name"]) for t in v["teilnehmer"]]
        for t in v["teilnehmer"]:
            hat_felder(t, "vorname", "name", "geburtsdatum", "gliederung", "email", "bemerkung", "extra", "voraussetzungen",
                       "vorhanden", "zeile")
            assert t["vorhanden"] is False
        assert ("Lena", "Leitung") not in tn
        anna = tn[("Anna", "Beispiel")]
        assert anna["geburtsdatum"] == "2002-10-03" and anna["gliederung"] == "OG Nord" and anna["zeile"] == 8, anna
        assert anna["extra"].get("Status") == "aktiv", anna["extra"]
        assert anna["email"] == "" and anna["bemerkung"] == ""
        bert = tn[("Bert", "Muster")]
        assert bert["geburtsdatum"] == "2004-05-06", bert          # echtes datetime in der Zelle
        idx = {vs["bezeichnung"]: str(vs["spaltenindex"]) for vs in v["voraussetzungen"]}
        assert anna["voraussetzungen"][idx["Bestätigung TN"]] is True
        assert bert["voraussetzungen"][idx["Bestätigung Gliederung"]] is False        # „nein“
        assert bert["voraussetzungen"][idx["Zahlung"]] is False                       # leer
        assert bert["voraussetzungen"][idx["Mindestalter 16 Jahre zu Beginn der Veranstaltung"]] is True
        assert set(anna["voraussetzungen"]) == set(idx.values()), "je Voraussetzungsspalte ein Eintrag"
        # Clara hat nur zwei Verwaltungshaken – die eigentlichen Voraussetzungen sind leer.
        clara_v = tn[("Clara", "Probe")]["voraussetzungen"]
        assert clara_v[idx["Bestätigung TN"]] is True and clara_v[idx["Kostenübernahme"]] is False
        assert all(clara_v[idx[t.replace("\n", " ")]] is False for t in VORAUSSETZUNGEN)
        assert len(v["ausbilder"]) == 1, v["ausbilder"]
        hat_felder(v["ausbilder"][0], "name", "funktion", "zeile")
        assert v["ausbilder"][0]["name"] == "Lena Leitung" and v["ausbilder"][0]["funktion"] == "Lehrgangsleitung"
        assert v["ausbilder"][0]["zeile"] == 14
        warn = " | ".join(v["warnungen"]).lower()
        assert len(v["warnungen"]) >= 2, v["warnungen"]
        assert "anna" in warn or "duplikat" in warn or "doppelt" in warn, v["warnungen"]   # das Duplikat
        assert "leer" in warn, v["warnungen"]                                                # die zwei Leerzeilen
        # Zuordnung überschreiben: Verwaltungsspalten ignorieren → 15 Voraussetzungen, „Status“ als Bemerkung.
        ueber = {str(spalten[t]["index"]): "ignorieren" for t in VERWALTUNG}
        ueber[str(spalten["Status"]["index"])] = "bemerkung"
        r = vorschau(zuordnung=json.dumps(ueber))
        assert r.status_code == 200, (r.status_code, r.get_json())
        v2 = r.json
        sp2 = {s["titel"].replace("\n", " "): s for s in v2["spalten"]}
        assert all(sp2[t]["zuordnung"] == "ignorieren" for t in VERWALTUNG), [sp2[t] for t in VERWALTUNG]
        assert sp2["Status"]["zuordnung"] == "bemerkung"
        assert [vs["bezeichnung"] for vs in v2["voraussetzungen"]] == [t.replace("\n", " ") for t in VORAUSSETZUNGEN]
        tn2 = {(t["vorname"], t["name"]): t for t in v2["teilnehmer"]}
        assert len(tn2[("Anna", "Beispiel")]["voraussetzungen"]) == 15
        assert tn2[("Anna", "Beispiel")]["bemerkung"] == "aktiv" and "Status" not in tn2[("Anna", "Beispiel")]["extra"]
        assert pr.post("/api/pruefungen/import/vorschau", headers=H, content_type="multipart/form-data",
                       data={"file": (excel_bauen(), "x.xlsx"), "zuordnung": "kein json"}).status_code == 400

        # --- Übernahme in einen neuen Lehrgang -----------------------------------------------------------
        r = uebernehmen(zuordnung=json.dumps(ueber))
        assert r.status_code == 201, (r.status_code, r.get_json())
        e = r.json
        hat_felder(e, "lehrgang", "angelegt", "aktualisiert", "voraussetzungen_neu", "ausbilder_neu", "warnungen")
        assert (e["angelegt"], e["aktualisiert"], e["voraussetzungen_neu"], e["ausbilder_neu"]) == (TN_ERWARTET, 0, 15, 1), e
        assert len(e["warnungen"]) >= 2
        lg = e["lehrgang"]
        hat_felder(lg, *LEHRGANG_DETAIL)
        lid = lg["id"]
        assert lg["titel"] == "Strömungsretter 1 (SR1)" and lg["nummer"] == "2026-0042" and lg["ort"] == "Rheinisch-Bergischer Kreis"
        assert lg["datum_von"] == "2026-12-04" and lg["datum_bis"] == "2026-12-13" and lg["status"] == "geplant"
        assert lg["created_by_name"] == "Petra Prüferin"
        # Wer importiert, wird Lehrgangsleitung; die Leitung aus der Datei steht als Freitext dahinter.
        assert [a["name"] for a in lg["ausbilder"]] == ["Petra Prüferin", "Lena Leitung"], lg["ausbilder"]
        assert lg["ausbilder"][0]["funktion"] == "Lehrgangsleitung" and lg["ausbilder"][1]["funktion"] == "Lehrgangsleitung"
        assert lg["ausbilder"][1]["user_id"] is None
        assert lg["ausbilder"][0]["user_id"] == pr_id
        assert [v["bezeichnung"] for v in lg["voraussetzungen"]] == [t.replace("\n", " ") for t in VORAUSSETZUNGEN]
        assert [v["sortierung"] for v in lg["voraussetzungen"]] == list(range(15))
        assert lg["leistungen"] == [] and lg["tn_anzahl"] == TN_ERWARTET and len(lg["teilnehmer"]) == TN_ERWARTET
        tn = {(t["vorname"], t["name"]): t for t in lg["teilnehmer"]}
        assert set(tn) == {("Anna", "Beispiel"), ("Bert", "Muster"), ("Clara", "Probe"), ("Dario", "Test"),
                           ("Emil", "Fiktiv"), ("Frida", "Erdacht")}, sorted(tn)
        assert all(t["geburtsdatum"] and t["gliederung"] for t in tn.values()), [(k, t["geburtsdatum"], t["gliederung"]) for k, t in tn.items()]
        assert tn[("Bert", "Muster")]["geburtsdatum"] == "2004-05-06" and tn[("Dario", "Test")]["geburtsdatum"] == "2005-12-24"
        assert tn[("Anna", "Beispiel")]["bemerkung"] == "aktiv"
        # Erfüllte Häkchen: Quelle Import, Name der Importierenden; „nein“ und leer setzen nichts.
        vid = {v["bezeichnung"]: str(v["id"]) for v in lg["voraussetzungen"]}
        mindest = vid["Mindestalter 16 Jahre zu Beginn der Veranstaltung"]
        letzte = vid["Teilnahmebestätigung Gliederung"]
        anna = tn[("Anna", "Beispiel")]
        assert len(anna["voraussetzungen"]) == 15 and anna["voraussetzungen_offen"] == 0, anna
        st = anna["voraussetzungen"][mindest]
        hat_felder(st, "erfuellt", "gesetzt_von_name", "gesetzt_am", "quelle")
        assert st["erfuellt"] is True and st["quelle"] == "import" and st["gesetzt_von_name"] == "Petra Prüferin" and st["gesetzt_am"], st
        emil = tn[("Emil", "Fiktiv")]
        assert emil["voraussetzungen_offen"] == 1 and letzte not in emil["voraussetzungen"], emil
        assert tn[("Clara", "Probe")]["voraussetzungen"] == {} and tn[("Clara", "Probe")]["voraussetzungen_offen"] == 15
        assert tn[("Dario", "Test")]["voraussetzungen"] == {}
        bert = tn[("Bert", "Muster")]
        assert bert["voraussetzungen_offen"] == 7 and sum(1 for s in bert["voraussetzungen"].values() if s["erfuellt"]) == 8, bert
        assert lg["voraussetzungen_offen"] == 4                # Anna und Frida haben alles, die anderen vier nicht
        r = pr.get(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{mindest}/verlauf")
        assert r.status_code == 200 and len(r.json["verlauf"]) == 1, r.get_json()
        assert r.json["verlauf"][0]["quelle"] == "import" and r.json["verlauf"][0]["user_name"] == "Petra Prüferin"

        # Vorschau gegen den bestehenden Lehrgang: alles schon vorhanden.
        r = vorschau(lehrgang_id=str(lid), zuordnung=json.dumps(ueber))
        assert r.status_code == 200, (r.status_code, r.get_json())
        assert all(t["vorhanden"] is True for t in r.json["teilnehmer"]), [(t["name"], t["vorhanden"]) for t in r.json["teilnehmer"]]
        assert all(vs["vorhanden"] is True for vs in r.json["voraussetzungen"])
        # Ohne Überschreibung tauchen die Verwaltungsspalten als neue Voraussetzungen auf.
        r = vorschau(lehrgang_id=str(lid))
        assert [vs["vorhanden"] for vs in r.json["voraussetzungen"]] == [False] * 4 + [True] * 15

        # --- Erneuter Import: keine Duplikate, ein manuell gesetzter Haken bleibt --------------------------
        # Vorher: Emils letzte Voraussetzung („nein“ in der Datei) von Hand setzen und bei Anna eine entfernen.
        assert pr.put(f"/api/pruefungen/teilnehmer/{emil['id']}/voraussetzungen/{letzte}", json={"erfuellt": True}).status_code == 200
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{mindest}", json={"erfuellt": False}).status_code == 200
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}", json={"email": "anna@example.org"}).status_code == 200
        r = uebernehmen(lehrgang_id=str(lid), zuordnung=json.dumps(ueber))
        assert r.status_code == 201, (r.status_code, r.get_json())
        e = r.json
        assert (e["angelegt"], e["aktualisiert"], e["voraussetzungen_neu"], e["ausbilder_neu"]) == (0, TN_ERWARTET, 0, 0), e
        lg = e["lehrgang"]
        assert lg["tn_anzahl"] == TN_ERWARTET and len(lg["voraussetzungen"]) == 15 and len(lg["ausbilder"]) == 2
        tn = {(t["vorname"], t["name"]): t for t in lg["teilnehmer"]}
        assert tn[("Anna", "Beispiel")]["id"] == anna["id"] and tn[("Anna", "Beispiel")]["email"] == "anna@example.org"
        # Ein „nein“ in der Datei nimmt den Haken nicht weg; ein Import setzt einen entfernten wieder (Datei sagt ja).
        assert tn[("Emil", "Fiktiv")]["voraussetzungen"][letzte]["erfuellt"] is True
        assert tn[("Emil", "Fiktiv")]["voraussetzungen"][letzte]["quelle"] == "manuell"
        st = tn[("Anna", "Beispiel")]["voraussetzungen"][mindest]
        assert st["erfuellt"] is True and st["quelle"] == "import", st
        r = pr.get(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{mindest}/verlauf")
        assert [x["quelle"] for x in r.json["verlauf"]] == ["import", "manuell", "import"], r.json["verlauf"]
        # Ein bereits erfüllter Haken bekommt keinen weiteren Verlaufseintrag.
        frida = tn[("Frida", "Erdacht")]
        r = pr.get(f"/api/pruefungen/teilnehmer/{frida['id']}/voraussetzungen/{mindest}/verlauf")
        assert len(r.json["verlauf"]) == 1, r.json["verlauf"]

        # --- Import in einen von Hand angelegten Lehrgang: leere Felder füllen, gefüllte lassen ---------------
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Manuell angelegt", "ort": "Eigener Ort"})
        manuell = r.json["lehrgang"]["id"]
        assert pr.post(f"/api/pruefungen/lehrgaenge/{manuell}/teilnehmer",
                       json={"name": "Muster", "vorname": "Bert"}).status_code == 201      # ohne Geburtsdatum → passt trotzdem
        assert pr.post(f"/api/pruefungen/lehrgaenge/{manuell}/voraussetzungen",
                       json={"bezeichnung": "mitgliedschaft  in der dlrg"}).status_code == 201   # gleichnamig (normalisiert)
        r = vorschau(lehrgang_id=str(manuell), zuordnung=json.dumps(ueber))
        assert r.status_code == 200
        tnv = {(t["vorname"], t["name"]): t["vorhanden"] for t in r.json["teilnehmer"]}
        assert tnv[("Bert", "Muster")] is True and tnv[("Anna", "Beispiel")] is False, tnv
        vorh = {vs["bezeichnung"]: vs["vorhanden"] for vs in r.json["voraussetzungen"]}
        assert vorh["Mitgliedschaft in der DLRG"] is True and vorh["Sprechfunkunterweisung"] is False, vorh
        r = uebernehmen(lehrgang_id=str(manuell), zuordnung=json.dumps(ueber))
        assert r.status_code == 201, (r.status_code, r.get_json())
        e = r.json
        assert (e["angelegt"], e["aktualisiert"], e["voraussetzungen_neu"], e["ausbilder_neu"]) == (TN_ERWARTET - 1, 1, 14, 1), e
        lg = e["lehrgang"]
        assert lg["titel"] == "Manuell angelegt" and lg["ort"] == "Eigener Ort", lg          # gefüllt bleibt
        assert lg["nummer"] == "2026-0042" and lg["datum_von"] == "2026-12-04" and lg["datum_bis"] == "2026-12-13"  # leer wird gefüllt
        assert len(lg["voraussetzungen"]) == 15 and lg["tn_anzahl"] == TN_ERWARTET
        bert2 = [t for t in lg["teilnehmer"] if t["name"] == "Muster"][0]
        assert bert2["geburtsdatum"] == "2004-05-06" and bert2["gliederung"] == "OG Süd", bert2   # leere Felder gefüllt
        assert pr.post("/api/pruefungen/import", data={"file": (excel_bauen(), "x.xlsx"), "lehrgang_id": "999999"},
                       headers=H, content_type="multipart/form-data").status_code == 404

        # --- Datei ohne Kopfbereich: der Titel kommt aus dem Dateinamen -----------------------------------------
        r = pr.post("/api/pruefungen/import", data={"file": (excel_bauen(kopf=False), "Herbstlehrgang 2026.xlsx")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, (r.status_code, r.get_json())
        assert r.json["lehrgang"]["titel"] == "Herbstlehrgang 2026" and r.json["lehrgang"]["nummer"] == "", r.json["lehrgang"]
        assert r.json["lehrgang"]["datum_von"] is None and r.json["angelegt"] == TN_ERWARTET
        assert len(r.json["lehrgang"]["voraussetzungen"]) == 19          # ohne Überschreibung zählen die Verwaltungsspalten mit

        # Die Lehrgangsliste zeigt alle drei Importe mit Jahr 2026.
        assert len(pr.get("/api/pruefungen/lehrgaenge?jahr=2026").json["lehrgaenge"]) == 2
        assert len(pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]) == 3
        print("Import-Test bestanden.")


def test_import_modul():
    """Die reinen Funktionen des Import-Moduls, ohne Flask."""
    from app import pruefungen_import as pi
    assert pi.normalisiert("  Mitgliedschaft\nin  der DLRG ") == "mitgliedschaft in der dlrg"
    assert pi.datum_lesen("2002-10-03 00:00:00") == "2002-10-03"
    assert pi.datum_lesen("03.10.2002") == "2002-10-03"
    assert pi.datum_lesen("03.10.02") == "2002-10-03"
    assert pi.datum_lesen(datetime(2004, 5, 6, 12, 0)) == "2004-05-06"
    assert pi.datum_lesen("kein Datum") is None and pi.datum_lesen(None) is None and pi.datum_lesen("") is None
    assert pi.zeitraum_lesen("04.12.2026 18:00 Uhr bis 13.12.2026 19:00 Uhr") == ("2026-12-04", "2026-12-13")
    assert pi.zeitraum_lesen("2026-12-04") == ("2026-12-04", "2026-12-04")
    assert pi.zeitraum_lesen("") == (None, None)
    for ja in ("ja", "J", "x", "✓", "✔", "wahr", "true", "yes", 1, "1", "ok", "erfüllt", "vorhanden", datetime(2026, 1, 1), "12.03.2025"):
        assert pi.ist_erfuellt(ja) is True, ja
    for nein in ("nein", "n", "-", "–", "falsch", "false", "no", 0, "0", "offen", "fehlt", "", None):
        assert pi.ist_erfuellt(nein) is False, nein
    a = pi.schluessel(" Anna ", "Beispiel", "2002-10-03")
    assert a == ("anna", "beispiel", "2002-10-03")
    assert pi.passt(a, pi.schluessel("anna", "BEISPIEL", None)) is True       # fehlendes Datum passt auf alles
    assert pi.passt(a, pi.schluessel("Anna", "Beispiel", "2002-10-04")) is False
    assert pi.passt(a, pi.schluessel("Anne", "Beispiel", "2002-10-03")) is False
    assert set(pi.ZUORDNUNGEN) == {"vorname", "name", "geburtsdatum", "gliederung", "email", "rolle", "bemerkung",
                                   "extra", "voraussetzung", "ignorieren"}
    erg = pi.analysieren(excel_bauen().getvalue(), dateiname="x.xlsx")
    assert erg["kopfzeile"] == 7 and len(erg["teilnehmer"]) == TN_ERWARTET and len(erg["voraussetzungen"]) == 19
    assert erg["lehrgang"]["nummer"] == "2026-0042"
    erg = pi.analysieren(excel_bauen(), zuordnung={2: "ignorieren"})
    assert all(t["geburtsdatum"] is None for t in erg["teilnehmer"])
    # Ein voller Name in „Name“ ohne Vorname wird geteilt: letztes Wort Nachname.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Name", "Gliederung", "Bemerkung"])
    ws.append(["Max Michael Mustermann", "OG Nord", "kommt später"])
    ws.append(["Nur Nachname", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    erg = pi.analysieren(buf.getvalue())
    assert erg["kopfzeile"] == 1
    assert (erg["teilnehmer"][0]["vorname"], erg["teilnehmer"][0]["name"]) == ("Max Michael", "Mustermann"), erg["teilnehmer"][0]
    try:
        pi.analysieren(b"kein zip")
        raise AssertionError("unlesbare Datei muss ImportFehler werfen")
    except pi.ImportFehler:
        pass
    assert issubclass(pi.ImportFehler, ValueError)
    print("Import-Modul-Test bestanden.")


def _xlsx(zeilen):
    """Kleine Arbeitsmappe aus einer Liste von Zeilen – für die Sonderfälle des Imports."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for r, zeile in enumerate(zeilen, start=1):
        for c, wert in enumerate(zeile, start=1):
            if wert is not None:
                ws.cell(row=r, column=c, value=wert)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _import(client, buf, name="liste.xlsx", **form):
    data = {"file": (buf, name)}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/pruefungen/import", data=data, headers=H, content_type="multipart/form-data")


def _vorschau(client, buf, name="liste.xlsx", **form):
    data = {"file": (buf, name)}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/pruefungen/import/vorschau", data=data, headers=H, content_type="multipart/form-data")


def test_nachtraege():
    """Nachträge aus der Durchsicht: strenge Zeitangaben, echte Wahrheitswerte, Namens-Schnappschüsse
    über Umbenennen und Löschen eines Kontos hinweg, Löschregeln, Grenzen der Zelle, Importsonderfälle."""
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        assert adm.put(f"/api/admin/users/{pr_id}", json={"is_pruefer": True}).status_code == 200
        lg = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Nachträge", "datum_von": "2026-05-01",
                                                          "datum_bis": "2026-05-03"}).json["lehrgang"]
        lid = lg["id"]
        anna = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Beispiel", "vorname": "Anna"}).json["teilnehmer"]
        bert = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Muster", "vorname": "Bert"}).json["teilnehmer"]

        # --- Zeitangaben: nur echtes mm:ss, Einzelteile 0–59, keine Python-Literale --------------
        def leistung(zeit):
            return pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": f"L {zeit}", "zeitansatz_sekunden": zeit})
        for schlecht in ("1:90", "1:-5", "-0:30", "1_0:00", "1:1e2", "0:60", "a:b", "1:2:3:4"):
            r = leistung(schlecht)
            assert r.status_code == 400, (schlecht, r.status_code, r.get_json())
        erwartet = {"02:30": 150, "90": 90, "1:02:03": 3723, "0:59": 59, "2:31.4": 151, "2:31,6": 152}
        for gut, sek in erwartet.items():
            r = leistung(gut)
            assert r.status_code == 201 and r.json["leistung"]["zeitansatz_sekunden"] == sek, (gut, r.get_json())
        l1 = leistung("03:00").json["leistung"]

        # --- Wahrheitswerte: Texte wie „false“ zählen nicht als wahr ------------------------------
        v1 = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": "DRSA"}).json["voraussetzung"]
        for falsch in (False, "false", "0", "nein"):
            r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{v1['id']}", json={"erfuellt": falsch})
            assert r.status_code == 200 and r.json["status"]["erfuellt"] is False, (falsch, r.get_json())
        for wahr in (True, "true", "1", "ja"):
            r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{v1['id']}", json={"erfuellt": wahr})
            assert r.status_code == 200 and r.json["status"]["erfuellt"] is True, (wahr, r.get_json())
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{v1['id']}", json={"erfuellt": "quatsch"}).status_code == 400
        zelle = f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{l1['id']}/versuche"
        b1 = pr.post(zelle, json={"ergebnis": "mangelhaft", "kommentar": "zu langsam"}).json["versuch"]
        # Die Zelle im Lehrgangsdetail trägt den Kommentar des letzten Versuchs – für die Liste je Person.
        z = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        z = next(t for t in z["teilnehmer"] if t["id"] == anna["id"])["leistungen"][str(l1["id"])]
        assert z["letzter_kommentar"] == "zu langsam" and z["letzte_zeit_sekunden"] is None, z
        r = pr.post(zelle, json={"ergebnis": "bestanden", "nachpruefung": "false"})
        assert r.status_code == 409, r.get_json()
        r = pr.post(zelle, json={"ergebnis": "bestanden", "nachpruefung": "vielleicht"})
        assert r.status_code == 400, r.get_json()

        # --- Zelle: Person und Leistung müssen zum selben Lehrgang gehören ---------------------------
        fremd = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Fremd"}).json["lehrgang"]
        fl = pr.post(f"/api/pruefungen/lehrgaenge/{fremd['id']}/leistungen", json={"bezeichnung": "Fremde Leistung"}).json["leistung"]
        for methode in (pr.get, lambda u: pr.post(u, json={"ergebnis": "bestanden"})):
            r = methode(f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{fl['id']}/versuche")
            assert r.status_code == 400 and "gehört nicht" in r.json["error"], r.get_json()

        # --- Zwei Prüfer: der Verlauf nennt, wer den ALTEN Stand geschrieben hatte -----------------
        assert adm.put(f"/api/admin/users/{nix_id}", json={"is_pruefer": True}).status_code == 200
        r = nix.put(f"/api/pruefungen/versuche/{b1['id']}", json={"ergebnis": "mangelhaft", "kommentar": "zu langsam, Seil verdreht", "zeit_sekunden": 200})
        assert r.status_code == 200, r.get_json()
        v = r.json["versuch"]
        assert v["bearbeitet_von_name"] == "Rainer Redakteur" and v["geprueft_von_name"] == "Petra Prüferin"
        assert v["verlauf"][0]["von_name"] == "Petra Prüferin" and v["verlauf"][0]["kommentar"] == "zu langsam", v["verlauf"]
        r = pr.put(f"/api/pruefungen/versuche/{b1['id']}", json={"ergebnis": "mangelhaft", "kommentar": "endgültig", "zeit_sekunden": 200})
        v = r.json["versuch"]
        assert v["bearbeitet_von_name"] == "Petra Prüferin"
        assert sorted(e["von_name"] for e in v["verlauf"]) == ["Petra Prüferin", "Rainer Redakteur"], v["verlauf"]
        # Der Verlauf ist nach Gültigkeitsbeginn sortiert (Zeitstempel in Sekunden – deshalb nicht
        # über ersetzt_am vergleichen, zwei Bearbeitungen in derselben Sekunde hätten denselben).
        neuester = v["verlauf"][-1]
        assert neuester["von_name"] == "Rainer Redakteur" and neuester["kommentar"] == "zu langsam, Seil verdreht", v["verlauf"]
        # Auf den mangelhaften Versuch folgt eine Nachprüfung durch Rainer – Versuch 1 darf danach nicht mehr „bestanden“ werden.
        np1 = nix.post(zelle, json={"ergebnis": "mangelhaft", "kommentar": "wieder zu langsam", "nachpruefung": True}).json["versuch"]
        assert np1["geprueft_von_name"] == "Rainer Redakteur" and np1["versuch_nr"] == 2
        r = pr.put(f"/api/pruefungen/versuche/{b1['id']}", json={"ergebnis": "bestanden", "kommentar": "endgültig", "zeit_sekunden": 200})
        assert r.status_code == 409 and "Nachprüfung" in r.json["error"], r.get_json()
        medien_nix = lade_medien(nix, np1["id"])
        # Die Zelle zählt ihre Anhänge über alle Versuche – die Übersichten zeigen dafür eine Büroklammer.
        zellen = {t["id"]: t["leistungen"] for t in pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["teilnehmer"]}
        assert zellen[anna["id"]][str(l1["id"])]["medien_anzahl"] == 2, zellen[anna["id"]]
        r = nix.put(f"/api/pruefungen/teilnehmer/{bert['id']}/voraussetzungen/{v1['id']}", json={"erfuellt": True})
        assert r.json["status"]["gesetzt_von_name"] == "Rainer Redakteur"

        # --- Namens-Schnappschüsse überleben Umbenennen und Löschen des Kontos -------------------
        assert adm.put(f"/api/admin/users/{nix_id}", json={"name": "Rainer Umbenannt"}).status_code == 200
        v = pr.get(zelle).json["versuche"]
        assert v[0]["bearbeitet_von_name"] == "Petra Prüferin" and v[1]["geprueft_von_name"] == "Rainer Redakteur"
        assert adm.delete(f"/api/admin/users/{nix_id}", headers=H).status_code == 200
        r = pr.get(zelle)
        assert r.status_code == 200
        v = r.json["versuche"]
        assert v[1]["geprueft_von_name"] == "Rainer Redakteur" and v[1]["medien"][0]["hochgeladen_von_name"] == "Rainer Redakteur"
        assert any(e["von_name"] == "Rainer Redakteur" for e in v[0]["verlauf"])
        det = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        bert_det = next(t for t in det["teilnehmer"] if t["id"] == bert["id"])
        assert bert_det["voraussetzungen"][str(v1["id"])]["gesetzt_von_name"] == "Rainer Redakteur"
        for m in medien_nix:
            assert pr.get(m["thumb"]).status_code == 200

        # --- Versuch mit Medien löschen räumt die Dateien weg ------------------------------------------
        pfade = [p for m in medien_nix for p in medien_dateien(tmp, m)]
        assert all(os.path.exists(p) for p in pfade)
        assert pr.delete(f"/api/pruefungen/versuche/{np1['id']}", headers=H).status_code == 200
        assert not any(os.path.exists(p) for p in pfade), pfade
        zellen = {t["id"]: t["leistungen"] for t in pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["teilnehmer"]}
        assert zellen[anna["id"]][str(l1["id"])]["medien_anzahl"] == 0
        assert pr.get(medien_nix[0]["thumb"]).status_code == 404

        # --- Voraussetzung mit gesetzten Haken löschen: Zähler und Verlauf folgen ----------------------
        v2 = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": "EH-Kurs"}).json["voraussetzung"]
        det = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert next(t for t in det["teilnehmer"] if t["id"] == bert["id"])["voraussetzungen_offen"] == 1   # DRSA gesetzt, EH offen
        assert pr.delete(f"/api/pruefungen/voraussetzungen/{v1['id']}", headers=H).status_code == 200
        det = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        bert_det = next(t for t in det["teilnehmer"] if t["id"] == bert["id"])
        assert bert_det["voraussetzungen_offen"] == 1 and str(v1["id"]) not in bert_det["voraussetzungen"]
        assert pr.get(f"/api/pruefungen/teilnehmer/{bert['id']}/voraussetzungen/{v1['id']}/verlauf").status_code == 404
        liste = next(x for x in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if x["id"] == lid)
        assert liste["voraussetzungen_offen"] == 2          # Anna und Bert: EH-Kurs offen
        pr.delete(f"/api/pruefungen/voraussetzungen/{v2['id']}", headers=H)

        # --- Kopie: Titelgrenze gilt auch für den Vorgabetitel -------------------------------------------
        lang = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "x" * 200}).json["lehrgang"]
        k = pr.post(f"/api/pruefungen/lehrgaenge/{lang['id']}/kopieren", json={}).json["lehrgang"]
        assert len(k["titel"]) <= 200 and k["titel"].endswith("(Kopie)"), k["titel"]

        # --- Import-Sonderfälle ------------------------------------------------------------------------
        KOPF2 = ["Vorname", "Nachname", "Rolle", "Anmeldung", "DRSA Silber"]
        r = _vorschau(pr, _xlsx([KOPF2,
                                ["Nurvorname", None, "Teilnehmender", "2026-01-05", "ja"],
                                [None, "Mustermann, Max", "TN", "2026-01-06", "nein"],
                                ["Gerda", "Gast", "Beobachter", "2026-01-07", "ja"],
                                ["Lena", "Leitung", "Lehrgangsleitung", "2026-01-08", None]]))
        assert r.status_code == 200, r.get_json()
        v = r.json
        namen = {(t["vorname"], t["name"]) for t in v["teilnehmer"]}
        assert namen == {("Max", "Mustermann"), ("Gerda", "Gast")}, namen          # Komma getrennt; „TN“ und eine unbekannte Rolle bleiben Teilnehmende
        assert [a["name"] for a in v["ausbilder"]] == ["Lena Leitung"]
        assert any("Nurvorname" in w and "Nachname" in w for w in v["warnungen"]), v["warnungen"]
        assert any("Beobachter" in w and "unbekannt" in w for w in v["warnungen"]), v["warnungen"]
        zu = {s["titel"]: s["zuordnung"] for s in v["spalten"]}
        assert zu["Anmeldung"] == "extra" and zu["DRSA Silber"] == "voraussetzung", zu   # reine Datumsspalte ist keine Voraussetzung
        # Zwei Titel genügen als Kopfzeile, wenn ein Namens-Titel dabei ist.
        r = _vorschau(pr, _xlsx([["Vorname", "Nachname"], ["Ida", "Zwei"]]))
        assert r.status_code == 200 and len(r.json["teilnehmer"]) == 1, r.get_json()
        # Ohne erkennbare Namensspalte: keine Fehlermeldung, sondern eine korrigierbare Vorschau.
        r = _vorschau(pr, _xlsx([["Person", "Gruppe", "Zahlung"], ["Otto Ohne", "OG A", "ja"], ["Paula Ohne", "OG B", "nein"]]))
        assert r.status_code == 200 and r.json["teilnehmer"] == [] and any("Nachname" in w for w in r.json["warnungen"]), r.get_json()
        assert _import(pr, _xlsx([["Person", "Gruppe", "Zahlung"], ["Otto Ohne", "OG A", "ja"]])).status_code == 400
        r = _vorschau(pr, _xlsx([["Person", "Gruppe", "Zahlung"], ["Otto Ohne", "OG A", "ja"]]), zuordnung=json.dumps({"0": "name"}))
        assert r.status_code == 200 and [(t["vorname"], t["name"]) for t in r.json["teilnehmer"]] == [("Otto", "Ohne")], r.get_json()
        # Verdrehter Zeitraum wird gedreht; ein unpassender Zeitraum füllt einen Lehrgang nicht.
        r = _import(pr, _xlsx([["Zeitraum", "13.12.2026 bis 04.12.2026"], [], ["Vorname", "Nachname"], ["Ida", "Drei"]]))
        assert r.status_code == 201, r.get_json()
        assert (r.json["lehrgang"]["datum_von"], r.json["lehrgang"]["datum_bis"]) == ("2026-12-04", "2026-12-13")
        assert any("gedreht" in w for w in r.json["warnungen"]), r.json["warnungen"]
        halb = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Halb", "datum_bis": "2026-01-05"}).json["lehrgang"]
        r = _import(pr, _xlsx([["Zeitraum", "10.01.2026 bis 12.01.2026"], [], ["Vorname", "Nachname"], ["Ida", "Vier"]]), lehrgang_id=halb["id"])
        assert r.status_code == 201 and r.json["lehrgang"]["datum_von"] is None and r.json["lehrgang"]["datum_bis"] == "2026-01-05", r.get_json()
        assert any("nicht übernommen" in w for w in r.json["warnungen"]), r.json["warnungen"]
        assert pr.put(f"/api/pruefungen/lehrgaenge/{halb['id']}", json={"status": "laufend"}).status_code == 200
        # Gleichnamige Teilnehmende: ohne Geburtsdatum in der Datei wird nicht geraten.
        zw = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Zwillinge"}).json["lehrgang"]
        for geb in ("2005-01-01", "2006-02-02"):
            pr.post(f"/api/pruefungen/lehrgaenge/{zw['id']}/teilnehmer", json={"name": "Doppel", "vorname": "Dana", "geburtsdatum": geb})
        r = _vorschau(pr, _xlsx([["Vorname", "Nachname", "EH"], ["Dana", "Doppel", "ja"]]), lehrgang_id=zw["id"])
        assert r.status_code == 200 and r.json["teilnehmer"][0]["mehrdeutig"] is True and any("2 Teilnehmende" in w for w in r.json["warnungen"]), r.get_json()
        r = _import(pr, _xlsx([["Vorname", "Nachname", "EH"], ["Dana", "Doppel", "ja"]]), lehrgang_id=zw["id"])
        assert r.status_code == 201 and r.json["angelegt"] == 0 and r.json["aktualisiert"] == 0 and len(r.json["lehrgang"]["teilnehmer"]) == 2, r.get_json()
        # Titellose Voraussetzungsspalte bekommt einen Ersatznamen statt stumm zu verschwinden.
        r = _import(pr, _xlsx([["Vorname", "Nachname", None], ["Ida", "Fünf", "ja"]]), zuordnung=json.dumps({"2": "voraussetzung"}))
        assert r.status_code == 201 and [x["bezeichnung"] for x in r.json["lehrgang"]["voraussetzungen"]] == ["Spalte C"], r.get_json()
        # Die Importgrenze liegt weit unter der Filmgrenze.
        r = pr.post("/api/pruefungen/import/vorschau", data={"file": (io.BytesIO(b"\0" * (26 * 1024 * 1024)), "riesig.xlsx")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 413, r.status_code
        print("Nachträge-Test bestanden.")




# ----------------------------------------------------------------------------------------------------
# Runde 2: Leitungsrechte, Profilbild, Kommentar, Lehrgangsergebnis, Einfrieren, Beispieldaten
# ----------------------------------------------------------------------------------------------------

# Die 17 Prüfungsleistungen der Checkliste „Beurteilung Strömungsretter 2“ – Reihenfolge ist Teil der Vorgabe.
SR2_LEISTUNGEN = (
    "Beherrschen der Standardknoten für SR", "Beherrschen der Anker", "Standardverfahren Flachseilbrücke",
    "Standardverfahren Schräghangrettung", "Standardverfahren Abseilen", "Notverfahren",
    "Führungsverhalten (Fachtechnisch)",
    "Sicherheitsbewusstsein (Gefährdungsbeurteilung, Schaffen von Sicherheit, Eigensicherung)",
    "Teamfähigkeit (Seiltechnik)", "Wurfsack", "Springersperre", "Grundlagen Raft", "Raftfähre", "Einsätze bei Nacht",
    "Rettungstechniken im/am strömenden Gewässer", "Führungsverhalten (Wasser)", "Teamfähigkeit (Wasser)",
)
TN_FELDER2 = TN_FELDER + ("bild", "kommentar", "ergebnis", "ergebnis_von_name", "ergebnis_am", "eingefroren")
LEHRGANG_KURZ2 = LEHRGANG_KURZ + ("darf_leiten", "ergebnis_bestanden", "ergebnis_nicht_bestanden")


def bild_hochladen(client, tid, name="portrait.jpg", inhalt=None):
    """Profilbild an eine Person hängen – Multipart mit Feld „file“, wie es der Browser schickt."""
    return client.post(f"/api/pruefungen/teilnehmer/{tid}/bild", data={"file": (inhalt or jpeg(), name)}, headers=H,
                       content_type="multipart/form-data")


def png():
    """Ein hochkantiges grünes PNG – prüft, dass auch ein anderes Format und Seitenverhältnis zum
    quadratischen Profilbild wird."""
    buf = io.BytesIO()
    Image.new("RGB", (300, 500), (20, 120, 20)).save(buf, "PNG")
    buf.seek(0)
    return buf


def bild_pfad(tmp, tn):
    """Datei auf dem Datenträger zur Bild-URL eines TN – abgeleitet aus der Antwort, nicht geraten."""
    assert tn["bild"] and tn["bild"].startswith("/media/pruefung/avatar/") and tn["bild"].endswith(".jpg"), tn["bild"]
    return os.path.join(tmp, "media", "pruefungen", "avatar", tn["bild"].rsplit("/", 1)[1])


def leitung_von(lg, user_id):
    """Einträge der Ausbilderliste, die diesen Nutzer als Leitung führen (Funktion enthält „leit“)."""
    return [a for a in lg["ausbilder"] if a["user_id"] == user_id and "leit" in (a["funktion"] or "").lower()]


def test_rechte_und_ergebnis():
    """Runde 2: Nur Leitung (Ausbilderliste mit eigener user_id und Leitungsfunktion) oder Administration
    darf Stammdaten, Definitionen und Versuche löschen bzw. bearbeiten; alle Prüfenden bewerten, haken ab
    und kommentieren. Dazu Profilbilder, das Lehrgangsergebnis mit Einfrieren und die Beispieldaten."""
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        anon = app.test_client()
        adm_id = adm.get("/api/me").json["user"]["id"]
        assert adm.put(f"/api/admin/users/{pr_id}", json={"is_pruefer": True}).status_code == 200
        # Ein zweiter Prüfer ohne Leitungsfunktion – an ihm wird die Rechtematrix durchgespielt.
        r = adm.post("/api/admin/users", json={"email": "zweit@example.org", "password": "passwort1",
                                               "name": "Zacharias Zweitprüfer", "gliederung": "OG Musterstadt",
                                               "role": "editor", "is_pruefer": True})
        assert r.status_code == 201, r.json
        zweit_id = r.json["user"]["id"]
        zweit = app.test_client()
        assert zweit.post("/api/auth/login", json={"email": "zweit@example.org", "password": "passwort1"}).status_code == 200
        assert zweit.get("/api/me").json["user"]["is_pruefer"] is True

        # --- A. Anlegen: der Anleger wird automatisch Lehrgangsleitung ------------------------------------
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Rechte-Lehrgang", "datum_von": "2026-06-01",
                                                          "datum_bis": "2026-06-03"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        lg = r.json["lehrgang"]
        hat_felder(lg, *LEHRGANG_KURZ2, "ausbilder")
        lid = lg["id"]
        assert lg["darf_leiten"] is True and lg["ergebnis_bestanden"] == 0 and lg["ergebnis_nicht_bestanden"] == 0, lg
        eintrag = leitung_von(lg, pr_id)
        assert len(eintrag) == 1 and eintrag[0]["funktion"] == "Lehrgangsleitung" and eintrag[0]["name"] == "Petra Prüferin", lg["ausbilder"]
        # Steht der Anleger schon als Leitung in der Liste, wird er nicht verdoppelt; Externe bleiben erhalten.
        r = pr.post("/api/pruefungen/lehrgaenge", json={
            "titel": "Schon Leitung",
            "ausbilder": [{"user_id": pr_id, "funktion": "Leitung"},
                          {"user_id": None, "name": "Erwin Extern", "funktion": "Referierende:r"}]})
        assert r.status_code == 201, r.get_json()
        assert len(leitung_von(r.json["lehrgang"], pr_id)) == 1 and len(r.json["lehrgang"]["ausbilder"]) == 2, r.json["lehrgang"]["ausbilder"]
        assert r.json["lehrgang"]["darf_leiten"] is True
        schon = r.json["lehrgang"]["id"]
        # Steht er nur als Referierende:r drin, kommt die Leitung dazu.
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Nur Referent",
                                                          "ausbilder": [{"user_id": pr_id, "funktion": "Referierende:r"}]})
        assert r.status_code == 201 and len(leitung_von(r.json["lehrgang"], pr_id)) == 1, r.get_json()
        assert r.json["lehrgang"]["darf_leiten"] is True
        nur_ref = r.json["lehrgang"]["id"]
        # Ein Administrator mit Prüferrecht braucht keinen Eintrag – und bekommt auch keinen.
        assert adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Admin-Lehrgang"}).status_code == 403   # noch ohne Flag
        assert adm.put(f"/api/admin/users/{adm_id}", json={"is_pruefer": True}).status_code == 200
        r = adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Admin-Lehrgang"})
        assert r.status_code == 201, r.get_json()
        admin_lg = r.json["lehrgang"]
        assert admin_lg["ausbilder"] == [] and admin_lg["darf_leiten"] is True, admin_lg
        # Der zweite Prüfer sieht denselben Lehrgang, darf ihn aber nicht leiten – seinen eigenen schon.
        assert pr.get(f"/api/pruefungen/lehrgaenge/{admin_lg['id']}").json["lehrgang"]["darf_leiten"] is False
        assert zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["darf_leiten"] is False
        r = zweit.post("/api/pruefungen/lehrgaenge", json={"titel": "Zweits Lehrgang"})
        assert r.status_code == 201 and r.json["lehrgang"]["darf_leiten"] is True and len(leitung_von(r.json["lehrgang"], zweit_id)) == 1, r.get_json()
        zweits = r.json["lehrgang"]["id"]
        liste = {e["id"]: e for e in zweit.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]}
        for e in liste.values():
            hat_felder(e, *LEHRGANG_KURZ2)
        assert liste[lid]["darf_leiten"] is False and liste[zweits]["darf_leiten"] is True and liste[admin_lg["id"]]["darf_leiten"] is False
        assert all(e["darf_leiten"] for e in adm.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]), "Admin leitet alles"
        liste_pr = {e["id"]: e["darf_leiten"] for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]}
        assert liste_pr[lid] is True and liste_pr[zweits] is False and liste_pr[admin_lg["id"]] is False, liste_pr
        # Import ohne lehrgang_id legt einen Lehrgang an – der Importierende wird Leitung.
        r = _import(zweit, _xlsx([["Vorname", "Nachname", "DRSA Silber"], ["Ida", "Import", "ja"]]), name="Import-Lehrgang.xlsx")
        assert r.status_code == 201, (r.status_code, r.get_json())
        imp_lg = r.json["lehrgang"]
        assert imp_lg["darf_leiten"] is True and len(leitung_von(imp_lg, zweit_id)) == 1, imp_lg["ausbilder"]
        assert pr.get(f"/api/pruefungen/lehrgaenge/{imp_lg['id']}").json["lehrgang"]["darf_leiten"] is False

        # --- A. Aufbau durch die Leitung (alles 200/201) --------------------------------------------------
        vor = [pr.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": b}).json["voraussetzung"]
               for b in ("DRSA Silber", "Tauglichkeit")]
        lei = [pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": b, "zeitansatz_sekunden": z}).json["leistung"]
               for b, z in (("Wurfsackwurf", "01:30"), ("Standardknoten", "00:15"))]
        anna = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Beispiel", "vorname": "Anna"}).json["teilnehmer"]
        bert = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Muster", "vorname": "Bert"}).json["teilnehmer"]
        clara = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Probe", "vorname": "Clara"}).json["teilnehmer"]
        for t in (anna, bert, clara):
            hat_felder(t, *TN_FELDER2)
            assert t["bild"] is None and t["kommentar"] == "" and t["ergebnis"] is None and t["eingefroren"] is False, t
            assert t["ergebnis_von_name"] == "" and t["ergebnis_am"] is None, t
        zelle_anna = f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{lei[0]['id']}/versuche"
        zelle_bert = f"/api/pruefungen/teilnehmer/{bert['id']}/leistungen/{lei[0]['id']}/versuche"
        zelle_clara = f"/api/pruefungen/teilnehmer/{clara['id']}/leistungen/{lei[0]['id']}/versuche"

        # --- A. Prüfer ohne Leitung: 403 auf allen Leitungsrouten -------------------------------------------
        def leitung_noetig(r):
            assert r.status_code == 403, (r.status_code, r.get_json())
            assert "Lehrgangsleitung" in r.json["error"], r.json
        leitung_noetig(zweit.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ort": "Fremdstadt"}))
        leitung_noetig(zweit.delete(f"/api/pruefungen/lehrgaenge/{lid}", headers=H))
        leitung_noetig(zweit.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={}))
        leitung_noetig(_import(zweit, _xlsx([["Vorname", "Nachname", "DRSA Silber"], ["Ida", "Import", "ja"]]), lehrgang_id=lid))
        leitung_noetig(zweit.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Eindringling"}))
        leitung_noetig(zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}", json={"vorname": "Annika"}))
        leitung_noetig(zweit.delete(f"/api/pruefungen/teilnehmer/{anna['id']}", headers=H))
        leitung_noetig(bild_hochladen(zweit, anna["id"]))
        leitung_noetig(zweit.delete(f"/api/pruefungen/teilnehmer/{anna['id']}/bild", headers=H))
        leitung_noetig(zweit.post(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": "Fremd"}))
        leitung_noetig(zweit.put(f"/api/pruefungen/voraussetzungen/{vor[0]['id']}", json={"bezeichnung": "Umbenannt"}))
        leitung_noetig(zweit.delete(f"/api/pruefungen/voraussetzungen/{vor[0]['id']}", headers=H))
        leitung_noetig(zweit.put(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen/reihenfolge", json={"ids": [vor[1]["id"], vor[0]["id"]]}))
        leitung_noetig(zweit.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Fremd"}))
        leitung_noetig(zweit.put(f"/api/pruefungen/leistungen/{lei[0]['id']}", json={"bezeichnung": "Umbenannt"}))
        leitung_noetig(zweit.delete(f"/api/pruefungen/leistungen/{lei[0]['id']}", headers=H))
        leitung_noetig(zweit.put(f"/api/pruefungen/lehrgaenge/{lid}/leistungen/reihenfolge", json={"ids": [lei[1]["id"], lei[0]["id"]]}))
        leitung_noetig(zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": "bestanden"}))
        assert zweit.post("/api/pruefungen/beispieldaten", json={}).status_code == 403
        # Nichts davon hat Spuren hinterlassen.
        det = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert det["ort"] == "" and [t["vorname"] for t in det["teilnehmer"]] == ["Anna", "Bert", "Clara"], det
        assert [v["id"] for v in det["voraussetzungen"]] == [vor[0]["id"], vor[1]["id"]]
        assert [l["bezeichnung"] for l in det["leistungen"]] == ["Wurfsackwurf", "Standardknoten"]
        assert det["ergebnis_bestanden"] == 0

        # --- A. Prüfer ohne Leitung: bewerten, Medien, abhaken, kommentieren, lesen -------------------------
        r = zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vor[0]['id']}", json={"erfuellt": True})
        assert r.status_code == 200 and r.json["status"]["gesetzt_von_name"] == "Zacharias Zweitprüfer", r.get_json()
        r = zweit.post(zelle_bert, json={"ergebnis": "mangelhaft", "kommentar": "Ziel verfehlt.", "zeit_sekunden": "01:45"})
        assert r.status_code == 201, (r.status_code, r.get_json())
        b1 = r.json["versuch"]
        r = zweit.put(f"/api/pruefungen/versuche/{b1['id']}", json={"ergebnis": "mangelhaft", "kommentar": "Ziel zweimal verfehlt.", "zeit_sekunden": 105})
        assert r.status_code == 200 and r.json["versuch"]["kommentar"] == "Ziel zweimal verfehlt.", r.get_json()
        medien_b1 = lade_medien(zweit, b1["id"])
        assert zweit.delete(f"/api/pruefungen/medien/{medien_b1[1]['id']}", headers=H).status_code == 200
        r = zweit.post(zelle_bert, json={"ergebnis": "bestanden", "nachpruefung": True, "kommentar": "Sauber."})
        assert r.status_code == 201, r.get_json()
        b2 = r.json["versuch"]
        r = zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "Sehr ruhig, gute Seilarbeit."})
        assert r.status_code == 200, (r.status_code, r.get_json())
        assert r.json["teilnehmer"]["kommentar"] == "Sehr ruhig, gute Seilarbeit." and r.json["teilnehmer"]["id"] == anna["id"], r.get_json()
        # Grenze 5000 Zeichen – wie beim Versuchskommentar wird gekappt statt abgewiesen; mehr landet nie in der Datenbank.
        r = zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "x" * 5001})
        assert r.status_code in (200, 400), (r.status_code, r.get_json())
        if r.status_code == 200:
            assert len(r.json["teilnehmer"]["kommentar"]) == 5000, len(r.json["teilnehmer"]["kommentar"])
        r = zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "x" * 5000})
        assert r.status_code == 200 and len(r.json["teilnehmer"]["kommentar"]) == 5000, r.status_code
        assert zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": 12}).status_code in (200, 400)
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "  Sehr ruhig.  "})
        assert r.status_code == 200 and r.json["teilnehmer"]["kommentar"].strip() == "Sehr ruhig.", r.get_json()
        assert zweit.put("/api/pruefungen/teilnehmer/999999/kommentar", json={"kommentar": "x"}).status_code == 404
        # Löschen eines Versuchs ist Leitungssache – auch des eigenen.
        leitung_noetig(zweit.delete(f"/api/pruefungen/versuche/{b2['id']}", headers=H))
        assert zweit.get(zelle_bert).status_code == 200 and zweit.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel").status_code == 200
        assert zweit.get(f"/api/pruefungen/teilnehmer/{bert['id']}/versuche").status_code == 200
        for m in medien_b1[:1]:
            assert zweit.get(m["thumb"]).status_code == 200
        det = zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert next(t for t in det["teilnehmer"] if t["id"] == anna["id"])["kommentar"] == "Sehr ruhig."
        # Ohne Prüferrecht bleibt alles zu – auch die neuen Routen.
        assert nix.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "x"}).status_code == 403
        assert nix.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": "bestanden"}).status_code == 403
        assert bild_hochladen(nix, anna["id"]).status_code == 403
        assert nix.post("/api/pruefungen/beispieldaten", json={}).status_code == 403

        # --- A. Leitung und Administration: dieselben Routen mit 200/201 ---------------------------------------
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ort": "Musterstadt"})
        assert r.status_code == 200 and r.json["lehrgang"]["ort"] == "Musterstadt", r.get_json()
        r = adm.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"nummer": "2026-0042"})
        assert r.status_code == 200 and r.json["lehrgang"]["nummer"] == "2026-0042", r.get_json()
        assert adm.put(f"/api/pruefungen/voraussetzungen/{vor[1]['id']}", json={"bezeichnung": "Ärztliche Tauglichkeit"}).status_code == 200
        assert pr.put(f"/api/pruefungen/leistungen/{lei[1]['id']}", json={"bezeichnung": "Standardknoten (15 s)"}).status_code == 200
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}/leistungen/reihenfolge", json={"ids": [l["id"] for l in lei]}).status_code == 200
        assert pr.put(f"/api/pruefungen/lehrgaenge/{lid}/voraussetzungen/reihenfolge", json={"ids": [v["id"] for v in vor]}).status_code == 200
        assert pr.delete(f"/api/pruefungen/versuche/{b2['id']}", headers=H).status_code == 200
        assert [v["id"] for v in pr.get(zelle_bert).json["versuche"]] == [b1["id"]]
        r = adm.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={"titel": "Kopie durch Admin"})
        assert r.status_code == 201, r.get_json()
        assert adm.delete(f"/api/pruefungen/lehrgaenge/{r.json['lehrgang']['id']}", headers=H).status_code == 200
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/kopieren", json={"titel": "Kopie durch Leitung"})
        assert r.status_code == 201, r.get_json()
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{r.json['lehrgang']['id']}", headers=H).status_code == 200
        r = _import(pr, _xlsx([["Vorname", "Nachname", "Ärztliche Tauglichkeit"], ["Dora", "Import", "ja"]]), lehrgang_id=lid)
        assert r.status_code == 201 and r.json["angelegt"] == 1, r.get_json()
        assert len(r.json["lehrgang"]["voraussetzungen"]) == 2, "gleichnamige Spalte wird wiederverwendet"
        dora = next(t for t in r.json["lehrgang"]["teilnehmer"] if t["vorname"] == "Dora")
        assert pr.delete(f"/api/pruefungen/teilnehmer/{dora['id']}", headers=H).status_code == 200
        # Leitung kommt und geht mit der Ausbilderliste: „Leiter:in“ zählt, „Referierende:r“ nicht.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ausbilder": [
            {"user_id": pr_id, "funktion": "Lehrgangsleitung"}, {"user_id": zweit_id, "funktion": "Leiter:in"}]})
        assert r.status_code == 200, r.get_json()
        assert zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["darf_leiten"] is True
        r = zweit.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"beschreibung": "Durch Zweit als Leitung"})
        assert r.status_code == 200 and r.json["lehrgang"]["beschreibung"] == "Durch Zweit als Leitung", r.get_json()
        # Wer die Liste bearbeitet, bleibt selbst als Leitung eingetragen – sonst stünde er sofort ohne Rechte da.
        r = zweit.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ausbilder": [
            {"user_id": pr_id, "funktion": "Lehrgangsleitung"}, {"user_id": zweit_id, "funktion": "Referierende:r"}]})
        assert r.status_code == 200 and r.json["lehrgang"]["darf_leiten"] is True, r.get_json()
        assert len(leitung_von(r.json["lehrgang"], zweit_id)) == 1 and len(leitung_von(r.json["lehrgang"], pr_id)) == 1, r.json["lehrgang"]["ausbilder"]
        # Die andere Leitung kann ihn aber herabstufen; danach greift die Sperre wieder.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ausbilder": [
            {"user_id": pr_id, "funktion": "Lehrgangsleitung"}, {"user_id": zweit_id, "funktion": "Referierende:r"}]})
        assert r.status_code == 200 and leitung_von(r.json["lehrgang"], zweit_id) == [], r.json["lehrgang"]["ausbilder"]
        assert any(a["user_id"] == zweit_id and a["funktion"] == "Referierende:r" for a in r.json["lehrgang"]["ausbilder"])
        assert zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["darf_leiten"] is False
        leitung_noetig(zweit.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"beschreibung": "geht nicht mehr"}))
        # Ein externer Eintrag mit gleichem Namen, aber ohne user_id, verleiht keine Leitung.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{lid}", json={"ausbilder": [
            {"user_id": pr_id, "funktion": "Lehrgangsleitung"}, {"user_id": None, "name": "Zacharias Zweitprüfer", "funktion": "Lehrgangsleitung"}]})
        assert r.status_code == 200, r.get_json()
        assert zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["darf_leiten"] is False
        # Eine leere Liste sperrt die einzige Leitung nicht aus; die Administration braucht keinen Eintrag.
        r = pr.put(f"/api/pruefungen/lehrgaenge/{nur_ref}", json={"ausbilder": []})
        assert r.status_code == 200 and len(leitung_von(r.json["lehrgang"], pr_id)) == 1 and r.json["lehrgang"]["darf_leiten"] is True, r.get_json()
        assert pr.put(f"/api/pruefungen/lehrgaenge/{nur_ref}", json={"titel": "Weiter Leitung"}).status_code == 200
        r = adm.put(f"/api/pruefungen/lehrgaenge/{admin_lg['id']}", json={"ausbilder": []})
        assert r.status_code == 200 and r.json["lehrgang"]["ausbilder"] == [] and r.json["lehrgang"]["darf_leiten"] is True, r.get_json()
        # Die Administration kann die letzte Leitung entfernen – dann bleibt nur sie selbst mit Rechten.
        r = adm.put(f"/api/pruefungen/lehrgaenge/{nur_ref}", json={"ausbilder": []})
        assert r.status_code == 200 and r.json["lehrgang"]["ausbilder"] == [], r.get_json()
        leitung_noetig(pr.put(f"/api/pruefungen/lehrgaenge/{nur_ref}", json={"titel": "Ausgesperrt"}))
        assert pr.get(f"/api/pruefungen/lehrgaenge/{nur_ref}").json["lehrgang"]["darf_leiten"] is False
        assert adm.delete(f"/api/pruefungen/lehrgaenge/{nur_ref}", headers=H).status_code == 200
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{schon}", headers=H).status_code == 200

        # --- B. Profilbild ------------------------------------------------------------------------------------
        r = bild_hochladen(pr, anna["id"], "anna.jpg")
        assert r.status_code == 200, (r.status_code, r.get_json())
        anna_b = r.json["teilnehmer"]
        hat_felder(anna_b, *TN_FELDER2)
        pfad1 = bild_pfad(tmp, anna_b)
        assert os.path.isfile(pfad1), pfad1
        with Image.open(pfad1) as im:
            assert im.size == (256, 256), im.size
        assert pr.get(anna_b["bild"]).status_code == 200
        assert zweit.get(anna_b["bild"]).status_code == 200            # jeder Prüfende sieht das Bild
        assert nix.get(anna_b["bild"]).status_code == 403
        assert anon.get(anna_b["bild"]).status_code in (302, 401)
        det = zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert next(t for t in det["teilnehmer"] if t["id"] == anna["id"])["bild"] == anna_b["bild"]
        # Erneut hochladen ersetzt die Datei; das alte Bild verschwindet vom Datenträger.
        r = bild_hochladen(adm, anna["id"], "anna2.png", inhalt=png())
        assert r.status_code == 200, (r.status_code, r.get_json())
        pfad2 = bild_pfad(tmp, r.json["teilnehmer"])
        assert pfad2 != pfad1 and os.path.isfile(pfad2) and not os.path.exists(pfad1), (pfad1, pfad2)
        assert pr.get(anna_b["bild"]).status_code == 404
        # Untaugliche Dateien: Klartext mit 400, Bestand bleibt.
        r = bild_hochladen(pr, anna["id"], "liste.txt", inhalt=io.BytesIO(b"kein bild"))
        assert r.status_code == 400 and r.json["error"], (r.status_code, r.get_json())
        r = bild_hochladen(pr, anna["id"], "kaputt.jpg", inhalt=io.BytesIO(b"\xff\xd8\xff kaputt"))
        assert r.status_code == 400 and r.json["error"], (r.status_code, r.get_json())
        r = pr.post(f"/api/pruefungen/teilnehmer/{anna['id']}/bild", data={}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 400, (r.status_code, r.get_json())
        assert bild_hochladen(pr, 999999).status_code == 404
        assert os.path.isfile(pfad2)
        # Entfernen: Feld leer, Datei weg; erneutes Entfernen bleibt ruhig.
        r = pr.delete(f"/api/pruefungen/teilnehmer/{anna['id']}/bild", headers=H)
        assert r.status_code == 200 and r.json["teilnehmer"]["bild"] is None, r.get_json()
        assert not os.path.exists(pfad2), pfad2
        r = pr.delete(f"/api/pruefungen/teilnehmer/{anna['id']}/bild", headers=H)
        assert r.status_code == 200 and r.json["teilnehmer"]["bild"] is None, r.get_json()
        assert pr.delete(f"/api/pruefungen/teilnehmer/{anna['id']}/bild").status_code == 403       # CSRF
        # TN löschen räumt das Bild weg.
        r = bild_hochladen(pr, clara["id"], "clara.jpg")
        assert r.status_code == 200, r.get_json()
        pfad_clara = bild_pfad(tmp, r.json["teilnehmer"])
        assert os.path.isfile(pfad_clara)
        assert pr.delete(f"/api/pruefungen/teilnehmer/{clara['id']}", headers=H).status_code == 200
        assert not os.path.exists(pfad_clara), pfad_clara
        clara = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Probe", "vorname": "Clara"}).json["teilnehmer"]
        zelle_clara = f"/api/pruefungen/teilnehmer/{clara['id']}/leistungen/{lei[0]['id']}/versuche"
        # Anna behält für den Rest ein Bild – das muss das Einfrieren überstehen.
        anna_b = bild_hochladen(pr, anna["id"], "anna3.jpg").json["teilnehmer"]
        pfad_anna = bild_pfad(tmp, anna_b)

        # --- B. Lehrgangsergebnis ------------------------------------------------------------------------------
        a1 = pr.post(zelle_anna, json={"ergebnis": "bestanden", "zeit_sekunden": "01:10"}).json["versuch"]
        medien_a1 = lade_medien(zweit, a1["id"], "anna_wurf.jpg")
        for schlecht in ("vielleicht", "BESTANDEN", "mangelhaft", 1, True, ["bestanden"]):
            r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": schlecht})
            assert r.status_code == 400, (schlecht, r.status_code, r.get_json())
        assert pr.put("/api/pruefungen/teilnehmer/999999/ergebnis", json={"ergebnis": "bestanden"}).status_code == 404
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": "bestanden"})
        assert r.status_code == 200, (r.status_code, r.get_json())
        anna_e = r.json["teilnehmer"]
        assert anna_e["ergebnis"] == "bestanden" and anna_e["eingefroren"] is True, anna_e
        assert anna_e["ergebnis_von_name"] == "Petra Prüferin" and anna_e["ergebnis_am"], anna_e
        datetime.fromisoformat(anna_e["ergebnis_am"].replace("Z", "+00:00"))
        assert anna_e["bild"] == anna_b["bild"] and anna_e["kommentar"] == "Sehr ruhig."
        # Die Administration setzt Berts Ergebnis; Namen und Zähler folgen.
        r = adm.put(f"/api/pruefungen/teilnehmer/{bert['id']}/ergebnis", json={"ergebnis": "nicht_bestanden"})
        assert r.status_code == 200, r.get_json()
        assert r.json["teilnehmer"]["ergebnis"] == "nicht_bestanden" and r.json["teilnehmer"]["ergebnis_von_name"] == "Administrator", r.get_json()
        det = zweit.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        assert det["ergebnis_bestanden"] == 1 and det["ergebnis_nicht_bestanden"] == 1, det
        tn = {t["id"]: t for t in det["teilnehmer"]}
        assert tn[anna["id"]]["eingefroren"] is True and tn[bert["id"]]["eingefroren"] is True and tn[clara["id"]]["eingefroren"] is False
        assert tn[anna["id"]]["ergebnis_am"] == anna_e["ergebnis_am"]
        kurz = next(e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid)
        assert kurz["ergebnis_bestanden"] == 1 and kurz["ergebnis_nicht_bestanden"] == 1, kurz
        # Umsetzen von bestanden auf nicht bestanden geht direkt (bleibt eingefroren).
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": "nicht_bestanden"})
        assert r.status_code == 200 and r.json["teilnehmer"]["ergebnis"] == "nicht_bestanden" and r.json["teilnehmer"]["eingefroren"] is True
        kurz = next(e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid)
        assert kurz["ergebnis_bestanden"] == 0 and kurz["ergebnis_nicht_bestanden"] == 2, kurz
        assert pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": "bestanden"}).status_code == 200

        # --- B. Einfrieren: 409 auf allem, was Prüfungsdaten ändert – für Leitung wie Prüfende ---------------
        def eingefroren(r):
            assert r.status_code == 409, (r.status_code, r.get_json())
            assert "eingefroren" in r.json["error"], r.json
        for client in (pr, zweit, adm):
            eingefroren(client.post(zelle_anna, json={"ergebnis": "mangelhaft", "kommentar": "nachträglich"}))
            eingefroren(client.post(f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{lei[1]['id']}/versuche", json={"ergebnis": "bestanden"}))
            eingefroren(client.put(f"/api/pruefungen/versuche/{a1['id']}", json={"ergebnis": "bestanden", "zeit_sekunden": 60}))
            eingefroren(client.post(f"/api/pruefungen/versuche/{a1['id']}/medien", headers=H, content_type="multipart/form-data",
                                    data={"files": [(jpeg(), "spaeter.jpg")]}))
            eingefroren(client.delete(f"/api/pruefungen/medien/{medien_a1[0]['id']}", headers=H))
            eingefroren(client.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vor[1]['id']}", json={"erfuellt": True}))
            eingefroren(client.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "nachträglich"}))
        eingefroren(pr.delete(f"/api/pruefungen/versuche/{a1['id']}", headers=H))
        eingefroren(pr.delete(f"/api/pruefungen/versuche/{b1['id']}", headers=H))
        # Nichts davon ist durchgekommen.
        r = pr.get(zelle_anna)
        assert [v["id"] for v in r.json["versuche"]] == [a1["id"]] and r.json["versuche"][0]["zeit_sekunden"] == 70, r.json
        assert {m["id"] for m in r.json["versuche"][0]["medien"]} == {m["id"] for m in medien_a1}
        assert all(os.path.isfile(p) for m in medien_a1 for p in medien_dateien(tmp, m))
        det = pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
        tn = {t["id"]: t for t in det["teilnehmer"]}
        assert tn[anna["id"]]["kommentar"] == "Sehr ruhig." and str(vor[1]["id"]) not in tn[anna["id"]]["voraussetzungen"]
        # Andere Teilnehmende sind nicht betroffen.
        c1 = zweit.post(zelle_clara, json={"ergebnis": "mangelhaft", "kommentar": "Zu kurz."})
        assert c1.status_code == 201, c1.get_json()
        assert zweit.put(f"/api/pruefungen/teilnehmer/{clara['id']}/kommentar", json={"kommentar": "Clara übt noch."}).status_code == 200
        # Stammdaten und Bild bleiben für die Leitung änderbar – für Prüfende weiter 403, nicht 409.
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}", json={"gliederung": "OG Nord", "email": "anna@example.org"})
        assert r.status_code == 200 and r.json["teilnehmer"]["gliederung"] == "OG Nord" and r.json["teilnehmer"]["eingefroren"] is True, r.get_json()
        leitung_noetig(zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}", json={"gliederung": "OG Süd"}))
        r = bild_hochladen(pr, anna["id"], "anna4.jpg")
        assert r.status_code == 200 and r.json["teilnehmer"]["eingefroren"] is True, r.get_json()
        assert not os.path.exists(pfad_anna) and os.path.isfile(bild_pfad(tmp, r.json["teilnehmer"]))
        pfad_anna = bild_pfad(tmp, r.json["teilnehmer"])
        assert pr.delete(f"/api/pruefungen/teilnehmer/{anna['id']}/bild", headers=H).status_code == 200
        assert not os.path.exists(pfad_anna)
        # Der Import setzt für eingefrorene TN keine Haken, übergeht sie mit Hinweis; andere bekommen ihre.
        r = _import(pr, _xlsx([["Vorname", "Nachname", "Ärztliche Tauglichkeit"], ["Anna", "Beispiel", "ja"], ["Clara", "Probe", "ja"]]), lehrgang_id=lid)
        assert r.status_code == 201, (r.status_code, r.get_json())
        assert r.json["angelegt"] == 0, r.get_json()
        tn = {t["id"]: t for t in r.json["lehrgang"]["teilnehmer"]}
        assert str(vor[1]["id"]) not in tn[anna["id"]]["voraussetzungen"], "eingefrorene Person darf keinen Haken bekommen"
        assert tn[clara["id"]]["voraussetzungen"][str(vor[1]["id"])]["erfuellt"] is True
        assert any("eingefroren" in w.lower() or "Anna" in w for w in r.json["warnungen"]), r.json["warnungen"]
        # Aufheben nur durch Leitung/Admin: alle vier Felder leer, danach geht wieder alles.
        leitung_noetig(zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": None}))
        r = pr.put(f"/api/pruefungen/teilnehmer/{anna['id']}/ergebnis", json={"ergebnis": None})
        assert r.status_code == 200, (r.status_code, r.get_json())
        anna_o = r.json["teilnehmer"]
        assert anna_o["ergebnis"] is None and anna_o["eingefroren"] is False, anna_o
        assert anna_o["ergebnis_von_name"] == "" and anna_o["ergebnis_am"] is None, anna_o
        r = zweit.post(f"/api/pruefungen/teilnehmer/{anna['id']}/leistungen/{lei[1]['id']}/versuche", json={"ergebnis": "bestanden", "zeit_sekunden": 12})
        assert r.status_code == 201, r.get_json()
        assert zweit.put(f"/api/pruefungen/versuche/{a1['id']}", json={"ergebnis": "bestanden", "zeit_sekunden": 60}).status_code == 200
        assert zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/kommentar", json={"kommentar": "Wieder frei."}).status_code == 200
        assert zweit.put(f"/api/pruefungen/teilnehmer/{anna['id']}/voraussetzungen/{vor[1]['id']}", json={"erfuellt": True}).status_code == 200
        r = zweit.post(f"/api/pruefungen/versuche/{a1['id']}/medien", headers=H, content_type="multipart/form-data",
                       data={"files": [(jpeg(), "spaeter.jpg")]})
        assert r.status_code == 201 and len(r.json["medien"]) == 1, r.get_json()
        assert zweit.delete(f"/api/pruefungen/medien/{r.json['medien'][0]['id']}", headers=H).status_code == 200
        assert pr.delete(f"/api/pruefungen/versuche/{a1['id']}", headers=H).status_code == 200
        kurz = next(e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid)
        assert kurz["ergebnis_bestanden"] == 0 and kurz["ergebnis_nicht_bestanden"] == 1, kurz     # Bert bleibt vermerkt
        assert adm.put(f"/api/pruefungen/teilnehmer/{bert['id']}/ergebnis", json={"ergebnis": None}).status_code == 200
        kurz = next(e for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"] if e["id"] == lid)
        assert kurz["ergebnis_bestanden"] == 0 and kurz["ergebnis_nicht_bestanden"] == 0, kurz

        # --- D. Beispieldaten: nur die Administration ----------------------------------------------------------
        assert pr.post("/api/pruefungen/beispieldaten", json={}).status_code == 403
        assert adm.post("/api/pruefungen/beispieldaten").status_code == 403                  # CSRF ohne JSON/Header
        vorher = {e["id"] for e in adm.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]}
        r = adm.post("/api/pruefungen/beispieldaten", json={})
        assert r.status_code == 201, (r.status_code, r.get_json())
        beispiele = r.json["lehrgaenge"]
        assert len(beispiele) == 2, beispiele
        for e in beispiele:
            hat_felder(e, *LEHRGANG_KURZ2)
            assert e["id"] not in vorher and e["darf_leiten"] is True and e["tn_anzahl"] > 0 and e["leistungen_anzahl"] > 0, e
        sr1 = next(e for e in beispiele if "SR1" in e["titel"])
        sr2 = next(e for e in beispiele if "SR2" in e["titel"])
        # SR2: Leistungen exakt nach der Checkliste, fünf Voraussetzungen, sechs Teilnehmende mit Bewertungen.
        det2 = adm.get(f"/api/pruefungen/lehrgaenge/{sr2['id']}").json["lehrgang"]
        assert tuple(l["bezeichnung"] for l in det2["leistungen"]) == SR2_LEISTUNGEN, [l["bezeichnung"] for l in det2["leistungen"]]
        assert len(det2["voraussetzungen"]) == 5, [v["bezeichnung"] for v in det2["voraussetzungen"]]
        assert any("Fitness" in v["bezeichnung"] for v in det2["voraussetzungen"]), det2["voraussetzungen"]
        assert det2["tn_anzahl"] == 6 and det2["zellen_abgenommen"] > 0, (det2["tn_anzahl"], det2["zellen_abgenommen"])
        assert len(leitung_von(det2, adm_id)) == 1, det2["ausbilder"]                      # der Aufrufer leitet
        assert any(a["user_id"] is None for a in det2["ausbilder"]), det2["ausbilder"]     # plus externe Referierende
        # SR1: mindestens 8 Teilnehmende, eine Nachprüfung, ein vermerktes Ergebnis, Haken und Kommentare.
        det1 = adm.get(f"/api/pruefungen/lehrgaenge/{sr1['id']}").json["lehrgang"]
        assert det1["tn_anzahl"] >= 8 and len(det1["teilnehmer"]) >= 8, det1["tn_anzahl"]
        assert len(det1["voraussetzungen"]) == 14 and len(det1["leistungen"]) == 9, (len(det1["voraussetzungen"]), len(det1["leistungen"]))
        assert any(l["zeitansatz_sekunden"] for l in det1["leistungen"]) and any(l["beschreibung_md"] for l in det1["leistungen"])
        versuche1 = [v for t in det1["teilnehmer"]
                     for v in adm.get(f"/api/pruefungen/teilnehmer/{t['id']}/versuche").json["versuche"]]
        assert any(v["ist_nachpruefung"] for v in versuche1), "Beispieldaten brauchen eine Nachprüfung"
        assert any(v["kommentar"] for v in versuche1) and all(v["geprueft_von_name"] for v in versuche1)
        mit_ergebnis = [t for t in det1["teilnehmer"] if t["ergebnis"]]
        assert mit_ergebnis and all(t["eingefroren"] and t["ergebnis_von_name"] and t["ergebnis_am"] for t in mit_ergebnis), det1["teilnehmer"]
        assert det1["ergebnis_bestanden"] + det1["ergebnis_nicht_bestanden"] == len(mit_ergebnis)
        assert any(t["voraussetzungen"] for t in det1["teilnehmer"]), "teils abgehakte Voraussetzungen"
        for t in det1["teilnehmer"] + det2["teilnehmer"]:
            hat_felder(t, *TN_FELDER2)
        assert all(a["name"] for a in det1["ausbilder"] + det2["ausbilder"])
        # Für Prüfende ohne Leitung sind die Beispiele sichtbar, aber nicht leitbar.
        assert pr.get(f"/api/pruefungen/lehrgaenge/{sr1['id']}").json["lehrgang"]["darf_leiten"] is False
        liste_pr = {e["id"]: e["darf_leiten"] for e in pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]}
        assert liste_pr[sr1["id"]] is False and liste_pr[sr2["id"]] is False
        leitung_noetig(pr.put(f"/api/pruefungen/lehrgaenge/{sr2['id']}", json={"ort": "Fremd"}))
        # Ein zweiter Aufruf legt weitere Kopien an, ohne die ersten zu berühren.
        r = adm.post("/api/pruefungen/beispieldaten", json={})
        assert r.status_code == 201 and len(r.json["lehrgaenge"]) == 2, r.get_json()
        neue = {e["id"] for e in r.json["lehrgaenge"]}
        assert not neue & {sr1["id"], sr2["id"]}
        assert {e["titel"] for e in r.json["lehrgaenge"]} != {sr1["titel"], sr2["titel"]}, "Kopien tragen einen Zusatz im Titel"
        assert adm.get(f"/api/pruefungen/lehrgaenge/{sr2['id']}").json["lehrgang"]["tn_anzahl"] == 6

        # --- Lehrgang löschen räumt auch die Profilbilder weg ------------------------------------------------------
        r = bild_hochladen(pr, bert["id"], "bert.jpg")
        assert r.status_code == 200, r.get_json()
        pfad_bert = bild_pfad(tmp, r.json["teilnehmer"])
        assert os.path.isfile(pfad_bert)
        leitung_noetig(zweit.delete(f"/api/pruefungen/lehrgaenge/{lid}", headers=H))
        assert pr.delete(f"/api/pruefungen/lehrgaenge/{lid}", headers=H).json["ok"] is True
        assert not os.path.exists(pfad_bert), pfad_bert
        assert pr.get(r.json["teilnehmer"]["bild"]).status_code == 404
        avatar_dir = os.path.join(tmp, "media", "pruefungen", "avatar")
        uebrig = os.listdir(avatar_dir) if os.path.isdir(avatar_dir) else []
        # Nur die Bilder der Beispieldaten (falls welche angelegt werden) dürfen noch liegen – jedes mit Datenbankzeile.
        bilder_db = {t["bild"].rsplit("/", 1)[1] for lgk in adm.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]
                     for t in adm.get(f"/api/pruefungen/lehrgaenge/{lgk['id']}").json["lehrgang"]["teilnehmer"] if t["bild"]}
        assert set(uebrig) == bilder_db, (uebrig, bilder_db)
        print("Rechte-/Ergebnis-Test bestanden.")


if __name__ == "__main__":
    test_pruefungen()
    test_import()
    test_import_modul()
    test_nachtraege()
    test_rechte_und_ergebnis()
