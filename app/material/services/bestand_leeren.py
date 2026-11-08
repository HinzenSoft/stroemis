"""Nur den Bestand der Materialablage auf dev leeren (Wunsch des Nutzers vom 08.11.2026): flask material
dev-bestand-leeren.

Anlass: Der Beispielbestand (scripts/material_beispielbestand.py) soll sich auf dev neu anlegen lassen, ohne den Katalog
zu verlieren – dev-zuruecksetzen leert das ganze Modul (auch Katalog, Formulare, Pool und Zuweisungen) und kommt dafür
nicht in Frage. Geleert wird hier nur, was zum Bestand gehört:

  ganz       Ordner und Gliederungen (samt Systemordnern), Artikel samt Seriennummern der Bestandteile, Prüfungen samt
             Befunden, Anhängen und Protokollen, Durchgänge samt Sammel- und Set-Protokollen, Set-Läufe, Freigaben,
             Änderungsanträge, Mangelmeldungen, Erinnerungslog, Mailfehler-Protokoll, Bestandsimporte samt Nacharbeit,
             Lebensläufe, Protokoll der globalen Suche, Merker „Antrag ohne Verwalter“ (BESTAND) – dazu der
             Volltextindex der Artikel
  teilweise  das Journal: die Einträge an Artikeln, Ordnern, Prüfungen und Durchgängen (JOURNAL_BESTAND) und die an
             gelöschten DEMO-Konten; mat_meta: die Merker des Beispielbestands und der gelöschten DEMO-Konten,
             zuletzt besuchte Artikel auf der Startseite (start:ziele) – Artikelnummern werden neu vergeben;
             Produktmeldungen verlieren ihren Ordner (folder_id NULL, wie ON DELETE SET NULL)
  Konten     die DEMO-Konten des Beispielbestands (DEMO_KONTEN: genau die Adressen aus dem Skript, Name „DEMO-…“) –
             nur, wenn außerhalb des Bestands nichts auf sie verweist (sonst bleiben sie und der Bericht sagt, warum)

Es bleiben Kategorien, Produkte, Bestandteil-Listen, Dokumente, Bilder, Prüfformulare (Pool, Versionen, Zuweisungen,
Standards – auch die DEMO-Formulare des Beispielbestands), Rückrufe, Produktmeldungen, das Journal des Katalogs und der
Konten, alle übrigen Konten, die übrigen Module und die Einstellungen. Rückrufe speichern keine Erledigung am Artikel –
der Zustand je Artikel wird abgeleitet (rueckruf.py); ohne Artikel ist ein Rückruf einfach ohne Betroffene. Die Zähler
bleiben, damit keine Nummer zweimal vergeben wird: Inventar- und STR-Nummern (mat_meta inventar_zaehler), Lebenslauf-
Kennungen (lebenslauf_zaehler_<jahr> und die Zählerdateien unter pdf/lebenslauf, die deshalb liegen bleiben),
Protokoll-IDs (sqlite_sequence von mat_inspection, mat_round, mat_round_setprotokoll – DELETE setzt sie nicht zurück).
Die Kennungen der Artikel und Ordner (ohne AUTOINCREMENT) beginnen wieder bei 1; die QR-Adressen hängen am zufälligen
qr_token, nicht an ihnen.

Eine Tabelle des Moduls, die weder BESTAND noch BLEIBT kennt (ein neuer Schemaschritt), und ein Journaleintrag mit einer
unbekannten Entität lassen den Befehl abbrechen, bevor er etwas ändert – erst einordnen.

Sperren wie dev-zuruecksetzen (zuruecksetzen.sperrgrund: STROEMIS_NAME auf „-dev“, BASE_URL in Umgebung und Anwendung auf
der Positivliste), dazu der Schalter --ja-bestand-loeschen; --trocken zählt nur. Läuft ein Katalogimport, bricht der
Befehl ab; sonst hält er dessen Sperre bis zum Schluss (ein Import schriebe sonst womöglich in ein Produkt, dessen Bilder
gerade wandern). Einen laufenden Beispielbestand erkennt er nicht – erst abbrechen oder enden lassen (README).

Ablauf (leeren):
  1. Exklusive Transaktion (Fremdschlüssel aus, wie in migrieren), Bestandsaufnahme und Sicherung der ganzen Datenbank
     über die Backup-API (zuruecksetzen._sichern: quick_check, Zeilen je mat_-Tabelle) nach
     <DATA_DIR>/sicherung-bestand-<Zeitstempel>/ (0700, Kopie 0600). Scheitert sie: Abbruch, nichts geändert.
  2. LIESMICH.txt mit dem Rückweg, dann die Medien des Bestands in die Sicherung VERSCHIEBEN (umbenennen, nie kopieren):
     Ordner-, Befund- und Mangelfotos unter media/material/{orig,web,thumb,slide} (nur Dateien, deren Schlüssel kein
     Produktbild und keine Produktmeldung nennt), media/material/anhang (nur Prüfanhänge) und pdf/ ohne pdf/lebenslauf.
     SIGTERM/SIGHUP werden wie in dev-zuruecksetzen zur Ausnahme (_signale_abfangen) – der Rückweg greift.
  3. Die Trigger der berührten Tabellen (Unveränderlichkeit der Nachweise, Volltext) werden in der Transaktion gezielt
     entfernt, die Zeilen gelöscht, der Volltextindex der Artikel neu aufgebaut und die Trigger mit ihrem genauen SQL
     wieder angelegt. Vor dem COMMIT: sqlite_master Zeichen für Zeichen wie vorher (Trigger, Schema, Version),
     PRAGMA foreign_key_check ohne neue Verstöße, quick_check ok. Scheitert etwas: ROLLBACK, die Medien zurück, die
     eigene Sicherung wieder weg.
  4. Danach die Startschritte des Moduls (wie nach dev-zuruecksetzen) – „docker compose restart“ räumt auf, was die
     Arbeitsprozesse im Speicher halten.
"""
import json
import logging
import os
import re
import shutil
import sqlite3
from datetime import datetime

