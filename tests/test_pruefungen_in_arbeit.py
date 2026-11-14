"""Wünsche des Nutzers zu den Riegenkarten vom 14.11.2026: „Kriterien abhaken und speichern können, ohne zwingend die
Bewertung anzugeben“ und „Speichern auch ohne den Speichern-Button zu drücken“.
python tests/test_pruefungen_in_arbeit.py  oder  pytest tests/test_pruefungen_in_arbeit.py

Vorher entstand ein Versuch erst mit „Bewertung speichern“, und ohne bestanden/mangelhaft ging das nicht. Jetzt
(Entscheidungen des Nutzers): Ein Versuch ohne Bewertung ist „in Arbeit“ und zählt als offen; der Dialog speichert alles
von selbst (Kriterien und Bewertung sofort, Zeit und Kommentar kurz nach dem Tippen, Medien beim Auswählen), „mangelhaft“
erst mit Kommentar; beim Ändern einer abgegebenen Bewertung gibt es einen Verlaufseintrag je Öffnen des Dialogs; ein
Versuch in Arbeit bleibt stehen, bis jemand bewertet oder ihn löscht, und das Lehrgangsergebnis lässt sich trotzdem
vermerken. Geprüft am Server (Zustände, Prüfer, Verlauf, Mängel, Zähler, Einfrieren) und in der echten App in Chromium
am Telefon (ohne Chromium übersprungen)."""
import json
import os
import sys
import tempfile
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from test_pruefungen import H, ausbilder_konto, umgebung  # noqa: E402


