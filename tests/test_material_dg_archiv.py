"""Abgeschlossene Prüfdurchgänge nur bei Bedarf – Menü „Prüfdurchgänge“ (Wunsch vom 27.10.2026):
python tests/test_material_dg_archiv.py  oder  pytest tests/test_material_dg_archiv.py

Aufbau: Gliederung G mit Lager, Fahrzeug › Rucksack; beendete Durchgänge in drei Jahren (die Uhr des Moduls wird dafür
verstellt, wie in test_material_bericht), einer davon abgebrochen, dazu ein offener über G und ein beendeter in einer
fremden Gliederung. Geprüft: GET /durchgaenge?abgeschlossen=1 – Jahre mit Anzahl, neuestes Jahr ohne ?jahr=, Filter
Jahr/Ordner (Zweig)/Titel, Seiten, Eingaben (400/404); die alte Liste (?offen=1, ohne Parameter) unverändert; Rechte und
Gliederungstrennung je Rolle (Material-Verwaltung, Materialwart, Prüfer ohne Prüffreigabe, Leser nur eines Ordners,
ohne Stufe, nicht angemeldet); die Seite /materialablage/durchgaenge mit Seitentitel; leere Zustände; Menü und Seite
statisch. Alle Namen und Titel sind Platzhalter."""
import json
import os
import re
import sys
import tempfile
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (_heute, freigeben, gliederung, katalog_grund, neuer_artikel, neues_konto,  # noqa: E402
                           pruef_formulare, umgebung)
from test_material_bericht import uhr  # noqa: E402
from test_material_setprotokolle import ausnehmen, pruefen  # noqa: E402
from test_material_ueberblick import ohne_post, ordner_neu  # noqa: E402

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(rel):
    with open(os.path.join(WURZEL, rel), encoding="utf-8") as fh:
        return fh.read()


def _durchgang(c, fid, titel):
    r = c.post(f"{API}/durchgaenge", json={"folder_id": fid, "titel": titel})
    assert r.status_code == 201, r.get_json()
    return r.json["durchgang"]["id"]


def _beenden(c, rid, iids, abbrechen=False, pruefer=None):
    """Alle Artikel ausnehmen und abschließen – oder einen prüfen und abbrechen (dann bleibt er „abgebrochen“)."""
    if abbrechen:
        pruefen(pruefer, iids[0], rid)
        r = c.post(f"{API}/durchgaenge/{rid}/abbrechen", json={})
    else:
        for iid in iids:
            ausnehmen(c, rid, iid)
        r = c.post(f"{API}/durchgaenge/{rid}/abschliessen", json={})
    assert r.status_code == 200, r.get_json()
    assert r.json["durchgang"]["offen"] is False


