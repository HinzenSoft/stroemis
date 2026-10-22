"""Herstellerdokumente einmal je Inhalt (Schritt 18, 22.10.2026): den Altbestand zusammenführen.

Bis Schritt 17 bekam jede hochgeladene oder importierte Dokumentdatei einen Zufallsnamen unter media/material/dok;
der Katalogimport einer Karabiner-Lieferung hätte so eine Gebrauchsanleitung für 89 Produkte 89-mal abgelegt. Seit
Schritt 18 heißt eine Datei nach ihrem Inhalt (<SHA-256><Endung>, katalog.inhaltsname) und gehört allen Zeilen von
mat_product_document mit diesem Inhalt; weg kommt sie erst, wenn keine Zeile sie mehr nennt (katalog._datei_freigeben).

zusammenfuehren bringt die vorhandenen Dateien einmal auf die neuen Namen – mit der SHA-256 aus der Datei, nicht aus der
Datenbank (ältere Zeilen haben keine oder eine fremde): Je Datei entsteht der Inhaltsname als harter Verweis (Kopie, wo
das Dateisystem keine Verweise kann), die Zeilen bekommen den neuen Namen, Prüfsumme und Größe; erst nach dem Commit
verschwinden die alten Namen. Bricht der Prozess vor dem Commit ab, stehen beide Namen da und der nächste Lauf findet
die alte Datei wieder vor – nichts geht verloren, nichts passiert zweimal. Bricht er nach dem Commit ab (oder scheitert
das Entfernen), nennt keine Zeile die alten Namen mehr: Solche Dateien ohne Zeile zählt jeder Lauf (aufraeumen) und
entfernt die, deren Inhalt unter seinem Inhaltsnamen liegt und von einer Zeile genannt wird; alle anderen bleiben und
stehen im Bericht. Zwischendateien (Punkt davor) älter als einen Tag stammen aus einem Absturz und gehen weg. Eine
Zeile, deren Datei fehlt, behält ihren Namen und steht als Warnung im Log. Fehlt gleich der ganze Ordner (Medien beim
Start nicht erreichbar), tut der Lauf nichts und meldet das; das Kennzeichen bleibt offen, der nächste Start versucht
es wieder.

Läuft beim Start nach der Migration (beim_start, Kennzeichen mat_meta.dok_inhalt – Schritt 18 setzt es auf „0“, der
erste vollständige Lauf auf „1“; danach nur noch das Aufräumen) und jederzeit von Hand: flask material
dok-zusammenfuehren [--probe]."""
import hashlib
import logging
import os
import shutil
import time

from .katalog import inhaltsname

KENNZEICHEN = "dok_inhalt"
# Eine Zwischendatei (Punkt davor), die so lange liegt, gehört zu keinem laufenden Upload, Import oder Kopieren mehr.
ZWISCHENDATEI_ALTER = 24 * 3600
log = logging.getLogger(__name__)


def _summe(pfad):
    summe = hashlib.sha256()
    with open(pfad, "rb") as fh:
        for stueck in iter(lambda: fh.read(1024 * 1024), b""):
            summe.update(stueck)
    return summe.hexdigest()


def _bestand(ordner):
    """(Zahl, Bytes) der Dokumentdateien im Ordner – ohne Zwischendateien (Punkt davor)."""
    zahl = groesse = 0
    try:
        for name in os.listdir(ordner):
            pfad = os.path.join(ordner, name)
            if not name.startswith(".") and os.path.isfile(pfad):
                zahl += 1
                groesse += os.path.getsize(pfad)
    except OSError:
        pass
    return zahl, groesse


def _verweisen(quelle, ziel):
    """Den Inhaltsnamen anlegen, ohne die alte Datei anzurühren: harter Verweis, sonst Kopie über eine Zwischendatei."""
    try:
        os.link(quelle, ziel)
        return
    except FileExistsError:
        raise
    except OSError:
        pass
    zwischen = os.path.join(os.path.dirname(ziel), "." + os.path.basename(ziel) + ".teil")   # Punkt davor: Zwischendatei
    try:
        shutil.copyfile(quelle, zwischen)
        os.replace(zwischen, ziel)
    except OSError:
        try:
            os.remove(zwischen)
        except OSError:
            pass
        raise


