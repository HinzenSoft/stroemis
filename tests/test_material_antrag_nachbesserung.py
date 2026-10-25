"""Nachbesserung Änderungsanträge nach den Prüfungen (Ablauf und Sicherheit, 25.10.2026):
python tests/test_material_antrag_nachbesserung.py

Übernommen aus den Proben der Prüfer (planung/material-phase4/proben_ablauf, proben_sicherheit), auf das erwartete
Verhalten nach der Nachbesserung gestellt:
  Ablauf 1   Produktwechsel per Antrag: Artikeljournal und Lebenslauf zeigen je Produkt nur die Zeit, in der der
             Artikel es hatte; Rückrufe des früheren Produkts stehen im Lebenslauf mit „früheres Produkt“.
  Ablauf 2 = Sicherheit 1   Obergrenze des Intervalls nur bei einer Änderung (PUT, Antrag stellen, Bestätigen).
  Sicherheit 2   Folgeeintrag „faelligkeit“ beim Bestätigen für Leser ohne Namen.
  Sicherheit 3   Produkt + Lebensende = schon von Hand gesetzter Wert → 400 mit Satz; nie 500 beim Bestätigen.
  Ablauf 3/4, Sicherheit 4   Texte (Karte neutral, Rückmeldung nennt die Material-Verwaltung).
  Sicherheit 5   Löschdialog zählt Sammelanträge einmal.
  Verbesserungen   Zähl-Aufruf für die Blase, Begründung nur aus unsichtbaren Zeichen 400.
Echte Mails gehen nie hinaus (Nahtstelle ersetzt). Alle Namen, Nummern und Texte sind Platzhalter."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, neuer_artikel  # noqa: E402
from test_material_antrag import (_pdf_text, aufbau, beantragen, bestaetigen, item, lesen, post,  # noqa: E402
                                  zeilen, zurueckziehen)
from test_material_antrag_zustaendig import konten  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUKT_FELDER = ("category_id", "manufacturer", "model", "article_no", "material_kind", "interval_months")


def _produkt_aendern(mv, pid, **neu):
    p = mv.get(f"/api/material/produkte/{pid}").json["produkt"]
    r = mv.put(f"/api/material/produkte/{pid}", json=dict({k: p[k] for k in PRODUKT_FELDER}, **neu))
    assert r.status_code == 200, r.get_json()


def test_produktwechsel_journal_lebenslauf():
    """Ablauf 1 (Probe lebenslauf_produktwechsel): Änderung an A während der Artikel A ist, Änderung an B vorher;
    Wechsel A → B per Antrag; danach eine Änderung an B. Journal und Lebenslauf: A-Änderung ja, B-vorher nein,
    B-nachher ja. Rückruf an A (vor dem Wechsel angelegt) im Lebenslauf als früheres Produkt; einer an A nach dem
    Wechsel nicht."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        b = t.mv.post("/api/material/produkte", json={"category_id": t.ids["karabiner"], "manufacturer": "Testwerk",
                                                       "model": "HMS Delta", "article_no": "HD-9",
                                                       "material_kind": "metall_hardware", "interval_months": 12}).json["produkt"]["id"]
        _produkt_aendern(t.mv, b, norm="EN Platzhalter-B-vorher")
        _produkt_aendern(t.mv, t.ids["hms"], norm="EN Platzhalter-A-waehrend")
        r = t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                      json={"title": "Platzhalter-Rückruf A vorher", "serials": "", "mail": False})
        assert r.status_code == 201, r.get_json()
        assert any("Platzhalter-A-waehrend" in str(e) for e in lesen(t.w, t.k1)["journal"])
        kid = beantragen(t.w, t.k1, product_id=b).json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        _produkt_aendern(t.mv, b, norm="EN Platzhalter-B-nachher")
        _produkt_aendern(t.mv, t.ids["hms"], norm="EN Platzhalter-A-spaeter")
        r = t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                      json={"title": "Platzhalter-Rückruf A spaeter", "serials": "", "mail": False})
        assert r.status_code == 201, r.get_json()
        # Je Produkteintrag der neue Wert (der Eintrag „B-nachher“ nennt „B-vorher“ als alten Wert – das ist richtig).
        neu = {(e["entity_id"], (e.get("nachher") or {}).get("norm")) for e in lesen(t.w, t.k1)["journal"]
               if e["entity"] == "product"}
        assert (t.ids["hms"], "EN Platzhalter-A-waehrend") in neu and (b, "EN Platzhalter-B-nachher") in neu, neu
        assert (b, "EN Platzhalter-B-vorher") not in neu and (t.ids["hms"], "EN Platzhalter-A-spaeter") not in neu, neu
        assert not any(e["entity"] == "product" and e["entity_id"] == b and e["action"] == "angelegt"
                       for e in lesen(t.w, t.k1)["journal"])
        text = " ".join(_pdf_text(t.w.get(f"/material/artikel/{t.k1}/lebenslauf.pdf").data).split())
        assert "Platzhalter-A-waehrend" in text and "Platzhalter-B-nachher" in text, text[:600]
        assert text.count("Platzhalter-B-vorher") == 1 and "Platzhalter-A-spaeter" not in text
        assert "Platzhalter-Rückruf A vorher" in text and "früheren Produkt" in text
        assert "Platzhalter-Rückruf A spaeter" not in text
        # Zeiträume selbst: zwei, der erste bis zum Eintrag des bestätigten Antrags.
        with t.app.app_context():
            from app.material.services import bestand, journal
            z = journal.produkt_zeitraeume(bestand.artikel(t.k1))
        assert [x["product_id"] for x in z] == [t.ids["hms"], b] and z[0]["ab"] is None and z[1]["bis"] is None
        assert z[0]["bis"] == z[1]["ab"] and zeilen(t.app, "SELECT action FROM mat_audit WHERE id = ?",
                                                    (z[0]["bis"],))[0]["action"] == "antrag_bestaetigt"
        # Ein Artikel ohne Wechsel: ein Zeitraum, Journal wie bisher mit der Geschichte des Produkts.
        with t.app.app_context():
            assert [x["product_id"] for x in journal.produkt_zeitraeume(bestand.artikel(t.k2))] == [t.ids["hms"]]
        assert "Platzhalter-A-spaeter" in str(lesen(t.w, t.k2)["journal"])
    print("Produktwechsel: Journal und Lebenslauf bestanden.")


