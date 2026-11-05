"""Bestand: die Ordnerseite zeigt den ganzen Zweig mit Überschriften je Unterordner (Wunsch des Nutzers vom 05.11.2026,
Bauauftrag planung/bestand-zweig/auftrag.md):  python tests/test_material_bestand_zweig.py  oder  pytest

1. Dienst und Schnittstelle: Gruppen in Baumreihenfolge (erst direkt im Ordner, dann je Unterordner mit Pfad relativ zum
   Ordner, leere fehlen), „Gesperrt“ dabei, „Ausgesondert“ nur mit dem Filter „ausgesondert“ (und auf seiner eigenen
   Seite), ein Ordner ohne Unterordner wie bisher; Filter (Status, „Aussonderung empfohlen“, Kategorie, „Zugeordnet an“)
   und ihre Zahlen im ganzen Zweig; Nachladen je Gruppe (ab, pro_gruppe) und Sortierung innerhalb jeder Gruppe.
2. Rechte: nur sichtbare Ordner und Artikel – ein Konto mit Freigabe an einem Unterordner öffnet den Oberordner nicht
   (404), sieht in seinem Zweig keine fremden Gruppen und holt keine fremde Gruppe nach (404); eine fremde Gliederung
   antwortet 404. Liste und Gruppenzahlen kommen aus gleich vielen Abfragen auf mat_item, egal wie viele Gruppen
   (kein Abruf je Gruppe); Antwortzeit bei 1000 Artikeln in 20 Unterordnern (gemessen, ausgegeben).
3. Oberfläche: statisch (material.js, Übungsdatei, material.css) und im Browser (1280×900 Maus, 360×740 Touch):
   Überschriften, „Weitere n anzeigen“, Filter (am Telefon in der Schublade), Mehrfachauswahl über Gruppen samt
   Gruppen-Häkchen und Verschieben, Leerzustand, Tippflächen gemessen. Ohne Chromium „übersprungen“.
Alles Platzhalter."""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (festschreiben, freigeben, gliederung, katalog_grund, neuer_artikel, neues_konto,  # noqa: E402
                           pruef_formulare, starten, umgebung)

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


class T:
    pass


def _ordner(c, name, parent, kind="standort"):
    r = c.post(f"{API}/ordner", json={"name": name, "kind": kind, "parent_id": parent})
    assert r.status_code == 201, r.get_json()
    return r.json["ordner"]["id"]


def _geprueft(t, iid, ergebnis="einsatzbereit", grund=""):
    r = starten(t.p, iid)
    assert r.status_code in (200, 201), r.get_json()
    d = {"ergebnis": ergebnis}
    if grund:
        d["grund"] = grund
    r = festschreiben(t.p, r.json["pruefung"]["id"], **d)
    assert r.status_code == 200, r.get_json()


def aufbau(tmp):
    """OG Nordstadt mit Zentrallager › Regal 3, Fahrzeug (ohne eigene Artikel) und Fahrzeug › Tasche; je ein Artikel direkt
    in der Gliederung und im Lager, drei im Regal (einer gesperrt → „Gesperrt“), einer in der Tasche ausgesondert (über
    „aussondern empfohlen“). Dazu die fremde Gliederung OG Südstadt."""
    t = T()
    t.app, k = umgebung(tmp)
    t.k, t.adm, t.w, t.p, t.mv = k, k["adm"], k["wart"], k["pruefer"], k["katalog"]
    t.ids = katalog_grund(t.adm)
    pruef_formulare(k["katalog"], t.ids)
    t.ga, t.sys = gliederung(t.adm, "OG Nordstadt")
    t.gb, _ = gliederung(t.adm, "OG Südstadt", standard=False)
    t.lager = _ordner(t.w, "Zentrallager", t.ga)
    t.regal = _ordner(t.w, "Regal 3", t.lager)
    t.fahrzeug = _ordner(t.w, "Fahrzeug", t.ga, "fahrzeug")
    t.tasche = _ordner(t.w, "Tasche", t.fahrzeug, "set")
    hms = t.ids["hms"]
    t.a_gl = neuer_artikel(t.w, hms, t.ga, serial_no="Z-GL")["id"]
    t.a_lager = neuer_artikel(t.w, hms, t.lager, serial_no="Z-LA")["id"]
    t.a_regal = [neuer_artikel(t.w, hms, t.regal, serial_no=f"Z-RE-{n}")["id"] for n in range(3)]
    t.a_gurt = neuer_artikel(t.w, t.ids["gurt"], t.regal, serial_no="Z-GU", manufactured_on="2025-01")["id"]
    t.a_aus = neuer_artikel(t.w, hms, t.tasche, serial_no="Z-AUS")["id"]
    _geprueft(t, t.a_regal[2], "aussondern_empfohlen", "Platzhalter")          # gesperrt, Empfehlung
    _geprueft(t, t.a_aus, "aussondern_empfohlen", "Platzhalter")
    r = t.w.post(f"{API}/artikel/{t.a_aus}/aussondern", json={"grund": "irreparabel"})
    assert r.status_code == 200, r.get_json()
    t.b1 = neuer_artikel(t.adm, hms, t.gb, serial_no="Z-SUED")["id"]
    return t


