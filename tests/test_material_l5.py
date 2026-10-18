"""Rauchtest für das Modul „Material“, Lieferung 5 (Feinschliff nach Pilot):  python tests/test_material_l5.py

Jeder Mangel braucht Foto UND Bemerkung; Korrekturen an der Urkundennummer im Profil (Häkchen weg → Nummer weg, keine
stille Löschung, die Verwaltung schreibt keinen alten Stand zurück, aufs Protokoll nur die Nummer eines Prüfers).
Alle Namen und Nummern hier sind erfunden und nur für den Test da."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, gliederung, jpeg, katalog_grund, neuer_artikel, pruef_formulare,  # noqa: E402
                           punkte_von, starten, umgebung)


def test_mangel_braucht_bemerkung():
    """Ein Mangel mit Foto, aber ohne Bemerkung lässt sich nicht festschreiben; mit Bemerkung schon."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on="2025-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        url = f"/api/material/pruefungen/{pr['id']}/punkte"
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "1"}).status_code == 200
        # Der kritische Punkt weicht ab → Mangel, mit Foto, aber ohne Bemerkung.
        r = p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"wert": "ja"})
        assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel", r.get_json()
        r = p1.post(f"{url}/{pk['Testpunkt kritisch']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        r = abschluss(p1, pr["id"], ergebnis="instandsetzen")
        assert r.status_code == 400 and "Bemerkung" in r.json["error"] and "Testpunkt kritisch" in r.json["error"], r.get_json()
        # Nur Leerraum zählt nicht als Bemerkung.
        assert p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"notiz": "   "}).status_code == 200
        assert abschluss(p1, pr["id"], ergebnis="instandsetzen").status_code == 400
        assert p1.put(f"{url}/{pk['Testpunkt kritisch']}", json={"notiz": "Schnitt im Band, 2 cm"}).status_code == 200
        r = abschluss(p1, pr["id"], ergebnis="instandsetzen")
        assert r.status_code == 200, r.get_json()
    print("Mangel braucht Bemerkung bestanden.")


