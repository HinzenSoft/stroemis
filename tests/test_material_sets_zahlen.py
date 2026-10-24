"""Sets, Teil 2 – Zahlen, CSV-Spalten und gebündelte Mails (Phase 4 · L2b, KERN Z):
python tests/test_material_sets_zahlen.py  oder  pytest

Zählsatz „N Artikel, darunter k Teile in m Sets“ in Baum, Übersicht und Jahresbericht (Web und PDF) aus derselben
gefilterten Menge (Summe Bericht = Baum, auch gesperrt; fremde Gliederung und ausgesonderte zählen nicht), der Zusatz
„andere_set_status“ an Statuslisten, die drei Set-Spalten im CSV-Export (Stichtag wie „Status“, Formelvorsilbe, fehlende
Set-Zeile, Export → Bestandsimport), die Erinnerungsmails mit Set-Kopfzeile (Probe P-C, dringendste Stufe, Grenzen) und
die Mangel-Mail an einem nur mitgesperrten Artikel. Echte Mails gehen nie hinaus (mailprotokoll.versand ist ersetzt).

Alle Hersteller, Modelle, Nummern, Namen und Daten sind erfunden und nur für den Test da."""
import logging
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import _heute, neues_konto  # noqa: E402
from test_material_bericht import bericht, pdf_text  # noqa: E402
from test_material_erinnerung import (BASIS, T0, an, log, lauf, planen, post, ref, um, uhr,  # noqa: E402
                                      versand)
from test_material_export import csv_lesen  # noqa: E402
from test_material_import import ok, probelauf  # noqa: E402
from test_material_meine_psa import melden, post_mangel  # noqa: E402
from test_material_sets import set_aufbau, set_neu, stimmig  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post, sperren, zustand  # noqa: E402


# --- Hilfen -------------------------------------------------------------------------------------------------------------

def inv(app, iid):
    return zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (iid,))[0]["inventory_no"]


def alle_im_lager(t):
    """Set S, seine Teile, art_a und F – die Artikel in lager_a."""
    return [t.s["id"], *t.teile, t.art_a["id"], t.f["id"]]


def geprueft(app, ids, tage, h=None):
    """Zuletzt geprüft vor 30 Tagen, nächste Prüfung in tage Tagen (negativ: überfällig)."""
    h = h or _heute()
    for iid in ids:
        zustand(app, iid, last_inspected_on=(h - timedelta(days=30)).isoformat(),
                next_due_on=(h + timedelta(days=tage)).isoformat())


def knoten(c, fid):
    return next(x for x in ok(c.get("/api/material/ordner"))["ordner"] if x["id"] == fid)


# --- C. Zahlen ----------------------------------------------------------------------------------------------------------

