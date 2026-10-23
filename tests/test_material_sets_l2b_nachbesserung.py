"""Hersteller-Sets, Teil 2 – Nachbesserung nach den drei Prüfungen (Phase 4 · Lieferung 2b, 23.10.2026):
python tests/test_material_sets_l2b_nachbesserung.py  oder  pytest

Sicherheit H1 (genau der Ablauf der Probe p9/p9b: Teil aus einem gesperrten Set entnehmen, einzeln freiprüfen, als
vorhandenen Artikel in ein neues Set an eine Position „Austausch laut Hersteller: nein“ einsetzen, dort „aussondern“ in
der ersten Set-Prüfung), die Bereinigung beim Start und die Absicherung in setlauf.wirkung; Ablauf A1 (Sperrgrund am
eingesetzten vorhandenen Teil), A3 (Auswahl mit 250 ähnlichen Bemerkungen); Browser B2 (Spalte „Bisherige
Inventarnummer“ im Bestandsimport). „Bestandteil ersetzt“ (A2, B1, Untergrenze, Doppelklick) und der Löschtext stehen in
test_material_sets_vorhanden.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, festschreiben, starten  # noqa: E402
from test_material_import import csv_bytes, ok, probelauf  # noqa: E402
from test_material_sets import set_aufbau, stimmig  # noqa: E402
from test_material_sets_pruefung import eingangsgeprueft, lage, lauf_auf, pruefen  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402


def zeile(app, iid):
    return zeilen(app, "SELECT * FROM mat_item WHERE id = ?", (iid,))[0]


def set_nein(t):
    """Ein Set-Produkt „Testset Beta“: ein HMS Beta einzeln mit „Austausch laut Hersteller: nein“, dazu ein Beutel ohne
    eigenen Artikel. Liefert (Produkt, Position des HMS)."""
    kat = t.k["katalog"]
    r = ok(kat.post("/api/material/produkte", json={
        "category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Beta", "article_no": "TB-1",
        "material_kind": "textil", "lifetime_years": 10, "is_set": True}), 201)
    pb = r["produkt"]["id"]
    r = ok(kat.put(f"/api/material/produkte/{pb}/bestandteile", json={"bestandteile": [
        {"produkt_id": t.ids["hms"], "bezeichnung": "Fester Karabiner", "anzahl": 1, "einzeln": True, "austausch": "nein"},
        {"bezeichnung": "Beutel", "anzahl": 1, "einzeln": False}]}))
    return pb, next(b["id"] for b in r["produkt"]["bestandteile"] if b["einzeln"])


def set_mit(t, pb, pos, item_id, serie):
    r = t.wart_a.post("/api/material/artikel", json={"product_id": pb, "folder_id": t.lager_a, "serial_no": serie,
                                                     "manufactured_on": f"{_heute().year - 1}-03",
                                                     "teile": [{"bestandteil_id": pos, "item_id": item_id}]})
    assert r.status_code == 201, r.get_json()
    return r.json["artikel"]["id"]


def test_h1_altwert_eigen():
    """H1: Nach Entnehmen aus einem gesperrten Set und Einzel-Freiprüfung ist das Teil frei OHNE Ursache (b); ein Altwert
    „eigen“ (Stand vor der Nachbesserung, per SQL nachgestellt) geht beim Einsetzen weg (a). „aussondern“ in der ersten
    Set-Prüfung an der Position „nein“ sperrt Teil und Set (c) – das Set-Protokoll sagt nicht „einsatzbereit“. Ein Altwert
    im freien Set (direkt gesetzt) sperrt ebenso, weil teil_bleibt_gesperrt am Sperrzustand hängt (c)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s = t.s["id"]
        k1, k2, _ = t.teile
        # Ablauf der Probe: erst K2 (Set gesperrt), dann K1 entnehmen – K1 gesperrt mit eigenem Grund.
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", headers=H, json={"teil_id": k2}))
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", headers=H, json={"teil_id": k1}))
        assert (zeile(app, k1)["lock_state"], zeile(app, k1)["lock_cause"]) == ("gesperrt", "eigen")
        pruefen(p, k1)
        z = zeile(app, k1)
        assert (z["lock_state"], z["lock_cause"], z["lock_reason"]) == ("frei", None, ""), z            # (b)
        pb, pos = set_nein(t)
        # (a): Altwert nachgestellt – nach dem Einsetzen ohne Ursache, ohne Grund, ohne Prüfmarke.
        sql(app, "UPDATE mat_item SET lock_cause = 'eigen', lock_reason = 'Altwert', set_pruefen = 1 WHERE id = ?", (k1,))
        sb = set_mit(t, pb, pos, k1, "SB-NEIN-1")
        z = zeile(app, k1)
        assert (z["parent_item_id"], z["lock_state"], z["lock_cause"], z["lock_reason"], z["set_pruefen"]) == (
            sb, "frei", None, "", 0), z
        # p9b: „aussondern“ an K1 in der ersten Set-Prüfung → K1 gesperrt (eigen), Set gesperrt.
        lauf_auf(p, sb)
        pruefen(p, k1, "aussondern", grund="Platzhalter: Riss")
        assert lage(app, sb)[k1][2:4] == ("gesperrt", "eigen") and lage(app, sb)[sb][2] == "gesperrt", lage(app, sb)
        assert "das Set aussondern" in zeile(app, k1)["lock_reason"]
        r = starten(p, sb)
        assert r.status_code in (200, 201), r.get_json()
        r = festschreiben(p, r.json["pruefung"]["id"], ergebnis="einsatzbereit", maengel_gesehen=[])
        assert r.status_code == 200, r.get_json()
        assert r.json["pruefung"]["set_protokoll"]["gesamt"] != "einsatzbereit", r.json["pruefung"]["set_protokoll"]
        assert zeile(app, sb)["lock_state"] == "gesperrt"
        # (c) ohne (a)/(b): ein freies Teil im freien Set mit Altwert „eigen“ (direkt gesetzt, wie eine alte Datenbank).
        f = t.f["id"]
        pruefen(p, f)
        sb2 = set_mit(t, pb, pos, f, "SB-NEIN-2")
        sql(app, "UPDATE mat_item SET lock_cause = 'eigen' WHERE id = ?", (f,))
        pruefen(p, f, "aussondern", grund="Platzhalter: Riss")
        assert lage(app, sb2)[f][2:4] == ("gesperrt", "eigen") and lage(app, sb2)[sb2][2] == "gesperrt", lage(app, sb2)
        assert stimmig(app)
    print("H1 (Altwert „eigen“) bestanden.")


