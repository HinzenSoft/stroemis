"""Nachbesserung aus der zweiten Durchsicht vor dem Merge (02.11.2026, planung/pruefung-merge2/auftrag_nachbesserung.md):
python tests/test_rechte_vor_merge2.py  oder  pytest …

Sicherheit: Verschieben nur, wer die Seite in den Papierkorb legen darf (Befund 1, Entscheidung des Nutzers „Verschieben:
nur wer löschen darf“, dazu Rechte-B4 PUT position), Kontosuche nur mit ganzer E-Mail-Adresse und Import-Vorschau ohne
Kontokennung (Befund 3), Anmeldeseite mit Sitzung springt zum Ziel, Medienlinks der Subdomain (Befund 4, Migration 2),
Kontaktadresse ohne Steuerzeichen. Rechte: can_create je Baumzeile/Seite im freigegebenen Abschnitt (B1), Kopieren nur
mit passenden Ausbildern (B3), Kandidaten „Bearbeiten erlauben“ (H1), keine zweite Leitungszeile (H2), Inhalte der
Leitstelle mit Lehrgängen/Katalogen (H5), Freigabe-Toast mit/ohne Mailserver (H6). Migration: Startprotokoll von Schritt
34 je Verknüpfung und Werkzeug scripts/vor_merge_riegenkarten.py. Dazu die Stellen der Oberfläche (B2 Autospeichern bei
403, bfcache, Speicherstand mit Kontokennung). Nur erfundene Namen, keine Mail geht hinaus (send_mail ersetzt)."""
import importlib.util
import io
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {"X-Requested-With": "XMLHttpRequest"}
MITGLIED, REDAKTEUR, VERWALTUNG = 1, 2, 3
W, P = "/api/wiki", "/api/pruefungen"


def make_app(tmp, **env):
    os.environ.update({
        "DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "https://stroemis.example.org",
        "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123", "VIDEOPFLEGE": "0",
    })
    os.environ.update(env)
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


def anmelden(app, mail, pw="passwort1"):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": mail, "password": pw})
    assert r.status_code == 200, (mail, r.get_json())
    return c


def konto(app, adm, mail, name, rechte):
    r = adm.post("/api/admin/users", json={"email": mail, "password": "passwort1", "name": name,
                                           "gliederung": "OG Beispielstadt", "rechte": rechte})
    assert r.status_code == 201, r.get_json()
    return anmelden(app, mail), r.json["user"]["id"]


def seite(c, titel, parent_id=None):
    r = c.post(f"{W}/pages", json={"title": titel, "content": f"# {titel}\n\nText", "parent_id": parent_id})
    assert r.status_code == 201, (titel, r.get_json())
    return r.json["page"]


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


# --- Sicherheit 1 / Rechte B4: Verschieben nur, wer löschen darf ------------------------------------------------------

