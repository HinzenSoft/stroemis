"""Interaktive Einführung je Modul (Wunsch des Nutzers vom 28.10.2026, Entscheidungen vom 03.11.2026; Bauvorlage
planung/tutorial/entwurf.md, README „Einführungen (Übungen je Modul)“).

Freiwillig mit Angebot: Beim Betreten eines Moduls bietet die Seite eine kurze Übung an – Grundteil für alle mit
Modulzugang, dazu ein Zusatzteil je Rolle (TEILE). Geübt wird auf der gewohnten Seite mit dem Abfrageteil
„uebung=<teil>“: Der Server zeichnet dann nur die Hülle der Seite – ohne echte Daten, mit den Rechten des Teils –, und
im Browser beantwortet einfuehrung.js jede Anfrage der Seite aus dem Übungsbestand der Übungsdatei
(app/static/js/uebung/<modul>.js). Die Übung gilt nur, wenn ihr Teil für das Konto gilt (Nachtrag des Hauptagenten vom
03.11.2026): Ein Mitglied mit ?uebung=verwaltung bekommt die normale Seite – niemand sieht über die Übung die Oberfläche
einer Rolle, die er nicht hat, und die Übungsstufe ist nie höher als die echte.

Zweite Absicherung ist die Sperre (sperre, aus csrf_guard in app/__init__.py): Eine Übungsanfrage – Kopfzeile
„X-Uebung: 1“ oder ein Referer derselben Herkunft mit „uebung=“ im Abfrageteil – kommt an /api/ und /media/ nicht
durch (auch nicht lesend), ebenso wenig jede schreibende Methode und jede Datei. Ausnahmen: der Merker
(/api/einfuehrung/…), GET /api/me, Abmelden, /static/ und Seitenaufrufe – so führt die Kopfleiste aus der Übung hinaus.
Seiten gibt es in der Übung nur, wenn sie einen Übungszweig haben (UEBUNGSSEITEN); jede andere Seite unter einem
Modulpfad antwortet aus der Übung mit „In der Übung nicht verfügbar.“ (Sicherheitsprüfung vom 04.11.2026). Eine
Übungsseite lädt Bilder, Medien und Rahmen außerdem nur aus /static/ (csp_quellen) – auch ein Element ohne Referer
erreicht so /api/ und /media/ nicht.

Merker ohne Schemaschritt in mat_meta (wie Startseite und Willkommen der Materialablage; Schema bleibt 34):
  einfuehrung:<Konto>  {"<modul>:<teil>": {"zustand": "abgelehnt" | "unterbrochen" | "erledigt", "ablauf": n, "am": …}}
Kein Eintrag heißt: noch nie angeboten. „unterbrochen“ trägt den nächsten unfertigen Ablauf (gesetzt beim Start und nach
jedem fertigen Ablauf), fortgesetzt wird an seinem Anfang. Aus „erledigt“ wird nichts anderes mehr. Der Merker geht mit
dem Konto (konto_vergessen in api_admin.delete_user); ein Zurücksetzen der Materialablage auf dev leert mat_meta und
damit auch ihn. Kein Journal, keine Mail, keine Anzeige in der Leitstelle (Entscheidung 1)."""
import copy
import json
import os
import re
import time
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

from flask import Blueprint, abort, current_app, g, has_request_context, jsonify, render_template, request

from . import auth, db, module

bp = Blueprint("einfuehrung", __name__, url_prefix="/api/einfuehrung")
auth.eingabefehler_abfangen(bp)

SCHLUESSEL = "einfuehrung:{uid}"            # in mat_meta
ZUSTAENDE = ("abgelehnt", "unterbrochen", "erledigt")
GESPERRT = "In der Übung gesperrt – es wird nichts gespeichert."
NICHT_IN_UEBUNG = "In der Übung nicht verfügbar"

# Je Modul die Wörter für Angebot und Abschluss („Bestand“ heißt in der Strömipedia „Seiten“ usw.).
MODULE = {
    "material": {"zu": "zur Materialablage", "bleibt": "Dein echter Bestand bleibt unverändert.",
                 "ist": "Dein echter Bestand ist unverändert."},
    "wiki": {"zu": "zur Strömipedia", "bleibt": "Die echten Seiten bleiben unverändert.",
             "ist": "Die echten Seiten sind unverändert."},
    "karte": {"zu": "zu den Ankerplätzen", "bleibt": "Die echten Alben bleiben unverändert.",
              "ist": "Die echten Alben sind unverändert."},
    "pruefungen": {"zu": "zu den Riegenkarten", "bleibt": "Die echten Lehrgänge bleiben unverändert.",
                   "ist": "Die echten Lehrgänge sind unverändert."},
}

