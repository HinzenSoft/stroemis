"""Interaktive Einführung – Übungen der Materialablage (Bauvorlage planung/tutorial/entwurf.md 3.1 und 5.3):
python tests/test_einfuehrung_material.py  oder  pytest tests/test_einfuehrung_material.py

1. Statisch: In material.js, suche.js, global.js und freigaben.js geht jeder programmatische Seitenwechsel über
   S.ziel(…) (außer den Wegen nach /login); die Übungsdatei app/static/js/uebung/material.js nennt nur Platzhalter
   („Übung“, …@example.invalid, Dateien unter /static/uebung/), alle Kennungen liegen in 900000001–900000099, und ihre
   Teile und Abläufe stimmen mit app/einfuehrung.py überein.
2. Durchlauf jedes Teils (Grundteil, Prüfer, Materialwart, Material-Verwaltung) bei 1280×900 (Maus) und 360×740
   (Telefon, Touch) mit der Hilfe tests/einfuehrung_browser.py bis „Geschafft“ – ohne fehlendes oder verdecktes Ziel,
   ohne unbeantwortete Anfrage (die Hilfe sammelt sie auf jeder Seite der Übung), ohne Anfrage an /api/ (außer Merker, /api/me) oder
   /media/, ohne Seite ohne Übungskennung, ohne Konsolenfehler und ohne waagerechten Bildlauf. Danach ist der Bestand der
   Datenbank unverändert (Prüfsumme ohne die Merker der Einführung). Ohne Chromium „übersprungen“ mit rc 0.
3. Dasselbe mit einem Testkatalog (Wunsch vom 04.11.2026, Platzhalter aus tests/test_einfuehrung_katalog.py): Produkte
   und Formulare aus dem Katalog, ihre Bilder laden als einzige Medien, dazu der Grundteil bei 844×390 (Touch).
Alle Inhalte sind Platzhalter."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from einfuehrung_browser import KONTO_JE_TEIL, Seite, Umgebung, uebersprungen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTE = ("app/material/static/material.js", "app/material/static/suche.js", "app/material/static/global.js",
           "app/material/static/freigaben.js")
UEBUNG = "app/static/js/uebung/material.js"
GROESSEN = ((1280, 900, False), (360, 740, True))
TEILE = ("grund", "pruefer", "materialwart", "verwaltung")


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


# --- 1. Statisch ---------------------------------------------------------------------------------------------------------

def _node():
    for kandidat in ("/home/harness/devtools/node/bin/node", shutil.which("node") or ""):
        if kandidat and os.path.isfile(kandidat):
            return kandidat
    return None


def test_statisch():
    # Jeder programmatische Seitenwechsel über S.ziel – sonst lüde er in der Übung die echte Seite (Bauvorlage 2.2).
    for pfad in SKRIPTE:
        for nr, zeile in enumerate(lies(pfad).splitlines(), 1):
            for treffer in re.finditer(r"location\.href\s*=(?!=)|location\.(?:replace|assign)\(|window\.open\(", zeile):
                rest = zeile[treffer.end():].lstrip()
                if rest.startswith("S.ziel(") or rest.startswith('"/login') or "/login?next=" in rest[:40]:
                    continue
                raise AssertionError(f"{pfad}:{nr}: Seitenwechsel ohne S.ziel: {zeile.strip()}")
    js = lies(UEBUNG)
    # Kennungen nur im Bereich der Materialablage; keine fremden Adressen, nur Übungsdateien und example.invalid.
    for zahl in re.findall(r"\b9\d{8}\b", js):
        assert 900000001 <= int(zahl) <= 900000999, zahl
    assert not re.search(r"https?://", js), "keine Adressen außerhalb"
    assert "/media/" not in js, "keine echten Medien"
    for adresse in re.findall(r'"(/static/[^"]+)"', js):
        assert adresse.startswith("/static/uebung/") and os.path.isfile(os.path.join(WURZEL, "app", adresse[1:])), adresse
    for mail in re.findall(r"[\w.+-]+@[\w.-]+", js):
        assert mail.endswith("@example.invalid"), mail
    # Namen von Ordnern, Produkten, Personen, Formular und Prüfpunkten: Platzhalter mit „Übung“ bzw. „Platzhalter“.
    namen = re.findall(r'\b(?:ordner\(ID\.\w+|produkt\(ID\.\w+, "\w+"|name:)\s*,?\s*"([^"]+)"', js)
    for n in namen:
        if n in ("Gesperrt", "Ausgesondert"):            # die Systemordner jeder Gliederung heißen so
            continue
        assert "Übung" in n or "Platzhalter" in n, n
    assert "Übungsperson A" in js and "Übungsperson B" in js and 'manufacturer: "Übung"' in js
    assert "data:image/png;base64," in js and "interval_months: null" in js and "lifetime_years: null" in js
    # Teile und Abläufe wie app/einfuehrung.py (wie tests/test_einfuehrung.py, hier mit allen Startadressen).
    node = _node()
    if node:
        skript = ("const reg = {}; globalThis.window = globalThis; globalThis.document = { getElementById: () => null };"
                  "globalThis.S = { einfuehrung: { modul(n, d) { reg[n] = d; } } };"
                  f"require({json.dumps(os.path.join(WURZEL, UEBUNG))});"
                  "const d = reg.material; const out = {};"
                  "for (const [k, t] of Object.entries(d.teile)) out[k] = t.ablaeufe.map((a) => [a.titel, a.start, a.schritte.length,"
                  " a.schritte.filter((s) => s.warten && !s.probe && !s.warten.klick).length]);"
                  "out._bestand = d.bestand(); out._antworten = d.antworten.length;"
                  "console.log(JSON.stringify(out));")
        r = subprocess.run([node, "-e", skript], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        teile = json.loads(r.stdout)
        sys.path.insert(0, WURZEL)
        from app import einfuehrung
        for t in einfuehrung.TEILE["material"]:
            ablaeufe = teile[t["teil"]]
            assert [a[0] for a in ablaeufe] == list(t["ablaeufe"]), (t["teil"], ablaeufe)
            assert ablaeufe[0][1] == t["start"], (t["teil"], ablaeufe[0])
            for titel, start, schritte, ohne_probe in ablaeufe:
                assert start.startswith("/materialablage") and schritte >= 4 and not ohne_probe, (t["teil"], titel)
        b = teile["_bestand"]
        assert {a["inventory_no"] for a in b["artikel"]} == {"Ü-0001", "Ü-0002", "Ü-0003"}, b
        assert [p["model"] for p in b["produkte"]] == ["Übungsgurt", "Übungshelm", "Übungsseil"]
        # Ohne Katalog (STROEMIS.einfuehrung.katalog fehlt): nur das Übungsformular mit drei Platzhalter-Punkten.
        assert [f["titel"] for f in b["formulare"]] == ["Übungsformular"]
        assert [p["art"] for p in b["formulare"][0]["punkte"]] == ["yesno", "text", "number"]
        assert all(p["text"].startswith("Platzhalter") for p in b["formulare"][0]["punkte"])
        assert all("Übung" in o["name"] or o["system_kind"] for o in b["ordner"])
        assert teile["_antworten"] >= 20
    print("Statisch bestanden.")


# --- 2. Durchläufe -----------------------------------------------------------------------------------------------------

def pruefsumme(u):
    """Prüfsumme der Datenbank ohne die Merker der Einführung (die schreibt die Übung mit Absicht)."""
    with u.app.app_context():
        from app import db
        zeilen = [z for z in db.get_db().iterdump() if "einfuehrung:" not in z]
    return hashlib.sha256("\n".join(zeilen).encode()).hexdigest()


def durchlauf(u, teil, breite, hoehe, touch, probe=None):
    rolle = KONTO_JE_TEIL[("material", teil)]
    u.merker_leeren(rolle)
    s = Seite(u, rolle, breite, hoehe, touch)
    u.seiten.append(s)
    try:
        vorher = pruefsumme(u)
        los = time.time()
        befunde = s.durchlauf("material", teil, foto=probe)
        dauer = time.time() - los
        if pruefsumme(u) != vorher:
            befunde.append("Die Datenbank hat sich in der Übung verändert.")
        return befunde, dauer
    finally:
        s.schliessen()


def test_durchlauf():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        for breite, hoehe, touch in GROESSEN:
            for teil in TEILE:
                befunde, dauer = durchlauf(u, teil, breite, hoehe, touch)
                assert not befunde, (teil, breite, befunde)
                print(f"material/{teil} {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({dauer:.1f} s)")
    print("Durchläufe bestanden.")


# Was je Teil mit dem Testkatalog auf den Seiten der Übung stehen muss (Namen aus tests/test_einfuehrung_katalog.py).
IM_TEXT = {"grund": ("Platzhalter Gurt mit Bild",), "pruefer": ("Platzhalter Seil mit Formular", "Platzhalter Datum"),
           "materialwart": ("Platzhalter Karabiner",), "verwaltung": ("Platzhalter Gurt mit Bild", "Platzhalter Gurte")}
BILDPROBE = """(() => {
  const b = [...document.images].filter((i) => (i.getAttribute('src') || '').startsWith('/media/'));
  return { kaputt: b.filter((i) => i.complete && !i.naturalWidth).map((i) => i.getAttribute('src')),
           geladen: b.filter((i) => i.naturalWidth).map((i) => i.getAttribute('src')), text: document.body.innerText };
})()"""


def test_durchlauf_katalog():
    """Mit einem Testkatalog (Platzhalter aus tests/test_einfuehrung_katalog.py): alle vier Teile bei 1280×900 (Maus) und
    360×740 (Touch), der Grundteil dazu bei 844×390 (Touch). Die Seiten zeigen die Produkte und Formulare der Auswahl, ihre
    Bilder laden (und nur sie, Umgebung.medien_frei), kein Bild bleibt kaputt, die Datenbank – Bestand und Katalog – bleibt
    unverändert."""
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_einfuehrung_katalog import katalog_platzhalter
    with Umgebung() as u:
        katalog_platzhalter(u.app)
        with u.app.test_request_context():
            from app import einfuehrung
            auswahl = einfuehrung.katalog_material()
            u.medien_frei = einfuehrung.katalog_bilder()
        assert {r: p and p["modell"] for r, p in auswahl["produkte"].items()} == {
            "gurt": "Gurt mit Bild", "seil": "Seil mit Formular", "helm": "Karabiner"}, auswahl
        geladen = set()
        for breite, hoehe, touch, teile in ((1280, 900, False, TEILE), (360, 740, True, TEILE), (844, 390, True, ("grund",))):
            for teil in teile:
                gesehen, kaputt = [], set()

                def probe(seite, _z, kaputt=kaputt, gesehen=gesehen):
                    r = seite.js(BILDPROBE)
                    kaputt.update(r["kaputt"])
                    geladen.update(r["geladen"])
                    gesehen.append(r["text"])
                befunde, dauer = durchlauf(u, teil, breite, hoehe, touch, probe)
                befunde += [f"Bild lädt nicht: {b}" for b in sorted(kaputt)]
                befunde += [f"Nicht auf den Seiten: {w}" for w in IM_TEXT[teil] if not any(w in t for t in gesehen)]
                assert not befunde, (teil, breite, befunde)
                print(f"material/{teil} mit Katalog {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({dauer:.1f} s)")
        assert geladen and geladen <= u.medien_frei, (geladen, u.medien_frei)
    print("Durchläufe mit Katalog bestanden.")


def test_systemnummer():
    """Systemnummer (Nachzug 10.11.2026, wie bestand.artikel_json und bestand.anlegen): Die Übungsartikel tragen
    `systemnummer` „STR-“ mit der Zahl ihrer Inventarnummer; ein Artikel ohne Herstellernummer bekommt sie als
    Seriennummer (vom System, `systemnummer` dann null), einer mit Herstellernummer behält sie. Alles in der Schicht der
    Übung – keine Anfrage erreicht den Server."""
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        s = Seite(u, "materialwart", 1280, 900, False)
        u.seiten.append(s)
        try:
            s.oeffnen(u.adresse("material", "materialwart"))
            assert s.warte("window.S && S.einfuehrung && S.einfuehrung.zustand() && S.einfuehrung.zustand().bereit", 15)
            vorher = pruefsumme(u)
            r = s.js("""(async () => {
              const post = (sn) => fetch('/api/material/artikel', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: 900000023, folder_id: 900000002, serial_no: sn }) }).then((x) => x.json());
              const alt = (await fetch('/api/material/artikel/900000011').then((x) => x.json())).artikel;
              const ohne = (await post('')).artikel;
              const mit = (await post('Ü-SN-9')).artikel;
              return { alt: [alt.serial_no, alt.serial_generated, alt.systemnummer],
                       ohne: [ohne.inventory_no, ohne.serial_no, ohne.serial_generated, ohne.systemnummer],
                       mit: [mit.serial_no, mit.serial_generated, mit.systemnummer] };
            })()""")
            assert r["alt"] == ["Ü-SN-0001", False, "STR-0001"], r
            assert r["ohne"] == ["Ü-0004", "STR-0004", True, None], r
            assert r["mit"] == ["Ü-SN-9", False, "STR-0005"], r
            assert pruefsumme(u) == vorher
            s.sammeln()
            assert not s.netz_befunde() and not s.fehler, (s.netz_befunde(), s.fehler)
        finally:
            s.schliessen()
    print("Systemnummer bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_durchlauf()
    test_durchlauf_katalog()
    test_systemnummer()
