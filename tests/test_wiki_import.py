"""Wiki-Import (ZIP, Wunsch vom 25.10.2026 W4):  python tests/test_wiki_import.py  oder  pytest tests/test_wiki_import.py

  1. Rundweg: Ein Abschnitt als ZIP exportiert und unter einer anderen Seite wieder eingelesen – Titel, Baum, natürliche
     Reihenfolge, Bilder umgeschrieben und abrufbar (Fragment #w= bleibt), Anhänge und Verweise vermerkt, eine Fassung je
     Seite; derselbe Import noch einmal → neue Seiten mit eigener Adresse und Hinweis (Entscheidung F5).
  2. Regeln eines selbst gepackten Archivs: Titel aus dem Dateinamen, Ordner ohne eigene .md, relative Bildpfade,
     Verweis auf eine andere .md → /stroemipedia/<slug>, nicht auflösbare Verweise als Hinweis, Codeblöcke und fremde Adressen
     unverändert, Videos und fremde Endungen übergangen (F6), unbenutzte Dateien nicht übernommen, HTML-Baustein
     angenommen, Systemdateien still übergangen, BOM und CRLF.
  3. Abbruch ohne Spuren: ../x.md, /etc/x.md, a\\b.md, symbolischer Verweis, doppelter Name, verschlüsselt, Packbombe,
     zu viele Einträge, zu große Seite, kein UTF-8, kein ZIP, keine Seite; ein Fehler mitten im Schreiben → keine Seite
     und keine Datei übrig.
  4. Rechte: Wiki-Verwaltung 201, Mitglied 403, Lesemodus 403, ohne Anmeldung 401; Grenze 413; Ziel unbekannt 400.
  5. Freigabe und Beschränkung erben die neuen Seiten vom Ziel; Oberfläche (statisch).

Alle Seiten, Namen und Dateien sind Platzhalter."""
import io
import os
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402

from test_smoke import H, jpeg, make_app  # noqa: E402
from test_wiki_lesemodus import konto  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class T:
    pass


def aufbau(tmp):
    t = T()
    t.app = make_app(tmp)
    t.adm = t.app.test_client()
    assert t.adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
    t.mitglied, _ = konto(t.app, t.adm, "mitglied@example.org", "Mitglied Platzhalter", {"wiki": 1})
    t.leser, _ = konto(t.app, t.adm, "leser@example.org", "Leser Platzhalter", {"wiki": 0, "karte": 1})
    t.redaktion, _ = konto(t.app, t.adm, "redaktion@example.org", "Redaktion Platzhalter", {"wiki": 2})
    t.media = os.path.join(tmp, "media", "wiki")
    return t


def seite(c, titel, inhalt="", parent=None):
    r = c.post("/api/wiki/pages", json={"title": titel, "content": inhalt, "parent_id": parent})
    assert r.status_code == 201, r.json
    return r.json["page"]


def datei(c, name, inhalt=None):
    r = c.post("/api/wiki/files", data={"file": (inhalt or jpeg(False), name)}, headers=H,
               content_type="multipart/form-data")
    assert r.status_code == 200, r.json
    return r.json["url"]


def importieren(c, daten, parent=None):
    form = {"file": (io.BytesIO(daten), "import.zip")}
    if parent is not None:
        form["parent_id"] = str(parent)
    return c.post("/api/wiki/import", data=form, headers=H, content_type="multipart/form-data")