# Die Teile je Modul in der Reihenfolge des Angebots (Bauvorlage 1.6 und 3). titel: wie Angebot, Abschluss und Profil
# ihn nennen; minuten: geschätzte Dauer; stufe: die Stufe, die rechte[modul] in der Übung trägt (nie höher als die echte,
# weil der Teil nur gilt, wenn das Konto die Rolle hat); start: Adresse des ersten Ablaufs; ablaeufe: die Titel der
# Abläufe in ihrer Reihenfolge. Die Abläufe selbst (Startadresse je Ablauf, Schritte, Antworten) stehen in der
# Übungsdatei uebung/<modul>.js – tests/test_einfuehrung.py vergleicht Teile und Titel mit ihr. Ändert ein Modul-Teil
# seine Abläufe, gehören Titel und Startadresse des ersten Ablaufs hierher.
TEILE = {
    "material": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/materialablage",
         "ablaeufe": ("Zurechtfinden", "Artikel finden", "Mangel melden")},
        {"teil": "pruefer", "titel": "Prüfer", "minuten": 4, "stufe": auth.MITGLIED,
         "start": "/materialablage/artikel/900000012", "ablaeufe": ("Prüfung durchführen",)},
        {"teil": "materialwart", "titel": "Materialwart", "minuten": 4, "stufe": auth.MITGLIED,
         "start": "/materialablage/artikel/neu?ordner=900000002",
         "ablaeufe": ("Artikel anlegen", "Freigabe erteilen", "Prüfdurchgang")},
        {"teil": "verwaltung", "titel": "Material-Verwaltung", "minuten": 5, "stufe": auth.VERWALTUNG,
         "start": "/materialablage/katalog", "ablaeufe": ("Katalog und Prüfformular", "Prüfformulare zuweisen")},
    ),
    "wiki": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/stroemipedia/uebung-start",
         "ablaeufe": ("Lesen", "Suchen", "Kommentieren", "Bearbeiten")},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 3, "stufe": auth.REDAKTEUR,
         "start": "/stroemipedia/uebung-start", "ablaeufe": ("Seite anlegen", "Bearbeiten erlauben", "Verlauf")},
        {"teil": "verwaltung", "titel": "Verwaltung", "minuten": 2, "stufe": auth.VERWALTUNG,
         "start": "/stroemipedia/uebung-seite-lesen", "ablaeufe": ("Für alle Angemeldeten freigeben", "Papierkorb")},
    ),
    "karte": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 3, "stufe": auth.MITGLIED, "start": "/ankerplaetze",
         "ablaeufe": ("Karte und Album", "Suchen und filtern")},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 4, "stufe": auth.REDAKTEUR, "start": "/ankerplaetze",
         "ablaeufe": ("Album anlegen", "Bilder hochladen", "Bild beschreiben")},
    ),
    "pruefungen": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/riegenkarten",
         "ablaeufe": ("Lehrgang öffnen", "Voraussetzung abhaken", "Bewerten", "Mängel")},
        {"teil": "leitung", "titel": "Leitung", "minuten": 3, "stufe": auth.MITGLIED,
         "start": "/riegenkarten/930000001#teilnehmer", "ablaeufe": ("Teilnehmende eintragen", "Lehrgangsergebnis")},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 3, "stufe": auth.REDAKTEUR, "start": "/riegenkarten",
         "ablaeufe": ("Lehrgang anlegen",)},
    ),
}

# Was data-darf der Materialablage in der Übung trägt (rechte.darf_alles mit den Rechten des Teils statt der echten).
# uid ist die eigene Kennung, die Urkundennummer ein Platzhalter.
_DARF_AUS = {"lesen": True, "grund": True, "verwalten": False, "pruefen": False, "katalog": False, "alles": False,
             "gliederung_anlegen": False, "qualifiziert": False, "urkundennummer": "", "pruefer_haekchen": False,
             "unterschrift": False}
DARF_MATERIAL = {
    "grund": dict(_DARF_AUS),
    "pruefer": dict(_DARF_AUS, pruefen=True, qualifiziert=True, urkundennummer="ÜBUNG", pruefer_haekchen=True,
                    unterschrift=True),
    "materialwart": dict(_DARF_AUS, verwalten=True, unterschrift=True),
    "verwaltung": dict(_DARF_AUS, verwalten=True, katalog=True, alles=True, gliederung_anlegen=True, unterschrift=True),
}

# Die Seiten mit Übungszweig (Befund 2 der Sicherheitsprüfung vom 04.11.2026): Nur diese Endpunkte zeichnen mit
# ?uebung= die Hülle, bevor sie Daten anfassen. Jeder andere Seitenaufruf mit „uebung=“ – oder aus einer Übungsseite
# heraus unter einem Modulpfad (Meine PSA, Echtheit prüfen, Bericht, Bestandsimport, Druck der Riegenkarten …) – bekommt
# vor der Route die Fehlerseite „In der Übung nicht verfügbar“ (sperre); einfuehrung.js hält Links, Formulare und
# Seitenwechsel dorthin schon im Browser an (seiten_muster). Bekommt eine Seite einen Übungszweig, gehört sie hierher –
# tests/test_einfuehrung.py ruft jede Seitenregel der Module mit „uebung=“ auf.
UEBUNGSSEITEN = frozenset({
    # Materialablage: _seite (Übungszweig vor Bezug, Banner, Willkommen) bzw. eigener Zweig vor jedem Datenzugriff
    "material.dashboard", "material.pruefungen", "material.bestand_seite", "material.antraege_seite",
    "material.ordner_seite", "material.artikel_neu", "material.artikel_seite", "material.pruefung_neu",
    "material.pruefung_seite", "material.durchgang_seite", "material.durchgaenge_seite", "material.katalog_seite",
    "material.produkt_seite", "material.formular_seite", "material.formulare_seite", "material.meldungen_seite",
    "material.suche_seite",
    # Strömipedia (_wiki), Ankerplätze, Riegenkarten (_pruefungen_seite ohne Druck)
    "pages.wiki", "pages.wiki_page", "pages.karte", "pages.pruefungen", "pages.pruefungen_lehrgang",
    "pages.pruefungen_kataloge", "pages.pruefungen_katalog",
})


# --- Wer welchen Teil hat (Bauvorlage 1.6) ---------------------------------------------------------------------------

def _leitung(user):
    """Leitung in einem Lehrgang der Riegenkarten – oder Redakteur, der jeden eigenen Lehrgang leitet."""
    return auth.schreibt("pruefungen", user) or bool(db.query(
        "SELECT 1 FROM pruef_ausbilder WHERE user_id = ? AND ist_leitung = 1 LIMIT 1", (user["id"],), one=True))


