"""Änderungsanträge an alle Stammdaten, Freigabe durch die zuständigen Materialwarte (Wunsch des Nutzers vom 24.10.2026,
Entscheidungen E1–E8): python tests/test_material_antrag_zustaendig.py

  1. Zuständig je Rolle: Materialwart an der Heimat und darüber entscheidet (auch aus einer fremden Gliederung, auch den
     eigenen Antrag – E5), Nachbarordner 404, abgelaufene Verwalterfreigabe 403, Prüfer, Führungskraft und
     Material-Verwaltung ohne eigene Verwalterfreigabe 403 und ohne Antrag in Liste und Zahl (E7); die
     Material-Verwaltung gibt sich die Freigabe selbst (Freigaben und Journal) und entscheidet dann (E6); ohne Stufe 403.
  2. Sammelantrag: mehrere Felder in einem Antrag (ein Journaleintrag, eine Mail, ganz oder gar nicht), höchstens einer
     je Artikel, Bestätigen und Ablehnen des Ganzen, Wert inzwischen anders → nur ablehnen, Zurückziehen der Gruppe.
  3. Die neuen Felder: Kauf, Erstgebrauch, Prüfintervall (rückt die Fälligkeit vor), Lebensende (nur textil; seit dem
     25.10.2026 auch wieder nach hinten bis zur Rechnung, Schritt 24), Herstellung nachtragen (E3), Produkt (Lebensende, Länge, Rückruf, DEMO-Grenze).
  4. PUT nach der ersten Prüfung: jedes freigabepflichtige Feld 409, Bemerkung, Länge und nächste Prüfung direkt – für
     Materialwart UND Prüfer (E2); der Prüfer sonst 403.
  5. Mails: an die zuständigen Materialwarte (ohne Antragsteller), Rückfall an die Material-Verwaltung nur ohne jedes
     zuständige Konto; Mailprotokoll führt auf die neue Seite.
  6. Trigger aus Schritt 23 (neue Felder, Gruppe, group_id fest, kein Vier-Augen) und Migration 22 → 23 mit Altbestand
     (offene und erledigte Anträge, Kennungsfolge), zweiter Lauf, frische Datenbank.
  7. Produktänderungen im Katalog stehen im Artikeljournal und im Lebenslauf (E8); Seiten, Weiterleitung, Oberfläche.
Echte Mails gehen nie hinaus (die Nahtstelle ist ersetzt). Alle Namen, Nummern und Texte sind Platzhalter."""
import os
import sqlite3
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, freigeben, make_app, neuer_artikel, neues_konto  # noqa: E402
from test_material_antrag import (_ohne_trigger, _pdf_text, _schema, _schema_in, _tabelle_sql, _zahlen,  # noqa: E402
                                  ablehnen, antraege, aufbau, beantragen, bestaetigen, item, journal, lesen, post,
                                  pruefen, sql, trigger_25, trigger_27, zeilen, zurueckziehen)
from test_material_trennung import bis_schritt, endversion  # noqa: E402

FEST = ("Seit der ersten Prüfung stehen die Stammdaten fest – sie sind Teil des Prüfnachweises. Eine Änderung beantragst "
        "du mit Begründung; entscheiden die Materialwarte des Ordners.")
NUR_ZUSTAENDIG = "Entscheiden dürfen die Materialwarte dieses Ordners"
NUR_DIREKT = "Als Prüfer änderst du hier Bemerkung, Länge und die nächste Prüfung"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def konten(t):
    """Weitere Konten an Gliederung A: wart2 verwaltet nur das Lager, fremd (Konto einer anderen Gliederung) verwaltet das
    Lager auch, nachbar verwaltet nur die Halle daneben, alt liest die Gliederung und hatte eine Verwalterfreigabe am
    Lager, die gestern endete."""
    t.halle = t.w.post("/api/material/ordner", json={"name": "Halle", "kind": "standort",
                                                    "parent_id": t.gid}).json["ordner"]["id"]
    t.wart2, t.wart2_id = neues_konto(t.app, "wart2@example.org", name="Wart Zwei")
    freigeben(t.adm, t.lager, t.wart2_id, "verwalten")
    t.fremd, t.fremd_id = neues_konto(t.app, "fremd@example.org", name="Fremd Wart")
    freigeben(t.adm, t.gid_b, t.fremd_id, "verwalten")
    freigeben(t.adm, t.lager, t.fremd_id, "verwalten")
    t.nachbar, t.nachbar_id = neues_konto(t.app, "nachbar@example.org", name="Nachbar Wart")
    freigeben(t.adm, t.halle, t.nachbar_id, "verwalten")
    t.alt, t.alt_id = neues_konto(t.app, "alt@example.org", name="Alt Wart")
    freigeben(t.adm, t.gid, t.alt_id, "lesen")
    freigeben(t.adm, t.lager, t.alt_id, "verwalten", bis=_heute() - timedelta(days=1))


def liste(c, status="offen"):
    r = c.get(f"/api/material/antraege?status={status}")
    assert r.status_code == 200, r.get_json()
    return r.json


# --- 1. Zuständig ------------------------------------------------------------------------------------------------------