def lesen(c, fid, **q):
    r = c.get(f"{API}/ordner/{fid}", query_string=q)
    assert r.status_code == 200, r.get_json()
    return r.json["ordner"]


def gruppen(o):
    return [(g["id"], g["pfad"], g["gesamt"]) for g in o["gruppen"]]


def ids_je_gruppe(o):
    out = {}
    for a in o["artikel"]:
        out.setdefault(a["folder_id"], []).append(a["id"])
    return out


# --- 1. Dienst und Schnittstelle ------------------------------------------------------------------------------------

def test_zweig_gruppen_und_filter():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        o = lesen(t.w, t.ga)
        # Baumreihenfolge: die Gliederung selbst, Lager, Regal, (Fahrzeug und Tasche ohne Treffer fehlen), Gesperrt.
        assert gruppen(o) == [(t.ga, [], 1), (t.lager, ["Zentrallager"], 1), (t.regal, ["Zentrallager", "Regal 3"], 3),
                              (t.sys["gesperrt"], ["Gesperrt"], 1)], gruppen(o)
        assert [g["system_kind"] for g in o["gruppen"]] == [None, None, None, "gesperrt"]
        assert ids_je_gruppe(o) == {t.ga: [t.a_gl], t.lager: [t.a_lager], t.regal: sorted([t.a_regal[0], t.a_regal[1], t.a_gurt]),
                                    t.sys["gesperrt"]: [t.a_regal[2]]}, ids_je_gruppe(o)
        # Die Artikel kommen gruppenweise hintereinander, in Gruppenreihenfolge.
        folge = [a["folder_id"] for a in o["artikel"]]
        assert folge == sorted(folge, key=[g["id"] for g in o["gruppen"]].index)
        assert o["artikel_gesamt"] == 6 and o["pro_gruppe"] == 50
        # Abschnitt „Unterordner“ bleibt: nur die direkten (nach Position und Name, Systemordner zuletzt).
        assert [u["id"] for u in o["unterordner"]] == [t.fahrzeug, t.lager, t.sys["gesperrt"], t.sys["ausgesondert"]]
        # Zahlen im ganzen Zweig – auch die ausgesonderten (für den Filter „ausgesondert“), dazu die Empfehlung.
        z = o["zahlen"]
        assert (z["neu"], z["gesperrt"], z["ausgesondert"], o["empfohlen"]) == (5, 1, 1, 1), (z, o["empfohlen"])
        assert {k["name"]: k["n"] for k in o["kategorien"]} == {"Karabiner": 5, "Gurte": 1}, o["kategorien"]
        # „Direkt“ zählt wie im Baum nur, was direkt hier liegt.
        assert sum(o["direkt"].values()) == 1
        # Ausgesondert nur mit dem Filter – dann als eigene Gruppe; auf der Seite von „Ausgesondert“ ohne Filter.
        o = lesen(t.w, t.ga, status="ausgesondert")
        assert gruppen(o) == [(t.sys["ausgesondert"], ["Ausgesondert"], 1)] and [a["id"] for a in o["artikel"]] == [t.a_aus]
        assert {k["name"]: k["n"] for k in o["kategorien"]} == {"Karabiner": 1}
        o = lesen(t.w, t.sys["ausgesondert"])
        assert gruppen(o) == [(t.sys["ausgesondert"], [], 1)] and o["artikel_gesamt"] == 1
        # Ein Ordner ohne Unterordner sieht aus wie bisher: eine Gruppe ohne Pfad.
        o = lesen(t.w, t.regal)
        assert gruppen(o) == [(t.regal, [], 3)] and o["unterordner"] == []
        # Statusfilter im Zweig: gesperrt → nur die Gruppe „Gesperrt“; Aussonderung empfohlen ebenso.
        assert gruppen(lesen(t.w, t.ga, status="gesperrt")) == [(t.sys["gesperrt"], ["Gesperrt"], 1)]
        o = lesen(t.w, t.ga, status="aussonderung_empfohlen")
        assert [a["id"] for a in o["artikel"]] == [t.a_regal[2]]
        # Kategorie im Zweig: Gurte → nur das Regal; die Statuszahlen zählen mit der Kategorie, die Kategorien ohne sie.
        o = lesen(t.w, t.ga, kategorie=t.ids["gurte"])
        assert gruppen(o) == [(t.regal, ["Zentrallager", "Regal 3"], 1)]
        assert sum(o["zahlen"].values()) == 1 and len(o["kategorien"]) == 2
        o = lesen(t.w, t.ga, kategorie=999999)
        assert o["gruppen"] == [] and o["artikel"] == [] and o["artikel_gesamt"] == 0
        # Zugeordnet an: über den ganzen Zweig; die Zahlen zählen ohne den Personenfilter.
        r = t.w.post(f"{API}/artikel/zuordnen", json={"ids": [t.a_regal[0], t.a_gl], "user_id": t.k["fuehrung_id"]})
        assert r.status_code == 200, r.get_json()
        o = lesen(t.w, t.ga, zugeordnet=t.k["fuehrung_id"])
        assert gruppen(o) == [(t.ga, [], 1), (t.regal, ["Zentrallager", "Regal 3"], 1)]
        assert sum(o["zahlen"].values()) == 7
        # Unbekannter Status und Sortierspalte: 400 wie bisher.
        assert t.w.get(f"{API}/ordner/{t.ga}?status=quatsch").status_code == 400
        assert t.w.get(f"{API}/ordner/{t.ga}?sort=quatsch").status_code == 400
    print("Zweig mit Gruppen, Filter und Zahlen bestanden.")


