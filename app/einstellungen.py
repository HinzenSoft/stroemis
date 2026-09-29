"""Einstellungen, die sich im Browser ändern lassen – statt nur in der .env.

Die .env bleibt gültig und ist weiterhin der Weg, eine frische Anlage einzurichten. Was hier
gespeichert wird, liegt aber DARÜBER: Sonst ließe sich ein Wert im Browser ändern, ohne dass er
wirkt, und niemand käme darauf, dass eine Zeile in einer Datei auf dem Server der Grund ist.

Gunicorn startet die Anwendung in jedem Arbeitsprozess getrennt; ein Wert, der nur im Speicher
stünde, gälte deshalb nur für den Prozess, der ihn entgegengenommen hat – und die Seite verhielte
sich bei jedem zweiten Aufruf anders. Die Werte stehen deshalb in der Datenbank und werden zu
Beginn jeder Anfrage über die Konfiguration gelegt.
"""
import os

from flask import current_app, request

from . import db

# Was die Anwendung beim Start aus Umgebung und Vorgaben gelesen hat. Ohne diese Kopie wäre
# „zurück auf die Vorgabe“ nicht möglich: Die Konfiguration trägt nach dem ersten Überlegen
# bereits den gespeicherten Wert, der ursprüngliche wäre verloren.
_grundstand = {}


class Feld:
    """Eine Einstellung: wie sie heißt, was sie bedeutet und wohin ihr Wert gehört.

    "schluessel" ist der Name in der .env, "config" der Schlüssel in der Flask-Konfiguration –
    meist derselbe, aber nicht immer: MAX_UPLOAD_MB steht als MAX_CONTENT_LENGTH in Bytes darin.
    """

    def __init__(self, schluessel, gruppe, titel, art="text", hilfe="", config=None,
                 wandeln=None, geheim=False, platzhalter=""):
        self.schluessel = schluessel
        self.gruppe = gruppe
        self.titel = titel
        self.art = art                 # text | mehrzeilig | zahl | schalter | passwort
        self.hilfe = hilfe
        self.config = config or schluessel
        self._wandeln = wandeln
        self.geheim = geheim           # wird nie an den Browser zurückgegeben
        self.platzhalter = platzhalter

    def wert(self, roh):
        """Den gespeicherten Text in das umrechnen, was die Konfiguration erwartet."""
        if self._wandeln:
            return self._wandeln(roh)
        if self.art == "schalter":
            return str(roh).strip().lower() in ("1", "true", "yes", "on")
        if self.art == "zahl":
            try:
                return int(str(roh).strip())
            except ValueError:
                return None
        return roh


def _mb(roh):
    try:
        return max(1, int(str(roh).strip())) * 1024 * 1024
    except ValueError:
        return None


def _idna(host):
    """Wie in __init__: Der Host-Header kommt in Punycode an, getippt wird mit Umlaut."""
    host = (host or "").strip().lower().split(":")[0]
    try:
        return host.encode("idna").decode()
    except UnicodeError:
        return host