from flask import current_app

from .. import models
from . import ZONE, importauftrag
from . import zuruecksetzen as zr

SCHALTER = "--ja-bestand-loeschen"
SICHERUNG_VORSATZ = zr.BESTAND_VORSATZ
# Die Tabellen des Bestands – werden ganz geleert (Kinder vor Eltern; die Fremdschlüssel sind in der Transaktion aus).
BESTAND = ("mat_set_protokoll_zeile", "mat_inspection_result", "mat_inspection_attachment", "mat_item_component_serial",
           "mat_round_item", "mat_round_setprotokoll", "mat_reminder_log", "mat_defect_report", "mat_item_change",
           "mat_import_row", "mat_import", "mat_set_lauf", "mat_inspection", "mat_round", "mat_lebenslauf",
           "mat_global_search", "mat_mail_fehler", "mat_antrag_ohne_verwalter", "mat_folder_grant", "mat_item",
           "mat_folder")
VOLLTEXT_BESTAND = ("mat_item_fts",)
# Was bleibt: Katalog, Formulare, Rückrufe und Meldungen (ganz) – Journal und mat_meta nur zum Teil (unten).
BLEIBT = ("mat_category", "mat_product", "mat_product_component", "mat_product_document", "mat_formular", "mat_form",
          "mat_checklist_item", "mat_formular_zuweisung", "mat_recall", "mat_product_request", "mat_product_fts")
TEILWEISE = ("mat_audit", "mat_meta")
# Journal (mat_audit.entity): diese Einträge gehören zum Bestand, die übrigen zum Katalog bzw. zu Konten.
JOURNAL_BESTAND = ("item", "folder", "inspection", "round")
JOURNAL_BLEIBT = ("product", "category", "document", "form", "formular", "request", "user")
# Merker des Beispielbestands in mat_meta (der große seit 25.10.2026, der kleine davor).
MERKER = ("beispielbestand_gross", "beispielbestand")
# Die DEMO-Konten aus scripts/material_beispielbestand.py (_konten_roh) – genau diese Adressen, nicht jede @example.invalid.
DEMO_KONTEN = re.compile(r"demo-(?:wart-a|wart-b|pruefer|pruefer-2|pruefer-ns|extern|mitglied|mv|einsatzkraft-\d{2,})"
                         r"@example\.invalid")
FOTO_ARTEN = ("orig", "web", "thumb", "slide")
LOESCHEN = ["BITTE LÖSCHEN, sobald der Neustart und ein erster Test auf dev geklappt haben (spätestens nach einer Woche):",
            "Die Kopie enthält ALLE Konten mit E-Mail, Passwort-Hash, Urkundennummer und Unterschrift, dazu Strömipedia",
            "und Riegenkarten – das Löschen eines Kontos auf dev erreicht sie nicht. Im Klon der Entwicklung:"]
log = logging.getLogger(__name__)


# --- Bestandsaufnahme --------------------------------------------------------------------------------------------