def _praedikat(modul, teil, user):
    from .material.services import rechte as mat
    if modul == "material":
        if not mat.zugang(user):
            return False
        return {"grund": lambda: True, "pruefer": lambda: mat.qualifiziert(user),
                "materialwart": lambda: bool(mat.darf_alles(user)["verwalten"]),
                "verwaltung": lambda: mat.ist_material_verwaltung(user)}[teil]()
    if not auth.nutzt(modul, user):
        return False
    if teil == "grund":
        return True
    if teil == "redakteur":
        return auth.schreibt(modul, user)
    if teil == "verwaltung":
        return auth.verwaltet(modul, user)
    if teil == "leitung":
        return _leitung(user)
    return False


def teil_von(modul, teil):
    """Die Angaben eines Teils aus TEILE – oder None."""
    return next((t for t in TEILE.get(modul, ()) if t["teil"] == teil), None)


def gilt(modul, teil, user=None):
    """Gilt der Teil für das Konto (Prädikat aus der Bauvorlage 1.6)? Je Anfrage einmal gerechnet."""
    user = user or auth.current_user()
    if not user or not teil_von(modul, teil):
        return False
    speicher = g.setdefault("einfuehrung_gilt", {}) if has_request_context() else {}
    schluessel = (int(user["id"]), modul, teil)
    if schluessel not in speicher:
        speicher[schluessel] = bool(_praedikat(modul, teil, user))
    return speicher[schluessel]


def uebung(modul):
    """Der Teil, in dem diese Seite geübt wird – nur mit einem bekannten Teil des Moduls in ?uebung= UND wenn er für das
    Konto gilt (sonst wird der Parameter übergangen: normale Seite). Sonst None."""
    if not has_request_context():
        return None
    teil = request.args.get("uebung")
    if not teil or not teil_von(modul, teil):
        return None
    return teil if gilt(modul, teil) else None


def stufe(modul, teil):
    t = teil_von(modul, teil)
    return t["stufe"] if t else auth.KEIN_ZUGRIFF


def darf_material(teil, user=None):
    """data-darf der Materialablage in der Übung (DARF_MATERIAL, uid = eigene Kennung)."""
    user = user or auth.current_user()
    return dict(DARF_MATERIAL[teil], uid=user["id"] if user else None)


# --- Katalog in der Übung der Materialablage (Wunsch vom 04.11.2026) -----------------------------------------------------
# „Falls möglich nutze für die Materialablage-Übungen Produkte und Prüfbögen, die im Katalog sind. Natürlich ohne, dass
# sie mit den Echtdaten der Artikel interagieren.“ Eine Übungsseite der Materialablage trägt eine kleine, feste Auswahl
# echter Katalogprodukte samt ihrem geltenden Prüfformular (STROEMIS.einfuehrung.katalog, aus seite()) – kein neuer Weg
# unter /api/, die Sperre bleibt ganz. Die Übungsdatei (app/static/js/uebung/material.js) füllt damit ihre
# Übungsprodukte (deren Kennungen im Übungsbereich bleiben); Artikel, Ordner, Personen und Prüfungen bleiben Übung.
# Mitgegeben werden nur Katalogfelder: Hersteller, Modell, Beschreibung, Artikelnummer, Norm, Materialart, Kategoriepfad
# (Namen), Prüfintervall und Lebensdauer (mit Quelle), das Produktbild und die Namen der geltenden Herstellerdokumente;
# vom Formular Titel, Version, Quelle und Prüfpunkte. Nichts über Artikel, Ordner, Bestand, Personen, Journal, Prüfungen
# oder Meldungen. Die Produktbilder der Auswahl (Web- und Vorschaufassung) sind die einzige Ausnahme der Sperre unter
# /media/ – nur GET, nur genau diese Dateien (sperre, csp_quellen).
#
# Je Rolle der Übung: Muster für den Namen einer Kategorie im Pfad des Produkts (der Reihe nach – das erste Muster mit
# einem passenden Produkt gilt) und die Materialart (None: jede). Der Katalog hat (Stand 04.11.2026) keine Helme – dann
# nimmt die Rolle „helm“ (der neue Artikel im Teil „Materialwart“) einen Karabiner; sonst bleibt der Platzhalter.
KATALOG_ROLLEN = (
    ("gurt", (r"gurte?",), "textil"),
    ("seil", (r"seile?",), "textil"),
    ("helm", (r"helme?", r"karabiner"), None),
)
# Dateinamen der Produktbilder, die als Ausnahme in Sperre und CSP stehen dürfen (kein Leerzeichen, kein „;“).
_BILDNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}")


def _katalog_bild(p):
    """Web- und Vorschaufassung des Produktbilds als {"web", "vorschau"} – nur, wenn beide Dateien da sind (sonst lüde
    die Übung ein kaputtes Bild) und ihre Namen harmlos sind. Sonst None."""
    from .material.services import katalog
    if not _BILDNAME.fullmatch(p.get("image") or ""):
        return None
    out = {"web": katalog.bild_url(p["image"]), "vorschau": katalog.bild_url(p["image"], "thumb")}
    for art, url in (("web", out["web"]), ("thumb", out["vorschau"])):
        name = url.rsplit("/", 1)[1]
        if not _BILDNAME.fullmatch(name) or not os.path.isfile(os.path.join(katalog.medien_dir(), art, name)):
            return None
    return out


