"""Beispielbestand für das Modul Material – NUR für dev und Tests, nie für echte Prüfungen.

Ein umfangreicherer Bestand zum Ausprobieren, gebaut allein aus dem vorhandenen Katalog: drei DEMO-Gliederungen
(„DEMO-OG …“) mit Lager, Fahrzeugen, Einsatzgruppen und persönlichen Ordnern, einige hundert Artikel der echten
Katalogprodukte, eine Prüfhistorie über deren aktive Prüfformulare (zurückdatiert und festgeschrieben, mit Protokoll
wie jede echte Prüfung), DEMO-Konten mit Freigaben, je Gliederung ein abgeschlossener und ein offener Prüfdurchgang und
Zuordnungen an DEMO-Personen. Am Ende kommt jeder Zustand vor: neu, einsatzbereit, bald fällig, überfällig, gesperrt
(Mangel), verloren gemeldet, ausgesondert und – wo der Katalog eine Lebensdauer hat – Lebensdauer erreicht.

Eigenständiges Werkzeug außerhalb von app/ (wie scripts/material_demo.py) und in EINER Datei, damit es sich per stdin
in den Container reichen lässt – das Docker-Abbild enthält scripts/ nicht. Es läuft nur mit ausdrücklichem Schalter:

    python scripts/material_beispielbestand.py --beispielbestand [--artikel N]

--artikel N: so viele Artikel insgesamt (Vorgabe 200), verteilt über alle echten Produkte. Ohne Angabe landen die
Daten wie bei run.py in ./data; für eine andere Datenbank vorher DATA_DIR setzen. Auf dem dev-Server: README,
Abschnitt „Beispielbestand (nur dev)“.

Der Katalog bleibt, wie er ist: Kategorien, Produkte, Formulare, Prüfpunkte, Dokumente, Produktbilder, Rückrufe und
Meldungen werden nur gelesen, nie geschrieben; einen DEMO-Katalog importiert das Skript nicht. Grundlage sind die
Produkte ohne DEMO-Kennzeichen außerhalb von DEMO-Kategorien – genau die, die der Katalog-Export mitnimmt. Alles
Fachliche (Prüfpunkte und Sollwerte, Intervalle, Lebensdauern, Hersteller, Produkte) kommt aus dem Katalog. Erfunden
sind nur Bestandsangaben, und die tragen „DEMO“: Ordner „DEMO-…“, Seriennummern „DEMO-…“, DEMO-Konten mit
@example.invalid, Bemerkungen „DEMO – nicht für echte Prüfungen“. Ein Wert, den ein Prüfpunkt verlangt und den nur
eine echte Prüfung liefern könnte (Messwert, Datum, Foto), wird nicht erfunden: Der Punkt steht auf „nicht zutreffend“
mit der DEMO-Bemerkung. Ein Mangel trägt die DEMO-Bemerkung und ein DEMO-Platzhalterfoto. Oberfläche, Protokolle,
Lebenslauf, CSV-Export und Steckbrief zeigen jeden Artikel einer DEMO-Gliederung als DEMO (bestand.demo_sql) – auch
wenn sein Produkt aus dem echten Katalog stammt.

Was danach gilt (deshalb vorher den Katalog exportieren – README):
  - Jede dabei benutzte Formularversion gilt als „benutzt“ und lässt sich nur noch über eine neue Version ändern.
  - Jedes Produkt, von dem es danach Artikel gibt, lässt sich nicht mehr löschen und seine Materialart nicht mehr
    ändern; seine Kategorie lässt sich nicht mehr löschen. Katalogpflege, die das braucht, vorher erledigen – oder
    später: Katalog exportieren, dev-Datenbank zurücksetzen, Export importieren.
  - Der Bestand lässt sich nicht wieder entfernen: Prüfnachweise werden nie gelöscht, Artikel mit Prüfungen auch nicht.
    Zurück geht es nur über das Zurücksetzen der dev-Datenbank.
  - Einmalig: Gibt es eine der Gliederungen schon, legt ein weiterer Lauf nichts an.

Alles läuft über die Dienste der App (bestand, pruefung, durchgang, zuordnung, unterschrift, freigaben) und in
Transaktionen – je Artikel eine samt seiner ganzen Prüfhistorie; scheitert ein Artikel, fehlt er ganz und steht im
Bericht. Im Journal steht als Akteur „Beispielbestand“, an den Prüfungen der DEMO-Prüfer. Die Konten legt das Skript
wie scripts/material_demo.py direkt an (ohne Anmeldung gibt es dafür keinen Dienst), mit Journaleintrag „rollen“ und
nur mit Zugang zum Modul Material.
"""
import io
import json
import os
import random
import sys
import time
from datetime import timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Im Container liegt das Skript unter /tmp, die App unter /srv (PYTHONPATH) und die Daten unter /data (DATA_DIR aus dem
# Abbild) – dann gilt beides von dort, nicht von hier.
if os.path.isfile(os.path.join(REPO_ROOT, "app", "__init__.py")):
    sys.path.insert(0, REPO_ROOT)
    os.environ.setdefault("DATA_DIR", os.path.join(REPO_ROOT, "data"))
    os.environ.setdefault("BASE_URL", "http://localhost:8080")          # wie run.py
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("VIDEOPFLEGE", "0")

HINWEIS = "DEMO – nicht für echte Prüfungen"
AKTEUR = "Beispielbestand"
# Vorgabe: gut 300 Protokolle in zweieinhalb bis drei Minuten (gemessen in der Sandbox: 200 Artikel, 305 Protokolle in
# 2:35 min; 240 Artikel, 385 Protokolle in 3:17 min).
VORGABE_ARTIKEL = 200
HOECHSTENS_ARTIKEL = 5000
SAAT = 20261018                      # gleicher Katalog, gleiche Verteilung – nachvollziehbar
POSTFACH = "example.invalid"
# Die Adresse der Produktion (BASE_URL) – dort legt das Skript nichts an, auch wenn es jemand in deren Container reicht.
PRODUKTION = {"strömis.de", "www.strömis.de", "xn--strmis-yxa.de", "www.xn--strmis-yxa.de"}

# Die Gliederungen: Kürzel (Seriennummern, Konten), Ort im Namen, Anteil am Bestand.
GLIEDERUNGEN = [("AU", "Auental", 0.40), ("BH", "Bachheim", 0.35), ("FS", "Flussstadt", 0.25)]
EINSATZKRAEFTE = 2                   # je Gliederung: DEMO-Personen mit persönlichem Ordner und Zuordnungen

# Ordnerbaum je Gliederung: (Schlüssel, Name, Ordnertyp, Oberordner, Gewicht beim Verteilen der Artikel). Dazu je
# DEMO-Einsatzkraft ein persönlicher Ordner unter „persoenlich“. Kein Ordner bekommt ein eigenes Prüfintervall – es
# gilt das aus dem Katalog.
ORDNER = [
    ("lager", "DEMO-Lager", "standort", None, 5),
    ("regal_a", "DEMO-Regal A", "sonstiges", "lager", 10),
    ("regal_b", "DEMO-Regal B", "sonstiges", "lager", 10),
    ("reserve", "DEMO-Reserve", "sonstiges", "lager", 5),
    ("fahrzeuge", "DEMO-Fahrzeuge", "sonstiges", None, 0),
    ("gw", "DEMO-GW-Wasserrettung", "fahrzeug", "fahrzeuge", 4),
    ("sr1", "DEMO-Seilrucksack 1", "set", "gw", 4),
    ("sr2", "DEMO-Seilrucksack 2", "set", "gw", 4),
    ("mtw", "DEMO-MTW", "fahrzeug", "fahrzeuge", 6),
    ("gruppen", "DEMO-Einsatzgruppen", "sonstiges", None, 0),
    ("gruppe1", "DEMO-Strömungsrettungsgruppe 1", "sonstiges", "gruppen", 8),
    ("gruppe2", "DEMO-Strömungsrettungsgruppe 2", "sonstiges", "gruppen", 8),
    ("persoenlich", "DEMO-Persönliche Ausrüstung", "sonstiges", None, 0),
]
GEWICHT_PERSON = 2
ZWEIG_ZU = ("gw", "sr1", "sr2")                             # abgeschlossener Durchgang (heute)
ZWEIG_OFFEN = ("lager", "regal_a", "regal_b", "reserve")    # offener Durchgang

# Anteile der Zustände an den Artikeln mit aktivem Formular (der Rest ist einsatzbereit); jeder kommt mindestens
# einmal vor, sofern es passende Artikel gibt. „lebensdauer…“ nur bei textilen Produkten mit Lebensdauer.
ANTEILE = [("lebensdauer", 0.03), ("aus_lebensdauer", 0.01), ("aus_mangel", 0.02), ("aus_verlust", 0.015),
           ("gesperrt", 0.04), ("verloren", 0.025), ("neu", 0.05), ("ueberfaellig", 0.12), ("bald", 0.10)]
FREIPRUEFUNG = 0.06                  # Anteil der einsatzbereiten mit Sperre und Freiprüfung in der Geschichte
# Gewichte für 1, 2, 3 oder 4 reguläre Prüfungen je Artikel. Jede Prüfung bekommt ihr Protokoll (gut eine halbe Sekunde
# je PDF) – das bestimmt die Laufzeit.
HISTORIE = (60, 28, 9, 3)


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


def produktion(adresse):
    """Zeigt BASE_URL auf die Produktion (auch in Punycode)?"""
    from urllib.parse import urlsplit
    host = (urlsplit(adresse or "").hostname or "").lower().rstrip(".")
    return host in PRODUKTION


def main(argv=None):
    try:
        n = schalter(sys.argv[1:] if argv is None else argv)
    except Abbruch as exc:
        print(__doc__)
        print(exc)
        sys.exit(exc.code)
    from flask import g

    from app import create_app

    app = create_app()
    with app.app_context():
        g.mat_akteur = AKTEUR
        try:
            Beispielbestand(app, n).anlegen()
        except Abbruch as exc:
            print(exc)
            sys.exit(exc.code)
        except Exception:
            print("Abgebrochen mit einem Fehler (unten). Was bis dahin fertig war, bleibt – jeder Artikel ganz oder gar "
                  "nicht; ein neuer Lauf legt nichts mehr an, solange es die Gliederungen gibt.", flush=True)
            raise


# --- Bilder: DEMO-Unterschrift und DEMO-Mangelfoto -----------------------------------------------------------------------

def unterschrift_uri(saat=0):
    """Eine gezeichnete Platzhalter-Unterschrift mit „DEMO“ als data:-URL, wie sie das Signatur-Pad liefert (wie
    demo_unterschrift in scripts/material_demo.py); saat variiert den Schwung je Person."""
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
    def __init__(self, app, n):
        from app.material.services import heute
        from app.material.services import status as st
        self.app, self.n = app, n
        self.h = heute()                    # Kalendertag in Deutschland, wie überall im Modul
        self.schwelle = st.schwelle_tage()
        self.rnd = random.Random(SAAT)
        self.gl = []                        # je Gliederung: kurz, ort, name, id, ordner{schlüssel: id}, konto{rolle: …}
        self.passwoerter = []
        self.uebersprungen = []
        self.zuordnungen = 0
        self._foto = None
        self._signatur = None

    # --- Vorprüfungen ---

    @staticmethod
    def namen():
        return [f"DEMO-OG {ort}" for _, ort, _ in GLIEDERUNGEN]

    def schon_da(self):
        from app import db
        return [r["name"] for r in db.query(
            f"SELECT name FROM mat_folder WHERE parent_id IS NULL AND demo = 1 AND name IN "
            f"({','.join('?' * len(GLIEDERUNGEN))}) ORDER BY id", self.namen())]

    def produkte(self):
        """Die echten Produkte: ohne DEMO-Kennzeichen, nicht in einer DEMO-Kategorie (wie beim Katalog-Export) und mit
        Prüfintervall (ohne lässt sich kein Artikel anlegen) – je mit Intervall, Lebensdauer (nur textil, wie retire_by)
        und aktivem Formular aus dem Katalog. Liefert (verwendbar, ausgelassen mit Grund)."""
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
            monate = herstellerseite(p)[0]
            if not monate:
                ausgelassen.append(f"{name} (kein Prüfintervall im Katalog)")
                continue
            f = katalog.formular_fuer_produkt(p["id"])
            gut.append({"id": p["id"], "name": name, "monate": monate,
                        "lebensdauer": p["lifetime_years"] if p["material_kind"] == "textil" else None,
                        "formular": f, "punkte": katalog.punkte(f["id"]) if f else []})
        return gut, ausgelassen

    # --- Ablauf ---

    def anlegen(self):
        from app import db
        start = time.monotonic()
        print(f"Datenbank: {self.app.config['DB_PATH']} · Adresse: {self.app.config['BASE_URL']} · Stichtag: "
              f"{self.h.strftime('%d.%m.%Y')}")
        if produktion(self.app.config["BASE_URL"]):
            raise Abbruch("Abgebrochen: Das ist die Adresse der Produktion – der Beispielbestand gehört nur auf dev. "
                          "Nichts angelegt.")
        da = self.schon_da()
        if da:
            print(f"Beispielbestand ist schon da ({', '.join(da)}) – nichts angelegt. Er lässt sich nicht entfernen; "
                  "neu anlegen geht nur mit einer zurückgesetzten dev-Datenbank.")
            return
        produkte, ausgelassen = self.produkte()
        if not produkte:
            raise Abbruch("Abgebrochen: Im Katalog gibt es keine echten Produkte (ohne DEMO-Kennzeichen, mit "
                          "Prüfintervall) – der Beispielbestand nimmt nur Produkte aus dem vorhandenen Katalog. Erst den "
                          "Katalog importieren." + (f" Nicht verwendbar: {'; '.join(ausgelassen)}." if ausgelassen else ""))
        roh = self._gliederungen_roh()
        mails = [k["mail"] for gl in roh for k in gl["konten"]]
        belegt = db.query(f"SELECT email FROM users WHERE email IN ({','.join('?' * len(mails))})", mails)
        if belegt:
            raise Abbruch("Abgebrochen: Diese DEMO-Konten gibt es schon – " + ", ".join(r["email"] for r in belegt)
                          + ". Nichts angelegt.")
        for gl in roh:
            self.gliederung_anlegen(gl)
        print(f"Gliederungen: {', '.join(self.namen())} – mit Ordnerbaum, Konten und Freigaben.")
        plaene = self.planen(produkte)
        print(f"Artikel: {len(plaene)} über {len({p['produkt']['id'] for p in plaene})} Produkte – lege an und prüfe "
              "(jede Prüfung bekommt ihr Protokoll) …", flush=True)
        for k, plan in enumerate(plaene, 1):
            self.artikel_anlegen(plan)
            if k % 25 == 0:
                print(f"  … {k} von {len(plaene)} Artikeln ({self._dauer(start)})", flush=True)
        for gl in self.gl:
            self.durchgaenge(gl, plaene)
        self.zuordnen(plaene)
        self.bericht(plaene, produkte, ausgelassen, start)

    @staticmethod
    def _dauer(start):
        s = int(time.monotonic() - start)
        return f"{s // 60}:{s % 60:02d} min"

    # --- Gliederungen, Ordner und Konten ---

    @staticmethod
    def _gliederungen_roh():
        out = []
        for kurz, ort, anteil in GLIEDERUNGEN:
            k = kurz.lower()
            konten = [
                {"rolle": "wart", "mail": f"demo-wart-{k}@{POSTFACH}", "name": f"DEMO-Materialwart {ort}"},
                {"rolle": "pruefer", "mail": f"demo-pruefer-{k}@{POSTFACH}", "name": f"DEMO-Prüferin {ort}",
                 "urkunde": f"DEMO-{kurz}-1012"},
                {"rolle": "mitglied", "mail": f"demo-mitglied-{k}@{POSTFACH}", "name": f"DEMO-Mitglied {ort}"},
                {"rolle": "extern", "mail": f"demo-extern-{k}@{POSTFACH}", "name": f"DEMO-Prüfer extern {ort}",
                 "urkunde": f"DEMO-{kurz}-2024"},
            ] + [{"rolle": f"person{n}", "mail": f"demo-einsatzkraft-{k}-{n}@{POSTFACH}",
                  "name": f"DEMO-Einsatzkraft {ort} {n}"} for n in range(1, EINSATZKRAEFTE + 1)]
            out.append({"kurz": kurz, "ort": ort, "anteil": anteil, "name": f"DEMO-OG {ort}", "konten": konten})
        return out

    def gliederung_anlegen(self, roh):
        """Ordnerbaum, Konten und Freigaben einer Gliederung – in einer Transaktion."""
        from app import db
        from app.material.services import bestand
        gl = dict(roh, ordner={}, konto={})
        with db.transaction(sofort=True):
            gl["id"] = bestand.ordner_anlegen({"name": gl["name"], "kind": "gliederung", "description":
                                               f"{HINWEIS}. Beispielbestand aus dem Katalog "
                                               "(scripts/material_beispielbestand.py)."}, demo=True)
            for schluessel, name, art, oben, _ in ORDNER:
                gl["ordner"][schluessel] = bestand.ordner_anlegen(
                    {"name": name, "kind": art, "parent_id": gl["ordner"][oben] if oben else gl["id"]}, demo=True)
            for n in range(1, EINSATZKRAEFTE + 1):
                gl["ordner"][f"person{n}"] = bestand.ordner_anlegen(
                    {"name": f"DEMO-Einsatzkraft {gl['ort']} {n}", "kind": "persoenlich",
                     "parent_id": gl["ordner"]["persoenlich"]}, demo=True)
            for k in gl["konten"]:
                gl["konto"][k["rolle"]] = self.konto_anlegen(k, gl)
            self.freigaben(gl)
        self.gl.append(gl)

    def konto_anlegen(self, k, gl):
        """Ein DEMO-Konto nur für das Modul Material (Karte, Wiki, Prüfungen und Verwaltung aus) mit zufälligem Passwort –
        wie in scripts/material_demo.py direkt, mit dem Journaleintrag „rollen“ wie in der Nutzerverwaltung. Prüfer
        (Häkchen und Urkundennummer) und Materialwart hinterlegen ihre DEMO-Unterschrift über den Dienst des Profils.
        users.recht_material = 1 (Mitglied): Heute wirkt die Stufe nicht, ein späterer Umbau liest sie wieder."""
        import secrets

        from werkzeug.security import generate_password_hash

        from app import db
        from app.material.services import journal, unterschrift
        passwort = secrets.token_urlsafe(12)
        urkunde = k.get("urkunde", "")
        uid = db.execute(
            "INSERT INTO users (email, password_hash, name, gliederung, recht_karte, recht_wiki, recht_pruefungen, "
            "recht_verwaltung, recht_material, mat_pruefer, mat_katalog, urkundennummer, created_at) "
            "VALUES (?,?,?,?,0,0,0,0,1,?,0,?,?)",
            (k["mail"], generate_password_hash(passwort), k["name"], gl["name"], int(bool(urkunde)), urkunde, db.now()))
        journal.eintragen("user", uid, "rollen", None, {"recht_material": 1, "mat_pruefer": int(bool(urkunde)),
                                                        "mat_katalog": 0, "urkundennummer": urkunde})
        if urkunde or k["rolle"] == "wart":
            unterschrift.setzen({"id": uid}, unterschrift_uri(uid))
        self.passwoerter.append((k["mail"], k["name"], passwort))
        return {"id": uid, "mail": k["mail"], "name": k["name"]}

    def freigaben(self, gl):
        """Materialwart: verwalten an der Gliederung (dauerhaft); Prüferin: lesen und prüfen (Prüffreigabe bis 31.12. des
        Folgejahres); Mitglied: lesen; externer Prüfer: nur prüfen im Lager, 30 Tage (zeigt „läuft bald ab“). Über den
        Schreibweg des Freigaben-Dienstes mit den Rechten der Plattform-Verwaltung – Prüffreigaben nur an qualifizierte
        Konten, höchstens 24 Monate; im Journal unter „Beispielbestand“, die Konten nur als Kontoverweis."""
        from app.material.services import freigaben, rechte
        plattform = rechte.Sicht(uid=None, alles=True, qualifiziert=False)
        extern_bis = (self.h + timedelta(days=30)).isoformat()
        for rolle, ordner, recht, ende in (("wart", gl["id"], "verwalten", None), ("pruefer", gl["id"], "lesen", None),
                                           ("pruefer", gl["id"], "pruefen", freigaben.vorgabe_bis()),
                                           ("mitglied", gl["id"], "lesen", None),
                                           ("extern", gl["ordner"]["lager"], "pruefen", extern_bis)):
            konto = rechte.waehlbares_konto(gl["konto"][rolle]["id"])
            neu = {"user_id": konto["id"], "permission": recht, "valid_until": freigaben._bis(ende, recht),
                   "note": "DEMO"}
            freigaben._schreiben(plattform, {"id": None}, ordner, None, neu, konto)
        rechte.sicht_verwerfen()

    @staticmethod
    def pruefer(uid):
        """Prüfer (oder aussondernder Materialwart) aus seinem Konto – wie nach einer Anmeldung (pruefer_aus): Name,
        Urkundennummer, Unterschrift aus dem Profil, Anmeldung."""
        from app import db
        from app.material.services import pruefung
        return pruefung.pruefer_aus(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True))

    # --- Plan: welcher Artikel wohin, mit welchem Zustand ---

    def planen(self, produkte):
        rnd = self.rnd
        # Artikel je Produkt: gleich viele, der Rest zufällig; jedes Produkt mindestens einmal, sofern n reicht.
        auswahl = list(produkte)
        if self.n < len(auswahl):
            rnd.shuffle(auswahl)
            auswahl = auswahl[:self.n]
            self.uebersprungen.append(f"Nur {self.n} von {len(produkte)} Produkten bekommen Artikel (--artikel).")
        je = [self.n // len(auswahl)] * len(auswahl)
        for k in rnd.sample(range(len(auswahl)), self.n % len(auswahl)):
            je[k] += 1
        plaene = [{"produkt": p, "zustand": None} for p, m in zip(auswahl, je) for _ in range(m)]
        rnd.shuffle(plaene)
        # Gliederung nach Anteil (gleichmäßig durchmischt), darin der Ordner nach Gewicht.
        anteile = [a for _, _, a in GLIEDERUNGEN]
        ziele = [(s, gw) for s, _, _, _, gw in ORDNER if gw] + [
            (f"person{n}", GEWICHT_PERSON) for n in range(1, EINSATZKRAEFTE + 1)]
        for k, plan in enumerate(plaene):
            plan["nr"] = k + 1
            plan["gl"] = self._nach_anteil((k + 0.5) / len(plaene), anteile)
            plan["ordner"] = self._nach_gewicht(ziele)
        # Beide Durchgänge brauchen prüfbare Artikel: mindestens 2 mit Formular im Zweig des GW, 4 im Lager (sofern die
        # Gliederung so viele hat) – nachgezogen aus den übrigen Ordnern, Artikel mit Formular zuerst.
        for gi in range(len(self.gl)):
            eigene = [p for p in plaene if p["gl"] == gi]
            for zweig, ziel, mindest in ((ZWEIG_ZU, "gw", 2), (ZWEIG_OFFEN, "regal_a", 4)):
                fehlen = mindest - sum(1 for p in eigene if p["ordner"] in zweig and p["produkt"]["formular"])
                rest = [p for p in eigene if p["ordner"] not in ZWEIG_ZU + ZWEIG_OFFEN]
                rest.sort(key=lambda p: not p["produkt"]["formular"])
                for p in rest[:max(0, fehlen)]:
                    p["ordner"] = ziel
        # Ohne aktives Formular gibt es keine Prüfung: neu. Nur wenn kein Produkt mit Formular eine Lebensdauer hat, steht
        # ein Artikel eines textilen Produkts mit Lebensdauer ohne Prüfung auf „Lebensdauer erreicht“ – sonst käme der
        # Zustand nicht vor (der Bericht nennt ihn).
        ohne = [p for p in plaene if not p["produkt"]["formular"]]
        for p in ohne:
            p["zustand"] = "neu"
        textil_ohne = [p for p in ohne if p["produkt"]["lebensdauer"] and p["ordner"] not in ZWEIG_ZU]
        if textil_ohne and not any(p["produkt"]["lebensdauer"] and p["produkt"]["formular"] for p in plaene):
            textil_ohne[0]["zustand"] = "lebensdauer"
        # Im Zweig des abgeschlossenen Durchgangs wird heute geprüft – dort steht alles mit Formular zur Prüfung an.
        for p in plaene:
            if p["zustand"] is None and p["ordner"] in ZWEIG_ZU:
                p["zustand"] = "durchgang_zu"
        frei = [p for p in plaene if p["zustand"] is None]
        rnd.shuffle(frei)              # die Gliederung folgt der Reihenfolge in plaene – die Zustände nicht
        anzahl = len(frei)
        for zustand, anteil in ANTEILE:
            pool = [p for p in frei if p["zustand"] is None and (
                p["produkt"]["lebensdauer"] or zustand not in ("lebensdauer", "aus_lebensdauer"))]
            for p in pool[:max(1, round(anzahl * anteil))]:
                p["zustand"] = zustand
        for p in frei:
            if p["zustand"] is None:
                p["zustand"] = "einsatzbereit"
                p["freipruefung"] = rnd.random() < FREIPRUEFUNG
        # Der offene Durchgang im Lager: ein Drittel der Einsatzbereiten heute geprüft (mindestens einer), einer in
        # Prüfung (Entwurf des externen Prüfers), einer mit Grund ausgenommen, der Rest offen. Hat das Lager zu wenige
        # Einsatzbereite, tauscht es Zustände mit Einsatzbereiten aus anderen Ordnern (derselben Gliederung zuerst) –
        # die Verteilung der Zustände bleibt; nur wenn es gar keine gibt, wird einer einsatzbereit.
        for gi in range(len(self.gl)):
            lager = [p for p in plaene if p["gl"] == gi and p["ordner"] in ZWEIG_OFFEN]
            bereit = [p for p in lager if p["zustand"] == "einsatzbereit" and not p.get("freipruefung")]
            draussen = [p for p in plaene if p["ordner"] not in ZWEIG_OFFEN + ZWEIG_ZU
                        and p["zustand"] == "einsatzbereit" and not p.get("freipruefung")]
            draussen.sort(key=lambda p: p["gl"] == gi)              # pop() nimmt die eigene Gliederung zuerst
            tauschbar = [p for p in lager if p["produkt"]["formular"] and p["zustand"] in (
                "neu", "ueberfaellig", "bald", "gesperrt", "verloren", "aus_mangel", "aus_verlust")]
            while len(bereit) < 2 and draussen and tauschbar:
                a, b = tauschbar.pop(), draussen.pop()
                a["zustand"], b["zustand"] = b["zustand"], a["zustand"]
                bereit.append(a)
            if not bereit and tauschbar:
                bereit.append(tauschbar.pop())
                bereit[0]["zustand"] = "einsatzbereit"
            for p in bereit[:max(1, len(bereit) // 3)]:
                p["zustand"], p["durchgang"] = "faellig", "erledigt"
            faellig = [p for p in lager if p["zustand"] in ("ueberfaellig", "bald")] + [
                p for p in lager if p["zustand"] == "einsatzbereit" and "durchgang" not in p]
            if faellig:
                faellig[0]["durchgang"] = "entwurf"
            rest = [p for p in lager if p["zustand"] in ("einsatzbereit", "ueberfaellig", "bald")
                    and "durchgang" not in p]
            if rest:
                rest[-1]["durchgang"] = "ausgenommen"
        return plaene

    @staticmethod
    def _nach_anteil(x, anteile):
        summe = 0.0
        for i, a in enumerate(anteile):
            summe += a
            if x < summe:
                return i
        return len(anteile) - 1

    def _nach_gewicht(self, ziele):
        x = self.rnd.random() * sum(g for _, g in ziele)
        for s, g in ziele:
            x -= g
            if x < 0:
                return s
        return ziele[-1][0]

    # --- Termine ---

    def _tag(self, von, bis):
        """Ein zufälliger Tag zwischen von und bis (beide eingeschlossen)."""
        if bis <= von:
            return von
        return von + timedelta(days=self.rnd.randint(0, (bis - von).days))

    def _letzte(self, monate, faellig_von, faellig_bis):
        """Tag der letzten Prüfung vor heute, sodass ihre Fälligkeit (Prüftag + Intervall aus dem Katalog) zwischen
        faellig_von und faellig_bis liegt."""
        from app.material.services.interval import plus_monate
        for _ in range(20):
            letzte = plus_monate(self._tag(faellig_von, faellig_bis), -monate)
            if letzte < self.h and faellig_von <= plus_monate(letzte, monate) <= faellig_bis:
                return letzte
        return min(plus_monate(faellig_von, -monate), self.h - timedelta(days=1))

    def _kette(self, letzte, monate, anzahl):
        """anzahl Prüftage: der letzte ist letzte, davor im Abstand des Intervalls (meist ein paar Tage früher)."""
        from app.material.services.interval import plus_monate
        tage = [letzte]
        for _ in range(anzahl - 1):
            frueher = plus_monate(tage[0], -monate) + timedelta(days=self.rnd.randint(0, 20))
            tage.insert(0, min(frueher, tage[0] - timedelta(days=14)))
        return tage

    def termine(self, plan):
        """Stammdaten (Herstellung, Kauf, Erstgebrauch) und die Ereignisse des Artikels in ihrer Reihenfolge: (Tag,
        Prüfart, Ergebnis, Mangel) für Prüfungen, (heute, „verlust“, …) für die Sperre bei Verlust und (heute,
        „aussondern“, …) für die Aussonderung durch den Materialwart. Intervall und Lebensdauer aus dem Katalog."""
        from app.material.services.interval import plus_jahre, plus_monate
        rnd, h, p = self.rnd, self.h, plan["produkt"]
        m, zustand, jahre = p["monate"], plan["zustand"], p["lebensdauer"]
        if zustand == "neu":
            kauf = h - timedelta(days=rnd.randint(0, 60 if p["formular"] else 900))
            return self._stamm(plan, kauf, None, h), []
        if zustand in ("lebensdauer", "aus_lebensdauer"):
            return self._termine_lebensende(plan)
        bald_bis = h + timedelta(days=max(1, self.schwelle - 3))
        spaeter = None
        if zustand == "einsatzbereit":
            letzte = self._letzte(m, h + timedelta(days=self.schwelle + 10), plus_monate(h - timedelta(days=3), m))
        elif zustand == "bald":
            letzte = self._letzte(m, h + timedelta(days=1), bald_bis)
        elif zustand == "ueberfaellig":
            letzte = self._letzte(m, h - timedelta(days=240), h - timedelta(days=1))
        elif zustand in ("faellig", "durchgang_zu"):
            letzte = self._letzte(m, h - timedelta(days=60), bald_bis)
        elif zustand in ("gesperrt", "aus_mangel"):
            spaeter = h - timedelta(days=rnd.randint(3, 90) if zustand == "gesperrt" else rnd.randint(5, 300))
            letzte = spaeter - timedelta(days=rnd.randint(20, max(21, m * 30 - 10)))
        else:                                                          # verloren, aus_verlust
            letzte = h - timedelta(days=rnd.randint(10, max(11, min(330, m * 30 - 10))))
        tage = self._kette(letzte, m, rnd.choices(range(1, len(HISTORIE) + 1), weights=HISTORIE)[0])
        if jahre:
            # Textil: Das Lebensende (Herstellung + Lebensdauer) bleibt mehr als 60 Tage vor uns – die Geschichte reicht
            # also nicht weiter zurück, als die Lebensdauer erlaubt.
            frueheste = plus_jahre(h + timedelta(days=60), -jahre) + timedelta(days=62)
            while len(tage) > 1 and tage[0] < frueheste:
                tage.pop(0)
        ereignisse = self._pruefungen(tage, plan.get("freipruefung"))
        if spaeter:
            ereignisse.append((spaeter, self._art(tage[-1], spaeter, m),
                               "instandsetzen" if zustand == "gesperrt" else "aussondern",
                               "mangel" if zustand == "gesperrt" else "kritisch"))
        elif zustand in ("verloren", "aus_verlust"):
            ereignisse.append((h, "verlust", None, None))
            if zustand == "aus_verlust":
                ereignisse.append((h, "aussondern", None, None))
        return self._stamm(plan, tage[0] - timedelta(days=rnd.randint(0, 20)), tage[0], h), ereignisse

    def _termine_lebensende(self, plan):
        """Textil mit Lebensdauer: Herstellung so lange her, dass das Lebensende zwischen 5 und 300 Tagen zurückliegt.
        Geprüft wurde vorher; „aus_lebensdauer“ endet mit einer Prüfung danach, Ergebnis „aussondern“."""
        from app.material.services.interval import plus_jahre
        rnd, h, p = self.rnd, self.h, plan["produkt"]
        m, jahre = p["monate"], p["lebensdauer"]
        herstellung = plus_jahre((h - timedelta(days=rnd.randint(5, 300))).replace(day=1), -jahre)
        ende = plus_jahre(herstellung, jahre)
        if not p["formular"]:
            return self._stamm(plan, herstellung + timedelta(days=rnd.randint(20, 200)), None, h, herstellung), []
        letzte = ende - timedelta(days=rnd.randint(20, max(21, min(200, m * 30 - 20))))
        tage = self._kette(letzte, m, rnd.choices(range(1, len(HISTORIE) + 1), weights=HISTORIE)[0])
        while len(tage) > 1 and tage[0] < herstellung + timedelta(days=60):
            tage.pop(0)
        tage[0] = max(tage[0], herstellung + timedelta(days=30))
        ereignisse = self._pruefungen(tage)
        if plan["zustand"] == "aus_lebensdauer":
            tag = self._tag(ende, h)
            ereignisse.append((tag, self._art(tage[-1], tag, m), "aussondern", None))
        return self._stamm(plan, tage[0] - timedelta(days=rnd.randint(0, 20)), tage[0], h, herstellung), ereignisse

    def _art(self, vorher, tag, monate):
        """Prüfart einer Prüfung am Tag tag nach der letzten am Tag vorher – wie der Vorschlag der App
        (pruefung.arten_fuer): periodisch, sobald der Artikel fällig oder bald fällig ist, sonst außerplanmäßig (ein
        Mangel, der zwischen zwei Prüfungen auffällt)."""
        from app.material.services.interval import plus_monate
        return "periodisch" if (plus_monate(vorher, monate) - tag).days <= self.schwelle else "ausserplanmaessig"

    def _pruefungen(self, tage, freipruefung=False):
        """Reguläre Prüfungen an diesen Tagen – die erste ist die Eingangsprüfung. Mit freipruefung endet eine davon mit
        einem Mangel („instandsetzen“), ein paar Tage später gibt eine Prüfung nach Reparatur den Artikel wieder frei."""
        ereignisse = [(t, "eingang" if k == 0 else "periodisch", "einsatzbereit", None) for k, t in enumerate(tage)]
        if freipruefung:
            for k in range(len(tage) - 1):
                luecke = (tage[k + 1] - tage[k]).days
                if luecke >= 30:
                    ereignisse[k] = (tage[k], ereignisse[k][1], "instandsetzen", "mangel")
                    reparatur = tage[k] + timedelta(days=self.rnd.randint(3, min(20, luecke - 10)))
                    ereignisse.insert(k + 1, (reparatur, "reparatur", "einsatzbereit", None))
                    break
        return ereignisse

    def _stamm(self, plan, kauf, erstgebrauch, spaetester, herstellung=None):
        """Herstellung (Monat), Kauf und Erstgebrauch – erfundene Bestandsangaben, passend zur Geschichte. Ohne
        vorgegebene Herstellung liegt sie 1 bis 15 Monate vor dem Kauf; bei textilem Material so, dass das Lebensende
        mehr als 60 Tage nach spaetester liegt (sonst so spät wie möglich: im Monat des Kaufs)."""
        from app.material.services.interval import plus_jahre, plus_monate
        p = plan["produkt"]
        if herstellung is None:
            herstellung = plus_monate(kauf.replace(day=1), -self.rnd.randint(1, 15))
            while p["lebensdauer"] and herstellung < kauf.replace(day=1) and \
                    plus_jahre(herstellung, p["lebensdauer"]) <= spaetester + timedelta(days=60):
                herstellung = plus_monate(herstellung, 1)
        kauf = max(kauf, herstellung)
        return {"manufactured_on": herstellung.strftime("%Y-%m"), "purchased_on": kauf.isoformat(),
                "first_use_on": erstgebrauch.isoformat() if erstgebrauch else None}

    # --- Artikel samt Geschichte ---

    def artikel_anlegen(self, plan):
        """Den Artikel mit seiner ganzen Geschichte in EINER Transaktion – scheitert etwas (etwa ein Formular, das sich
        so nicht ausfüllen lässt), fehlt der Artikel ganz und steht im Bericht."""
        from app import db
        from app.material.services import Abgelehnt, bestand, protokoll
        gl = self.gl[plan["gl"]]
        stamm, ereignisse = self.termine(plan)
        fotos = []
        plan["iid"] = None
        try:
            with protokoll.dateien_sichern(), db.transaction(sofort=True):
                iid = bestand.artikel_anlegen(dict(
                    stamm, product_id=plan["produkt"]["id"], folder_id=gl["ordner"][plan["ordner"]],
                    serial_no=f"DEMO-{gl['kurz']}-{plan['nr']:04d}", notes=HINWEIS))
                for e in ereignisse:
                    self.ereignis(iid, plan, e, fotos)
        except Abgelehnt as exc:
            self._fotos_weg(fotos)
            self.uebersprungen.append(f"Artikel {plan['produkt']['name']} ({plan['zustand']}): {exc}")
            return
        except BaseException:
            self._fotos_weg(fotos)
            raise
        plan["iid"] = iid

    @staticmethod
    def _fotos_weg(fotos):
        """Mangelfotos eines zurückgerollten Vorgangs – ihre Dateien liegen schon, ihre Zeilen nicht mehr."""
        from app.images import delete_photo_files
        from app.material.services import katalog
        for name in fotos:
            delete_photo_files(katalog.medien_dir(), name)

    def _pruefer_fuer(self, plan):
        """Wer prüft: die Prüferin der Gliederung, im Lager auch der externe Prüfer (seine Prüffreigabe gilt nur dort)."""
        gl = self.gl[plan["gl"]]
        kandidaten = [gl["konto"]["pruefer"]["id"]]
        if plan["ordner"] in ZWEIG_OFFEN:
            kandidaten.append(gl["konto"]["extern"]["id"])
        return self.pruefer(self.rnd.choice(kandidaten))

    def ereignis(self, iid, plan, e, fotos):
        from app.material.services import pruefung
        tag, art, ergebnis, mangel = e
        if art == "verlust":
            pruefung.sperren(iid, {"grund": "verlust", "text": HINWEIS}, self._pruefer_fuer(plan))
        elif art == "aussondern":
            wart = self.pruefer(self.gl[plan["gl"]]["konto"]["wart"]["id"])
            pruefung.aussondern(iid, {"grund": "verlust", "bemerkung": HINWEIS}, wart)
        else:
            self.pruefen(iid, self._pruefer_fuer(plan), art, ergebnis, mangel, tag, fotos)

    def pruefen(self, iid, pruefer, art, ergebnis, mangel, tag, fotos, durchgang_id=None, abschliessen=True):
        """Eine Prüfung über den Prüfdienst: Entwurf mit den Prüfpunkten des aktiven Formulars (vorbelegt mit ihrem Soll),
        ausfüllen, abschließen und festschreiben (Protokoll) – mit dem Prüftag tag (None: heute)."""
        from app.material.services import pruefung
        pid, _ = pruefung.starten(iid, pruefer, art, durchgang_id)
        self.befunde(pid, pruefer, mangel, fotos)
        if not abschliessen:
            return pid
        d = {"ergebnis": ergebnis, "bemerkung": HINWEIS}
        if ergebnis == "aussondern" and not mangel:
            d["grund"] = f"Lebensdauer erreicht ({HINWEIS})"
        elif ergebnis != "einsatzbereit":
            d["grund"] = HINWEIS
        pruefung.abschliessen(pid, d, pruefer, pruefdatum=tag)
        return pid

    def befunde(self, pid, pruefer, mangel, fotos):
        """Die Prüfpunkte aus dem Katalog: Ja/Nein und Zahlen mit Sollwert stehen schon auf ihrem Soll. Ein Pflichtpunkt,
        dessen Wert nur eine echte Prüfung liefert (Messwert, Datum, Foto), steht auf „nicht zutreffend“ mit der
        DEMO-Bemerkung; ein Pflicht-Textfeld bekommt die DEMO-Bemerkung als Wert, ein Pflicht-Unterschriftsfeld die
        DEMO-Unterschrift. mangel („mangel“ oder „kritisch“): ein Punkt weicht vom Soll ab – mit DEMO-Bemerkung und
        DEMO-Platzhalterfoto, wie es jeder Mangel braucht."""
        from werkzeug.datastructures import FileStorage

        from app import db
        from app.material.services import pruefung
        punkte = pruefung.befunde(pid)
        ziel = self._mangelpunkt(punkte, mangel == "kritisch") if mangel else None
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
                if r["mandatory"] and not (r["value"] or "").strip():
                    pruefung.punkt_setzen(pid, r["id"], {"wert": HINWEIS}, pruefer)
            elif r["editor"] in ("number", "date", "photo"):
                beantwortet = r["photo"] if r["editor"] == "photo" else (r["value"] or "").strip()
                if r["mandatory"] and not beantwortet:
                    pruefung.punkt_setzen(pid, r["id"], {"befund": "nicht_zutreffend", "notiz": HINWEIS}, pruefer)

    @staticmethod
    def _mangelpunkt(punkte, kritisch):
        """Der Punkt, an dem ein Mangel steht: ein kritischer Ja/Nein-Punkt (wenn verlangt), sonst irgendein
        Ja/Nein-Punkt, sonst der erste Punkt, der einen Befund kennt (kein Unterschriftsfeld)."""
        janein = [r for r in punkte if r["editor"] == "yesno"]
        for liste in ([r for r in janein if r["is_critical"]] if kritisch else [], janein,
                      [r for r in punkte if r["editor"] != "signature"]):
            if liste:
                return liste[0]
        return None

    # --- Prüfdurchgänge ---

    def durchgaenge(self, gl, plaene):
        """Je Gliederung: ein heute abgeschlossener Durchgang im GW-Wasserrettung (mit Sammelprotokoll; ein Artikel mit
        Mangel, Artikel ohne Formular ausgenommen) und ein offener im Lager – teils erledigt, einer in Prüfung beim
        externen Prüfer, einer ausgenommen, der Rest offen."""
        from app.material.services import Abgelehnt, durchgang
        wart = self.pruefer(gl["konto"]["wart"]["id"])
        eigene = {p["iid"]: p for p in plaene if p["iid"] and self.gl[p["gl"]] is gl}
        jahr = self.h.year
        try:
            rid = durchgang.eroeffnen(gl["ordner"]["gw"], {"titel": f"DEMO-Jahresprüfung GW-Wasserrettung {jahr}"},
                                      wart)
        except Abgelehnt as exc:
            self.uebersprungen.append(f"{gl['name']}: kein abgeschlossener Durchgang – {exc}")
            rid = None
        if rid:
            mangel_offen = True
            for iid in self._im_durchgang(rid):
                plan = eigene.get(iid)
                if plan and plan["zustand"] == "durchgang_zu":
                    mangel = "mangel" if mangel_offen else None
                    mangel_offen = False
                    self._im_durchgang_pruefen(iid, plan, rid, "instandsetzen" if mangel else "einsatzbereit", mangel)
                else:
                    grund = (f"{HINWEIS}: kein aktives Prüfformular im Katalog" if plan and not plan["produkt"]["formular"]
                             else f"{HINWEIS}: nicht auffindbar")
                    durchgang.ausnehmen(rid, iid, {"grund": grund}, wart)
            durchgang.abschliessen(rid, wart)
        try:
            rid = durchgang.eroeffnen(gl["ordner"]["lager"], {"titel": f"DEMO-Prüfdurchgang Lager {jahr}"}, wart)
        except Abgelehnt as exc:
            self.uebersprungen.append(f"{gl['name']}: kein offener Durchgang – {exc}")
            return
        for iid in self._im_durchgang(rid):
            plan = eigene.get(iid) or {}
            if plan.get("durchgang") == "erledigt":
                self._im_durchgang_pruefen(iid, plan, rid, "einsatzbereit", None)
            elif plan.get("durchgang") == "entwurf":
                extern = self.pruefer(gl["konto"]["extern"]["id"])
                self.pruefen(iid, extern, "periodisch", None, None, None, [], rid, abschliessen=False)
            elif plan.get("durchgang") == "ausgenommen":
                durchgang.ausnehmen(rid, iid, {"grund": f"{HINWEIS}: in Reparatur beim Hersteller"}, wart)

    @staticmethod
    def _im_durchgang(rid):
        from app import db
        return [r["item_id"] for r in db.query("SELECT ri.item_id FROM mat_round_item ri JOIN mat_item i ON i.id = "
                                                "ri.item_id WHERE ri.round_id = ? ORDER BY i.inventory_no", (rid,))]

    def _im_durchgang_pruefen(self, iid, plan, rid, ergebnis, mangel):
        from app import db
        from app.material.services import Abgelehnt, protokoll
        fotos = []
        try:
            with protokoll.dateien_sichern(), db.transaction(sofort=True):
                self.pruefen(iid, self._pruefer_fuer(plan), "periodisch", ergebnis, mangel, None, fotos, rid)
        except Abgelehnt as exc:
            self._fotos_weg(fotos)
            self.uebersprungen.append(f"Durchgang, {plan['produkt']['name']}: {exc}")
        except BaseException:
            self._fotos_weg(fotos)
            raise

    # --- Zuordnungen ---

    def zuordnen(self, plaene):
        """Was in einem persönlichen Ordner liegt, gehört dieser DEMO-Person; dazu gut ein Drittel der Einsatzgruppen.
        Über den Schreibweg der Personenzuordnung (Journal am Artikel mit Kontoverweis); Ausgesonderte nicht."""
        from app import db
        from app.material.services import bestand, rechte, zuordnung
        for gi, gl in enumerate(self.gl):
            personen = [gl["konto"][f"person{n}"]["id"] for n in range(1, EINSATZKRAEFTE + 1)]
            with db.transaction(sofort=True):
                for p in plaene:
                    if p["gl"] != gi or not p["iid"]:
                        continue
                    if p["ordner"].startswith("person"):
                        uid = gl["konto"][p["ordner"]]["id"]
                    elif p["ordner"] in ("gruppe1", "gruppe2") and self.rnd.random() < 0.4:
                        uid = self.rnd.choice(personen)
                    else:
                        continue
                    i = bestand.artikel(p["iid"])
                    if i["lock_state"] != "ausgesondert" and zuordnung._schreiben(i, rechte.waehlbares_konto(uid)["id"]):
                        self.zuordnungen += 1

    # --- Bericht ---

    def bericht(self, plaene, produkte, ausgelassen, start):
        from app import db
        from app.material.services import bestand
        from app.material.services import status as st
        ids = json.dumps([p["iid"] for p in plaene if p["iid"]])
        artikel = db.query("SELECT * FROM mat_item WHERE id IN (SELECT value FROM json_each(?))", (ids,))
        zaehlung = st.leere_zaehlung()
        for i in artikel:
            zaehlung[st.status(i)] += 1
        verloren = sum(1 for i in artikel if i["lock_state"] == "verloren")
        x = db.query("SELECT SUM(locked_at IS NOT NULL) AS fest, SUM(kind = 'aussonderung') AS aus, "
                     "SUM(completed_at IS NULL) AS entwurf FROM mat_inspection WHERE item_id IN "
                     "(SELECT value FROM json_each(?))", (ids,), one=True)
        runden = db.query("SELECT SUM(closed_on IS NOT NULL) AS zu, SUM(closed_on IS NULL) AS offen FROM mat_round "
                          "WHERE folder_id IN (SELECT value FROM json_each(?))",
                          (json.dumps([g["ordner"][s] for g in self.gl for s in ("gw", "lager")]),), one=True)
        demo = sum(1 for i in artikel if bestand.ist_demo(i["id"]))
        print()
        print("DEMO-Konten (Passwörter nur hier – sie werden nicht erneut angezeigt):")
        for mail, name, pw in self.passwoerter:
            print(f"  {mail:<42} {name:<32} Passwort: {pw}")
        print()
        print(f"Beispielbestand angelegt – Laufzeit {self._dauer(start)}.")
        print(f"  Gliederungen  {len(self.gl)} ({', '.join(g['name'] for g in self.gl)}), je {len(self.gl[0]['ordner'])} "
              "Ordner darunter")
        print(f"  Konten        {len(self.passwoerter)} DEMO-Konten (je Gliederung Materialwart, Prüferin, Mitglied, "
              f"externer Prüfer, {EINSATZKRAEFTE} Einsatzkräfte)")
        print(f"  Artikel       {len(artikel)} aus {len({p['produkt']['id'] for p in plaene if p['iid']})} Produkten, "
              f"davon {demo} als DEMO gekennzeichnet")
        print(f"  Prüfungen     {x['fest'] or 0} festgeschrieben mit Protokoll (davon {x['aus'] or 0} Aussonderungen), "
              f"{x['entwurf'] or 0} in Prüfung (Entwurf)")
        print(f"  Durchgänge    {runden['zu'] or 0} abgeschlossen mit Sammelprotokoll, {runden['offen'] or 0} offen")
        print(f"  Zuordnungen   {self.zuordnungen}")
        je_gl = []
        for g in self.gl:
            zweig, z = bestand.unterbaum(g["id"]), st.leere_zaehlung()
            for i in artikel:
                if bestand.heimat(i) in zweig:
                    z[st.status(i)] += 1
            je_gl.append(z)
        print(f"Zustände {'gesamt':>19}  " + "  ".join(f"{g['kurz']:>3}" for g in self.gl))
        for s in st.STATUS:
            zusatz = f"  (davon verloren gemeldet: {verloren})" if s == "gesperrt" else ""
            print(f"  {st.LABEL[s]:<22}{zaehlung[s]:>4}  " + "  ".join(f"{z[s]:>3}" for z in je_gl) + zusatz)
        fehlen = [st.LABEL[s] for s in st.STATUS if not zaehlung[s]] + ([] if verloren else ["verloren gemeldet"])
        if fehlen:
            grund = "" if any(p["lebensdauer"] for p in produkte) else " (der Katalog hat kein textiles Produkt mit Lebensdauer)"
            print(f"  Kommt nicht vor: {', '.join(fehlen)}{grund}.")
        ohne = sorted({p["name"] for p in produkte if not p["formular"]})
        if ohne:
            ende = sum(1 for p in plaene if p["iid"] and not p["produkt"]["formular"] and p["zustand"] == "lebensdauer")
            print(f"Ohne aktives Prüfformular (keine Prüfung möglich, Artikel „neu“"
                  f"{f', davon {ende} am Ende der Lebensdauer' if ende else ''}): {', '.join(ohne)}.")
        if ausgelassen:
            print(f"Nicht verwendet: {'; '.join(ausgelassen)}.")
        benutzt = db.query("SELECT DISTINCT f.title, f.version FROM mat_inspection x JOIN mat_form f ON f.id = x.form_id "
                           "WHERE x.item_id IN (SELECT value FROM json_each(?)) ORDER BY f.title, f.version", (ids,))
        if benutzt:
            print("Jetzt „benutzt“ (nur noch über eine neue Version änderbar): "
                  + ", ".join(f"„{f['title']}“ Version {f['version']}" for f in benutzt) + ".")
        mit_artikeln = len({p["produkt"]["id"] for p in plaene if p["iid"]})
        if mit_artikeln:
            print(f"Jetzt mit Artikeln: {mit_artikeln} Produkte – sie lassen sich nicht mehr löschen, ihre Materialart "
                  "nicht mehr ändern und ihre Kategorien nicht mehr löschen. Katalogpflege, die das braucht: Katalog "
                  "exportieren, dev-Datenbank zurücksetzen, Export importieren.")
        if self.uebersprungen:
            print("Hinweise:")
            for zeile in self.uebersprungen:
                print(f"  {zeile}")


if __name__ == "__main__":
    main()