def aufbau(tmp):
    app, k = umgebung(tmp)
    adm, w, p = k["adm"], k["wart"], k["pruefer"]
    ids = katalog_grund(adm)
    pruef_formulare(k["katalog"], ids)
    g, _ = gliederung(adm, "OG Archivstadt")
    fremd, _ = gliederung(adm, "OG Fremdort", standard=False)
    lager = ordner_neu(w, g, "Lager", "standort")
    fz = ordner_neu(w, g, "Fahrzeug", "fahrzeug")
    rucksack = ordner_neu(w, fz, "Rucksack", "set")
    fremd_lager = ordner_neu(adm, fremd, "Fremdlager", "standort")
    n = iter(range(1, 100))

    def art(c, fid):
        return neuer_artikel(c, ids["hms"], fid, serial_no=f"DG-{next(n):03d}")["id"]
    t = SimpleNamespace(app=app, k=k, adm=adm, w=w, p=p, g=g, fremd=fremd, lager=lager, fz=fz, rucksack=rucksack,
                        fremd_lager=fremd_lager)
    t.l1, t.f1, t.r1, t.x1 = art(w, lager), art(w, fz), art(w, rucksack), art(adm, fremd_lager)
    J = _heute().year
    t.J = J
    t.rid = {}
    with uhr(date(J - 2, 5, 10)):
        t.rid["lager_alt"] = rid = _durchgang(w, lager, "Platzhalter Lager alt")
        _beenden(w, rid, [t.l1])
    with uhr(date(J - 1, 3, 1)):
        t.rid["fahrzeug"] = rid = _durchgang(w, fz, "Platzhalter Fahrzeug")
        _beenden(w, rid, [t.f1, t.r1])
        t.rid["fremd"] = rid = _durchgang(adm, fremd_lager, "Platzhalter fremd")
        _beenden(adm, rid, [t.x1])
    with uhr(date(J - 1, 9, 20)):
        t.rid["rucksack"] = rid = _durchgang(w, rucksack, "Platzhalter Rucksack 100%")
        _beenden(w, rid, [t.r1])
    # Laufendes Jahr: zwei abgeschlossene am selben Tag (Reihenfolge nach Kennung), ein abgebrochener.
    t.rid["lager_neu"] = rid = _durchgang(w, lager, "Platzhalter Lager neu")
    _beenden(w, rid, [t.l1])
    t.rid["lager_nach"] = rid = _durchgang(w, lager, "Platzhalter Lager Nachprüfung")
    _beenden(w, rid, [t.l1])
    t.rid["abbruch"] = rid = _durchgang(w, fz, "Platzhalter abgebrochen")
    _beenden(w, rid, [t.f1], abbrechen=True, pruefer=p)
    t.rid["offen"] = _durchgang(w, g, "Platzhalter offen")
    return t


def archiv(c, **q):
    q.setdefault("abgeschlossen", "1")
    return c.get(f"{API}/durchgaenge", query_string=q)


def titel(r):
    return [x["titel"] for x in r.json["durchgaenge"]]


