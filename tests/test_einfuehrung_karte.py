"""Interaktive Einführung – Übungen der Ankerplätze (Bauvorlage planung/tutorial/entwurf.md 3.3 und 5.3):
python tests/test_einfuehrung_karte.py  oder  pytest tests/test_einfuehrung_karte.py

1. Statisch: map.js wechselt die Seite nur über S.ziel (Ausnahme: der Weg nach /login) und öffnet kein Fenster; die
   Übungsdatei app/static/js/uebung/karte.js nennt nur Platzhalter („Übung“, example.invalid), keine fremden Adressen,
   Bilder nur unter /static/uebung/karte/ (vorhanden, 800 × 600, höchstens 60 KB) und Kennungen nur im Bereich
   920000001–920000099.
2. Browser (Chromium über tests/einfuehrung_browser.py; ohne Chromium „übersprungen“ mit rc 0): beide Teile („grund“,
   „redakteur“) bei 1280×900 (Maus) und 360×740 (Telefon, Touch – die Seitenleiste ist dort eine Schublade von unten,
   die Leiste der Führung darf ihr Ziel nicht verdecken) bis „Geschafft“; die Datei kommt über „Übungsbild nehmen“.
   Rot bei fehlendem oder verdecktem Ziel, unbeantworteter Anfrage, Anfrage an /api/ oder /media/ der eigenen Herkunft
   (Kartenkacheln fremder Herkunft sind erlaubt), Seite ohne Übungskennung, Konsolenfehler oder waagerechtem Bildlauf.
3. Ein echtes Album mit Bild erscheint in der Übung nicht; nach allen Durchläufen sind Datenbank (iterdump-Prüfsumme)
   und Medienordner unverändert.
Alle Inhalte sind Platzhalter."""
import hashlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from einfuehrung_browser import WURZEL, Umgebung, uebersprungen  # noqa: E402

GROESSEN = ((1280, 900, False), (360, 740, True))
ECHT = "Echtes Album Probe"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


# --- 1. Statisch ---------------------------------------------------------------------------------------------------------

def test_statisch():
    # map.js: programmatische Seitenwechsel nur über S.ziel – außer dem Weg nach /login (401) –, kein window.open.
    js = lies("app/static/js/map.js")
    for zeile in js.splitlines():
        if re.search(r"location\.(href\s*=(?!=)|replace\(|assign\()|window\.open\(", zeile):
            assert "S.ziel(" in zeile or re.search(r"location\.href\s*=\s*\"/login\"", zeile), zeile
    # Übungsdatei: nur Platzhalter, keine fremden Adressen, Bilder vorhanden, Kennungen im eigenen Bereich.
    text = lies("app/static/js/uebung/karte.js")
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    assert not re.search(r"https?://", code), "keine fremden Adressen"
    assert "/media/" not in code, "keine Medien des Servers"
    for mail in re.findall(r"[\w.+-]+@[\w.-]+", code):
        assert mail.endswith("@example.invalid"), mail
    for zahl in re.findall(r"\b9\d{8}\b", text):
        assert 920000001 <= int(zahl) <= 920000099, zahl
    for titel in re.findall(r'album\(\w+, "([^"]+)"', code):
        assert titel.startswith("Übungsalbum "), titel
    for name in re.findall(r'(?:name|contact_name|contact_org): "([^"]*)"', code):
        assert not name or "Übung" in name, name
    assert re.search(r'name: "Übungsort"', code)
    # Die Bilder kommen aus dem eigenen Ordner (die Vorlage BILD(n) setzt den Pfad zusammen).
    assert "const BILD = (n) => `/static/uebung/karte/uebungsbild-${n}.jpg`;" in text
    from PIL import Image
    for n in range(1, 9):
        pfad = os.path.join(WURZEL, f"app/static/uebung/karte/uebungsbild-{n}.jpg")
        assert os.path.getsize(pfad) <= 60 * 1024, pfad
        with Image.open(pfad) as b:
            assert b.format == "JPEG" and b.size == (800, 600), pfad
    # Kein Wortlaut aus Fachinhalten: Beschreibungen und Hinweise sind als Platzhalter gekennzeichnet.
    for feld in re.findall(r'(?:description|contact_notes): "([^"]*)"', code) + re.findall(r'album\([^)]*?"(Übung: [^"]*)"', code):
        assert feld.startswith("Übung: Platzhalter"), feld
    print("Statisch bestanden.")


# --- 2./3. Browser -------------------------------------------------------------------------------------------------------

def _pruefsummen(u):
    """Je Tabelle eine Prüfsumme über ihre Zeilen (aus iterdump)."""
    with u.app.app_context():
        from app import db
        out = {}
        for zeile in db.get_db().iterdump():
            m = re.match(r'INSERT INTO "([^"]+)"', zeile)
            if m:
                out[m.group(1)] = hashlib.sha256((out.get(m.group(1), "") + zeile).encode()).hexdigest()
        return out