def test_verschieben_nur_wer_loeschen_darf():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        mia, _ = konto(app, adm, "mia@example.org", "Mia Mitglied", {"wiki": MITGLIED})
        mats, mats_id = konto(app, adm, "mats@example.org", "Mats Mitglied", {"wiki": MITGLIED})
        rita, _ = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"wiki": REDAKTEUR})
        ralf, ralf_id = konto(app, adm, "ralf@example.org", "Ralf Redakteur", {"wiki": REDAKTEUR})
        artikel = seite(rita, "Ritas Artikel")
        kind = seite(rita, "Ritas Kind", artikel["id"])
        nachbar = seite(rita, "Ritas Nachbar")
        assert rita.put(f"{W}/pages/{artikel['id']}/editors", json={"user_ids": [ralf_id, mats_id]}).status_code == 200
        versteck = seite(ralf, "Ralfs Versteck")
        assert ralf.put(f"{W}/pages/{versteck['id']}/restrict", json={"read_restricted": True}).status_code == 200

        # p22: Ralf (Redakteur mit Freigabe) hängt Ritas Artikel nicht unter sein beschränktes Versteck – weder per PUT
        # noch per reorder, und auch die Stelle (position) nicht. Bearbeiten mit Freigabe bleibt erlaubt.
        r = ralf.put(f"{W}/pages/{artikel['id']}", json={"parent_id": versteck["id"]})
        assert r.status_code == 403 and "Papierkorb" in r.json["error"], r.get_json()
        r = ralf.put(f"{W}/reorder", json={"items": [{"id": artikel["id"], "parent_id": versteck["id"], "position": 0}]})
        assert r.status_code == 403 and "Papierkorb" in r.json["error"], r.get_json()
        r = ralf.put(f"{W}/pages/{artikel['id']}", json={"position": 7})
        assert r.status_code == 403, r.get_json()
        r = ralf.put(f"{W}/reorder", json={"items": [{"id": kind["id"], "parent_id": artikel["id"], "position": 3}]})
        assert r.status_code == 403, r.get_json()          # auch die Unterseite (Freigabe vererbt sich) nicht
        r = ralf.put(f"{W}/pages/{artikel['id']}", json={"title": "Ritas Artikel", "content": "# Ritas Artikel\n\nNeu",
                                                         "base_version": artikel["version"]})
        assert r.status_code == 200, r.get_json()
        assert mia.get(f"{W}/pages/{artikel['slug']}").status_code == 200
        assert mia.get(f"{W}/pages/{kind['slug']}").status_code == 200
        # B4: Mitglied mit Freigabe ändert die Stelle per PUT position nicht (wie /reorder); Inhalt schon.
        r = mats.put(f"{W}/pages/{artikel['id']}", json={"position": 5})
        assert r.status_code == 403 and "Redakteure" in r.json["error"], r.get_json()
        # Gleiche Werte mitgeschickt (wie ein Editor, der alles sendet) sind kein Verschieben.
        r = ralf.put(f"{W}/pages/{artikel['id']}", json={"parent_id": None, "position": 0})
        assert r.status_code == 200, r.get_json()
        # reorder: unveränderte Einträge bleiben unberührt (kein 403 für fremde Nachbarn, die bleiben, wo sie sind).
        eigen = seite(ralf, "Ralfs Seite")
        r = ralf.put(f"{W}/reorder", json={"items": [{"id": nachbar["id"], "parent_id": None, "position": 0},
                                                     {"id": eigen["id"], "parent_id": None, "position": 9}]})
        assert r.status_code == 200 and r.json["moved"] == 1, r.get_json()
        r = ralf.put(f"{W}/reorder", json={"items": [{"id": nachbar["id"], "parent_id": None, "position": 4}]})
        assert r.status_code == 403, r.get_json()

        # Die Erstellerin und die Verwaltung dürfen weiter verschieben.
        r = rita.put(f"{W}/pages/{artikel['id']}", json={"parent_id": nachbar["id"]})
        assert r.status_code == 200 and r.json["page"]["parent_id"] == nachbar["id"], r.get_json()
        r = rita.put(f"{W}/reorder", json={"items": [{"id": artikel["id"], "parent_id": None, "position": 2}]})
        assert r.status_code == 200, r.get_json()
        assert rita.put(f"{W}/pages/{artikel['id']}", json={"position": 1}).status_code == 200
        r = adm.put(f"{W}/pages/{artikel['id']}", json={"parent_id": nachbar["id"]})
        assert r.status_code == 200, r.get_json()
        r = adm.put(f"{W}/reorder", json={"items": [{"id": artikel["id"], "parent_id": None, "position": 0}]})
        assert r.status_code == 200, r.get_json()
        # Im Baum: Ziehen (can_delete) nur an eigenen Seiten.
        baum = {p["id"]: p for p in ralf.get(f"{W}/tree").json["pages"]}
        assert not baum[artikel["id"]]["can_delete"] and baum[artikel["id"]]["can_edit"]
        assert baum[eigen["id"]]["can_delete"]
        js = lies("app/static/js/wiki.js")
        assert '<div class="row"${p.can_delete ? \' draggable="true"\' : ""}>' in js
        assert "function ablagePlan(moved, target, mode)" in js and "items.every((it) => state.byId.get(it.id).can_delete)" in js
        print("Verschieben bestanden.")


# --- Rechte B1, B5, H1: Anlegen im freigegebenen Abschnitt, Teilen-Dialog ---------------------------------------------

