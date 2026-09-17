"""Rauchtest gegen die Flask-App (ohne Browser): python tests/test_smoke.py  oder  pytest tests/"""
import io
import logging
import multiprocessing
import os
import re
import socket
import sqlite3
import sys
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

H = {"X-Requested-With": "XMLHttpRequest"}


def make_app(tmp):
    os.environ.update({
        "DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "http://localhost",
        "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123",
    })
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


def jpeg(with_gps):
    img = Image.new("RGB", (640, 480), (200, 30, 30))
    exif = Image.Exif()
    if with_gps:
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2], gps[3], gps[4], gps[5], gps[6] = "N", (48.0, 8.0, 30.0), "E", (9.0, 10.0, 0.0), b"\x00", 512.0
        ex = exif.get_ifd(0x8769)
        ex[0x9003] = "2026:09:01 10:11:12"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    buf.seek(0)
    return buf


class PruefstandSMTP(threading.Thread):
    """Ein winziger SMTP-Server für die Prüfung. Er nimmt Mails an und legt sie ab; Empfänger,
    die „abweisen“ im Namen tragen, lehnt er mit 550 ab – damit lässt sich prüfen, ob die
    Anwendung die Antwort des Mailservers auch wirklich auswertet."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.post = []                      # [(Umschlagabsender, [Empfänger], Rohtext)]
        self._laeuft = True

    def run(self):
        # Mit Zeitschranke statt blockierendem accept: Ein close() aus einem anderen Faden weckt
        # ein wartendes accept() nicht zuverlässig, und der Faden liefe weiter.
        self.sock.settimeout(0.2)
        self.faeden = []
        while self._laeuft:
            try:
                verbindung, _ = self.sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            f = threading.Thread(target=self._sitzung, args=(verbindung,), daemon=True)
            self.faeden.append(f)
            f.start()

    def _sitzung(self, c):
        f = c.makefile("rb")
        sag = lambda t: c.sendall((t + "\r\n").encode())
        sag("220 pruefstand ESMTP")
        umschlag, empfaenger, daten = None, [], []
        while True:
            zeile = f.readline()
            if not zeile:
                break
            b = zeile.decode("utf-8", "replace").strip()
            o = b.upper()
            if o.startswith(("EHLO", "HELO")):
                sag("250-pruefstand")
                sag("250 SIZE 10240000")
            elif o.startswith("MAIL FROM:"):
                umschlag = b[10:].split()[0].strip().strip("<>")
                sag("250 OK")
            elif o.startswith("RCPT TO:"):
                adr = b[8:].split()[0].strip().strip("<>")
                if "abweisen" in adr:
                    sag("550 5.1.1 Unbekannter Empfaenger")
                else:
                    empfaenger.append(adr)
                    sag("250 OK")
            elif o == "DATA":
                sag("354 los")
                while True:
                    z = f.readline()
                    if not z or z.strip() == b".":
                        break
                    daten.append(z.decode("utf-8", "replace"))
                self.post.append((umschlag, empfaenger, "".join(daten)))
                umschlag, empfaenger, daten = None, [], []
                sag("250 2.0.0 Angenommen")
            elif o == "QUIT":
                sag("221 tschuess")
                break
            else:
                sag("250 OK")
        c.close()

    def stop(self):
        self._laeuft = False
        for f in getattr(self, "faeden", []):
            f.join(timeout=2)
        try:
            self.sock.close()
        except OSError:
            pass


def test_everything():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = app.test_client()

        # Seiten ohne Login leiten zur Anmeldung (und zwar auf /login, nicht auf eine andere Auth-Seite)
        for path in ("/", "/wiki", "/profil", "/admin"):
            r = c.get(path)
            assert r.status_code == 302 and r.headers["Location"].startswith("/login?next="), (path, r.headers)
        assert '"f-login"' in c.get("/login").text
        assert "fehlt der Link" in c.get("/reset").text          # Reset ohne Token erklärt sich
        assert 'data-next="/"' in c.get("/login?next=//evil.com").text  # keine offene Weiterleitung
        assert c.get("/api/albums").status_code == 401

        # CSRF-Schutz: Formular-POST ohne Header wird abgelehnt
        r = c.post("/api/auth/login", data={"email": "x", "password": "y"})
        assert r.status_code == 403

        # Login als Admin
        r = c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"})
        assert r.status_code == 200 and r.json["user"]["role"] == "admin"
        assert c.get("/").status_code == 200
        assert "Content-Security-Policy" in c.get("/").headers

        # Zweiter Nutzer per Kontoanfrage: gesperrt bis zur Freigabe durch den Admin
        c2 = app.test_client()
        r = c2.post("/api/auth/register", json={"email": "sr@example.org", "password": "passwort1", "name": "Sabine",
                                                "gliederung": "OG Test", "reason": "SR2, Ausbildung"})
        assert r.status_code == 201 and r.json["pending"] is True
        assert c2.post("/api/auth/register", json={"email": "x2@example.org", "password": "passwort1", "name": "X"}).status_code == 400  # Gliederung Pflicht
        r = c2.post("/api/auth/login", json={"email": "sr@example.org", "password": "passwort1"})
        assert r.status_code == 403 and "Freigabe" in r.json["error"]
        pend = [u for u in c.get("/api/admin/users").json["users"] if u["status"] == "pending"]
        assert len(pend) == 1 and pend[0]["reason"] == "SR2, Ausbildung"
        assert c.post(f"/api/admin/users/{pend[0]['id']}/approve", json={}).status_code == 200
        assert c2.post("/api/auth/login", json={"email": "sr@example.org", "password": "passwort1"}).status_code == 200

        # Album + Uploads (ein Bild mit, eins ohne Geotag)
        r = c2.post("/api/albums", json={"title": "Wehr Test", "category": "wasser", "contact_name": "Max"})
        assert r.status_code == 201
        aid = r.json["album"]["id"]
        data = {"files": [(jpeg(True), "mit.jpg"), (jpeg(False), "ohne.jpg"), (io.BytesIO(b"\x00\x00\x00\x18ftypmp42"), "clip.mp4")],
                "posters": [(io.BytesIO(b""), ""), (io.BytesIO(b""), ""), (jpeg(False), "poster.jpg")]}
        r = c2.post(f"/api/albums/{aid}/photos", data=data, headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.json
        photos = r.json["photos"]
        assert len(photos) == 3 and len(r.json["unlocated"]) == 2
        vid = next(p for p in photos if p["kind"] == "video")
        assert c2.get(vid["thumb"]).status_code == 200 and c2.get(vid["orig"]).status_code == 200
        c2.put(f"/api/photos/{vid['id']}", json={"lat": 48.2, "lon": 9.3})
        geo = next(p for p in photos if p["lat"] is not None)
        assert abs(geo["lat"] - (48 + 8 / 60 + 30 / 3600)) < 1e-6 and geo["altitude"] == 512.0
        assert geo["taken_at"].startswith("2026-09-01T10:11:12")
        assert c2.get(geo["thumb"]).status_code == 200
        assert c2.get(geo["web"]).status_code == 200

        # --- Albumdeckblatt ------------------------------------------------------------------
        # Ohne Wahl zeigt das Album sein erstes Bild; das gewählte Deckblatt geht vor und wird
        # auch auf der Karte gekennzeichnet, damit es im Bilderstapel obenauf liegt.
        albumliste = lambda: [a for a in c2.get("/api/albums").json["albums"] if a["id"] == aid][0]
        assert albumliste()["cover"] == photos[0]["thumb"], albumliste()["cover"]
        assert c2.put(f"/api/albums/{aid}/cover", json={"photo_id": vid["id"]}, headers=H).status_code == 200
        assert albumliste()["cover"] == vid["thumb"]
        assert [p["id"] for p in c2.get("/api/map").json["photos"] if p["cover"]] == [vid["id"]]
        # Ein Bild aus einem anderen Album darf nicht Deckblatt werden.
        fremd = c2.post("/api/albums", json={"title": "Fremd", "category": "seil"}).json["album"]["id"]
        assert c2.put(f"/api/albums/{fremd}/cover", json={"photo_id": vid["id"]}, headers=H).status_code == 400
        assert c2.put(f"/api/albums/{aid}/cover", json={"photo_id": None}, headers=H).status_code == 200
        assert albumliste()["cover"] == photos[0]["thumb"]
        c2.delete(f"/api/albums/{fremd}", headers=H)

        # Bild ohne Geotag manuell platzieren, Notiz + Höhe setzen
        pid = r.json["unlocated"][0]
        r = c2.put(f"/api/photos/{pid}", json={"lat": 48.1, "lon": 9.2, "note": "Ankerpunkt", "height_m": "12,5"})
        assert r.status_code == 200 and r.json["photo"]["geo_source"] == "manual" and r.json["photo"]["height_m"] == 12.5
        assert len(c2.get("/api/map").json["photos"]) == 3 and {p["kind"] for p in c2.get("/api/map").json["photos"]} == {"image", "video"}

        # --- Einwurf: Dateien auf die Karte gezogen → neues Album; liegt eines in der Nähe, sagt
        #     die Antwort das, und die Bilder lassen sich dorthin zusammenlegen ------------------
        # Zwei Alben genau am Geotag der Probebilder: eines von Sabine (c2), eines vom Admin (c).
        # „Wehr Test“ liegt mit seinen drei Bildern im Mittel gut vier Kilometer weit weg.
        nah = c2.post("/api/albums", json={"title": "Nahe", "category": "seil"}).json["album"]["id"]
        assert c2.post(f"/api/albums/{nah}/photos", data={"files": [(jpeg(True), "n.jpg")]}, headers=H,
                       content_type="multipart/form-data").status_code == 201
        fremdnah = c.post("/api/albums", json={"title": "Fremd nah", "category": "seil"}).json["album"]["id"]
        assert c.post(f"/api/albums/{fremdnah}/photos", data={"files": [(jpeg(True), "f.jpg")]}, headers=H,
                      content_type="multipart/form-data").status_code == 201
        alben = lambda: len(c2.get("/api/albums").json["albums"])
        vorher = alben()
        # Ohne Titel entsteht nichts.
        r = c2.post("/api/albums/einwurf", data={"files": [(jpeg(True), "a.jpg")], "title": " ", "category": "seil"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 400 and "Titel" in r.json["error"] and alben() == vorher
        # Nur Unbrauchbares: kein leeres Album bleibt zurück.
        r = c2.post("/api/albums/einwurf", data={"files": [(io.BytesIO(b"nix"), "x.txt")], "title": "Leer", "category": "seil"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 400 and ".txt" in r.json["error"] and alben() == vorher, r.json
        # Ein Bild mit und eins ohne Geotag, dazu eine Datei über der engen Anfragegrenze (1 MB):
        # Der Einwurf gehört zu den Hochladewegen und muss die große Grenze bekommen.
        gross = io.BytesIO()
        Image.frombytes("RGB", (1400, 1000), os.urandom(1400 * 1000 * 3)).save(gross, "JPEG", quality=95)
        assert gross.tell() > 1024 * 1024
        gross.seek(0)
        r = c2.post("/api/albums/einwurf", data={"files": [(jpeg(True), "e.jpg"), (jpeg(False), "o.jpg"), (gross, "gross.jpg")],
                                                "title": "Einwurf", "category": "wasser"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201, r.json
        e = r.json
        assert e["album"]["title"] == "Einwurf" and e["album"]["category"] == "wasser" and e["album"]["can_edit"] is True
        assert len(e["photos"]) == 3 and len(e["unlocated"]) == 2 and e["errors"] == []
        nahe = {n["title"]: n for n in e["nahe"]}
        assert set(nahe) == {"Nahe", "Fremd nah"}, nahe                 # „Wehr Test“ ist zu weit
        assert nahe["Nahe"]["can_edit"] is True and nahe["Fremd nah"]["can_edit"] is False
        assert nahe["Nahe"]["abstand_m"] < 5 and nahe["Nahe"]["photo_count"] == 1
        assert e["nahe"][0]["abstand_m"] <= e["nahe"][1]["abstand_m"]  # nächstes zuerst
        neu_id = e["album"]["id"]
        # In ein fremdes Album darf Sabine nicht zusammenlegen; das neue Album bleibt dann stehen.
        assert c2.post(f"/api/albums/{neu_id}/zusammenlegen", json={"ziel": fremdnah}).status_code == 403
        assert c2.post(f"/api/albums/{neu_id}/zusammenlegen", json={"ziel": neu_id}).status_code == 400
        assert c2.post(f"/api/albums/{neu_id}/zusammenlegen", json={"ziel": 999999}).status_code == 404
        assert c2.get(f"/api/albums/{neu_id}").status_code == 200
        # In das eigene: Die Bilder wandern hinten dran, das neue Album löst sich auf.
        r = c2.post(f"/api/albums/{neu_id}/zusammenlegen", json={"ziel": nah})
        assert r.status_code == 200 and r.json["album"]["id"] == nah and r.json["album"]["photo_count"] == 4, r.json
        assert c2.get(f"/api/albums/{neu_id}").status_code == 404
        reihe = [p["id"] for p in c2.get(f"/api/albums/{nah}").json["album"]["photos"]]
        assert reihe[1:] == [p["id"] for p in e["photos"]], reihe          # Reihenfolge bleibt, hinten angehängt
        assert alben() == vorher + 0
        # Ohne Geotag gibt es keine Nähe und keine Rückfrage.
        r = c2.post("/api/albums/einwurf", data={"files": [(jpeg(False), "o.jpg")], "title": "Ohne", "category": "seil"},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 201 and r.json["nahe"] == [] and r.json["unlocated"] == [r.json["photos"][0]["id"]]
        for a_id, client in ((nah, c2), (fremdnah, c), (r.json["album"]["id"], c2)):
            assert client.delete(f"/api/albums/{a_id}", headers=H).status_code == 200
        assert len(c2.get("/api/map").json["photos"]) == 3
        # Slideshow für die Anmeldeseite: signierte Links, ohne Login abrufbar
        anon = app.test_client()
        imgs = anon.get("/api/public/slideshow").json["images"]
        assert imgs and anon.get(imgs[0]["url"]).status_code == 200
        assert anon.get("/media/slide/kaputt").status_code == 404

        # Rechte: fremder Nutzer darf nicht bearbeiten, Admin schon
        c3 = app.test_client()
        c3.post("/api/auth/register", json={"email": "x@example.org", "password": "passwort1", "name": "Xaver", "gliederung": "OG X"})
        x_id = [u for u in c.get("/api/admin/users").json["users"] if u["email"] == "x@example.org"][0]["id"]
        c.post(f"/api/admin/users/{x_id}/approve", json={})
        c3.post("/api/auth/login", json={"email": "x@example.org", "password": "passwort1"})
        assert c3.put(f"/api/albums/{aid}", json={"title": "Hack"}).status_code == 403
        # Das Deckblatt darf nur festlegen, wer das Album bearbeiten darf.
        assert c3.put(f"/api/albums/{aid}/cover", json={"photo_id": vid["id"]}, headers=H).status_code == 403
        assert c3.get(f"/api/albums/{aid}").status_code == 200
        assert c.put(f"/api/albums/{aid}", json={"title": "Wehr Test (Admin)"}).status_code == 200

        # Wiki: Seite, Unterseite, Suche, Verlauf
        r = c2.post("/api/wiki/pages", json={"title": "Anker", "content": "# Anker\n\n:::info\n**Tipp**\n\nText\n:::\n"})
        assert r.status_code == 201
        root = r.json["page"]
        r = c2.post("/api/wiki/pages", json={"title": "Ringankern", "parent_id": root["id"], "content": "Ring"})
        assert r.status_code == 201 and r.json["page"]["slug"] == "ringankern"
        assert c2.put(f"/api/wiki/pages/{root['id']}", json={"content": "# Anker\n\nneu", "format": "markdown"}).status_code == 200
        # Fremde dürfen nicht bearbeiten – bis der Ersteller sie freigibt (Freigabe vererbt sich auf Unterseiten)
        assert c3.put(f"/api/wiki/pages/{root['id']}", json={"content": "hack"}).status_code == 403
        assert c3.put(f"/api/wiki/pages/{root['id']}/editors", json={"user_ids": [x_id]}).status_code == 403
        assert c2.put(f"/api/wiki/pages/{root['id']}/editors", json={"user_ids": [x_id]}).status_code == 200
        assert c3.put(f"/api/wiki/pages/{root['id']}", json={"content": "# Anker\n\nvon Xaver", "format": "markdown"}).status_code == 200
        ring = c3.get("/api/wiki/pages/ringankern").json["page"]
        assert ring["can_edit"] is True and ring["can_delete"] is False
        # Kommentare: Kommentator und Seitenersteller dürfen löschen, andere nicht
        r = c3.post(f"/api/wiki/pages/{root['id']}/comments", json={"body": "Lastwinkel prüfen?", "quote": "von Xaver"})
        assert r.status_code == 201
        cid = r.json["comment"]["id"]
        c4x = app.test_client()
        c4x.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"})
        assert c2.get(f"/api/wiki/pages/{root['id']}/comments").json["comments"][0]["can_delete"] is True   # Ersteller
        assert c3.get(f"/api/wiki/pages/{root['id']}/comments").json["comments"][0]["can_delete"] is True   # Kommentator
        r = c3.post(f"/api/wiki/pages/{root['id']}/comments", json={"body": "Antwort", "parent_id": cid})
        assert r.status_code == 201
        assert c3.delete(f"/api/wiki/comments/{cid}", headers=H).status_code == 200
        assert c2.get(f"/api/wiki/pages/{root['id']}/comments").json["comments"] == []
        # Öffentliche Freigabe: nur Admin; Abschnitt inkl. Unterseiten; ohne Login lesbar; Subdomain
        assert anon.get("/api/public/pages/anker").status_code == 404
        assert c2.put(f"/api/wiki/pages/{root['id']}/share", json={"is_public": True}).status_code == 403
        assert c.put(f"/api/wiki/pages/{root['id']}/share", json={"is_public": True, "public_children": True}).status_code == 200
        pub = anon.get("/api/public/pages/ringankern").json
        assert pub["page"]["title"] == "Ringankern" and {t["slug"] for t in pub["tree"]} == {"anker", "ringankern"}
        assert anon.get("/api/public/index").json["pages"][0]["slug"] == "anker"
        assert anon.get("/oeffentlich/ringankern").status_code == 200
        r = anon.get("/", headers={"Host": "wiki.xn--strmis-yxa.de"})
        assert r.status_code == 200 and "public.js" in r.text
        r = anon.get("/ringankern", headers={"Host": "wiki.xn--strmis-yxa.de"})
        assert r.status_code == 200 and "public.js" in r.text
        assert anon.get("/ringankern").status_code == 404
        assert anon.get("/api/wiki/tree", headers={"Host": "wiki.xn--strmis-yxa.de"}).status_code == 401
        assert len(c2.get(f"/api/wiki/pages/{root['id']}/revisions").json["revisions"]) == 3
        assert c2.get("/api/wiki/search?q=ring").json["results"][0]["slug"] == "ringankern"
        assert c3.delete(f"/api/wiki/pages/{root['id']}", headers=H).status_code == 403
        assert c3.delete(f"/api/wiki/pages/{root['id']}").status_code == 403  # ohne Header: CSRF-Schutz

        # Xaver hat „Anker“ im Editor offen, während Sabine die Seite speichert – sein Stand ist
        # von vorher. Sein nächstes automatisches Speichern darf ihren nicht überschreiben.
        vor = c3.get("/api/wiki/pages/anker").json["page"]["version"]
        assert c2.put(f"/api/wiki/pages/{root['id']}", json={"content": "# Anker\n\nvon Sabine",
                                                             "format": "markdown"}).status_code == 200
        r = c3.put(f"/api/wiki/pages/{root['id']}", json={"content": "# Anker\n\nalter Stand",
                                                          "format": "markdown", "base_version": vor})
        assert r.status_code == 409, r.json
        assert c2.get("/api/wiki/pages/anker").json["page"]["content"] == "# Anker\n\nvon Sabine"
        assert len(c2.get(f"/api/wiki/pages/{root['id']}/revisions").json["revisions"]) == 4

        # Eine neue Seite bringt ihre Verweise mit: Die Rückverweisliste des Ziels füllt sich beim
        # Speichern, nicht erst beim nächsten Öffnen.
        seil = c2.post("/api/wiki/pages", json={"title": "Seiltechnik", "content": "# Seiltechnik"}).json["page"]
        band = c2.post("/api/wiki/pages", json={"title": "Bandschlingenanker", "parent_id": seil["id"],
                                                "content": "# Bandschlingenanker\n\nText"}).json["page"]
        c2.post("/api/wiki/pages", json={"title": "Neu", "parent_id": seil["id"],
                                         "content": "Mit [Verweis](/wiki/bandschlingenanker)"})
        rueck = c2.get(f"/api/wiki/pages/{band['id']}/backlinks").json
        assert [q["title"] for q in rueck["pages"]] == ["Neu"], rueck
        tree = c2.get("/api/wiki/tree").json["pages"]
        assert {p["title"] for p in tree} == {"Seiltechnik", "Neu", "Anker", "Ringankern", "Bandschlingenanker"}
        # Keine Hintertür: Im öffentlichen Abschnitt „Anker“ darf ein Nicht-Administrator keine
        # Unterseite anlegen – sonst käme Veröffentlichen durch die Hintertür.
        r = c2.post("/api/wiki/pages", json={"title": "Hintertür", "parent_id": root["id"], "content": "Geheim"})
        assert r.status_code == 403, r.json
        assert c2.get("/api/wiki/pages/hintertuer").json.get("page") is None

        # Wiki-Anhang: öffentlich nur, wenn eine öffentliche Seite ihn einbindet
        r = c2.post("/api/wiki/files", data={"file": (jpeg(False), "skizze.jpg")}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["kind"] == "image"
        assert anon.get(r.json["url"]).status_code in (401, 302)  # nicht öffentlich: Login-Weiterleitung
        c2.put(f"/api/wiki/pages/{root['id']}", json={"content": f"# Anker\n\n![s]({r.json['url']})", "format": "markdown"})
        assert anon.get(r.json["url"]).status_code == 200
        # Zuschneiden: Das Ergebnis ist eine NEUE Datei, das Ausgangsbild bleibt liegen –
        # sonst verlöre ein Bild, das an zwei Stellen steht, an beiden seine Ränder.
        bild = r.json["url"].rsplit("/", 1)[-1]
        zu = c2.post("/api/wiki/files/zuschnitt", headers=H,
                     json={"file": r.json["url"], "x": 0.25, "y": 0.5, "w": 0.5, "h": 0.5})
        assert zu.status_code == 200 and zu.json["url"] != r.json["url"], zu.json
        medien = os.path.join(tmp, "media", "wiki")
        assert os.path.isfile(os.path.join(medien, bild))            # das Original steht noch da
        with Image.open(os.path.join(medien, zu.json["url"].rsplit("/", 1)[-1])) as aus:
            assert aus.size == (320, 240), aus.size                  # 640x480, halbiert
        # Ein Ausschnitt außerhalb des Bildes und ein Weg nach draußen werden abgewiesen
        assert c2.post("/api/wiki/files/zuschnitt", headers=H,
                       json={"file": bild, "x": 0.8, "y": 0, "w": 0.5, "h": 1}).status_code == 400
        assert c2.post("/api/wiki/files/zuschnitt", headers=H,
                       json={"file": "../../stroemis.db", "x": 0, "y": 0, "w": 1, "h": 1}).status_code == 400

        # Drehen: ebenfalls eine neue Datei, Kanten vertauscht, das Ausgangsbild bleibt
        dr = c2.post("/api/wiki/files/drehung", headers=H, json={"file": r.json["url"], "grad": 90})
        assert dr.status_code == 200 and dr.json["url"] != r.json["url"], dr.json
        gedreht = dr.json["url"].rsplit("/", 1)[-1]
        with Image.open(os.path.join(medien, gedreht)) as aus:
            assert aus.size == (480, 640), aus.size                   # aus 640x480 wird hochkant
        assert os.path.isfile(os.path.join(medien, bild))             # das Original steht noch da
        # Zweimal 90 Grad ist dasselbe wie einmal 180 – und führt zurück ins Querformat
        dr2 = c2.post("/api/wiki/files/drehung", headers=H, json={"file": dr.json["url"], "grad": 90})
        with Image.open(os.path.join(medien, dr2.json["url"].rsplit("/", 1)[-1])) as aus:
            assert aus.size == (640, 480), aus.size
        for schlecht in (45, 0, 360, "rechts", None):
            rr = c2.post("/api/wiki/files/drehung", headers=H, json={"file": bild, "grad": schlecht})
            assert rr.status_code == 400 and "Vierteln" in rr.json["error"], (schlecht, rr.json)
        assert c2.post("/api/wiki/files/drehung", headers=H,
                       json={"file": "../../stroemis.db", "grad": 90}).status_code == 400
        assert c2.post("/api/wiki/files/drehung", headers=H, json={"grad": 90}).status_code == 400
        assert c2.post("/api/wiki/files/drehung", headers=H,
                       json={"file": "fehlt-gar-nicht.jpg", "grad": 90}).status_code == 400
        assert anon.post("/api/wiki/files/drehung", headers=H,
                         json={"file": bild, "grad": 90}).status_code in (302, 401)
        # Die Richtung stimmt: Eine Ecke oben links steht nach der Rechtsdrehung oben rechts.
        ecke = Image.new("RGB", (400, 200), (250, 250, 250))
        ecke.paste((200, 20, 20), (0, 0, 80, 60))         # roter Klotz oben links
        eb = io.BytesIO(); ecke.save(eb, "PNG"); eb.seek(0)
        eu = c2.post("/api/wiki/files", data={"file": (eb, "ecke.png")}, headers=H,
                     content_type="multipart/form-data")
        def rot_bei(pfad, x, y):
            with Image.open(pfad) as im:
                p = im.convert("RGB").getpixel((x, y))
                return p[0] > 150 and p[1] < 90
        rechts = c2.post("/api/wiki/files/drehung", headers=H, json={"file": eu.json["url"], "grad": 90})
        pfad_r = os.path.join(medien, rechts.json["url"].rsplit("/", 1)[-1])
        with Image.open(pfad_r) as im:
            assert im.size == (200, 400), im.size
        assert rot_bei(pfad_r, 195, 5) and not rot_bei(pfad_r, 5, 5), "nach rechts gedreht gehört die Ecke nach oben rechts"
        links = c2.post("/api/wiki/files/drehung", headers=H, json={"file": eu.json["url"], "grad": 270})
        pfad_l = os.path.join(medien, links.json["url"].rsplit("/", 1)[-1])
        assert rot_bei(pfad_l, 5, 395) and not rot_bei(pfad_l, 5, 5), "nach links gedreht gehört die Ecke nach unten links"
        halb = c2.post("/api/wiki/files/drehung", headers=H, json={"file": eu.json["url"], "grad": 180})
        pfad_h = os.path.join(medien, halb.json["url"].rsplit("/", 1)[-1])
        assert rot_bei(pfad_h, 395, 195) and not rot_bei(pfad_h, 5, 5), "um 180 Grad gehört die Ecke nach unten rechts"

        # Importierte Bilder tragen ihre Aufnahmerichtung noch im EXIF – die Drehung muss sie
        # vorher anwenden, sonst kippt das Bild um eine Vierteldrehung zu viel.
        quer = Image.new("RGB", (640, 480), (20, 90, 160))
        ex = Image.Exif(); ex[0x0112] = 6                 # „hochkant, 90 Grad im Uhrzeigersinn“
        with open(os.path.join(medien, "ausimport.jpg"), "wb") as fh:
            quer.save(fh, "JPEG", exif=ex.tobytes())
        ri = c2.post("/api/wiki/files/drehung", headers=H,
                     json={"file": "/media/wiki/ausimport.jpg", "grad": 90})
        assert ri.status_code == 200, ri.json
        with Image.open(os.path.join(medien, ri.json["url"].rsplit("/", 1)[-1])) as aus:
            # Angezeigt wird die Datei als 480x640; eine Vierteldrehung macht daraus 640x480.
            assert aus.size == (640, 480), aus.size

        # Ein GIF bleibt außen vor – beim Neuschreiben ginge die Bewegung verloren.
        gif = c2.post("/api/wiki/files", data={"file": (io.BytesIO(b"GIF89a" + b"\x00" * 20), "bewegt.gif")},
                      headers=H, content_type="multipart/form-data")
        assert gif.status_code == 200, gif.json
        rr = c2.post("/api/wiki/files/drehung", headers=H, json={"file": gif.json["url"], "grad": 90})
        assert rr.status_code == 400 and "nicht drehen" in rr.json["error"], rr.json
        # Ein durchsichtiges PNG bleibt durchsichtig: Sonst bekäme ein freigestelltes Bild
        # beim Drehen einen weißen Kasten.
        durch = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
        durch.paste((10, 120, 200, 255), (0, 0, 150, 120))
        pb = io.BytesIO(); durch.save(pb, "PNG"); pb.seek(0)
        pu = c2.post("/api/wiki/files", data={"file": (pb, "frei.png")}, headers=H,
                     content_type="multipart/form-data")
        pd = c2.post("/api/wiki/files/drehung", headers=H, json={"file": pu.json["url"], "grad": 270})
        assert pd.status_code == 200 and pd.json["url"].endswith(".png"), pd.json
        with Image.open(os.path.join(medien, pd.json["url"].rsplit("/", 1)[-1])) as aus:
            assert aus.size == (120, 300) and aus.mode == "RGBA", (aus.size, aus.mode)
            assert aus.getpixel((5, 5))[3] == 0, aus.getpixel((5, 5))   # oben links bleibt leer

        r = c2.post("/api/wiki/files", data={"file": (io.BytesIO(b"\x00\x00\x00\x18ftypmp42"), "c.mov")}, headers=H, content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["kind"] == "video"

        # Anhänge: Dokumente werden unverändert abgelegt, ausführbare Dateien abgewiesen
        for name, kind in (("handbuch.pdf", "file"), ("liste.xlsx", "file"), ("track.gpx", "file")):
            r = c2.post("/api/wiki/files", data={"file": (io.BytesIO(b"%PDF-1.4 test"), name)},
                        headers=H, content_type="multipart/form-data")
            assert r.status_code == 200 and r.json["kind"] == kind, (name, r.status_code, r.json)
            assert r.json["url"].endswith(os.path.splitext(name)[1]), r.json["url"]
            assert c2.get(r.json["url"]).status_code == 200          # angemeldet abrufbar
            assert anon.get(r.json["url"]).status_code in (401, 302)  # ohne Freigabe nicht öffentlich
        for name in ("schaedlich.exe", "start.sh", "makro.docm"):
            r = c2.post("/api/wiki/files", data={"file": (io.BytesIO(b"MZ"), name)},
                        headers=H, content_type="multipart/form-data")
            assert r.status_code == 400, (name, r.status_code)

        # Admin-Endpunkte + Passwort-Reset-Link
        assert c2.get("/api/admin/users").status_code == 403
        users = c.get("/api/admin/users").json["users"]
        assert len(users) == 3 and all(u["status"] == "active" for u in users)
        r = c.post("/api/auth/forgot", json={"email": "sr@example.org"})
        assert r.status_code == 200
        from app.auth import make_reset_token
        with app.app_context():
            from app import db
            u = db.query("SELECT * FROM users WHERE email = 'sr@example.org'", one=True)
            token = make_reset_token(u)
        c4 = app.test_client()
        assert c4.post("/api/auth/reset", json={"token": token, "password": "neuespw12"}).status_code == 200
        assert c4.post("/api/auth/reset", json={"token": token, "password": "neuespw12"}).status_code == 400
        assert c4.post("/api/auth/login", json={"email": "sr@example.org", "password": "neuespw12"}).status_code == 200

        # Löschen räumt Dateien weg
        r = c2.delete(f"/api/albums/{aid}", headers=H); assert r.status_code == 200, (r.status_code, r.get_json())
        assert c2.get(geo["thumb"]).status_code == 404
        # --- Seiteneigenschaften, Merkliste, Papierkorb, Export, Sortieren, Rückverweise ---
        icon = c2.put(f"/api/wiki/pages/{root['id']}/icon", json={"icon": "🧗"})
        assert icon.status_code == 200 and icon.json["page"]["icon"] == "🧗"
        assert c2.put(f"/api/wiki/pages/{root['id']}/options", json={"is_template": True}).status_code == 200
        assert [p["title"] for p in c2.get("/api/wiki/templates").json["pages"]] == ["Anker"]
        assert c2.put(f"/api/wiki/pages/{root['id']}/favorite", json={"favorite": True}).json["favorite"] is True
        assert [p["title"] for p in c2.get("/api/wiki/favorites").json["pages"]] == ["Anker"]
        assert any(p["favorite"] for p in c2.get("/api/wiki/tree").json["pages"])
        assert c2.get("/api/wiki/recent").json["changed"], "zuletzt geändert darf nicht leer sein"

        # Rückverweise: Anker verlinkt auf ringankern (aus dem Import-Inhalt)
        c2.put(f"/api/wiki/pages/{root['id']}", json={"content": "# Anker\n\n[zu Ring](/wiki/ringankern)", "format": "markdown"})
        ring_id = [p for p in c2.get("/api/wiki/tree").json["pages"] if p["slug"] == "ringankern"][0]["id"]
        assert [p["slug"] for p in c2.get(f"/api/wiki/pages/{ring_id}/backlinks").json["pages"]] == ["anker"]

        # Umbenennen: Im Text von Anker steht weiter der alte Name. Der Verweis muss trotzdem in
        # beide Richtungen halten – samt Zähler in den Angaben zur Seite.
        def rueck(pid):
            return [q["title"] for q in c2.get(f"/api/wiki/pages/{pid}/backlinks").json["pages"]]

        def hin(pid):
            return [q["title"] for q in c2.get(f"/api/wiki/pages/{pid}/backlinks").json["outgoing"]]

        c2.put(f"/api/wiki/pages/{ring_id}", json={"title": "Ringanker"})
        umbenannt = c2.get("/api/wiki/pages/ringanker").json["page"]
        assert umbenannt["id"] == ring_id and umbenannt["backlink_count"] == 1, umbenannt
        assert rueck(ring_id) == ["Anker"]
        assert hin(root["id"]) == ["Ringanker"]
        # Das nächste Speichern von Anker trägt den alten Namen wieder in die Verweistabelle ein –
        # genau daran scheiterte ein Umschreiben der Tabelle beim Umbenennen.
        c2.put(f"/api/wiki/pages/{root['id']}",
               json={"content": "# Anker\n\n[zu Ring](/wiki/ringankern), noch einmal gespeichert", "format": "markdown"})
        assert rueck(ring_id) == ["Anker"] and hin(root["id"]) == ["Ringanker"]
        # Zurück zum alten Namen – er gehört der Seite ja noch. Danach findet auch der Rest des
        # Tests die Seite wieder unter ringankern.
        c2.put(f"/api/wiki/pages/{ring_id}", json={"title": "Ringankern"})
        assert c2.get("/api/wiki/pages/ringankern").json["page"]["slug"] == "ringankern"
        assert rueck(ring_id) == ["Anker"] and hin(root["id"]) == ["Ringankern"]

        # Export: einzelne Seite als Markdown, Abschnitt als ZIP
        r = c2.get(f"/api/wiki/pages/{root['id']}/export")
        assert r.status_code == 200 and b"Anker" in r.data and "attachment" in r.headers["Content-Disposition"]
        r = c2.get(f"/api/wiki/pages/{root['id']}/export?children=1")
        assert r.status_code == 200
        names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
        assert any(n.endswith("Ringankern.md") for n in names), names

        # Duplizieren, sortieren, Papierkorb, Wiederherstellen, endgültig löschen
        dup = c2.post(f"/api/wiki/pages/{root['id']}/duplicate", json={})
        assert dup.status_code == 201
        dup_id = dup.json["page"]["id"]
        # Verschieben in den öffentlichen Abschnitt ist Veröffentlichen – das darf nur der Admin
        assert c2.put("/api/wiki/reorder", json={"items": [{"id": dup_id, "parent_id": root["id"], "position": 3}]}).status_code == 403
        assert c.put("/api/wiki/reorder", json={"items": [{"id": dup_id, "parent_id": root["id"], "position": 3}]}).status_code == 200
        assert c2.put("/api/wiki/reorder", json={"items": [{"id": dup_id, "parent_id": None, "position": 1}]}).status_code == 200
        assert c2.delete(f"/api/wiki/pages/{dup_id}", headers=H).status_code == 200
        assert not any(p["id"] == dup_id for p in c2.get("/api/wiki/tree").json["pages"])   # aus dem Baum raus
        assert any(p["id"] == dup_id for p in c2.get("/api/wiki/trash").json["pages"])
        assert c2.post(f"/api/wiki/pages/{dup_id}/restore", json={}).status_code == 200
        assert any(p["id"] == dup_id for p in c2.get("/api/wiki/tree").json["pages"])       # wieder da
        c2.delete(f"/api/wiki/pages/{dup_id}", headers=H)
        assert c2.delete(f"/api/wiki/trash/{dup_id}", headers=H).status_code == 200
        assert not any(p["id"] == dup_id for p in c2.get("/api/wiki/trash").json["pages"])

        # Suche: Mehrwortsuche und escapte Platzhalter
        assert c2.get("/api/wiki/search?q=anker%20ring").json["results"], "Mehrwortsuche findet nichts"
        assert c2.get("/api/wiki/search?q=%25").json["results"] == []   # "%" ist kein Platzhalter

        # Öffentliche Suche zeigt nur freigegebene Seiten
        pub_hits = anon.get("/api/public/search?q=ring").json["results"]
        assert all(h["slug"] in ("anker", "ringankern", "bandschlingenanker") for h in pub_hits), pub_hits
        assert anon.get("/api/public/search?q=x").json["results"] == []  # zu kurz

        # --- Lesebeschränkung, Beschriftungen, Beobachten ---------------------------------
        priv = c2.post("/api/wiki/pages", json={"title": "Nur intern", "content": "# Nur intern\ngeheimwort"}).json["page"]
        privsub = c2.post("/api/wiki/pages", json={"title": "Nur intern Detail", "parent_id": priv["id"],
                                                   "content": "Details"}).json["page"]
        assert c3.get("/api/wiki/pages/nur-intern").status_code == 200          # vorher frei lesbar
        assert c3.put(f"/api/wiki/pages/{priv['id']}/restrict", json={"read_restricted": True}).status_code == 403
        assert c2.put(f"/api/wiki/pages/{priv['id']}/restrict", json={"read_restricted": True}).status_code == 200
        # Fremde sehen weder Seite noch Unterseite, weder im Baum noch in der Suche
        assert c3.get("/api/wiki/pages/nur-intern").status_code == 403
        assert c3.get(f"/api/wiki/pages/{privsub['slug']}").status_code == 403
        assert not any(p["slug"] == "nur-intern" for p in c3.get("/api/wiki/tree").json["pages"])
        assert c3.get("/api/wiki/search?q=geheimwort").json["results"] == []
        assert c3.get(f"/api/wiki/pages/{priv['id']}/revisions").status_code == 403
        assert c3.get(f"/api/wiki/pages/{priv['id']}/comments").status_code == 403
        assert c3.get(f"/api/wiki/pages/{priv['id']}/export").status_code == 403
        # Ersteller und Admin behalten den Zugriff
        assert c2.get("/api/wiki/pages/nur-intern").status_code == 200
        assert c.get("/api/wiki/pages/nur-intern").status_code == 200
        assert c2.get("/api/wiki/search?q=geheimwort").json["results"], "Ersteller muss finden"
        # Freigabe zum Bearbeiten öffnet auch das Lesen – samt Unterseite
        c2.put(f"/api/wiki/pages/{priv['id']}/editors", json={"user_ids": [x_id]})
        assert c3.get("/api/wiki/pages/nur-intern").status_code == 200
        assert c3.get(f"/api/wiki/pages/{privsub['slug']}").status_code == 200
        # Beschränkt und öffentlich schließen sich gegenseitig aus
        assert c.put(f"/api/wiki/pages/{priv['id']}/share", json={"is_public": True}).status_code == 400
        assert c2.put(f"/api/wiki/pages/{root['id']}/restrict", json={"read_restricted": True}).status_code == 400

        # Beobachten
        assert c3.put(f"/api/wiki/pages/{priv['id']}/watch", json={"watch": True}).json["watch"] is True
        assert [p["slug"] for p in c3.get("/api/wiki/watches").json["pages"]] == ["nur-intern"]
        assert c2.put(f"/api/wiki/pages/{priv['id']}", json={"content": "# Nur intern\ngeaendert",
                                                             "format": "markdown"}).status_code == 200
        assert c3.put(f"/api/wiki/pages/{priv['id']}/watch", json={"watch": False}).json["watch"] is False

        # Kommentar-Anker speichert das Umfeld mit
        rc = c2.post(f"/api/wiki/pages/{priv['id']}/comments",
                     json={"body": "Passt das?", "quote": "geaendert", "quote_before": "intern ", "quote_after": "."})
        assert rc.status_code == 201
        got = c2.get(f"/api/wiki/pages/{priv['id']}/comments").json["comments"][0]
        # Der Kontext wird beim Speichern getrimmt – findText normalisiert Leerraum ohnehin.
        assert got["quote_before"] == "intern" and got["quote_after"] == "." and got["can_edit"] is True

        print("Rauchtest bestanden.")


def test_haertung():
    """Prüft die Absicherungen: Veröffentlichen nur durch Admins, alte Adressen, gleichzeitiges
    Bearbeiten, ein Speichervorgang an der falschen Seite, Anmeldebremse,
    Zwischenspeicher-Kennzeichnung und Verlaufsgrenzen."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        app.config.update(MAX_REVISIONS=3)
        adm = app.test_client()
        adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"})

        # Zwei gewöhnliche Nutzer
        def member(mail):
            c = app.test_client()
            c.post("/api/auth/register", json={"email": mail, "password": "passwort1", "name": mail[:3],
                                               "gliederung": "OG Test"})
            uid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == mail][0]["id"]
            adm.post(f"/api/admin/users/{uid}/approve", json={})
            c.post("/api/auth/login", json={"email": mail, "password": "passwort1"})
            return c, uid
        c1, uid1 = member("a@example.org")
        c2, uid2 = member("b@example.org")

        # --- Veröffentlichen bleibt beim Admin, auch über Unterseiten -----------------------
        pub = adm.post("/api/wiki/pages", json={"title": "Freigegeben", "content": "# Freigegeben"}).json["page"]
        assert adm.put(f"/api/wiki/pages/{pub['id']}/share",
                       json={"is_public": True, "public_children": True}).status_code == 200
        r = c1.post("/api/wiki/pages", json={"title": "Schmuggel", "parent_id": pub["id"], "content": "x"})
        assert r.status_code == 403, r.json                      # Unterseite im freigegebenen Abschnitt
        eigen = c1.post("/api/wiki/pages", json={"title": "Eigen", "content": "x"}).json["page"]
        assert c1.put(f"/api/wiki/pages/{eigen['id']}", json={"parent_id": pub["id"]}).status_code == 403
        assert adm.post("/api/wiki/pages", json={"title": "Erlaubt", "parent_id": pub["id"],
                                                 "content": "x"}).status_code == 201
        assert anon_get(app, "/api/public/pages/erlaubt").status_code == 200
        assert anon_get(app, "/api/public/pages/schmuggel").status_code == 404

        # --- Umbenennen: die alte Adresse trägt weiter ---------------------------------------
        assert c1.put(f"/api/wiki/pages/{eigen['id']}", json={"title": "Umbenannt"}).json["page"]["slug"] == "umbenannt"
        assert c1.get("/api/wiki/pages/eigen").json["page"]["slug"] == "umbenannt"   # alter Link
        # und eine neue Seite bekommt die freigewordene Adresse nicht einfach ab
        assert c2.post("/api/wiki/pages", json={"title": "Eigen"}).json["page"]["slug"] != "eigen"

        # --- Gleichzeitiges Bearbeiten ------------------------------------------------------
        seite = c1.get("/api/wiki/pages/umbenannt").json["page"]
        assert c2.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid2]}).status_code == 403
        c1.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid2]})
        assert c2.put(f"/api/wiki/pages/{eigen['id']}",
                      json={"content": "von b", "base_version": seite["version"]}).status_code == 200
        r = c1.put(f"/api/wiki/pages/{eigen['id']}", json={"content": "von a", "base_version": seite["version"]})
        assert r.status_code == 409 and "neu laden" in r.json["error"]                # veralteter Stand
        assert c1.put(f"/api/wiki/pages/{eigen['id']}", json={"content": "von a"}).status_code == 200  # ohne Stand

        # Freigaben nur an freigeschaltete Konten
        warte = app.test_client()
        warte.post("/api/auth/register", json={"email": "c@example.org", "password": "passwort1", "name": "C",
                                               "gliederung": "OG Test"})
        wid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "c@example.org"][0]["id"]
        r = c1.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid2, wid]})
        assert [e["id"] for e in r.json["editors"]] == [uid2]

        # --- Ersteller umschreiben: nur die Administration ------------------------------------
        # Gebraucht nach einem Import – dort trägt jede Seite den Namen dessen, der die Ausfuhr
        # eingespielt hat – und wenn jemand die Gliederung verlässt. Am Ersteller hängen Rechte,
        # also darf ihn niemand sonst verschieben, auch nicht der Ersteller selbst: Sonst schriebe
        # sich ein Nutzer eine fremde Seite zu oder gäbe seine eigene unbemerkt weiter.
        assert c1.put(f"/api/wiki/pages/{eigen['id']}/creator", json={"user_id": uid2}).status_code == 403
        assert c2.put(f"/api/wiki/pages/{eigen['id']}/creator", json={"user_id": uid2}).status_code == 403
        # Ein noch nicht freigeschaltetes Konto erbt keine Seite, und ohne Angabe passiert nichts.
        assert adm.put(f"/api/wiki/pages/{eigen['id']}/creator", json={"user_id": wid}).status_code == 400
        assert adm.put(f"/api/wiki/pages/{eigen['id']}/creator", json={}).status_code == 400
        r = adm.put(f"/api/wiki/pages/{eigen['id']}/creator", json={"user_id": uid2})
        assert r.status_code == 200, r.json
        assert r.json["page"]["created_by"] == uid2 and r.json["page"]["created_by_name"] == "b@e"
        # Der neue Ersteller steht nicht zusätzlich als Bearbeiter da – dort stünde er doppelt.
        assert [e["id"] for e in r.json["page"]["editors"]] == []
        # Mit dem Namen gehen die Rechte über: Freigeben darf jetzt b, nicht mehr a.
        assert c1.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid1]}).status_code == 403
        assert c2.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid1]}).status_code == 200
        # und zurück, damit die Seite den folgenden Prüfungen wieder a gehört
        assert adm.put(f"/api/wiki/pages/{eigen['id']}/creator",
                       json={"user_id": uid1}).json["page"]["created_by"] == uid1
        c1.put(f"/api/wiki/pages/{eigen['id']}/editors", json={"user_ids": [uid2]})

        # --- Synchronisierte Abschnitte: der Einbau zählt als Verweis ------------------------
        # Wer einen Baustein ändert, ändert ihn auf allen Seiten mit, die ihn einbinden. Über
        # die Rückverweise der Quellseite sieht man, wen das betrifft – vor dem Ändern.
        q = c1.post("/api/wiki/pages", json={"title": "Bausteinquelle", "format": "markdown",
                                             "content": ":::baustein sicherung\nText\n:::"}).json["page"]
        c1.post("/api/wiki/pages", json={"title": "Bausteinnutzer", "format": "markdown",
                                         "content": ":::einbau bausteinquelle#sicherung\n:::"})
        rueck = c1.get(f"/api/wiki/pages/{q['id']}/backlinks").json["pages"]
        assert [x["title"] for x in rueck] == ["Bausteinnutzer"], rueck

        # --- Seiten sind immer Markdown ------------------------------------------------------
        # Früher gab es daneben das Format "html" (aus Docmost übernommene Seiten), und wer nur
        # den Inhalt schickte, machte aus einer Markdown-Seite eine HTML-Seite: Der Artikel stand
        # danach als roher Text mit Strichen und Sternchen da. Jetzt gibt es nur noch Markdown –
        # auch eine ausdrückliche Angabe ändert daran nichts.
        fmt = c1.post("/api/wiki/pages", json={"title": "Formatprobe", "content": "# Hallo"}).json["page"]
        assert fmt["format"] == "markdown"
        nach = c1.put(f"/api/wiki/pages/{fmt['id']}", json={"content": "# Hallo Welt"}).json["page"]
        assert nach["format"] == "markdown"
        assert c1.put(f"/api/wiki/pages/{fmt['id']}",
                      json={"content": "<p>x</p>", "format": "html"}).json["page"]["format"] == "markdown"

        # --- Leerer Inhalt löscht keinen Artikel ---------------------------------------------
        # Ein Strg+Z direkt nach dem Öffnen leerte den Editor, und das automatische Speichern
        # schrieb die Leere zur Seite. Der Editor hält das inzwischen auf; der Server nimmt sie
        # zusätzlich nicht mehr stillschweigend an.
        nl = c1.post("/api/wiki/pages", json={"title": "Nicht leeren", "format": "markdown",
                                              "content": "# Nicht leeren\n\nText"}).json["page"]
        r = c1.put(f"/api/wiki/pages/{nl['id']}", json={"content": "", "format": "markdown"})
        assert r.status_code == 400 and "leer" in r.json["error"], (r.status_code, r.json)
        assert c1.get(f"/api/wiki/pages/{nl['slug']}").json["page"]["content"].endswith("Text")
        # Leerraum ist genauso leer
        assert c1.put(f"/api/wiki/pages/{nl['id']}", json={"content": "  \n\n"}).status_code == 400
        # Absichtlich leeren bleibt möglich: die Überschrift allein genügt dafür …
        assert c1.put(f"/api/wiki/pages/{nl['id']}",
                      json={"content": "# Nicht leeren\n", "format": "markdown"}).status_code == 200
        # … und wer wirklich alles löschen will, sagt es ausdrücklich.
        r = c1.put(f"/api/wiki/pages/{nl['id']}",
                   json={"content": "", "format": "markdown", "leeren": True})
        assert r.status_code == 200 and r.json["page"]["content"] == ""
        # Auf einer schon leeren Seite steht die Sperre nicht im Weg.
        assert c1.put(f"/api/wiki/pages/{nl['id']}", json={"content": ""}).status_code == 200
        # Ein leerer Stand aus dem Verlauf bleibt trotzdem wiederherstellbar.
        fid = c1.get(f"/api/wiki/pages/{nl['id']}/revisions").json["revisions"][0]["id"]
        assert c1.post(f"/api/wiki/revisions/{fid}/restore", json={}).status_code == 200

        # --- Verlauf wird gekappt ------------------------------------------------------------
        for i in range(5):
            c1.put(f"/api/wiki/pages/{eigen['id']}", json={"content": f"Fassung {i}"})
        assert len(c1.get(f"/api/wiki/pages/{eigen['id']}/revisions").json["revisions"]) == 3

        # --- Rolle „Redakteur" ---------------------------------------------------------------
        # Darf alle Inhalte bearbeiten, aber keine Nutzer verwalten und nichts veröffentlichen.
        red, red_id = member("redakteur@example.org")
        assert adm.put(f"/api/admin/users/{red_id}", json={"role": "editor"}).status_code == 200
        assert [u["role"] for u in adm.get("/api/admin/users").json["users"]
                if u["email"] == "redakteur@example.org"] == ["editor"]
        rseite = c1.post("/api/wiki/pages", json={"title": "Fremde Seite", "format": "markdown",
                                                  "content": "# Fremde Seite\n\nText"}).json["page"]
        c1.put(f"/api/wiki/pages/{rseite['id']}/restrict", json={"read_restricted": True})
        assert red.get(f"/api/wiki/pages/{rseite['slug']}").status_code == 200      # lesen
        assert red.put(f"/api/wiki/pages/{rseite['id']}",
                       json={"content": "# Fremde Seite\n\nVom Redakteur"}).status_code == 200
        assert red.delete(f"/api/wiki/pages/{rseite['id']}", headers=H).status_code == 200
        red.post(f"/api/wiki/pages/{rseite['id']}/restore", json={}, headers=H)
        assert red.get("/api/admin/users").status_code == 403                        # keine Nutzer
        assert red.put(f"/api/admin/users/{red_id}", json={"role": "admin"}, headers=H).status_code == 403
        assert red.put(f"/api/wiki/pages/{rseite['id']}/share",
                       json={"is_public": True}, headers=H).status_code == 403       # kein Veröffentlichen
        # Eine unbekannte Rollenbezeichnung darf keine Rechte verteilen.
        adm.put(f"/api/admin/users/{red_id}", json={"role": "superchef"})
        assert [u["role"] for u in adm.get("/api/admin/users").json["users"]
                if u["email"] == "redakteur@example.org"] == ["user"]
        assert red.get(f"/api/wiki/pages/{rseite['slug']}").status_code == 403
        c1.delete(f"/api/wiki/pages/{rseite['id']}", headers=H)

        # --- Nur einer bearbeitet: Anwesenheit und Schreibplatz -------------------------------
        # Der Editor speichert selbstständig; zwei gleichzeitig hieße, dass einer seine Arbeit
        # verliert. Also bekommt genau ein Reiter das Schreibrecht, und die anderen erfahren,
        # wer es hat.
        gem = c1.post("/api/wiki/pages", json={"title": "Gemeinsam", "format": "markdown",
                                               "content": "# Gemeinsam\n\nText"}).json["page"]
        c1.put(f"/api/wiki/pages/{gem['id']}/editors", json={"user_ids": [uid2]})

        def puls(klient, reiter, modus, **rest):
            return klient.post("/api/wiki/praesenz", headers=H,
                               json={"reiter": reiter, "page_id": gem["id"], "modus": modus, **rest})

        assert puls(c1, "reiter-eins-aaa", "schreiben").json["modus"] == "schreiben"
        zweit = puls(c2, "reiter-zwei-bbb", "schreiben").json
        assert zweit["modus"] == "lesen" and zweit["schreiber"]["name"] == "a@e", zweit
        # Der Platz bleibt beim Ersten, solange er sich meldet.
        assert puls(c1, "reiter-eins-aaa", "schreiben").json["modus"] == "schreiben"
        assert puls(c2, "reiter-zwei-bbb", "schreiben").json["modus"] == "lesen"
        # Entreißen lässt sich der Platz nicht – auch nicht, wer danach fragt. Ohne diese Zusage
        # könnte ein zweiter Reiter dem Ersten mitten im Satz das Speichern abstellen.
        assert puls(c2, "reiter-zwei-bbb", "schreiben", uebernehmen=True).json["modus"] == "lesen"
        assert puls(c1, "reiter-eins-aaa", "schreiben").json["modus"] == "schreiben"
        # Wer geht, gibt den Platz frei.
        c2.post("/api/wiki/praesenz", headers=H, json={"reiter": "reiter-zwei-bbb", "weg": True})
        assert puls(c1, "reiter-eins-aaa", "schreiben").json["modus"] == "schreiben"
        # Ohne Bearbeitungsrecht gibt es nur Lesen, ohne Leserecht gar nichts.
        fremd_c, _ = member("fremd@example.org")
        assert puls(fremd_c, "reiter-drei-ccc", "schreiben").json["modus"] == "lesen"
        c1.put(f"/api/wiki/pages/{gem['id']}/restrict", json={"read_restricted": True})
        assert puls(fremd_c, "reiter-drei-ccc", "lesen").status_code == 403
        c1.put(f"/api/wiki/pages/{gem['id']}/restrict", json={"read_restricted": False})
        # Eine unbrauchbare Reiterkennung wird abgewiesen.
        assert puls(c1, "kurz", "lesen").status_code == 400
        c1.delete(f"/api/wiki/pages/{gem['id']}", headers=H)

        # --- Gleichzeitiges Speichern: nur einer kommt durch ----------------------------------
        # Die Fassung wird im UPDATE selbst geprüft. Ohne das kamen zwei Speichervorgänge mit
        # derselben base_version beide durch und der erste wurde still überschrieben.
        wett = c1.post("/api/wiki/pages", json={"title": "Wettlauf", "format": "markdown",
                                                "content": "# Wettlauf\n\nStart"}).json["page"]
        beide = 0
        for runde in range(8):
            stand = c1.get("/api/wiki/pages/wettlauf").json["page"]["version"]
            tor, ergebnis = threading.Barrier(2), {}

            def schreibt(name, klient=None):
                eigen = app.test_client()
                eigen.post("/api/auth/login", json={"email": "a@example.org", "password": "passwort1"})
                tor.wait()
                ergebnis[name] = eigen.put(f"/api/wiki/pages/{wett['id']}", json={
                    "content": f"# Wettlauf\n\n{name}{runde}", "format": "markdown",
                    "base_version": stand, "sitzung": f"{name}{runde:010d}"}).status_code

            faeden = [threading.Thread(target=schreibt, args=(n,)) for n in ("A", "B")]
            for f in faeden:
                f.start()
            for f in faeden:
                f.join()
            if ergebnis.get("A") == 200 and ergebnis.get("B") == 200:
                beide += 1
        assert beide == 0, f"{beide} von 8 Runden nahmen beide Speichervorgänge an"
        # Die Absage nennt den aktuellen Stand, damit der Editor ihn zeigen kann.
        alt_stand = c1.get("/api/wiki/pages/wettlauf").json["page"]["version"] - 1
        absage = c1.put(f"/api/wiki/pages/{wett['id']}", json={"content": "# Wettlauf\n\nspät",
                                                              "format": "markdown", "base_version": alt_stand})
        assert absage.status_code == 409 and absage.json["page"]["version"] > alt_stand, absage.json
        c1.delete(f"/api/wiki/pages/{wett['id']}", headers=H)

        # --- Eine Fassung je Bearbeitung, nicht je Zeitfenster --------------------------------
        app.config.update(MAX_REVISIONS=20)          # der Deckel ist eben geprüft, jetzt stört er
        sp = c1.post("/api/wiki/pages", json={"title": "Sitzungsprobe", "format": "markdown",
                                              "content": "# Sitzungsprobe\n\nStart"}).json["page"]

        def fassungen():
            return c1.get(f"/api/wiki/pages/{sp['id']}/revisions").json["revisions"]

        def stand(fid):
            return c1.get(f"/api/wiki/revisions/{fid}").json["revision"]["content"]

        assert len(fassungen()) == 1                                  # das Anlegen
        # Zwei Zwischenstände derselben Bearbeitung schreiben dieselbe Fassung fort.
        for text in ("A1", "A2"):
            c1.put(f"/api/wiki/pages/{sp['id']}",
                   json={"content": f"# Sitzungsprobe\n\n{text}", "sitzung": "a1a1a1a1a1a1"})
        assert len(fassungen()) == 2
        assert stand(fassungen()[0]["id"]).endswith("A2")
        # Die nächste Bearbeitung kommt unmittelbar danach – und bekommt trotzdem eine eigene
        # Fassung. Der Stand vor ihr bleibt damit abrufbar; genau das konnte die Zeitregel nicht.
        c1.put(f"/api/wiki/pages/{sp['id']}",
               json={"content": "# Sitzungsprobe\n\nB1", "sitzung": "b2b2b2b2b2b2"})
        staende = [stand(f["id"]) for f in fassungen()]
        assert len(staende) == 3 and staende[0].endswith("B1") and staende[1].endswith("A2"), staende
        # Ohne brauchbares Kennzeichen entsteht immer eine eigene Fassung.
        c1.put(f"/api/wiki/pages/{sp['id']}", json={"content": "# Sitzungsprobe\n\nC1"})
        c1.put(f"/api/wiki/pages/{sp['id']}", json={"content": "# Sitzungsprobe\n\nC2", "sitzung": "kurz"})
        c1.put(f"/api/wiki/pages/{sp['id']}", json={"content": "# Sitzungsprobe\n\nC3", "sitzung": {"x": 1}})
        assert len(fassungen()) == 6
        # Das Kennzeichen bleibt Innenleben: es steht in keiner Antwort.
        assert "sitzung" not in c1.get(f"/api/wiki/revisions/{fassungen()[0]['id']}").json["revision"]
        assert all("sitzung" not in f for f in fassungen())
        # Ein fremdes Kennzeichen schreibt keine fremde Fassung fort: die letzte Fassung
        # gehört c1, also legt c2 trotz gleichem Kennzeichen eine eigene an.
        c1.put(f"/api/wiki/pages/{sp['id']}/editors", json={"user_ids": [uid2]})
        c2.put(f"/api/wiki/pages/{sp['id']}",
               json={"content": "# Sitzungsprobe\n\nD1", "sitzung": "c3c3c3c3c3c3"})
        c2.put(f"/api/wiki/pages/{sp['id']}",
               json={"content": "# Sitzungsprobe\n\nD2", "sitzung": "c3c3c3c3c3c3"})
        c1.put(f"/api/wiki/pages/{sp['id']}",
               json={"content": "# Sitzungsprobe\n\nE1", "sitzung": "c3c3c3c3c3c3"})
        staende = [stand(f["id"]) for f in fassungen()]
        assert len(staende) == 8, staende                     # 6 + eine je Person
        assert staende[0].endswith("E1") and staende[1].endswith("D2"), staende

        # --- Ein Speichervorgang, der die falsche Seite trifft ---------------------------------
        # Im Browser konnte ein nachgeholter Speicherlauf den Text der gerade geöffneten Seite
        # unter der Kennung der zuvor bearbeiteten ablegen (siehe jetztSichern in wiki.js und
        # tests/nachgeholtes_speichern.html). Der Server kann das nicht erkennen: die Anfrage
        # trägt den passenden Stand und dieselbe Person, sie sieht aus wie jede andere. Er muss
        # den Schaden aber eingrenzen – und genau das wird hier festgehalten.
        rs = c1.post("/api/wiki/pages", json={"title": "Seite R", "format": "markdown",
                                              "content": "# Seite R\n\nInhalt von R."}).json["page"]
        qs = c1.post("/api/wiki/pages", json={"title": "Seite Q", "format": "markdown",
                                              "content": "# Seite Q\n\nInhalt von Q."}).json["page"]
        assert rs["slug"] == "seite-r" and qs["slug"] == "seite-q"
        # Eine gewöhnliche Bearbeitung von R, mit Kennzeichen wie jede andere.
        rs = c1.put(f"/api/wiki/pages/{rs['id']}",
                    json={"title": "Seite R", "content": "# Seite R\n\nInhalt von R. Nachtrag.",
                          "format": "markdown", "base_version": rs["version"],
                          "sitzung": "r1r1r1r1r1r1"}).json["page"]
        # Und nun der Fehlschuss: derselbe Vorgang schickt den Text von Q an die Kennung von R.
        r = c1.put(f"/api/wiki/pages/{rs['id']}",
                   json={"title": "Seite Q", "content": "# Seite Q\n\nInhalt von Q.",
                         "format": "markdown", "base_version": rs["version"],
                         "sitzung": "r1r1r1r1r1r1"})
        assert r.status_code == 200, r.json
        # Die Adresse von Q ist vergeben: R bekommt eine eigene Nummer, Q behält die seine.
        # Q selbst bleibt unangetastet – der Unfall bleibt auf eine Seite beschränkt.
        assert r.json["page"]["slug"] == "seite-q-2", r.json["page"]
        q_jetzt = c1.get("/api/wiki/pages/seite-q").json["page"]
        assert q_jetzt["id"] == qs["id"] and q_jetzt["title"] == "Seite Q"
        assert q_jetzt["content"].endswith("Inhalt von Q.")
        # Die bisherige Adresse von R trägt weiter: ein Verweis darauf läuft nicht ins Leere.
        assert c1.get("/api/wiki/pages/seite-r").json["page"]["id"] == rs["id"]
        # Die Zwischenstände derselben Bearbeitung haben einander überschrieben – der in R
        # getippte Nachtrag ist damit fort. Die Fassung von VOR der Bearbeitung steht aber noch,
        # mit Titel und Text; nur deshalb war der Unfall überhaupt zurückzunehmen.
        verlauf = c1.get(f"/api/wiki/pages/{rs['id']}/revisions").json["revisions"]
        assert len(verlauf) == 2, verlauf
        assert not any("Nachtrag" in stand(f["id"]) for f in verlauf), "Zwischenstand überlebt nicht"
        anlage = c1.get(f"/api/wiki/revisions/{verlauf[-1]['id']}").json["revision"]
        assert anlage["title"] == "Seite R" and anlage["content"].endswith("Inhalt von R."), anlage
        # Zurückholen stellt Titel und Text wieder her. Die Adresse bleibt die vergebene – ein
        # Zurückrollen benennt nicht um. Beide Adressen führen danach auf dieselbe Seite, es geht
        # also kein Verweis verloren.
        assert c1.post(f"/api/wiki/revisions/{verlauf[-1]['id']}/restore", json={}).status_code == 200
        zurueck = c1.get("/api/wiki/pages/seite-r").json["page"]
        assert zurueck["title"] == "Seite R" and zurueck["content"].endswith("Inhalt von R."), zurueck
        assert c1.get("/api/wiki/pages/seite-r").json["page"]["id"] == rs["id"]
        assert c1.get(f"/api/wiki/pages/{zurueck['slug']}").json["page"]["id"] == rs["id"]

        # --- Post an Beobachter: je Bearbeitung eine, nicht je Fassung ------------------------
        # Ohne SMTP schreibt der Versand die Mail ins Log – von dort wird hier mitgelesen.
        class Mitlesen(logging.Handler):
            def __init__(self):
                super().__init__()
                self.zeilen = []

            def emit(self, record):
                self.zeilen.append(record.getMessage())

        beob = c2.post("/api/wiki/pages", json={"title": "Beobachtet", "format": "markdown",
                                                "content": "# Beobachtet\n\nStart"}).json["page"]
        c2.put(f"/api/wiki/pages/{beob['id']}/editors", json={"user_ids": [uid1]})
        c2.put(f"/api/wiki/pages/{beob['id']}/watch", json={"watch": True})
        mit = Mitlesen()
        app.logger.addHandler(mit)
        try:
            # Zwei Bearbeitungen dicht hintereinander: zwei Fassungen, aber nur eine Nachricht.
            for text, kennung in (("F1", "f6f6f6f6f6f6"), ("G1", "a7a7a7a7a7a7")):
                c1.put(f"/api/wiki/pages/{beob['id']}",
                       json={"content": f"# Beobachtet\n\n{text}", "sitzung": kennung})
        finally:
            app.logger.removeHandler(mit)
        post = [z for z in mit.zeilen if "wurde geändert" in z]
        assert len(c1.get(f"/api/wiki/pages/{beob['id']}/revisions").json["revisions"]) == 3, "zwei Fassungen"
        assert len(post) == 1, post

        # Übergang: ein Browser von vor der Umstellung schickt "still" statt eines Kennzeichens.
        # Seine Zwischenstände dürfen den Verlauf nicht fluten (sonst räumt MAX_REVISIONS ihn leer).
        # Für ihn gilt wieder die alte Regel: dieselbe Person, kurz hintereinander, dieselbe
        # Fassung – drei Zwischenstände dürfen also keine drei Fassungen werden. Die Fassung
        # der letzten richtigen Bearbeitung (E1, mit Kennzeichen) rührt er dabei nicht an.
        vor_alt = len(fassungen())
        for text in ("Alt1", "Alt2", "Alt3"):
            c1.put(f"/api/wiki/pages/{sp['id']}", json={"content": f"# Sitzungsprobe\n\n{text}",
                                                        "still": True})
        assert len(fassungen()) == vor_alt + 1, fassungen()
        assert stand(fassungen()[0]["id"]).endswith("Alt3")
        assert stand(fassungen()[1]["id"]).endswith("E1"), "Fassung mit Kennzeichen blieb stehen"

        # Die Gegenrichtungen brauchen Abstand. Statt zu warten wird die letzte Fassung
        # zurückdatiert – die Ruhezeit der Post und die Zeitunabhängigkeit des Verlaufs lassen
        # sich sonst in einem Testlauf gar nicht auseinanderhalten.
        def zurueckdatieren(pid, minuten):
            # Mit Python rechnen, nicht mit SQLites datetime(): das schriebe den Zeitstempel ohne
            # Zeitzone zurück, und _sekunden_her lieferte dann "unendlich lange her" – der Test
            # wäre grün, ohne die Ruhezeit je berührt zu haben.
            konn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
            rid, alt = konn.execute("SELECT id, created_at FROM wiki_revisions WHERE page_id = ? "
                                    "ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
            frueher = (datetime.fromisoformat(alt) - timedelta(minutes=minuten)).isoformat()
            konn.execute("UPDATE wiki_revisions SET created_at = ? WHERE id = ?", (frueher, rid))
            konn.commit()
            konn.close()

        # (1) Nach der Ruhezeit geht wieder Post raus – sonst bliebe es für immer still.
        zurueckdatieren(beob["id"], 20)
        mit2 = Mitlesen()
        app.logger.addHandler(mit2)
        try:
            c1.put(f"/api/wiki/pages/{beob['id']}",
                   json={"content": "# Beobachtet\n\nH1", "sitzung": "b8b8b8b8b8b8"})
        finally:
            app.logger.removeHandler(mit2)
        assert len([z for z in mit2.zeilen if "wurde geändert" in z]) == 1, mit2.zeilen

        # (2) Dasselbe Kennzeichen schreibt dieselbe Fassung fort – auch nach langer Pause.
        # Genau hier hing früher die Zehn-Minuten-Regel; fiele sie zurück, entstünde eine zweite.
        vorher = len(c1.get(f"/api/wiki/pages/{beob['id']}/revisions").json["revisions"])
        zurueckdatieren(beob["id"], 30)
        c1.put(f"/api/wiki/pages/{beob['id']}",
               json={"content": "# Beobachtet\n\nH2", "sitzung": "b8b8b8b8b8b8"})
        fass = c1.get(f"/api/wiki/pages/{beob['id']}/revisions").json["revisions"]
        assert len(fass) == vorher, fass
        assert c1.get(f"/api/wiki/revisions/{fass[0]['id']}").json["revision"]["content"].endswith("H2")
        app.config.update(MAX_REVISIONS=3)

        # --- Anmeldebremse -------------------------------------------------------------------
        angriff = app.test_client()
        codes = [angriff.post("/api/auth/login", json={"email": "a@example.org", "password": "falsch"}).status_code
                 for _ in range(12)]
        assert codes[0] == 401 and codes[-1] == 429, codes
        assert angriff.post("/api/auth/login",
                            json={"email": "a@example.org", "password": "passwort1"}).status_code == 429

        # --- Kontoanfrage verrät vorhandene Adressen nicht -----------------------------------
        neu = app.test_client()
        r1 = neu.post("/api/auth/register", json={"email": "neu@example.org", "password": "passwort1",
                                                  "name": "N", "gliederung": "OG"})
        r2 = neu.post("/api/auth/register", json={"email": "a@example.org", "password": "passwort1",
                                                  "name": "N", "gliederung": "OG"})
        assert (r1.status_code, r1.json) == (r2.status_code, r2.json), (r1.json, r2.json)

        # --- Reset: Link im Fragment, gesperrte Konten abgewiesen, Versandmeldung stimmt -----
        from app import auth as auth_mod
        from app import db as db_mod
        with app.app_context():
            gesperrt = db_mod.query("SELECT * FROM users WHERE email = 'c@example.org'", one=True)
            token_gesperrt = auth_mod.make_reset_token(gesperrt)
            mails = []
            echt, auth_mod.send_mail = auth_mod.send_mail, lambda to, s, b: mails.append((to, b)) or True
            try:
                auth_mod.send_reset_mail(db_mod.query("SELECT * FROM users WHERE email = 'a@example.org'", one=True))
            finally:
                auth_mod.send_mail = echt
        assert "/reset#token=" in mails[0][1] and "?token=" not in mails[0][1]
        assert app.test_client().post("/api/auth/reset",
                                      json={"token": token_gesperrt, "password": "neuespw12"}).status_code == 403
        # Mit funktionierendem Versand meldet der Admin-Endpunkt auch „verschickt“
        echt, auth_mod.send_mail = auth_mod.send_mail, lambda to, s, b: True
        try:
            assert adm.post(f"/api/admin/users/{uid1}/reset-mail", json={}).json["sent"] is True
        finally:
            auth_mod.send_mail = echt
        assert adm.post(f"/api/admin/users/{uid1}/reset-mail", json={}).json["sent"] is False   # ohne SMTP

        # --- Medien: Zwischenspeicher und CSP ------------------------------------------------
        aid = c1.post("/api/albums", json={"title": "A", "category": "seil"}).json["album"]["id"]
        r = c1.post(f"/api/albums/{aid}/photos", data={"files": [(jpeg(True), "m.jpg")], "posters": [(io.BytesIO(b""), "")]},
                    headers=H, content_type="multipart/form-data")
        foto = r.json["photos"][0]
        cc = c1.get(foto["thumb"]).headers["Cache-Control"]
        assert "private" in cc and "public" not in cc, cc
        assert "default-src 'none'" in c1.get(foto["thumb"]).headers["Content-Security-Policy"]
        # Ein Anhang einer öffentlichen Seite darf gemeinsam zwischengespeichert werden
        up = c1.post("/api/wiki/files", data={"file": (jpeg(False), "s.jpg")}, headers=H,
                     content_type="multipart/form-data").json["url"]
        adm.put(f"/api/wiki/pages/{pub['id']}", json={"content": f"# Freigegeben\n\n![s]({up})", "format": "markdown"})
        assert "public" in anon_get(app, up).headers["Cache-Control"]
        assert anon_get(app, up).status_code == 200

        # --- Album-Besitzer darf Bilder im eigenen Album ändern ------------------------------
        r = adm.post(f"/api/albums/{aid}/photos", data={"files": [(jpeg(False), "vomadmin.jpg")],
                                                        "posters": [(io.BytesIO(b""), "")]},
                     headers=H, content_type="multipart/form-data")
        fremd = r.json["photos"][0]
        assert fremd["owner_id"] != uid1
        assert c1.put(f"/api/photos/{fremd['id']}", json={"title": "vom Albumbesitzer"}).status_code == 200
        assert c2.put(f"/api/photos/{fremd['id']}", json={"title": "von fremd"}).status_code == 403

        # --- Wer an einer Seite geschrieben hat ----------------------------------------------
        mit = adm.post("/api/wiki/pages", json={"title": "Gemeinsam", "content": "# Gemeinsam\n\nEins"}).json["page"]
        adm.put(f"/api/wiki/pages/{mit['id']}/editors", json={"user_ids": [uid1]})
        c1.put(f"/api/wiki/pages/{mit['id']}", json={"content": "# Gemeinsam\n\nZwei", "format": "markdown"})
        r = adm.get(f"/api/wiki/pages/{mit['id']}/contributors").json
        assert r["owner"]["name"] == "Administrator", r
        assert [x["name"] for x in r["contributors"]] == ["a@e"], r      # der Ersteller steht nicht doppelt
        assert c2.get(f"/api/wiki/pages/{mit['id']}/contributors").status_code == 200

        # --- Lesebeschränkung hält gegen Freigabe, Kopie, Verlauf und Papierkorb ------------
        gh = c1.post("/api/wiki/pages", json={"title": "Vertraulich", "content": "# Vertraulich\n\nGEHEIM"}).json["page"]
        assert c1.put(f"/api/wiki/pages/{gh['id']}/restrict", json={"read_restricted": True}).status_code == 200
        assert c2.get(f"/api/wiki/pages/{gh['slug']}").status_code == 403
        # Kopieren gab den Inhalt früher ohne Leserecht heraus.
        assert c2.post(f"/api/wiki/pages/{gh['id']}/duplicate", json={}).status_code == 403
        # Auch der Verlauf – und zwar ebenso, wenn die Seite im Papierkorb liegt.
        assert c2.get(f"/api/wiki/pages/{gh['id']}/revisions").status_code == 403
        rid = c1.get(f"/api/wiki/pages/{gh['id']}/revisions").json["revisions"][0]["id"]
        assert c2.get(f"/api/wiki/revisions/{rid}").status_code == 403
        assert c1.delete(f"/api/wiki/pages/{gh['id']}", headers=H).status_code == 200
        assert c2.get(f"/api/wiki/pages/{gh['id']}/revisions").status_code == 403
        assert c2.get(f"/api/wiki/revisions/{rid}").status_code == 403
        # Zurückrollen ebenso: für Fremde eine Abweisung (früher ein Absturz über die fehlende
        # Seite), und selbst der Administrator schreibt keine Fassung in den Papierkorb hinein.
        assert c2.post(f"/api/wiki/revisions/{rid}/restore", json={}).status_code == 403
        r = adm.post(f"/api/wiki/revisions/{rid}/restore", json={})
        assert r.status_code == 409 and "Papierkorb" in r.json["error"], (r.status_code, r.json)
        assert adm.post(f"/api/wiki/pages/{gh['id']}/restore", json={}).status_code == 200
        # In der Reihenfolge geht es dann: erst die Seite zurückholen, dann die Fassung.
        assert c1.post(f"/api/wiki/revisions/{rid}/restore", json={}).status_code == 200
        assert c2.post(f"/api/wiki/revisions/{rid}/restore", json={}).status_code == 403
        # Kommentare: ohne Leserecht weder lesen noch schreiben. Der Anker eines Kommentars ist
        # ein Stück Seitentext – eine Antwort erbt ihn, und die Kennungen sind durchzählbar.
        adm.put(f"/api/wiki/pages/{gh['id']}/watch", json={"watch": True})
        mitk = Mitlesen()
        app.logger.addHandler(mitk)
        try:
            r = c1.post(f"/api/wiki/pages/{gh['id']}/comments",
                        json={"body": "Stimmt die Zahl?", "quote": "GEHEIM",
                              "quote_before": "Vertraulich ", "quote_after": " – bitte prüfen"})
            assert r.status_code == 201, r.json
            kid = r.json["comment"]["id"]
            assert len([z for z in mitk.zeilen if "neuen Kommentar" in z]) == 1, mitk.zeilen
            assert c2.get(f"/api/wiki/pages/{gh['id']}/comments").status_code == 403
            r = c2.post(f"/api/wiki/pages/{gh['id']}/comments", json={"body": "Hallo?"})
            assert r.status_code == 403, (r.status_code, r.json)
            r = c2.post(f"/api/wiki/pages/{gh['id']}/comments", json={"body": "Hallo?", "parent_id": kid})
            assert r.status_code == 403, (r.status_code, r.json)
            assert "GEHEIM" not in r.get_data(as_text=True), r.json          # auch kein geerbter Anker
            # Ändern, Erledigen und Löschen ebenso wenig
            assert c2.put(f"/api/wiki/comments/{kid}", json={"resolved": True}).status_code == 403
            assert c2.put(f"/api/wiki/comments/{kid}", json={"body": "umgeschrieben"}).status_code == 403
            assert c2.delete(f"/api/wiki/comments/{kid}", headers=H).status_code == 403
        finally:
            app.logger.removeHandler(mitk)
        # Post gab es nur für den einen erlaubten Kommentar – die abgewiesenen lösen keine aus.
        assert len([z for z in mitk.zeilen if "neuen Kommentar" in z]) == 1, mitk.zeilen
        strang = c1.get(f"/api/wiki/pages/{gh['id']}/comments").json["comments"]
        assert [x["body"] for x in strang] == ["Stimmt die Zahl?"], strang
        assert strang[0]["resolved"] == 0, strang
        # Und auch im Papierkorb hängen die Rechte an der Seite: dort lief die Prüfung früher
        # ins Leere, weil _get_page gelöschte Seiten ausblendet.
        assert c1.delete(f"/api/wiki/pages/{gh['id']}", headers=H).status_code == 200
        assert c2.put(f"/api/wiki/comments/{kid}", json={"resolved": True}).status_code == 403
        assert c2.delete(f"/api/wiki/comments/{kid}", headers=H).status_code == 403
        assert adm.post(f"/api/wiki/pages/{gh['id']}/restore", json={}).status_code == 200
        adm.put(f"/api/wiki/pages/{gh['id']}/watch", json={"watch": False})
        # Ein Abschnitt mit beschränkter Unterseite lässt sich nicht mitsamt Unterseiten freigeben.
        dach = adm.post("/api/wiki/pages", json={"title": "Dach", "content": "# Dach"}).json["page"]
        adm.put(f"/api/wiki/pages/{gh['id']}", json={"parent_id": dach["id"]})
        r = adm.put(f"/api/wiki/pages/{dach['id']}/share", json={"is_public": True, "public_children": True})
        assert r.status_code == 400 and "lesebeschränkte" in r.json["error"], r.json
        # Und selbst wenn sie es doch würde: öffentlich ausgeliefert wird sie nicht.
        adm.put(f"/api/wiki/pages/{dach['id']}/share", json={"is_public": True, "public_children": False})
        db_ = app.test_client()
        with app.app_context():
            from app import db as _db
            _db.execute("UPDATE wiki_pages SET public_children = 1 WHERE id = ?", (dach["id"],))
        assert db_.get(f"/api/public/pages/{gh['slug']}").status_code == 404

        # --- Papierkorb: was gemeinsam gelöscht wurde, kommt gemeinsam zurück ----------------
        # Eine Unterseite, die schon vorher einzeln im Papierkorb lag, darf beim Wiederherstellen
        # des Elternteils nicht ungefragt mitkommen. Der Zeitstempel taugt dafür nicht – db.now()
        # zählt in ganzen Sekunden, zwei Löschvorgänge kurz hintereinander tragen denselben.
        pe = c1.post("/api/wiki/pages", json={"title": "Papierkorb-Eltern", "content": "x"}).json["page"]
        pk1 = c1.post("/api/wiki/pages", json={"title": "Zuerst weg", "parent_id": pe["id"], "content": "x"}).json["page"]
        c1.post("/api/wiki/pages", json={"title": "Kommt mit", "parent_id": pe["id"], "content": "x"})
        c1.delete(f"/api/wiki/pages/{pk1['id']}", headers=H)
        r = c1.delete(f"/api/wiki/pages/{pe['id']}", headers=H)
        assert r.json["trashed"] == 2, r.json            # das zuerst gelöschte Kind zählt nicht mit
        r = c1.post(f"/api/wiki/pages/{pe['id']}/restore", headers=H)
        assert r.json["restored"] == 2, r.json
        titel = {p["title"] for p in c1.get("/api/wiki/tree").json["pages"]}
        assert "Kommt mit" in titel and "Zuerst weg" not in titel, titel
        assert "Zuerst weg" in {p["title"] for p in c1.get("/api/wiki/trash").json["pages"]}
        assert c1.post(f"/api/wiki/pages/{pk1['id']}/restore", headers=H).status_code == 200
        c1.delete(f"/api/wiki/pages/{pe['id']}", headers=H)

        # --- Umsortieren: zwei Seiten können sich nicht gegenseitig aufnehmen ----------------
        # Jede für sich besteht die Zyklusprüfung gegen den alten Stand; zusammen geschrieben
        # wären beide aus dem Baum verschwunden und nur noch über die Suche zu finden.
        za = c1.post("/api/wiki/pages", json={"title": "Zyklus A", "content": "x"}).json["page"]
        zb = c1.post("/api/wiki/pages", json={"title": "Zyklus B", "content": "x"}).json["page"]
        r = c1.put("/api/wiki/reorder", headers=H, json={"items": [
            {"id": za["id"], "parent_id": zb["id"], "position": 0},
            {"id": zb["id"], "parent_id": za["id"], "position": 0}]})
        assert r.status_code == 400, r.json
        wurzeln = [p["id"] for p in c1.get("/api/wiki/tree").json["pages"] if p["parent_id"] is None]
        assert za["id"] in wurzeln and zb["id"] in wurzeln

        # --- Lesebeschränkung und öffentliche Freigabe schließen einander aus ----------------
        # Sonst entstünde eine Seite, die Angemeldete nicht sehen dürfen und jeder im Netz lesen kann.
        bd = c1.post("/api/wiki/pages", json={"title": "Beschränkt-Dach", "content": "x"}).json["page"]
        bu = c1.post("/api/wiki/pages", json={"title": "Beschränkt-Unter", "parent_id": bd["id"], "content": "x"}).json["page"]
        assert adm.put(f"/api/wiki/pages/{bu['id']}/share", json={"is_public": True}).status_code == 200
        assert c1.put(f"/api/wiki/pages/{bd['id']}/restrict", json={"read_restricted": True}).status_code == 400
        adm.put(f"/api/wiki/pages/{bu['id']}/share", json={"is_public": False})
        assert c1.put(f"/api/wiki/pages/{bd['id']}/restrict", json={"read_restricted": True}).status_code == 200
        assert adm.put(f"/api/wiki/pages/{bu['id']}/share", json={"is_public": True}).status_code == 400
        # Und auf Fremdes, das man nicht lesen darf, gibt es keine Merkliste.
        assert c2.put(f"/api/wiki/pages/{bd['id']}/favorite", json={"favorite": True}, headers=H).status_code == 403
        c1.delete(f"/api/wiki/pages/{bd['id']}", headers=H)

        # --- Export: gleichnamige Geschwister überschreiben sich nicht im Archiv -------------
        dd = c1.post("/api/wiki/pages", json={"title": "Doppel", "content": "x"}).json["page"]
        c1.post("/api/wiki/pages", json={"title": "Foo", "parent_id": dd["id"], "content": "x"})
        c1.post("/api/wiki/pages", json={"title": "Foo.", "parent_id": dd["id"], "content": "x"})
        namen = zipfile.ZipFile(io.BytesIO(c1.get(f"/api/wiki/pages/{dd['id']}/export?children=1").data)).namelist()
        assert len(set(namen)) == len(namen) == 3, namen
        c1.delete(f"/api/wiki/pages/{dd['id']}", headers=H)

        # --- Bestandsvideos: alte Adresse führt zur gewandelten Datei ------------------------
        # Ohne ffmpeg wird hier nichts gewandelt; geprüft wird die Auslieferung: Liegt zu einem
        # .mov nur noch das .mp4, kommt es unter der alten Adresse – mit dem richtigen Typ.
        import os as _os
        wiki_dir = _os.path.join(app.config["MEDIA_DIR"], "wiki"); _os.makedirs(wiki_dir, exist_ok=True)
        with open(_os.path.join(wiki_dir, "alt.mp4"), "wb") as fh:
            fh.write(b"\x00" * 16)
        r = c1.get("/media/wiki/alt.mov")
        assert r.status_code == 200 and r.mimetype == "video/mp4", (r.status_code, r.mimetype)
        assert c1.get("/media/wiki/alt.webm").status_code == 200          # jede Videoendung führt hin
        assert c1.get("/media/wiki/alt.jpg").status_code == 404           # kein Bild wird umgeleitet
        assert c1.get("/media/wiki/fehlt.mov").status_code == 404
        assert anon_get(app, "/media/wiki/alt.mov").status_code in (302, 401)   # weiter nur angemeldet
        # Der Stand der Videopflege ist Verwaltungssache.
        assert c1.get("/api/admin/videos").status_code == 403
        st = adm.get("/api/admin/videos")
        assert st.status_code == 200 and {"laeuft", "geprueft", "gewandelt", "fehler", "fertig"} <= set(st.json)

        # --- Pegel: die Funktion ist ausgebaut, nichts davon darf mehr nach außen dringen -----
        with app.app_context():
            db_ = __import__("app.db", fromlist=["db"])
            assert not db_.query("SELECT 1 FROM sqlite_master WHERE name = 'pegel_stationen'", one=True)
            assert not [r["name"] for r in db_.query("PRAGMA table_info(photos)") if r["name"].startswith("pegel")]
        assert not [k for k in c1.get(f"/api/photos/{fremd['id']}").json["photo"] if k.startswith("pegel")]
        assert c1.post(f"/api/photos/{fremd['id']}/pegel", headers=H).status_code == 404

        # --- Aufnahmezeit eines Bildes muss ein Zeitpunkt sein -------------------------------
        r = c1.put(f"/api/photos/{fremd['id']}", json={"taken_at": "<img src=x onerror=alert(1)>"})
        assert r.status_code == 400, (r.status_code, r.json)
        assert c1.put(f"/api/photos/{fremd['id']}", json={"taken_at": "2024-05-01T10:00"}).status_code == 200

        # --- Profilbild: hochladen, ausliefern, ersetzen, entfernen -------------------------
        import os as _os2
        av_dir = _os2.path.join(app.config["MEDIA_DIR"], "avatar")
        r = c1.post("/api/me/avatar", data={"file": (jpeg(False), "ich.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.json
        adresse = r.json["user"]["avatar"]
        assert adresse.startswith("/media/avatar/") and adresse.endswith(".jpg"), adresse
        datei1 = adresse.rsplit("/", 1)[1]
        # Quadratisch auf Maß gebracht – ein 640x480-Bild kommt als 256x256 zurück.
        from app.images import AVATAR_SIZE
        with Image.open(_os2.path.join(av_dir, datei1)) as im:
            assert im.size == (AVATAR_SIZE, AVATAR_SIZE), im.size
        # Keine Aufnahmedaten im abgelegten Bild: Ein Profilbild darf nicht den Wohnort verraten.
        # jpeg(True) trägt GPS-Koordinaten und die Aufnahmezeit im EXIF.
        r2 = c1.post("/api/me/avatar", data={"file": (jpeg(True), "telefon.jpg")}, headers=H,
                     content_type="multipart/form-data")
        with Image.open(_os2.path.join(av_dir, r2.json["user"]["avatar"].rsplit("/", 1)[1])) as im:
            ex = im.getexif()
            assert len(ex) == 0 and len(ex.get_ifd(0x8825)) == 0, dict(ex)
        adresse = r2.json["user"]["avatar"]
        datei1 = adresse.rsplit("/", 1)[1]
        r = c1.get(adresse)
        assert r.status_code == 200 and r.mimetype == "image/jpeg", (r.status_code, r.mimetype)
        assert anon_get(app, adresse).status_code in (302, 401)        # nur für Angemeldete
        # Das Bild steht an der Autorenangabe der eigenen Seiten und in den Mitwirkenden.
        meins = c1.post("/api/wiki/pages", json={"title": "Mit Bild", "content": "x"}).json["page"]
        pj = c1.get(f"/api/wiki/pages/{meins['slug']}").json["page"]
        assert pj["created_by_avatar"] == adresse, pj.get("created_by_avatar")
        assert c1.get(f"/api/wiki/pages/{meins['id']}/contributors").json["owner"]["avatar"] == adresse
        # Ein zweites Bild ersetzt das erste, die alte Datei bleibt nicht liegen.
        r2 = c1.post("/api/me/avatar", data={"file": (jpeg(True), "neu.jpg")}, headers=H,
                     content_type="multipart/form-data")
        adresse2 = r2.json["user"]["avatar"]
        assert adresse2 != adresse and not _os2.path.exists(_os2.path.join(av_dir, datei1))
        # Zwei Reiter laden gleichzeitig hoch: Einer gewinnt, der andere räumt seine Datei weg.
        # Der Endpunkt schreibt dafür bedingt – geprüft wird hier, dass die Bedingung wirklich
        # trägt, also ein überholter Stand keine Zeile mehr trifft.
        with app.app_context():
            import app.db as _db
            jetzt = _db.query("SELECT avatar FROM users WHERE id = ?", (uid1,), one=True)["avatar"]
            assert _db.execute_zeilen("UPDATE users SET avatar = ? WHERE id = ? AND avatar = ?",
                                      ("neu.jpg", uid1, "ueberholt.jpg")) == 0
            assert _db.execute_zeilen("UPDATE users SET avatar = ? WHERE id = ? AND avatar = ?",
                                      (jetzt, uid1, jetzt)) == 1

        # Was kein Bild ist, wird abgewiesen – mit Grund, nicht mit einem Serverfehler.
        r = c1.post("/api/me/avatar", data={"file": (io.BytesIO(b"kein bild"), "x.txt")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 400 and "eignet sich nicht" in r.json["error"], r.json
        r = c1.post("/api/me/avatar", data={"file": (io.BytesIO(b"kein bild"), "x.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 400 and "nicht als Bild" in r.json["error"], r.json
        assert c1.post("/api/me/avatar", headers=H, content_type="multipart/form-data").status_code == 400
        assert c1.get("/api/me").json["user"]["avatar"] == adresse2    # keine der Abweisungen hat gelöscht
        # Entfernen: Datenbank und Datei.
        datei2 = adresse2.rsplit("/", 1)[1]
        assert c1.delete("/api/me/avatar", headers=H).json["user"]["avatar"] is None
        assert not _os2.path.exists(_os2.path.join(av_dir, datei2))
        assert c1.get(f"/api/wiki/pages/{meins['slug']}").json["page"]["created_by_avatar"] is None
        assert c1.delete("/api/me/avatar", headers=H).status_code == 200   # zweimal schadet nicht
        # Ein Dateiname aus der Datenbank darf nicht aus dem Verzeichnis hinausführen.
        from app.images import delete_avatar
        merk = _os2.path.join(tmp, "merk.txt")
        open(merk, "w").write("bleibt")
        delete_avatar(app.config["MEDIA_DIR"], "../../merk.txt")
        assert _os2.path.exists(merk)
        # Ein freigestelltes PNG bekommt weiß hinterlegt, nicht schwarz – JPEG kennt kein Alpha.
        durchsichtig = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        durchsichtig.paste((200, 30, 30, 255), (100, 100, 200, 200))
        buf = io.BytesIO(); durchsichtig.save(buf, "PNG"); buf.seek(0)
        r = c1.post("/api/me/avatar", data={"file": (buf, "frei.png")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.json
        with Image.open(_os2.path.join(av_dir, r.json["user"]["avatar"].rsplit("/", 1)[1])) as im:
            assert im.getpixel((3, 3)) == (255, 255, 255), im.getpixel((3, 3))
        c1.delete("/api/me/avatar", headers=H)
        assert app.test_client().post("/api/me/avatar", headers=H).status_code in (302, 401)
        # Zu große Datei: abgewiesen, bevor überhaupt etwas gepuffert wird (413 aus size_guard),
        # und – falls der Kopf die Länge verschweigt – spätestens in store_avatar (400).
        from app.images import AVATAR_MAX_BYTES, AVATAR_MAX_PIXEL, store_avatar
        r = c1.post("/api/me/avatar", data={"file": (io.BytesIO(b"\x00" * (AVATAR_MAX_BYTES + 1)), "riesig.jpg")},
                    headers=H, content_type="multipart/form-data")
        assert r.status_code == 413 and "zu groß" in r.json["error"], (r.status_code, r.json)
        assert f"{AVATAR_MAX_BYTES // (1024 * 1024)} MB" in r.json["error"], r.json   # die eigene Grenze
        class _FS:
            def __init__(self, b, n): self.stream, self.filename = b, n
        try:
            store_avatar(_FS(io.BytesIO(b"\x00" * (AVATAR_MAX_BYTES + 1)), "gross.jpg"), tmp)
            raise AssertionError("zu große Datei kam durch")
        except ValueError as e:
            assert "zu groß" in str(e), e
        # Ein Bild mit zu vielen Pixeln wird abgewiesen, bevor Pillow es entfaltet.
        gross = Image.new("RGB", (4200, 4200), (10, 10, 10))
        buf = io.BytesIO(); gross.save(buf, "PNG"); buf.seek(0)
        assert buf.getbuffer().nbytes < AVATAR_MAX_BYTES        # klein auf der Platte, riesig im Speicher
        r = c1.post("/api/me/avatar", data={"file": (buf, "flaeche.png")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 400 and "Megapixel" in r.json["error"], r.json
        assert 4200 * 4200 > AVATAR_MAX_PIXEL
        # Mit dem Konto verschwindet auch sein Bild – sonst bliebe es für immer liegen.
        weg = c2.post("/api/me/avatar", data={"file": (jpeg(False), "b.jpg")}, headers=H,
                      content_type="multipart/form-data").json["user"]["avatar"]
        pfad2 = _os2.path.join(av_dir, weg.rsplit("/", 1)[1])
        assert _os2.path.exists(pfad2)
        assert adm.delete(f"/api/admin/users/{uid2}", headers=H).status_code == 200
        assert not _os2.path.exists(pfad2)

        # --- Mailversand: Kopfzeilen, Umschlag und die Antwort des Servers -------------------
        # Warum das hier steht: Mails der Plattform wurden von Empfängern abgewiesen. Was die
        # Anwendung dazu beitragen kann, sind saubere Kopfzeilen und eine Auskunft darüber, was
        # der Mailserver geantwortet hat – eine abgewiesene Adresse kommt nicht als Ausnahme,
        # sondern als Rückgabewert, und der wurde früher weggeworfen.
        post = PruefstandSMTP()
        post.start()
        try:
            app.config.update(SMTP_HOST="127.0.0.1", SMTP_PORT=post.port, SMTP_STARTTLS=False,
                              SMTP_SSL=False, SMTP_USER="", SMTP_ENVELOPE_FROM="",
                              MAIL_FROM="strömis.de <post@hinzen.tech>")
            r = adm.post("/api/admin/testmail", json={"to": "wer@example.org"})
            assert r.status_code == 200 and r.json["ok"] is True, r.json
            assert "angenommen" in r.json["meldung"], r.json
            umschlag, empfaenger, roh = post.post[-1]
            # SMTP trennt Zeilen mit CRLF; für die Prüfungen reicht \n.
            kopf = roh.replace("\r\n", "\n").split("\n\n", 1)[0]
            # Der Umschlagabsender entscheidet über die SPF-Prüfung und muss ohne eigene Angabe
            # auf derselben Domain liegen wie das From – sonst scheitert DMARC.
            assert umschlag == "post@hinzen.tech" and empfaenger == ["wer@example.org"], (umschlag, empfaenger)
            # Ohne Message-ID gilt eine Mail vielen Filtern als verdächtig, und ihre Domain soll
            # die des Absenders sein.
            m = re.search(r"^Message-ID: <(\S+)>$", kopf, re.M)
            assert m and m.group(1).endswith("@hinzen.tech"), kopf
            assert re.search(r"^Auto-Submitted: auto-generated$", kopf, re.M), kopf
            # Der Anzeigename muss als EIN kodiertes Wort dastehen. Python kodierte sonst nur
            # „strömis“ und hängte „.de“ roh daran – ein abgeschnittenes kodiertes Wort, das
            # ein Teil der Empfänger wörtlich anzeigt.
            von = re.search(r"^From: (.+)$", kopf, re.M).group(1)
            assert von.endswith("<post@hinzen.tech>") and "?=.de" not in von, von

            # Ein eigener Umschlagabsender geht vor – für Rückläufer in ein anderes Postfach.
            app.config["SMTP_ENVELOPE_FROM"] = "bounce@hinzen.tech"
            assert adm.post("/api/admin/testmail", json={"to": "wer@example.org"}).json["ok"] is True
            assert post.post[-1][0] == "bounce@hinzen.tech", post.post[-1][0]
            app.config["SMTP_ENVELOPE_FROM"] = ""

            # Weist der Mailserver den Empfänger ab, steht sein Wortlaut im Bericht.
            r = adm.post("/api/admin/testmail", json={"to": "abweisen@example.org"})
            assert r.json["ok"] is False and "550" in r.json["meldung"], r.json
            assert "Unbekannter Empfaenger" in r.json["meldung"], r.json
            assert adm.post("/api/admin/testmail", json={"to": "keine-adresse"}).status_code == 400

            # Ist der Mailserver nicht erreichbar, wirft der Versand nicht, sondern berichtet.
            app.config["SMTP_PORT"] = 1        # dort horcht niemand
            r = adm.post("/api/admin/testmail", json={"to": "wer@example.org"})
            assert r.json["ok"] is False and "Keine Verbindung" in r.json["meldung"], r.json
            with app.app_context():
                from app.mailer import send_mail as _send
                assert _send("wer@example.org", "Betreff", "Text") is False
        finally:
            post.stop()
            # Abwarten, bis der Faden wirklich zu ist: Weiter unten gabelt sich der Prozess
            # (mehrere Arbeitsprozesse), und fork() aus einem Prozess mit laufenden Fäden ist
            # eine bekannte Quelle für Hänger.
            post.join(timeout=5)
            app.config.update(SMTP_HOST="", SMTP_PORT=587, SMTP_STARTTLS=True)
        # Nur Administratoren dürfen die Probemail auslösen.
        assert c1.post("/api/admin/testmail", json={}).status_code == 403

        # --- /healthz antwortet ohne Anmeldung ----------------------------------------------
        assert anon_get(app, "/healthz").status_code == 200

        # --- Sitzungsschlüssel wird nur einmal erzeugt ---------------------------------------
        from app import _load_secret
        with tempfile.TemporaryDirectory() as d:
            assert _load_secret(d) == _load_secret(d)

    # --- Erster Start mit mehreren Arbeitsprozessen -------------------------------------
    # Gunicorn startet die App in jedem Arbeitsprozess getrennt und damit gleichzeitig. Beim
    # allerersten Start legen sie zusammen das Schema und den Administrator an; ohne Absicherung
    # stirbt einer von ihnen und gunicorn fährt daraufhin ganz herunter.
    with tempfile.TemporaryDirectory() as tmp:
        q = multiprocessing.Queue()
        ps = [multiprocessing.Process(target=_starte_app, args=(tmp, q)) for _ in range(6)]
        for p in ps:
            p.start()
        for p in ps:
            p.join(60)
        raus = [q.get() for _ in ps]
        assert all(r == "ok" for r in raus), raus

    print("Härtungstest bestanden.")


def _starte_app(tmp, q):
    """Die App in einem eigenen Prozess hochfahren – für den Test des ersten Starts."""
    os.environ.update({"DATA_DIR": tmp, "COOKIE_SECURE": "false", "SECRET_KEY": "probe-nur-fuer-den-test",
                       "ADMIN_EMAIL": "admin@example.org", "ADMIN_PASSWORD": "geheim123"})
    try:
        from app import create_app
        create_app()
        q.put("ok")
    except Exception as e:                                   # noqa: BLE001 – der Grund gehört in die Meldung
        q.put(f"{type(e).__name__}: {e}")


def anon_get(app, path):
    return app.test_client().get(path)


if __name__ == "__main__":
    test_everything()
    test_haertung()
