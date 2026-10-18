"""Personenzuordnung, Meldungen je Bereich und Löschkonzept (Phase 2 · Lieferung 1, Paket D):
python tests/test_material_zuordnung.py  oder  pytest tests/test_material_zuordnung.py

Nach dem Bauentwurf 8.3: Zuordnen, ändern, lösen und die Sammelaktion (ganz oder gar nicht) – nur, wer den Artikel
verwaltet, an jedes aktive Konto mit Namen; im Journal steht die Person nur als Kontoverweis. Die Personen eines
Ordners (für den Filter) nur mit Grundrecht. Meldungen sieht nur, wer Katalogpfleger, Verwaltung oder Melder ist oder
ihren Ordner sieht (6.x, 2.2). Beim Löschen eines Kontos räumt der Code vorher auf und schreibt das Journal (7.).

Was erst mit Paket A1R (Lesefelder zugeordnet/zugeordnet_name, Filter ?zugeordnet, CSV-Spalte, Lösen beim Aussondern,
Beschriftung im Lebenslauf) grün werden kann, steht in WARTET_AUF. Alle Namen, Hersteller und Nummern hier sind
erfunden und nur für den Test da."""
import json
import os
import re
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, freigeben, gliederung, katalog_grund, neuer_artikel,  # noqa: E402
                           neues_konto, pdf_seiten, pruef_formulare, starten, umgebung, unterschreiben)
from test_material_trennung import gleich_wie_unbekannt, sql, zeilen, zwei_gliederungen  # noqa: E402
from test_material_ueberblick import ordner_neu, sperren  # noqa: E402

ZU = "/api/material/artikel/{}/zuordnung"
SAMMEL = "/api/material/artikel/zuordnen"


@contextmanager
def post_der_meldungen():
    """Mails der Produktmeldungen direkt statt im Hintergrund und nur in eine Liste."""
    from app.material.services import meldung
    post = []
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or True
    try:
        yield post
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt


