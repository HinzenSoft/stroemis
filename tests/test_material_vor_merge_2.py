"""Nachbesserung vor dem Merge, Runde 2 (26.10.2026):  python tests/test_material_vor_merge_2.py  oder pytest

N-A1: Als Prüfung zum Rückruf zählt nur eine, deren ENTWURF nach dem späteren von Rückruf-Anlage und letztem bestätigtem
Antrag auf Produkt oder Seriennummer begann – ein Entwurf, der schon offen war, als der Rückruf bzw. der Antrag kam,
erledigt ihn nicht (Banner, Marke, Übersicht, Jahresbericht, Meine PSA, Lebenslauf). „Bald fällig“ aus der .env: nur
eine ganze Zahl 0–365, sonst Warnung im Log und Vorgabe 30 – die App startet auch bei „abc“, die Leitstelle zeigt den
wirksamen Wert. Alles Platzhalter."""
import logging
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import anmelden, festschreiben, make_app, neuer_artikel, neues_konto, starten  # noqa: E402
from test_material_a4_n5 import _geprueft, aufbau  # noqa: E402
from test_material_vor_merge import _antrag_bestaetigt, _lebenslauf, _rueckruf_am_artikel  # noqa: E402

API = "/api/material"
TITEL = "Rückruf Platzhalter N-A1"


def _entwurf(t, iid):
    r = starten(t.p, iid)
    assert r.status_code in (200, 201), r.get_json()
    return r.json["pruefung"]["id"]