def zip_aus(eintraege):
    """eintraege: [(name, bytes|str)] oder [(ZipInfo, bytes)]."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in eintraege:
            z.writestr(name, inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt)
    return buf.getvalue()


def png():
    buf = io.BytesIO()
    Image.new("RGBA", (40, 30), (10, 20, 200, 128)).save(buf, "PNG")
    return buf.getvalue()


def zeilen(app, sql, args=()):
    from app import db
    with app.app_context():
        return db.query(sql, args)


def baum(c):
    return {p["id"]: p for p in c.get("/api/wiki/tree").json["pages"]}


def dateien_auf_platte(t):
    return set(os.listdir(t.media)) if os.path.isdir(t.media) else set()


# --- 1. Rundweg -------------------------------------------------------------------------------------------------------

def test_rundweg():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        bild = datei(t.adm, "platzhalter.jpg")
        pdf = datei(t.adm, "platzhalter.pdf", io.BytesIO(b"%PDF-1.4 Platzhalter"))
        oben = seite(t.adm, "Platzhalter Abschnitt", f"# Platzhalter Abschnitt\n\n![Bild]({bild}#w=50)\n\n"
                                                    f"[Anleitung]({pdf})\n")
        k10 = seite(t.adm, "Kind 10", "# Kind 10\n\nZEHN\n", oben["id"])
        k2 = seite(t.adm, "Kind 2", f"# Kind 2\n\nZWEI [zum Abschnitt](/wiki/{oben['slug']})\n\n![b]({bild})\n",
                   oben["id"])
        seite(t.adm, "Enkel", "# Enkel\n\nENKEL\n", k10["id"])
        r = t.adm.get(f"/api/wiki/pages/{oben['id']}/export?children=1")
        assert r.status_code == 200
        export = r.data
        ziel = seite(t.adm, "Platzhalter Ziel", "# Platzhalter Ziel\n")
        vorher = dateien_auf_platte(t)
        r = importieren(t.adm, export, ziel["id"])
        assert r.status_code == 201, r.json
        d = r.json
        assert [s["title"] for s in d["seiten"]] == ["Platzhalter Abschnitt", "Kind 2", "Kind 10", "Enkel"], d
        assert d["dateien"] == 2 and d["hinweise"] == [], d
        neu = {s["title"]: s for s in d["seiten"]}
        assert neu["Platzhalter Abschnitt"]["parent_id"] == ziel["id"]
        assert neu["Kind 2"]["parent_id"] == neu["Kind 10"]["parent_id"] == neu["Platzhalter Abschnitt"]["id"]
        assert neu["Enkel"]["parent_id"] == neu["Kind 10"]["id"]
        b = baum(t.adm)
        assert b[neu["Kind 2"]["id"]]["position"] < b[neu["Kind 10"]["id"]]["position"]   # natürliche Reihenfolge
        assert all(s["slug"] != x["slug"] for s in d["seiten"] for x in (oben, k2, k10))
        p = t.adm.get(f"/api/wiki/pages/{neu['Platzhalter Abschnitt']['slug']}").json["page"]
        assert p["content"].startswith("# Platzhalter Abschnitt") and bild not in p["content"], p["content"]
        refs = zeilen(t.app, "SELECT file FROM wiki_page_files WHERE page_id = ?", (p["id"],))
        assert len(refs) == 2, refs
        for ref in (x["file"] for x in refs):
            assert f"/media/wiki/{ref}" in p["content"] and t.adm.get(f"/media/wiki/{ref}").status_code == 200
        assert "#w=50)" in p["content"]
        neue_dateien = dateien_auf_platte(t) - vorher
        assert len(neue_dateien) == 2, neue_dateien
        vermerkt = {x["file"] for x in zeilen(t.app, "SELECT file FROM wiki_files")}
        assert neue_dateien <= vermerkt
        # Dasselbe Bild auf zwei Seiten: einmal abgelegt.
        k2neu = t.adm.get(f"/api/wiki/pages/{neu['Kind 2']['slug']}").json["page"]
        bild_neu = [x["file"] for x in refs if x["file"].endswith(".jpg")][0]
        assert f"/media/wiki/{bild_neu})" in k2neu["content"], k2neu["content"]
        # Wiki-Links bleiben, wie sie waren (sie zeigen auf die Ursprungsseite); Verknüpfung vermerkt.
        assert f"(/wiki/{oben['slug']})" in k2neu["content"]
        assert zeilen(t.app, "SELECT target_slug FROM wiki_page_links WHERE page_id = ?", (k2neu["id"],)) == [
            {"target_slug": oben["slug"]}]
        for s in d["seiten"]:
            assert len(zeilen(t.app, "SELECT id FROM wiki_revisions WHERE page_id = ?", (s["id"],))) == 1
            assert zeilen(t.app, "SELECT created_by FROM wiki_pages WHERE id = ?", (s["id"],))[0]["created_by"] == 1
        # Noch einmal unter dasselbe Ziel: neue Seiten, eigene Adressen, Hinweis; die vorhandenen bleiben.
        r = importieren(t.adm, export, ziel["id"])
        assert r.status_code == 201, r.json
        d2 = r.json
        assert d2["hinweise"][0].startswith("Unter „Platzhalter Ziel“ gibt es schon eine Seite „Platzhalter Abschnitt“"), d2
        assert d2["seiten"][0]["slug"] != neu["Platzhalter Abschnitt"]["slug"]
        assert t.adm.get(f"/api/wiki/pages/{neu['Platzhalter Abschnitt']['slug']}").json["page"]["id"] == \
            neu["Platzhalter Abschnitt"]["id"]
        b = baum(t.adm)
        assert b[d2["seiten"][0]["id"]]["position"] > b[neu["Platzhalter Abschnitt"]["id"]]["position"]
        # Oberste Ebene.
        r = importieren(t.adm, export)
        assert r.status_code == 201 and r.json["seiten"][0]["parent_id"] is None, r.json
        assert r.json["hinweise"][0].startswith("Auf der obersten Ebene gibt es schon eine Seite"), r.json
    print("Rundweg bestanden.")


def test_rundweg_gleichnamige_geschwister():
    """Zwei Geschwister mit demselben Titel, jedes mit eigener Unterseite (Nachbesserung vor dem Merge, ablauf_module
    Befund 1): Der Export legt den Pfad je Seite einmal fest – das zweite „Übung“ heißt „Übung-<slug>“, und seine
    Unterseite liegt in genau diesem Ordner. Der Import baut den Baum gleich wieder auf."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        oben = seite(t.adm, "Platzhalter Rundlauf", "# Platzhalter Rundlauf\n")
        u1 = seite(t.adm, "Übung", "# Übung\n\nERSTE\n", oben["id"])
        u2 = seite(t.adm, "Übung", "# Übung\n\nZWEITE\n", oben["id"])
        seite(t.adm, "Kind der ersten", "# Kind der ersten\n", u1["id"])
        e2 = seite(t.adm, "Kind der zweiten", "# Kind der zweiten\n", u2["id"])
        seite(t.adm, "Enkel der zweiten", "# Enkel der zweiten\n", e2["id"])
        r = t.adm.get(f"/api/wiki/pages/{oben['id']}/export?children=1")
        assert r.status_code == 200
        namen = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
        zweite = f"Platzhalter Rundlauf/Übung-{u2['slug']}"
        assert "Platzhalter Rundlauf/Übung/Kind der ersten.md" in namen, namen
        assert f"{zweite}.md" in namen and f"{zweite}/Kind der zweiten.md" in namen, namen
        assert f"{zweite}/Kind der zweiten/Enkel der zweiten.md" in namen, namen
        assert len(namen) == len(set(n.lower() for n in namen)) == 6, namen
        d = importieren(t.adm, r.data).json
        nach_id = {x["id"]: x for x in d["seiten"]}

        def text(x):
            return t.adm.get(f"/api/wiki/pages/{x['slug']}").json["page"]["content"]

        for kind, erwartet in (("Kind der ersten", "ERSTE"), ("Kind der zweiten", "ZWEITE")):
            k = [x for x in d["seiten"] if x["title"] == kind]
            assert len(k) == 1, d
            eltern = nach_id[k[0]["parent_id"]]
            assert eltern["title"] == "Übung" and erwartet in text(eltern), (kind, eltern)
        enkel = [x for x in d["seiten"] if x["title"] == "Enkel der zweiten"][0]
        assert nach_id[enkel["parent_id"]]["title"] == "Kind der zweiten"
        uebungen = [x for x in d["seiten"] if x["title"] == "Übung"]
        assert len(uebungen) == 2 and {nach_id[x["parent_id"]]["title"] for x in uebungen} == {"Platzhalter Rundlauf"}
    print("Rundweg mit gleichnamigen Geschwistern bestanden.")


