"""Neue Modulnamen samt Adressen (Wunsch des Nutzers, 26.10.2026):  python tests/test_umbenennung.py  oder
pytest tests/test_umbenennung.py

Strömipedia (Modul wiki, /stroemipedia), Ankerplätze (karte, /ankerplaetze), Riegenkarten (pruefungen, /riegenkarten),
Materialablage (material, /materialablage), Leitstelle (verwaltung, /leitstelle). Geprüft: jede alte Adresse leitet
dauerhaft auf die neue (301, Abfrage bleibt, Umlaut-Schreibweisen), nichts sonst wird erfasst, kein offener Sprung;
die neuen Adressen antworten wie früher die alten (Anmeldung, 403, Startweiche); Kopfleiste, Titel, Meldungen,
Einstellungen und Mails tragen die neuen Namen und Adressen; neue Protokolle drucken /materialablage/pruefen, ein
festgeschriebenes Protokoll mit der alten Adresse bleibt unverändert prüfbar; gespeicherte Wiki-Links in beiden
Schreibweisen zählen. Alle Namen, Seiten und Prüfpunkte sind Platzhalter."""
import io
import os
import re
import sys
import tempfile
import unicodedata
from urllib.parse import quote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _flach, festschreiben, gliederung, katalog_grund, neuer_artikel,  # noqa: E402
                           neues_konto, pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung)

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEU = ("/stroemipedia", "/ankerplaetze", "/riegenkarten", "/materialablage", "/leitstelle")

# (alte Adresse, neue Adresse) – Pfad samt Abfrage, wie der Browser sie schickt.
WEITER = [
    ("/wiki", "/stroemipedia"),
    ("/wiki/platzhalter-seite", "/stroemipedia/platzhalter-seite"),
    ("/wiki/platzhalter-seite?leise=1", "/stroemipedia/platzhalter-seite?leise=1"),
    ("/karte", "/ankerplaetze"),
    ("/karte?album=3", "/ankerplaetze?album=3"),
    ("/pruefungen", "/riegenkarten"),
    ("/pruefungen/kataloge", "/riegenkarten/kataloge"),
    ("/pruefungen/kataloge/3", "/riegenkarten/kataloge/3"),
    ("/pruefungen/5", "/riegenkarten/5"),
    ("/pruefungen/5/druck?ansicht=tn&teilnehmer=2", "/riegenkarten/5/druck?ansicht=tn&teilnehmer=2"),
    ("/material", "/materialablage"),
    ("/material/pruefungen?status=ueberfaellig&ordner=4", "/materialablage/pruefungen?status=ueberfaellig&ordner=4"),
    ("/material/ordner/7?freigaben=materialwart", "/materialablage/ordner/7?freigaben=materialwart"),
    ("/material/artikel/12", "/materialablage/artikel/12"),
    ("/material/pruefen", "/materialablage/pruefen"),
    ("/material/meine-psa/9", "/materialablage/meine-psa/9"),
    ("/material/katalog/meldungen?status=offen", "/materialablage/katalog/meldungen?status=offen"),
    ("/material/suche?q=AB%2012", "/materialablage/suche?q=AB%2012"),
    ("/material/export/4.csv", "/materialablage/export/4.csv"),
    ("/admin", "/leitstelle"),
    ("/admin?x=%C3%A4", "/leitstelle?x=%C3%A4"),
    # Umlaut-Schreibweisen (Entscheidung F3 A) – wie der Browser sie kodiert, auch zerlegt (NFD).
    ("/str%C3%B6mipedia", "/stroemipedia"),
    ("/str%C3%B6mipedia/platzhalter-seite", "/stroemipedia/platzhalter-seite"),
    ("/ankerpl%C3%A4tze", "/ankerplaetze"),
    ("/" + quote(unicodedata.normalize("NFD", "ankerplätze")), "/ankerplaetze"),
    # Schrägstrich am Ende der Startseite (Nachbesserung vor dem Merge, N6) – auch bei den alten Adressen in einem Schritt.
    ("/stroemipedia/", "/stroemipedia"),
    ("/ankerplaetze/", "/ankerplaetze"),
    ("/riegenkarten/", "/riegenkarten"),
    ("/materialablage/?ordner=4", "/materialablage?ordner=4"),
    ("/leitstelle/", "/leitstelle"),
    ("/wiki/", "/stroemipedia"),
    ("/material/?x=1", "/materialablage?x=1"),
    ("/str%C3%B6mipedia/", "/stroemipedia"),
]

