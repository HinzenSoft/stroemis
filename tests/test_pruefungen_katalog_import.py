"""Rückmeldung des Nutzers zu den Riegenkarten vom 13.11.2026: „Bei den Riegenkarten lässt sich ein Katalog bei Erstellung
eines Lehrgangs durch Import nicht auswählen/festlegen“.
python tests/test_pruefungen_katalog_import.py  oder  pytest tests/test_pruefungen_katalog_import.py

Die Auswahl „Prüfungsleistungen aus Katalog übernehmen“ gab es nur im Dialog „Lehrgang anlegen“. Ein per Import angelegter
Lehrgang bekam seine Leistungen nur einzeln – auch nachträglich ließ sich kein Katalog übernehmen. Jetzt (Entscheidungen
des Nutzers): dieselbe Auswahl in der Import-Vorschau eines neuen Lehrgangs, und ein Lehrgang ohne Leistungen bietet im
Reiter „Leistungen“ „Aus Katalog übernehmen“ an. Geprüft am Server (Rechte, Grenzen, nichts halb angelegt) und in der
echten App in Chromium (ohne Chromium übersprungen)."""
import base64
import io
import os
import sys
import tempfile
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from test_pruefungen import H, excel_bauen, umgebung  # noqa: E402

LEISTUNGEN = [("Standardknoten", ["Achter", "Palstek"]), ("Wurfsackwurf", [])]


def _katalog(client, titel="SR1 (Standard)"):
    r = client.post("/api/pruefungen/kataloge", json={"titel": titel})
    assert r.status_code == 201, r.get_json()
    kid = r.json["katalog"]["id"]
    for bez, krit in LEISTUNGEN:
        r = client.post(f"/api/pruefungen/kataloge/{kid}/leistungen", json={"bezeichnung": bez, "kriterien": krit})
        assert r.status_code == 201, r.get_json()
    return kid


def _leistungen(lg):
    return [(l["bezeichnung"], [k["bezeichnung"] for k in l.get("kriterien") or []]) for l in lg["leistungen"]]


def test_server():
    with tempfile.TemporaryDirectory() as tmp:
        app, adm, pr, pr_id, nix, nix_id = umgebung(tmp)
        assert adm.put(f"/api/admin/users/{pr_id}", json={"rechte": {"pruefungen": 2}}).status_code == 200
        kid = _katalog(pr)

        def importieren(client=pr, **felder):
            data = {"file": (excel_bauen(), "2026-0042 - Strömungsretter 1.xlsx")}
            data.update(felder)
            return client.post("/api/pruefungen/import", data=data, headers=H, content_type="multipart/form-data")

        def lehrgaenge():
            return {e["id"] for e in adm.get("/api/pruefungen/lehrgaenge").json["lehrgaenge"]}

        # Import als neuer Lehrgang mit Katalog: Leistungen samt Kriterien kopiert, Anzahl in der Antwort
        r = importieren(katalog_id=str(kid))
        assert r.status_code == 201, r.get_json()
        assert r.json["leistungen_neu"] == 2 and r.json["angelegt"] > 0, r.get_json()
        lg = pr.get(f"/api/pruefungen/lehrgaenge/{r.json['lehrgang']['id']}").json["lehrgang"]
        assert _leistungen(lg) == [("Standardknoten", ["Achter", "Palstek"]), ("Wurfsackwurf", [])], lg["leistungen"]

        # Ein unbekannter Katalog legt nichts an – weder Lehrgang noch Teilnehmende
        vorher = lehrgaenge()
        assert importieren(katalog_id="999999").status_code == 404
        assert importieren(katalog_id="kein").status_code == 400
        assert lehrgaenge() == vorher

        # Ohne Katalog wie bisher: leer
        r = importieren()
        assert r.status_code == 201 and r.json["leistungen_neu"] == 0, r.get_json()
        leer = r.json["lehrgang"]["id"]
        assert pr.get(f"/api/pruefungen/lehrgaenge/{leer}").json["lehrgang"]["leistungen"] == []

        # In einen bestehenden Lehrgang gibt es beim Import keinen Katalog (dafür „Aus Katalog übernehmen“)
        r = importieren(lehrgang_id=str(leer), katalog_id=str(kid))
        assert r.status_code == 400 and "Aus Katalog übernehmen" in r.json["error"], r.get_json()
        assert pr.get(f"/api/pruefungen/lehrgaenge/{leer}").json["lehrgang"]["leistungen"] == []

        # Nachträglich: nur die Leitung, nur mit lesbarem Katalog, nur solange leer
        url = f"/api/pruefungen/lehrgaenge/{leer}/katalog"
        assert nix.post(url, json={"katalog_id": kid}).status_code == 403                 # kein Recht in den Riegenkarten
        r = adm.post("/api/admin/users", json={"email": "rita@example.org", "password": "passwort1", "name": "Rita Redakteurin",
                                               "rechte": {"pruefungen": 2}})
        assert r.status_code == 201, r.get_json()
        rita = app.test_client()
        assert rita.post("/api/auth/login", json={"email": "rita@example.org", "password": "passwort1"}).status_code == 200
        assert rita.post(url, json={"katalog_id": kid}).status_code == 404                # fremder Lehrgang: „nicht gefunden“
        assert pr.post(url, json={"katalog_id": 999999}).status_code == 404
        assert pr.post(url, json={}).status_code == 400
        assert pr.post("/api/pruefungen/lehrgaenge/999999/katalog", json={"katalog_id": kid}).status_code == 404
        r = pr.post(url, json={"katalog_id": kid})
        assert r.status_code == 200 and r.json["leistungen_neu"] == 2, r.get_json()
        assert _leistungen(r.json["lehrgang"]) == [("Standardknoten", ["Achter", "Palstek"]), ("Wurfsackwurf", [])]
        r = pr.post(url, json={"katalog_id": kid})
        assert r.status_code == 409 and "schon Prüfungsleistungen" in r.json["error"], r.get_json()
        assert len(pr.get(f"/api/pruefungen/lehrgaenge/{leer}").json["lehrgang"]["leistungen"]) == 2