def test_nachladen_und_sortierung():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        weitere = [neuer_artikel(t.w, t.ids["hms"], t.regal, serial_no=f"Z-MEHR-{n:02d}")["id"] for n in range(6)]
        alle_regal = sorted([t.a_regal[0], t.a_regal[1], t.a_gurt] + weitere)
        o = lesen(t.w, t.ga, pro_gruppe=4)
        assert gruppen(o)[2] == (t.regal, ["Zentrallager", "Regal 3"], 9) and o["pro_gruppe"] == 4
        geholt = ids_je_gruppe(o)[t.regal]
        assert len(geholt) == 4
        # Nachladen ab 4 und ab 8 mit derselben Größe: zusammen alle, in der Reihenfolge der Inventarnummer.
        for ab in (4, 8):
            r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.regal}?ab={ab}&pro_gruppe=4")
            assert r.status_code == 200 and r.json["gesamt"] == 9 and r.json["ab"] == ab, r.get_json()
            geholt += [a["id"] for a in r.json["artikel"]]
        assert geholt == alle_regal, geholt
        # Sortierung innerhalb jeder Gruppe: Seriennummer absteigend – die Gruppen bleiben in Baumreihenfolge.
        o = lesen(t.w, t.ga, sort="serie", richtung="ab", pro_gruppe=4)
        assert [g["id"] for g in o["gruppen"]] == [t.ga, t.lager, t.regal, t.sys["gesperrt"]]
        regal = [a["serial_no"] for a in o["artikel"] if a["folder_id"] == t.regal]
        alle_serien = sorted([f"Z-RE-{n}" for n in range(2)] + ["Z-GU"] + [f"Z-MEHR-{n:02d}" for n in range(6)], reverse=True)
        assert regal == alle_serien[:4], regal
        r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.regal}?ab=4&pro_gruppe=4&sort=serie&richtung=ab")
        assert [a["serial_no"] for a in r.json["artikel"]] == alle_serien[4:8]
        # Nachladen mit Filtern: Kategorie Gurte im Regal → nur der Gurt.
        r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.regal}?kategorie={t.ids['gurte']}")
        assert [a["id"] for a in r.json["artikel"]] == [t.a_gurt] and r.json["gesamt"] == 1
        # Ausgesondert nachladen nur mit dem Filter.
        r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.sys['ausgesondert']}")
        assert r.status_code == 200 and r.json["artikel"] == []
        r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.sys['ausgesondert']}?status=ausgesondert")
        assert [a["id"] for a in r.json["artikel"]] == [t.a_aus]
        # Eine Gruppe außerhalb des Zweigs: 404 (Geschwister, Oberordner, fremde Gliederung, Unbekanntes).
        for fid, gid in ((t.lager, t.fahrzeug), (t.regal, t.lager), (t.ga, t.gb), (t.ga, 999999)):
            assert t.w.get(f"{API}/ordner/{fid}/gruppe/{gid}").status_code == 404, (fid, gid)
        # Grenzen: pro_gruppe wird auf 1 … 500 begrenzt, ab nie negativ.
        assert lesen(t.w, t.ga, pro_gruppe=-5)["pro_gruppe"] == 1
        assert lesen(t.w, t.ga, pro_gruppe=10 ** 6)["pro_gruppe"] == 500
        r = t.w.get(f"{API}/ordner/{t.ga}/gruppe/{t.regal}?ab=-3")
        assert r.status_code == 200 and r.json["ab"] == 0
    print("Nachladen und Sortierung je Gruppe bestanden.")