def test_api_jahre_und_filter():
    """Jahre mit Anzahl (neueste zuerst), ohne ?jahr= das neueste mit seinen Durchgängen (neueste Abschlüsse zuerst,
    gleiches Datum nach Kennung), Filter Jahr, Ordner (Zweig), Titel; Seiten; Eingaben; alte Liste unverändert."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        J, w = t.J, t.w
        r = archiv(w)
        assert r.status_code == 200, r.get_json()
        d = r.json
        assert d["jahre"] == [{"jahr": J, "anzahl": 3}, {"jahr": J - 1, "anzahl": 2}, {"jahr": J - 2, "anzahl": 1}], d["jahre"]
        assert (d["jahr"], d["gesamt"], d["seite"], d["pro_seite"]) == (J, 3, 1, 50)
        assert titel(r) == ["Platzhalter abgebrochen", "Platzhalter Lager Nachprüfung", "Platzhalter Lager neu"], titel(r)
        abbruch = r.json["durchgaenge"][0]
        assert abbruch["abgebrochen"] is True and abbruch["offen"] is False and abbruch["protokoll"]["url"]
        assert abbruch["zaehlung"]["erledigt"] == 1 and abbruch["ordner"].endswith("Fahrzeug")
        assert all(x["protokoll"] and not x["offen"] for x in r.json["durchgaenge"])
        # Ein Jahr, ein leeres Jahr, Unsinn.
        r = archiv(w, jahr=str(J - 1))
        assert (r.json["jahr"], r.json["gesamt"]) == (J - 1, 2)
        assert titel(r) == ["Platzhalter Rucksack 100%", "Platzhalter Fahrzeug"], titel(r)
        assert [x["eroeffnet_am"][:4] for x in r.json["durchgaenge"]] == [str(J - 1)] * 2
        r = archiv(w, jahr="2000")
        assert r.status_code == 200 and (r.json["gesamt"], r.json["durchgaenge"]) == (0, [])
        assert len(r.json["jahre"]) == 3
        for falsch in ("1800", "abc", "20 24", "２０２５", "-2025", "99999"):
            r = archiv(w, jahr=falsch)
            assert r.status_code == 400 and "1990 und 2100" in r.json["error"], (falsch, r.get_json())
        # Ordner: der Zweig – Fahrzeug enthält den Rucksack, das Lager nicht.
        r = archiv(w, ordner=str(t.fz))
        assert r.json["jahre"] == [{"jahr": J, "anzahl": 1}, {"jahr": J - 1, "anzahl": 2}], r.json["jahre"]
        assert titel(r) == ["Platzhalter abgebrochen"]
        assert titel(archiv(w, ordner=t.fz, jahr=J - 1)) == ["Platzhalter Rucksack 100%", "Platzhalter Fahrzeug"]
        r = archiv(w, ordner=t.rucksack)
        assert r.json["jahre"] == [{"jahr": J - 1, "anzahl": 1}] and r.json["jahr"] == J - 1
        assert titel(r) == ["Platzhalter Rucksack 100%"]
        r = archiv(w, ordner=t.g)
        assert sum(j["anzahl"] for j in r.json["jahre"]) == 6
        # Titel: jedes Wort, ohne Rücksicht auf Groß/klein (ASCII); % und _ sind keine Platzhalter.
        assert titel(archiv(w, q="lager", jahr=J)) == ["Platzhalter Lager Nachprüfung", "Platzhalter Lager neu"]
        r = archiv(w, q="LAGER NEU")
        assert r.json["jahre"] == [{"jahr": J, "anzahl": 1}] and titel(r) == ["Platzhalter Lager neu"]
        assert archiv(w, q="lager").json["jahre"] == [{"jahr": J, "anzahl": 2}, {"jahr": J - 2, "anzahl": 1}]
        assert titel(archiv(w, q="100%")) == ["Platzhalter Rucksack 100%"]
        r = archiv(w, q="%")
        assert r.json["jahre"] == [{"jahr": J - 1, "anzahl": 1}], r.json["jahre"]
        r = archiv(w, q="Platz_alter")
        assert r.json["jahre"] == [] and r.json["jahr"] is None and r.json["durchgaenge"] == []
        assert titel(archiv(w, q="Rucksack", ordner=t.lager)) == []
        assert archiv(w, q="x" * 201).status_code == 400
        # Seiten: höchstens 100 je Abruf, sonst wie bestellt.
        r = archiv(w, pro_seite=2)
        assert titel(r) == ["Platzhalter abgebrochen", "Platzhalter Lager Nachprüfung"] and r.json["gesamt"] == 3
        r = archiv(w, pro_seite=2, seite=2)
        assert titel(r) == ["Platzhalter Lager neu"] and r.json["seite"] == 2
        assert archiv(w, pro_seite=2, seite=3).json["durchgaenge"] == []
        assert archiv(w, pro_seite=500).json["pro_seite"] == 100
        assert archiv(w, seite="x").status_code == 400
        # Die bisherige Liste bleibt: ?offen=1 nur der offene, ohne Parameter alle (offene zuerst).
        r = w.get(f"{API}/durchgaenge?offen=1")
        assert titel(r) == ["Platzhalter offen"] and "jahre" not in r.json
        r = w.get(f"{API}/durchgaenge")
        assert titel(r)[0] == "Platzhalter offen" and len(r.json["durchgaenge"]) == 7
        assert archiv(w, abgeschlossen="0").json == r.json
    print("Schnittstelle (Jahre, Filter, Seiten) bestanden.")


def test_rechte_und_gliederung():
    """Der Server liefert nur Sichtbares: Gliederungstrennung, Leser eines Unterordners, Ordnerfilter nur auf sichtbare
    Ordner (fremd und unbekannt gleich: 404), ohne Stufe 403, ohne Anmeldung 401."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        J = t.J
        alle = lambda c: sorted(x["titel"] for j in archiv(c).json["jahre"]  # noqa: E731
                                for x in archiv(c, jahr=j["jahr"]).json["durchgaenge"])
        eigene = ["Platzhalter Fahrzeug", "Platzhalter Lager Nachprüfung", "Platzhalter Lager alt", "Platzhalter Lager neu",
                  "Platzhalter Rucksack 100%", "Platzhalter abgebrochen"]
        # Materialwart, Prüfer und Führungskraft der Gliederung: nur G; die Material-Verwaltung alles.
        for name in ("wart", "pruefer", "fuehrung"):
            assert alle(t.k[name]) == eigene, (name, alle(t.k[name]))
        assert alle(t.k["katalog"]) == sorted(eigene + ["Platzhalter fremd"])
        assert archiv(t.k["katalog"], jahr=J - 1).json["gesamt"] == 3
        # Fremder Ordner und unbekannter Ordner: dieselbe Antwort.
        for oid in (t.fremd_lager, t.fremd, 987654):
            r = archiv(t.w, ordner=oid)
            assert r.status_code == 404 and r.json["error"] == "Ordner nicht gefunden.", (oid, r.get_json())
        assert archiv(t.k["katalog"], ordner=t.fremd_lager).json["jahre"] == [{"jahr": J - 1, "anzahl": 1}]
        assert archiv(t.w, ordner="x").status_code == 400
        assert archiv(t.w, ordner="0").status_code == 400
        # Ein Leser nur des Rucksacks sieht nur dessen Durchgang; Fahrzeug und G sind für ihn nur Pfad (404).
        leser, lid = neues_konto(t.app, "leser@example.org")
        freigeben(t.adm, t.rucksack, lid, "lesen")
        assert alle(leser) == ["Platzhalter Rucksack 100%"]
        assert archiv(leser, ordner=t.rucksack).json["jahre"] == [{"jahr": J - 1, "anzahl": 1}]
        for oid in (t.fz, t.g):
            assert archiv(leser, ordner=oid).status_code == 404
        # Ohne Freigabe: leer, aber kein Fehler (leerer Zustand der Seite).
        ohne, _ = neues_konto(t.app, "ohne@example.org")
        r = archiv(ohne)
        assert r.status_code == 200 and r.json == {"jahre": [], "jahr": None, "gesamt": 0, "seite": 1, "pro_seite": 50,
                                                   "durchgaenge": []}, r.json
        assert archiv(t.k["nutzer"]).status_code == 403
        anonym = t.app.test_client()
        assert archiv(anonym).status_code == 401
    print("Rechte und Gliederungstrennung bestanden.")


