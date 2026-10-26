"""Modul Material auf dev zurücksetzen (Wunsch des Nutzers vom 23.10.2026): flask material dev-zuruecksetzen.

Vor Lieferung 3 soll sich das Modul auf dev von null an testen lassen. Zurückgesetzt wird nur das Modul: alle Tabellen,
Trigger, Views und Volltextindizes mit dem Vorsatz mat_ (Katalog, Ordner und Gliederungen, Bestand, Prüfungen,
Protokolle, Durchgänge, Importe, Rückrufe, Anträge, Meldungen, Journal, Erinnerungslog und Mailfehler-Protokoll, mat_meta
mit den Laufmarken des Tageslaufs) und seine Dateien unter media/material und pdf/. Konten, Strömipedia,
Ankerplätze, Riegenkarten und die Tabelle einstellungen (auch „Bald fällig“ und der Schalter Erinnerungsmails) bleiben, ebenso die
Spalten des Moduls an users (Modulstufe, Häkchen Prüfer, Urkundennummer, Unterschrift, mat_ref, PSA-Mails): Keine davon
verweist auf eine Zeile des Moduls – mat_ref ist der Verweis, auf den das Journal zeigt, nicht umgekehrt –, nach dem
Leeren zeigt also nichts ins Leere und nichts muss zurückgesetzt werden. Die DEMO-Konten (@example.invalid) bleiben auch;
der Befehl nennt sie nur.

Sperren gegen die Produktion, alle drei nötig: STROEMIS_NAME endet auf „-dev“ (erinnerung.dev_umgebung, dieselbe Regel
wie die harte Sperre der Erinnerungsmails), BASE_URL zeigt in der Umgebung UND in der Anwendung (Leitstelle →
Einstellungen) auf eine Adresse der Entwicklung, und der ausdrückliche Schalter --ja-alles-loeschen. --trocken zeigt nur,
was geschähe (auch er nur auf dev). Die Adresse prüft eine Positivliste (adresse_frei, Nachbesserung nach der
Sicherheitsprüfung vom 23.10.2026): Der Host wird bereinigt (Leerraum, fehlendes Schema, Unicode NFKC, Punktvarianten wie
der ideographische Punkt, IDNA, klein) und ist nur frei, wenn er mit „dev.“ beginnt oder localhost bzw. 127.0.0.1 ist
(run.py setzt http://localhost:8080). Leer, unlesbar oder sonst etwas – auch jede Schreibweise von strömis.de – sperrt.
Eine leere BASE_URL braucht kein Test und kein Probelauf: Die Tests setzen https://dev.strömis.de, ohne Eintrag gilt in
der Anwendung ohnehin die Vorgabe https://strömis.de.

Katalogimport im Hintergrund (importauftrag.py, Nachbesserung nach der Sicherheitsprüfung vom 24.10.2026): Läuft gerade
einer, bricht der Befehl ab, bevor er etwas ändert; sonst hält er dessen Sperre bis zum Schluss – ein Start in der Zeit
bekommt 409. Nach dem COMMIT leert er DATA_DIR/katalog-import (Aufträge, Berichte, Dateien von Probeläufen beziehen sich
auf den geleerten Katalog); die Sperrdatei bleibt.

Ablauf (zuruecksetzen):
  1. Das frische Schema entsteht zuerst in einer Vorlage im Speicher: models.migrieren auf einer leeren Datenbank, die
     nur die übrigen Tabellen dieser Datenbank kennt (ohne Zeilen). So läuft dieselbe Migration wie bei einer neuen
     Installation (Ergebnis Schemaversion SCHEMA_VERSION), ohne dass Schritt 8 bis 10 die echten Konten anfassen –
     Schritt 10 rechnete sonst die Modulstufen aus Freigaben neu, und die gibt es nach dem Leeren nicht mehr.
  2. Eine exklusive Transaktion (Fremdschlüssel aus wie in migrieren; wartet bis zu WARTEN Sekunden auf die Sperre).
     Unter ihr kann niemand schreiben – die Sicherung entspricht genau dem, was danach verschwindet.
  3. Sicherung: die ganze Datenbank über die Backup-API (eine zweite, lesende Verbindung; WAL lässt sie neben der
     Sperre lesen) nach <DATA_DIR>/sicherung-material-<Zeitstempel>/stroemis.db, umgestellt auf das gewöhnliche
     Journal, mit quick_check und denselben Zeilenzahlen je mat_-Tabelle. Scheitert sie: Abbruch, nichts gelöscht.
     Ordner 0700, Kopie 0600: Sie enthält alle Konten (Passwort-Hash, Urkundennummer, Unterschrift), Strömipedia und Riegenkarten
     – README und LIESMICH.txt fordern auf, sie nach dem ersten erfolgreichen Test zu löschen; der Bericht nennt ältere.
  4. LIESMICH.txt mit dem Rückweg für einen abgebrochenen Lauf, dann media/material und pdf/ in die Sicherung
     VERSCHIEBEN (umbenannt, nie kopiert – kein doppelter Platz; auf einem anderen Dateisystem scheitert das, und es
     bleibt alles, wie es war). Ab der exklusiven Transaktion bis nach dem Rückweg werden SIGTERM und SIGHUP (docker
     compose stop/restart, Deploy, abgerissene Verbindung) zu einer Ausnahme (_signale_abfangen) – der Rückweg greift.
     Nur gegen SIGKILL hilft das nicht: Dann rollt SQLite die Datenbank zurück, und LIESMICH.txt sagt, wie die Medien
     zurückkommen.
  5. Alle Objekte des Moduls entfernen (DROP – keine Zeile wird einzeln gelöscht, die Trigger der unveränderlichen
     Nachweise bleiben unberührt, bis ihre Tabelle als Ganzes geht) und das Schema aus der Vorlage anlegen, samt ihrer
     Zeilen (mat_meta). Erst dann COMMIT (danach LIESMICH.txt mit dem vollen Rückweg). Scheitert etwas vor dem
     COMMIT: ROLLBACK, die Medien zurück an ihren Platz, die eigene Sicherung wieder weg.
  6. Danach die Startschritte des Moduls (START_SCHRITTE) wie bei einem Start – das Modul steht dann da wie nach einer
     neuen Installation. Laufende Arbeitsprozesse sehen das neue Schema sofort; „docker compose restart“ danach räumt
     auf, was sie im Speicher halten.
"""
import contextlib
import logging
import os
import re
import shutil
import signal
import sqlite3
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