def test_anlegen_im_freigegebenen_abschnitt():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        rita, rita_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"wiki": REDAKTEUR})
        _, mia_id = konto(app, adm, "mia@example.org", "Mia Mitglied", {"wiki": MITGLIED})
        _, olga_id = konto(app, adm, "olga@example.org", "Olga Ohne", {"karte": MITGLIED})
        frei = seite(adm, "Freigegeben")
        frei_kind = seite(adm, "Freigegeben Kind", frei["id"])
        nur_seite = seite(adm, "Nur die Seite")
        normal = seite(adm, "Normal")
        assert adm.put(f"{W}/pages/{frei['id']}/share", json={"is_public": True, "public_children": True}).status_code == 200
        assert adm.put(f"{W}/pages/{nur_seite['id']}/share", json={"is_public": True, "public_children": False}).status_code == 200
        baum = {p["id"]: p for p in rita.get(f"{W}/tree").json["pages"]}
        assert not baum[frei["id"]]["can_create"] and not baum[frei_kind["id"]]["can_create"]
        assert baum[nur_seite["id"]]["can_create"] and baum[normal["id"]]["can_create"]
        assert all(p["can_create"] for p in adm.get(f"{W}/tree").json["pages"])
        # Seite: can_create (Unterseite) und can_duplicate (Kopie daneben) wie der Server antwortet.
        for p, unter, dup in ((frei, False, True), (frei_kind, False, False), (normal, True, True)):
            j = rita.get(f"{W}/pages/{p['slug']}").json["page"]
            assert (j["can_create"], j["can_duplicate"]) == (unter, dup), (p["title"], j["can_create"], j["can_duplicate"])
            assert (rita.post(f"{W}/pages", json={"title": "x", "parent_id": p["id"]}).status_code == 201) == unter
            assert (rita.post(f"{W}/pages/{p['id']}/duplicate", json={}).status_code == 201) == dup, p["title"]
        j = adm.get(f"{W}/pages/{frei_kind['slug']}").json["page"]
        assert j["can_create"] and j["can_duplicate"]
        js = lies("app/static/js/wiki.js")
        assert "${p.can_create ? `<button class=\"row-add\"" in js
        assert "${page.can_create ? '<button type=\"button\" data-a=\"child\">Unterseite anlegen</button>' : \"\"}" in js
        assert "${darfDuplizieren(page) ? '<button type=\"button\" data-a=\"dup\">Duplizieren</button>' : \"\"}" in js
        assert "${p.can_duplicate ? '<button type=\"button\" data-a=\"dup\">Duplizieren</button>' : \"\"}" in js
        # B5: der Satz im Teilen-Dialog.
        assert "Normalerweise liest jeder mit Stufe in der Strömipedia jede Seite." in js
        assert "Normalerweise darf jeder Angemeldete jede Seite lesen." not in js
        # H1: „Bearbeiten erlauben“ bietet nur Konten mit Strömipedia-Stufe an; eine bestehende Freigabe bleibt sichtbar.
        ids = {u["id"] for u in rita.get(f"{W}/users").json["users"]}
        assert {rita_id, mia_id} <= ids and olga_id not in ids, ids
        eigen = seite(rita, "Ritas Seite")
        assert rita.put(f"{W}/pages/{eigen['id']}/editors", json={"user_ids": [mia_id]}).status_code == 200
        assert adm.put(f"/api/admin/users/{mia_id}", json={"rechte": {"wiki": 0}}).status_code == 200
        assert mia_id not in {u["id"] for u in rita.get(f"{W}/users").json["users"]}
        assert [e["id"] for e in rita.get(f"{W}/pages/{eigen['slug']}").json["page"]["editors"]] == [mia_id]
        assert "ohne Stufe in der Strömipedia, die Freigabe wirkt nicht" in js
        print("Anlegen im freigegebenen Abschnitt bestanden.")


# --- Sicherheit 3: Kontosuche und Import-Vorschau ----------------------------------------------------------------------