# --- 2. Regeln ---------------------------------------------------------------------------------------------------------

def test_regeln():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        bild = png()
        archiv = zip_aus([
            ("10 Zehn.md", "\ufeff# Zehn *fett*\r\n\r\nTEXT ZEHN\r\n"),
            ("2 Zwei.md", "Ohne Titelzeile.\n\n[zur Zehn](10%20Zehn.md#abs) · [weg](https://example.org/x.png)\n"
                          ":::einbau fremde-seite#teil\n:::\n"),
            ("Ordner/Unter.md", "# Unter\n\n![a](../bilder/a.png#w=30) ![b](<../bilder/a.png>)\n"
                                "<img src=\"../bilder/a.png\">\n\n```\n![code](../bilder/a.png)\n```\n"
                                "`![inline](../bilder/a.png)`\n\n![fehlt](fehlt.png)\n\n[Film](../film.mp4)\n\n"
                                "[Baustein](../baustein.html)\n"),
            ("bilder/a.png", bild),
            ("bilder/unbenutzt.png", bild),
            ("film.mp4", b"\x00\x00\x00\x18ftypmp42"),
            ("baustein.html", "<!doctype html><p>Platzhalter</p>"),
            ("programm.exe", b"MZ"),
            ("__MACOSX/._10 Zehn.md", b"\x00\x05\x16\x07"),
            (".DS_Store", b"\x00"),
            ("Ordner/Thumbs.db", b"\x00"),
        ])
        ziel = seite(t.adm, "Platzhalter Regeln", "# Platzhalter Regeln\n")
        r = importieren(t.adm, archiv, ziel["id"])
        assert r.status_code == 201, r.json
        d = r.json
        assert [s["title"] for s in d["seiten"]] == ["2 Zwei", "Zehn fett", "Ordner", "Unter"], d
        s = {x["title"]: t.adm.get(f"/api/wiki/pages/{x['slug']}").json["page"] for x in d["seiten"]}
        assert s["Unter"]["parent_id"] == s["Ordner"]["id"] and s["Ordner"]["parent_id"] == ziel["id"]
        assert s["Ordner"]["content"] == "# Ordner\n"
        assert s["2 Zwei"]["content"].startswith("# 2 Zwei\n\nOhne Titelzeile.")
        assert s["Zehn fett"]["content"] == "# Zehn *fett*\n\nTEXT ZEHN\n"            # BOM und CRLF weg, Titel ohne Stern
        assert f"[zur Zehn](/stroemipedia/{s['Zehn fett']['slug']}#abs)" in s["2 Zwei"]["content"]
        assert "(https://example.org/x.png)" in s["2 Zwei"]["content"] and ":::einbau fremde-seite#teil" in s["2 Zwei"]["content"]
        u = s["Unter"]["content"]
        neu = [x["file"] for x in zeilen(t.app, "SELECT file FROM wiki_page_files WHERE page_id = ?", (s["Unter"]["id"],))]
        png_neu = [x for x in neu if x.endswith(".png")]
        html_neu = [x for x in neu if x.endswith(".html")]
        assert len(png_neu) == 1 and len(html_neu) == 1, neu
        assert f"![a](/media/wiki/{png_neu[0]}#w=30)" in u and f"![b](</media/wiki/{png_neu[0]}>)" in u, u
        assert f'<img src="/media/wiki/{png_neu[0]}">' in u
        assert "```\n![code](../bilder/a.png)\n```" in u and "`![inline](../bilder/a.png)`" in u
        assert "![fehlt](fehlt.png)" in u and "[Film](../film.mp4)" in u
        assert f"[Baustein](/media/wiki/{html_neu[0]})" in u
        assert d["dateien"] == 2, d
        h = "\n".join(d["hinweise"])
        assert "Verweis ohne Datei in „Ordner/Unter.md“: fehlt.png" in h, h
        assert "Video „film.mp4“ übergangen – Videos einzeln hochladen." in h
        assert "„bilder/unbenutzt.png“ – keine Seite verweist darauf, nicht übernommen." in h
        assert "„programm.exe“ übergangen" in h
        assert "MACOSX" not in h and "DS_Store" not in h and "Thumbs" not in h
        assert h.count("film.mp4") == 1 and h.count("fehlt.png") == 1                     # je Hinweis einmal
        # Das Bild ist neu geschrieben (PNG mit Durchsicht bleibt PNG).
        assert Image.open(os.path.join(t.media, png_neu[0])).size == (40, 30)
    print("Regeln bestanden.")