def test_zaehlsatz():
    """Baum, Übersicht (/start) und Jahresbericht: m und k aus derselben gefilterten Menge – je Konto nur, was es sieht
    (die Gliederung B zählt für wart_a nicht), ohne ausgesonderte; Summe Bericht = Baum je Gliederung, auch wenn das Set
    gesperrt in „Gesperrt“ liegt (Bericht zählt nach Heimat, Baum nach Ordner). Der Satz steht in Web-Antwort und PDF
    nur, wenn es Sets gibt."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, adm = t.app, t.wart_a, t.adm
        j = _heute().year
        # Gliederung A: art_a, S mit drei Teilen, F → 6 Artikel, 3 Teile in 1 Set; B (wart_b) ebenso mit art_b, SB.
        a = knoten(w, t.a)
        assert a["bestand"] == 6 and a["bestand_sets"] == {"anzahl": 1, "teile": 3}, a
        assert knoten(w, t.lager_a)["bestand_sets"] == {"anzahl": 1, "teile": 3}
        assert t.b not in [x["id"] for x in ok(w.get("/api/material/ordner"))["ordner"]]
        start = ok(w.get("/api/material/start"))
        assert start["bestand"] == 6 and start["bestand_sets"] == {"anzahl": 1, "teile": 3}, start["bestand_sets"]
        zeile = next(x for x in start["ordner_uebersicht"] if x["id"] == t.a)
        assert zeile["bestand_sets"] == {"anzahl": 1, "teile": 3} and zeile["bestand"] == 6, zeile
        assert ok(adm.get("/api/material/start"))["bestand_sets"] == {"anzahl": 2, "teile": 6}
        # Ein Ordner ohne Sets trägt Nullen; der Bericht dort keinen Satz.
        leer = ok(w.post("/api/material/ordner", json={"name": "Leer Platzhalter", "parent_id": t.a}), 201)["ordner"]
        assert knoten(w, leer["id"])["bestand_sets"] == {"anzahl": 0, "teile": 0}
        assert bericht(w, leer["id"], jahr=j)["bestand"]["sets_satz"] is None
        # Bericht = Baum.
        b = bericht(w, t.a, jahr=j)["bestand"]
        assert b["bestand"] == a["bestand"] and b["sets"] == a["bestand_sets"], b
        assert b["sets_satz"] == "6 Artikel, darunter 3 Teile in 1 Set", b["sets_satz"]
        r, seiten = pdf_text(w, f"/material/ordner/{t.a}/bericht-{j}.pdf", os.path.join(tmp, "bericht.pdf"))
        text = " ".join(" ".join(seiten).split())
        assert "6 Artikel, darunter 3 Teile in 1 Set" in text, text[:2000]
        # Gesperrt: das Set liegt in „Gesperrt“ – Baum und Bericht zählen weiter gleich (und gleich viel).
        sperren(t.k["pruefer"], t.teile[0])
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item WHERE folder_id = ?", (t.sys_a["gesperrt"],))[0]["n"] == 4
        a = knoten(w, t.a)
        b = bericht(w, t.a, jahr=j)["bestand"]
        assert a["bestand_sets"] == b["sets"] == {"anzahl": 1, "teile": 3} and a["bestand"] == b["bestand"] == 6, (a, b)
        assert knoten(w, t.sys_a["gesperrt"])["bestand_sets"] == {"anzahl": 1, "teile": 3}
        # Ausgesondert (Set B mit allen Teilen – hier direkt gesetzt): zählt nicht mehr.
        ids_b = [t.sb["id"], *t.teile_b]
        sql(app, f"UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id IN ({','.join('?' * len(ids_b))})", ids_b)
        assert ok(adm.get("/api/material/start"))["bestand_sets"] == {"anzahl": 1, "teile": 3}
        bb = bericht(adm, t.b, jahr=j)["bestand"]
        assert bb["sets"] == {"anzahl": 0, "teile": 0} and bb["sets_satz"] is None, bb
        assert knoten(adm, t.b)["bestand_sets"] == {"anzahl": 0, "teile": 0}
    print("Zählsatz bestanden.")


def test_andere_set_status():
    """Statuslisten: Teile mit dem gefilterten Status in Sets mit anderem Set-Status – Zahl k und die Sets (Kennung,
    Inventarnummer), nur aus der gefilterten Menge; ohne Statusfilter (Ordner) None."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        s = t.s["id"]
        geprueft(app, alle_im_lager(t), 300)
        geprueft(app, [s], -5)                               # Set-Artikel überfällig, die Teile einsatzbereit
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        assert o["andere_set_status"] is None
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}?status=einsatzbereit"))["ordner"]
        assert s not in [x["id"] for x in o["artikel"]]
        assert o["andere_set_status"] == {"teile": 3, "sets_gesamt": 1,
                                          "sets": [{"id": s, "inventory_no": inv(app, s), "teile": 3,
                                                    "status": "ueberfaellig", "status_text": "überfällig"}]}, o
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}?status=ueberfaellig"))["ordner"]
        assert s in [x["id"] for x in o["artikel"]] and o["andere_set_status"]["teile"] == 0
        f = ok(w.get("/api/material/faellig?status=einsatzbereit"))
        assert f["andere_set_status"]["teile"] == 3 and [x["id"] for x in f["andere_set_status"]["sets"]] == [s], f
        # Fällige ohne Filter: Der Set-Status ist der schlechteste, ein Teil im Fälligen steckt also nie in einem Set mit
        # Status außerhalb (gesperrt sperrt alle Teile mit) – nichts. Mit „bald fällig“: zwei Teile in 10 Tagen.
        assert ok(w.get("/api/material/faellig"))["andere_set_status"]["teile"] == 0
        geprueft(app, t.teile[1:], 10)
        f = ok(w.get("/api/material/faellig?status=bald_faellig"))
        assert s not in [x["id"] for x in f["artikel"]] and f["andere_set_status"]["teile"] == 2, f["andere_set_status"]
        assert ok(w.get(f"/api/material/faellig?status=bald_faellig&ordner={t.lager_a}"))["andere_set_status"]["teile"] == 2
        assert w.get(f"/api/material/faellig?status=bald_faellig&ordner={t.lager_b}").status_code == 404
        # Gesperrt: alle Teile mitgesperrt – Set und Teile „gesperrt“, nichts mehr anders.
        sperren(t.k["pruefer"], t.teile[0])
        assert ok(w.get("/api/material/faellig?status=bald_faellig"))["andere_set_status"]["teile"] == 0
        f = ok(w.get("/api/material/faellig?status=gesperrt"))
        assert s in [x["id"] for x in f["artikel"]] and f["andere_set_status"]["teile"] == 0
        # Fremde Gliederung: wart_b sieht nur sein Set.
        geprueft(app, [t.sb["id"], *t.teile_b], 300)
        geprueft(app, [t.sb["id"]], -5)
        fb = ok(t.wart_b.get("/api/material/faellig?status=einsatzbereit"))["andere_set_status"]
        assert [x["id"] for x in fb["sets"]] == [t.sb["id"]] and fb["teile"] == 3, fb
        assert t.wart_b.get(f"/api/material/ordner/{t.lager_a}?status=einsatzbereit").status_code == 404
    print("Zusatz an Statuslisten bestanden.")


