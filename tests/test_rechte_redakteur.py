"""Stufe „Redakteur“ in Strömipedia, Ankerplätzen und Riegenkarten (Entwurf planung/rechte-redakteur/entwurf.md,
Entscheidungen des Nutzers vom 28.10. und 01.11.2026): python tests/test_rechte_redakteur.py  oder  pytest …

Je Endpunkt die Rollen Mitglied / Redakteur / Verwaltung, eigen und fremd; in den Riegenkarten dazu die Sichtbarkeit
(ein Mitglied sieht nur Lehrgänge, in denen es mit seinem Konto als Ausbilder steht – sonst 404, auch für Medien), die
Mitglied-Leitung und die eigenen Kataloge. Dazu Leitstelle (Stufen je Modul), Schema-Schritt 33 (frisch, Vorversion mit
Altbestand, zweiter Lauf, Abbruch) und die Beschriftung im Journal der Materialablage. Nur erfundene Namen, keine Mail
geht hinaus (send_mail ersetzt)."""
import io
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402
from PIL import Image  # noqa: E402

H = {"X-Requested-With": "XMLHttpRequest"}
MITGLIED, REDAKTEUR, VERWALTUNG = 1, 2, 3


def make_app(tmp):
    os.environ.update({
        "DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "http://localhost",
        "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123", "VIDEOPFLEGE": "0",
    })
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (200, 30, 30)).save(buf, "JPEG")
    buf.seek(0)
    return buf


def xlsx(zeilen):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r, zeile in enumerate(zeilen, start=1):
        for c, wert in enumerate(zeile, start=1):
            ws.cell(row=r, column=c, value=wert)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


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


def stufe_setzen(adm, uid, **rechte):
    r = adm.put(f"/api/admin/users/{uid}", json={"rechte": rechte})
    assert r.status_code == 200, r.get_json()
    return r.json["user"]["rechte"]


def datei(client, url, name="bild.jpg", feld="file", **form):
    data = {feld: (jpeg(), name)}
    data.update(form)
    return client.post(url, data=data, headers=H, content_type="multipart/form-data")


# --- Leitstelle: Stufen je Modul, Gleichzug, Kontoanfrage-Mail --------------------------------------------------------

def test_leitstelle():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        assert adm.get("/api/me").json["user"]["rechte"] == {m: VERWALTUNG for m in
                                                             ("karte", "wiki", "pruefungen", "material", "verwaltung")}
        _, uid = konto(app, adm, "ella@example.org", "Ella Beispiel", {})
        # Redakteur gibt es nur in den drei Modulen mit eigenen Inhalten.
        assert stufe_setzen(adm, uid, wiki=REDAKTEUR, karte=REDAKTEUR, pruefungen=REDAKTEUR) == {
            "karte": 2, "wiki": 2, "pruefungen": 2, "material": 1, "verwaltung": 0}
        for modul, wert in (("material", 2), ("verwaltung", 1), ("verwaltung", 2), ("wiki", 4), ("karte", -1),
                            ("pruefungen", "2"), ("wiki", 2.5), ("material", True)):
            r = adm.put(f"/api/admin/users/{uid}", json={"rechte": {modul: wert}})
            assert r.status_code == 400, (modul, wert, r.get_json())
        r = adm.put(f"/api/admin/users/{uid}", json={"rechte": {"material": 2}})
        assert "Materialablage" in r.json["error"] and "(3)" in r.json["error"], r.get_json()
        r = adm.put(f"/api/admin/users/{uid}", json={"rechte": {"verwaltung": 2}})
        assert "Leitstelle" in r.json["error"], r.get_json()
        # Verwaltung in der Leitstelle zieht alles auf Verwaltung (3) – auch gespeichert.
        assert stufe_setzen(adm, uid, verwaltung=VERWALTUNG) == {m: 3 for m in
                                                                ("karte", "wiki", "pruefungen", "material", "verwaltung")}
        with app.app_context():
            from app import db
            assert db.query("SELECT recht_karte, recht_wiki, recht_pruefungen, recht_material, recht_verwaltung "
                            "FROM users WHERE id = ?", (uid,), one=True) == {
                "recht_karte": 3, "recht_wiki": 3, "recht_pruefungen": 3, "recht_material": 3, "recht_verwaltung": 3}
        assert stufe_setzen(adm, uid, verwaltung=0, wiki=REDAKTEUR)["wiki"] == REDAKTEUR
        # Vorgabe neuer Konten und Kontoanfragen bleibt (Entscheidung 5A): Materialablage Mitglied, sonst nichts.
        r = adm.post("/api/admin/users", json={"email": "neu@example.org", "password": "passwort1", "name": "Neu"})
        assert r.json["user"]["rechte"] == {"karte": 0, "wiki": 0, "pruefungen": 0, "material": 1, "verwaltung": 0}
        # Die Kontoanfrage-Mail findet die Plattform-Verwaltung auch mit der Zahl 3 (auth.notify_admins_about_request).
        from app import auth
        post = []
        alt = auth.send_mail
        auth.send_mail = lambda an, betreff, text, **kw: post.append((an, betreff)) or True
        try:
            app.config["ADMIN_NOTIFY_EMAIL"] = ""
            r = app.test_client().post("/api/auth/register", json={"email": "anfrage@example.org", "password": "passwort1",
                                                                   "name": "Anna Anfrage", "gliederung": "OG Test"})
            assert r.status_code == 201, r.get_json()
        finally:
            auth.send_mail = alt
        assert any(an == "admin@example.org" and "Kontoanfrage" in betreff for an, betreff in post), post
        anfrage = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "anfrage@example.org"][0]
        assert anfrage["rechte"] == {"karte": 0, "wiki": 0, "pruefungen": 0, "material": 1, "verwaltung": 0}
        # Vorlagen und Seiten kennen die Stufen als Zahl (Kontextprozessor „stufe“, common.js S.STUFE).
        html = adm.get("/leitstelle").get_data(as_text=True)
        assert "„Redakteur“" in html and "Redakteure vergibst du hier von Hand" in html
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "js",
                               "common.js"), encoding="utf-8").read()
        assert "window.S.STUFE = Object.freeze({ kein: 0, mitglied: 1, redakteur: 2, verwaltung: 3 });" in js
        print("Leitstelle-Test bestanden.")