# --- 3. Abbruch -------------------------------------------------------------------------------------------------------

def _verschluesselt():
    roh = bytearray(zip_aus([("a.md", "# A\n")]))
    for sig, ab in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = roh.index(sig)
        roh[i + ab] |= 0x1
    return bytes(roh)


def _symlink():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.md", "# A\n")
        zi = zipfile.ZipInfo("verweis.md")
        zi.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(zi, "/etc/passwd")
    return buf.getvalue()


def _doppelt():
    buf = io.BytesIO()
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.md", "# A\n")
            z.writestr("a.md", "# B\n")
    return buf.getvalue()


def test_abbruch():
    from app import api_wiki, wiki_import
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        ziel = seite(t.adm, "Platzhalter Abbruch", "# Platzhalter Abbruch\n")
        seiten_vorher = len(baum(t.adm))
        faelle = [
            (zip_aus([("../x.md", "# X\n")]), "kein schlichter Pfad"),
            (zip_aus([("/etc/x.md", "# X\n")]), "kein relativer Pfad"),
            (zip_aus([("a\\b.md", "# X\n")]), "kein relativer Pfad"),
            (zip_aus([("C:/x.md", "# X\n")]), "kein relativer Pfad"),
            (zip_aus([("a\x01b.md", "# X\n")]), "Steuerzeichen"),
            (zip_aus([("/".join(["o"] * 21) + ".md", "# X\n")]), "tiefer als 20 Ebenen"),
            (_symlink(), "symbolischer Verweis"),
            (_doppelt(), "steht doppelt"),
            (_verschluesselt(), "verschlüsselt"),
            (zip_aus([("a.md", "# A\n"), ("bombe.png", b"\x00" * (3 * 1024 * 1024))]), "ungewöhnlich stark gepackt"),
            (zip_aus([(f"s{i}.txt", "") for i in range(2001)]), "höchstens 2000"),
            (zip_aus([("gross.md", "# G\n" + os.urandom(600 * 1024).hex())]), "so lang darf eine Seite nicht sein"),
            (zip_aus([("latin.md", "# Gr\xfc\xdfe\n".encode("latin-1"))]), "kein UTF-8"),
            (zip_aus([("nul.md", "# N\n\x00")]), "Nullzeichen"),
            (zip_aus([("a.md", "# A\n"), ("a.markdown", "# B\n")]), "wären dieselbe Seite"),
            (zip_aus([("nur.png", png())]), "keine Seite"),
            (zip_aus([("lang.md", "# " + "x" * 201 + "\n")]), "länger als 200 Zeichen"),
            (b"kein zip", "kein ZIP-Archiv"),
        ]
        for daten, text in faelle:
            vorher = dateien_auf_platte(t)
            r = importieren(t.adm, daten, ziel["id"])
            assert r.status_code == 400 and text in r.json["error"], (text, r.status_code, r.json)
            assert len(baum(t.adm)) == seiten_vorher and dateien_auf_platte(t) == vorher, text
        # Alle Seiten zusammen über der Grenze für Seitentext.
        alt, wiki_import.MAX_SEITEN_TEXT = wiki_import.MAX_SEITEN_TEXT, 10
        try:
            r = importieren(t.adm, zip_aus([("a.md", "# A\n"), ("b.md", "# B mit etwas mehr Text\n")]), ziel["id"])
        finally:
            wiki_import.MAX_SEITEN_TEXT = alt
        assert r.status_code == 400 and "zusammen" in r.json["error"], r.json
        # Fehler mitten im Schreiben: Seiten und schon abgelegte Bilder sind wieder weg.
        archiv = zip_aus([("a.md", "# A\n\n![x](x.png)\n"), ("b.md", "# B\n\n![y](y.png)\n"), ("x.png", png()),
                          ("y.png", png())])
        echt = api_wiki.sync_page_links
        aufrufe = []

        def kaputt(pid, content):
            aufrufe.append(pid)
            if len(aufrufe) == 2:
                raise wiki_import.ImportFehler("Platzhalter-Fehler beim Schreiben")
            return echt(pid, content)
        api_wiki.sync_page_links = kaputt
        try:
            vorher = dateien_auf_platte(t)
            r = importieren(t.adm, archiv, ziel["id"])
        finally:
            api_wiki.sync_page_links = echt
        assert r.status_code == 400 and "Platzhalter-Fehler" in r.json["error"], r.json
        assert len(aufrufe) == 2 and len(baum(t.adm)) == seiten_vorher and dateien_auf_platte(t) == vorher
        assert not zeilen(t.app, "SELECT id FROM wiki_pages WHERE title IN ('A', 'B')")
        assert not zeilen(t.app, "SELECT id FROM wiki_revisions WHERE title IN ('A', 'B')")
        # Ein kaputtes Bild bricht nicht ab: Hinweis, Verweis bleibt.
        r = importieren(t.adm, zip_aus([("k.md", "# K\n\n![k](k.jpg)\n"), ("k.jpg", b"kein bild")]), ziel["id"])
        assert r.status_code == 201 and "„k.jpg“ ließ sich nicht verarbeiten (Dateityp nicht lesbar)" in "\n".join(r.json["hinweise"]), r.json
    print("Abbruch bestanden.")