from flask import current_app

from .. import models
from . import ZONE, erinnerung, importauftrag

# Positivliste für BASE_URL (adresse_frei): Hosts der Entwicklung beginnen mit „dev.“, lokal läuft run.py.
DEV_VORSATZ = "dev."
LOKAL = {"localhost", "127.0.0.1"}
# Was IDNA außer dem Punkt als Trenner liest: ideographischer, vollbreiter und halbbreiter ideographischer Punkt.
PUNKTE = re.compile("[\u3002\uff0e\uff61]")
SICHERUNG_VORSATZ = "sicherung-material-"
SCHALTER = "--ja-alles-loeschen"
WARTEN = 30                                   # Sekunden auf die Schreibsperre (busy_timeout)
RESERVE = 64 * 1024 * 1024                    # so viel Platz bleibt nach der Sicherung mindestens frei
DEMO_POSTFACH = "@example.invalid"           # die DEMO-Konten aus scripts/material_beispielbestand.py
# Objekte des Moduls in sqlite_master: an einer Tabelle mat_* oder selbst mit dem Vorsatz (Trigger, Views).
MODUL = "(tbl_name LIKE 'mat\\_%' ESCAPE '\\' OR name LIKE 'mat\\_%' ESCAPE '\\')"
log = logging.getLogger(__name__)


class Gescheitert(Exception):
    """Abbruch mit Klartext für die Kommandozeile – die Meldung sagt, was geändert ist (meist: nichts)."""


class Signal(Exception):
    """SIGTERM oder SIGHUP im kritischen Abschnitt (_signale_abfangen) – führt in den Rückweg."""


# --- Sperren ---------------------------------------------------------------------------------------------------

def host(adresse):
    """Der Host einer BASE_URL, bereinigt: Leerraum weg, fehlendes Schema ergänzt, Unicode NFKC, Punktvarianten als Punkt,
    IDNA (Punycode), klein, ohne Punkt am Ende. None, wenn nichts Lesbares darin steht."""
    roh = PUNKTE.sub(".", unicodedata.normalize("NFKC", (adresse or "").strip()))
    if not roh:
        return None
    if "://" not in roh:
        roh = "//" + roh.lstrip("/")
    try:
        name = urlsplit(roh).hostname
        if not name:
            return None
        return name.encode("idna").decode("ascii").lower().rstrip(".") or None
    except (ValueError, UnicodeError):
        return None