def _katalog_auswahl():
    """Je Rolle (KATALOG_ROLLEN) ein Produkt mit seinem geltenden Formular: nicht DEMO, ohne laufenden Rückruf,
    Kategorie und Materialart passend, mit geltendem Formular (katalog.formular_fuer_produkt – die eine Stelle, die das
    Formular eines Produkts bestimmt), das Prüfpunkte hat. DEMO nach der Regel des Katalogs wie im Export
    (katalog.produkt_ist_demo: auch über eine DEMO-Kategorie – Sicherheitsprüfung vom 04.11.2026, Befund 4). Das Formular
    zählt wie im Export unabhängig von seinem DEMO-Kennzeichen (Entscheidung vom 04.11.2026, Formular-Pool R1) – im Pool
    einer DEMO-Kategorie steht es ohnehin nur für DEMO-Produkte (Zuweisung nur im Teilbaum). Produkte mit Bild zuerst,
    dann die kleinste Kennung – dieselbe Auswahl für alle. {rolle: (Produktzeile, Formularzeile, Kategoriepfad, Bild)};
    fehlt eine Rolle, bleibt in der Übung ihr Platzhalter."""
    from .material.models import produkt_demo_sql
    from .material.services import katalog
    # Ohne ein aktives Formular gilt für kein Produkt eins – dann muss niemand die Produkte durchgehen.
    if not db.query("SELECT 1 FROM mat_form WHERE active = 1 LIMIT 1", one=True):
        return {}
    produkte = db.query(f"SELECT * FROM mat_product p WHERE NOT {produkt_demo_sql('p')} AND NOT EXISTS (SELECT 1 FROM "
                        "mat_recall r WHERE r.product_id = p.id AND r.closed_at IS NULL) ORDER BY p.id")
    pfade, bilder, out, vergeben = {}, {}, {}, set()

    def pfad(kid):
        if kid not in pfade:
            pfade[kid] = katalog.kategorie_pfad(kid)
        return pfade[kid]

    def bild(p):
        if p["id"] not in bilder:
            bilder[p["id"]] = _katalog_bild(p)
        return bilder[p["id"]]

    for rolle, muster, materialart in KATALOG_ROLLEN:
        for m in muster:
            passt = re.compile(rf"(?:{m})$", re.IGNORECASE)
            kandidaten = sorted((p for p in produkte if p["id"] not in vergeben
                                 and (materialart is None or p["material_kind"] == materialart)
                                 and any(passt.search(k["name"].strip()) for k in pfad(p["category_id"]))),
                                key=lambda p: (bild(p) is None, p["id"]))
            for p in kandidaten:
                f = katalog.formular_fuer_produkt(p["id"])
                if f and f["punkte_anzahl"]:
                    out[rolle] = (p, f, pfad(p["category_id"]), bild(p))
                    vergeben.add(p["id"])
                    break
            if rolle in out:
                break
    return out


# Die Auswahl geht je Produkt Kategoriepfad, Bild und Formular durch – bei einem großen Katalog ein Vielfaches einer
# normalen Seite, und das für jede Übungsseite und jedes ihrer Bilder. Darum prozessweit zwischengespeichert
# (Sicherheitsprüfung vom 04.11.2026, Befund 1): je App, mit dem Katalog-Stand und dem Tag als Schlüssel und höchstens
# KATALOG_FRIST Sekunden lang für das, was der Stand nicht sieht (Bilddateien). Der Stand ist seit Schritt 38 vor allem
# der Zähler mat_meta.katalog_stand: Trigger an jeder Tabelle, aus der die Auswahl stammt (models.KATALOG_STAND_TABELLEN),
# zählen ihn bei jeder Änderung hoch – auch bei zweien in derselben Sekunde (daran scheiterte der Schlüssel aus Zahl und
# letzter Änderung, der dahinter bleibt) und bei SQL von Hand; Lesen schreibt nichts. Gefahrlos: Die Auswahl trägt nur
# Katalogfelder, die jedes Konto mit Modulzugang ohnehin liest, und die Medienroute prüft jedes Bild weiter selbst.
KATALOG_FRIST = 60
_KATALOG_STAND = ("SELECT (SELECT IFNULL(MAX(wert), '') FROM mat_meta WHERE schluessel = 'katalog_stand') || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(updated_at), '') FROM mat_product) || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(updated_at), '') FROM mat_form) || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(updated_at), '') FROM mat_category) || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(id), 0) FROM mat_formular_zuweisung) || ';' || "
                  "(SELECT COUNT(*) || '|' || COUNT(closed_at) FROM mat_recall) || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(id), 0) FROM mat_product_document) || ';' || "
                  "(SELECT COUNT(*) || '|' || IFNULL(MAX(id), 0) FROM mat_checklist_item) AS stand")


def katalog_vergessen():
    """Den Zwischenspeicher der Auswahl dieser App leeren (Tests, die den Katalog mit SQL von Hand ändern)."""
    current_app.extensions.pop("einfuehrung_katalog", None)


def katalog_material():
    """Die Auswahl für die Übungsseite (STROEMIS.einfuehrung.katalog): {"produkte": {rolle: {…} | None},
    "formulare": [{…}]} – je Produkt nur Katalogfelder (siehe oben); „formular“ ist die Stelle in „formulare“ (ein
    Formular, das für zwei Produkte gilt, steht dort einmal), „kategorie“ im Formular die Stelle der Kategorie, deren
    Standard es ist, im Kategoriepfad des Produkts (None: dem Produkt zugewiesen), „heimat“ die Stelle der Kategorie, in
    deren Pool es steht. Je Anfrage einmal gelesen, gerechnet nur, wenn der Zwischenspeicher (siehe oben) nichts Gültiges
    hat."""
    if has_request_context() and "einfuehrung_katalog" in g:
        return g.einfuehrung_katalog
    from .material.services import heute
    schluessel = (db.query(_KATALOG_STAND, one=True)["stand"], heute().isoformat())
    gemerkt = current_app.extensions.get("einfuehrung_katalog")
    if gemerkt and gemerkt[0] == schluessel and time.monotonic() - gemerkt[1] < KATALOG_FRIST:
        out = copy.deepcopy(gemerkt[2])
    else:
        out = _katalog_rechnen()
        # Ein Tupel in einem Schritt – gleichzeitige Anfragen anderer Fäden sehen den alten oder den neuen Eintrag.
        current_app.extensions["einfuehrung_katalog"] = (schluessel, time.monotonic(), copy.deepcopy(out))
    if has_request_context():
        g.einfuehrung_katalog = out
    return out