def test_kontosuche():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        leitung, _ = konto(app, adm, "leo@example.org", "Leo Leitung", {"pruefungen": MITGLIED})
        red, _ = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"pruefungen": REDAKTEUR})
        konto(app, adm, "anna.verborgen@example.org", "Anna Beispiel", {"pruefungen": MITGLIED})
        lg = red.post(f"{P}/lehrgaenge", json={"titel": "SR1"}).json["lehrgang"]
        uid_leo = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "leo@example.org"][0]["id"]
        r = red.put(f"{P}/lehrgaenge/{lg['id']}", json={"ausbilder": [
            {"user_id": lg["ausbilder"][0]["user_id"], "ist_leitung": True}, {"user_id": uid_leo, "ist_leitung": True}]})
        assert r.status_code == 200, r.get_json()
        for c in (leitung, red):
            # p12 Teil 6: Teile der Adresse treffen nicht mehr; der Name weiter als Teilstring.
            for teil in ("@e", "anna.verb", "@example.org", "verborgen@example.or", "a@"):
                assert c.get(f"{P}/nutzer", query_string={"q": teil}).json["nutzer"] == [], teil
            for ganz in ("anna.verborgen@example.org", " ANNA.Verborgen@Example.ORG "):
                assert [n["name"] for n in c.get(f"{P}/nutzer", query_string={"q": ganz}).json["nutzer"]] == ["Anna Beispiel"]
            assert [n["name"] for n in c.get(f"{P}/nutzer", query_string={"q": "beisp"}).json["nutzer"]] == ["Anna Beispiel"]
        # p12 Teil 7: Die Import-Vorschau nennt den Namen des Kontos (zum Gegenlesen), keine Kennung, keine Adresse.
        wb = openpyxl.Workbook()
        ws = wb.active
        for z in (["Name", "Vorname", "E-Mail", "Rolle"], ["Muster", "Max", "max@example.org", "Teilnehmer"],
                  ["Y", "X", "anna.verborgen@example.org", "Ausbilder"], ["R", "Q", "", "Ausbilder"]):
            ws.append(z)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        r = red.post(f"{P}/import/vorschau", data={"file": (buf, "liste.xlsx")}, headers=H,
                     content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        konten = [a["konto"] for a in r.json["ausbilder"]]
        assert {"name": "Anna Beispiel", "eingetragen": False} in konten, konten
        assert all(k is None or set(k) == {"name", "eingetragen"} for k in konten), konten
        assert all("email" not in a for a in r.json["ausbilder"]), r.json["ausbilder"]   # die Adresse bleibt in der Datei
        assert "eine E-Mail-Adresse zählt nur vollständig" in lies("app/static/js/pruefungen.js")
        print("Kontosuche bestanden.")


# --- Sicherheit 4 / Migration 2: Anmeldeseite mit Sitzung, Medienlinks der Subdomain ----------------------------------

def test_anmeldung_springt_zum_ziel():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        host = app.config["PUBLIC_HOST"]
        basis = app.config["BASE_URL"].rstrip("/")
        adm = anmelden(app, "admin@example.org", "geheim123")
        frei = seite(adm, "Freigabe Abschnitt")
        assert adm.put(f"{W}/pages/{frei['id']}/share", json={"is_public": True, "public_children": True}).status_code == 200
        bild = adm.post(f"{W}/files", data={"file": (_jpeg(), "bild.jpg")}, headers=H, content_type="multipart/form-data")
        assert bild.status_code in (200, 201), bild.get_json()
        url = bild.json["url"]
        anon = app.test_client()
        # Seite der Subdomain ohne Sitzung → Anmeldung unter BASE_URL mit Rücksprung; mit Sitzung direkt zur Seite.
        r = anon.get(f"/{frei['slug']}", headers={"Host": host})
        assert r.status_code == 302 and r.headers["Location"] == f"{basis}/login?next=/stroemipedia/{frei['slug']}", r.headers
        r = adm.get(f"/login?next=/stroemipedia/{frei['slug']}")
        assert r.status_code == 302 and r.headers["Location"] == f"/stroemipedia/{frei['slug']}", r.headers
        # Bild der Subdomain: ohne Sitzung zur Anmeldung unter BASE_URL mit Rücksprung auf die Datei (nicht /oeffentlich).
        r = anon.get(url, headers={"Host": host})
        assert r.status_code == 302 and r.headers["Location"] == f"{basis}/login?next={url}", r.headers
        r = adm.get(f"/login?next={url}")
        assert r.status_code == 302 and r.headers["Location"] == url, r.headers
        assert adm.get(url).status_code == 200
        # Auf der Hauptadresse bleibt der Rücksprung relativ.
        r = anon.get(url)
        assert r.status_code == 302 and r.headers["Location"] == f"/login?next={url}", r.headers
        # Offene Weiterleitung bleibt zu; ohne next zur Startseite; registrieren mit Sitzung wie bisher zur Startseite.
        for boese in ("//evil.example", "https://evil.example", "/\\evil.example", "\x01/x"):
            r = adm.get("/login", query_string={"next": boese})
            assert r.status_code == 302 and r.headers["Location"] == "/", (boese, r.headers)
        assert adm.get("/login").headers["Location"] == "/"
        assert adm.get("/register?next=/leitstelle").headers["Location"] == "/"
        assert anon.get(f"/login?next=/stroemipedia/{frei['slug']}").status_code == 200
        print("Anmeldung mit Ziel bestanden.")


def _jpeg():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, "JPEG")
    buf.seek(0)
    return buf