def adresse_frei(adresse):
    """Positivliste: frei nur eine Adresse der Entwicklung (Host mit „dev.“ davor) oder localhost/127.0.0.1."""
    h = host(adresse)
    return bool(h) and (h.startswith(DEV_VORSATZ) or h in LOKAL)


def sperrgrund():
    """None, wenn dies eindeutig die Entwicklung ist – sonst der Grund, warum der Befehl hier nichts tut."""
    name = (os.environ.get("STROEMIS_NAME") or "").strip()
    if not erinnerung.dev_umgebung():
        return (f"Das ist nicht die Entwicklung: STROEMIS_NAME ist „{name or 'nicht gesetzt'}“ – auf dev endet er auf "
                "„-dev“ (scripts/dev-einrichten.sh).")
    for herkunft, adresse in (("BASE_URL in der Umgebung", os.environ.get("BASE_URL")),
                              ("BASE_URL der Anwendung (Leitstelle → Einstellungen)", current_app.config.get("BASE_URL"))):
        if not adresse_frei(adresse):
            zeigt = f"ist „{adresse.strip()}“" if (adresse or "").strip() else "fehlt"
            return (f"{herkunft} {zeigt} – frei ist nur eine Adresse der Entwicklung (Host mit „dev.“ davor) oder "
                    "localhost/127.0.0.1.")
    return None


# --- Bestand -----------------------------------------------------------------------------------------------------

def _tabellen(conn):
    """{Name: Art} der Tabellen des Moduls – Art „table“ oder „virtual“ (Volltextindex); Schattentabellen der
    Volltextindizes gehören zu ihrem Index und zählen nicht."""
    return {r[1]: r[2] for r in conn.execute("PRAGMA main.table_list")
            if r[1].startswith("mat_") and r[2] in ("table", "virtual")}


def _medien():
    """[(Pfad relativ zu DATA_DIR, voller Pfad)] der Dateiablagen des Moduls (katalog.medien_dir, protokoll.ablage)."""
    from . import katalog, protokoll
    daten = current_app.config["DATA_DIR"]
    return [(os.path.relpath(p, daten), p) for p in (katalog.medien_dir(), protokoll.ablage())]


def _groesse(pfad):
    """(Dateien, Bytes) unter einem Ordner; (0, 0), wenn es ihn nicht gibt."""
    dateien = groesse = 0
    for wurzel, _, namen in os.walk(pfad):
        for n in namen:
            try:
                groesse += os.lstat(os.path.join(wurzel, n)).st_size
                dateien += 1
            except OSError:
                pass
    return dateien, groesse


def bestand(conn):
    """Was das Zurücksetzen träfe und was bleibt: Zeilen je Tabelle, Volltextindizes, Trigger, Indizes, Views, Medien,
    Größe der Datenbank, Konten und DEMO-Konten."""
    tabellen = _tabellen(conn)
    zeilen = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
              for t in sorted(tabellen) if tabellen[t] == "table"}
    arten = dict(conn.execute(f"SELECT type, COUNT(*) FROM sqlite_master WHERE {MODUL} AND sql IS NOT NULL "
                              "GROUP BY type").fetchall())
    seiten, seite = conn.execute("PRAGMA page_count").fetchone()[0], conn.execute("PRAGMA page_size").fetchone()[0]
    return {"zeilen": zeilen, "volltext": sorted(t for t, a in tabellen.items() if a == "virtual"),
            "trigger": arten.get("trigger", 0), "indizes": arten.get("index", 0), "views": arten.get("view", 0),
            "medien": [(rel, *_groesse(p)) for rel, p in _medien()], "db_bytes": seiten * seite,
            "katalogimport": importauftrag.zwischendaten(),
            "konten": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "demo_konten": conn.execute("SELECT email, name FROM users WHERE lower(email) LIKE ? ORDER BY email",
                                        ("%" + DEMO_POSTFACH,)).fetchall()}


def _mb(n):
    return f"{n / (1024 * 1024):.1f} MB"


def _bleibt(b):
    return [f"Bleibt: Konten ({b['konten']}) samt Modulstufe, Häkchen Prüfer, Urkundennummer, Unterschrift und "
            "PSA-Mails, Strömipedia, Ankerplätze, Riegenkarten und Einstellungen (Leitstelle → Einstellungen)."]


