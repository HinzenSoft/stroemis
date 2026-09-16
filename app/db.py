"""SQLite-Anbindung (Standardbibliothek, keine ORM-Abhängigkeit)."""
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name          TEXT NOT NULL DEFAULT '',
  gliederung    TEXT NOT NULL DEFAULT '',
  phone         TEXT NOT NULL DEFAULT '',
  role          TEXT NOT NULL DEFAULT 'user',      -- 'user' | 'editor' | 'admin'
  active        INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS albums (
  id            INTEGER PRIMARY KEY,
  title         TEXT NOT NULL,
  category      TEXT NOT NULL DEFAULT 'sonstiges', -- 'seil' | 'wasser' | 'sonstiges'
  description   TEXT NOT NULL DEFAULT '',
  contact_name  TEXT NOT NULL DEFAULT '',
  contact_org   TEXT NOT NULL DEFAULT '',
  contact_phone TEXT NOT NULL DEFAULT '',
  contact_email TEXT NOT NULL DEFAULT '',
  contact_notes TEXT NOT NULL DEFAULT '',
  owner_id      INTEGER NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS photos (
  id            INTEGER PRIMARY KEY,
  album_id      INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
  owner_id      INTEGER NOT NULL REFERENCES users(id),
  file          TEXT NOT NULL,                     -- Dateiname im Media-Verzeichnis
  original_name TEXT NOT NULL DEFAULT '',
  width         INTEGER,
  height        INTEGER,
  lat           REAL,
  lon           REAL,
  altitude      REAL,                             -- Höhe ü. NN aus EXIF (m)
  geo_source    TEXT,                             -- 'exif' | 'manual' | NULL
  taken_at      TEXT,
  title         TEXT NOT NULL DEFAULT '',
  note          TEXT NOT NULL DEFAULT '',
  height_m      REAL,                             -- Objekthöhe / Absturzhöhe (m)
  details       TEXT NOT NULL DEFAULT '',         -- weitere Infos
  sort          INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_album ON photos(album_id);

CREATE TABLE IF NOT EXISTS wiki_pages (
  id            INTEGER PRIMARY KEY,
  title         TEXT NOT NULL,
  slug          TEXT UNIQUE NOT NULL,
  parent_id     INTEGER REFERENCES wiki_pages(id) ON DELETE SET NULL,
  content       TEXT NOT NULL DEFAULT '',
  position      INTEGER NOT NULL DEFAULT 0,
  created_by    INTEGER REFERENCES users(id),
  updated_by    INTEGER REFERENCES users(id),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wiki_revisions (
  id            INTEGER PRIMARY KEY,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  user_id       INTEGER REFERENCES users(id),
  created_at    TEXT NOT NULL,
  sitzung       TEXT                    -- Kennzeichen der Bearbeitung, siehe _revision
);
CREATE INDEX IF NOT EXISTS idx_wiki_rev_page ON wiki_revisions(page_id);

CREATE TABLE IF NOT EXISTS wiki_editors (
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (page_id, user_id)
);

CREATE TABLE IF NOT EXISTS wiki_comments (
  id            INTEGER PRIMARY KEY,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  parent_id     INTEGER REFERENCES wiki_comments(id) ON DELETE CASCADE,
  user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  quote         TEXT NOT NULL DEFAULT '',        -- markierte Textstelle (Anker)
  body          TEXT NOT NULL,
  resolved      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wiki_comments_page ON wiki_comments(page_id);

CREATE TABLE IF NOT EXISTS wiki_files (
  id            INTEGER PRIMARY KEY,
  file          TEXT NOT NULL,
  original_name TEXT NOT NULL DEFAULT '',
  user_id       INTEGER REFERENCES users(id),
  created_at    TEXT NOT NULL
);

-- Frühere Adressen einer Seite: nach dem Umbenennen bleiben alte Links gültig.
-- Wer ist gerade auf einer Seite, und wer schreibt daran? Kurzlebig: Jeder Browser-Reiter meldet
-- sich alle paar Sekunden; bleibt die Meldung aus, gilt er als weg. Nichts davon ist es wert,
-- aufgehoben zu werden – die Tabelle darf jederzeit leer sein.
CREATE TABLE IF NOT EXISTS wiki_praesenz (
  reiter        TEXT PRIMARY KEY,       -- Kennung des Browser-Reiters, nicht des Nutzers
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  modus         TEXT NOT NULL,          -- 'lesen' | 'schreiben'
  seit          TEXT NOT NULL,
  gesehen       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_praesenz_seite ON wiki_praesenz(page_id);

CREATE TABLE IF NOT EXISTS wiki_slugs (
  slug          TEXT PRIMARY KEY,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE
);

-- Welche Seite bindet welchen Anhang ein? Beantwortet die Frage „darf das ohne Login raus?“
-- mit einem Index statt mit einem LIKE über alle Seiteninhalte.
CREATE TABLE IF NOT EXISTS wiki_page_files (
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  file          TEXT NOT NULL,
  PRIMARY KEY (page_id, file)
);
CREATE INDEX IF NOT EXISTS idx_wiki_page_files_file ON wiki_page_files(file);

-- Merkliste je Nutzer.
CREATE TABLE IF NOT EXISTS wiki_favorites (
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  created_at    TEXT NOT NULL,
  PRIMARY KEY (user_id, page_id)
);

-- Zuletzt besuchte Seiten je Nutzer (eine Zeile je Seite, Zeitstempel wird überschrieben).
CREATE TABLE IF NOT EXISTS wiki_views (
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  seen_at       TEXT NOT NULL,
  PRIMARY KEY (user_id, page_id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_views_seen ON wiki_views(user_id, seen_at DESC);

-- Verweise von Seite zu Seite, für "Was verlinkt hierher".
CREATE TABLE IF NOT EXISTS wiki_page_links (
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  target_slug   TEXT NOT NULL,
  PRIMARY KEY (page_id, target_slug)
);
CREATE INDEX IF NOT EXISTS idx_wiki_page_links_target ON wiki_page_links(target_slug);

-- Wer möchte über Änderungen an einer Seite benachrichtigt werden?
CREATE TABLE IF NOT EXISTS wiki_watches (
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  page_id       INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
  created_at    TEXT NOT NULL,
  PRIMARY KEY (user_id, page_id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_watches_page ON wiki_watches(page_id);

-- Fehlgeschlagene Anmeldeversuche, um Passwort-Raten auszubremsen (workerübergreifend).
CREATE TABLE IF NOT EXISTS login_attempts (
  id            INTEGER PRIMARY KEY,
  scope         TEXT NOT NULL,                    -- 'ip:…' | 'mail:…' | 'forgot:…'
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(scope, created_at);
"""


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Spalten, die nach der ersten Version dazukamen (ALTER TABLE ist in SQLite nur additiv möglich)
MIGRATIONS = [
    ("users", "status", "TEXT NOT NULL DEFAULT 'active'"),                 # pending | active
    ("users", "reason", "TEXT NOT NULL DEFAULT ''"),                       # Begründung der Kontoanfrage
    ("photos", "kind", "TEXT NOT NULL DEFAULT 'image'"),                   # image | video
    ("wiki_pages", "format", "TEXT NOT NULL DEFAULT 'markdown'"),       # 'markdown' | 'html'
    ("wiki_pages", "is_public", "INTEGER NOT NULL DEFAULT 0"),           # ohne Login sichtbar
    ("wiki_pages", "public_children", "INTEGER NOT NULL DEFAULT 0"),     # Freigabe gilt für Unterseiten
    ("wiki_revisions", "format", "TEXT NOT NULL DEFAULT 'markdown'"),
    ("wiki_pages", "version", "INTEGER NOT NULL DEFAULT 0"),           # zählt jede Änderung mit
    ("wiki_pages", "icon", "TEXT NOT NULL DEFAULT ''"),                # Emoji vor dem Titel
    ("wiki_pages", "deleted_at", "TEXT"),                              # gesetzt = im Papierkorb
    ("wiki_pages", "is_template", "INTEGER NOT NULL DEFAULT 0"),       # als Vorlage anbieten
    ("wiki_files", "kind", "TEXT NOT NULL DEFAULT 'image'"),           # image | video | file
    ("wiki_files", "size", "INTEGER NOT NULL DEFAULT 0"),              # Bytes, für die Anhangsliste
    ("wiki_pages", "read_restricted", "INTEGER NOT NULL DEFAULT 0"),   # nur für Freigegebene lesbar
    ("wiki_comments", "quote_before", "TEXT NOT NULL DEFAULT ''"),     # Text vor der Fundstelle
    ("wiki_comments", "quote_after", "TEXT NOT NULL DEFAULT ''"),      # Text danach – macht den Anker eindeutig
    ("wiki_revisions", "sitzung", "TEXT"),                             # welche Bearbeitung die Fassung schrieb
    ("albums", "cover_photo_id", "INTEGER"),                           # gewähltes Deckblatt des Albums
    # Welcher Löschvorgang eine Seite in den Papierkorb gelegt hat. Beim Wiederherstellen kommt
    # genau diese Gruppe zurück – eine Unterseite, die schon vorher einzeln gelöscht wurde,
    # bleibt liegen. Der Zeitstempel taugte dafür nicht: db.now() zählt in ganzen Sekunden.
    ("wiki_pages", "deleted_batch", "TEXT"),
    # Profilbild: der Dateiname unter media/avatar. Leer heißt: es werden die Initialen gezeigt.
    ("users", "avatar", "TEXT NOT NULL DEFAULT ''"),
]


# Tabellen, deren Inhalt vollständig aus den Seiten abgeleitet ist. Ändert sich die Art, wie sie
# gefüllt werden, muss der Bestand neu aufgebaut werden: die Tabelle fällt weg, init_db meldet sie
# danach als neu, und die App trägt sie einmalig wieder ein. DERIVED_VERSION dabei hochzählen.
# 2: wiki_page_files enthielt an Umlauten abgeschnittene Dateinamen (zu enge Fundstelle im Text).
# 3: Seitenverweise (wiki_page_links) kamen dazu.
DERIVED_VERSION = 5   # 5: eingebundene Abschnitte zählen jetzt als Verweis
DERIVED_TABLES = ("wiki_page_files", "wiki_page_links")
# Tabellen und Spalten aus entfernten Funktionen – werden beim Start einmalig abgeräumt.
# pegel_stationen: Die automatische Pegelzuordnung (PegelAlarm) ist wieder ausgebaut –
# der Zugang zur Schnittstelle wurde verwehrt. Mit ihr gehen die Pegelspalten der Bilder.
OBSOLETE_TABLES = ("wiki_labels", "pegel_stationen")
OBSOLETE_COLUMNS = (("wiki_pages", "full_width"),
                    ("photos", "pegel_url"), ("photos", "pegel_station"), ("photos", "pegel_gewaesser"),
                    ("photos", "pegel_entfernung_m"), ("photos", "pegel_quelle"), ("photos", "pegel_betreiber"),
                    ("photos", "pegel_wert"), ("photos", "pegel_einheit"), ("photos", "pegel_wert_zeit"))


def init_db():
    """Legt Tabellen und neue Spalten an. Liefert die Namen der Tabellen, die es vorher noch nicht gab –
    daran erkennt die App, ob sie einmalig Bestandsdaten nachtragen muss.

    Gunicorn startet die App in jedem Arbeitsprozess getrennt, also alle gleichzeitig. Beim ersten
    Start schreiben sie damit zeitgleich am Schema. Der Wartezeitwert lässt SQLite selbst auf die
    Schreibsperre warten; die Wiederholung fängt die eine Stelle ab, an der das nicht greift –
    das Umschalten auf WAL braucht kurz die alleinige Sperre."""
    for versuch in range(20):
        try:
            return _init_db_einmal()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or versuch == 19:
                raise
            time.sleep(0.1 * (versuch + 1))


def _init_db_einmal():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA journal_mode = WAL")
    if conn.execute("PRAGMA user_version").fetchone()[0] < DERIVED_VERSION:
        for table in DERIVED_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"PRAGMA user_version = {DERIVED_VERSION}")
    for table in OBSOLETE_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    for table, column in OBSOLETE_COLUMNS:
        # DROP COLUMN kennt SQLite erst ab 3.35. Ist es älter, bleibt die Spalte stehen –
        # sie stört nicht, weil sie nirgends mehr gelesen wird.
        try:
            if column in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        except sqlite3.Error:
            pass
    before = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.executescript(SCHEMA)
    for table, column, decl in MIGRATIONS:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            except sqlite3.OperationalError as e:
                # Gunicorn startet die App in jedem Arbeitsprozess getrennt und damit gleichzeitig:
                # zwischen Abfrage und ALTER kann ein anderer Prozess die Spalte schon angelegt
                # haben. Nur genau diesen Fall abfangen, alles andere gehört gemeldet.
                if "duplicate column" not in str(e).lower():
                    raise
    conn.commit()
    after = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.close()
    return after - before


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    if not getattr(g, "tx_depth", 0):
        conn.commit()
    rid = cur.lastrowid
    cur.close()
    return rid


def execute_zeilen(sql, args=()):
    """Wie execute, liefert aber die Zahl der betroffenen Zeilen statt der neuen Kennung.
    Gebraucht für bedingte Schreibzugriffe („nur, wenn die Fassung noch stimmt“)."""
    conn = get_db()
    cur = conn.execute(sql, args)
    if not getattr(g, "tx_depth", 0):
        conn.commit()
    n = cur.rowcount
    cur.close()
    return n


@contextmanager
def transaction():
    """Mehrere Schreibzugriffe als eine Einheit – bricht einer ab, bleibt nichts halb erledigt.
    execute() innerhalb des Blocks schreibt mit, committet aber erst am Ende."""
    conn = get_db()
    g.tx_depth = getattr(g, "tx_depth", 0) + 1
    try:
        yield conn
    except BaseException:
        g.tx_depth -= 1
        if not g.tx_depth:
            conn.rollback()
        raise
    g.tx_depth -= 1
    if not g.tx_depth:
        conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