def _katalog_rechnen():
    from .material.services import katalog
    from .material.services.interval import herstellerseite
    auswahl = _katalog_auswahl()
    formulare, stelle, produkte = [], {}, {}
    for rolle, _muster, _art in KATALOG_ROLLEN:
        if rolle not in auswahl:
            produkte[rolle] = None
            continue
        p, f, kpfad, bild = auswahl[rolle]
        if f["id"] not in stelle:
            stelle[f["id"]] = len(formulare)
            ids = [k["id"] for k in kpfad]
            von = (f["standard_von"] or {}).get("id")
            heimat = f["formular"]["heimat"]["id"]
            formulare.append({"titel": f["title"], "version": f["version"], "quelle": f["quelle"],
                              "kategorie": ids.index(von) if von in ids else None,
                              "heimat": ids.index(heimat) if heimat in ids else None,
                              "punkte": [{k: v for k, v in katalog.punkt_json(x).items() if k not in ("id", "position")}
                                         for x in katalog.punkte(f["id"])]})
        monate, quelle = herstellerseite(p)
        produkte[rolle] = {
            "hersteller": p["manufacturer"], "modell": p["model"], "beschreibung": p["description"],
            "artikelnummer": p["article_no"], "norm": p["norm"], "materialart": p["material_kind"],
            "kategorie": [k["name"] for k in kpfad], "intervall": {"monate": monate, "quelle": quelle or ""},
            "lebensdauer": {"jahre": p["lifetime_years"], "quelle": p["lifetime_source"]}, "bild": bild,
            "dokumente": [{"titel": d["title"], "art": d["kind"], "version": d["version"], "gueltig_ab": d["valid_from"],
                           "datei": bool(d["datei"]), "groesse": d["size"]}
                          for d in katalog.dokumente(p["id"]) if d["gilt"]],
            "formular": stelle[f["id"]]}
    return {"produkte": produkte, "formulare": formulare}


def katalog_bilder():
    """Die Adressen der Produktbilder der Auswahl (Web- und Vorschaufassung) – die Ausnahme in Sperre und CSP."""
    return {u for p in katalog_material()["produkte"].values() if p and p["bild"] for u in p["bild"].values()}


# --- Merker ----------------------------------------------------------------------------------------------------------

def merker(uid):
    """{"<modul>:<teil>": {zustand, ablauf, am}} des Kontos – leer ohne Eintrag oder bei unlesbarem Wert."""
    row = db.query("SELECT wert FROM mat_meta WHERE schluessel = ?", (SCHLUESSEL.format(uid=int(uid)),), one=True)
    try:
        wert = json.loads(row["wert"]) if row else {}
    except (ValueError, RecursionError):           # auch ein tief geschachtelter Wert (Befund 2 der Endprüfung)
        return {}
    return wert if isinstance(wert, dict) else {}


def konto_vergessen(uid):
    """Beim Löschen eines Kontos (api_admin.delete_user): der Merker geht mit."""
    db.execute("DELETE FROM mat_meta WHERE schluessel = ?", (SCHLUESSEL.format(uid=int(uid)),))


def adresse(modul, teil, ablauf=0):
    """Die Übungsadresse eines Teils: Startadresse des ersten Ablaufs mit uebung=<teil> (und ablauf=n beim Fortsetzen;
    die Übungsdatei kennt die Startadresse jedes Ablaufs und führt dorthin)."""
    t = teil_von(modul, teil)
    s = urlsplit(t["start"])
    abfrage = [(k, v) for k, werte in parse_qs(s.query, keep_blank_values=True).items() for v in werte
               if k not in ("uebung", "ablauf")]
    abfrage.append(("uebung", teil))
    if ablauf:
        abfrage.append(("ablauf", str(int(ablauf))))
    return urlunsplit(("", "", s.path, urlencode(abfrage), s.fragment))


def _eintrag(modul, t, m):
    """Ein Teil, wie Angebot, Abschluss und Profil ihn brauchen."""
    stand = m.get(f"{modul}:{t['teil']}") if isinstance(m.get(f"{modul}:{t['teil']}"), dict) else {}
    zustand = stand.get("zustand") if stand.get("zustand") in ZUSTAENDE else "offen"
    ablauf = stand.get("ablauf") if isinstance(stand.get("ablauf"), int) and not isinstance(stand.get("ablauf"), bool) \
        else 0
    ablauf = ablauf if 0 <= ablauf < len(t["ablaeufe"]) else 0
    return {"teil": t["teil"], "titel": t["titel"], "minuten": t["minuten"], "zustand": zustand, "ablauf": ablauf,
            "ablaeufe": len(t["ablaeufe"]), "ablauf_titel": t["ablaeufe"][ablauf], "am": stand.get("am") or "",
            "adresse": adresse(modul, t["teil"], ablauf if zustand == "unterbrochen" else 0)}


def teile(modul, user=None, m=None):
    """Die Teile des Moduls, die für das Konto gelten, mit ihrem Stand."""
    user = user or auth.current_user()
    if not user or modul not in TEILE:
        return []
    m = merker(user["id"]) if m is None else m
    return [_eintrag(modul, t, m) for t in TEILE[modul] if gilt(modul, t["teil"], user)]


