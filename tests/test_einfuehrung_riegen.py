"""Interaktive Einführung – Übungen der Riegenkarten (Bauvorlage planung/tutorial/entwurf.md 3.4 und 5.3):
python tests/test_einfuehrung_riegen.py  oder  pytest tests/test_einfuehrung_riegen.py

1. Statisch: pruefungen.js wechselt die Seite und öffnet Druckansichten nur über S.ziel (Ausnahme: der Weg nach /login);
   die Übungsdatei nennt nur Platzhalter („Übung“, „Platzhalter“), keine Adressen außer /static/uebung/ und keine
   Mailadressen, alle Kennungen liegen in 930000001–930000099; darf_leiten ist im Grundteil falsch, sonst wahr.
2. Browser (tests/einfuehrung_browser.py; ohne Chromium „übersprungen“ mit rc 0): jeder Teil (Grundteil, Leitung,
   Redakteur) bei 1280×900 (Maus) und 360×740 (Telefon, Touch – Karten statt Tabelle) bis „Geschafft“ – ohne Anfrage
   an /api/ (außer Merker und /api/me) und /media/, ohne Seite ohne Übungskennung, ohne Konsolenfehler.
3. Daneben: Ein echter Lehrgang mit Platzhalter-Teilnehmenden erscheint in der Übung nicht und bleibt unverändert
   (Prüfsumme der Riegenkarten-Tabellen); eine Druckansicht meldet „In der Übung nicht verfügbar.“ statt sich zu öffnen
   (kein Seitenwechsel, keine Kennung an ihrer Adresse);
   eine Stoppuhr mit Übungskennung räumt „Übung unterbrechen“ weg, eine echte bleibt.
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
# Die Führung zeigt einen Schritt (oder „Hier geht es in der Übung nicht weiter.“) und leitet nicht gerade um.
BEREIT = ("(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand(); "
          "return z && (z.bereit || z.sackgasse) && !z.umgeleitet; })()")
TEILE = ("grund", "leitung", "redakteur")


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


# --- 1. Statisch ---------------------------------------------------------------------------------------------------------

def test_statisch():
    js = lies("app/static/js/pruefungen.js")
    # Jeder programmatische Seitenwechsel und jede Druckansicht über S.ziel – bis auf den Weg nach /login.
    stellen = re.findall(r"(location\.href\s*=[^;]*;|location\.(?:replace|assign)\([^;]*;|window\.open\([^;]*;)", js)
    assert len(stellen) == 10, stellen
    for s in stellen:
        assert "S.ziel(" in s or '"/login?next="' in s, s
    assert js.count("S.ziel(") == 9
    for alt in ('location.href = `/riegenkarten/${lg.id}#teilnehmer`', 'window.open(`/riegenkarten/'):
        assert alt not in js, alt
    # Die Übungsdatei: nur Platzhalter, nur eigene Kennungen, keine Medien und keine echten Adressen.
    u = lies("app/static/js/uebung/pruefungen.js")
    kennungen = {int(k) for k in re.findall(r"\b9\d{8}\b", u)}
    assert kennungen and all(930000001 <= k <= 930000099 for k in kennungen), sorted(kennungen)
    assert "/media/" not in u and "@" not in u and "http" not in u
    assert all(a[1:].startswith("/static/uebung/") for a in re.findall(r"[\"'`]/[^\"'`]*", u) if "/static/" in a)
    bestand = u[u.index("function bestand()"):u.index("function neueKennung(")]
    namen = re.findall(r'(?:bezeichnung|titel|name|vorname|gliederung|beschreibung|kommentar|_name): "([^"]+)"', bestand)
    assert len(namen) > 15, namen
    for name in namen:
        assert "Übung" in name or "Platzhalter" in name or name == "Teilnehmer", name
    assert 'name: `Übung ${nr}`, vorname: "Teilnehmer"' in u
    assert "zeitansatz_sekunden: null" in u and not re.search(r"zeitansatz_sekunden: \d", u)
    # darf_leiten: im Grundteil prüft das Konto nur mit, sonst leitet es den Übungslehrgang.
    assert 'const leitet = () => (STROEMIS.einfuehrung || {}).uebung !== "grund";' in u
    assert "ist_leitung: leitet() }" in u
    # Druckansichten sind keine Dateien – window.open meldet „In der Übung nicht verfügbar.“
    assert "dateien: []," in u
    print("Statisch bestanden.")


# --- 2./3. Browser -------------------------------------------------------------------------------------------------------

def _pruefsumme(u):
    """Prüfsumme aller Zeilen der Riegenkarten (pruef_*) – die Übung darf daran nichts ändern."""
    tabellen = [z["name"] for z in u.sql("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'pruef_%' "
                                         "ORDER BY name")]
    h = hashlib.sha256()
    for t in tabellen:
        for zeile in u.sql(f"SELECT * FROM {t} ORDER BY rowid"):
            h.update(json.dumps([t, dict(zeile)], sort_keys=True, default=str).encode())
    return h.hexdigest()


def _echter_lehrgang(u):
    """Der Lehrgang „Übung Platzhalter“ der Testhilfe (die Leitung leitet ihn) bekommt Platzhalter-Teilnehmende."""
    lid = u.sql("SELECT id FROM pruef_lehrgaenge WHERE titel = 'Übung Platzhalter'")[0]["id"]
    for nr in (1, 2):
        r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"vorname": "Echt", "name": f"Platzhalter {nr}"})
        assert r.status_code == 201, r.get_json()
    return lid


def _unterbrechen(s, wo):
    """Esc → „Unterbrechen“: zurück auf der echten Startseite. Liefert die Stelle im Netzprotokoll davor."""
    assert s.warte(BEREIT, 15), wo
    s.taste()
    assert s.warte("Boolean(document.querySelector('dialog[open] #c-ok'))", 5), wo
    s.sammeln()
    grenze = len(s.anfragen)
    assert s.klick("dialog[open] #c-ok") is None
    assert s.warte("location.pathname === '/riegenkarten' && !location.search && document.readyState === 'complete'", 10), wo
    return grenze


def _nebenproben(u, breite, hoehe, touch):
    """Übung der Leitung: der echte Lehrgang fehlt in der Liste; Druckansicht → Toast; Stoppuhr-Reste gehen mit."""
    wo = f"{breite}×{hoehe}"
    bereit = BEREIT
    u.merker_leeren("leitung")
    s = u.seite("leitung", breite, hoehe, touch)
    try:
        # Der Start führt zur Startadresse des Teils (Lehrgang, Reiter „Teilnehmende“) …
        s.oeffnen("/riegenkarten?uebung=leitung", warten=0.3)
        assert s.warte("location.pathname === '/riegenkarten/930000001' && " + bereit, 15), wo
        s.sammeln()
        von = len(s.anfragen)
        # … und über „Alle Lehrgänge“ zur Liste: Darin steht nur der Übungslehrgang, nicht der echte.
        s.js("document.querySelector('a.zurueck').click(); true")
        assert s.warte("location.pathname === '/riegenkarten' && location.search.includes('uebung=leitung') "
                       "&& Boolean(document.querySelector('#lg-tabelle tr[data-id]'))", 10), wo
        liste = s.js("document.getElementById('lg-liste').textContent")
        assert "Übungslehrgang" in liste and "Übung Platzhalter" not in liste, liste
        # Druckansicht „je Teilnehmende“: kein neuer Reiter, nur der Toast.
        s.oeffnen("/riegenkarten/930000001?uebung=leitung#bewertung", warten=0.3)
        assert s.warte("Boolean(document.querySelector('[data-act=bew-ansicht][data-a=tn]'))", 10), wo
        s.js("document.querySelector('[data-act=bew-ansicht][data-a=tn]').click(); true")
        assert s.warte("Boolean(document.querySelector('[data-act=bew-tn-druck]'))", 5), wo
        s.js("(() => { window.__offen = []; const o = window.open; window.open = (...a) => { const r = o.apply(window, a); "
             "window.__offen.push([a[0], r === null]); return r; }; document.querySelector('[data-act=bew-tn-druck]').click(); })()")
        assert s.warte("document.getElementById('toast').textContent === 'In der Übung nicht verfügbar.'", 5), wo
        # Die Druckansicht hat keinen Übungszweig: S.ziel gibt sie ohne Kennung zurück, die Schicht öffnet nichts und
        # bleibt auf der Seite (Nachbesserung nach der Sicherheitsprüfung, d3f803b).
        adr, nichts = s.js("window.__offen[0]")
        assert "/druck?" in adr and "uebung=" not in adr and nichts, adr
        s.b.warten(0.5)
        assert s.js("location.pathname + location.search") == "/riegenkarten/930000001?uebung=leitung", wo
        assert s.js("window.__offen.length") == 1, wo
        # Stoppuhr (gehört nicht in die Übung): Was eine Übungsseite unter „pruef:stoppuhr“ ablegt, ist nach „Übung
        # unterbrechen“ auf der echten Seite nicht mehr da …
        s.js("localStorage.setItem('pruef:stoppuhr', JSON.stringify({ tid: 930000011, lid: 930000031, lehrgang: 930000001, "
             "start: Date.now(), tn_name: 'Teilnehmer Übung 1', leistung: 'Platzhalter-Leistung A' })); true")
        grenze = _unterbrechen(s, wo)
        assert s.js("localStorage.getItem('pruef:stoppuhr')") is None
        assert s.js("Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter((k) => /9[0-3]\\d{7}/.test(k))") == []
        # … eine echte (anderer Lehrgang) übersteht eine Übung.
        s.js("localStorage.setItem('pruef:stoppuhr', JSON.stringify({ tid: 5, lid: 6, lehrgang: 7, start: Date.now(), "
             "tn_name: 'Echt', leistung: 'Echt' })); true")
        s.oeffnen("/riegenkarten/930000001?uebung=leitung&ablauf=1", warten=0.3)
        assert s.warte(bereit, 15), wo
        _unterbrechen(s, wo)
        assert s.js("JSON.parse(localStorage.getItem('pruef:stoppuhr')).lehrgang") == 7
        s.js("localStorage.removeItem('pruef:stoppuhr'); true")
        s.sammeln()
        befunde = s.netz_befunde(grenze, von) + s.fehler
        assert not befunde, befunde
    finally:
        s.schliessen()
    u.merker_leeren("leitung")


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _echter_lehrgang(u)
        vorher = _pruefsumme(u)
        for breite, hoehe, touch in GROESSEN:
            for teil in TEILE:
                befunde = u.durchlauf("pruefungen", teil, breite, hoehe, touch)
                assert not befunde, (teil, breite, befunde)
                print(f"Durchlauf {teil} {breite}×{hoehe} bestanden.")
            _nebenproben(u, breite, hoehe, touch)
            print(f"Nebenproben {breite}×{hoehe} bestanden.")
        assert _pruefsumme(u) == vorher, "Die Übung hat echte Lehrgänge verändert."
    print("Browser bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_browser()