# --- Hinweis Kontaktadresse: Steuerzeichen ------------------------------------------------------------------------------

def test_kontaktadresse_ohne_steuerzeichen():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        for wert in ("a@b.de\x00", "a\x00@b.de", "a@b.de\x7f", "a@b.d\x01e", "a@b.de\x9f", "a@b.de\x1b[0m"):
            for schl in ("KONTAKT_EMAIL", "FEHLER_EMAIL"):
                r = adm.put("/api/admin/einstellungen", json={"werte": {schl: wert}})
                assert r.status_code == 400, (schl, repr(wert), r.status_code)
        for wert in ("verwalter@strömis.de", "a.b-c_d+e@sub.example.org", ""):
            assert adm.put("/api/admin/einstellungen", json={"werte": {"KONTAKT_EMAIL": wert}}).status_code == 200
        print("Kontaktadresse bestanden.")


# --- Rechte B3, H2: Kopieren und eigene Leitungszeile -----------------------------------------------------------------

def test_kopieren_und_leitung():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        rita, rita_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"pruefungen": REDAKTEUR})
        _, mia_id = konto(app, adm, "mia@example.org", "Mia Mitglied", {"pruefungen": MITGLIED})
        _, arno_id = konto(app, adm, "arno@example.org", "Arno Ohnestufe", {"pruefungen": MITGLIED})
        _, doris_id = konto(app, adm, "doris@example.org", "Doris Deaktiviert", {"pruefungen": MITGLIED})
        r = rita.post(f"{P}/lehrgaenge", json={"titel": "SR1", "ausbilder": [
            {"user_id": rita_id, "funktion": "Co", "ist_leitung": True}, {"user_id": mia_id, "funktion": "Wasser"},
            {"user_id": arno_id, "funktion": "Boot"}, {"user_id": doris_id, "funktion": "Seil"}]})
        assert r.status_code == 201, r.get_json()
        lid = r.json["lehrgang"]["id"]
        # Stufe bzw. Konto weg: bleiben im Original eingetragen (ohne Zugriff) …
        assert adm.put(f"/api/admin/users/{arno_id}", json={"rechte": {"pruefungen": 0}}).status_code == 200
        assert adm.put(f"/api/admin/users/{doris_id}", json={"active": False}).status_code == 200
        # H2: Rita nimmt sich im Dialog das Kennzeichen „Leitung“ – sie bleibt Leitung, in IHRER Zeile, ohne zweite.
        alt = rita.get(f"{P}/lehrgaenge/{lid}").json["lehrgang"]["ausbilder"]
        neu = [{"user_id": a["user_id"], "funktion": a["funktion"], "ist_leitung": False if a["user_id"] == rita_id
                else a["ist_leitung"]} for a in alt]
        r = rita.put(f"{P}/lehrgaenge/{lid}", json={"ausbilder": neu})
        assert r.status_code == 200, r.get_json()
        zeilen = [(a["user_id"], a["funktion"], a["ist_leitung"]) for a in r.json["lehrgang"]["ausbilder"]]
        assert zeilen == [(rita_id, "Co", True), (mia_id, "Wasser", False), (arno_id, "Boot", False),
                          (doris_id, "Seil", False)], zeilen
        # B3: Die Kopie übernimmt nur passende Konten; die übrigen nennt die Antwort.
        r = rita.post(f"{P}/lehrgaenge/{lid}/kopieren", json={"titel": "SR1 Kopie"})
        assert r.status_code == 201, r.get_json()
        assert [(a["user_id"], a["funktion"], a["ist_leitung"]) for a in r.json["lehrgang"]["ausbilder"]] == [
            (rita_id, "Co", True), (mia_id, "Wasser", False)], r.json["lehrgang"]["ausbilder"]
        assert r.json["ausbilder_nicht_uebernommen"] == [{"name": "Arno Ohnestufe", "funktion": "Boot"},
                                                         {"name": "Doris Deaktiviert", "funktion": "Seil"}], r.get_json()
        # Mit allen passenden Konten: nichts nicht übernommen.
        assert adm.put(f"/api/admin/users/{arno_id}", json={"rechte": {"pruefungen": MITGLIED}}).status_code == 200
        r = rita.post(f"{P}/lehrgaenge/{lid}/kopieren", json={})
        assert r.status_code == 201 and len(r.json["lehrgang"]["ausbilder"]) == 3, r.get_json()
        assert r.json["ausbilder_nicht_uebernommen"] == [{"name": "Doris Deaktiviert", "funktion": "Seil"}]
        js = lies("app/static/js/pruefungen.js")
        assert "const nicht = r.ausbilder_nicht_uebernommen || [];\n            meldungMerken(`Kopie" in js
        print("Kopieren und Leitung bestanden.")


