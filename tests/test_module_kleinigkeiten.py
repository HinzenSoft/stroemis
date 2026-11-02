"""Kleinigkeiten aus dem Artikel-Nachzug (02.11.2026, Freigabe des Nutzers „umsetzen“, Liste
planung/wiki-module/kleinigkeiten_nach_artikeln.md, Punkte 1–10):  python tests/test_module_kleinigkeiten.py  oder pytest …

1 Sprung zum Anker bei nachladenden Bildern und Markierung der Gliederung (markdown.js, mit node nachgestellt),
2 Herzschlag im Editor: „keine Berechtigung mehr“ statt „… bearbeitet“ (Server: darf_schreiben), 3 Vorlagen auch über
„+“ und „Erste Seite anlegen“, 4 Ersteller und Bearbeiter nur mit Stufe in der Strömipedia, 5 README, 6 Hilfetext im
Ausbilder-Dialog, 7 Leistungsdialog bei eingefrorenen Bewertungen, 8 „Bild bearbeiten“ ohne Rundungsverlust,
9 Marke „verloren“ in Meine PSA, 10 Rückruf-Dialog. Nur erfundene Namen, Platzhalterinhalte, keine Mail geht hinaus
(kein Mailserver eingestellt)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rechte_redakteur import H, REDAKTEUR, MITGLIED, anmelden, konto, make_app, stufe_setzen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json(silent=True))
    return r.get_json()


def node(skript, *argumente):
    """Ein Stück Browser-Skript unter node ausführen (JSON zurück) – ohne node (anderer Rechner) None."""
    n = shutil.which("node")
    if not n:
        return None
    aus = subprocess.run([n, "-e", skript, *argumente], capture_output=True, text=True, check=True, timeout=60).stdout
    return json.loads(aus)


# --- 1 Sprung zum Anker ---------------------------------------------------------------------------------------------

ANKER_SKRIPT = r"""
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const src = js.slice(js.indexOf("  function ankerHalten("), js.indexOf("  function tocHtml("));
function lauf(fall) {
  const fenster = {};
  const window = { addEventListener(t, f) { (fenster[t] = fenster[t] || []).push(f); },
                   removeEventListener(t, f) { fenster[t] = (fenster[t] || []).filter((x) => x !== f); } };
  const location = { hash: "#ziel" };
  let uhr = null, gestoppt = false;
  const setTimeout = (f, ms) => { uhr = { f, ms }; return 1; };
  const clearTimeout = () => { gestoppt = true; };
  const bild = (complete, davor) => { const l = {}; return { complete,
    compareDocumentPosition: () => (davor ? 4 : 2),
    addEventListener(t, f) { (l[t] = l[t] || []).push(f); },
    removeEventListener(t, f) { l[t] = (l[t] || []).filter((x) => x !== f); },
    feuer(t) { (l[t] || []).slice().forEach((f) => f()); } }; };
  const bilder = [bild(false, true), bild(false, true), bild(true, true), bild(false, false)];
  const root = { querySelectorAll: () => bilder };
  let spruenge = 0;
  const ziel = { isConnected: true, scrollIntoView(o) { if (o.block === "start") spruenge++; } };
  const ankerHalten = new Function("window", "location", "Node", "entziffern", "setTimeout", "clearTimeout",
    src + "; return ankerHalten;")(window, location, { DOCUMENT_POSITION_FOLLOWING: 4 }, (s) => decodeURIComponent(s),
    setTimeout, clearTimeout);
  ankerHalten(root, ziel, "ziel");
  const horcht = () => ["wheel", "touchstart", "pointerdown", "keydown"].every((t) => (fenster[t] || []).length === 1);
  const vorher = horcht();
  if (fall === "geladen") { bilder[3].feuer("load"); bilder[0].feuer("load"); bilder[1].feuer("error"); bilder[0].feuer("load"); }
  if (fall === "gerollt") { bilder[0].feuer("load"); fenster.wheel[0](); bilder[1].feuer("load"); }
  if (fall === "anderer_anker") { location.hash = "#woanders"; bilder[0].feuer("load"); bilder[1].feuer("load"); }
  if (fall === "frist") { uhr.f(); bilder[0].feuer("load"); }
  const leer = ["wheel", "touchstart", "pointerdown", "keydown"].every((t) => !(fenster[t] || []).length);
  return { spruenge, vorher, leer, frist: uhr && uhr.ms, gestoppt };
}
console.log(JSON.stringify(["geladen", "gerollt", "anderer_anker", "frist"].map(lauf)));
"""


def test_1_anker_haelt_bis_die_bilder_geladen_sind():
    js = lesen("app/static/js/markdown.js")
    teil = js[js.index("  function scrollToHash(root) {"):js.index("  function tocHtml(items) {")]
    assert 't.scrollIntoView({ block: "start" });\n    ankerHalten(root, t, id);\n    return true;' in teil
    # Nur Bilder ÜBER dem Ziel, die noch laden; eigenes Rollen, Tippen, Tasten beenden das Nachführen.
    assert '.filter((i) => !i.complete && (i.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING));' in teil
    assert 'const SELBST = ["wheel", "touchstart", "pointerdown", "keydown"];' in teil
    erg = node(ANKER_SKRIPT, os.path.join(WURZEL, "app/static/js/markdown.js"))
    if erg is not None:
        geladen, gerollt, anderer, frist = erg
        # Zwei Bilder darüber laden (eins mit Fehler): zweimal neu ausgerichtet, das Bild darunter zählt nicht,
        # danach horcht nichts mehr (auch ein später doppeltes load bewegt nichts).
        assert geladen == {"spruenge": 2, "vorher": True, "leer": True, "frist": 10000, "gestoppt": True}, geladen
        # Selbst gerollt: nach dem Rad kein Sprung mehr.
        assert gerollt["spruenge"] == 1 and gerollt["leer"], gerollt
        # Anderer Anker in der Adresse: kein Sprung.
        assert anderer["spruenge"] == 0 and anderer["leer"], anderer
        # Nach 10 s ist Schluss.
        assert frist["spruenge"] == 0 and frist["leer"], frist


def test_1_gliederung_markiert_den_angesprungenen_abschnitt():
    js = lesen("app/static/js/markdown.js")
    spy = js[js.index("  function tocScrollspy(root, tocEl) {"):js.index("  function scrollToHash(root) {")]
    assert "const grenze = Math.max(120, (parseFloat(getComputedStyle(sichtbar[0]).scrollMarginTop) || 0) + 8);" in spy
    assert "if (h.getBoundingClientRect().top <= grenze) active = h; else break;" in spy
    assert "<= 120)" not in spy
    # Die Grenze liegt über dem Sprungabstand der Überschriften (Kopfleiste 52 + 72 = 124 px).
    css = lesen("app/static/css/app.css")
    assert ".wiki-editor .toastui-editor-contents :is(h1, h2, h3, h4, h5, h6) { scroll-margin-top: calc(var(--topbar) + 72px); }" in css
    assert "  --topbar: 52px;" in css


# --- 2 Herzschlag im Editor -----------------------------------------------------------------------------------------

def test_2_herzschlag_unterscheidet_recht_und_schreibplatz():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        rita, _ = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"wiki": REDAKTEUR})
        ralf, ralf_id = konto(app, adm, "ralf@example.org", "Ralf Redakteur", {"wiki": REDAKTEUR})
        s = ok(rita.post("/api/wiki/pages", json={"title": "Platzhalterseite", "content": "# Platzhalterseite\n\nText"}), 201)["page"]

        def puls(c, reiter, modus="schreiben"):
            return c.post("/api/wiki/praesenz", json={"reiter": reiter, "page_id": s["id"], "modus": modus}, headers=H)

        # Ohne Freigabe: lesen, und zwar weil das Recht fehlt.
        d = ok(puls(ralf, "reiter-ralf-1"))
        assert (d["modus"], d["darf_schreiben"], d["schreiber"]) == ("lesen", False, None), d
        ok(rita.put(f"/api/wiki/pages/{s['id']}/editors", json={"user_ids": [ralf_id]}))
        d = ok(puls(ralf, "reiter-ralf-1"))
        assert (d["modus"], d["darf_schreiben"]) == ("schreiben", True), d
        # Jemand anderes hat den Schreibplatz: lesen, das Recht ist aber da – dann nennt der Editor den Schreiber.
        d = ok(puls(rita, "reiter-rita-1"))
        assert (d["modus"], d["darf_schreiben"], d["schreiber"]["name"]) == ("lesen", True, "Ralf Redakteur"), d
        # Freigabe entzogen, während Ralf schreibt: lesen ohne Recht und ohne fremden Schreiber.
        ok(puls(rita, "reiter-rita-1", "lesen"))
        ok(rita.put(f"/api/wiki/pages/{s['id']}/editors", json={"user_ids": []}))
        d = ok(puls(ralf, "reiter-ralf-1"))
        assert (d["modus"], d["darf_schreiben"], d["schreiber"]) == ("lesen", False, None), d
        # Stufe ganz weg: der Herzschlag antwortet 403 – auch das führt im Editor zu „keine Berechtigung mehr“.
        stufe_setzen(adm, ralf_id, wiki=0)
        assert puls(ralf, "reiter-ralf-1").status_code == 403
    js = lesen("app/static/js/wiki.js")
    puls_js = js[js.index("  async function praesenzPuls(extra = {}) {"):js.index("  /* Den Schreibplatz verliert nur")]
    assert "if (e && e.status === 403) abgewiesen = e;" in puls_js
    assert ("if (abgewiesen && wunsch === \"schreiben\" && state.schreibrecht && state.current === p) {\n"
            "      state.schreibrecht = false;\n      bearbeitungVerweigert(abgewiesen.message);") in puls_js
    assert ('if (d.darf_schreiben === false) bearbeitungVerweigert("Du darfst diese Seite nicht mehr bearbeiten.");\n'
            "      else schreibrechtVerloren(d);") in puls_js
    weg = js[js.index("  function bearbeitungVerweigert(meldung) {"):js.index("  async function schreibrechtHolen(p) {")]
    # Derselbe Weg wie beim 403 des Speicherns: nichts mehr speichern, beim Verlassen fragen, Text bleibt.
    assert "state.editorGesperrt = true;\n    state.editorVerweigert = true;" in weg
    assert "Dein Text steht noch im Editor – kopiere ihn, bevor du die Seite verlässt." in weg
    assert '"Nicht gespeichert – keine Berechtigung mehr"' in weg and "bearbeitet" not in weg
    assert 'stand("Nicht gespeichert – keine Berechtigung mehr", true);' in js       # der Weg beim Speichern bleibt


# --- 3 Vorlagen über „+“ und „Erste Seite anlegen“ --------------------------------------------------------------

def test_3_alle_wege_zur_neuen_seite_bieten_vorlagen():
    js = lesen("app/static/js/wiki.js")
    plus = js[js.index('treeEl.querySelectorAll(".row-add")'):js.index('treeEl.querySelectorAll(".row-menu")')]
    assert 'side.classList.remove("open");\n      neueSeite(+b.closest("li").dataset.id);' in plus and "openEditor" not in plus
    assert '$("#h-new").onclick = () => neueSeite(null);' in js
    # openEditor mit parent_id ruft nur noch neueSeite selbst auf – ohne Vorlagen bzw. nach „Weiter“.
    teil = js[js.index("  async function neueSeite(parentId) {"):js.index("  /* Papierkorb: wiederherstellen")]
    assert js.count("openEditor({ parent_id") == teil.count("openEditor({ parent_id") == 2


# --- 4 Ersteller und Bearbeiter nur mit Stufe ---------------------------------------------------------------------

def test_4_ersteller_und_bearbeiter_nur_mit_stufe():
    import app.api_wiki as aw
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        rita, rita_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"wiki": REDAKTEUR})
        _, ralf_id = konto(app, adm, "ralf@example.org", "Ralf Redakteur", {"wiki": REDAKTEUR})
        _, mia_id = konto(app, adm, "mia@example.org", "Mia Mitglied", {"wiki": MITGLIED})
        _, leo_id = konto(app, adm, "leo@example.org", "Leo ohne Stufe", {"wiki": 0})
        _, lea_id = konto(app, adm, "lea@example.org", "Lea ohne Stufe", {"wiki": 0})
        s = ok(rita.post("/api/wiki/pages", json={"title": "Platzhalterseite", "content": "Text"}), 201)["page"]
        # Die Auswahl der Dialoge zeigt nur Konten mit Stufe – der Server nimmt jetzt auch nur diese an.
        auswahl = {u["id"] for u in ok(adm.get("/api/wiki/users"))["users"]}
        assert {rita_id, ralf_id, mia_id} <= auswahl and not {leo_id, lea_id} & auswahl
        r = adm.put(f"/api/wiki/pages/{s['id']}/creator", json={"user_id": leo_id})
        assert r.status_code == 400 and r.json["error"] == aw.OHNE_STUFE_ERSTELLER, r.get_json()
        assert "Leo" not in r.json["error"]
        assert ok(adm.get(f"/api/wiki/pages/{s['slug']}"))["page"]["created_by"] == rita_id
        assert ok(adm.put(f"/api/wiki/pages/{s['id']}/creator", json={"user_id": mia_id}))["page"]["created_by"] == mia_id
        assert ok(adm.put(f"/api/wiki/pages/{s['id']}/creator", json={"user_id": rita_id}))["page"]["created_by"] == rita_id
        # Bearbeiter: ein neues Konto ohne Stufe lehnt der Server ab, statt es still zu speichern – ohne Namen.
        r = rita.put(f"/api/wiki/pages/{s['id']}/editors", json={"user_ids": [ralf_id, leo_id]})
        assert r.status_code == 400 and r.json["error"].startswith("Ein gewähltes Konto hat keine Stufe in der Strömipedia"), r.get_json()
        assert "Leo" not in r.json["error"]
        r = rita.put(f"/api/wiki/pages/{s['id']}/editors", json={"user_ids": [leo_id, lea_id]})
        assert r.status_code == 400 and r.json["error"].startswith("2 gewählte Konten haben keine Stufe"), r.get_json()
        assert ok(adm.get(f"/api/wiki/pages/{s['slug']}"))["page"]["editors"] == []      # nichts gespeichert
        assert [e["id"] for e in ok(rita.put(f"/api/wiki/pages/{s['id']}/editors",
                                             json={"user_ids": [mia_id]}))["editors"]] == [mia_id]
        # Wer schon freigegeben ist und die Stufe verliert, bleibt stehen (der Dialog schickt ihn mit, bis man ihn abwählt).
        stufe_setzen(adm, mia_id, wiki=0)
        ids = [e["id"] for e in ok(rita.put(f"/api/wiki/pages/{s['id']}/editors",
                                            json={"user_ids": [mia_id, ralf_id]}))["editors"]]
        assert sorted(ids) == sorted([mia_id, ralf_id]), ids
        assert [e["id"] for e in ok(rita.put(f"/api/wiki/pages/{s['id']}/editors",
                                             json={"user_ids": [ralf_id]}))["editors"]] == [ralf_id]
        # Abgewählt ist sie „neu“ – ein zweites Mal lässt sie sich ohne Stufe nicht mehr freigeben.
        assert rita.put(f"/api/wiki/pages/{s['id']}/editors", json={"user_ids": [ralf_id, mia_id]}).status_code == 400
        # Ein Ersteller, der seine Stufe verloren hat, bleibt beim erneuten Setzen derselben Kennung unverändert.
        stufe_setzen(adm, rita_id, wiki=0)
        assert ok(adm.put(f"/api/wiki/pages/{s['id']}/creator", json={"user_id": rita_id}))["page"]["created_by"] == rita_id


# --- 5 README, 6 Hilfetext ----------------------------------------------------------------------------------------

def test_5_readme_und_6_hilfetext():
    readme = lesen("README.md")
    assert "In den Papierkorb oder endgültig löschen kann ein Mitglied" not in readme
    assert ("In den Papierkorb legen oder endgültig löschen kann ein Redakteur nur eigene Seiten und nur Teilbäume ohne "
            "Seiten anderer Ersteller; ein Mitglied löscht keine Seiten, die Wiki-Verwaltung jede (`can_delete`).") in readme
    js = lesen("app/static/js/pruefungen.js")
    assert ("Ausbilder ist nur, wer ein Konto mit Stufe in den Riegenkarten hat – suche die Person über Namen oder "
            "vollständige E-Mail-Adresse.</p>") in js


# --- 7 Leistungsdialog bei eingefrorenen Bewertungen --------------------------------------------------------------

def test_7_eingefrorener_leistungsdialog():
    js = lesen("app/static/js/pruefungen.js")
    dlg = js[js.index("  function leistungDialog(l) {"):js.index("  async function leistungLoeschen(l) {")]
    assert "const fest = !neu && !!l.kriterien_eingefroren;" in dlg
    # Alles nur zum Lesen, die Beschreibung als Text, die Kriterien ohne eigenen Satz.
    assert 'required${nurLesen}>' in dlg and 'value="${l.zeitansatz_sekunden != null ? fmtZeit(l.zeitansatz_sekunden) : ""}"${nurLesen}>' in dlg
    assert '<div class="md pl-fest">' in dlg and "kriterienListeHtml(l, fest)" in dlg
    assert 'const holen = fest ? () => l.beschreibung_md : mdEditorEinrichten(' in dlg
    # Der Grund als Satz über der Knopfzeile, „Speichern“ ausgegraut und fokussierbar (aria-disabled + describedby).
    satz = dlg.index('<p class="help knopfgrund" id="pl-grund" aria-live="polite">${esc(LEISTUNG_EINGEFROREN)}</p>')
    assert satz < dlg.index('<div class="dlg-actions">')
    assert '<button class="btn" id="pl-save" type="button"${fest ? \' aria-disabled="true" aria-describedby="pl-grund"\' : ""}>' in dlg
    assert 'if (knopf.getAttribute("aria-disabled") === "true") {' in dlg and 'grund.classList.add("betont");' in dlg
    # Der Satz sagt, was nicht mehr geht – und passt zum Server (dieselbe Bedingung wie die Kriterien).
    assert ('const LEISTUNG_EINGEFROREN = "Zu dieser Leistung gibt es Bewertungen von Personen mit vermerktem '
            'Lehrgangsergebnis – deren Prüfungsdaten sind eingefroren, deshalb lassen sich Bezeichnung, Zeitansatz, '
            'Beschreibung und Kriterien nicht mehr ändern. Die Lehrgangsleitung kann das Ergebnis aufheben.";') in js
    py = lesen("app/api_pruefungen.py")
    upd = py[py.index("def update_leistung(lid):"):py.index("def delete_leistung(lid):")]
    assert "_eingefroren_betroffen_pruefen(_LEISTUNG_BETROFFEN, (lid,))" in upd
    assert 'out["kriterien_eingefroren"] = _eingefroren_betroffen(_LEISTUNG_BETROFFEN, (p["id"],))' in py
    css = lesen("app/static/css/pruefungen.css")
    assert "#dlg .knopfgrund { margin: 10px 0 0; color: var(--anthrazit); }" in css
    assert "#dlg .knopfgrund.betont { font-weight: 700; color: var(--rot-auf-flaeche); }" in css


# --- 8 Bild bearbeiten ohne Rundungsverlust ------------------------------------------------------------------------

BILD_SKRIPT = r"""
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const src = js.slice(js.indexOf("  const BILD_FELDER = "), js.indexOf("  function openLightbox(i) {"));
const bildAenderungen = new Function(src + "; return bildAenderungen;")();
const anfang = { title: "DEMO-Titel", note: "", details: "", taken_at: "2026-09-01T10:11", height_m: "", altitude: "512.4" };
console.log(JSON.stringify([
  bildAenderungen(anfang, Object.assign({}, anfang)),
  bildAenderungen(anfang, Object.assign({}, anfang, { title: "DEMO-Neu" })),
  bildAenderungen(anfang, Object.assign({}, anfang, { altitude: "" , height_m: "3,5" })),
  bildAenderungen(anfang, Object.assign({}, anfang, { altitude: "600", taken_at: "2026-09-02T08:00" })),
]));
"""


def test_8_bild_bearbeiten_schickt_nur_geaendertes():
    erg = node(BILD_SKRIPT, os.path.join(WURZEL, "app/static/js/map.js"))
    if erg is not None:
        assert erg == [{}, {"title": "DEMO-Neu"}, {"height_m": "3,5", "altitude": None},
                       {"taken_at": "2026-09-02T08:00", "altitude": "600"}], erg
    js = lesen("app/static/js/map.js")
    assert "const anfang = formular();" in js and "const body = bildAenderungen(anfang, formular());" in js
    assert 'height_m: g("#p-height") || null, altitude: g("#p-alt") || null' not in js
    # Der Server lässt weg, was nicht im Körper steht – Höhe und Aufnahmezeit bleiben auf die Stelle genau.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        aid = ok(adm.post("/api/albums", json={"title": "DEMO-Album", "category": "seil"}), 201)["album"]["id"]
        from app import db
        with app.app_context():
            pid = db.execute("INSERT INTO photos (album_id, owner_id, file, original_name, altitude, taken_at, created_at) "
                             "VALUES (?, 1, 'demo.jpg', 'demo.jpg', 512.37, '2026-09-01T10:11:12', ?)", (aid, db.now()))
        ph = ok(adm.put(f"/api/photos/{pid}", json={"title": "DEMO-Titel"}))["photo"]
        assert (ph["title"], ph["altitude"], ph["taken_at"]) == ("DEMO-Titel", 512.37, "2026-09-01T10:11:12"), ph
        ph = ok(adm.put(f"/api/photos/{pid}", json={}))["photo"]
        assert (ph["altitude"], ph["taken_at"]) == (512.37, "2026-09-01T10:11:12"), ph
        assert ok(adm.put(f"/api/photos/{pid}", json={"altitude": None}))["photo"]["altitude"] is None


# --- 9 Meine PSA, 10 Rückruf-Dialog -------------------------------------------------------------------------------

def test_9_verloren_in_meiner_psa_und_10_rueckruf_dialog():
    js = lesen("app/material/static/material.js")
    karte = js[js.index("  function psaKarte(k, einzeln) {"):js.index("  async function meinePsa() {")]
    assert ("<h2 id=\"psa-${Number(k.id)}\">${inv} ${k.verloren ? '<span class=\"mat-status s-gesperrt\">verloren</span>' "
            ": statusMarke(k.status)}</h2>") in karte
    # Dieselbe Marke wie am Titel der Artikelseite.
    assert "${verloren ? '<span class=\"mat-status s-gesperrt gross\">verloren</span>' : statusMarke(a.status, true)}" in js
    dlg = js[js.index("  function sperrDialog(a, grund, text) {"):js.index("  /* Aussonderung durch den Materialwart")]
    assert '${esc(a.inventory_no)} ${verlust ? "als verloren melden" : "wegen Rückruf sperren"}</h2>' in dlg
    assert '${verlust ? "Verlust melden" : "Wegen Rückruf sperren"}</button>' in dlg
    assert '${verlust ? "als verloren gemeldet" : "wegen Rückruf gesperrt"}' in dlg
    # Der Banner-Knopf bleibt „Sperren (Rückruf)“.
    assert 'data-act="rr-sperren" data-id="${r.id}">Sperren (Rückruf)</button>' in js



# --- 11 Anleitung als „i“ an der Überschrift, 12 Karten mittig ---------------------------------------------------

def test_11_anleitung_als_i_an_der_ueberschrift():
    import re
    common = lesen("app/static/js/common.js")
    teil = common[common.index("window.S.anleitung = (function () {"):]
    assert 'return window.S.info("Anleitung", `${window.S.esc((opt && opt.satz) || ANLEITUNG_SATZ)}<span class="info-absatz"><a' in teil
    assert ">Anleitung in der Strömipedia öffnen</a></span>`);" in teil and "nur-vorlesen" not in teil
    mat = lesen("app/material/static/material.js")
    assert 'infoKnopf("Anleitung", `${esc(satz || ANLEITUNG_SATZ)}<span' in mat
    # Überall IN der Überschrift: nirgends mehr hinter </h1>, und der Hinweiskasten ist weg (das Willkommen bleibt).
    for pfad in ("app/material/static/material.js", "app/static/js/pruefungen.js", "app/static/js/wiki.js"):
        js = lesen(pfad)
        assert not re.search(r"</h1>\$\{(?:anleitungKopf|S\.anleitung\.kopf)\(", js), pfad
    assert mat.count("${anleitungKopf(") == 16 and "anleitungHinweis" not in mat
    assert '<h1>Materialablage${anleitungKopf("uebersicht", ' in mat
    assert '<h1>Riegenkarten${anleitungKopf("uebersicht", ' in lesen("app/static/js/pruefungen.js")
    assert '<h1>Strömipedia${S.anleitung.kopf("uebersicht", { neuerTab: false,' in lesen("app/static/js/wiki.js")
    assert 'if (link) panelTitle.insertAdjacentHTML("beforeend", link);' in lesen("app/static/js/map.js")
    assert "im „i“ an der Überschrift der Übersicht" in lesen("app/material/templates/material/seite.html")
    # Je Überschrift höchstens ein „i“: Keine Überschrift mit „i“ bekommt zusätzlich das der Anleitung.
    for pfad in ("app/material/static/material.js", "app/static/js/pruefungen.js"):
        for h1 in re.findall(r"<h1>.*?</h1>", lesen(pfad)):
            assert not ("anleitungKopf(" in h1 and re.search(r"\b(?:infoKnopf|info)\(", h1)), h1[:120]
    # Menüeinträge und „Mehr dazu“ bleiben.
    wiki = lesen("app/static/js/wiki.js")
    assert "Anleitung zur Strömipedia" in wiki and "Anleitung zum Editor" in wiki
    assert 'target="_blank" rel="noopener">Mehr dazu in der Strömipedia</a></span>' in common
    css = lesen("app/static/css/app.css") + lesen("app/static/css/pruefungen.css") + lesen("app/material/static/material.css")
    assert "mat-anleitung-hinweis" not in css and "> .kopf-anleitung" not in css and ".mat-kopf-anleitung.lnk { display: inline-block; }" in css


def test_12_karten_der_stroemipedia_mittig():
    css = lesen("app/static/css/app.css")
    assert (".wiki-karten { list-style: none; margin: 0 0 8px; padding: 0; container: karten / inline-size;\n"
            "  display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; }") in css
    assert ".wiki-karte { --spalten: 1; flex: 0 0 calc((100% - (var(--spalten) - 1) * 12px) / var(--spalten));" in css
    for breite, n in ((492, 2), (744, 3), (996, 4), (1248, 5)):
        assert f"@container karten (min-width: {breite}px) {{ .wiki-karte {{ --spalten: {n}; }} }}" in css
        assert breite == n * 240 + (n - 1) * 12                    # dieselben Grenzen wie auto-fill ab 240 px
    assert "grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr))" not in css
    assert ".start-wiki .wiki-karten" not in css                   # eine Regel für alle drei Stellen


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print("ok", name)