# --- 2. Rechte, Abfragen, Leistung -----------------------------------------------------------------------------------

def test_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        # Ein Konto mit Lesefreigabe nur am Zentrallager.
        c, uid = neues_konto(t.app, "lager-leser@example.org")
        freigeben(t.adm, t.lager, uid, "lesen")
        assert c.get(f"{API}/ordner/{t.ga}").status_code == 404
        assert c.get(f"{API}/ordner/{t.ga}/gruppe/{t.lager}").status_code == 404
        o = lesen(c, t.lager)
        assert gruppen(o) == [(t.lager, [], 1), (t.regal, ["Regal 3"], 3)], gruppen(o)
        assert sum(o["zahlen"].values()) == 4 and o["artikel_gesamt"] == 4
        # Der gesperrte Artikel aus dem Regal liegt in „Gesperrt“ der Gliederung – dort (teilweise sichtbar) sieht das
        # Konto ihn, im Zweig des Lagers nicht; eine fremde Gruppe holt es nicht nach.
        assert c.get(f"{API}/ordner/{t.lager}/gruppe/{t.sys['gesperrt']}").status_code == 404
        o = lesen(c, t.sys["gesperrt"])
        assert o.get("teilweise") and [a["id"] for a in o["artikel"]] == [t.a_regal[2]]
        # Fremde Gliederung: 404, auch über die Gruppe; die Material-Verwaltung sieht beide.
        assert t.w.get(f"{API}/ordner/{t.gb}").status_code == 404
        assert t.w.get(f"{API}/ordner/{t.gb}/gruppe/{t.gb}").status_code == 404
        assert [a["id"] for a in lesen(t.mv, t.gb)["artikel"]] == [t.b1]
        assert lesen(t.mv, t.ga)["artikel_gesamt"] == 6
        # Ohne Grundrecht kein Personenfilter: Prüfer (lesen + prüfen) sehen die Liste, der Filter gilt nur mit Grundrecht.
        o = lesen(t.p, t.ga)
        assert o["artikel_gesamt"] == 6
    print("Rechte im Zweig bestanden.")


def _zaehle_artikelabfragen(app, aufruf):
    """Wie oft db.query mit einer Abfrage auf mat_item läuft, während aufruf() die Ordnerseite holt."""
    from app import db
    zahl = [0]
    original = db.query

    def zaehlend(sql, *a, **k):
        if "FROM mat_item" in sql:
            zahl[0] += 1
        return original(sql, *a, **k)
    db.query = zaehlend
    try:
        aufruf()
    finally:
        db.query = original
    return zahl[0]


