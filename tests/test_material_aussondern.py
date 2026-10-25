"""Aussondern nur durch den Materialwart (Wunsch des Nutzers vom 25.10.2026, Schritt 28):  python
tests/test_material_aussondern.py  oder pytest

Prüfer sondern nicht mehr aus – das Ergebnis „aussondern empfohlen“ sperrt nur (wie „instandsetzen“), die Empfehlung
steht im Prüfprotokoll und am Artikel. Der Materialwart sondert aus, wenn die letzte Prüfung „instandsetzen“ oder
„aussondern empfohlen“ ergab (E2); ohne Prüfung nur einen verloren gemeldeten Artikel; nach einer Mangelmeldung erst
nach einer Prüfung. Dazu kritischer Mangel und Lebensende, Durchgang mit Sammelprotokoll, Berichtigung, Altbestand
(„aussondern“ vor Schritt 28), Schritt 28 (frisch = migriert, zweiter Lauf, Trigger unverändert) und die Oberfläche
statisch.

Alle Namen, Nummern und Ergebnisse hier sind Platzhalter."""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, festschreiben, jpeg, make_app, neuer_artikel, punkte_von  # noqa: E402
from test_material_antrag import _pdf_text  # noqa: E402
from test_material_mangel import geprueft, item, melden, neue_sekunde, post_mangel, pruefung  # noqa: E402
from test_material_meine_psa import aufbau  # noqa: E402
from test_material_set_rueckbau import _schema, _unterschied, roh  # noqa: E402
from test_material_trennung import bis_schritt, endversion, zeilen  # noqa: E402
from test_material_ueberblick import sperren  # noqa: E402

API = "/api/material"


def aussondern(c, iid, grund="irreparabel"):
    return c.post(f"{API}/artikel/{iid}/aussondern", json={"grund": grund})


def artikel(c, iid):
    return c.get(f"{API}/artikel/{iid}").json["artikel"]


def test_ergebnis_sperrt_nur():
    """„aussondern empfohlen“ sperrt (Gesperrt, Herkunft gemerkt, Sperrgrund), sondert nicht aus, steht im Protokoll und
    am Artikel (Marke in der Liste „Gesperrt“); „aussondern“ ist kein Prüfergebnis mehr (400); der Prüfer sondert auch
    über die Route nicht aus (403). Danach sondert der Materialwart aus – das Journal nennt die Empfehlung."""
    from app.material.services import pruefung as dienst
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        w, p = t.w, t.k["pruefer"]
        geprueft(t.app, a1)
        pr = pruefung(p, a1)
        r = festschreiben(p, pr["id"], ergebnis="aussondern", grund="Platzhalter")
        assert r.status_code == 400 and r.json["error"] == dienst.NICHT_AUSSONDERN, r.get_json()
        r = festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen")
        assert r.status_code == 400 and "Grund" in r.json["error"], r.get_json()
        r = festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter verformt")
        assert r.status_code == 200 and r.json["pruefung"]["ergebnis"] == "aussondern_empfohlen", r.get_json()
        assert r.json["pruefung"]["ergebnis_text"] == "aussondern empfohlen"
        a = artikel(w, a1)
        assert a["lock_state"] == "gesperrt" and a["folder_id"] == t.system["gesperrt"] and a["origin_folder_id"] == t.lager
        assert a["lock_reason"].endswith("aussondern empfohlen – Platzhalter verformt"), a["lock_reason"]
        assert not [x for x in a["pruefungen"] if x["art"] == "aussonderung"]
        assert a["aussonderung_empfohlen"]["pruefung"] == pr["id"] and a["aussonderung_empfohlen"]["grund"] == \
            "Platzhalter verformt" and a["aussonderung_empfohlen"]["pruefer"] == "pruefer"
        assert a["aussondern"] == {"ok": True, "grund": ""}
        assert artikel(p, a1)["aussondern"] is None                 # Prüfer ohne „verwalten“
        liste = w.get(f"{API}/ordner/{t.system['gesperrt']}").json["ordner"]["artikel"]
        assert [x["aussonderung_empfohlen"] for x in liste if x["id"] == a1] == [True]
        text = " ".join(_pdf_text(w.get(f"/material/pruefung/{pr['id']}/pdf").data).split())
        assert "aussondern empfohlen" in text and "Der Prüfer empfiehlt, den Artikel auszusondern" in text, text[:800]
        # Der Prüfer sondert nicht aus – auch nicht über die Route.
        assert aussondern(p, a1).status_code == 403
        r = aussondern(w, a1)
        assert r.status_code == 200, r.get_json()
        aid = r.json["aussonderung"]
        j = zeilen(t.app, "SELECT after_json FROM mat_audit WHERE entity = 'inspection' AND entity_id = ? "
                          "AND action = 'ausgesondert'", (aid,))
        assert f'"empfehlung": {pr["id"]}' in j[0]["after_json"], j
        x = zeilen(t.app, "SELECT basis_inspection_id, result, kind FROM mat_inspection WHERE id = ?", (aid,))[0]
        assert x == {"basis_inspection_id": None, "result": "aussondern", "kind": "aussonderung"}
        assert artikel(w, a1)["status"] == "ausgesondert"
    print("Ergebnis sperrt nur bestanden.")


