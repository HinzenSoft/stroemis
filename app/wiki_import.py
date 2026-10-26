"""Wiki: Seiten aus einem ZIP importieren (Wunsch vom 25.10.2026, W4).

Das Gegenstück zum Export „Abschnitt als ZIP herunterladen“ (api_wiki.export_page): Ein Export lässt sich ohne Änderung
wieder einlesen, ein selbst gepacktes Archiv mit Markdown-Dateien ebenso. Nur die Wiki-Verwaltung importiert
(api_wiki.import_pages); die Grenze der Anfrage setzt size_guard (WIKI_IMPORT_MAX_BYTES, Vorgabe 200 MB).

Ablauf – alles geprüft, bevor die erste Seite entsteht:
  1. Archiv: Zahl der Einträge und Größe des Inhaltsverzeichnisses aus dem Ende-Satz, bevor zipfile es einliest; keine
     doppelten Namen, nichts verschlüsselt, entpackt höchstens MAX_ENTPACKT, je Eintrag ab 1 MB ein Packverhältnis bis
     MAX_VERHAELTNIS. Gelesen wird nie mehr als die angegebene Größe.
  2. Pfade: nur schlichte relative Pfade – „..“, führender Schrägstrich, Rückstrich, Laufwerk, Steuerzeichen,
     symbolische Verweise und mehr als MAX_TIEFE Ebenen brechen ab. Still übergangen: Verzeichniseinträge, __MACOSX/,
     Teile mit führendem Punkt (.DS_Store) und Thumbs.db.
  3. Seiten sind *.md und *.markdown (UTF-8, auch mit BOM, ohne NUL, je höchstens MAX_REQUEST_LENGTH wie eine Seite im
     Editor; höchstens MAX_SEITEN, zusammen höchstens MAX_SEITEN_TEXT). Titel = erste Zeile „# …“ (Regel wie wiki.js
     titelZeile), sonst der Dateiname – dann steht „# <Titel>“ vorn, wie der Editor es schreibt.
  4. Baum: „A.md“ und der Ordner „A/“ sind dieselbe Seite, „A/B.md“ ist ihre Unterseite; ein Ordner ohne eigene .md wird
     eine Seite mit seinem Namen als Titel. Die oberste Ebene kommt unter die Zielseite, Geschwister in natürlicher
     Reihenfolge der Namen („2 …“ vor „10 …“), hinter die vorhandenen Geschwister.
  5. Anhänge: Dateien mit einer Wiki-Endung, auf die eine Seite verweist – abgelegt wie beim Hochladen (store_wiki_file:
     Bilder neu geschrieben, ohne EXIF), jede Archivdatei einmal. Videos werden übergangen (Entscheidung F6: einzeln
     hochladen – die Wandlung dauert Minuten), ebenso fremde Endungen und unbenutzte Dateien; das Ergebnis sagt es.
  6. Verweise außerhalb von Code: „](…)“ und src="…" auf „/media/wiki/<ref>“ (so schreibt der Export: Eintrag
     „media/<ref>“) oder relativ zur .md → die neue Datei; ein relativer Verweis auf eine importierte .md → /stroemipedia/<slug>.
     Fragment (#w=…) bleibt. Was sich nicht auflösen lässt, bleibt stehen und steht als Hinweis im Ergebnis.
  7. Geschrieben wird in EINER Transaktion (Seiten wie api_wiki.create_page: freie Adresse, Fassung, Verknüpfungen zu
     Dateien und Seiten); scheitert etwas, bleibt keine Seite und keine abgelegte Datei übrig. Keine Mails.
  8. Gleicher Titel unter derselben Zielseite (Entscheidung F5): Es entsteht trotzdem eine neue Seite mit eigener Adresse,
     die vorhandene bleibt unberührt; das Ergebnis nennt es.
  9. Freigabe und Lesebeschränkung werden nicht gesetzt – die neuen Seiten erben sie von der Zielseite."""
import os
import posixpath
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from urllib.parse import unquote

from flask import current_app
from werkzeug.datastructures import FileStorage