def test_abfragen_und_leistung():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        hms = t.ids["hms"]
        # Zwei Gliederungen mit je 6 Artikeln: einmal in einem Unterordner, einmal in sechs.
        g1, _ = gliederung(t.adm, "OG Eins")
        g2, _ = gliederung(t.adm, "OG Zwei")
        u1 = _ordner(t.w, "Platzhalter A", g1)
        for n in range(6):
            neuer_artikel(t.w, hms, u1, serial_no=f"Q1-{n}")
            neuer_artikel(t.w, hms, _ordner(t.w, f"Platzhalter {n}", g2), serial_no=f"Q2-{n}")
        eins = _zaehle_artikelabfragen(t.app, lambda: lesen(t.w, g1))
        zwei = _zaehle_artikelabfragen(t.app, lambda: lesen(t.w, g2))
        assert len(lesen(t.w, g2)["gruppen"]) == 6
        assert eins == zwei, (eins, zwei)
        # Leistung: 1000 Artikel in 20 Unterordnern (je 50 – jede Gruppe ganz geladen) direkt über den Dienst angelegt.
        g3, _ = gliederung(t.adm, "OG Leistung")
        ordner = [_ordner(t.w, f"Platzhalter Regal {n:02d}", g3) for n in range(20)]
        with t.app.test_request_context():
            from flask import g
            from app import db
            from app.material.services import bestand
            g.user = db.query("SELECT * FROM users WHERE email = 'wart@example.org'", one=True)
            g.mat_akteur = "Test"
            for n in range(1000):
                with db.transaction():
                    bestand.artikel_anlegen({"product_id": hms, "folder_id": ordner[n % 20], "serial_no": f"L-{n:04d}"})
        zeiten = []
        for _ in range(3):
            los = time.perf_counter()
            o = lesen(t.w, g3)
            zeiten.append(time.perf_counter() - los)
        assert o["artikel_gesamt"] == 1000 and len(o["gruppen"]) == 20 and len(o["artikel"]) == 1000
        los = time.perf_counter()
        r = t.w.get(f"{API}/ordner/{g3}/gruppe/{ordner[3]}?ab=25")
        nachladen = time.perf_counter() - los
        assert r.status_code == 200 and len(r.json["artikel"]) == 25
        print(f"Ordnerseite mit 1000 Artikeln in 20 Gruppen: {min(zeiten):.2f} s (bester von 3, alle {', '.join(f'{z:.2f}' for z in zeiten)}),"
              f" Nachladen 25: {nachladen:.2f} s")
        assert min(zeiten) < 10, zeiten
    print("Abfragen und Leistung bestanden.")


# --- 3. Oberfläche ------------------------------------------------------------------------------------------------------

def test_statisch():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    ue = lies("app/static/js/uebung/material.js")
    teil = js[js.index("  async function ordner() {"):js.index("  /* --- Produktsuche mit allen Treffern")]
    # Gruppen statt Seiten; „weitere anzeigen“ je Gruppe; kein Link mehr auf die Fälligen der Person im Zweig.
    assert "seitenleiste(" not in teil and "pro_seite" not in teil and "Fällige Artikel" not in teil
    assert "gruppen: d.gruppen" in teil and '"gruppe-mehr": async (b) =>' in teil
    assert "api(`${API}/ordner/${id}/gruppe/${g.id}?${anfrage({ ab })}`)" in teil
    assert '"Artikel samt Unterordnern" : "Artikel in diesem Ordner"' in teil
    assert "const zeigeFilter = Boolean(zweigAlle || filter || person || kategorie);" in teil
    assert 'concat(!ausgesondertHier && (d.zahlen.ausgesondert || filter === "ausgesondert") ? ["ausgesondert"] : [])' in teil
    # Mehrfachauswahl über alle Gruppen: Ereignisse am Abschnitt, Häkchen je Gruppe, Quellen beim Verschieben.
    assert 'bereich.addEventListener("change"' in teil and ".mat-zweig-alle" in teil and "quelle: gewaehlteOrdner()" in teil
    assert "const quellen = [].concat(opts.quelle);" in js and "quellen.every((q) => wechselErlaubt(q, o.id))" in js
    # Tabelle: ein <tbody> je Gruppe, Überschrift mit Pfad als Link, „Weitere n anzeigen“ grau umrandet.
    assert '<tbody class="mat-zweig-gruppe" data-gruppe="${g.id}">' in js and 'g.pfad.join(" › ")' in js
    assert '<th scope="rowgroup"' in js and 'class="btn secondary small" data-act="gruppe-mehr"' in js
    assert "?pro_gruppe=1`" in js and "?pro_seite=1`" not in js
    # CSS: Überschrift als Karte, 44 px am Finger nur unter (pointer: coarse).
    block = css[css.index("/* Ordnerseite: der ganze Zweig mit Überschriften"):]
    assert "table.list.mat-karten tr.mat-zweig-kopf::before { content: none; }" in block
    finger = block[block.index("@media (pointer: coarse)"):]
    assert "tr.mat-zweig-kopf th a { display: inline-flex; align-items: center; min-height: 44px; }" in finger
    assert ":hover" not in block.replace("@media (hover: hover) and (pointer: fine) {\n  table.list.mat-tabelle tr:is(.mat-zweig-kopf, .mat-zweig-mehr):hover td", "")
    # Übung: Gruppen und Nachladen in der Übungsdatei.
    assert "gruppen, artikel: liste.map((a) => artikelKurz(z, a)), artikel_gesamt: liste.length, pro_gruppe: 50, zahlen," in ue
    assert '/^\\/api\\/material\\/ordner\\/(\\d+)\\/gruppe\\/(\\d+)$/' in ue
    print("Oberfläche (statisch) bestanden.")