def angebot(modul, user=None, m=None):
    """Was beim Betreten angeboten wird: Teile, die für das Konto gelten und offen oder unterbrochen sind (Bauvorlage
    2.6). „Nicht jetzt“ setzt sie auf abgelehnt – dann kommt nur noch ein Teil dazu, der durch eine neue Rolle gilt."""
    return [t for t in teile(modul, user, m) if t["zustand"] in ("offen", "unterbrochen")]


def seite(modul):
    """Für eine Seite des Moduls (vor dem Zeichnen, nicht für Fehler- und Druckseiten): setzt g.einfuehrung – base.html
    gibt es als STROEMIS.einfuehrung an einfuehrung.js, inject legt im Übungsmodus die Stufe des Teils auf rechte[modul].
    Liefert den Teil der Übung oder None."""
    user = auth.current_user()
    if not user:
        return None
    teil = uebung(modul)
    m = merker(user["id"])
    alle = teile(modul, user, m)
    daten = {"modul": modul, "name": module.NAME[modul], "start": module.PFAD[modul], **MODULE[modul],
             "uebung": teil, "teile": alle,
             # Im Übungsmodus kein Angebot; Seiten der Übung bieten nichts an.
             "angebot": [] if teil else [t for t in alle if t["zustand"] in ("offen", "unterbrochen")],
             "anleitung": ""}
    if teil:
        daten["stufe"] = stufe(modul, teil)
        daten["anleitung"] = _anleitung_uebersicht(modul, user)
        # Für einfuehrung.js und S.ziel: welche Adressen unter den Modulpfaden eine Übungsseite haben.
        daten["seiten"] = seiten_muster()
        daten["bereiche"] = list(_bereiche() + _alte_bereiche())
        if modul == "material":
            # Echte Katalogprodukte und ihre Prüfformulare für die Übungsprodukte (katalog_material).
            daten["katalog"] = katalog_material()
    g.einfuehrung = daten
    return teil


def _anleitung_uebersicht(modul, user):
    """Die Adresse der Anleitung des Moduls in der Strömipedia (Thema „uebersicht“) – nur, wenn das Konto sie lesen darf."""
    if modul == "material":
        from .material.services import anleitung as mat_anleitung
        return mat_anleitung.verweise(user).get("uebersicht") or ""
    from . import anleitung
    return anleitung.verweise(modul, user).get("uebersicht") or ""


def rechte_in_uebung(rechte):
    """Für den Kontextprozessor: im Übungsmodus trägt rechte[modul] die Stufe des Teils."""
    e = getattr(g, "einfuehrung", None) if has_request_context() else None
    if not e or not e.get("uebung"):
        return rechte
    return dict(rechte, **{e["modul"]: e["stufe"]})


# --- Profil „Einführungen“ (Bauvorlage 2.9) ----------------------------------------------------------------------------

def _datum(zeitpunkt):
    from datetime import datetime, timezone

    from .material.services import ZONE
    try:
        t = datetime.fromisoformat(zeitpunkt)
    except (TypeError, ValueError):
        return ""
    t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return t.astimezone(ZONE).strftime("%d.%m.%Y")


def profil(user=None):
    """Je Modul mit Übung für das Konto: Name und je geltendem Teil eine Zeile (Titel, Minuten, Stand, Knopf, Adresse).
    Leer, wenn das Konto kein Modul mit Übung hat – dann gibt es den Abschnitt nicht."""
    user = user or auth.current_user()
    if not user:
        return []
    m = merker(user["id"])
    out = []
    for modul in TEILE:
        zeilen = []
        for t in teile(modul, user, m):
            if t["zustand"] == "erledigt":
                datum = _datum(t["am"])
                stand, knopf = (f"erledigt am {datum}" if datum else "erledigt"), "Erneut ansehen"
            elif t["zustand"] == "unterbrochen":
                stand, knopf = f"unterbrochen bei „{t['ablauf_titel']}“", "Fortsetzen"
            else:
                stand, knopf = "noch nicht begonnen", "Starten"
            zeilen.append(dict(t, stand=stand, knopf=knopf))
        if zeilen:
            out.append({"modul": modul, "name": module.NAME[modul], "zeilen": zeilen})
    return out


# --- Sperre (Bauvorlage 2.4) -------------------------------------------------------------------------------------------

def _uebungsanfrage():
    """Kopfzeile X-Uebung: 1 oder ein Referer derselben Herkunft mit „uebung=“ im Abfrageteil (fängt, was keine
    Kopfzeile tragen kann: <img>, Beacon, Datei-Links, window.open; die Referrer-Policy schickt bei gleicher Herkunft die
    volle Adresse)."""
    return request.headers.get("X-Uebung") == "1" or _uebungs_referer() is not None


def _uebungs_referer():
    """Der Referer als urlsplit-Ergebnis, wenn er eine Übungsseite derselben Herkunft nennt – sonst None."""
    ref = request.headers.get("Referer") or ""
    if not ref:
        return None
    try:
        teile_ref = urlsplit(ref)
    except ValueError:
        return None
    if teile_ref.netloc.lower() != (request.host or "").lower():
        return None
    return teile_ref if "uebung" in parse_qs(teile_ref.query, keep_blank_values=True) else None


def _datei(pfad):
    """Eine Datei statt einer Seite – dieselbe Regel wie der Service Worker (app/static/js/sw.js): Endung im letzten
    Abschnitt oder …/pdf, …/sammelprotokoll."""
    endung = pfad.rsplit("/", 1)[-1].rpartition(".")
    return bool(endung[1] and re.fullmatch(r"[A-Za-z0-9]{1,8}", endung[2])) or pfad.endswith(("/pdf", "/sammelprotokoll"))


_FREI = ("/static/", "/sw.js", "/manifest.webmanifest", "/offline")