from . import api_wiki, db
from .images import VIDEO_EXT, WIKI_EXT, store_wiki_file

MAX_EINTRAEGE = 2000
MAX_VERZEICHNIS = 512 * 1024
MAX_ENTPACKT = 1024 ** 3
MAX_VERHAELTNIS = 100
MAX_SEITEN = 500
# Alle Seiten liegen beim Umschreiben zugleich im Arbeitsspeicher – 500 Seiten zu je 1 MB wären zu viel.
MAX_SEITEN_TEXT = 64 * 1024 * 1024
MAX_TIEFE = 20
MAX_TITEL = 200
# Je Art höchstens so viele Hinweise einzeln – ein Archiv mit 800 fremden Dateien soll nicht 800 Zeilen liefern.
MAX_HINWEISE = 50
SEITEN_EXT = (".md", ".markdown")

_LESEFEHLER = (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, RuntimeError, OSError,
               NotImplementedError, ValueError)
_TITEL_RE = re.compile(r"^[ \t]*#[ \t]+(.+?)[ \t]*#*[ \t]*$")
_ZAUN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_INLINE_CODE_RE = re.compile(r"(`+[^`\n]*?`+)")
# „](ziel)“ bzw. „](ziel "Titel")“ und „](<ziel mit Leerzeichen>)“; src="ziel" bzw. src='ziel'.
_LINK_RE = re.compile(r"(\]\(\s*)(<[^>\n]*>|[^)\s]+)")
_SRC_RE = re.compile(r"(\bsrc\s*=\s*)([\"'])(.*?)\2", re.IGNORECASE)
_FREMD_RE = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|//|#|/(?!media/wiki/))", re.IGNORECASE)


class ImportFehler(ValueError):
    """Ein Grund, aus dem der ganze Import nicht stattfindet – der Text darf dem Nutzer gezeigt werden."""

    def __init__(self, text, status=400):
        super().__init__(text)
        self.status = status


# --- 1. und 2.: Archiv und Pfade ------------------------------------------------------------------------------------

def _verzeichnis_pruefen(fh):
    """Zahl der Einträge und Größe des Inhaltsverzeichnisses aus dem Ende-Satz (wie im Katalogimport des Moduls
    Material) – bevor zipfile das Verzeichnis einliest und für jeden Eintrag ein Objekt anlegt."""
    try:
        ende = zipfile._EndRecData(fh)
    except _LESEFEHLER:
        ende = None
    if not ende:
        raise ImportFehler("Die Datei ist kein ZIP-Archiv oder beschädigt.")
    if ende[zipfile._ECD_ENTRIES_TOTAL] > MAX_EINTRAEGE:
        raise ImportFehler(f"Das Archiv hat {ende[zipfile._ECD_ENTRIES_TOTAL]} Einträge – höchstens {MAX_EINTRAEGE} "
                           "werden gelesen.")
    if ende[zipfile._ECD_SIZE] > MAX_VERZEICHNIS:
        raise ImportFehler(f"Das Inhaltsverzeichnis des Archivs ist {ende[zipfile._ECD_SIZE] // 1024} KB groß – "
                           f"höchstens {MAX_VERZEICHNIS // 1024} KB werden gelesen.")
    fh.seek(0)


def _pfad(info):
    """Der Pfad eines Eintrags als Liste seiner Teile – oder None für das, was still übergangen wird. Wirft bei allem,
    was in einem Wiki-Export nichts zu suchen hat."""
    name = info.filename
    kurz = name[:120]
    if "\x00" in name or re.search(r"[\x00-\x1f\x7f]", name):
        raise ImportFehler(f"„{kurz}“: Steuerzeichen im Dateinamen – so ein Archiv wird nicht gelesen.")
    if name.startswith("/") or "\\" in name or re.match(r"^[A-Za-z]:", name):
        raise ImportFehler(f"„{kurz}“ ist kein relativer Pfad im Archiv – so ein Archiv wird nicht gelesen.")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ImportFehler(f"„{kurz}“ ist ein symbolischer Verweis – so ein Archiv wird nicht gelesen.")
    teile = name.rstrip("/").split("/")
    if any(t in ("", ".", "..") for t in teile):
        raise ImportFehler(f"„{kurz}“ ist kein schlichter Pfad im Archiv – so ein Archiv wird nicht gelesen.")
    if len(teile) > MAX_TIEFE:
        raise ImportFehler(f"„{kurz}“ liegt tiefer als {MAX_TIEFE} Ebenen.")
    if info.is_dir() or teile[0] == "__MACOSX" or any(t.startswith(".") for t in teile) or teile[-1] == "Thumbs.db":
        return None
    return teile