def _medien(u):
    wurzel = u.app.config["MEDIA_DIR"]
    out = {}
    for ordner, _dirs, dateien in os.walk(wurzel):
        for d in dateien:
            pfad = os.path.join(ordner, d)
            with open(pfad, "rb") as fh:
                out[os.path.relpath(pfad, wurzel)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _echtes_album(u):
    """Ein echtes Album mit einem Bild (Übungsbild als Datei, ohne Geotag) – angelegt vom Redakteur."""
    c = u._anmelden("uebung-redakteur@example.invalid", "passwort1")
    r = c.post("/api/albums", json={"title": ECHT, "category": "wasser"})
    assert r.status_code == 201, r.get_json()
    aid = r.json["album"]["id"]
    with open(os.path.join(WURZEL, "app/static/uebung/karte/uebungsbild-1.jpg"), "rb") as fh:
        daten = fh.read()
    r = c.post(f"/api/albums/{aid}/photos", data={"files": (io.BytesIO(daten), "echt.jpg")},
               content_type="multipart/form-data", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 201 and len(r.json["photos"]) == 1, r.get_json()
    pid = r.json["photos"][0]["id"]
    assert c.put(f"/api/photos/{pid}", json={"lat": 50.0, "lon": 7.0}).status_code == 200
    return aid


def _echtes_bleibt_draussen(u, breite, hoehe, touch):
    """Die Liste der Alben in der Übung zeigt nur die Übungsalben – das echte Album kommt nicht vor, auch nicht auf der
    Karte; kein Abruf an /api/ oder /media/."""
    wo = f"{breite}×{hoehe}"
    u.merker_leeren("mitglied")
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/ankerplaetze?uebung=grund", warten=0.3)
        assert s.warte("(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand(); return z && z.bereit; })()", 10), wo
        assert s.js("document.title").startswith("Übung · ")
        assert s.klick("#btn-albums") is None
        assert s.warte("document.querySelectorAll('#al-liste .album-wahl').length === 3", 5), wo
        titel = s.js("[...document.querySelectorAll('#al-liste .album-wahl .t')].map((t) => t.textContent)")
        assert sorted(titel) == ["Übungsalbum A", "Übungsalbum B", "Übungsalbum C"], titel
        info = s.js("""(() => ({ text: document.body.textContent, bilder: [...document.querySelectorAll('img')].map((i) => i.src),
            marker: [...document.querySelectorAll('.thumb-marker .tm, .cluster-marker .stack')].map((m) => m.style.backgroundImage) }))()""")
        assert ECHT not in info["text"], wo
        assert all("/static/" in b or not b.startswith(u.basis) for b in info["bilder"]), info["bilder"]
        assert info["marker"] and all("/static/uebung/karte/" in m for m in info["marker"]), info["marker"]
        assert s.js("document.querySelector('#map .leaflet-tile-pane') !== null")
        s.sammeln()
        befunde = s.netz_befunde() + s.fehler
        assert not befunde, befunde
    finally:
        s.schliessen()


def _durchlauf(u, teil, breite, hoehe, touch):
    rolle = "mitglied" if teil == "grund" else "redakteur"
    u.merker_leeren(rolle)
    return u.durchlauf("karte", teil, breite, hoehe, touch, rolle=rolle)


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        aid = _echtes_album(u)
        summe, medien = _pruefsummen(u), _medien(u)
        konten = [r["id"] for r in u.sql("SELECT id FROM users ORDER BY id")]
        assert medien, "das echte Bild liegt im Medienordner"
        for breite, hoehe, touch in GROESSEN:
            _echtes_bleibt_draussen(u, breite, hoehe, touch)
            # Beide Teile über die gemeinsame Hilfe (der Tipp auf die Karte: probe {klick: "#map", frei: true}).
            for teil in ("grund", "redakteur"):
                befunde = _durchlauf(u, teil, breite, hoehe, touch)
                assert not befunde, (teil, breite, befunde)
        # Echte Alben und Bilder unverändert – bis auf die Merker der Einführung (mat_meta, „einfuehrung:…“).
        u.sql("DELETE FROM mat_meta WHERE schluessel LIKE 'einfuehrung:%'")
        # Die Konten tragen ihre letzte Anmeldung (die Seiten der Durchläufe melden sich an) – dort zählen nur die Zeilen.
        nachher = _pruefsummen(u)
        anders = sorted(t for t in set(summe) | set(nachher) if summe.get(t) != nachher.get(t) and t != "users")
        assert not anders, anders
        assert [r["id"] for r in u.sql("SELECT id FROM users ORDER BY id")] == konten
        assert _medien(u) == medien
        assert u.sql("SELECT title FROM albums WHERE id = ?", (aid,))[0]["title"] == ECHT
        assert u.sql("SELECT COUNT(*) AS n FROM albums")[0]["n"] == 1
    print("Browser bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_browser()