def einordnen(conn):
    """Tabellen des Moduls, die weder BESTAND noch BLEIBT noch TEILWEISE kennt (ein neuer Schemaschritt) – leer, wenn
    alles eingeordnet ist."""
    bekannt = set(BESTAND) | set(VOLLTEXT_BESTAND) | set(BLEIBT) | set(TEILWEISE)
    return sorted(set(zr._tabellen(conn)) - bekannt)


def _schluessel(name):
    return os.path.splitext(name or "")[0]


def _fotos(conn, sql):
    """Die Schlüssel (Dateiname ohne Endung) der Fotos aus einer Abfrage – Spalte mit einem Namen oder einer JSON-Liste."""
    out = set()
    for (wert,) in conn.execute(sql):
        if not wert:
            continue
        if wert.startswith("["):
            try:
                namen = json.loads(wert)
            except ValueError:
                continue
            out |= {_schluessel(n) for n in namen if isinstance(n, str) and n}
        else:
            out.add(_schluessel(wert))
    return out - {""}


def _medien(conn):
    """[(relativer Pfad, voller Pfad)] der Dateien und Ordner, die in die Sicherung wandern: Fotos des Bestands (Ordner,
    Befunde, Mängel – ohne die Schlüssel, die ein Produktbild oder eine Produktmeldung nennt), media/material/anhang und
    pdf/ ohne pdf/lebenslauf (Zählerdateien der Lebenslauf-Kennungen)."""
    from . import katalog, protokoll
    daten = current_app.config["DATA_DIR"]
    medien = katalog.medien_dir()
    bestand = (_fotos(conn, "SELECT photo FROM mat_folder") | _fotos(conn, "SELECT photo FROM mat_inspection_result")
               | _fotos(conn, "SELECT photos_json FROM mat_defect_report"))
    bestand -= (_fotos(conn, "SELECT image FROM mat_product") | _fotos(conn, "SELECT photos_json FROM mat_product_request"))
    out = []
    for art in FOTO_ARTEN:
        ordner = os.path.join(medien, art)
        try:
            namen = sorted(os.listdir(ordner))
        except OSError:
            continue
        out += [(os.path.relpath(os.path.join(ordner, n), daten), os.path.join(ordner, n)) for n in namen
                if _schluessel(n) in bestand and os.path.isfile(os.path.join(ordner, n))]
    anhang = os.path.join(medien, "anhang")
    if os.path.lexists(anhang):
        out.append((os.path.relpath(anhang, daten), anhang))
    pdf = protokoll.ablage()
    try:
        namen = sorted(os.listdir(pdf))
    except OSError:
        namen = []
    out += [(os.path.relpath(os.path.join(pdf, n), daten), os.path.join(pdf, n)) for n in namen if n != "lebenslauf"]
    return out


def _verweise_auf_konten(conn):
    """[(Tabelle, Spalte)] aller Fremdschlüssel auf users – außerhalb der Tabellen des Bestands."""
    out = []
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite\\_%' "
                             "ESCAPE '\\' ORDER BY name").fetchall():
        if t in BESTAND:
            continue
        out += [(t, r[3]) for r in conn.execute(f'PRAGMA foreign_key_list("{t}")') if r[2] == "users"]
    return out


def demo_konten(conn):
    """(löschbar, bleiben): löschbar [(id, E-Mail, Name)] die DEMO-Konten des Beispielbestands, auf die nach dem Leeren
    nichts mehr verweist; bleiben [(E-Mail, Name, Grund)] die übrigen Konten mit @example.invalid. Ein Verweis im
    Journal zählt nicht, wenn der Eintrag mitgeht (Bestand oder ein Eintrag an einem löschbaren DEMO-Konto) – deshalb
    bis zum Fixpunkt."""
    kandidaten, bleiben = {}, []
    for uid, mail, name in conn.execute("SELECT id, email, name FROM users WHERE lower(email) LIKE ? ORDER BY email",
                                        ("%" + zr.DEMO_POSTFACH,)).fetchall():
        if DEMO_KONTEN.fullmatch((mail or "").lower()) and (name or "").startswith("DEMO"):
            kandidaten[uid] = (mail, name)
        else:
            bleiben.append((mail, name, "nicht aus dem Beispielbestand"))
    spalten = _verweise_auf_konten(conn)
    gruende = {}
    while True:
        ids = [u for u in kandidaten if u not in gruende]
        neu = {}
        for uid in ids:
            for t, s in spalten:
                bedingung = f'"{s}" = ?'
                werte = [uid]
                if t == "mat_audit":
                    bedingung += (f" AND entity NOT IN ({','.join('?' * len(JOURNAL_BESTAND))}) AND NOT (entity = 'user' "
                                  f"AND entity_id IN ({','.join('?' * len(ids))}))")
                    werte += [*JOURNAL_BESTAND, *ids]
                if conn.execute(f'SELECT 1 FROM "{t}" WHERE {bedingung} LIMIT 1', werte).fetchone():
                    neu[uid] = f"Verweis aus {t}.{s}"
                    break
        if not neu:
            break
        gruende.update(neu)
    loeschbar = [(u, m, n) for u, (m, n) in kandidaten.items() if u not in gruende]
    bleiben += [(kandidaten[u][0], kandidaten[u][1], g) for u, g in gruende.items()]
    return loeschbar, sorted(bleiben)