def _bericht(probe):
    return {"zeilen": 0, "umbenannt": 0, "zusammengefuehrt": 0, "berichtigt": 0, "umgeschrieben": 0, "bytes_frei": 0,
            "fehlend": [], "waisen": 0, "waisen_bytes": 0, "waisen_entfernt": 0, "zwischendateien": 0,
            "ordner_fehlt": False, "probe": probe, "vollstaendig": False, "erledigt": False}


def aufraeumen(ordner, genannt, b, probe=False):
    """Der Ordner nach den Zeilen: Dateien, die keine Zeile nennt (Waisen – alte Namen aus einem Abbruch zwischen
    Commit und Entfernen oder aus gescheitertem Entfernen), zählen; die, deren Inhalt schon unter seinem Inhaltsnamen
    liegt und von einer Zeile genannt wird, gehen weg (Dubletten), alle anderen bleiben und stehen im Bericht – sie
    könnten von Hand hingelegt sein. Zwischendateien (Punkt davor: .neu-… vom Hochladen und Import, .<sha><ext>.teil
    vom Kopieren) älter als ZWISCHENDATEI_ALTER stammen aus einem Absturz und gehen weg; jüngere gehören einem laufenden
    Vorgang. Eine Datei, die schon ihren Inhaltsnamen trägt, bleibt immer (ein Import legt seine Dateien vor der
    Transaktion ab, die Zeilen kommen erst danach). genannt: die Dateinamen, die nach dem Lauf eine Zeile nennt."""
    try:
        namen = sorted(os.listdir(ordner))
    except OSError:
        return
    grenze = time.time() - ZWISCHENDATEI_ALTER
    for name in namen:
        pfad = os.path.join(ordner, name)
        if name in genannt or not os.path.isfile(pfad):
            continue
        try:
            if name.startswith("."):
                if os.path.getmtime(pfad) < grenze:
                    b["zwischendateien"] += 1
                    if not probe:
                        os.remove(pfad)
                continue
            groesse = os.path.getsize(pfad)
            neu = inhaltsname(_summe(pfad), os.path.splitext(name)[1].lower())
        except OSError as exc:                          # zwischendurch verschwunden oder nicht lesbar
            log.warning("Dokumentdatei %s ohne Zeile ließ sich nicht prüfen: %s", name, exc)
            continue
        if neu != name and neu in genannt:
            b["waisen_entfernt"] += 1
            b["bytes_frei"] += groesse
            if not probe:
                try:
                    os.remove(pfad)
                except OSError as exc:
                    log.warning("Alte Dokumentdatei %s ließ sich nicht entfernen: %s", name, exc)
        else:
            b["waisen"] += 1
            b["waisen_bytes"] += groesse


