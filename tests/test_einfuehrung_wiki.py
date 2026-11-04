"""Interaktive Einführung – Übungen der Strömipedia (Bauvorlage planung/tutorial/entwurf.md 3.2 und 5.3):
python tests/test_einfuehrung_wiki.py  oder  pytest tests/test_einfuehrung_wiki.py

1. Statisch: wiki.js wechselt Seiten und öffnet Fenster nur über S.ziel (Ausnahme: Wege nach /login); die Übungsdatei
   app/static/js/uebung/wiki.js enthält nur Platzhalter („Übung“, example.invalid, Bilder unter /static/uebung/), alle
   Kennungen im Bereich der Strömipedia (9100000xx), keine fremden Adressen; die Abläufe stehen so in app/einfuehrung.py.
2. Browser (Chromium über tests/einfuehrung_browser.py; ohne Chromium „übersprungen“ mit rc 0): alle drei Teile
   (Grundteil, Redakteur, Verwaltung) bis „Geschafft“ bei 1280×900 (Maus) und 360×740 (Telefon, Touch: Seitenbaum als
   Schublade, Suchzeile #zeilen-suche) – je Schritt Ziel sichtbar, Probe ausgeführt, keine Anfrage an /api/ (außer
   Merker) und /media/, jede Seite mit Übungskennung, keine Konsolenfehler, kein waagerechter Bildlauf. Dazu: eine echte
   Seite erscheint in der Übung nicht, der Router behält die Kennung (auch mit Zurück), der Export meldet „In der Übung
   gibt es diese Datei nicht.“ statt die Seite zu verlassen (die Sprechblase überdeckt das Menü dabei nicht), nach der Übung liegt kein Entwurf mit Übungskennung im Browser, und die
   Datenbank ist danach dieselbe (iterdump-Prüfsumme).
Alle Inhalte sind Platzhalter."""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROESSEN = ((1280, 900, False), (360, 740, True))
TEILE = ("grund", "redakteur", "verwaltung")


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def test_statisch():
    wiki = lies("app/static/js/wiki.js")
    # Jeder Seitenwechsel und jedes neue Fenster geht über S.ziel – im Übungsmodus behält er die Kennung, sonst ändert er
    # nichts (common.js). Nur Wege nach /login (abgelaufene Anmeldung) dürfen ohne.
    for zeile in wiki.splitlines():
        if re.search(r"location\.href\s*=(?!=)|location\.replace\(|location\.assign\(|window\.open\(", zeile):
            assert "S.ziel(" in zeile or "/login" in zeile, zeile.strip()
    assert wiki.count("S.ziel(") >= 7
    uebung = lies("app/static/js/uebung/wiki.js")
    assert not re.search(r"https?://", uebung), "keine fremden Adressen"
    assert "/media/" not in uebung, "keine Medien – Bilder nur unter /static/uebung/"
    for zahl in re.findall(r"\b9\d{8}\b", uebung):
        assert zahl.startswith("9100000"), zahl
    for adresse in re.findall(r'"(/static/[^"]+)"', uebung):
        assert adresse.startswith("/static/uebung/") and os.path.isfile(os.path.join(WURZEL, "app", adresse[1:])), adresse
    for mail in re.findall(r'[\w.-]+@[\w.-]+', uebung):
        assert mail.endswith("@example.invalid"), mail
    for wert in re.findall(r'(?:name|title): "([^"]*)"', uebung):
        assert "Übung" in wert, wert
    for adresse in re.findall(r'"/stroemipedia/([^"?#]+)"', uebung):
        assert adresse.startswith("uebung-"), adresse
    # Die Abläufe stehen in app/einfuehrung.py (Titel, Startadresse des ersten Ablaufs) – Vergleich in test_einfuehrung.py.
    from app import einfuehrung
    teile = {t["teil"]: t for t in einfuehrung.TEILE["wiki"]}
    assert set(teile) == set(TEILE)
    assert teile["grund"]["ablaeufe"] == ("Lesen", "Suchen", "Kommentieren", "Bearbeiten")
    assert teile["grund"]["start"] == "/stroemipedia/uebung-start" and teile["grund"]["minuten"] <= 5
    # Das Übungsbild der Strömipedia: aus dem Erzeugerskript des Grundgerüsts, höchstens 60 KB.
    pfad = os.path.join(WURZEL, "app/static/uebung/wiki/uebungsbild-7.jpg")
    assert os.path.getsize(pfad) <= 60 * 1024
    from PIL import Image
    with Image.open(pfad) as b:
        assert b.format == "JPEG" and b.size == (800, 600)
    print("Statisch bestanden.")


def pruefsumme(u):
    """Prüfsumme aller Tabellen der Strömipedia (iterdump; Anmeldungen und Merker der Einführung zählen nicht)."""
    with u.app.app_context():
        from app import db
        zeilen = [z for z in db.get_db().iterdump() if re.match(r'INSERT INTO "?wiki_', z)]
        return hashlib.sha256("\n".join(zeilen).encode()).hexdigest(), len(zeilen)