def _festschreiben(t, pid):
    r = festschreiben(t.p, pid, ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()


def test_n_a1_rueckruf_waehrend_entwurf():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        hms = t.ids["hms"]
        rueckruf_x = neuer_artikel(t.w, hms, t.ga, serial_no="NA1-RR")["id"]       # Rückruf kommt während des Entwurfs
        antrag_x = neuer_artikel(t.w, hms, t.ga, serial_no="NA1-ALT")["id"]        # Antrag kommt während des Entwurfs
        kontrolle = neuer_artikel(t.w, hms, t.ga, serial_no="NA1-KONTROLLE")["id"]  # Entwurf erst nach dem Rückruf
        for iid in (rueckruf_x, antrag_x, kontrolle):
            _geprueft(t, iid)
        time.sleep(1.1)                                      # gleiche Sekunde zählt als „vorher“
        e_rr, e_antrag = _entwurf(t, rueckruf_x), _entwurf(t, antrag_x)
        # Beim Öffnen der Entwürfe sah der Prüfer keinen Rückruf.
        assert _rueckruf_am_artikel(t.p, rueckruf_x) == _rueckruf_am_artikel(t.p, antrag_x) == []
        time.sleep(1.1)
        r = t.mv.post(f"{API}/produkte/{hms}/rueckrufe",
                      json={"title": TITEL, "serials": "NA1-RR\nNA1-NEU\nNA1-KONTROLLE", "mail": False})
        assert r.status_code == 201, r.get_json()
        time.sleep(1.1)
        _antrag_bestaetigt(t, antrag_x, serial_no="NA1-NEU")              # bei offenem Entwurf erlaubt (200)
        e_kontrolle = _entwurf(t, kontrolle)
        time.sleep(1.1)
        for pid in (e_rr, e_antrag, e_kontrolle):
            _festschreiben(t, pid)

        # Banner am Artikel (jede Rolle bekommt denselben Zustand).
        for c in (t.w, t.p, t.mv):
            assert _rueckruf_am_artikel(c, rueckruf_x) == [(TITEL, "offen", None)], _rueckruf_am_artikel(c, rueckruf_x)
            assert _rueckruf_am_artikel(c, antrag_x) == [(TITEL, "offen", None)], _rueckruf_am_artikel(c, antrag_x)
            assert _rueckruf_am_artikel(c, kontrolle) == [(TITEL, "erledigt", "geprueft")]
        # Marke in der Ordnerliste, Übersicht, Produktseite.
        marke = {a["id"]: a["rueckruf"] for a in t.w.get(f"{API}/ordner/{t.ga}").json["ordner"]["artikel"]}
        assert (marke[rueckruf_x], marke[antrag_x], marke[kontrolle]) == (TITEL, TITEL, None), marke
        uebersicht = [(x["title"], x["betroffen"], x["offen"]) for x in t.w.get(f"{API}/start").json["rueckrufe"]]
        assert uebersicht == [(TITEL, 3, 2)], uebersicht
        produkt = t.w.get(f"{API}/produkte/{hms}").json["produkt"]["rueckrufe"]
        assert [(x["betroffen"], x["offen"]) for x in produkt if x["title"] == TITEL] == [(3, 2)], produkt
        # Jahresbericht des Zweigs.
        r = t.w.get(f"{API}/ordner/{t.ga}/bericht")
        assert r.status_code == 200, r.get_json()
        rr = [x for x in r.json["bericht"]["rueckrufe"] if x["titel"] == TITEL]
        assert [(x["betroffen"], x["offen"]) for x in rr] == [(3, 2)], rr
        assert sorted(a["zustand"] for a in rr[0]["artikel"]) == ["erledigt", "offen", "offen"], rr
        # Meine PSA: Karte trägt den Rückruf nur, solange er für den Artikel offen ist.
        person, person_id = neues_konto(t.app, "person_na1@example.org", name="Person Platzhalter", stufe=0)
        for iid in (rueckruf_x, kontrolle):
            r = t.w.put(f"{API}/artikel/{iid}/zuordnung", json={"user_id": person_id})
            assert r.status_code == 200, r.get_json()
        karten = {k["id"]: k["rueckruf"] for k in person.get(f"{API}/meine-psa").json["artikel"]}
        assert karten[rueckruf_x] and not karten[kontrolle], karten
        # Lebenslauf.
        text = _lebenslauf(t, tmp, rueckruf_x)
        assert "für diesen Artikel offen" in text and "nach dem Rückruf geprüft" not in text, text[:3000]
        assert "für diesen Artikel offen" in _lebenslauf(t, tmp, antrag_x)
        assert "erledigt – nach dem Rückruf geprüft" in _lebenslauf(t, tmp, kontrolle)

        # Eine Prüfung, die nach Rückruf bzw. Antrag beginnt, erledigt ihn.
        for iid in (rueckruf_x, antrag_x):
            _geprueft(t, iid)
            assert _rueckruf_am_artikel(t.w, iid) == [(TITEL, "erledigt", "geprueft")], iid
        uebersicht = [(x["title"], x["betroffen"], x["offen"]) for x in t.w.get(f"{API}/start").json["rueckrufe"]]
        assert uebersicht == [(TITEL, 3, 0)], uebersicht
        karten = {k["id"]: k["rueckruf"] for k in person.get(f"{API}/meine-psa").json["artikel"]}
        assert not karten[rueckruf_x], karten
        assert "erledigt – nach dem Rückruf geprüft" in _lebenslauf(t, tmp, rueckruf_x)
    print("N-A1 bestanden.")


class _Sammler(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append(record.getMessage())


def test_bald_faellig_aus_der_env():
    """MATERIAL_BALD_FAELLIG_TAGE in der Umgebung: 0–365 gilt (Leitstelle „umgebung“); alles andere – auch „abc“ – gilt
    nicht: Warnung im Log, Vorgabe 30, Leitstelle zeigt 30 als Vorgabe. Leer heißt Vorgabe ohne Warnung."""
    sammler = _Sammler()
    log = logging.getLogger("app")
    log.addHandler(sammler)
    alt = os.environ.get("MATERIAL_BALD_FAELLIG_TAGE")
    try:
        for roh, wirksam, warnung in (("abc", 30, True), ("1000", 30, True), ("366", 30, True), ("-5", 30, True),
                                      ("1.5", 30, True), ("1e2", 30, True), ("", 30, False), ("0", 0, False),
                                      ("365", 365, False), (" 45 ", 45, False)):
            os.environ["MATERIAL_BALD_FAELLIG_TAGE"] = roh
            sammler.zeilen.clear()
            with tempfile.TemporaryDirectory() as tmp:
                app = make_app(tmp)                      # startet – auch bei „abc“
                assert app.config["MATERIAL_BALD_FAELLIG_TAGE"] == wirksam, (roh, app.config["MATERIAL_BALD_FAELLIG_TAGE"])
                treffer = [z for z in sammler.zeilen if "MATERIAL_BALD_FAELLIG_TAGE" in z]
                assert bool(treffer) == warnung, (roh, sammler.zeilen)
                if warnung:
                    assert "es gilt die Vorgabe 30" in treffer[0] and repr(roh.strip()) in treffer[0], treffer
                adm = anmelden(app, "admin@example.org", "geheim123")
                felder = adm.get("/api/admin/einstellungen").json["felder"]
                f = [x for x in felder if x["schluessel"] == "MATERIAL_BALD_FAELLIG_TAGE"][0]
                erwartet = (roh, "umgebung") if not warnung and roh else (str(wirksam), "vorgabe")
                assert (f["wert"], f["quelle"]) == erwartet, (roh, f)
                assert adm.get(f"{API}/start").json["schwelle_tage"] == wirksam
                # Ein gültiger gespeicherter Wert liegt weiter darüber.
                r = adm.put("/api/admin/einstellungen", json={"werte": {"MATERIAL_BALD_FAELLIG_TAGE": "12"}})
                assert r.status_code == 200, r.get_json()
                assert adm.get(f"{API}/start").json["schwelle_tage"] == 12
    finally:
        log.removeHandler(sammler)
        if alt is None:
            os.environ.pop("MATERIAL_BALD_FAELLIG_TAGE", None)
        else:
            os.environ["MATERIAL_BALD_FAELLIG_TAGE"] = alt
    print("„Bald fällig“ aus der .env bestanden.")


if __name__ == "__main__":
    test_n_a1_rueckruf_waehrend_entwurf()
    test_bald_faellig_aus_der_env()
    print("Alle Tests der Nachbesserung vor dem Merge, Runde 2, bestanden.")
