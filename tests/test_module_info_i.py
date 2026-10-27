"""Info-„i“ app-weit (27.10.2026): python tests/test_module_info_i.py  oder  pytest tests/test_module_info_i.py

Entscheidungen des Nutzers: „Alle 55 in einem Zug“, „Ja, app-weit“, „Ein „i“ je Liste“ (Bestandsaufnahme
planung/info-i/bestandsaufnahme.md). Geprüft wird hier:
  - S.info in common.js (Markup, aria, Verhalten einmal je Seite, Esc im Dialog, Fokus beim Öffnen eines Dialogs nicht
    aufs „i“), Aussehen in app.css (.info, 44 px nur unter pointer: coarse), das Jinja-Makro „info“ mit demselben Markup;
  - jede der 55 Stellen (M1–M31, R1–R9, W1–W6, A1, L1–L6, P1–P2): das „i“ steht am Begriff, der Erklärsatz nicht mehr
    darunter; was sichtbar bleiben muss (Datenschutz, Folge der Aktion), steht noch da;
  - die Marken einer Liste mit einem „i“ an der Überschrift (title je Zeile bleibt), die zwei Nebenbefunde;
  - die gerenderten Vorlagen (Leitstelle, Profil) mit einem Konto.
Das Verhalten im Browser (Hover, Antippen, Esc, Tab in den Link, Tippflächen) ist gemessen (Bericht); hier hängen die
Stellen im Code. Alle Konten und Inhalte sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


MAT, FRG = "app/material/static/material.js", "app/material/static/freigaben.js"
RK, WIKI, MAP, ADM = "app/static/js/pruefungen.js", "app/static/js/wiki.js", "app/static/js/map.js", "app/static/js/admin.js"
ADMIN_HTML, PROFIL = "app/templates/admin.html", "app/templates/profil.html"

# (Stelle, Datei, das „i“ am Begriff, der frühere Erklärsatz als Hilfezeile – darf nicht mehr vorkommen)
STELLEN = [
    ("M1", MAT, '<h1>Bestand${infoKnopf("Bestand", info)}</h1>', "Oben stehen die Gliederungen"),
    ("M2", MAT, '<span class="info-absatz">${ZAEHLER_LEGENDE}</span>', '!<p class="help mat-legende">'),
    ("M3", MAT, '<h2>Fälligkeiten je Ordner${d.ordner_uebersicht.length ? infoKnopf("Fälligkeiten je Ordner", ordnerUebersichtInfo(',
     "Die Zahlen gelten für den ganzen Zweig"),
    ("M4", MAT, 'if (zuInfo) zuInfo.innerHTML = infoKnopf("Zu prüfen", `Überfällig, Lebensdauer erreicht', "Überfällig, Lebensdauer erreicht"),
    ("M5", MAT, '<h2>Offene Prüfungen${infoKnopf("Offene Prüfungen", "Eine offene Prüfung reserviert', "Eine offene Prüfung reserviert"),
    ("M6", MAT, 'Prüfintervall (Monate)${infoKnopf("Prüfintervall", "Nur zum Verschärfen', "Nur zum Verschärfen"),
    ("M7", MAT, '<h2>Rückrufe${infoKnopf("Rückrufe", "Rückrufe, die im Jahr', "Rückrufe, die im Jahr"),
    ("M8", MAT, 'Kalenderjahr${infoKnopf("Kalenderjahr", "Bestandszahlen gelten zum Stichtag heute', "!CSV. Bestandszahlen gelten"),
    ("M9", MAT, '<h2>QR-Code und NFC${infoKnopf("QR-Code und NFC", "Diese Adresse öffnet', "Diese Adresse öffnet nach der Anmeldung"),
    ("M10", MAT, '<h2>Journal${infoKnopf("Journal", "Änderungen am Artikel und an seinem Produkt', "Änderungen am Artikel und an seinem Produkt, neueste"),
    ("M11", MAT, 'Seriennummer des Herstellers${infoKnopf("Seriennummer des Herstellers", "Ohne Herstellernummer', "Ohne Herstellernummer vergibt"),
    ("M12", MAT, '<h1>Artikel anlegen${infoKnopf("Artikel anlegen", "Neu angelegte Artikel', '!<p class="notice">Neu angelegte Artikel'),
    ("M13", MAT, '${infoKnopf("Dokumente für alle Produkte dieser Kategorie", "Pflegehinweise', "Pflegehinweise, allgemeine Anleitungen"),
    ("M14", MAT, '${infoKnopf("Lebensdauer", "Nur ein Vorschlag beim Anlegen', "Nur ein Vorschlag beim Anlegen"),
    ("M15", MAT, 'Artikel haben eine Länge${infoKnopf("Artikel haben eine Länge", "Seile und Meterware', "Seile und Meterware"),
    ("M16", MAT, '<h2>Bestandteile${infoKnopf("Bestandteile", BESTANDTEILE_INFO)}</h2>', "Jede Prüfung fragt je Position ab"),
    ("M17", MAT, '<h2>Prüfformular${infoKnopf("Prüfformular", "Ein aktives spezifisches Formular', "Ein aktives spezifisches Formular"),
    ("M18", MAT, '<h2>Herstellerdokumente${infoKnopf("Herstellerdokumente", `Gelten für alle Artikel', "Gelten für alle Artikel dieses Produkts"),
    ("M19", MAT, '<strong>Prüfanleitung in der Strömipedia${infoKnopf("Prüfanleitung in der Strömipedia", info)}:</strong>',
     "Die Verknüpfung gehört nicht zum Prüfinhalt"),
    ("M20", MAT, '<h2 class="mat-fp-punkte">Prüfpunkte${infoKnopf("Prüfpunkte", PRUEFPUNKTE_INFO)}</h2>', "Bei der Prüfung ist jeder Befund"),
    ("M21", MAT, 'Seite suchen (Titel)${infoKnopf("Seite suchen", `${WIKI_PRUEFUNG_INFO} Jeder sieht nur', "Jeder sieht nur, was er in der Strömipedia"),
    ("M22", MAT, 'infoKnopf("Eingangsprüfung", "Die erste Prüfung eines Artikels', "Die erste Prüfung eines Artikels ist"),
    ("M23", MAT, '<h2>Anhänge${bearbeitbar() ? infoKnopf("Anhänge", "Externe Prüfkarte', "Externe Prüfkarte, Bericht"),
    ("M24", MAT, '<h1>Änderungsanträge${infoKnopf("Änderungsanträge", "Seit der ersten Prüfung', "Seit der ersten Prüfung stehen die Stammdaten eines Artikels"),
    ("M25", MAT, 'Betroffene Seriennummern${infoKnopf("Betroffene Seriennummern", "Groß/klein', "Groß/klein und Leerzeichen"),
    ("M26", MAT, 'Mail an Materialwarte und Prüfer${infoKnopf("Mail an Materialwarte und Prüfer", "An die Verwalter', "An die Verwalter der betroffenen"),
    ("M27", MAT, '<h1>Bestandsliste importieren${infoKnopf("Bestandsliste importieren", "Importierte Artikel', "Importierte Artikel stehen auf"),
    ("M28", MAT, 'zugeordnet${infoKnopf("Spalten", `Mehrere Spalten in der Bemerkung', "Mehrere Spalten in der Bemerkung"),
    ("M29", MAT, '<th>geändert${b.version === 2 ? infoKnopf("neu und geändert", "Eine geänderte Prüfliste', "Eine geänderte Prüfliste wird"),
    ("M30", FRG, '<label for="mf-anker">Gilt für${info("Gilt für", `Freigaben für', "!gelten dort und in allen Unterordnern, bis\n"),
    ("M31", FRG, '<summary>Geerbt von oben <span class="mf-zahl">${d.geerbt.length}</span>${info("Geerbt von oben", "Freigaben an Oberordnern',
     "Freigaben an Oberordnern gelten"),
    ("R1", RK, '<label>Lehrgangsleitung und Referierende${info("Lehrgangsleitung und Referierende", `Mehrere Personen', "Mehrere Personen können"),
    ("R2", RK, 'aus Katalog übernehmen (optional)${info("Prüfungsleistungen aus Katalog", `Die Leistungen werden einmalig', "Die Leistungen werden einmalig"),
    ("R3", RK, '<h1>Prüfungsleistungskataloge${info("Prüfungsleistungskataloge", `Ein Katalog ist eine Vorlage', "Ein Katalog ist eine Vorlage"),
    ("R4", RK, '<label for="kl-zeit">Zeitansatz${info("Zeitansatz", ZEITANSATZ_INFO)}', "Mit Zeitansatz zeigt"),
    ("R5", RK, '<label for="pl-zeit">Zeitansatz${info("Zeitansatz", ZEITANSATZ_INFO)}', "Mit Zeitansatz zeigt"),
    ("R6", RK, '${info("Kriterienliste", `${KRITERIEN_INFO} Wird beim Anlegen', "!Zusätzlich zur Beschreibung: einzeln abhakbare Punkte. Wird"),
    ("R7", RK, '${info("Kriterienliste", `${KRITERIEN_INFO} Im Bewertungsdialog', "!Zusätzlich zur Beschreibung: einzeln abhakbare Punkte. Im"),
    ("R8", RK, 'Datei (.xlsx)${info("Datei", "Kopfzeilen über der Tabelle', "Kopfzeilen über der Tabelle"),
    ("R9", RK, 'aus dem ISC${info("ISC", `Im ISC unter', "!aus dem ISC übernehmen: Dort unter"),
    ("W1", WIKI, '<h2>Papierkorb${rows.length ? info("Papierkorb", `Wiederhergestellte Seiten', "Wiederhergestellte Seiten kommen"),
    ("W2", WIKI, '<h3>Bearbeiten erlauben${info("Bearbeiten erlauben", "Freigegebene Nutzer', "Freigegebene Nutzer dürfen"),
    ("W3", WIKI, 'Lesen einschränken${info("Lesen einschränken", `Normalerweise darf', "Normalerweise darf jeder Angemeldete"),
    ("W4", WIKI, '<h2>Textfarbe${info("Textfarbe", `Nach dem Handbuch CD', "Nach dem Handbuch CD"),
    ("W5", WIKI, '<h2>Abschnitt einbinden${info("Abschnitt einbinden", `Zeigt einen synchronisierten', "Zeigt einen synchronisierten Abschnitt"),
    ("W6", WIKI, '<h2>Spalten einfügen${info("Spalten einfügen", "Die Spalten stehen im Editor', "Die Spalten stehen im Editor"),
    ("A1", MAP, '${S.info("Album", "Ein Album ist ein Übungsobjekt oder ein Übungsgewässer.")}</h2>', "!Ein Album ist ein Übungsobjekt oder ein Übungsgewässer. Alle"),
    ("L1", ADM, '<label>Rechte${S.info("Rechte", `„–“ kein Zugriff', "kein Zugriff (in der Strömipedia: nur die öffentlichen Seiten lesen) · „Mitglied“"),
    ("L2", ADM, 'Prüfer (Sachkundiger)${S.info("Prüfer", `Das Häkchen wirkt nur', "Das Häkchen wirkt nur mit Stufe"),
    ("L3", ADM, '<legend>Freigaben in der Materialablage${S.info("Freigaben in der Materialablage", "Angelegt wird', "Angelegt wird eine Freigabe am Ordner (Bestand"),
    ("L4", ADM, '<summary>Verlauf (Materialablage)${S.info("Verlauf", "Änderungen an Stufe', "!Änderungen an Stufe, Häkchen „Prüfer“, Urkundennummer und Unterschrift (ohne Bild) –\n"),
    ("L5", ADMIN_HTML, '{% call info("einstellungen", "Einstellungen") -%}', '!<p class="help">Was hier gesetzt wird'),
    ("L6", ADM, 'dazu sagt.${S.info("SPF, DKIM, DMARC", "Kommt sie an', "!dazu sagt. Kommt sie an"),
    ("P1", PROFIL, '<h2>Profilbild{% call info("profilbild", "Profilbild") %}Es steht neben deinem Namen', '!<div class="help">Es steht neben deinem Namen'),
    ("P2", PROFIL, 'Erinnerungen zu meiner PSA per Mail{% call info("psa-mails", "Erinnerungen zu meiner PSA") %}Eine Mail am Morgen',
     '!<div class="help">Eine Mail am Morgen'),
]


def test_app_weit_bereitgestellt():
    common, css = lies("app/static/js/common.js"), lies("app/static/css/app.css")
    info = common[common.index("function info(thema, html) {"):common.index("/* Verhalten der Info-Symbole")]
    for stelle in ('const id = `info-${++infoZahl}`;', '<span class="info"><button type="button" class="info-knopf"',
                   'aria-label="Info zu ${esc(thema)}" aria-expanded="false"', 'aria-controls="${id}" aria-describedby="${id}"',
                   'aria-hidden="true" focusable="false"', '<span class="info-text" role="tooltip" id="${id}" hidden>${html}</span></span>'):
        assert stelle in info, stelle
    assert "return { esc, api, toast, dialog, confirm, fmtDate, fmtCoord, CAT, titel, info };" in common
    verhalten = common[common.index("function infoZeigen(w, an, fest) {"):common.index("/* Seitentitel im Reiter")]
    # Einmal je Seite am document (Delegation) – auch für später gezeichnete; Info in einem Dialog bleibt in dessen Inhalt.
    for stelle in ('document.addEventListener("click"', 'document.addEventListener("pointerover"', 'document.addEventListener("pointerout"',
                   'document.addEventListener("focusin"', 'document.addEventListener("focusout"', 'w.closest("dialog .dlg-body, dialog")',
                   'if (!k && w && e.target.closest(".info-text") && !e.target.closest("a[href]")) e.preventDefault();',
                   'if (w.closest("dialog")) { e.preventDefault(); e.stopPropagation(); }', "}, true);"):
        assert stelle in verhalten, stelle
    # Öffnet ein Dialog mit einem „i“ im Titel, bekommt das erste Bedienelement den Fokus, nicht das „i“.
    dlg = common[common.index("function dialog(html, onOpen) {"):common.index("function confirm(")]
    assert '.find((el) => !el.closest(".info"));' in dlg
    for regel in (".info { position: relative; display: inline-block;", ".info-knopf { display: inline-flex;",
                  ".info-text { position: absolute; top: calc(100% + 6px);", ".info-text[hidden] { display: none; }",
                  ".info-absatz { display: block;",
                  "@media (pointer: coarse) {\n  .info-knopf { width: 44px; height: 44px; margin: -11px -8px -11px -6px; }"):
        assert regel in css, regel
    # Die Materialablage nutzt dieselbe Umsetzung – keine eigenen Regeln, keine eigenen Listener mehr.
    mat, mcss = lies(MAT), lies("app/material/static/material.css")
    assert "const infoKnopf = S.info;" in mat and "mat-info" not in mat + mcss and "function infoZeigen" not in mat
    assert ".mat-nur-touch" not in mcss and ".mat-bt-flach" not in mcss
    # Jedes Modul holt sich S.info (Strömipedia, Riegenkarten, Freigaben) bzw. ruft es direkt (Leitstelle, Ankerplätze).
    for datei in (WIKI, RK):
        assert "const { esc, api, toast, dialog, fmtDate, info } = S;" in lies(datei), datei
    assert "const { esc, api, toast, confirm, info } = S;" in lies(FRG)
    print("App-weit bereitgestellt bestanden.")


def test_makro_wie_skript():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = make_app(tmp)
        with app.app_context():
            t = app.jinja_env.from_string('{% from "_makros.html" import info %}{% call info("probe", "Probe <x>") %}'
                                          'Text mit <a href="/x">Link</a>{% endcall %}')
            html = t.render()
    assert html.startswith('<span class="info"><button type="button" class="info-knopf" aria-label="Info zu Probe &lt;x&gt;" '
                           'aria-expanded="false"\n  aria-controls="info-probe" aria-describedby="info-probe">'), html
    assert html.endswith('<span class="info-text" role="tooltip" id="info-probe" hidden>Text mit <a href="/x">Link</a></span></span>'), html
    # Dasselbe Bild wie im Skript (Kreis, Punkt, Strich).
    svg = re.search(r"<svg.*?</svg>", html, re.S).group(0)
    common = lies("app/static/js/common.js")
    assert re.sub(r"\s+", " ", svg) == re.sub(r"\s+", " ", re.search(r"<svg.*?</svg>", common, re.S).group(0))
    print("Makro wie Skript bestanden.")


def test_alle_stellen():
    texte = {d: lies(d) for d in {s[1] for s in STELLEN}}
    assert len(STELLEN) == 55
    # Der alte Satz steht nicht mehr als Hilfezeile da (class="help"/"notice" mit dem Satz) – er ist ins „i“ gewandert;
    # mit „!“ davor: dieses Stück (Markup oder Satzfolge von früher) darf gar nicht mehr vorkommen.
    for nr, datei, neu, alt in STELLEN:
        assert neu in texte[datei], (nr, neu)
        if alt.startswith("!"):
            assert alt[1:] not in texte[datei], (nr, "Erklärsatz steht noch da", alt)
        else:
            assert alt in texte[datei], (nr, "Satz fehlt in der Info", alt)
            assert not re.search(r'class="(?:help|notice)[^"]*">[^<]{0,40}?' + re.escape(alt[:50]), texte[datei]), (nr, alt)
    print("Alle 55 Stellen bestanden.")


def test_sichtbar_geblieben():
    """Was nach der Regel sichtbar bleibt: Datenschutz, Folge der Aktion, Rechtsfolge, Sperrgrund."""
    mat, adm, karte = lies(MAT), lies(ADM), lies(MAP)
    # Datenschutz sichtbar, aber eine Zeile; die Einzelheiten im „i“ (Auftrag „letzte offene Punkte“, test_module_letzte_offene).
    assert '<span class="help">Ohne Haken nennt keine Ausgabe einen Prüfer.</span>' in mat
    assert "Diese Version wurde schon für Prüfungen benutzt und bleibt unverändert" in mat
    assert "Verknüpfen kann, wer in der Strömipedia mindestens Mitglied ist." in mat
    assert '`<p class="help">${esc(IMPORT_PERSONEN)}</p>`' in mat
    assert "Für „${esc(produktName(p))}“. Der Hinweis steht danach am Produkt" in mat          # Dialogeinleitung Rückruf
    assert '<p class="help">Alle angemeldeten Nutzer können es sehen.</p>' in karte
    assert '<p class="help">Verschickt eine Probemail über den eingerichteten Mailserver und zeigt, was er\n        dazu sagt.' in adm
    assert "Vorbelegt mit dem Sollwert – ändere nur, was abweicht." in mat                      # Anleitung in der Prüfung
    assert "Name und Kontaktdaten sind für andere angemeldete Nutzer sichtbar" in lies(PROFIL)
    print("Sichtbar geblieben bestanden.")


def test_marken_je_liste():
    rk, mat, html = lies(RK), lies(MAT), lies(ADMIN_HTML)
    # Riegenkarten: Schloss „eingefroren“ – title je Zeile bleibt, ein „i“ an „Teilnehmende“ und „Bewertung“.
    assert 'title="${esc(EINGEFROREN)}">🔒</span>' in rk
    assert 'const eingefrorenInfo = (tns) => (tns.some((t) => t.eingefroren) ? info("eingefroren", `🔒 eingefroren: ${esc(EINGEFROREN)}`) : "");' in rk
    assert '<h2>Teilnehmende${eingefrorenInfo(tns)}</h2>' in rk and '<h2>Bewertung${eingefrorenInfo(tns)}</h2>' in rk
    assert 'title="Lehrgangsleitung: darf' not in rk                                           # R1: das title je Zeile entfällt
    # Prüfung: „kritisch“ in den Befunden.
    assert ('<h2>Befunde${pr.punkte.some((x) => x.kritisch) ? infoKnopf("kritisch", "„kritisch“: Ein Mangel an diesem Prüfpunkt '
            'schließt „einsatzbereit“ aus.") : ""}</h2>') in mat
    assert 'title="Ein Mangel hier schließt „einsatzbereit“ aus">kritisch</span>' in mat
    # Leitstelle: Marken der Nutzerliste seit dem Auftrag „letzte offene Punkte“ (Nutzer: „i“ und Box redundant) in der
    # Box „Hilfe: Rechte je Modul“ statt im „i“ am Seitentitel; das title je Marke bleibt.
    assert 'data-titel-info="nutzer"' not in html and 'info("nutzerliste"' not in html
    html = html[html.index("<summary>Hilfe: Rechte je Modul</summary>"):html.index("</details>", html.index("Hilfe: Rechte je Modul"))]
    for marke in ("„Prüfer – Urkundennummer fehlt“", "„wirkt nicht – kein Zugang“", "„ohne Namen – kein Zugang“", "„n Freigaben“"):
        assert marke in html, marke
    assert 'el.classList.toggle("hidden", el.dataset.titelInfo !== name)' in lies(ADM)
    assert 'title="Ohne Stufe Mitglied oder Verwaltung in der Materialablage wirken Häkchen und Freigaben nicht."' in lies(ADM)
    print("Marken je Liste bestanden.")


def test_nebenbefunde():
    mat = lies(MAT)
    # „Mit dem Beginn reservierst du …“ steht ÜBER der Knopfzeile und beschreibt „Prüfung beginnen“.
    teil = mat[mat.index('<fieldset class="mat-arten"><legend>Art der Prüfung</legend>'):]
    assert teil.index('<p class="help" id="pa-folge">Mit dem Beginn reservierst du') < teil.index('<div class="btn-row mat-knoepfe">')
    assert '<button class="btn" data-act="beginnen" aria-describedby="pa-folge">Prüfung beginnen</button>' in teil
    # „Anlegen und nächsten“: keine Zeile am Telefon mehr unter den Knöpfen, das title bleibt.
    assert "„Anlegen und nächsten“: Produkt und Ordner" not in mat
    assert 'title="Produkt und Ordner bleiben für den nächsten Artikel stehen">Anlegen und nächsten</button>' in mat
    print("Nebenbefunde bestanden.")


def test_vorlagen_gerendert():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = make_app(tmp)
        c = app.test_client()
        assert c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
        leit = c.get("/leitstelle").get_data(as_text=True)
        assert 'Info zu Nutzerverwaltung' not in leit and 'info-nutzerliste' not in leit
        assert '<span data-titel-info="einstellungen" class="hidden">' in leit and 'id="info-einstellungen" hidden>' in leit
        assert leit.count('class="info-knopf"') == 1
        hilfe = leit[leit.index("Hilfe: Rechte je Modul"):leit.index("</details>", leit.index("Hilfe: Rechte je Modul"))]
        assert "Marken in der Spalte „Materialablage“:" in hilfe and "„Prüfer – Urkundennummer fehlt“" in hilfe
        profil = c.get("/profil").get_data(as_text=True)
        assert 'aria-label="Info zu Profilbild"' in profil and 'id="info-profilbild" hidden>Es steht neben deinem Namen' in profil
        wiki = c.get("/stroemipedia").get_data(as_text=True)
        # Seit dem Auftrag „letzte offene Punkte“: Import der obersten Ebene im Menü „⋯“ über dem Baum (title nennt ihn).
        assert 'id="btn-baum-mehr"' in wiki and 'title="Papierkorb, Seiten aus ZIP importieren">⋯</button>' in wiki
        # Am Finger sind die Einträge des „⋯“-Menüs im Seitenbaum (mit dem Import) 44 px hoch.
        css = lies("app/static/css/app.css")
        touch = css[css.index("/* Fingerbedienung (Punkt 12"):]
        assert ".tree-menu button { min-height: 44px; }" in touch[:touch.index("\n}\n")]
        # Ohne Wiki-Verwaltung kein Knopf „Importieren“ (der Server lehnt den Import ohnehin ab).
        r = c.post("/api/admin/users", json={"email": "mitglied-info@example.org", "name": "Mitglied Platzhalter",
                                             "password": "geheim123", "rechte": {"wiki": 1}})
        assert r.status_code in (200, 201), r.json
        m = app.test_client()
        assert m.post("/api/auth/login", json={"email": "mitglied-info@example.org", "password": "geheim123"}).status_code == 200
        mw = m.get("/stroemipedia").get_data(as_text=True)
        assert 'id="btn-baum-mehr"' in mw and 'title="Papierkorb">⋯</button>' in mw and "importieren" not in mw[mw.index('id="btn-baum-mehr"'):][:200]
    print("Vorlagen gerendert bestanden.")


if __name__ == "__main__":
    test_app_weit_bereitgestellt()
    test_makro_wie_skript()
    test_alle_stellen()
    test_sichtbar_geblieben()
    test_marken_je_liste()
    test_nebenbefunde()
    test_vorlagen_gerendert()