def bestand(conn):
    """Was das Leeren träfe und was bleibt: Zeilen je Tabelle des Bestands, Journaleinträge je Entität, Merker, Medien,
    DEMO-Konten, Größe der Datenbank. Wirft Gescheitert, wenn eine Tabelle oder Entität nicht eingeordnet ist."""
    fremd = einordnen(conn)
    if fremd:
        raise zr.Gescheitert(f"Nicht eingeordnete Tabellen des Moduls: {', '.join(fremd)} – nichts geändert. Erst in "
                             "services/bestand_leeren.py einordnen (Bestand oder bleibt).")
    entitaeten = dict(conn.execute("SELECT entity, COUNT(*) FROM mat_audit GROUP BY entity").fetchall())
    fremd = sorted(set(entitaeten) - set(JOURNAL_BESTAND) - set(JOURNAL_BLEIBT))
    if fremd:
        raise zr.Gescheitert(f"Journal mit nicht eingeordneten Entitäten: {', '.join(fremd)} – nichts geändert. Erst in "
                             "services/bestand_leeren.py einordnen.")
    loeschbar, bleiben = demo_konten(conn)
    ids = [u for u, _, _ in loeschbar]
    konto_journal = conn.execute(f"SELECT COUNT(*) FROM mat_audit WHERE entity = 'user' AND entity_id IN "
                                 f"({','.join('?' * len(ids))})", ids).fetchone()[0] if ids else 0
    medien = _medien(conn)
    dateien = groesse = 0
    for _, pfad in medien:
        if os.path.isdir(pfad) and not os.path.islink(pfad):
            n, g = zr._groesse(pfad)
        else:
            n, g = 1, os.lstat(pfad).st_size
        dateien, groesse = dateien + n, groesse + g
    seiten, seite = conn.execute("PRAGMA page_count").fetchone()[0], conn.execute("PRAGMA page_size").fetchone()[0]
    alle = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t, art in sorted(zr._tabellen(conn).items()) if art == "table"}
    return {"zeilen": {t: alle[t] for t in BESTAND}, "alle": alle,
            "journal": {e: entitaeten.get(e, 0) for e in JOURNAL_BESTAND}, "konto_journal": konto_journal,
            "journal_bleibt": sum(n for e, n in entitaeten.items() if e not in JOURNAL_BESTAND) - konto_journal,
            "merker": [m for m in MERKER if conn.execute("SELECT 1 FROM mat_meta WHERE schluessel = ?", (m,)).fetchone()],
            "meldungen": conn.execute("SELECT COUNT(*) FROM mat_product_request WHERE folder_id IS NOT NULL").fetchone()[0],
            "medien": medien, "medien_dateien": dateien, "medien_bytes": groesse,
            "demo_loeschen": loeschbar, "demo_bleiben": bleiben, "db_bytes": seiten * seite,
            "konten": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "katalog": {t: alle[t] for t in BLEIBT if t in alle}}


# --- Texte ---------------------------------------------------------------------------------------------------------

def _bleibt(b):
    k = b["katalog"]
    return [f"Bleibt: Katalog (Kategorien {k.get('mat_category', 0)}, Produkte {k.get('mat_product', 0)}, Dokumente "
            f"{k.get('mat_product_document', 0)}), Prüfformulare (Pool {k.get('mat_formular', 0)}, Versionen "
            f"{k.get('mat_form', 0)}, Zuweisungen {k.get('mat_formular_zuweisung', 0)}), Rückrufe {k.get('mat_recall', 0)}, "
            f"Produktmeldungen {k.get('mat_product_request', 0)}, Journal an Katalog und Konten ({b['journal_bleibt']} "
            "Einträge), die übrigen Konten, Strömipedia, Ankerplätze, Riegenkarten, Einstellungen. Die Zähler (Inventar-, "
            "STR-, Protokoll- und Lebenslaufnummern) laufen weiter – keine Nummer wird zweimal vergeben."]