# --- Rechte H3, H5, H6: Leitstelle ------------------------------------------------------------------------------------

def test_leitstelle():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        rita, rita_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"pruefungen": REDAKTEUR})
        assert rita.post(f"{P}/lehrgaenge", json={"titel": "SR1"}).status_code == 201
        assert rita.post(f"{P}/lehrgaenge", json={"titel": "SR2"}).status_code == 201
        assert rita.post(f"{P}/kataloge", json={"titel": "Katalog Rita"}).status_code == 201
        u = [x for x in adm.get("/api/admin/users").json["users"] if x["id"] == rita_id][0]
        assert (u["lehrgang_count"], u["katalog_count"], u["page_count"]) == (2, 1, 0), u
        js = lies("app/static/js/admin.js")
        assert 'u.lehrgang_count ? mehrzahl(u.lehrgang_count, "Lehrgang", "Lehrgänge") : ""' in js
        assert "Alben, Bilder, Seiten der Strömipedia und Kataloge der Riegenkarten bleiben erhalten" in js
        # H6: Freigabe ohne und mit Mailserver (Versand scheitert) unterscheidbar. Die Anfragen entstehen vorher ohne
        # Mailserver; send_mail ist überall ersetzt – es geht nie etwas hinaus.
        from app import api_admin, auth, mailer
        post = []
        ersatz = {m: m.send_mail for m in (api_admin, auth, mailer)}
        try:
            for m in ersatz:
                m.send_mail = lambda an, *a, **k: post.append(an) or True
            uids = []
            for i in range(3):
                mail = f"anfrage{i}@example.org"
                r = app.test_client().post("/api/auth/register", json={"email": mail, "password": "passwort1",
                                                                       "name": "Anna Anfrage", "gliederung": "OG"})
                assert r.status_code == 201, r.get_json()
                uids.append([x for x in adm.get("/api/admin/users").json["users"] if x["email"] == mail][0]["id"])
            for uid, host, sendet, erwartet in ((uids[0], "", False, (False, False)),
                                                (uids[1], "smtp.example.invalid", False, (False, True)),
                                                (uids[2], "smtp.example.invalid", True, (True, True))):
                api_admin.send_mail = lambda an, *a, ergebnis=sendet, **k: post.append(an) or ergebnis
                app.config["SMTP_HOST"] = host
                r = adm.post(f"/api/admin/users/{uid}/approve", json={})
                assert r.status_code == 200 and (r.json["mailed"], r.json["mailserver"]) == erwartet, r.get_json()
        finally:
            for m, f in ersatz.items():
                m.send_mail = f
            app.config["SMTP_HOST"] = ""
        assert "r.mailserver ? `${u.name} freigegeben – die E-Mail ließ sich nicht verschicken" in js
        print("Leitstelle bestanden.")