def _frei(pfad):
    """Was eine Übungsanfrage immer darf: der Merker, GET /api/me, Abmelden (ändert nur die Sitzung – Befund 1 der
    Sicherheitsprüfung vom 04.11.2026) und was zur App gehört (/static/, Worker, Manifest, Hinweisseite)."""
    return (pfad.startswith("/api/einfuehrung/") or pfad.startswith(_FREI) or pfad in _FREI
            or (pfad == "/api/me" and request.method in ("GET", "HEAD"))
            or (pfad == "/api/auth/logout" and request.method == "POST"))


def _bereiche():
    """Die Pfade der Module mit Übung (/materialablage, /stroemipedia, …)."""
    return tuple(module.PFAD[m] for m in TEILE)


def _alte_bereiche():
    """Ihre alten Pfade und die Schreibweisen mit Umlaut (module.ALT, module.UMLAUT) – sie leiten nur weiter. In der
    Übung hält einfuehrung.js Links und Seitenwechsel dorthin an (Hinweis 3 der Endprüfung). Kodiert wie im Browser
    (URL.pathname: „/str%C3%B6mipedia“)."""
    return tuple(quote(p) for m in TEILE for p in (module.ALT.get(m), module.UMLAUT.get(m)) if p)


def _modul_von(pfad):
    """Das Modul mit Übung, unter dessen Pfad die Adresse liegt – oder None."""
    return next((m for m in TEILE if pfad == module.PFAD[m] or pfad.startswith(module.PFAD[m] + "/")), None)