def test_bedingungen_materialwart():
    """E2 je Sperrart: frei 409; direkte Sperre (Sturz, Beschädigung) 409 bis zu einer Prüfung mit „instandsetzen“ oder
    „aussondern empfohlen“; Verlust sofort; Mangelmeldung 409 NUR_GEMELDET bis zu einer Prüfung; nach einer
    Freiprüfung und neuer Sperre wieder 409; nichts ändert sich bei einer Ablehnung."""
    from app.material.services import mangel
    from app.material.services import pruefung as dienst
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w, p = t.w, t.k["pruefer"]
        a1, a2, a3 = t.art
        a4 = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="AUS-4")["id"]
        a5 = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="AUS-5")["id"]
        for iid in (a1, a2, a3, a4, a5):
            geprueft(t.app, iid)
        # Frei: nichts auszusondern.
        r = aussondern(w, a1)
        assert r.status_code == 409 and r.json["error"] == dienst.AUSSONDERN_NUR_GESPERRT, r.get_json()
        # Direkte Sperre ohne Prüfung.
        sperren(p, a1, "sturz")
        vorher = item(t.app, a1)
        r = aussondern(w, a1)
        assert r.status_code == 409 and r.json["error"] == dienst.AUSSONDERN_OHNE_PRUEFUNG, r.get_json()
        assert item(t.app, a1) == vorher
        assert artikel(w, a1)["aussondern"] == {"ok": False, "grund": dienst.AUSSONDERN_OHNE_PRUEFUNG}
        pr = pruefung(p, a1)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhalter").status_code == 200
        assert artikel(w, a1)["aussonderung_empfohlen"] is None
        assert aussondern(w, a1).status_code == 200
        # Verlust: sofort.
        sperren(p, a2, "verlust")
        assert aussondern(w, a2, "verlust").status_code == 200
        # Mangelmeldung: erst nach einer Prüfung.
        assert melden(w, a3).status_code == 201
        r = aussondern(w, a3)
        assert r.status_code == 409 and r.json["error"] == mangel.NUR_GEMELDET, r.get_json()
        neue_sekunde()
        pr = pruefung(p, a3)
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter").status_code == 200
        assert aussondern(w, a3).status_code == 200
        assert zeilen(t.app, "SELECT closed_at FROM mat_defect_report WHERE item_id = ?", (a3,))[0]["closed_at"]
        # Freiprüfung, danach eine neue Sperre: die alte Prüfung zählt nicht mehr.
        pr = pruefung(p, a4)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhalter").status_code == 200
        pr = pruefung(p, a4)
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit").status_code == 200
        sperren(p, a4, "beschaedigung")
        r = aussondern(w, a4)
        assert r.status_code == 409 and r.json["error"] == dienst.AUSSONDERN_OHNE_PRUEFUNG, r.get_json()
        # Eine Prüfung am schon gesperrten Artikel mit „aussondern empfohlen“ hält die Sperre und macht den Weg frei.
        pr = pruefung(p, a4)
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter").status_code == 200
        a = artikel(w, a4)
        assert a["lock_reason"].startswith("Beschädigung") and a["aussonderung_empfohlen"]["pruefung"] == pr["id"]
        assert aussondern(w, a4).status_code == 200
        # Rückruf-Sperre wie Sturz.
        sperren(p, a5, "rueckruf")
        assert aussondern(w, a5).status_code == 409
    print("Bedingungen des Materialwarts bestanden.")