def _demo_text(b):
    if not b["demo_konten"]:
        return []
    return (["DEMO-Konten (bleiben, jetzt ohne Freigaben – über die Nutzerverwaltung löschen, falls nicht mehr "
             "gebraucht; material_beispielbestand.py übernimmt vorhandene und legt nur fehlende an):"]
            + [f"  {mail} ({name})" for mail, name in b["demo_konten"]])


def trocken_text(b, ziel):
    """Der Probelauf für die Kommandozeile."""
    zeilen = ["Probelauf – nichts geändert.", "", "Würde nach der Sicherung gelöscht (Tabellen mit Zeilen):"]
    breite = max((len(t) for t in b["zeilen"]), default=0)
    zeilen += [f"  {t:<{breite}}  {n:>7}" for t, n in b["zeilen"].items() if n]
    leer = sum(1 for n in b["zeilen"].values() if not n)
    zeilen.append(f"  {len(b['zeilen'])} Tabellen ({leer} davon leer), {sum(b['zeilen'].values())} Zeilen; dazu "
                  f"{len(b['volltext'])} Volltextindizes, {b['trigger']} Trigger, {b['indizes']} Indizes, "
                  f"{b['views']} Views. Das Schema entsteht danach frisch (Version {models.SCHEMA_VERSION}).")
    zeilen += ["", "Würde in die Sicherung verschoben:"]
    zeilen += [f"  {rel:<15} {n} Dateien, {_mb(g)}" if n else f"  {rel:<15} leer oder nicht da"
               for rel, n, g in b["medien"]]
    n, g = b["katalogimport"]
    zeilen += ["", f"Würde danach geleert: {importauftrag.ORDNER} (Aufträge des Katalogimports) – "
                   + (f"{n} Dateien, {_mb(g)}" if n else "leer")]
    if importauftrag.laeuft():
        zeilen.append("ACHTUNG Gerade läuft ein Katalogimport – der echte Lauf bräche jetzt ab, ohne etwas zu ändern.")
    frei = shutil.disk_usage(current_app.config["DATA_DIR"]).free
    zeilen += ["", f"Sicherung nach: {ziel} (Datenbank {_mb(b['db_bytes'])}, frei {_mb(frei)})"]
    zeilen += _bleibt(b) + _demo_text(b) + _aeltere_text(aeltere_sicherungen())
    zeilen += ["", f"Wirklich zurücksetzen: derselbe Befehl mit {SCHALTER} statt --trocken, danach "
                   "„docker compose restart“. Während des Laufs nicht auf dev pushen und den Container nicht neu "
                   "starten."]
    return "\n".join(zeilen)


def bericht_text(e):
    """Der Bericht nach dem Zurücksetzen."""
    b = e["vorher"]
    zeilen = [f"Materialablage zurückgesetzt. Sicherung: {e['sicherung']}",
              f"  Datenbank (vorher, ganz): stroemis.db, {_mb(b['db_bytes'])}"]
    zeilen += [f"  {rel:<15} {n} Dateien, {_mb(g)} verschoben" for rel, n, g in b["medien"] if n]
    if b["katalogimport"][0]:
        zeilen.append(f"  {importauftrag.ORDNER:<15} {b['katalogimport'][0]} Dateien geleert (Aufträge des Katalogimports)")
    zeilen += [f"Geleert: {len(b['zeilen'])} Tabellen mit {sum(b['zeilen'].values())} Zeilen, "
               f"{len(b['volltext'])} Volltextindizes; Schema frisch angelegt (Version {e['version']})."]
    if e.get("start_fehler"):
        zeilen.append(f"ACHTUNG Die Startschritte des Moduls scheiterten ({e['start_fehler']}) – der Neustart holt "
                      "sie nach.")
    zeilen += _bleibt(b) + _demo_text(b)
    zeilen += ["", "Jetzt den Container neu starten: docker compose restart",
               f"Rückweg: {os.path.join(e['sicherung'], 'LIESMICH.txt')}",
               "", "Die Sicherung enthält alle Konten mit Passwort-Hash, Urkundennummern, Strömipedia und Riegenkarten – löschen, "
               "sobald der Neustart und ein erster Test geklappt haben:",
               f"  rm -rf data/{os.path.basename(e['sicherung'])}"]
    zeilen += _aeltere_text(e.get("aeltere"))
    return "\n".join(zeilen)


# --- Zurücksetzen ------------------------------------------------------------------------------------------------

def sicherungsziel(jetzt=None):
    """<DATA_DIR>/sicherung-material-<JJJJ-MM-TT_hhmmss> (deutsche Zeit) – noch nicht angelegt."""
    stempel = (jetzt or datetime.now(ZONE)).strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(current_app.config["DATA_DIR"], f"{SICHERUNG_VORSATZ}{stempel}")