def test_intervall_obergrenze_nur_bei_aenderung():
    """Ablauf 2 = Sicherheit 1 (Proben intervall_katalog_gesenkt, probe9): Intervall 12 am Artikel, offener Antrag auf
    die Seriennummer, dann senkt der Katalog die Vorgabe auf 6. Bemerkung (Materialwart und Prüfer) 200, neuer Antrag
    ohne Intervall 201, der offene lässt sich bestätigen; ein Intervall über 6 beantragen bleibt 400, 6 geht."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kid = beantragen(t.w, t.k1, interval_months=12).json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        offen = beantragen(t.p, t.k1, serial_no="AN-701").json["antrag"]["id"]
        _produkt_aendern(t.mv, t.ids["hms"], interval_months=6)
        assert item(t.app, t.k1)["interval_months"] == 12
        for c, text in ((t.w, "Platzhalter Bemerkung"), (t.p, "Platzhalter Bemerkung P")):
            a = lesen(c, t.k1)
            r = c.put(f"/api/material/artikel/{t.k1}", json={"stand": a["stand"], "notes": text})
            assert r.status_code == 200, r.get_json()
        assert bestaetigen(t.w, offen).status_code == 200 and item(t.app, t.k1)["serial_no"] == "AN-701"
        r = beantragen(t.w, t.k1, purchased_on="2024-06")
        assert r.status_code == 201, r.get_json()
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        r = beantragen(t.w, t.k1, interval_months=10)
        assert r.status_code == 400 and "Herstellervorgabe (6 Monate)" in r.json["error"], r.get_json()
        r = beantragen(t.w, t.k1, interval_months=6)
        assert r.status_code == 201 and bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        # Vor der ersten Prüfung direkt: ein höheres Intervall weiter 400, dasselbe gespeicherte bleibt.
        neu = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-702", interval_months=6)["id"]
        r = t.w.put(f"/api/material/artikel/{neu}", json={"interval_months": 9})
        assert r.status_code == 400 and "Herstellervorgabe" in r.json["error"], r.get_json()
    print("Intervall-Obergrenze nur bei Änderung bestanden.")


def test_faelligkeit_ohne_namen_fuer_leser():
    """Sicherheit 2 (probe2b): Intervall-Antrag bestätigt → „faelligkeit“ trägt die Antrag-Nr.; der Leser sieht als
    Handelnden „(Person)“ – im Journal und im Lebenslauf –, der Materialwart den Namen."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        konten(t)
        kid = beantragen(t.p, t.k1, interval_months=6, begruendung="Platzhalter Intervall").json["antrag"]["id"]
        assert t.wart2.post(f"/api/material/antraege/{kid}/bestaetigen", headers=H, json={}).status_code == 200
        f = [e for e in lesen(t.f, t.k1)["journal"] if e["action"] == "faelligkeit"]
        assert f and f[0]["nachher"]["antrag"] == kid and f[0]["user_name"] == "(Person)", f
        w = [e for e in lesen(t.w, t.k1)["journal"] if e["action"] == "faelligkeit"]
        assert w[0]["user_name"] == "Wart Zwei", w
        assert "Wart Zwei" not in _pdf_text(t.f.get(f"/material/artikel/{t.k1}/lebenslauf.pdf").data)
    print("Fälligkeit ohne Namen für Leser bestanden.")