FELDER = [
    # --- Seite ------------------------------------------------------------------------------
    Feld("SITE_NAME", "Seite", "Name der Seite",
         hilfe="Steht im Betreff jeder Mail und in der Kopfzeile."),
    Feld("BASE_URL", "Seite", "Adresse der Anwendung",
         hilfe="Damit werden die Links in E-Mails gebaut – etwa der zum Zurücksetzen des "
               "Passworts. Ohne Schrägstrich am Ende.",
         platzhalter="https://strömis.de"),
    Feld("PUBLIC_URL", "Seite", "Adresse des öffentlichen Wikis",
         platzhalter="https://wiki.strömis.de"),
    Feld("PUBLIC_HOST", "Seite", "Hostname des öffentlichen Wikis",
         wandeln=_idna,
         hilfe="Anfragen an diesen Namen landen im öffentlichen Bereich."),
    Feld("ALLOW_REGISTRATION", "Seite", "Kontoanfragen erlauben", art="schalter",
         hilfe="Aus heißt: Konten legt nur ein Administrator an."),
    Feld("LOGIN_SLIDESHOW", "Seite", "Bilder auf der Anmeldeseite", art="schalter",
         hilfe="Zeigt zufällige Bilder aus den Spots hinter dem Anmeldeformular."),

    # --- Prüfungen --------------------------------------------------------------------------
    Feld("SPRACHEINGABE", "Prüfungen", "Diktieren per Mikrofon", art="schalter",
         hilfe="Mikrofon-Knopf an den Kommentarfeldern der Prüfungen – für draußen, mit Handschuhen. "
               "Die Erkennung übernimmt der Browser; Chrome und Safari können das Audio dafür an "
               "Google bzw. Apple senden. Aus, wenn der Datenschutz das nicht zulässt."),

    # --- E-Mail -----------------------------------------------------------------------------
    Feld("MAIL_FROM", "E-Mail", "Absender",
         hilfe="Name und Adresse, wie sie beim Empfänger stehen. Die Domain dahinter entscheidet "
               "über SPF, DKIM und DMARC – sie sollte zur Seite gehören.",
         platzhalter="strömis.de <noreply@xn--strmis-yxa.de>"),
    Feld("SMTP_HOST", "E-Mail", "Mailserver",
         hilfe="Leer heißt: Es wird nichts verschickt, Mails stehen nur im Protokoll."),
    Feld("SMTP_PORT", "E-Mail", "Port",
         hilfe="Leer nimmt 465 bei SSL, sonst 587.", platzhalter="587"),
    Feld("SMTP_USER", "E-Mail", "Benutzername"),
    Feld("SMTP_PASSWORD", "E-Mail", "Kennwort", art="passwort", geheim=True,
         hilfe="Wird nie zurückgegeben. Leer lassen behält das gespeicherte Kennwort."),
    Feld("SMTP_SSL", "E-Mail", "Verbindung von Anfang an verschlüsselt (SMTPS)", art="schalter",
         hilfe="Für Port 465. Sonst wird über STARTTLS verschlüsselt."),
    Feld("SMTP_STARTTLS", "E-Mail", "STARTTLS verwenden", art="schalter"),
    Feld("SMTP_ENVELOPE_FROM", "E-Mail", "Absender des Umschlags",
         hilfe="Gegen diese Adresse prüft der Empfänger SPF, und an sie gehen Rückläufer. Leer "
               "heißt: dieselbe wie oben – so verlangt es DMARC."),
    Feld("ADMIN_NOTIFY_EMAIL", "E-Mail", "Benachrichtigungen an",
         hilfe="Zusätzliche Adresse für Kontoanfragen. Leer heißt: nur an die Administratoren."),

    # --- Karte ------------------------------------------------------------------------------
    Feld("MAP_CENTER", "Karte", "Mittelpunkt beim Öffnen",
         hilfe="Breite und Länge, durch Komma getrennt.", platzhalter="51.0,10.4"),
    Feld("MAP_ZOOM", "Karte", "Zoomstufe beim Öffnen", art="zahl", platzhalter="6"),
    Feld("TILE_URL", "Karte", "Straßenkarte"),
    Feld("TILE_ATTRIBUTION", "Karte", "Rechtehinweis Straßenkarte", art="mehrzeilig",
         hilfe="OpenStreetMap verlangt die Namensnennung. Leer setzt die Vorgabe wieder ein."),
    Feld("SAT_URL", "Karte", "Luftbild",
         hilfe="Achtung: Esri ordnet die Kacheln {z}/{y}/{x}, nicht {z}/{x}/{y}."),
    Feld("SAT_LABELS_URL", "Karte", "Beschriftung über dem Luftbild", art="mehrzeilig",
         hilfe="Mehrere Ebenen durch Komma getrennt, von unten nach oben. Leer schaltet sie ab."),
    Feld("SAT_ATTRIBUTION", "Karte", "Rechtehinweis Luftbild", art="mehrzeilig"),
    Feld("TOPO_URL", "Karte", "Geländekarte"),
    Feld("TOPO_ATTRIBUTION", "Karte", "Rechtehinweis Geländekarte", art="mehrzeilig"),
    Feld("GEOCODE_URL", "Karte", "Adresssuche",
         hilfe="Leer schaltet die Suche ab. Die öffentliche Nominatim-Adresse erlaubt eine "
               "Anfrage je Sekunde und keine Massenabfragen."),

    # --- Grenzen ----------------------------------------------------------------------------
    Feld("MAX_UPLOAD_MB", "Grenzen", "Größte Datei (MB)", art="zahl",
         config="MAX_CONTENT_LENGTH", wandeln=_mb,
         hilfe="Gilt für Bilder, Filme, Wiki-Anhänge und die Medien zu Prüfungen – Videos vom "
               "Telefon sind schnell einige hundert Megabyte groß."),
    Feld("MAX_REQUEST_MB", "Grenzen", "Größte gewöhnliche Anfrage (MB)", art="zahl",
         config="MAX_REQUEST_LENGTH", wandeln=_mb,
         hilfe="Alles außer Dateiuploads – eine Wiki-Seite etwa."),
    Feld("WIKI_MAX_REVISIONS", "Grenzen", "Aufbewahrte Fassungen je Wiki-Seite", art="zahl",
         config="MAX_REVISIONS"),

    # --- Sicherheit -------------------------------------------------------------------------
    Feld("COOKIE_SECURE", "Sicherheit", "Sitzungscookie nur über HTTPS", art="schalter",
         config="SESSION_COOKIE_SECURE",
         hilfe="Im Betrieb an. Aus nur für den Zugriff über einfaches HTTP – sonst wirft der "
               "Browser das Cookie weg und die Anmeldung wirkt wirkungslos."),
]