def _konten_text(b, schon):
    zeilen = []
    if b["demo_loeschen"]:
        zeilen += [f"DEMO-Konten des Beispielbestands {schon} ({len(b['demo_loeschen'])}):"]
        zeilen += [f"  {mail} ({name})" for _, mail, name in b["demo_loeschen"]]
    if b["demo_bleiben"]:
        zeilen += ["Konten mit @example.invalid, die bleiben:"]
        zeilen += [f"  {mail} ({name}) – {grund}" for mail, name, grund in b["demo_bleiben"]]
    return zeilen


def _zeilen_text(b):
    breite = max((len(t) for t in b["zeilen"]), default=0)
    zeilen = [f"  {t:<{breite}}  {n:>7}" for t, n in b["zeilen"].items() if n]
    leer = sum(1 for n in b["zeilen"].values() if not n)
    j = b["journal"]
    zeilen.append(f"  {len(b['zeilen'])} Tabellen ({leer} davon leer), {sum(b['zeilen'].values())} Zeilen; dazu "
                  f"{sum(j.values())} Journaleinträge (" + ", ".join(f"{e} {n}" for e, n in j.items())
                  + f") und {b['konto_journal']} an DEMO-Konten, Volltextindex der Artikel.")
    if b["merker"]:
        zeilen.append(f"  Merker des Beispielbestands: {', '.join(b['merker'])}")
    if b["meldungen"]:
        zeilen.append(f"  Produktmeldungen mit Ordner: {b['meldungen']} – sie bleiben, nur ohne Ordner.")
    return zeilen


def trocken_text(b, ziel):
    """Der Probelauf für die Kommandozeile."""
    zeilen = ["Probelauf – nichts geändert.", "", "Würde nach der Sicherung gelöscht (Tabellen des Bestands mit Zeilen):"]
    zeilen += _zeilen_text(b)
    zeilen += ["", f"Würde in die Sicherung verschoben: {b['medien_dateien']} Dateien, {zr._mb(b['medien_bytes'])} "
                   "(Fotos des Bestands unter media/material, media/material/anhang, pdf/ ohne pdf/lebenslauf)"]
    if importauftrag.laeuft():
        zeilen.append("ACHTUNG Gerade läuft ein Katalogimport – der echte Lauf bräche jetzt ab, ohne etwas zu ändern.")
    frei = shutil.disk_usage(current_app.config["DATA_DIR"]).free
    zeilen += ["", f"Sicherung nach: {ziel} (Datenbank {zr._mb(b['db_bytes'])}, frei {zr._mb(frei)})"]
    zeilen += _bleibt(b) + _konten_text(b, "– würden gelöscht") + zr._aeltere_text(zr.aeltere_sicherungen())
    zeilen += ["", f"Wirklich leeren: derselbe Befehl mit {SCHALTER} statt --trocken, danach „docker compose restart“. "
                   "Vorher einen laufenden Beispielbestand abbrechen; während des Laufs nicht auf dev pushen und den "
                   "Container nicht neu starten."]
    return "\n".join(zeilen)


def bericht_text(e):
    """Der Bericht nach dem Leeren."""
    b = e["vorher"]
    zeilen = [f"Bestand der Materialablage geleert. Sicherung: {e['sicherung']}",
              f"  Datenbank (vorher, ganz): stroemis.db, {zr._mb(b['db_bytes'])}",
              f"  Medien des Bestands: {b['medien_dateien']} Dateien, {zr._mb(b['medien_bytes'])} verschoben", "",
              "Geleert:"]
    zeilen += _zeilen_text(b)
    zeilen += [f"Schema unverändert (Version {e['version']}), Trigger wieder angelegt."]
    if e.get("start_fehler"):
        zeilen.append(f"ACHTUNG Die Startschritte des Moduls scheiterten ({e['start_fehler']}) – der Neustart holt "
                      "sie nach.")
    zeilen += _bleibt(b) + _konten_text(b, "gelöscht")
    zeilen += ["", "Jetzt den Container neu starten: docker compose restart",
               f"Rückweg: {os.path.join(e['sicherung'], 'LIESMICH.txt')}",
               "", "Die Sicherung enthält alle Konten mit Passwort-Hash, Urkundennummern, Strömipedia und Riegenkarten – "
               "löschen, sobald der Neustart und ein erster Test geklappt haben:",
               f"  rm -rf data/{os.path.basename(e['sicherung'])}"]
    zeilen += zr._aeltere_text(e.get("aeltere"))
    return "\n".join(zeilen)