def aeltere_sicherungen(ausser=None):
    """[(Name, Zeitpunkt, Bytes)] der Sicherungsordner unter DATA_DIR, ältester zuerst – ohne ausser (die eben
    angelegte). Sie enthalten alle Konten und sollen nach dem ersten erfolgreichen Test weg."""
    daten = current_app.config["DATA_DIR"]
    out = []
    for name in sorted(os.listdir(daten)):
        pfad = os.path.join(daten, name)
        if name.startswith(SICHERUNG_VORSATZ) and os.path.isdir(pfad) and pfad != ausser:
            out.append((name, datetime.fromtimestamp(os.stat(pfad).st_mtime, ZONE), _groesse(pfad)[1]))
    return sorted(out, key=lambda x: x[1])


def _aeltere_text(liste):
    if not liste:
        return []
    return (["", "Ältere Sicherungen – sie enthalten alle Konten mit Passwort-Hash, Urkundennummern, Strömipedia und Riegenkarten;",
             "löschen, sobald sie nicht mehr gebraucht werden (im Klon: rm -rf data/<Ordner>):"]
            + [f"  {name}  {zeit:%d.%m.%Y %H:%M}  {_mb(groesse)}" for name, zeit, groesse in liste])


def _schreiben(pfad, text):
    """Eine Textdatei nur für den Besitzer (0600) – wie die Kopie der Datenbank daneben."""
    fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(pfad, 0o600)


def _ordner_anlegen(ziel):
    """Den Sicherungsordner neu anlegen – nie einen vorhandenen benutzen (zwei Läufe in derselben Sekunde: -2, -3 …)."""
    for n in range(1, 100):
        pfad = ziel if n == 1 else f"{ziel}-{n}"
        try:
            os.mkdir(pfad, 0o700)
        except FileExistsError:
            continue
        os.chmod(pfad, 0o700)                           # mkdir rechnet die umask ab – nie weiter als 0700
        return pfad
    raise Gescheitert(f"Kein freier Name für den Sicherungsordner neben {ziel} – nichts geändert.")


def _vorlage(conn):
    """Das Schema des Moduls, wie es eine neue Installation anlegt: models.migrieren auf einer leeren Datenbank im
    Speicher, die die übrigen Tabellen dieser Datenbank kennt (nur ihre Form, keine Zeile)."""
    vorlage = sqlite3.connect(":memory:")
    kern = {r[1] for r in conn.execute("PRAGMA main.table_list")
            if r[2] == "table" and not r[1].startswith(("mat_", "sqlite_"))}
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY rowid").fetchall():
        if name in kern and sql:
            vorlage.execute(sql)
    vorlage.commit()
    models.migrieren(vorlage)
    return vorlage


def _sichern(db_pfad, ordner, erwartet):
    """Die ganze Datenbank nach ordner/stroemis.db (Backup-API, gewöhnliches Journal) und prüfen: quick_check und
    dieselben Zeilen je mat_-Tabelle wie unter der Sperre gezählt. Scheitert etwas, geht die Teilkopie weg."""
    ziel = os.path.join(ordner, "stroemis.db")
    try:
        os.close(os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))   # leer anlegen: SQLite übernimmt die Rechte
        with contextlib.closing(sqlite3.connect(db_pfad, timeout=WARTEN)) as quelle, \
                contextlib.closing(sqlite3.connect(ziel)) as kopie:
            quelle.backup(kopie)
            kopie.execute("PRAGMA journal_mode = DELETE")
            pruefung = kopie.execute("PRAGMA quick_check").fetchone()[0]
            gezaehlt = {t: kopie.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in erwartet}
        if pruefung != "ok" or gezaehlt != erwartet:
            raise sqlite3.DatabaseError(f"die Kopie stimmt nicht (quick_check: {pruefung})")
        os.chmod(ziel, 0o600)
        with open(ziel, "rb") as fh:
            os.fsync(fh.fileno())
    except (sqlite3.Error, OSError) as exc:
        for rest in (ziel, ziel + "-journal"):
            try:
                os.remove(rest)
            except OSError:
                pass
        raise Gescheitert(f"Die Sicherung der Datenbank ist gescheitert ({exc}) – nichts gelöscht, nichts "
                          "verschoben.") from exc