def test_zustaendig():
    with post() as mails, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        konten(t)
        r = beantragen(t.w, t.k1, serial_no="AN-101", purchased_on="2024-06", begruendung="Platzhalter zuständig")
        assert r.status_code == 201, r.get_json()
        a = r.json["antrag"]
        kid = a["id"]
        assert [x["feld"] for x in a["aenderungen"]] == ["serial_no", "purchased_on"], a
        assert a["eigen"] and a["entscheiden"] and a["felder_text"] == "Seriennummer, Kauf", a
        # Mail an die zuständigen Materialwarte ohne den Antragsteller.
        assert sorted(m[0] for m in mails) == ["fremd@example.org", "wart2@example.org"], mails
        # Liste, Zahl und Übersicht: nur eigene und zu entscheidende (E7).
        for c, sieht, zahl in ((t.w, True, 1), (t.wart2, True, 1), (t.fremd, True, 1), (t.nachbar, False, 0),
                               (t.alt, False, 0), (t.p, False, 0), (t.f, False, 0), (t.mv, False, 0), (t.adm, False, 0)):
            d = liste(c)
            assert ([x["id"] for x in d["antraege"]] == [kid]) is sieht and d["zu_entscheiden"] == zahl, (c, d)
            assert c.get("/api/material/start").json["antraege_offen"] == zahl
        assert t.k["nutzer"].get("/api/material/antraege").status_code == 403
        # Artikelseite und Journal wie bisher: jeder Leser sieht den offenen Antrag; entscheiden nur Zuständige.
        for c, inhalt, entscheiden in ((t.f, False, False), (t.p, True, False), (t.mv, True, False),
                                       (t.wart2, True, True)):
            x = lesen(c, t.k1)
            assert x["antrag_offen"] and x["antraege"][0]["inhalt"] is inhalt and x["darf_entscheiden"] is entscheiden, c
            assert x["darf_antrag"] is False
        # Entscheiden: nicht lesbar 404, lesbar ohne Zuständigkeit 403.
        unbekannt = bestaetigen(t.wart2, 999999)
        for c in (t.nachbar,):
            r = bestaetigen(c, kid)
            assert r.status_code == 404 and r.get_json() == unbekannt.get_json(), r.get_json()
        for c in (t.alt, t.p, t.f, t.mv, t.adm):
            for f in (bestaetigen, ablehnen):
                r = f(c, kid, antwort="Platzhalter")
                assert r.status_code == 403 and NUR_ZUSTAENDIG in r.json["error"], (c, r.get_json())
        assert bestaetigen(t.k["nutzer"], kid).status_code == 403
        assert t.app.test_client().post(f"/api/material/antraege/{kid}/bestaetigen", json={}).status_code == 401
        # E5: Der Antragsteller ist zuständig und bestätigt selbst – kein Vier-Augen, kein Bescheid an sich selbst.
        mails.clear()
        r = bestaetigen(t.w, kid)
        assert r.status_code == 200 and r.json["antrag"]["status"] == "bestaetigt", r.get_json()
        assert mails == [] and (item(t.app, t.k1)["serial_no"], item(t.app, t.k1)["purchased_on"]) == ("AN-101", "2024-06")
        # Materialwart aus einer fremden Gliederung entscheidet einen Antrag des Prüfers.
        kid2 = beantragen(t.p, t.k1, first_use_on="2024-07").json["antrag"]["id"]
        assert bestaetigen(t.fremd, kid2).status_code == 200 and item(t.app, t.k1)["first_use_on"] == "2024-07"
        # E6: Die Material-Verwaltung gibt sich die Verwalterfreigabe selbst und entscheidet dann.
        kid3 = beantragen(t.p, t.k1, serial_no="AN-102").json["antrag"]["id"]
        r = t.mv.post(f"/api/material/ordner/{t.gid}/freigaben", headers=H,
                      json={"user_id": t.k["katalog_id"], "grundrecht": "verwalten"})
        assert r.status_code == 201, r.get_json()
        # Sie hatte schon „lesen“ an der Gliederung – die Zeile wird zu „verwalten“ (Journal am Ordner).
        assert any(e["action"] in ("freigabe_erteilt", "freigabe_geaendert") for e in zeilen(
            t.app, "SELECT action FROM mat_audit WHERE entity = 'folder' AND entity_id = ?", (t.gid,)))
        d = liste(t.mv)
        assert [x["id"] for x in d["antraege"]] == [kid3] and d["zu_entscheiden"] == 1 and d["antraege"][0]["entscheiden"]
        assert ablehnen(t.mv, kid3, antwort="Platzhalter MV").status_code == 200
        # Die fremde Gliederung B: dort entscheidet sie ohne Freigabe nicht (adm beantragt, B hat keinen Materialwart).
        fb_geprueft = t.fb
        sql(t.app, "INSERT INTO mat_inspection (item_id, kind, inspector_name, inspected_on, result, created_at, "
                   "updated_at, completed_at) VALUES (?, 'eingang', 'Prüfer', '2026-10-01', 'einsatzbereit', "
                   "'2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00')",
            (fb_geprueft,))
        kid4 = beantragen(t.mv, fb_geprueft, serial_no="AN-B2").json["antrag"]["id"]
        assert bestaetigen(t.mv, kid4).status_code == 403     # ihre Freigabe gilt an A, nicht an B
        assert bestaetigen(t.fremd, kid4).status_code == 200  # fremd verwaltet B
    print("Zuständig bestanden.")


def test_ohne_zustaendige():
    """Gliederung B hat nur fremd als Materialwart. Ohne jedes zuständige Konto geht die Mail an die Material-Verwaltung
    (mit dem Hinweis auf die Verwalterfreigabe), der Antrag trägt „ohne_zustaendige“; ist der Antragsteller der einzige
    zuständige, geht keine Mail; fehlt nur die Adresse, kein Rückfall."""
    with post() as mails, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sql(t.app, "INSERT INTO mat_inspection (item_id, kind, inspector_name, inspected_on, result, created_at, "
                   "updated_at, completed_at) VALUES (?, 'eingang', 'Prüfer', '2026-10-01', 'einsatzbereit', "
                   "'2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00')", (t.fb,))
        r = beantragen(t.adm, t.fb, serial_no="AN-B3")
        assert r.status_code == 201 and r.json["antrag"]["ohne_zustaendige"] is True, r.get_json()
        assert [m[0] for m in mails] == ["katalog@example.org"], mails
        assert "keinen Materialwart mit Freigabe „verwalten“" in mails[0][2] and "/material/bestand/antraege" in mails[0][2]
        assert zeilen(t.app, "SELECT COUNT(*) AS n FROM mat_audit WHERE action = 'antrag_gestellt'")[0]["n"] == 1
        assert zurueckziehen(t.adm, r.json["antrag"]["id"]).status_code == 200
        # Der Antragsteller ist der einzige Zuständige: keine Mail, er entscheidet selbst.
        einzig, einzig_id = neues_konto(t.app, "einzig@example.org", name="Einzig Wart")
        freigeben(t.adm, t.gid_b, einzig_id, "verwalten")
        mails.clear()
        r = beantragen(einzig, t.fb, serial_no="AN-B4")
        assert r.status_code == 201 and r.json["mail"] is False and mails == [], (r.get_json(), mails)
        assert r.json["antrag"]["ohne_zustaendige"] is False and r.json["antrag"]["entscheiden"] is True
        assert bestaetigen(einzig, r.json["antrag"]["id"]).status_code == 200
        # Zuständig ohne Adresse: kein Rückfall an die Material-Verwaltung.
        sql(t.app, "UPDATE users SET email = '' WHERE id = ?", (einzig_id,))
        mails.clear()
        r = beantragen(t.adm, t.fb, serial_no="AN-B5")
        assert r.status_code == 201 and r.json["mail"] is False and mails == [], (r.get_json(), mails)
    print("Ohne Zuständige bestanden.")


# --- 2. Sammelantrag ---------------------------------------------------------------------------------------------------

