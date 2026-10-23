"""Hersteller-Sets, Paket K2 (Phase 4 · Lieferung 2):  python tests/test_material_sets_pruefung.py  oder  pytest

Sperr-Kaskade je Sperrweg (Prüfer-Sperre, Ergebnis „instandsetzen“, Mangelmeldung, Verlust, Unvollständigkeit), eigene
Sperre an einem mitgesperrten Teil, Freiprüfung im gesperrten Set, „Set prüfen“ mit Prüfumfang und Teiletabelle, die
Freigabe-Bedingungen einzeln, Berichtigungen (geben nie frei), Wettläufe, Set aussondern mit der Wahl je Teil, Ergebnis
„aussondern“ an Teil und Set-Artikel, Teil entnehmen, tauschen, einsetzen und löschen, Durchgang mit Set
(Sammelprotokoll), Unveränderlichkeit der Teiletabelle, Jahresbericht (eine Set-Sperre zählt einmal), Mails und
Datenschutz (kein Meldername am Set), Trennung der Gliederungen für die neuen Routen.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import os
import sys
import tempfile
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, freigeben, mails_abfangen, mails_zurueck,  # noqa: E402
                           neues_konto, starten)
from test_material_import import ok  # noqa: E402
from test_material_sets import abgewiesen, roh, set_aufbau, stimmig  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402


# --- Hilfen -------------------------------------------------------------------------------------------------------------

def lage(app, sid):
    """{Kennung: (folder_id, origin_folder_id, lock_state, lock_cause, set_pruefen)} für Set und Teile."""
    return {r["id"]: (r["folder_id"], r["origin_folder_id"], r["lock_state"], r["lock_cause"], r["set_pruefen"])
            for r in zeilen(app, "SELECT * FROM mat_item WHERE id = ? OR parent_item_id = ? ORDER BY id", (sid, sid))}


def eintraege(app, iid, ab=0):
    return zeilen(app, "SELECT id, action, user_name, before_json, after_json FROM mat_audit WHERE entity = 'item' "
                       "AND entity_id = ? AND id > ? ORDER BY id", (iid, ab))


def letzte_journal_id(app):
    return zeilen(app, "SELECT MAX(id) AS m FROM mat_audit")[0]["m"]


def pruefen(c, iid, ergebnis="einsatzbereit", **d):
    """Eine Prüfung beginnen und festschreiben (gemeldete Mängel abgehakt) – liefert die Prüfung."""
    r = starten(c, iid)
    assert r.status_code in (200, 201), r.get_json()
    pr = r.json["pruefung"]
    if ergebnis == "einsatzbereit":
        d.setdefault("maengel_gesehen", [m["id"] for m in pr["maengel"]])
    else:
        d.setdefault("grund", "Testgrund")
    r = festschreiben(c, pr["id"], ergebnis=ergebnis, **d)
    assert r.status_code == 200, r.get_json()
    return r.json["pruefung"]


def lauf_auf(c, sid, **d):
    r = c.post(f"/api/material/artikel/{sid}/set-lauf", json=d)
    assert r.status_code in (200, 201), r.get_json()
    return r.json["lauf"]


def set_pruefen(c, sid, teile, ergebnis="einsatzbereit", **d):
    """„Set prüfen“: Lauf eröffnen, die Teile mit „einsatzbereit“ prüfen, den Set-Artikel festschreiben."""
    lauf_auf(c, sid)
    for t in teile:
        pruefen(c, t)
    return pruefen(c, sid, ergebnis, **d)


def eingangsgeprueft(t):
    """Das Set aus set_aufbau einmal frei geprüft (Eingang) – danach einsatzbereit."""
    p = t.k["pruefer"]
    pr = set_pruefen(p, t.s["id"], t.teile)
    assert pr["set_protokoll"]["gesamt"] == "einsatzbereit", pr["set_protokoll"]
    return pr


# --- Sperr-Kaskade ------------------------------------------------------------------------------------------------------

def test_kaskade():
    """Jeder Sperrweg sperrt das ganze Set (eine Anweisung, alle nach „Gesperrt“, Herkunft = Heimat des Sets): eigener Grund
    am Anlass („eigen“), alle anderen „set“; Journal „set_gesperrt“ als System. Eine eigene Sperre geht auch an einem
    mitgesperrten Teil, eine zweite eigene nicht (409). Verlust am Set: alle verloren; am Teil: nur dieses. Mangelmeldung
    an einem Teil: Leser sehen am Set und an den übrigen Teilen keinen Meldernamen; die Mails nennen das ganze Set."""
    from app.material.services import mangel, meldung
    gesendet = []

    def abfangen(an, betreff, inhalt):
        gesendet.append((an, betreff, inhalt))
        return True
    alt1 = mails_abfangen(meldung, abfangen)
    alt = mails_abfangen(mangel, abfangen)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, w, p, f = t.app, t.wart_a, t.k["pruefer"], t.k["fuehrung"]
            s, k1, k2, r1 = t.s["id"], *t.teile
            eingangsgeprueft(t)
            gesperrt = t.sys_a["gesperrt"]
            # 1. Prüfer-Sperre am Teil.
            ab = letzte_journal_id(app)
            ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz", "text": "Teststurz"}))
            l = lage(app, s)
            assert l == {s: (gesperrt, t.lager_a, "gesperrt", "set", 0), k1: (gesperrt, t.lager_a, "gesperrt", "eigen", 1),
                         k2: (gesperrt, t.lager_a, "gesperrt", "set", 0), r1: (gesperrt, t.lager_a, "gesperrt", "set", 0)}, l
            assert zeilen(app, "SELECT set_lock_origin FROM mat_item WHERE id = ?", (s,))[0]["set_lock_origin"] == "teil"
            e = eintraege(app, k1, ab)
            assert [(x["action"], x["user_name"]) for x in e] == [("gesperrt", "pruefer")], e
            for x in (s, k2, r1):
                e = eintraege(app, x, ab)
                assert [(y["action"], y["user_name"]) for y in e] == [("set_gesperrt", "System")], e
            assert '"teil": "' in eintraege(app, s, ab)[0]["after_json"]
            a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
            assert a["status"] == "gesperrt" and [g["art"] for g in a["set"]["sperrgruende"]] == ["eigen", "pruefen",
                                                                                                "set_pruefung"] or \
                [g["art"] for g in a["set"]["sperrgruende"]] == ["eigen", "set_pruefung"], a["set"]["sperrgruende"]
            assert "Teststurz" in a["set"]["sperrgruende"][0]["text"]
            assert stimmig(app)
            # 2. Eigene Sperre am mitgesperrten Teil geht; eine zweite an einem eigen gesperrten nicht.
            ok(p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "beschaedigung"}))
            assert lage(app, s)[k2][2:] == ("gesperrt", "eigen", 1)
            r = p.post(f"/api/material/artikel/{k2}/sperren", json={"grund": "sturz"})
            assert r.status_code == 409 and "schon gesperrt" in r.json["error"], r.get_json()
            # 3. Verlust an einem Teil: nur dieses verloren.
            ok(p.post(f"/api/material/artikel/{r1}/sperren", json={"grund": "verlust"}))
            assert lage(app, s)[r1][2:] == ("verloren", "eigen", 1) and lage(app, s)[s][2] == "gesperrt"
            assert stimmig(app)
        with tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, w, p, f = t.app, t.wart_a, t.k["pruefer"], t.k["fuehrung"]
            s, k1, k2, r1 = t.s["id"], *t.teile
            # 4. Verlust am Set-Artikel: alle verloren, Ursprung „set“.
            ok(p.post(f"/api/material/artikel/{s}/sperren", json={"grund": "verlust"}))
            l = lage(app, s)
            assert {v[2] for v in l.values()} == {"verloren"} and l[s][3] == "eigen", l
            assert zeilen(app, "SELECT set_lock_origin FROM mat_item WHERE id = ?", (s,))[0]["set_lock_origin"] == "set"
            # 5. Mangelmeldung am Teil eines freien Sets (zweites Set in A, der Person zugeordnet) – Datenschutz und Mails.
        with tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, w, p, f = t.app, t.wart_a, t.k["pruefer"], t.k["fuehrung"]
            s, k1, k2, r1 = t.s["id"], *t.teile
            # Die PSA-Person ist zugeordnet, gemeldet hat „fuehrung“; „leser“ liest A nur.
            person, person_id = neues_konto(app, "psa_person@example.org", name="PSA Person", stufe=0)
            leser, leser_id = neues_konto(app, "leser@example.org", name="Nur Leser")
            freigeben(t.adm, t.a, leser_id, "lesen")
            ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
            ab = letzte_journal_id(app)
            gesendet.clear()
            r = f.post(f"/api/material/artikel/{k2}/mangel", json={"beschreibung": "Testmangel am Teil"})
            assert r.status_code == 201, r.get_json()
            assert lage(app, s)[k2][2:4] == ("gesperrt", "eigen") and lage(app, s)[s][2:4] == ("gesperrt", "set")
            assert [x["action"] for x in eintraege(app, k2, ab)] == ["mangel_gemeldet"]
            for x in (s, k1, r1):
                e = eintraege(app, x, ab)
                assert [(y["action"], y["user_name"]) for y in e] == [("set_gesperrt", "System")], e
                assert '"mangel"' not in e[0]["after_json"]
            # Wer nur liest, sieht an keinem Artikel des Sets den Meldernamen (auch nicht im Lebenslauf-Journal).
            for x in (s, k1, k2, r1):
                text = leser.get(f"/api/material/artikel/{x}").get_data(as_text=True)
                assert '"fuehrung"' not in text, (x, text[text.find("fuehrung") - 200:text.find("fuehrung") + 50])
            texte = "\n".join(b + "\n" + i for _, b, i in gesendet)
            assert "das ganze Set ist mit allen 3 Teilen gesperrt" in texte, texte
            assert any("mit dem ganzen Set gesperrt" in b for _, b, _ in gesendet), [b for _, b, _ in gesendet]
            assert stimmig(app)
    finally:
        mails_zurueck(alt)
        mails_zurueck(alt1)
    print("Sperr-Kaskade bestanden.")


# --- Set prüfen und Freigabe -------------------------------------------------------------------------------------------

def _pdf(app, pid):
    zeile = zeilen(app, "SELECT pdf_path FROM mat_inspection WHERE id = ?", (pid,))[0]
    return os.path.join(app.config["DATA_DIR"], zeile["pdf_path"])


def _pdf_text(pfad):
    from test_material import pdf_seiten
    return " ".join(" ".join(seite.split()) for seite in pdf_seiten(pfad))


def test_set_pruefung_freigabe():
    """„Set prüfen“: Set-Artikel nur im Lauf; ein freies Set prüft alle Teile; der Set-Artikel lässt sich erst festschreiben,
    wenn der Prüfumfang geprüft und kein Entwurf mehr offen ist; Set-Protokoll = P-Protokoll mit Teiletabelle (PDF/A),
    Teil-Protokoll mit „Teil von Set“. Gesperrtes Set: Prüfumfang Set-Artikel + Teile mit eigener Sperre (die übrigen
    „übernommen“), vom Set-Artikel aus alle; jede Freigabe-Bedingung einzeln; erst ohne Gründe EIN Übergang auf frei,
    zurück in die Heimat. Berichtigungen geben nie frei. Teiletabelle unveränderlich."""
    import subprocess
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        # Ohne Lauf keine Prüfung am Set-Artikel.
        r = starten(p, s)
        assert r.status_code == 409 and "Set prüfen" in r.json["error"], r.get_json()
        lf = lauf_auf(p, s)
        assert [u["zu_pruefen"] for u in lf["umfang"]] == [True, True, True], lf
        assert lf["fortschritt"] == {"geprueft": 0, "zu_pruefen": 3, "teile": 3} and lf["bereit"] is False
        r = p.post(f"/api/material/artikel/{s}/set-lauf", json={})
        assert r.status_code == 200 and r.json["lauf"]["id"] == lf["id"]
        pr_s = ok(starten(p, s), 201)["pruefung"]
        assert pr_s["set_lauf"]["rolle"] == "set" and pr_s["set_abschluss"]["bereit"] is False
        assert [x["text"] for x in pr_s["punkte"] if x["gruppe"] == "Bestandteile des Sets"] == ["Tasche vorhanden"]
        r = festschreiben(p, pr_s["id"], ergebnis="einsatzbereit")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
        teil_pr = [pruefen(p, x) for x in t.teile]
        assert all(x["set_lauf"]["rolle"] == "teil" and x["set_lauf"]["id"] == lf["id"] for x in teil_pr)
        assert ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]["bereit"] is True
        r = festschreiben(p, pr_s["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        sp = r.json["pruefung"]["set_protokoll"]
        assert sp["gesamt"] == "einsatzbereit" and [z["art"] for z in sp["zeilen"]] == ["teil", "teil", "teil", "bestandteil"]
        assert [z["protokoll_id"] for z in sp["zeilen"][:3]] == [x["protokoll"]["id"] for x in teil_pr], sp["zeilen"]
        assert not any(z["uebernommen"] for z in sp["zeilen"]) and sp["zeilen"][3]["vorhanden"] is True
        assert zeilen(app, "SELECT state, set_inspection_id FROM mat_set_lauf WHERE id = ?", (lf["id"],)) == [
            {"state": "abgeschlossen", "set_inspection_id": pr_s["id"]}]
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["set"]["status"] == "einsatzbereit" and a["set"]["lauf"] is None
        assert a["set"]["letzte_pruefung"]["gesamtergebnis"] == "einsatzbereit"
        # PDF: Set-Protokoll mit Teiletabelle (PDF/A geprüft), Teil-Protokoll mit „Teil von Set“.
        pfad = _pdf(app, pr_s["id"])
        text = _pdf_text(pfad)
        assert "Set-Prüfung" in text and "Gesamtergebnis des Sets" in text and teil_pr[0]["protokoll"]["id"] in text, text
        assert "Tasche" in text and "vorhanden" in text
        assert f"Teil von Set {t.s['inventory_no']}" in _pdf_text(_pdf(app, teil_pr[0]["id"]))
        vera = "/home/harness/devtools/bin/st-vera"
        if os.path.exists(vera):
            lauf = subprocess.run([vera, pfad], capture_output=True, text=True, timeout=300)
            assert lauf.returncode == 0 and "PASS" in lauf.stdout, (lauf.stdout[-600:], lauf.stderr[-600:])
        # Die Teiletabelle ist festgeschrieben.
        conn = roh(app)
        try:
            zid = conn.execute("SELECT id FROM mat_set_protokoll_zeile WHERE inspection_id = ? LIMIT 1",
                               (pr_s["id"],)).fetchone()[0]
            abgewiesen(conn, "UPDATE mat_set_protokoll_zeile SET ergebnis = 'aussondern' WHERE id = ?", (zid,))
            abgewiesen(conn, "DELETE FROM mat_set_protokoll_zeile WHERE id = ?", (zid,))
            abgewiesen(conn, "INSERT INTO mat_set_protokoll_zeile (inspection_id, art, bezeichnung) VALUES (?, 'teil', 'x')",
                       (pr_s["id"],))
            abgewiesen(conn, "INSERT OR REPLACE INTO mat_set_protokoll_zeile (id, inspection_id, art, bezeichnung) "
                             "VALUES (?, ?, 'teil', 'x')", (zid, pr_s["id"]))
        finally:
            conn.close()

        # Gesperrt über ein Teil: Prüfumfang = Set-Artikel + dieses Teil, die übrigen „übernommen“.
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        lf = lauf_auf(p, s)
        assert [(u["teil"]["id"], u["zu_pruefen"]) for u in lf["umfang"]] == [(k1, True), (k2, False), (r1, False)]
        assert lf["umfang"][1]["uebernommen"]["protokoll_id"] == teil_pr[1]["protokoll"]["id"]
        assert any("eigene Sperre" in g for g in lf["freigabe_gruende"]), lf["freigabe_gruende"]

        def blockiert(vorher, nachher, erwartet):
            """Einen Freigabe-Grund herstellen (SQL), k1 und den Set-Artikel prüfen: Das Set bleibt gesperrt mit diesem
            Grund; danach den Grund wieder wegnehmen."""
            sql(app, *vorher) if vorher else None
            lauf_auf(p, s)
            pruefen(p, k1)
            pr = pruefen(p, s)
            assert pr["set_protokoll"]["gesamt"] == "gesperrt", pr["set_protokoll"]
            assert any(erwartet in g for g in pr["set_protokoll"]["gruende"]), (erwartet, pr["set_protokoll"]["gruende"])
            assert lage(app, s)[s][2] == "gesperrt" and lage(app, s)[k1][3] == "set"
            sql(app, *nachher) if nachher else None
            return pr
        def ohne_uebernahme(vorher, nachher, erwartet):
            """Nachbesserung (Ablauf N1, Browser B7): Ein Teil ohne übernehmbare Prüfung (überfällig, neu) gehört von selbst
            zum Prüfumfang – die Vorschau und der Lauf sagen „zu prüfen“, der Set-Artikel lässt sich vorher nicht
            festschreiben (409). Danach den Lauf abbrechen und den Grund wieder wegnehmen."""
            sql(app, *vorher)
            a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
            assert {x["id"]: x["zu_pruefen"] for x in a["set"]["teile"]} == {k1: True, k2: True, r1: False}, a["set"]["teile"]
            lauf_auf(p, s)
            pruefen(p, k1)
            lf = ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]
            assert [(u["teil"]["id"], u["zu_pruefen"]) for u in lf["umfang"]] == [(k1, True), (k2, True), (r1, False)], lf
            assert lf["fortschritt"]["zu_pruefen"] == 2 and lf["bereit"] is False
            assert any(erwartet in g and g.endswith("bitte jetzt prüfen.") for g in lf["freigabe_gruende"]), lf
            e = ok(starten(p, s), 201)["pruefung"]
            r = festschreiben(p, e["id"], ergebnis="einsatzbereit")
            assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
            nr_k2 = zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (k2,))[0]["inventory_no"]
            assert nr_k2 in r.json["error"], r.get_json()
            assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
            assert ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))["bleibt"] is True
            sql(app, *nachher)
        gestern = (_heute() - timedelta(days=1)).isoformat()
        k2_due = zeilen(app, "SELECT next_due_on FROM mat_item WHERE id = ?", (k2,))[0]["next_due_on"]
        ohne_uebernahme(("UPDATE mat_item SET next_due_on = ? WHERE id = ?", (gestern, k2)),
                        ("UPDATE mat_item SET next_due_on = ? WHERE id = ?", (k2_due, k2)), "überfällig")
        alt_li = zeilen(app, "SELECT last_inspected_on FROM mat_item WHERE id = ?", (k2,))[0]["last_inspected_on"]
        ohne_uebernahme(("UPDATE mat_item SET last_inspected_on = NULL WHERE id = ?", (k2,)),
                        ("UPDATE mat_item SET last_inspected_on = ? WHERE id = ?", (alt_li, k2)), "noch nie geprüft")
        # Übernommen, aber blockiert: Den Lauf schließen – das Set bleibt gesperrt, mit dem Grund als ganzem Satz.
        pr = blockiert(("UPDATE mat_item SET retire_by = ? WHERE id = ?", (gestern, r1)),
                       ("UPDATE mat_item SET retire_by = NULL WHERE id = ?", (r1,)), "Lebensdauer erreicht")
        assert [z["uebernommen"] for z in pr["set_protokoll"]["zeilen"][:3]] == [False, True, True]
        blockiert(("UPDATE mat_item SET lock_state = 'verloren' WHERE id = ?", (k2,)),
                  ("UPDATE mat_item SET lock_state = 'gesperrt' WHERE id = ?", (k2,)), "verloren")
        # Berichtigung der Set-Prüfung gibt nie frei (der Grund ist weg, das Set bleibt gesperrt), übernimmt die Tabelle.
        letzte = zeilen(app, "SELECT id FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL "
                             "ORDER BY id DESC LIMIT 1", (s,))[0]["id"]
        b = ok(p.post(f"/api/material/pruefungen/{letzte}/berichtigen", json={"grund": "Testberichtigung"}), 201)["pruefung"]
        r = festschreiben(p, b["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        assert r.json["pruefung"]["set_protokoll"]["berichtigung"] is True and lage(app, s)[s][2] == "gesperrt"
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_set_protokoll_zeile WHERE inspection_id = ?", (b["id"],)) == \
            zeilen(app, "SELECT COUNT(*) AS n FROM mat_set_protokoll_zeile WHERE inspection_id = ?", (letzte,))
        # Wettlauf: Meldung an k2 nach der Teilprüfung von k1, während der Set-Artikel im Entwurf ist → keine Freigabe.
        lauf_auf(p, s)
        pruefen(p, k1)
        e = ok(starten(p, s), 201)["pruefung"]
        ok(w.post(f"/api/material/artikel/{k2}/mangel", json={"beschreibung": "Testmangel"}), 201)
        r = festschreiben(p, e["id"], ergebnis="einsatzbereit")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()   # k2 jetzt im Umfang
        pruefen(p, k2)
        r = festschreiben(p, e["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200 and r.json["pruefung"]["set_protokoll"]["gesamt"] == "einsatzbereit", r.get_json()
        l = lage(app, s)
        assert {v for v in l.values()} == {(t.lager_a, None, "frei", None, 0)}, l
        assert [(x["action"], x["user_name"]) for x in eintraege(app, k2)][-1] == ("set_frei", "System")
        assert stimmig(app)

        # Sperre vom Set-Artikel aus: alle Teile im Umfang; Berichtigung „instandsetzen → einsatzbereit“ am Teil gibt nicht frei.
        ok(p.post(f"/api/material/artikel/{s}/sperren", json={"grund": "beschaedigung"}))
        lf = lauf_auf(p, s)
        assert all(u["zu_pruefen"] for u in lf["umfang"]), lf["umfang"]
        pi = pruefen(p, k1, "instandsetzen")
        assert lage(app, s)[k1][3] == "eigen"
        b = ok(p.post(f"/api/material/pruefungen/{pi['id']}/berichtigen", json={"grund": "Testberichtigung"}), 201)["pruefung"]
        assert b["set_lauf"]["id"] == lf["id"]                       # zählt im noch offenen Lauf
        assert festschreiben(p, b["id"], ergebnis="einsatzbereit").status_code == 200
        assert lage(app, s)[k1][2:4] == ("gesperrt", "set") and lage(app, s)[s][2] == "gesperrt"
        # Abbrechen: offener Entwurf am Set-Artikel → 409; Teil-Entwürfe laufen weiter; mit Prüfungen bleibt der Lauf.
        e_k2 = ok(starten(p, k2), 201)["pruefung"]
        e_s = ok(starten(p, s), 201)["pruefung"]
        r = p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H)
        assert r.status_code == 409 and "Set-Artikels ist offen" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e_s['id']}", headers=H).status_code == 200
        r = ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        assert r["bleibt"] is True and r["artikel"]["set"]["lauf"] is None
        assert zeilen(app, "SELECT set_lauf_id FROM mat_inspection WHERE id = ?", (e_k2["id"],))[0]["set_lauf_id"] is None
        assert zeilen(app, "SELECT state FROM mat_set_lauf WHERE id = ?", (lf["id"],))[0]["state"] == "abgebrochen"
        # Ein Lauf ohne Prüfung verschwindet beim Abbrechen.
        assert p.delete(f"/api/material/pruefungen/{e_k2['id']}", headers=H).status_code == 200
        lf2 = lauf_auf(p, s)
        r = ok(w.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        assert r["bleibt"] is False and not zeilen(app, "SELECT 1 FROM mat_set_lauf WHERE id = ?", (lf2["id"],))
        assert stimmig(app)
    print("Set prüfen und Freigabe bestanden.")


def test_hinweis_tage():
    """Mehr als sieben Tage zwischen der ersten Teilprüfung und dem Abschluss: Hinweis im Set-Protokoll und am Lauf."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, p = t.app, t.k["pruefer"]
        s = t.s["id"]
        lauf_auf(p, s)
        e = ok(starten(p, t.teile[0]), 201)["pruefung"]
        with app.test_request_context():
            from app import db
            from app.material.services import pruefung
            u = db.query("SELECT * FROM users WHERE id = ?", (t.k["pruefer_id"],), one=True)
            pruefung.abschliessen(e["id"], {"ergebnis": "einsatzbereit"}, pruefung.pruefer_aus(u),
                                  pruefdatum=_heute() - timedelta(days=10))
        for x in t.teile[1:]:
            pruefen(p, x)
        assert ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]["hinweis_tage"] == 10
        pr = pruefen(p, s)
        assert "liegen 10 Tage" in pr["set_protokoll"]["hinweis"], pr["set_protokoll"]
    print("Hinweis nach mehr als sieben Tagen bestanden.")