def test_kritisch_lebensende_berichtigung():
    """Kritischer Mangel: „einsatzbereit“ aus, „aussondern empfohlen“ geht. Lebensende erreicht: ebenso. Berichtigung
    einer Empfehlung zu „einsatzbereit“ gibt frei (Freiprüfung); die Empfehlung ist danach weg."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w, p = t.w, t.k["pruefer"]
        a1 = t.art[0]
        geprueft(t.app, a1)
        pr = pruefung(p, a1)
        url = f"{API}/pruefungen/{pr['id']}/punkte"
        pk = punkte_von(pr)
        assert p.put(f"{url}/{pk['Testpunkt Verschluss']}", json={"wert": "nein", "notiz": "Platzhalter klemmt"}).status_code == 200
        assert p.post(f"{url}/{pk['Testpunkt Verschluss']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                      content_type="multipart/form-data").status_code == 200
        r = festschreiben(p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "„aussondern empfohlen“" in r.json["error"], r.get_json()
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen").status_code == 200   # Mangel: ohne Grund
        # Lebensende erreicht (textil).
        h = _heute()
        alt = neuer_artikel(w, t.ids["gurt"], t.lager, manufactured_on=f"{h.year - 11}-01")["id"]
        pr = pruefung(p, alt)
        pk = punkte_von(pr)
        p.put(f"{API}/pruefungen/{pr['id']}/punkte/{pk['Testpunkt Messwert']}", json={"wert": "1"})
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit").status_code == 400
        r = festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Lebensdauer überschritten")
        assert r.status_code == 200 and artikel(w, alt)["lock_state"] == "gesperrt", r.get_json()
        # Berichtigung einer Empfehlung (der erste Artikel, kritischer Mangel bleibt im Original).
        b = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="BER-1")["id"]
        geprueft(t.app, b)
        pr = pruefung(p, b)
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter").status_code == 200
        r = p.post(f"{API}/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter verwechselt"})
        assert r.status_code in (200, 201), r.get_json()
        neu = r.json["pruefung"]
        assert festschreiben(p, neu["id"], ergebnis="einsatzbereit").status_code == 200
        a = artikel(w, b)
        assert a["lock_state"] == "frei" and a["aussonderung_empfohlen"] is None and a["folder_id"] == t.lager
    print("Kritisch, Lebensende und Berichtigung bestanden.")


def test_durchgang_und_altbestand():
    """Im Durchgang zählt „aussondern empfohlen“ als erledigt; das Sammelprotokoll nennt „davon aussondern empfohlen“.
    Altbestand: eine Prüfung mit „aussondern“ (vor Schritt 28) heißt „aussondern (ausgesondert)“, lässt sich nicht
    berichtigen, und das Sammelprotokoll zählt sie als „davon ausgesondert“."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w, p = t.w, t.k["pruefer"]
        for iid in t.art:
            geprueft(t.app, iid)
        rid = w.post(f"{API}/durchgaenge", json={"folder_id": t.lager, "titel": "Platzhalter"}).json["durchgang"]["id"]
        pr = pruefung(p, t.art[0], durchgang_id=rid)
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter").status_code == 200
        for iid in t.art[1:]:
            pr = pruefung(p, iid, durchgang_id=rid)
            assert festschreiben(p, pr["id"], ergebnis="einsatzbereit").status_code == 200
        assert w.post(f"{API}/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
        haupt = " ".join(_pdf_text(w.get(f"/material/durchgang/{rid}/sammelprotokoll").data).split())
        assert "davon aussondern empfohlen 1" in haupt and "davon ausgesondert" not in haupt, haupt[:900]
        # Altbestand: eine Prüfung mit „aussondern“, wie sie vor Schritt 28 entstand (direkt in der Tabelle).
        alt = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="ALT-1")["id"]
        conn = roh(t.app)
        with conn:
            jetzt = "2026-01-02T10:00:00+00:00"
            xid = conn.execute("INSERT INTO mat_inspection (item_id, inspector_name, inspected_on, kind, result, reason, "
                               "completed_at, created_at, updated_at) VALUES (?, 'Altprüfer', '2026-01-02', 'eingang', "
                               "'aussondern', 'Platzhalter alt', ?, ?, ?)", (alt, jetzt, jetzt, jetzt)).lastrowid
        conn.close()
        x = w.get(f"{API}/pruefungen/{xid}").json["pruefung"]
        assert x["ergebnis"] == "aussondern" and x["ergebnis_text"] == "aussondern (ausgesondert)", x
        with t.app.app_context():
            from app.material.services import pruefung as dienst
            p_alt = zeilen(t.app, "SELECT * FROM mat_inspection WHERE id = ?", (xid,))[0]
            assert dienst.berichtigbar(p_alt)["ok"] is False
    print("Durchgang und Altbestand bestanden.")


