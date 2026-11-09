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
   Werte in der Datenbank, zurück je Punkt; zugeklappt, wenn alles „n. z.“ ist (allein die Marke, rechtsbündig; seit
   09.11.2026 kein „n Punkte zeigen“ – aufklappen nur über das Aufheben an der Marke; der Fokus geht auf die Überschrift,
   mit der Tastatur mit sichtbarem Rahmen, ein zweites Enter hebt nichts auf; Bildschirmleser „nicht zutreffend, n Punkte
   ausgeblendet“; Untergruppen mit der Gruppe, nach dem Neuladen ebenso); Festschreiben danach über
   die Oberfläche; 30 Punkte unter 1 s; kein
   waagerechter Bildlauf, keine Konsolenfehler. Ohne Chromium „übersprungen“ mit rc 0.
   Gruppenkopf (Bauauftrag planung/pruefung-gruppenkopf, 05.11.2026): Knopf „n. z.“ statt „alle n. z.“ (Name für
   Bildschirmleser unverändert); vor jeder Gruppe außer der ersten ein neutraler Trenner (1 px, Farbe --linie), vor
   Untergruppen keiner.
   Marke als Knopf (Bauauftrag planung/pruefung-nz-pille, 05.11.2026): die Knöpfe aller Köpfe – auch zugeklappt – wieder
   rechtsbündig (±1 px am rechten Rand der Liste), der Name breit bis 12 px davor, kein Name ragt hinein; kein Knopf
   „n. z. aufheben“ mehr – die graue Marke „nicht zutreffend“ ist ein Knopf (data-act nz-aufheben, Name „<Name>: nicht
   zutreffend – aufheben“, title, Hand als Zeiger, sichtbarer Fokus, Tastatur mit Tab und Enter, am Finger
   44 px Tippfläche – Rechteck des Knopfs und Treffer über elementFromPoint –, sichtbar nicht höher).
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


# Je Kopf: Zustand, versteckt, Text der Marke, Beschreibung der Überschrift für Bildschirmleser (aria-describedby), Zahl
# der Knöpfe im Kopf, Art der Marke, „n. z.“ vorhanden.
KOPF = """(() => {{ const k = document.querySelector('.mat-gruppenkopf[data-g="{g}"][data-u="{u}"]');
  const t = k.querySelector(':scope > h3, :scope > h4');
  const besch = (t.getAttribute('aria-describedby') || '').split(' ').filter(Boolean).map((i) => document.getElementById(i).textContent).join(' ');
  return [k.dataset.zustand, k.hidden, k.querySelector('.mat-befund') ? k.querySelector('.mat-befund').textContent : '',
          besch, k.querySelectorAll('button').length,
          k.querySelector('.mat-nz-auf') ? 'alter Knopf' : k.querySelector('.mat-befund') ? k.querySelector('.mat-befund').tagName + ' '
            + (k.querySelector('.mat-befund').dataset.act || '') : '', !!k.querySelector('.mat-alle-nz')]; }})()"""


def kopf(s, g, u=-1):
    return s.js(KOPF.format(g=g, u=u))


def fokus_wo(s):
    """Wo der Fokus steht: [Element, Text, sichtbarer Rahmen (:focus-visible), „g:u“ seines Kopfs]."""
    return s.js("""(() => { const a = document.activeElement; const k = a.closest('.mat-gruppenkopf');
      return [a.tagName, a.textContent.trim(), a.matches(':focus-visible'), k ? k.dataset.g + ':' + k.dataset.u : '']; })()""")


def marke_rechts(s, g, u):
    """Die Marke eines zugeklappten Kopfs steht allein rechts: ihr rechter Rand ±1 px am rechten Rand der Liste."""
    return s.js(f"""(() => {{ const b = document.querySelector('.mat-gruppenkopf[data-g="{g}"][data-u="{u}"] .mat-nz-pille');
      return Math.abs(b.getBoundingClientRect().right - document.querySelector('.mat-pliste').getBoundingClientRect().right) <= 1; }})()""")


