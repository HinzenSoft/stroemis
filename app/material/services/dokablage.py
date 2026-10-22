"""Herstellerdokumente einmal je Inhalt (Schritt 18, 22.10.2026): den Altbestand zusammenführen.

Bis Schritt 17 bekam jede hochgeladene oder importierte Dokumentdatei einen Zufallsnamen unter media/material/dok;
der Katalogimport einer Karabiner-Lieferung hätte so eine Gebrauchsanleitung für 89 Produkte 89-mal abgelegt. Seit
Schritt 18 heißt eine Datei nach ihrem Inhalt (<SHA-256><Endung>, katalog.inhaltsname) und gehört allen Zeilen von
mat_product_document mit diesem Inhalt; weg kommt sie erst, wenn keine Zeile sie mehr nennt (katalog._datei_freigeben).

zusammenfuehren bringt die vorhandenen Dateien einmal auf die neuen Namen – mit der SHA-256 aus der Datei, nicht aus der
Datenbank (ältere Zeilen haben keine oder eine fremde): Je Datei entsteht der Inhaltsname als harter Verweis (Kopie, wo
das Dateisystem keine Verweise kann), die Zeilen bekommen den neuen Namen, Prüfsumme und Größe; erst nach dem Commit
verschwinden die alten Namen. Bricht der Prozess dazwischen ab, stehen beide Namen da und der nächste Lauf findet die
alte Datei wieder vor – nichts geht verloren, nichts passiert zweimal. Eine Zeile, deren Datei fehlt, behält ihren Namen
und steht als Warnung im Log. Fehlt gleich der ganze Ordner (Medien beim Start nicht erreichbar), tut der Lauf nichts
und meldet das; das Kennzeichen bleibt offen, der nächste Start versucht es wieder.

Läuft beim Start nach der Migration (beim_start, Kennzeichen mat_meta.dok_inhalt – Schritt 18 setzt es auf „0“, der
erste vollständige Lauf auf „1“) und jederzeit von Hand: flask material dok-zusammenfuehren [--probe]."""
import hashlib
import logging
import os
import shutil

from .katalog import inhaltsname

KENNZEICHEN = "dok_inhalt"
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
    zwischen = ziel + ".teil"
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
            "fehlend": [], "ordner_fehlt": False, "probe": probe, "vollstaendig": False, "erledigt": False}


def zusammenfuehren(conn, ordner, probe=False, nur_wenn_offen=False):
    """Alle Dokumentdateien auf ihren Inhaltsnamen bringen; liefert den Bericht. probe: nur rechnen, nichts ändern.
    nur_wenn_offen: unter der Schreibsperre das Kennzeichen lesen und nichts tun, wenn es schon auf „1“ steht (beim
    Start – die anderen Arbeitsprozesse warten auf die Sperre und finden es dann gesetzt). conn ist eine rohe
    sqlite3-Verbindung; beim Start gibt es noch keinen Anfragekontext."""
    b = _bericht(probe)
    if not probe:
        conn.execute("BEGIN IMMEDIATE")
    try:
        if nur_wenn_offen:
            stand = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = ?", (KENNZEICHEN,)).fetchone()
            if stand and stand[0] == "1":
                b["erledigt"] = b["vollstaendig"] = True
                return b
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
        alte_namen, neue_namen = [], set()
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
            if neu != name:
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
        b["dateien_nachher"], b["bytes_nachher"] = _bestand(ordner)
    else:
        b["dateien_nachher"] -= b["zusammengefuehrt"]
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
        return
    _warnen(b)
    if b["ordner_fehlt"]:
        log.warning("media/material/dok ist nicht erreichbar – die Zusammenführung der Herstellerdokumente (Schritt 18) "
                    "wartet auf den nächsten Start; %d Dokumente nennen eine Datei.", b["zeilen"])
    elif b["umbenannt"] or b["zusammengefuehrt"] or b["berichtigt"]:
        log.info("Herstellerdokumente einmal je Inhalt (Schritt 18): %d Dateien → %d, %.1f MB frei; %d umbenannt, "
                 "%d Dubletten zusammengeführt, %d Zeilen umgeschrieben, %d fehlend.", b["dateien_vorher"],
                 b["dateien_nachher"], b["bytes_frei"] / (1024 * 1024), b["umbenannt"], b["zusammengefuehrt"],
                 b["umgeschrieben"], len(b["fehlend"]))


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
               + ("" if b["probe"] else f", Zeilen umgeschrieben: {b['umgeschrieben']}")]
    for f in b["fehlend"]:
        zeilen.append(f"ACHTUNG Datei fehlt: {f['name']} – "
                      + ", ".join(f"Dokument {did} „{titel}“" for did, titel in f["dokumente"]))
    return "\n".join(zeilen)
