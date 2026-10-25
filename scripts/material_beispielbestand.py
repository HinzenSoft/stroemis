"""Beispielbestand für das Modul Material – NUR für dev und Tests, nie für echte Prüfungen.

Ein realistischer Bestand einer großen Gliederung mit gut zwei Jahren Geschichte, gebaut allein aus dem vorhandenen
Katalog (Wunsch des Nutzers vom 25.10.2026): der „DEMO-Kreisverband Flussland“ mit Zentrallager (Regale, Reserve), fünf
Fahrzeugen mit Seilrucksäcken und Taschen als Ordner der Art „Set“ (auch ein Set im Set), drei Einsatzgruppen und
persönlichen Ordnern für bis zu 40 DEMO-Einsatzkräfte – dazu die kleine „DEMO-OG Nachbarstadt“, damit sich die Trennung
je Gliederung und die globale Suche (Seriennummer DEMO-NS-4711) ausprobieren lassen. Vorgabe 800 Artikel.

Eigenständiges Werkzeug außerhalb von app/, dazu die Datei der Petzl-Prüfpunkte daneben (beide zusammen per tar in den
Container reichen – README; fehlt die Datei, gibt es nur Platzhalter-Formulare) – das Docker-Abbild enthält scripts/
nicht. Es läuft nur mit ausdrücklichem Schalter:

    python scripts/material_beispielbestand.py --beispielbestand [--artikel N]

--artikel N: so viele Artikel zu Beginn und als geplante Nachkäufe (Vorgabe 800; Ersatz für Ausgesondertes kommt dazu).
Ohne Angabe landen die Daten wie bei run.py in ./data; für eine andere Datenbank vorher DATA_DIR setzen. Auf dem
dev-Server: README, Abschnitt „Beispielbestand (nur dev)“. Nur auf dev oder lokal: BASE_URL muss gesetzt sein (das
Skript belegt sie nicht vor) und in der Umgebung UND in der Anwendung (Verwaltung → Einstellungen) die Positivliste von
flask material dev-zuruecksetzen erfüllen (Host mit „dev.“ davor oder localhost/127.0.0.1, zuruecksetzen.adresse_frei);
dazu die dev-Kennung (STROEMIS_NAME endet auf „-dev“) – nur lokal (beide Adressen localhost/127.0.0.1) geht es ohne.
Sonst legt das Skript nichts an.

Der Katalog: Kategorien, Produkte, Dokumente, Bilder, Rückrufe und Meldungen werden nur gelesen. Einzige Ausnahme sind
DEMO-Formulare für echte Kategorien ohne wirksames aktives Prüfformular (formulare) – mit DEMO-Kennzeichen, aktiv; der
Katalog-Export lässt sie aus: nach den Petzl-Prüfberichten, wo scripts/beispielbestand_petzl_punkte.json die Kategorie
nach ihrem Namen kennt (Punkte wörtlich, mit Gruppe, Soll und kritisch; Fundstellen je Punkt in der Datei, die Quellen im
Bericht – das Formular hat kein Feld dafür), sonst Platzhalter (je ein Punkt Ja/Nein, Text, Zahl, bei Artikellänge
„Länge (m)“) an der obersten Kategorie ohne Formular. Grundlage sind die Produkte ohne DEMO-Kennzeichen außerhalb von DEMO-Kategorien und ohne Stückliste
(Sets nur als Ordnerart). Alles Fachliche (Prüfpunkte, Intervalle, Lebensdauern, Hersteller, Produkte) kommt aus dem
Katalog; erfunden sind nur Bestandsangaben, und die tragen „DEMO“: Ordner „DEMO-…“, Seriennummern „DEMO-…“, DEMO-Konten mit
@example.invalid, Bemerkungen, Gründe und Befunde „DEMO – nicht für echte Prüfungen“, Seillängen als Bestandswert. Ein
Wert, den nur eine echte Prüfung liefern könnte (Messwert, Datum, Foto), wird nicht erfunden: Der Punkt steht auf „nicht
zutreffend“ mit der DEMO-Bemerkung; ein Mangel trägt die DEMO-Bemerkung und ein DEMO-Platzhalterfoto.

Die Geschichte („volles Leben“): Die Uhr dieses Prozesses wird für den Lauf zurückgestellt (Uhr – services.datetime,
db.datetime, models.datetime; nur hier, nie in der App) und läuft Tag für Tag nach vorn, nie über gestern hinaus, so
dass Journal, Prüftage, Protokolle und Durchgänge ihr damaliges Datum tragen. Bekannte Grenze: Zeitstempel, die SQLite
selbst setzt (applied_at bestätigter Anträge, Trigger mit 'now'), tragen den Lauftag – sie werden nicht umgangen. Ab
gut zwei Jahren vor heute: Ersterfassung je Bereich kurz vor seiner ersten Jahresprüfung (die Eingangsprüfung geschieht
im Durchgang), jährliche Prüfdurchgänge je Bereich (abgeschlossen, mit Sammelprotokoll), dazwischen Prüfungen bei
kürzerem Intervall und außerplanmäßige, Mängel mit Sperre und späterer Prüfung nach Reparatur (nur an nicht kritischen
Punkten; ein kritischer führt zur Aussonderung), Aussonderungen (Mangel, Lebensdauer, Verlust) mit Nachkauf, Nachkäufe
über die Jahre, verloren gemeldete Artikel, Verschiebungen, Zuordnungen zu Personen (auch beendete: Einsatzkräfte
scheiden aus, ihre Ausrüstung geht über die Reserve an neue, sie selbst bekommen danach nichts mehr), Änderungsanträge
(bestätigt, abgelehnt, zurückgezogen, offen – jeder Zustand kommt vor). Heute:
ein offener Durchgang im Zentrallager (teils erledigt, einer in Prüfung beim externen Prüfer, einer ausgenommen); im
MTW 2 ist die Jahresprüfung ausgefallen (überfällig), die persönliche Ausrüstung ist bald fällig.

Was danach gilt (deshalb vorher den Katalog exportieren – README):
  - Jede benutzte Formularversion lässt sich nur noch über eine neue Version ändern; jedes Produkt mit Artikeln lässt
    sich nicht mehr löschen und seine Materialart nicht mehr ändern, seine Kategorie nicht mehr löschen.
  - Der Bestand lässt sich nicht wieder entfernen (Prüfnachweise bleiben). Zurück geht es nur über
    flask material dev-zuruecksetzen und den Katalog-Export.
  - Einmalig: Gibt es eine der Gliederungen schon, legt ein weiterer Lauf nichts an. Erst am Ende steht der Merker
    „beispielbestand_gross“ in mat_meta; ein abgebrochener Lauf hinterlässt einen Teilbestand, den ein weiterer Lauf als
    unvollständig meldet (Rückgabewert 1).

Alles läuft über die Dienste der App (bestand, pruefung, durchgang, zuordnung, antrag, unterschrift, freigaben) in
Transaktionen – je Vorgang eine; scheitert einer, steht er unter „Hinweise“ im Bericht. Im Journal steht als Akteur
„Beispielbestand“ bzw. das handelnde DEMO-Konto. Mails gehen keine hinaus (auch nicht ins Mailprotokoll): Die
Hintergrund-Versender der Dienste sind in diesem Prozess abgeschaltet. Die Konten legt das Skript direkt an (ohne Anmeldung
gibt es dafür keinen Dienst), mit Journaleintrag „rollen“ und nur mit Zugang zum Modul Material; gibt es ein passendes
DEMO-Konto mit derselben Adresse schon (aktiv, freigeschaltet, mit der Stufe der Rolle), nimmt es dieses unverändert
(Passwort, Name und Rollen bleiben) – sonst bricht es vor jedem Schreiben ab. Laufzeit: Jede Prüfung bekommt ihr
Protokoll (gut eine halbe Sekunde je PDF), nach jedem Vorgang eine kurze Pause für andere Schreiber – bei 800 Artikeln
rund eine halbe Stunde, unter Last länger.
"""
import heapq
import io
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Im Container liegt das Skript unter /tmp, die App unter /srv (PYTHONPATH) und die Daten unter /data (DATA_DIR aus dem
# Abbild) – dann gilt beides von dort, nicht von hier.
if os.path.isfile(os.path.join(REPO_ROOT, "app", "__init__.py")):
    sys.path.insert(0, REPO_ROOT)
    os.environ.setdefault("DATA_DIR", os.path.join(REPO_ROOT, "data"))
# BASE_URL belegt das Skript nicht vor (anders als run.py): Fehlt sie, bricht es ab (sperrgrund) – im Klon der
# Produktion zeigte <Klon>/data sonst auf die echte Datenbank (Sicherheitsprüfung vom 25.10.2026, Befund 3).
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("VIDEOPFLEGE", "0")

HINWEIS = "DEMO – nicht für echte Prüfungen"
AKTEUR = "Beispielbestand"
VORGABE_ARTIKEL = 800
HOECHSTENS_ARTIKEL = 5000
SAAT = 20261025                      # gleicher Katalog, gleicher Stichtag, gleicher Bestand – nachvollziehbar
POSTFACH = "example.invalid"
# Schlüssel in mat_meta – erst am Ende eines vollständigen Laufs gesetzt; eigener Name, damit der Merker des früheren
# kleinen Beispielbestands einen abgebrochenen Lauf nicht als „schon da“ erscheinen lässt.
MERKER = "beispielbestand_gross"
PAUSE = 0.05                         # Sekunden nach jedem Vorgang – andere Schreiber (dev, Anmeldung) kommen dazwischen
TAGE = 2 * 365 + 60                  # Beginn der Geschichte: gut zwei Jahre vor heute
FORMULAR_TITEL = "DEMO-Prüfformular (Platzhalter) – "
PETZL_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beispielbestand_petzl_punkte.json")
# Frühere Namen einer Kategorie mit Petzl-Vorlage: Der Katalog bis 24.10.2026 (lieferung-20261024) heißt „Bandmaterial“,
# was seither „Textilmaterial“ heißt.
PETZL_ALIAS = {"Bandmaterial": "Textilmaterial"}

# Die Gliederungen: Kürzel (Seriennummern), Name, Anteil am Bestand, Ordnerbaum.
GROSS, KLEIN = "FL", "NS"
GLIEDERUNGEN = [(GROSS, "DEMO-Kreisverband Flussland", 0.94), (KLEIN, "DEMO-OG Nachbarstadt", 0.06)]
# Ordnerbaum je Gliederung: (Schlüssel, Name, Ordnertyp, Oberordner). Kein Ordner bekommt ein eigenes Prüfintervall.
ORDNER = {
    GROSS: [
        ("lager", "DEMO-Zentrallager", "standort", None),
        ("regal_seile", "DEMO-Regal Seile", "sonstiges", "lager"),
        ("regal_hardware", "DEMO-Regal Hardware", "sonstiges", "lager"),
        ("regal_psa", "DEMO-Regal PSA", "sonstiges", "lager"),
        ("reserve", "DEMO-Reserve", "sonstiges", "lager"),
        ("fahrzeuge", "DEMO-Fahrzeuge", "sonstiges", None),
        ("gw1", "DEMO-GW-Wasserrettung 1", "fahrzeug", "fahrzeuge"),
        ("sr1", "DEMO-Seilrucksack 1", "set", "gw1"),
        ("fzt", "DEMO-Flaschenzugtasche", "set", "sr1"),                 # ein Set im Set
        ("sr2", "DEMO-Seilrucksack 2", "set", "gw1"),
        ("gw2", "DEMO-GW-Wasserrettung 2", "fahrzeug", "fahrzeuge"),
        ("sr3", "DEMO-Seilrucksack 3", "set", "gw2"),
        ("mtw1", "DEMO-MTW 1", "fahrzeug", "fahrzeuge"),
        ("mtw2", "DEMO-MTW 2", "fahrzeug", "fahrzeuge"),
        ("boot", "DEMO-Mehrzweckboot", "fahrzeug", "fahrzeuge"),
        ("rt", "DEMO-Rettungstasche Boot", "set", "boot"),
        ("gruppen", "DEMO-Einsatzgruppen", "sonstiges", None),
        ("gruppe1", "DEMO-Strömungsrettungsgruppe 1", "sonstiges", "gruppen"),
        ("gruppe2", "DEMO-Strömungsrettungsgruppe 2", "sonstiges", "gruppen"),
        ("gruppe3", "DEMO-Strömungsrettungsgruppe 3", "sonstiges", "gruppen"),
        ("persoenlich", "DEMO-Persönliche Ausrüstung", "sonstiges", None),
    ],
    KLEIN: [
        ("lager", "DEMO-Lager NS", "standort", None),
        ("mtw", "DEMO-MTW NS", "fahrzeug", None),
    ],
}
# Bereiche mit eigener Jahresprüfung: (Gliederung, Ordner, Tage seit der letzten Runde). Die Runden davor liegen je ein
# Jahr früher, solange sie nach dem Beginn liegen. Im MTW 2 liegt die letzte gut ein Jahr zurück – die Runde dieses Jahres
# ist ausgefallen, der Bereich seit gut einem Monat überfällig; die persönliche Ausrüstung ist bald fällig. Das
# Zentrallager prüft heute in einem offenen Durchgang (OFFENER_DURCHGANG).
BEREICHE = [
    (GROSS, "lager", 368), (GROSS, "gw1", 200), (GROSS, "gw2", 150), (GROSS, "mtw1", 110), (GROSS, "boot", 80),
    (GROSS, "mtw2", 400), (GROSS, "gruppen", 45), (GROSS, "persoenlich", 345), (KLEIN, "lager", 170),
    (KLEIN, "mtw", 230),
]
OFFENER_DURCHGANG = (GROSS, "lager", 12)          # eröffnet vor 12 Tagen, ein Drittel erledigt
EINSATZKRAEFTE = 40                               # höchstens; bei kleinem --artikel weniger (je 20 Artikel eine)
# Was die Einsatzkräfte sehen: die erste liest ihren persönlichen Ordner, die übrigen haben – wie die meisten, denen PSA
# zugeordnet ist (services/zuordnung.py) – keinen Modulzugang und sehen nach der Anmeldung nur „Meine PSA“.
OHNE_ZUGANG = "ohne Modulzugang – sieht „Meine PSA“"

# Artikeltypen nach Stichwörtern im Kategorienamen (typ_fuer: die unterste Kategorie zuerst, erst ohne Treffer ihre
# Oberkategorien) – in dieser Reihenfolge, denn „Seilrollen“ sind Rollen, „Abseilgeräte“ und „Abseilachten“ Abseilgeräte
# und „Seilklemmen“ Seilklemmen, keine Seile; Bandmaterial (Katalog bis 24.10.2026) und Textilmaterial sind Schlingen.
# Dazu ihr Gewicht im allgemeinen Bestand und die Ordner, in die sie kommen (Gewichte). Was zu keinem Typ passt, ist
# „sonstiges“. Typen ohne Produkt im Katalog fallen weg.
TYPEN = [
    ("rolle", ("rolle", "flaschenz"), 3),
    ("abseil", ("abseil", "achter", "sicherungsger"), 6),
    ("seilklemme", ("seilklemm",), 3),
    ("seil", ("seil",), 10),
    ("karabiner", ("karabiner", "verbindungsmittel"), 30),
    ("schlinge", ("schling", "band", "textil"), 14),
    ("platte", ("platte", "rigging"), 3),
    ("gurt", ("gurt",), 8),
    ("helm", ("helm",), 4),
    ("weste", ("weste", "schwimm", "auftrieb"), 4),
    ("sonstiges", (), 4),
]
_GRUPPEN = {"gruppe1": 1, "gruppe2": 1, "gruppe3": 1}
ZIELE = {
    "seil": dict(regal_seile=4, sr1=1, sr2=1, sr3=1, gw1=1, gw2=1, boot=1, **_GRUPPEN),
    "karabiner": dict(regal_hardware=4, sr1=2, sr2=2, sr3=2, fzt=2, rt=1, mtw1=1, **_GRUPPEN),
    "rolle": dict(fzt=3, regal_hardware=2, gw1=1, gw2=1),
    "seilklemme": dict(regal_hardware=2, sr1=1, sr2=1, sr3=1, fzt=1),
    "abseil": dict(regal_hardware=2, sr1=1, sr2=1, sr3=1, **_GRUPPEN),
    "schlinge": dict(regal_hardware=2, sr1=2, sr2=2, sr3=2, fzt=1, boot=1, **_GRUPPEN),
    "platte": dict(regal_hardware=2, sr1=1, sr2=1, sr3=1),
    "gurt": dict(regal_psa=4, reserve=3, mtw1=1, mtw2=1, boot=1),
    "helm": dict(regal_psa=4, reserve=3, mtw1=1, mtw2=1, boot=1),
    "weste": dict(regal_psa=4, reserve=3, mtw1=1, mtw2=1, boot=1),
    "sonstiges": dict(regal_hardware=2, reserve=2, gw1=1, gw2=1, mtw1=1, mtw2=1),
}
ZIELE_KLEIN = {"lager": 3, "mtw": 2}
# So viel passt in einen Rucksack oder eine Tasche – ist sie voll, kommt der Artikel in einen anderen passenden Ordner.
FASSUNG = {"sr1": 18, "sr2": 18, "sr3": 18, "fzt": 10, "rt": 12}
# Persönliche Ausrüstung je Einsatzkraft (nur Typen, die der Katalog hat) – sie ist von Anfang an da (kein Nachkauf ohne
# Vorgänger; Ersatz kommt nach einer Aussonderung).
KIT = [("gurt", 1), ("helm", 1), ("weste", 1), ("karabiner", 2), ("schlinge", 1), ("abseil", 1)]
LAENGEN = (20, 30, 40, 50, 60, 100)          # Bestandsangabe „Länge (m)“ für Seile – erfunden wie die Seriennummer
# Wahrscheinlichkeiten der Geschichte
NACHKAUF = 0.18                    # Anteil der Artikel, die erst im Lauf der Jahre dazukommen
MANGEL, AUSSONDERN = 0.03, 0.008   # je Prüfung: Mangel (instandsetzen, später Prüfung nach Reparatur) bzw. aussondern
EINSATZ = 0.03                     # je Artikel und Jahr eine außerplanmäßige Prüfung (nach einem Einsatz)
VERLUST, LEBENSENDE, VERSCHIEBEN, ANTRAG = 0.012, 0.05, 0.05, 0.02
GRUPPE_ZUGEORDNET = 0.3            # Anteil der Gruppenausrüstung mit Zuordnung zu einer Person
ANTRAG_TEXT = {"bestaetigt": "bestätigt", "abgelehnt": "abgelehnt", "zurueckgezogen": "zurückgezogen", "offen": "offen"}


class Abbruch(Exception):
    """Klartext an die Kommandozeile, dann Ende mit dem Rückgabewert code."""

    def __init__(self, text, code=1):
        super().__init__(text)
        self.code = code


def schalter(argv):
    """Zahl der Artikel – nur mit --beispielbestand. Ohne Schalter oder mit Unbekanntem: Abbruch mit Rückgabewert 2."""
    ja, n, rest = False, VORGABE_ARTIKEL, list(argv)
    while rest:
        a = rest.pop(0)
        if a == "--beispielbestand":
            ja = True
        elif a == "--artikel" or a.startswith("--artikel="):
            wert = a.split("=", 1)[1] if "=" in a else (rest.pop(0) if rest else "")
            if not wert.isdigit() or not 1 <= int(wert) <= HOECHSTENS_ARTIKEL:
                raise Abbruch(f"Abgebrochen: --artikel braucht eine Zahl von 1 bis {HOECHSTENS_ARTIKEL}.", 2)
            n = int(wert)
        else:
            raise Abbruch(f"Abgebrochen: unbekannte Angabe „{a}“.", 2)
    if not ja:
        raise Abbruch("Abgebrochen: Der Beispielbestand wird nur mit dem Schalter --beispielbestand angelegt.", 2)
    return n


def typ_fuer(pfad):
    """Der Artikeltyp zu einem Kategoriepfad (Namen von oben nach unten): nach dem Namen der untersten Kategorie, passt
    der zu keinem Typ, nach der nächsthöheren – nie per Teilstring über den ganzen Pfad (Ablaufprüfung vom 25.10.2026)."""
    for name in reversed([(n or "").lower() for n in pfad]):
        typ = next((t for t, worte, _ in TYPEN if any(w in name for w in worte)), None)
        if typ:
            return typ
    return "sonstiges"


def sperrgrund():
    """None, wenn dies die Entwicklung oder ein lokaler Lauf ist – sonst der Grund. Nötig ist beides: BASE_URL in der
    Umgebung (gesetzt, das Skript belegt sie nicht vor) und in der Anwendung erfüllt die Positivliste von flask material
    dev-zuruecksetzen, und dazu die dev-Kennung (STROEMIS_NAME endet auf „-dev“, wie bei dev-zuruecksetzen) – oder beide
    Adressen sind localhost/127.0.0.1."""
    from flask import current_app

    from app import einstellungen
    from app.material.services import erinnerung, zuruecksetzen
    einstellungen.anwenden()
    adressen = (("BASE_URL in der Umgebung", os.environ.get("BASE_URL")),
                ("BASE_URL der Anwendung", current_app.config.get("BASE_URL")))
    for herkunft, adresse in adressen:
        if not zuruecksetzen.adresse_frei(adresse):
            zeigt = f"ist „{adresse.strip()}“" if (adresse or "").strip() else "fehlt"
            return (f"{herkunft} {zeigt} – der Beispielbestand gehört nur auf dev (Host mit „dev.“ davor) oder "
                    "localhost/127.0.0.1.")
    lokal = all(zuruecksetzen.host(adresse) in zuruecksetzen.LOKAL for _, adresse in adressen)
    if not lokal and not erinnerung.dev_umgebung():
        name = (os.environ.get("STROEMIS_NAME") or "").strip()
        return (f"STROEMIS_NAME ist „{name or 'nicht gesetzt'}“ – der Beispielbestand gehört nur auf dev (dort endet er "
                "auf „-dev“, scripts/dev-einrichten.sh) oder mit BASE_URL localhost/127.0.0.1.")
    return None


def _unterbrochen(signum, _frame):
    """SIGHUP (abgerissene Verbindung) und SIGTERM wie Strg-C: Der Vorgang in Arbeit rollt samt seinen neuen
    Protokolldateien zurück (protokoll.dateien_sichern), und der Hinweis unten erscheint – soweit es die Ausgabe noch
    gibt."""
    raise KeyboardInterrupt(f"Signal {signum}")


def main(argv=None):
    try:
        n = schalter(sys.argv[1:] if argv is None else argv)
    except Abbruch as exc:
        print(__doc__)
        print(exc)
        sys.exit(exc.code)
    import signal

    from flask import g

    from app import create_app

    app = create_app()
    vorher = {sig: signal.signal(sig, _unterbrochen) for sig in (signal.SIGHUP, signal.SIGTERM)}
    uhr = Uhr()
    try:
        with app.app_context():
            g.mat_akteur = AKTEUR
            lauf = Beispielbestand(app, n, uhr)
            try:
                with uhr, still():
                    lauf.anlegen()
            except Abbruch as exc:
                print(exc)
                sys.exit(exc.code)
            except (Exception, KeyboardInterrupt) as exc:
                try:
                    print(("Unterbrochen. " if isinstance(exc, KeyboardInterrupt) else "Abgebrochen mit einem Fehler "
                           "(unten). ") + lauf.stand(), flush=True)
                except OSError:                                     # die Ausgabe gibt es nicht mehr
                    pass
                raise
    finally:
        for sig, alt in vorher.items():
            signal.signal(sig, alt)


# --- Die Uhr des Laufs und stille Versender -------------------------------------------------------------------------------

class Uhr:
    """Stellt für die Dauer des Laufs die Uhr dieses Prozesses um versatz zurück: datetime in services (heute, jetzt),
    in app.db (db.now – Zeitstempel im Journal und an den Zeilen) und in app.material.models. stellen(tag) setzt den
    Kalendertag (nie rückwärts, damit Zeitstempel und Prüftage in ihrer Reihenfolge bleiben, und nie über gestern hinaus –
    was heute geschieht, läuft mit der echten Uhr, echt()); die Uhrzeit läuft weiter. Beim Verlassen gilt wieder die echte
    Uhr."""

    def __init__(self):
        self.versatz = timedelta(0)
        self.gestellt = False
        self._alt = []

    def __enter__(self):
        from app import db as app_db
        from app.material import models, services
        uhr = self

        class Verstellt(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + uhr.versatz

        for modul in (services, app_db, models):
            self._alt.append((modul, modul.datetime))
            modul.datetime = Verstellt
        return self

    def __exit__(self, *_):
        for modul, alt in self._alt:
            modul.datetime = alt
        self._alt = []
        self.versatz, self.gestellt = timedelta(0), False

    def tag(self):
        from app.material.services import heute
        return heute()

    def stellen(self, tag):
        echt = datetime.now(self._zone()).date()
        neu = timedelta(days=(min(tag, echt - timedelta(days=1)) - echt).days)
        if not self.gestellt or neu > self.versatz:
            self.versatz, self.gestellt = neu, True

    def echt(self):
        """Zurück auf heute (für die Schritte von heute)."""
        self.versatz = timedelta(0)

    @staticmethod
    def _zone():
        from app.material.services import ZONE
        return ZONE


class still:
    """Die Hintergrund-Versender (Mails zu Anträgen, Mängeln, Meldungen) tun in diesem Prozess nichts – es geht nichts
    hinaus und nichts ins Mailprotokoll."""

    def __enter__(self):
        from app.material.services import antrag, mangel, meldung
        self._alt = [(m, m.HINTERGRUND) for m in (antrag, mangel, meldung)]
        for m, _ in self._alt:
            m.HINTERGRUND = lambda *a, **k: None
        return self

    def __exit__(self, *_):
        for m, alt in self._alt:
            m.HINTERGRUND = alt


# --- Platzhalter-Formulare --------------------------------------------------------------------------------------------

def _platzhalter_punkte(mit_laenge):
    """Die Prüfpunkte eines Platzhalter-Formulars: je ein Punkt der Arten Ja/Nein, Text und Zahl, bei Artikellänge dazu
    „Länge (m)“ – ohne Inhalt, nur zum Durchklicken. Pflicht ist nur der Ja/Nein-Punkt (Soll „ja“, nicht kritisch)."""
    punkte = [{"gruppe": "DEMO-Gruppe", "text": "DEMO Ja/Nein-Punkt (Platzhalter)", "art": "yesno", "soll": "ja"},
              {"gruppe": "DEMO-Gruppe", "text": "DEMO Text-Punkt (Platzhalter)", "art": "text", "pflicht": False},
              {"gruppe": "DEMO-Gruppe", "text": "DEMO Zahl-Punkt (Platzhalter)", "art": "number", "pflicht": False}]
    if mit_laenge:
        punkte.append({"gruppe": "DEMO-Gruppe", "text": "DEMO Länge (Platzhalter)", "art": "laenge", "pflicht": False})
    return punkte


def petzl_vorlagen(pfad=None):
    """Die Prüfpunkte nach den Petzl-Prüfberichten je Kategoriename aus scripts/beispielbestand_petzl_punkte.json (Kopie
    der Recherche vom 25.10.2026, je Punkt mit Fundstelle). Fehlt die Datei (etwa, weil nur dieses Skript in den
    Container gereicht wurde – README), gibt es nur Platzhalter: {} und der Grund."""
    pfad = pfad or PETZL_DATEI
    try:
        with open(pfad, encoding="utf-8") as fh:
            daten = json.load(fh)
    except (OSError, ValueError) as exc:
        return {}, f"{os.path.basename(pfad)} nicht lesbar ({exc.__class__.__name__}) – nur Platzhalter-Formulare"
    return {k: v for k, v in daten.items() if isinstance(v, dict) and v.get("punkte")}, None


def petzl_vorlage(vorlagen, name):
    """Die Petzl-Vorlage zu einem Kategorienamen – auch unter einem früheren Namen (PETZL_ALIAS) – oder None."""
    return vorlagen.get(name) or vorlagen.get(PETZL_ALIAS.get(name, ""))


def petzl_titel(kategorie, v):
    """„DEMO – Prüfformular nach Petzl-Prüfbericht (<Bezugsprodukt>) – <Kategorie>“, bei einer nächstliegenden Vorlage mit
    Zusatz; passt das nicht in die 160 Zeichen des Titels, ohne das Bezugsprodukt."""
    zusatz = " (nächstliegende Petzl-Vorlage)" if v.get("nächstliegend") else ""
    titel = f"DEMO – Prüfformular nach Petzl-Prüfbericht ({v['bezugsprodukt']}) – {kategorie}{zusatz}"
    return titel if len(titel) <= 160 else f"DEMO – Prüfformular nach Petzl-Prüfbericht – {kategorie}{zusatz}"


GRUPPE_MAX = 80                      # so lang darf die Gruppe eines Prüfpunkts sein (katalog.punkte_pruefen)


def petzl_gruppe(gruppe):
    """Die Gruppe eines Petzl-Punkts – zu lang für die App (drei Überschriften der Petzl-Berichte), fällt der Zusatz in
    Klammern am Ende weg („… Verbindungsöse (z. B. an der ASTRO-Reihe)“ → „… Verbindungsöse“); reicht das nicht,
    gekürzt mit „…“."""
    import re
    g = (gruppe or "").strip()
    if len(g) > GRUPPE_MAX:
        g = re.sub(r"\s*\([^()]*\)$", "", g)
    return g if len(g) <= GRUPPE_MAX else g[:GRUPPE_MAX - 1].rstrip() + "…"


def petzl_punkte(v):
    """Die Punkte wörtlich (berichtigte Fassung „text“) mit Gruppe, Art, Pflicht, Soll und kritisch – so, wie die App sie
    als Prüfpunkt kennt."""
    return [{"gruppe": petzl_gruppe(p.get("gruppe")), "text": p["text"], "art": p["art_app"],
             "pflicht": bool(p.get("pflicht")), "soll": p.get("soll") or "", "kritisch": bool(p.get("kritisch"))}
            for p in v["punkte"]]


def formulare(vorlagen):
    """Prüfformulare für echte Kategorien ohne wirksames aktives Formular – DEMO-gekennzeichnet und aktiv, der
    Katalog-Export lässt sie aus. Echte Formulare (aktiv wie inaktiv) und DEMO-Kategorien samt Teilbaum bleiben unberührt.
      1. Petzl: Eine echte Kategorie, deren Name (oder früherer Name, PETZL_ALIAS) in vorlagen steht, die selbst kein Formular hat und über keine
         Oberkategorie ein aktives echtes, bekommt das Formular nach dem Petzl-Prüfbericht.
      2. Platzhalter: von oben nach unten – eine echte Kategorie, die weder
         selbst noch über eine Oberkategorie ein aktives Formular hat, bekommt eins, so hoch wie möglich (die
         Unterkategorien erben es; ein Formular an einer Unterkategorie geht ihm vor). „Länge (m)“ kommt dazu, wenn eine
         Kategorie des Teilbaums eine Artikellänge vorsieht. Eine Kategorie mit nur einem inaktiven echten Formular
         bekommt keins (aktiv verdrängte das DEMO-Formular es im Export); ihre Unterkategorien bekommen eigene.
    Ein zweiter Lauf legt nichts doppelt an. Liefert (petzl, platzhalter, ohne) – je Kategorienamen."""
    from app import db
    from app.material.services import katalog
    kats = {k["id"]: k for k in db.query("SELECT id, parent_id, name, demo FROM mat_category ORDER BY position, name, id")}
    kinder = {}
    for k in kats.values():
        kinder.setdefault(k["parent_id"], []).append(k)
    formulare_an = {}
    for f in db.query("SELECT category_id, active, demo FROM mat_form WHERE category_id IS NOT NULL"):
        formulare_an.setdefault(f["category_id"], []).append(f)
    raus, stapel = set(), [k["id"] for k in kats.values() if k["demo"]]
    while stapel:
        x = stapel.pop()
        if x not in raus:
            raus.add(x)
            stapel += [c["id"] for c in kinder.get(x, [])]

    def anlegen(kid, titel, punkte):
        fid = katalog.formular_anlegen({"kategorie_id": kid, "titel": titel, "punkte": punkte}, demo=True)
        katalog.formular_aktivieren(fid)
        formulare_an[kid] = [{"active": 1, "demo": 1}]

    petzl = []
    for k in kats.values():
        v = petzl_vorlage(vorlagen, k["name"])
        if k["id"] in raus or not v or formulare_an.get(k["id"]):
            continue
        oben = [x["id"] for x in katalog.kategorie_pfad(k["id"])][:-1]
        if any(f["active"] and not f["demo"] for o in oben for f in formulare_an.get(o, [])):
            continue
        anlegen(k["id"], petzl_titel(k["name"], v), petzl_punkte(v))
        petzl.append(k["name"])
    laenge = katalog.laenge_kategorien()
    platzhalter, ohne = [], []

    def abdecken(k, geerbt):
        if k["id"] in raus:
            return
        eigene = formulare_an.get(k["id"], [])
        if not geerbt and not eigene:
            anlegen(k["id"], FORMULAR_TITEL + k["name"],
                    _platzhalter_punkte(bool(katalog._unterkategorien(k["id"]) & laenge)))
            platzhalter.append(k["name"])
        abgedeckt = geerbt or not eigene or any(f["active"] or f["demo"] for f in eigene)
        if not abgedeckt:
            ohne.append(k["name"])
        for kind in kinder.get(k["id"], []):
            abdecken(kind, abgedeckt)

    for k in kinder.get(None, []):
        abdecken(k, False)
    return petzl, platzhalter, ohne


# --- Bilder: DEMO-Unterschrift und DEMO-Mangelfoto -----------------------------------------------------------------------

def unterschrift_uri(saat=0):
    """Eine gezeichnete Platzhalter-Unterschrift mit „DEMO“ als data:-URL, wie sie das Signatur-Pad liefert; saat
    variiert den Schwung je Person."""
    import base64
    import math

    from PIL import Image, ImageDraw

    from app.material.services import unterschrift
    bild = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    zeichnen = ImageDraw.Draw(bild)
    welle = 18.0 + saat % 9
    punkte = [(30 + x, 110 + 35 * math.sin(x / welle) * math.exp(-x / 500.0)) for x in range(0, 540, 4)]
    zeichnen.line(punkte, fill=(20, 40, 110, 255), width=5, joint="curve")
    zeichnen.text((40, 150), "DEMO – keine echte Unterschrift", fill=(20, 40, 110, 255))
    puffer = io.BytesIO()
    bild.save(puffer, "PNG")
    return unterschrift.VORSATZ + base64.b64encode(puffer.getvalue()).decode()


def mangelfoto_png():
    """Platzhalter für das Pflichtfoto eines Mangels: grau, durchgestrichen, mit „DEMO“ – sichtbar kein echtes Foto."""
    from PIL import Image, ImageDraw
    bild = Image.new("RGB", (640, 480), (190, 190, 190))
    zeichnen = ImageDraw.Draw(bild)
    zeichnen.rectangle((20, 20, 619, 459), outline=(200, 30, 30), width=8)
    zeichnen.line((20, 20, 619, 459), fill=(200, 30, 30), width=6)
    zeichnen.line((20, 459, 619, 20), fill=(200, 30, 30), width=6)
    zeichnen.rectangle((40, 205, 600, 255), fill=(255, 255, 255))
    zeichnen.text((60, 222), "DEMO-Platzhalterfoto – kein echter Mangel", fill=(0, 0, 0))
    puffer = io.BytesIO()
    bild.save(puffer, "PNG")
    return puffer.getvalue()


# --- Der Lauf ------------------------------------------------------------------------------------------------------------

class Beispielbestand:
    def __init__(self, app, n, uhr):
        from app.material.services import heute
        from app.material.services import status as st
        self.app, self.n, self.uhr = app, n, uhr
        self.h = heute()                    # Kalendertag in Deutschland, wie überall im Modul
        self.beginn = self.h - timedelta(days=TAGE)
        self.schwelle = st.schwelle_tage()
        self.rnd = random.Random(SAAT)
        self.gl = {}                        # Kürzel → {kurz, name, id, ordner{schlüssel: id}}
        self.konto = {}                     # Rolle → {id, mail, name}
        self.passwoerter = []               # (Mail, Name, Passwort oder None, Hinweis)
        self.hinweise = []
        self.abweichend = []                # vorhandene DEMO-Konten, die anders eingestellt sind als ihre Rolle
        self.zahl = {k: 0 for k in ("pruefungen", "runden", "nachkauf", "verschoben", "zugeordnet", "geloest",
                                    "ausgeschieden", "eintritt", "antraege", "aussonderungen", "verloren")}
        self.antraege = {}
        self.fertig_gesetzt = False
        self.artikel = []                   # Pläne aller Artikel (auch Nachkäufe)
        self.personen = []                  # Rollen der Einsatzkräfte, die zu Beginn da sind
        self.ausgeschieden = {}             # Rolle → Austrittstag
        self.neue_personen = []             # die später eintreten
        self._ereignisse, self._nr = [], 0
        self._foto = self._signatur = None
        self._start = time.monotonic()
        self._formulare = ([], [], [])
        self._vorlagen = {}

    # --- Vorprüfungen ---

    @staticmethod
    def namen():
        return [name for _, name, _ in GLIEDERUNGEN]

    def stand(self):
        """Was nach einem Abbruch da ist – für den Hinweis in main."""
        if self.fertig_gesetzt:
            return ("Der Beispielbestand ist vollständig angelegt, nur der Bericht fehlt – die Passwörter der DEMO-Konten "
                    "setzt die Nutzerverwaltung neu.")
        if not self.gl:
            return "Nichts angelegt – ein neuer Lauf beginnt von vorn."
        return ("Was bis dahin fertig war, bleibt – jeder Vorgang ganz oder gar nicht. Der Beispielbestand ist damit "
                "unvollständig, und kein weiterer Lauf ergänzt ihn: Neu geht es nur mit einer zurückgesetzten "
                "dev-Datenbank und dem Katalog-Export (README, „Beispielbestand (nur dev)“).")

    @staticmethod
    def fertig():
        """Hat ein Lauf den Beispielbestand vollständig angelegt (Merker in mat_meta)?"""
        from app import db
        return bool(db.query("SELECT 1 FROM mat_meta WHERE schluessel = ?", (MERKER,), one=True))

    def schon_da(self):
        from app import db
        return [r["name"] for r in db.query(
            f"SELECT name FROM mat_folder WHERE parent_id IS NULL AND demo = 1 AND name IN "
            f"({','.join('?' * len(GLIEDERUNGEN))}) ORDER BY id", self.namen())]

    def produkte(self):
        """Die echten Produkte: ohne DEMO-Kennzeichen, nicht in einer DEMO-Kategorie (wie beim Katalog-Export), ohne
        Stückliste und mit Prüfintervall – je mit Typ, Intervall, Lebensdauer (nur textil), Länge und aktivem Formular.
        Liefert (verwendbar, ausgelassen mit Grund)."""
        from app import db
        from app.material.services import katalog, katalog_export
        from app.material.services.interval import herstellerseite
        raus = katalog_export._ausgeschlossen(db.query("SELECT id, parent_id, demo FROM mat_category"))
        gut, ausgelassen = [], []
        for p in db.query("SELECT * FROM mat_product WHERE demo = 0 ORDER BY manufacturer COLLATE NOCASE, "
                          "model COLLATE NOCASE, id"):
            name = f"{p['manufacturer']} {p['model']}".strip()
            if p["category_id"] in raus:
                ausgelassen.append(f"{name} (in einer DEMO-Kategorie)")
                continue
            if p["is_set"]:
                ausgelassen.append(f"{name} (Set mit Stückliste)")
                continue
            monate = herstellerseite(p)[0]
            if not monate:
                ausgelassen.append(f"{name} (kein Prüfintervall im Katalog)")
                continue
            typ = typ_fuer([k["name"] for k in katalog.kategorie_pfad(p["category_id"])])
            f = katalog.formular_fuer_produkt(p["id"])
            gut.append({"id": p["id"], "name": name, "monate": monate, "typ": typ,
                        "lebensdauer": p["lifetime_years"] if p["material_kind"] == "textil" else None,
                        "textil": p["material_kind"] == "textil", "laenge": katalog.laenge_wirksam(p["category_id"]),
                        "formular": bool(f)})
        return gut, ausgelassen

    # --- Ablauf ---

    def anlegen(self):
        from app import db
        print(f"Datenbank: {self.app.config['DB_PATH']} · Adresse: {self.app.config['BASE_URL']} · Stichtag: "
              f"{self.h.strftime('%d.%m.%Y')} · Geschichte ab {self.beginn.strftime('%d.%m.%Y')}")
        grund = sperrgrund()
        if grund:
            raise Abbruch(f"Abgebrochen: {grund} Nichts angelegt.")
        da = self.schon_da()
        if da and not self.fertig():
            raise Abbruch(f"Abgebrochen: Der Beispielbestand ist unvollständig ({', '.join(da)}) – ein früherer Lauf "
                          "wurde abgebrochen. Ergänzen lässt er sich nicht; neu geht es nur mit einer zurückgesetzten "
                          "dev-Datenbank und dem Katalog-Export (README, „Beispielbestand (nur dev)“). Nichts angelegt.")
        if da:
            print(f"Beispielbestand ist schon da ({', '.join(da)}) – nichts angelegt. Er lässt sich nicht entfernen; "
                  "neu anlegen geht nur mit einer zurückgesetzten dev-Datenbank.")
            return
        produkte, ausgelassen = self.produkte()
        if not produkte:
            raise Abbruch("Abgebrochen: Im Katalog gibt es keine echten Produkte (ohne DEMO-Kennzeichen, ohne Stückliste, "
                          "mit Prüfintervall) – der Beispielbestand nimmt nur Produkte aus dem vorhandenen Katalog. Erst "
                          "den Katalog importieren." + (f" Nicht verwendbar: {'; '.join(ausgelassen)}." if ausgelassen
                                                        else ""))
        konten = self._konten_roh()
        unpassend = self.konten_pruefen(konten)
        if unpassend:
            raise Abbruch("Abgebrochen: Diese Adressen gehören schon Konten, die der Beispielbestand nicht übernehmen kann "
                          "(er ändert vorhandene Konten nicht) – " + "; ".join(unpassend) + ". Nichts angelegt. Eine offene "
                          "Kontoanfrage unter Verwaltung → Konten ablehnen; ein vorhandenes DEMO-Konto dort selbst "
                          "freischalten oder passend einstellen.")
        self.uhr.stellen(self.beginn)
        for kurz, name, _ in GLIEDERUNGEN:
            self.gliederung_anlegen(kurz, name)
        for k in konten:
            self.konto[k["rolle"]] = self.konto_anlegen(k)
        self.freigaben()
        print(f"Gliederungen: {', '.join(self.namen())} – mit Ordnerbaum, {len(konten)} Konten und Freigaben.")
        self._vorlagen, fehlt = petzl_vorlagen()
        if fehlt:
            self.hinweise.append(fehlt)
        self._formulare = formulare(self._vorlagen)
        petzl, platzhalter, _ = self._formulare
        if petzl or platzhalter:
            print(f"Formulare (DEMO, aktiv): {len(petzl)} nach Petzl-Prüfbericht ({', '.join(petzl)}), "
                  f"{len(platzhalter)} Platzhalter ({', '.join(platzhalter[:8])}{' …' if len(platzhalter) > 8 else ''}).")
            produkte, ausgelassen = self.produkte()
        self.planen(produkte)
        print(f"Artikel: {len(self.artikel)} geplant über {len({a['produkt']['id'] for a in self.artikel})} Produkte – "
              "spiele die Geschichte ab (jede Prüfung bekommt ihr Protokoll) …", flush=True)
        self.abspielen()
        self.heute_schritte()
        db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET "
                   "wert = excluded.wert", (MERKER, f"fertig {self.h.isoformat()}"))
        self.fertig_gesetzt = True
        self.bericht(produkte, ausgelassen)

    def _dauer(self):
        s = int(time.monotonic() - self._start)
        return f"{s // 60}:{s % 60:02d} min"

    # --- Gliederungen, Ordner und Konten ---

    def gliederung_anlegen(self, kurz, name):
        from app import db
        from app.material.services import bestand
        gl = {"kurz": kurz, "name": name, "ordner": {}}
        with db.transaction(sofort=True):
            gl["id"] = bestand.ordner_anlegen({"name": name, "kind": "gliederung", "description":
                                               f"{HINWEIS}. Beispielbestand aus dem Katalog "
                                               "(scripts/material_beispielbestand.py)."}, demo=True)
            for schluessel, oname, art, oben in ORDNER[kurz]:
                gl["ordner"][schluessel] = bestand.ordner_anlegen(
                    {"name": oname, "kind": art, "parent_id": gl["ordner"][oben] if oben else gl["id"]}, demo=True)
        self.gl[kurz] = gl

    def _personen_zahl(self):
        return max(1, min(EINSATZKRAEFTE, self.n // 20))

    def _konten_roh(self):
        """Die DEMO-Konten mit den bekannten Postfächern: Materialwart je Gliederung, zwei Prüfer und ein Prüfer der
        Nachbarstadt (dauerhaft), ein externer Prüfer (befristet im Zentrallager), ein Mitglied (lesen), die
        DEMO-Material-Verwaltung (Stufe Verwaltung) und die Einsatzkräfte – die ersten von Beginn an, einige treten später
        ein (sie übernehmen die Ausrüstung Ausgeschiedener)."""
        konten = [
            {"rolle": "wart", "mail": f"demo-wart-a@{POSTFACH}", "name": "DEMO-Materialwart Flussland", "stufe": 1},
            {"rolle": "wart_ns", "mail": f"demo-wart-b@{POSTFACH}", "name": "DEMO-Materialwart Nachbarstadt", "stufe": 1},
            {"rolle": "pruefer", "mail": f"demo-pruefer@{POSTFACH}", "name": "DEMO-Prüfer", "stufe": 1,
             "urkunde": "DEMO-1012"},
            {"rolle": "pruefer2", "mail": f"demo-pruefer-2@{POSTFACH}", "name": "DEMO-Prüferin 2", "stufe": 1,
             "urkunde": "DEMO-1013"},
            {"rolle": "pruefer_ns", "mail": f"demo-pruefer-ns@{POSTFACH}", "name": "DEMO-Prüfer Nachbarstadt",
             "stufe": 1, "urkunde": "DEMO-1014"},
            {"rolle": "extern", "mail": f"demo-extern@{POSTFACH}", "name": "DEMO-Prüfer extern", "stufe": 1,
             "urkunde": "DEMO-2024"},
            {"rolle": "mitglied", "mail": f"demo-mitglied@{POSTFACH}", "name": "DEMO-Mitglied", "stufe": 1},
            {"rolle": "mv", "mail": f"demo-mv@{POSTFACH}", "name": "DEMO-Material-Verwaltung", "stufe": 2},
        ]
        p = self._personen_zahl()
        neu = max(1, p // 12)
        for k in range(1, p + neu + 1):
            konten.append({"rolle": f"person{k}", "mail": f"demo-einsatzkraft-{k:02d}@{POSTFACH}",
                           "name": f"DEMO-Einsatzkraft {k:02d}", "stufe": 1 if k == 1 else 0, "person": True,
                           "sicht": "liest ihren persönlichen Ordner" if k == 1 else OHNE_ZUGANG})
        self.personen = [f"person{k}" for k in range(1, p + 1)]
        self.neue_personen = [f"person{k}" for k in range(p + 1, p + neu + 1)]
        return konten

    @staticmethod
    def konten_pruefen(konten):
        """Vor jedem Schreiben: Gibt es zu einer Adresse schon ein Konto, übernimmt der Lauf es nur, wenn es „DEMO-…“
        heißt, aktiv und freigeschaltet ist (keine offene Kontoanfrage – die kann jeder über die Registrierung stellen) und
        schon hat, was die Rolle braucht (Stufe im Modul Material, bei Prüfern Häkchen und gültige Urkundennummer). Der
        Lauf stuft kein Konto hoch und ändert keine Rolle (Sicherheitsprüfung vom 25.10.2026, Befund 2). Liefert je
        unpassendem Konto „Adresse (Grund)“."""
        from app import db
        from app.material.services import rechte
        vorhanden = {r["email"]: r for r in db.query(
            f"SELECT * FROM users WHERE email IN ({','.join('?' * len(konten))})", [k["mail"] for k in konten])}
        unpassend = []
        for k in konten:
            u = vorhanden.get(k["mail"])
            if not u:
                continue
            if not (u["name"] or "").startswith("DEMO"):
                grund = "heißt nicht „DEMO-…“"
            elif (u.get("status") or "active") == "pending":
                grund = "offene Kontoanfrage"
            elif not u["active"] or (u.get("status") or "active") != "active":
                grund = "deaktiviert"
            elif (u["recht_material"] or 0) < k["stufe"]:
                grund = f"Stufe im Modul Material {u['recht_material'] or 0}, gebraucht {k['stufe']}"
            elif k.get("urkunde") and not rechte.ist_pruefer(u):
                grund = "kein Prüfer mit gültiger Urkundennummer"
            else:
                continue
            unpassend.append(f"{k['mail']} ({grund})")
        return unpassend

    def konto_anlegen(self, k):
        """Ein DEMO-Konto nur für das Modul Material (Karte, Wiki, Prüfungen und Verwaltung aus) – mit zufälligem Passwort,
        die Einsatzkräfte mit einem gemeinsamen –, mit dem Journaleintrag „rollen“ wie in der Nutzerverwaltung. Prüfer und
        Materialwarte hinterlegen ihre DEMO-Unterschrift über den Dienst des Profils. Gibt es ein passendes DEMO-Konto mit
        der Adresse schon (konten_pruefen, etwa aus einem früheren Lauf), bleibt es mit Name, Passwort und Rollen; der
        Bericht nennt, worin es von der Rolle abweicht. Fehlt ihm nur die Unterschrift, kommt die DEMO-Unterschrift dazu."""
        import secrets

        from werkzeug.security import generate_password_hash

        from app import db
        from app.material.services import journal, unterschrift
        urkunde = k.get("urkunde", "")
        alt = db.query("SELECT * FROM users WHERE email = ?", (k["mail"],), one=True)
        with db.transaction(sofort=True):
            if alt:
                uid = alt["id"]
                anders = [f"Stufe im Modul Material {alt['recht_material']} statt {k['stufe']}"
                          if (alt["recht_material"] or 0) != k["stufe"] else ""]
                anders += [f"{name} an" for spalte, name in (("recht_verwaltung", "Verwaltung"), ("recht_karte", "Karte"),
                                                             ("recht_wiki", "Wiki"), ("recht_pruefungen", "Prüfungen"),
                                                             ("mat_katalog", "Katalogpflege"))
                           if alt[spalte]]
                if alt["mat_pruefer"] and not urkunde:
                    anders.append("Häkchen Prüfer")
                if any(anders):
                    self.abweichend.append(f"{k['mail']}: {', '.join(a for a in anders if a)}")
                self.passwoerter.append((k["mail"], alt["name"], None, k.get("sicht")))
                name = alt["name"]
            else:
                if k.get("person"):
                    passwort = self._gemeinsam = getattr(self, "_gemeinsam", None) or secrets.token_urlsafe(12)
                else:
                    passwort = secrets.token_urlsafe(12)
                uid = db.execute(
                    "INSERT INTO users (email, password_hash, name, gliederung, recht_karte, recht_wiki, recht_pruefungen, "
                    "recht_verwaltung, recht_material, mat_pruefer, mat_katalog, urkundennummer, created_at) "
                    "VALUES (?,?,?,?,0,0,0,0,?,?,0,?,?)",
                    (k["mail"], generate_password_hash(passwort), k["name"], GLIEDERUNGEN[0][1], k["stufe"],
                     int(bool(urkunde)), urkunde, db.now()))
                journal.eintragen("user", uid, "rollen", None, {"recht_material": k["stufe"],
                                                                "mat_pruefer": int(bool(urkunde)), "mat_katalog": 0,
                                                                "urkundennummer": urkunde})
                self.passwoerter.append((k["mail"], k["name"], passwort, k.get("sicht")))
                name = k["name"]
            if (urkunde or k["rolle"].startswith("wart")) and not unterschrift.von(uid):
                unterschrift.setzen({"id": uid}, unterschrift_uri(uid))
        return {"id": uid, "mail": k["mail"], "name": name}

    def freigaben(self, extern=False):
        """Materialwart: verwalten an seiner Gliederung; die Prüfer: lesen und prüfen, beides dauerhaft (befristet ist
        eine Prüffreigabe nur für Externe); Mitglied: lesen; die erste Einsatzkraft: lesen an ihrem persönlichen Ordner.
        Mit extern nur der externe Prüfer: prüfen im Zentrallager, 30 Tage ab heute (zeigt „läuft bald ab“). Über den
        Schreibweg des Freigaben-Dienstes mit den Rechten der Material-Verwaltung; im Journal unter „Beispielbestand“, die
        Konten nur als Kontoverweis. Eine Freigabe, die das Konto dort schon hat, bleibt."""
        from app import db
        from app.material.services import freigaben, rechte
        plattform = rechte.Sicht(uid=None, alles=True, qualifiziert=False)
        fl, ns = self.gl[GROSS], self.gl[KLEIN]
        if extern:
            liste = [("extern", fl["ordner"]["lager"], "pruefen", (self.h + timedelta(days=30)).isoformat())]
        else:
            liste = [("wart", fl["id"], "verwalten", None), ("wart_ns", ns["id"], "verwalten", None),
                     ("pruefer", fl["id"], "lesen", None), ("pruefer", fl["id"], "pruefen", None),
                     ("pruefer2", fl["id"], "lesen", None), ("pruefer2", fl["id"], "pruefen", None),
                     ("pruefer_ns", ns["id"], "lesen", None), ("pruefer_ns", ns["id"], "pruefen", None),
                     ("mitglied", fl["id"], "lesen", None)]
        for rolle, ordner, recht, ende in liste:
            konto = rechte.waehlbares_konto(self.konto[rolle]["id"])
            if db.query("SELECT 1 FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = ?",
                        (ordner, konto["id"], recht), one=True):
                continue
            neu = {"user_id": konto["id"], "permission": recht, "valid_until": freigaben._bis(ende, recht),
                   "note": "DEMO"}
            freigaben._schreiben(plattform, {"id": None}, ordner, None, neu, konto)
        rechte.sicht_verwerfen()

    def _personenordner(self, rolle):
        """Der persönliche Ordner einer Einsatzkraft – beim ersten Bedarf angelegt (an ihrem Eintrittstag); die erste
        bekommt dort lesen."""
        from app.material.services import bestand, freigaben, rechte
        fl = self.gl[GROSS]
        if rolle not in fl["ordner"]:
            fl["ordner"][rolle] = bestand.ordner_anlegen(
                {"name": self.konto[rolle]["name"], "kind": "persoenlich", "parent_id": fl["ordner"]["persoenlich"]},
                demo=True)
            if rolle == "person1":
                konto = rechte.waehlbares_konto(self.konto[rolle]["id"])
                freigaben._schreiben(rechte.Sicht(uid=None, alles=True, qualifiziert=False), {"id": None},
                                     fl["ordner"][rolle], None, {"user_id": konto["id"], "permission": "lesen",
                                                                 "valid_until": None, "note": "DEMO"}, konto)
                rechte.sicht_verwerfen()
        return fl["ordner"][rolle]

    @staticmethod
    def pruefer(uid):
        """Prüfer (oder aussondernder Materialwart) aus seinem Konto – wie nach einer Anmeldung (pruefer_aus)."""
        from app import db
        from app.material.services import pruefung
        return pruefung.pruefer_aus(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True))

    def _pruefer_fuer(self, a):
        rollen = ["pruefer_ns"] if a["gl"] == KLEIN else ["pruefer", "pruefer2"]
        return self.pruefer(self.konto[self.rnd.choice(rollen)]["id"])

    def _wart(self, a):
        return self.pruefer(self.konto["wart_ns" if a["gl"] == KLEIN else "wart"]["id"])

    # --- Plan ---

    def _favoriten(self, liste):
        """Gewichte je Produkt eines Typs: bis zu drei Standardprodukte machen gut zwei Drittel aus, der Rest verteilt
        sich auf die übrigen – so sieht ein gewachsener Bestand aus."""
        auswahl = sorted(liste, key=lambda p: p["id"])
        self.rnd.shuffle(auswahl)
        fav = auswahl[:3]
        gewichte = [6, 3, 2][:len(fav)]
        rest = auswahl[3:]
        if rest:
            je = 0.45 * sum(gewichte) / len(rest)
            return fav + rest, gewichte + [je] * len(rest)
        return fav, gewichte

    @staticmethod
    def _bereich(kurz, ordner):
        """Der Bereich (Ordner mit Jahresprüfung), zu dem ein Ordner gehört."""
        oben = {s: o for s, _, _, o in ORDNER[kurz]}
        bereiche = {b for k, b, _ in BEREICHE if k == kurz}
        x = ordner if ordner in oben else "persoenlich"
        while x not in bereiche and oben.get(x):
            x = oben[x]
        return x

    def _runden(self, kurz, bereich):
        """Die Tage der Jahresprüfungen eines Bereichs nach dem Beginn, älteste zuerst."""
        tage = next(t for k, b, t in BEREICHE if (k, b) == (kurz, bereich))
        out, k = [], 0
        while True:
            tag = self.h - timedelta(days=tage + 365 * k)
            if tag <= self.beginn + timedelta(days=20):
                break
            out.insert(0, tag)
            k += 1
        return out

    def planen(self, produkte):
        """Welche Artikel wohin: zuerst die persönliche Ausrüstung je Einsatzkraft (Kit), dann der übrige Bestand nach den
        Gewichten der Typen und Ordner, ein kleiner Teil in die Nachbarstadt. Ein Teil kommt erst im Lauf der Jahre
        (Nachkauf, nie die persönliche Ausrüstung – sonst stünde eine Einsatzkraft lange ohne Gurt da), der Rest wird je
        Bereich kurz vor seiner ersten Jahresprüfung erfasst."""
        rnd = self.rnd
        je_typ = {}
        for p in produkte:
            je_typ.setdefault(p["typ"], []).append(p)
        wahl = {t: self._favoriten(liste) for t, liste in je_typ.items()}
        gewicht = {t: g for t, _, g in TYPEN if t in je_typ}

        def produkt(typ):
            liste, gew = wahl[typ]
            return rnd.choices(liste, weights=gew)[0]

        plaene = []
        kit = [(t, m) for t, m in KIT if t in je_typ]
        for rolle in self.personen:
            for typ, m in kit:
                for _ in range(m):
                    if len(plaene) < self.n:
                        plaene.append({"typ": typ, "produkt": produkt(typ), "gl": GROSS, "ordner": rolle,
                                       "person": rolle})
        rest = self.n - len(plaene)
        klein = round(rest * GLIEDERUNGEN[1][2]) if rest >= 20 else min(rest, 1 if self.n >= 4 else 0)
        typen, gew = list(gewicht), list(gewicht.values())
        belegt = {}
        for k in range(rest):
            typ = rnd.choices(typen, weights=gew)[0]
            if k < klein:
                ziele = ZIELE_KLEIN
                kurz = KLEIN
            else:
                ziele, kurz = ZIELE.get(typ, ZIELE["sonstiges"]), GROSS
            ziele = {o: w for o, w in ziele.items() if belegt.get(o, 0) < FASSUNG.get(o, self.n)} or \
                {"reserve" if kurz == GROSS else "lager": 1}
            ordner = rnd.choices(list(ziele), weights=list(ziele.values()))[0]
            belegt[ordner] = belegt.get(ordner, 0) + 1
            a = {"typ": typ, "produkt": produkt(typ), "gl": kurz, "ordner": ordner, "person": None}
            if ordner in _GRUPPEN and rnd.random() < GRUPPE_ZUGEORDNET and self.personen:
                a["person"] = rnd.choice(self.personen)
            plaene.append(a)
        rnd.shuffle(plaene)
        # Die globale Suche aus dem Kreisverband heraus findet diese Nummer in der Nachbarstadt (wie bisher).
        ns = [a for a in plaene if a["gl"] == KLEIN]
        for k, a in enumerate(plaene, 1):
            a["serie"] = f"DEMO-{a['gl']}-{k:04d}"
        if ns:
            ns[0]["serie"] = "DEMO-NS-4711"
        # Wann jeder Artikel kommt: Nachkauf irgendwann (die letzten Tage mit: „neu“), sonst Ersterfassung des Bereichs.
        erstes = {}
        for kurz, bereich, _ in BEREICHE:
            runden = self._runden(kurz, bereich)
            erstes[(kurz, bereich)] = runden[0] if runden else self.beginn + timedelta(days=30)
        for a in plaene:
            a["bereich"] = self._bereich(a["gl"], a["ordner"])
            if rnd.random() < NACHKAUF and not a["ordner"].startswith("person"):
                a["erfasst"] = self._tag(self.beginn + timedelta(days=40), self.h - timedelta(days=1))
                a["nachkauf"] = True
            else:
                a["erfasst"] = max(self.beginn, erstes[(a["gl"], a["bereich"])] - timedelta(days=rnd.randint(3, 25)))
                a["nachkauf"] = False
            a.update(self._stamm(a))
        # Lebensende: Bei einigen textilen Artikeln des Erstbestands endet die Lebensdauer in der Geschichte – sie werden
        # in der nächsten Runde ausgesondert, oder sie stehen am Ende auf „Lebensdauer erreicht“.
        textil = [a for a in plaene if a["produkt"]["lebensdauer"] and not a["nachkauf"]]
        for k, a in enumerate(rnd.sample(textil, min(len(textil), max(1 if textil else 0,
                                                                     round(len(textil) * LEBENSENDE))))):
            self._lebensende(a, spaet=k % 3 == 0)
        self.artikel = plaene
        for a in plaene:
            self._ereignis(a["erfasst"], 1, "erfassen", a)
        for kurz, bereich, _ in BEREICHE:
            for tag in self._runden(kurz, bereich):
                self._ereignis(tag, 3, "runde", (kurz, bereich))
        # Im Zentrallager läuft heute ein Durchgang – eröffnet vor ein paar Tagen.
        kurz, bereich, vor = OFFENER_DURCHGANG
        self._ereignis(self.h - timedelta(days=vor), 3, "runde_offen", (kurz, bereich))
        # Einsatzkräfte scheiden aus, neue treten ein und übernehmen deren Ausrüstung über die Reserve.
        gehen = rnd.sample(self.personen[1:], min(len(self.neue_personen), max(0, len(self.personen) - 1)))
        for alt, neu in zip(gehen, self.neue_personen):
            tag = self._tag(self.beginn + timedelta(days=200), self.h - timedelta(days=90))
            self._ereignis(tag, 5, "austritt", (alt, neu))
        # Mindestens ein Mangel mit Prüfung nach Reparatur – vor sechs Wochen, sonst käme er bei wenigen Artikeln nicht vor.
        kandidaten = [a for a in plaene if a["gl"] == GROSS and not a["nachkauf"] and a["produkt"]["formular"]
                      and not a["ordner"].startswith("person")]
        if kandidaten:
            self._ereignis(self.h - timedelta(days=45), 2, "pruefen", (rnd.choice(kandidaten), "mangel"))
        # Änderungsanträge an Artikeln, deren Stammdaten feststehen (nach der ersten Prüfung).
        for a in rnd.sample(plaene, min(len(plaene), max(4, round(len(plaene) * ANTRAG)))):
            self._ereignis(self._tag(max(a["erfasst"], self.beginn + timedelta(days=200)), self.h - timedelta(days=2)),
                           6, "antrag", a)

    def _stamm(self, a):
        """Kauf, Herstellung (Monat) und Erstgebrauch – erfundene Bestandsangaben, passend zur Geschichte. Herstellung
        vor dem Kauf; bei textilem Material so, dass die Lebensdauer am Ende noch mehr als 60 Tage reicht (das Lebensende
        in der Geschichte setzt _lebensende eigens)."""
        from app.material.services.interval import plus_jahre, plus_monate
        rnd, p = self.rnd, a["produkt"]
        if a["nachkauf"]:
            kauf = a["erfasst"] - timedelta(days=rnd.randint(0, 20))
        else:
            kauf = a["erfasst"] - timedelta(days=rnd.randint(30, 1200))
        herstellung = plus_monate(kauf.replace(day=1), -rnd.randint(1, 10))
        if p["lebensdauer"]:
            frueheste = plus_jahre((self.h + timedelta(days=60)).replace(day=1), -p["lebensdauer"])
            herstellung = max(herstellung, plus_monate(frueheste, 1))
            kauf = max(kauf, herstellung)
        werte = {"purchased_on": min(kauf, a["erfasst"]).isoformat(), "first_use_on": None}
        if p["textil"] or rnd.random() < 0.8:
            werte["manufactured_on"] = min(herstellung, a["erfasst"].replace(day=1)).strftime("%Y-%m")
        else:
            werte["manufactured_on"] = None
        if not a["nachkauf"] and rnd.random() < 0.6:
            werte["first_use_on"] = min(kauf + timedelta(days=rnd.randint(0, 40)), a["erfasst"]).isoformat()
        if p["laenge"]:
            werte["length_m"] = rnd.choice(LAENGEN)
        return werte

    def _lebensende(self, a, spaet=False):
        """Herstellung so lange her, dass das Lebensende zwischen der Erfassung (+120 Tage) und gestern liegt – mit spaet
        nach der letzten Jahresprüfung des Bereichs: Dann steht der Artikel am Ende auf „Lebensdauer erreicht“."""
        from app.material.services.interval import plus_jahre, plus_monate
        jahre = a["produkt"]["lebensdauer"]
        von = a["erfasst"] + timedelta(days=120)
        if spaet:
            runden = self._runden(a["gl"], a["bereich"])
            von = max(von, (runden[-1] if runden else von) + timedelta(days=35))
        ende = self._tag(von, self.h - timedelta(days=5))
        herstellung = plus_jahre(ende.replace(day=1), -jahre)
        kauf = min(plus_monate(herstellung, self.rnd.randint(1, 8)), a["erfasst"])
        a.update(manufactured_on=herstellung.strftime("%Y-%m"), purchased_on=kauf.isoformat(), first_use_on=None)

    def _tag(self, von, bis):
        if bis <= von:
            return von
        return von + timedelta(days=self.rnd.randint(0, (bis - von).days))

    def _ereignis(self, tag, rang, art, daten):
        """Ein Ereignis in die Warteschlange – nach Tag, dann Rang (erfassen vor prüfen vor Runde …), dann Reihenfolge."""
        if tag >= self.h:
            return
        self._nr += 1
        heapq.heappush(self._ereignisse, (tag, rang, self._nr, art, daten))

    # --- Abspielen ---

    def abspielen(self):
        monat = None
        while self._ereignisse:
            tag, _, _, art, daten = heapq.heappop(self._ereignisse)
            self.uhr.stellen(tag)
            jetzt = self.uhr.tag()
            if (jetzt.year, jetzt.month) != monat:
                monat = (jetzt.year, jetzt.month)
                print(f"  … {jetzt.strftime('%m/%Y')}: {self.zahl['pruefungen']} Prüfungen, "
                      f"{sum(1 for a in self.artikel if a.get('iid'))} Artikel ({self._dauer()})", flush=True)
            getattr(self, f"_e_{art}")(daten)

    def _versuch(self, was, aufgabe, fotos=None):
        """Ein Vorgang in seiner Transaktion; scheitert er an einer Regel der App, steht er unter „Hinweise“. Danach eine
        kurze Pause (PAUSE): Ohne sie hielte der Lauf die Schreibsperre fast ununterbrochen, und auf dev scheiterten
        Schreibzugriffe und Anmeldungen nach 15 s (Sicherheitsprüfung vom 25.10.2026, Befund 1)."""
        from app import db
        from app.material.services import Abgelehnt, protokoll
        fotos = [] if fotos is None else fotos
        try:
            with protokoll.dateien_sichern(), db.transaction(sofort=True):
                return aufgabe(fotos)
        except Abgelehnt as exc:
            self._fotos_weg(fotos)
            self.hinweise.append(f"{self.uhr.tag().isoformat()} {was}: {exc}")
        except BaseException:
            self._fotos_weg(fotos)
            raise
        finally:
            time.sleep(PAUSE)
        return None

    @staticmethod
    def _fotos_weg(fotos):
        """Mangelfotos eines zurückgerollten Vorgangs – ihre Dateien liegen schon, ihre Zeilen nicht mehr."""
        from app.images import delete_photo_files
        from app.material.services import katalog
        for name in fotos:
            delete_photo_files(katalog.medien_dir(), name)

    def _ordner_id(self, a):
        if a["ordner"] in self.ausgeschieden:          # nach dem Austritt kommt nichts mehr in ihren Ordner
            a["ordner"] = a["ordner_jetzt"] = "reserve"
        if a["ordner"].startswith("person"):
            return self._personenordner(a["ordner"])
        return self.gl[a["gl"]]["ordner"][a["ordner"]]

    def _e_erfassen(self, a):
        from app.material.services import bestand, zuordnung, rechte

        def anlegen(_):
            if a["person"] in self.ausgeschieden:       # Ausgeschiedene bekommen nichts mehr zugeordnet
                a["person"] = None
            werte = {k: a[k] for k in ("purchased_on", "manufactured_on", "first_use_on", "length_m") if a.get(k)}
            iid = bestand.artikel_anlegen(dict(werte, product_id=a["produkt"]["id"], folder_id=self._ordner_id(a),
                                               serial_no=a["serie"], notes=HINWEIS))
            if a["person"]:
                zuordnung._schreiben(bestand.artikel(iid), rechte.waehlbares_konto(self.konto[a["person"]]["id"])["id"])
                self.zahl["zugeordnet"] += 1
            return iid

        a["iid"] = self._versuch(f"Artikel {a['produkt']['name']} anlegen", anlegen)
        if not a["iid"]:
            return
        if a["nachkauf"]:
            self._ereignis(a["erfasst"] + timedelta(days=self.rnd.randint(0, 6)), 2, "pruefen", (a, None))
        self._plane_leben(a)

    def _plane_leben(self, a):
        """Was einem Artikel zwischen den Runden geschieht: außerplanmäßige Prüfungen nach Einsätzen, ein Verlust, eine
        Verschiebung."""
        rnd, von = self.rnd, a["erfasst"] + timedelta(days=30)
        for _ in range(math.ceil(max(0, (self.h - von).days) / 365)):
            if rnd.random() < EINSATZ:
                self._ereignis(self._tag(von, self.h - timedelta(days=1)), 2, "pruefen", (a, "ausserplanmaessig"))
        if rnd.random() < VERLUST:
            self._ereignis(self._tag(von, self.h - timedelta(days=1)), 4, "verlust", a)
        if not a["ordner"].startswith("person") and rnd.random() < VERSCHIEBEN:
            self._ereignis(self._tag(von, self.h - timedelta(days=1)), 5, "verschieben", a)

    def _artikel(self, a):
        from app.material.services import bestand
        return bestand.artikel(a["iid"]) if a.get("iid") else None

    def _e_pruefen(self, daten):
        """Eine Einzelprüfung: Eingang (Nachkauf), periodisch bei kürzerem Intervall, außerplanmäßig nach einem Einsatz
        (dann oft mit Mangel) oder nach Reparatur."""
        a, art = daten
        i = self._artikel(a)
        if not i or i["lock_state"] == "ausgesondert" or not a["produkt"]["formular"]:
            return
        if art == "reparatur":
            if i["lock_state"] != "gesperrt":
                return
            self.pruefen(a, "reparatur", "einsatzbereit", None)
            return
        if i["lock_state"] != "frei":
            return
        if art in ("ausserplanmaessig", "mangel") and not i["last_inspected_on"]:
            return
        if art == "mangel":
            self.pruefen(a, "ausserplanmaessig", "instandsetzen", "mangel")
            return
        mangel = "zufall"
        if art == "ausserplanmaessig":
            x = self.rnd.random()
            mangel = "kritisch" if x < 0.08 else ("mangel" if x < 0.45 else None)
        self.pruefen(a, art, *self._ergebnis(i, mangel))

    def _ergebnis(self, i, mangel="zufall"):
        """(Ergebnis, Mangel) einer Prüfung am Tag der Uhr: Lebensdauer erreicht → aussondern („lebensdauer“); sonst nach
        mangel („mangel“, „kritisch“, None) bzw. dem Zufall einer gewöhnlichen Prüfung."""
        tag = self.uhr.tag().isoformat()
        if i["retire_by"] and i["retire_by"] <= tag:
            return "aussondern", "lebensdauer"
        if mangel == "zufall":
            x = self.rnd.random()
            mangel = "kritisch" if x < AUSSONDERN else ("mangel" if x < AUSSONDERN + MANGEL else None)
        if mangel == "kritisch":
            return "aussondern", "kritisch"
        if mangel == "mangel":
            return "instandsetzen", "mangel"
        return "einsatzbereit", None

    def pruefen(self, a, art, ergebnis, mangel, durchgang_id=None, pruefer=None, abschliessen=True):
        """Eine Prüfung über den Prüfdienst: Entwurf mit den Prüfpunkten des aktiven Formulars, ausfüllen, abschließen und
        festschreiben (Protokoll) – Prüftag ist der Tag der Uhr. Danach, was daraus folgt: Prüfung nach Reparatur,
        Nachkauf, die nächste Prüfung bei kürzerem Intervall."""
        from app.material.services import pruefung
        pruefer = pruefer or self._pruefer_fuer(a)

        def tun(fotos):
            pid, _ = pruefung.starten(a["iid"], pruefer, art, durchgang_id)
            self.befunde(pid, pruefer, mangel, fotos)
            if not abschliessen:
                return pid
            d = {"ergebnis": ergebnis, "bemerkung": HINWEIS}
            if ergebnis == "aussondern" and mangel in (None, "lebensdauer"):
                d["grund"] = f"Lebensdauer erreicht ({HINWEIS})"
            elif ergebnis != "einsatzbereit":
                d["grund"] = HINWEIS
            pruefung.abschliessen(pid, d, pruefer)
            return pid

        pid = self._versuch(f"Prüfung {a['produkt']['name']} ({art or 'Vorschlag'})", tun)
        if not pid or not abschliessen:
            return pid
        self.zahl["pruefungen"] += 1
        tag = self.uhr.tag()
        if ergebnis == "instandsetzen":
            self._ereignis(tag + timedelta(days=self.rnd.randint(5, 30)), 2, "pruefen", (a, "reparatur"))
        elif ergebnis == "aussondern":
            self.zahl["aussonderungen"] += 1
            self._ereignis(tag + timedelta(days=self.rnd.randint(10, 60)), 1, "nachkauf", a)
        elif a["produkt"]["monate"] < 12:
            from app.material.services.interval import plus_monate
            self._ereignis(plus_monate(tag, a["produkt"]["monate"]) - timedelta(days=self.rnd.randint(3, 20)), 2,
                           "pruefen", (a, None))
        return pid

    def befunde(self, pid, pruefer, mangel, fotos):
        """Die Prüfpunkte aus dem Katalog: Ja/Nein und Zahlen mit Sollwert stehen schon auf ihrem Soll. Ein Pflichtpunkt,
        dessen Wert nur eine echte Prüfung liefert (Messwert, Datum, Foto), steht auf „nicht zutreffend“ mit der
        DEMO-Bemerkung; ein Pflicht-Textfeld bekommt die DEMO-Bemerkung als Wert, ein Pflicht-Unterschriftsfeld die
        DEMO-Unterschrift. mangel („mangel“, „kritisch“ oder „lebensdauer“): ein Punkt weicht vom Soll ab (_mangelpunkt) –
        mit DEMO-Bemerkung und DEMO-Platzhalterfoto, wie es jeder Mangel braucht."""
        from werkzeug.datastructures import FileStorage

        from app import db
        from app.material.services import pruefung
        punkte = pruefung.befunde(pid)
        ziel = self._mangelpunkt(punkte, mangel) if mangel else None
        for r in punkte:
            if ziel and r["id"] == ziel["id"]:
                if r["editor"] == "yesno":
                    d = {"wert": "nein" if r["expected_value"] == "ja" else "ja", "notiz": HINWEIS}
                else:
                    d = {"befund": "mangel", "notiz": HINWEIS}
                pruefung.punkt_setzen(pid, r["id"], d, pruefer)
                if self._foto is None:
                    self._foto = mangelfoto_png()
                datei = FileStorage(stream=io.BytesIO(self._foto), filename="demo-mangel.png", content_type="image/png")
                pruefung.punkt_foto_setzen(pid, r["id"], datei, pruefer)
                fotos.append(db.query("SELECT photo FROM mat_inspection_result WHERE id = ?", (r["id"],),
                                      one=True)["photo"])
            elif r["editor"] == "signature":
                if r["mandatory"]:
                    if self._signatur is None:
                        self._signatur = unterschrift_uri(7)
                    pruefung.punkt_setzen(pid, r["id"], {"unterschrift": self._signatur}, pruefer)
            elif r["editor"] == "text":
                if not (r["value"] or "").strip():
                    pruefung.punkt_setzen(pid, r["id"], {"wert": HINWEIS}, pruefer)
            elif r["editor"] in ("number", "date", "photo", "laenge"):
                beantwortet = r["photo"] if r["editor"] == "photo" else (r["value"] or "").strip()
                if r["mandatory"] and not beantwortet and r["finding"] != "nicht_zutreffend":
                    pruefung.punkt_setzen(pid, r["id"], {"befund": "nicht_zutreffend", "notiz": HINWEIS}, pruefer)

    def _mangelpunkt(self, punkte, mangel):
        """Der Punkt, an dem ein Befund vom Soll abweicht (Ablaufprüfung vom 25.10.2026, Befunde 3 und 4):
          - „lebensdauer“: der Ja/Nein-Punkt zur Lebensdauer (Text mit „Lebensdauer“), ohne einen solchen keiner;
          - „kritisch“ (aussondern): ein kritischer Ja/Nein-Punkt, ohne einen solchen ein gewöhnlicher;
          - „mangel“ (instandsetzen): nur ein nicht kritischer Punkt – ein kritischer führte zur Aussonderung.
        Der Punkt zur Lebensdauer steht nur für das Lebensende. Gestreut über die Punkte, die „vorangehenden Kontrollen“
        (Seriennummer lesbar …) nur, wenn sonst keiner bleibt; ohne Ja/Nein-Punkt der erste nicht kritische Punkt, der
        einen Befund kennt (kein Unterschriftsfeld)."""
        janein = [r for r in punkte if r["editor"] == "yesno"]
        if mangel == "lebensdauer":
            return next((r for r in janein if "lebensdauer" in r["checklist_text"].lower()), None)
        janein = [r for r in janein if "lebensdauer" not in r["checklist_text"].lower()]
        gewoehnlich = [r for r in janein if not r["is_critical"]]
        liste = ([r for r in janein if r["is_critical"]] or gewoehnlich) if mangel == "kritisch" else gewoehnlich
        if liste:
            weiter = [r for r in liste if not r["group_name"].startswith("Vorangehende")]
            return self.rnd.choice(weiter or liste)
        return next((r for r in punkte if r["editor"] not in ("signature", "yesno") and not r["is_critical"]), None)

    def _e_nachkauf(self, alt):
        """Ersatz für einen ausgesonderten Artikel: dasselbe Produkt in denselben Ordner, derselben Person zugeordnet –
        mit Eingangsprüfung ein paar Tage später."""
        a = dict(alt, iid=None, nachkauf=True, erfasst=self.uhr.tag(), serie=f"{alt['serie']}-E")
        a["ordner"] = alt.get("ordner_jetzt", alt["ordner"])
        a.update(self._stamm(a))
        self.artikel.append(a)
        self.zahl["nachkauf"] += 1
        self._e_erfassen(a)

    def _e_verlust(self, a):
        """Verloren gemeldet (Sperre durch den Prüfer); die Hälfte sondert der Materialwart später aus und kauft nach."""
        from app.material.services import pruefung
        i = self._artikel(a)
        if not i or i["lock_state"] != "frei":
            return
        pruefer = self._pruefer_fuer(a)
        if self._versuch("Verlust melden", lambda _: pruefung.sperren(a["iid"], {"grund": "verlust", "text": HINWEIS},
                                                                       pruefer)) is None and \
                self._artikel(a)["lock_state"] != "verloren":
            return
        self.zahl["verloren"] += 1
        if self.rnd.random() < 0.5:
            self._ereignis(self.uhr.tag() + timedelta(days=self.rnd.randint(14, 60)), 4, "aussondern_verlust", a)

    def _e_aussondern_verlust(self, a):
        from app.material.services import pruefung
        i = self._artikel(a)
        if not i or i["lock_state"] != "verloren":
            return
        wart = self._wart(a)
        if self._versuch("Aussondern nach Verlust", lambda _: pruefung.aussondern(
                a["iid"], {"grund": "verlust", "bemerkung": HINWEIS}, wart) or True):
            self.zahl["aussonderungen"] += 1
            self._ereignis(self.uhr.tag() + timedelta(days=self.rnd.randint(7, 40)), 1, "nachkauf", a)

    def _e_verschieben(self, a):
        """In einen anderen Ordner derselben Gliederung, wie es zum Typ passt (nicht in einen Rucksack oder eine Tasche –
        die sind gepackt)."""
        from app.material.services import bestand
        i = self._artikel(a)
        if not i or i["lock_state"] != "frei":
            return
        ziele = {o: w for o, w in (ZIELE_KLEIN if a["gl"] == KLEIN else ZIELE.get(a["typ"], ZIELE["sonstiges"])).items()
                 if o not in FASSUNG}
        ziele.pop(a.get("ordner_jetzt", a["ordner"]), None)
        if not ziele:
            return
        neu = self.rnd.choices(list(ziele), weights=list(ziele.values()))[0]
        if self._versuch("Verschieben", lambda _: bestand.artikel_verschieben([a["iid"]], self.gl[a["gl"]]["ordner"][neu])):
            a["ordner_jetzt"] = neu
            self.zahl["verschoben"] += 1

    def _e_austritt(self, daten):
        """Eine Einsatzkraft scheidet aus: Zuordnungen lösen, ihre persönliche Ausrüstung in die Reserve; 20 bis 60 Tage
        später tritt eine neue ein – ihr persönlicher Ordner entsteht, und die Ausrüstung kommt dorthin, ihr zugeordnet.
        Danach bekommt die Ausgeschiedene nichts mehr – weder eine Zuordnung noch etwas in ihren Ordner, auch nicht, was
        erst geplant ist (Nachkauf, Ersatz für Ausgesondertes): Das kommt in die Reserve, ohne Person (_e_erfassen,
        _ordner_id)."""
        from app.material.services import bestand, zuordnung
        alt, neu = daten
        fl = self.gl[GROSS]
        eigene = [a for a in self.artikel if a.get("iid") and a["person"] == alt]
        mit = []

        def raus(_):
            for a in eigene:
                i = bestand.artikel(a["iid"])
                if i["lock_state"] == "ausgesondert":
                    continue
                if zuordnung._schreiben(i, None):
                    self.zahl["geloest"] += 1
                if i["lock_state"] == "frei" and a.get("ordner_jetzt", a["ordner"]).startswith("person"):
                    mit.append(a)
            if mit:
                bestand.artikel_verschieben([a["iid"] for a in mit], fl["ordner"]["reserve"])
            return True

        if self._versuch(f"Austritt {self.konto[alt]['name']}", raus):
            self.zahl["ausgeschieden"] += 1
            self.ausgeschieden[alt] = self.uhr.tag()
            for a in self.artikel:
                if a["person"] == alt:
                    a["person"] = None
                if a.get("ordner_jetzt", a["ordner"]) == alt:
                    a["ordner_jetzt"] = "reserve"
            for a in mit:
                a["ordner_jetzt"] = "reserve"
            self._ereignis(self.uhr.tag() + timedelta(days=self.rnd.randint(20, 60)), 5, "eintritt", (neu, mit))

    def _e_eintritt(self, daten):
        from app.material.services import bestand, rechte, zuordnung
        neu, artikel = daten
        bewegt = []

        def rein(_):
            fid = self._personenordner(neu)
            uid = rechte.waehlbares_konto(self.konto[neu]["id"])["id"]
            bewegt.extend(a for a in artikel if bestand.artikel(a["iid"])["lock_state"] == "frei")
            if bewegt:
                bestand.artikel_verschieben([a["iid"] for a in bewegt], fid)
                for a in bewegt:
                    if zuordnung._schreiben(bestand.artikel(a["iid"]), uid):
                        self.zahl["zugeordnet"] += 1
            return True

        if self._versuch(f"Eintritt {self.konto[neu]['name']}", rein):
            self.zahl["eintritt"] += 1
            for a in bewegt:
                a["person"], a["ordner_jetzt"] = neu, neu

    def _als(self, rolle, aufgabe):
        """aufgabe() als angemeldetes DEMO-Konto (für Dienste, die den Handelnden aus der Anfrage lesen)."""
        from flask import g

        from app import db
        from app.material.services import Abgelehnt, rechte
        with self.app.test_request_context():
            g.user = db.query("SELECT * FROM users WHERE id = ?", (self.konto[rolle]["id"],), one=True)
            rechte.sicht_verwerfen()
            try:
                return aufgabe()
            except Abgelehnt as exc:
                self.hinweise.append(f"{self.uhr.tag().isoformat()} Änderungsantrag: {exc}")
                return None
            finally:
                g.pop("user", None)
                rechte.sicht_verwerfen()

    def _e_antrag(self, a, folge=None):
        """Der Prüfer beantragt eine korrigierte Seriennummer; die Material-Verwaltung bestätigt oder lehnt ab, oder der
        Antragsteller zieht zurück – ein junger Antrag bleibt offen. Mit folge (sicherstellen) geschieht das gleich: Wahr,
        wenn der Antrag diesen Zustand hat."""
        from app.material.services import antrag, bestand
        i = self._artikel(a)
        if not i or i["lock_state"] == "ausgesondert" or not bestand.stammdaten_fest(i["id"]):
            return
        rolle = "pruefer_ns" if a["gl"] == KLEIN else self.rnd.choice(["pruefer", "pruefer2"])
        neu = f"{i['serial_no']}-K"
        ids = self._als(rolle, lambda: antrag.stellen(i["id"], {"serial_no": neu, "begruendung": HINWEIS})[0])
        if not ids:
            return
        self.zahl["antraege"] += 1
        if folge:
            self.antraege[ids[0]] = "offen"
            return folge == "offen" or self._e_entscheiden((ids[0], folge, rolle))
        tag = self.uhr.tag()
        x = self.rnd.random()
        if (self.h - tag).days < 30 and x < 0.5:
            self.antraege[ids[0]] = "offen"
            return
        folge = "bestaetigt" if x < 0.55 else ("abgelehnt" if x < 0.8 else "zurueckgezogen")
        self._ereignis(tag + timedelta(days=self.rnd.randint(1, 10)), 6, "entscheiden", (ids[0], folge, rolle))
        self.antraege[ids[0]] = "offen"

    def _e_entscheiden(self, daten):
        from app.material.services import antrag
        aid, folge, rolle = daten
        if folge == "bestaetigt":
            ok = self._als("mv", lambda: antrag.bestaetigen(aid, {"antwort": HINWEIS}) or True)
        elif folge == "abgelehnt":
            ok = self._als("mv", lambda: antrag.ablehnen(aid, {"antwort": HINWEIS}) or True)
        else:
            ok = self._als(rolle, lambda: antrag.zurueckziehen(aid) or True)
        if ok:
            self.antraege[aid] = folge
        return bool(ok)

    # --- Prüfdurchgänge ---

    def _e_runde(self, daten, offen=False):
        """Die Jahresprüfung eines Bereichs: Durchgang eröffnen, jeden Artikel prüfen (verteilt über ein paar Tage, gut 40
        am Tag), Gesperrtes und Verlorenes mit Grund ausnehmen, abschließen (Sammelprotokoll). offen: nur ein Drittel
        bis gestern – der Rest geschieht heute (heute_schritte)."""
        from app import db
        from app.material.services import Abgelehnt, bestand, durchgang
        kurz, bereich = daten
        gl = self.gl[kurz]
        wart = self.pruefer(self.konto["wart_ns" if kurz == KLEIN else "wart"]["id"])
        titel = (f"DEMO-Jahresprüfung {next(n for s, n, _, _ in ORDNER[kurz] if s == bereich)} "
                 f"{self.uhr.tag().year}")
        bedingung, args = bestand.heimat_im_zweig(gl["ordner"][bereich])
        if not db.query(f"SELECT 1 FROM mat_item i WHERE {bedingung} AND i.lock_state <> 'ausgesondert' LIMIT 1", args):
            return                                         # (noch) nichts in diesem Bereich – keine Runde
        try:
            rid = durchgang.eroeffnen(gl["ordner"][bereich], {"titel": titel}, wart)
        except Abgelehnt as exc:
            self.hinweise.append(f"{self.uhr.tag().isoformat()} {titel}: {exc}")
            return
        nach_iid = {a["iid"]: a for a in self.artikel if a.get("iid")}
        ids = [r["item_id"] for r in db.query("SELECT ri.item_id FROM mat_round_item ri JOIN mat_item i ON i.id = "
                                               "ri.item_id WHERE ri.round_id = ? ORDER BY i.inventory_no", (rid,))]
        if offen:
            self._offen = (rid, wart, ids, nach_iid)
            ids = ids[:max(1, len(ids) // 3)]
        start = self.uhr.tag()
        for k, iid in enumerate(ids):
            self.uhr.stellen(start + timedelta(days=k // 40))
            self._runde_artikel(rid, iid, nach_iid.get(iid), wart)
        if offen:
            return
        self.uhr.stellen(start + timedelta(days=len(ids) // 40 + self.rnd.randint(0, 3)))
        if self._versuch(titel + " abschließen", lambda _: durchgang.abschliessen(rid, wart) or True):
            self.zahl["runden"] += 1
        print(f"  {titel}: {len(ids)} Artikel ({self._dauer()})", flush=True)

    def _e_runde_offen(self, daten):
        self._e_runde(daten, offen=True)

    def _runde_artikel(self, rid, iid, a, wart):
        from app.material.services import bestand, durchgang
        i = bestand.artikel(iid)
        grund = None
        if not a or not a["produkt"]["formular"]:
            grund = f"{HINWEIS}: kein aktives Prüfformular im Katalog"
        elif i["lock_state"] == "verloren":
            grund = f"{HINWEIS}: verloren gemeldet"
        elif i["lock_state"] != "frei":
            grund = f"{HINWEIS}: gesperrt – in Reparatur"
        if grund:
            self._versuch("Ausnehmen", lambda _: durchgang.ausnehmen(rid, iid, {"grund": grund}, wart))
            return
        if not self.pruefen(a, None, *self._ergebnis(i), durchgang_id=rid):
            self._versuch("Ausnehmen", lambda _: durchgang.ausnehmen(
                rid, iid, {"grund": f"{HINWEIS}: nicht prüfbar"}, wart))

    # --- Heute ---

    def heute_schritte(self):
        """Mit der echten Uhr: die Prüffreigabe des externen Prüfers (30 Tage), im offenen Durchgang ein Entwurf bei ihm und
        ein Artikel mit Grund ausgenommen; dazu, was sonst nicht vorkäme (gesperrt, verloren, neu)."""
        from app.material.services import bestand, durchgang
        self.uhr.echt()
        self.freigaben(extern=True)
        if getattr(self, "_offen", None):
            rid, wart, ids, nach_iid = self._offen
            rest = [iid for iid in ids if not db_erledigt(rid, iid)]
            extern = self.pruefer(self.konto["extern"]["id"])
            frei = [iid for iid in rest if nach_iid.get(iid) and nach_iid[iid]["produkt"]["formular"]
                    and bestand.artikel(iid)["lock_state"] == "frei"]
            if frei:
                self.pruefen(nach_iid[frei[0]], None, None, None, durchgang_id=rid, pruefer=extern, abschliessen=False)
            if len(frei) > 1:
                self._versuch("Ausnehmen", lambda _: durchgang.ausnehmen(
                    rid, frei[-1], {"grund": f"{HINWEIS}: beim Hersteller zur Reparatur"}, wart))
        self.sicherstellen()

    def sicherstellen(self):
        """Was in der Geschichte zufällig nicht vorkam, geschieht heute an Artikeln außerhalb der persönlichen Ordner:
        eine Aussonderung aus einer Prüfung (kritischer Mangel), eine durch den Materialwart (nach Verlust), ein Mangel
        (gesperrt), ein Verlust (verloren gemeldet), ein Nachkauf ohne Eingangsprüfung (neu) und je fehlendem
        Antragszustand (bestätigt, abgelehnt, zurückgezogen, offen) ein Änderungsantrag."""
        from app import db
        from app.material.services import bestand, pruefung
        ids = json.dumps([a["iid"] for a in self.artikel if a.get("iid")])

        def gibt(where):
            return db.query(f"SELECT 1 FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE x.item_id IN "
                            f"(SELECT value FROM json_each(?)) AND {where} LIMIT 1", (ids,))

        def gesperrt(zustand):
            return db.query("SELECT 1 FROM mat_item WHERE id IN (SELECT value FROM json_each(?)) AND lock_state = ? "
                            "LIMIT 1", (ids, zustand))

        frei = [a for a in self.artikel if a.get("iid") and a["produkt"]["formular"] and a["gl"] == GROSS
                and not a.get("ordner_jetzt", a["ordner"]).startswith("person")
                and bestand.artikel(a["iid"])["lock_state"] == "frei" and bestand.artikel(a["iid"])["last_inspected_on"]
                and not bestand.artikel(a["iid"])["retire_by"]]
        self.rnd.shuffle(frei)
        if not gibt("x.kind = 'aussonderung' AND x.basis_inspection_id IS NOT NULL") and frei:
            self.pruefen(frei.pop(), "ausserplanmaessig", "aussondern", "kritisch")
        if not gibt("x.kind = 'aussonderung' AND x.basis_inspection_id IS NULL") and frei:
            a = frei.pop()
            pruefer, wart = self._pruefer_fuer(a), self._wart(a)
            if self._versuch("Verlust melden", lambda _: pruefung.sperren(
                    a["iid"], {"grund": "verlust", "text": HINWEIS}, pruefer) or True):
                self.zahl["verloren"] += 1
                if self._versuch("Aussondern nach Verlust", lambda _: pruefung.aussondern(
                        a["iid"], {"grund": "verlust", "bemerkung": HINWEIS}, wart) or True):
                    self.zahl["aussonderungen"] += 1
        if not gesperrt("gesperrt") and frei:
            self.pruefen(frei.pop(), "ausserplanmaessig", "instandsetzen", "mangel")
        if not gesperrt("verloren") and frei:
            self._e_verlust(frei.pop())
        if not any(a.get("iid") and not bestand.artikel(a["iid"])["last_inspected_on"]
                   and bestand.artikel(a["iid"])["lock_state"] == "frei" for a in self.artikel) and self.artikel:
            muster = next((a for a in self.artikel if a["gl"] == GROSS and not a["ordner"].startswith("person")),
                          self.artikel[0])
            a = dict(muster, iid=None, nachkauf=True, erfasst=self.h, person=None, serie=f"{muster['serie']}-N")
            a.update(self._stamm(a))
            self.artikel.append(a)
            self.zahl["nachkauf"] += 1
            self._e_erfassen(a)
        da = {r["status"] for r in db.query("SELECT status FROM mat_item_change WHERE item_id IN (SELECT value FROM "
                                            "json_each(?))", (ids,))}
        for folge in ANTRAG_TEXT:
            while folge not in da and frei:
                a = frei.pop()
                if not db.query("SELECT 1 FROM mat_item_change WHERE item_id = ? AND status = 'offen'", (a["iid"],)) \
                        and self._e_antrag(a, folge):
                    da.add(folge)

    # --- Bericht ---

    def bericht(self, produkte, ausgelassen):
        from app import db
        from app.material.services import bestand
        from app.material.services import status as st
        ids = json.dumps([a["iid"] for a in self.artikel if a.get("iid")])
        artikel = db.query("SELECT * FROM mat_item WHERE id IN (SELECT value FROM json_each(?))", (ids,))
        verloren = sum(1 for i in artikel if i["lock_state"] == "verloren")
        x = db.query("SELECT SUM(locked_at IS NOT NULL) AS fest, SUM(kind = 'aussonderung') AS aus, "
                     "SUM(completed_at IS NULL) AS entwurf, MIN(inspected_on) AS erste FROM mat_inspection WHERE item_id IN "
                     "(SELECT value FROM json_each(?))", (ids,), one=True)
        zweige = json.dumps(sorted({f for g in self.gl.values() for f in bestand.unterbaum(g["id"])}))
        runden = db.query("SELECT SUM(closed_on IS NOT NULL) AS zu, SUM(closed_on IS NULL) AS offen FROM mat_round "
                          "WHERE folder_id IN (SELECT value FROM json_each(?))", (zweige,), one=True)
        antraege = {}
        for r in db.query("SELECT status, COUNT(*) AS n FROM mat_item_change WHERE item_id IN "
                          "(SELECT value FROM json_each(?)) GROUP BY status", (ids,)):
            antraege[r["status"]] = r["n"]
        demo = sum(1 for i in artikel if bestand.ist_demo(i["id"]))
        print()
        print("DEMO-Konten (Passwörter nur hier – sie werden nicht erneut angezeigt):")
        gemeinsam = [k for k in self.passwoerter if k[3] == OHNE_ZUGANG and k[2]]
        for mail, name, pw, sicht in self.passwoerter:
            if (mail, name, pw, sicht) in gemeinsam:
                continue
            text = f"Passwort: {pw}" if pw else "schon da – Passwort unverändert"
            print(f"  {mail:<42} {name:<32} {text}" + (f"  ({sicht})" if sicht else ""))
        if gemeinsam:
            von, bis = gemeinsam[0][0].split("@")[0], gemeinsam[-1][0].split("@")[0].rsplit("-", 1)[-1]
            print(f"  {von} bis -{bis}@{POSTFACH}: {len(gemeinsam)} Einsatzkräfte ({OHNE_ZUGANG}) – gemeinsames "
                  f"Passwort wie oben: {gemeinsam[0][2]}")
        print()
        print(f"Beispielbestand angelegt – Laufzeit {self._dauer()}.")
        for g in self.gl.values():
            print(f"  {g['name']:<34} {len(bestand.unterbaum(g['id'])) - 1} Ordner darunter")
        print(f"  Konten        {len(self.passwoerter)} DEMO-Konten")
        print(f"  Artikel       {len(artikel)} aus {len({a['produkt']['id'] for a in self.artikel if a.get('iid')})} "
              f"Produkten, davon {demo} als DEMO gekennzeichnet; {self.zahl['nachkauf']} Nachkäufe als Ersatz")
        print(f"  Geschichte    ab {x['erste'] or '–'}; {x['fest'] or 0} Prüfungen festgeschrieben mit Protokoll (davon "
              f"{x['aus'] or 0} Aussonderungen), {x['entwurf'] or 0} in Prüfung (Entwurf)")
        print(f"  Durchgänge    {runden['zu'] or 0} abgeschlossen mit Sammelprotokoll, {runden['offen'] or 0} offen")
        print(f"  Zuordnungen   {self.zahl['zugeordnet']} gesetzt, {self.zahl['geloest']} gelöst "
              f"({self.zahl['ausgeschieden']} Einsatzkräfte ausgeschieden, {self.zahl['eintritt']} eingetreten)")
        print(f"  Verschoben    {self.zahl['verschoben']} Artikel; verloren gemeldet: {self.zahl['verloren']}")
        print("  Anträge       " + (", ".join(f"{antraege[s]} {t}" for s, t in ANTRAG_TEXT.items() if s in antraege)
                                     or "keine"))
        zaehlung = st.leere_zaehlung()
        for i in artikel:
            zaehlung[st.status(i)] += 1
        print("Zustände")
        for s in st.STATUS:
            zusatz = f"  (davon verloren gemeldet: {verloren})" if s == "gesperrt" else ""
            print(f"  {st.LABEL[s]:<22}{zaehlung[s]:>5}{zusatz}")
        fehlen = [st.LABEL[s] for s in st.STATUS if not zaehlung[s]] + ([] if verloren else ["verloren gemeldet"])
        if fehlen:
            grund = "" if any(p["lebensdauer"] for p in produkte) else " (der Katalog hat kein textiles Produkt mit Lebensdauer)"
            print(f"  Kommt nicht vor: {', '.join(fehlen)}{grund}.")
        petzl, platzhalter, ohne_form = self._formulare
        if petzl:
            print("Formulare nach Petzl-Prüfbericht (DEMO, nicht im Katalog-Export; Fundstelle je Punkt in "
                  "scripts/beispielbestand_petzl_punkte.json):")
            for name in petzl:
                for q in petzl_vorlage(self._vorlagen, name)["quelle"].values():
                    print(f"  {name}: {q['hersteller']} „{q['titel']}“ ({q.get('version_gedruckt') or 'ohne Versionsangabe'}"
                          f"), {q['dateiname']}")
        if platzhalter:
            print(f"Platzhalter-Formulare (DEMO, nicht im Katalog-Export): {', '.join(platzhalter)}.")
        if ohne_form:
            print(f"Ohne wirksames Formular (nur ein inaktives echtes – bitte im Katalog aktivieren): {', '.join(ohne_form)}.")
        ohne = sorted({p["name"] for p in produkte if not p["formular"]})
        if ohne:
            print(f"Ohne aktives Prüfformular (keine Prüfung möglich, Artikel „neu“): {', '.join(ohne)}.")
        if ausgelassen:
            print(f"Nicht verwendet: {'; '.join(ausgelassen[:20])}{' …' if len(ausgelassen) > 20 else ''}.")
        mit_artikeln = len({a["produkt"]["id"] for a in self.artikel if a.get("iid")})
        if mit_artikeln:
            print(f"Jetzt mit Artikeln: {mit_artikeln} Produkte – sie lassen sich nicht mehr löschen, ihre Materialart "
                  "nicht mehr ändern und ihre Kategorien nicht mehr löschen; benutzte Formularversionen nur noch über eine "
                  "neue Version ändern. Katalogpflege, die das braucht: Katalog exportieren, dev-Datenbank zurücksetzen, "
                  "Export importieren.")
        if self.abweichend:
            print("Vorhandene DEMO-Konten übernommen, Rollen unverändert – sie weichen ab: " + "; ".join(self.abweichend)
                  + ".")
        if self.hinweise:
            print(f"Hinweise ({len(self.hinweise)}):")
            for zeile in self.hinweise[:40]:
                print(f"  {zeile}")
            if len(self.hinweise) > 40:
                print(f"  … und {len(self.hinweise) - 40} weitere")


def db_erledigt(rid, iid):
    """Hat der Artikel im Durchgang schon eine abgeschlossene Prüfung oder einen Ausnahmegrund?"""
    from app import db
    return bool(db.query("SELECT 1 FROM mat_round_item ri WHERE ri.round_id = ? AND ri.item_id = ? AND "
                         "(ri.excluded_reason IS NOT NULL OR EXISTS (SELECT 1 FROM mat_inspection x WHERE x.round_id = "
                         "ri.round_id AND x.item_id = ri.item_id))", (rid, iid), one=True))


if __name__ == "__main__":
    main()