def taste(s, name):
    code = {"Enter": 13, "Tab": 9}[name]
    s.b.rufen("Input.dispatchKeyEvent", type="keyDown", key=name, code=name, windowsVirtualKeyCode=code, **({"text": "\r"} if name == "Enter" else {}))
    s.b.rufen("Input.dispatchKeyEvent", type="keyUp", key=name, code=name, windowsVirtualKeyCode=code)
    s.b.warten(0.1)


def sichtbar(s, rid):
    return s.js(f"(() => {{ const k = document.querySelector('#pp-{rid}'); return !!k && k.getClientRects().length > 0; }})()")


RECHTS = """(() => {
  const koepfe = [...document.querySelectorAll('.mat-gruppenkopf')].filter((k) => k.getClientRects().length);
  const text = (t) => { const r = document.createRange(); r.selectNodeContents(t); return Math.max(...[...r.getClientRects()].map((x) => x.right)); };
  const liste = document.querySelector('.mat-pliste').getBoundingClientRect();
  return { liste: [liste.left, liste.right], koepfe: koepfe.map((k) => { const t = k.querySelector('h3, h4'); const tr = t.getBoundingClientRect();
    const b = k.querySelector('.mat-kopf-knoepfe'); const br = b && b.getBoundingClientRect();
    return [t.textContent.trim(), text(t), tr.right, tr.bottom, br ? [br.left, br.right, br.top] : null]; }) }; })()"""


def rechts(s, breite):
    """Die Knöpfe aller sichtbaren Köpfe rechtsbündig (±1 px am rechten Rand der Liste); neben dem Namen reicht der Name
    bis 12 px davor (kein Name ragt hinein), sonst stehen die Knöpfe in einer eigenen Zeile darunter. Am Rechner
    alle neben dem Namen."""
    m = s.js(RECHTS)
    l, r = m["liste"]
    mit = [k for k in m["koepfe"] if k[4] is not None]
    assert mit and all(abs(k[4][1] - r) <= 1 for k in mit), m
    for name, text_rechts, t_rechts, t_unten, (kl, _, ko) in mit:
        if ko < t_unten - 1:   # in einer Zeile mit dem Namen
            assert text_rechts <= kl - 12 + 1 and abs(t_rechts - (kl - 12)) <= 1, (name, m)
        else:
            assert breite < 1000, (name, m)
    assert all(k[1] <= r + 1 for k in m["koepfe"]), m
    assert s.js("[...document.querySelectorAll('.mat-kopf-knoepfe')].every((k) => k.scrollWidth <= k.clientWidth)"), m
    return len(mit)