# Bleibt, wie es ist: kein 301.
UNBERUEHRT = ["/", "/materialx", "/materialablage", "/wikis", "/wiki-seite", "/administration", "/kartei",
              "/pruefungenx", "/api/material/start", "/api/wiki/tree", "/api/admin/users", "/api/pruefungen/lehrgaenge",
              "/media/material/web/x.jpg", "/media/wiki/x.jpg", "/media/pruefung/web/x.jpg",
              "/static/material/material.js", "/m/abcdef", "/oeffentlich/", "/login?next=/material",
              "/stroemipedia", "/leitstelle", "/riegenkarten", "/ankerplaetze", "/stroemipedia/x/",
              "/riegenkarten/kataloge/", "/stroemipedia//"]


def _app(tmp):
    return umgebung(tmp)


def test_weiterleitungen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        for c in (app.test_client(), k["adm"], k["nutzer"]):          # ohne Anmeldung, Plattform-Verwaltung, ohne Stufe
            for alt, neu in WEITER:
                for r in (c.get(alt), c.head(alt)):
                    assert r.status_code == 301, (alt, r.status_code)
                    assert r.headers["Location"] == neu, (alt, r.headers["Location"])
                    assert "max-age=86400" in r.headers.get("Cache-Control", ""), r.headers
        anon = app.test_client()
        for pfad in UNBERUEHRT:
            assert anon.get(pfad).status_code != 301, pfad
        # Nur GET und HEAD: Schreibende Anfragen an alte Seitenpfade werden nicht umgelenkt (Seiten kennen sie nicht).
        for methode in ("post", "put", "delete", "patch"):
            for alt in ("/material", "/wiki/x", "/admin", "/material/pruefen"):
                r = getattr(k["adm"], methode)(alt, json={}, headers=H)
                assert r.status_code in (404, 405), (methode, alt, r.status_code)
        # Kein offener Sprung: Ziel ist immer ein eigener Pfad mit festem Präfix – kein Host, kein Schema, kein „//“,
        # kein Rückstrich, keine Steuerzeichen.
        boese = ["/wiki//evil.example/x", "/wiki/%5C%5Cevil.example", "/material/%2F%2Fevil.example",
                 "/admin/..%2F..%2Fevil", "/karte/%0d%0aSet-Cookie:x=1", "/wiki/@evil.example",
                 "/admin?next=//evil.example", "/wiki/https:%2F%2Fevil.example", "/material/%E2%80%AE"]
        for pfad in boese:
            r = anon.get(pfad)
            assert r.status_code == 301, (pfad, r.status_code)
            ziel = r.headers["Location"]
            assert any(ziel == n or ziel.startswith(n + "/") or ziel.startswith(n + "?") for n in NEU), (pfad, ziel)
            teile = urlsplit(ziel)
            assert not teile.scheme and not teile.netloc, ziel                 # eigener Host, kein Schema
            assert "\\" not in ziel and "\r" not in ziel and "\n" not in ziel and not ziel.startswith("//"), ziel
        # Der Schrägstrich-Fall kennt nur die fünf festen Startseiten: kein Sprung auf „//…“ oder fremde Pfade.
        from app import module
        for pfad in ("//stroemipedia/", "//evil.example/", "/stroemipedia//", "/leitstelle/x/", "/"):
            assert module.weiterleitung(pfad) is None, pfad
        assert module.weiterleitung("/wiki//") == "/stroemipedia//"           # bleibt ein eigener Pfad (404 dort)
        # Die Wiki-Subdomain schreibt vorher auf /oeffentlich/… um – dort greift keine Weiterleitung (wie bisher).
        host = app.config["PUBLIC_HOST"]
        r = anon.get("/wiki/platzhalter", headers={"Host": host})
        assert r.status_code != 301, r.status_code
        assert anon.get("/", headers={"Host": host}).status_code == 200
    print("Weiterleitungen bestanden.")