GROESSEN = ((1280, 900, False), (360, 740, True))


def _browser_bestand(u):
    """Übung Gliederung › Platzhalter Lager › Platzhalter Regal (55 Artikel – eine Gruppe mit „weitere anzeigen“),
    Platzhalter Fahrzeug (2 Artikel), Platzhalter Leer (ohne Artikel); 1 Artikel direkt in der Gliederung, einer gesperrt
    (Gruppe „Gesperrt“). Rechte: Materialwart verwaltet die Gliederung (Umgebung)."""
    from test_material import katalog_grund as grund
    ids = grund(u.adm)
    gid = u.sql("SELECT id FROM mat_folder WHERE name = 'Übung Gliederung'")[0]["id"]
    lager = _ordner(u.adm, "Platzhalter Lager", gid)
    regal = _ordner(u.adm, "Platzhalter Regal", lager)
    fahrzeug = _ordner(u.adm, "Platzhalter Fahrzeug", gid, "fahrzeug")
    leer = _ordner(u.adm, "Platzhalter Leer", gid)
    with u.app.test_request_context():
        from flask import g
        from app import db
        from app.material.services import bestand
        g.user = db.query("SELECT * FROM users WHERE email = 'admin@example.org'", one=True)
        g.mat_akteur = "Test"
        for n in range(55):
            with db.transaction():
                bestand.artikel_anlegen({"product_id": ids["hms"], "folder_id": regal, "serial_no": f"B-RE-{n:02d}"})
    a_gl = neuer_artikel(u.adm, ids["hms"], gid, serial_no="B-GL")["id"]
    fz = [neuer_artikel(u.adm, ids["hms"], fahrzeug, serial_no=f"B-FZ-{n}")["id"] for n in range(2)]
    # Gesperrt per „Verlust melden“ (Prüfer, ohne Prüfung): Gruppe „Gesperrt“ mit ausgegrautem Häkchen.
    from einfuehrung_browser import PASSWORT, mail
    freigeben(u.adm, gid, u.ids["pruefer"], "lesen")
    freigeben(u.adm, gid, u.ids["pruefer"], "pruefen")
    gesperrt = neuer_artikel(u.adm, ids["hms"], fahrzeug, serial_no="B-SP")["id"]
    r = u._anmelden(mail("pruefer"), PASSWORT).post(f"{API}/artikel/{gesperrt}/sperren", json={"grund": "verlust", "text": "Platzhalter"})
    assert r.status_code == 200, r.get_json()
    return {"gid": gid, "lager": lager, "regal": regal, "fahrzeug": fahrzeug, "leer": leer, "a_gl": a_gl, "fz": fz,
            "gesperrt": gesperrt}