def test_produkt_und_lebensende_klartext():
    """Sicherheit 3 (probe10): Lebensende von Hand 01.06.2032, Herstellung früher (Rechnung 01.01.2031 davor); Antrag
    „anderes textiles Produkt + Lebensende 01.06.2032“ → 400 mit Satz statt 201 und 500 beim Bestätigen. Ein Antrag, der
    beim Bestätigen nicht ganz anwendbar ist, endet mit 409 (nachgestellt mit einer falschen Antragszeile)."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kid = beantragen(t.w, t.g1, retire_by="2032-06-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        kid = beantragen(t.w, t.g1, manufactured_on="2021-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        g = item(t.app, t.g1)
        assert (g["retire_by"], g["retire_by_manual"]) == ("2031-01-01", "2032-06-01"), g
        lang = t.mv.post("/api/material/produkte", json={"category_id": t.ids["gurte"], "manufacturer": "Testwerk",
                                                          "model": "Gurt Lang", "article_no": "GL-1",
                                                          "material_kind": "textil", "lifetime_years": 15}).json["produkt"]["id"]
        r = beantragen(t.w, t.g1, product_id=lang, retire_by="2032-06-01")
        assert r.status_code == 400 and "schon von Hand gesetzt" in r.json["error"], r.get_json()
        # 409 statt 500: ein Antrag, dessen Zeile nach dem Schreiben nicht angewendet ist (nachgestellt: _plan liefert
        # statt des Kaufs nur eine Bemerkung – der Trigger lässt das zu, die Zeile bleibt offen).
        from app.material.services import antrag
        kid = beantragen(t.w, t.k1, purchased_on="2024-07").json["antrag"]["id"]
        echt = antrag._plan

        def falsch(item_, wuensche):
            echt(item_, wuensche)
            return {"notes": "Platzhalter nicht angewendet"}
        antrag._plan = falsch
        try:
            t.app.testing = False
            r = bestaetigen(t.w, kid)
        finally:
            antrag._plan = echt
            t.app.testing = True
        assert r.status_code == 409 and "nicht vollständig anwenden" in r.json["error"], (r.status_code, r.get_json())
        assert item(t.app, t.k1)["purchased_on"] == "2024-05"
        assert zeilen(t.app, "SELECT status FROM mat_item_change WHERE id = ?", (kid,))[0]["status"] == "offen"
    print("Produkt + Lebensende mit Klartext, 409 statt 500 bestanden.")


def test_loeschdialog_zaehler_begruendung():
    """Sicherheit 5: Ein Sammelantrag mit drei Feldern zählt im Dialog „Konto löschen“ einmal. Zähl-Aufruf ?nur_zahl=1
    liefert nur zu_entscheiden. Begründung nur aus U+200B und Leerzeichen 400."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.p, t.k1, serial_no="AN-703", purchased_on="2024-03", interval_months=6,
                       begruendung="Platzhalter drei Felder")
        assert r.status_code == 201, r.get_json()
        f = t.adm.get(f"/api/admin/users/{t.k['pruefer_id']}/material-folgen").json
        assert f["antraege"] == 1, f
        z = t.w.get("/api/material/antraege?nur_zahl=1").json
        assert z == {"zu_entscheiden": 1}, z
        assert t.w.get("/api/material/antraege").json["zu_entscheiden"] == 1
        assert t.f.get("/api/material/antraege?nur_zahl=1").json == {"zu_entscheiden": 0}
        assert t.k["nutzer"].get("/api/material/antraege?nur_zahl=1").status_code == 403
        assert zurueckziehen(t.p, r.json["antrag"]["id"]).status_code == 200
        for leer in ("​", " ​​ ", "​\n⁠"):
            r = beantragen(t.w, t.k1, serial_no="AN-704", begruendung=leer)
            assert r.status_code == 400 and "Begründung" in r.json["error"], (leer, r.get_json())
        assert beantragen(t.w, t.k1, serial_no="AN-704", begruendung="​Platzhalter").status_code == 201
    print("Löschdialog, Zähl-Aufruf und Begründung bestanden.")


def test_oberflaeche_statisch():
    """Ablauf 3/4 = Sicherheit 4: Kartentext neutral, Rückmeldung nach „Antrag senden“ nennt im Rückfall die
    Material-Verwaltung; die Blase holt nur die Zahl."""
    js = open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8").read()
    assert "ist benachrichtigt" not in js
    assert "die Material-Verwaltung kann sich die Freigabe dort geben und dann entscheiden." in js
    assert '"Antrag gesendet – die Material-Verwaltung bekommt eine Mail."' in js and "r.antrag.ohne_zustaendige" in js
    zaehlen = js[js.index("async function antraegeZaehlen(el)"):js.index("async function antraegeZaehlen(el)") + 400]
    assert "antraege?nur_zahl=1" in zaehlen
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_produktwechsel_journal_lebenslauf()
    test_intervall_obergrenze_nur_bei_aenderung()
    test_faelligkeit_ohne_namen_fuer_leser()
    test_produkt_und_lebensende_klartext()
    test_loeschdialog_zaehler_begruendung()
    test_oberflaeche_statisch()