NACH_SCHLUESSEL = {f.schluessel: f for f in FELDER}
GRUPPEN = []
for _f in FELDER:
    if _f.gruppe not in GRUPPEN:
        GRUPPEN.append(_f.gruppe)


def grundstand_merken(app):
    """Den Stand aus Umgebung und Vorgaben festhalten, bevor etwas überlegt wird."""
    _grundstand.clear()
    for f in FELDER:
        _grundstand[f.schluessel] = app.config.get(f.config)


def gespeichert():
    """Alle gespeicherten Werte – Schlüssel auf Text."""
    return {r["schluessel"]: r["wert"]
            for r in db.query("SELECT schluessel, wert FROM einstellungen")}


def abgeschaltet():
    """Notausgang: Mit EINSTELLUNGEN_AUS=1 gilt wieder ausschließlich die .env.

    Gebraucht, wenn eine Einstellung die Anwendung unbedienbar gemacht hat – etwa das
    Sitzungscookie nur über HTTPS, während der Zugriff über einfaches HTTP läuft. Dann käme
    niemand mehr an die Oberfläche, um den Wert zurückzunehmen. Steht in der .env.example."""
    return str(os.environ.get("EINSTELLUNGEN_AUS", "")).strip().lower() in ("1", "true", "yes", "on")


def anwenden():
    """Die gespeicherten Werte über die Konfiguration legen. Läuft zu Beginn jeder Anfrage.

    Eine Abfrage je Anfrage – dieselbe Größenordnung wie die Abfrage des angemeldeten Nutzers.
    Ein Zwischenspeicher im Prozess wäre billiger, brächte aber genau das zurück, was hier
    vermieden werden soll: zwei Arbeitsprozesse mit verschiedenen Werten."""
    if abgeschaltet():
        return
    try:
        werte = gespeichert()
    except Exception:
        return                         # Beim allerersten Start gibt es die Tabelle noch nicht.
    for schluessel, roh in werte.items():
        f = NACH_SCHLUESSEL.get(schluessel)
        if not f:
            continue
        wert = f.wert(roh)
        if wert is not None:
            current_app.config[f.config] = wert


def beim_start_anwenden(app):
    """Dasselbe einmal beim Hochfahren.

    Gebraucht für die allererste Anfrage eines frisch gestarteten Arbeitsprozesses: Die Weiche
    für den öffentlichen Hostnamen läuft VOR dem Anfragehaken, sie sähe sonst einmal den Wert
    aus der .env."""
    if abgeschaltet():
        return
    with app.app_context():
        try:
            werte = gespeichert()
        except Exception:
            return
        for schluessel, roh in werte.items():
            f = NACH_SCHLUESSEL.get(schluessel)
            if not f:
                continue
            wert = f.wert(roh)
            if wert is not None:
                app.config[f.config] = wert