# --- Strömipedia ------------------------------------------------------------------------------------------------------

def test_wiki():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        m, m_id = konto(app, adm, "mia@example.org", "Mia Mitglied", {"wiki": MITGLIED})
        r1, r1_id = konto(app, adm, "rolf@example.org", "Rolf Redakteur", {"wiki": REDAKTEUR})
        r2, r2_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"wiki": REDAKTEUR})
        v, _ = konto(app, adm, "vera@example.org", "Vera Verwaltung", {"wiki": VERWALTUNG})
        lese, _ = konto(app, adm, "leo@example.org", "Leo Lesemodus", {"wiki": 0})

        # Altbestand: Mia war früher „Mitglied mit Anlegen“ – heute Redakteur gesetzt, eine Seite angelegt, zurück auf
        # Mitglied (bestehende Mitglieder bleiben Mitglied und verlieren Anlegen und Bearbeiten).
        stufe_setzen(adm, m_id, wiki=REDAKTEUR)
        alt = m.post("/api/wiki/pages", json={"title": "Mias alte Seite", "content": "# Alt\n\nText"}).json["page"]
        stufe_setzen(adm, m_id, wiki=MITGLIED)

        # Redakteur: eigene Seiten anlegen, bearbeiten, Unterseite unter fremder Seite (Entscheidung 3A).
        r = r1.post("/api/wiki/pages", json={"title": "Rolfs Seite", "content": "# Rolfs Seite\n\nInhalt"})
        assert r.status_code == 201 and r.json["page"]["can_edit"] and r.json["page"]["can_create"], r.get_json()
        rolf = r.json["page"]
        rita = r2.post("/api/wiki/pages", json={"title": "Ritas Seite", "content": "# Ritas Seite\n\nText"}).json["page"]
        kind = r2.post("/api/wiki/pages", json={"title": "Ritas Unterseite", "content": "# U\n\nText",
                                                "parent_id": rita["id"]}).json["page"]
        r = r1.post("/api/wiki/pages", json={"title": "Rolf unter Rita", "content": "# x", "parent_id": rita["id"]})
        assert r.status_code == 201, r.get_json()
        assert r1.put(f"/api/wiki/pages/{rolf['id']}", json={"content": "# Rolfs Seite\n\nNeu"}).status_code == 200
        assert r1.put(f"/api/wiki/pages/{rita['id']}", json={"content": "# fremd"}).status_code == 403
        assert r1.put(f"/api/wiki/pages/{rita['id']}/icon", json={"icon": "x"}).status_code == 403
        assert r1.delete(f"/api/wiki/pages/{rita['id']}", headers=H).status_code == 403
        assert r1.put(f"/api/wiki/pages/{rolf['id']}/icon", json={"icon": "🌊"}).status_code == 200
        assert r1.post(f"/api/wiki/pages/{rita['id']}/duplicate", json={}).status_code == 201
        assert datei(r1, "/api/wiki/files").status_code == 200

        # Mitglied: lesen, kommentieren, beobachten – nichts anlegen, nichts bearbeiten (auch die alte eigene Seite nicht).
        seite = m.get(f"/api/wiki/pages/{rolf['slug']}")
        assert seite.status_code == 200
        p = seite.json["page"]
        assert (p["can_edit"], p["can_delete"], p["can_share"], p["can_publish"], p["can_create"]) == (
            False, False, False, False, False), p
        r = m.post("/api/wiki/pages", json={"title": "Mia neu", "content": "# x"})
        assert r.status_code == 403 and r.json["error"] == "Seiten anlegen dürfen Redakteure und die Wiki-Verwaltung."
        assert m.post(f"/api/wiki/pages/{rolf['id']}/duplicate", json={}).status_code == 403
        r = datei(m, "/api/wiki/files")
        assert r.status_code == 403 and "Dateien hochladen" in r.json["error"], r.get_json()
        assert m.post("/api/wiki/files/drehung", json={"file": "x.jpg", "grad": 90}).status_code == 403
        assert m.post("/api/wiki/files/zuschnitt", json={"file": "x.jpg", "x": 0, "y": 0, "w": 1, "h": 1}).status_code == 403
        r = m.put("/api/wiki/reorder", json={"items": [{"id": alt["id"], "parent_id": None, "position": 3}]})
        assert r.status_code == 403, r.get_json()
        for methode, url, body in (("put", f"/api/wiki/pages/{alt['id']}", {"content": "# Alt\n\nNeu"}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/icon", {"icon": "x"}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/options", {"is_template": True}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/restrict", {"read_restricted": True}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/editors", {"user_ids": [r1_id]}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/share", {"is_public": True}),
                                   ("put", f"/api/wiki/pages/{alt['id']}/creator", {"user_id": m_id}),
                                   ("delete", f"/api/wiki/pages/{alt['id']}", None)):
            r = getattr(m, methode)(url, json=body, headers=H) if body is not None else getattr(m, methode)(url, headers=H)
            assert r.status_code == 403, (url, r.status_code, r.get_json())
        alt_json = m.get(f"/api/wiki/pages/{alt['slug']}").json["page"]
        assert alt_json["can_edit"] is False and alt_json["can_delete"] is False
        assert m.put(f"/api/wiki/pages/{rolf['id']}/watch", json={"watch": True}).status_code == 200
        assert m.put(f"/api/wiki/pages/{rolf['id']}/favorite", json={"favorite": True}).status_code == 200
        assert m.get(f"/api/wiki/pages/{rolf['id']}/export").status_code == 200
        # Baum: Rechte je Zeile, die Oberfläche zeigt danach nur, was geht.
        baum = {b["id"]: b for b in m.get("/api/wiki/tree").json["pages"]}
        assert not any(b["can_edit"] or b["can_delete"] for b in baum.values()), baum
        baum_r = {b["id"]: b for b in r1.get("/api/wiki/tree").json["pages"]}
        assert baum_r[rolf["id"]]["can_edit"] and baum_r[rolf["id"]]["can_delete"]
        assert not baum_r[rita["id"]]["can_edit"] and not baum_r[rita["id"]]["can_delete"]
        assert all(b["can_edit"] and b["can_delete"] for b in v.get("/api/wiki/tree").json["pages"])
        # Papierkorb: nichts wiederherstellbar für das Mitglied, die eigene für den Redakteur.
        assert r1.delete(f"/api/wiki/pages/{rolf['id']}", headers=H).status_code == 200
        papier = {e["id"]: e for e in m.get("/api/wiki/trash").json["pages"]}
        assert papier[rolf["id"]]["can_restore"] is False
        assert {e["id"]: e for e in r1.get("/api/wiki/trash").json["pages"]}[rolf["id"]]["can_restore"] is True
        assert m.post(f"/api/wiki/pages/{rolf['id']}/restore", json={}, headers=H).status_code == 403
        assert r1.post(f"/api/wiki/pages/{rolf['id']}/restore", json={}, headers=H).status_code == 200

        # Kommentare (Entscheidung 4A): Verfasser die eigenen, der Seitenersteller fremde erst ab Redakteur.
        r = m.post(f"/api/wiki/pages/{rolf['id']}/comments", json={"body": "Frage von Mia"})
        assert r.status_code == 201 and r.json["comment"]["can_delete"] and r.json["comment"]["can_edit"], r.get_json()
        mk = r.json["comment"]
        rk = r1.post(f"/api/wiki/pages/{rolf['id']}/comments", json={"body": "Antwort von Rolf"}).json["comment"]
        assert m.put(f"/api/wiki/comments/{mk['id']}", json={"body": "Frage von Mia, genauer"}).status_code == 200
        assert m.delete(f"/api/wiki/comments/{rk['id']}", headers=H).status_code == 403
        assert m.put(f"/api/wiki/comments/{rk['id']}", json={"resolved": True}).status_code == 403
        assert r1.put(f"/api/wiki/comments/{mk['id']}", json={"resolved": True}).status_code == 200   # Ersteller ab Redakteur
        assert r1.put(f"/api/wiki/comments/{mk['id']}", json={"body": "fremd ändern"}).status_code == 403
        assert r2.delete(f"/api/wiki/comments/{mk['id']}", headers=H).status_code == 403             # fremde Seite
        # An Mias alter Seite erledigt Mia als Mitglied fremde Kommentare nicht mehr.
        fremd_k = r1.post(f"/api/wiki/pages/{alt['id']}/comments", json={"body": "Hinweis"}).json["comment"]
        liste = {c["id"]: c for c in m.get(f"/api/wiki/pages/{alt['id']}/comments").json["comments"]}
        assert liste[fremd_k["id"]]["can_delete"] is False
        assert m.delete(f"/api/wiki/comments/{fremd_k['id']}", headers=H).status_code == 403
        assert v.delete(f"/api/wiki/comments/{fremd_k['id']}", headers=H).status_code == 200
        assert m.delete(f"/api/wiki/comments/{mk['id']}", headers=H).status_code == 200

        # Bearbeitungsfreigabe an ein Mitglied: samt Unterseiten wie ein Redakteur (Wunsch des Nutzers 02.11.2026, vorher
        # Entscheidung 2B: genau diese Seite), kein Verschieben, kein Löschen.
        assert r2.put(f"/api/wiki/pages/{rita['id']}/editors", json={"user_ids": [m_id, r1_id]}).status_code == 200
        assert m.get(f"/api/wiki/pages/{rita['slug']}").json["page"]["can_edit"] is True
        assert m.get(f"/api/wiki/pages/{kind['slug']}").json["page"]["can_edit"] is True
        assert m.put(f"/api/wiki/pages/{rita['id']}", json={"content": "# Ritas Seite\n\nVon Mia"}).status_code == 200
        assert m.put(f"/api/wiki/pages/{kind['id']}", json={"content": "# U\n\nVon Mia"}).status_code == 200
        r = m.put(f"/api/wiki/pages/{kind['id']}", json={"parent_id": None})
        assert r.status_code == 403 and "verschieben" in r.json["error"], r.get_json()
        assert m.delete(f"/api/wiki/pages/{kind['id']}", headers=H).status_code == 403
        r = m.put(f"/api/wiki/pages/{rita['id']}", json={"parent_id": rolf["id"]})
        assert r.status_code == 403 and "verschieben" in r.json["error"], r.get_json()
        assert m.put(f"/api/wiki/pages/{rita['id']}", json={"parent_id": None, "title": "Ritas Seite"}).status_code == 200
        assert m.delete(f"/api/wiki/pages/{rita['id']}", headers=H).status_code == 403
        assert m.put(f"/api/wiki/pages/{rita['id']}/editors", json={"user_ids": []}).status_code == 403
        assert datei(m, "/api/wiki/files").status_code == 200          # mit Freigabe darf sie Bilder einfügen
        baum = {b["id"]: b for b in m.get("/api/wiki/tree").json["pages"]}
        assert baum[rita["id"]]["can_edit"] and baum[kind["id"]]["can_edit"] and not baum[rita["id"]]["can_delete"]
        assert not baum[kind["id"]]["can_delete"] and not baum[kind["id"]]["can_create"]
        # Ein Redakteur mit derselben Freigabe bearbeitet ebenso die Unterseiten (Vererbung wie bisher).
        assert r1.put(f"/api/wiki/pages/{kind['id']}", json={"content": "# U\n\nVon Rolf"}).status_code == 200
        assert {b["id"]: b for b in r1.get("/api/wiki/tree").json["pages"]}[kind["id"]]["can_edit"] is True
        assert r1.delete(f"/api/wiki/pages/{kind['id']}", headers=H).status_code == 403

        # Lesebeschränkung (Entscheidung 1A): gilt für Mitglied und Redakteur gleich; die Freigabe öffnet sie.
        geheim = r2.post("/api/wiki/pages", json={"title": "Entwurf", "content": "# Entwurf"}).json["page"]
        assert r2.put(f"/api/wiki/pages/{geheim['id']}/restrict", json={"read_restricted": True}).status_code == 200
        assert m.get(f"/api/wiki/pages/{geheim['slug']}").status_code == 403
        assert r1.get(f"/api/wiki/pages/{geheim['slug']}").status_code == 403
        assert v.get(f"/api/wiki/pages/{geheim['slug']}").status_code == 200
        assert r2.put(f"/api/wiki/pages/{geheim['id']}/editors", json={"user_ids": [m_id]}).status_code == 200
        assert m.get(f"/api/wiki/pages/{geheim['slug']}").status_code == 200

        # Nur die Verwaltung stellt öffentlich, importiert, ändert den Ersteller, stellt HTML-Bausteine ein.
        for c in (m, r1, r2):
            assert c.put(f"/api/wiki/pages/{rolf['id']}/share", json={"is_public": True}, headers=H).status_code == 403
            assert c.put(f"/api/wiki/pages/{rolf['id']}/creator", json={"user_id": r2_id}).status_code == 403
            assert c.post("/api/wiki/import", data={"file": (io.BytesIO(b"PK"), "a.zip")}, headers=H,
                          content_type="multipart/form-data").status_code == 403
            html = c.post("/api/wiki/files", data={"file": (io.BytesIO(b"<!doctype html><p>x"), "b.html")}, headers=H,
                          content_type="multipart/form-data")
            assert html.status_code == 403, html.get_json()
        assert v.put(f"/api/wiki/pages/{rolf['id']}/share", json={"is_public": True}, headers=H).status_code == 200
        assert v.put(f"/api/wiki/pages/{rita['id']}", json={"content": "# Ritas Seite\n\nVerwaltung"}).status_code == 200
        # Ohne Wiki-Stufe bleibt der Lesemodus: die internen Schnittstellen sind zu.
        assert lese.get("/api/wiki/tree").status_code == 403
        assert lese.post(f"/api/wiki/pages/{rolf['id']}/comments", json={"body": "x"}).status_code == 403

        # Oberfläche: Mitglied ohne Knopfzeile über dem Baum, Redakteur mit „Neue Seite“ und Papierkorb, Verwaltung mit ⋯.
        seite_m, seite_r, seite_v = (c.get("/stroemipedia").get_data(as_text=True) for c in (m, r1, v))
        assert 'id="btn-new-page"' not in seite_m and 'baum-knoepfe' not in seite_m
        assert 'id="btn-new-page"' in seite_r and 'id="btn-papierkorb"' in seite_r and 'id="btn-baum-mehr"' not in seite_r
        assert 'id="btn-new-page"' in seite_v and 'id="btn-baum-mehr"' in seite_v
        print("Strömipedia-Test bestanden.")


# --- Ankerplätze -----------------------------------------------------------------------------------------------------

def test_karte():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        m, m_id = konto(app, adm, "mats@example.org", "Mats Mitglied", {"karte": MITGLIED})
        r1, _ = konto(app, adm, "rene@example.org", "René Redakteur", {"karte": REDAKTEUR})
        r2, _ = konto(app, adm, "ruth@example.org", "Ruth Redakteurin", {"karte": REDAKTEUR})
        v, _ = konto(app, adm, "viola@example.org", "Viola Verwaltung", {"karte": VERWALTUNG})

        # Altbestand: ein Album, das Mats als früheres Mitglied angelegt hat.
        stufe_setzen(adm, m_id, karte=REDAKTEUR)
        alt = m.post("/api/albums", json={"title": "Mats' altes Album"}).json["album"]
        alt_bild = datei(m, f"/api/albums/{alt['id']}/photos", feld="files").json["photos"][0]
        stufe_setzen(adm, m_id, karte=MITGLIED)

        # Redakteur: eigene Alben, Bilder nur in eigene (Entscheidung: fremde nur die Verwaltung).
        r = r1.post("/api/albums", json={"title": "Wehr Nord", "category": "wasser"})
        assert r.status_code == 201, r.get_json()
        eigen = r.json["album"]
        fremd = r2.post("/api/albums", json={"title": "Brücke Süd"}).json["album"]
        assert datei(r1, f"/api/albums/{eigen['id']}/photos", feld="files").status_code == 201
        assert datei(r1, f"/api/albums/{fremd['id']}/photos", feld="files").status_code == 403
        assert r1.put(f"/api/albums/{fremd['id']}", json={"title": "x"}).status_code == 403
        assert r1.post(f"/api/albums/{eigen['id']}/zusammenlegen", json={"ziel": fremd["id"]}).status_code == 403
        assert r1.put(f"/api/albums/{eigen['id']}", json={"description": "Zugang über den Damm"}).status_code == 200
        r = r1.post("/api/albums/einwurf", data={"files": (jpeg(), "e.jpg"), "title": "Einwurf"}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        assert r1.get(f"/api/albums/{fremd['id']}").json["album"]["can_edit"] is False

        # Mitglied: sieht Karte, Alben und Bilder – legt nichts an, bearbeitet nichts (auch das alte eigene Album nicht).
        assert m.get("/api/map").status_code == 200 and m.get("/ankerplaetze").status_code == 200
        assert {a["id"] for a in m.get("/api/albums").json["albums"]} >= {eigen["id"], fremd["id"], alt["id"]}
        assert m.get(f"/api/albums/{alt['id']}").json["album"]["can_edit"] is False
        assert m.get(f"/api/photos/{alt_bild['id']}").json["photo"]["can_edit"] is False
        r = m.post("/api/albums", json={"title": "Mats neu"})
        assert r.status_code == 403 and r.json["error"] == "Alben anlegen dürfen Redakteure und die Verwaltung der Ankerplätze."
        r = m.post("/api/albums/einwurf", data={"files": (jpeg(), "e.jpg"), "title": "x"}, headers=H,
                   content_type="multipart/form-data")
        assert r.status_code == 403, r.get_json()
        assert m.put(f"/api/albums/{alt['id']}", json={"title": "x"}).status_code == 403
        assert m.put(f"/api/albums/{alt['id']}/cover", json={"photo_id": alt_bild["id"]}).status_code == 403
        assert datei(m, f"/api/albums/{alt['id']}/photos", feld="files").status_code == 403
        assert m.put(f"/api/photos/{alt_bild['id']}", json={"title": "x"}).status_code == 403
        assert m.delete(f"/api/photos/{alt_bild['id']}", headers=H).status_code == 403
        assert m.delete(f"/api/albums/{alt['id']}", headers=H).status_code == 403
        assert m.get(alt_bild["thumb"]).status_code == 200

        # Verwaltung: alle Alben, auch Bilder in fremde.
        assert datei(v, f"/api/albums/{fremd['id']}/photos", feld="files").status_code == 201
        assert v.put(f"/api/albums/{alt['id']}", json={"title": "Umbenannt"}).status_code == 200

        # Oberfläche: „Album anlegen“ ab Redakteur.
        assert 'id="btn-new-album"' not in m.get("/ankerplaetze").get_data(as_text=True)
        assert 'id="btn-new-album"' in r1.get("/ankerplaetze").get_data(as_text=True)
        print("Ankerplätze-Test bestanden.")


# --- Riegenkarten ----------------------------------------------------------------------------------------------------

def test_riegenkarten():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        leit, leit_id = konto(app, adm, "lena@example.org", "Lena Leitung", {"pruefungen": MITGLIED})
        pruef, pruef_id = konto(app, adm, "paul@example.org", "Paul Prüfer", {"pruefungen": MITGLIED})
        aussen, _ = konto(app, adm, "olga@example.org", "Olga Außen", {"pruefungen": MITGLIED})
        r1, r1_id = konto(app, adm, "robert@example.org", "Robert Redakteur", {"pruefungen": REDAKTEUR})
        r2, r2_id = konto(app, adm, "ronja@example.org", "Ronja Redakteurin", {"pruefungen": REDAKTEUR})
        v, _ = konto(app, adm, "valentin@example.org", "Valentin Verwaltung", {"pruefungen": VERWALTUNG})
        api = "/api/pruefungen"

        # Redakteur legt an und wird Leitung; er trägt ein Mitglied als Leitung ein (Entscheidung a) und eines als Prüfer.
        r = r1.post(f"{api}/lehrgaenge", json={"titel": "SR1 Frühjahr", "ausbilder": [
            {"user_id": leit_id, "funktion": "Lehrgangsleitung", "ist_leitung": True},
            {"user_id": pruef_id, "funktion": "Prüfer"}]})
        assert r.status_code == 201, r.get_json()
        lg = r.json["lehrgang"]
        lid = lg["id"]
        assert any(a["user_id"] == r1_id and a["ist_leitung"] for a in lg["ausbilder"]), lg["ausbilder"]
        assert lg["darf_leiten"] is True and lg["darf_kopieren"] is True
        tn = r1.post(f"{api}/lehrgaenge/{lid}/teilnehmer", json={"name": "Muster", "vorname": "Max"}).json["teilnehmer"]
        pl = r1.post(f"{api}/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Wurfsackwurf"}).json["leistung"]
        vo = r1.post(f"{api}/lehrgaenge/{lid}/voraussetzungen", json={"bezeichnung": "DRSA"}).json["voraussetzung"]
        kr = r1.post(f"{api}/leistungen/{pl['id']}/kriterien", json={"bezeichnung": "Ziel getroffen"}).json["kriterium"]
        bild = r1.post(f"{api}/teilnehmer/{tn['id']}/bild", data={"file": (jpeg(), "p.jpg")}, headers=H,
                       content_type="multipart/form-data").json["teilnehmer"]["bild"]
        zelle = f"{api}/teilnehmer/{tn['id']}/leistungen/{pl['id']}/versuche"

        # Mitglied als Prüfer (eingetragen, ohne Leitung): sieht und bewertet, pflegt nicht, kopiert nicht.
        liste = pruef.get(f"{api}/lehrgaenge").json["lehrgaenge"]
        assert [x["id"] for x in liste] == [lid] and liste[0]["darf_leiten"] is False and liste[0]["darf_kopieren"] is False
        assert pruef.get(f"/riegenkarten/{lid}").status_code == 200 and pruef.get(f"/riegenkarten/{lid}/druck").status_code == 200
        r = pruef.post(zelle, json={"ergebnis": "mangelhaft", "kommentar": "Zu kurz."})
        assert r.status_code == 201, r.get_json()
        versuch = r.json["versuch"]
        r = pruef.post(f"{api}/versuche/{versuch['id']}/medien", data={"files": [(jpeg(), "f.jpg")]}, headers=H,
                       content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        medium = r.json["medien"][0]
        assert pruef.put(f"{api}/teilnehmer/{tn['id']}/voraussetzungen/{vo['id']}", json={"erfuellt": True}).status_code == 200
        assert pruef.put(f"{api}/teilnehmer/{tn['id']}/kommentar", json={"kommentar": "ruhig"}).status_code == 200
        assert pruef.get(f"{api}/lehrgaenge/{lid}/maengel").status_code == 200
        for url in (medium["thumb"], medium["web"], medium["orig"], bild):
            assert pruef.get(url).status_code == 200, url
        r = pruef.put(f"{api}/lehrgaenge/{lid}", json={"ort": "x"})
        assert r.status_code == 403 and "Lehrgangsleitung" in r.json["error"], r.get_json()
        assert pruef.post(f"{api}/lehrgaenge/{lid}/kopieren", json={}).status_code == 403
        # Mitglied legt nichts an und sieht keine Kataloge (Entscheidung c) – Schnittstelle und Seite.
        r = pruef.post(f"{api}/lehrgaenge", json={"titel": "Eigener"})
        assert r.status_code == 403 and r.json["error"] == "Lehrgänge anlegen dürfen Redakteure und die Verwaltung der Riegenkarten."
        r = pruef.post(f"{api}/import", data={"file": (xlsx([["Vorname", "Nachname"], ["Ida", "Neu"]]), "l.xlsx")},
                       headers=H, content_type="multipart/form-data")
        assert r.status_code == 403, r.get_json()
        assert pruef.post(f"{api}/import/vorschau", data={"file": (xlsx([["Vorname"], ["Ida"]]), "l.xlsx")}, headers=H,
                          content_type="multipart/form-data").status_code == 403
        assert pruef.get(f"{api}/kataloge").status_code == 403
        assert pruef.get("/riegenkarten/kataloge").status_code == 403
        assert pruef.get("/riegenkarten/kataloge/1").status_code == 403
        assert pruef.get("/riegenkarten").status_code == 200

        # Mitglied als Leitung: pflegt genau diesen Lehrgang, importiert hinein, kopiert nicht (Kopie = Anlegen).
        lg_l = leit.get(f"{api}/lehrgaenge/{lid}").json["lehrgang"]
        assert lg_l["darf_leiten"] is True and lg_l["darf_kopieren"] is False
        assert leit.put(f"{api}/lehrgaenge/{lid}", json={"ort": "Beispielfluss"}).status_code == 200
        assert leit.post(f"{api}/lehrgaenge/{lid}/teilnehmer", json={"name": "Probe", "vorname": "Pia"}).status_code == 201
        imp = {"file": (xlsx([["Vorname", "Nachname"], ["Ida", "Import"]]), "l.xlsx"), "lehrgang_id": str(lid)}
        assert leit.post(f"{api}/import/vorschau", data=dict(imp), headers=H,
                         content_type="multipart/form-data").status_code == 200
        imp["file"] = (xlsx([["Vorname", "Nachname"], ["Ida", "Import"]]), "l.xlsx")
        r = leit.post(f"{api}/import", data=imp, headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        r = leit.post(f"{api}/lehrgaenge/{lid}/kopieren", json={})
        assert r.status_code == 403 and r.json["error"].startswith("Lehrgänge anlegen"), r.get_json()
        assert leit.delete(f"{api}/versuche/{versuch['id']}", headers=H).status_code == 200
        versuch = pruef.post(zelle, json={"ergebnis": "mangelhaft", "kommentar": "Wieder zu kurz."}).json["versuch"]
        medium = pruef.post(f"{api}/versuche/{versuch['id']}/medien", data={"files": [(jpeg(), "g.jpg")]}, headers=H,
                            content_type="multipart/form-data").json["medien"][0]

        # Mitglied ohne Eintrag: sieht den Lehrgang nicht – überall 404, auch Seiten und Medien.
        assert aussen.get(f"{api}/lehrgaenge").json["lehrgaenge"] == []
        nicht = [("get", f"{api}/lehrgaenge/{lid}"), ("put", f"{api}/lehrgaenge/{lid}"),
                 ("delete", f"{api}/lehrgaenge/{lid}"), ("post", f"{api}/lehrgaenge/{lid}/kopieren"),
                 ("post", f"{api}/lehrgaenge/{lid}/teilnehmer"), ("put", f"{api}/teilnehmer/{tn['id']}"),
                 ("get", f"{api}/teilnehmer/{tn['id']}/versuche"), ("put", f"{api}/teilnehmer/{tn['id']}/kommentar"),
                 ("put", f"{api}/teilnehmer/{tn['id']}/ergebnis"), ("delete", f"{api}/teilnehmer/{tn['id']}/bild"),
                 ("get", zelle), ("post", zelle), ("put", f"{api}/versuche/{versuch['id']}"),
                 ("delete", f"{api}/versuche/{versuch['id']}"), ("post", f"{api}/versuche/{versuch['id']}/medien"),
                 ("delete", f"{api}/medien/{medium['id']}"),
                 ("put", f"{api}/teilnehmer/{tn['id']}/voraussetzungen/{vo['id']}"),
                 ("get", f"{api}/teilnehmer/{tn['id']}/voraussetzungen/{vo['id']}/verlauf"),
                 ("put", f"{api}/voraussetzungen/{vo['id']}"), ("post", f"{api}/lehrgaenge/{lid}/voraussetzungen"),
                 ("put", f"{api}/leistungen/{pl['id']}"), ("post", f"{api}/leistungen/{pl['id']}/kriterien"),
                 ("put", f"{api}/kriterien/{kr['id']}"), ("delete", f"{api}/kriterien/{kr['id']}"),
                 ("get", f"{api}/lehrgaenge/{lid}/maengel"), ("put", f"{api}/lehrgaenge/{lid}/leistungen/reihenfolge")]
        for methode, url in nicht:
            kw = {"headers": H}
            if methode in ("put", "post"):
                kw["json"] = {"ergebnis": "bestanden", "titel": "x", "name": "x", "bezeichnung": "x", "ids": []}
            r = getattr(aussen, methode)(url, **kw)
            assert r.status_code == 404, (methode, url, r.status_code, r.get_json())
        r = aussen.post(f"{api}/import/vorschau", data={"file": (xlsx([["Vorname"], ["Ida"]]), "l.xlsx"),
                                                         "lehrgang_id": str(lid)}, headers=H,
                        content_type="multipart/form-data")
        assert r.status_code == 404, r.get_json()
        for url in (f"/riegenkarten/{lid}", f"/riegenkarten/{lid}/druck"):
            assert aussen.get(url).status_code == 404, url
        for url in (medium["thumb"], medium["web"], medium["orig"], bild, "/media/pruefung/thumb/../x.jpg",
                    "/media/pruefung/orig/gibtesnicht.jpg"):
            assert aussen.get(url).status_code == 404, url
        assert app.test_client().get(medium["thumb"]).status_code in (302, 401)
        # Ein zweiter Redakteur sieht den fremden Lehrgang ebenso wenig; die Verwaltung sieht alles.
        assert r2.get(f"{api}/lehrgaenge/{lid}").status_code == 404 and r2.get(medium["thumb"]).status_code == 404
        assert v.get(f"{api}/lehrgaenge/{lid}").json["lehrgang"]["darf_leiten"] is True
        assert v.get(medium["thumb"]).status_code == 200 and v.get("/media/pruefung/orig/gibtesnicht.jpg").status_code == 404
        # Freitext-Ausbilder gibt es nicht mehr (01.11.2026); ein Lehrgang der Verwaltung ohne Ausbilder-Eintrag sieht
        # nur die Verwaltung.
        r = v.post(f"{api}/lehrgaenge", json={"titel": "Nur Freitext", "ausbilder": [
            {"user_id": None, "name": "Lena Leitung", "funktion": "Lehrgangsleitung", "ist_leitung": True}]})
        assert r.status_code == 400 and "nur mit Konto" in r.json["error"], r.get_json()
        frei = v.post(f"{api}/lehrgaenge", json={"titel": "Ohne Eintrag"}).json["lehrgang"]
        assert frei["ausbilder"] == []
        assert leit.get(f"{api}/lehrgaenge/{frei['id']}").status_code == 404
        assert frei["id"] not in {x["id"] for x in r1.get(f"{api}/lehrgaenge").json["lehrgaenge"]}
        assert frei["id"] in {x["id"] for x in v.get(f"{api}/lehrgaenge").json["lehrgaenge"]}

        # Redakteur: kopieren (wird Leitung der Kopie), Import als neuer Lehrgang.
        r = r1.post(f"{api}/lehrgaenge/{lid}/kopieren", json={"titel": "SR1 Herbst"})
        assert r.status_code == 201 and r.json["lehrgang"]["darf_leiten"] is True, r.get_json()
        r = r1.post(f"{api}/import", data={"file": (xlsx([["Vorname", "Nachname"], ["Ida", "Neu"]]), "neu.xlsx")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201 and r.json["lehrgang"]["darf_leiten"] is True, r.get_json()

        # Kataloge: Redakteur eigene anlegen und pflegen, fremde lesen und als Vorlage nutzen; Verwaltung alle.
        r = r1.post(f"{api}/kataloge", json={"titel": "SR1-Katalog"})
        assert r.status_code == 201 and r.json["katalog"]["darf_bearbeiten"] is True, r.get_json()
        k1 = r.json["katalog"]
        kl = r1.post(f"{api}/kataloge/{k1['id']}/leistungen", json={"bezeichnung": "Knoten", "kriterien": ["Achter"]})
        assert kl.status_code == 201, kl.get_json()
        kl = kl.json["leistung"]
        assert r1.put(f"{api}/kataloge/{k1['id']}", json={"beschreibung": "Vorlage"}).status_code == 200
        assert r2.get(f"{api}/kataloge/{k1['id']}").json["katalog"]["darf_bearbeiten"] is False
        assert {k["id"]: k for k in r2.get(f"{api}/kataloge").json["kataloge"]}[k1["id"]]["darf_bearbeiten"] is False
        for methode, url in (("put", f"{api}/kataloge/{k1['id']}"), ("delete", f"{api}/kataloge/{k1['id']}"),
                             ("post", f"{api}/kataloge/{k1['id']}/leistungen"),
                             ("put", f"{api}/katalog-leistungen/{kl['id']}"),
                             ("delete", f"{api}/katalog-leistungen/{kl['id']}"),
                             ("post", f"{api}/katalog-leistungen/{kl['id']}/kriterien"),
                             ("put", f"{api}/katalog-kriterien/{kl['kriterien'][0]['id']}"),
                             ("put", f"{api}/kataloge/{k1['id']}/leistungen/reihenfolge")):
            kw = {"headers": H}
            if methode in ("put", "post"):
                kw["json"] = {"titel": "x", "bezeichnung": "x", "ids": []}
            r = getattr(r2, methode)(url, **kw)
            assert r.status_code == 403 and "Ersteller" in r.json["error"], (methode, url, r.status_code, r.get_json())
            r = getattr(pruef, methode)(url, **kw)
            assert r.status_code == 403 and "Kataloge sehen" in r.json["error"], (methode, url, r.get_json())
        r = r2.post(f"{api}/lehrgaenge", json={"titel": "Aus fremdem Katalog", "katalog_id": k1["id"]})
        assert r.status_code == 201 and [x["bezeichnung"] for x in r.json["lehrgang"]["leistungen"]] == ["Knoten"]
        assert v.put(f"{api}/kataloge/{k1['id']}", json={"titel": "SR1-Katalog (geprüft)"}).status_code == 200
        assert r1.get("/riegenkarten/kataloge").status_code == 200
        # Ein Katalog ohne Ersteller (Konto gelöscht, Altbestand) gehört der Verwaltung.
        with app.app_context():
            from app import db
            ohne = db.execute("INSERT INTO pruef_kataloge (titel, created_by, created_by_name, created_at, updated_at) "
                              "VALUES ('Altkatalog', NULL, 'früher', '2026-01-01', '2026-01-01')")
        assert r1.get(f"{api}/kataloge/{ohne}").json["katalog"]["darf_bearbeiten"] is False
        assert r1.put(f"{api}/kataloge/{ohne}", json={"titel": "x"}).status_code == 403
        assert v.put(f"{api}/kataloge/{ohne}", json={"titel": "Altkatalog"}).status_code == 200
        # Löschen eines Kontos: seine Kataloge gehen an die löschende Verwaltung (wie Seiten und Alben).
        k2 = r2.post(f"{api}/kataloge", json={"titel": "Ronjas Katalog"}).json["katalog"]
        adm_id = adm.get("/api/me").json["user"]["id"]
        assert adm.delete(f"/api/admin/users/{r2_id}", headers=H).status_code == 200
        with app.app_context():
            assert db.query("SELECT created_by FROM pruef_kataloge WHERE id = ?", (k2["id"],), one=True)["created_by"] == adm_id

        # Oberfläche: Seiten zeigen dieselbe Ansicht; die Knöpfe zeichnet pruefungen.js nach Stufe und Flags.
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "js",
                               "pruefungen.js"), encoding="utf-8").read()
        assert "const darfAnlegen = () => S.stufe(\"pruefungen\") >= S.STUFE.redakteur;" in js
        assert "lg.darf_kopieren ?" in js and "k.darf_bearbeiten ?" in js and "istAdmin" not in js
        print("Riegenkarten-Test bestanden.")


# --- Schema-Schritt 33 ----------------------------------------------------------------------------------------------

def test_migration():
    """Frisch: Startkonto 3 überall. Vorversion (Schema 32, Werte 0/1/2): 2 → 3, 0 und 1 bleiben. Zweiter Start: nichts
    ändert sich (auch ein neuer Redakteur bleibt 2). Abbruch im Schritt: Schema 32 und alle Werte stehen wie vorher."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        from app import db
        from app.material import models
        with app.app_context():
            assert db.query("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'", one=True)["wert"] == "34"
            assert db.query("SELECT recht_wiki, recht_verwaltung FROM users", one=True) == {"recht_wiki": 3,
                                                                                             "recht_verwaltung": 3}
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        conn.execute("UPDATE mat_meta SET wert = '32' WHERE schluessel = 'schema_version'")
        conn.execute("UPDATE users SET recht_karte = 2, recht_wiki = 2, recht_pruefungen = 2, recht_material = 2, "
                     "recht_verwaltung = 2")
        werte = {"m@example.org": (1, 1, 1, 1, 0), "v@example.org": (2, 2, 2, 2, 0), "n@example.org": (0, 0, 0, 0, 0),
                 "g@example.org": (2, 1, 0, 2, 0)}
        for mail, (k, w, p, ma, ve) in werte.items():
            conn.execute("INSERT INTO users (email, password_hash, name, recht_karte, recht_wiki, recht_pruefungen, "
                         "recht_material, recht_verwaltung, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (mail, "x", mail, k, w, p, ma, ve, "2026-01-01T00:00:00"))
        conn.commit()
        spalten = "email, recht_karte, recht_wiki, recht_pruefungen, recht_material, recht_verwaltung"

        def stand():
            c = sqlite3.connect(pfad)
            try:
                return ({r[0]: r[1:] for r in c.execute(f"SELECT {spalten} FROM users")},
                        c.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0])
            finally:
                c.close()
        vorher = stand()
        # Abbruch mitten im Schritt: alles bleibt wie vorher, der nächste Start versucht es neu.
        alt = models.SCHRITTE[33]

        def bricht(c):
            alt(c)
            raise RuntimeError("Abbruch (Probe)")
        models.SCHRITTE[33] = bricht
        try:
            try:
                models.migrieren(conn)
                raise AssertionError("Der Abbruch hätte durchschlagen müssen.")
            except RuntimeError:
                pass
        finally:
            models.SCHRITTE[33] = alt
        conn.close()
        assert stand() == vorher and vorher[1] == "32", stand()
        make_app(tmp)                                       # Neustart: Schritt 33 läuft
        nachher, version = stand()
        assert version == "34"
        assert nachher["admin@example.org"] == (3, 3, 3, 3, 3), nachher
        assert nachher["m@example.org"] == (1, 1, 1, 1, 0) and nachher["n@example.org"] == (0, 0, 0, 0, 0)
        assert nachher["v@example.org"] == (3, 3, 3, 3, 0) and nachher["g@example.org"] == (3, 1, 0, 3, 0), nachher
        # Danach vergebene Redakteure (2) bleiben über weitere Starts 2.
        c = sqlite3.connect(pfad)
        c.execute("UPDATE users SET recht_wiki = 2 WHERE email = 'm@example.org'")
        c.commit()
        c.close()
        zweiter = stand()
        make_app(tmp)
        assert stand() == zweiter and zweiter[0]["m@example.org"] == (1, 2, 1, 1, 0)
        print("Migrations-Test bestanden.")


def test_materialablage():
    """Die Materialablage bleibt fachlich gleich: Verwaltung heißt dort jetzt 3, die Beschriftung des Journals kennt 2
    (vor Schritt 33) und 3 als Verwaltung; der Mailempfänger „Material-Verwaltung“ findet die Stufe 3."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        _, mv_id = konto(app, adm, "mara@example.org", "Mara Materialverwaltung", {"material": VERWALTUNG})
        from app.material.services import beschriftung, rechte
        assert beschriftung.wert_text(2, "recht_material") == "Verwaltung (2)"
        assert beschriftung.wert_text(3, "recht_material") == "Verwaltung (3)"
        assert beschriftung.wert_text(1, "recht_material") == "Mitglied (1)"
        with app.test_request_context():
            assert [u["id"] for u in rechte.material_verwaltung_konten()] == [mv_id]
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "material", "static",
                               "material.js"), encoding="utf-8").read()
        assert '["kein Zugriff", "Mitglied", "Verwaltung", "Verwaltung"][v]' in js
        print("Materialablage-Test bestanden.")


def test_keine_feste_zwei():
    """Keine Stufe mehr als feste Zahl 2 in Skripten und Vorlagen (Rechte-Vergleiche) und keine in SQL außer den
    historischen Schritten der Materialablage (bis 10) und db.NACHARBEITEN."""
    wurzel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
    js_muster = re.compile(r"(rechte|\.rechte\.\w+|rechte\[\w+\])\s*(===?|>=|<=|!==?)\s*2\b|"
                           r"\b(karte|wiki|pruefungen|material|verwaltung)\s*===?\s*2\b")
    sql_muster = re.compile(r"recht_\w+\s*(=|>=|<|<=|!=)\s*2\b")
    funde = []
    for ordner, _, dateien in os.walk(wurzel):
        for name in dateien:
            pfad = os.path.join(ordner, name)
            if "vendor" in pfad or not name.endswith((".js", ".html", ".py")):
                continue
            text = open(pfad, encoding="utf-8").read()
            if name.endswith((".js", ".html")):
                funde += [f"{pfad}: {m.group(0)}" for m in js_muster.finditer(text)]
            if name.endswith(".py") and not pfad.endswith(os.path.join("app", "db.py")) \
                    and not pfad.endswith(os.path.join("material", "models.py")):
                funde += [f"{pfad}: {m.group(0)}" for m in sql_muster.finditer(text)]
    assert not funde, funde
    print("Statische Prüfung bestanden.")


if __name__ == "__main__":
    test_leitstelle()
    test_wiki()
    test_karte()
    test_riegenkarten()
    test_migration()
    test_materialablage()
    test_keine_feste_zwei()