def _archiv_oeffnen(fh):
    _verzeichnis_pruefen(fh)
    try:
        archiv = zipfile.ZipFile(fh)
        eintraege = archiv.infolist()
    except _LESEFEHLER:
        raise ImportFehler("Die Datei ist kein ZIP-Archiv oder beschädigt.")
    try:
        if len(eintraege) > MAX_EINTRAEGE:
            raise ImportFehler(f"Das Archiv hat {len(eintraege)} Einträge – höchstens {MAX_EINTRAEGE} werden gelesen.")
        gesehen, summe = set(), 0
        for i in eintraege:
            schluessel = unicodedata.normalize("NFC", i.filename)
            if schluessel in gesehen:
                raise ImportFehler(f"„{i.filename[:120]}“ steht doppelt im Archiv – so ein Archiv wird nicht gelesen.")
            gesehen.add(schluessel)
            if i.flag_bits & 0x1:
                raise ImportFehler(f"„{i.filename[:120]}“ ist verschlüsselt – verschlüsselte Archive werden nicht "
                                   "gelesen.")
            if i.file_size > 1024 * 1024 and i.file_size > MAX_VERHAELTNIS * max(i.compress_size, 1):
                raise ImportFehler(f"„{i.filename[:120]}“ ist ungewöhnlich stark gepackt und wird nicht gelesen.")
            summe += i.file_size
        if summe > MAX_ENTPACKT:
            raise ImportFehler(f"Das Archiv ist entpackt {summe // (1024 * 1024)} MB groß – höchstens "
                               f"{MAX_ENTPACKT // (1024 * 1024)} MB werden gelesen.")
    except BaseException:
        archiv.close()
        raise
    return archiv


def _lesen(archiv, info, grenze):
    """Den Inhalt eines Eintrags – nie mehr als grenze Bytes (zipfile hält sich an die Größe im Verzeichnis)."""
    try:
        with archiv.open(info) as fh:
            roh = fh.read(grenze + 1)
    except _LESEFEHLER:
        raise ImportFehler(f"„{info.filename[:120]}“ ist beschädigt oder lässt sich nicht lesen.")
    if len(roh) > grenze:
        raise ImportFehler(f"„{info.filename[:120]}“ ist zu groß.")
    return roh


# --- 3. und 4.: Seiten und Baum -------------------------------------------------------------------------------------

def titel_aus(md):
    """Der Seitentitel aus der ersten Zeile „# …“ ohne Auszeichnungen – dieselbe Regel wie wiki.js titelZeile."""
    m = _TITEL_RE.match((md or "").split("\n", 1)[0])
    if not m:
        return None
    roh = m.group(1).strip()
    roh = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", roh)
    roh = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", roh)
    roh = re.sub(r"`([^`]*)`", r"\1", roh)
    roh = re.sub(r"\*\*([^*]+)\*\*|__([^_]+)__", lambda x: x.group(1) or x.group(2), roh)
    roh = re.sub(r"\*([^*]+)\*|_([^_]+)_", lambda x: x.group(1) or x.group(2), roh)
    roh = re.sub(r"~~([^~]+)~~|\+\+([^+]+)\+\+|==([^=]+)==", lambda x: x.group(1) or x.group(2) or x.group(3), roh)
    return roh.strip() or None