def _darf(html):
    m = re.search(r'data-darf="([^"]*)"', html)
    return json.loads(m.group(1).replace("&#34;", '"').replace("&quot;", '"'))


def test_seite_und_menue_je_rolle():
    """Die Seite /materialablage/durchgaenge: Ansicht, Seitentitel, für jede Rolle mit Zugang; ohne Stufe 403, ohne
    Anmeldung zur Anmeldung. Das Menü „Prüfdurchgänge“ zeigt „Prüfdurchgang anlegen“ nach DARF.verwalten/pruefen –
    die Seite liefert dafür je Rolle die passenden Flags (Material-Verwaltung, Materialwart, Prüfer mit und ohne
    Prüffreigabe, Leser)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        g, _ = gliederung(k["adm"], "OG Archivstadt")
        p2, p2_id = neues_konto(app, "pruefer2@example.org", mat_pruefer=True, urkundennummer="1012-0815")
        # p2 hat das Häkchen „Prüfer“ und liest G, aber ohne Prüffreigabe (nach der Gliederung angelegt): kein Anlegen.
        freigeben(k["adm"], g, p2_id, "lesen")
        erwartet = {"katalog": True, "wart": True, "pruefer": True, "fuehrung": False}
        for name, anlegen in list(erwartet.items()) + [("p2", False)]:
            c = p2 if name == "p2" else k[name]
            r = c.get("/materialablage/durchgaenge")
            html = r.get_data(as_text=True)
            assert r.status_code == 200, name
            assert 'data-ansicht="durchgaenge"' in html
            assert "<title>Abgeschlossene Prüfdurchgänge – Materialablage – strömis.de</title>" in html, name
            d = _darf(html)
            assert bool(d["verwalten"] or d["pruefen"]) is anlegen, (name, d)
            assert d["lesen"] is True, (name, d)
            r = c.get("/materialablage/pruefungen")
            assert r.status_code == 200 and _darf(r.get_data(as_text=True)) == d
        r = k["nutzer"].get("/materialablage/durchgaenge")
        assert r.status_code == 403
        r = app.test_client().get("/materialablage/durchgaenge?ordner=3")
        assert r.status_code == 302 and "/login" in r.headers["Location"] and "durchgaenge" in r.headers["Location"]
    print("Seite und Menü je Rolle bestanden.")


def test_oberflaeche_statisch():
    """Prüfungen: nur laufende Durchgänge, Menü „Prüfdurchgänge“ statt „Prüfdurchgang anlegen“; die neue Ansicht mit
    Jahren, Filtern, leeren Zuständen, Verlauf und Karten; Brotkrume des beendeten Durchgangs; CSS am Finger."""
    js, css = lies("app/material/static/material.js"), lies("app/material/static/material.css")
    # Prüfungen: keine zugeklappte Liste mehr, laufende mit Leertext; das Menü mit zwei bzw. einem Eintrag.
    assert "mat-runden-alt" not in js and "pr-runden-alt" not in js and "mat-runden-alt" not in css
    assert 'rundenKasten($("#pr-runden"), true)' in js and 'rundenKasten($("#mat-runden"));' in js
    assert 'leer("Gerade läuft kein Prüfdurchgang.")' in js and "durchgaenge?offen=1" in js
    # Seit dem gemeinsamen Menübaustein (UI/UX vor dem Merge, A3): S.menue – ohne Recht zum Anlegen ein Knopf.
    menue = js[js.index("const rundenMenue = () =>"):js.index("] });", js.index("const rundenMenue = () =>"))]
    assert 'S.menue({ text: "Prüfdurchgänge", klein: false, art: "mat-menue", links: true, eintraege: [' in menue
    assert '(DARF.verwalten || DARF.pruefen) && { text: "Prüfdurchgang anlegen"' in menue and 'attrs: \'data-act="runde"\'' in menue
    assert '{ text: "Abgeschlossene Prüfdurchgänge"' in menue and 'href: `/materialablage/durchgaenge' in menue
    assert "${rundenMenue()}</div></div>" in js
    pruef = js[js.index("async function pruefungen() {"):js.index("async function zeigenIn(")]
    assert "k-anlegen" not in pruef and 'class="btn"' not in pruef
    # Neue Ansicht.
    assert "durchgaenge: durchgaengeArchiv," in js and 'durchgaenge: "pruefungen"' in js
    assert '"durchgang", "durchgaenge", "katalog"' in js
    teil = js[js.index("async function durchgaengeArchiv() {"):js.index("/* --- Bestand ---")]
    for stelle in ('seitenTitel("Abgeschlossene Prüfdurchgänge");', "abgeschlossen: \"1\"", 'p.set("jahr", String(jahr))',
                   'p.set("ordner", String(ordner))', 'p.set("q", q)', "history.state.durchgaenge", "history.replaceState(",
                   'window.addEventListener("pagehide", merken);', "ordnerOptionen(baum, () => true, ordner, false)",
                   '<option value="">alle Ordner</option>', 'class="list mat-tabelle mat-karten mat-dg-tabelle"',
                   'class="mat-k-titel"', 'class="mat-k-halb"', 'class="tabelle-aktionen">${sammelPdf(r)}',
                   '<span class="badge grey">abgebrochen</span>', 'data-act="dg-mehr"', "Weitere anzeigen (${rest})",
                   '"Noch keine abgeschlossenen Prüfdurchgänge."', '"In diesem Ordner (mit Unterordnern) keine abgeschlossenen Prüfdurchgänge."',
                   '"Keine abgeschlossenen Prüfdurchgänge mit diesen Wörtern im Titel."',
                   'leer("In diesem Jahr keine abgeschlossenen Prüfdurchgänge (mehr).")', "esc(r.titel)", "esc(r.ordner)",
                   "esc(e.message)", "esc(q)", '<summary><h2>${j.jahr} <span class="mat-dg-anzahl">',
                   'inhalt.addEventListener("toggle"', "DG_PRO_SEITE * 20"):
        assert stelle in teil, stelle
    # Brotkrume eines beendeten Durchgangs.
    assert """d.offen ? "" : '<a href="/materialablage/durchgaenge">Abgeschlossene Prüfdurchgänge</a>'""" in js
    # CSS: Filter, Jahresköpfe, am Telefon untereinander, am Finger 44 px.
    for regel in (".mat-dg-filter { display: flex;", ".mat-dg-klapp > summary h2 { display: inline;",
                  "@container mat-seite (max-width: 600px) {\n  .mat-dg-filter { margin-top: 0; }",
                  "@media (pointer: coarse) {\n  .mat-dg-klapp > summary { min-height: 44px;"):
        assert regel in css, regel
    assert '"durchgaenge": "Abgeschlossene Prüfdurchgänge"' in lies("app/material/templates/material/seite.html")
    print("Oberfläche (statisch) bestanden.")


def test_info_symbol_und_namen():
    """Nachtrag 1: „i“ hinter „Prüfsumme“ statt des Erklärsatzes (Knopf mit aria-label/-expanded/-describedby, Info mit
    role=tooltip und Link zur Prüfseite, 44 px am Finger). Nachtrag 2: Namen hinter „von“ und in Personenfeldern als
    Einheit (person, .mat-name)."""
    js, css = lies("app/material/static/material.js"), lies("app/material/static/material.css")
    # Seit 27.10.2026 app-weit: S.info in common.js, Aussehen in app.css (.info) – material.js nimmt sie als infoKnopf.
    common, app_css = lies("app/static/js/common.js"), lies("app/static/css/app.css")
    assert "const infoKnopf = S.info;" in js and "function infoKnopf" not in js and "mat-info" not in js + css
    info = common[common.index("function info(thema, html) {"):common.index("/* Verhalten der Info-Symbole")]
    for stelle in ('class="info-knopf" aria-label="Info zu ${esc(thema)}" aria-expanded="false"',
                   'aria-controls="${id}" aria-describedby="${id}"', '<svg viewBox="0 0 20 20"', 'aria-hidden="true" focusable="false"',
                   '<span class="info-text" role="tooltip" id="${id}" hidden>${html}</span>'):
        assert stelle in info, stelle
    assert ("const PRUEFSUMME_INFO = 'Die Prüfsumme steht im Fuß jeder Seite des PDFs. Ob eine Datei unverändert ist, "
            "zeigt die <a href=\"/materialablage/pruefen\">Prüfseite</a>.';") in js
    assert '<dt>Prüfsumme${infoKnopf("Prüfsumme", PRUEFSUMME_INFO)}</dt>' in js
    assert '<p class="help">Die Prüfsumme steht im Fuß jeder Seite des PDFs.' not in js
    assert "auf der Prüfseite prüfen</a>" not in js
    assert '· Prüfsumme${infoKnopf("Prüfsumme", (d.set_protokolle || []).length' in js
    verhalten = common[common.index("function infoZeigen(w, an, fest) {"):common.index("/* Seitentitel im Reiter")]
    for stelle in ('k.setAttribute("aria-expanded", String(an));', "t.hidden = !an;", 'e.pointerType !== "mouse"',
                   '"focusin"', '"focusout"', 'e.key !== "Escape"', "k.focus();"):
        assert stelle in verhalten, stelle
    for regel in (".info-text { position: absolute;", ".info-text[hidden] { display: none; }",
                  "@media (pointer: coarse) {\n  .info-knopf { width: 44px; height: 44px;"):
        assert regel in app_css, regel
    assert ".mat-name { display: inline-block; max-width: 100%; overflow-wrap: anywhere; }" in css
    assert 'const person = (n) => `<span class="mat-name">${esc(n)}</span>`;' in js
    for stelle in ('${p.anmeldung ? ` von ${person(p.anmeldung)}` : ""}', '<dd>${person(pr.pruefer || "–")}',
                   'von ${person(d.eroeffnet_von || "–")}', 'von ${person(d.geschlossen_von || "–")}',
                   '<span class="muted">von ${person(j.user_name || "–")}</span>', 'Gemeldet von ${person(m.created_by_name || "–")}',
                   'const wer = (name) => (name ? ` von ${person(name)}` : "");',
                   "In Prüfung bei <strong>${person(a.entwurf.pruefer)}</strong>"):
        assert stelle in js, stelle
    assert js.count("person(") >= 30
    # Nie in einem Attribut (data-wer, alt, title) – dort bleibt esc().
    assert not re.search(r'="[^"<>]*\$\{person\(', js)
    print("Info-Symbol und Namen als Einheit bestanden.")


def test_knopftexte_ohne_auslassung():
    """Nachtrag 4: kein nachgestelltes „…“ in Knopf- und Menütexten aller Module (reine „…“-Knöpfe, Platzhalter,
    Ladeanzeigen und gekürzte Werte ausgenommen). Nachtrag 3: Katalog-Export ohne „von dev in die Produktion“. Nachtrag 5:
    „Änderung beantragen“ und „Bestandteile bearbeiten“ neben der Überschrift."""
    dateien = []
    for wurzel in ("app/static/js", "app/material/static", "app/templates", "app/material/templates"):
        for ordner, _, namen in os.walk(os.path.join(WURZEL, wurzel)):
            dateien += [os.path.join(ordner, n) for n in namen if n.endswith((".js", ".html")) and "vendor" not in ordner]
    funde = []
    muster = re.compile(r"[^\s>…⋯] ?(…|\.\.\.)\s*(</(button|strong|summary|a)>|<input)")
    for d in dateien:
        with open(d, encoding="utf-8") as fh:
            for nr, zeile in enumerate(fh, 1):
                for m in muster.finditer(zeile):
                    if not re.search(r"(Wird|wird|Lade|Hochladen|Prüfen, ob)[^<>]*$", zeile[:m.start() + 1]):
                        funde.append(f"{os.path.relpath(d, WURZEL)}:{nr}: {zeile.strip()[:120]}")
    assert not funde, "\n".join(funde)
    js = lies("app/material/static/material.js")
    for alt in ("Mangel melden …", "Zuordnen …", "Änderung beantragen …", "Verschieben nach …</button>", "Zuordnen an …</button>",
                "Prüfdurchgang anlegen …", "Löschen …</strong>", "Übernehmen …</button>"):
        assert alt not in js, alt
    assert '<label class="btn secondary mat-bildwahl-knopf">${esc(wort)} wählen<input' in js
    assert '{ text: "Reset-Mail senden", kurz: "Reset-Mail", attrs: \'data-act="reset"\' }' in lies("app/static/js/admin.js")   # S.menue (A3)
    assert ">Seiten aus ZIP importieren</button>" in lies("app/static/js/wiki.js")
    assert "von dev in die Produktion" not in js and "Zum Sichern oder für eine andere Installation" in js
    assert ("<div class=\"mat-kastenkopf\"><h2>Bestandteile${infoKnopf(\"Bestandteile\", BESTANDTEILE_INFO)}</h2>${k ? '<button class=\"btn secondary small\" "
            "data-act=\"stueckliste\">") in js
    assert ".mat-kastenkopf:has(> .btn) { border-bottom: 1px solid var(--linie);" in lies("app/material/static/material.css")
    print("Knopftexte ohne „…“ bestanden.")


if __name__ == "__main__":
    test_api_jahre_und_filter()
    test_rechte_und_gliederung()
    test_seite_und_menue_je_rolle()
    test_oberflaeche_statisch()
    test_info_symbol_und_namen()
    test_knopftexte_ohne_auslassung()