def _vorbereiten(s, pfad):
    s.oeffnen(pfad, warten=0.6)
    assert s.warte("!!document.querySelector('#mat-artikel-titel')"), "Ordnerseite lädt nicht"
    # Angebot der Einführung und Hinweise beiseite – sie liegen sonst über Zeilen.
    s.js("""(() => { const k = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Nicht jetzt');
      if (k) k.click(); document.querySelectorAll('dialog[open]').forEach((d) => d.close()); })()""")
    s.b.warten(0.3)


def _ablauf(u, d, breite, hoehe, touch, bilder):
    from test_material_formular_editor import flaeche, klick, tippflaechen
    s = u.seite("materialwart", breite, hoehe, touch)
    name = f"{breite}{'-touch' if touch else ''}"
    try:
        _vorbereiten(s, f"/materialablage/ordner/{d['gid']}")
        # Überschriften: Pfad relativ zur Gliederung, Baumreihenfolge, leere Ordner fehlen, Gesperrt dabei.
        koepfe = s.js("[...document.querySelectorAll('tr.mat-zweig-kopf th a')].map((a) => a.textContent.trim())")
        assert koepfe == ["Platzhalter Fahrzeug", "Platzhalter Lager › Platzhalter Regal", "Gesperrt"], koepfe
        assert s.js("document.querySelector('#mat-artikel-titel').textContent.trim()") == "Artikel samt Unterordnern"
        # Die erste Gruppe (direkt in der Gliederung) ohne Überschrift.
        assert s.js("!document.querySelector('tbody.mat-zweig-gruppe').querySelector('tr.mat-zweig-kopf')")
        assert s.js(f"document.querySelectorAll('tbody[data-gruppe=\"{d['regal']}\"] tr[data-id]').length") == 50
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        if touch:
            # Karten: Überschriftzeile mit Häkchen links, Link 44 px; „weitere anzeigen“ 44 px.
            assert s.js("getComputedStyle(document.querySelector('table.mat-artikel thead')).display") == "none"
            tippflaechen(s, "tr.mat-zweig-kopf th a")
            tippflaechen(s, "tr.mat-zweig-kopf .mat-wahl-feld")
            tippflaechen(s, '[data-act="gruppe-mehr"]')
        s.b.foto(os.path.join(bilder, f"ordner_{name}"))
        # „Weitere 5 anzeigen“: hängt die restlichen an, der Knopf verschwindet, der Fokus geht auf die erste neue Zeile.
        assert s.js("document.querySelector('[data-act=\"gruppe-mehr\"]').textContent.trim()") == "Weitere 5 anzeigen"
        klick(s, '[data-act="gruppe-mehr"]')
        assert s.warte(f"document.querySelectorAll('tbody[data-gruppe=\"{d['regal']}\"] tr[data-id]').length === 55")
        assert s.js("!document.querySelector('[data-act=\"gruppe-mehr\"]')")
        assert s.js("document.activeElement && document.activeElement.classList.contains('mat-inv')")
        # Mehrfachauswahl über Gruppen: Häkchen der Gruppe „Fahrzeug“ und ein Artikel des Regals → 3 ausgewählt.
        fz = f'tbody[data-gruppe="{d["fahrzeug"]}"] .mat-zweig-alle'
        if touch:
            klick(s, f'tbody[data-gruppe="{d["fahrzeug"]}"] tr.mat-zweig-kopf .mat-wahl-feld')
        else:
            klick(s, fz)
        erster = s.js(f"document.querySelector('tbody[data-gruppe=\"{d['regal']}\"] .mat-wahl-art').value")
        klick(s, f'tbody[data-gruppe="{d["regal"]}"] tr[data-id="{erster}"] .mat-wahl-feld')
        assert s.warte("document.querySelector('#mat-sammel-n').textContent.includes('3 Artikel')"), s.js("document.querySelector('#mat-sammel-n').textContent")
        assert s.js(f"document.querySelector('{fz}').checked")
        # Das gesperrte Häkchen der Gruppe „Gesperrt“ bleibt aus; „alle auswählen“ steht halb.
        assert s.js("document.querySelector('.mat-alle').indeterminate")
        # Verschieben: Ziel „Platzhalter Leer“.
        klick(s, '[data-act="sammel-verschieben"]')
        assert s.warte("!!document.querySelector('#dlg[open] input[name=ziel]')")
        klick(s, f'#dlg input[name=ziel][value="{d["leer"]}"]' if not touch else f'#dlg label:has(> input[name=ziel][value="{d["leer"]}"])')
        klick(s, "#ow-ok")
        assert s.warte(f"!!document.querySelector('tbody[data-gruppe=\"{d['leer']}\"]')"), "Ziel erscheint nicht als Gruppe"
        assert s.js(f"document.querySelectorAll('tbody[data-gruppe=\"{d['leer']}\"] tr[data-id]').length") == 3
        assert s.js(f"!document.querySelector('tbody[data-gruppe=\"{d['fahrzeug']}\"]')")
        s.b.foto(os.path.join(bilder, f"ordner_verschoben_{name}"))
        # Filter „gesperrt“ (am Telefon über die Schublade): nur die Gruppe „Gesperrt“; danach zurücksetzen.
        if touch:
            klick(s, '[data-act="filter-auf"]')
            assert s.warte("document.querySelector('#mat-side').classList.contains('open')"), "Schublade öffnet nicht"
            s.b.warten(0.5)
            tippflaechen(s, '#mat-side-filter [data-act="filter"][data-f="gesperrt"]')
            s.b.foto(os.path.join(bilder, f"ordner_filter_schublade_{name}"), ganz=False)
        klick(s, '#mat-side-filter [data-act="filter"][data-f="gesperrt"]')
        assert s.warte("document.querySelectorAll('tr.mat-zweig-kopf').length === 1")
        assert s.js("document.querySelector('tr.mat-zweig-kopf th a').textContent.trim()") == "Gesperrt"
        assert s.js("document.querySelector('.mat-gefiltert').textContent").startswith("Gefiltert: Status „gesperrt“")
        assert s.js("document.querySelector('#mat-side-filter [data-f=\"\"] .mat-side-anzahl').textContent") == "59"
        klick(s, '[data-act="filter-weg"]')
        assert s.warte("document.querySelectorAll('tr.mat-zweig-kopf').length === 3")
        # Leerzustand: ein Ordner ohne Artikel im Zweig.
        _vorbereiten(s, f"/materialablage/ordner/{d['lager']}")
        assert s.js("document.querySelectorAll('tr.mat-zweig-kopf').length") == 1      # nur das Regal
        if not touch:
            flaeche(s, "tr.mat-zweig-kopf th a")
        s.sammeln()
        assert not s.fehler, s.fehler
        return s
    finally:
        s.schliessen()


