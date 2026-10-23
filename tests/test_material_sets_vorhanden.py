"""Hersteller-Sets, Teil 2 – KERN A (Phase 4 · Lieferung 2b):  python tests/test_material_sets_vorhanden.py  oder  pytest

Vorhandenen Artikel einsetzen (beim Set anlegen und bei „Teil einsetzen“) mit Sicht, Produkt, Gliederung, DEMO-Grenze und
Zuständen in dieser Reihenfolge, Reihenfolge der Wirkung (sperren vor Durchgang und Fälligkeit, freies UND gesperrtes Set),
Prüfung im offenen Lauf (T2), Zuordnung (U10), die Auswahl (Kandidaten am Set und am Ordner, „Bisherige Inventarnummer“
aus dem Bestandsimport, Grenzen), der Prüfumfang eines nie geprüften Sets (Probe P-B), „Set löschen“ mit vorhandenen
Teilen (Probe P-A), „Set auflösen“ mit allen Bedingungen (auch die Fremdschlüssel-Fälle) und „Bestandteil ersetzt“ mit
Marke an der Set-Zeile (Proben P5/P6 aus kritik_l2b_sicherheit), Rechte und Trennung der neuen Routen.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import io
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, mails_abfangen, mails_zurueck, neuer_artikel, neues_konto, starten  # noqa: E402
from test_material_import import csv_bytes, nach_nr, ok, probelauf  # noqa: E402
from test_material_sets import set_aufbau, set_neu, stimmig  # noqa: E402
from test_material_sets_pruefung import eingangsgeprueft, eintraege, lage, lauf_auf, pruefen  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post, ordner_neu  # noqa: E402


# --- Hilfen -------------------------------------------------------------------------------------------------------------

def positionen(liste):
    """(Position der zwei HMS Beta, Position der Rolle Gamma) aus der Stückliste von set_katalog."""
    hms = next(b["id"] for b in liste if b["einzeln"] and b["anzahl"] == 2)
    rolle = next(b["id"] for b in liste if b["einzeln"] and b["anzahl"] == 1)
    return hms, rolle


def anlegen(c, t, ordner, serie, hms=(), rolle=None):
    """POST /artikel mit dem Set-Produkt: hms – zwei Einträge (Kennung eines vorhandenen Artikels oder Seriennummer eines
    neuen Teils als Text mit „neu:“ davor), rolle ebenso. Liefert die Antwort."""
    hms_pos, rolle_pos = positionen(t.liste)

    def block(pos, x):
        if isinstance(x, str) and x.startswith("neu:"):
            return {"bestandteil_id": pos, "serial_no": x[4:]}
        if isinstance(x, dict):
            return dict(x, bestandteil_id=pos)
        return {"bestandteil_id": pos, "item_id": x}
    teile = [block(hms_pos, x) for x in hms] + [block(rolle_pos, rolle if rolle is not None else f"neu:{serie}-R")]
    return c.post("/api/material/artikel", json={"product_id": t.set_p, "folder_id": ordner, "serial_no": serie,
                                                 "manufactured_on": f"{_heute().year - 1}-03", "teile": teile})


def kennung_von(app, serie):
    return zeilen(app, "SELECT id FROM mat_item WHERE serial_no = ?", (serie,))[0]["id"]


def zeile(app, iid):
    return zeilen(app, "SELECT * FROM mat_item WHERE id = ?", (iid,))[0]


def aktionen(app, iid, ab=0):
    return [x["action"] for x in eintraege(app, iid, ab)]


def letzte_id(app):
    return zeilen(app, "SELECT COALESCE(MAX(id), 0) AS m FROM mat_audit")[0]["m"]


def kandidaten(c, fid, pid, q):
    return c.get(f"/api/material/ordner/{fid}/kandidaten", query_string={"product_id": pid, "q": q})


def sperren_bericht(c, gliederung):
    return ok(c.get(f"/api/material/ordner/{gliederung}/bericht?jahr={_heute().year}"))["bericht"]["sperren"]


# --- 1. Set anlegen mit vorhandenen Teilen, Auswahl im Ordner, Bestandsimport -------------------------------------------

def test_anlegen_mit_vorhandenen():
    """Liste mit Set-Karabinern als eigenen Zeilen importieren (die Set-Zeile geht mit Hinweis in die Nacharbeit), die
    Teile über die Auswahl finden (auch über die „Bisherige Inventarnummer“), das Set mit ihnen anlegen: Bedingungen in
    der Reihenfolge Sicht → Produkt → Gliederung/DEMO → Zustände, Eingabeform (item_id oder Felder, doppelt), Wirkung
    (Ordner und Zuordnung wie das Set, Journal an Teil und Set) und Grenzen der Auswahl."""
    from app.material.services import mangel
    alt = mails_abfangen(mangel, lambda an, betreff, inhalt: True)
    try:
        with ohne_post(), tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, w, p, adm = t.app, t.wart_a, t.k["pruefer"], t.adm
            jahr = _heute().year - 1
            daten = csv_bytes([["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Inventarnummer", "Herstellung"],
                               ["Testwerk", "HMS Beta", "HB-7", "IMP-K1", "ALT-0815", f"{jahr}-01"],
                               ["Testwerk", "HMS Beta", "HB-7", "IMP-K2", "ALT-0816", f"{jahr}-01"],
                               ["Testwerk", "Rolle Gamma", "RG-1", "IMP-R1", "ALT-0817", f"{jahr}-01"],
                               ["Testwerk", "Testset Alpha", "TS-1", "IMP-SET-1", "ALT-0800", f"{jahr}-01"]])
            bericht = ok(probelauf(w, t.lager_a, daten))
            satz = nach_nr(bericht)[5]
            assert satz["status"] == "nacharbeit", satz
            assert any("aus dem Bestand wählen" in g["text"] and "erneut prüfen" in g["text"] for g in satz["gruende"]), satz
            r = ok(w.post(f"/api/material/ordner/{t.lager_a}/import", headers=H, content_type="multipart/form-data",
                          data={"file": (io.BytesIO(daten), "liste.csv")}), 201)
            assert r["import"]["angelegt"] == 3, r
            k1, k2, r1 = (kennung_von(app, x) for x in ("IMP-K1", "IMP-K2", "IMP-R1"))
            assert "Bisherige Inventarnummer: ALT-0815" in zeile(app, k1)["notes"]

            # Auswahl im Ordner: Inventar-, Serien- und bisherige Inventarnummer; nur Produkt der Position, frei, ohne Set.
            hms = t.ids["hms"]
            r = ok(kandidaten(w, t.lager_a, hms, "0815"))
            assert [x["id"] for x in r["treffer"]] == [k1] and r["weitere"] is False and r["hinweis"] is None, r
            assert r["treffer"][0]["bisherige_inventarnummer"] == "ALT-0815", r
            assert set(r["treffer"][0]) == {"id", "inventory_no", "serial_no", "bisherige_inventarnummer", "produkt",
                                            "ordner", "status", "status_text", "zugeordnet"}, r
            assert [x["id"] for x in ok(kandidaten(w, t.lager_a, hms, "imp-k"))["treffer"]] == [k1, k2]
            inv_k2 = zeile(app, k2)["inventory_no"]
            assert [x["id"] for x in ok(kandidaten(w, t.lager_a, hms, inv_k2))["treffer"]] == [k2]
            # Teil eines Sets und Artikel mit anderem Produkt sind keine Kandidaten; die Nummer eines anderen Produkts genau
            # → 200 mit „hinweis“ (beide Namen, der Artikel); fremd und unbekannt gleich (200, leer – Nachbesserung B3);
            # zu kurz, zu lang 400; LIKE-Zeichen wörtlich.
            unbekannt = kandidaten(w, t.lager_a, hms, "GIBTESNICHT")
            assert unbekannt.status_code == 200 and unbekannt.get_json() == {"treffer": [], "weitere": False,
                                                                             "hinweis": None}, unbekannt.get_json()
            for q in ("SET-A-K1", "TEST-B-0001", "SET-B-K1", "%%", "_M"):
                r = kandidaten(w, t.lager_a, hms, q)
                assert (r.status_code, r.get_json()) == (200, unbekannt.get_json()), (q, r.get_json())
            r = ok(kandidaten(w, t.lager_a, hms, "imp-r1"))
            assert r["treffer"] == [] and "Rolle Gamma" in r["hinweis"]["text"] and "HMS Beta" in r["hinweis"]["text"] \
                and "Einsetzen lässt sich nur" in r["hinweis"]["text"] and r["hinweis"]["artikel"]["id"] == r1, r
            for q, code in (("a", 400), ("x" * 81, 400)):
                assert kandidaten(w, t.lager_a, hms, q).status_code == code, q
            assert kandidaten(w, t.lager_a, t.set_p, "IMP").status_code == 400            # ein Set-Produkt ist kein Teil
            assert kandidaten(w, t.sys_a["gesperrt"], hms, "IMP").status_code in (403, 409)
            # Grenze: höchstens 20 Treffer, dann „weitere“.
            for n in range(21):
                neuer_artikel(w, hms, t.lager_a, serial_no=f"VIEL-{n:02d}")
            r = ok(kandidaten(w, t.lager_a, hms, "VIEL-"))
            assert len(r["treffer"]) == 20 and r["weitere"] is True, r
            # Nur dieselbe Gliederung, nicht über die DEMO-Grenze.
            demo = ordner_neu(w, t.a, "Demo Musterstadt")
            sql(app, "UPDATE mat_folder SET demo = 1 WHERE id = ?", (demo,))
            d1 = neuer_artikel(w, hms, demo, serial_no="DEMO-K1")["id"]
            assert ok(kandidaten(w, t.lager_a, hms, "DEMO-K1"))["treffer"] == []
            andere = neuer_artikel(adm, hms, t.lager_b, serial_no="ANDERE-GL-1")["id"]
            assert ok(kandidaten(adm, t.lager_a, hms, "ANDERE-GL"))["treffer"] == []

            # Zuordnung und Ablage vor dem Einsetzen: K1 einer Person zugeordnet, R1 in einem Fach.
            person, person_id = neues_konto(app, "psa_vorhanden@example.org", name="PSA Vorhanden", stufe=0)
            ok(w.put(f"/api/material/artikel/{k1}/zuordnung", json={"user_id": person_id}))
            fach = ordner_neu(w, t.lager_a, "Fach Musterstadt")
            ok(w.post("/api/material/artikel/verschieben", json={"ids": [r1], "folder_id": fach}))

            # Eingabeform: item_id oder Felder; eine Kennung nur einmal; Unsinn 400.
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=({"item_id": k1, "serial_no": "X-1"}, k2), rolle=r1)
            assert r.status_code == 400 and "nicht beides" in r.json["error"], r.get_json()
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(k1, k1), rolle=r1)
            assert r.status_code == 400 and "zweimal" in r.json["error"], r.get_json()
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=({"item_id": "abc"}, k2), rolle=r1)
            assert r.status_code == 400, r.get_json()
            # Sicht: fremd (B, auch als Text und 7.0) wie unbekannt.
            unbekannt = anlegen(w, t, t.lager_a, "SET-V-1", hms=(999999, k2), rolle=r1)
            assert unbekannt.status_code == 404 and unbekannt.json["error"] == "Artikel nicht gefunden.", unbekannt.get_json()
            for fremd in (t.art_b["id"], str(t.teile_b[0]), float(t.sb["id"])):
                r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(fremd, k2), rolle=r1)
                assert (r.status_code, r.get_json()) == (404, unbekannt.get_json()), (fremd, r.get_json())
            # Produkt vor Gliederung und Zustand: die Rolle an der HMS-Position, das Set selbst.
            for falsch in (r1, t.s["id"]):
                r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(falsch, k2), rolle="neu:SET-V-1-R")
                assert r.status_code == 409 and "Einsetzen lässt sich nur" in r.json["error"], r.get_json()
            # Gliederung (die Verwaltung sieht beide) und DEMO-Grenze.
            r = anlegen(adm, t, t.lager_a, "SET-V-1", hms=(andere, k2), rolle=r1)
            assert r.status_code == 409 and "anderen Gliederung" in r.json["error"], r.get_json()
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(d1, k2), rolle=r1)
            assert r.status_code == 409 and "Demodaten" in r.json["error"], r.get_json()
            # Zustände: Teil eines Sets, gesperrt, offener Entwurf, offene Meldung, offener Rückruf, Lebensdauer.
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(t.teile[0], k2), rolle=r1)
            assert r.status_code == 409 and "Teil des Sets" in r.json["error"], r.get_json()
            gesperrt = neuer_artikel(w, hms, t.lager_a, serial_no="GESP-1")["id"]
            ok(p.post(f"/api/material/artikel/{gesperrt}/sperren", json={"grund": "sturz"}))
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(gesperrt, k2), rolle=r1)
            assert r.status_code == 409 and "nur freie Artikel" in r.json["error"], r.get_json()
            entwurf = neuer_artikel(w, hms, t.lager_a, serial_no="ENTW-1")["id"]
            e = ok(starten(p, entwurf), 201)["pruefung"]
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(entwurf, k2), rolle=r1)
            assert r.status_code == 409 and "In Prüfung bei" in r.json["error"], r.get_json()
            assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
            gemeldet = neuer_artikel(w, hms, t.lager_a, serial_no="MELD-1")["id"]
            sql(app, "INSERT INTO mat_defect_report (item_id, description, reporter_name, lock_before, created_at) "
                     "VALUES (?, 'Testmangel', 'Test', 'frei', ?)", (gemeldet, _heute().isoformat() + "T00:00:00+00:00"))
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(gemeldet, k2), rolle=r1)
            assert r.status_code == 409 and "Mangel offen" in r.json["error"], r.get_json()
            rr = neuer_artikel(w, t.rolle, t.lager_a, serial_no="RUECK-1")["id"]
            ok(t.k["katalog"].post(f"/api/material/produkte/{t.rolle}/rueckrufe",
                                   json={"title": "Testrückruf Rolle", "serials": "RUECK-1", "mail": False}), 201)
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(k1, k2), rolle=rr)
            assert r.status_code == 409 and "Testrückruf Rolle" in r.json["error"], r.get_json()
            alt_k = neuer_artikel(w, hms, t.lager_a, serial_no="LEBEN-1")["id"]
            sql(app, "UPDATE mat_item SET retire_by = ? WHERE id = ?", ((_heute() - timedelta(days=1)).isoformat(), alt_k))
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(alt_k, k2), rolle=r1)
            assert r.status_code == 409 and "Lebensdauer" in r.json["error"], r.get_json()
            # Ein Leser und ein Prüfer verwalten den Ordner nicht: 403 (Route), nichts geschrieben.
            assert anlegen(t.k["fuehrung"], t, t.lager_a, "SET-V-1", hms=(k1, k2), rolle=r1).status_code == 403
            assert not zeilen(app, "SELECT 1 FROM mat_item WHERE serial_no = 'SET-V-1'")
            assert all(zeile(app, x)["parent_item_id"] is None for x in (k1, k2, r1))

            # Erfolg: alle drei vorhanden, das Set neu und frei.
            ab = letzte_id(app)
            r = anlegen(w, t, t.lager_a, "SET-V-1", hms=(k1, str(k2)), rolle=float(r1))
            assert r.status_code == 201, r.get_json()
            s = r.json["artikel"]["id"]
            assert r.json["hinweise"] == [] and sorted(x["id"] for x in r.json["artikel"]["set"]["teile"]) == sorted([k1, k2, r1])
            for x in (k1, k2, r1):
                z = zeile(app, x)
                assert (z["parent_item_id"], z["folder_id"], z["lock_state"], z["assigned_user_id"], z["set_pruefen"]) == (
                    s, t.lager_a, "frei", None, 0), z
            assert zeile(app, s)["lock_state"] == "frei" and stimmig(app)
            assert aktionen(app, k1, ab) == ["zuordnung_geloest", "eingesetzt"]
            assert aktionen(app, r1, ab) == ["verschoben", "eingesetzt"]
            ein = eintraege(app, r1, ab)[-1]
            assert f'"set": {s}' in ein["after_json"] and "Rolle" in ein["after_json"], ein
            j = eintraege(app, s, ab)
            # Ein Eintrag am Set (Nachbesserung V11): „set_angelegt“ nennt die drei als vorhanden, ohne Herkunftspfad.
            assert [x["action"] for x in j] == ["angelegt", "set_angelegt"], j
            assert j[1]["after_json"].count('"vorhanden": true') == 3, j[1]
            assert "ordner" not in j[1]["after_json"] and "herkunft" not in j[1]["after_json"], j[1]
            # Danach sind die drei keine Kandidaten mehr.
            assert ok(kandidaten(w, t.lager_a, hms, "IMP-K"))["treffer"] == []
    finally:
        mails_zurueck(alt)
    print("Set anlegen mit vorhandenen Teilen bestanden.")


# --- 2. Teil einsetzen mit vorhandenem Artikel: Reihenfolge, Lauf, Zuordnung ---------------------------------------------

def test_einsetzen_vorhandener():
    """„Teil einsetzen“ mit item_id in ein gesperrtes Set (T3): erst sperren, dann Durchgang und Fälligkeit nach der Heimat
    des Sets – die Durchgangszeile bleibt, das strengere Ordnerintervall greift. Beim Anlegen (freies Set) nimmt ein
    Durchgang des alten Zweigs den Artikel heraus. Zuordnung des Sets (U10), Journal ohne Herkunftspfad (T14), eine
    Prüfung im offenen Lauf desselben Sets → 409 (T2), item_id beim Tauschen 400, mit Feldern 400, vollständiges Set 409,
    Auswahl am Set (Position fremd 404)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        hms = t.ids["hms"]
        # Ein Set im Fach mit strengem Intervall (1 Monat), eingangsgeprüft, einer Person zugeordnet.
        fach = ordner_neu(w, t.lager_a, "Fach Streng")
        ok(w.put(f"/api/material/ordner/{fach}", json={"name": "Fach Streng", "interval_months": 1}))
        neu = set_neu(w, t.set_p, fach, t.liste, "SET-T3", ("SET-T3-K1", "SET-T3-K2", "SET-T3-R1"))["artikel"]
        s, (k1, k2, r1) = neu["id"], [x["id"] for x in neu["set"]["teile"]]
        lauf_auf(p, s)
        for x in (k1, k2, r1, s):
            pruefen(p, x)
        assert zeile(app, s)["lock_state"] == "frei"
        p1, p1_id = neues_konto(app, "psa_eins@example.org", name="PSA Eins", stufe=0)
        _, p2_id = neues_konto(app, "psa_zwei@example.org", name="PSA Zwei", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": p1_id}))
        # Vollständig: item_id → 409 wie beim neuen Teil.
        f = t.f["id"]
        r = w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"item_id": f, "bestaetigt": True})
        assert r.status_code == 409 and "vollständig" in r.json["error"], r.get_json()
        # Tauschen nur mit neuem Teil; Einsetzen nicht mit item_id und Feldern.
        r = w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": k1, "item_id": f, "bestaetigt": True})
        assert r.status_code == 400 and "nur mit einem neuen Teil" in r.json["error"], r.get_json()
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k2}))
        assert zeile(app, s)["lock_state"] == "gesperrt"
        r = w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"item_id": f, "serial_no": "X-2", "bestaetigt": True})
        assert r.status_code == 400 and "nicht beides" in r.json["error"], r.get_json()
        # Auswahl am Set: Position dieses Sets (einzeln geführt), sonst 404 wie unbekannt.
        hms_slot = next(b["id"] for b in neu["set"]["bestandteile"] if b["einzeln"] and b["anzahl"] == 2)
        tasche = next(b["id"] for b in neu["set"]["bestandteile"] if not b["einzeln"])
        fremd_slot = next(b["id"] for b in t.sb["set"]["bestandteile"] if b["einzeln"])
        r = ok(w.get(f"/api/material/artikel/{s}/kandidaten", query_string={"slot_id": hms_slot, "q": "FREI-A"}))
        assert [x["id"] for x in r["treffer"]] == [f], r
        unbekannt = w.get(f"/api/material/artikel/{s}/kandidaten", query_string={"slot_id": 999999, "q": "FREI-A"})
        assert unbekannt.status_code == 404
        for slot in (tasche, fremd_slot):
            r = w.get(f"/api/material/artikel/{s}/kandidaten", query_string={"slot_id": slot, "q": "FREI-A"})
            assert (r.status_code, r.get_json()) == (404, unbekannt.get_json()), r.get_json()
        assert p.get(f"/api/material/artikel/{s}/kandidaten", query_string={"slot_id": hms_slot, "q": "FREI-A"}
                     ).status_code == 403
        # Wettlauf (U9): Ändert sich der Artikel zwischen dem Lesen und dem Schreiben (hier mitten in der Prüfung der
        # Zustände nachgestellt), trifft das bedingte UPDATE nichts – 409, nichts geschrieben.
        from app import db as db_mod
        from app.material.services import mangel
        echt = mangel.offene_ids

        def dazwischen(iid):
            db_mod.execute("UPDATE mat_item SET folder_id = ? WHERE id = ?", (fach, iid))
            return echt(iid)
        mangel.offene_ids = dazwischen
        try:
            r = w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"item_id": f, "bestaetigt": True})
        finally:
            mangel.offene_ids = echt
        assert r.status_code == 409 and "inzwischen geändert" in r.json["error"], r.get_json()
        assert zeile(app, f)["folder_id"] == t.lager_a and zeile(app, f)["parent_item_id"] is None
        # Durchgang über das Lager (F liegt darin, das Set im Fach darunter); F einer anderen Person zugeordnet.
        rid = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang T3"}), 201)[
            "durchgang"]["id"]
        ok(w.put(f"/api/material/artikel/{f}/zuordnung", json={"user_id": p2_id}))
        grenze = (_heute() + timedelta(days=31)).isoformat()
        assert zeile(app, f)["next_due_on"] > grenze
        ab = letzte_id(app)
        r = ok(w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"item_id": str(f), "bestaetigt": True}), 201)
        assert r["teil"]["id"] == f and r["hinweise"] == []
        assert lage(app, s)[f] == (t.sys_a["gesperrt"], fach, "gesperrt", "set", 1), lage(app, s)
        z = zeile(app, f)
        assert z["assigned_user_id"] == p1_id and z["next_due_on"] <= grenze, z
        assert zeilen(app, "SELECT excluded_reason FROM mat_round_item WHERE round_id = ? AND item_id = ?",
                      (rid, f))[0]["excluded_reason"] is None
        assert aktionen(app, f, ab) == ["verschoben", "zuordnung_geloest", "zugeordnet", "eingesetzt", "set_gesperrt",
                                        "faelligkeit"], aktionen(app, f, ab)
        j = eintraege(app, s, ab)
        assert [x["action"] for x in j] == ["teil_eingesetzt"], j
        assert '"vorhanden": true' in j[0]["after_json"] and "ordner" not in j[0]["after_json"], j
        assert '"bestaetigt": "laut Herstellerunterlagen zulässig"' in j[0]["after_json"]
        nr_f = zeile(app, f)["inventory_no"]
        assert zeile(app, s)["lock_reason"] == f"Teil {nr_f} neu eingesetzt – Set prüfen"
        assert ok(p1.get("/api/material/meine-psa"))["gesamt"] == 1
        assert stimmig(app)
        lf = lauf_auf(p, s)
        assert {u["teil"]["id"]: u["zu_pruefen"] for u in lf["umfang"]} == {k1: False, r1: False, f: True}, lf["umfang"]
        ok(w.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))

        # T2: im offenen Lauf geprüft, entnommen, wieder eingesetzt → 409; nach Abbruch des Laufs geht es.
        t_s = t.s["id"]
        sk1 = t.teile[0]
        eingangsgeprueft(t)
        lauf_auf(p, t_s)
        pruefen(p, sk1)
        ok(w.post(f"/api/material/artikel/{t_s}/teil-entnehmen", json={"teil_id": sk1}))
        assert zeile(app, sk1)["lock_state"] == "frei"
        r = w.post(f"/api/material/artikel/{t_s}/teil-einsetzen", json={"item_id": sk1, "bestaetigt": True})
        assert r.status_code == 409 and "offenen Set-Prüfung" in r.json["error"], r.get_json()
        ok(w.delete(f"/api/material/artikel/{t_s}/set-lauf", headers=H))
        ok(w.post(f"/api/material/artikel/{t_s}/teil-einsetzen", json={"item_id": sk1, "bestaetigt": True}), 201)
        assert lage(app, t_s)[sk1][2:] == ("gesperrt", "set", 1)

        # Freies Set (beim Anlegen): Ein Durchgang des alten Zweigs nimmt den Artikel heraus, die Fälligkeit folgt dem
        # Ordner des neuen Sets.
        halle = ordner_neu(w, t.a, "Halle Musterstadt")
        alt_h = neuer_artikel(w, hms, halle, serial_no="HALLE-K1")["id"]
        rid_h = ok(w.post("/api/material/durchgaenge", json={"folder_id": halle, "titel": "Testdurchgang Halle"}), 201)[
            "durchgang"]["id"]
        assert zeile(app, alt_h)["next_due_on"] > grenze
        r = anlegen(w, t, fach, "SET-FREI-1", hms=(alt_h, "neu:SET-FREI-1-K2"))
        assert r.status_code == 201, r.get_json()
        s2 = r.json["artikel"]["id"]
        assert lage(app, s2)[alt_h] == (fach, None, "frei", None, 0)
        assert zeile(app, alt_h)["next_due_on"] <= grenze
        assert "nicht mehr im Bereich" in zeilen(app, "SELECT excluded_reason FROM mat_round_item WHERE round_id = ? "
                                                      "AND item_id = ?", (rid_h, alt_h))[0]["excluded_reason"]
        assert stimmig(app)
    print("Teil einsetzen mit vorhandenem Artikel bestanden.")