def _natuerlich(name):
    """Sortierschlüssel „natürlich“: Zahlen als Zahlen („2 …“ vor „10 …“), sonst ohne Groß und klein."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.casefold()) for t in re.split(r"(\d+)", name) if t]


class _Knoten:
    """Eine künftige Seite: Schlüssel = Pfad ohne Endung („A/B“), aus einer .md oder einem Ordner."""

    def __init__(self, schluessel, quelle=None):
        self.schluessel = schluessel
        self.quelle = quelle            # Archivpfad der .md – None bei einem Ordner ohne eigene Datei
        self.titel = None
        self.inhalt = ""
        self.kinder = []
        self.pid = None
        self.slug = None


# --- 5. und 6.: Anhänge und Verweise --------------------------------------------------------------------------------

def _zeilen_ausserhalb_code(inhalt, f):
    """f auf jeden Textteil außerhalb von Codeblöcken und Inline-Code anwenden; der Rest bleibt, wie er ist."""
    raus, zaun = [], None
    for zeile in inhalt.split("\n"):
        m = _ZAUN_RE.match(zeile)
        if m:
            zaun = None if zaun and zeile.strip().startswith(zaun) else (zaun or m.group(1))
            raus.append(zeile)
            continue
        if zaun:
            raus.append(zeile)
            continue
        teile = _INLINE_CODE_RE.split(zeile)
        raus.append("".join(t if i % 2 else f(t) for i, t in enumerate(teile)))
    return "\n".join(raus)


def _ziel_zerlegen(ziel):
    """(Pfad, Anhang) – Anhang ist „#…“ bzw. „?…“ samt Zeichen, er bleibt beim Umschreiben erhalten."""
    m = re.match(r"^([^#?]*)(.*)$", ziel, re.DOTALL)
    return m.group(1), m.group(2)


def _archivpfad(ziel, md_pfad):
    """Der Eintrag im Archiv, auf den ein Verweis zeigt – oder None (fremde Adresse, Wiki-Link, Anker, außerhalb)."""
    if not ziel or _FREMD_RE.match(ziel):
        return None
    pfad, _ = _ziel_zerlegen(ziel)
    pfad = unquote(pfad)
    if pfad.startswith("/media/wiki/"):
        ref = pfad[len("/media/wiki/"):].strip("/")
        return "media/" + ref if ref and ".." not in ref.split("/") else None
    neu = posixpath.normpath(posixpath.join(posixpath.dirname(md_pfad), pfad))
    if neu.startswith("../") or neu in ("..", ".") or neu.startswith("/"):
        return None
    return unicodedata.normalize("NFC", neu)