def test_h1_absicherung_und_start():
    """H1 (d): Ist das Set trotz eines schlechteren Teilergebnisses im Lauf frei (hier nachgestellt, indem das Ergebnis
    am Teil nichts bewirkt), schreibt „einsatzbereit“ am Set-Artikel nicht fest (409). Die Startbereinigung entfernt
    lock_cause an freien Artikeln und lässt gesperrte unberührt."""
    from app.material.services import setaustausch, sets
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, p = t.app, t.k["pruefer"]
        pb, pos = set_nein(t)
        f = t.f["id"]
        sb = set_mit(t, pb, pos, f, "SB-NEIN-D")
        lauf_auf(p, sb)
        echt = setaustausch.teil_bleibt_gesperrt
        setaustausch.teil_bleibt_gesperrt = lambda *a, **k: None          # der alte Fehler: keine Sperre
        try:
            pruefen(p, f, "aussondern", grund="Platzhalter: Riss")
        finally:
            setaustausch.teil_bleibt_gesperrt = echt
        assert zeile(app, sb)["lock_state"] == "frei"
        r = starten(p, sb)
        assert r.status_code in (200, 201), r.get_json()
        r = festschreiben(p, r.json["pruefung"]["id"], ergebnis="einsatzbereit", maengel_gesehen=[])
        assert r.status_code == 409 and "nicht mit „einsatzbereit“ geprüft" in r.json["error"], r.get_json()
        assert zeile(app, sb)["last_inspected_on"] is None
        # Startbereinigung: frei mit Ursache → ohne; gesperrt bleibt.
        k1 = t.teile[0]
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        sql(app, "UPDATE mat_item SET lock_cause = 'eigen' WHERE id = ?", (f,))
        vorher = {x["id"]: x["lock_cause"] for x in zeilen(app, "SELECT id, lock_cause FROM mat_item "
                                                                "WHERE lock_state <> 'frei'")}
        conn = sqlite3.connect(app.config["DB_PATH"])
        try:
            sets.beim_start(conn)
            sets.beim_start(conn)                                           # wiederholbar
        finally:
            conn.close()
        assert zeile(app, f)["lock_cause"] is None
        assert not zeilen(app, "SELECT 1 FROM mat_item WHERE lock_state = 'frei' AND lock_cause IS NOT NULL")
        assert {x["id"]: x["lock_cause"] for x in zeilen(app, "SELECT id, lock_cause FROM mat_item "
                                                              "WHERE lock_state <> 'frei'")} == vorher
    print("H1 (Absicherung, Startbereinigung) bestanden.")