def _liesmich(ordner, zeit, fertig):
    """Was in der Sicherung liegt und wie es zurückgeht – auf dem VPS im Klon der Entwicklung. Die Medien liegen unter
    denselben relativen Pfaden wie unter data/; „cp -a“ legt sie zurück (in vorhandene Ordner hinein, die seither
    entstandenen bleiben daneben). fertig=False: vor dem ersten Verschieben – Rückweg für einen abgebrochenen Lauf
    (Datenbank unverändert); nach dem COMMIT überschreibt fertig=True ihn mit dem vollen Rückweg."""
    name = os.path.basename(ordner)
    kopf = [f"Sicherung vor „flask material dev-bestand-leeren“ am {zeit:%d.%m.%Y um %H:%M:%S}.", ""]
    inhalt = [f"{'stroemis.db':<15}die ganze Datenbank vorher (alle Module, Backup-API)",
              f"{'media/, pdf/':<15}die Medien des Bestands, vorher unter data/media bzw. data/pdf, hierher verschoben"]
    zurueck = [f"  for t in media pdf; do [ -d data/{name}/$t ] && cp -a data/{name}/$t data/; done"]
    loeschen = ["", *LOESCHEN, "", f"  rm -rf data/{name}"]
    sudo = ["(data/ gehört dem Nutzer 1000 – ist das nicht dein Nutzer, rm, cp und chown mit sudo.)"]
    if not fertig:
        text = kopf + [
            "LAUF UNVOLLSTÄNDIG, solange dieser Absatz hier steht: Der Lauf wurde nach dem Sichern abgebrochen (etwa",
            "Container neu gestartet oder Verbindung weg). Die Datenbank ist dann unverändert – SQLite verwirft den",
            "offenen Umbau –, nur ein Teil der Medien des Bestands liegt hier. Zurück im Klon der Entwicklung:", *sudo, "",
            "  docker compose stop", *zurueck, "  sudo chown -R 1000:1000 data", "  docker compose up -d", "", *inhalt,
            *loeschen]
    else:
        text = kopf + inhalt + [
            "", "Rückweg im Klon der Entwicklung – was seit dem Leeren auf dev entstand, auch an Konten, Katalog,",
            "Strömipedia, Ankerplätzen und Riegenkarten, geht dabei verloren:", *sudo, "",
            "  docker compose stop",
            "  rm -f data/stroemis.db-wal data/stroemis.db-shm",
            f"  cp data/{name}/stroemis.db data/stroemis.db", *zurueck,
            "  sudo chown -R 1000:1000 data", "  docker compose up -d", *loeschen]
    zr._schreiben(os.path.join(ordner, "LIESMICH.txt"), "\n".join(text) + "\n")


# --- Leeren --------------------------------------------------------------------------------------------------------

def sicherungsziel(jetzt=None):
    """<DATA_DIR>/sicherung-bestand-<JJJJ-MM-TT_hhmmss> (deutsche Zeit) – noch nicht angelegt."""
    stempel = (jetzt or datetime.now(ZONE)).strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(current_app.config["DATA_DIR"], f"{SICHERUNG_VORSATZ}{stempel}")


def _schema(conn):
    return conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()


def _ziele_ohne_artikel(conn):
    """„Zuletzt besucht“ der Startseite (start:ziele:<Konto>, app/start.py): die Artikel der Materialablage heraus – ihre
    Kennungen werden neu vergeben, ein alter Eintrag zeigte sonst auf einen anderen Artikel. Alben und Lehrgänge bleiben."""
    from ... import start
    vorsatz = start.ZIELE.format(uid="")
    for schluessel, wert in conn.execute("SELECT schluessel, wert FROM mat_meta WHERE substr(schluessel, 1, ?) = ?",
                                         (len(vorsatz), vorsatz)).fetchall():
        try:
            liste = json.loads(wert)
        except ValueError:
            continue
        if not isinstance(liste, list):
            continue
        rest = [z for z in liste if not (isinstance(z, list) and z and z[0] == "material")]
        if rest != liste:
            conn.execute("UPDATE mat_meta SET wert = ? WHERE schluessel = ?", (json.dumps(rest), schluessel))