def test_schritt_28():
    """Frisch = migriert (27 → 28), Trigger und Indizes in genau ihrer Fassung zurück, Zeilen und Zähler bleiben, zweiter
    Lauf ändert nichts; der Schutz festgeschriebener Prüfungen wirkt danach weiter; der neue Wert geht, ein unbekannter
    nicht."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        bis_schritt(27)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        sql_27 = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'mat_inspection'").fetchone()[0]
        assert "'aussondern_empfohlen'" not in sql_27
        trigger_27 = sorted(conn.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('trigger', 'index')"))
        conn.close()
        t = aufbau(tmp)                     # startet die App: 27 → 28
        assert zeilen(t.app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        conn = sqlite3.connect(pfad)
        assert sorted(conn.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('trigger', 'index')")) == trigger_27
        conn.close()
        # Eine festgeschriebene Prüfung (nach dem Umbau entstanden) bleibt geschützt; der Zähler wächst weiter.
        p = t.k["pruefer"]
        a1 = t.art[0]
        geprueft(t.app, a1)
        pr = pruefung(p, a1)
        assert festschreiben(p, pr["id"], ergebnis="aussondern_empfohlen", grund="Platzhalter").status_code == 200
        conn = roh(t.app)
        try:
            for befehl in ("UPDATE mat_inspection SET result = 'einsatzbereit' WHERE id = ?",
                           "DELETE FROM mat_inspection WHERE id = ?"):
                try:
                    conn.execute(befehl, (pr["id"],))
                except sqlite3.IntegrityError:
                    conn.rollback()
                else:
                    raise AssertionError(f"nicht abgewiesen: {befehl}")
            try:
                conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, result, created_at, updated_at) "
                             "VALUES (?, '2026-01-01', 'eingang', 'weg', 'x', 'x')", (a1,))
            except sqlite3.IntegrityError as exc:
                assert "CHECK" in str(exc), exc
                conn.rollback()
            else:
                raise AssertionError("unbekanntes Ergebnis nicht abgewiesen")
        finally:
            conn.close()
        # Zweiter Lauf ändert nichts.
        conn = sqlite3.connect(pfad)
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_28(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
    print("Schritt 28 bestanden.")


def test_oberflaeche_statisch():
    """Prüfdialog nur mit den wählbaren Ergebnissen, keine „endgültig“-Warnung und kein roter Bestätigen-Knopf mehr;
    Marke „Aussonderung empfohlen“ in Listen und am Artikel; „Aussondern“ ausgegraut mit dem Grund vom Server; Dialog mit
    der Empfehlung und vorbelegtem Grund; Journal-Beschriftung „empfehlung“ in beiden Sprachen."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    assert 'const WAEHLBAR = ["einsatzbereit", "instandsetzen", "aussondern_empfohlen"];' in js
    assert "${WAEHLBAR.map((e) => `<button type=\"button\" data-act=\"ergebnis\"" in js
    assert "„aussondern“ ist endgültig" not in js and 'daten.ergebnis === "aussondern" ? " danger"' not in js
    assert "const empfohlenMarke = (x) =>" in js and "${empfohlenMarke(a.aussonderung_empfohlen)}" in js
    assert "${empfohlenMarke(empf)}" in js
    assert "aussondernNein ? ' disabled aria-describedby=\"mat-aussondern-hilfe\"'" in js
    assert "const NUR_GEMELDET" not in js
    assert 'k === vorbelegt ? " selected" : ""' in js
    from app.material.services import beschriftung
    assert f'empfehlung: "{beschriftung.FELD["empfehlung"]}"' in js
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    assert ".mat-empfohlen-marke {" in css and ".e-aussondern_empfohlen" in css
    # Designsprache (Nutzer, 25.10.2026): keine Erklärzeile unter Knöpfen – der Satz steht über der Knopfzeile.
    for satz, knoepfe in (('id="mat-aussondern-hilfe"', '<div class="btn-row mat-pruefknoepfe">'),
                          ('id="mat-schon-gemeldet"', '<div class="btn-row mat-pruefknoepfe">'),
                          ('<p class="help mat-nur-touch">Lebenslauf (PDF)', "lebenslaufKnopf(a) : \"\"}</div>"),
                          ('<p class="help mat-nur-touch">„Anlegen und nächsten“', '<div class="btn-row mat-knoepfe">'),
                          ('id="psa-schon-${Number(k.id)}"', '<div class="btn-row mat-psa-knoepfe">'),
                          ('<p class="help">${esc(b.frist)}</p>', 'data-act="bi-neu">Neu wählen</button>'),
                          ('id="pr-hinweis" aria-live="polite"', '<div class="mat-ergebnis" role="group"'),
                          ("${pruefHinweis(a)}</p>`", 'id="mat-schon-gemeldet">Du hast am'),
                          ('id="mat-schon-gemeldet">Du hast am', 'id="mat-aussondern-hilfe">')):
        assert js.index(satz) < js.index(knoepfe), satz
    # Browserprüfung des Endstands (25.10.2026): Marke auch in der Durchgangsliste, in der Karte umbrechend; Grund der
    # Empfehlung im Banner nicht doppelt; Statuszeile der Prüfung beschreibt Ergebnis und „Festschreiben“.
    assert js.count("${empfohlenMarke(a.aussonderung_empfohlen)}") == 2
    assert 'const sperrText = empf && /aussondern empfohlen/.test(a.lock_reason || "") ? "Aussonderung empfohlen"' in js
    assert 'aria-label="Ergebnis" aria-describedby="pr-hinweis"' in js and 'id="pr-ok" aria-describedby="pr-hinweis"' in js
    assert "table.list.mat-karten td.mat-k-marke .mat-empfohlen-marke { white-space: normal; max-width: 100%;" in css
    vorlage = open(os.path.join(wurzel, "app/material/templates/material/pdf/sammelprotokoll.html"), encoding="utf-8").read()
    assert "tr.set-kopf td { hyphens: manual; overflow-wrap: normal; }" in vorlage
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_ergebnis_sperrt_nur()
    test_bedingungen_materialwart()
    test_kritisch_lebensende_berichtigung()
    test_durchgang_und_altbestand()
    test_schritt_28()
    test_oberflaeche_statisch()
    print("Alle Tests zum Aussondern bestanden.")
