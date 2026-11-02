"""Startseite über alle Module (02.11.2026, Auftrag planung/startseite/auftrag_startseite.md):
python tests/test_module_startseite.py  oder  pytest tests/test_module_startseite.py

  1. Route und Navigation: „/“ zeigt die Startseite (Logo dorthin, kein Reiter aktiv, „Strömipedia“ nach /stroemipedia),
     ohne Anmeldung zur Anmeldung, nach der Anmeldung „/“ (ein next geht vor), ohne jeden Bereich die Hinweisseite;
     Fehlerseiten führen „Zur Startseite“, die PWA startet auf „/“.
  2. Rechte je Rolle: kein Modul, Lesemodus, Mitglied, Redakteur, Verwaltung der Module, Plattform-Verwaltung,
     Materialwart, Prüfer – jede Kachel, jeder Titel und jeder Link nur aus dem, was das Konto sieht.
  3. Die Zahlen der Materialablage sind die der Übersicht (GET /api/material/start).
  4. „Zuletzt besucht“: Alben, Lehrgänge, Artikel und Seiten; Gelöschtes und nicht mehr Sichtbares fällt weg; höchstens 20
     gemerkt; mit dem Konto gelöscht.
  5. „Neu seit deinem letzten Besuch“: Vergleich mit dem vorigen Besuch, stabil innerhalb eines Besuchs, eigene Änderungen
     zählen nicht; der Merker schreibt nur mit dem CSRF-Schutz der Schnittstelle.
  6. Abschnitte der Strömipedia als Karten (Startseite, Übersicht, Lesemodus), Suchfeld der Startseite.
Alle Inhalte sind Platzhalter."""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, freigeben, neues_konto  # noqa: E402
from test_material_meine_psa import aufbau, melden, post_mangel, zuordnen  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import zustand  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def module_von(c):
    r = c.get("/api/start")
    assert r.status_code == 200, r.get_json()
    return [k["modul"] for k in r.json["kacheln"]], r.json


def kachel(d, modul):
    return next(k for k in d["kacheln"] if k["modul"] == modul)


def zahlen(k):
    return {z["art"]: z["zahl"] for z in k["zeilen"]}


def seite(adm, titel, parent=None, inhalt="Platzhalter"):
    r = adm.post("/api/wiki/pages", json={"title": titel, "content": inhalt, "parent_id": parent})
    assert r.status_code == 201, r.get_json()
    return r.json["page"]


def lehrgang(c, titel, status="laufend", ausbilder=()):
    r = c.post("/api/pruefungen/lehrgaenge", json={"titel": titel, "status": status,
                                                   "ausbilder": [{"user_id": u, "funktion": "Platzhalter"} for u in ausbilder]})
    assert r.status_code == 201, r.get_json()
    return r.json["lehrgang"]


def album(c, titel):
    r = c.post("/api/albums", json={"title": titel})
    assert r.status_code == 201, r.get_json()
    return r.json["album"]


def rechte(adm, uid, **stufen):
    r = adm.put(f"/api/admin/users/{uid}", json={"rechte": stufen})
    assert r.status_code == 200, r.get_json()


def merker(app, uid):
    return {z["schluessel"]: json.loads(z["wert"]) for z in zeilen(
        app, "SELECT schluessel, wert FROM mat_meta WHERE schluessel IN (?, ?)", (f"start:besuch:{uid}", f"start:ziele:{uid}"))}


# --- 1. Route und Navigation ---------------------------------------------------------------------------------------