def test_sammelantrag():
    with post() as mails, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = t.mv.post("/api/material/produkte", json={"category_id": t.ids["karabiner"], "manufacturer": "Testwerk",
                                                      "model": "HMS Gamma", "article_no": "HG-1",
                                                      "material_kind": "metall_hardware", "interval_months": 12})
        hms2 = r.json["produkt"]["id"]
        vorher = item(t.app, t.k1)
        # Ganz oder gar nicht: Kauf vor der Herstellung → 400, nichts gespeichert.
        r = beantragen(t.p, t.k1, manufactured_on="2024-06", purchased_on="2024-05")
        assert r.status_code == 400 and "Kaufdatum liegt vor dem Herstelldatum" in r.json["error"], r.get_json()
        assert antraege(t.app, t.k1) == []
        mails.clear()
        r = beantragen(t.p, t.k1, product_id=hms2, serial_no="AN-SAMMEL", manufactured_on="2024-02",
                       purchased_on="2024-04", first_use_on="2024-05", interval_months=6,
                       notes="wird nicht beantragt", begruendung="Platzhalter Sammelantrag")
        assert r.status_code == 201, r.get_json()
        a = r.json["antrag"]
        kid = a["id"]
        felder = ["product_id", "serial_no", "manufactured_on", "purchased_on", "first_use_on", "interval_months"]
        assert [x["feld"] for x in a["aenderungen"]] == felder, a
        assert a["aenderungen"][0]["neu_text"] == "Testwerk HMS Gamma (HG-1)" and a["aenderungen"][5]["neu_text"] == "6 Monate"
        z = antraege(t.app, t.k1)
        assert z[0]["group_id"] is None and all(x["group_id"] == kid for x in z[1:]) and len(z) == 6, z
        assert {x["reason"] for x in z} == {"Platzhalter Sammelantrag"} and len({x["created_at"] for x in z}) == 1
        j = journal(t.app, t.k1, "antrag_gestellt")
        assert len(j) == 1 and j[0]["nachher"]["antrag"] == kid and j[0]["nachher"]["produkt"] == "Testwerk HMS Gamma (HG-1)"
        assert j[0]["vorher"]["serial_no"] == "AN-100" and j[0]["nachher"]["interval_months"] == 6, j
        assert len(mails) == 1 and "Produkt:" in mails[0][2] and "Prüfintervall: (leer) → 6 Monate" in mails[0][2], mails
        assert "(Produkt, Seriennummer, Herstellung, Kauf, Erstgebrauch, Prüfintervall)" in mails[0][1]
        # Höchstens ein offener Antrag je Artikel – auch für ein anderes Feld und ein anderes Konto.
        r = beantragen(t.w, t.k1, notes="x", purchased_on="2024-03")
        assert r.status_code == 409 and "läuft schon ein Änderungsantrag" in r.json["error"], r.get_json()
        # Listen zeigen EINE Karte, die Folgezeilen sind keine eigenen Anträge.
        assert [x["id"] for x in liste(t.w)["antraege"]] == [kid]
        assert bestaetigen(t.w, z[2]["id"]).status_code == 200            # die Nummer einer Folgezeile meint den Kopf
        n = item(t.app, t.k1)
        assert (n["product_id"], n["serial_no"], n["manufactured_on"], n["purchased_on"], n["first_use_on"],
                n["interval_months"]) == (hms2, "AN-SAMMEL", "2024-02", "2024-04", "2024-05", 6), n
        assert n["notes"] == vorher["notes"]
        assert all(x["status"] == "bestaetigt" and x["applied_at"] for x in antraege(t.app, t.k1))
        j = journal(t.app, t.k1, "antrag_bestaetigt")
        assert len(j) == 1 and j[0]["nachher"]["produkt"] == "Testwerk HMS Gamma (HG-1)" and j[0]["nachher"]["antrag"] == kid
        assert set(felder) <= set(j[0]["nachher"]), j
        # Kürzeres Intervall: Die nächste Prüfung rückt vor (höchstens heute + 6 Monate).
        assert n["next_due_on"] <= (_heute() + timedelta(days=186)).isoformat(), n
        # Wert inzwischen anders → nur ablehnen.
        kid2 = beantragen(t.w, t.k1, purchased_on="2024-03", first_use_on="2024-06").json["antrag"]["id"]
        _ohne_trigger(t.app, "UPDATE mat_item SET first_use_on = '2024-08' WHERE id = ?", (t.k1,))
        x = liste(t.w)["antraege"][0]
        assert x["passt"] is False and [y["passt"] for y in x["aenderungen"]] == [True, False], x
        r = bestaetigen(t.w, kid2)
        assert r.status_code == 409 and "nicht mehr den Wert" in r.json["error"], r.get_json()
        assert item(t.app, t.k1)["purchased_on"] == "2024-04"
        assert ablehnen(t.w, kid2, antwort="Platzhalter Stand").status_code == 200
        assert {x["status"] for x in antraege(t.app, t.k1) if x["id"] >= kid2} == {"abgelehnt"}
        j = journal(t.app, t.k1, "antrag_abgelehnt")[-1]
        assert j["nachher"] == {"antrag": kid2, "feld": "Kauf, Erstgebrauch", "ablehnung": "Platzhalter Stand"}, j
        # Zurückziehen: die ganze Gruppe.
        kid3 = beantragen(t.p, t.k1, purchased_on="2024-03", interval_months="").json["antrag"]["id"]
        assert zurueckziehen(t.p, kid3).status_code == 200
        assert {x["status"] for x in antraege(t.app, t.k1) if x["id"] >= kid3} == {"zurueckgezogen"}
        assert journal(t.app, t.k1, "antrag_zurueckgezogen")[-1]["nachher"]["feld"] == "Kauf, Prüfintervall"
        # Nichts geändert, nur gleiche Werte: 400.
        r = beantragen(t.w, t.k1, purchased_on="2024-04", serial_no="AN-SAMMEL")
        assert r.status_code == 400 and "mindestens ein Feld" in r.json["error"], r.get_json()
    print("Sammelantrag bestanden.")


# --- 3. Die neuen Felder -----------------------------------------------------------------------------------------------

