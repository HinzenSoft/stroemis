"""Reste vor dem finalen Test (27.10.2026) – fünf kleine Punkte aus der Liste nach dem Merge, Teil A:
python tests/test_material_reste.py  oder  pytest tests/test_material_reste.py

  1  Langer Mangeltext im Banner der Artikelseite: ab 600 Zeichen eingeklappt, „Weiterlesen“ zeigt den Rest.
  2  Brotkrumen am Telefon in einer Zeile: lange Glieder mit „…“, ab vier Gliedern „…“ für den Mittelteil.
  3  Knopf „Produktmeldungen“ im Katalog (vorher „Meldungen“), Seitentitel ebenso.
  4  Ergebnisseite einer Prüfung ohne doppeltes „Ergebnis / Ergebnis“.
  5  Unterschrift-Dialog: Fokus beim Öffnen auf der Zeichenfläche (Rechner) bzw. dem Titel (Touch), nicht auf „Abbrechen“.

Gemessen wird im Browser (Bericht); hier die Server-Seite und die Stellen im Code, an denen die Lösungen hängen. Alle
Namen und Texte sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import umgebung  # noqa: E402
from test_material_meine_psa import aufbau, melden, post_mangel  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _block(text, anfang, ende="\n  }\n"):
    i = text.index(anfang)
    return text[i:text.index(ende, i) + len(ende)]


def test_mangeltext_weiterlesen():
    """1: Der Server liefert die Beschreibung ganz (auch über 600 Zeichen); eingeklappt wird nur im Banner der Artikelseite."""
    js, css = lies("app/material/static/material.js"), lies("app/material/static/material.css")
    kurz = _block(js, "  function mangelTextKurz(m, klasse) {")
    assert "const MANGEL_LANG = 600, MANGEL_ANFANG = 400;" in js
    assert "if (t.length < MANGEL_LANG) return mangelText(m, klasse);" in kurz           # kürzere Texte unverändert
    assert "m.inhalt ?" in kurz                                                          # verborgener Inhalt bleibt verborgen
    for teil in ('<span class="mat-mangel-punkte" aria-hidden="true"> …</span>', '<span class="mat-mangel-rest" hidden>${esc(t.slice(schnitt))}</span>',
                 '${esc(t.slice(0, schnitt))}', 'class="btn secondary small" data-act="mangel-weiterlesen" aria-expanded="false" aria-controls="${id}">Weiterlesen</button>'):
        assert teil in kurz, teil
    umschalten = _block(js, "  function mangelWeiterlesen(b) {")
    assert 'b.textContent = auf ? "Weniger anzeigen" : "Weiterlesen";' in umschalten and 'b.setAttribute("aria-expanded", String(auf));' in umschalten
    # Nur der Banner der Artikelseite kürzt; Hinweis in der Prüfung und erledigte Meldungen zeigen den Text ganz.
    assert '${mangelTextKurz(m, "mat-text mat-mangel-text")}' in _block(js, "  function mangelBanner(m, sperre) {")
    assert "mangelTextKurz" not in _block(js, "  function mangelHinweis(liste, berichtigung) {")
    assert "mangelTextKurz" not in _block(js, "  function mangelErledigt(liste) {")
    assert '"mangel-weiterlesen": (b) => mangelWeiterlesen(b),' in js
    assert ".mat-mangel-banner .mat-mangel-mehr { margin: 2px 0 10px; }" in css
    # Unter Touch 44 px hoch wie jeder Knopf in #mat-inhalt (gemessen 99 × 44 bei 344/390 px).
    assert ":where(#mat-inhalt, #dlg, dialog .dlg-actions) .btn" in css

    lang = "Platzhalter " * 160                                                          # 1 920 Zeichen
    with tempfile.TemporaryDirectory() as tmp, post_mangel():
        t = aufbau(tmp)
        r = melden(t.w, t.art[0], lang)
        assert r.status_code == 201, r.get_data(as_text=True)
        a = t.w.get(f"/api/material/artikel/{t.art[0]}").json["artikel"]
        m = [x for x in a["maengel"] if x["offen"]][0]
        assert m["inhalt"] and m["description"].strip() == lang.strip(), len(m["description"])
        assert isinstance(m["id"], int)                                                  # für id="mangel-text-<id>"
    print("Weiterlesen bestanden.")


def test_brotkrumen_eine_zeile():
    """2: Jedes Glied in .mat-pfad-glied, ab vier Gliedern die Lücke „…“; am Telefon eine Zeile mit Kürzung."""
    js, css = lies("app/material/static/material.js"), lies("app/material/static/material.css")
    pfad = _block(js, "  function pfadHtml(glieder) {")
    assert 'const html = glieder.filter(Boolean).map((g, i) => `<span class="mat-pfad-glied">${i ? "/ " : ""}${g}</span>`);' in pfad
    assert ('if (html.length > 3) html.splice(1, 0, \'<span class="mat-pfad-glied mat-pfad-luecke">/ <button type="button" '
            'class="mat-pfad-mehr" aria-label="Ganzen Pfad zeigen">…</button></span>\');') in pfad
    klick = js[js.index("  // „…“ in gekürzten Brotkrumen (pfadHtml)"):]
    klick = klick[:klick.index("  });\n") + 6]
    assert 'pfad.classList.add("offen");' in klick and 'pfad.querySelector(".mat-pfad-luecke ~ .mat-pfad-glied a")' in klick
    # Am Rechner und über 600 px bleibt alles wie bisher: die Lücke gibt es dort nicht.
    assert "\n.mat-pfad-luecke { display: none; }\n" in css
    block = css[css.index("/* Brotkrumen am Telefon (Reste vor dem finalen Test, 2)"):]
    block = block[:block.index("\n  }\n}\n")]
    assert "@media (pointer: coarse) {\n  @container mat-seite (max-width: 600px) {" in block
    for regel in (".mat-pfad:not(.offen) { flex-wrap: nowrap; }",
                  ".mat-pfad:not(.offen) > .mat-pfad-glied { flex: 0 1 auto; min-width: calc(44px + 1em); }",
                  ".mat-pfad:not(.offen) > .mat-pfad-glied:first-child { min-width: 44px; }",
                  ".mat-pfad:not(.offen) > .mat-pfad-glied:not(:first-child, :last-child) { flex-shrink: 1000; }",
                  ".mat-pfad:not(.offen) > .mat-pfad-glied:last-child:not(:nth-child(2)) { flex-shrink: 0; max-width: 50%; }",
                  ".mat-pfad:not(.offen) > .mat-pfad-glied:first-child:nth-last-child(2) { flex-shrink: 0; max-width: calc(100% - 44px - 2em); }",
                  "min-width: 44px; line-height: 44px; overflow: hidden;", "text-overflow: ellipsis;",
                  ".mat-pfad:not(.offen) > .mat-pfad-luecke { display: inline-flex; }",
                  ".mat-pfad:not(.offen) > .mat-pfad-luecke ~ .mat-pfad-glied:not(:last-child) { display: none; }",
                  ".mat-pfad-mehr { min-width: 44px; min-height: 44px;"):
        assert regel in block, regel
    # Die Prüfseite (Vorlage) hat ihre zwei Glieder ebenfalls je in einem .mat-pfad-glied.
    pruefen = lies("app/material/templates/material/pruefen.html")
    assert ('<div class="mat-pfad"><span class="mat-pfad-glied"><a href="/materialablage">Materialablage</a></span> '
            '<span class="mat-pfad-glied">/ <a href="/materialablage/pruefungen">Prüfungen</a></span></div>') in pruefen
    print("Brotkrumen bestanden.")


def test_produktmeldungen():
    """3: Knopf und Seitentitel heißen wie die Seite."""
    js = lies("app/material/static/material.js")
    assert 'href="/materialablage/katalog/meldungen">Produktmeldungen<span class="mat-meldezahl" id="kat-meldungen" hidden></span></a>' in js
    assert 'href="/materialablage/katalog/meldungen">Meldungen<' not in js
    assert '"meldungen": "Produktmeldungen"' in lies("app/material/templates/material/seite.html")
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        r = k["katalog"].get("/materialablage/katalog/meldungen")
        assert r.status_code == 200
        titel = re.sub(r"\s+", " ", re.findall(r"<title>(.*?)</title>", r.text, re.S)[0]).strip()
        assert titel == "Produktmeldungen – Materialablage – strömis.de", titel
    print("Produktmeldungen bestanden.")


def test_ergebnis_einmal():
    """4: Unter „Ergebnis“ steht die Marke, keine Zeile „Ergebnis“ mehr."""
    js = lies("app/material/static/material.js")
    box = js[js.index("      const ergebnisBox = pr.entwurf ?"):]
    box = box[:box.index("</dl></section>${protokollHtml()}</div>`;")]
    assert '<h2>Ergebnis</h2><p class="mat-ergebnis-zeile">${ergebnisMarke(pr.ergebnis)}</p><dl class="mat-daten">' in box
    assert "<dt>Ergebnis</dt>" not in box
    assert ".mat-ergebnis-zeile { margin: 0 0 10px; }" in lies("app/material/static/material.css")
    print("Ergebnis bestanden.")


def test_unterschrift_fokus():
    """5: autofocus auf Zeichenfläche bzw. Titel, gesetzt vor showModal() (sonst nähme der Dialog „Abbrechen“)."""
    js = lies("app/material/static/unterschrift.js")
    teil = js[js.index("      const start = "):js.index("      dlg.showModal();") + len("      dlg.showModal();")]
    assert 'const start = window.matchMedia("(pointer: coarse)").matches ? dlg.querySelector("h2") : canvas;' in teil
    assert "start.tabIndex = -1;" in teil and "start.autofocus = true;" in teil
    # Die Knöpfe bleiben in ihrer Reihenfolge; „Abbrechen“ trägt kein autofocus.
    assert 'data-us="ab">Abbrechen</button>' in js and "autofocus" not in js[js.index("dlg.innerHTML"):js.index("document.body.appendChild(dlg);")]
    print("Unterschrift bestanden.")


if __name__ == "__main__":
    test_mangeltext_weiterlesen()
    test_brotkrumen_eine_zeile()
    test_produktmeldungen()
    test_ergebnis_einmal()
    test_unterschrift_fokus()