def _leeren(conn):
    """Alle Objekte des Moduls entfernen: Views, Trigger an fremden Tabellen (gibt es heute keine), Volltextindizes
    (mit ihren Schattentabellen), dann die Tabellen – Trigger und Indizes gehen mit ihrer Tabelle."""
    for (name,) in conn.execute(f"SELECT name FROM sqlite_master WHERE type = 'view' AND {MODUL}").fetchall():
        conn.execute(f'DROP VIEW "{name}"')
    for (name,) in conn.execute(f"SELECT name FROM sqlite_master WHERE type = 'trigger' AND {MODUL} "
                                "AND tbl_name NOT LIKE 'mat\\_%' ESCAPE '\\'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    for art in ("virtual", "table"):
        for name in [t for t, a in _tabellen(conn).items() if a == art]:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    rest = conn.execute(f"SELECT type, name FROM sqlite_master WHERE {MODUL}").fetchall()
    if rest:
        raise sqlite3.DatabaseError(f"nach dem Leeren übrig: {rest[:5]}")


def _anlegen(conn, vorlage):
    """Das Schema aus der Vorlage anlegen – Tabellen, Volltextindizes, Indizes, Views, Trigger – und ihre Zeilen
    übernehmen (mat_meta; sqlite_sequence, falls die Vorlage dort etwas für das Modul hat)."""
    schatten = {r[1] for r in vorlage.execute("PRAGMA main.table_list") if r[2] == "shadow"}
    virtuell = {r[1] for r in vorlage.execute("PRAGMA main.table_list") if r[2] == "virtual"}
    objekte = [(typ, name, sql) for typ, name, sql in vorlage.execute(
        f"SELECT type, name, sql FROM sqlite_master WHERE {MODUL} AND sql IS NOT NULL ORDER BY rowid")
        if name not in schatten]
    rang = {"table": 0, "virtual": 1, "index": 2, "view": 3, "trigger": 4}
    objekte.sort(key=lambda o: rang["virtual" if o[1] in virtuell else o[0]])
    for _, _, sql in objekte:
        conn.execute(sql)
    for typ, name, _ in objekte:
        if typ != "table" or name in virtuell:
            continue
        cur = vorlage.execute(f'SELECT * FROM "{name}"')
        zeilen = cur.fetchall()
        if zeilen:
            spalten = ", ".join(f'"{d[0]}"' for d in cur.description)
            conn.executemany(f'INSERT INTO "{name}" ({spalten}) VALUES ({", ".join("?" * len(cur.description))})',
                             zeilen)
    if vorlage.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
        for name, seq in vorlage.execute("SELECT name, seq FROM sqlite_sequence WHERE name LIKE 'mat\\_%' ESCAPE '\\'"):
            conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (name, seq))


LOESCHEN = ["BITTE LÖSCHEN, sobald der Neustart und ein erster Test auf dev geklappt haben (spätestens vor Lieferung 3):",
            "Die Kopie enthält ALLE Konten mit E-Mail, Passwort-Hash, Urkundennummer und Unterschrift, dazu Strömipedia",
            "und Riegenkarten – das Löschen eines Kontos auf dev erreicht sie nicht. Im Klon der Entwicklung:"]