def test_route_und_navigation():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        anon = t.app.test_client()
        r = anon.get("/")
        assert r.status_code == 302 and "/login?next=/" in r.headers["Location"], r.headers
        html = t.adm.get("/").get_data(as_text=True)
        assert 'id="start-inhalt"' in html and "js/start.js" in html and "<title>Start – strömis.de</title>" in html
        assert '<a class="brand" href="/">' in html
        # Kein Reiter ist aktiv, „Strömipedia“ führt zur Strömipedia – für Stufe und Lesemodus.
        nav = html[html.index('<nav class="nav"'):html.index("</nav>")]
        assert 'class="active"' not in nav, nav
        assert '<a href="/stroemipedia" class="">Strömipedia</a>' in nav and 'href="/"' not in nav
        assert '<a href="/stroemipedia" class="">Strömipedia</a>' in t.person.get("/").get_data(as_text=True)
        assert '<a href="/stroemipedia" class="active">Strömipedia</a>' in t.adm.get("/stroemipedia").get_data(as_text=True)
        # Die Strömipedia selbst liegt unverändert unter /stroemipedia (Stufe: wiki.html, ohne: Lesemodus).
        assert 'id="wiki-search"' in t.adm.get("/stroemipedia").get_data(as_text=True)
        assert 'data-modus="lesemodus"' in t.person.get("/stroemipedia").get_data(as_text=True)
        # Alte Lesezeichen: „/“ bleibt gültig, /wiki/ führt weiter in die Strömipedia.
        assert t.adm.get("/").status_code == 200 and t.adm.get("/wiki").headers["Location"] == "/stroemipedia"
        # Anmeldung: ohne next nach „/“, mit next dorthin; schon angemeldet springt /login gleich zum Ziel.
        assert 'data-next="/"' in anon.get("/login").get_data(as_text=True)
        assert 'data-next="/ankerplaetze"' in anon.get("/login?next=/ankerplaetze").get_data(as_text=True)
        assert t.adm.get("/login").headers["Location"] == "/"
        assert t.adm.get("/login?next=/riegenkarten").headers["Location"] == "/riegenkarten"
        js = lies("app/static/js/auth.js")
        assert 'const next = shell.dataset.next || "/";' in js
        # PWA: Start auf „/“, der Kurzbefehl „Strömipedia“ zur Strömipedia.
        m = anon.get("/manifest.webmanifest").get_json(force=True)
        assert m["start_url"] == "/" and {k["name"]: k["url"] for k in m["shortcuts"]}["Strömipedia"] == "/stroemipedia"
        # Fehlerseiten: „Zur Startseite“ (mit Anmeldung und ohne).
        assert '<a href="/">Zur Startseite</a>' in t.adm.get("/gibt-es-nicht").get_data(as_text=True)
        assert '<a href="/">Zur Startseite</a>' in anon.get("/gibt-es-nicht").get_data(as_text=True)
        assert "Zur Strömipedia" not in lies("app/templates/error.html")
        # Ohne jeden Bereich (kein Modul, nicht einmal der Lesemodus – hier: Status ungleich „active“ bei offener Sitzung)
        # bleibt die Hinweisseite, mit dem Weg ins Profil.
        sql(t.app, "UPDATE users SET status = 'gesperrt' WHERE id = ?", (t.person2_id,))
        r = t.person2.get("/")
        text = r.get_data(as_text=True)
        assert r.status_code == 403 and "Für dein Konto ist noch kein Bereich freigeschaltet." in text, text[-800:]
        assert '<a href="/profil">Zum Profil</a>' in text and t.person2.get("/api/start").status_code == 403
    print("Route und Navigation bestanden.")


# --- 2. Rechte je Rolle ----------------------------------------------------------------------------------------------

