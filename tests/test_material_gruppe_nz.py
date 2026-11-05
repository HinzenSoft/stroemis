"""„alle n. z.“ je Gruppe und Untergruppe und optionale Prüfpunkte nur mit Antwort (Wünsche vom 05.11.2026; Bauauftrag
planung/gruppe-nz/auftrag.md und zwei Zusätze):
python tests/test_material_gruppe_nz.py  oder  pytest tests/test_material_gruppe_nz.py

1. Dienst: Ein optionaler Ja/Nein-, Text-, Zahl- oder Datumspunkt nimmt nur seine Antwort auf – Befund „in Ordnung“
   (auch „Nein“ gegen das Soll), „mangel“/„nicht_zutreffend“, eine neue Bemerkung und ein Foto lehnt er ab; Foto,
   Unterschrift und Länge bleiben wie Pflichtpunkte. Ein älterer Entwurf mit Mangel bzw. „n. z.“ an einem solchen Punkt
   wird beim Festschreiben „in Ordnung“; Festschreiben ohne Foto/Bemerkung, keine Mängel in Journal, Lebenslauf,
   Jahresbericht und CSV, Ergebnis ohne Mangel braucht einen Grund; Prüfprotokoll (PDF-Text): Befund „optional“, die
   Antwort im Wert, keine Mangel-Legende. Gruppe auf „n. z.“ je Punkt über die vorhandene Schnittstelle: 30 Punkte in
   der Zeit.
2. Browser (1280 Maus, 360 Touch): optionale Punkte ohne Befundknöpfe, Bemerkung und Foto (auch nach Hin und Her);
   „alle n. z.“ an Gruppe und Untergruppe (Name für Bildschirmleser, 44 px am Finger, Tipp auf die Mitte trifft), ohne
   Rückfrage mit Toast, mit Rückfrage bei einem Mangel (Zahl genannt; Abbrechen ändert nichts), optionale Punkte bleiben,
   Werte in der Datenbank, zurück je Punkt, Festschreiben danach über die Oberfläche; 30 Punkte unter 1 s; kein
   waagerechter Bildlauf, keine Konsolenfehler. Ohne Chromium „übersprungen“ mit rc 0.
3. Statisch: Knopfsprache und Touch-Regel.
Alle Inhalte sind Platzhalter."""
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, _heute, abschluss, gliederung, katalog_grund, neuer_artikel, pdf_layout_seiten,  # noqa: E402
                           starten, umgebung)

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GA, GB, GV = "Platzhalter Gruppe A", "Platzhalter Gruppe B", "Platzhalter Gruppe Viele"
UK, US = "Platzhalter UG Körper", "Platzhalter UG Schnapper"
PUNKTE = [
    {"gruppe": GA, "text": "Platzhalter A1", "art": "yesno", "soll": "ja"},
    {"gruppe": GA, "text": "Platzhalter A2 optional", "art": "yesno", "soll": "ja", "pflicht": False},
    {"gruppe": GA, "text": "Platzhalter A3 optional", "art": "text", "soll": "Platzhalter Hinweis", "pflicht": False},
    {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K1", "art": "yesno", "soll": "ja"},
    {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K2", "art": "text"},
    {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K3", "art": "number"},
    {"gruppe": GA, "untergruppe": US, "text": "Platzhalter S1", "art": "yesno", "soll": "nein"},
    {"gruppe": GA, "untergruppe": US, "text": "Platzhalter S2 optional", "art": "number", "pflicht": False},
    {"gruppe": GB, "text": "Platzhalter B1", "art": "yesno", "soll": "ja"},
    {"gruppe": GB, "text": "Platzhalter B2 optional", "art": "date", "pflicht": False},
    {"gruppe": GB, "text": "Platzhalter B3 Foto optional", "art": "photo", "pflicht": False},
] + [{"gruppe": GV, "text": f"Platzhalter V{n}", "art": "yesno", "soll": "ja"} for n in range(1, 31)]
OPTIONAL = ("Platzhalter A2 optional", "Platzhalter A3 optional", "Platzhalter S2 optional", "Platzhalter B2 optional")


def formular(c, kategorie, titel="Platzhalter Gruppe n. z."):
    r = c.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": titel, "punkte": PUNKTE})
    assert r.status_code == 201, r.get_json()
    f = r.json["formular"]
    assert c.post(f"{API}/formulare/{f['id']}/aktivieren", json={}).status_code == 200
    r = c.put(f"{API}/formular-pool/{f['formular_id']}/zuweisung", json={"kategorien": [kategorie], "produkte": []})
    assert r.status_code == 200, r.get_json()
    return f["id"]


def ids_von(pr):
    return {x["text"]: x["id"] for x in pr["punkte"]}


def _bild():
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(puffer, "JPEG")
    puffer.seek(0)
    return puffer


# --- 1. Dienst ---------------------------------------------------------------------------------------------------------

def test_dienst_und_protokoll():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, p1 = k["wart"], k["pruefer"]
        formular(k["katalog"], ids["gurte"])
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        r = starten(p1, a["id"])
        assert r.status_code == 201, r.get_json()
        pr = r.json["pruefung"]
        pid, n = pr["id"], ids_von(pr)
        url = lambda t: f"{API}/pruefungen/{pid}/punkte/{n[t]}"   # noqa: E731

        def setzen(t, **d):
            return p1.put(url(t), json=d)
        # Optional Ja/Nein: „Nein“ gegen das Soll ist in Ordnung; Pflicht-Ja/Nein bleibt ein Mangel.
        r = setzen("Platzhalter A2 optional", wert="nein")
        assert r.status_code == 200 and (r.json["punkt"]["befund"], r.json["punkt"]["wert"]) == ("ok", "nein"), r.get_json()
        assert setzen("Platzhalter A1", wert="nein").json["punkt"]["befund"] == "mangel"
        assert setzen("Platzhalter A1", wert="ja").json["punkt"]["befund"] == "ok"
        # Kein Mangel, kein „n. z.“, keine neue Bemerkung, kein Foto – an allen vier Arten; „ok“ und der Wert gehen.
        from app.material.services.pruefung import NUR_ANTWORT
        for t in OPTIONAL:
            for d in ({"befund": "mangel"}, {"befund": "nicht_zutreffend"}, {"notiz": "Platzhalter Bemerkung"}):
                r = setzen(t, **d)
                assert r.status_code == 400 and r.json["error"] == NUR_ANTWORT, (t, d, r.get_json())
            r = p1.post(f"{url(t)}/foto", data={"file": (_bild(), "a.jpg")}, content_type="multipart/form-data", headers=H)
            assert r.status_code == 400 and r.json["error"] == NUR_ANTWORT, (t, r.get_json())
            r = setzen(t, befund="ok", notiz="")
            assert r.status_code == 200 and r.json["punkt"]["befund"] == "ok", (t, r.get_json())
        assert setzen("Platzhalter A3 optional", wert="Platzhalter Antwort").json["punkt"]["befund"] == "ok"
        assert setzen("Platzhalter S2 optional", wert="7").json["punkt"]["wert"] == "7"
        assert setzen("Platzhalter B2 optional", wert="2026-01-02").json["punkt"]["befund"] == "ok"
        assert setzen("Platzhalter A2 optional", wert="nein").json["punkt"]["wert"] == "nein"
        # Foto, Unterschrift, Länge: wie bisher – ein optionaler Fotopunkt nimmt „n. z.“ und ein Foto.
        assert setzen("Platzhalter B3 Foto optional", befund="nicht_zutreffend").json["punkt"]["befund"] == "nicht_zutreffend"
        r = p1.post(f"{url('Platzhalter B3 Foto optional')}/foto", data={"file": (_bild(), "a.jpg")},
                    content_type="multipart/form-data", headers=H)
        assert r.status_code == 200 and r.json["punkt"]["foto"], r.get_json()
        # Gruppe „n. z.“ je Punkt über die vorhandene Schnittstelle: 30 Punkte (Festlegung 5).
        los = time.time()
        for x in range(1, 31):
            assert setzen(f"Platzhalter V{x}", befund="nicht_zutreffend").status_code == 200
        dauer = time.time() - los
        print(f"30 Punkte einzeln auf n. z.: {dauer:.2f} s")
        assert dauer < 3, dauer
        # Ein älterer Entwurf: Mangel bzw. „n. z.“ an optionalen Antwortpunkten (vor dem 05.11.2026 möglich), mit Bemerkung.
        with app.app_context():
            from app import db
            db.execute("UPDATE mat_inspection_result SET finding = 'mangel', note = 'Platzhalter alt' WHERE id = ?",
                       (n["Platzhalter A2 optional"],))
            db.execute("UPDATE mat_inspection_result SET finding = 'nicht_zutreffend' WHERE id = ?",
                       (n["Platzhalter A3 optional"],))
        assert setzen("Platzhalter K2", wert="Platzhalter").status_code == 200
        assert setzen("Platzhalter K3", wert="3").status_code == 200
        # Ohne Mangel braucht „instandsetzen“ einen Grund – der alte Mangel am optionalen Punkt zählt nicht.
        r = abschluss(p1, pid, ergebnis="instandsetzen")
        assert r.status_code == 400 and "einen Grund" in r.json["error"], r.get_json()
        r = abschluss(p1, pid, ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            from app import db
            zeilen = {z["checklist_text"]: z for z in db.query("SELECT * FROM mat_inspection_result WHERE inspection_id = ?", (pid,))}
            journal = db.query("SELECT after_json FROM mat_audit WHERE entity = 'inspection' AND entity_id = ? AND "
                               "action = 'abgeschlossen'", (pid,), one=True)
        assert (zeilen["Platzhalter A2 optional"]["finding"], zeilen["Platzhalter A2 optional"]["value"],
                zeilen["Platzhalter A2 optional"]["note"]) == ("ok", "nein", "Platzhalter alt")
        assert zeilen["Platzhalter A3 optional"]["finding"] == "ok"
        assert not [t for t, z in zeilen.items() if z["finding"] == "mangel"]
        assert json.loads(journal["after_json"])["maengel"] == 0
        # Lebenslauf, Jahresbericht, CSV: keine Mängel.
        art = w.get(f"{API}/artikel/{a['id']}").json["artikel"]
        eintrag = next(x for x in art["pruefungen"] if x["id"] == pid)
        assert not eintrag.get("maengel"), eintrag
        b = w.get(f"{API}/ordner/{gid}/bericht").json["bericht"]
        assert b["pruefungen"]["mit_mangel"] == 0 and b["pruefungen"]["gesamt"] == 1, b["pruefungen"]
        from test_material_export import csv_lesen
        r = w.get(f"/materialablage/export/{gid}-pruefungen-{_heute().year}.csv")
        assert r.status_code == 200, r.status_code
        _kopf, csv_zeilen = csv_lesen(r.get_data())
        assert [z["Mängel"] for z in csv_zeilen] == ["0"], csv_zeilen
        # Prüfprotokoll: Befund „optional“, die Antwort im Wert, keine Mangel-Legende.
        r = w.get(f"/materialablage/pruefung/{pid}/pdf")
        assert r.status_code == 200
        pfad = os.path.join(tmp, "p.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.get_data())
        text = pdf_layout_seiten(pfad)
        zeilen_pdf = "\n".join(text).splitlines()

        def zeile(t):
            treffer = [z for z in zeilen_pdf if t in z]
            assert treffer, (t, zeilen_pdf)
            return " ".join(treffer[0].split())
        print("PDF:", " | ".join(zeile(t) for t in ("Platzhalter A1",) + OPTIONAL))
        assert zeile("Platzhalter A2 optional").endswith("Ja optional Nein"), zeile("Platzhalter A2 optional")
        assert "optional Platzhalter Antwort" in zeile("Platzhalter A3 optional"), zeile("Platzhalter A3 optional")
        assert zeile("Platzhalter S2 optional").endswith("optional 7"), zeile("Platzhalter S2 optional")
        assert zeile("Platzhalter B2 optional").endswith("optional 02.01.2026"), zeile("Platzhalter B2 optional")
        assert zeile("Platzhalter A1").endswith("Ja in Ordnung Ja"), zeile("Platzhalter A1")
        assert "nicht zutreffend" in zeile("Platzhalter V1")
        assert not any(z.strip() == "Nr. Mangel" or "Mangel" in z.split() for z in zeilen_pdf), [z for z in zeilen_pdf if "Mangel" in z]
        # Die Ansicht der festgeschriebenen Prüfung liefert die Antwort.
        x = next(y for y in w.get(f"{API}/pruefungen/{pid}").json["pruefung"]["punkte"] if y["text"] == "Platzhalter A2 optional")
        assert (x["befund"], x["wert"], x["pflicht"]) == ("ok", "nein", False)
    print("Dienst und Prüfprotokoll bestanden.")


# --- 2. Browser --------------------------------------------------------------------------------------------------------

GROESSEN = ((1280, 900, False), (360, 740, True))


def _db(u, pid):
    return {z["checklist_text"]: z for z in u.sql("SELECT checklist_text, finding, value, note FROM mat_inspection_result "
                                                  "WHERE inspection_id = ?", (pid,))}


def _toast(s, teil):
    return s.warte(f"[...document.querySelectorAll('.toast, [role=status], [role=alert]')].some((e) => "
                   f"e.textContent.includes({json.dumps(teil)}))", sek=6)


def _mitte(s, sel):
    """Das Element mitten ins Bild – sonst liegt es womöglich unter der klebenden Abschlussleiste."""
    s.js(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{ block: 'center' }})")
    s.b.warten(0.15)


def klick(s, sel):
    if not sel.startswith("dialog") and not sel.startswith("#einf"):
        _mitte(s, sel)
    return s.klick(sel)


def _mitte_trifft(s, sel):
    _mitte(s, sel)
    p = s.punkt(sel)
    assert p and p["trifft"], (sel, p)


def ablauf(u, ids, gid, breite, hoehe, touch):
    from einfuehrung_browser import PASSWORT, mail
    r = u.adm.post(f"{API}/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2025-01"})
    assert r.status_code == 201, r.get_json()
    p = u._anmelden(mail("pruefer"), PASSWORT)
    r = p.post(f"{API}/artikel/{r.json['artikel']['id']}/pruefungen", json={})
    assert r.status_code == 201, r.get_json()
    pid, n = r.json["pruefung"]["id"], ids_von(r.json["pruefung"])
    karte = lambda t: f"#pp-{n[t]}"   # noqa: E731
    s = u.seite("pruefer", breite, hoehe, touch)
    try:
        s.oeffnen(f"/materialablage/pruefung/{pid}", warten=0.6)
        assert s.warte("!!document.querySelector('.mat-punkt-text')")
        # Das Angebot der Übung (schwebende Karte unten) beim ersten Besuch: „Nicht jetzt“.
        if s.warte("!!document.querySelector('#einf-nicht-jetzt')", sek=3):
            assert klick(s, "#einf-nicht-jetzt") is None
            assert s.warte("!document.querySelector('#einf-nicht-jetzt')")
        # Knöpfe: je Gruppe und Untergruppe einer, mit Namen für Bildschirmleser, grau umrandet.
        knoepfe = s.js("""[...document.querySelectorAll('.mat-gruppenkopf')].map((k) => [k.querySelector('h3, h4').tagName,
          k.querySelector('h3, h4').textContent.trim(), (k.querySelector('.mat-alle-nz') || {}).className || '',
          k.querySelector('.mat-alle-nz') ? [k.querySelector('.mat-alle-nz').getAttribute('aria-label'),
          k.querySelector('.mat-alle-nz').textContent.trim(), k.querySelector('.mat-alle-nz').tabIndex] : null])""")
        assert [x[:2] for x in knoepfe] == [["H3", GA], ["H4", UK], ["H4", US], ["H3", GB], ["H3", GV]], knoepfe
        for _, name, klasse, knopf in knoepfe:
            assert klasse == "btn secondary small mat-alle-nz" and knopf == [f"{name}: alle Punkte nicht zutreffend", "alle n. z.", 0], knoepfe
        # Optionale Antwortpunkte: nur das Feld bzw. Ja/Nein – kein Befund, keine Bemerkung, kein Foto.
        def nur_antwort(t, art):
            return s.js(f"""(() => {{ const k = document.querySelector({json.dumps(karte(t))});
              return [k.querySelectorAll('[data-act=pbefund]').length, k.querySelectorAll('[data-act=pwert]').length,
                      k.querySelectorAll('.mat-pwert').length, !!k.querySelector('[data-act=pnotiz-auf], .mat-punkt-foto, input[type=file]'),
                      !!k.querySelector('.mat-pnotiz:not([hidden])'), k.classList.contains('mangel'), !!k.querySelector('.mat-pflicht'),
                      k.textContent.includes('optional')]; }})()""") == ([0, 2, 0, False, False, False, False, True] if art == "yesno"
                                                                       else [0, 0, 1, False, False, False, False, True])
        for t, art in (("Platzhalter A2 optional", "yesno"), ("Platzhalter A3 optional", "text"),
                       ("Platzhalter S2 optional", "number"), ("Platzhalter B2 optional", "date")):
            assert nur_antwort(t, art), t
        # Hin und her: „Nein“, „Ja“, „Nein“ – kein Mangel, kein Rot, kein Foto, keine Bemerkung.
        for w in ("nein", "ja", "nein"):
            assert klick(s, f'{karte("Platzhalter A2 optional")} [data-wert="{w}"]') is None
            assert s.warte(f"document.querySelector('{karte('Platzhalter A2 optional')} [data-wert=\"{w}\"]').getAttribute('aria-checked') === 'true'")
        assert nur_antwort("Platzhalter A2 optional", "yesno")
        assert (_db(u, pid)["Platzhalter A2 optional"]["finding"], _db(u, pid)["Platzhalter A2 optional"]["value"]) == ("ok", "nein")
        assert "Optionale Punkte nehmen nur ihre Antwort auf." in s.js("document.querySelector('.mat-punkte > .help').textContent")
        # Am Finger: 44 px, Tipp auf die Mitte trifft den Knopf.
        if touch:
            hoehen = s.js("[...document.querySelectorAll('.mat-alle-nz')].map((b) => b.getBoundingClientRect().height)")
            assert min(hoehen) >= 44, hoehen
            for sel in ('.mat-alle-nz[data-g="0"][data-u="-1"]', '.mat-alle-nz[data-g="0"][data-u="0"]',
                        '.mat-alle-nz[data-g="0"][data-u="1"]', '.mat-alle-nz[data-g="1"]', '.mat-alle-nz[data-g="2"]'):
                _mitte_trifft(s, sel)
        # Untergruppe „Körper“: nichts eingetragen → ohne Rückfrage, Toast mit Anzahl.
        assert klick(s, '.mat-alle-nz[data-g="0"][data-u="0"]') is None
        assert _toast(s, f"„{UK}“: 3 Punkte nicht zutreffend"), "Toast fehlt"
        assert not s.js("!!document.querySelector('dialog[open]')")
        d = _db(u, pid)
        assert [d[t]["finding"] for t in ("Platzhalter K1", "Platzhalter K2", "Platzhalter K3")] == ["nicht_zutreffend"] * 3, d
        assert d["Platzhalter A1"]["finding"] == "ok" and d["Platzhalter S1"]["finding"] == "ok"
        assert s.js(f"document.querySelector('{karte('Platzhalter K1')}').classList.contains('nz')")
        # Mangel an A1 (Pflicht, „Nein“) mit Bemerkung → Gruppe A fragt nach, mit Zahl.
        assert klick(s, f'{karte("Platzhalter A1")} [data-wert="nein"]') is None
        assert s.warte(f"document.querySelector('{karte('Platzhalter A1')}').classList.contains('mangel')")
        assert klick(s, '.mat-alle-nz[data-g="0"][data-u="-1"]') is None
        assert s.warte("!!document.querySelector('dialog[open] #c-titel')")
        frage = s.js("[document.querySelector('dialog[open] #c-titel').textContent, document.querySelector('dialog[open] .dlg-body p').textContent,"
                     " document.querySelector('dialog[open] #c-ok').className, document.querySelector('dialog[open] #c-ok').textContent]")
        assert frage[0] == f"„{GA}“: alle Punkte nicht zutreffend?" and frage[2:] == ["btn", "Alle n. z."], frage
        assert frage[1].startswith("Bei 1 von 2 Punkten ist schon etwas eingetragen: 1 Mangel."), frage
        if touch:
            for sel in ("dialog[open] #c-ok", "dialog[open] #c-no"):
                _mitte_trifft(s, sel)
        assert klick(s, "dialog[open] #c-no") is None
        assert s.warte("!document.querySelector('dialog[open]')")
        assert _db(u, pid)["Platzhalter A1"]["finding"] == "mangel"
        assert klick(s, '.mat-alle-nz[data-g="0"][data-u="-1"]') is None
        assert s.warte("!!document.querySelector('dialog[open] #c-ok')")
        assert klick(s, "dialog[open] #c-ok") is None
        assert _toast(s, f"„{GA}“: 2 Punkte nicht zutreffend"), "Toast fehlt"
        d = _db(u, pid)
        assert [d[t]["finding"] for t in ("Platzhalter A1", "Platzhalter K1", "Platzhalter S1")] == ["nicht_zutreffend"] * 3, d
        # Optionale Punkte bleiben, wie sie sind; Gruppe B unberührt.
        assert (d["Platzhalter A2 optional"]["finding"], d["Platzhalter A2 optional"]["value"]) == ("ok", "nein")
        assert d["Platzhalter S2 optional"]["finding"] == "ok" and d["Platzhalter B1"]["finding"] == "ok"
        assert not s.js(f"document.querySelector('{karte('Platzhalter A1')}').classList.contains('mangel')")
        # Zurück je Punkt: n. z. an A1 noch einmal → wieder der Sollwert.
        assert klick(s, f'{karte("Platzhalter A1")} [data-befund="nicht_zutreffend"]') is None
        assert s.warte(f"document.querySelector('{karte('Platzhalter A1')} [data-wert=\"ja\"]').getAttribute('aria-checked') === 'true'")
        assert (_db(u, pid)["Platzhalter A1"]["finding"], _db(u, pid)["Platzhalter A1"]["value"]) == ("ok", "ja")
        # 30 Punkte auf einmal (Festlegung 5: unter 1 s je Punkt-Anfrage).
        los = time.time()
        assert klick(s, '.mat-alle-nz[data-g="2"]') is None
        assert _toast(s, f"„{GV}“: 30 Punkte nicht zutreffend"), "Toast fehlt"
        dauer = time.time() - los
        print(f"  {breite}×{hoehe}: 30 Punkte n. z. in {dauer:.2f} s")
        assert dauer < 2.5, dauer
        assert {d["finding"] for t, d in _db(u, pid).items() if t.startswith("Platzhalter V")} == {"nicht_zutreffend"}
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        # Festschreiben danach über die Oberfläche (Unterschrift im Profil hinterlegt).
        s.js("document.querySelector('.mat-abschluss-ende').scrollIntoView({ block: 'end' })")
        s.b.warten(0.4)
        assert klick(s, '.mat-ergebnis [data-e="einsatzbereit"]') is None
        assert klick(s, "#pr-ok") is None
        assert s.warte("!!document.querySelector('dialog[open] #fs-ok')"), "Festschreib-Dialog fehlt"
        assert klick(s, "dialog[open] #fs-ok") is None
        assert s.warte("!document.querySelector('#pr-ok') && !!document.querySelector('.mat-protokoll')", sek=20), "nicht festgeschrieben"
        z = u.sql("SELECT completed_at, result FROM mat_inspection WHERE id = ?", (pid,))[0]
        assert z["completed_at"] and z["result"] == "einsatzbereit", z
        lesen = s.js("""[...document.querySelectorAll('.mat-befunde tbody tr')].filter((tr) => tr.textContent.includes('optional') && !tr.textContent.includes('Foto optional'))
          .map((tr) => tr.querySelector('[data-l=Befund]').textContent.trim())""")
        assert lesen and set(lesen) == {"optional"}, lesen
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()


def test_browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_material import freigeben, katalog_grund as grund, unterschrift_hinterlegen
    with Umgebung() as u:
        ids = grund(u.adm)
        formular(u.adm, ids["gurte"])
        gid = u.sql("SELECT id FROM mat_folder WHERE name = 'Übung Gliederung'")[0]["id"]
        freigeben(u.adm, gid, u.ids["pruefer"], "lesen")
        freigeben(u.adm, gid, u.ids["pruefer"], "pruefen")
        unterschrift_hinterlegen(u.app, u.ids["pruefer"])
        for breite, hoehe, touch in GROESSEN:
            los = time.time()
            ablauf(u, ids, gid, breite, hoehe, touch)
            print(f"Gruppe n. z. und optionale Punkte {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({time.time() - los:.1f} s)")


# --- 3. Statisch -------------------------------------------------------------------------------------------------------

def test_statisch():
    with open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8") as fh:
        js = fh.read()
    with open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8") as fh:
        css = fh.read()
    knopf = js[js.index("const alleNzKnopf"):]
    knopf = knopf[:knopf.index("\n")]
    assert 'class="btn secondary small mat-alle-nz"' in knopf and ': alle Punkte nicht zutreffend">alle n. z.</button>' in knopf
    aktion = js[js.index('"alle-nz": async'):js.index('"pnotiz-auf":')]
    assert "endgueltig: false" in aktion and "btn ghost" not in aktion and "!nurAntwort(x)" in aktion
    regel = ".mat-gruppenkopf > .mat-alle-nz { min-height: 44px; }"
    i = css.index(regel)
    assert css.rfind("@media (pointer: coarse) {", 0, i) > css.rfind("\n}\n", 0, i), regel
    with open(os.path.join(WURZEL, "app/static/js/uebung/material.js"), encoding="utf-8") as fh:
        assert "|| !p.pflicht ?" in fh.read()
    print("Statisch bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_dienst_und_protokoll()
    test_browser()