# --- 3. Prüfumfang eines nie geprüften Sets (Probe P-B) ------------------------------------------------------------------

def test_umfang_nie_geprueft():
    """P-B: Ein einzeln geprüfter Altartikel kommt als vorhandenes Teil in ein neues Set; ein Prüfer sperrt ein anderes
    Teil, bevor das Set je geprüft wurde. Der erste Lauf prüft trotzdem alle Teile – auch den Altartikel mit gültiger
    Prüfung; ohne seine Prüfung im Lauf lässt sich der Set-Artikel nicht festschreiben."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        f = t.f["id"]
        pruefen(p, f)
        r = anlegen(w, t, t.lager_a, "SET-PB", hms=(f, "neu:SET-PB-K2"))
        assert r.status_code == 201, r.get_json()
        s = r.json["artikel"]["id"]
        k2, r1 = kennung_von(app, "SET-PB-K2"), kennung_von(app, "SET-PB-R")
        ok(p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "sturz"}))
        assert zeile(app, s)["set_lock_origin"] == "teil" and zeile(app, f)["set_pruefen"] == 0
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        assert {x["id"]: x["zu_pruefen"] for x in a["teile"]} == {f: True, k2: True, r1: True}, a["teile"]
        lf = lauf_auf(p, s)
        assert all(u["zu_pruefen"] for u in lf["umfang"]) and lf["fortschritt"]["zu_pruefen"] == 3, lf
        pruefen(p, k2)
        pruefen(p, r1)
        e = ok(starten(p, s), 201)["pruefung"]
        r = p.post(f"/api/material/pruefungen/{e['id']}/festschreiben", json={"ergebnis": "einsatzbereit"})
        assert r.status_code == 409 and zeile(app, f)["inventory_no"] in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        pruefen(p, f)
        pr = pruefen(p, s)
        assert pr["set_protokoll"]["gesamt"] == "einsatzbereit", pr["set_protokoll"]
        assert zeile(app, s)["lock_state"] == "frei"
    print("Prüfumfang eines nie geprüften Sets bestanden.")


# --- 4. Set löschen und Set auflösen -------------------------------------------------------------------------------------

def test_loeschen_und_aufloesen():
    """P-A: „Set löschen“ mit einem eingesetzten vorhandenen Artikel → 409 mit Verweis auf „Set auflösen“, der Artikel
    bleibt. „Set auflösen“: nur frei; Entwurf am Set, Meldung, Durchgangszeile, Antrag, Lauf mit Prüfung, offener Entwurf
    oder Prüfung seit dem Einsetzen an einem Teil → 409 mit Grund; ein offener Lauf ohne Prüfung endet. Wirkung: Teile
    frei im Ordner mit ihrer Zuordnung, Journal „aus_set_geloest“, der Set-Artikel weg mit „geloescht“ zuletzt – eine
    wiedervergebene Kennung zeigt den alten Verlauf nicht."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        hms = t.ids["hms"]
        nummer = iter(range(1, 100))

        def neues(ordner=None, vorhanden=True):
            n = next(nummer)
            alt_k = neuer_artikel(w, hms, ordner or t.lager_a, serial_no=f"AUF-{n}-ALT")["id"]
            r = anlegen(w, t, ordner or t.lager_a, f"AUF-{n}", hms=(alt_k if vorhanden else f"neu:AUF-{n}-K1",
                                                                     f"neu:AUF-{n}-K2"))
            assert r.status_code == 201, r.get_json()
            s = r.json["artikel"]["id"]
            return s, [x["id"] for x in r.json["artikel"]["set"]["teile"]], alt_k

        def aufloesen(s, c=w):
            return c.post(f"/api/material/artikel/{s}/aufloesen", headers=H, json={})

        # P-A: Set löschen mit vorhandenem Teil.
        f = t.f["id"]
        pruefen(p, f)                                       # vor dem Einsetzen geprüft – zählt nicht gegen Auflösen
        r = anlegen(w, t, t.lager_a, "AUF-PA", hms=(f, "neu:AUF-PA-K2"))
        s = r.json["artikel"]["id"]
        r = w.delete(f"/api/material/artikel/{s}", headers=H)
        assert r.status_code == 409 and "„Set auflösen“ gibt die Teile frei" in r.json["error"] \
            and t.f["inventory_no"] in r.json["error"], r.get_json()
        assert zeile(app, f)["parent_item_id"] == s
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["darf_loeschen"] is False and a["set"]["vorhandene_teile"] == [t.f["inventory_no"]], a["set"]
        assert a["set"]["aufloesen_hindernis"] is None, a["set"]
        # Kontrolle: ein Set nur mit neuen Teilen löscht sich wie bisher (auch mit per „Teil einsetzen“ neuem Teil).
        s_neu, _, _ = neues(vorhanden=False)
        assert w.delete(f"/api/material/artikel/{s_neu}", headers=H).status_code == 200

        # Rechte: Prüfer und Leser 403, fremd 404 wie unbekannt.
        assert aufloesen(s, p).status_code == 403 and aufloesen(s, t.k["fuehrung"]).status_code == 403
        assert aufloesen(t.sb["id"]).status_code == 404 and aufloesen(999999).status_code == 404
        assert aufloesen(t.teile[0]).status_code == 409             # ein Teil ist kein Set

        # Nur ein freies Set.
        s_g, _, _ = neues()
        ok(p.post(f"/api/material/artikel/{s_g}/sperren", json={"grund": "sturz"}))
        r = aufloesen(s_g)
        assert r.status_code == 409 and "nur ein freies Set" in r.json["error"], r.get_json()
        assert ok(w.get(f"/api/material/artikel/{s_g}"))["artikel"]["set"]["aufloesen_hindernis"] == r.json["error"]
        # Entwurf am Set (in einer Set-Prüfung).
        s_e, _, _ = neues()
        lauf_auf(p, s_e)
        ok(starten(p, s_e), 201)
        r = aufloesen(s_e)
        assert r.status_code == 409 and "Prüfung (auch eine begonnene)" in r.json["error"], r.get_json()
        # Meldung am Set (direkt geschrieben – über die Oberfläche sperrt sie das Set).
        s_m, _, _ = neues()
        sql(app, "INSERT INTO mat_defect_report (item_id, description, reporter_name, lock_before, created_at) "
                 "VALUES (?, 'Testmangel', 'Test', 'frei', ?)", (s_m, _heute().isoformat() + "T00:00:00+00:00"))
        r = aufloesen(s_m)
        assert r.status_code == 409 and "Mangel gemeldet" in r.json["error"], r.get_json()
        # Durchgangszeile.
        fach_dg = ordner_neu(w, t.lager_a, "Fach Durchgang")
        s_d, _, _ = neues(fach_dg)
        ok(w.post("/api/material/durchgaenge", json={"folder_id": fach_dg, "titel": "Testdurchgang Auflösen"}), 201)
        r = aufloesen(s_d)
        assert r.status_code == 409 and "Prüfdurchgang" in r.json["error"], r.get_json()
        # Antrag (direkt geschrieben – ohne Prüfung gibt es keinen).
        s_a, _, _ = neues()
        sql(app, "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by_name, created_at) "
                 "VALUES (?, 'serial_no', 'AUF-ALT', 'AUF-NEU', 'Testgrund', 'Test', ?)",
            (s_a, _heute().isoformat() + "T00:00:00+00:00"))
        r = aufloesen(s_a)
        assert r.status_code == 409 and "Änderungsantrag" in r.json["error"], r.get_json()
        # Lauf mit Prüfung (eines Teils, abgebrochen).
        s_l, teile_l, _ = neues()
        lauf_auf(p, s_l)
        pruefen(p, teile_l[-1])
        ok(w.delete(f"/api/material/artikel/{s_l}/set-lauf", headers=H))
        r = aufloesen(s_l)
        assert r.status_code == 409 and "Set-Prüfung mit Prüfungen" in r.json["error"], r.get_json()
        # Offener Entwurf an einem Teil; Prüfung eines Teils seit dem Einsetzen.
        s_t, teile_t, alt_t = neues()
        e = ok(starten(p, alt_t), 201)["pruefung"]
        r = aufloesen(s_t)
        assert r.status_code == 409 and "In Prüfung bei" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        pruefen(p, alt_t)
        r = aufloesen(s_t)
        assert r.status_code == 409 and "als Teil dieses Sets geprüft" in r.json["error"], r.get_json()
        # „Set löschen“ verweist dann nicht auf „Set auflösen“, sondern nennt, warum auch das nicht geht.
        r = w.delete(f"/api/material/artikel/{s_t}", headers=H)
        assert r.status_code == 409 and "Auflösen geht auch nicht" in r.json["error"] \
            and "als Teil dieses Sets geprüft" in r.json["error"] and "gibt die Teile frei" not in r.json["error"], r.get_json()
        assert stimmig(app)

        # Erfolg: das Set aus P-A, einer Person zugeordnet, mit offenem Lauf ohne Prüfung.
        _, person_id = neues_konto(app, "psa_auf@example.org", name="PSA Auflösen", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
        lf = lauf_auf(p, s)
        teile = sorted(x["id"] for x in ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]["teile"])
        ab = letzte_id(app)
        r = ok(aufloesen(s))
        assert sorted(x["id"] for x in r["teile"]) == teile, r
        assert not zeilen(app, "SELECT 1 FROM mat_item WHERE id = ?", (s,))
        assert not zeilen(app, "SELECT 1 FROM mat_set_lauf WHERE id = ?", (lf["id"],))
        assert not zeilen(app, "SELECT 1 FROM mat_item_set_slot WHERE set_item_id = ?", (s,))
        for x in teile:
            z = zeile(app, x)
            assert (z["parent_item_id"], z["folder_id"], z["lock_state"], z["assigned_user_id"], z["set_pruefen"]) == (
                None, t.lager_a, "frei", person_id, 0), z
            assert aktionen(app, x, ab) == ["aus_set_geloest"]
        j = eintraege(app, s, ab)
        assert [x["action"] for x in j] == ["set_lauf_abgebrochen", "geloescht"], j
        assert '"grund": "Set aufgelöst"' in j[-1]["after_json"]
        # Ein ungeprüftes neues Teil lässt sich danach einzeln löschen; der geprüfte Altartikel bleibt.
        neu_teil = kennung_von(app, "AUF-PA-K2")
        assert w.delete(f"/api/material/artikel/{neu_teil}", headers=H).status_code == 200
        assert w.delete(f"/api/material/artikel/{f}", headers=H).status_code == 409
        # Die Kennung des Sets wird wiedervergeben – der neue Artikel zeigt nur seinen eigenen Verlauf (S15).
        frisch = None
        for n in range(200):
            x = neuer_artikel(w, hms, t.lager_a, serial_no=f"FRISCH-{n}")
            if x["id"] == s:
                frisch = x
                break
            if x["id"] > s:
                break
        if frisch is not None:
            journal = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["journal"]
            assert [e["action"] for e in journal] == ["angelegt"], journal
        assert stimmig(app)
    print("Set löschen und Set auflösen bestanden.")