def uebungsreste(s):
    """Schlüssel in localStorage/sessionStorage, deren Name eine Übungskennung trägt, und der Übungszustand."""
    return s.js("""(() => { const out = []; for (const sp of [localStorage, sessionStorage]) for (let i = 0; i < sp.length; i++) {
      const k = sp.key(i); if (/\\b9[0-3]\\d{7}\\b/.test(k) || k === 'stroemis-uebung') out.push(k); } return out; })()""")


def _durchlauf(u, teil, breite, hoehe, touch):
    """Ein Teil bis „Geschafft“; danach keine Übungsreste im Browser."""
    rolle = {"grund": "mitglied", "redakteur": "redakteur", "verwaltung": "wikiverwaltung"}[teil]
    s = u.seite(rolle, breite, hoehe, touch)
    try:
        befunde = s.durchlauf("wiki", teil)
        if not befunde:
            reste = uebungsreste(s)
            if reste:
                befunde.append(f"Übungsreste im Browser: {reste}")
        return befunde
    finally:
        s.schliessen()


def _router_export_echt(u):
    """Echte Seite nicht in der Übung, Router mit Kennung (auch Zurück), Export als Hinweis statt Seitenwechsel."""
    s = u.seite("mitglied", 1280, 900, False)
    try:
        s.oeffnen(u.adresse("wiki", "grund"))
        if s.warte("document.querySelector('#dev-hinweis')?.open", 2):
            assert s.klick("#dev-hinweis-ok") is None
        assert s.warte("S.einfuehrung.zustand().bereit && Boolean(document.querySelector('#tree li[data-id=\"910000002\"]'))", 15)
        baum = s.js("document.querySelector('#tree').textContent")
        assert "Übung: Seite lesen" in baum and "Echte Seite" not in baum, baum
        assert s.klick('#tree li[data-id="910000002"] > .row > a') is None
        assert s.warte("location.pathname === '/stroemipedia/uebung-seite-lesen'", 5)
        assert "uebung=grund" in s.js("location.search")
        assert s.warte("document.querySelector('h1.seitentitel')?.textContent.startsWith('Übung: Seite lesen')", 5)
        # Zurück: wieder „Übung: Start“, die Kennung bleibt (kein Neuladen ohne Übung).
        s.js("history.back()")
        assert s.warte("location.pathname === '/stroemipedia/uebung-start' && location.search.includes('uebung=grund')", 5)
        assert s.warte("document.querySelector('h1.seitentitel')?.textContent.startsWith('Übung: Start')", 5)
        s.js("history.forward()")
        assert s.warte("location.pathname === '/stroemipedia/uebung-seite-lesen' && location.search.includes('uebung=grund')", 5)
        # Export aus dem Menü „⋯“ (wiki.js: location.href auf die Datei): Hinweis statt Seitenwechsel, das Menü schließt.
        # Die Sprechblase des laufenden Schritts überdeckt das geöffnete Menü nicht – gewählt wird mit einem echten Klick.
        assert s.warte("document.querySelector('h1.seitentitel')?.textContent.startsWith('Übung: Seite lesen')", 5)
        s.sammeln()
        vorher = len(s.anfragen)
        assert s.klick("#pg-more") is None
        assert s.warte("Boolean(document.querySelector('.menue-schwebend button[data-a=\"export\"]'))", 5)
        s.ruhe()
        assert s.klick('.menue-schwebend button[data-a="export"]') is None
        assert s.warte("[...document.querySelectorAll('.toast, [role=status]')].some((t) => t.textContent.includes('In der Übung gibt es diese Datei nicht.'))", 5)
        s.b.warten(0.5)
        assert s.js("location.pathname") == "/stroemipedia/uebung-seite-lesen"
        assert not s.js("Boolean(document.querySelector('.menue-schwebend'))")
        s.sammeln()
        assert not s.netz_befunde(von=vorher), s.netz_befunde(von=vorher)
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung(dev=True) as u:
        # Eine echte Seite: In der Übung darf sie nirgends erscheinen.
        r = u.adm.post("/api/wiki/pages", json={"title": "Echte Seite", "content": "# Echte Seite\n\nKein Übungstext."})
        assert r.status_code == 201, r.get_json()
        summe = pruefsumme(u)
        _router_export_echt(u)
        for breite, hoehe, touch in GROESSEN:
            for teil in TEILE:
                befunde = _durchlauf(u, teil, breite, hoehe, touch)
                assert not befunde, (teil, breite, befunde)
                merker = {"grund": "mitglied", "redakteur": "redakteur", "verwaltung": "wikiverwaltung"}[teil]
                assert u.merker(merker)[f"wiki:{teil}"]["zustand"] == "erledigt"
            for rolle in ("mitglied", "redakteur", "wikiverwaltung"):
                u.merker_leeren(rolle)
        # Nichts davon hat die Strömipedia erreicht: Seiten, Kommentare, Verlauf, Freigaben, Besuche, Präsenz unverändert.
        assert pruefsumme(u) == summe and summe[1] > 0
        echt = u.adm.get("/api/wiki/tree").get_json()["pages"]
        assert [p["title"] for p in echt] == ["Echte Seite"], echt
    print("Browser bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_browser()
    print(json.dumps({"ok": True}))