# --- 4. Rechte und Grenzen --------------------------------------------------------------------------------------------

def test_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        archiv = zip_aus([("a.md", "# A\n")])
        for c, code in ((t.mitglied, 403), (t.leser, 403), (t.app.test_client(), 401)):
            r = importieren(c, archiv)
            assert r.status_code == code, (code, r.json)
        assert importieren(t.mitglied, archiv).json["error"] == "Seiten importieren darf nur die Wiki-Verwaltung."
        assert not zeilen(t.app, "SELECT id FROM wiki_pages WHERE title = 'A'")
        assert importieren(t.redaktion, archiv).status_code == 201
        r = importieren(t.adm, archiv, 999999)
        assert r.status_code == 400 and "gibt es nicht" in r.json["error"], r.json
        assert t.adm.post("/api/wiki/import", data={}, headers=H, content_type="multipart/form-data").status_code == 400
        # Vorgabe 200 MB (Entscheidung F6), einstellbar über WIKI_IMPORT_MB.
        assert t.app.config["WIKI_IMPORT_MAX_BYTES"] == 200 * 1024 * 1024
        t.app.config["WIKI_IMPORT_MAX_BYTES"] = 1024
        r = importieren(t.adm, zip_aus([("a.md", "# A\n" + os.urandom(2048).hex())]))
        assert r.status_code == 413 and "Grenze: 0 MB" in r.json["error"], r.json
        t.app.config["WIKI_IMPORT_MAX_BYTES"] = 200 * 1024 * 1024
    print("Rechte bestanden.")