def test_rechte_je_rolle():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm, app = t.adm, t.app
        # Strömipedia: offen (für alle Angemeldeten freigegeben samt Unterseiten), intern, beschränkt.
        offen = seite(adm, "Platzhalter Offen")
        unter_offen = seite(adm, "Platzhalter Offen Unterseite", offen["id"])
        assert adm.put(f"/api/wiki/pages/{offen['id']}/share", json={"is_public": True, "public_children": True}).status_code == 200
        intern = seite(adm, "Platzhalter Intern")
        geheim = seite(adm, "Platzhalter Geheim")
        assert adm.put(f"/api/wiki/pages/{geheim['id']}/restrict", json={"read_restricted": True}).status_code == 200
        geheim_unter = seite(adm, "Platzhalter Geheim Unterseite", geheim["id"])
        alb = album(adm, "Platzhalter Album")
        # Konten je Rolle (Name immer gesetzt – ohne Namen kein Modulzugang in der Materialablage).
        kein, kein_id = neues_konto(app, "kein@example.org", name="Kein Modul", stufe=0)
        lese, lese_id = neues_konto(app, "lese@example.org", name="Lesemodus Karte", stufe=0, rechte={"karte": 1})
        mitglied, mitglied_id = neues_konto(app, "mitglied2@example.org", name="Mitglied Alle",
                                            rechte={"wiki": 1, "karte": 1, "pruefungen": 1, "material": 1})
        red, red_id = neues_konto(app, "red@example.org", name="Redakteur Alle",
                                  rechte={"wiki": 2, "karte": 2, "pruefungen": 2, "material": 1})
        modv, modv_id = neues_konto(app, "modv@example.org", name="Verwaltung Module",
                                    rechte={"wiki": 3, "karte": 3, "pruefungen": 3, "material": 3})
        eigen = lehrgang(red, "Platzhalter Lehrgang Redakteur")                 # Redakteur wird Leitung
        fremd = lehrgang(adm, "Platzhalter Lehrgang Fremd")
        # Eine offene Kontoanfrage für die Kachel der Leitstelle – direkt eingetragen (die Anfrage schickte eine Mail).
        sql(app, "INSERT INTO users (email, password_hash, name, active, status, created_at) VALUES "
                 "('anfrage@example.org', 'x', 'Anfrage Platzhalter', 0, 'pending', '2026-11-01T10:00:00+00:00')")

        def nichts_fremdes(d, verboten):
            text = json.dumps(d, ensure_ascii=False)
            for v in verboten:
                assert v not in text, (v, text[:2000])

        geheim_titel = ("Platzhalter Geheim",)
        intern_titel = ("Platzhalter Intern",)
        # Kein Modul = Lesemodus: nur die Strömipedia mit den freigegebenen Seiten.
        mods, d = module_von(kein)
        assert mods == ["wiki"] and d["lesemodus"] is True, mods
        assert zahlen(kachel(d, "wiki")) == {"seiten_frei": 2}
        assert [a["title"] for a in d["abschnitte"]] == ["Platzhalter Offen"] and d["abschnitte"][0]["seiten"] == 2
        nichts_fremdes(d, geheim_titel + intern_titel + ("Platzhalter Album", "Lehrgang", "/ankerplaetze", "/riegenkarten",
                                                        "/materialablage", "/leitstelle"))
        assert 'name="suche"' in kein.get("/").get_data(as_text=True)
        # Lesemodus mit Ankerplätzen.
        mods, d = module_von(lese)
        assert mods == ["wiki", "karte"] and zahlen(kachel(d, "karte")) == {"alben": 1}
        nichts_fremdes(d, geheim_titel + intern_titel + ("Lehrgang", "/riegenkarten", "/materialablage", "/leitstelle"))
        # Mitglied überall: alle Module außer der Leitstelle; Riegenkarten ohne fremde Lehrgänge, die Materialablage ohne
        # Bestand (keine Freigabe).
        mods, d = module_von(mitglied)
        assert mods == ["wiki", "karte", "pruefungen", "material"], mods
        assert zahlen(kachel(d, "wiki")) == {"seiten": 3}                       # alles außer der beschränkten Seite samt Unterseite
        assert kachel(d, "pruefungen")["zeilen"] == [] and kachel(d, "pruefungen")["ruhig"] == "Kein laufender Lehrgang."
        assert kachel(d, "material") == {"modul": "material", "name": "Materialablage", "pfad": "/materialablage",
                                         "zeilen": [], "ruhig": "Für dich ist noch kein Bestand freigegeben."}
        nichts_fremdes(d, geheim_titel + ("Platzhalter Lehrgang", "/leitstelle"))
        # Redakteur: der eigene Lehrgang, nicht der fremde.
        mods, d = module_von(red)
        assert mods == ["wiki", "karte", "pruefungen", "material"]
        assert zahlen(kachel(d, "pruefungen")) == {"laufend": 1}
        assert kachel(d, "pruefungen")["zeilen"][0]["href"] == f"/riegenkarten/{eigen['id']}"
        assert [e["titel"] for e in d["neu"] if e["modul"] == "pruefungen"] == ["Platzhalter Lehrgang Redakteur"]
        nichts_fremdes(d, geheim_titel + ("Platzhalter Lehrgang Fremd", "/leitstelle"))
        # Verwaltung der Module (ohne Plattform-Verwaltung): alles in den Modulen, keine Leitstelle.
        mods, d = module_von(modv)
        assert mods == ["wiki", "karte", "pruefungen", "material"]
        assert zahlen(kachel(d, "pruefungen")) == {"laufend": 2} and zahlen(kachel(d, "wiki")) == {"seiten": 5}
        nichts_fremdes(d, ("/leitstelle", "Kontoanfrage"))
        # Plattform-Verwaltung: alle fünf, die Leitstelle mit der offenen Kontoanfrage.
        mods, d = module_von(adm)
        assert mods == ["wiki", "karte", "pruefungen", "material", "verwaltung"], mods
        assert kachel(d, "verwaltung")["zeilen"] == [{"art": "anfragen", "zahl": 1, "href": "/leitstelle#pending"}]
        assert {a["title"] for a in d["abschnitte"]} == {"Platzhalter Offen", "Platzhalter Intern", "Platzhalter Geheim"}
        # Materialwart und Prüfer der Gliederung: Bestand, keine Riegenkarten, keine Leitstelle.
        for c in (t.w, t.k["pruefer"]):
            mods, d = module_von(c)
            assert mods == ["wiki", "material"], mods
            # Drei neue Artikel warten auf die Eingangsprüfung – wie die Statuskachel „neu“ der Übersicht.
            assert zahlen(kachel(d, "material")) == {"neu": 3}
            assert kachel(d, "material")["zeilen"][0]["href"] == "/materialablage/pruefungen?status=neu#zu-pruefen"
            nichts_fremdes(d, geheim_titel + intern_titel + ("/riegenkarten", "/leitstelle"))
        # „Meine PSA“ ohne Modulzugang: eine eigene Kachel, kein Bestand.
        zuordnen(t, t.art[0], t.person_id)
        mods, d = module_von(t.person)
        assert mods == ["wiki", "meine_psa"], mods
        assert kachel(d, "meine_psa")["name"] == "Meine PSA" and kachel(d, "meine_psa")["pfad"] == "/materialablage/meine-psa"
        assert zahlen(kachel(d, "meine_psa")) == {"psa": 1, "psa_dringend": 1}  # neu (ohne Prüfung) zählt als nicht einsatzbereit
        # Zuletzt besucht: Was ein Konto nicht sieht, wird gar nicht erst gemerkt – fremder Lehrgang (404), beschränkte
        # Seite (403), fremder Artikel (404).
        assert red.get(f"/riegenkarten/{fremd['id']}").status_code == 404
        assert mitglied.get(f"/api/wiki/pages/{geheim_unter['slug']}").status_code == 403
        assert mitglied.get(f"/materialablage/artikel/{t.art[1]}").status_code == 404
        assert merker(app, red_id) == {} and merker(app, mitglied_id) == {}
        assert not zeilen(app, "SELECT 1 FROM wiki_views WHERE user_id = ?", (mitglied_id,))
        assert unter_offen and alb and intern and kein_id and lese_id and modv_id
    print("Rechte je Rolle bestanden.")