def _loeschen(conn, b):
    """Die Zeilen des Bestands löschen – unter der exklusiven Transaktion, Fremdschlüssel aus. Die Trigger der berührten
    Tabellen gehen vorher weg und kommen danach mit ihrem genauen SQL wieder (der Aufrufer prüft sqlite_master)."""
    from ... import einfuehrung, start
    from . import anleitung
    beruehrt = set(BESTAND) | {"mat_audit", "mat_meta", "mat_product_request", "users"}
    trigger = [(name, sql) for name, tbl, sql in conn.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger' ORDER BY rowid").fetchall() if tbl in beruehrt]
    for name, _ in trigger:
        conn.execute(f'DROP TRIGGER "{name}"')
    for t in BESTAND:
        conn.execute(f'DELETE FROM "{t}"')
    conn.execute(f"DELETE FROM mat_audit WHERE entity IN ({','.join('?' * len(JOURNAL_BESTAND))})", JOURNAL_BESTAND)
    conn.execute("UPDATE mat_product_request SET folder_id = NULL WHERE folder_id IS NOT NULL")
    conn.execute(f"DELETE FROM mat_meta WHERE schluessel IN ({','.join('?' * len(MERKER))})", MERKER)
    _ziele_ohne_artikel(conn)
    for uid, _, _ in b["demo_loeschen"]:
        conn.execute("DELETE FROM mat_audit WHERE entity = 'user' AND entity_id = ?", (uid,))
        # Merker des Kontos (wie api_admin.delete_user, dazu das Willkommen der Materialablage).
        conn.execute("DELETE FROM mat_meta WHERE schluessel IN (?, ?, ?, ?)",
                     (start.BESUCH.format(uid=uid), start.ZIELE.format(uid=uid), einfuehrung.SCHLUESSEL.format(uid=uid),
                      anleitung.WILLKOMMEN.format(uid=uid)))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    for v in VOLLTEXT_BESTAND:
        conn.execute(f"INSERT INTO \"{v}\" (\"{v}\") VALUES ('rebuild')")
    for _, sql in trigger:
        conn.execute(sql)


def leeren(jetzt=None):
    """Sichern, verschieben, löschen (siehe oben). Liefert {"sicherung", "vorher", "version", "zeit", "start_fehler",
    "aeltere"}; Gescheitert mit Klartext, wenn nichts geändert wurde oder – nur, wenn das Zurückschieben der Medien
    selbst scheitert – was wo liegt. sperrgrund() prüft der Aufrufer vorher."""
    from .. import START_SCHRITTE
    db_pfad = current_app.config["DB_PATH"]
    jetzt = jetzt or datetime.now(ZONE)
    try:
        sperre = importauftrag.anhalten()
    except OSError as exc:
        raise zr.Gescheitert(f"Die Sperre des Katalogimports ließ sich nicht nehmen ({exc}) – nichts geändert.") from exc
    if sperre is None:
        raise zr.Gescheitert("Gerade läuft ein Katalogimport (Hinweis oben auf der Katalogseite) – nichts geändert. "
                             "Warten, bis er zu Ende ist, dann erneut.")
    conn = sqlite3.connect(db_pfad, timeout=zr.WARTEN, isolation_level=None)
    try:
        if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise zr.Gescheitert("Die Datenbank läuft nicht im WAL-Modus – die Sicherung unter der Sperre ginge so "
                                 "nicht. Nichts geändert; einmal den Container starten, dann erneut.")
        groesse = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
        frei = shutil.disk_usage(current_app.config["DATA_DIR"]).free
        if frei < groesse + zr.RESERVE:
            raise zr.Gescheitert(f"Zu wenig Platz für die Sicherung: frei {zr._mb(frei)}, gebraucht "
                                 f"{zr._mb(groesse + zr.RESERVE)} – nichts geändert.")
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise zr.Gescheitert(f"Die Datenbank ist belegt ({exc}) – nichts geändert. Später erneut, oder den "
                                 "Container vorher neu starten.") from exc
        try:
            vorher = bestand(conn)                      # Gescheitert bei Uneingeordnetem – noch ist nichts angelegt
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        ordner = zr._ordner_anlegen(sicherungsziel(jetzt))
        verschoben = []
        with zr._signale_abfangen() as zustand:
            try:
                zr._sichern(db_pfad, ordner, vorher["alle"])
                _liesmich(ordner, jetzt, fertig=False)
                for rel, quelle in vorher["medien"]:
                    ziel = os.path.join(ordner, rel)
                    os.makedirs(os.path.dirname(ziel), mode=0o700, exist_ok=True)
                    os.rename(quelle, ziel)                 # nie kopieren; ein anderes Dateisystem scheitert hier
                    verschoben.append((quelle, ziel))
                schema = _schema(conn)
                version = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0]
                verstoesse = set(conn.execute("PRAGMA foreign_key_check").fetchall())
                _loeschen(conn, vorher)
                if _schema(conn) != schema:
                    raise sqlite3.DatabaseError("Schema oder Trigger nach dem Leeren anders als vorher")
                neu = set(conn.execute("PRAGMA foreign_key_check").fetchall()) - verstoesse
                if neu:
                    raise sqlite3.DatabaseError(f"Fremdschlüssel verletzt: {sorted(neu)[:5]}")
                pruefung = conn.execute("PRAGMA quick_check").fetchone()[0]
                if pruefung != "ok":
                    raise sqlite3.DatabaseError(f"quick_check: {pruefung}")
                rest = {t: n for t in BESTAND if (n := conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])}
                if rest:
                    raise sqlite3.DatabaseError(f"nach dem Leeren übrig: {rest}")
                zustand["fertig"] = True                    # ein Signal ab hier bricht nicht mehr ab
                conn.execute("COMMIT")
            except BaseException as exc:
                zustand["abbruch"] = True                   # ein Signal unterbricht den Rückweg nicht
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                _zurueck(ordner, verschoben, exc, [os.path.join(ordner, rel) for rel, _ in vorher["medien"]])
                raise
    finally:
        conn.close()
        sperre.close()
    e = {"sicherung": ordner, "vorher": vorher, "version": int(version), "zeit": jetzt, "start_fehler": None,
         "aeltere": zr.aeltere_sicherungen(ausser=ordner)}
    _liesmich(ordner, jetzt, fertig=True)
    # Wie beim Start (db.init_db): eine eigene Verbindung, jeder Schritt mit seiner eigenen Transaktion.
    start = sqlite3.connect(db_pfad, timeout=zr.WARTEN)
    try:
        for schritt in START_SCHRITTE:
            schritt(start)
    except Exception as exc:                            # das Leeren selbst ist geschehen
        log.exception("Startschritte nach dem Leeren des Bestands gescheitert")
        e["start_fehler"] = str(exc)
    finally:
        start.close()
    if int(version) != models.SCHEMA_VERSION:           # nur ein Hinweis: das Leeren ändert die Version nicht
        log.warning("Schemaversion %s, erwartet %s", version, models.SCHEMA_VERSION)
    log.warning("Bestand der Materialablage geleert (dev): %d Zeilen, %d Dateien verschoben, %d DEMO-Konten; "
                "Sicherung %s", sum(vorher["zeilen"].values()), vorher["medien_dateien"], len(vorher["demo_loeschen"]),
                ordner)
    return e


