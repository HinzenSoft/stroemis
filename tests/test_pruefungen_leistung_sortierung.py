"""Wunsch des Nutzers zu den Riegenkarten vom 14.11.2026: „In der je Leistung Seite soll nach Teilnehmernamen oder nach
offenen Prüfungen sortieren können“.
python tests/test_pruefungen_leistung_sortierung.py  oder  pytest tests/test_pruefungen_leistung_sortierung.py

Vorher stand die Liste „je Leistung“ in der Reihenfolge des Anlegens. Jetzt (Entscheidung des Nutzers „Noch nicht
bestanden zuerst“) wählt eine Auswahl neben der Leistung „Nach Name“ (Nachname, Vorname) oder „Offene zuerst“: keine
Bewertung oder mangelhaft mit offener Nachprüfung vorn, dann bestanden, Gesperrte (Lehrgangsergebnis vermerkt) am Ende,
je Gruppe nach Name. Die Wahl gilt je Gerät und übersteht das Neuladen. Geprüft in der echten App (Server im Faden) in
Chromium; ohne Chromium übersprungen."""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

# (Name, Vorname, Versuche) – absichtlich nicht alphabetisch angelegt
PERSONEN = [("Weber", "Dora", []), ("Zander", "Zoe", ["bestanden"]), ("Becker", "Bert", ["mangelhaft"]),
            ("Adler", "Anton", ["bestanden"]), ("Müller", "Maria", ["mangelhaft", "bestanden"])]
LISTE = r"[...document.querySelectorAll('.zellen-liste .zelle-zeile .tn-name')].map((e) => e.textContent.replace(/,\s*Lehrgang.*$/, '').trim())"


def _lauf(u):
    r = u.adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Reihenfolge", "status": "laufend", "ausbilder": [
        {"user_id": u.ids["redakteur"], "funktion": "Leitung", "ist_leitung": True}]})
    assert r.status_code == 201, r.get_json()
    lid = r.json["lehrgang"]["id"]
    r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Wurfsack"})
    assert r.status_code == 201, r.get_json()
    pl = r.json["leistung"]["id"]
    for name, vorname, versuche in PERSONEN:
        r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": name, "vorname": vorname})
        assert r.status_code == 201, r.get_json()
        tid = r.json["teilnehmer"]["id"]
        for i, erg in enumerate(versuche):
            r = u.adm.post(f"/api/pruefungen/teilnehmer/{tid}/leistungen/{pl}/versuche",
                           json={"ergebnis": erg, "kommentar": "Wurf zu kurz." if erg == "mangelhaft" else "", "nachpruefung": i > 0})
            assert r.status_code == 201, r.get_json()
        if name == "Zander":
            assert u.adm.put(f"/api/pruefungen/teilnehmer/{tid}/ergebnis", json={"ergebnis": "bestanden"}).status_code == 200

    nach_name = ["Anton Adler", "Bert Becker", "Maria Müller", "Dora Weber", "Zoe Zander"]
    offen_zuerst = ["Bert Becker", "Dora Weber", "Anton Adler", "Maria Müller", "Zoe Zander"]
    s = u.seite("redakteur", 390, 844, touch=True)
    try:
        s.oeffnen(f"/riegenkarten/{lid}#bewertung", warten=1.5)
        s.ruhe(1.0)
        if s.js("!document.querySelector('#bew-sort')"):
            s.klick('[data-act="bew-ansicht"][data-a="leistung"]')
        assert s.warte("!!document.querySelector('#bew-sort')"), "Auswahl der Reihenfolge"
        assert s.js("document.querySelector('#bew-sort').value") == "name"
        assert s.js(LISTE) == nach_name, s.js(LISTE)
        s.js("(() => { const w = document.querySelector('#bew-sort'); w.value = 'offen'; w.dispatchEvent(new Event('change')); })()")
        assert s.warte(f"({LISTE})[0] === 'Bert Becker'", sek=5) and s.js(LISTE) == offen_zuerst, s.js(LISTE)
        # Die Auswahl passt in die Zeile neben der Leistung, ohne seitlich zu rollen
        assert s.js("document.documentElement.scrollWidth <= innerWidth"), "kein seitliches Rollen"
        # Neu laden: die Wahl bleibt
        s.oeffnen(f"/riegenkarten/{lid}#bewertung", warten=1.5)
        s.ruhe(1.0)
        assert s.warte("!!document.querySelector('#bew-sort')") and s.js("document.querySelector('#bew-sort').value") == "offen"
        assert s.js(LISTE) == offen_zuerst, s.js(LISTE)
    finally:
        s.schliessen()


def test_leistung_sortierung():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_leistung_sortierung()
    print("ok")