# --- 3. Zahlen der Materialablage = Übersicht -------------------------------------------------------------------------

def test_zahlen_materialablage_wie_uebersicht():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        heute = datetime.now(timezone.utc).date()
        # Ein Artikel überfällig, einer bald fällig, einer mit Mangel.
        zustand(t.app, t.art[0], last_inspected_on=(heute - timedelta(days=400)).isoformat(),
                next_due_on=(heute - timedelta(days=5)).isoformat())
        zustand(t.app, t.art[1], last_inspected_on=(heute - timedelta(days=350)).isoformat(),
                next_due_on=(heute + timedelta(days=10)).isoformat())
        with post_mangel():
            assert melden(t.k["fuehrung"], t.art[2]).status_code == 201
        for c in (t.adm, t.w, t.k["pruefer"], t.k["fuehrung"], t.k["katalog"]):
            u = c.get("/api/material/start").json
            k = kachel(c.get("/api/start").json, "material")
            soll = {"ueberfaellig": u["zaehlung"]["ueberfaellig"], "neu": u["zaehlung"]["neu"],
                    "bald_faellig": u["zaehlung"]["bald_faellig"], "maengel": u["maengel_gesamt"],
                    "antraege": u["antraege_offen"]}
            assert zahlen(k) == {a: n for a, n in soll.items() if n}, (zahlen(k), soll)
            assert zahlen(k)["ueberfaellig"] == 1 and zahlen(k)["bald_faellig"] == 1 and zahlen(k)["maengel"] == 1
            z = {x["art"]: x for x in k["zeilen"]}
            assert z["ueberfaellig"]["href"] == "/materialablage/pruefungen?status=ueberfaellig#zu-pruefen"
            assert z["bald_faellig"]["href"] == "/materialablage/pruefungen?status=bald_faellig#zu-pruefen"
            assert z["bald_faellig"]["tage"] == u["schwelle_tage"] and z["maengel"]["href"] == "/materialablage"
        # Die Kachel ruft dieselben Dienste wie die Übersicht – nichts ist neu gerechnet.
        quelle = lies("app/start.py")
        for aufruf in ("bestand.zaehlung()", "mangel.anzahl_offen()", "antrag.zu_entscheiden(user)", "psa.kurz(user)"):
            assert aufruf in quelle, aufruf
        assert "gesamt = anzahl_offen()" in lies("app/material/services/mangel.py")
        # Ohne Bestand (Mitglied ohne Freigabe) die eigene PSA.
        zuordnen(t, t.art[0], t.mitglied_id)
        k = kachel(t.mitglied.get("/api/start").json, "material")
        assert zahlen(k) == {"psa": 1, "psa_dringend": 1} and k["zeilen"][0]["href"] == "/materialablage/meine-psa"
    print("Zahlen der Materialablage wie die Übersicht bestanden.")