# --- Aussondern ---------------------------------------------------------------------------------------------------------

def test_aussondern():
    """Set aussondern (Materialwart) mit der Wahl je Teil: Vorbelegung (eigene Prüfer-Sperre → mit aussondern, sonst
    weiterführen), Vorbedingungen (nur Unvollständigkeit → 409, ungeprüfte Meldung → 409, offener Entwurf → 409); ein nur
    mitgesperrtes Teil darf mit. Ergebnis „aussondern“ am Set-Artikel im Lauf und an einem Teil."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        eingangsgeprueft(t)
        person, person_id = neues_konto(app, "psa_aus@example.org", name="PSA Aus", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
        # Nur unvollständig gesperrt (Materialwart hat entnommen): kein Sachkundiger hat es gesehen → 409.
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": r1}))
        r = w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 409 and "unvollständig" in r.json["error"], r.get_json()
        # Prüfer sperrt k1 (Sturz): Vorbelegung k1 aussondern, k2 weiterführen.
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert {x["id"]: x["verbleib_vorschlag"] for x in a["set"]["teile"]} == {k1: "aussondern", k2: "weiterfuehren"}
        # Offener Entwurf an einem Teil → 409; ungeprüfte Meldung → 409.
        e = ok(starten(p, k2), 201)["pruefung"]
        r = w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 409 and "In Prüfung" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        ok(w.post(f"/api/material/artikel/{k2}/mangel", json={"beschreibung": "Testmangel"}), 201)
        r = w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 409 and "Mangelmeldung" in r.json["error"], r.get_json()
        time.sleep(1.1)                             # „danach geprüft“ heißt: in einer späteren Sekunde (mangel.UNGEPRUEFT)
        pruefen(p, k2, "instandsetzen")             # ein Prüfer hat die Meldung gesehen
        # Fremde Teil-Kennung in „verbleib“ → 404.
        r = w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel", "verbleib": [
            {"teil_id": t.teile_b[0], "verbleib": "aussondern"}]})
        assert r.status_code == 404, r.get_json()
        # k2 weiterführen (überstimmt die Vorbelegung „aussondern“ – k2 hat jetzt eine eigene Prüfer-Sperre).
        r = ok(w.post(f"/api/material/artikel/{s}/aussondern", json={"grund": "irreparabel", "verbleib": [
            {"teil_id": k2, "verbleib": "weiterfuehren"}]}))
        z = {x["id"]: x for x in zeilen(app, "SELECT * FROM mat_item WHERE id IN (?, ?, ?)", (s, k1, k2))}
        assert z[s]["lock_state"] == "ausgesondert" and z[k1]["lock_state"] == "ausgesondert" and z[k1]["parent_item_id"] == s
        assert z[k2]["parent_item_id"] is None and z[k2]["lock_state"] == "gesperrt" and z[k2]["lock_cause"] == "eigen"
        assert z[k2]["origin_folder_id"] == t.lager_a and z[k2]["assigned_user_id"] is None
        assert {z[s]["folder_id"], z[k1]["folder_id"]} == {t.sys_a["ausgesondert"]} and z[s]["assigned_user_id"] is None
        anz = zeilen(app, "SELECT item_id, protocol_id FROM mat_inspection WHERE kind = 'aussonderung' AND item_id IN (?, ?)",
                     (s, k1))
        assert len(anz) == 2 and all(x["protocol_id"].startswith("A-") for x in anz), anz
        assert stimmig(app)
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        eingangsgeprueft(t)
        # Ergebnis „aussondern“ an einem Teil: entnommen und ausgesondert, das Set unvollständig gesperrt.
        pr = pruefen(p, r1, "aussondern")
        z = zeilen(app, "SELECT parent_item_id, lock_state FROM mat_item WHERE id = ?", (r1,))[0]
        assert z == {"parent_item_id": None, "lock_state": "ausgesondert"}, z
        assert lage(app, s)[s][2:4] == ("gesperrt", "set")
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["set"]["vollstaendig"] is False and [g["art"] for g in a["set"]["sperrgruende"]][0] == "unvollstaendig"
        assert "teil_entnommen" in [x["action"] for x in eintraege(app, s)]
        # Ergebnis „aussondern“ am Set-Artikel im Lauf: ein nur mitgesperrtes Teil mit aussondern, eines weiterführen.
        lauf_auf(p, s)
        pruefen(p, k1)
        pruefen(p, k2)
        pr = pruefen(p, s, "aussondern", verbleib=[{"teil_id": k1, "verbleib": "aussondern"},
                                                  {"teil_id": k2, "verbleib": "weiterfuehren"}])
        assert pr["set_protokoll"]["gesamt"] == "ausgesondert"
        z = {x["id"]: x for x in zeilen(app, "SELECT * FROM mat_item WHERE id IN (?, ?, ?)", (s, k1, k2))}
        assert (z[s]["lock_state"], z[k1]["lock_state"], z[k2]["lock_state"]) == ("ausgesondert", "ausgesondert", "gesperrt")
        assert z[k2]["lock_reason"] == "aus ausgesondertem Set entnommen" and z[k2]["parent_item_id"] is None
        aus = zeilen(app, "SELECT item_id, basis_inspection_id FROM mat_inspection WHERE kind = 'aussonderung' "
                          "AND item_id IN (?, ?)", (s, k1))
        assert {x["basis_inspection_id"] for x in aus} == {pr["id"]}, aus
        assert "Aussonderungsprotokoll A-" in _pdf_text(_pdf(app, pr["id"]))
    print("Aussondern im Set bestanden.")


# --- Tauschen, entnehmen, einsetzen, löschen ----------------------------------------------------------------------------

def test_tausch_entnahme_loeschen():
    """„Austausch laut Hersteller“: nein → 409, nicht belegt → Bestätigung Pflicht (Journal), ja ohne. Tauschen sperrt das
    Set („Teil getauscht“), das neue Teil übernimmt Zuordnung und Lage und ist im Lauf zu prüfen; das alte verliert die
    Zuordnung. Entnehmen aus gesperrtem Set: eigene Sperre; „aussondern“ nur mit eigener Prüfer-Sperre; offener Entwurf
    409; doppelt 404. Einsetzen an der fehlenden Position. Ungeprüftes Teil löschen sperrt das Set. Fremde Teil-Kennung
    wie unbekannt (404, auch als „7“ und 7.0)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        # Ungeprüftes Teil einzeln löschen: das Set ist unvollständig und gesperrt.
        ok(w.delete(f"/api/material/artikel/{k2}", headers=H))
        assert lage(app, s)[s][2:4] == ("gesperrt", "set") and k2 not in lage(app, s)
        assert [x["action"] for x in eintraege(app, s)][-2:] == ["teil_geloescht", "gesperrt"]
        assert '"set_grund": "unvollstaendig"' in eintraege(app, s)[-1]["after_json"]
        # Einsetzen an der fehlenden Position (nicht belegt → Bestätigung).
        r = w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"serial_no": "SET-A-K3"})
        assert r.status_code == 400 and "Herstellerunterlagen" in r.json["error"], r.get_json()
        r = ok(w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"serial_no": "SET-A-K3", "bestaetigt": True}), 201)
        k3 = r["teil"]["id"]
        assert lage(app, s)[k3] == (t.sys_a["gesperrt"], t.lager_a, "gesperrt", "set", 1)
        assert r["artikel"]["set"]["vollstaendig"] is True
        assert '"bestaetigt": "laut Herstellerunterlagen zulässig"' in eintraege(app, s)[-1]["after_json"]
        r = w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"serial_no": "SET-A-K4", "bestaetigt": True})
        assert r.status_code == 409 and "vollständig" in r.json["error"], r.get_json()
        # Eingang prüfen → frei.
        set_pruefen(p, s, [k1, k3, r1])
        assert lage(app, s)[s][2] == "frei"
        person, person_id = neues_konto(app, "psa_tausch@example.org", name="PSA Tausch", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
        # Tausch der Rolle (Austausch „ja“): ohne Bestätigung; altes Teil frei im Ordner, ohne Zuordnung.
        r = ok(w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": r1, "serial_no": "SET-A-R2"}), 201)
        r2 = r["teil"]["id"]
        z = {x["id"]: x for x in zeilen(app, "SELECT * FROM mat_item WHERE id IN (?, ?)", (r1, r2))}
        assert z[r1]["parent_item_id"] is None and z[r1]["lock_state"] == "frei" and z[r1]["assigned_user_id"] is None
        assert z[r1]["folder_id"] == t.lager_a
        assert z[r2]["parent_item_id"] == s and z[r2]["assigned_user_id"] == person_id and z[r2]["set_pruefen"] == 1
        assert lage(app, s)[s][2:4] == ("gesperrt", "set")
        assert [x["action"] for x in eintraege(app, r1)][-2:] == ["entnommen", "zuordnung_geloest"]
        # Der Grund am Set ist abgeleitet (gruende_nachziehen): das neue Teil, nicht das entnommene.
        nr_r2 = zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (r2,))[0]["inventory_no"]
        assert zeilen(app, "SELECT lock_reason FROM mat_item WHERE id = ?", (s,))[0]["lock_reason"] == \
            f"Teil {nr_r2} neu eingesetzt – Set prüfen"
        lf = lauf_auf(p, s)
        assert [(u["teil"]["id"], u["zu_pruefen"]) for u in lf["umfang"]] == [(k1, False), (k3, False), (r2, True)]
        # Austausch „nein“ → 409 (Katalog: Kopie der Stückliste ist fest – direkt in der Kopie eines neuen Sets setzen).
        sql(app, "DROP TRIGGER mat_slot_aendern")
        sql(app, "UPDATE mat_item_set_slot SET austausch = 'nein' WHERE set_item_id = ? AND einzeln = 1 AND "
                 "bezeichnung = 'Verbindungselement'", (s,))
        r = w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": k1, "serial_no": "SET-A-K9",
                                                                      "bestaetigt": True})
        assert r.status_code == 409 and "nicht austauschbar" in r.json["error"], r.get_json()
        # Ebenso „Teil entnehmen“ (Nachbesserung, Ablauf N3): dann nur das Set aussondern.
        r = w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1})
        assert r.status_code == 409 and r.json["error"].startswith(
            "Laut Hersteller nicht austauschbar – das Set aussondern"), r.get_json()
        sql(app, "UPDATE mat_item_set_slot SET austausch = 'nicht_belegt' WHERE set_item_id = ? AND einzeln = 1 AND "
                 "bezeichnung = 'Verbindungselement'", (s,))
        # Entnehmen aus dem gesperrten Set: offener Entwurf → 409; „aussondern“ ohne eigene Prüfer-Sperre → 409.
        e = ok(starten(p, k1), 201)["pruefung"]
        r = w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1})
        assert r.status_code == 409 and "In Prüfung" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        r = w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1, "verbleib": "aussondern",
                                                                       "grund": "irreparabel"})
        assert r.status_code == 409 and "eigener Sperre durch einen Prüfer" in r.json["error"], r.get_json()
        r = ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": k1}))
        z = zeilen(app, "SELECT * FROM mat_item WHERE id = ?", (k1,))[0]
        assert (z["parent_item_id"], z["lock_state"], z["lock_cause"], z["lock_reason"], z["origin_folder_id"]) == (
            None, "gesperrt", "eigen", "aus gesperrtem Set entnommen", t.lager_a), z
        # Doppelt (oder nicht mehr im Set) → 404 wie unbekannt.
        unbekannt = w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": 999999})
        assert unbekannt.status_code == 404
        for x in (k1, t.teile_b[0], str(t.teile_b[0]), float(t.teile_b[0])):
            r = w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": x})
            assert r.status_code == 404 and r.get_json() == unbekannt.get_json(), (x, r.get_json())
            r = w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": x, "bestaetigt": True})
            assert r.status_code == 404 and r.get_json() == unbekannt.get_json(), (x, r.get_json())
        # Ein geprüftes Teil löschen → 409.
        r = w.delete(f"/api/material/artikel/{k3}", headers=H)
        assert r.status_code == 409 and "Prüfungen" in r.json["error"], r.get_json()
        # Lebenslauf des Sets: nur Einträge am Set selbst – mit den Teil-Ereignissen.
        aktionen = [x["action"] for x in eintraege(app, s)]
        for x in ("teil_geloescht", "teil_eingesetzt", "teil_entnommen", "set_lauf_eroeffnet", "set_geprueft"):
            assert x in aktionen, (x, aktionen)
        assert stimmig(app)
    print("Teil tauschen, entnehmen, einsetzen und löschen bestanden.")


