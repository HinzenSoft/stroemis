"""Gerätetest 01.11.2026 – Teil 3 Riegenkarten (Auftrag planung/geraetetest/auftrag_geraetetest.md):
python tests/test_geraetetest_riegen.py  oder  pytest tests/test_geraetetest_riegen.py

  B2  „Voraussetzungen“ als erkennbarer Aufklapper (Pfeil, Zeile als Knopf, „4 von 6 erfüllt“, offen bei Offenem).
  B3/Q3  Reiter kleben unter der Kopfleiste, Angaben am Telefon und bei wenig Höhe zugeklappt, Bearbeiten/Import im Menü.
  F2  Status der Lehrgangsliste in einer Zeile, offene Mängel und Voraussetzungen unter dem Titel.
  W1  Ohne Netz: Anzeige zurück, „Nicht gespeichert – keine Verbindung.“, solange die Antwort fehlt „Wird gespeichert …“.
  W2  Abhaken mit Erfolgsmeldung (Toast role="status"), Fokus bleibt, Zuschreibung 14 px.
  W4  Kriterien-Schalter mit dem Zustand im Namen.   B11  Überschriften der Beschreibungen drei Stufen tiefer, leere weg.
  FT6 Neuer Lehrgang öffnet bei den Teilnehmenden, Leerzustand; „Alle Bewertungen“ meldet am Feld; „Verlauf“ erst mit Verlauf.
  FT7 Fehler am Feld im Bewertungsdialog.   FT4 Erfolgsmeldungen für bisher stille Schreibvorgänge.
Das Verhalten im Browser (Lage, Kleben, Tippflächen, ohne Netz, hängende Anfrage) ist gemessen
(planung/geraetetest/bericht_teil3.md); hier steht, dass die Stellen im Code hängen. Nur Platzhalter."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RK, PCSS = "app/static/js/pruefungen.js", "app/static/css/pruefungen.css"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, von, bis):
    return text[text.index(von):text.index(bis, text.index(von))]


def test_b2_voraussetzungen_aufklapper():
    rk, css = lies(RK), lies(PCSS)
    tn = abschnitt(rk, "function teilnehmerHtml(lg) {", "async function voraussetzungSetzen(cb) {")
    assert "const vorAuf = (tn) => (state.vorKlapp[tn.id] != null ? state.vorKlapp[tn.id] : tn.voraussetzungen_offen > 0);" in tn
    assert '<details class="vor-klapp" data-tid="${tn.id}"${vorAuf(tn) ? " open" : ""}>' in tn
    assert "${vor.length - (tn.voraussetzungen_offen || 0)} von ${vor.length} erfüllt</span></summary>" in tn
    # Der Zustand übersteht das Neuzeichnen; wer in der Karte abhakt, behält sie offen.
    assert 'else if (d.classList.contains("vor-klapp")) state.vorKlapp[+d.dataset.tid] = d.open;' in rk
    assert "if (inKarte) state.vorKlapp[tid] = true;" in rk
    assert 'const AUFKLAPPER = "details:not(.lg-kopf):not(.vor-klapp):not(.menue)";' in rk
    # Gezeichneter Pfeil (Chrome zeichnet bei flex keinen), die ganze Zeile mit Rahmen.
    assert ".pruef details:is(.vor-klapp, .lg-kopf, .beschreibung-kopf, .staende) > summary::before," in css
    assert "border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: translateY(-70%) rotate(-45deg);" in css
    assert "[open] > summary::before { transform: translateY(-70%) rotate(45deg); }" in css
    zeile = abschnitt(css, ".tn-karte details.vor-klapp > summary {", "}")
    assert "border: 1px solid var(--linie)" in zeile and "display: flex" in zeile and "min-height" not in zeile
    assert ".vor-klapp-zahl.offen { color: var(--rot-auf-flaeche); font-weight: 700; }" in css
    # Am Finger ist die Beschriftung neben dem Kasten mindestens 44 px hoch (nur unter pointer: coarse).
    assert "  .vk-zeile .vk-text { min-height: 44px; display: flex; flex-direction: column; justify-content: center; }" in css


def test_b3_q3_kopf_und_reiter():
    rk, css = lies(RK), lies(PCSS)
    assert 'const kompaktMq = window.matchMedia("(max-width: 760px), (max-height: 599px)");' in rk
    assert "const kopfOffen = () => !kompaktMq.matches || state.kopfOffen === true;" in rk
    kopf = abschnitt(rk, "function renderLehrgangSeite() {", "function renderReiter() {")
    assert '<details class="lg-kopf"${kopfOffen() ? " open" : ""}>' in kopf
    assert '<summary><span class="lg-kopf-titel">Angaben zum Lehrgang</span>' in kopf
    assert '<div class="reiter-kleben">\n        <div class="su-banner hidden" id="su-banner"></div>' in kopf
    assert '<button class="btn secondary" data-act="lg-import-in"' not in kopf
    assert "reiterObenSetzen();\n    renderReiter();" in kopf
    # Die Höhe der Kopfleiste wird gemessen – rollt sie mit, kleben die Reiter ganz oben.
    oben = abschnitt(rk, "function reiterObenSetzen() {", "\n  }\n")
    assert 'pos === "sticky" || pos === "fixed" ? Math.round(k.getBoundingClientRect().height) : 0' in oben
    assert 'new MutationObserver(reiterObenSetzen).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });' in rk
    # Reiterwechsel unten: der neue Reiter beginnt unter der Leiste.
    assert "if (klebt) window.scrollTo({ top: Math.max(0, window.scrollY + $(\"#reiter-inhalt\").getBoundingClientRect().top - unterLeiste) });" in rk
    assert ".pruef .reiter-kleben { position: sticky; top: var(--reiter-oben, var(--topbar)); z-index: 30; background: var(--weiss);" in css
    assert "@media (min-width: 761px) and (min-height: 600px) {\n  .pruef details.lg-kopf > summary { display: none; }\n}" in css
    assert ".pruef[data-ansicht=lehrgang] .page-head { flex-wrap: nowrap; align-items: flex-start; }" in css
    assert ".pruef details.lg-kopf[open] > summary .lg-kopf-kurz { display: none; }" in css
    assert ".pruef .c-tabs.reiter { margin: 14px 0 16px; }" not in css


def test_f2_liste():
    rk, css = lies(RK), lies(PCSS)
    liste = abschnitt(rk, "async function listeLaden(erstmal) {", "Kataloge: Vorlagen")
    assert '<col class="lg-status-spalte">' in liste and "${lgHinweisHtml(lg)}</td>" in liste
    assert "${fortschrittHtml(lg, { ohneHinweise: true })}" in liste
    assert "#lg-tabelle col.lg-status-spalte { width: 9.5em; }" in css
    assert "#lg-tabelle td[data-l=Status] .badge { white-space: nowrap; overflow-wrap: normal; }" in css


def test_w1_w2_voraussetzung_setzen():
    rk, css = lies(RK), lies(PCSS)
    assert 'const NICHT_GESPEICHERT = "Nicht gespeichert – keine Verbindung.";' in rk
    assert "const schreibFehler = (e) => (e && e.status === 0 ? Object.assign(new Error(NICHT_GESPEICHERT), { status: 0 }) : e);" in rk
    vs = abschnitt(rk, "async function voraussetzungSetzen(cb) {", "async function verlaufDialog(")
    assert 'zeigen("Wird gespeichert …");' in vs
    assert 'setTimeout(() => zeigen("Noch nicht gespeichert – keine Antwort vom Server"), 10000);' in vs
    assert "cb.checked = !erfuellt;" in vs and "S.fehlschlag(cb, schreibFehler(e));" in vs and "clearTimeout(langsam);" in vs
    assert 'toast(`Gespeichert – ${tn ? `${tnName(tn)}: ` : ""}„${v ? v.bezeichnung : "Voraussetzung"}“ ${erfuellt ? "erfüllt" : "nicht erfüllt"}`);' in vs
    assert "if (neu && hatteFokus) neu.focus({ preventScroll: true });" in vs
    # Bewertung, Kommentar, Ergebnis ohne Netz mit derselben Meldung.
    assert rk.count("S.fehlschlag(knopf, schreibFehler(e));") >= 3
    assert ".vk-zeile .vk-text small { display: block; font-size: var(--fs-mittel);" in css
    assert ".vk-stand.speichert {" in css


def test_w4_kriterien_zustand_im_namen():
    rk = lies(RK)
    assert 'const KRIT_TEXT = { leer: "nicht bewertet", ja: "erfüllt", nein: "nicht erfüllt" };' in rk
    assert 'aria-label="${esc(k.bezeichnung)}: ${KRIT_TEXT[z]}">' in rk
    assert '<span class="nur-vorlesen" id="bw-krit-ansage" aria-live="polite"></span>' in rk
    assert 'btn.setAttribute("aria-label", name);' in rk and '$("#bw-krit-ansage", form).textContent = name;' in rk
    assert 'btn.setAttribute("aria-pressed", String(naechster === "ja"));' not in rk


def test_b11_ueberschriften():
    rk, css = lies(RK), lies(PCSS)
    md = abschnitt(rk, "const md = (text) => {", "\n  };\n")
    assert 't.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach((h) => {' in md
    assert 'if (!h.textContent.trim() && !h.querySelector("img")) { h.remove(); return; }' in md
    assert "document.createElement(`h${Math.min(6, +h.tagName[1] + 3)}`)" in md
    assert ".leistung-karte .md-vorschau :is(h4, h5, h6) {" in css
    assert ".pruef .md :is(h4, h5, h6), #dlg .md :is(h4, h5, h6) {" in css


def test_ft6_ft7_ft4():
    rk = lies(RK)
    # FT6
    # Seit der Einführung (03.11.2026) über S.ziel – in der Übung behält die Adresse ihre Kennung.
    assert 'meldungMerken("Lehrgang angelegt"); location.href = S.ziel(`/riegenkarten/${lg.id}#teilnehmer`);' in rk
    assert "#leistungen`; });" not in rk
    assert "<strong>Noch niemand eingetragen</strong>" in rk
    assert 'S.feldFehler($("#mf-tn"), "Bitte zuerst eine Person wählen.")' in rk
    assert 'toast("Bitte zuerst eine Person wählen.", true)' not in rk
    assert '${tns.length ? \'<button class="btn secondary small" data-act="m-alle" id="mf-alle"' in rk
    assert '${st ? `<button type="button" class="btn secondary small vk-verlauf"' in rk
    # FT7
    assert '<div class="bew-wahl" id="bw-wahl" role="group" aria-labelledby="bw-wahl-label" tabindex="-1">' in rk
    assert 'S.feldFehler(wahl, "Bitte „bestanden“ oder „mangelhaft“ wählen.")' in rk and "S.feldOk(wahl);" in rk
    assert 'S.feldFehler(komm, e.message)' in rk
    # FT4: Reihenfolge, Voraussetzungen und Kriterien melden sich.
    assert rk.count('toast("Reihenfolge gespeichert");') == 2
    assert 'toast(b.hasAttribute("data-del") ? "Voraussetzung gelöscht" : "Reihenfolge gespeichert");' in rk
    assert rk.count('toast(b.hasAttribute("data-krit-del") ? "Kriterium gelöscht" : "Reihenfolge gespeichert");') == 2
    assert rk.count('toast("Kriterium angelegt");') == 2 and 'toast("Voraussetzung angelegt");' in rk
    assert 'toast("Umbenannt");' in rk
    # Keine Erklärtexte unter Knöpfen, kein Emoji in den neuen Meldungen.
    for t in re.findall(r'toast\("([^"]+)"\)', rk):
        assert not re.search(r"[\U0001F300-\U0001FAFF]", t), t


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(name, "bestanden.")