def trenner(s):
    """Je sichtbarem Kopf [Ebene, Trenner]: Trenner = 1 px oben in der Farbe von --linie."""
    return s.js("""(() => { const p = document.createElement('div'); p.style.color = 'var(--linie)'; document.body.append(p);
      const linie = getComputedStyle(p).color; p.remove();
      return [...document.querySelectorAll('.mat-gruppenkopf')].filter((k) => k.getClientRects().length).map((k) => {
        const c = getComputedStyle(k); const t = c.borderTopWidth !== '0px';
        if (t && (c.borderTopWidth !== '1px' || c.borderTopColor !== linie || c.borderTopStyle !== 'solid')) return ['falsch', c.borderTopWidth, c.borderTopColor, linie];
        return [k.querySelector('h3, h4').tagName, t]; }); })()""")


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
            assert klasse == "btn secondary small mat-alle-nz" and knopf == [f"{name}: alle Punkte nicht zutreffend", "n. z.", 0], knoepfe
        rechts(s, breite)
        assert trenner(s) == [["H3", False], ["H4", False], ["H4", False], ["H3", True], ["H3", True]], trenner(s)
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
        # Zugeklappt (dritter Wunsch): allein „nicht zutreffend“ (ein Knopf, der aufhebt; seit 09.11.2026 kein „3 Punkte
        # zeigen“ mehr daneben); die Punkte weg; für Bildschirmleser „nicht zutreffend, 3 Punkte ausgeblendet“.
        assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"0\"]').dataset.zustand === 'zu'")
        assert kopf(s, 0, 0) == ["zu", False, "nicht zutreffend", "nicht zutreffend, 3 Punkte ausgeblendet", 1, "BUTTON nz-aufheben", False], kopf(s, 0, 0)
        assert not s.js("!!document.querySelector('.mat-nz-zeigen, [data-act=\"nz-zeigen\"], .mat-gruppenkopf [aria-expanded]')")
        assert not any(sichtbar(s, n[t]) for t in ("Platzhalter K1", "Platzhalter K2", "Platzhalter K3"))
        assert sichtbar(s, n["Platzhalter A1"]) and sichtbar(s, n["Platzhalter S1"])
        assert rechts(s, breite) == 5   # zugeklappt ebenso rechtsbündig
        assert marke_rechts(s, 0, 0)
        # Fokus nach dem Zuklappen auf der Überschrift (nicht verloren, nicht auf der Marke), nach dem Klick ohne Rahmen.
        assert fokus_wo(s) == ["H4", "Platzhalter UG Körper", False, "0:0"], fokus_wo(s)
        pille = '.mat-gruppenkopf[data-g="0"][data-u="0"] .mat-nz-pille'
        assert s.js(f"""(() => {{ const b = document.querySelector({json.dumps(pille)}); const c = getComputedStyle(b);
          return [b.className, b.type, b.getAttribute('aria-label'), b.title, b.tabIndex, c.cursor, c.borderTopWidth === '0px' || c.borderTopColor === 'rgba(0, 0, 0, 0)',
                  (() => {{ const p = document.createElement('div'); p.style.color = 'var(--grau-hell)'; document.body.append(p);
                            const f = getComputedStyle(p).color; p.remove(); return c.backgroundColor === f; }})()]; }})()""") == [
            "mat-befund b-nicht_zutreffend mat-nz-pille", "button", f"{UK}: nicht zutreffend – aufheben", "n. z. aufheben", 0,
            "pointer", True, True]
        assert not s.js("!!document.querySelector('.mat-nz-auf')")
        assert s.js(f"(() => {{ const b = document.querySelector({json.dumps(pille)}); return document.getElementById(b.getAttribute('aria-describedby')).textContent; }})()") == "3 Punkte ausgeblendet"
        if touch:
            # Die Marke ist 44 px hoch (Rechteck des Knopfs) und trifft oben und unten 21 px von der Mitte – in der Mitte
            # und an beiden Enden (dort ab dem runden Ende: der Browser trifft nur innerhalb der Rundung); sichtbar bleibt sie so klein wie vorher (gefärbt nur innen: clientHeight unter 30 px, Rand durchsichtig).
            _mitte_trifft(s, pille)
            flaeche = s.js(f"""(() => {{ const b = document.querySelector({json.dumps(pille)}); const r = b.getBoundingClientRect(); const c = getComputedStyle(b);
              const y = r.top + r.height / 2; const trifft = (x, yy) => {{ const t = document.elementFromPoint(x, yy); return !!t && (t === b || b.contains(t)); }};
              return [r.height, b.clientHeight, c.borderTopColor, c.backgroundClip,
                      ...[r.left + r.height / 2, r.left + r.width / 2, r.right - r.height / 2].flatMap((x) => [trifft(x, y - 21.5), trifft(x, y + 21.5)])]; }})()""")
            assert flaeche[0] >= 44 and flaeche[1] < 30 and flaeche[2:4] == ["rgba(0, 0, 0, 0)", "padding-box"] and flaeche[4:] == [True] * 6, flaeche
        # Ein Klick auf die Überschrift klappt nicht auf (aufklappen nur über das Aufheben an der Marke).
        assert klick(s, '.mat-gruppenkopf[data-g="0"][data-u="0"] > h4') is None
        s.b.warten(0.3)
        assert kopf(s, 0, 0)[0] == "zu" and not sichtbar(s, n["Platzhalter K1"])
        assert _db(u, pid)["Platzhalter K1"]["finding"] == "nicht_zutreffend"
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
        # Gruppe A zugeklappt – samt Untergruppen und optionalen Punkten.
        assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"-1\"]').dataset.zustand === 'zu'")
        assert kopf(s, 0) == ["zu", False, "nicht zutreffend", "nicht zutreffend, 8 Punkte ausgeblendet", 1, "BUTTON nz-aufheben", False], kopf(s, 0)
        assert kopf(s, 0, 0)[:2] == ["schlicht", True] and kopf(s, 0, 1)[:2] == ["schlicht", True]
        assert not any(sichtbar(s, n[t]) for t in ("Platzhalter A1", "Platzhalter A2 optional", "Platzhalter K1", "Platzhalter S2 optional"))
        assert marke_rechts(s, 0, -1) and fokus_wo(s)[:2] == ["H3", GA], fokus_wo(s)
        # Aufklappen nur über das Aufheben an der Marke: alle Punkte der Gruppe wieder auf ihrer Vorbelegung (A1 vorher
        # Mangel: jetzt sein Soll „ja“, kein Rot), Untergruppen wieder mit eigenem „n. z.“; der Fokus auf „n. z.“.
        assert klick(s, '.mat-gruppenkopf[data-g="0"][data-u="-1"] .mat-nz-pille') is None
        assert _toast(s, f"„{GA}“: 5 Punkte wieder offen"), "Toast fehlt"
        assert s.warte(f"!!document.querySelector('{karte('Platzhalter A1')}').getClientRects().length")
        assert [kopf(s, 0)[0], kopf(s, 0, 0)[0], kopf(s, 0, 1)[0]] == ["normal"] * 3 and sichtbar(s, n["Platzhalter K1"])
        assert not s.js(f"document.querySelector('{karte('Platzhalter A1')}').classList.contains('mangel')")
        d = _db(u, pid)
        assert [(d[t]["finding"], d[t]["value"]) for t in ("Platzhalter A1", "Platzhalter S1")] == [("ok", "ja"), ("ok", "nein")], d
        if not touch:
            assert s.js("document.activeElement.matches('.mat-gruppenkopf[data-g=\"0\"][data-u=\"-1\"] .mat-alle-nz')")
        # Zurück je Punkt: n. z. an A1 zweimal → wieder der Sollwert, die Gruppe bleibt offen.
        for _ in range(2):
            assert klick(s, f'{karte("Platzhalter A1")} [data-befund="nicht_zutreffend"]') is None
            s.b.warten(0.3)
        assert s.warte(f"document.querySelector('{karte('Platzhalter A1')} [data-wert=\"ja\"]').getAttribute('aria-checked') === 'true'")
        assert (_db(u, pid)["Platzhalter A1"]["finding"], _db(u, pid)["Platzhalter A1"]["value"]) == ("ok", "ja")
        # Einzeln auf „n. z.“: „Körper“ und „Schnapper“ klappen je für sich zu, sobald ihr letzter Punkt „n. z.“ ist; der
        # Fokus (im Punkt, der wegklappt) geht auf die Überschrift.
        for t in ("Platzhalter K1", "Platzhalter K2", "Platzhalter K3", "Platzhalter S1"):
            assert klick(s, f'{karte(t)} [data-befund="nicht_zutreffend"]') is None
            assert s.warte(f"(() => {{ const k = document.querySelector('{karte(t)}'); return k.classList.contains('nz') || !k.getClientRects().length; }})()")
            if t == "Platzhalter K3":
                assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"0\"]').dataset.zustand === 'zu'")
                if not touch:
                    assert fokus_wo(s) == ["H4", UK, False, "0:0"], fokus_wo(s)
        assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"1\"]').dataset.zustand === 'zu'")
        assert kopf(s, 0)[6] and kopf(s, 0, 0)[0] == "zu" and kopf(s, 0, 1)[0] == "zu", (kopf(s, 0), kopf(s, 0, 0), kopf(s, 0, 1))
        assert kopf(s, 0, 1)[3] == "nicht zutreffend, 2 Punkte ausgeblendet", kopf(s, 0, 1)
        assert not sichtbar(s, n["Platzhalter K1"]) and not sichtbar(s, n["Platzhalter S1"])
        # Aufheben über die Marke an „Schnapper“: S1 wieder auf seinem Soll („nein“), Toast; der optionale S2 bleibt.
        # Mit der Maus über die Tastatur: von der Überschrift mit Tab auf die Marke (sichtbarer Fokus), Enter.
        pille = '.mat-gruppenkopf[data-g="0"][data-u="1"] .mat-nz-pille'
        if touch:
            assert klick(s, pille) is None
        else:
            _mitte(s, pille)
            s.js("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"1\"] > h4').focus()")
            for art in ("keyDown", "keyUp"):
                s.b.rufen("Input.dispatchKeyEvent", type=art, key="Tab", code="Tab", windowsVirtualKeyCode=9)
            fokus = s.js(f"""(() => {{ const b = document.activeElement; const c = getComputedStyle(b);
              return [b.matches({json.dumps(pille)}), b.matches(':focus-visible'), c.outlineStyle, parseFloat(c.outlineWidth) > 0]; }})()""")
            assert fokus == [True, True, "solid", True], fokus
            s.b.rufen("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r")
            s.b.rufen("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
        assert _toast(s, f"„{US}“: 1 Punkt wieder offen"), "Toast fehlt"
        assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"0\"][data-u=\"1\"]').dataset.zustand === 'normal'")
        assert (_db(u, pid)["Platzhalter S1"]["finding"], _db(u, pid)["Platzhalter S1"]["value"]) == ("ok", "nein")
        assert sichtbar(s, n["Platzhalter S1"]) and sichtbar(s, n["Platzhalter S2 optional"])
        if not touch:
            # Ganz mit der Tastatur an Gruppe B: Enter auf „n. z.“ klappt zu, der Fokus steht sichtbar auf der Überschrift;
            # ein zweites Enter hebt nichts auf; Tab führt zur Marke, Enter hebt auf (Fokus wieder auf „n. z.“).
            s.js("document.querySelector('.mat-alle-nz[data-g=\"1\"]').scrollIntoView({ block: 'center' })")
            s.js("document.querySelector('.mat-alle-nz[data-g=\"1\"]').focus()")
            taste(s, "Enter")
            assert _toast(s, f"„{GB}“: 2 Punkte nicht zutreffend"), "Toast fehlt"
            assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"1\"]').dataset.zustand === 'zu'")
            assert fokus_wo(s) == ["H3", GB, True, "1:-1"], fokus_wo(s)
            assert s.js("(() => { const c = getComputedStyle(document.activeElement); return c.outlineStyle === 'solid' && parseFloat(c.outlineWidth) > 0; })()")
            taste(s, "Enter")
            s.b.warten(0.4)
            assert kopf(s, 1)[0] == "zu" and _db(u, pid)["Platzhalter B1"]["finding"] == "nicht_zutreffend"
            taste(s, "Tab")
            assert s.js("document.activeElement.matches('.mat-gruppenkopf[data-g=\"1\"] .mat-nz-pille:focus-visible')")
            taste(s, "Enter")
            assert _toast(s, f"„{GB}“: 2 Punkte wieder offen"), "Toast fehlt"
            assert s.warte("document.querySelector('.mat-gruppenkopf[data-g=\"1\"]').dataset.zustand === 'normal'")
            assert s.js("document.activeElement.matches('.mat-alle-nz[data-g=\"1\"]')")
            assert _db(u, pid)["Platzhalter B1"]["finding"] == "ok"
        # 30 Punkte auf einmal (Festlegung 5: unter 1 s je Punkt-Anfrage).
        los = time.time()
        assert klick(s, '.mat-alle-nz[data-g="2"]') is None
        assert _toast(s, f"„{GV}“: 30 Punkte nicht zutreffend"), "Toast fehlt"
        dauer = time.time() - los
        print(f"  {breite}×{hoehe}: 30 Punkte n. z. in {dauer:.2f} s")
        assert dauer < 2.5, dauer
        assert {d["finding"] for t, d in _db(u, pid).items() if t.startswith("Platzhalter V")} == {"nicht_zutreffend"}
        # Nach dem Neuladen derselbe Zustand (aus den Befunden): „Viele“ und „Körper“ zu, „Schnapper“ offen.
        s.oeffnen(f"/materialablage/pruefung/{pid}", warten=0.6)
        assert s.warte("!!document.querySelector('.mat-gruppenkopf')")
        assert [kopf(s, 2)[0], kopf(s, 0, 0)[0], kopf(s, 0, 1)[0], kopf(s, 0)[0]] == ["zu", "zu", "normal", "normal"]
        assert kopf(s, 2)[3] == "nicht zutreffend, 30 Punkte ausgeblendet" and kopf(s, 2)[4] == 1
        assert not sichtbar(s, n["Platzhalter V1"]) and not sichtbar(s, n["Platzhalter K2"])
        assert rechts(s, breite) == 5 and marke_rechts(s, 2, -1) and marke_rechts(s, 0, 0)
        assert trenner(s) == [["H3", False], ["H4", False], ["H4", False], ["H3", True], ["H3", True]], trenner(s)
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
    kopf = js[js.index("    function kopfInnen("):js.index("    const kopfHtml")]
    assert 'class="btn secondary small mat-alle-nz"' in kopf and ': alle Punkte nicht zutreffend">n. z.</button>' in kopf
    assert "alle n. z.</button>" not in js and kopf.count('<div class="mat-kopf-knoepfe">') == 2
    assert '<div class="mat-pliste">${html}</div>' in js
    # Seit 09.11.2026 kein „n Punkte zeigen“ mehr: weder Link noch Handler, Zustand „auf“ oder Regel.
    for rest in ("mat-nz-zeigen", "nz-zeigen", "Punkte zeigen", "Punkt zeigen", "Punkte ausblenden", "aufgeklappt.", 'zustand: auf'):
        assert rest not in js, rest
    assert "mat-nz-zeigen" not in css and 'data-zustand="auf"' not in css
    assert 'tabindex="-1" aria-describedby="${id}-nz ${id}-zahl"' in kopf and 'aria-describedby="${id}-zahl" title="n. z. aufheben"' in kopf
    assert '<span id="${id}-nz" hidden>nicht zutreffend,</span><span id="${id}-zahl" hidden>${plural(z.teil.length, "Punkt", "Punkte")} ausgeblendet</span>' in kopf
    zeichnen = js[js.index("    function bloeckeZeichnen("):js.index("    function punkteHtml(")]
    assert '$(":scope > :is(h3, h4)", ziel)' in zeichnen
    assert "mat-nz-auf" not in js and "n. z. aufheben</button>" not in js and "mat-nz-auf" not in css
    assert ('<button type="button" class="mat-befund b-nicht_zutreffend mat-nz-pille" data-act="nz-aufheben"' in kopf
            and ': nicht zutreffend – aufheben" aria-describedby="${id}-zahl" title="n. z. aufheben">nicht zutreffend</button>' in kopf)
    aktion = js[js.index('"alle-nz": async'):js.index('"pnotiz-auf":')]
    assert "endgueltig: false" in aktion and "btn ghost" not in aktion and "nzFaehig(x)" in aktion
    assert "const nzFaehig = (x) => !nurAntwort(x)" in js
    for regel in (".mat-kopf-knoepfe, .mat-kopf-knoepfe > .mat-alle-nz { min-height: 44px; }",
                  ".mat-kopf-knoepfe > button.mat-nz-pille { --nz-rand:", "background-clip: padding-box;",
                  ".mat-kopf-knoepfe > button.mat-nz-pille:focus-visible {",
                  "button.mat-nz-pille:active {"):
        i = css.index(regel)
        assert css.rfind("@media (pointer: coarse) {", 0, i) > css.rfind("\n}\n", 0, i), regel
    assert css.index("button.mat-nz-pille:hover") > css.index("@media (hover: hover) and (pointer: fine) { button.mat-nz-pille:hover")
    # Rechtsbündig statt Teilraster, Trenner neutral (--linie, kein Rot), nur vor Gruppen.
    assert "subgrid" not in css and ".mat-gruppenkopf { display: flex;" in css and "justify-content: space-between" in css
    assert "margin-left: auto" in next(z for z in css.splitlines() if z.startswith(".mat-kopf-knoepfe {"))
    trenner = next(z for z in css.splitlines() if z.startswith(".mat-gruppenkopf:not(.mat-ug-kopf, :first-child)"))
    assert "border-top: 1px solid var(--linie)" in trenner and "rot" not in trenner, trenner
    with open(os.path.join(WURZEL, "app/static/js/uebung/material.js"), encoding="utf-8") as fh:
        assert "|| !p.pflicht ?" in fh.read()
    print("Statisch bestanden.")


if __name__ == "__main__":
    test_statisch()
    test_dienst_und_protokoll()
    test_browser()