# --- Durchgang, Jahresbericht, Trennung ---------------------------------------------------------------------------------

def test_durchgang_mit_set():
    """Im Ordner-Durchgang bleiben Set und Teile eigene Zeilen; „Set prüfen“ von dort trägt round_id, die Prüfungen
    zählen in Lauf und Durchgang; ein offener Lauf blockiert die Eröffnung nicht; das Sammelprotokoll gruppiert die Teile
    unter dem Set mit dem Gesamtergebnis."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1 = t.s["id"], t.teile[0]
        # Offener Lauf außerhalb – der Durchgang geht trotzdem auf.
        lauf_auf(p, s)
        e = ok(starten(p, k1), 201)["pruefung"]
        d = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang Set"}), 201)
        rid = d["durchgang"]["id"]
        assert zeilen(app, "SELECT round_id, set_lauf_id FROM mat_inspection WHERE id = ?", (e["id"],))[0]["round_id"] == rid
        r = p.post(f"/api/material/artikel/{s}/set-lauf", json={"durchgang_id": rid})
        assert r.status_code == 409 and "außerhalb dieses Durchgangs" in r.json["error"], r.get_json()
        assert p.delete(f"/api/material/pruefungen/{e['id']}", headers=H).status_code == 200
        ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))
        lf = lauf_auf(p, s, durchgang_id=rid)
        assert lf["round_id"] == rid and lf["durchgang"]["id"] == rid
        dj = ok(p.get(f"/api/material/durchgaenge/{rid}"))["durchgang"]
        zeile = {a["id"]: a for a in dj["artikel"] if a.get("sichtbar")}
        assert zeile[s]["set_lauf"]["id"] == lf["id"] and zeile[k1]["teil_von"]["id"] == s
        for x in t.teile:
            pr = pruefen(p, x)
            assert pr["durchgang"]["id"] == rid and pr["set_lauf"]["id"] == lf["id"]
        pr_s = pruefen(p, s)
        assert pr_s["durchgang"]["id"] == rid
        pruefen(p, t.f["id"])
        pruefen(p, t.art_a["id"])
        ok(w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}))
        r = zeilen(app, "SELECT pdf_path FROM mat_round WHERE id = ?", (rid,))[0]
        text = _pdf_text(os.path.join(app.config["DATA_DIR"], r["pdf_path"]))
        inv = t.s["inventory_no"]
        assert text.count(f"Teil von Set {inv}") == 3 and "Set-Prüfung: einsatzbereit" in text, text
        assert text.index("Set-Prüfung: einsatzbereit") < text.index(f"Teil von Set {inv}")
    print("Durchgang mit Set bestanden.")


def test_bericht_und_trennung():
    """Jahresbericht: eine Set-Sperre zählt einmal (am Anlass), Unvollständigkeit als Art „set“, die Freigabe einmal.
    Trennung: Set-Routen mit einem Set aus B antworten 404 wie unbekannt; der Rückruf nennt das Set."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, p = t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        eingangsgeprueft(t)
        jahr = _heute().year

        def sperren_bericht():
            return ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]["sperren"]
        vorher = sperren_bericht()
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz"}))
        b = sperren_bericht()
        assert b["gesamt"] == vorher["gesamt"] + 1, (vorher, b)
        set_pruefen(p, s, [k1])
        b2 = sperren_bericht()
        assert b2["gesamt"] == b["gesamt"] and b2["freigegeben"] == b["freigegeben"] + 1, (b, b2)
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": r1}))
        b3 = sperren_bericht()
        assert b3["gesamt"] == b2["gesamt"] + 1 and {a["art"]: a["n"] for a in b3["arten"]}["set"] == 1, b3
        # Trennung: ein Set aus B.
        sb = t.sb["id"]
        for methode, pfad, d in (("GET", f"/api/material/artikel/{sb}/set-lauf", None),
                                 ("POST", f"/api/material/artikel/{sb}/set-lauf", {}),
                                 ("DELETE", f"/api/material/artikel/{sb}/set-lauf", None),
                                 ("POST", f"/api/material/artikel/{sb}/teil-entnehmen", {"teil_id": t.teile_b[0]}),
                                 ("POST", f"/api/material/artikel/{sb}/teil-tauschen", {"teil_id": t.teile_b[0]}),
                                 ("POST", f"/api/material/artikel/{sb}/teil-einsetzen", {})):
            for c in (w, p):
                r = c.open(pfad, method=methode, headers=H, json=d)
                assert r.status_code == 404, (methode, pfad, r.status_code, r.get_json())
        # Rückruf am Produkt der Verbindungselemente: Die Liste nennt bei Teilen das Set (A17).
        r = ok(t.k["katalog"].post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe",
                                   json={"title": "Testrückruf", "mail": False}), 201)
        je = {a["id"]: a["set_inventar"] for a in r["rueckruf"]["artikel"]}
        assert je[k1] == je[k2] == t.s["inventory_no"] and je[t.f["id"]] is None, je
        # Lebenslauf-PDF des Sets enthält die Teil-Ereignisse mit lesbaren Beschriftungen.
        r = w.get(f"/material/artikel/{s}/lebenslauf.pdf")
        assert r.status_code == 200
    print("Jahresbericht und Trennung bei Sets bestanden.")


if __name__ == "__main__":
    test_kaskade()
    test_set_pruefung_freigabe()
    test_hinweis_tage()
    test_aussondern()
    test_tausch_entnahme_loeschen()
    test_durchgang_mit_set()
    test_bericht_und_trennung()