class _Import:
    def __init__(self, archiv, eintraege, seiten, hinweise):
        self.archiv = archiv
        self.eintraege = eintraege      # Archivpfad (NFC) → ZipInfo, ohne Übergangenes
        self.seiten = seiten            # Archivpfad der .md → _Knoten
        self.hinweise = hinweise
        self.zaehler = {}
        self.dateien = {}               # Archivpfad → neue Adresse /media/wiki/… (oder None: nicht übernommen)
        self.abgelegt = []              # (Name, Originalname, Art) – fürs Vermerken und fürs Aufräumen
        self.benutzt = set()
        self.vorlauf = True             # erster Lauf: Dateien ablegen, Hinweise sammeln; zweiter: nur umschreiben
        self.still = False              # im zweiten Lauf: Hinweise zu Verweisen stehen schon da

    def hinweis(self, art, text):
        if self.still:
            return
        n = self.zaehler.get(art, 0) + 1
        self.zaehler[art] = n
        if n <= MAX_HINWEISE:
            self.hinweise.append(text)

    def zusammenfassen(self):
        for art, n in self.zaehler.items():
            if n > MAX_HINWEISE:
                self.hinweise.append(f"… und {n - MAX_HINWEISE} weitere Hinweise dieser Art ({art}).")

    def datei(self, pfad):
        """Die neue Adresse eines Anhangs – beim ersten Verweis abgelegt, danach dieselbe."""
        if pfad in self.dateien:
            return self.dateien[pfad]
        info = self.eintraege[pfad]
        name = pfad.rsplit("/", 1)[-1]
        ext = os.path.splitext(name)[1].lower()
        self.dateien[pfad] = None
        if ext in VIDEO_EXT:
            self.hinweis("Videos", f"Video „{pfad}“ übergangen – Videos einzeln hochladen.")
            return None
        if ext not in WIKI_EXT:
            self.hinweis("Dateityp", f"„{pfad}“ übergangen – Dateityp {ext or '(ohne Endung)'} wird in der Strömipedia nicht "
                                     "unterstützt.")
            return None
        tmp = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, dir=current_app.config["TMP_DIR"])
        try:
            try:
                with self.archiv.open(info) as quelle:
                    shutil.copyfileobj(quelle, tmp, 1024 * 1024)
            except _LESEFEHLER:
                raise ImportFehler(f"„{pfad[:120]}“ ist beschädigt oder lässt sich nicht lesen.")
            tmp.seek(0)
            try:
                neu, art = store_wiki_file(FileStorage(stream=tmp, filename=name), current_app.config["MEDIA_DIR"])
            except Exception:                    # noqa: BLE001 – Pillow und Dateisystem nennen Serverpfade
                current_app.logger.exception("Wiki-Import: %s ließ sich nicht ablegen", pfad)
                self.hinweis("Dateien", f"„{pfad}“ ließ sich nicht verarbeiten – nicht übernommen.")
                return None
        finally:
            tmp.close()
        self.abgelegt.append((neu, name, art))
        self.dateien[pfad] = f"/media/wiki/{neu}"
        return self.dateien[pfad]

    def ziel(self, ziel, md_pfad):
        """Ein Verweisziel umgeschrieben – oder unverändert."""
        pfad = _archivpfad(ziel, md_pfad)
        if pfad is None:
            return ziel
        _, anhang = _ziel_zerlegen(ziel)
        if pfad in self.seiten:
            self.benutzt.add(pfad)
            if self.vorlauf:
                return ziel
            return f"/stroemipedia/{self.seiten[pfad].slug}" + (anhang if anhang.startswith("#") else "")
        if pfad not in self.eintraege:
            self.hinweis("Verweise", f"Verweis ohne Datei in „{md_pfad}“: {ziel[:200]}")
            return ziel
        self.benutzt.add(pfad)
        neu = self.datei(pfad)
        return neu + anhang if neu else ziel

    def umschreiben(self, inhalt, md_pfad):
        def teil(text):
            def link(m):
                roh = m.group(2)
                spitz = roh.startswith("<") and roh.endswith(">")
                neu = self.ziel(roh[1:-1] if spitz else roh, md_pfad)
                return m.group(1) + (f"<{neu}>" if spitz else neu)

            text = _LINK_RE.sub(link, text)
            return _SRC_RE.sub(lambda m: m.group(1) + m.group(2) + self.ziel(m.group(3), md_pfad) + m.group(2), text)
        return _zeilen_ausserhalb_code(inhalt, teil)


# --- Ablauf ---------------------------------------------------------------------------------------------------------