def _liesmich(ordner, zeit, medien, fertig):
    """Was in der Sicherung liegt und wie es zurückgeht – auf dem VPS im Klon der Entwicklung. medien: die relativen
    Pfade, die (noch) hierher verschoben werden. fertig=False: vor dem ersten Verschieben – der Rückweg für einen Lauf,
    der danach abbricht (Datenbank unverändert, nur die Medien zurück); nach dem COMMIT überschreibt fertig=True ihn
    mit dem vollen Rückweg."""
    name = os.path.basename(ordner)
    kopf = [f"Sicherung vor „flask material dev-zuruecksetzen“ am {zeit:%d.%m.%Y um %H:%M:%S}.", ""]
    inhalt = ([f"{'stroemis.db':<15}die ganze Datenbank vorher (alle Module, Backup-API)"]
              + [f"{rel:<15}vorher unter data/{rel}, hierher verschoben" for rel in medien])
    loeschen = ["", *LOESCHEN, "", f"  rm -rf data/{name}"]
    sudo = ["(data/ gehört dem Nutzer 1000 – ist das nicht dein Nutzer, rm, cp und mv mit sudo.)"]
    if not fertig:
        text = kopf + [
            "LAUF UNVOLLSTÄNDIG, solange dieser Absatz hier steht: Der Lauf wurde nach dem Sichern abgebrochen (etwa",
            "Container neu gestartet oder Verbindung weg). Die Datenbank ist dann unverändert – SQLite verwirft den",
            "offenen Umbau –, nur die Medien des Moduls liegen hier. Zurück im Klon der Entwicklung (legte ein Start",
            "die Ordner unter data/ inzwischen leer neu an, sie vorher mit rmdir entfernen):", *sudo, "",
            "  docker compose stop"]
        text += [f"  mv data/{name}/{rel} data/{rel}        (nur, falls data/{name}/{rel} da ist)" for rel in medien]
        text += ["  docker compose up -d", "", *inhalt, *loeschen]
    else:
        text = kopf + inhalt + [
            "", "Rückweg im Klon der Entwicklung – was seit dem Zurücksetzen auf dev entstand, auch an Konten,",
            "Strömipedia, Ankerplätzen und Riegenkarten, geht dabei verloren:", *sudo, "",
            "  docker compose stop",
            "  rm -f data/stroemis.db-wal data/stroemis.db-shm",
            f"  cp data/{name}/stroemis.db data/stroemis.db"]
        for rel in medien:
            text += [f"  rm -rf data/{rel}", f"  mv data/{name}/{rel} data/{rel}"]
        text += ["  sudo chown -R 1000:1000 data", "  docker compose up -d", *loeschen]
    _schreiben(os.path.join(ordner, "LIESMICH.txt"), "\n".join(text) + "\n")


@contextlib.contextmanager
def _signale_abfangen():
    """SIGTERM und SIGHUP (docker compose stop/restart, Deploy, abgerissene Verbindung) werden im kritischen Abschnitt zu
    einer Ausnahme (Signal) – der Rückweg greift: ROLLBACK, Medien zurück. Nur das erste Signal bricht ab; weitere,
    während der Rückweg läuft, und jedes nach zustand["fertig"] (unmittelbar vor dem COMMIT gesetzt) gehen ins Leere,
    damit weder der Rückweg noch ein gelungener Lauf halb endet. Danach gelten die alten Handler wieder. Außerhalb des
    Hauptthreads (signal.signal geht dort nicht) bleibt alles, wie es ist."""
    zustand = {"fertig": False, "abbruch": False}

    def abbrechen(signum, _frame):
        if zustand["fertig"] or zustand["abbruch"]:
            return
        zustand["abbruch"] = True
        raise Signal(f"Signal {signal.Signals(signum).name}")

    alt = {}
    try:
        for s in (signal.SIGTERM, signal.SIGHUP):
            alt[s] = signal.signal(s, abbrechen)
    except ValueError:
        pass
    try:
        yield zustand
    finally:
        for s, h in alt.items():
            signal.signal(s, h)


