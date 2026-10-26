"""Lesemodus des Wikis:  python tests/test_wiki_lesemodus.py  oder  pytest tests/test_wiki_lesemodus.py

Ein angemeldetes, aktives Konto ohne Stufe im Wiki („kein Zugriff“) liest im angemeldeten Bereich genau die Seiten, die
der öffentliche Teil ohne Anmeldung zeigt – mit Vererbung über „mit Unterseiten“ und den Dateien dieser Seiten – und
nicht mehr. Der Lesemodus holt alles über /api/public; die internen Schnittstellen bleiben bei wiki_required und
antworten wie bisher 403. Der Rundumtest geht dazu jede Wiki-Route der url_map durch: Nichts liefert dem Konto mehr als
einem Anonymen, und kein Merkmal einer nicht öffentlichen Seite (Titel, Inhalt, Kommentar, Datei, Bearbeiter) steht
in irgendeiner Antwort. Mitglied, Verwaltung, wartende und deaktivierte Konten bleiben, wie sie waren.

Alle Seiten, Namen und Dateien hier sind Platzhalter."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import H, jpeg, make_app  # noqa: E402

KEIN_ZUGANG = "Für dein Konto ist die Strömipedia nicht freigeschaltet."


def konto(app, adm, mail, name, rechte=None):
    """Konto anfragen, freigeben, Stufen setzen, anmelden – liefert (Client, Kennung)."""
    c = app.test_client()
    c.post("/api/auth/register", json={"email": mail, "password": "passwort1", "name": name,
                                       "gliederung": "OG Platzhalter"})
    uid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == mail][0]["id"]
    assert adm.post(f"/api/admin/users/{uid}/approve", json={}).status_code == 200
    if rechte:
        assert adm.put(f"/api/admin/users/{uid}", json={"rechte": rechte}).status_code == 200
    assert c.post("/api/auth/login", json={"email": mail, "password": "passwort1"}).status_code == 200
    return c, uid


def aufbau(tmp):
    """Ein kleines Wiki aus Platzhaltern:

    offen        selbst freigegeben; bindet die Datei datei_offen ein, verlinkt die interne Seite und baut einen
                 Abschnitt der internen Seite ein
    abschnitt    freigegeben samt Unterseiten → kind → enkel erben die Freigabe
    intern       nicht freigegeben, mit eigener Datei, Baustein, Kommentar, Bearbeiter und Verlauf
    unter_intern selbst freigegeben, aber unter der internen Seite – deren Titel darf nirgends auftauchen
    geheim       lesebeschränkt; darunter gesperrt_offen, das (Altbestand) als öffentlich markiert ist – die
                 Beschränkung wiegt schwerer
    weg          freigegeben, dann in den Papierkorb gelegt
    """
    from app import db

    app = make_app(tmp)
    adm = app.test_client()
    assert adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
    leser, leser_id = konto(app, adm, "leser@example.org", "Leserin Platzhalter", {"wiki": 0, "karte": 1})
    mitglied, mitglied_id = konto(app, adm, "mitglied@example.org", "Mitglied Platzhalter", {"wiki": 1})

    def datei(name):
        r = adm.post("/api/wiki/files", data={"file": (jpeg(False), name)}, headers=H,
                     content_type="multipart/form-data")
        assert r.status_code == 200, r.json
        return r.json["url"]

    def seite(titel, inhalt="", parent=None):
        r = adm.post("/api/wiki/pages", json={"title": titel, "content": inhalt, "parent_id": parent})
        assert r.status_code == 201, r.json
        return r.json["page"]

    def teilen(p, kinder=False):
        r = adm.put(f"/api/wiki/pages/{p['id']}/share", json={"is_public": True, "public_children": kinder})
        assert r.status_code == 200, r.json

    datei_offen, datei_intern, datei_weg = datei("platzhalter-offen.jpg"), datei("platzhalter-intern.jpg"), \
        datei("platzhalter-weg.jpg")
    intern = seite("Platzhalter Intern", "# Platzhalter Intern\n\nINTERN-MARKE Text.\n\n"
                   f"![bild]({datei_intern})\n\n:::baustein teil\nINTERN-BAUSTEIN-TEXT\n:::\n")
    adm.put(f"/api/wiki/pages/{intern['id']}", json={"content": intern["content"] + "\nINTERN-FASSUNG-ZWEI\n"})
    offen = seite("Platzhalter Offen", "# Platzhalter Offen\n\nOFFEN-MARKE Text.\n\n"
                  f"![bild]({datei_offen})\n\n[zur internen Seite](/wiki/{intern['slug']})\n\n"
                  f":::einbau {intern['slug']}#teil\n:::\n")
    teilen(offen)
    abschnitt = seite("Platzhalter Abschnitt", "ABSCHNITT-MARKE")
    teilen(abschnitt, kinder=True)
    kind = seite("Platzhalter Kind", "KIND-MARKE", abschnitt["id"])
    enkel = seite("Platzhalter Enkel", "ENKEL-MARKE", kind["id"])
    unter_intern = seite("Platzhalter Unter Intern", "UNTERSEITE-MARKE", intern["id"])
    teilen(unter_intern)
    geheim = seite("Platzhalter Geheim", "GEHEIM-MARKE")
    gesperrt_offen = seite("Platzhalter Gesperrt Offen", "GESPERRT-MARKE", geheim["id"])
    assert adm.put(f"/api/wiki/pages/{geheim['id']}/restrict", json={"read_restricted": True}).status_code == 200
    weg = seite("Platzhalter Weg", f"WEG-MARKE\n\n![bild]({datei_weg})")
    teilen(weg)
    assert adm.delete(f"/api/wiki/pages/{weg['id']}", headers=H).status_code == 200
    with app.app_context():
        # Altbestand: freigegeben unter einem beschränkten Abschnitt (heute lehnt das Teilen das ab).
        db.execute("UPDATE wiki_pages SET is_public = 1, public_children = 1 WHERE id = ?", (gesperrt_offen["id"],))
    # Kommentare (auch an der öffentlichen Seite – die zeigt der öffentliche Teil nicht), Bearbeiter, Verlauf.
    for p, text in ((intern, "KOMMENTAR-INTERN"), (offen, "KOMMENTAR-OFFEN")):
        assert adm.post(f"/api/wiki/pages/{p['id']}/comments", json={"body": text}).status_code == 201
    assert adm.put(f"/api/wiki/pages/{intern['id']}/editors", json={"user_ids": [mitglied_id]}).status_code == 200

    oeffentlich = {"offen": offen, "abschnitt": abschnitt, "kind": kind, "enkel": enkel, "unter_intern": unter_intern}
    nicht = {"intern": intern, "geheim": geheim, "gesperrt_offen": gesperrt_offen, "weg": weg}
    # Was ein Konto ohne Stufe im Wiki nie zu sehen bekommen darf.
    merkmale = ["Platzhalter Intern", "INTERN-MARKE", "INTERN-BAUSTEIN-TEXT", "INTERN-FASSUNG-ZWEI",
                "Platzhalter Geheim", "GEHEIM-MARKE", "Platzhalter Gesperrt Offen", "GESPERRT-MARKE",
                "Platzhalter Weg", "WEG-MARKE", "KOMMENTAR-INTERN", "KOMMENTAR-OFFEN",
                datei_intern.rsplit("/", 1)[1], datei_weg.rsplit("/", 1)[1],
                "Administrator", "admin@example.org", "Mitglied Platzhalter", "mitglied@example.org"]
    return dict(app=app, adm=adm, leser=leser, leser_id=leser_id, mitglied=mitglied, mitglied_id=mitglied_id,
                oeffentlich=oeffentlich, nicht=nicht, merkmale=merkmale, datei_offen=datei_offen,
                datei_intern=datei_intern, datei_weg=datei_weg)


def ohne_merkmal(antwort, merkmale, wo):
    """Kein Merkmal in der Antwort. Die Suche wiederholt ihre Suchwörter („terms“) – das ist die eigene Eingabe und
    kein Fund; geprüft wird dort alles andere."""
    if not isinstance(antwort, str):
        d = antwort.get_json(silent=True)
        antwort = (json.dumps({k: v for k, v in d.items() if k != "terms"}, ensure_ascii=False)
                   if isinstance(d, dict) else antwort.get_data(as_text=True))
    for m in merkmale:
        assert m not in antwort, f"{wo}: „{m}“ steht in der Antwort"


def test_lesen():
    """Öffentliche Seiten samt geerbter Freigabe und ihrer Datei – im angemeldeten Bereich, unter eigener Kopfleiste."""
    with tempfile.TemporaryDirectory() as tmp:
        w = aufbau(tmp)
        app, leser, oeff, nicht = w["app"], w["leser"], w["oeffentlich"], w["nicht"]
        anon = app.test_client()

        # Die Seiten des Wikis öffnen den Lesemodus: Kopfleiste, Reiter „Wiki“ aktiv, Hinweis, der öffentliche Leser.
        for adresse in ("/stroemipedia", f"/stroemipedia/{oeff['offen']['slug']}", f"/stroemipedia/{nicht['intern']['slug']}", "/stroemipedia/gibt-es-nicht"):
            r = leser.get(adresse)
            assert r.status_code == 200, adresse
            assert 'id="logout"' in r.text and '<a href="/stroemipedia" class="active">Strömipedia</a>' in r.text, adresse
            assert "Du siehst die öffentlichen Seiten der Strömipedia." in r.text and 'data-modus="lesemodus"' in r.text
            assert "js/public.js" in r.text and "js/wiki.js" not in r.text and "toastui" not in r.text
            ohne_merkmal(r.text, w["merkmale"], adresse)
        # Startseite ohne jedes Modul: der Lesemodus statt der Sackgasse; mit Spots führt sie wie bisher dorthin.
        r = leser.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/ankerplaetze")
        # Mit dem Modul Material (Vorgabe neuer Konten) führt sie dorthin, ohne jedes Modul in den Lesemodus.
        assert w["adm"].put(f"/api/admin/users/{w['leser_id']}", json={"rechte": {"karte": 0}}).status_code == 200
        r = leser.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/materialablage")
        assert w["adm"].put(f"/api/admin/users/{w['leser_id']}", json={"rechte": {"material": 0}}).status_code == 200
        r = leser.get("/")
        assert r.status_code == 302 and r.headers["Location"].endswith("/stroemipedia")
        # Der Reiter steht auch auf anderen Seiten und führt nach /stroemipedia (nicht auf die Startseite).
        assert '<a href="/stroemipedia" class="">Strömipedia</a>' in leser.get("/profil").text

        # Lesen: dieselbe Antwort wie ohne Anmeldung – selbst freigegeben, geerbt, unter interner Elternseite.
        for name, p in oeff.items():
            a, b = leser.get(f"/api/public/pages/{p['slug']}"), anon.get(f"/api/public/pages/{p['slug']}")
            assert a.status_code == 200 and a.get_data() == b.get_data(), name
            assert a.json["page"]["title"] == p["title"]
            ohne_merkmal(a, w["merkmale"], name)
        # Der Baum der geerbten Seite zeigt den Abschnitt, nicht mehr.
        baum = leser.get(f"/api/public/pages/{oeff['enkel']['slug']}").json["tree"]
        assert [t["title"] for t in baum] == ["Platzhalter Abschnitt", "Platzhalter Kind", "Platzhalter Enkel"]
        # Unter einer internen Elternseite: der Baum nennt nur die Seite selbst.
        baum = leser.get(f"/api/public/pages/{oeff['unter_intern']['slug']}").json["tree"]
        assert [t["title"] for t in baum] == ["Platzhalter Unter Intern"] and baum[0]["parent_id"] is None

        # Nicht öffentlich, beschränkt, beschränkt trotz Freigabe, im Papierkorb, unbekannt: wie ohne Anmeldung.
        for name, p in [*nicht.items(), ("unbekannt", {"slug": "gibt-es-nicht"})]:
            a, b = leser.get(f"/api/public/pages/{p['slug']}"), anon.get(f"/api/public/pages/{p['slug']}")
            assert a.status_code == 404 and a.get_data() == b.get_data(), name
            ohne_merkmal(a, w["merkmale"], name)

        # Dateien: die der öffentlichen Seite ja (wie ohne Anmeldung), die anderen wie bisher 403 (ohne Anmeldung zur Anmeldung).
        a, b = leser.get(w["datei_offen"]), anon.get(w["datei_offen"])
        assert a.status_code == 200 and b.status_code == 200 and a.get_data() == b.get_data()
        for d in (w["datei_intern"], w["datei_weg"]):
            assert leser.get(d).status_code == 403 and anon.get(d).status_code == 302, d
        # Die internen Schnittstellen bleiben zu – auch für die öffentliche Seite.
        for pfad in ("/api/wiki/tree", f"/api/wiki/pages/{oeff['offen']['slug']}", "/api/wiki/search?q=Platzhalter",
                     f"/api/wiki/pages/{oeff['offen']['id']}/attachments"):
            r = leser.get(pfad)
            assert r.status_code == 403 and r.json["error"] == KEIN_ZUGANG, pfad
    print("Lesen bestanden.")


def test_suche_und_baum():
    """Suche und Einstiegsseiten enthalten nur die öffentlichen Seiten – keine Titel nicht öffentlicher Eltern."""
    with tempfile.TemporaryDirectory() as tmp:
        w = aufbau(tmp)
        app, leser, oeff = w["app"], w["leser"], w["oeffentlich"]
        anon = app.test_client()
        for q in ("Platzhalter", "MARKE", "INTERN-MARKE", "GEHEIM-MARKE", "Text", "Intern", "Weg"):
            a, b = leser.get(f"/api/public/search?q={q}"), anon.get(f"/api/public/search?q={q}")
            assert a.status_code == 200 and a.get_data() == b.get_data(), q
            ohne_merkmal(a, w["merkmale"], q)
        treffer = {r["slug"] for r in leser.get("/api/public/search?q=Platzhalter").json["results"]}
        assert treffer == {p["slug"] for p in oeff.values()}, treffer
        assert leser.get("/api/public/search?q=INTERN-MARKE").json["results"] == []
        # „Intern“ steht im Titel der internen Seite, ihrer öffentlichen Unterseite und im Link der offenen Seite –
        # gefunden werden nur die beiden öffentlichen, nie die interne Elternseite.
        assert [r["title"] for r in leser.get("/api/public/search?q=Intern").json["results"]] == [
            "Platzhalter Offen", "Platzhalter Unter Intern"]
        # Einstiegsseiten: nur, was selbst freigegeben ist – ohne Papierkorb und ohne den beschränkten Altbestand.
        a, b = leser.get("/api/public/index"), anon.get("/api/public/index")
        assert a.get_data() == b.get_data()
        assert {p["slug"] for p in a.json["pages"]} == {oeff[k]["slug"] for k in ("offen", "abschnitt", "unter_intern")}
        ohne_merkmal(a, w["merkmale"], "index")
    print("Suche und Baum bestanden.")


# Werte für die Platzhalter der Routen: jede Kennung, die es gibt – öffentliche wie nicht öffentliche.
def _werte(w):
    from app import db
    with w["app"].app_context():
        seiten = db.query("SELECT id, slug FROM wiki_pages")
        fassungen = [r["id"] for r in db.query("SELECT id FROM wiki_revisions")]
        kommentare = [r["id"] for r in db.query("SELECT id FROM wiki_comments")]
    return {"pid": [s["id"] for s in seiten] + [9999], "rid": fassungen + [9999], "cid": kommentare + [9999],
            "slug": [s["slug"] for s in seiten] + ["gibt-es-nicht"]}


ABFRAGEN = {"wiki.search": ["?q=Platzhalter", "?q=INTERN-MARKE"], "wiki_public.public_search": [
    "?q=Platzhalter", "?q=INTERN-MARKE", "?q=Intern", "?q=GEHEIM-MARKE", "?q=WEG-MARKE"],
    "wiki.export_page": ["", "?children=1"], "wiki.get_page": ["", "?leise=1"]}


def _ohne_nonce(text):
    return re.sub(r'nonce="[^"]*"', "", text)


def test_rundum():
    """Jede Wiki-Route der url_map für ein Konto ohne Stufe im Wiki: Die internen antworten 403 wie bisher, die
    öffentlichen wortgleich wie ohne Anmeldung, die Seiten liefern nur die leere Hülle – und nirgends ein Merkmal."""
    with tempfile.TemporaryDirectory() as tmp:
        w = aufbau(tmp)
        app, leser, mitglied = w["app"], w["leser"], w["mitglied"]
        anon = app.test_client()
        werte = _werte(w)
        geprueft, anzahl = set(), 0
        for regel in app.url_map.iter_rules():
            ep = regel.endpoint
            wiki = ep.startswith(("wiki.", "wiki_public.")) or ep in (
                "pages.wiki", "pages.wiki_page", "pages.public_index", "pages.public_page", "pages.media")
            if not wiki:
                continue
            geprueft.add(ep)
            unbekannt = set(regel.arguments) - {"pid", "rid", "cid", "slug", "kind", "filename"}
            assert not unbekannt, f"{regel.rule}: neue Platzhalter {unbekannt} – Werte in _werte ergänzen"
            if ep == "pages.media":
                continue                                              # eigener Block unten (Dateien)
            namen = sorted(regel.arguments)
            belegungen = [{}] if not namen else [{namen[0]: v} for v in werte[namen[0]]]
            assert len(namen) <= 1, regel.rule
            for methode in sorted(regel.methods - {"HEAD", "OPTIONS"}):
                for belegung in belegungen:
                    for abfrage in ABFRAGEN.get(ep, [""]):
                        url = regel.build(belegung, append_unknown=False)[1] + abfrage
                        rumpf = {} if methode == "GET" else {"json": {}}
                        a, b = (c.open(url, method=methode, headers=H, **rumpf) for c in (leser, anon))
                        anzahl += 1
                        text = a.get_data(as_text=True)
                        ohne_merkmal(a, w["merkmale"], f"{methode} {url}")
                        if ep.startswith("wiki."):
                            # Intern: wie bisher – wiki_required, bevor irgendetwas gelesen oder geschrieben wird.
                            assert a.status_code == 403 and a.json == {"error": KEIN_ZUGANG}, (methode, url, a.status_code)
                            assert b.status_code == 401, (methode, url, b.status_code)
                        elif ep.startswith("wiki_public."):
                            # Öffentlich: Byte für Byte, was auch ohne Anmeldung kommt.
                            assert (a.status_code, a.get_data()) == (b.status_code, b.get_data()), (methode, url)
                        elif ep in ("pages.public_index", "pages.public_page"):
                            assert a.status_code == b.status_code == 200
                            assert _ohne_nonce(text) == _ohne_nonce(b.get_data(as_text=True)), url
                        else:
                            # /stroemipedia und /stroemipedia/<slug>: die Hülle des Lesemodus – der Inhalt kommt über /api/public.
                            assert a.status_code == 200 and 'data-modus="lesemodus"' in text, url
                            assert b.status_code == 302 and "/login" in b.headers["Location"], url
        assert geprueft >= {"wiki.tree", "wiki.get_page", "wiki.update_page", "wiki.trash", "wiki.purge_page",
                            "wiki.revisions", "wiki.get_revision", "wiki.restore_revision", "wiki.bausteine",
                            "wiki.templates", "wiki.upload_file", "wiki.reorder", "wiki.set_share",
                            "wiki_public.public_page", "wiki_public.public_search", "wiki_public.public_index",
                            "pages.wiki", "pages.wiki_page", "pages.media"}, geprueft
        assert anzahl > 250, anzahl
        # Gegenprobe: Die Werte taugen – ein Mitglied kommt mit denselben Kennungen an die internen Seiten.
        assert mitglied.get(f"/api/wiki/pages/{w['nicht']['intern']['slug']}").status_code == 200
        assert mitglied.get(f"/api/wiki/pages/{w['nicht']['intern']['id']}/revisions").status_code == 200

        # Dateien: öffentlich wie ohne Anmeldung, alles andere wie bisher (403 angemeldet, ohne Anmeldung zur Anmeldung).
        from app import db
        with app.app_context():
            dateien = [r["file"] for r in db.query("SELECT file FROM wiki_files")]
        oeffentliche = {w["datei_offen"].rsplit("/", 1)[1]}
        assert len(dateien) == 3
        for datei in dateien:
            a, b = leser.get(f"/media/wiki/{datei}"), anon.get(f"/media/wiki/{datei}")
            if datei in oeffentliche:
                assert a.status_code == b.status_code == 200 and a.get_data() == b.get_data(), datei
            else:
                assert (a.status_code, b.status_code) == (403, 302), datei
    print(f"Rundumtest bestanden ({anzahl} Aufrufe).")


def test_unveraendert():
    """Mitglied und Verwaltung arbeiten im Wiki wie bisher; wartende und deaktivierte Konten kommen nicht hinein."""
    with tempfile.TemporaryDirectory() as tmp:
        w = aufbau(tmp)
        app, adm, mitglied, intern = w["app"], w["adm"], w["mitglied"], w["nicht"]["intern"]
        for c, name in ((mitglied, "Mitglied"), (adm, "Verwaltung")):
            r = c.get("/stroemipedia")
            assert r.status_code == 200 and "js/wiki.js" in r.text and 'data-modus="lesemodus"' not in r.text, name
            assert "Du siehst die öffentlichen Seiten" not in r.text, name
            assert '<a href="/" class="active">Strömipedia</a>' in r.text, name
            assert c.get("/").status_code == 200, name
            assert intern["slug"] in {p["slug"] for p in c.get("/api/wiki/tree").json["pages"]}, name
            assert c.get(f"/api/wiki/pages/{intern['slug']}").status_code == 200, name
            assert c.get("/api/wiki/search?q=INTERN-MARKE").json["results"], name
        assert mitglied.post("/api/wiki/pages", json={"title": "Platzhalter Mitglied"}).status_code == 201

        # Wartend: keine Anmeldung, keine Sitzung – /stroemipedia führt zur Anmeldung, die Schnittstelle sagt 401.
        c = app.test_client()
        c.post("/api/auth/register", json={"email": "wartet@example.org", "password": "passwort1", "name": "Wartend",
                                           "gliederung": "OG Platzhalter"})
        assert c.post("/api/auth/login", json={"email": "wartet@example.org", "password": "passwort1"}).status_code == 403
        r = c.get("/stroemipedia")
        assert r.status_code == 302 and r.headers["Location"].startswith("/login"), r.status_code
        assert c.get("/api/wiki/tree").status_code == 401

        # Deaktiviert: die laufende Sitzung verfällt, der Lesemodus mit ihr.
        leser = w["leser"]
        assert leser.get("/stroemipedia").status_code == 200
        assert adm.put(f"/api/admin/users/{w['leser_id']}", json={"active": False}).status_code == 200
        r = leser.get("/stroemipedia")
        assert r.status_code == 302 and r.headers["Location"].startswith("/login"), r.status_code
        assert leser.get("/api/wiki/tree").status_code == 401

        # Ohne Anmeldung: wie bisher zur Anmeldung, der öffentliche Teil bleibt offen.
        anon = app.test_client()
        assert anon.get("/stroemipedia").status_code == 302 and anon.get("/").status_code == 302
        assert anon.get(f"/api/public/pages/{w['oeffentlich']['offen']['slug']}").status_code == 200
        assert anon.get("/oeffentlich/").status_code == 200
    print("Unverändert bestanden.")


def test_keine_post():
    """Wem die Stufe im Wiki genommen wird, der bekommt zu beobachteten Seiten keine Nachrichten mehr – auch nicht zu
    öffentlichen: Der öffentliche Teil verschickt keine, und Titel wie Bearbeiter interner Seiten kämen sonst per Post."""
    from app import api_wiki
    with tempfile.TemporaryDirectory() as tmp:
        w = aufbau(tmp)
        adm, mitglied = w["adm"], w["mitglied"]
        seiten = (w["oeffentlich"]["offen"], w["nicht"]["intern"])
        for p in seiten:
            assert mitglied.put(f"/api/wiki/pages/{p['id']}/watch", json={"watch": True}).json["watch"] is True
        post = []

        def kommentieren():
            post.clear()
            for p in seiten:
                r = adm.post(f"/api/wiki/pages/{p['id']}/comments", json={"body": "Platzhalterkommentar"})
                assert r.status_code == 201
            return sorted(betreff for an, betreff in post if an == "mitglied@example.org")

        bisher = api_wiki.send_mail
        api_wiki.send_mail = lambda an, betreff, text: post.append((an, betreff))
        try:
            assert len(kommentieren()) == 2                       # als Mitglied: zu beiden Seiten
            assert adm.put(f"/api/admin/users/{w['mitglied_id']}", json={"rechte": {"wiki": 0}}).status_code == 200
            assert kommentieren() == []                           # ohne Stufe: zu keiner
            assert adm.put(f"/api/admin/users/{w['mitglied_id']}", json={"rechte": {"wiki": 1}}).status_code == 200
            assert len(kommentieren()) == 2                       # wieder Mitglied: wie vorher
        finally:
            api_wiki.send_mail = bisher
    print("Keine Post bestanden.")


if __name__ == "__main__":
    test_lesen()
    test_suche_und_baum()
    test_rundum()
    test_unveraendert()
    test_keine_post()