def test_neue_adressen_wie_die_alten():
    """Die neuen Adressen antworten wie früher die alten: ohne Anmeldung zur Anmeldung mit next = neuer Pfad, ohne
    Stufe 403, die Startweiche führt auf die neuen Pfade; die öffentliche Prüfseite braucht keine Anmeldung."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        anon = app.test_client()
        for pfad in ("/stroemipedia", "/stroemipedia/x", "/ankerplaetze", "/riegenkarten", "/riegenkarten/kataloge",
                     "/leitstelle", "/materialablage/bestand", "/materialablage/artikel/1"):
            r = anon.get(pfad)
            assert r.status_code == 302 and "/login" in r.headers["Location"], (pfad, r.status_code)
            assert quote(pfad, safe="") in r.headers["Location"] or pfad in r.headers["Location"], r.headers["Location"]
        assert anon.get("/materialablage/pruefen").status_code == 200
        r = anon.get("/material/pruefen", follow_redirects=True)
        assert r.status_code == 200 and "Protokoll prüfen" in r.text
        # Mitglied nur in der Materialablage (Vorgabe neuer Konten): Riegenkarten, Ankerplätze, Leitstelle zu.
        w = k["wart"]
        assert w.get("/materialablage").status_code == 200
        for pfad in ("/riegenkarten", "/ankerplaetze", "/leitstelle"):
            assert w.get(pfad).status_code == 403, pfad
            assert w.get(pfad.replace("/riegenkarten", "/pruefungen").replace("/ankerplaetze", "/karte")
                         .replace("/leitstelle", "/admin"), follow_redirects=True).status_code == 403, pfad
        assert w.get("/").headers["Location"] == "/materialablage"
        # Startweiche je Modul.
        for mail, rechte, ziel in (("nur-karte@example.org", {"karte": 1, "material": 0}, "/ankerplaetze"),
                                   ("nur-rk@example.org", {"pruefungen": 1, "material": 0}, "/riegenkarten")):
            c, _ = neues_konto(app, mail, rechte=rechte)
            r = c.get("/")
            assert r.status_code == 302 and r.headers["Location"] == ziel, (mail, r.headers.get("Location"))
            assert c.get(ziel).status_code == 200
        # Ohne jedes Modul: Lesemodus unter /stroemipedia.
        c, _ = neues_konto(app, "nichts@example.org", stufe=0)
        r = c.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/stroemipedia"), r.headers.get("Location")
        assert 'data-modus="lesemodus"' in c.get("/stroemipedia").text
        # Fremde Gegenstände bleiben unter der neuen Adresse, was sie waren (404 wie unbekannt).
        assert k["nutzer"].get("/materialablage/artikel/999999").status_code == 403    # ohne Stufe: kein Zugang
        assert w.get("/materialablage/artikel/999999").status_code == 404
    print("Neue Adressen bestanden.")


def _nav(html):
    m = re.search(r'<nav class="nav" aria-label="Hauptnavigation">(.*?)</nav>', html, re.S)
    assert m, html[:500]
    return m.group(1)


def test_namen_in_der_oberflaeche():
    from app import auth
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        voll, _ = neues_konto(app, "voll@example.org", name="Voll Platzhalter",
                              rechte={"verwaltung": 2, "material": 2, "wiki": 2, "karte": 2, "pruefungen": 2})
        nav = _nav(voll.get("/profil").text)
        for name, pfad in (("Strömipedia", "/"), ("Ankerplätze", "/ankerplaetze"), ("Riegenkarten", "/riegenkarten"),
                           ("Materialablage", "/materialablage"), ("Leitstelle", "/leitstelle")):
            assert re.search(rf'<a href="{re.escape(pfad)}" class="[^"]*">{name}</a>', nav), (name, nav)
        for alt in (">Wiki<", ">Spots<", ">Prüfungen<", ">Material<", ">Verwaltung<"):
            assert alt not in nav, (alt, nav)
        # Reihenfolge unverändert (Priority+ in common.js legt Überlauf unter „Mehr“).
        stellen = [nav.index(n) for n in ("Strömipedia", "Ankerplätze", "Riegenkarten", "Materialablage", "Leitstelle",
                                          "Profil")]
        assert stellen == sorted(stellen), stellen
        for pfad, titel in (("/", "Strömipedia"), ("/stroemipedia", "Strömipedia"), ("/ankerplaetze", "Ankerplätze"),
                            ("/riegenkarten", "Riegenkarten"), ("/materialablage", "Materialablage"),
                            ("/leitstelle", "Leitstelle")):
            html = voll.get(pfad).text
            assert f"<title>{titel} – strömis.de</title>" in html, (pfad, re.findall(r"<title>.*?</title>", html))
        html = voll.get("/leitstelle").text
        for spalte in ("Ankerplätze", "Strömipedia", "Riegenkarten", "Materialablage", "Leitstelle"):
            assert f"<th>{spalte}</th>" in html, spalte
        assert "Globale Suchen (Materialablage)" in html and '"module": {' not in html
        assert '"name": {' in html or "module: {" in html                      # STROEMIS.module für admin.js
        # Öffentliche Strömipedia (ohne Anmeldung) und Lesemodus.
        oeff = app.test_client().get("/oeffentlich/").text
        assert "<title>Strömipedia – strömis.de</title>" in oeff and "öffentliche Strömipedia" in oeff
        assert "Strömipedia durchsuchen" in oeff and "Wiki" not in oeff.split("</header>")[0]
        login = app.test_client().get("/login").text
        assert "öffentlichen Strömipedia" in login and "Wiki" not in login
        # Fehlerseite der Materialablage und ohne Recht.
        r = k["wart"].get("/materialablage/artikel/999999")
        assert "Zur Übersicht der Materialablage" in r.text
        # Zugangsmeldungen der Schnittstellen nennen die neuen Namen.
        # Die 403-Seite eines Moduls nennt es (wie die Schnittstelle, Verbesserung 2 der Browserprüfung).
        for pfad, modul in (("/riegenkarten", "pruefungen"), ("/ankerplaetze", "karte"), ("/leitstelle", "verwaltung"),
                            ("/pruefungen/kataloge", "pruefungen")):
            r = k["wart"].get(pfad, follow_redirects=True)
            assert r.status_code == 403 and auth.KEIN_ZUGANG[modul] in r.text, (pfad, r.text[-600:])
        # Spalten der Rechte-Matrix in der Reihenfolge der Kopfleiste.
        html = voll.get("/leitstelle").text
        spalten = [html.index(f"<th>{n}</th>") for n in ("Strömipedia", "Ankerplätze", "Riegenkarten", "Materialablage",
                                                         "Leitstelle")]
        assert spalten == sorted(spalten), spalten
        r = k["wart"].get("/api/map")
        assert r.status_code == 403 and r.json["error"] == "Für dein Konto sind die Ankerplätze nicht freigeschaltet."
        r = k["wart"].get("/api/pruefungen/lehrgaenge")
        assert r.status_code == 403 and "Riegenkarten" in r.json["error"], r.get_json()
        r = k["nutzer"].get("/api/wiki/tree")
        assert r.status_code == 403 and r.json["error"] == "Für dein Konto ist die Strömipedia nicht freigeschaltet."
        # Einstellungen: Gruppen mit den neuen Namen.
        gruppen = k["adm"].get("/api/admin/einstellungen").json["gruppen"]
        assert "Riegenkarten" in gruppen and "Materialablage" in gruppen
        assert "Prüfungen" not in gruppen and "Material" not in gruppen, gruppen
    print("Namen in der Oberfläche bestanden.")


def test_mails():
    """Kontoanfrage (Leitstelle) und Beobachten (Strömipedia) mit neuen Links; die Mails der Materialablage prüfen
    test_material_erinnerung/_mangel/_antrag/_rueckruf mit – hier statisch: kein Link baut mehr einen alten Pfad."""
    from app import api_wiki, auth
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        post = []
        alt = auth.send_mail, api_wiki.send_mail
        auth.send_mail = api_wiki.send_mail = lambda an, betreff, text: post.append((an, betreff, text))
        try:
            c = app.test_client()
            r = c.post("/api/auth/register", json={"email": "anfrage@example.org", "password": "passwort1",
                                                   "name": "Anfrage Platzhalter", "gliederung": "OG Platzhalter"})
            assert r.status_code in (200, 201), r.get_json()
            texte = [t for _, b, t in post if "Kontoanfrage" in b]
            assert texte and "https://strömis.de/leitstelle\n" in texte[0], texte
            # Beobachten: eine Seite, ein zweites Konto beobachtet, die Verwaltung kommentiert.
            adm = k["adm"]
            seite = adm.post("/api/wiki/pages", json={"title": "Platzhalter Beobachtet", "content": "# x\n"}).json["page"]
            leser, _ = neues_konto(app, "beob@example.org", name="Beob Platzhalter", rechte={"wiki": 1})
            assert leser.put(f"/api/wiki/pages/{seite['id']}/watch", json={"watch": True}).status_code == 200
            post.clear()
            assert adm.post(f"/api/wiki/pages/{seite['id']}/comments", json={"body": "Platzhalter"}).status_code == 201
            texte = [t for an, _, t in post if an == "beob@example.org"]
            assert texte and f"https://strömis.de/stroemipedia/{seite['slug']}" in texte[0], texte
        finally:
            auth.send_mail, api_wiki.send_mail = alt
    # Statisch: Mail- und PDF-Links in der Anwendung bauen keinen alten Seitenpfad mehr.
    alt_link = re.compile(r"(?:\{basis\}|BASE_URL[^\n]*?\}|rstrip\('/'\)\})/(?:material|wiki|pruefungen|admin|karte)\b")
    for wurzel, _, dateien in os.walk(os.path.join(WURZEL, "app")):
        for d in dateien:
            if d.endswith(".py"):
                text = open(os.path.join(wurzel, d), encoding="utf-8").read()
                assert not alt_link.search(text), (d, alt_link.search(text).group(0))
    print("Mails bestanden.")


def _protokoll(app, tmp, pid):
    zeile = protokoll_zeile(app, pid)
    pfad = os.path.join(tmp, zeile["pdf_path"])
    with open(pfad, "rb") as fh:
        return zeile, pfad, fh.read()


def test_pdf():
    """Neue Protokolle und Lebensläufe: Kopf „Materialablage · …“, Prüfseite strömis.de/materialablage/pruefen.
    Ein Protokoll, das noch die alte Adresse trägt (wie alle vor der Umbenennung), bleibt byteweise, wie es ist, und
    lässt sich über die alte wie die neue Prüfseite prüfen."""
    from app.material.services import protokoll
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        alt_art = neuer_artikel(w, ids["hms"], gid)
        neu_art = neuer_artikel(w, ids["hms"], gid)
        # „Altes“ Protokoll: festgeschrieben, als die Prüfseite noch unter /material/pruefen lag.
        vorher = protokoll.PRUEFSEITE
        protokoll.PRUEFSEITE = "/material/pruefen"
        try:
            pid_alt = starten(p1, alt_art["id"]).json["pruefung"]["id"]
            assert festschreiben(p1, pid_alt, ergebnis="einsatzbereit").status_code == 200
        finally:
            protokoll.PRUEFSEITE = vorher
        pid = starten(p1, neu_art["id"]).json["pruefung"]["id"]
        assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
        _, pfad, daten = _protokoll(app, tmp, pid)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "materialablage/pruefen" in text and "/material/pruefen" not in text, text[-400:]
        assert "Materialablage · Prüfnachweis" in text, text[:300]
        zeile_alt, pfad_alt, daten_alt = _protokoll(app, tmp, pid_alt)
        text_alt = _flach(" ".join(pdf_seiten(pfad_alt)))
        assert "/material/pruefen" in text_alt and "materialablage/pruefen" not in text_alt
        # Das alte PDF: Download unverändert, alte Adresse führt ohne Anmeldung zur Prüfseite, die es als
        # unverändert erkennt.
        assert k["fuehrung"].get(f"/materialablage/pruefung/{pid_alt}/pdf").data == daten_alt
        assert k["fuehrung"].get(f"/material/pruefung/{pid_alt}/pdf", follow_redirects=True).data == daten_alt
        anon = app.test_client()
        r = anon.get("/material/pruefen")
        assert r.status_code == 301 and r.headers["Location"] == "/materialablage/pruefen"
        assert anon.get(r.headers["Location"]).status_code == 200
        for inhalt, pid_ in ((daten_alt, pid_alt), (daten, pid)):
            r = anon.post("/api/material/pruefen", data={"datei": (io.BytesIO(inhalt), "protokoll.pdf")}, headers=H,
                          content_type="multipart/form-data")
            assert r.status_code == 200 and r.json["ergebnis"] == "unveraendert", (pid_, r.get_json())
        # Lebenslauf: neuer Kopf und neue Prüfseite.
        r = k["fuehrung"].get(f"/materialablage/artikel/{neu_art['id']}/lebenslauf.pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        lpfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(lpfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(lpfad)))
        assert "Materialablage · Lebenslauf" in text and "materialablage/pruefen" in text, text[:300]
    print("PDF bestanden.")


def test_wiki_links():
    """F4 A: keine Datenmigration – gespeicherte Links /wiki/<slug> und neue /stroemipedia/<slug> zählen beide als
    interner Verweis („Was verlinkt hierher“)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = _app(tmp)
        adm = k["adm"]
        a = adm.post("/api/wiki/pages", json={"title": "Platzhalter A", "content": "# A\n"}).json["page"]
        b = adm.post("/api/wiki/pages", json={"title": "Platzhalter B", "content": "# B\n"}).json["page"]
        q = adm.post("/api/wiki/pages", json={"title": "Platzhalter Quelle", "content":
                     f"# Q\n\n[alt](/wiki/{a['slug']}) und [neu](/stroemipedia/{b['slug']})\n"}).json["page"]
        with app.app_context():
            from app import db
            ziele = {r["target_slug"] for r in db.query("SELECT target_slug FROM wiki_page_links WHERE page_id = ?",
                                                        (q["id"],))}
        assert ziele == {a["slug"], b["slug"]}, ziele
        # Die Seite leitet von der alten Adresse auf die neue, beide Links funktionieren damit auch als Lesezeichen.
        assert adm.get(f"/wiki/{a['slug']}").headers["Location"] == f"/stroemipedia/{a['slug']}"
        assert adm.get(f"/stroemipedia/{a['slug']}").status_code == 200
    # Browser-Code: Klickweiche, Umschreiben im öffentlichen Teil und der Editor kennen beide Schreibweisen;
    # neue Links schreibt der Editor als /stroemipedia/.
    wiki = open(os.path.join(WURZEL, "app/static/js/wiki.js"), encoding="utf-8").read()
    oeff = open(os.path.join(WURZEL, "app/static/js/public.js"), encoding="utf-8").read()
    assert "/^\\/(?:stroemipedia|wiki)\\//.test(href)" in wiki and 'urlEl.value = "/stroemipedia/" + b.dataset.slug' in wiki
    assert "a[href^=\"/stroemipedia/\"], a[href^=\"/wiki/\"]" in oeff
    # Startseite und Zurück-Taste (Browserprüfung B1): slugFromPath erkennt beide Präfixe und die Startadressen. Der
    # Ausdruck aus wiki.js, nach Python übertragen (nur „\/“ → „/“), gegen die Pfade, die der Browser zeigt.
    m = re.search(r"function slugFromPath\(\) \{ return MD\.entziffern\(location\.pathname\.replace\(/(.+?)/, \"\"\)\); \}", wiki)
    assert m, "slugFromPath nicht gefunden"
    ausdruck = re.compile(m.group(1).replace("\\/", "/"))
    for pfad, slug in (("/", ""), ("/stroemipedia", ""), ("/stroemipedia/", ""), ("/stroemipedia/demo-zwei", "demo-zwei"),
                       ("/wiki", ""), ("/wiki/alt-seite", "alt-seite")):
        assert ausdruck.sub("", pfad, count=1) == slug, (pfad, ausdruck.sub("", pfad, count=1))
    print("Wiki-Links bestanden.")