def aufbau(tmp):
    """Umgebung mit Katalog und Formularen, eine Gliederung (Standardfreigaben) mit Lager und drei Karabinern, dazu
    Personen ohne Modulzugang: zwei mit Namen, eine deaktivierte, eine ohne Namen. Liefert (app, k, ids, gid, system,
    lager, art, personen)."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    gid, system = gliederung(k["adm"])
    lager = ordner_neu(k["wart"], gid, "Lager")
    art = [neuer_artikel(k["wart"], ids["hms"], lager, serial_no=f"ZU-{n}")["id"] for n in (1, 2, 3)]
    p = {}
    for name, mail in (("Person Eins", "person1@example.org"), ("Person Zwei", "person2@example.org"),
                       ("Person Inaktiv", "inaktiv@example.org"), ("", "namenlos@example.org")):
        p[mail.split("@")[0]] = neues_konto(app, mail, name=name)[1]
    assert k["adm"].put(f"/api/admin/users/{p['inaktiv']}", json={"active": False}).status_code == 200
    return app, k, ids, gid, system, lager, art, p


def ref_von(app, uid):
    return zeilen(app, "SELECT mat_ref FROM users WHERE id = ?", (uid,))[0]["mat_ref"]


def journal_am(app, iid, *aktionen):
    return zeilen(app, f"SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action IN "
                       f"({','.join('?' * len(aktionen))}) ORDER BY id", (iid, *aktionen))


def zugeordnet(app, iid):
    return zeilen(app, "SELECT assigned_user_id FROM mat_item WHERE id = ?", (iid,))[0]["assigned_user_id"]


def _werte(daten):
    """Alle Werte eines JSON-Gebildes (verschachtelt) – für „keine Kontokennung im Journal“."""
    if isinstance(daten, dict):
        for v in daten.values():
            yield from _werte(v)
    elif isinstance(daten, list):
        for v in daten:
            yield from _werte(v)
    else:
        yield daten


def nur_verweis(eintrag, ref, namen=(), uid=None, **sonst):
    """Ein Journaleintrag am Artikel nennt die Person nur über ihren Verweis: genau {"konto": {"ref"}} (und, wo
    angegeben, die übrigen Felder) – kein Name, keine E-Mail, keine Kontokennung."""
    daten = json.loads(eintrag)
    assert daten == dict({"konto": {"ref": ref}}, **sonst), daten
    assert re.fullmatch(r"[0-9a-f]{32}", ref), ref
    for n in namen:
        assert n not in eintrag, (n, eintrag)
    assert "@" not in eintrag, eintrag
    if uid is not None:
        assert uid not in list(_werte(daten)) and str(uid) not in list(_werte(daten)), daten


# --- Zuordnen, ändern, lösen --------------------------------------------------------------------------------------

def test_zuordnen():
    """Zuordnen, ändern, lösen am einzelnen Artikel – nur der Verwalter, an jedes aktive Konto mit Namen (auch ohne
    Modulzugang). Inaktiv, ohne Namen und nicht vorhanden antworten gleich; ausgesonderte Artikel bekommen niemanden.
    Im Journal steht die Person nur als Kontoverweis, einmal je Änderung."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager, art, p = aufbau(tmp)
        w = k["wart"]
        a1, a2, a3 = art
        r = w.put(ZU.format(a1), json={"user_id": p["person1"]})
        assert r.status_code == 200 and r.json["artikel"]["id"] == a1, r.get_json()
        assert zugeordnet(app, a1) == p["person1"]
        ref1 = ref_von(app, p["person1"])           # seit dem ersten Eintrag gesetzt (journal.konto_ref)
        e = journal_am(app, a1, "zugeordnet")
        assert len(e) == 1 and e[0]["before_json"] is None and e[0]["user_name"] == "wart", e
        nur_verweis(e[0]["after_json"], ref1, ("Person Eins", "person1"), p["person1"])
        # Ändern: vorher das alte Konto, nachher das neue – wieder nur Verweise.
        r = w.put(ZU.format(a1), json={"user_id": str(p["person2"])})              # „7“ gilt wie 7
        assert r.status_code == 200 and zugeordnet(app, a1) == p["person2"], r.get_json()
        e = journal_am(app, a1, "zugeordnet")
        assert len(e) == 2, e
        ref2 = ref_von(app, p["person2"])
        assert ref2 != ref1
        nur_verweis(e[1]["before_json"], ref1, ("Person Eins",), p["person1"])
        nur_verweis(e[1]["after_json"], ref2, ("Person Zwei",), p["person2"])
        # Dieselbe Person noch einmal: nichts geändert, kein Eintrag.
        assert w.put(ZU.format(a1), json={"user_id": float(p["person2"])}).status_code == 200
        assert len(journal_am(app, a1, "zugeordnet", "zuordnung_geloest")) == 2
        # Lösen.
        r = w.put(ZU.format(a1), json={"user_id": None})
        assert r.status_code == 200 and zugeordnet(app, a1) is None, r.get_json()
        e = journal_am(app, a1, "zuordnung_geloest")
        assert len(e) == 1 and e[0]["before_json"] is None, e
        nur_verweis(e[0]["after_json"], ref2, ("Person Zwei",), p["person2"])
        assert w.put(ZU.format(a1), json={"user_id": None}).status_code == 200          # schon gelöst: kein Eintrag
        assert len(journal_am(app, a1, "zugeordnet", "zuordnung_geloest")) == 3

        # Eingaben: Person fehlt, Unsinn, nicht vorhanden – inaktiv und ohne Namen antworten wie nicht vorhanden.
        assert w.put(ZU.format(a2), json={}).status_code == 400
        assert w.put(ZU.format(a2), json={"user_id": "abc"}).status_code == 400
        assert w.put(ZU.format(a2), json={"user_id": True}).status_code == 400
        unbekannt = w.put(ZU.format(a2), json={"user_id": 999999})
        assert unbekannt.status_code == 404 and unbekannt.json["error"] == "Konto nicht gefunden.", unbekannt.get_json()
        for uid in (p["inaktiv"], p["namenlos"], str(p["inaktiv"]), float(p["namenlos"])):
            gleich_wie_unbekannt(w.put(ZU.format(a2), json={"user_id": uid}), unbekannt)
        assert zugeordnet(app, a2) is None

        # Rechte: nur wer den Artikel verwaltet. Führungskraft und Prüfer sehen ihn (403), wer keinen Modulzugang hat,
        # erfährt das (403), ohne Anmeldung 401.
        for wer in ("fuehrung", "pruefer", "katalog"):
            r = k[wer].put(ZU.format(a2), json={"user_id": p["person1"]})
            assert r.status_code == 403 and "Materialwarte" in r.json["error"], (wer, r.get_json())
        r = k["nutzer"].put(ZU.format(a2), json={"user_id": p["person1"]})
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        assert app.test_client().put(ZU.format(a2), json={"user_id": p["person1"]}, headers=H).status_code == 401
        assert w.put(ZU.format(999999), json={"user_id": p["person1"]}).status_code == 404
        # Die Verwaltung darf überall.
        assert k["adm"].put(ZU.format(a2), json={"user_id": p["person1"]}).status_code == 200
        assert zugeordnet(app, a2) == p["person1"]

        # Gesperrt: zuordnen geht (die PSA gehört weiter der Person). Ausgesondert: 409, lösen geht.
        sperren(k["pruefer"], a3)
        assert w.put(ZU.format(a3), json={"user_id": p["person1"]}).status_code == 200
        assert w.post(f"/api/material/artikel/{a3}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        sql(app, "UPDATE mat_item SET assigned_user_id = NULL WHERE id = ?", (a3,))   # löst ab Paket A1R das Aussondern
        r = w.put(ZU.format(a3), json={"user_id": p["person2"]})
        assert r.status_code == 409 and "Ausgesondert" in r.json["error"], r.get_json()
        assert zugeordnet(app, a3) is None
        sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ?", (p["person2"], a3))      # Altbestand
        assert w.put(ZU.format(a3), json={"user_id": None}).status_code == 200 and zugeordnet(app, a3) is None
        # Ein später deaktiviertes Konto: Die Zuordnung bleibt.
        assert k["adm"].put(f"/api/admin/users/{p['person1']}", json={"active": False}).status_code == 200
        assert zugeordnet(app, a2) == p["person1"]
    print("Zuordnen bestanden.")


def test_sammelaktion():
    """POST /artikel/zuordnen: ganz oder gar nicht. Ein fremder oder unbekannter Artikel → 404 (gleich), ein
    ausgesonderter → 409, ohne Verwalten → 403; dabei ändert sich nichts. Kennungen wie im Dienst („7“, 7.0)."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, ids = t.app, t.wart_a, t.ids
        _, person = neues_konto(app, "person@example.org", name="Person Sammel")
        a = [t.art_a["id"]] + [neuer_artikel(w, ids["hms"], t.lager_a, serial_no=f"SA-{n}")["id"] for n in (1, 2)]
        weg = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="SA-9")["id"]
        sperren(t.k["pruefer"], weg)
        assert w.post(f"/api/material/artikel/{weg}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        journal = zeilen(app, "SELECT COUNT(*) AS n FROM mat_audit")[0]["n"]

        def stand():
            return [zugeordnet(app, i) for i in a + [t.art_b["id"]]]
        r = w.post(SAMMEL, json={"ids": [a[0], str(a[1]), float(a[2])], "user_id": person})
        assert r.status_code == 200 and r.json == {"geaendert": 3}, r.get_json()
        assert stand() == [person, person, person, None]
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_audit")[0]["n"] == journal + 3
        # Noch einmal: nichts zu tun. Doppelte Kennungen zählen einmal.
        assert w.post(SAMMEL, json={"ids": [a[0], a[0]], "user_id": person}).json == {"geaendert": 0}
        # Ganz oder gar nicht: fremd wie unbekannt, ausgesondert 409 – nichts geändert.
        unbekannt = w.post(SAMMEL, json={"ids": [a[0], 999999], "user_id": None})
        assert unbekannt.status_code == 404 and unbekannt.json["error"] == "Artikel nicht gefunden.", unbekannt.get_json()
        for fremd in (t.art_b["id"], str(t.art_b["id"]), float(t.art_b["id"])):
            gleich_wie_unbekannt(w.post(SAMMEL, json={"ids": [a[0], fremd], "user_id": None}), unbekannt)
        r = w.post(SAMMEL, json={"ids": [a[0], weg], "user_id": t.wart_b_id})
        assert r.status_code == 409, r.get_json()
        assert stand() == [person, person, person, None]
        # Ein fremder Artikel antwortet 404, auch wenn die Person nicht taugt – erst die Artikel, dann die Person.
        gleich_wie_unbekannt(w.post(SAMMEL, json={"ids": [t.art_b["id"]], "user_id": 999999}), unbekannt)
        r = w.post(SAMMEL, json={"ids": [a[0]], "user_id": 999999})
        assert r.status_code == 404 and r.json["error"] == "Konto nicht gefunden.", r.get_json()
        # Eingaben: leer, zu viele, keine Liste, Unsinn.
        for falsch in ({"user_id": None}, {"ids": [], "user_id": None}, {"ids": list(range(1, 502)), "user_id": None},
                       {"ids": a[0], "user_id": None}, {"ids": ["abc"], "user_id": None}, {"ids": [a[0]]}):
            assert w.post(SAMMEL, json=falsch).status_code == 400, falsch
        # Rechte: wer nirgends verwaltet 403; wer B verwaltet, sieht A nicht (404); ohne Modulzugang 403.
        r = t.k["fuehrung"].post(SAMMEL, json={"ids": [a[0]], "user_id": None})
        assert r.status_code == 403 and r.json["error"], r.get_json()
        gleich_wie_unbekannt(t.wart_b.post(SAMMEL, json={"ids": [a[0]], "user_id": None}),
                             t.wart_b.post(SAMMEL, json={"ids": [999999], "user_id": None}))
        assert t.k["nutzer"].post(SAMMEL, json={"ids": [a[0]], "user_id": None}).status_code == 403
        assert stand() == [person, person, person, None]
        # An eine Person aus der anderen Gliederung zuordnen geht (jedes aktive Konto mit Namen) – und lösen.
        assert w.post(SAMMEL, json={"ids": a[:2], "user_id": t.wart_b_id}).json == {"geaendert": 2}
        assert w.post(SAMMEL, json={"ids": a, "user_id": None}).json == {"geaendert": 3}
        assert stand() == [None, None, None, None]
        e = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND action IN ('zugeordnet', 'zuordnung_geloest') "
                        "ORDER BY id")
        assert len(e) == 8 and all("Sammel" not in (x["after_json"] or "") + (x["before_json"] or "") for x in e), e
    print("Sammelaktion bestanden.")


def test_zugeordnete():
    """GET /ordner/<fid>/zugeordnete: Personen mit Zuordnungen im Zweig (über die Heimat, also auch gesperrte Artikel
    im Systemordner), je mit Zahl und „aktiv“ – nur mit Grundrecht: Prüfsicht 403, Fremdes 404 wie Unbekanntes."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, ids = t.app, t.wart_a, t.ids
        _, eins = neues_konto(app, "eins@example.org", name="Anna Eins")
        _, zwei = neues_konto(app, "zwei@example.org", name="Bert Zwei")
        fach = ordner_neu(w, t.lager_a, "Fach")
        a_fach = neuer_artikel(w, ids["hms"], fach, serial_no="ZG-1")["id"]
        a_gesperrt = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="ZG-2")["id"]
        a_halle = neuer_artikel(w, ids["hms"], ordner_neu(w, t.a, "Halle"), serial_no="ZG-3")["id"]
        for iid, uid in ((t.art_a["id"], eins), (a_fach, eins), (a_gesperrt, zwei), (a_halle, zwei)):
            assert w.put(ZU.format(iid), json={"user_id": uid}).status_code == 200
        assert t.wart_b.put(ZU.format(t.art_b["id"]), json={"user_id": eins}).status_code == 200
        sperren(t.k["pruefer"], a_gesperrt)                      # liegt jetzt in „Gesperrt“, Heimat bleibt das Lager
        r = w.get(f"/api/material/ordner/{t.lager_a}/zugeordnete")
        assert r.status_code == 200, r.get_json()
        assert r.json["zugeordnete"] == [{"id": eins, "name": "Anna Eins", "anzahl": 2, "aktiv": True},
                                         {"id": zwei, "name": "Bert Zwei", "anzahl": 1, "aktiv": True}], r.json
        assert [(x["id"], x["anzahl"]) for x in w.get(f"/api/material/ordner/{t.a}/zugeordnete").json["zugeordnete"]] \
            == [(eins, 2), (zwei, 2)]
        assert w.get(f"/api/material/ordner/{fach}/zugeordnete").json["zugeordnete"][0]["anzahl"] == 1
        # In B nur die eigene Zuordnung von B – die Zuordnung an „eins“ aus A zählt dort nicht mit.
        assert t.wart_b.get(f"/api/material/ordner/{t.b}/zugeordnete").json["zugeordnete"] == [
            {"id": eins, "name": "Anna Eins", "anzahl": 1, "aktiv": True}]
        # Deaktiviert: steht weiter da, mit aktiv false.
        assert t.adm.put(f"/api/admin/users/{zwei}", json={"active": False}).status_code == 200
        assert w.get(f"/api/material/ordner/{t.a}/zugeordnete").json["zugeordnete"][1]["aktiv"] is False
        # Rechte: Führungskraft liest (Grundrecht), die Prüfsicht nicht, Fremdes wie Unbekanntes.
        assert t.k["fuehrung"].get(f"/api/material/ordner/{t.lager_a}/zugeordnete").status_code == 200
        ext, ext_id = neues_konto(app, "extern@example.org", name="Externer Prüfer", mat_pruefer=True,
                                  urkundennummer="1012-8001")
        freigeben(t.adm, t.lager_a, ext_id, "pruefen")
        r = ext.get(f"/api/material/ordner/{t.lager_a}/zugeordnete")
        assert r.status_code == 403 and "Prüffreigabe allein" in r.json["error"], r.get_json()
        gleich_wie_unbekannt(w.get(f"/api/material/ordner/{t.lager_b}/zugeordnete"),
                             w.get("/api/material/ordner/999999/zugeordnete"))
        gleich_wie_unbekannt(ext.get(f"/api/material/ordner/{t.a}/zugeordnete"),
                             ext.get("/api/material/ordner/999999/zugeordnete"))
        assert t.k["nutzer"].get(f"/api/material/ordner/{t.a}/zugeordnete").status_code == 403
    print("Zugeordnete eines Ordners bestanden.")