# --- 4. Zuletzt besucht ----------------------------------------------------------------------------------------------

def test_zuletzt_besucht():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm, app = t.adm, t.app
        u, uid = neues_konto(app, "besucher@example.org", name="Besucher Platzhalter",
                             rechte={"wiki": 1, "karte": 1, "pruefungen": 1, "material": 1})
        freigeben(adm, t.gid, uid, "lesen")
        s = seite(adm, "Platzhalter Seite")
        a = album(adm, "Platzhalter Album Besuch")
        lg = lehrgang(adm, "Platzhalter Lehrgang Besuch", ausbilder=[uid])
        assert u.get(f"/api/wiki/pages/{s['slug']}").status_code == 200
        assert u.get(f"/api/albums/{a['id']}").status_code == 200
        assert u.get(f"/riegenkarten/{lg['id']}").status_code == 200
        assert u.get(f"/materialablage/artikel/{t.art[0]}").status_code == 200
        d = u.get("/api/start").json
        assert {e["modul"] for e in d["zuletzt"]} == {"wiki", "karte", "pruefungen", "material"}, d["zuletzt"]
        z = {e["modul"]: e for e in d["zuletzt"]}
        assert z["karte"]["href"] == f"/ankerplaetze#album={a['id']}" and z["pruefungen"]["href"] == f"/riegenkarten/{lg['id']}"
        assert z["material"]["href"] == f"/materialablage/artikel/{t.art[0]}" and z["material"]["titel"].startswith("M-")
        assert z["material"]["zusatz"] == "Testwerk HMS Beta" and z["wiki"]["titel"] == "Platzhalter Seite"
        assert all(e["modulname"] for e in d["zuletzt"])
        # Leise Abrufe (Einbau, Nachziehen) sind kein Besuch.
        s2 = seite(adm, "Platzhalter Leise")
        assert u.get(f"/api/wiki/pages/{s2['slug']}?leise=1").status_code == 200
        assert "Platzhalter Leise" not in json.dumps(u.get("/api/start").json["zuletzt"])
        # Was nicht mehr sichtbar oder gelöscht ist, fällt weg – beim Zeigen neu gefiltert.
        assert adm.delete(f"/api/albums/{a['id']}", headers=H).status_code == 200
        sql(app, "DELETE FROM pruef_ausbilder WHERE lehrgang_id = ? AND user_id = ?", (lg["id"], uid))
        sql(app, "DELETE FROM mat_folder_grant WHERE user_id = ?", (uid,))
        from app.material.services import rechte as mat_rechte
        with app.app_context():
            mat_rechte.sicht_verwerfen()
        assert adm.put(f"/api/wiki/pages/{s['id']}/restrict", json={"read_restricted": True}).status_code == 200
        assert u.get("/api/start").json["zuletzt"] == []
        # Ohne Stufe in den Riegenkarten fällt auch ein Lehrgang weg, in dem das Konto (noch) steht.
        lg2 = lehrgang(adm, "Platzhalter Lehrgang Zwei", ausbilder=[uid])
        assert u.get(f"/riegenkarten/{lg2['id']}").status_code == 200
        assert [e["titel"] for e in u.get("/api/start").json["zuletzt"]] == ["Platzhalter Lehrgang Zwei"]
        rechte(adm, uid, pruefungen=0)
        assert u.get("/api/start").json["zuletzt"] == []
        # Höchstens 20 gemerkt, neueste zuerst, jedes Ziel nur einmal.
        rechte(adm, uid, karte=1)
        alben = [album(adm, f"Platzhalter Album {n:02d}") for n in range(25)]
        for x in alben:
            u.get(f"/api/albums/{x['id']}")
        u.get(f"/api/albums/{alben[3]['id']}")
        ziele = merker(app, uid)[f"start:ziele:{uid}"]
        assert len(ziele) == 20 and ziele[0][:2] == ["karte", alben[3]["id"]]
        assert len({(z[0], z[1]) for z in ziele}) == 20
        d = u.get("/api/start").json
        assert len(d["zuletzt"]) == 8 and d["zuletzt"][0]["titel"] == "Platzhalter Album 03"
        # Mit dem Konto gehen beide Merker.
        assert u.post("/api/start/besuch", json={}).status_code == 200
        assert set(merker(app, uid)) == {f"start:besuch:{uid}", f"start:ziele:{uid}"}
        assert adm.delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        assert merker(app, uid) == {}
    print("Zuletzt besucht bestanden.")


