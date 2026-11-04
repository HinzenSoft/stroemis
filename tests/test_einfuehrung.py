"""Interaktive Einführung je Modul – Grundgerüst, Server ohne Browser (Bauvorlage planung/tutorial/entwurf.md 5.1):
python tests/test_einfuehrung.py  oder  pytest tests/test_einfuehrung.py

  1. Sperre: jede Regel unter /api/ mit jeder Methode und „X-Uebung: 1“ → 403 mit dem Satz; die schreibenden auch mit
     einem Übungs-Referer; /media/ und Protokolle; Datenbank vorher/nachher gleich; Ausnahmen (Merker, /api/me,
     Abmelden) gehen; ohne Kennung unverändert. Seiten ohne Übungszweig: jede Seitenregel der Module mit „uebung=“ bzw.
     Übungs-Referer → Übungszweig (UEBUNGSSEITEN) oder „In der Übung nicht verfügbar“, nie echte Daten; die Muster für
     den Browser decken genau diese Seiten; engere CSP der Übungsseite (Sicherheitsprüfung vom 04.11.2026).
  2. Merker: 401, 404, 403, 400, CSRF, „erledigt“ bleibt, gleichzeitige Aufrufe, Konto löschen räumt ihn weg.
  3. Angebot je Rolle (Materialablage, Strömipedia, Ankerplätze, Riegenkarten), „Nicht jetzt“, neue Rolle, „unterbrochen“;
     kein Angebot auf Startseite, Profil, Leitstelle, Druck-, Fehler- und Lesemodusseiten.
  4. Übungsseiten ohne echte Daten (kein Banner, kein „Zuletzt besucht“, kein Willkommen, keine Weiterleitung der Suche,
     Hülle eines fremden Lehrgangs), Stufe und data-darf des Teils; ein Teil, der nicht gilt, wird übergangen.
  5. Profil „Einführungen“ je Rolle mit Ständen und Adressen; ohne Modul kein Abschnitt.
  6. Statisch: einfuehrung.js ohne fremde Adressen, CSS nur mit Tokens und Touch-Regeln, Knopftexte ohne „…“, jede
     Übungsdatei registriert die Teile und Abläufe aus app/einfuehrung.py.
Alle Inhalte sind Platzhalter."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, neues_konto  # noqa: E402
from test_material_meine_psa import aufbau, melden, post_mangel  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SATZ = "In der Übung gesperrt – es wird nichts gespeichert."
UEBUNG_REF = {"Referer": "http://localhost/materialablage?uebung=grund"}


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def einf(c, pfad):
    """STROEMIS.einfuehrung einer Seite (None, wenn die Seite keine Einführung kennt)."""
    r = c.get(pfad)
    html = r.get_data(as_text=True)
    m = re.search(r"einfuehrung: (.*?), kontakt: ", html)
    assert m, (pfad, r.status_code, html[:300])
    return json.loads(m.group(1)), r, html


def rechte_im_html(html):
    m = re.search(r"window\.STROEMIS = \{ user: (\{.*?\}), mapCenter", html)
    return json.loads(m.group(1))["rechte"]


def merker(app, uid):
    z = zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = ?", (f"einfuehrung:{uid}",))
    return json.loads(z[0]["wert"]) if z else {}


def put(c, modul, teil, **body):
    return c.put(f"/api/einfuehrung/{modul}/{teil}", json=body)


def pruefsumme(app):
    con = sqlite3.connect(app.config["DB_PATH"])
    try:
        return hashlib.sha256("\n".join(con.iterdump()).encode()).hexdigest()
    finally:
        con.close()


def konten(app):
    """Konten je Rolle der vier Module (Platzhalter). Liefert {rolle: (Client, Kennung)}."""
    k = {}
    k["wiki_mitglied"] = neues_konto(app, "wiki-m@example.invalid", stufe=0, rechte={"wiki": 1})
    k["wiki_redakteur"] = neues_konto(app, "wiki-r@example.invalid", stufe=0, rechte={"wiki": 2})
    k["wiki_verwaltung"] = neues_konto(app, "wiki-v@example.invalid", stufe=0, rechte={"wiki": 3})
    k["lesemodus"] = neues_konto(app, "lese@example.invalid", stufe=0)
    k["karte_mitglied"] = neues_konto(app, "karte-m@example.invalid", stufe=0, rechte={"karte": 1})
    k["karte_redakteur"] = neues_konto(app, "karte-r@example.invalid", stufe=0, rechte={"karte": 2})
    k["riegen_mitglied"] = neues_konto(app, "riegen-m@example.invalid", stufe=0, rechte={"pruefungen": 1})
    k["riegen_leitung"] = neues_konto(app, "riegen-l@example.invalid", stufe=0, rechte={"pruefungen": 1})
    k["riegen_redakteur"] = neues_konto(app, "riegen-r@example.invalid", stufe=0, rechte={"pruefungen": 2})
    k["leitstelle"] = neues_konto(app, "leit@example.invalid", stufe=0, rechte={"verwaltung": 3})
    return k


def lehrgang(adm, titel, ausbilder=()):
    r = adm.post("/api/pruefungen/lehrgaenge", json={"titel": titel, "status": "laufend", "ausbilder": [
        {"user_id": uid, "funktion": "Platzhalter", "ist_leitung": leit} for uid, leit in ausbilder]})
    assert r.status_code == 201, r.get_json()
    return r.json["lehrgang"]["id"]


# --- 1. Sperre ---------------------------------------------------------------------------------------------------------

def _adresse(regel):
    """Eine Adresse zu einer Regel: Zahlen aus dem Bereich der Übung, sonst „uebung“."""
    return re.sub(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>", lambda m: "900000001" if m.group(1) in ("int", "float") else "uebung",
                  regel.rule)


def test_sperre():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm = t.adm
        assert adm.get("/api/material/start").status_code == 200       # Tageslauf und Einstellungen einmal angestoßen
        vorher = pruefsumme(t.app)
        geprueft = 0
        for regel in t.app.url_map.iter_rules():
            if not regel.rule.startswith("/api/"):
                continue
            url = _adresse(regel)
            for methode in sorted(regel.methods):
                ausnahme = (regel.rule.startswith("/api/einfuehrung/")
                            or (regel.rule == "/api/me" and methode in ("GET", "HEAD"))
                            or (regel.rule == "/api/auth/logout" and methode == "POST"))
                if ausnahme:
                    continue
                r = adm.open(url, method=methode, headers=dict(H, **{"X-Uebung": "1"}), json={})
                assert r.status_code == 403, (methode, url, r.status_code)
                if methode != "HEAD":
                    assert r.get_json() == {"error": SATZ}, (methode, url, r.get_data(as_text=True)[:200])
                geprueft += 1
                # Ohne Kopfzeile, aber aus einer Übungsseite (Referer): ebenso gesperrt – lesend wie schreibend.
                r = adm.open(url, method=methode, headers=dict(H, **UEBUNG_REF), json={})
                assert r.status_code == 403, ("Referer", methode, url, r.status_code)
        assert geprueft > 400, geprueft
        # Medien und Dateien aus einer Übungsseite: gesperrt (Fehlerseite mit dem Satz), auch eine Seite mit POST.
        for url in ("/media/thumb/x.jpg", "/media/material/foto/x.jpg", "/media/pruefung/thumb/x.jpg",
                    "/materialablage/pruefung/900000001/pdf", "/materialablage/durchgang/900000001/sammelprotokoll",
                    f"/materialablage/artikel/{t.art[0]}/lebenslauf.pdf"):
            r = adm.get(url, headers=UEBUNG_REF)
            assert r.status_code == 403 and SATZ in r.get_data(as_text=True), (url, r.status_code)
        r = adm.post("/materialablage", headers=dict(H, **{"X-Uebung": "1"}))
        assert r.status_code == 403 and SATZ in r.get_data(as_text=True)
        # Ein fremder Referer mit „uebung=“ ist keine Übungsanfrage (die Referrer-Policy schickt ihn so nie).
        assert adm.get("/api/material/start", headers={"Referer": "https://fremd.example/?uebung=grund"}).status_code == 200
        assert pruefsumme(t.app) == vorher, "Die Datenbank hat sich durch gesperrte Anfragen geändert."
        # Ausnahmen: Merker und /api/me; Seitenaufrufe und /static/ aus der Übung.
        assert adm.get("/api/me", headers={"X-Uebung": "1"}).status_code == 200
        assert put(adm, "material", "grund", zustand="unterbrochen", ablauf=0).status_code == 200
        r = adm.put("/api/einfuehrung/material/grund", json={"zustand": "abgelehnt"}, headers={"X-Uebung": "1"})
        assert r.status_code == 200, r.get_json()
        assert adm.get("/materialablage?uebung=grund", headers=UEBUNG_REF).status_code == 200
        assert adm.get("/static/js/einfuehrung.js", headers={"X-Uebung": "1"}).status_code == 200
        assert adm.get("/static/uebung/uebungsdatei.pdf", headers=UEBUNG_REF).status_code == 200
        assert adm.get("/riegenkarten", headers=UEBUNG_REF).status_code == 200
        # Ohne Kennung unverändert erreichbar (Stichprobe).
        for url in ("/api/material/start", "/api/wiki/tree", "/api/albums", "/api/pruefungen/lehrgaenge", "/api/me"):
            assert adm.get(url).status_code == 200, url
        with post_mangel():
            assert melden(t.w, t.art[0]).status_code == 201
        # Abmelden aus der Übung (Befund 1 der Sicherheitsprüfung): geht – mit Referer wie mit Kopfzeile; die Sitzung ist weg.
        from test_material import anmelden
        for kopf in (UEBUNG_REF, {"X-Uebung": "1", **UEBUNG_REF}, {"X-Uebung": "1"}):
            c = anmelden(t.app, "mitglied@example.org", "passwort1")
            assert c.get("/api/me").status_code == 200
            r = c.post("/api/auth/logout", json={}, headers=kopf)
            assert r.status_code == 200, (kopf, r.status_code, r.get_data(as_text=True)[:200])
            assert c.get("/api/me").status_code == 401, kopf
        # Nur POST: ein GET an dieselbe Adresse bleibt aus der Übung gesperrt.
        assert t.mitglied.get("/api/auth/logout", headers=UEBUNG_REF).status_code == 403
    print("Sperre bestanden.")


# --- 1b. Seiten ohne Übungszweig (Befund 2 der Sicherheitsprüfung vom 04.11.2026) --------------------------------------

NICHT = "In der Übung nicht verfügbar"


def _modul_von(pfad):
    from app import einfuehrung, module
    return next((m for m in einfuehrung.TEILE if pfad == module.PFAD[m] or pfad.startswith(module.PFAD[m] + "/")), None)


def test_seiten_ohne_uebung():
    from app import einfuehrung
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        adm = t.adm
        lid = lehrgang(adm, "Geheimer Platzhalter-Lehrgang")
        geheim = ("Lager Platzhalter", "PSA-1", "OG Musterstadt", "Geheimer Platzhalter-Lehrgang")
        regeln = [r for r in t.app.url_map.iter_rules() if "GET" in r.methods and _modul_von(r.rule)
                  and not r.rule.startswith(("/api/", "/media/"))]
        endpunkte = {r.endpoint for r in regeln}
        # Die Liste nennt nur Seiten, die es gibt – und jede davon hat einen Übungszweig.
        assert einfuehrung.UEBUNGSSEITEN <= endpunkte, einfuehrung.UEBUNGSSEITEN - endpunkte
        vorher = pruefsumme(t.app)
        mit, ohne = 0, 0
        for regel in regeln:
            url = _adresse(regel)
            modul = _modul_von(regel.rule)
            if regel.endpoint in einfuehrung.UEBUNGSSEITEN:
                # Übungszweig: mit einem der Teile des Moduls die Hülle (Kataloge der Riegenkarten nur im Teil „Redakteur“;
                # ein Teil, der für das Konto nicht gilt, wird übergangen – dann die normale Seite, hier 404).
                gefunden = []
                for t_ in einfuehrung.TEILE[modul]:
                    e, r, html = einf(adm, f"{url}?uebung={t_['teil']}")
                    assert r.status_code in (200, 403, 404) and NICHT not in html, (url, t_["teil"], r.status_code)
                    assert not any(x in html for x in geheim), (url, t_["teil"])
                    if r.status_code == 200 and e and e["uebung"] == t_["teil"]:
                        gefunden.append(t_["teil"])
                assert gefunden, (regel.endpoint, url)
                mit += 1
                continue
            # Ohne Übungszweig: mit Kennung in der Adresse und aus einer Übungsseite heraus die Fehlerseite, vor der Route.
            for pfad, kopf in ((f"{url}?uebung=grund", {}), (url, UEBUNG_REF), (f"{url}?uebung=gibtsnicht", {})):
                r = adm.get(pfad, headers=kopf)
                html = r.get_data(as_text=True)
                if kopf and einfuehrung._datei(url):            # Dateien aus der Übung: schon die Dateisperre
                    assert r.status_code == 403 and SATZ in html, (regel.endpoint, pfad, r.status_code)
                    continue
                assert r.status_code == 403 and f"<h1>{NICHT}</h1>" in html, (regel.endpoint, pfad, r.status_code)
                assert "Diese Seite gibt es in der Übung nicht." in html and ">Zurück zur Übung</a>" in html
                assert "einfuehrung: {\"gesperrt\": true, \"uebung\": null}" in html, html[html.find("einfuehrung:"):][:80]
                assert "js/uebung/" not in html and not any(x in html for x in geheim), pfad
            ohne += 1
        assert mit == len(einfuehrung.UEBUNGSSEITEN) and ohne >= 15, (mit, ohne)
        # Mit echten Kennungen ebenso – die Sperre kommt vor jeder Frage nach dem Gegenstand.
        for pfad in (f"/materialablage/ordner/{t.lager}/bericht", f"/materialablage/meine-psa/{t.art[0]}",
                     f"/riegenkarten/{lid}/druck", "/materialablage/meine-psa", "/materialablage/pruefen",
                     f"/materialablage/ordner/{t.lager}/import", f"/materialablage/artikel/{t.art[0]}/lebenslauf.pdf"):
            r = adm.get(pfad + "?uebung=grund")
            assert r.status_code == 403 and NICHT in r.get_data(as_text=True), (pfad, r.status_code)
            assert not any(x in r.get_data(as_text=True) for x in geheim), pfad
        assert pruefsumme(t.app) == vorher, "Die Datenbank hat sich durch gesperrte Seiten geändert."
        # Der Weg zurück: an die Übungsseite des Referers (nur Pfad und Abfrage, kein fremder Host, kein „//“), sonst die
        # Übungsadresse des Teils aus der Adresse.
        r = adm.get("/materialablage/meine-psa", headers={"Referer": "http://localhost/materialablage/bestand?uebung=grund#x"})
        assert 'href="/materialablage/bestand?uebung=grund"' in r.get_data(as_text=True)
        r = adm.get("/materialablage/meine-psa", headers={"Referer": "http://localhost//fremd.example/?uebung=grund"})
        assert 'href="/fremd.example/?uebung=grund"' in r.get_data(as_text=True)
        # Ohne Referer: die Übungsadresse des Teils (der Teil „Leitung“ beginnt im Übungslehrgang, Reiter „Teilnehmende“).
        r = adm.get("/riegenkarten/5/druck?uebung=leitung")
        assert 'href="/riegenkarten/930000001?uebung=leitung#teilnehmer"' in r.get_data(as_text=True)
        r = adm.get("/materialablage/pruefen?uebung=gibtsnicht")
        assert 'href="/materialablage"' in r.get_data(as_text=True)
        # Außerhalb der Module mit Übungs-Referer: Ausgang (Kopfleiste) – die echte Seite. Mit Kennung in der Adresse nicht.
        for pfad in ("/", "/profil", "/leitstelle"):
            assert adm.get(pfad, headers=UEBUNG_REF).status_code == 200, pfad
        assert adm.get("/profil?uebung=grund").status_code == 403
        # Ohne Übung (kein Referer, keine Kennung) unverändert erreichbar.
        for pfad in ("/materialablage/meine-psa", "/materialablage/pruefen", f"/riegenkarten/{lid}/druck"):
            assert adm.get(pfad).status_code == 200, pfad
        # Die Muster für den Browser (STROEMIS.einfuehrung.seiten) treffen genau die Seiten mit Übungszweig.
        e, r, html = einf(adm, "/materialablage?uebung=grund")
        muster = [re.compile(m) for m in e["seiten"]]
        assert e["bereiche"] == ["/materialablage", "/stroemipedia", "/ankerplaetze", "/riegenkarten"], e["bereiche"]
        for regel in regeln:
            url = _adresse(regel)
            assert any(m.match(url) for m in muster) == (regel.endpoint in einfuehrung.UEBUNGSSEITEN), (regel.endpoint, url)
        assert not any(m.match("/materialablage/meine-psa") for m in muster)
        # Ohne Übung trägt STROEMIS.einfuehrung keine Muster.
        e, r, html = einf(adm, "/materialablage")
        assert "seiten" not in e and "bereiche" not in e
        # Engere CSP nur auf Übungsseiten: Bilder, Medien und Rahmen nur aus /static/, Netz nur die Ausnahmen der Sperre.
        csp = adm.get("/stroemipedia?uebung=grund").headers["Content-Security-Policy"]
        assert "img-src localhost/static/ data: blob:" in csp and "media-src localhost/static/ blob:" in csp, csp
        assert "frame-src localhost/static/ blob:" in csp, csp
        assert ("connect-src localhost/static/ localhost/api/einfuehrung/ localhost/api/me localhost/api/auth/logout;"
                in csp), csp
        assert "'unsafe-eval'" not in csp and "script-src 'self' 'nonce-" in csp
        for pfad in ("/stroemipedia", "/materialablage/meine-psa", "/materialablage/meine-psa?uebung=grund"):
            csp = adm.get(pfad).headers["Content-Security-Policy"]
            assert "img-src 'self' data: blob:" in csp and "connect-src 'self';" in csp and "frame-src" not in csp, pfad
    print("Seiten ohne Übungszweig bestanden.")


# --- 2. Merker ---------------------------------------------------------------------------------------------------------

def test_merker():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        anon = t.app.test_client()
        assert anon.put("/api/einfuehrung/material/grund", json={"zustand": "abgelehnt"}).status_code == 401
        assert put(t.mitglied, "material", "gibtsnicht", zustand="abgelehnt").status_code == 404
        assert put(t.mitglied, "leitstelle", "grund", zustand="abgelehnt").status_code == 404
        assert put(t.mitglied, "verwaltung", "grund", zustand="abgelehnt").status_code == 404
        # Ohne Modulzugang (person: Stufe 0) und ohne die Rolle des Teils: 403.
        assert put(t.person, "material", "grund", zustand="abgelehnt").status_code == 403
        assert put(t.mitglied, "material", "pruefer", zustand="abgelehnt").status_code == 403
        assert put(t.mitglied, "wiki", "grund", zustand="abgelehnt").status_code == 403
        for falsch in ({"zustand": "fertig"}, {"zustand": "offen"}, {"zustand": "unterbrochen", "ablauf": 3},
                       {"zustand": "unterbrochen", "ablauf": -1}, {"zustand": "unterbrochen", "ablauf": "0"},
                       {"zustand": "unterbrochen", "ablauf": True}, {"zustand": "unterbrochen", "ablauf": 0.0}, {}):
            r = put(t.mitglied, "material", "grund", **falsch)
            assert r.status_code == 400, (falsch, r.status_code)
        r = t.mitglied.put("/api/einfuehrung/material/grund", data="zustand=abgelehnt",
                           content_type="application/x-www-form-urlencoded")
        assert r.status_code == 403 and "X-Requested-With" in r.get_json()["error"]
        r = t.mitglied.put("/api/einfuehrung/material/grund", json={"zustand": "abgelehnt"},
                           headers={"Sec-Fetch-Site": "cross-site"})
        assert r.status_code == 403
        assert merker(t.app, t.mitglied_id) == {}
        assert put(t.mitglied, "material", "grund", zustand="unterbrochen", ablauf=0).json == {"ok": True}
        m = merker(t.app, t.mitglied_id)["material:grund"]
        assert m["zustand"] == "unterbrochen" and m["ablauf"] == 0 and m["am"]
        assert put(t.mitglied, "material", "grund", zustand="erledigt").status_code == 200
        # Aus „erledigt“ wird nichts anderes mehr.
        for z in ("unterbrochen", "abgelehnt"):
            assert put(t.mitglied, "material", "grund", zustand=z).status_code == 200
            assert merker(t.app, t.mitglied_id)["material:grund"]["zustand"] == "erledigt"
        # Gleichzeitige Aufrufe (zwei Teile, zwei Reiter): nichts geht verloren.
        sql(t.app, "UPDATE users SET mat_pruefer = 1, urkundennummer = 'UE-1', recht_wiki = 3, recht_karte = 2, "
                   "recht_pruefungen = 2 WHERE id = ?", (t.mitglied_id,))
        paare = [("material", "pruefer"), ("wiki", "grund"), ("wiki", "redakteur"), ("wiki", "verwaltung"),
                 ("karte", "grund"), ("karte", "redakteur"), ("pruefungen", "grund"), ("pruefungen", "redakteur")]
        fehler = []

        def lauf(modul, teil):
            from test_material import anmelden
            c = anmelden(t.app, "mitglied@example.org", "passwort1")
            for _ in range(3):
                r = put(c, modul, teil, zustand="unterbrochen", ablauf=0)
                if r.status_code != 200:
                    fehler.append((modul, teil, r.status_code))
        faeden = [threading.Thread(target=lauf, args=p) for p in paare]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join()
        assert not fehler, fehler
        m = merker(t.app, t.mitglied_id)
        assert set(m) == {"material:grund"} | {f"{a}:{b}" for a, b in paare}, m
        # Konto löschen: der Merker geht mit.
        assert t.adm.delete(f"/api/admin/users/{t.mitglied_id}", headers=H).status_code == 200
        assert not zeilen(t.app, "SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"einfuehrung:{t.mitglied_id}",))
    print("Merker bestanden.")


# --- 3. Angebot je Rolle -------------------------------------------------------------------------------------------------

def teile_im_angebot(c, pfad):
    e, r, _ = einf(c, pfad)
    assert r.status_code == 200, (pfad, r.status_code)
    return [x["teil"] for x in e["angebot"]], e


def test_angebot_je_rolle():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k = konten(t.app)
        lehrgang(t.adm, "Platzhalter-Lehrgang", [(k["riegen_leitung"][1], True), (k["riegen_mitglied"][1], False)])
        pruefer = t.k["pruefer"]
        # Materialablage: Mitglied ohne Freigabe, Prüfer, Materialwart, Material-Verwaltung.
        assert teile_im_angebot(t.mitglied, "/materialablage")[0] == ["grund"]
        assert teile_im_angebot(pruefer, "/materialablage")[0] == ["grund", "pruefer"]
        assert teile_im_angebot(t.w, "/materialablage")[0] == ["grund", "materialwart"]
        an, e = teile_im_angebot(t.k["katalog"], "/materialablage/katalog")
        assert an == ["grund", "materialwart", "verwaltung"], an
        assert e["modul"] == "material" and e["name"] == "Materialablage" and e["uebung"] is None
        assert e["zu"] == "zur Materialablage" and e["bleibt"] == "Dein echter Bestand bleibt unverändert."
        assert e["angebot"][0] == {"teil": "grund", "titel": "Grundteil", "minuten": 5, "zustand": "offen", "ablauf": 0,
                                   "ablaeufe": 3, "ablauf_titel": "Zurechtfinden", "am": "",
                                   "adresse": "/materialablage?uebung=grund"}
        # Jede Seite des Moduls, auch die Artikelseite nach einem QR-Scan.
        assert teile_im_angebot(t.w, f"/materialablage/artikel/{t.art[0]}")[0] == ["grund", "materialwart"]
        # Strömipedia, Ankerplätze, Riegenkarten.
        assert teile_im_angebot(k["wiki_mitglied"][0], "/stroemipedia")[0] == ["grund"]
        assert teile_im_angebot(k["wiki_redakteur"][0], "/stroemipedia/irgendwas")[0] == ["grund", "redakteur"]
        assert teile_im_angebot(k["wiki_verwaltung"][0], "/stroemipedia")[0] == ["grund", "redakteur", "verwaltung"]
        assert teile_im_angebot(k["karte_mitglied"][0], "/ankerplaetze")[0] == ["grund"]
        assert teile_im_angebot(k["karte_redakteur"][0], "/ankerplaetze")[0] == ["grund", "redakteur"]
        assert teile_im_angebot(k["riegen_mitglied"][0], "/riegenkarten")[0] == ["grund"]
        assert teile_im_angebot(k["riegen_leitung"][0], "/riegenkarten")[0] == ["grund", "leitung"]
        assert teile_im_angebot(k["riegen_redakteur"][0], "/riegenkarten/kataloge")[0] == ["grund", "leitung", "redakteur"]
        # Kein Angebot: Startseite, Profil, Leitstelle, Druck, Fehlerseiten, Lesemodus, Seite in der Übung.
        lid = lehrgang(t.adm, "Platzhalter-Druck", [(k["riegen_leitung"][1], True)])
        for c, pfad in ((t.mitglied, "/"), (t.mitglied, "/profil"), (k["leitstelle"][0], "/leitstelle"),
                        (k["riegen_leitung"][0], f"/riegenkarten/{lid}/druck"),
                        (t.mitglied, "/materialablage/artikel/987654"), (t.mitglied, "/materialablage/ordner/987654"),
                        (k["riegen_mitglied"][0], "/riegenkarten/987654"), (t.mitglied, "/gibt-es-nicht"),
                        (k["lesemodus"][0], "/stroemipedia"), (t.person, "/materialablage"),
                        (t.mitglied, "/materialablage?uebung=grund")):
            e, r, html = einf(c, pfad)
            assert e is None or e["angebot"] == [], (pfad, e)
            if e is None:
                assert "js/einfuehrung.js" in html or r.status_code in (302,), pfad
        # „Nicht jetzt“: alle angebotenen Teile abgelehnt – danach kein Angebot.
        for teil in ("grund", "pruefer"):
            assert put(pruefer, "material", teil, zustand="abgelehnt").status_code == 200
        assert teile_im_angebot(pruefer, "/materialablage")[0] == []
        # Neue Rolle: nur ihr Teil.
        sql(t.app, "INSERT INTO mat_folder_grant (folder_id, user_id, permission, valid_until, granted_by, created_at) "
                   "VALUES (?, ?, 'verwalten', NULL, 1, '2026-11-03T00:00:00+00:00')", (t.lager, t.k["pruefer_id"]))
        an, e = teile_im_angebot(pruefer, "/materialablage")
        assert an == ["materialwart"], an
        # Unterbrochen: Angebot zum Fortsetzen mit dem Stand; ein späterer Ablauf führt mit ablauf=n hin.
        assert put(t.mitglied, "material", "grund", zustand="unterbrochen", ablauf=0).status_code == 200
        an, e = teile_im_angebot(t.mitglied, "/materialablage/bestand")
        assert an == ["grund"] and e["angebot"][0]["zustand"] == "unterbrochen"
        from app import einfuehrung
        alt = einfuehrung.TEILE["material"]
        einfuehrung.TEILE["material"] = (dict(alt[0], ablaeufe=("Zurechtfinden", "Artikel finden", "Mangel melden")),) + alt[1:]
        try:
            assert put(t.mitglied, "material", "grund", zustand="unterbrochen", ablauf=2).status_code == 200
            an, e = teile_im_angebot(t.mitglied, "/materialablage")
            g = e["angebot"][0]
            assert (g["ablauf"], g["ablaeufe"], g["ablauf_titel"]) == (2, 3, "Mangel melden"), g
            assert g["adresse"] == "/materialablage?uebung=grund&ablauf=2", g
        finally:
            einfuehrung.TEILE["material"] = alt
        # Lehrgang: Leitung nur mit ist_leitung (ein Ausbilder ohne Leitung hat den Teil nicht).
        assert put(k["riegen_mitglied"][0], "pruefungen", "leitung", zustand="abgelehnt").status_code == 403
    print("Angebot je Rolle bestanden.")


# --- 4. Übungsseiten ohne echte Daten ------------------------------------------------------------------------------------

def test_uebungsseiten():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k = konten(t.app)
        iid = t.art[0]
        with post_mangel():
            assert melden(t.w, iid).status_code == 201                    # gesperrt: Banner schon im HTML
        echt = t.w.get(f"/materialablage/artikel/{iid}").get_data(as_text=True)
        assert 'class="mat-banner' in echt
        ziele = f"start:ziele:{t.k['wart_id']}"
        sql(t.app, "DELETE FROM mat_meta WHERE schluessel = ?", (ziele,))
        e, r, html = einf(t.w, f"/materialablage/artikel/{iid}?uebung=grund")
        assert r.status_code == 200 and e["uebung"] == "grund" and e["angebot"] == []
        assert 'class="mat-banner' not in html and "Platzhalter: Mangel" not in html
        assert not zeilen(t.app, "SELECT 1 FROM mat_meta WHERE schluessel = ?", (ziele,)), "kein „Zuletzt besucht“"
        assert "<title>Übung · Artikel – Materialablage – strömis.de</title>" in html
        assert "js/einfuehrung.js" in html and "js/uebung/material.js" in html
        assert html.index("js/common.js") < html.index("js/einfuehrung.js") < html.index("js/uebung/material.js") \
            < html.index("material/material.js")
        darf = json.loads(re.search(r'data-darf="([^"]*)"', html).group(1).replace("&#34;", '"'))
        assert darf == dict(einfuehrung_darf("grund"), uid=t.k["wart_id"]), darf
        # Ein fremder Artikel gibt es in der Übung nicht als Fehlerseite – nur die Hülle mit der Kennung der Adresse.
        e, r, html = einf(t.mitglied, "/materialablage/artikel/900000011?uebung=grund")
        assert r.status_code == 200 and '"id": 900000011' in re.search(r'data-daten="([^"]*)"', html).group(1).replace("&#34;", '"')
        # Willkommen: in der Übung weder gezeigt noch gemerkt.
        r = t.adm.post("/api/wiki/pages", json={"title": "Materialablage", "content": "Platzhalter"})
        assert r.status_code == 201, r.get_json()
        assert t.adm.put(f"/api/wiki/pages/{r.json['page']['id']}/share", json={"is_public": True}).status_code == 200
        e, r, html = einf(t.mitglied, "/materialablage?uebung=grund")
        assert 'id="mat-willkommen"' not in html and e["anleitung"]
        assert not zeilen(t.app, "SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"willkommen:{t.mitglied_id}",))
        assert 'id="mat-willkommen"' in t.mitglied.get("/materialablage").get_data(as_text=True)
        # Suche: in der Übung ohne Datenbanksuche und ohne Weiterleitung.
        assert t.w.get("/materialablage/suche?q=PSA-2").status_code == 302
        r = t.w.get("/materialablage/suche?q=PSA-2&uebung=grund")
        assert r.status_code == 200 and 'data-ansicht="suche"' in r.get_data(as_text=True)
        # Artikel anlegen: auch ohne Verwalterrecht die Hülle (Teil „Materialwart“ gilt aber nur für Materialwarte).
        assert t.mitglied.get("/materialablage/artikel/neu").status_code == 403
        assert t.mitglied.get("/materialablage/artikel/neu?uebung=grund").status_code == 200
        r = t.w.get("/materialablage/artikel/neu?ordner=900000002&uebung=materialwart")
        assert r.status_code == 200 and "&#34;ordner&#34;: 900000002" in r.get_data(as_text=True)
        # Fremder Lehrgang: in der Übung die Hülle ohne Titel, sonst 404.
        lid = lehrgang(t.adm, "Geheimer Platzhalter-Lehrgang")
        c = k["riegen_mitglied"][0]
        assert c.get(f"/riegenkarten/{lid}").status_code == 404
        e, r, html = einf(c, f"/riegenkarten/{lid}?uebung=grund")
        assert r.status_code == 200 and "Geheimer" not in html and e["uebung"] == "grund"
        assert not zeilen(t.app, "SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"start:ziele:{k['riegen_mitglied'][1]}",))
        # Kataloge in der Übung nur im Teil „Redakteur“; die Druckansicht kennt keine Übung.
        assert k["riegen_redakteur"][0].get("/riegenkarten/kataloge?uebung=grund").status_code == 403
        assert k["riegen_redakteur"][0].get("/riegenkarten/kataloge?uebung=redakteur").status_code == 200
        assert c.get(f"/riegenkarten/{lid}/druck?uebung=grund").status_code == 403      # ohne Übungszweig
        # Stufe des Teils in rechte[modul] – nie höher als die echte.
        e, r, html = einf(k["wiki_verwaltung"][0], "/stroemipedia?uebung=grund")
        assert rechte_im_html(html)["wiki"] == 1 and 'id="btn-new-page"' not in html
        e, r, html = einf(k["wiki_verwaltung"][0], "/stroemipedia?uebung=redakteur")
        assert rechte_im_html(html)["wiki"] == 2 and 'id="btn-new-page"' in html and 'id="btn-papierkorb"' in html
        e, r, html = einf(k["karte_redakteur"][0], "/ankerplaetze?uebung=redakteur")
        assert rechte_im_html(html)["karte"] == 2 and 'id="btn-new-album"' in html
        e, r, html = einf(t.k["katalog"], "/materialablage?uebung=verwaltung")
        darf = json.loads(re.search(r'data-darf="([^"]*)"', html).group(1).replace("&#34;", '"'))
        assert darf["katalog"] and darf["alles"] and rechte_im_html(html)["material"] == 3
        # Nachtrag: Ein Teil, der nicht gilt, wird übergangen – normale Seite, keine erhöhten Rechte.
        for c, pfad, modul in ((k["wiki_mitglied"][0], "/stroemipedia?uebung=verwaltung", "wiki"),
                               (k["wiki_mitglied"][0], "/stroemipedia?uebung=redakteur", "wiki"),
                               (k["karte_mitglied"][0], "/ankerplaetze?uebung=redakteur", "karte"),
                               (k["riegen_mitglied"][0], "/riegenkarten?uebung=leitung", "pruefungen"),
                               (t.mitglied, "/materialablage?uebung=verwaltung", "material"),
                               (t.mitglied, "/materialablage?uebung=pruefer", "material"),
                               (t.mitglied, "/materialablage?uebung=gibtsnicht", "material")):
            e, r, html = einf(c, pfad)
            assert r.status_code == 200 and e["uebung"] is None and "js/uebung/" not in html, pfad
            assert "<title>Übung" not in html and rechte_im_html(html)[modul] == 1, pfad
            assert 'id="btn-new-page"' not in html and 'id="btn-new-album"' not in html
            if modul == "material":
                darf = json.loads(re.search(r'data-darf="([^"]*)"', html).group(1).replace("&#34;", '"'))
                assert not darf["katalog"] and not darf["verwalten"] and not darf["pruefen"], darf
        # Im Lesemodus der Strömipedia gibt es keine Übung.
        e, r, html = einf(k["lesemodus"][0], "/stroemipedia?uebung=grund")
        assert e is None and "js/uebung/" not in html
    print("Übungsseiten bestanden.")


def einfuehrung_darf(teil):
    from app import einfuehrung
    return einfuehrung.DARF_MATERIAL[teil]


# --- 5. Profil -----------------------------------------------------------------------------------------------------------

def test_profil():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k = konten(t.app)
        html = t.k["pruefer"].get("/profil").get_data(as_text=True)
        teil = html[html.index('id="einfuehrungen"'):html.index("Passwort ändern")]
        assert "<h2 id=\"einf-titel\">Einführungen</h2>" in teil
        assert "Kurze Übungen an Übungsdaten – dein echter Bestand bleibt unverändert." in teil
        assert teil.count('class="einf-zeile"') == 2 and '<h3 class="einf-modul">Materialablage</h3>' in teil
        assert "Grundteil · etwa 5 Min." in teil and "Prüfer · etwa 4 Min." in teil
        assert teil.count("noch nicht begonnen") == 2 and teil.count(">Starten</a>") == 2
        assert 'href="/materialablage/artikel/900000012?uebung=pruefer"' in teil and 'class="btn secondary small"' in teil
        assert put(t.k["pruefer"], "material", "grund", zustand="erledigt").status_code == 200
        assert put(t.k["pruefer"], "material", "pruefer", zustand="unterbrochen", ablauf=0).status_code == 200
        html = t.k["pruefer"].get("/profil").get_data(as_text=True)
        assert re.search(r"erledigt am \d\d\.\d\d\.\d{4}", html) and ">Erneut ansehen</a>" in html
        assert "unterbrochen bei „Prüfung durchführen“" in html and ">Fortsetzen</a>" in html
        assert 'aria-label="Materialablage, Prüfer: Fortsetzen"' in html
        # „Nicht jetzt“ (abgelehnt) heißt im Profil „noch nicht begonnen“ mit „Starten“.
        assert put(t.mitglied, "material", "grund", zustand="abgelehnt").status_code == 200
        html = t.mitglied.get("/profil").get_data(as_text=True)
        assert "noch nicht begonnen" in html and ">Starten</a>" in html
        # Mehrere Module, je mit Zwischenzeile; Reihenfolge Materialablage, Strömipedia, Ankerplätze, Riegenkarten.
        sql(t.app, "UPDATE users SET recht_wiki = 3, recht_karte = 1, recht_pruefungen = 2 WHERE id = ?", (t.mitglied_id,))
        html = t.mitglied.get("/profil").get_data(as_text=True)
        module = re.findall(r'<h3 class="einf-modul">([^<]+)</h3>', html)
        assert module == ["Materialablage", "Strömipedia", "Ankerplätze", "Riegenkarten"], module
        assert html.index('id="einfuehrungen"') < html.index("<h2>Passwort ändern</h2>")
        # Ohne Modul mit Übung: kein Abschnitt (Lesemodus, Leitstelle allein, kein Zugang zur Materialablage).
        for c in (k["lesemodus"][0], t.person):
            assert 'id="einfuehrungen"' not in c.get("/profil").get_data(as_text=True)
        html = k["leitstelle"][0].get("/profil").get_data(as_text=True)
        assert 'id="einfuehrungen"' in html          # Plattform-Verwaltung hat alle Module
    print("Profil bestanden.")


# --- 6. Statisch ---------------------------------------------------------------------------------------------------------

def _node():
    for kandidat in ("/home/harness/devtools/node/bin/node", shutil.which("node") or ""):
        if kandidat and os.path.isfile(kandidat):
            return kandidat
    return None


def _uebungsdatei_teile(modul):
    """Teile und Abläufe einer Übungsdatei: mit Node ausgeführt (S.einfuehrung.modul abgefangen), sonst aus dem Text."""
    pfad = os.path.join(WURZEL, "app", "static", "js", "uebung", f"{modul}.js")
    node = _node()
    if node:
        skript = ("const reg = {}; globalThis.window = globalThis; globalThis.document = { getElementById: () => null };"
                  "globalThis.S = { einfuehrung: { modul(n, d) { reg[n] = d; } } };"
                  f"require({json.dumps(pfad)});"
                  "const out = {}; for (const [n, d] of Object.entries(reg)) { out[n] = {};"
                  " for (const [k, t] of Object.entries(d.teile)) out[n][k] = t.ablaeufe.map((a) => [a.titel, a.start]); }"
                  "console.log(JSON.stringify(out));")
        r = subprocess.run([node, "-e", skript], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)[modul]
    text = lies(f"app/static/js/uebung/{modul}.js")
    return {k: None for k in re.findall(r"^\s{6}(\w+): ", text, flags=re.M)}


def test_statisch():
    from app import einfuehrung
    js = lies("app/static/js/einfuehrung.js")
    assert not re.search(r"https?://", js), "keine fremden Adressen"
    assert not re.search(r"^\s*import\b|\bimport\(|require\(", js, flags=re.M) and "/vendor/" not in js
    assert "Übung · Schritt ${n} von ${m}" in js and "Übung unterbrechen" in js and "Übungsbild nehmen" in js
    assert 'S.confirm("Übung unterbrechen?", "Unterbrechen", "Weiter üben", { endgueltig: false })' in js
    assert '"In der Übung nicht verfügbar."' in js and '"In der Übung gibt es diese Datei nicht."' in js
    # Knopftexte ohne „…“ (Designsprache) – in der Führung und im Angebot.
    for knopf in re.findall(r'(?:text|knopf): "([^"]*)"', js) + re.findall(r">([^<>]*)</button>", js):
        assert "…" not in knopf and "..." not in knopf, knopf
    # Die Schicht deckt alle Wege ab (Bauvorlage 2.3); Kopfzeile nur an Merker, /api/me und /static/.
    for wort in ("window.fetch = ", "window.XMLHttpRequest = UebungXHR", '"sendBeacon"', "window.open = function",
                 "history[art] = function", 'document.addEventListener("submit"', '"X-Uebung": "1"', "ablageAufraeumen",
                 'role", "dialog"', 'aria-modal", "false"', 'role", "region"', "dialog[open]"):
        assert wort in js, wort
    # Führung robust (04.11.2026): Ziele sofort ins Bild (kein weicher Bildlauf – auch nicht ohne „Bewegung reduzieren“),
    # bereit erst nach Schrift, Zurück eines Overlays und Animationen, kein Auswerten während eines Seitenwechsels, „m“
    # beim Betreten des Ablaufs festgehalten, jeder Ablauf mit neu geladener Startseite, Editor ohne aria-describedby,
    # Seitenwechsel auf Dateien, Menüs frei.
    assert "S.weich()" not in js and 'behavior: "instant"' in js and "smooth" not in js
    for wort in ("function beruhigen(s, el, lauf)", "document.fonts.ready", "document.getAnimations()", "overlaySchliesst()",
                 "elementsFromPoint", "seiteGehtGerade()", "function zaehlungFesthalten()", "location.reload()",
                 "el.isContentEditable", 'setAttribute("aria-live", "polite")', "istDatei(u) && !(ausgang",
                 'classList.toggle("unter-menue"', 'd.matches(":modal")'):
        assert wort in js, wort
    # Nachbesserung nach der Sicherheitsprüfung: Übungsablage, Seiten ohne Übungszweig, Referer, Abmelden.
    for wort in ("ablageUmlegen()", 'const ABLAGE = "stroemis-uebung-ablage"', 'addEventListener("navigate"',
                 "echteAblage()", '(pfad === "/api/auth/logout" && methode === "POST")', "E.seiten", "E.gesperrt",
                 'a.referrerPolicy = "no-referrer"', 'attributeFilter: ["referrerpolicy", "rel"]'):
        assert wort in js, wort
    assert "KENNUNG" not in js, "Aufräumen nur noch die Übungsablage"
    # common.js: der Helfer S.ziel (nur Seiten mit Übungszweig bekommen die Kennung), in der Rückgabe von window.S; das
    # Abmelden leert die echte Ablage.
    common = lies("app/static/js/common.js")
    assert "function ziel(url)" in common and "reihenfolgeKnoepfe, ziel };" in common
    assert "(e.seiten || []).some(" in common and "window.S.einfuehrung.echteAblage" in common
    # CSS: Abschnitt „Einführung“ nur mit Tokens, :hover nur mit Maus, 44 px nur am Finger, Bewegung reduzieren.
    css = lies("app/static/css/app.css")
    teil = css[css.index("/* --- Einführung: Angebot, Führung, Profil"):]
    ohne = re.sub(r"/\*.*?\*/", "", teil, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", ohne), "keine freien Farbwerte"
    assert ":hover" not in ohne
    vorn = ohne[:ohne.index("@media (pointer: coarse)")]
    assert "44px" not in vorn and "min-height: 44px" in ohne[ohne.index("@media (pointer: coarse)"):]
    assert "transition" not in re.sub(r"@media \(prefers-reduced-motion: no-preference\) \{[^{}]*\{[^{}]*\}\s*\}", "", ohne)
    assert "@media (prefers-reduced-motion: no-preference) {\n  .fuehrung-rahmen { transition:" in teil
    for token in ("var(--wasser)", "var(--radius-gross)", "var(--schatten-dialog)", "var(--schatten-leiste)",
                  "var(--sicher-unten)", "var(--abdunkeln-leicht)", "var(--fuehrung-hoehe, 0px)"):
        assert token in teil, token
    # Vorlagen: Skripte nach common.js und vor den Skripten der Seite, Titelvorsatz, Profilabschnitt vor „Passwort“.
    base = lies("app/templates/base.html")
    assert base.index("js/common.js") < base.index("js/einfuehrung.js") < base.index("{% block scripts %}")
    assert "{% if uebung_teil %}Übung · {% endif %}" in base and "einfuehrung: {{ einfuehrung | tojson }}" in base
    profil = lies("app/templates/profil.html")
    assert profil.index('id="einfuehrungen"') < profil.index("<h2>Passwort ändern</h2>")
    # Jede Übungsdatei registriert genau die Teile aus TEILE, mit denselben Abläufen und derselben Startadresse.
    for modul, teile in einfuehrung.TEILE.items():
        gefunden = _uebungsdatei_teile(modul)
        assert set(gefunden) == {t["teil"] for t in teile}, (modul, gefunden)
        for t in teile:
            if gefunden[t["teil"]] is None:
                continue
            titel = [a[0] for a in gefunden[t["teil"]]]
            assert titel == list(t["ablaeufe"]), (modul, t["teil"], titel)
            assert gefunden[t["teil"]][0][1] == t["start"], (modul, t["teil"], gefunden[t["teil"]][0])
        text = lies(f"app/static/js/uebung/{modul}.js")
        bereich = {"material": "90", "wiki": "91", "karte": "92", "pruefungen": "93"}[modul]
        for zahl in re.findall(r"\b9\d{8}\b", text):
            assert zahl.startswith(bereich), (modul, zahl)
        for adresse in re.findall(r'"(/static/[^"]+)"', text):
            assert adresse.startswith("/static/uebung/") and os.path.isfile(os.path.join(WURZEL, "app", adresse[1:])), adresse
    # Übungsdateien: gültiges PDF mit einer Seite, Bilder höchstens 60 KB, Erzeugerskript vorhanden.
    with open(os.path.join(WURZEL, "app/static/uebung/uebungsdatei.pdf"), "rb") as fh:
        pdf = fh.read()
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF") and b"/Count 1" in pdf
    try:
        import pypdf
        leser = pypdf.PdfReader(os.path.join(WURZEL, "app/static/uebung/uebungsdatei.pdf"), strict=True)
        assert len(leser.pages) == 1 and "Übungsdatei – kein echtes Dokument" in leser.pages[0].extract_text()
    except ImportError:
        pass
    for n in (1, 2, 3):
        pfad = os.path.join(WURZEL, f"app/static/uebung/uebungsbild-{n}.jpg")
        assert os.path.getsize(pfad) <= 60 * 1024, pfad
        from PIL import Image
        with Image.open(pfad) as b:
            assert b.format == "JPEG" and b.size == (800, 600)
    assert "def bild(n)" in lies("scripts/uebungsdateien.py")
    # README und CHANGELOG nennen die Einführung.
    readme = lies("README.md")
    assert "## Einführungen (Übungen je Modul)" in readme and "**Übungssperre (Einführung):**" in readme
    assert "`einfuehrung.UEBUNGSSEITEN`" in readme and "stroemis-uebung-ablage" in readme
    assert "**Nach der Sicherheitsprüfung nachgebessert**" in lies("CHANGELOG-Material.md")
    assert "| Interaktive Einführung je Modul |" in lies("CHANGELOG-Material.md")
    # Übungen je Modul und robuste Führung (04.11.2026): kein „folgt“ mehr, die Durchlauftests in der Testliste.
    changelog = lies("CHANGELOG-Material.md")
    assert "**Übungen je Modul**: folgt" not in changelog and "**Führung robust gemacht" in changelog
    for t in ("material", "wiki", "karte", "riegen"):
        assert f"python tests/test_einfuehrung_{t}.py" in readme, t
    print("Statisch bestanden.")


if __name__ == "__main__":
    test_sperre()
    test_seiten_ohne_uebung()
    test_merker()
    test_angebot_je_rolle()
    test_uebungsseiten()
    test_profil()
    test_statisch()
