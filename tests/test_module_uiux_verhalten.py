"""UI/UX vor dem Merge, Teil U1a „Verhalten“ (27.10.2026, Auftrag planung/material-phase4/auftrag_uiux_bau.md):
python tests/test_module_uiux_verhalten.py  oder  pytest tests/test_module_uiux_verhalten.py

  A1  Zurück schließt Overlays: S.overlayVerlauf/dialogVerlauf/klassenVerlauf in common.js, eingebaut in alle Dialoge,
      Schubladen, die Seitenleiste der Karte und die Großansichten.
  A2  Fehler am Feld: S.feldFehler/S.fehlschlag – kein „toast(…, true); knopf.disabled = false“ mehr, Pflichtfelder der
      Dialoge melden am Feld; „Grund“ bei Ausnehmen und „aussondern empfohlen“ sichtbar Pflicht.
  A3/D1  Ein Menübaustein (S.menue, S.menueSchwebend); ein Eintrag wird ein Knopf; kurze Sätze in den Einträgen.
  A4  Rückfrage nicht-endgültig ({ endgueltig: false }), Titel = Frage.
  A11 S.plural app-weit.  A12 Strömipedia-Export mit Datum und Uhrzeit.  A13 deutsche Fehlerseiten.
  A15 weiche Bildläufe nur ohne „Bewegung reduzieren“.  A16 Beschriftungen.  D2 Dialogfuß.  D3 Bedienzeichen.
Das Verhalten selbst (Zurück, Tasten, Fokus) prüft die Browserprobe (Bericht bericht_uiux_bau_u1a.md); hier steht, dass
jede Stelle den Baustein benutzt. Alle Inhalte sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import H, make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON = "app/static/js/common.js"
MAT = "app/material/static/material.js"
JS = ["app/static/js/common.js", "app/static/js/wiki.js", "app/static/js/map.js", "app/static/js/pruefungen.js",
      "app/static/js/admin.js", "app/static/js/markdown.js", "app/static/js/public.js", "app/static/js/profile.js",
      MAT, "app/material/static/freigaben.js", "app/material/static/unterschrift.js", "app/material/static/global.js",
      "app/material/static/profil_unterschrift.js"]


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def test_a1_zurueck_schliesst_overlays():
    co = lies(COMMON)
    # Der Baustein: eigener Verlaufseintrag je Overlay, popstate schließt das oberste, Schließen auf anderem Weg nimmt den
    # Eintrag heraus – aber nicht, solange die Seite geht (Chromium bräche den Seitenwechsel sonst ab).
    for teil in ("function overlayVerlauf(schliessen)", "function dialogVerlauf(dlg)", "function klassenVerlauf(el, klasse, schliessen, gilt)",
                 'window.addEventListener("popstate", (e) => {', "history.go(-n);", 'window.addEventListener("beforeunload", () => { ovSeiteGeht = Date.now(); });',
                 "if (ovSeiteGeht && Date.now() - ovSeiteGeht < 3000) return;", "history.pushState = function (state, titel, url) {",
                 "history.replaceState = function (state, titel, url) {", 'const ev = new Event("cancel", { cancelable: true });',
                 "e.stopImmediatePropagation();"):
        assert teil in co, teil
    # S.dialog und S.confirm melden ihren Dialog an; alle eigenen <dialog> der Module ebenso.
    dlg = co[co.index("  function dialog(html, onOpen) {"):co.index("  function frageTeilen(text) {")]
    assert "if (!dlg.open) dlg.showModal();\n    dialogVerlauf(dlg);" in dlg
    conf = co[co.index("  function confirm(text, okLabel, neinLabel, opt = {}) {"):co.index("  function fmtDate(")]
    assert "dlg.showModal();\n      dialogVerlauf(dlg);" in conf
    for pfad, anzahl in (("app/static/js/map.js", 1), ("app/static/js/pruefungen.js", 3), (MAT, 1),
                         ("app/material/static/freigaben.js", 1), ("app/material/static/unterschrift.js", 1)):
        assert lies(pfad).count("S.dialogVerlauf(") == anzahl, pfad
    # Jedes showModal außerhalb von S.dialog/S.confirm hat seinen Verlauf.
    for pfad in JS:
        js = lies(pfad)
        for m in re.finditer(r"(\w+)\.showModal\(\)", js):
            danach = js[m.end():m.end() + 200]
            if pfad == COMMON:
                continue
            assert f"S.dialogVerlauf({m.group(1)})" in danach, (pfad, js[m.start() - 80:m.end() + 80])
    # Schubladen und die Seitenleiste der Karte; die Bildergroßansicht der Strömipedia.
    assert 'S.klassenVerlauf(side, "open", () => side.classList.remove("open"), () => getComputedStyle(side).position === "fixed");' \
        in lies("app/static/js/wiki.js")
    assert "S.klassenVerlauf(side, \"open\"" in lies("app/static/js/public.js")
    assert 'S.klassenVerlauf(leiste, "open", () => leisteZu(true), alsSchublade);' in lies(MAT)
    assert 'S.klassenVerlauf(panel, "open", closePanel);' in lies("app/static/js/map.js")
    assert "verlauf = S.overlayVerlauf(() => { verlauf = null; close(); });" in lies("app/static/js/markdown.js")
    # Die Leitstelle hat keine eigene Rückfrage mehr (A4) – also auch kein eigenes <dialog> ohne Verlauf.
    assert 'document.createElement("dialog")' not in lies("app/static/js/admin.js")
    print("A1 Zurück schließt Overlays bestanden.")


def test_a2_fehler_am_feld():
    co = lies(COMMON)
    for teil in ("function feldFehler(feld, text) {", "function fehlschlag(knopf, fehler, feld) {", 'feld.setAttribute("aria-invalid", "true");',
                 "feld.setAttribute(\"aria-describedby\", [...beschr, p.id].join(\" \"));", "feld.focus();",
                 "const m = text.match(/^„([^“]+)“/);",
                 '(!ae || ae === document.body || ae.tagName === "DIALOG" || ae === knopf)) knopf.focus();'):
        assert teil in co, teil
    # Das alte Muster (Toast, Knopf frei, Fokus verloren) gibt es nirgends mehr.
    alt = re.compile(r"toast\((\w+)\.message, true\);\s*\w+\.disabled = false|\w+\.disabled = false; (S\.)?toast\(\w+\.message, true\)")
    for pfad in JS:
        assert not alt.search(lies(pfad)), (pfad, alt.search(lies(pfad)).group(0))
    mat = lies(MAT)
    # Pflicht „Grund“ sichtbar: Ausnehmen mit „(Pflicht)“ in der Beschriftung, in der Prüfleiste als Satz.
    assert '<label for="dn-grund">Grund (Pflicht)</label>' in mat
    assert 'S.feldFehler($("#dn-grund", body), "Bitte einen Grund angeben – er steht im Sammelprotokoll.")' in mat
    assert 'if (grundPflicht) teile.push("Ohne Mangel ist ein Grund Pflicht");' in mat
    assert 'S.feldFehler(imAbschluss("#pr-grund"), `Ohne Mangel braucht „${ERGEBNIS[ergebnis]}“ einen Grund.`)' in mat
    assert '<p class="error feld-fehler" id="pr-grund-fehler" hidden></p>' in mat
    # Pflichtfelder in Dialogen der anderen Module.
    for pfad, teil in (("app/static/js/pruefungen.js", 'S.feldFehler($("#lg-titel", body), "Bitte einen Titel angeben.")'),
                       ("app/static/js/pruefungen.js", 'S.feldFehler($("#tn-name", body), "Bitte den Nachnamen angeben.")'),
                       ("app/static/js/map.js", 'S.feldFehler(titel, "Bitte einen Titel für das Album angeben.")'),
                       ("app/static/js/admin.js", 'S.feldFehler(body.querySelector("#u-email"), EMAIL_FEHLT)'),
                       ("app/static/js/wiki.js", 'S.feldFehler(body.querySelector("#c-text"), "Der Kommentar ist leer.")'),
                       ("app/material/static/freigaben.js", 'S.feldFehler(feld("mf-person"), "Bitte zuerst eine Person wählen.")')):
        assert teil in lies(pfad), (pfad, teil)
    css = lies("app/static/css/app.css")
    assert ':is(input, select, textarea)[aria-invalid="true"] { border-color: var(--rot); box-shadow: inset 0 0 0 1px var(--rot); }' in css
    print("A2 Fehler am Feld bestanden.")


def test_a3_ein_menuebaustein():
    co = lies(COMMON)
    for teil in ("function menue(opt) {", "function menueSchwebend(anker, box) {", "function menueAusrichten(m) {",
                 'document.addEventListener("focusout", (e) => {', '{ ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: liste.length - 1 }',
                 'liste.style.bottom = "calc(100% + 6px)"', "if (eintraege.length === 1) {"):
        assert teil in co, teil
    # Keine handgebauten Menüs mehr: alle über S.menue bzw. S.menueSchwebend, die alten Schließ-Handler sind weg.
    for pfad in JS:
        js = lies(pfad)
        if pfad == COMMON:
            continue
        assert '<details class="mat-menue">' not in js and '<details class="zeilenmenue">' not in js, pfad
        assert "wireMenuKeys" not in js and 'details.zeilenmenue[open]' not in js and 'details.mat-menue[open]' not in js, pfad
    assert lies("app/static/js/wiki.js").count("S.menueSchwebend(") == 4
    # Ein Eintrag → grauer Knopf: Mailversand, Nacharbeit, Prüfdurchgänge (ohne Anlegen), Leitstelle eigenes Konto,
    # Riegenkarten „Löschen“ der Prüfungsleistung.
    mat = lies(MAT)
    assert "S.menue({ art: \"mat-menue\", links: true, eintraege: [{ text: \"Alle erledigt\"" in mat
    assert 'S.menue({ art: "mat-menue", links: true, eintraege: [{ text: "Als CSV herunterladen"' in mat
    assert '(DARF.verwalten || DARF.pruefen) && { text: "Prüfdurchgang anlegen"' in mat
    assert 'u.id !== STROEMIS.user.id && { text: "Löschen", attrs: \'data-act="delete"\' }' in lies("app/static/js/admin.js")
    assert '${zeilenMenue([["Löschen", `data-act="${praefix}-del" data-lid="${l.id}"`]])}' in lies("app/static/js/pruefungen.js")
    # Kurze Sätze unter den Einträgen (am 390er höchstens zwei Zeilen): keiner länger als 45 Zeichen.
    saetze = re.findall(r'satz: "([^"]+)"', mat)
    assert len(saetze) >= 15 and all(len(x) <= 45 for x in saetze), [x for x in saetze if len(x) > 45]
    print("A3/D1 Ein Menübaustein bestanden.")


def test_a4_rueckfrage_nicht_endgueltig():
    co = lies(COMMON)
    assert 'class="${opt.endgueltig === false ? "btn" : "btn danger"}" id="c-ok"' in co
    assert "Bist du sicher?" not in co.replace('titel: t || "Bist du sicher?"', "")   # nur noch Rückfall ohne Frage
    stellen = {"app/static/js/admin.js": 2, "app/static/js/wiki.js": 1, MAT: 3, "app/material/static/freigaben.js": 1}
    for pfad, n in stellen.items():
        assert lies(pfad).count("{ endgueltig: false }") >= n, pfad
    admin = lies("app/static/js/admin.js")
    assert 'S.confirm("", okLabel, "", { titel, html, endgueltig: false, fokus: "nein" })' in admin
    print("A4 Rückfrage bestanden.")


def test_a11_plural_a15_bewegung():
    assert "const plural = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;" in lies(COMMON)
    for pfad in JS[1:]:
        js = lies(pfad)
        assert "=> `${n} ${n === 1 ? eins : viele}`" not in js, pfad
        assert 'behavior: "smooth"' not in js, pfad
    assert 'S.plural(a.photo_count, "Bild", "Bilder")' in lies("app/static/js/map.js")
    assert 'S.plural(tn.voraussetzungen_offen, "Voraussetzung", "Voraussetzungen")' in lies("app/static/js/pruefungen.js")
    assert 'S.plural(state.pages.length, "Seite", "Seiten")' in lies("app/static/js/wiki.js")
    assert '"(prefers-reduced-motion: reduce)"' in lies(COMMON)
    print("A11/A15 bestanden.")


def test_a16_beschriftungen_d2_d3():
    m = lies("app/static/js/map.js")
    for fid in ("al-title", "al-cat", "al-desc", "al-cname", "al-corg", "al-cphone", "al-cemail", "al-cnotes", "ew-title", "ew-cat",
                "p-title", "p-note", "p-height", "p-alt", "p-lat", "p-lon", "p-taken", "p-details"):
        assert f'<label for="{fid}">' in m, fid
    a = lies("app/static/js/admin.js")
    for fid in ("u-name", "u-gl", "u-email", "u-phone", "u-pw"):
        assert f'<label for="{fid}">' in a, fid
    w = lies("app/static/js/wiki.js")
    assert 'aria-label="Nutzer suchen"' in w and '<label for="be-body">' in w and '<label for="be-col-${i}">' in w
    # D2: dritte Aktion links außen, Infodialog mit grauem „Schließen“, „Teilen“ mit „Abbrechen“.
    mat = lies(MAT)
    assert mat.count("dlg-neben") >= 2 and ">OK</button>" not in mat
    assert '<button class="btn secondary dlg-neben" id="ic-clear" type="button">Entfernen</button>' in w
    assert 'data-close type="button">Abbrechen</button><button class="btn" id="sh-save"' in w
    assert "dialog .dlg-actions > .dlg-neben { margin-right: auto; }" in lies("app/static/css/app.css")
    # D3: ein Schließen-Zeichen (✕) mit Namen, Reihenfolge ↑/↓ und Entfernen ✕ über die Hilfen.
    for pfad in JS:
        assert ">×</button>" not in lies(pfad), pfad
    assert '>✕</button>' in lies("app/templates/index.html")
    pr = lies("app/static/js/pruefungen.js")
    assert "S.reihenfolgeKnoepfe(i, n, hoch, runter)" in pr and ">Hoch</button>" not in pr and ">Nach oben</button>" not in pr
    assert pr.count("S.entfernenKnopf(") >= 5
    print("A16/D2/D3 bestanden.")


def test_a12_export_a13_fehlerseiten():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)

        # 500: eine Route, die scheitert (vor der ersten Anfrage angemeldet) – geprüft außerhalb des Testmodus, der
        # Ausnahmen durchreicht.
        @app.get("/probe-kaputt")
        def kaputt():
            raise RuntimeError("Platzhalter-Fehler")

        @app.get("/api/probe-kaputt")
        def kaputt_api():
            raise RuntimeError("Platzhalter-Fehler")

        c = app.test_client()
        assert c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
        r = c.post("/api/wiki/pages", json={"title": "DEMO-Export", "content": "# DEMO-Export\n\nPlatzhalter.\n"}, headers=H)
        pid = r.json["page"]["id"]
        for args, endung in (("", "md"), ("?children=1", "zip")):
            r = c.get(f"/api/wiki/pages/{pid}/export{args}", headers=H)
            assert r.status_code == 200
            name = r.headers["Content-Disposition"]
            assert re.search(r'filename=DEMO-Export_\d{4}-\d{2}-\d{2}_\d{4}\.' + endung, name), name
        wiki = lies("app/static/js/wiki.js")
        assert wiki.count("export?stand=${Date.now()}") == 2 and "export?children=1&stand=${Date.now()}" in wiki

        # A13: 404 und 405 als deutsche Seite mit Kopfleiste und sprechendem Titel, Schnittstellen als JSON.
        r = c.get("/gibt-es-nicht")
        html = r.get_data(as_text=True)
        assert r.status_code == 404 and "<title>Seite nicht gefunden – strömis.de</title>" in html and "Fehler 404" in html
        assert 'class="bauchbinde' in html
        r = c.delete("/profil")
        html = r.get_data(as_text=True)
        assert r.status_code == 405 and "<title>Nicht möglich – strömis.de</title>" in html and "Method Not Allowed" not in html
        r = c.patch("/api/wiki/pages", headers=H)
        assert r.status_code == 405 and r.json["error"] == "Das geht auf dieser Seite nicht."

        app.config["TESTING"] = False
        app.config["PROPAGATE_EXCEPTIONS"] = False
        r = c.get("/probe-kaputt")
        html = r.get_data(as_text=True)
        assert r.status_code == 500 and "<title>Etwas ist schiefgegangen – strömis.de</title>" in html
        assert "Internal Server Error" not in html and "Platzhalter-Fehler" not in html and "Fehler 500" in html
        r = c.get("/api/probe-kaputt", headers=H)
        assert r.status_code == 500 and r.json["error"].startswith("Hier ist etwas schiefgegangen.")
    print("A12 Export und A13 Fehlerseiten bestanden.")


if __name__ == "__main__":
    test_a1_zurueck_schliesst_overlays()
    test_a2_fehler_am_feld()
    test_a3_ein_menuebaustein()
    test_a4_rueckfrage_nicht_endgueltig()
    test_a11_plural_a15_bewegung()
    test_a16_beschriftungen_d2_d3()
    test_a12_export_a13_fehlerseiten()