# Stellen, an denen die alten Pfade bewusst stehen: die Tabelle der Weiterleitungen und die Regeln für gespeicherte
# Wiki-Links (F4 A).
ERLAUBT = {"app/module.py", "app/api_wiki.py", "app/static/js/wiki.js", "app/static/js/public.js"}
ALT_PFAD = re.compile(r"(?<![\w/.\\-])/(?:material|wiki|pruefungen|admin|karte)(?![\w\-])")
ALT_TEXT = re.compile(r"Modul Material|öffentliches Wiki|>Wiki<|>Spots<|Zum Wiki|Material-Übersicht|"
                      r"Jahresbericht Material|Verwaltung → Einstellungen|Material → |„Material“")


def _texte_py(pfad):
    """Die Zeichenketten einer Python-Datei, die bei Nutzern ankommen können: ohne Kommentare und Docstrings und ohne
    die Pfade der Schnittstellen-Blueprints (Routen an api.*, relativ zu /api/material)."""
    import ast
    baum = ast.parse(open(pfad, encoding="utf-8").read())
    weg = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef)):
            rumpf = knoten.body
            if rumpf and isinstance(rumpf[0], ast.Expr) and isinstance(rumpf[0].value, ast.Constant):
                weg.add(id(rumpf[0].value))
            for deko in getattr(knoten, "decorator_list", []):
                if isinstance(deko, ast.Call) and isinstance(deko.func, ast.Attribute) and \
                        isinstance(deko.func.value, ast.Name) and deko.func.value.id == "api" and deko.args:
                    weg.add(id(deko.args[0]))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str) and id(knoten) not in weg:
            yield knoten.lineno, knoten.value