def _quelle(schluessel, werte):
    """Woher der Wert kommt, der gerade gilt – das gehört in die Oberfläche.

    Ohne diese Auskunft sieht man einem Feld nicht an, ob es hier gesetzt wurde, aus der .env
    stammt oder die eingebaute Vorgabe ist. Wer dann etwas ändert und nichts geschieht, sucht
    an der falschen Stelle."""
    if schluessel in werte:
        return "gespeichert"
    if os.environ.get(schluessel) is not None:
        return "umgebung"
    return "vorgabe"


def _anzeigewert(f, werte):
    """Der Wert, den die Oberfläche zeigt. Geheimes nie."""
    if f.geheim:
        return ""
    if f.schluessel in werte:
        return werte[f.schluessel]
    roh = os.environ.get(f.schluessel)
    if roh is not None:
        return roh
    grund = _grundstand.get(f.schluessel)
    if isinstance(grund, bool):
        return "true" if grund else "false"
    if f.config == "MAX_CONTENT_LENGTH" or f.config == "MAX_REQUEST_LENGTH":
        return str((grund or 0) // (1024 * 1024))
    return "" if grund is None else str(grund)


def als_json():
    """Alle Felder mit ihrem geltenden Wert – für die Oberfläche."""
    werte = gespeichert()
    raus = []
    for f in FELDER:
        raus.append({
            "schluessel": f.schluessel,
            "gruppe": f.gruppe,
            "titel": f.titel,
            "art": f.art,
            "hilfe": f.hilfe,
            "platzhalter": f.platzhalter,
            "geheim": f.geheim,
            "quelle": _quelle(f.schluessel, werte),
            "wert": _anzeigewert(f, werte),
            # Nur beim Kennwort: ob überhaupt eines hinterlegt ist. Der Wert selbst nie.
            "gesetzt": bool(werte.get(f.schluessel)) if f.geheim else None,
        })
    return {"gruppen": GRUPPEN, "felder": raus}


def speichern(eingaben, uid):
    """Werte schreiben. Liefert die Zahl der geänderten Felder.

    Ein leeres Kennwortfeld heißt „unverändert“, nicht „löschen“ – sonst räumte jedes Speichern
    des Formulars das Kennwort weg, weil es ja nie zurückgegeben wird. Zum Löschen wird der
    Schlüssel ausdrücklich zurückgesetzt (siehe zuruecksetzen)."""
    geschrieben = 0
    jetzt = db.now()
    with db.transaction():
        for schluessel, roh in (eingaben or {}).items():
            f = NACH_SCHLUESSEL.get(schluessel)
            if not f:
                continue               # Unbekanntes wird stillschweigend übergangen
            text = "" if roh is None else str(roh)
            if f.art == "schalter":
                text = "true" if roh in (True, "true", "1", 1, "on", "yes") else "false"
            text = text.strip()
            if f.geheim and not text:
                continue
            if f.art == "zahl" and text:
                try:
                    int(text)
                except ValueError:
                    raise ValueError(f"„{f.titel}“ braucht eine Zahl.")
            db.execute(
                "INSERT INTO einstellungen (schluessel, wert, geaendert_am, geaendert_von) "
                "VALUES (?,?,?,?) ON CONFLICT(schluessel) DO UPDATE SET "
                "wert = excluded.wert, geaendert_am = excluded.geaendert_am, "
                "geaendert_von = excluded.geaendert_von",
                (schluessel, text, jetzt, uid))
            geschrieben += 1
    return geschrieben


def zuruecksetzen(schluessel):
    """Einen Wert wieder aus Umgebung und Vorgabe holen.

    Die Zeile fällt weg, und in der Konfiguration steht sofort wieder der Stand vom Start –
    sonst bliebe der gelöschte Wert bis zur nächsten Anfrage stehen."""
    f = NACH_SCHLUESSEL.get(schluessel)
    if not f:
        return False
    db.execute("DELETE FROM einstellungen WHERE schluessel = ?", (schluessel,))
    if f.schluessel in _grundstand:
        current_app.config[f.config] = _grundstand[f.schluessel]
    return True


def ist_statisch(pfad=None):
    """Statische Dateien und Medien brauchen die Einstellungen nicht – und jede Bilddatei
    sollte keine Datenbankabfrage kosten."""
    p = pfad if pfad is not None else request.path
    return p.startswith(("/static/", "/media/", "/favicon"))