# --- Oberfläche: Autospeichern bei 403, bfcache, Speicherstand ---------------------------------------------------------

def test_oberflaeche():
    js = lies("app/static/js/wiki.js")
    assert "if (e.status === 403) verweigert = true;" in js
    assert 'stand("Nicht gespeichert – keine Berechtigung mehr", true);' in js
    assert "if (!lebt || isNew || konflikt || verweigert) return;" in js          # kein Dauerversuch
    assert "Kopiere den Text vorher, wenn du ihn noch brauchst." in js            # Rückfrage beim Verlassen
    common = lies("app/static/js/common.js")
    assert 'if (!e.persisted || !ich) return;' in common and 'fetch("/api/me"' in common and "location.reload();" in common
    mat = lies("app/material/static/material.js")
    assert ("const ABLAGE = `stroemis-mat-pruefung-${(window.STROEMIS && STROEMIS.user && STROEMIS.user.id) || 0}-"
            "${DATEN.id}`;") in mat
    print("Oberfläche bestanden.")


# --- Migration: Startprotokoll von Schritt 34 und Werkzeug vor dem Merge ----------------------------------------------

class _Protokoll(logging.Handler):
    def __init__(self):
        super().__init__()
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append(record.getMessage())


def _werkzeug():
    spec = importlib.util.spec_from_file_location("vor_merge_riegenkarten",
                                                  os.path.join(WURZEL, "scripts", "vor_merge_riegenkarten.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_schritt34_und_werkzeug():
    """Vorversion (Schema 33) mit Freitext-Ausbildern: Das Werkzeug sagt vorher, was Schritt 34 tut – dieselben Fälle wie
    das Startprotokoll danach (je Verknüpfung eine Zeile, Summe getrennt nach verknüpft, zusammengelegt, entfernt), die
    neue Zahl der Ausbilder-Zeilen stimmt, und es ändert nichts an der Datenbank. Dazu die Liste der Bewertenden ohne
    Eintrag und die alte Skala (ohne mat_meta: Verwaltung = 2)."""
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)                                   # legt die Datenbank im heutigen Schema an
        from app.material import models
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        konten = {}
        for mail, name, stufe in (("e@example.org", "Eva Eindeutig", MITGLIED), ("d1@example.org", "Dana Doppelt", 1),
                                  ("d2@example.org", "Dana Doppelt", 1), ("o@example.org", "Otto Ohnestufe", 0),
                                  ("b@example.org", "Bea Bewertend", MITGLIED)):
            konten[mail] = conn.execute("INSERT INTO users (email, password_hash, name, recht_pruefungen, active, "
                                        "created_at) VALUES (?,?,?,?,1,'2026-01-01')", (mail, "x", name, stufe)).lastrowid
        a = conn.execute("INSERT INTO pruef_lehrgaenge (titel, created_at, updated_at) VALUES ('SR Alt', '2026-01-01', "
                         "'2026-01-01')").lastrowid
        for uid, name, funktion, leit in ((konten["e@example.org"], "Eva Eindeutig", "", 0),
                                          (None, "Eindeutig, Eva", "Leitung", 1), (None, "Dana Doppelt", "Seil", 0),
                                          (None, "Otto Ohnestufe", "", 0), (None, "Bea Bewertend", "Boot", 0)):
            conn.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, ist_leitung) "
                         "VALUES (?,?,?,?,?)", (a, uid, name, funktion, leit))
        tn = conn.execute("INSERT INTO pruef_teilnehmer (lehrgang_id, name, created_at) VALUES (?, 'Muster', "
                          "'2026-01-01')", (a,)).lastrowid
        lei = conn.execute("INSERT INTO pruef_leistungen (lehrgang_id, bezeichnung) VALUES (?, 'Wurfsack')", (a,)).lastrowid
        for nr, uid in enumerate((konten["b@example.org"], konten["o@example.org"]), start=1):
            conn.execute("INSERT INTO pruef_versuche (teilnehmer_id, leistung_id, versuch_nr, ergebnis, geprueft_von, "
                         "geprueft_von_name, geprueft_am) VALUES (?,?,?,'bestanden',?,'x','2026-01-01')",
                         (tn, lei, nr, uid))
        conn.execute("UPDATE mat_meta SET wert = '33' WHERE schluessel = 'schema_version'")
        conn.commit()
        conn.close()
        with open(pfad, "rb") as fh:
            roh_vorher = fh.read()

        werkzeug = _werkzeug()
        aus = io.StringIO()
        with redirect_stdout(aus):
            assert werkzeug.main(pfad) == 0
        text = aus.getvalue()
        with open(pfad, "rb") as fh:
            assert fh.read() == roh_vorher                       # nur lesend
        assert f"zusammenlegen Lehrgang {a} „SR Alt“: Eindeutig, Eva (Leitung) → Konto {konten['e@example.org']} " \
               "„Eva Eindeutig“ (ohne Gliederung)" in text, text
        assert f"verknüpfen    Lehrgang {a} „SR Alt“: Bea Bewertend (Boot) → Konto {konten['b@example.org']}" in text, text
        assert f"ENTFERNEN     Lehrgang {a} „SR Alt“: Dana Doppelt (Seil) – mehrdeutig – Konten " \
               f"{konten['d1@example.org']}, {konten['d2@example.org']}" in text, text
        assert f"ENTFERNEN     Lehrgang {a} „SR Alt“: Otto Ohnestufe – nur Konten ohne Stufe" in text, text
        assert "Summe: 1 verknüpfen, 1 zusammenlegen, 2 entfernen; pruef_ausbilder 5 → 2 Zeilen" in text, text
        assert f"Konto {konten['b@example.org']} „Bea Bewertend“, 1 Bewertung – wird über Schritt 34 verknüpft" in text
        assert f"Konto {konten['o@example.org']} „Otto Ohnestufe“, 1 Bewertung – sieht ihn danach NICHT mehr" in text

        # Alte Skala (main ohne mat_meta): Verwaltung = 2.
        kopie = os.path.join(tmp, "kopie.db")
        shutil.copy(pfad, kopie)
        k = sqlite3.connect(kopie)
        k.execute("DROP TABLE mat_meta")
        k.commit()
        assert werkzeug.verwaltungsstufe(k) == 2
        k.close()

        # Der echte Schritt 34 tut genau das – das Protokoll nennt jede Verknüpfung und die Summe getrennt.
        protokoll = _Protokoll()
        logging.getLogger("app.material.models").addHandler(protokoll)
        try:
            make_app(tmp)
        finally:
            logging.getLogger("app.material.models").removeHandler(protokoll)
        assert protokoll.zeilen == [
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR Alt“ – Freitext „Eindeutig, Eva“ (Leitung) mit der vorhandenen "
            f"Zeile von Konto {konten['e@example.org']} zusammengelegt",
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR Alt“ – Freitext „Bea Bewertend“ (Boot) mit Konto "
            f"{konten['b@example.org']} verknüpft",
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR Alt“ – Ausbilder ohne passendes Konto entfernt: "
            "Dana Doppelt (Seil), Otto Ohnestufe",
            "Schritt 34 (Riegenkarten): 1 Freitext-Ausbilder mit Konten verknüpft, 1 mit einer vorhandenen Zeile "
            "zusammengelegt, 2 entfernt."], protokoll.zeilen
        k = sqlite3.connect(pfad)
        assert k.execute("SELECT count(*) FROM pruef_ausbilder").fetchone()[0] == 2
        k.close()
        assert models.SCHEMA_VERSION >= 34
        # Nach der Migration: keine Freitext-Ausbilder mehr, das Werkzeug sagt es (und rechnet mit Verwaltung = 3).
        aus = io.StringIO()
        with redirect_stdout(aus):
            werkzeug.main(pfad)
        assert "schon migriert" in aus.getvalue() and "Keine Freitext-Ausbilder" in aus.getvalue(), aus.getvalue()
        print("Schritt 34 und Werkzeug bestanden.")


if __name__ == "__main__":
    test_verschieben_nur_wer_loeschen_darf()
    test_anlegen_im_freigegebenen_abschnitt()
    test_kontosuche()
    test_anmeldung_springt_zum_ziel()
    test_kontaktadresse_ohne_steuerzeichen()
    test_kopieren_und_leitung()
    test_leitstelle()
    test_oberflaeche()
    test_schritt34_und_werkzeug()