# --- D. CSV -------------------------------------------------------------------------------------------------------------

def test_csv_set_spalten():
    """Set (Inventarnummer), Set-Produkt, Set-Status: an Teilen ihr Set, an der Set-Zeile die eigenen Werte, sonst leer;
    Set-Status mit demselben Stichtag wie „Status“; ein Hersteller mit „=“ bekommt die Formelvorsilbe; fehlt die Set-Zeile
    in der Menge, bleiben die Spalten leer und das Protokoll nennt es; Export → Bestandsimport ignoriert die Spalten."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        s, (k1, k2, r1) = t.s["id"], t.teile
        geprueft(app, alle_im_lager(t), 300)
        geprueft(app, [k2], -2)
        sql(app, "UPDATE mat_product SET manufacturer = '=Platzhalterwerk' WHERE id = ?", (t.set_p,))
        kopf, rows = csv_lesen(ok_bytes(t.k["fuehrung"].get(f"/material/export/{t.lager_a}.csv")))
        i = kopf.index("Herkunftsordner")
        assert kopf[i + 1:i + 4] == ["Set (Inventarnummer)", "Set-Produkt", "Set-Status"], kopf
        je = {r["Inventarnummer"]: r for r in rows}
        s_inv = inv(app, s)
        for iid, status in ((s, "einsatzbereit"), (k1, "einsatzbereit"), (k2, "überfällig"), (r1, "einsatzbereit")):
            r = je[inv(app, iid)]
            assert r["Status"] == status, (iid, r)
            assert (r["Set (Inventarnummer)"], r["Set-Produkt"], r["Set-Status"]) == (
                s_inv, "'=Platzhalterwerk Testset Alpha", "überfällig"), r
        assert je[s_inv]["Hersteller"] == "'=Platzhalterwerk"
        for frei in (t.f["id"], t.art_a["id"]):
            r = je[inv(app, frei)]
            assert (r["Set (Inventarnummer)"], r["Set-Produkt"], r["Set-Status"]) == ("", "", ""), r
        # Fehlt die Set-Zeile in der Menge (verletzte Invariante): leer + Protokoll, nichts nachgeladen.
        with app.app_context():
            from app import db
            from app.material.services import export
            from app.material.services import status as st
            rows_db = db.query(export.ARTIKEL_SQL + "WHERE i.id IN (?, ?)", (k1, k2))
            meldungen = []
            h = logging.Handler()
            h.emit = lambda rec: meldungen.append(rec.getMessage())
            app.logger.addHandler(h)
            try:
                werte = export._set_spalten(rows_db, _heute(), st.schwelle_tage())
            finally:
                app.logger.removeHandler(h)
            assert werte == {} and any("fehlt in der Menge" in m and str(s) in m for m in meldungen), (werte, meldungen)
        # Export → Bestandsimport: die drei Spalten ignoriert, „Set (Inventarnummer)“ nie die „Bisherige Inventarnummer“.
        sql(app, "UPDATE mat_product SET manufacturer = 'Testwerk' WHERE id = ?", (t.set_p,))
        daten = ok_bytes(t.k["fuehrung"].get(f"/material/export/{t.lager_a}.csv"))
        b = ok(probelauf(w, t.lager_a, daten))
        zu = {x["titel"]: x["zuordnung"] for x in b["spalten"]}
        assert zu["Set (Inventarnummer)"] == zu["Set-Produkt"] == zu["Set-Status"] == "ignorieren", zu
        assert [tt for tt, f in zu.items() if f == "inventarnummer"] == ["Inventarnummer"], zu
        bisher = {z["bisherige_nummer"] for z in b["zeilen"]}
        assert bisher == {inv(app, x) for x in alle_im_lager(t)}, bisher
        with app.app_context():
            from app.material.services import bestandsimport
            for titel in ("Set (Inventarnummer)", "Set-Produkt", "Set-Status"):
                assert bestandsimport.erkennen(titel) == ("ignorieren", 0, False), titel
        assert stimmig(app)
    print("CSV-Spalten der Sets bestanden.")


def ok_bytes(r):
    assert r.status_code == 200, r.status_code
    return r.data


# --- E. Mails -----------------------------------------------------------------------------------------------------------

def mail_an(p, adresse):
    return {m.adresse: m for m in p.mails}[adresse]


def test_mails_probe_pc():
    """Probe P-C: K1 in 10 Tagen fällig, das Set selbst in 300 Tagen – K1 steht unter der Kopfzeile seines Sets
    (Inventarnummer, Produkt, Set-Fälligkeit, Link aufs Set), der Betreff zählt „1 Set“, die Zahl am Ordner eine Zeile;
    vermerkt wird nur K1. Dringendste Stufe: ein überfälliges Teil macht die Gruppe „überfällig“ (einmal gezählt),
    gemischt mit einem einzelnen Artikel „2 überfällig (davon 1 Set)“. Deine PSA ebenso, mit Link auf die Karte des Sets
    unter „Meine PSA“."""
    from app.material.services import erinnerung
    with ohne_post(), tempfile.TemporaryDirectory() as tmp, uhr(um(T0)):
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        s, (k1, k2, r1) = t.s["id"], t.teile
        geprueft(app, alle_im_lager(t), 300, T0)
        geprueft(app, [k1], 10, T0)
        s_inv, k1_inv = inv(app, s), inv(app, k1)
        faellig_k1 = (T0 + timedelta(days=10)).strftime("%d.%m.%Y")
        with versand(app):
            m = mail_an(planen(app), "wart@example.org")
            assert m.betreff == "strömis.de – Material: 1 Set in 30 Tagen fällig", m.betreff
            assert erinnerung.zahlen(m) == (1, 0, 0, 0)
            txt = m.text
            assert "OG Musterstadt / Lager Musterstadt (1)" in txt, txt
            block = txt.split("OG Musterstadt / Lager Musterstadt (1)\n")[1].split("\n\n")[0].splitlines()
            assert block[0] == f"  Set {s_inv}  Testwerk Testset Alpha – Set fällig am {faellig_k1} (in 10 Tagen)", block
            assert block[1].startswith(f"    {k1_inv}  Testwerk HMS Beta, SN SET-A-K1   fällig am {faellig_k1}"), block
            assert block[2] == f"    Set: {BASIS}/material/artikel/{s}", block
            assert block[3] == f"  Ordner: {BASIS}/material/ordner/{t.lager_a}", block
            with post() as liste:
                lauf(app)
            assert len(an(liste, "wart@example.org")) == 1
            assert {z["item_id"] for z in log(app) if z["konto_ref"] == ref(app, t.k["wart_id"])} == {k1}
            # Dringendste Stufe: K2 überfällig, R1 in 5 Tagen – die Gruppe zählt einmal als „überfällig“.
            geprueft(app, [k2], -3, T0)
            geprueft(app, [r1], 5, T0)
            m = mail_an(planen(app), "wart@example.org")
            assert m.betreff == "strömis.de – Material: 1 Set überfällig", m.betreff
            assert f"  Set {s_inv}  Testwerk Testset Alpha – Set überfällig (fällig war der " in m.text, m.text
            assert k1_inv not in m.text                      # schon gemeldet
            geprueft(app, [t.f["id"]], -1, T0)
            m = mail_an(planen(app), "wart@example.org")
            assert m.betreff == "strömis.de – Material: 2 überfällig (davon 1 Set)", m.betreff
            assert erinnerung.zahlen(m) == (2, 0, 0, 0) and "OG Musterstadt / Lager Musterstadt (2)" in m.text
            # Deine PSA: das Set einer Person zugeordnet (alle Teile mit).
            person, person_id = neues_konto(app, "psa_pc@example.org", name="Person Platzhalter", stufe=0)
            ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
            mp = mail_an(planen(app), "psa_pc@example.org")
            assert mp.betreff == "strömis.de – Deine PSA: 1 Set überfällig", mp.betreff
            assert erinnerung.zahlen(mp) == (0, 0, 0, 1)
            assert f"  Set {s_inv}  Testwerk Testset Alpha – Set überfällig" in mp.text, mp.text
            assert f"    Das Set in Meine PSA: {BASIS}/material/meine-psa/{s}" in mp.text
            assert f"Deine PSA im Überblick: {BASIS}/material/meine-psa" in mp.text
        assert stimmig(app)
    print("Mails mit Set-Kopfzeile (P-C) bestanden.")


def test_mails_grenze():
    """Ein Set mit 30 Teilen: an der Grenze eine Zeile, darunter höchstens MAIL_SET_TEILE_MAX Artikel, der Rest „… und n
    weitere Teile“; vermerkt wird alles. Mit MAIL_ARTIKEL_MAX = 1 steht nur das dringendere Set da, der einzelne Artikel
    als „… und 1 weitere in diesem Ordner“; „Deine PSA“ ebenso mit MAIL_PSA_MAX = 1."""
    from app.material.services import erinnerung
    with ohne_post(), tempfile.TemporaryDirectory() as tmp, uhr(um(T0)):
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        mv = t.k["katalog"]
        liste = ok(mv.post("/api/material/produkte", json={
            "category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Gross", "article_no": "TS-G",
            "material_kind": "textil", "lifetime_years": 10, "is_set": True, "bestandteile": [
                {"produkt_id": t.ids["hms"], "bezeichnung": "Verbindungselement", "anzahl": 15, "einzeln": True},
                {"produkt_id": t.rolle, "anzahl": 15, "einzeln": True, "austausch": "ja"}]}), 201)
        gross = liste["produkt"]["id"]
        g = set_neu(w, gross, t.lager_a, liste["produkt"]["bestandteile"], "SET-G-1",
                    [f"SET-G-K{n}" for n in range(30)])["artikel"]
        gid = g["id"]
        g_teile = [x["id"] for x in g["set"]["teile"]]
        assert len(g_teile) == 30
        geprueft(app, alle_im_lager(t) + [gid] + g_teile, 300, T0)
        geprueft(app, [gid] + g_teile, 3, T0)                # 31 Artikel in 3 Tagen
        geprueft(app, [t.f["id"]], 20, T0)                   # ein einzelner in 20 Tagen
        alt = (erinnerung.MAIL_ARTIKEL_MAX, erinnerung.MAIL_PSA_MAX)
        erinnerung.MAIL_ARTIKEL_MAX = erinnerung.MAIL_PSA_MAX = 1
        try:
            with versand(app):
                m = mail_an(planen(app), "wart@example.org")
                assert m.betreff == "strömis.de – Material: 1 Set in 7 Tagen fällig, 1 in 30 Tagen fällig", m.betreff
                txt = m.text
                block = txt.split("OG Musterstadt / Lager Musterstadt (2)\n")[1].split("\n\n")[0].splitlines()
                assert block[0].startswith(f"  Set {inv(app, gid)}  Testwerk Testset Gross – Set fällig am "), block
                assert block[1].startswith(f"    {inv(app, gid)}  Testwerk Testset Gross, SN SET-G-1   "), block
                teil_zeilen = [z for z in block if z.startswith("    ") and "SN SET-G-K" in z]
                assert len(teil_zeilen) == erinnerung.MAIL_SET_TEILE_MAX - 1, block
                assert f"    … und {31 - erinnerung.MAIL_SET_TEILE_MAX} weitere Teile" in block, block
                assert "  … und 1 weitere in diesem Ordner" in block and inv(app, t.f["id"]) not in txt, block
                # Deine PSA: Set und F einer Person – eine Zeile (das Set), der Rest gezählt.
                person, person_id = neues_konto(app, "psa_gr@example.org", name="Person Grenze", stufe=0)
                ok(w.put(f"/api/material/artikel/{gid}/zuordnung", json={"user_id": person_id}))
                ok(w.put(f"/api/material/artikel/{t.f['id']}/zuordnung", json={"user_id": person_id}))
                mp = mail_an(planen(app), "psa_gr@example.org")
                assert mp.betreff == "strömis.de – Deine PSA: 2 in 30 Tagen fällig (davon 1 Set)", mp.betreff
                assert "  … und 1 weitere – alle unter Meine PSA" in mp.text, mp.text
                assert f"    … und {31 - erinnerung.MAIL_SET_TEILE_MAX} weitere Teile" in mp.text
                with post():
                    lauf(app)
                gemeldet = {z["item_id"] for z in log(app) if z["konto_ref"] == ref(app, t.k["wart_id"])}
                assert gemeldet == {gid, *g_teile, t.f["id"]}, len(gemeldet)
                assert {z["item_id"] for z in log(app) if z["konto_ref"] == ref(app, person_id)} == {gid, *g_teile,
                                                                                                    t.f["id"]}
        finally:
            erinnerung.MAIL_ARTIKEL_MAX, erinnerung.MAIL_PSA_MAX = alt
        assert stimmig(app)
    print("Grenzen der Mails mit Sets bestanden.")


def test_mangel_mail_mitgesperrt():
    """Mangel an einem nur mitgesperrten Teil bzw. Set-Artikel (lock_cause „set“): Die Mail sagt, dass er bisher nur mit
    dem Set gesperrt war und jetzt einen eigenen Grund hat – nicht „war schon gesperrt (Mangel gemeldet …)“. An einem
    schon aus eigenem Grund gesperrten bleibt der bisherige Satz."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app = t.app
        s, (k1, k2, _) = t.s["id"], t.teile
        sperren(t.k["pruefer"], k1)
        assert zeilen(app, "SELECT lock_cause FROM mat_item WHERE id = ?", (k2,))[0]["lock_cause"] == "set"
        s_inv = inv(app, s)
        with post_mangel() as liste:
            r = melden(t.k["fuehrung"], k2)
            assert r.status_code == 201, r.get_json()
            wart = [x for x in liste if x[0] == "wart@example.org"]
            assert len(wart) == 1, liste
            _, betreff, text = wart[0]
            assert (f"Er war bisher nur mit dem Set {s_inv} gesperrt; jetzt ist er zusätzlich aus eigenem "
                    "Grund gesperrt (diese Meldung). Freigeben kann das Set nur ein Prüfer mit der Set-Prüfung.") in text, text
            assert "war schon gesperrt" not in text and f"Set {s_inv} mit allen Teilen gesperrt" in betreff, betreff
            assert zeilen(app, "SELECT lock_cause FROM mat_item WHERE id = ?", (k2,))[0]["lock_cause"] == "eigen"
            liste.clear()
            r = melden(t.k["fuehrung"], s)
            assert r.status_code == 201, r.get_json()
            text = [x for x in liste if x[0] == "wart@example.org"][0][2]
            assert (f"Das Set {s_inv} war schon gesperrt; der Set-Artikel selbst ist jetzt zusätzlich aus eigenem Grund "
                    "gesperrt (diese Meldung).") in text, text
            liste.clear()
            r = melden(t.k["fuehrung"], k1)                  # schon aus eigenem Grund gesperrt
            assert r.status_code == 201, r.get_json()
            text = [x for x in liste if x[0] == "wart@example.org"][0][2]
            assert "Er war schon gesperrt (" in text and "bisher nur mit" not in text, text
        assert stimmig(app)
    print("Mangel-Mail an mitgesperrten Artikeln bestanden.")


if __name__ == "__main__":
    test_zaehlsatz()
    test_andere_set_status()
    test_csv_set_spalten()
    test_mails_probe_pc()
    test_mails_grenze()
    test_mangel_mail_mitgesperrt()