def test_felder():
    from test_material_laenge import kategorie_neu
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        # Lebensende: nur textil, höchstens bis zur Rechnung (Wunsch vom 25.10.2026), nicht entfernen.
        g = item(t.app, t.g1)
        assert g["retire_by"] == "2034-01-01"
        for d, text in (({"retire_by": "2034-06-01"}, "höchstens bis zur Rechnung"), ({"retire_by": "2034-01-01"}, "mindestens ein Feld"),
                        ({"retire_by": ""}, "nicht entfernen")):
            r = beantragen(t.w, t.g1, **d)
            assert r.status_code == 400 and text in r.json["error"], (d, r.get_json())
        r = beantragen(t.w, t.k1, retire_by="2030-01-01")
        assert r.status_code == 400 and "nur bei textilem Material" in r.json["error"], r.get_json()
        kid = beantragen(t.w, t.g1, retire_by="2031-05-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        g = item(t.app, t.g1)
        assert (g["retire_by"], g["retire_by_manual"]) == ("2031-05-01", "2031-05-01"), g
        a = lesen(t.w, t.g1)
        assert a["lebensdauer"]["vorgezogen"] is True
        # Herstellung bei textil ändern: Lebensende bleibt das vorgezogene, solange es früher liegt.
        kid = beantragen(t.p, t.g1, manufactured_on="2023-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert item(t.app, t.g1)["retire_by"] == "2031-05-01"
        # E3: Herstellung bei Metall nachtragen – nur per Antrag.
        assert item(t.app, t.k2)["manufactured_on"] is None
        r = t.w.put(f"/api/material/artikel/{t.k2}", headers=H, json={"manufactured_on": "2023-11"})
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        kid = beantragen(t.w, t.k2, manufactured_on="2023-11").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200 and item(t.app, t.k2)["manufactured_on"] == "2023-11"
        # Kauf und Intervall leeren per Antrag; Intervall über der Herstellervorgabe 400.
        r = beantragen(t.w, t.k1, interval_months=24)
        assert r.status_code == 400 and "Herstellervorgabe" in r.json["error"], r.get_json()
        kid = beantragen(t.w, t.k1, purchased_on="").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200 and item(t.app, t.k1)["purchased_on"] is None
        # Produkt: textil → textil mit anderer Lebensdauer rechnet das Lebensende neu.
        gurt2 = t.mv.post("/api/material/produkte", json={"category_id": t.ids["gurte"], "manufacturer": "Testwerk",
                                                          "model": "Gurt Beta", "article_no": "GB-1", "material_kind": "textil",
                                                          "lifetime_years": 6}).json["produkt"]["id"]
        g2 = neuer_artikel(t.w, t.ids["gurt"], t.lager, serial_no="AN-G2", manufactured_on="2024-01")["id"]
        pruefen(t.p, g2, gurt=True)
        kid = beantragen(t.w, g2, product_id=gurt2).json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert (item(t.app, g2)["product_id"], item(t.app, g2)["retire_by"]) == (gurt2, "2030-01-01")
        # textil → Metall: Lebensende fällt weg.
        kid = beantragen(t.w, g2, product_id=t.ids["hms"]).json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert (item(t.app, g2)["retire_by"], item(t.app, g2)["retire_by_manual"]) == (None, None)
        # Länge fällt weg, wenn die Kategorie des neuen Produkts keine vorsieht.
        seile = kategorie_neu(t.mv, name="Seile", parent_id=t.ids["gurte"], default_material_kind="textil",
                              default_interval_months=12, items_have_length=True)["id"]
        seil = t.mv.post("/api/material/produkte", json={"category_id": seile, "manufacturer": "Testwerk", "model": "Seil",
                                                         "article_no": "S-1", "material_kind": "textil",
                                                         "lifetime_years": 10}).json["produkt"]["id"]
        s1 = neuer_artikel(t.w, seil, t.lager, serial_no="AN-SEIL", manufactured_on="2024-01", length_m="50")["id"]
        pruefen(t.p, s1)
        kid = beantragen(t.w, s1, product_id=gurt2).json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert item(t.app, s1)["length_m"] is None
        assert journal(t.app, s1, "antrag_bestaetigt")[-1]["vorher"]["length_m"] == 50.0
        # Rückruf nach dem neuen Produkt: im Antrag angekündigt, im Journal vermerkt.
        rr = t.mv.post(f"/api/material/produkte/{gurt2}/rueckrufe", headers=H,
                       json={"title": "Platzhalter-Rückruf Gurt Beta", "serials": "", "mail": False}).json["rueckruf"]["id"]
        g3 = neuer_artikel(t.w, t.ids["gurt"], t.lager, serial_no="AN-G3", manufactured_on="2024-01")["id"]
        pruefen(t.p, g3, gurt=True)
        r = beantragen(t.w, g3, product_id=gurt2)
        assert r.json["antrag"]["rueckruf"]["neu"] == [{"id": rr, "title": "Platzhalter-Rückruf Gurt Beta"}], r.get_json()
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert journal(t.app, g3, "antrag_bestaetigt")[-1]["nachher"]["rueckruf_neu"] == [
            f"Platzhalter-Rückruf Gurt Beta (Nr. {rr})"]
        # Serie beim neuen Produkt muss frei sein.
        k4 = neuer_artikel(t.w, gurt2, t.lager, serial_no="AN-100", manufactured_on="2024-01")["id"]
        assert k4
        r = beantragen(t.w, t.k1, product_id=gurt2, manufactured_on="2024-02")
        assert r.status_code == 409 and "gibt es bei diesem Produkt schon" in r.json["error"], r.get_json()
        # DEMO-Grenze: ein echter Artikel wird kein DEMO-Artikel.
        sql(t.app, "UPDATE mat_product SET demo = 1 WHERE id = ?", (gurt2,))
        r = beantragen(t.w, t.g1, product_id=gurt2)
        assert r.status_code == 409 and "DEMO" in r.json["error"], r.get_json()
    print("Felder bestanden.")


def hms_anders(t):
    """Ein zweites Metallprodukt (für den Produktwechsel an einem Teil)."""
    r = t.mv.post("/api/material/produkte", json={"category_id": t.ids["karabiner"], "manufacturer": "Testwerk",
                                                  "model": "HMS Delta", "article_no": "HD-1",
                                                  "material_kind": "metall_hardware", "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


# --- 4. Bearbeiten nach der ersten Prüfung -----------------------------------------------------------------------------

def test_bearbeiten():
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        url = f"/api/material/artikel/{t.k1}"
        for d in ({"serial_no": "AN-X"}, {"manufactured_on": "2024-01"}, {"purchased_on": "2024-06"},
                  {"purchased_on": None}, {"first_use_on": "2024-06"}, {"interval_months": 6},
                  {"product_id": t.ids["gurt"]}):
            r = t.w.put(url, headers=H, json=d)
            assert r.status_code == 409, (d, r.get_json())
        r = t.w.put(f"/api/material/artikel/{t.g1}", headers=H, json={"retire_by": "2030-01-01"})
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        # Gleiche Werte gehen durch (der Dialog schickt sie mit), die direkten Felder auch.
        a = lesen(t.w, t.k1)
        r = t.w.put(url, headers=H, json={"stand": a["stand"], "serial_no": "an-100", "manufactured_on": "2024-03",
                                         "purchased_on": "2024-05", "notes": "Platzhalter Bemerkung",
                                         "next_due_on": (_heute() + timedelta(days=30)).isoformat()})
        assert r.status_code == 200 and r.json["artikel"]["notes"] == "Platzhalter Bemerkung", r.get_json()
        assert item(t.app, t.k1)["serial_no"] == "AN-100"
        # Prüfer (E2): Bemerkung, Länge, nächste Prüfung – sonst 403; Führungskraft gar nicht.
        r = t.p.put(url, headers=H, json={"notes": "Platzhalter Prüfer",
                                         "next_due_on": (_heute() + timedelta(days=20)).isoformat()})
        assert r.status_code == 200 and item(t.app, t.k1)["notes"] == "Platzhalter Prüfer", r.get_json()
        j = journal(t.app, t.k1, "geaendert")[-1]
        assert j["user_name"] == "pruefer" and j["nachher"]["notes"] == "Platzhalter Prüfer", j
        for d in ({"purchased_on": "2024-06"}, {"serial_no": "AN-Y"}, {"interval_months": 6}, {"retire_by": "2030-01-01"}):
            r = t.p.put(url, headers=H, json=d)
            assert r.status_code == 403 and NUR_DIREKT in r.json["error"], (d, r.get_json())
        r = t.p.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"serial_no": "AN-NEU-P"})
        assert r.status_code == 403, r.get_json()                       # auch vor der ersten Prüfung nur die drei
        r = t.p.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"notes": "vor der Prüfung"})
        assert r.status_code == 200, r.get_json()
        assert t.f.put(url, headers=H, json={"notes": "x"}).status_code == 403
        # Länge: direkt und weiter über den Prüfpunkt (test_material_laenge).
        from test_material_laenge import kategorie_neu
        seile = kategorie_neu(t.mv, name="Seile", parent_id=t.ids["gurte"], default_material_kind="textil",
                              default_interval_months=12, items_have_length=True)["id"]
        seil = t.mv.post("/api/material/produkte", json={"category_id": seile, "manufacturer": "Testwerk", "model": "Seil",
                                                         "article_no": "S-1", "material_kind": "textil",
                                                         "lifetime_years": 10}).json["produkt"]["id"]
        s1 = neuer_artikel(t.w, seil, t.lager, serial_no="AN-SEIL", manufactured_on="2024-01", length_m="50")["id"]
        pruefen(t.p, s1)
        r = t.p.put(f"/api/material/artikel/{s1}", headers=H, json={"length_m": "48,5"})
        assert r.status_code == 200 and item(t.app, s1)["length_m"] == 48.5, r.get_json()
        # Vor der ersten Prüfung bleibt alles direkt für den Materialwart.
        r = t.w.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"purchased_on": "2024-02", "interval_months": 6})
        assert r.status_code == 200 and item(t.app, t.neu1)["interval_months"] == 6, r.get_json()
        # Antrag am ungeprüften Artikel: 409.
        r = beantragen(t.w, t.neu1, purchased_on="2024-03")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
    print("Bearbeiten bestanden.")