def zuruecksetzen(jetzt=None):
    """Sichern, verschieben, leeren, frisch anlegen (siehe oben). Liefert {"sicherung", "vorher", "version", "zeit",
    "start_fehler"}; Gescheitert mit Klartext, wenn nichts geändert wurde oder – nur, wenn das Zurückschieben der
    Medien selbst scheitert – was wo liegt. sperrgrund() prüft der Aufrufer vorher."""
    from .. import START_SCHRITTE
    db_pfad = current_app.config["DB_PATH"]
    jetzt = jetzt or datetime.now(ZONE)
    try:
        sperre = importauftrag.anhalten()
    except OSError as exc:
        raise Gescheitert(f"Die Sperre des Katalogimports ließ sich nicht nehmen ({exc}) – nichts geändert.") from exc
    if sperre is None:
        raise Gescheitert("Gerade läuft ein Katalogimport (Hinweis oben auf der Katalogseite) – nichts geändert. Warten, "
                          "bis er zu Ende ist, dann erneut.")
    conn = sqlite3.connect(db_pfad, timeout=WARTEN, isolation_level=None)
    vorlage = None
    try:
        if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise Gescheitert("Die Datenbank läuft nicht im WAL-Modus – die Sicherung unter der Sperre ginge so nicht. "
                              "Nichts geändert; einmal den Container starten, dann erneut.")
        try:
            vorlage = _vorlage(conn)
        except sqlite3.Error as exc:
            raise Gescheitert(f"Das frische Schema ließ sich nicht aufbauen ({exc}) – nichts geändert.") from exc
        groesse = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
        frei = shutil.disk_usage(current_app.config["DATA_DIR"]).free
        if frei < groesse + RESERVE:
            raise Gescheitert(f"Zu wenig Platz für die Sicherung: frei {_mb(frei)}, gebraucht {_mb(groesse + RESERVE)} "
                              "– nichts geändert.")
        ordner = _ordner_anlegen(sicherungsziel(jetzt))
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            os.rmdir(ordner)
            raise Gescheitert(f"Die Datenbank ist belegt ({exc}) – nichts geändert. Später erneut, oder den Container "
                              "vorher neu starten.") from exc
        verschoben = []
        with _signale_abfangen() as zustand:
            try:
                vorher = bestand(conn)
                _sichern(db_pfad, ordner, vorher["zeilen"])
                medien = [(rel, quelle) for rel, quelle in _medien() if os.path.lexists(quelle)]
                _liesmich(ordner, jetzt, [rel for rel, _ in medien], fertig=False)
                for rel, quelle in medien:
                    ziel = os.path.join(ordner, rel)
                    os.makedirs(os.path.dirname(ziel), mode=0o700, exist_ok=True)
                    os.rename(quelle, ziel)                 # nie kopieren; ein anderes Dateisystem scheitert hier
                    verschoben.append((quelle, ziel))
                _leeren(conn)
                _anlegen(conn, vorlage)
                version = int(conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0])
                if version != models.SCHEMA_VERSION:
                    raise sqlite3.DatabaseError(f"Schemaversion {version} statt {models.SCHEMA_VERSION}")
                zustand["fertig"] = True                    # ein Signal ab hier bricht nicht mehr ab
                conn.execute("COMMIT")
            except BaseException as exc:
                zustand["abbruch"] = True                   # ein Signal unterbricht den Rückweg nicht
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                _zurueck(ordner, verschoben, exc)
                raise
        try:
            importauftrag.leeren_unter_sperre()
        except OSError as exc:                          # das Zurücksetzen selbst ist geschehen
            log.warning("Aufträge des Katalogimports nicht geleert: %s", exc)
    finally:
        conn.close()
        if vorlage is not None:
            vorlage.close()
        sperre.close()
    e = {"sicherung": ordner, "vorher": vorher, "version": version, "zeit": jetzt, "start_fehler": None,
         "aeltere": aeltere_sicherungen(ausser=ordner)}
    _liesmich(ordner, jetzt, [os.path.relpath(q, current_app.config["DATA_DIR"]) for q, _ in verschoben], fertig=True)
    # Wie beim Start (db.init_db): eine eigene Verbindung, jeder Schritt mit seiner eigenen Transaktion.
    start = sqlite3.connect(db_pfad, timeout=WARTEN)
    try:
        for schritt in START_SCHRITTE:
            schritt(start)
    except Exception as exc:                            # das Zurücksetzen selbst ist geschehen
        log.exception("Startschritte nach dem Zurücksetzen gescheitert")
        e["start_fehler"] = str(exc)
    finally:
        start.close()
    log.warning("Materialablage zurückgesetzt (dev): %d Tabellen, %d Zeilen geleert, Medien verschoben; Sicherung %s",
                len(vorher["zeilen"]), sum(vorher["zeilen"].values()), ordner)
    return e


def _zurueck(ordner, verschoben, exc):
    """Nach einem Abbruch vor dem COMMIT: die Medien zurück an ihren Platz und die eigene Sicherung wieder weg – nur,
    wenn alles zurück ist, und nur mit genauen Pfaden (os.rmdir entfernt nie einen Ordner mit Inhalt)."""
    liegen = []
    for quelle, ziel in reversed(verschoben):
        try:
            os.rename(ziel, quelle)
        except OSError as fehler:
            liegen.append(f"{ziel} (gehört nach {quelle}: {fehler})")
    if liegen:
        raise Gescheitert(f"Abgebrochen ({exc}); die Datenbank ist unverändert, aber nicht alle Medien ließen sich "
                          f"zurückschieben – sie liegen noch in der Sicherung: {'; '.join(liegen)}") from exc
    for rest in ("stroemis.db", "LIESMICH.txt"):
        try:
            os.remove(os.path.join(ordner, rest))
        except OSError:
            pass
    for leer in sorted({os.path.dirname(z) for _, z in verschoben} | {ordner}, key=len, reverse=True):
        try:
            os.rmdir(leer)
        except OSError:
            pass
    if not isinstance(exc, Gescheitert):
        raise Gescheitert(f"Abgebrochen ({exc}) – nichts geändert: Datenbank unverändert, Medien zurück an ihrem "
                          "Platz.") from exc