def _zurueck(ordner, verschoben, exc, geplant):
    """Nach einem Abbruch vor dem COMMIT: die Medien zurück an ihren Platz und die eigene Sicherung wieder weg – nur,
    wenn alles zurück ist, und nur mit genauen Pfaden (os.rmdir entfernt nie einen Ordner mit Inhalt). geplant: alle
    Ziele in der Sicherung – auch die, deren Ordner schon angelegt war, als das Verschieben scheiterte."""
    liegen = []
    for quelle, ziel in reversed(verschoben):
        try:
            os.rename(ziel, quelle)
        except OSError as fehler:
            liegen.append(f"{ziel} (gehört nach {quelle}: {fehler})")
    if liegen:
        raise zr.Gescheitert(f"Abgebrochen ({exc}); die Datenbank ist unverändert, aber nicht alle Medien ließen sich "
                             f"zurückschieben – sie liegen noch in der Sicherung: {'; '.join(liegen[:20])}") from exc
    for rest in ("stroemis.db", "stroemis.db-journal", "LIESMICH.txt"):
        try:
            os.remove(os.path.join(ordner, rest))
        except OSError:
            pass
    leere = set()
    for ziel in geplant:
        d = os.path.dirname(ziel)
        while d.startswith(ordner + os.sep):
            leere.add(d)
            d = os.path.dirname(d)
    for leer in sorted(leere | {ordner}, key=len, reverse=True):
        try:
            os.rmdir(leer)
        except OSError:
            pass
    if not isinstance(exc, zr.Gescheitert):
        raise zr.Gescheitert(f"Abgebrochen ({exc}) – nichts geändert: Datenbank unverändert, Medien zurück an ihrem "
                             "Platz.") from exc