def zusammenfuehren(conn, ordner, probe=False, nur_wenn_offen=False):
    """Alle Dokumentdateien auf ihren Inhaltsnamen bringen; liefert den Bericht. probe: nur rechnen, nichts ändern.
    nur_wenn_offen: unter der Schreibsperre das Kennzeichen lesen und die Zeilen in Ruhe lassen, wenn es schon auf
    „1“ steht (beim Start – die anderen Arbeitsprozesse warten auf die Sperre und finden es dann gesetzt); der Ordner
    wird trotzdem aufgeräumt (aufraeumen – Waisen nach einem Abbruch zwischen Commit und Entfernen, alte
    Zwischendateien), ebenfalls unter der Sperre, damit es nur einer tut. conn ist eine rohe sqlite3-Verbindung; beim
    Start gibt es noch keinen Anfragekontext."""
    b = _bericht(probe)
    if not probe:
        conn.execute("BEGIN IMMEDIATE")
    try:
        if nur_wenn_offen:
            stand = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = ?", (KENNZEICHEN,)).fetchone()
            b["erledigt"] = bool(stand and stand[0] == "1")
        zeilen = conn.execute("SELECT id, title, file_path, sha256, size FROM mat_product_document "
                              "WHERE file_path IS NOT NULL ORDER BY file_path, id").fetchall()
        b["zeilen"] = len(zeilen)
        b["dateien_vorher"], b["bytes_vorher"] = _bestand(ordner)
        b["dateien_nachher"], b["bytes_nachher"] = b["dateien_vorher"], b["bytes_vorher"]
        if zeilen and not os.path.isdir(ordner):
            b["ordner_fehlt"] = True
            return b
        nach_name = {}
        for z in zeilen:
            nach_name.setdefault(z[2], []).append(z)
        alte_namen, neue_namen, genannt = [], set(), set(nach_name)
        if b["erledigt"]:
            aufraeumen(ordner, genannt, b)
            b["dateien_nachher"], b["bytes_nachher"] = _bestand(ordner)
            b["vollstaendig"] = True
            return b
        for name, gruppe in sorted(nach_name.items()):
            pfad = os.path.join(ordner, name)
            if "/" in name or "\\" in name or name.startswith(".") or not os.path.isfile(pfad):
                b["fehlend"].append({"name": name, "dokumente": [(z[0], z[1]) for z in gruppe]})
                continue
            ext = os.path.splitext(name)[1].lower()
            sha, groesse = _summe(pfad), os.path.getsize(pfad)
            neu = inhaltsname(sha, ext)
            falsch = sum(1 for z in gruppe if (z[3], z[4]) != (sha, groesse))
            b["berichtigt"] += falsch
            genannt.add(neu)
            if neu != name:
                genannt.discard(name)
                ziel = os.path.join(ordner, neu)
                if neu in neue_namen or os.path.isfile(ziel):
                    # Derselbe Inhalt liegt schon unter seinem Namen – die alte Datei ist eine Dublette.
                    if os.path.isfile(ziel) and os.path.getsize(ziel) != groesse:
                        log.warning("Dokumentdatei %s hat %d statt %d Bytes – durch %s (geprüft) ersetzt.",
                                    neu, os.path.getsize(ziel), groesse, name)
                        if not probe:
                            os.remove(ziel)
                            _verweisen(pfad, ziel)
                    b["zusammengefuehrt"] += 1
                    b["bytes_frei"] += groesse
                else:
                    if not probe:
                        _verweisen(pfad, ziel)
                    b["umbenannt"] += 1
                neue_namen.add(neu)
                alte_namen.append(pfad)
            if not probe and (neu != name or falsch):
                b["umgeschrieben"] += conn.execute(
                    "UPDATE mat_product_document SET file_path = ?, sha256 = ?, size = ? WHERE file_path = ?",
                    (neu, sha, groesse, name)).rowcount
        if not probe:
            conn.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, '1') "
                         "ON CONFLICT(schluessel) DO UPDATE SET wert = '1'", (KENNZEICHEN,))
            conn.commit()
    finally:
        if conn.in_transaction:
            conn.rollback()
    if not probe:
        for pfad in alte_namen:
            try:
                os.remove(pfad)
            except OSError as exc:
                log.warning("Alte Dokumentdatei %s ließ sich nicht entfernen: %s", os.path.basename(pfad), exc)
        aufraeumen(ordner, genannt, b)
        b["dateien_nachher"], b["bytes_nachher"] = _bestand(ordner)
    else:
        # Die alten Namen liegen noch; sie zählen nicht als Waisen (genannt enthält beide Namen jeder Gruppe nicht
        # mehr, deshalb hier die alten dazu).
        aufraeumen(ordner, genannt | set(nach_name), b, probe=True)
        b["dateien_nachher"] -= b["zusammengefuehrt"] + b["waisen_entfernt"]
        b["bytes_nachher"] -= b["bytes_frei"]
    b["vollstaendig"] = True
    return b


def _warnen(b):
    for f in b["fehlend"]:
        log.warning("Dokumentdatei fehlt unter media/material/dok: %s (%s) – die Zeile behält ihren Namen.", f["name"],
                    ", ".join(f"Dokument {did} „{titel}“" for did, titel in f["dokumente"]))