def _texte_js_html(pfad):
    """Zeilen einer JS- oder HTML-Datei ohne Kommentare (/* */, //, {# #}, <!-- -->) und ohne ${API}/…-Aufrufe."""
    text = open(pfad, encoding="utf-8").read()
    for muster in (r"/\*.*?\*/", r"\{#.*?#\}", r"<!--.*?-->"):
        text = re.sub(muster, lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    for nr, zeile in enumerate(text.split("\n"), 1):
        if zeile.strip().startswith("//"):
            continue
        yield nr, re.sub(r"\$\{API\}/\S*", "", zeile)


def test_statisch():
    from app import auth
    assert auth.MODULE == ("karte", "wiki", "pruefungen", "material", "verwaltung")
    from app.material.routes import api
    assert api.url_prefix == "/api/material"
    funde = []
    for wurzel, _, dateien in os.walk(os.path.join(WURZEL, "app")):
        for d in dateien:
            if not d.endswith((".py", ".js", ".html")) or "vendor" in wurzel:
                continue
            pfad = os.path.relpath(os.path.join(wurzel, d), WURZEL)
            texte = _texte_py if d.endswith(".py") else _texte_js_html
            for nr, text in texte(os.path.join(WURZEL, pfad)):
                if pfad not in ERLAUBT and ALT_PFAD.search(text.replace("media/wiki", "")):
                    funde.append(f"{pfad}:{nr}: {text.strip()[:120]}")
                # Die Meldung im Trigger des Journals (models.py) bleibt: Sie steht im Schema.
                if pfad != "app/material/models.py" and ALT_TEXT.search(text):
                    funde.append(f"{pfad}:{nr}: {text.strip()[:120]}")
    assert not funde, "\n".join(funde)
    print("Statisch bestanden.")


if __name__ == "__main__":
    test_weiterleitungen()
    test_neue_adressen_wie_die_alten()
    test_namen_in_der_oberflaeche()
    test_mails()
    test_pdf()
    test_wiki_links()
    test_statisch()