def _browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        adm_id = u.adm.get("/api/me").json["user"]["id"]
        assert u.adm.put(f"/api/admin/users/{adm_id}", json={"rechte": {"pruefungen": 3}}).status_code == 200
        kid = _katalog(u.adm)
        s = u.seite("redakteur", 1100, 1000)
        try:
            # 1. Import als neuer Lehrgang: Katalog in der Vorschau wählen
            s.oeffnen("/riegenkarten", warten=1.5)
            s.ruhe(1.0)
            s.klick('[data-act="lg-import"]')
            assert s.warte("!!document.querySelector('dialog[open] #imp-datei')"), "Importdialog"
            daten = base64.b64encode(excel_bauen().getvalue()).decode()
            s.js(f"""(() => {{ const b = Uint8Array.from(atob('{daten}'), (c) => c.charCodeAt(0));
              const dt = new DataTransfer(); dt.items.add(new File([b], 'Herbst.xlsx'));
              const i = document.querySelector('#imp-datei'); i.files = dt.files; i.dispatchEvent(new Event('change')); }})()""")
            assert s.warte("!!document.querySelector('dialog[open] #imp-katalog')", sek=15), "Katalogauswahl in der Vorschau"
            optionen = s.js("[...document.querySelectorAll('#imp-katalog option')].map((o) => o.textContent.trim())")
            assert optionen == ["– Keine Vorlage, leer beginnen –", "SR1 (Standard) (2 Leistungen)"], optionen
            s.js(f"(() => {{ const w = document.querySelector('#imp-katalog'); w.value = '{kid}'; w.dispatchEvent(new Event('change')); }})()")
            # Eine geänderte Spaltenzuordnung zeichnet die Vorschau neu – die Wahl bleibt
            s.js("(() => { const w = document.querySelector('select[data-spalte]'); w.dispatchEvent(new Event('change')); })()")
            assert s.warte(f"document.querySelector('#imp-katalog') && document.querySelector('#imp-katalog').value === '{kid}'",
                           sek=15), "Wahl überlebt das Neuzeichnen"
            s.klick("#imp-go")
            assert s.warte("/\\/riegenkarten\\/\\d+/.test(location.pathname)", sek=15), "Lehrgang angelegt"
            lid = int(s.js("location.pathname.split('/').pop()"))
            lg = u.adm.get(f"/api/pruefungen/lehrgaenge/{lid}").json["lehrgang"]
            assert _leistungen(lg) == [("Standardknoten", ["Achter", "Palstek"]), ("Wurfsackwurf", [])], lg["leistungen"]

            # 2. Ein Lehrgang ohne Leistungen: im Reiter „Leistungen“ aus dem Katalog übernehmen
            r = u.adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Leer", "ausbilder": [
                {"user_id": u.ids["redakteur"], "funktion": "Leitung", "ist_leitung": True}]})
            assert r.status_code == 201, r.get_json()
            leer = r.json["lehrgang"]["id"]
            s.oeffnen(f"/riegenkarten/{leer}#leistungen", warten=1.5)
            s.ruhe(1.0)
            assert s.warte("!!document.querySelector('[data-act=\"pl-katalog\"]')"), "Knopf im leeren Reiter"
            s.klick('[data-act="pl-katalog"]')
            assert s.warte("!!document.querySelector('dialog[open] #pl-katalog-wahl')"), "Dialog"
            assert s.js("document.querySelector('#pl-katalog-wahl').value") == str(kid)
            s.klick("#pl-katalog-ok")
            assert s.warte("document.querySelectorAll('.leistung-karte').length === 2", sek=10), "Leistungen da"
            assert s.js("!document.querySelector('[data-act=\"pl-katalog\"]')"), "Knopf weg, sobald Leistungen da sind"
            time.sleep(0.3)
        finally:
            s.schliessen()


def test_browser():
    _browser()


if __name__ == "__main__":
    test_server()
    test_browser()
    print("ok")