def test_browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    bilder = os.environ.get("ST_BILDER") or tempfile.mkdtemp(prefix="bestand-zweig-")
    with Umgebung() as u:
        d = _browser_bestand(u)
        for breite, hoehe, touch in GROESSEN:
            los = time.time()
            _ablauf(u, d, breite, hoehe, touch, bilder)
            # Für die nächste Größe zurück: die verschobenen Artikel wieder ins Fahrzeug bzw. Regal.
            for a in u.sql("SELECT id, serial_no FROM mat_item WHERE folder_id = ?", (d["leer"],)):
                ziel = d["fahrzeug"] if a["serial_no"].startswith("B-FZ") else d["regal"]
                r = u.adm.post(f"{API}/artikel/verschieben", json={"ids": [a["id"]], "folder_id": ziel})
                assert r.status_code == 200, r.get_json()
            print(f"Ordnerseite mit Zweig {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({time.time() - los:.1f} s)")
        # Leerzustand: ein leerer Ordner.
        s = u.seite("materialwart", 360, 740, True)
        try:
            _vorbereiten(s, f"/materialablage/ordner/{d['leer']}")
            assert s.js("document.querySelector('.leerzustand').textContent.trim()") == "Hier liegen keine Artikel."
            assert s.js("document.querySelector('#mat-artikel-titel').textContent.trim()") == "Artikel in diesem Ordner"
            s.sammeln()
            assert not s.fehler, s.fehler
        finally:
            s.schliessen()
    print(f"Browser bestanden (Fotos: {bilder}).")


if __name__ == "__main__":
    test_zweig_gruppen_und_filter()
    test_nachladen_und_sortierung()
    test_rechte()
    test_abfragen_und_leistung()
    test_statisch()
    test_browser()
    print(json.dumps({"ergebnis": "Alle Tests zum Zweig im Bestand bestanden."}, ensure_ascii=False))