def test_urkunde_korrekturen():
    """Häkchen weg → Nummer weg; PUT ohne Feld löscht nichts; die Verwaltung schreibt beim Speichern keinen alten
    Stand zurück; aufs Protokoll kommt die Nummer nur, wenn das Konto wirksam Prüfer ist."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, p1, pid = k["adm"], k["pruefer"], k["pruefer_id"]

        def nummer():
            with app.app_context():
                from app import db
                return db.query("SELECT urkundennummer FROM users WHERE id = ?", (pid,), one=True)["urkundennummer"]

        assert nummer() == "1012-4711"
        # PUT ohne das Feld: 400, die Nummer bleibt.
        for koerper in ({}, {"nummer": "1012-1"}):
            r = p1.put("/api/material/urkundennummer", json=koerper)
            assert r.status_code == 400, (koerper, r.get_json())
        assert nummer() == "1012-4711"
        # Der Prüfer ändert seine Nummer; die Verwaltung speichert danach nur die Rechte – die Nummer bleibt die neue.
        assert p1.put("/api/material/urkundennummer", json={"urkundennummer": "1012-0815"}).status_code == 200
        assert adm.put(f"/api/admin/users/{pid}", json={"gliederung": "OG Test", "rechte": {"material": 2}}).status_code == 200
        assert nummer() == "1012-0815"
        # Häkchen weg → Nummer weg; Häkchen wieder → ohne Nummer, also noch kein Prüfer.
        assert adm.put(f"/api/admin/users/{pid}", json={"mat_pruefer": False}).status_code == 200
        assert nummer() == ""
        assert adm.put(f"/api/admin/users/{pid}", json={"mat_pruefer": True}).status_code == 200
        assert nummer() == "" and not p1.get("/api/material/start").json["darf"]["pruefen"]
        # pruefer_aus: ohne Häkchen trägt das Protokoll keine (alte) Nummer.
        with app.app_context():
            from app.material.services import pruefung
            konto = {"id": 99, "name": "x", "email": "x@example.org", "mat_pruefer": 0, "urkundennummer": "1012-9999",
                     "signature_png": None}
            assert pruefung.pruefer_aus(konto)["urkunde"] == ""
            konto["mat_pruefer"] = 1
            assert pruefung.pruefer_aus(konto)["urkunde"] == "1012-9999"
    print("Urkunde-Korrekturen bestanden.")


def test_css_klammern():
    """Die Stylesheets lassen sich parsen: Jede geöffnete Klammer wird geschlossen (Kommentare und Zeichenketten
    ausgenommen). Beim Zusammenführen der Geräte-Pakete gingen zwei „}“ verloren – die Regeln dahinter hingen dann in
    fremden Media-Abfragen und griffen fast nirgends, ohne dass ein Test es merkte."""
    import re
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("app/static/css/app.css", "app/static/css/pruefungen.css", "app/material/static/material.css"):
        text = open(os.path.join(wurzel, rel), encoding="utf-8").read()
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', '""', text)
        tiefe = 0
        for nr, zeile in enumerate(text.split("\n"), 1):
            for z in zeile:
                tiefe += (z == "{") - (z == "}")
                assert tiefe >= 0, f"{rel}: überzählige }} (Zeile {nr} ohne Kommentare)"
        assert tiefe == 0, f"{rel}: {tiefe} Block/Blöcke nicht geschlossen"
    print("CSS-Klammern bestanden.")


def test_shell_geruest():
    """Seitengerüst (Lieferung 5, Geräte): Die Hauptnavigation trägt das Menü „Mehr“ (verborgen, bis common.js Punkte
    hineinlegt) – innerhalb von <nav>, sonst griffe „Abmelden“ daraus nicht mehr. Der Name vor „Profil“ endet mit einem
    Leerzeichen (Vorlesen), ohne festes Leerzeichen davor. Die Modulnavigation hat Reiterleiste, Lupe und Suchformular
    mit den Kennungen, die material.js und suche.js erwarten."""
    import re
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        for konto in ("adm", "pruefer", "nutzer"):
            html = k[konto].get("/profil").get_data(as_text=True)
            nav = re.search(r'<nav class="nav" aria-label="Hauptnavigation">(.*?)</nav>', html, re.S)
            assert nav, konto
            nav = nav.group(1)
            assert 'id="logout"' in nav and '<div class="nav-mehr" hidden>' in nav, konto
            assert 'id="nav-mehr-knopf" aria-expanded="false" aria-controls="nav-mehr-liste"' in nav, konto
            assert '<div class="nav-mehr-liste" id="nav-mehr-liste" hidden></div>' in nav, konto
            assert nav.index('id="logout"') < nav.index("nav-mehr"), konto
            name = re.search(r'<span class="user">([^<]*)</span>Profil</a>', nav)
            assert name and name.group(1).endswith(" ") and name.group(1).strip(), (konto, name)
            assert "&nbsp;Profil" not in nav, konto
        for konto in ("wart", "pruefer"):
            html = k[konto].get("/material/artikel/neu").get_data(as_text=True)
            mnav = re.search(r'<nav class="mat-nav" aria-label="Modul Material">(.*?)</nav>', html, re.S)
            assert mnav, konto
            mnav = mnav.group(1)
            assert '<div class="mat-reiter">' in mnav and mnav.count('data-nav="') == 4, konto
            assert 'id="mat-lupe" aria-controls="mat-suche" aria-expanded="false"' in mnav and " hidden>" in mnav, konto
            assert '<form class="mat-suche" id="mat-suche" action="/material/suche"' in mnav, konto
            assert '<span class="mat-side-auf-text"> Ordner</span>' in mnav, konto
            # Reihenfolge: Ordner-Knopf, Reiter, Lupe, Suche – material.js prüft die Zeile in dieser Folge.
            assert mnav.index("mat-side-auf") < mnav.index("mat-reiter") < mnav.index("mat-lupe") < mnav.index("mat-suche"), konto
        # Die öffentliche Prüfseite (ohne Anmeldung) hat keine Hauptnavigation – also auch kein „Mehr“.
        with app.test_client() as gast:
            html = gast.get("/material/pruefen").get_data(as_text=True)
            assert "nav-mehr" not in html
    print("Seitengerüst (shell) bestanden.")

def test_pruefform_tippen_speichern():
    """Das Prüfformular speichert Wert und Bemerkung schon beim Tippen (material.js, entprellt, mit keepalive) – oft
    mehrmals je Feld und auch kurz vor dem Neuladen noch einmal. Darauf verlässt es sich: Ein PUT nur mit „notiz“ bzw.
    „wert“ lässt Befund und das andere Feld stehen, derselbe Stand zweimal ändert nichts, Zwischenstände füllen weder
    den Lebenslauf noch das Journal, eine halbe Zahl wird abgelehnt (und bleibt im Browser), und der Entwurf als Ganzes
    gibt den letzten Stand zurück. Dasselbe gilt für die Bemerkung zur Prüfung."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on="2025-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        url = f"/api/material/pruefungen/{pr['id']}/punkte"

        def journal_anzahl():
            with app.app_context():
                from app import db
                return db.query("SELECT COUNT(*) AS n FROM mat_audit", one=True)["n"]

        vorher = journal_anzahl()
        krit = pk["Testpunkt kritisch"]
        r = p1.put(f"{url}/{krit}", json={"wert": "ja"})                 # Mangel
        assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel", r.get_json()
        # Zwischenstände der Bemerkung, wie sie beim Tippen hinausgehen – der Befund bleibt Mangel, der Wert „ja“.
        for stand in ("Schnitt", "Schnitt im Band", "Schnitt im Band, 2 cm", "Schnitt im Band, 2 cm"):
            r = p1.put(f"{url}/{krit}", json={"notiz": stand})
            assert r.status_code == 200, r.get_json()
            assert r.json["punkt"]["notiz"] == stand and r.json["punkt"]["befund"] == "mangel" and r.json["punkt"]["wert"] == "ja"
        # Messwert getippt: „1“, „1,“ (Komma gerade getippt), „-“ (halb) wird abgelehnt, „1,5“ steht.
        mw = pk["Testpunkt Messwert"]
        assert p1.put(f"{url}/{mw}", json={"wert": "1"}).status_code == 200
        assert p1.put(f"{url}/{mw}", json={"wert": "1,"}).status_code == 200
        r = p1.put(f"{url}/{mw}", json={"wert": "-"})
        assert r.status_code == 400 and "Zahl" in r.json["error"], r.get_json()
        r = p1.put(f"{url}/{mw}", json={"wert": "1,5"})
        assert r.status_code == 200 and r.json["punkt"]["wert"] == "1,5", r.get_json()
        # Eine Bemerkung am Messwert lässt den Wert stehen.
        r = p1.put(f"{url}/{mw}", json={"notiz": "an der dünnsten Stelle"})
        assert r.status_code == 200 and r.json["punkt"]["wert"] == "1,5" and r.json["punkt"]["notiz"] == "an der dünnsten Stelle"
        # Bemerkung zur Prüfung, mehrmals beim Tippen.
        for stand in ("Schnapper", "Schnapper gereinigt"):
            assert p1.put(f"/api/material/pruefungen/{pr['id']}", json={"bemerkung": stand}).status_code == 200
        # Der Entwurf (so lädt ihn die Seite neu) trägt den letzten Stand.
        d = p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        pkt = {x["id"]: x for x in d["punkte"]}
        assert pkt[krit]["notiz"] == "Schnitt im Band, 2 cm" and pkt[mw]["wert"] == "1,5" and d["bemerkung"] == "Schnapper gereinigt"
        # Zwischenstände hinterlassen keine Spur im Journal.
        assert journal_anzahl() == vorher, (journal_anzahl(), vorher)
        # Ohne X-Requested-With (etwa ein fremdes Formular) wird nichts gespeichert – keepalive ändert daran nichts.
        r = p1.put(f"{url}/{krit}", data='{"notiz": "fremd"}', headers={"Content-Type": "text/plain"})
        assert r.status_code in (400, 403), r.status_code
    print("Prüfformular: Speichern beim Tippen bestanden.")