def _vorbereiten(archiv, hinweise):
    """Einträge prüfen und sortieren, Seiten lesen, Baum bauen. Liefert (Wurzeln, Seiten, Einträge)."""
    eintraege, seiten_pfade = {}, []
    for info in archiv.infolist():
        teile = _pfad(info)
        if teile is None:
            continue
        pfad = unicodedata.normalize("NFC", "/".join(teile))
        eintraege[pfad] = info
        if os.path.splitext(pfad)[1].lower() in SEITEN_EXT:
            seiten_pfade.append(pfad)
    if not seiten_pfade:
        raise ImportFehler("Im Archiv steht keine Seite (Dateien *.md oder *.markdown).")
    if len(seiten_pfade) > MAX_SEITEN:
        raise ImportFehler(f"Das Archiv hat {len(seiten_pfade)} Seiten – höchstens {MAX_SEITEN} je Import.")
    grenze = current_app.config["MAX_REQUEST_LENGTH"]
    text_summe = sum(eintraege[p].file_size for p in seiten_pfade)
    if text_summe > MAX_SEITEN_TEXT:
        raise ImportFehler(f"Die Seiten im Archiv sind zusammen {text_summe // (1024 * 1024)} MB groß – höchstens "
                           f"{MAX_SEITEN_TEXT // (1024 * 1024)} MB je Import.")
    knoten, seiten = {}, {}
    for pfad in seiten_pfade:
        schluessel = os.path.splitext(pfad)[0]
        if schluessel in knoten:
            raise ImportFehler(f"„{knoten[schluessel].quelle}“ und „{pfad}“ wären dieselbe Seite – bitte eine davon "
                               "umbenennen.")
        info = eintraege[pfad]
        if info.file_size > grenze:
            raise ImportFehler(f"„{pfad[:120]}“ ist größer als {grenze // 1024} KB – so lang darf eine Seite nicht "
                               "sein.")
        roh = _lesen(archiv, info, grenze)
        try:
            text = roh.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ImportFehler(f"„{pfad[:120]}“ ist kein UTF-8-Text.")
        if "\x00" in text:
            raise ImportFehler(f"„{pfad[:120]}“ enthält Nullzeichen – das ist keine Textdatei.")
        text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\n")
        k = _Knoten(schluessel, pfad)
        k.titel = titel_aus(text)
        if not k.titel:
            k.titel = os.path.splitext(pfad.rsplit("/", 1)[-1])[0].strip() or "Seite"
            text = f"# {k.titel}\n\n{text}"
        k.inhalt = text
        knoten[schluessel] = k
        seiten[pfad] = k
    # Ordner ohne eigene Seite: eine Seite mit dem Ordnernamen (nur Titelzeile).
    for schluessel in list(knoten):
        teile = schluessel.split("/")
        for n in range(1, len(teile)):
            oben = "/".join(teile[:n])
            if oben not in knoten:
                k = _Knoten(oben)
                k.titel = teile[n - 1]
                k.inhalt = f"# {k.titel}\n"
                knoten[oben] = k
    for k in knoten.values():
        if len(k.titel) > MAX_TITEL:
            raise ImportFehler(f"„{(k.quelle or k.schluessel)[:120]}“: Der Titel ist länger als {MAX_TITEL} Zeichen.")
    wurzeln = []
    for schluessel, k in knoten.items():
        oben = schluessel.rsplit("/", 1)[0] if "/" in schluessel else None
        (knoten[oben].kinder if oben else wurzeln).append(k)
    for k in knoten.values():
        k.kinder.sort(key=lambda x: _natuerlich(x.schluessel.rsplit("/", 1)[-1]))
    wurzeln.sort(key=lambda x: _natuerlich(x.schluessel))
    return wurzeln, seiten, eintraege