# --- 5. Erben, Oberfläche ---------------------------------------------------------------------------------------------

def test_erben():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        offen = seite(t.adm, "Platzhalter Offen", "# Platzhalter Offen\n")
        assert t.adm.put(f"/api/wiki/pages/{offen['id']}/share",
                         json={"is_public": True, "public_children": True}).status_code == 200
        geheim = seite(t.adm, "Platzhalter Geheim", "# Platzhalter Geheim\n")
        assert t.adm.put(f"/api/wiki/pages/{geheim['id']}/restrict", json={"read_restricted": True}).status_code == 200
        archiv = zip_aus([("Neu.md", "# Neu\n\nNEU-MARKE\n"), ("Neu/Kind.md", "# Kind\n")])
        r = importieren(t.adm, archiv, offen["id"])
        assert r.status_code == 201, r.json
        for s in r.json["seiten"]:
            p = t.adm.get(f"/api/wiki/pages/{s['slug']}").json["page"]
            assert p["effective_public"] and not p["is_public"] and not p["read_restricted"], p
        anon = t.app.test_client()
        assert anon.get(f"/api/public/pages/{r.json['seiten'][0]['slug']}").status_code == 200
        r = importieren(t.adm, archiv, geheim["id"])
        assert r.status_code == 201
        for s in r.json["seiten"]:
            assert t.mitglied.get(f"/api/wiki/pages/{s['slug']}").status_code == 403
            assert t.adm.get(f"/api/wiki/pages/{s['slug']}").status_code == 200
    print("Erben bestanden.")