# --- 5. Trigger und Migration ------------------------------------------------------------------------------------------

def test_trigger_23():
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        wart = t.k["wart_id"]

        def geht_nicht(befehl, args=(), text="seit seiner ersten Prüfung fest"):
            try:
                conn.execute(befehl, args)
            except sqlite3.IntegrityError as e:
                assert text in str(e), (befehl, e)
                return
            raise AssertionError(befehl)

        def neu(iid, feld, alt, wert, gruppe=None, ts="2026-10-24T08:00:00+00:00", grund="Platzhalter"):
            return conn.execute("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                                "created_by_name, created_at, group_id) VALUES (?,?,?,?,?,?,'wart',?,?)",
                                (iid, feld, alt, wert, grund, wart, ts, gruppe)).lastrowid

        def bestaetigt(kid):
            conn.execute("UPDATE mat_item_change SET status = 'bestaetigt', resolved_by = ?, resolved_by_name = 'wart', "
                         "resolved_at = '2026-10-24T09:00:00+00:00' WHERE id = ? OR group_id = ?", (wart, kid, kid))

        try:
            for befehl in ("UPDATE mat_item SET purchased_on = '2024-06' WHERE id = ?",
                           "UPDATE mat_item SET first_use_on = '2024-06' WHERE id = ?",
                           "UPDATE mat_item SET interval_months = 6 WHERE id = ?",
                           "UPDATE mat_item SET manufactured_on = '2024-01' WHERE id = ?"):
                geht_nicht(befehl, (t.k1,))
            geht_nicht("UPDATE mat_item SET retire_by_manual = '2030-01-01', retire_by = '2030-01-01' WHERE id = ?", (t.g1,))
            geht_nicht("UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["gurt"], t.k1), "Produkt eines Artikels")
            geht_nicht("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.k2,))   # kein Nachtragen (E3)
            # Erlaubt: Länge, Bemerkung, nächste Prüfung, derselbe Wert, ein abgeleitetes Lebensende.
            conn.execute("UPDATE mat_item SET notes = 'x', next_due_on = '2026-11-01', purchased_on = purchased_on, "
                         "interval_months = interval_months WHERE id = ?", (t.k1,))
            conn.execute("UPDATE mat_item SET retire_by = '2033-01-01' WHERE id = ?", (t.g1,))
            # Gruppe: Kopf nur ohne offenen Antrag am Artikel, Folgezeile nur passend zum offenen Kopf.
            kid = neu(t.k1, "purchased_on", "2024-05", "2024-06")
            geht_nicht("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                       "created_by_name, created_at) VALUES (?, 'first_use_on', NULL, '2024-06', 'x', ?, 'wart', 'x')",
                       (t.k1, wart), "höchstens ein offener Änderungsantrag")
            for falsch in ({"ts": "2026-10-24T08:00:01+00:00"}, {"grund": "anders"}):
                try:
                    neu(t.k1, "first_use_on", None, "2024-06", gruppe=kid, **falsch)
                    raise AssertionError(falsch)
                except sqlite3.IntegrityError as e:
                    assert "höchstens ein offener" in str(e), e
            try:
                neu(t.k2, "first_use_on", None, "2024-06", gruppe=kid)
                raise AssertionError("fremder Artikel")
            except sqlite3.IntegrityError as e:
                assert "höchstens ein offener" in str(e) or "CHECK" in str(e), e
            folge = neu(t.k1, "interval_months", None, "6", gruppe=kid)
            geht_nicht("UPDATE mat_item_change SET group_id = NULL WHERE id = ?", (folge,), "nur einmal entscheiden")
            # Produkt und Lebensende nie leer (CHECK).
            for feld in ("product_id", "retire_by"):
                try:
                    neu(t.g1, feld, "x", None)
                    raise AssertionError(feld)
                except sqlite3.IntegrityError as e:
                    assert "CHECK" in str(e), e
            # Kein Vier-Augen: der Antragsteller selbst bestätigt.
            bestaetigt(kid)
            # Je Zeile genau ihre Änderung: erst der Kauf (nur seine Zeile ist danach verbraucht), dann das Intervall.
            geht_nicht("UPDATE mat_item SET purchased_on = '2024-07' WHERE id = ?", (t.k1,))
            conn.execute("UPDATE mat_item SET purchased_on = '2024-06' WHERE id = ?", (t.k1,))
            assert [r[0] for r in conn.execute("SELECT applied_at IS NOT NULL FROM mat_item_change WHERE id IN (?, ?) "
                                               "ORDER BY id", (kid, folge))] == [1, 0]
            conn.execute("UPDATE mat_item SET interval_months = 6 WHERE id = ?", (t.k1,))
            assert [r[0] for r in conn.execute("SELECT applied_at IS NOT NULL FROM mat_item_change WHERE id IN (?, ?) "
                                               "ORDER BY id", (kid, folge))] == [1, 1]
            geht_nicht("UPDATE mat_item SET purchased_on = '2024-05' WHERE id = ?", (t.k1,))       # verbraucht
            # Lebensende: genau der vorgezogene Wert; Produkt: genau dieses.
            kl = neu(t.g1, "retire_by", "2033-01-01", "2031-01-01")
            bestaetigt(kl)
            geht_nicht("UPDATE mat_item SET retire_by_manual = '2031-02-01', retire_by = '2031-02-01' WHERE id = ?", (t.g1,))
            conn.execute("UPDATE mat_item SET retire_by_manual = '2031-01-01', retire_by = '2031-01-01' WHERE id = ?", (t.g1,))
            kp = neu(t.k1, "product_id", str(t.ids["hms"]), str(t.sonst))
            bestaetigt(kp)
            geht_nicht("UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["gurt"], t.k1), "Produkt eines Artikels")
            conn.execute("UPDATE mat_item SET product_id = ? WHERE id = ?", (t.sonst, t.k1))
            assert conn.execute("SELECT applied_at FROM mat_item_change WHERE id = ?", (kp,)).fetchone()[0]
            conn.rollback()
        finally:
            conn.close()
    print("Trigger 23 bestanden.")


def _altbestand_22(tmp):
    """Ein Stand 22 mit Anträgen aus der Zeit davor: offene (Seriennummer und Herstellung am selben Artikel, gemeinsam
    gestellt – damals zwei Zeilen), bestätigte und abgelehnte; die Kennungsfolge liegt über den Zeilen (ein Antrag, den
    es nicht mehr gibt, ließ eine Lücke – hier nachgestellt über sqlite_sequence)."""
    t = bis_schritt(22)(aufbau, tmp)
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    try:
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "22"

        def neu(iid, feld, alt, wert):
            return conn.execute(
                "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, created_by_name, "
                "created_at) VALUES (?,?,?,?,'Platzhalter alt',?,'wart','2026-10-23T08:00:00+00:00')",
                (iid, feld, alt, wert, t.k["wart_id"])).lastrowid
        t.a_sn = neu(t.k1, "serial_no", "AN-100", "AN-ALT")
        t.a_hd = neu(t.k1, "manufactured_on", "2024-03", "2024-02")
        t.a_erl = neu(t.s1, "serial_no", "AN-S1", "AN-S1-ALT")
        conn.execute("UPDATE mat_item_change SET status = 'abgelehnt', answer = 'Platzhalter', resolved_by_name = 'katalog', "
                     "resolved_at = '2026-10-23T09:00:00+00:00' WHERE id = ?", (t.a_erl,))
        conn.execute("UPDATE sqlite_sequence SET seq = 40 WHERE name = 'mat_item_change'")
        conn.commit()
    finally:
        conn.close()
    return t


def test_migration_23():
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, _ = _schema(pfad)
        assert version == endversion(), version
        assert set(models.ANTRAG_TRIGGER_23) <= set(trigger) and "mat_item_change_gruppe" in trigger
        assert "'purchased_on'" in _tabelle_sql(pfad) and "group_id" in _tabelle_sql(pfad)
        assert "retire_by_manual" in trigger["mat_item_stammdaten_fest"]
        assert "mat_item_change" in trigger["mat_item_produkt_fest"]
        assert not any("vier" in n for n in trigger), trigger
        # Schritt 15 bleibt, wie er ausgeliefert wurde.
        assert models.ANTRAGSFELDER_15 == ("serial_no", "manufactured_on")
        assert "('serial_no', 'manufactured_on')" in models.SCHRITT_15[0]
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = _altbestand_22(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        alt = zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")
        vorher = _zahlen(pfad)
        v22, t22, _ = _schema(pfad)
        assert v22 == "22" and "'purchased_on'" not in _tabelle_sql(pfad)
        make_app(tmp)
        v23, t23, _ = _schema(pfad)
        # Seit Schritt 25 dazu dessen Trigger (Seriennummern der Bestandteile), seit Schritt 26 die Wächter des Rückbaus
        # der Set-Funktion statt der entfallenen Set-Trigger.
        neu_26 = {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_26}
        erwartet = (set(t22) | {"mat_item_change_gruppe"} | trigger_25() | neu_26 | trigger_27()) - set(models.TRIGGER_WEG_26)
        assert v23 == endversion() and set(t23) == erwartet, set(t23) ^ erwartet
        for n in ("mat_item_stammdaten_fest", "mat_item_produkt_fest", "mat_item_antrag_angewendet",
                  "mat_item_change_inhalt"):
            assert t23[n] != t22[n], n
        # Seit Schritt 25 dazu component_id, stueck und component_label (leer) – die alten Spalten unverändert.
        assert [{k: r[k] for k in alt[0]} for r in zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")] == alt \
            and len(alt) == 3
        assert all(x["group_id"] is None for x in alt)
        assert zeilen(t.app, "SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'")[0]["seq"] == 40
        assert _zahlen(pfad) == vorher
        indizes = {r["name"] for r in zeilen(t.app, "SELECT name FROM sqlite_master WHERE type = 'index' "
                                                    "AND tbl_name = 'mat_item_change' AND sql IS NOT NULL")}
        assert "idx_mat_item_change_gruppe" in indizes and "ux_mat_item_change_offen" in indizes, indizes
        # Zweiter Lauf: nichts.
        conn = sqlite3.connect(pfad)
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_23(conn)
        models._schritt_24(conn)                   # seit Schritt 24 die Artikeltrigger in seiner Fassung
        models._schritt_25(conn)                   # seit Schritt 25 die Antragstrigger in seiner Fassung
        models._schritt_26(conn)                   # seit Schritt 26 die Stücklisten-Trigger in seiner Fassung
        assert conn.total_changes == n and _schema_in(conn) == t23
        conn.rollback()
        conn.close()
        # Altanträge: zwei Einzelanträge am selben Artikel, beide sichtbar und entscheidbar (Materialwart, E5/E6).
        d = liste(t.w)
        assert [x["id"] for x in d["antraege"]] == [t.a_sn, t.a_hd] and d["zu_entscheiden"] == 2, d
        assert liste(t.mv)["antraege"] == []                    # die Material-Verwaltung ohne Verwalterfreigabe nicht
        assert bestaetigen(t.w, t.a_sn).status_code == 200 and item(t.app, t.k1)["serial_no"] == "AN-ALT"
        assert ablehnen(t.w, t.a_hd, antwort="Platzhalter").status_code == 200
        # Neue Kennungen liegen über der Folge.
        neu = beantragen(t.w, t.k1, purchased_on="2024-06").json["antrag"]["id"]
        assert neu == 41, neu
    print("Migration 22 → 23 bestanden.")


# --- Lebensende per Antrag auch wieder nach hinten (Wunsch vom 25.10.2026, Schritt 24) ---------------------------------

def test_lebensende_nach_hinten():
    """Ein vorgezogenes Lebensende lässt sich per Antrag wieder nach hinten setzen – höchstens bis zur Rechnung aus
    Herstellung und Lebensdauer. Genau die Rechnung: retire_by_manual wird leer, das Lebensende folgt danach wieder
    Herstellung und Katalog. Über die Rechnung hinaus 400 (auch beim Bestätigen, wenn der Katalog die Lebensdauer
    inzwischen verkürzt hat)."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        # g1: textil, Herstellung 01/2024, Lebensdauer 10 Jahre → Rechnung 01.01.2034.
        assert lesen(t.w, t.g1)["lebensdauer"]["berechnet"] == "2034-01-01"
        kid = beantragen(t.w, t.g1, retire_by="2030-05-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        # Nach hinten, aber vor die Rechnung: bleibt von Hand gesetzt.
        r = beantragen(t.p, t.g1, retire_by="2032-02-01")
        assert r.status_code == 201, r.get_json()
        a = r.json["antrag"]["aenderungen"][0]
        assert (a["feld"], a["alt"], a["neu"]) == ("retire_by", "2030-05-01", "2032-02-01"), a
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        g = item(t.app, t.g1)
        assert (g["retire_by"], g["retire_by_manual"]) == ("2032-02-01", "2032-02-01"), g
        j = journal(t.app, t.g1, "antrag_bestaetigt")[-1]
        assert j["vorher"]["retire_by"] == "2030-05-01" and j["nachher"]["retire_by"] == "2032-02-01", j
        # Über die Rechnung hinaus nicht – der Satz nennt sie.
        r = beantragen(t.w, t.g1, retire_by="2034-01-02")
        assert r.status_code == 400 and "höchstens bis zur Rechnung" in r.json["error"] and "01.01.2034" in r.json["error"]
        # Genau auf die Rechnung: nicht mehr von Hand gesetzt.
        kid = beantragen(t.w, t.g1, retire_by="2034-01-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        g = item(t.app, t.g1)
        assert (g["retire_by"], g["retire_by_manual"]) == ("2034-01-01", None), g
        x = lesen(t.w, t.g1)["lebensdauer"]
        assert x["vorgezogen"] is False and x["ende"] == "2034-01-01", x
        assert zeilen(t.app, "SELECT applied_at FROM mat_item_change WHERE id = ?", (kid,))[0]["applied_at"]
        j = journal(t.app, t.g1, "antrag_bestaetigt")[-1]
        assert j["vorher"] == {"retire_by": "2032-02-01", "retire_by_manual": "2032-02-01"} and \
            j["nachher"]["retire_by_manual"] is None, j
        # Danach folgt es wieder der Herstellung (per Antrag).
        kid = beantragen(t.w, t.g1, manufactured_on="2024-06").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert (item(t.app, t.g1)["retire_by"], item(t.app, t.g1)["retire_by_manual"]) == ("2034-06-01", None)
        # Herstellung und Lebensende in einem Antrag: die Grenze ist die neue Rechnung.
        kid = beantragen(t.w, t.g1, retire_by="2031-01-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        r = beantragen(t.w, t.g1, manufactured_on="2024-03", retire_by="2034-06-01")
        assert r.status_code == 400 and "01.03.2034" in r.json["error"], r.get_json()
        # Dasselbe Datum, das die neue Herstellung ohnehin ergäbe, ohne von Hand gesetztes: kein Lebensende-Antrag.
        kid = beantragen(t.w, t.g1, retire_by="2034-06-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200 and item(t.app, t.g1)["retire_by_manual"] is None
        r = beantragen(t.w, t.g1, manufactured_on="2024-03", retire_by="2034-03-01")
        assert r.status_code == 400 and "ergibt sich schon" in r.json["error"], r.get_json()
        kid = beantragen(t.w, t.g1, manufactured_on="2024-03", retire_by="2033-03-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        assert (item(t.app, t.g1)["retire_by"], item(t.app, t.g1)["retire_by_manual"]) == ("2033-03-01", "2033-03-01")
        # Beim Bestätigen gilt die Rechnung von dann: Der Katalog verkürzt die Lebensdauer, der Antrag geht nicht mehr.
        r = beantragen(t.w, t.g1, retire_by="2034-01-01")
        assert r.status_code == 201, r.get_json()
        kid = r.json["antrag"]["id"]
        sql(t.app, "UPDATE mat_product SET lifetime_years = 9 WHERE id = ?", (t.ids["gurt"],))
        r = bestaetigen(t.w, kid)
        assert r.status_code == 400 and "01.03.2033" in r.json["error"], r.get_json()
        assert ablehnen(t.w, kid, antwort="Platzhalter").status_code == 200
    print("Lebensende nach hinten bestanden.")


def test_trigger_24():
    """Schritt 24: retire_by_manual wird nur mit einem bestätigten Antrag leer, dessen neuer Wert das wirksame Lebensende
    derselben Anweisung ist; die Zeile ist danach angewendet. Alles andere wie Schritt 23."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kid = beantragen(t.w, t.g1, retire_by="2030-05-01").json["antrag"]["id"]
        assert bestaetigen(t.w, kid).status_code == 200
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        wart = t.k["wart_id"]

        def geht_nicht(befehl, args=()):
            try:
                conn.execute(befehl, args)
            except sqlite3.IntegrityError as e:
                assert "seit seiner ersten Prüfung fest" in str(e), (befehl, e)
                return
            raise AssertionError(befehl)

        try:
            leeren = "UPDATE mat_item SET retire_by_manual = NULL, retire_by = ? WHERE id = ?"
            geht_nicht(leeren, ("2034-01-01", t.g1))                      # ohne Antrag
            kz = conn.execute("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                              "created_by_name, created_at) VALUES (?, 'retire_by', '2030-05-01', '2034-01-01', "
                              "'Platzhalter', ?, 'wart', '2026-10-25T08:00:00+00:00')", (t.g1, wart)).lastrowid
            geht_nicht(leeren, ("2034-01-01", t.g1))                      # offen, nicht bestätigt
            conn.execute("UPDATE mat_item_change SET status = 'bestaetigt', resolved_by = ?, resolved_by_name = 'wart', "
                         "resolved_at = '2026-10-25T09:00:00+00:00' WHERE id = ?", (wart, kz))
            geht_nicht(leeren, ("2033-01-01", t.g1))                      # anderes wirksames Lebensende
            geht_nicht("UPDATE mat_item SET retire_by_manual = '2032-01-01', retire_by = '2032-01-01' WHERE id = ?",
                       (t.g1,))                                           # anderer von Hand gesetzter Wert
            conn.execute(leeren, ("2034-01-01", t.g1))
            assert conn.execute("SELECT applied_at FROM mat_item_change WHERE id = ?", (kz,)).fetchone()[0]
            geht_nicht("UPDATE mat_item SET retire_by_manual = '2030-05-01', retire_by = '2030-05-01' WHERE id = ?",
                       (t.g1,))                                           # verbraucht, nicht zurück
            conn.rollback()
        finally:
            conn.close()
    print("Trigger 24 bestanden.")


def test_migration_24():
    """23 → 24: nur die zwei Artikeltrigger ändern sich (gleiche Namen), keine Tabelle, keine Zeile; zweiter Lauf
    nichts; ein frischer Stand 24 hat dieselben Trigger. Seit Schritt 25 läuft die Migration dafür nur bis 24
    (bis_schritt); 24 → 25 prüft test_material_bestandteile.test_migration_25."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        bis_schritt(24)(make_app, frisch)
        v, t_frisch, _ = _schema(os.path.join(frisch, "stroemis.db"))
        assert v == "24" and int(endversion()) >= 25, v
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(23)(aufbau, tmp)
        kid = beantragen(t.w, t.g1, retire_by="2030-05-01").json["antrag"]["id"]
        pfad = os.path.join(tmp, "stroemis.db")
        alt = zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")
        vorher = _zahlen(pfad)
        v23, t23, _ = _schema(pfad)
        assert v23 == "23", v23
        bis_schritt(24)(make_app, tmp)
        v24, t24, _ = _schema(pfad)
        assert v24 == "24" and set(t24) == set(t23), set(t24) ^ set(t23)
        assert {n for n in t24 if t24[n] != t23[n]} == {"mat_item_stammdaten_fest", "mat_item_antrag_angewendet"}
        assert t24 == t_frisch
        assert zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id") == alt and _zahlen(pfad) == vorher
        conn = sqlite3.connect(pfad)
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_24(conn)
        assert conn.total_changes == n and _schema_in(conn) == t24
        conn.rollback()
        conn.close()
        # Der offene Antrag aus Stand 23 wirkt nach dem Umstieg wie zuvor.
        assert bestaetigen(t.w, kid).status_code == 200 and item(t.app, t.g1)["retire_by_manual"] == "2030-05-01"
    print("Migration 23 → 24 bestanden.")


# --- 6. Produktjournal am Artikel (E8), Seiten, Mailprotokoll ---------------------------------------------------------

def test_produktaenderung_am_artikel():
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = t.mv.put(f"/api/material/produkte/{t.ids['hms']}", headers=H, json={"norm": "EN 362:Platzhalter"})
        assert r.status_code == 200, r.get_json()
        j = [e for e in lesen(t.w, t.k1)["journal"] if e["entity"] == "product" and e["action"] == "geaendert"]
        assert j and j[0]["nachher"]["norm"] == "EN 362:Platzhalter", j
        text = " ".join(_pdf_text(t.w.get(f"/material/artikel/{t.k1}/lebenslauf.pdf").data).split())
        assert "Produkt geändert" in text and "EN 362:Platzhalter" in text, text
        # Rückrufe stehen im eigenen Abschnitt, nicht als Journalzeile des Produkts.
        t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                  json={"title": "Platzhalter-Rückruf E8", "serials": "AN-100\nAN-B1", "mail": False})
        text = " ".join(_pdf_text(t.w.get(f"/material/artikel/{t.k1}/lebenslauf.pdf").data).split())
        assert "Rückruf angelegt" not in text and "AN-B1" not in text, text
        # Materialart mit Artikeln bleibt 409, Löschen eines Produkts mit Artikeln auch.
        assert t.mv.put(f"/api/material/produkte/{t.ids['hms']}", headers=H,
                        json={"material_kind": "textil", "lifetime_years": 10}).status_code == 409
        assert t.mv.delete(f"/api/material/produkte/{t.ids['hms']}", headers=H).status_code == 409
    print("Produktänderung am Artikel bestanden.")


def test_seiten():
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = t.w.get("/material/katalog/meldungen?bereich=antraege&status=erledigt")
        assert r.status_code == 302 and r.headers["Location"].endswith("/material/bestand/antraege?status=erledigt"), r
        r = t.w.get("/material/katalog/meldungen?bereich=antraege")
        assert r.headers["Location"].endswith("/material/bestand/antraege")
        r = t.w.get("/material/bestand/antraege")
        assert r.status_code == 200 and "antraege" in r.get_data(as_text=True)
        assert "antraege_offen" not in t.mv.get("/api/material/meldungen?status=offen").json
        from app.material.services import mailprotokoll
        assert mailprotokoll.BEZUG_PFAD["change"] == "/material/bestand/antraege"
    print("Seiten bestanden.")


def test_oberflaeche_statisch():
    """material.js: Knopf „Änderungsanträge“ mit Blase auf der Bestandsseite, eigene Seite mit Filter und Karten (graue
    Knöpfe, Rückfragen mit einem roten Knopf bzw. „Ablehnen“ endgültig), Katalog → Meldungen ohne Bereichswahl, Blase
    dort nur Produktmeldungen; Dialog „Bearbeiten“ mit schreibgeschütztem Block und grauem „Änderung beantragen …“,
    Antragsdialog mit allen Feldern und EINEM roten „Antrag senden“; Prüfer bearbeiten die drei direkten Felder; kein
    Hilfetext unter Knöpfen; kein btn ghost."""
    js = open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8").read()
    best = js[js.index("async function bestand()"):js.index("/* --- Foto im Dialog")]
    assert ('<a class="btn secondary mat-mit-zahl" href="/material/bestand/antraege">Änderungsanträge'
            '<span class="mat-meldezahl" id="bst-antraege" hidden></span></a>') in best
    assert "antraegeZaehlen(" in best
    seite = js[js.index("async function antraegeSeite()"):js.index("function antragBestaetigenDialog")]
    assert '<a class="btn secondary" href="/material/bestand">Bestand</a>' in seite
    karte = seite[seite.index("function antragKarte("):]
    assert 'class="btn"' not in karte and "btn danger" not in karte and 'data-act="bestaetigen"' in karte
    best_dlg = js[js.index("function antragBestaetigenDialog"):js.index("function antragAblehnenDialog")]
    assert best_dlg.count('class="btn"') == 1
    abl = js[js.index("function antragAblehnenDialog"):js.index("function zuordnenDialog")]
    assert '<button class="btn danger" id="aa-ablehnen" type="button">Ablehnen</button>' in abl and 'class="btn"' not in abl
    m = js[js.index("async function meldungen()"):js.index("function zuordnenDialog(m, danach)")]
    assert "mat-bereiche" not in js and "bereich=antraege" not in js and "antraegeZeichnen" not in m
    zaehlen = js[js.index("async function meldungenZaehlen(el)"):js.index("async function meldungenZaehlen(el)") + 600]
    assert "antraege_offen" not in zaehlen
    dlg = js[js.index("function artikelDialog(a)"):js.index("/* --- Änderungsanträge")]
    assert "Seit der ersten Prüfung fest – Teil des Prüfnachweises." in dlg and 'id="ad-antrag">Änderung beantragen …' in dlg
    assert "herstellung_nachtragbar" not in js and "nachtragen" not in dlg
    antrag_dlg = js[js.index("function antragDialog(a)"):js.index("/* --- Artikel anlegen")]
    assert antrag_dlg.count('class="btn"') == 1 and '<button class="btn" id="aa-ok" type="button">Antrag senden</button>' in antrag_dlg
    for feld in ("aa-sn", "aa-herst", "aa-kauf", "aa-erst", "aa-ende", "aa-int", "aa-grund", "aa-anders"):
        assert f'id="{feld}"' in antrag_dlg or f'datumFeld("{feld}"' in antrag_dlg, feld
    assert "produktFolgen(a, neuesProdukt)" in antrag_dlg
    # Lebensende auch wieder nach hinten (25.10.2026): Hilfe am Feld mit der Rechnung, kein „nur vorziehen“ mehr.
    assert "Lebensende (nur vorziehen)" not in antrag_dlg and 'id="aa-ende-hilfe"' in antrag_dlg
    assert "a.lebensdauer.berechnet" in antrag_dlg and "höchstens bis" in antrag_dlg
    artikel = js[js.index("async function artikel()"):js.index("function artikelDialog(a)")]
    assert "Seriennummer und Herstellung stehen seit der ersten Prüfung fest – eine Abweichung beantragst du" not in js
    assert "darf.pruefen" in artikel and 'data-act="entscheiden"' not in artikel
    assert '/material/bestand/antraege">Entscheiden …</a>' in js
    assert "btn ghost" not in js
    assert ".mat-bereiche" not in css
    assert "antraege: \"bestand\"" in js and "antraege: antraegeSeite" in js
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_zustaendig()
    test_ohne_zustaendige()
    test_sammelantrag()
    test_felder()
    test_bearbeiten()
    test_trigger_23()
    test_migration_23()
    test_lebensende_nach_hinten()
    test_trigger_24()
    test_migration_24()
    test_produktaenderung_am_artikel()
    test_seiten()
    test_oberflaeche_statisch()