# --- 5. „Bestandteil ersetzt“ ----------------------------------------------------------------------------------------------

def test_bestandteil_ersetzt():
    """Eingaben (Position dieses Sets, nicht einzeln geführt – sonst 404 wie unbekannt; Datum, Bemerkung; Bestätigung
    bei „nicht belegt“; „nein“ 409), offener Entwurf am Set-Artikel → 409 (P6), Wirkung: Sperre wie beim Tausch mit
    set_grund „bestandteil“, Marke set_pruefen an der Set-Zeile nach der Kaskade, Grund und Sperrgründe nennen es, der
    Jahresbericht zählt die Sperre einmal (am schon gesperrten Set nicht noch einmal); Freigabe und Aussondern setzen die
    Marke zurück; eine eigene Sperre des Set-Artikels bleibt (P5). Rechte und Trennung."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, (k1, k2, r1) = t.s["id"], t.teile
        eingangsgeprueft(t)
        tasche = next(b for b in t.s["set"]["bestandteile"] if not b["einzeln"])
        assert tasche["austausch"] == "nicht_belegt"
        einzeln = next(b["id"] for b in t.s["set"]["bestandteile"] if b["einzeln"])
        fremd = next(b["id"] for b in t.sb["set"]["bestandteile"] if not b["einzeln"])
        url = f"/api/material/artikel/{s}/bestandteil-ersetzt"

        def ersetzt(c=w, **d):
            return c.post(url, headers=H, json=d)
        unbekannt = ersetzt(slot_id=999999, bestaetigt=True)
        assert unbekannt.status_code == 404
        for slot in (einzeln, fremd, str(fremd), float(fremd)):
            r = ersetzt(slot_id=slot, bestaetigt=True)
            assert (r.status_code, r.get_json()) == (404, unbekannt.get_json()), (slot, r.get_json())
        for d, teil in (({"datum": (_heute() + timedelta(days=1)).isoformat()}, "Zukunft"), ({"datum": "gestern"}, "Datum"),
                        ({"bemerkung": "x" * 201}, "zu lang"), ({"bemerkung": 7}, "Text")):
            r = ersetzt(slot_id=tasche["id"], bestaetigt=True, **d)
            assert r.status_code == 400 and teil in r.json["error"], (d, r.get_json())
        r = ersetzt(slot_id=tasche["id"])
        assert r.status_code == 400 and "Herstellerunterlagen" in r.json["error"], r.get_json()
        # Untergrenze (Nachbesserung, Sicherheit Hinweis): nicht vor der Erfassung des Sets.
        from datetime import date
        vor = (date.fromisoformat(zeile(app, s)["created_at"][:10]) - timedelta(days=1)).isoformat()
        for d in (vor, "1900-01-01"):
            r = ersetzt(slot_id=tasche["id"], bestaetigt=True, datum=d)
            assert r.status_code == 400 and "vor der Erfassung des Sets" in r.json["error"], (d, r.get_json())
        # Rechte: Prüfer und Leser 403; ein Set aus B 404.
        assert ersetzt(p, slot_id=tasche["id"], bestaetigt=True).status_code == 403
        assert ersetzt(t.k["fuehrung"], slot_id=tasche["id"], bestaetigt=True).status_code == 403
        assert w.post(f"/api/material/artikel/{t.sb['id']}/bestandteil-ersetzt", headers=H,
                      json={"slot_id": fremd, "bestaetigt": True}).status_code == 404
        # P6: offener Entwurf am Set-Artikel → 409; nach dem Verwerfen geht es.
        lauf_auf(p, s)
        e = ok(starten(p, s), 201)["pruefung"]
        r = ersetzt(slot_id=tasche["id"], bestaetigt=True)
        assert r.status_code == 409 and "Erst festschreiben oder verwerfen" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        ok(w.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        # „nein“ → 409 (die Kopie ist fest – direkt in der Kopie gesetzt), dann zurück auf „nicht belegt“.
        sql(app, "DROP TRIGGER mat_slot_aendern")
        sql(app, "UPDATE mat_item_set_slot SET austausch = 'nein' WHERE id = ?", (tasche["id"],))
        r = ersetzt(slot_id=tasche["id"], bestaetigt=True)
        assert r.status_code == 409 and "nicht austauschbar" in r.json["error"], r.get_json()
        sql(app, "UPDATE mat_item_set_slot SET austausch = 'nicht_belegt' WHERE id = ?", (tasche["id"],))

        # Wirkung am freien Set.
        vorher = sperren_bericht(w, t.a)
        ab = letzte_id(app)
        r = ok(ersetzt(slot_id=tasche["id"], bestaetigt=True, datum=_heute().isoformat(),
                       bemerkung="Charge 0000 (Platzhalter)"))
        assert lage(app, s)[s] == (t.sys_a["gesperrt"], t.lager_a, "gesperrt", "set", 1), lage(app, s)
        assert all(lage(app, s)[x][2:] == ("gesperrt", "set", 0) for x in (k1, k2, r1)), lage(app, s)
        inv = t.s["inventory_no"]
        assert zeile(app, s)["lock_reason"] == "Bestandteil ersetzt – Set prüfen"
        assert zeile(app, k1)["lock_reason"] == f"mit dem Set {inv} gesperrt (Bestandteil ersetzt – Set prüfen)"
        sg = r["artikel"]["set"]["sperrgruende"]
        assert [g["art"] for g in sg] == ["bestandteil", "set_pruefung"], sg
        j = eintraege(app, s, ab)
        assert [x["action"] for x in j] == ["bestandteil_ersetzt", "gesperrt"], j
        assert '"set_grund": "bestandteil"' in j[1]["after_json"]
        # B1: die Position der Stückliste (1, 2, …), nicht die Kennung der Kopie. A2: Journal „gesperrt“ und
        # Jahresbericht nennen den Anlass, nicht „Set-Prüfung ausstehend“.
        assert f'"position": {tasche["position"]}' in j[0]["after_json"] and '"slot"' not in j[0]["after_json"], j[0]
        assert '"lock_reason": "Bestandteil ersetzt – Set prüfen"' in j[1]["after_json"], j[1]
        mit = [x["after_json"] for x in eintraege(app, k1, ab) if x["action"] == "set_gesperrt"]
        assert mit and all("(Bestandteil ersetzt – Set prüfen)" in x for x in mit), mit
        assert '"bestaetigt": "laut Herstellerunterlagen zulässig"' in j[0]["after_json"] and "Charge 0000" in j[0]["after_json"]
        b = sperren_bericht(w, t.a)
        assert b["gesamt"] == vorher["gesamt"] + 1, (vorher, b)
        assert {a["art"]: a["n"] for a in b["arten"]}["set"] == {a["art"]: a["n"] for a in vorher["arten"]}["set"] + 1
        assert "Bestandteil ersetzt" in {a["art"]: a["text"] for a in b["arten"]}["set"]
        assert [x["grund"] for x in b["liste"] if x["inventarnummer"] == inv] == ["Bestandteil ersetzt – Set prüfen"], b
        # Doppelklick: dieselbe Position, dasselbe Datum, dieselbe Bemerkung gleich noch einmal → 409, kein Eintrag.
        ab2 = letzte_id(app)
        r = ersetzt(slot_id=tasche["id"], bestaetigt=True, datum=_heute().isoformat(), bemerkung="Charge 0000 (Platzhalter)")
        assert r.status_code == 409 and "schon eingetragen" in r.json["error"], r.get_json()
        assert letzte_id(app) == ab2
        # Am schon gesperrten Set: noch ein Eintrag (andere Bemerkung), keine neue Sperre.
        ok(ersetzt(slot_id=tasche["id"], bestaetigt=True, bemerkung="zweiter Ersatz (Platzhalter)"))
        assert sperren_bericht(w, t.a)["gesamt"] == b["gesamt"]
        # Set prüfen: der Set-Artikel mit seinen Bestandteil-Zeilen; einsatzbereit gibt frei, die Marke ist weg.
        lf = lauf_auf(p, s)
        assert not any(u["zu_pruefen"] for u in lf["umfang"]), lf["umfang"]
        pr = pruefen(p, s)
        assert pr["set_protokoll"]["gesamt"] == "einsatzbereit", pr["set_protokoll"]
        assert all(v[2] == "frei" and v[4] == 0 for v in lage(app, s).values()), lage(app, s)

        # P5: Eine eigene Sperre des Set-Artikels bleibt; Aussondern setzt die Marke zurück.
        ok(p.post(f"/api/material/artikel/{s}/sperren", json={"grund": "sturz"}))
        grund = zeile(app, s)["lock_reason"]
        ok(ersetzt(slot_id=tasche["id"], bestaetigt=True))
        z = zeile(app, s)
        assert (z["lock_cause"], z["lock_reason"], z["set_pruefen"]) == ("eigen", grund, 1), z
        sg = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]["sperrgruende"]
        assert [g["art"] for g in sg] == ["eigen", "bestandteil", "set_pruefung"], sg
        ok(w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"}))
        assert all(v[2] == "ausgesondert" and v[4] == 0 for v in lage(app, s).values()), lage(app, s)
        r = ersetzt(slot_id=tasche["id"], bestaetigt=True)
        assert r.status_code == 409 and "ausgesondert" in r.json["error"], r.get_json()
        # Die Kaskade nimmt den Set-Artikel nie als „neu“ (T4).
        with app.test_request_context():
            from app.material.services import sets
            try:
                sets.sperren(t.sb["id"], set_grund="tausch", neu=[t.sb["id"]])
                raise AssertionError("Set-Kennung in neu angenommen")
            except ValueError:
                pass
        assert stimmig(app)
    print("Bestandteil ersetzt bestanden.")


# --- 6. Beschriftungen (statisch) ----------------------------------------------------------------------------------------

def test_beschriftungen():
    """Die neuen Journal-Aktionen, Felder und der Anlass „bestandteil“ stehen gleichlautend in beschriftung.py und in den
    Tabellen von material.js (den vollständigen Abgleich von FELD und AKTION macht test_material_l5); der Jahresbericht
    nennt „Bestandteil ersetzt“ bei der Sperrart „set“."""
    from app.material.services import bericht, beschriftung, sets
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "material", "static",
                           "material.js"), encoding="utf-8").read()
    for schluessel in ("eingesetzt", "aus_set_geloest", "bestandteil_ersetzt"):
        assert f'{schluessel}: "{beschriftung.AKTION[schluessel]}"' in js, schluessel
    for schluessel in ("vorhanden", "slot", "position", "bemerkung"):
        assert f'{schluessel}: "{beschriftung.FELD[schluessel]}"' in js, schluessel
    assert beschriftung.SET_WERTE["set_grund"]["bestandteil"] == sets.BESTANDTEIL_ERSETZT
    assert f'bestandteil: "{sets.BESTANDTEIL_ERSETZT}"' in js
    assert "bestandteil" in sets.SET_GRUENDE and "Bestandteil ersetzt" in dict(bericht.SPERRARTEN)["set"]
    print("Beschriftungen bestanden.")


if __name__ == "__main__":
    test_anlegen_mit_vorhandenen()
    test_einsetzen_vorhandener()
    test_umfang_nie_geprueft()
    test_loeschen_und_aufloesen()
    test_bestandteil_ersetzt()
    test_beschriftungen()