def beim_start(conn):
    """Nach der Migration, einmal (Kennzeichen in mat_meta) und nur von dem Arbeitsprozess, der die Schreibsperre
    zuerst bekommt – die anderen finden das Kennzeichen gesetzt vor."""
    pfad = conn.execute("PRAGMA database_list").fetchone()[2]
    if not pfad:
        return
    ordner = os.path.join(os.path.dirname(pfad), "media", "material", "dok")
    b = zusammenfuehren(conn, ordner, nur_wenn_offen=True)
    if b["erledigt"]:
        _aufgeraeumt_melden(b)                      # jeder Start räumt nur noch den Ordner auf – still, wenn nichts war
        return
    _warnen(b)
    if b["ordner_fehlt"]:
        log.warning("media/material/dok ist nicht erreichbar – die Zusammenführung der Herstellerdokumente (Schritt 18) "
                    "wartet auf den nächsten Start; %d Dokumente nennen eine Datei.", b["zeilen"])
        return
    if b["umbenannt"] or b["zusammengefuehrt"] or b["berichtigt"]:
        log.info("Herstellerdokumente einmal je Inhalt (Schritt 18): %d Dateien → %d, %.1f MB frei; %d umbenannt, "
                 "%d Dubletten zusammengeführt, %d Zeilen umgeschrieben, %d fehlend.", b["dateien_vorher"],
                 b["dateien_nachher"], b["bytes_frei"] / (1024 * 1024), b["umbenannt"], b["zusammengefuehrt"],
                 b["umgeschrieben"], len(b["fehlend"]))
    _aufgeraeumt_melden(b)


def _aufgeraeumt_melden(b):
    """Eine Logzeile, wenn aufraeumen etwas gefunden hat: Dateien ohne Zeile (die liegen bleiben) als Warnung,
    entfernte Dubletten und Zwischendateien als Info."""
    if b["waisen"]:
        log.warning("media/material/dok: %d Dateien ohne Zeile (%.1f MB) – sie bleiben liegen; Bericht mit "
                    "`flask material dok-zusammenfuehren --probe`.", b["waisen"], b["waisen_bytes"] / (1024 * 1024))
    if b["waisen_entfernt"] or b["zwischendateien"]:
        log.info("media/material/dok aufgeräumt: %d Dateien ohne Zeile entfernt (Inhalt liegt unter seinem "
                 "Inhaltsnamen), %d Zwischendateien älter als ein Tag entfernt.", b["waisen_entfernt"],
                 b["zwischendateien"])


def bericht_text(b):
    """Der Bericht für die Kommandozeile."""
    mb = 1024 * 1024
    zeilen = ["Probelauf – nichts geändert." if b["probe"] else "Zusammengeführt.",
              f"Dokumente mit Datei: {b['zeilen']}",
              f"Dateien vorher: {b['dateien_vorher']} ({b['bytes_vorher'] / mb:.1f} MB)"]
    if b["ordner_fehlt"]:
        zeilen.append("ACHTUNG media/material/dok ist nicht erreichbar – nichts geändert.")
        return "\n".join(zeilen)
    zeilen += [f"Dateien nachher: {b['dateien_nachher']} ({b['bytes_nachher'] / mb:.1f} MB), "
               f"frei: {b['bytes_frei'] / mb:.1f} MB",
               f"Umbenannt: {b['umbenannt']}, Dubletten zusammengeführt: {b['zusammengefuehrt']}, "
               f"Prüfsumme oder Größe berichtigt: {b['berichtigt']}"
               + ("" if b["probe"] else f", Zeilen umgeschrieben: {b['umgeschrieben']}"),
               f"Dateien ohne Zeile: {b['waisen']} ({b['waisen_bytes'] / mb:.1f} MB) – bleiben liegen; "
               f"{'zu entfernen' if b['probe'] else 'entfernt'}, weil der Inhalt unter seinem Inhaltsnamen liegt: "
               f"{b['waisen_entfernt']}",
               f"Zwischendateien älter als ein Tag {'zu entfernen' if b['probe'] else 'entfernt'}: {b['zwischendateien']}"]
    for f in b["fehlend"]:
        zeilen.append(f"ACHTUNG Datei fehlt: {f['name']} – "
                      + ", ".join(f"Dokument {did} „{titel}“" for did, titel in f["dokumente"]))
    return "\n".join(zeilen)