def test_formulare_ordnerfoto_und_suchfeld():
    """Das Ordnerfoto öffnet groß wie ein Produktbild: Der Ordner liefert neben Web- und Vorschaufassung das Original
    (nur für Konten mit Zugang zum Modul). Das Nummernsuchfeld korrigiert nichts und schreibt groß (iOS)."""
    import io

    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        w, f = k["wart"], k["fuehrung"]
        gid, _ = gliederung(w)
        o = w.get(f"/api/material/ordner/{gid}").json["ordner"]
        assert o["foto"] is None and o["original"] is None, o
        r = w.post(f"/api/material/ordner/{gid}/foto", data={"file": (jpeg(400, 200), "regal.jpg")}, headers=H,
                   content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        o = f.get(f"/api/material/ordner/{gid}").json["ordner"]
        assert o["original"].startswith("/media/material/orig/") and o["foto"].startswith("/media/material/web/"), o
        assert f.get(o["foto"]).status_code == 200
        r = f.get(o["original"])
        assert r.status_code == 200 and Image.open(io.BytesIO(r.data)).size == (400, 200)
        assert k["nutzer"].get(o["original"]).status_code == 403
        # Auch in der Liste der Ordner (Leiste) steht das Original, ohne Foto keins.
        baum = {x["id"]: x for x in f.get("/api/material/ordner").json["ordner"]}
        assert baum[gid]["original"] == o["original"]
        assert w.delete(f"/api/material/ordner/{gid}/foto", headers=H).status_code == 200
        assert f.get(f"/api/material/ordner/{gid}").json["ordner"]["original"] is None
        html = f.get(f"/material/ordner/{gid}").get_data(as_text=True)
        feld = html[html.index('name="q"'):]
        feld = feld[:feld.index(">")]
        for attr in ('autocapitalize="characters"', 'autocorrect="off"', 'spellcheck="false"', 'enterkeyhint="search"'):
            assert attr in feld, (attr, feld)
    print("Ordnerfoto (Original) und Suchfeld bestanden.")


if __name__ == "__main__":
    test_mangel_braucht_bemerkung()
    test_urkunde_korrekturen()
    test_css_klammern()
    test_shell_geruest()
    test_pruefform_tippen_speichern()
    test_formulare_ordnerfoto_und_suchfeld()