_PLATZHALTER = re.compile(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>")


def _muster(regel):
    """Die Regel als regulärer Ausdruck, den auch JavaScript versteht (Teile der Werkzeug-Umwandler: int → \\d+, sonst
    [^/]+ bzw. der Ausdruck des Umwandlers)."""
    teile, pos = [], 0
    for m in _PLATZHALTER.finditer(regel.rule):
        umwandler = current_app.url_map.converters.get(m.group(1) or "default")
        teile += [re.escape(regel.rule[pos:m.start()]), f"(?:{getattr(umwandler, 'regex', '[^/]+')})"]
        pos = m.end()
    teile.append(re.escape(regel.rule[pos:]))
    return "^" + "".join(teile) + "$"


def seiten_muster():
    """Die Adressen der Seiten mit Übungszweig (UEBUNGSSEITEN) als Ausdrücke für einfuehrung.js und S.ziel."""
    return sorted({_muster(r) for r in current_app.url_map.iter_rules() if r.endpoint in UEBUNGSSEITEN})


def kennung(ziel):
    """Der Teil, den eine Weiterleitung aus der Übung an ziel (eigener Pfad) weitergibt (Hinweis 3 der Endprüfung):
    ?uebung= der Anfrage oder – kommt sie ohne Kennung von einer Übungsseite desselben Moduls – „uebung=“ des Referers.
    Sonst None (dann führt die Weiterleitung wie bisher auf die echte Seite)."""
    if not has_request_context():
        return None
    if "uebung" in request.args:
        return request.args.get("uebung")
    ref = _uebungs_referer()
    modul = _modul_von(urlsplit(ziel).path)
    if not ref or not modul or _modul_von(ref.path) != modul:
        return None
    return (parse_qs(ref.query, keep_blank_values=True).get("uebung") or [""])[0]


def mit_kennung(ziel):
    """ziel einer Weiterleitung, aus der Übung mit der Kennung (kennung) – die Zielseite zeichnet dann ihren Übungszweig
    bzw. die Sperre die Fehlerseite, nie die echte Seite im selben Reiter. Ohne Übung unverändert."""
    teil = kennung(ziel)
    s = urlsplit(ziel)
    if teil is None or "uebung" in parse_qs(s.query, keep_blank_values=True):
        return ziel
    abfrage = s.query + ("&" if s.query else "") + urlencode({"uebung": teil})
    return urlunsplit(("", "", s.path, abfrage, s.fragment))


def _zurueck():
    """Wohin „Zurück zur Übung“ auf der Fehlerseite führt: die Übungsseite, von der die Anfrage kam (nur Pfad und Abfrage
    derselben Herkunft), sonst die Übungsadresse des Teils aus der Adresse bzw. die Startseite des Moduls."""
    ref = _uebungs_referer()
    if ref:
        # Auch ein Rückstrich vorn fällt weg – Browser lesen „/\“ wie „//“ (Hinweis 4 der Endprüfung).
        return urlunsplit(("", "", "/" + ref.path.lstrip("/\\"), ref.query, ""))
    modul = _modul_von(request.path)
    if not modul:
        return "/"
    teil = request.args.get("uebung")
    return adresse(modul, teil) if teil_von(modul, teil) else module.PFAD[modul]


def _nicht_in_uebung():
    """Die Fehlerseite „In der Übung nicht verfügbar“ (403) mit dem Weg zurück – vor der Route, ohne Datenzugriff.
    STROEMIS.einfuehrung trägt nur „gesperrt“: einfuehrung.js lässt Übungszustand und Übungsablage dann stehen, damit
    „Zurück zur Übung“ an derselben Stelle weitermacht."""
    g.einfuehrung = {"uebung": None, "gesperrt": True}
    return render_template("error.html", user=auth.current_user(), code=403, titel=NICHT_IN_UEBUNG,
                           message="Diese Seite gibt es in der Übung nicht.", zurueck=_zurueck()), 403


def _katalogbild(pfad):
    """Die eine Ausnahme unter /media/: ein Produktbild der Auswahl für die Übung (katalog_bilder) – nur mit GET, nur
    genau diese Dateien. Erst die billigen Bedingungen – Methode, Web- oder Vorschaubild mit harmlosem Namen, angemeldet
    mit Modulzugang (nur dann zeigt die Übungsseite die Auswahl) –, dann die Auswahl (Sicherheitsprüfung vom 04.11.2026,
    Befund 1: sonst rechnete jede Anfrage mit X-Uebung sie, auch ohne Anmeldung). Die Medienroute prüft danach wie immer
    Anmeldung und Modulzugang."""
    if request.method != "GET" or not pfad.startswith(("/media/material/web/", "/media/material/thumb/")):
        return False
    if not _BILDNAME.fullmatch(pfad.rsplit("/", 1)[1]):
        return False
    from .material.services.rechte import zugang
    return zugang(auth.current_user()) and pfad in katalog_bilder()


def sperre():
    """Erster Schritt von csrf_guard: Eine Übungsanfrage an /api/ oder /media/, mit schreibender Methode oder an eine
    Datei bekommt 403 mit GESPERRT (Schnittstelle als JSON, sonst die deutsche Fehlerseite). Erlaubt bleiben der Merker,
    GET /api/me, Abmelden, /static/ (und was zur App gehört: Worker, Manifest, Hinweisseite) und Seitenaufrufe.
    Seitenaufrufe mit „uebung=“ – und aus einer Übungsseite heraus unter einem Modulpfad – gehen nur an Seiten mit
    Übungszweig (UEBUNGSSEITEN), sonst die Fehlerseite „In der Übung nicht verfügbar“. Sonst None."""
    pfad = request.path
    if _frei(pfad):
        return None
    uebungsanfrage = _uebungsanfrage()
    if uebungsanfrage and _katalogbild(pfad):
        return None
    if uebungsanfrage and (pfad.startswith(("/api/", "/media/")) or request.method not in ("GET", "HEAD")
                           or _datei(pfad)):
        if pfad.startswith("/api/"):
            return jsonify(error=GESPERRT), 403
        abort(403, description=GESPERRT)
    if (request.method in ("GET", "HEAD") and not pfad.startswith(("/api/", "/media/"))
            and ("uebung" in request.args or (uebungsanfrage and _modul_von(pfad)))
            and request.endpoint not in UEBUNGSSEITEN):
        return _nicht_in_uebung()
    return None


def csp_quellen():
    """Für security_headers (app/__init__.py): Auf einer Übungsseite (Hinweis 1 der Sicherheitsprüfung vom 04.11.2026)
    lädt der Browser Bilder, Medien und Rahmen nur aus /static/ und verbindet sich nur mit den Ausnahmen der Sperre – so
    erreicht auch ein Element mit referrerpolicy="no-referrer" (das der Server nicht als Übung erkennen könnte) /api/ und
    /media/ nicht. Dazu (Hinweis 1 der Endprüfung) ein enges default-src (kein Prefetch an /api/ ohne Referer) und kein
    Worker außer dem Service Worker. In der Materialablage kommen in img-src die Produktbilder der Auswahl dazu („bilder“,
    katalog_material). {"bild": …, "bilder": …, "netz": …, "worker": …} – oder None für jede andere Seite (dann gilt
    'self')."""
    e = getattr(g, "einfuehrung", None) if has_request_context() else None
    host = request.host if has_request_context() else ""
    if not e or not e.get("uebung") or not re.fullmatch(r"[A-Za-z0-9.-]+(?::\d{1,5})?", host or ""):
        return None
    # Genau die Dateien, die auch die Sperre durchlässt (_katalogbild).
    bilder = sorted(u for p in ((e.get("katalog") or {}).get("produkte") or {}).values() if p and p.get("bild")
                    for u in p["bild"].values())
    return {"bild": f"{host}/static/", "bilder": " ".join(f"{host}{u}" for u in bilder),
            "netz": " ".join(f"{host}{p}" for p in ("/static/", "/api/einfuehrung/", "/api/me", "/api/auth/logout")),
            # Kein Worker außer dem Service Worker (ein Worker hätte die weite CSP seiner Datei und keinen Übungs-Referer)
            "worker": f"{host}/sw.js"}


# --- Schnittstelle: Merker -------------------------------------------------------------------------------------------

@bp.put("/<modul>/<teil>")
@auth.login_required
def merken(modul, teil):
    """Den Stand eines Teils merken: {zustand: abgelehnt | unterbrochen | erledigt, ablauf: n}. 404 für unbekannte Teile,
    403, wenn der Teil nicht für das Konto gilt (ohne Modulzugang nie), 400 bei falschem Zustand oder Ablauf. Aus
    „erledigt“ wird nichts anderes (Antwort trotzdem ok). Unter der Schreibsperre: Zwei gleichzeitige Aufrufe (zwei
    Teile, zwei Reiter) verlieren nichts."""
    t = teil_von(modul, teil)
    if not t:
        return jsonify(error="Diese Übung gibt es nicht."), 404
    user = auth.current_user()
    if not gilt(modul, teil, user):
        return jsonify(error="Diese Übung gibt es für dein Konto nicht."), 403
    d = auth.json_body()
    zustand, ablauf = d.get("zustand"), d.get("ablauf", 0)
    if zustand not in ZUSTAENDE:
        return jsonify(error="Unbekannter Zustand der Übung."), 400
    if not isinstance(ablauf, int) or isinstance(ablauf, bool) or not 0 <= ablauf < len(t["ablaeufe"]):
        return jsonify(error="Diesen Ablauf gibt es in der Übung nicht."), 400
    schluessel = SCHLUESSEL.format(uid=int(user["id"]))
    with db.transaction(sofort=True):
        alle = merker(user["id"])
        alt = alle.get(f"{modul}:{teil}")
        if not (isinstance(alt, dict) and alt.get("zustand") == "erledigt"):
            alle[f"{modul}:{teil}"] = {"zustand": zustand, "ablauf": ablauf, "am": db.now()}
            db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
                       "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, json.dumps(alle)))
    return jsonify(ok=True)
