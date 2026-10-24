"""Sets, Nachbesserung nach den drei Prüfungen (Phase 4 · Lieferung 2):  python tests/test_material_sets_nachbesserung.py
oder  pytest

Der Sperrgrund folgt dem Set (Ablauf M1: kein Text eines entnommenen Teils im Aussonderungsprotokoll, in „Meine PSA“
und an den Teilen), die Set-Prüfung folgt dem offenen Durchgang (M2), wer eine Set-Prüfung abbrechen darf (Sicherheit 1),
Durchgang löschen und abbrechen mit offener Set-Prüfung (2), Berichtigung nach „Teil entnehmen“ (3), Set aussondern
beendet die Set-Prüfung (4), Name des Eröffners beim Kontolöschen (5), Rückweg auf Code-Stand 20 (6), „Austausch laut
Hersteller: nein“ (Ablauf N3), Jahresbericht beim Aussondern des Sets (N2) und die Kommandozeile des Katalogimports.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, freigeben, katalog_grund, make_app, neues_konto,  # noqa: E402
                           umgebung, unterschreiben)
from test_material_import import ok  # noqa: E402
from test_material_sets import abgewiesen, roh, set_aufbau, set_katalog, stimmig  # noqa: E402
from test_material_sets_pruefung import _pdf, _pdf_text, eingangsgeprueft, lage, lauf_auf, pruefen, set_pruefen  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402


def nummer(app, iid):
    return zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (iid,))[0]["inventory_no"]


def grund(app, iid):
    return zeilen(app, "SELECT lock_reason FROM mat_item WHERE id = ?", (iid,))[0]["lock_reason"]


def zweiter_pruefer(t, mail="pruefer2@example.org", name="Prüfer Zwei", urkunde="1012-4712"):
    """Ein weiterer Prüfer mit Lese- und Prüffreigabe in Gliederung A und hinterlegter Unterschrift."""
    c, uid = neues_konto(t.app, mail, name=name, mat_pruefer=True, urkundennummer=urkunde)
    freigeben(t.adm, t.a, uid, "lesen")
    freigeben(t.adm, t.a, uid, "pruefen")
    unterschreiben(c)
    return c, uid


# --- Ablauf M1: der Sperrgrund folgt dem Set ----------------------------------------------------------------------------

def test_sperrgrund_folgt_dem_set():
    """Die Probe aus Ablauf M1: Prüfer sperrt K1 (Sturz), der Materialwart entnimmt K1, der Prüfer sperrt K2
    (Beschädigung), der Materialwart sondert das Set aus – das Aussonderungsprotokoll nennt den tatsächlichen Grund (K2),
    nicht K1. Unterwegs tragen Set-Artikel, mitgesperrte Teile und „Meine PSA“ nie den Text von K1. Dazu: Freiprüfung des
    auslösenden Teils, Teil löschen und Ergebnis „aussondern“ an einem Teil ziehen den Grund ebenso nach."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        eingangsgeprueft(t)
        person, person_id = neues_konto(app, "psa_m1@example.org", name="PSA Mone", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
        nr1, nr2 = nummer(app, k1), nummer(app, k2)
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz", "text": "Platzhalter-Sturz"}))
        assert nr1 in grund(app, s) and nr1 in grund(app, k2), (grund(app, s), grund(app, k2))
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1}))
        for x in (s, k2, r1):
            assert nr1 not in grund(app, x) and "Platzhalter-Sturz" not in grund(app, x), (x, grund(app, x))
        assert grund(app, s) == "unvollständig: „Verbindungselement“ fehlt", grund(app, s)
        assert grund(app, k2) == f"mit dem Set {t.s['inventory_no']} gesperrt (unvollständig: „Verbindungselement“ fehlt)"
        # Dieselbe Zeile in der Antwort der Artikelseite, der Teil-Seite und in „Meine PSA“.
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert nr1 not in a["lock_reason"] and all(nr1 not in x["lock_reason"] for x in a["set"]["teile"]), a
        assert nr1 not in ok(w.get(f"/api/material/artikel/{k2}"))["artikel"]["lock_reason"]
        karte = ok(person.get("/api/material/meine-psa"))["artikel"][0]
        assert karte["lock_reason"] == grund(app, s) and nr1 not in karte["lock_reason"], karte["lock_reason"]
        ok(p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "beschaedigung", "text": "Platzhalter-Schaden"}))
        assert grund(app, s) == f"wegen Teil {nr2}: Beschädigung: Platzhalter-Schaden; unvollständig: „Verbindungselement“ " \
            "fehlt", grund(app, s)
        assert nr1 not in grund(app, r1) and nr2 in grund(app, r1)
        sb = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        assert all(g["text"].endswith(".") for g in sb["sperrgruende"]), sb["sperrgruende"]
        ok(w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"}))
        aid = zeilen(app, "SELECT id FROM mat_inspection WHERE item_id = ? AND kind = 'aussonderung'", (s,))[0]["id"]
        text = _pdf_text(_pdf(app, aid))
        assert "Platzhalter-Schaden" in text and nr2 in text, text
        assert "Platzhalter-Sturz" not in text and nr1 not in text, text
        assert stimmig(app)

    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        nr1, nr2 = nummer(app, k1), nummer(app, k2)
        # Teil löschen (ungeprüft, nach einer Prüfer-Sperre): der Grund des gelöschten Teils verschwindet.
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz", "text": "Platzhalter-Sturz"}))
        assert w.delete(f"/api/material/artikel/{k1}", headers=H).status_code == 200
        assert grund(app, s) == "unvollständig: „Verbindungselement“ fehlt" and nr1 not in grund(app, k2)
        # Freiprüfung eines Teils außerhalb einer Set-Prüfung: sein eigener Grund verschwindet, es bleibt zu prüfen.
        ok(p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "beschaedigung", "text": "Platzhalter-Schaden"}))
        assert "Platzhalter-Schaden" in grund(app, s)
        pruefen(p, k2)
        assert "Platzhalter-Schaden" not in grund(app, s) and f"Teil {nr2} in der Set-Prüfung zu prüfen" in grund(app, s)
        assert lage(app, s)[k2][3:] == ("set", 1)
        assert grund(app, k2).startswith(f"mit dem Set {t.s['inventory_no']} gesperrt (")
        # Ergebnis „aussondern“ an einem Teil: entnommen und ausgesondert – sein Text bleibt nicht am Set.
        pruefen(p, r1, "aussondern")
        assert nummer(app, r1) not in grund(app, s) and "„Testwerk Rolle Gamma“ fehlt" in grund(app, s), grund(app, s)
        assert stimmig(app)
    print("Sperrgrund folgt dem Set bestanden.")