def test_a1_sperrgrund_eingesetzt():
    """A1: Ein eingesetzter vorhandener Artikel mit gültiger Prüfung heißt unter „Gesperrt, weil“ „wurde eingesetzt
    (vorhandener Artikel)“, nicht „war selbst gesperrt“; ein Teil mit eigener Sperre im Set und Freiprüfung weiter
    „war selbst gesperrt“."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s = t.s["id"]
        k1, k2, _ = t.teile
        eingangsgeprueft(t)
        f = t.f["id"]
        pruefen(p, f)
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", headers=H, json={"teil_id": k2}))
        ok(w.post(f"/api/material/artikel/{s}/teil-einsetzen", headers=H, json={"item_id": f, "bestaetigt": True}), 201)
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        pruefen(p, k1)                                                      # Freiprüfung im gesperrten Set
        texte = {g["artikel"]["id"]: g["text"] for g in ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"][
            "sperrgruende"] if g["art"] == "pruefen"}
        nr_f, nr_k1 = zeile(app, f)["inventory_no"], zeile(app, k1)["inventory_no"]
        assert texte[f] == f"{nr_f} wurde eingesetzt (vorhandener Artikel) – in der Set-Prüfung zur Freigabe prüfen.", texte
        assert texte[k1] == f"{nr_k1} war selbst gesperrt – in der Set-Prüfung zur Freigabe prüfen.", texte
    print("A1 (Sperrgrund am eingesetzten Teil) bestanden.")


def test_a3_auswahl_viele_fehltreffer():
    """A3: 250 importierte Artikel mit „Standort: Halle K-2“ in der Bemerkung – die Suche „K-2“ findet 20 echte Treffer
    (bisherige Inventarnummer K-200 … K-250) und „weitere“, statt nach 200 Fehltreffern abzubrechen. B2: die Spalte heißt
    „Bisherige Inventarnummer“ wie das Zielfeld."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        zeilen_ = [["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Bisherige Inventarnummer", "Standort"]]
        zeilen_ += [["Testwerk", "HMS Beta", "HB-7", f"VIELE-{n:03d}", f"K-{n:03d}", "Halle K-2"] for n in range(1, 251)]
        daten = csv_bytes(zeilen_)
        b = ok(probelauf(w, t.lager_a, daten))
        assert {s["titel"]: s["zuordnung"] for s in b["spalten"]}["Bisherige Inventarnummer"] == "inventarnummer", b["spalten"]
        r = ok(w.post(f"/api/material/ordner/{t.lager_a}/import", headers=H, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(daten), "liste.csv")}), 201)
        assert r["import"]["angelegt"] == 250, r["import"]
        r = ok(w.get(f"/api/material/ordner/{t.lager_a}/kandidaten", query_string={"product_id": t.ids["hms"], "q": "K-2"}))
        assert len(r["treffer"]) == 20 and r["weitere"] is True, (len(r["treffer"]), r["weitere"])
        assert all(x["bisherige_inventarnummer"].startswith("K-2") for x in r["treffer"]), r["treffer"]
        r = ok(w.get(f"/api/material/ordner/{t.lager_a}/kandidaten", query_string={"product_id": t.ids["hms"],
                                                                                   "q": "K-23"}))
        assert sorted(x["bisherige_inventarnummer"] for x in r["treffer"]) == [f"K-23{n}" for n in range(10)], r
        assert r["weitere"] is False
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item WHERE notes LIKE '%Halle K-2%'")[0]["n"] == 250
    print("A3 (Auswahl mit vielen Fehltreffern) bestanden.")


def test_b2_spalten_bisherige_nummer():
    """B2: „Bisherige Inventarnummer“, „Alte Inventarnummer“, „Bisherige Nummer“, „Alte Nummer“ werden zur bisherigen
    Inventarnummer; „Set (Inventarnummer)“ aus dem eigenen Export bleibt ignoriert und ohne Warnung; eine andere ignorierte
    Spalte mit „Inventar“ im Titel nennt der Probelauf."""
    from app.material.services import bestandsimport
    for titel in ("Bisherige Inventarnummer", "Alte Inventarnummer", "Bisherige Nummer", "Alte Nummer"):
        assert bestandsimport.erkennen(titel)[0] == "inventarnummer", titel
    assert bestandsimport.erkennen("Set (Inventarnummer)")[0] == "ignorieren"
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        daten = csv_bytes([["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Alte Nummer", "Set (Inventarnummer)",
                            "Altes Inventar"],
                           ["Testwerk", "HMS Beta", "HB-7", "B2-1", "ALT-B2-1", "M-000001", "X"]])
        b = ok(probelauf(t.wart_a, t.lager_a, daten))
        zu = {s["titel"]: s["zuordnung"] for s in b["spalten"]}
        assert (zu["Alte Nummer"], zu["Set (Inventarnummer)"], zu["Altes Inventar"]) == (
            "inventarnummer", "ignorieren", "ignorieren"), zu
        warn = [x for x in b["warnungen"] if "Inventar" in x]
        assert len(warn) == 1 and "„Altes Inventar“" in warn[0] and "Bisherige Inventarnummer" in warn[0], b["warnungen"]
    print("B2 (Spalte „Bisherige Inventarnummer“) bestanden.")


if __name__ == "__main__":
    test_h1_altwert_eigen()
    test_h1_absicherung_und_start()
    test_a1_sperrgrund_eingesetzt()
    test_a3_auswahl_viele_fehltreffer()
    test_b2_spalten_bisherige_nummer()