def test_lebenslauf_ohne_namen():
    """Der Lebenslauf (zur Weitergabe gedacht) nennt die zugeordnete Person nie – weder Namen noch E-Mail."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager, art, p = aufbau(tmp)
        w = k["wart"]
        assert w.put(ZU.format(art[0]), json={"user_id": p["person1"]}).status_code == 200
        assert w.put(ZU.format(art[0]), json={"user_id": p["person2"]}).status_code == 200
        r = w.get(f"/material/artikel/{art[0]}/lebenslauf.pdf")
        assert r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(pdf_seiten(pfad)).split())
        for verboten in ("Person Eins", "Person Zwei", "person1", "person2"):
            assert verboten not in text, (verboten, text[:2000])
    print("Lebenslauf ohne Namen bestanden.")


# --- Meldungen je Bereich -----------------------------------------------------------------------------------------

def test_meldungen_je_bereich():
    """Meldungen sieht nur, wer Katalogpfleger oder Verwaltung ist, sie gemacht hat oder ihren Ordner sieht – in der
    Liste, in der Zahl der offenen und beim Lesen (sonst 404 wie unbekannt). Den Ordnerpfad zeigt eine Meldung nur, wer
    den Ordner sieht; sonst nur die Gliederung – auch in der Mail an die Katalogpfleger."""
    with post_der_meldungen() as post, tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, kp, f = t.app, t.wart_a, t.k["katalog"], t.k["fuehrung"]

        def melden(c, modell, **felder):
            r = c.post("/api/material/meldungen", headers=H, json=dict({"manufacturer": "Meldewerk", "model": modell},
                                                                       **felder))
            assert r.status_code == 201, r.get_json()
            return r.json["meldung"]
        m_a = melden(w, "Testmodell A", folder_id=t.lager_a)
        post.clear()
        m_b = melden(t.wart_b, "Testmodell B", folder_id=t.lager_b, note="Notiz Nachbarstadt")
        m_ohne = melden(t.adm, "Testmodell ohne Ordner")
        # Die Mail an die Katalogpfleger nennt nur die Gliederung.
        an_kp = [x for x in post if x[0] == "katalog@example.org" and "Testmodell B" in x[1]]
        assert len(an_kp) == 1 and "Für:            OG Nachbarstadt\n" in an_kp[0][2], post
        assert "Lager Nachbarstadt" not in an_kp[0][2], an_kp[0][2]
        # Der Melder sieht den Pfad seines Ordners.
        assert m_b["ordner"] == {"id": t.lager_b, "pfad": "OG Nachbarstadt / Lager Nachbarstadt"}, m_b["ordner"]

        def ids_(c, **q):
            r = c.get("/api/material/meldungen", query_string=q)
            assert r.status_code == 200, r.get_json()
            return [m["id"] for m in r.json["meldungen"]], r.json
        # Katalogpflege und Verwaltung: alle; offen zählt alle.
        for c in (kp, t.adm):
            liste, j = ids_(c)
            assert liste == [m_a["id"], m_b["id"], m_ohne["id"]] and j["offen"] == 3, j
        assert kp.get("/api/material/start").json["meldungen_offen"] == 3
        # Führungskraft von A: nur die aus A – auch in der Zahl.
        liste, j = ids_(f)
        assert liste == [m_a["id"]] and j["offen"] == 1 and j["alle"], j
        # Materialwart von A: standardmäßig die eigenen, mit eigene=0 alle, die er sieht – nicht B, nicht die ohne Ordner.
        assert ids_(w)[0] == [m_a["id"]]
        liste, j = ids_(w, eigene="0")
        assert liste == [m_a["id"]] and j["offen"] == 1, j
        for status in ("alle", "erledigt"):
            assert m_b["id"] not in ids_(w, eigene="0", status=status)[0]
        # Materialwart von B entsprechend.
        assert ids_(t.wart_b, eigene="0")[0] == [m_b["id"]]
        # Lesen: Fremdes wie Unbekanntes; der Melder, Katalogpflege und Verwaltung lesen.
        unbekannt = w.get("/api/material/meldungen/999999")
        assert unbekannt.status_code == 404 and unbekannt.json["error"] == "Meldung nicht gefunden."
        for mid in (m_b["id"], m_ohne["id"]):
            gleich_wie_unbekannt(w.get(f"/api/material/meldungen/{mid}"), unbekannt)
            gleich_wie_unbekannt(f.get(f"/api/material/meldungen/{mid}"), unbekannt)
        assert w.get(f"/api/material/meldungen/{m_a['id']}").status_code == 200
        assert f.get(f"/api/material/meldungen/{m_a['id']}").status_code == 200
        assert t.adm.get(f"/api/material/meldungen/{m_ohne['id']}").status_code == 200
        # Wer den Ordner nicht sieht (Katalogpflege ohne Freigabe in B), liest nur die Gliederung.
        r = kp.get(f"/api/material/meldungen/{m_b['id']}")
        assert r.status_code == 200 and r.json["meldung"]["ordner"] == {"gliederung": "OG Nachbarstadt"}, r.get_json()
        assert "Lager Nachbarstadt" not in r.get_data(as_text=True)
        assert {m["id"]: m["ordner"] for m in kp.get("/api/material/meldungen").json["meldungen"]}[m_b["id"]] == \
            {"gliederung": "OG Nachbarstadt"}
        assert t.adm.get(f"/api/material/meldungen/{m_b['id']}").json["meldung"]["ordner"]["pfad"] == \
            "OG Nachbarstadt / Lager Nachbarstadt"
        # Verliert der Melder seine Freigabe, liest er seine Meldung weiter – nur noch mit der Gliederung.
        sql(app, "DELETE FROM mat_folder_grant WHERE user_id = ?", (t.wart_b_id,))
        r = t.wart_b.get(f"/api/material/meldungen/{m_b['id']}")
        assert r.status_code == 200 and r.json["meldung"]["ordner"] == {"gliederung": "OG Nachbarstadt"}, r.get_json()
        assert r.json["meldung"]["eigen"] is True
        assert t.wart_b.get("/api/material/meldungen").status_code == 403          # ohne Modulzugang keine Liste
        # Ohne Anmeldung nichts.
        assert app.test_client().get(f"/api/material/meldungen/{m_a['id']}").status_code == 401
    print("Meldungen je Bereich bestanden.")


# --- Löschkonzept -------------------------------------------------------------------------------------------------

def _ohne_kennung(rows):
    """mat_audit-Zeilen ohne user_id – die setzt die Datenbank beim Löschen eines Kontos auf NULL."""
    return [{k_: v for k_, v in r.items() if k_ != "user_id"} for r in rows]


def test_loeschkonzept():
    """Ein Konto mit Freigaben (auch einer abgelaufenen), Zuordnungen, einem Entwurf, einer festgeschriebenen Prüfung,
    Meldungen (gemacht und bearbeitet) und Suchprotokoll wird gelöscht. Danach: Freigaben weg (mit Journal), Zuordnungen
    gelöst (mit Journal), der Entwurf ohne Namen und ohne Urkundennummer, die festgeschriebene Prüfung unverändert,
    Meldungen und Suchprotokoll ohne Namen; das Journal ist nur gewachsen; der Kontoverweis ist unauflösbar.
    material-folgen hat vorher richtig gezählt. Bricht das Löschen ab, bleibt alles stehen."""
    with post_der_meldungen(), tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager, art, p = aufbau(tmp)
        adm, w = k["adm"], k["wart"]
        geht, uid = neues_konto(app, "geht@example.org", name="Person Geht", mat_pruefer=True, mat_katalog=True,
                                urkundennummer="1012-0999")
        fach = ordner_neu(w, lager, "Fach")
        g_lesen = freigeben(adm, gid, uid, "lesen")
        g_pruefen = freigeben(adm, gid, uid, "pruefen")
        g_verwalten = freigeben(adm, fach, uid, "verwalten")
        g_alt = freigeben(adm, lager, uid, "pruefen", bis=_heute() - timedelta(days=3))   # abgelaufen
        unterschreiben(geht)
        a1, a2, a3 = art
        a4 = neuer_artikel(w, ids["hms"], fach, serial_no="ZU-4")["id"]
        for iid in (a1, a2):
            assert w.put(ZU.format(iid), json={"user_id": uid}).status_code == 200
        assert w.put(ZU.format(a3), json={"user_id": p["person1"]}).status_code == 200      # bleibt
        entwurf = starten(geht, a3).json["pruefung"]["id"]
        fest = starten(geht, a4).json["pruefung"]["id"]
        assert festschreiben(geht, fest, ergebnis="einsatzbereit").status_code == 200
        r = geht.post("/api/material/meldungen", headers=H, json={"manufacturer": "Meldewerk", "model": "Von Geht",
                                                                  "folder_id": fach})
        assert r.status_code == 201, r.get_json()
        m_eigen = r.json["meldung"]["id"]
        m_wart = w.post("/api/material/meldungen", headers=H, json={"manufacturer": "Meldewerk", "model": "Vom Wart"}
                        ).json["meldung"]["id"]
        assert geht.post(f"/api/material/meldungen/{m_wart}/ablehnen", json={"antwort": "Testablehnung"},
                         headers=H).status_code == 200
        with app.test_request_context():
            from flask import g
            from app import db
            from app.material.services import globalprotokoll
            g.user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
            such = globalprotokoll.eintragen("suche", "TEST-SERIE-0001", [])

        # Was das Löschen bewirkt – nur für die Verwaltung.
        r = adm.get(f"/api/admin/users/{uid}/material-folgen")
        assert r.status_code == 200 and r.json == {"freigaben": 4, "zuordnungen": 2, "entwuerfe": 1, "pruefungen": 1}, \
            r.get_json()
        assert w.get(f"/api/admin/users/{uid}/material-folgen").status_code == 403
        assert adm.get("/api/admin/users/999999/material-folgen").status_code == 404
        # Deaktivieren ändert im Modul nichts.
        assert adm.put(f"/api/admin/users/{uid}", json={"active": False}).status_code == 200
        assert adm.get(f"/api/admin/users/{uid}/material-folgen").json["zuordnungen"] == 2
        assert zugeordnet(app, a1) == uid
        assert adm.put(f"/api/admin/users/{uid}", json={"active": True}).status_code == 200

        ref = ref_von(app, uid)
        vorher = zeilen(app, "SELECT * FROM mat_audit ORDER BY id")
        freigaben = {r_["id"]: r_ for r_ in zeilen(app, "SELECT * FROM mat_folder_grant WHERE user_id = ?", (uid,))}
        assert set(freigaben) == {g_lesen, g_pruefen, g_verwalten, g_alt}
        fest_vorher = zeilen(app, "SELECT * FROM mat_inspection WHERE id = ?", (fest,))[0]
        assert fest_vorher["inspector_name"] == "Person Geht" and fest_vorher["inspector_certificate"] == "1012-0999"
        admin_name = zeilen(app, "SELECT name FROM users WHERE email = 'admin@example.org'")[0]["name"]

        # Bricht das Löschen ab (hier: ein Trigger, der das DELETE verweigert), bleibt alles stehen.
        sql(app, f"CREATE TRIGGER test_nicht_loeschen BEFORE DELETE ON users WHEN OLD.id = {int(uid)} "
                 "BEGIN SELECT RAISE(ABORT, 'Test: nicht löschen'); END")
        try:
            r = adm.delete(f"/api/admin/users/{uid}", headers=H)
            assert r.status_code >= 400, r.status_code
        except sqlite3.IntegrityError:
            pass
        sql(app, "DROP TRIGGER test_nicht_loeschen")
        assert zeilen(app, "SELECT * FROM mat_audit ORDER BY id") == vorher
        assert len(zeilen(app, "SELECT id FROM mat_folder_grant WHERE user_id = ?", (uid,))) == 4
        assert zugeordnet(app, a1) == uid and ref_von(app, uid) == ref

        # Löschen.
        assert adm.delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        assert not zeilen(app, "SELECT 1 FROM users WHERE id = ?", (uid,))
        assert adm.get(f"/api/admin/users/{uid}/material-folgen").status_code == 404
        # Freigaben weg – je Zeile ein Eintrag am Ordner, vorher die Freigabe (mit Verweis), nachher der Grund.
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE user_id = ?", (uid,))
        neu = zeilen(app, "SELECT * FROM mat_audit WHERE id > ? ORDER BY id", (vorher[-1]["id"],))
        entfernt = [e for e in neu if e["action"] == "freigabe_entfernt"]
        assert len(entfernt) == 4, neu
        for e in entfernt:
            v = json.loads(e["before_json"])
            f_ = freigaben[v["freigabe"]]
            assert e["entity"] == "folder" and e["entity_id"] == f_["folder_id"] and e["user_name"] == admin_name, e
            assert v == {"freigabe": f_["id"], "konto": {"ref": ref}, "recht": f_["permission"],
                         "bis": f_["valid_until"]}, v
            assert json.loads(e["after_json"]) == {"grund": "Konto gelöscht"}, e
        # Zuordnungen gelöst – je Artikel ein Eintrag mit Verweis und Grund; die andere bleibt.
        assert [zugeordnet(app, i) for i in (a1, a2, a3)] == [None, None, p["person1"]]
        geloest = [e for e in neu if e["action"] == "zuordnung_geloest"]
        assert sorted(e["entity_id"] for e in geloest) == [a1, a2] and all(e["entity"] == "item" for e in geloest)
        for e in geloest:
            assert e["before_json"] is None
            nur_verweis(e["after_json"], ref, ("Person Geht", "geht"), uid, grund="Konto gelöscht")
        assert {e["action"] for e in neu} == {"freigabe_entfernt", "zuordnung_geloest"}, neu
        # Der Entwurf: ohne Namen, ohne Urkundennummer, ohne Kennung – eine Reservierung, die der Materialwart freigibt.
        x = zeilen(app, "SELECT * FROM mat_inspection WHERE id = ?", (entwurf,))[0]
        assert (x["inspector_name"], x["inspector_certificate"], x["inspector_user_id"]) == ("(gelöschtes Konto)", "", None)
        r = w.delete(f"/api/material/pruefungen/{entwurf}", headers=H)
        assert r.status_code == 200, r.get_json()
        # Die festgeschriebene Prüfung bleibt, wie sie war (Name, Urkunde – EN 365); nur die Kennung ist weg.
        x = zeilen(app, "SELECT * FROM mat_inspection WHERE id = ?", (fest,))[0]
        assert x["inspector_user_id"] is None and dict(x, inspector_user_id=uid) == fest_vorher, x
        # Meldungen und Suchprotokoll ohne Namen.
        m = {r_["id"]: r_ for r_ in zeilen(app, "SELECT * FROM mat_product_request WHERE id IN (?, ?)", (m_eigen, m_wart))}
        assert (m[m_eigen]["created_by_name"], m[m_eigen]["created_by"]) == ("(gelöschtes Konto)", None), m[m_eigen]
        assert (m[m_wart]["resolved_by_name"], m[m_wart]["resolved_by"]) == ("(gelöschtes Konto)", None), m[m_wart]
        assert m[m_wart]["created_by_name"] == "wart"
        s = zeilen(app, "SELECT * FROM mat_global_search WHERE id = ?", (such,))[0]
        assert (s["user_name"], s["user_id"]) == ("(gelöschtes Konto)", None), s
        # Das Journal ist nur gewachsen: Was vorher stand, steht noch – nur die Kontokennung ist auf NULL.
        nachher = zeilen(app, "SELECT * FROM mat_audit ORDER BY id")
        assert _ohne_kennung(nachher[:len(vorher)]) == _ohne_kennung(vorher)
        assert not any(r_["user_id"] == uid for r_ in nachher)
        assert any(r_["user_name"] == "Person Geht" for r_ in nachher)              # als Handelnder bleibt er
        # Der Verweis führt nirgends mehr hin – und stand nie in einem Eintrag am Konto.
        with app.app_context():
            from app.material.services import journal
            assert journal.konto_name(ref) == "(gelöschtes Konto)"
        assert not zeilen(app, "SELECT 1 FROM users WHERE mat_ref = ?", (ref,))
        assert not [r_ for r_ in nachher if r_["entity"] == "user"
                    and ref in (r_["before_json"] or "") + (r_["after_json"] or "")]
        assert [r_ for r_ in nachher if r_["entity"] == "user" and r_["entity_id"] == uid]   # die Einträge bleiben
    print("Löschkonzept bestanden.")


# --- Tests, die erst mit einem anderen Paket grün werden ------------------------------------------------------------

def test_anzeige_und_filter_a1r():
    """6.3 mit Paket A1R: Mit Grundrecht steht die Person am Artikel (zugeordnet, auch deaktiviert) und in Listen
    (zugeordnet_name); in der Prüfsicht null. Filter ?zugeordnet in Ordner und Fällig, CSV mit „Zugeordnet an“, im
    Lebenslauf „Zuordnung geändert“ ohne Namen."""
    import csv
    import io
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager, art, p = aufbau(tmp)
        w = k["wart"]
        for iid in art[:2]:
            assert w.put(ZU.format(iid), json={"user_id": p["person1"]}).status_code == 200
        r = w.put(ZU.format(art[0]), json={"user_id": p["person2"]})
        assert r.json["artikel"]["zugeordnet"] == {"id": p["person2"], "name": "Person Zwei", "gliederung": "",
                                                   "aktiv": True}, r.json["artikel"]
        a = k["fuehrung"].get(f"/api/material/artikel/{art[1]}").json["artikel"]
        assert a["zugeordnet"]["name"] == "Person Eins", a["zugeordnet"]
        ext, ext_id = neues_konto(app, "extern@example.org", name="Externer Prüfer", mat_pruefer=True,
                                  urkundennummer="1012-8001")
        freigeben(k["adm"], lager, ext_id, "pruefen")
        a = ext.get(f"/api/material/artikel/{art[1]}").json["artikel"]
        assert a["zugeordnet"] is None and a["journal"] is None, a
        assert "Person Eins" not in ext.get(f"/api/material/ordner/{lager}").get_data(as_text=True)
        zeilen_ = {x["id"]: x for x in w.get(f"/api/material/ordner/{lager}").json["ordner"]["artikel"]}
        assert (zeilen_[art[0]]["zugeordnet_name"], zeilen_[art[2]]["zugeordnet_name"]) == ("Person Zwei", None)
        r = w.get(f"/api/material/ordner/{lager}", query_string={"zugeordnet": p["person1"]})
        assert [x["id"] for x in r.json["ordner"]["artikel"]] == [art[1]], r.get_json()
        r = w.get("/api/material/faellig", query_string={"zugeordnet": p["person1"]})
        assert [x["id"] for x in r.json["artikel"]] == [art[1]], r.get_json()
        text = w.get(f"/material/export/{lager}.csv").data.decode("utf-8-sig")
        zeilen_ = list(csv.DictReader(io.StringIO(text, newline=""), delimiter=";"))
        assert {z["Zugeordnet an"] for z in zeilen_} == {"Person Zwei", "Person Eins", ""}, zeilen_
        assert k["adm"].put(f"/api/admin/users/{p['person2']}", json={"active": False}).status_code == 200
        assert w.get(f"/api/material/artikel/{art[0]}").json["artikel"]["zugeordnet"]["aktiv"] is False
        r = w.get(f"/material/artikel/{art[0]}/lebenslauf.pdf")
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(pdf_seiten(pfad)).split())
        assert "Zuordnung geändert" in text and "(Person)" in text and "Person Zwei" not in text, text[:2000]
    print("Anzeige und Filter (A1R) bestanden.")


def test_loesen_beim_aussondern_a1r():
    """6.1 mit Paket A1R: Aussondern löst die Zuordnung – Journal „zuordnung_geloest“ mit Verweis und Grund."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager, art, p = aufbau(tmp)
        w = k["wart"]
        assert w.put(ZU.format(art[0]), json={"user_id": p["person1"]}).status_code == 200
        sperren(k["pruefer"], art[0])
        assert w.post(f"/api/material/artikel/{art[0]}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        assert zugeordnet(app, art[0]) is None
        e = journal_am(app, art[0], "zuordnung_geloest")
        assert len(e) == 1, e
        nur_verweis(e[0]["after_json"], ref_von(app, p["person1"]), ("Person Eins",), p["person1"], grund="ausgesondert")
    print("Lösen beim Aussondern (A1R) bestanden.")


# Was erst nach dem Zusammenführen mit einem anderen Paket grün sein kann (Bauentwurf 9.3): Name → Paket. Der Block
# __main__ führt diese Tests aus und meldet ein Scheitern nur; die Integration leert die Tabelle.
WARTET_AUF = {"test_anzeige_und_filter_a1r": "A1R", "test_loesen_beim_aussondern_a1r": "A1R"}


if __name__ == "__main__":
    test_zuordnen()
    test_sammelaktion()
    test_zugeordnete()
    test_lebenslauf_ohne_namen()
    test_meldungen_je_bereich()
    test_loeschkonzept()
    for name, paket in WARTET_AUF.items():
        try:
            globals()[name]()
        except Exception as exc:                 # wartet auf das andere Paket – meldet, scheitert aber nicht
            print(f"{name}: wartet auf Paket {paket} ({type(exc).__name__}: {str(exc)[:200]})")