def test_oberflaeche_statisch():
    js = open(os.path.join(WURZEL, "app/static/js/wiki.js"), encoding="utf-8").read()
    # Seit 27.10.2026 (Wunsch des Nutzers) im „⋯“-Menü jeder Seite im Seitenbaum, nicht mehr im Menü des Seitenkopfs;
    # der Dialog wählt die Seite der Zeile vor, auf die oberste Ebene führt der graue Knopf „Importieren“ über dem Baum.
    kopf = js[js.index("function pageMenu(anchor, p)"):js.index("/* Seiten aus einem ZIP importieren")]
    assert 'data-a="import"' not in kopf and "importDialog" not in kopf
    baum = js[js.index("function treeRowMenu(anchor, page)"):js.index("function wireTreeDrag()")]
    assert '${darfImportieren() ? \'<button type="button" data-a="import">Seiten aus ZIP importieren</button>\' : ""}' in baum
    assert baum.index('data-a="export"') < baum.index('data-a="import"') < baum.index('data-a="del"')
    assert 'if (a === "import") { side.classList.remove("open"); return importDialog(page); }' in baum
    assert "const darfImportieren = () => { const u = window.STROEMIS && STROEMIS.user; return !!(u && u.rechte && u.rechte.wiki === 2); };" in js
    # Oberste Ebene: seit dem Auftrag „letzte offene Punkte“ (27.10.2026) im Menü „⋯“ neben „Neue Seite“ über dem Baum
    # (mit dem Papierkorb) – vorher drei Knöpfe, „Importieren“ brach am Telefon in eine zweite Zeile.
    menue = js[js.index("function baumMenu(anchor)"):js.index("function treeRowMenu(anchor, page)")]
    assert '<button type="button" data-a="trash">Papierkorb</button>' in menue
    assert '${darfImportieren() ? \'<button type="button" data-a="import">Seiten aus ZIP importieren</button>\' : ""}' in menue
    assert 'if (b.dataset.a === "import") { side.classList.remove("open"); importDialog(null); }' in menue
    assert 'if (b.dataset.a === "trash") return trashDialog();' in menue and "wireMenuKeys(box, close);" in menue
    assert '$("#btn-baum-mehr").addEventListener("click", (e) => baumMenu(e.currentTarget));' in js
    assert "#btn-import" not in js and "#btn-trash" not in js
    html = open(os.path.join(WURZEL, "app/templates/wiki.html"), encoding="utf-8").read()
    anfang = html.rindex("<div", 0, html.index('id="btn-new-page"'))
    zeile = html[anfang:html.index("</div>", anfang)]
    assert zeile.count("<button") == 2 and 'class="btn small"' in zeile and 'class="btn secondary small" id="btn-baum-mehr"' in zeile
    assert 'aria-haspopup="menu" aria-label="Weitere Aktionen"' in zeile and ">⋯</button>" in zeile and "…" not in zeile
    dlg = js[js.index("function importDialog(p)"):js.index("/* --- Ende Import")]
    assert '${p && k.id === p.id ? " selected" : ""}' in dlg
    assert "<h2>Seiten importieren</h2>" in dlg and 'accept=".zip' in dlg and "Einsortieren unter" in dlg
    assert dlg.count('class="btn"') == 1 and '<button class="btn" id="im-ok" type="button">Importieren</button>' in dlg
    assert "Wird importiert …" in dlg and "btn ghost" not in dlg and "esc(" in dlg
    assert "– oberste Ebene –" in dlg and "ohne Anmeldung sichtbar" in dlg and "ebenso beschränkt" in dlg
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_rundweg()
    test_rundweg_gleichnamige_geschwister()
    test_regeln()
    test_abbruch()
    test_rechte()
    test_erben()
    test_oberflaeche_statisch()
