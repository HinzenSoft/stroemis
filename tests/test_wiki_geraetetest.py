"""Gerätetest 01.11.2026, Teil 2 – Strömipedia (planung/geraetetest/auftrag_geraetetest.md):
python tests/test_wiki_geraetetest.py  oder  pytest tests/test_wiki_geraetetest.py

  W5/B10  Speicherstand sofort: „Ungespeichert“ nach der Eingabe, „Speichert …“, dann „Gespeichert HH:MM“; Live-Region.
  FT12    „/“-Menü im sichtbaren Bereich: höchstens 40 % hoch, über dem Cursor, wenn darunter der Platz fehlt.
  Q4/Q1   Artikel-Leiste bis 500 px Höhe und mit Tastatur nicht klebend; der Cursor bleibt unter den Leisten sichtbar.
  T1      Artikel-Leiste einzeilig: Pfad nimmt nur den Rest und kürzt den Mittelteil, „Teilen“/„Inhaltsverzeichnis“
          weichen am Finger in „⋯“ aus.
  FT1     Inhaltsverzeichnis in „⋯“ (Lesen und Bearbeiten), als Dialog, wenn keine Gliederung neben dem Text steht.
  O1      Kästchen von Aufgabenlisten 24 px mit Namen.
  W6      Kommentar als Blatt über dem Artikel, solange die Kommentare unter dem Artikel stehen.
  FT5     Rein numerische Dateinamen werden kein Alternativtext.
  FT4     Erfolgsmeldungen für Hochladen und Kommentar erledigt/wieder öffnen/löschen.
Statisch über die Quelltexte; Verhalten und Maße sind im Browser gemessen (planung/geraetetest/bericht_teil2.md)."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i)]


def test_speicherstand():
    js = lies("app/static/js/wiki.js")
    assert '<span class="muted small" id="ed-status" role="status" aria-live="polite"></span>' in js
    assert 'const uhrzeit = () => new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });' in js
    # Sofort nach der Eingabe – nicht während einer laufenden Anfrage, nicht bei Konflikt oder fremdem Schreiber.
    aenderung = abschnitt(js, 'meinEditor.on("change", () => {\n      // Während einer Anfrage', "editorCleanup.push")
    # verweigert: nach einem 403 (Nachbesserung vom 02.11.2026) kein „Ungespeichert“ mehr – es wird nicht mehr gespeichert.
    assert 'if (!isNew && !konflikt && !verweigert && !state.editorGesperrt && !sichertGerade) stand("Ungespeichert");' in aenderung
    assert "spaeterSichern();" in aenderung
    sichern = abschnitt(js, "const jetztSichern = async () => {", "const spaeterSichern")
    assert 'stand("Speichert …");' in sichern
    assert "gespeichertAnzeige = `Gespeichert ${uhrzeit()}" in sichern
    # Während der Anfrage weitergeschrieben: nicht „Gespeichert“ melden.
    assert 'stand(editorStand() !== md ? "Ungespeichert" : gespeichertAnzeige, EDMD.repariert());' in sichern
    assert "if (md === gesichert) { state.dirty = false; stand(gespeichertAnzeige); return true; }" in sichern
    # Das Hochladen räumt die Statuszeile nur weg, wenn dort noch sein eigener Text steht.
    datei = abschnitt(js, "function pickFile(accept, cb) {", "function pickImage(cb)")
    assert "if (status && status.textContent === ladeText) status.textContent = \"\";" in datei


def test_slash_menue():
    js = lies("app/static/js/wiki.js")
    menue = abschnitt(js, "const renderSlash = () => {", "const pick = (i) => {")
    assert "window.visualViewport" in menue
    assert "Math.floor(sichtHoehe * 0.4)" in menue
    assert "if (hoehe > unten && oben > unten) {" in menue
    assert "verdeckteHoehe()" in menue
    # Pfeiltasten: der gewählte Eintrag bleibt im rollenden Menü sichtbar.
    assert 'menu.querySelector("button.sel")' in menue and "menu.scrollTop" in menue
    css = lies("app/static/css/app.css")
    assert "max-height: 40vh; overflow: auto;" in css[css.index(".ed-slash {"):css.index(".ed-slash-title")]
    assert ".ed-slash { max-height: 40dvh; }" not in css


def test_leisten_und_cursor():
    css = lies("app/static/css/app.css")
    hoehe = abschnitt(css, "@media (max-height: 500px) {\n  .wiki-head", "\n}")
    assert "position: static;" in hoehe
    assert "html.tastatur .wiki-head, html.tastatur .wiki-head.editing-head { position: static; }" in css
    js = lies("app/static/js/wiki.js")
    assert "const verdeckteHoehe = () => {" in js
    plugin = abschnitt(js, "const leistenAbstand = ({ pmState }) => ({", "/* Toast UI baut im WYSIWYG")
    assert 'Object.defineProperty(plugin.props, "scrollThreshold"' in plugin
    assert 'Object.defineProperty(plugin.props, "scrollMargin"' in plugin
    assert "verdeckteHoehe()" in plugin
    assert "plugins: [autorWidget, layoutPlugin, medienNodeView, leistenAbstand," in js


def test_artikel_leiste_einzeilig():
    css = lies("app/static/css/app.css")
    assert ".wiki-head .krumen { flex: 1 1 0; min-width: 0; flex-wrap: nowrap; overflow: hidden; }" in css
    assert "container: wiki-kopf / inline-size;" in css
    block = abschnitt(css, "@container wiki-kopf (max-width: 720px) {", "\n  }")
    assert ".btn-row #pg-share, .btn-row #pg-toc { display: none; }" in block
    assert css.rindex("@media (pointer: coarse) {", 0, css.index("@container wiki-kopf")) > 0
    assert ".krumen.kurz .krumen-mitte { display: none; }" in css
    assert ".krumen.kurz .krume-auslassung { display: contents; }" in css
    assert ".krumen .krume-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" in css
    # Telefon im Editor: nur der Speicherstand gibt nach.
    assert ".wiki-head.editing-head .btn-row { flex: 1 1 auto; min-width: 0; flex-wrap: nowrap; justify-content: flex-end; }" in css
    assert ".wiki-head.editing-head .btn-row > :not(#ed-status) { flex: none; }" in css
    js = lies("app/static/js/wiki.js")
    pfad = abschnitt(js, "function krumenPfad(crumbs, p, neu) {", "/* Mittelteil des Pfads kürzen")
    assert '<span class="krumen-mitte">' in pfad and '<span class="krume-auslassung" aria-hidden="true">' in pfad
    assert '<span class="krume-text">${esc(c.title)}</span>' in pfad
    assert "function krumenKuerzen() {" in js and "function kopfBeobachten() {" in js
    assert js.count("kopfBeobachten();") == 2


def test_inhaltsverzeichnis_im_menue():
    js = lies("app/static/js/wiki.js")
    assert "const tocImMenue = () => {" in js and "function tocAusMenue() {" in js
    seite = abschnitt(js, "function pageMenu(anchor, p) {", "function importDialog()")
    assert "${tocMenueEintrag()}" in seite and 'if (a === "toc") return tocAusMenue();' in seite
    editor = abschnitt(js, 'const mehr = $("#ed-more");', "const leseKnopf")
    assert "${tocMenueEintrag()}" in editor and 'b.dataset.a === "toc"' in editor
    dlg = abschnitt(js, "function tocAusMenue() {", "/* ====")
    assert "<h2>Inhaltsverzeichnis</h2>" in dlg and "nachDialog(" in dlg
    assert "function nachDialog(fn) {" in js
    css = lies("app/static/css/app.css")
    assert "dialog .toc-list a { display: flex; align-items: center; min-height: 44px; }" in css


def test_aufgabenlisten():
    css = lies("app/static/css/app.css")
    assert ".wiki-content li > input[type=checkbox] { width: 24px; height: 24px;" in css
    md = lies("app/static/js/markdown.js")
    block = abschnitt(md, 'wurzel.querySelectorAll("li > input[type=checkbox]")', "// Bilder und Videos")
    assert 'kaestchen.setAttribute("aria-label"' in block and 'querySelectorAll("ul, ol, input")' in block


def test_kommentar_blatt_und_meldungen():
    js = lies("app/static/js/wiki.js")
    assert "function kommentarHtml(c, isReply) {" in js and "function kommentarAktionen(wurzel, zu) {" in js
    assert "function kommentarBlatt(c) {" in js
    assert "if (c && schmalesRaster.matches) return kommentarBlatt(c);" in js
    aktionen = abschnitt(js, "function kommentarAktionen(wurzel, zu) {", "function renderComments()")
    assert 'toast(c.resolved ? "Kommentar wieder geöffnet" : "Kommentar erledigt");' in aktionen
    assert 'toast("Kommentar gelöscht")' in aktionen
    assert "kommentarAktionen(commentsEl);" in js


def test_dateinamen_und_upload_meldung():
    js = lies("app/static/js/wiki.js")
    m = re.search(r"return /(\^\[[^/]+\]\*\$)/\.test\(n\) \? \"\" : n;", js)
    assert m, "nameOhneEndung"
    muster = re.compile(m.group(1))
    for name in ("48698", "20261101_120301", "1234-5678", "", "000.1"):
        assert muster.match(name), name
    for name in ("Knoten", "IMG_1234", "Seil 2", "Bild48698"):
        assert not muster.match(name), name
    assert "const alt = nameOhneEndung(f.name);" in js
    assert "mdBeschriftung(nameOhneEndung(f.name))" in js
    assert 'const alt = r.kind === "video" ? "Video" : nameOhneEndung(file.name);' in js
    assert js.count("hochgeladenMelden(r.kind, alt);") == 2
    assert '"Bild hochgeladen – den Alternativtext trägst du am Bild unter „ALT“ ein."' in js
    assert 'f.name.replace(/\\.[^.]+$/, "")' not in js


if __name__ == "__main__":
    test_speicherstand()
    test_slash_menue()
    test_leisten_und_cursor()
    test_artikel_leiste_einzeilig()
    test_inhaltsverzeichnis_im_menue()
    test_aufgabenlisten()
    test_kommentar_blatt_und_meldungen()
    test_dateinamen_und_upload_meldung()
    print("Gerätetest Teil 2 (Strömipedia) bestanden.")