# --- 5. Neu seit dem letzten Besuch ----------------------------------------------------------------------------------

def test_neu_seit_besuch():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm, app = t.adm, t.app
        u, uid = neues_konto(app, "neu@example.org", name="Neu Platzhalter", rechte={"wiki": 2, "karte": 2})
        seite(adm, "Platzhalter Alt")
        # Erster Besuch: kein Vergleichspunkt, keine „neu“-Zeilen.
        d = u.get("/api/start").json
        assert d["seit"] is None and set(zahlen(kachel(d, "wiki"))) == {"seiten"}
        # Der Merker schreibt nur aus eigenem Skript (CSRF-Schutz der Schnittstelle).
        assert u.post("/api/start/besuch").status_code == 403
        assert u.post("/api/start/besuch", json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert u.get("/api/start/besuch").status_code == 405
        assert app.test_client().post("/api/start/besuch", json={}).status_code == 401
        # Der vorige Besuch liegt zwei Stunden zurück: was seitdem andere angelegt haben, zählt.
        jetzt = datetime.now(timezone.utc).replace(microsecond=0)
        vor = (jetzt - timedelta(hours=2)).isoformat()
        sql(app, "INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?)",
            (f"start:besuch:{uid}", json.dumps({"bisher": (jetzt - timedelta(days=3)).isoformat(), "zuletzt": vor})))
        sql(app, "UPDATE wiki_pages SET created_at = ?, updated_at = ?", ((jetzt - timedelta(days=1)).isoformat(),) * 2)
        neu1 = seite(adm, "Platzhalter Neu Eins")
        x = album(adm, "Platzhalter Album Neu")
        eigene = seite(u, "Platzhalter Eigene")                                   # eigene Änderung: zählt nicht
        d = u.get("/api/start").json
        assert d["seit"] == vor
        w = {z["art"]: z for z in kachel(d, "wiki")["zeilen"]}
        assert w["wiki_neu"]["zahl"] == 1 and w["wiki_neu"]["href"] == f"/stroemipedia/{neu1['slug']}", w
        assert zahlen(kachel(d, "karte")) == {"alben": 1, "alben_neu": 1}
        assert kachel(d, "karte")["zeilen"][1]["href"] == f"/ankerplaetze#album={x['id']}"
        # Besuch merken: Innerhalb des Besuchs (weniger als 30 Minuten) bleibt der Vergleichspunkt – dieselben Zahlen.
        assert u.post("/api/start/besuch", json={}).status_code == 200
        b = merker(app, uid)[f"start:besuch:{uid}"]
        assert b["bisher"] == vor and b["zuletzt"] >= jetzt.isoformat()
        seite(adm, "Platzhalter Neu Zwei")
        d = u.get("/api/start").json
        assert d["seit"] == vor and zahlen(kachel(d, "wiki"))["wiki_neu"] == 2
        assert u.post("/api/start/besuch", json={}).status_code == 200
        assert merker(app, uid)[f"start:besuch:{uid}"]["bisher"] == vor
        # Nach der Pause beginnt ein neuer Besuch: Vergleichspunkt ist der letzte Aufruf, das Neue von eben ist alt.
        lange = (jetzt - timedelta(minutes=45)).isoformat()
        sql(app, "UPDATE mat_meta SET wert = ? WHERE schluessel = ?",
            (json.dumps({"bisher": vor, "zuletzt": lange}), f"start:besuch:{uid}"))
        sql(app, "UPDATE wiki_pages SET created_at = ?, updated_at = ?", ((jetzt - timedelta(hours=1)).isoformat(),) * 2)
        sql(app, "UPDATE albums SET created_at = ?, updated_at = ?", ((jetzt - timedelta(hours=1)).isoformat(),) * 2)
        d = u.get("/api/start").json
        assert d["seit"] == lange and set(zahlen(kachel(d, "wiki"))) == {"seiten"}
        assert kachel(d, "karte")["zeilen"] == [{"art": "alben", "zahl": 1, "href": "/ankerplaetze"}]
        assert eigene
    print("Neu seit dem letzten Besuch bestanden.")


# --- 6. Abschnitte als Karten, Suchfeld ------------------------------------------------------------------------------

def test_abschnitte_und_suche():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm = t.adm
        oben = seite(adm, "Platzhalter Abschnitt")
        kinder = [seite(adm, f"Platzhalter Kind {n}", oben["id"]) for n in range(8)]
        enkel = seite(adm, "Platzhalter Enkel", kinder[0]["id"])
        geheim = seite(adm, "Platzhalter Kind Geheim", oben["id"])
        assert adm.put(f"/api/wiki/pages/{oben['id']}/share", json={"is_public": True, "public_children": True}).status_code == 200
        # Beschränkt unter einem freigegebenen Abschnitt lässt die Oberfläche nicht zu – als Altbestand direkt gesetzt.
        sql(t.app, "UPDATE wiki_pages SET read_restricted = 1 WHERE id = ?", (geheim["id"],))
        seite(adm, "Platzhalter Zweiter Abschnitt")
        mitglied, _ = neues_konto(t.app, "wikimitglied@example.org", name="Wiki Mitglied", rechte={"wiki": 1})
        # Startseite, Stufe: die obersten Abschnitte mit Zahl (Abschnitt + alles darunter, soweit lesbar) und drei Unterseiten.
        d = mitglied.get("/api/start").json
        a = d["abschnitte"][0]
        assert a["title"] == "Platzhalter Abschnitt" and a["seiten"] == 1 + 8 + 1 and a["kinder"] == 8, a
        assert [x["title"] for x in a["unterseiten"]] == ["Platzhalter Kind 0", "Platzhalter Kind 1", "Platzhalter Kind 2"]
        assert d["abschnitte_gesamt"] == 2 and "Geheim" not in json.dumps(d)
        # Die Verwaltung liest die beschränkte Unterseite mit.
        assert adm.get("/api/start").json["abschnitte"][0]["seiten"] == 11
        # Lesemodus: dieselben Karten aus den freigegebenen Einstiegsseiten (/api/public/index), ohne Beschränktes.
        p = t.person.get("/api/public/index").json["pages"]
        assert [x["title"] for x in p] == ["Platzhalter Abschnitt"] and p[0]["seiten"] == 10 and p[0]["kinder"] == 8
        assert len(p[0]["unterseiten"]) == 6 and {"id", "slug", "public_children", "updated_at"} <= set(p[0])
        assert "Geheim" not in json.dumps(p) and "Zweiter" not in json.dumps(p)
        d = t.person.get("/api/start").json
        assert d["lesemodus"] and [x["title"] for x in d["abschnitte"]] == ["Platzhalter Abschnitt"]
        # Besuche im Lesemodus zählen für „Zuletzt besucht“ (nicht beim leisen Einbau).
        assert t.person.get(f"/api/public/pages/{kinder[1]['slug']}").status_code == 200
        assert t.person.get(f"/api/public/pages/{kinder[2]['slug']}?leise=1").status_code == 200
        assert [e["titel"] for e in t.person.get("/api/start").json["zuletzt"]] == ["Platzhalter Kind 1"]
        # Suchfeld der Startseite: GET-Formular zur Strömipedia mit „suche“; wiki.js und public.js lesen den Parameter.
        html = mitglied.get("/").get_data(as_text=True)
        assert re.search(r'<form class="start-suche" action="/stroemipedia" method="get" role="search">\s*<input type="search" '
                         r'name="suche"', html), html
        for datei in ("app/static/js/wiki.js", "app/static/js/public.js"):
            js = lies(datei)
            assert 'new URLSearchParams(location.search).get("suche")' in js and 'searchInput.dispatchEvent(new Event("input"))' in js
        assert 'holeSeite: (slug) => get(`/api/public/pages/${encodeURIComponent(slug)}?leise=1`)' in lies("app/static/js/public.js")
        # Übersicht der Strömipedia: Karten statt Liste, volle Breite (Klasse uebersicht).
        wiki = lies("app/static/js/wiki.js")
        assert '<ul class="wiki-karten">${roots.map(karte).join("")}</ul>' in wiki and 'shell.classList.add("uebersicht")' in wiki
        assert "home-baum" not in wiki and enkel
    print("Abschnitte und Suche bestanden.")


def test_oberflaeche_texte_und_muster():
    """start.js: Texte aus Eingaben nur über esc, Zahlen über Number; Knöpfe und Muster der Designsprache."""
    js = lies("app/static/js/start.js")
    for stelle in ("esc(k.name)", "esc(k.pfad)", "esc(z.href)", "esc(e.titel)", "esc(e.zusatz)", "esc(e.modulname)",
                   "esc(e.href)", "esc(s.title)", "esc(s.slug)", "esc(k.ruhig)", "Number(z.zahl)"):
        assert stelle in js, stelle
    # Kein Feld aus der Antwort steht roh in einer Einsetzung ${…} – nur über esc(…) bzw. Number(…).
    roh = re.findall(r"\$\{\s*[a-z]\.(?:titel|title|name|href|zusatz|ruhig|modulname|slug|pfad|icon|zahl|tage|modul)\s*\}", js)
    assert not roh, roh
    html = lies("app/templates/start.html")
    assert 'class="btn secondary" type="submit">Suchen</button>' in html and 'class="btn"' not in html
    css = lies("app/static/css/app.css")
    teil = css[css.index("Startseite über alle Module (Wunsch vom 02.11.2026"):]
    assert "#" not in re.sub(r"/\*.*?\*/", "", teil, flags=re.S).replace("#pending", ""), "keine freien Farbwerte"
    assert "@container start (min-width: 1100px)" in teil and "@container start (min-width: 740px)" in teil
    # Surface Duo nebeneinander: die Startseite ganz in der rechten Hälfte (nichts auf der Falz).
    assert "main.page.breit.start { max-width: env(viewport-segment-width 1 0); margin-left: env(viewport-segment-left 1 0);" in teil
    # Suchtreffer der Strömipedia am Finger 44 px – das Suchfeld der Startseite führt am Telefon direkt dorthin.
    assert ".search-results a { line-height: 44px; }" in css
    touch = teil[teil.index("@media (pointer: coarse)"):]
    assert ".start-zeile { align-items: center; min-height: 44px; }" in touch
    for hover in re.findall(r"[^{}]*:hover[^{]*\{", re.sub(r"@media \(hover: hover\) and \(pointer: fine\) \{[^@]*?\}\s*\}", "", teil)):
        raise AssertionError(f":hover außerhalb von (hover: hover): {hover}")
    print("Texte und Muster bestanden.")


if __name__ == "__main__":
    test_route_und_navigation()
    test_rechte_je_rolle()
    test_zahlen_materialablage_wie_uebersicht()
    test_zuletzt_besucht()
    test_neu_seit_besuch()
    test_abschnitte_und_suche()
    test_oberflaeche_texte_und_muster()