def test_server():
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        assert adm.put(f"/api/admin/users/{pr_id}", json={"rechte": {"pruefungen": 2}}).status_code == 200
        zweit_id = ausbilder_konto(adm, "zweit@example.org", "Zacharias Zweitprüfer")
        zweit = app.test_client()
        assert zweit.post("/api/auth/login", json={"email": "zweit@example.org", "password": "passwort1"}).status_code == 200
        r = pr.post("/api/pruefungen/lehrgaenge", json={"titel": "Zwischenstand", "ausbilder": [
            {"user_id": pr_id, "funktion": "Leitung", "ist_leitung": True}, {"user_id": zweit_id, "funktion": "Prüfer"}]})
        assert r.status_code == 201, r.get_json()
        lid = r.json["lehrgang"]["id"]
        r = pr.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Knoten", "kriterien": ["Achter", "Palstek"]})
        assert r.status_code == 201, r.get_json()
        lei = r.json["leistung"]
        k1, k2 = [k["id"] for k in pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]["leistungen"][0]["kriterien"]]
        anna, bert, clara = [pr.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": n, "vorname": v}).json["teilnehmer"]
                             for n, v in (("Adler", "Anna"), ("Becker", "Bert"), ("Christ", "Clara"))]
        zelle = lambda tn: f"/api/pruefungen/teilnehmer/{tn['id']}/leistungen/{lei['id']}/versuche"  # noqa: E731

        def detail():
            return pr.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]

        def zellwert(tn):
            t = next(x for x in detail()["teilnehmer"] if x["id"] == tn["id"])
            return t["leistungen"].get(str(lei["id"]))

        # 1. Nur ein Haken, keine Bewertung: Versuch in Arbeit, die Zelle zählt nicht als abgenommen
        r = zweit.post(zelle(anna), json={"ergebnis": "", "kriterien": {str(k1): True}, "sitzung": "s1"})
        assert r.status_code == 201 and r.json["versuch"]["ergebnis"] == "", r.get_json()
        va = r.json["versuch"]
        z = zellwert(anna)
        assert z["status"] == "in_arbeit" and z["kriterien_erfuellt"] == 1, z
        assert pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"][0]["zellen_abgenommen"] == 0
        # Ein zweiter Versuch neben dem in Arbeit geht nicht – weiter geht es mit diesem
        assert pr.post(zelle(anna), json={"ergebnis": "bestanden"}).status_code == 409
        # Weiter in Arbeit: Zeit und Kommentar, ohne Verlauf und ohne „bearbeitet“
        r = zweit.put(f"/api/pruefungen/versuche/{va['id']}", json={"zeit_sekunden": 95, "kommentar": "Ruhig.", "sitzung": "s1",
                                                                      "kriterien": {str(k1): True, str(k2): False}})
        assert r.status_code == 200, r.get_json()
        v = r.json["versuch"]
        assert v["ergebnis"] == "" and v["verlauf"] == [] and v["bearbeitet_am"] is None and v["zeit_sekunden"] == 95, v
        # „mangelhaft“ braucht auch hier den Kommentar; zurück auf „ohne Bewertung“ geht eine Bewertung nicht
        assert pr.put(f"/api/pruefungen/versuche/{va['id']}", json={"ergebnis": "mangelhaft", "kommentar": ""}).status_code == 400
        # 2. Wer bewertet, ist der Prüfer – auch wenn jemand anders angefangen hat
        r = pr.put(f"/api/pruefungen/versuche/{va['id']}", json={"ergebnis": "bestanden", "sitzung": "s2"})
        assert r.status_code == 200, r.get_json()
        v = r.json["versuch"]
        assert v["ergebnis"] == "bestanden" and v["geprueft_von_name"] == "Petra Prüferin" and v["verlauf"] == [], v
        assert v["bearbeitet_am"] is None and v["kriterien"] == {str(k1): True, str(k2): False}, v
        assert zellwert(anna)["status"] == "bestanden"
        assert pr.put(f"/api/pruefungen/versuche/{va['id']}", json={"ergebnis": ""}).status_code == 400

        # 3. Ändern einer Bewertung: ein Verlaufseintrag je Öffnen (sitzung) und Person
        def aendern(c, text, sitzung):
            r = c.put(f"/api/pruefungen/versuche/{va['id']}", json={"kommentar": text, "sitzung": sitzung})
            assert r.status_code == 200, r.get_json()
            return r.json["versuch"]
        assert len(aendern(pr, "R", "s3")["verlauf"]) == 1
        assert len(aendern(pr, "Ru", "s3")["verlauf"]) == 1           # derselbe Dialog: nachgeführt
        v = aendern(pr, "Ruhig und sicher.", "s3")
        assert len(v["verlauf"]) == 1 and v["verlauf"][0]["kommentar"] == "Ruhig." and v["kommentar"] == "Ruhig und sicher.", v
        assert len(aendern(pr, "Neu geöffnet.", "s4")["verlauf"]) == 2      # neues Öffnen: eigener Eintrag
        v = aendern(zweit, "Andere Person.", "s4")                            # gleiche Kennung, andere Person
        assert len(v["verlauf"]) == 3 and v["verlauf"][-1]["kommentar"] == "Neu geöffnet.", v
        assert len(aendern(pr, "Ohne Kennung.", "")["verlauf"]) == 4          # ohne Kennung wie bisher

        # 4. Ein ganz geleerter Versuch in Arbeit fällt weg
        r = zweit.post(zelle(clara), json={"ergebnis": "", "kriterien": {str(k2): True}})
        assert r.status_code == 201, r.get_json()
        r = zweit.put(f"/api/pruefungen/versuche/{r.json['versuch']['id']}", json={"kriterien": {}})
        assert r.status_code == 200 and r.json["versuch"] is None, r.get_json()
        assert zellwert(clara) is None and pr.get(zelle(clara)).json["versuche"] == []

        # 5. Nachprüfung in Arbeit: Der Mangel bleibt offen
        r = pr.post(zelle(bert), json={"ergebnis": "mangelhaft", "kommentar": "Palstek fehlt."})
        assert r.status_code == 201, r.get_json()
        v1 = r.json["versuch"]
        r = pr.post(zelle(bert), json={"ergebnis": "", "nachpruefung": True, "kriterien": {str(k2): True}})
        assert r.status_code == 201 and r.json["versuch"]["ist_nachpruefung"], r.get_json()
        np = r.json["versuch"]
        assert zellwert(bert)["status"] == "nachpruefung_in_arbeit"
        m = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel?nur_offen=1").json["maengel"]
        assert [(x["versuch"]["id"], x["nachpruefung_status"]) for x in m] == [(v1["id"], "offen")], m
        assert pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"][0]["offene_maengel"] == 1
        assert pr.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"][0]["zellen_abgenommen"] == 2
        # Löschen eines Versuchs in Arbeit: wie jeder Versuch – Sache der Leitung
        assert zweit.delete(f"/api/pruefungen/versuche/{np['id']}", headers=H).status_code == 403
        r = pr.post(zelle(bert), json={"ergebnis": "bestanden", "nachpruefung": True})
        assert r.status_code == 409, "neben der Nachprüfung in Arbeit keine zweite"
        r = pr.put(f"/api/pruefungen/versuche/{np['id']}", json={"ergebnis": "bestanden"})
        assert r.status_code == 200, r.get_json()
        m = pr.get(f"/api/pruefungen/lehrgaenge/{lid}/maengel").json["maengel"]
        assert [x["nachpruefung_status"] for x in m] == ["bestanden"], m

        # 6. Lehrgangsergebnis trotz Versuch in Arbeit; danach ist er mit eingefroren
        r = zweit.post(zelle(clara), json={"ergebnis": "", "kommentar": "Angefangen."})
        assert r.status_code == 201, r.get_json()
        vc = r.json["versuch"]
        assert pr.put(f"/api/pruefungen/teilnehmer/{clara['id']}/ergebnis", json={"ergebnis": "nicht_bestanden"}).status_code == 200
        assert zweit.put(f"/api/pruefungen/versuche/{vc['id']}", json={"ergebnis": "bestanden"}).status_code == 409
        assert zellwert(clara)["status"] == "in_arbeit"
        # Ohne Recht in den Riegenkarten nichts davon
        assert nix.post(zelle(anna), json={"ergebnis": ""}).status_code == 403