# --- Ablauf M2, N1: Set-Prüfung und Durchgang, Prüfumfang -----------------------------------------------------------------

def test_set_pruefung_folgt_dem_durchgang():
    """„Set prüfen“ an der Set-Seite (ohne durchgang_id) bei offenem Durchgang: Der Lauf übernimmt den Durchgang wie
    pruefung.starten; „Set prüfen“ aus dem Durchgang liefert denselben Lauf; das Sammelprotokoll hat die Zeile
    „Set-Prüfung“ mit dem Gesamtergebnis (hier gesperrt, obwohl der Set-Artikel selbst „einsatzbereit“ ist)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        d = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang M2"}), 201)
        rid = d["durchgang"]["id"]
        lf = lauf_auf(p, s)
        assert lf["round_id"] == rid and lf["durchgang"]["id"] == rid and lf["eigen"] is True, lf
        assert p.post(f"/api/material/artikel/{s}/set-lauf", json={"durchgang_id": rid}).status_code == 200
        pruefen(p, k1)
        pruefen(p, k2, "instandsetzen")
        pruefen(p, r1)
        pr = pruefen(p, s)
        assert pr["ergebnis"] == "einsatzbereit" and pr["set_protokoll"]["gesamt"] == "gesperrt", pr["set_protokoll"]
        pruefen(p, t.f["id"])
        pruefen(p, t.art_a["id"])
        ok(w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}))
        pfad = zeilen(app, "SELECT pdf_path FROM mat_round WHERE id = ?", (rid,))[0]["pdf_path"]
        text = _pdf_text(os.path.join(app.config["DATA_DIR"], pfad))
        assert "Set-Prüfung: nicht einsatzbereit – Set gesperrt" in text, text
        # Frühere Set-Prüfungen tragen Gesamtergebnis und Protokoll (Browser V5).
        x = ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["laeufe"][0]
        assert x["gesamtergebnis"] == "gesperrt" and x["protokoll_id"] == pr["protokoll"]["id"], x
    print("Set-Prüfung folgt dem Durchgang bestanden.")


# --- Sicherheit 1–4 -----------------------------------------------------------------------------------------------------

def test_abbrechen_und_durchgang():
    """Abbrechen darf, wer die Set-Prüfung eröffnet hat, oder der Materialwart – ein anderer Prüfer bekommt 403.
    Durchgang mit offener Set-Prüfung: nicht löschbar (409 mit Klartext, loeschbar false); abbrechen löst die Set-Prüfung
    vom Durchgang wie einen offenen Entwurf; ohne Set-Prüfung lässt er sich löschen."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, _ = t.s["id"], *t.teile
        p2, _ = zweiter_pruefer(t)
        lf = lauf_auf(p, s)
        pruefen(p, k1)
        assert ok(p2.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]["eigen"] is False
        r = p2.delete(f"/api/material/artikel/{s}/set-lauf", headers=H)
        assert r.status_code == 403 and "begonnen hat" in r.json["error"], r.get_json()
        assert zeilen(app, "SELECT state FROM mat_set_lauf WHERE id = ?", (lf["id"],))[0]["state"] == "offen"
        assert ok(w.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))["bleibt"] is True
        lauf_auf(p2, s)
        assert ok(p2.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))["bleibt"] is False

        # Durchgang mit offener Set-Prüfung (noch nichts geprüft).
        rid = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang S2"}),
                 201)["durchgang"]["id"]
        lf = lauf_auf(p, s, durchgang_id=rid)
        assert ok(w.get(f"/api/material/durchgaenge/{rid}"))["durchgang"]["loeschbar"] is False
        r = w.delete(f"/api/material/durchgaenge/{rid}", headers=H)
        assert r.status_code == 409 and "Set-Prüfung" in r.json["error"] and t.s["inventory_no"] in r.json["error"], \
            r.get_json()
        ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        assert ok(w.get(f"/api/material/durchgaenge/{rid}"))["durchgang"]["loeschbar"] is True
        assert w.delete(f"/api/material/durchgaenge/{rid}", headers=H).status_code == 200
        # Abbrechen: Die Set-Prüfung läuft ohne Durchgang weiter; ohne Prüfung verschwindet der Durchgang.
        rid = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang S2b"}),
                 201)["durchgang"]["id"]
        lf = lauf_auf(p, s, durchgang_id=rid)
        r = ok(w.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={}))
        assert r["durchgang"] is None, r
        assert zeilen(app, "SELECT state, round_id FROM mat_set_lauf WHERE id = ?", (lf["id"],)) == [
            {"state": "offen", "round_id": None}]
        # Mit einer Prüfung im Durchgang bleibt er „abgebrochen“, die Set-Prüfung läuft weiter.
        rid = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang S2c"}),
                 201)["durchgang"]["id"]
        ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        lf = lauf_auf(p, s, durchgang_id=rid)
        pruefen(p, k2)
        assert ok(w.post(f"/api/material/durchgaenge/{rid}/abbrechen", json={}))["durchgang"] is not None
        assert zeilen(app, "SELECT aborted FROM mat_round WHERE id = ?", (rid,))[0]["aborted"] == 1
        assert zeilen(app, "SELECT state, round_id FROM mat_set_lauf WHERE id = ?", (lf["id"],)) == [
            {"state": "offen", "round_id": None}]
        assert [x["action"] for x in zeilen(app, "SELECT action FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                                                 "ORDER BY id DESC LIMIT 1", (s,))] == ["set_lauf_geaendert"]
        assert stimmig(app)
    print("Abbrechen und Durchgang mit Set-Prüfung bestanden.")


def test_berichtigung_und_aussondern_mit_lauf():
    """Berichtigung einer Teilprüfung nach „Teil entnehmen“ bei offener Set-Prüfung: als Einzelprüfung (kein 409).
    „Set aussondern“ durch den Materialwart beendet eine offene Set-Prüfung (Journal mit Grund)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, _ = t.s["id"], *t.teile
        eingangsgeprueft(t)
        lf = lauf_auf(p, s)
        pk1 = pruefen(p, k1)
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1}))
        b = ok(p.post(f"/api/material/pruefungen/{pk1['id']}/berichtigen", json={"grund": "Testberichtigung"}), 201)
        assert b["pruefung"]["set_lauf"] is None, b["pruefung"]["set_lauf"]
        assert festschreiben(p, b["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        # Set aussondern bei offener Set-Prüfung (mit einer Teilprüfung darin): der Lauf endet „abgebrochen“.
        ok(p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "sturz"}))
        ok(w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"}))
        assert zeilen(app, "SELECT state FROM mat_set_lauf WHERE id = ?", (lf["id"],))[0]["state"] == "abgebrochen"
        letzte = zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                             "AND action = 'set_lauf_abgebrochen' ORDER BY id DESC LIMIT 1", (s,))[0]["after_json"]
        assert json.loads(letzte)["grund"] == "Set ausgesondert", letzte
        assert ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]["lauf"] is None
    print("Berichtigung nach Entnehmen und Aussondern mit Set-Prüfung bestanden.")


def test_konto_loeschen_und_rueckweg():
    """Kontolöschen: An einer offenen Set-Prüfung wird der Eröffner „(gelöschtes Konto)“, an einer abgeschlossenen
    bleibt sein Name; den Namen ändert sonst nichts (Trigger). Rückweg auf Code-Stand 20: Ein Teil, das schon gesperrt ist,
    ohne Ursache, wird bei der nächsten Set-Sperre „eigen“ mit seinem Grund und ist im Freigabe-Lauf zu prüfen."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        p2, uid = zweiter_pruefer(t)
        set_pruefen(p2, s, t.teile)
        alt = zeilen(app, "SELECT id FROM mat_set_lauf WHERE set_item_id = ? AND state = 'abgeschlossen'", (s,))[0]["id"]
        neu = lauf_auf(p2, s)["id"]
        assert t.adm.delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        namen = {r["id"]: (r["opened_by"], r["opened_by_name"]) for r in zeilen(
            app, "SELECT id, opened_by, opened_by_name FROM mat_set_lauf WHERE id IN (?, ?)", (alt, neu))}
        assert namen == {alt: (None, "Prüfer Zwei"), neu: (None, "(gelöschtes Konto)")}, namen
        conn = roh(app)
        try:
            for lid, name in ((alt, "(gelöschtes Konto)"), (neu, "Jemand")):
                abgewiesen(conn, "UPDATE mat_set_lauf SET opened_by_name = ? WHERE id = ?", (name, lid), "unveränderlich")
            abgewiesen(conn, "UPDATE mat_set_lauf SET round_id = ? WHERE id = ?", (t.durchgang_b, neu), "unveränderlich")
        finally:
            conn.close()
        assert ok(w.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))["bleibt"] is False

        # Rückweg: K2 wie von Code-Stand 20 einzeln gesperrt (ohne Ursache, Set frei) – die nächste Set-Sperre behält es.
        sql(app, "UPDATE mat_item SET lock_state = 'gesperrt', lock_reason = 'Platzhalter-Rückweg', lock_cause = NULL "
                 "WHERE id = ?", (k2,))
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        z = {r["id"]: r for r in zeilen(app, "SELECT * FROM mat_item WHERE id IN (?, ?)", (k1, k2))}
        assert (z[k2]["lock_cause"], z[k2]["lock_reason"], z[k2]["set_pruefen"]) == ("eigen", "Platzhalter-Rückweg", 1), \
            z[k2]
        assert (z[k1]["lock_cause"], z[k1]["set_pruefen"]) == ("eigen", 1)
        lf = lauf_auf(p, s)
        assert {u["teil"]["id"]: u["zu_pruefen"] for u in lf["umfang"]} == {k1: True, k2: True, r1: False}, lf["umfang"]
        assert any("Platzhalter-Rückweg" in g for g in lf["freigabe_gruende"]), lf["freigabe_gruende"]
        assert stimmig(app)
    print("Kontolöschen und Rückweg bestanden.")


# --- Ablauf N3, N2: Austausch „nein“, Jahresbericht --------------------------------------------------------------------

def test_nicht_austauschbar_und_bericht():
    """„Austausch laut Hersteller: nein“: Ergebnis „aussondern“ an so einem Teil entnimmt es nicht – es bleibt gesperrt im
    Set (eigener Grund mit „das Set aussondern“), der Materialwart sondert danach das Set aus (Teil vorbelegt „mit
    aussondern“). Jahresbericht (Entscheidung zu L2 Nr. 39, 23.10.2026): Teile, die beim Aussondern eines Sets entnommen
    und gesperrt weitergeführt werden, zählen mit ihrer eigenen Sperre (Art „set_entnommen“) – aus einem freien Set wie
    aus einem gesperrten, in dem sie nur mitgesperrt waren; das Set selbst ist bei den Aussonderungen eine Zeile, die
    mit ihm ausgesonderten Teile zählen darin."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        sql(app, "DROP TRIGGER mat_slot_aendern")
        sql(app, "UPDATE mat_item_set_slot SET austausch = 'nein' WHERE set_item_id = ? AND einzeln = 1 AND "
                 "bezeichnung = 'Verbindungselement'", (s,))
        eingangsgeprueft(t)
        pruefen(p, k1, "aussondern")
        z = zeilen(app, "SELECT parent_item_id, lock_state, lock_cause, lock_reason FROM mat_item WHERE id = ?", (k1,))[0]
        assert (z["parent_item_id"], z["lock_state"], z["lock_cause"]) == (s, "gesperrt", "eigen"), z
        assert z["lock_reason"].endswith("laut Hersteller nicht austauschbar: das Set aussondern"), z
        assert not zeilen(app, "SELECT 1 FROM mat_inspection WHERE item_id = ? AND kind = 'aussonderung'", (k1,))
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["set"]["vollstaendig"] is True and a["status"] == "gesperrt"
        assert {x["id"]: x["verbleib_vorschlag"] for x in a["set"]["teile"]} == {k1: "aussondern", k2: "weiterfuehren",
                                                                                r1: "weiterfuehren"}
        jahr = _heute().year
        vorher = ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]
        ok(w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"}))
        z = {r["id"]: r for r in zeilen(app, "SELECT * FROM mat_item WHERE id IN (?, ?)", (s, k1))}
        assert (z[s]["lock_state"], z[k1]["lock_state"], z[k1]["parent_item_id"]) == ("ausgesondert", "ausgesondert", s)
        # Bericht: K2 und R1 waren nur mit dem Set gesperrt – jetzt je eine eigene Sperre; K1 zählt in der Zeile des Sets.
        b = ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]
        arten = {x["art"]: x["n"] for x in b["sperren"]["arten"]}
        vor = {x["art"]: x["n"] for x in vorher["sperren"]["arten"]}
        assert arten["set_entnommen"] - vor["set_entnommen"] == 2 and arten["set"] == vor["set"], (vorher, b)
        neu_ = [x for x in b["sperren"]["liste"] if x["art"] == "set_entnommen"]
        assert {x["inventarnummer"] for x in neu_} == {nummer(app, k2), nummer(app, r1)}, neu_
        assert all(x["art_text"] == "aus ausgesondertem Set entnommen" and x["grund"] == "aus ausgesondertem Set entnommen"
                   for x in neu_), neu_
        au = b["aussonderungen"]
        assert au["gesamt"] - vorher["aussonderungen"]["gesamt"] == 1 == b["bewegungen"]["aussonderungen"], au
        zeile = next(x for x in au["liste"] if x["inventarnummer"] == nummer(app, s))
        assert zeile["set_text"] == "Set, mit 1 Teil" and nummer(app, k1) not in {x["inventarnummer"] for x in au["liste"]}
        # Mit Haken „Prüfer nennen“: „Aussonderungen durch“ zählt das Set ebenso einmal.
        bh = ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}&pruefer=1"))["bericht"]
        assert sum(x["n"] for x in bh["pruefer"]["aussonderungen_durch"]) == au["gesamt"], bh["pruefer"]
        # Die CSV-Prüfungsliste führt weiter jedes Aussonderungsprotokoll (Set und K1).
        r = w.get(f"/material/export/{t.a}-pruefungen-{jahr}.csv")
        assert r.status_code == 200 and r.data.decode("utf-8-sig").count("Aussonderungsprotokoll") == 2, r.data[:300]
        # Das PDF nennt die neue Sperrart und den Zusatz am Set.
        r = w.get(f"/material/ordner/{t.a}/bericht-{jahr}.pdf")
        assert r.status_code == 200 and r.data.startswith(b"%PDF")
        pfad = os.path.join(tmp, "bericht.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _pdf_text(pfad)
        assert "aus ausgesondertem Set entnommen" in text and "Set, mit 1 Teil" in text, text[-2000:]

    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s = t.s["id"]
        eingangsgeprueft(t)
        jahr = _heute().year
        vorher = ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]["sperren"]
        lauf_auf(p, s)
        for x in t.teile:
            pruefen(p, x)
        pruefen(p, s, "aussondern")                      # Vorbelegung: alle Teile entnehmen und weiterführen
        bericht = ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]
        b = bericht["sperren"]
        arten = {x["art"]: x["n"] for x in b["arten"]}
        vor = {x["art"]: x["n"] for x in vorher["arten"]}
        assert arten["set_entnommen"] - vor["set_entnommen"] == 3 and arten["set"] == vor["set"], (vorher, b)
        assert arten["pruefung"] == vor["pruefung"], (vorher, b)
        # Alle Teile weitergeführt: Das Set ist eine Zeile ohne Teile („Set“), aus der Prüfung.
        au = bericht["aussonderungen"]
        assert [(x["inventarnummer"], x["set_text"], x["art"]) for x in au["liste"]] == [
            (t.s["inventory_no"], "Set", "pruefung")], au
    print("Austausch „nein“ und Jahresbericht bestanden.")


# --- Kommandozeile des Katalogimports -----------------------------------------------------------------------------------

def test_import_kommandozeile():
    """flask material import-catalog: die Zeile „Stücklisten“ (neu, geändert, unverändert); ein Set, an dem sich nur die
    Stückliste ändert, zählt bei den Produkten als geändert, nicht als unverändert."""
    with tempfile.TemporaryDirectory() as quelle, tempfile.TemporaryDirectory() as ziel:
        app, k = umgebung(quelle)
        ids = katalog_grund(k["adm"])
        set_katalog(k["katalog"], ids)
        with app.app_context():
            from app.material.services import katalog_export
            daten, _, _ = katalog_export.sammeln(mit_dateien=False)
        app2 = make_app(ziel)
        pfad = os.path.join(ziel, "katalog.json")

        def cli(d):
            with open(pfad, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False)
            r = app2.test_cli_runner().invoke(args=["material", "import-catalog", pfad])
            assert r.exit_code == 0, r.output
            return r.output
        aus = cli(daten)
        assert "Stücklisten neu 1, geaendert 0, unveraendert 0" in aus, aus
        aus = cli(daten)
        assert "Stücklisten neu 0, geaendert 0, unveraendert 1" in aus, aus
        geaendert = json.loads(json.dumps(daten))
        s = next(p for p in geaendert["produkte"] if p["modell"] == "Testset Alpha")
        s["bestandteile"][2]["bezeichnung"] = "Tasche (Platzhalter)"
        n = len(daten["produkte"])
        aus = cli(geaendert)
        assert "Stücklisten neu 0, geaendert 1, unveraendert 0" in aus, aus
        assert f"Produkte    neu 0, geaendert 1, unveraendert {n - 1}" in aus, aus
    print("Kommandozeile des Katalogimports bestanden.")


if __name__ == "__main__":
    test_sperrgrund_folgt_dem_set()
    test_set_pruefung_folgt_dem_durchgang()
    test_abbrechen_und_durchgang()
    test_berichtigung_und_aussondern_mit_lauf()
    test_konto_loeschen_und_rueckweg()
    test_nicht_austauschbar_und_bericht()
    test_import_kommandozeile()