def importieren(fh, parent_id, uid):
    """Ein ZIP (Datei-Objekt, durchsuchbar) unter die Seite parent_id (None: oberste Ebene) einlesen. Liefert
    {seiten: [{id, title, slug, parent_id}], dateien: n, hinweise: [...]} oder wirft ImportFehler."""
    hinweise = []
    archiv = _archiv_oeffnen(fh)
    imp = None
    try:
        wurzeln, seiten, eintraege = _vorbereiten(archiv, hinweise)
        imp = _Import(archiv, eintraege, seiten, hinweise)
        # Reihenfolge: Eltern vor Kindern (für parent_id), Geschwister wie sortiert.
        reihe = []

        def ablaufen(liste, oben):
            for k in liste:
                reihe.append((k, oben))
                ablaufen(k.kinder, k)
        ablaufen(wurzeln, None)
        try:
            # Vorlauf ohne Schreibsperre: Anhänge ablegen (Bilder neu schreiben dauert) und Hinweise sammeln. Verweise
            # auf andere importierte Seiten kommen erst im zweiten Lauf an die Reihe, wenn ihre Adressen feststehen.
            for k, _ in reihe:
                if k.quelle:
                    imp.umschreiben(k.inhalt, k.quelle)
            imp.vorlauf, imp.still = False, True
            ts = db.now()
            with db.transaction(sofort=True):
                vorhanden = {r["title"].casefold(): r["title"] for r in db.query(
                    "SELECT title FROM wiki_pages WHERE parent_id IS ? AND deleted_at IS NULL", (parent_id,))}
                start = db.query("SELECT COALESCE(MAX(position), -1) + 1 AS n FROM wiki_pages WHERE parent_id IS ? "
                                 "AND deleted_at IS NULL", (parent_id,), one=True)["n"]
                positionen = {}
                for k, oben in reihe:
                    eltern = oben.pid if oben else parent_id
                    pos = positionen.get(eltern, start if oben is None else 0)
                    positionen[eltern] = pos + 1
                    k.slug = api_wiki.unique_slug(k.titel)
                    k.pid = db.execute(
                        "INSERT INTO wiki_pages (title, slug, parent_id, content, format, position, created_by, "
                        "updated_by, created_at, updated_at) VALUES (?,?,?,'',?,?,?,?,?,?)",
                        (k.titel, k.slug, eltern, api_wiki.FORMAT, pos, uid, uid, ts, ts))
                # Erst alle Adressen, dann die Inhalte: Verweise auf eine andere importierte Seite kennen ihren slug.
                for k, _ in reihe:
                    inhalt = imp.umschreiben(k.inhalt, k.quelle) if k.quelle else k.inhalt
                    db.execute("UPDATE wiki_pages SET content = ? WHERE id = ?", (inhalt, k.pid))
                    api_wiki._revision(k.pid, k.titel, inhalt, api_wiki.FORMAT, uid, ts)
                    api_wiki.sync_page_files(k.pid, inhalt)
                    api_wiki.sync_page_links(k.pid, inhalt)
                for name, original, art in imp.abgelegt:
                    api_wiki._datei_vermerken(name, original, art)
        except BaseException:
            _aufraeumen(imp.abgelegt)
            raise
    finally:
        archiv.close()
    imp.still = False
    ziel = db.query("SELECT title FROM wiki_pages WHERE id = ?", (parent_id,), one=True) if parent_id else None
    for k in reversed(wurzeln):
        if k.titel.casefold() in vorhanden:
            wo = f"Unter „{ziel['title']}“" if ziel else "Auf der obersten Ebene"
            hinweise.insert(0, f"{wo} gibt es schon eine Seite „{vorhanden[k.titel.casefold()]}“ – die importierte "
                               f"steht daneben unter eigener Adresse (/stroemipedia/{k.slug}).")
    for pfad in imp.eintraege:
        if pfad in imp.seiten or pfad in imp.benutzt:
            continue
        ext = os.path.splitext(pfad)[1].lower()
        if ext in VIDEO_EXT:
            imp.hinweis("Videos", f"Video „{pfad}“ übergangen – Videos einzeln hochladen.")
        elif ext in WIKI_EXT:
            imp.hinweis("unbenutzt", f"„{pfad}“ – keine Seite verweist darauf, nicht übernommen.")
        else:
            imp.hinweis("Dateityp", f"„{pfad}“ übergangen – Dateityp {ext or '(ohne Endung)'} wird in der Strömipedia nicht "
                                    "unterstützt.")
    imp.zusammenfassen()
    return {"seiten": [{"id": k.pid, "title": k.titel, "slug": k.slug, "parent_id": oben.pid if oben else parent_id}
                       for k, oben in reihe],
            "dateien": len(imp.abgelegt), "hinweise": hinweise}


def _aufraeumen(abgelegt):
    """Die schon abgelegten Dateien eines gescheiterten Imports löschen – sonst lägen sie bis zum Hintergrundlauf als
    Waisen in media/wiki."""
    d = os.path.join(current_app.config["MEDIA_DIR"], "wiki")
    for name, _, _ in abgelegt:
        try:
            os.remove(os.path.join(d, name))
        except OSError:
            pass