def tipp(s, sel):
    """Ein Tipp wie mit dem Finger – vorher ins Bild gerollt (am Telefon liegen Bewertung und „Schließen“ weiter unten)."""
    s.js(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{ block: 'center' }})")
    time.sleep(0.2)
    befund = s.klick(sel)
    assert not befund, befund


def _browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        r = u.adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Autosave", "status": "laufend", "ausbilder": [
            {"user_id": u.ids["redakteur"], "funktion": "Leitung", "ist_leitung": True}]})
        assert r.status_code == 201, r.get_json()
        lid = r.json["lehrgang"]["id"]
        r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen", json={"bezeichnung": "Knoten", "kriterien": ["Achter", "Palstek"]})
        assert r.status_code == 201, r.get_json()
        pl = r.json["leistung"]["id"]
        r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": "Adler", "vorname": "Anna"})
        assert r.status_code == 201, r.get_json()
        tid = r.json["teilnehmer"]["id"]
        zelle = f"/api/pruefungen/teilnehmer/{tid}/leistungen/{pl}/versuche"
        versuche = lambda: u.adm.get(zelle).json["versuche"]  # noqa: E731
        s = u.seite("redakteur", 390, 844, touch=True)
        try:
            s.oeffnen(f"/riegenkarten/{lid}#bewertung", warten=1.5)
            s.ruhe(1.0)
            tipp(s, f'[data-act="zelle"][data-tid="{tid}"][data-lid="{pl}"]')
            assert s.warte("!!document.querySelector('dialog[open] #bw-kriterien')"), "Dialog"
            # Kein Speichern-Knopf mehr, nur „Schließen“ und der Stand
            assert s.js("!document.querySelector('#bw-save') && !!document.querySelector('#bw-schliessen') && !!document.querySelector('#bw-stand')")
            # 1. Ein Haken speichert sofort einen Versuch in Arbeit
            tipp(s, "#bw-kriterien .krit-zeile")
            assert s.warte("document.querySelector('#bw-stand').classList.contains('ok')", sek=10), s.js("document.querySelector('#bw-stand').textContent")
            v = versuche()
            assert len(v) == 1 and v[0]["ergebnis"] == "" and list(v[0]["kriterien"].values()) == [True], v
            # 2. Kommentar: kurz nach dem Tippen, ohne Knopf
            s.js("(() => { const k = document.querySelector('#bw-komm'); k.value = 'Achter sauber.'; k.dispatchEvent(new Event('input')); })()")
            assert s.warte("document.querySelector('#bw-stand').textContent.startsWith('Ungespeichert')", sek=3)
            for _ in range(30):
                if versuche()[0]["kommentar"] == "Achter sauber.":
                    break
                time.sleep(0.2)
            assert versuche()[0]["kommentar"] == "Achter sauber.", versuche()
            # 3. „mangelhaft“ wartet auf den Kommentar – ohne Kommentar bleibt der Versuch in Arbeit
            s.js("(() => { const k = document.querySelector('#bw-komm'); k.value = ''; k.dispatchEvent(new Event('input')); })()")
            tipp(s, "#bw-wahl button[data-erg=mangelhaft]")
            assert s.warte("document.querySelector('#bw-komm').classList.contains('fehler')", sek=5), "Fehler am Kommentar"
            time.sleep(1.2)
            assert versuche()[0]["ergebnis"] == "" and versuche()[0]["kommentar"] == "", versuche()
            s.js("(() => { const k = document.querySelector('#bw-komm'); k.value = 'Palstek fehlt.'; k.dispatchEvent(new Event('input')); k.dispatchEvent(new Event('blur')); })()")
            for _ in range(30):
                if versuche()[0]["ergebnis"] == "mangelhaft":
                    break
                time.sleep(0.2)
            v = versuche()
            assert len(v) == 1 and v[0]["ergebnis"] == "mangelhaft" and v[0]["kommentar"] == "Palstek fehlt." and v[0]["verlauf"] == [], v
            # 4. Schließen: Die Matrix zeigt das Ergebnis; ein neuer Versuch in Arbeit erscheint als „in Arbeit“
            tipp(s, "#bw-schliessen")
            assert s.warte(f"(document.querySelector('[data-act=\"zelle\"][data-tid=\"{tid}\"] .txt') || {{}}).textContent?.startsWith('mangelhaft')", sek=10)
            assert s.js("document.documentElement.scrollWidth <= innerWidth"), "kein seitliches Rollen"
            # 5. Bearbeiten einer abgegebenen Bewertung: mehrere Speicherungen, ein Verlaufseintrag
            tipp(s, f'[data-act="zelle"][data-tid="{tid}"][data-lid="{pl}"]')
            assert s.warte("!!document.querySelector('dialog[open] [data-v-edit]')"), "Übersicht mit Bearbeiten"
            tipp(s, "[data-v-edit]")
            assert s.warte("!!document.querySelector('dialog[open] #bw-komm')")
            for text in ("Palstek fehlt, Achter gut.", "Palstek fehlt, Achter sehr gut."):
                s.js(f"(() => {{ const k = document.querySelector('#bw-komm'); k.value = {text!r}; k.dispatchEvent(new Event('input')); k.dispatchEvent(new Event('blur')); }})()")
                for _ in range(30):
                    if versuche()[0]["kommentar"] == text:
                        break
                    time.sleep(0.2)
            v = versuche()
            assert v[0]["kommentar"] == "Palstek fehlt, Achter sehr gut." and len(v[0]["verlauf"]) == 1, v
            assert v[0]["verlauf"][0]["kommentar"] == "Palstek fehlt.", v
            # 6. Offenes beim Schließen: Esc mitten im Tippen speichert noch
            s.js("(() => { const k = document.querySelector('#bw-komm'); k.value = 'Zuletzt getippt.'; k.dispatchEvent(new Event('input')); document.querySelector('#dlg').close(); })()")
            for _ in range(30):
                if versuche()[0]["kommentar"] == "Zuletzt getippt.":
                    break
                time.sleep(0.2)
            assert versuche()[0]["kommentar"] == "Zuletzt getippt." and len(versuche()[0]["verlauf"]) == 1, versuche()
        finally:
            s.schliessen()


def test_browser():
    _browser()


if __name__ == "__main__":
    test_server()
    test_browser()
    print("ok")
