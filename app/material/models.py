"""Schema des Moduls Material: alle Tabellen mit dem Vorsatz mat_, die Schemaversion in mat_meta und
die Migrationsschritte, die beim Start laufen (siehe db.SCHEMA_MODULE).

Alle Tabellen entstehen mit Lieferung 1 – auch die, deren Logik erst in Phase 2 kommt (Freigaben je
Ordner, Erinnerungen). Was später dazukommt, ist ein weiterer Schritt in SCHRITTE und eine höhere
SCHEMA_VERSION. Schritt 1 bleibt, wie er ausgeliefert wurde; jeder spätere Schritt baut darauf auf.

Schritt 2 (Lieferung 2) baut mat_inspection und mat_round einmal neu auf: Die Prüfart
„Eingangsprüfung“ muss in die CHECK-Regel (die ändert SQLite nur mit einer neuen Tabelle), und beide
bekommen AUTOINCREMENT – ein verworfener Entwurf oder ein gelöschter leerer Durchgang gibt seine Kennung
sonst an den nächsten weiter, und das unveränderliche Journal hinge am falschen Vorgang. Der Umbau
übernimmt jede vorhandene Zeile (bis Lieferung 1 konnte ohnehin keine entstehen) und läuft nach dem
Verfahren aus der SQLite-Dokumentation: Fremdschlüssel aus, neue Tabelle, kopieren, alte löschen,
umbenennen, Indizes neu, foreign_key_check – alles in einer Transaktion.

Feldnamen folgen dem Konzept vom 16.10.2026 (englisch, wie dort festgelegt). Abweichungen:
  - mat_checklist_item.group_name statt group – „group“ ist ein SQL-Schlüsselwort.
  - mat_round_item (Artikel eines Prüfdurchgangs samt Ausnahmegrund) statt einer JSON-Spalte
    „excluded“ an mat_round: Fortschritt und Abschlussbedingung sind damit einfache Abfragen.
  - mat_category.default_material_kind – ohne sie ließe sich „Lebensdauer nur bei textilen
    Kategorien“ nicht prüfen; mat_product.lifetime_source – „sonstiges nur mit Herstellerangabe“.
  - Namensschnappschüsse (*_name) und demo-Kennzeichen wie im übrigen Bestand.
  - mat_item.last_inspected_on (Lieferung 2): Tag der letzten abgeschlossenen Prüfung. Fehlt er, hat
    der Artikel noch keine Eingangsprüfung – sein Status ist „neu“.
  - mat_inspection.basis_inspection_id (Lieferung 2): Eine Aussonderung, die aus einer Prüfung folgt,
    verweist auf diese; die Prüfart „eingang“ (Eingangsprüfung) kam dazu.
  - mat_product_document.category_id (Schritt 3): Ein Dokument hängt an einem Produkt oder an einer
    Kategorie und gilt dann für alle Produkte darin; Art „Pflegehinweis“.
"""
import sqlite3

SCHEMA_VERSION = 3

# --- Wertelisten -------------------------------------------------------------------------------
# Was die Datenbank per CHECK erzwingt, steht hier ein zweites Mal – mit den Wörtern, die die
# Oberfläche zeigt. Die Reihenfolge ist die der Auswahllisten.
# Der Schlüssel „metall_hardware“ bleibt (Datenbank, Katalogimport); angezeigt wird kurz „Metall“.
MATERIALARTEN = {"textil": "textil", "metall_hardware": "Metall", "sonstiges": "sonstiges"}
ORDNERARTEN = {"gliederung": "Gliederung", "standort": "Standort", "fahrzeug": "Fahrzeug", "set": "Set",
               "persoenlich": "persönlich", "sonstiges": "sonstiges"}
SYSTEMORDNER = {"gesperrt": "Gesperrt", "ausgesondert": "Ausgesondert"}
DOKUMENTARTEN = {"produktbild": "Produktbild", "konformitaetserklaerung": "Konformitätserklärung",
                 "gebrauchsanleitung": "Gebrauchsanleitung", "pruefanweisung": "Prüfanweisung",
                 "pflegehinweis": "Pflegehinweis", "datenblatt": "Datenblatt", "sonstiges": "Sonstiges"}
# Die Dokumentarten, mit denen Schritt 1 die Tabelle angelegt hat (Schritt 3 nahm „Pflegehinweis“ dazu).
DOKUMENTARTEN_1 = ("produktbild", "konformitaetserklaerung", "gebrauchsanleitung", "pruefanweisung", "datenblatt",
                   "sonstiges")
EDITOREN = {"yesno": "Ja/Nein", "text": "Text", "date": "Datum", "number": "Zahl", "photo": "Foto",
            "signature": "Unterschrift"}
SPERRZUSTAENDE = ("frei", "gesperrt", "ausgesondert", "verloren")
PRUEFARTEN = {"eingang": "Eingangsprüfung", "periodisch": "periodisch", "ausserplanmaessig": "außerplanmäßig",
              "reparatur": "Reparatur", "aussonderung": "Aussonderung"}
# Die Prüfarten, mit denen Schritt 1 die Tabelle angelegt hat – Schritt 1 bleibt, wie er ausgeliefert wurde.
PRUEFARTEN_1 = ("periodisch", "ausserplanmaessig", "reparatur", "aussonderung")
# Sperre ohne Prüfung (nur Prüfer) und Aussonderung durch den Materialwart: die Gründe zur Auswahl.
SPERRGRUENDE = {"sturz": "Sturzbelastung", "beschaedigung": "Beschädigung", "verlust": "Verlust"}
AUSSONDERUNGSGRUENDE = {"lebensdauer": "Lebensdauer erreicht", "verlust": "Verlust", "irreparabel": "irreparabel"}
ERGEBNISSE = {"einsatzbereit": "einsatzbereit", "instandsetzen": "instandsetzen", "aussondern": "aussondern"}
BEFUNDE = ("ok", "mangel", "nicht_zutreffend")
ANHANGARTEN = {"externes_pruefformular": "externes Prüfformular", "pruefbericht": "Prüfbericht", "foto": "Foto",
               "sonstiges": "Sonstiges"}
FREIGABEN = ("lesen", "pruefen", "verwalten")
ERINNERUNGEN = ("30_tage", "7_tage", "faellig", "lebensdauer")


def _in(werte):
    return "(" + ", ".join(f"'{w}'" for w in werte) + ")"


# --- Schritt 1: alle Tabellen ---------------------------------------------------------------------
SCHRITT_1 = [
    """CREATE TABLE IF NOT EXISTS mat_category (
      id                      INTEGER PRIMARY KEY,
      parent_id               INTEGER REFERENCES mat_category(id),
      name                    TEXT NOT NULL,
      norm                    TEXT NOT NULL DEFAULT '',
      default_material_kind   TEXT CHECK (default_material_kind IN """ + _in(MATERIALARTEN) + """),
      default_interval_months INTEGER CHECK (default_interval_months BETWEEN 1 AND 120),
      default_lifetime_years  INTEGER CHECK (default_lifetime_years BETWEEN 1 AND 50),
      position                INTEGER NOT NULL DEFAULT 0,
      demo                    INTEGER NOT NULL DEFAULT 0,
      created_at              TEXT NOT NULL,
      updated_at              TEXT NOT NULL,
      -- Eine Lebensdauer gibt es nur bei textilem Material.
      CHECK (default_lifetime_years IS NULL OR default_material_kind = 'textil')
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_category_name ON mat_category(COALESCE(parent_id, 0), name COLLATE NOCASE)",

    """CREATE TABLE IF NOT EXISTS mat_product (
      id               INTEGER PRIMARY KEY,
      category_id      INTEGER NOT NULL REFERENCES mat_category(id),
      manufacturer     TEXT NOT NULL,
      model            TEXT NOT NULL,
      article_no       TEXT NOT NULL DEFAULT '',
      -- Hersteller + Modell + Artikelnummer, vereinheitlicht (nur Buchstaben und Ziffern, ohne Groß/klein;
      -- „-“ als Artikelnummer zählt als leer): Dubletten wie „Gurt X / 123-45“ und „gurt-x / 12345“
      -- fängt der eindeutige Index.
      dedupe_key       TEXT NOT NULL UNIQUE,
      norm             TEXT NOT NULL DEFAULT '',
      material_kind    TEXT NOT NULL CHECK (material_kind IN """ + _in(MATERIALARTEN) + """),
      interval_months  INTEGER CHECK (interval_months BETWEEN 1 AND 120),
      lifetime_years   INTEGER CHECK (lifetime_years BETWEEN 1 AND 50),
      lifetime_source  TEXT NOT NULL DEFAULT '',    -- Fundstelle der Herstellerangabe zur Lebensdauer
      description      TEXT NOT NULL DEFAULT '',
      image            TEXT NOT NULL DEFAULT '',    -- Datei unter media/material/{orig,web,thumb}
      wiki_page_id     INTEGER REFERENCES wiki_pages(id) ON DELETE SET NULL,   -- ab Phase 2
      demo             INTEGER NOT NULL DEFAULT 0,
      created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_at       TEXT NOT NULL,
      updated_at       TEXT NOT NULL,
      CHECK (material_kind <> 'textil' OR lifetime_years IS NOT NULL),
      CHECK (material_kind <> 'metall_hardware' OR lifetime_years IS NULL),
      CHECK (material_kind <> 'sonstiges' OR lifetime_years IS NULL OR lifetime_source <> '')
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_product_category ON mat_product(category_id)",

    """CREATE TABLE IF NOT EXISTS mat_product_document (
      id               INTEGER PRIMARY KEY,
      product_id       INTEGER NOT NULL REFERENCES mat_product(id) ON DELETE CASCADE,
      kind             TEXT NOT NULL CHECK (kind IN """ + _in(DOKUMENTARTEN_1) + """),
      title            TEXT NOT NULL,
      file_path        TEXT,                        -- Datei unter media/material/dok
      url              TEXT,
      mime             TEXT NOT NULL DEFAULT '',
      size             INTEGER NOT NULL DEFAULT 0,
      sha256           TEXT NOT NULL DEFAULT '',
      version          TEXT NOT NULL DEFAULT '',
      valid_from       TEXT NOT NULL,               -- 'YYYY-MM-DD'
      replaces_id      INTEGER REFERENCES mat_product_document(id),   -- Vorgängerversion
      withdrawn_on     TEXT,                        -- zurückgezogen ab diesem Tag
      uploaded_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      uploaded_by_name TEXT NOT NULL DEFAULT '',
      uploaded_at      TEXT NOT NULL,
      CHECK ((file_path IS NULL) <> (url IS NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_document_product ON mat_product_document(product_id)",
    # Jede Version hat höchstens einen Nachfolger – auch wenn zwei gleichzeitig „Neue Version“ drücken.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_document_nachfolger ON mat_product_document(replaces_id) "
    "WHERE replaces_id IS NOT NULL",

    """CREATE TABLE IF NOT EXISTS mat_form (
      id          INTEGER PRIMARY KEY,
      category_id INTEGER REFERENCES mat_category(id),     -- generisch je Kategorie …
      product_id  INTEGER REFERENCES mat_product(id),      -- … oder spezifisch je Produkt
      version     INTEGER NOT NULL,
      title       TEXT NOT NULL DEFAULT '',
      valid_from  TEXT,                                    -- gesetzt beim ersten Aktivieren
      active      INTEGER NOT NULL DEFAULT 0,
      demo        INTEGER NOT NULL DEFAULT 0,
      created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_at  TEXT NOT NULL,
      updated_at  TEXT NOT NULL,
      CHECK ((category_id IS NULL) <> (product_id IS NULL))
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_form_cat_version ON mat_form(category_id, version) WHERE category_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_form_prod_version ON mat_form(product_id, version) WHERE product_id IS NOT NULL",
    # Höchstens ein aktives Formular je Kategorie und je Produkt – die Datenbank sorgt dafür.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_form_cat_aktiv ON mat_form(category_id) WHERE category_id IS NOT NULL AND active = 1",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_form_prod_aktiv ON mat_form(product_id) WHERE product_id IS NOT NULL AND active = 1",

    """CREATE TABLE IF NOT EXISTS mat_checklist_item (
      id             INTEGER PRIMARY KEY,
      form_id        INTEGER NOT NULL REFERENCES mat_form(id) ON DELETE CASCADE,
      group_name     TEXT NOT NULL DEFAULT '',
      position       INTEGER NOT NULL DEFAULT 0,
      label          TEXT NOT NULL,
      editor         TEXT NOT NULL CHECK (editor IN """ + _in(EDITOREN) + """),
      mandatory      INTEGER NOT NULL DEFAULT 1,
      expected_value TEXT NOT NULL DEFAULT '',
      is_critical    INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_checklist_form ON mat_checklist_item(form_id, position)",

    """CREATE TABLE IF NOT EXISTS mat_folder (
      id              INTEGER PRIMARY KEY,
      parent_id       INTEGER REFERENCES mat_folder(id),
      name            TEXT NOT NULL,
      description     TEXT NOT NULL DEFAULT '',
      photo           TEXT NOT NULL DEFAULT '',      -- Datei unter media/material/{orig,web,thumb}
      kind            TEXT NOT NULL DEFAULT 'sonstiges' CHECK (kind IN """ + _in(ORDNERARTEN) + """),
      system_kind     TEXT CHECK (system_kind IN """ + _in(SYSTEMORDNER) + """),
      interval_months INTEGER CHECK (interval_months BETWEEN 1 AND 120),
      owner_user_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
      position        INTEGER NOT NULL DEFAULT 0,
      demo            INTEGER NOT NULL DEFAULT 0,
      created_at      TEXT NOT NULL,
      updated_at      TEXT NOT NULL,
      -- Systemordner hängen immer unter ihrer Gliederung.
      CHECK (system_kind IS NULL OR parent_id IS NOT NULL)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_folder_parent ON mat_folder(parent_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_folder_system ON mat_folder(parent_id, system_kind) WHERE system_kind IS NOT NULL",

    """CREATE TABLE IF NOT EXISTS mat_item (
      id               INTEGER PRIMARY KEY,
      product_id       INTEGER NOT NULL REFERENCES mat_product(id),
      folder_id        INTEGER NOT NULL REFERENCES mat_folder(id),
      origin_folder_id INTEGER REFERENCES mat_folder(id) ON DELETE SET NULL,   -- Herkunft beim Sperren
      serial_no        TEXT NOT NULL,
      serial_generated INTEGER NOT NULL DEFAULT 0,  -- 1 = vom System vergeben (Hersteller hat keine)
      inventory_no     TEXT NOT NULL UNIQUE,        -- plattformweit eineindeutig, vom System vergeben
      manufactured_on  TEXT,                        -- 'YYYY-MM' oder 'YYYY-MM-DD'
      purchased_on     TEXT,
      first_use_on     TEXT,
      retire_by        TEXT,                        -- nur bei textilem Material: wirksames Lebensende
      retire_by_manual TEXT,                        -- vom Materialwart vorgezogen; retire_by = min(Rechnung, dieses)
      lock_state       TEXT NOT NULL DEFAULT 'frei' CHECK (lock_state IN """ + _in(SPERRZUSTAENDE) + """),
      lock_reason      TEXT NOT NULL DEFAULT '',
      next_due_on      TEXT,
      interval_months  INTEGER CHECK (interval_months BETWEEN 1 AND 120),
      assigned_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,      -- Oberfläche ab Phase 2
      qr_token         TEXT NOT NULL UNIQUE,
      notes            TEXT NOT NULL DEFAULT '',
      created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_at       TEXT NOT NULL,
      updated_at       TEXT NOT NULL
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_item_serial ON mat_item(product_id, serial_no COLLATE NOCASE)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_folder ON mat_item(folder_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_product ON mat_item(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_due ON mat_item(next_due_on)",

    """CREATE TABLE IF NOT EXISTS mat_round (
      id               INTEGER PRIMARY KEY,
      folder_id        INTEGER NOT NULL REFERENCES mat_folder(id),
      title            TEXT NOT NULL,
      opened_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
      opened_by_name   TEXT NOT NULL DEFAULT '',
      opened_on        TEXT NOT NULL,
      closed_on        TEXT,
      closed_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
      closed_by_name   TEXT NOT NULL DEFAULT '',
      protocol_id      TEXT UNIQUE,
      pdf_path         TEXT,
      pdf_sha256       TEXT,
      pdf_hashed_bytes INTEGER,
      file_sha256      TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_round_folder ON mat_round(folder_id)",

    """CREATE TABLE IF NOT EXISTS mat_round_item (
      round_id         INTEGER NOT NULL REFERENCES mat_round(id) ON DELETE CASCADE,
      item_id          INTEGER NOT NULL REFERENCES mat_item(id),
      excluded_reason  TEXT,                        -- gesetzt = mit Grund ausgenommen
      excluded_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      excluded_by_name TEXT NOT NULL DEFAULT '',
      excluded_at      TEXT,
      PRIMARY KEY (round_id, item_id)
    )""",

    """CREATE TABLE IF NOT EXISTS mat_inspection (
      id                     INTEGER PRIMARY KEY,
      item_id                INTEGER NOT NULL REFERENCES mat_item(id),
      round_id               INTEGER REFERENCES mat_round(id),
      protocol_id            TEXT UNIQUE,
      inspector_user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      inspector_name         TEXT NOT NULL DEFAULT '',
      inspector_certificate  TEXT NOT NULL DEFAULT '',   -- Urkundennummer zum Prüfzeitpunkt
      form_id                INTEGER REFERENCES mat_form(id),
      form_version           INTEGER,
      inspected_on           TEXT NOT NULL,
      kind                   TEXT NOT NULL CHECK (kind IN """ + _in(PRUEFARTEN_1) + """),
      result                 TEXT CHECK (result IN """ + _in(ERGEBNISSE) + """),
      reason                 TEXT NOT NULL DEFAULT '',   -- Grund einer Sperre oder Aussonderung
      remarks                TEXT NOT NULL DEFAULT '',
      next_due_on            TEXT,
      signature_png          BLOB,                       -- Kopie der Profil-Unterschrift
      corrects_inspection_id INTEGER REFERENCES mat_inspection(id),
      documents_json         TEXT NOT NULL DEFAULT '[]', -- zum Prüfzeitpunkt gültige Produktdokumente
      completed_at           TEXT,                       -- abgeschlossen (Ergebnis wirkt)
      locked_at              TEXT,                       -- festgeschrieben (unveränderlich)
      pdf_path               TEXT,
      pdf_sha256             TEXT,                       -- aufgedruckter Wert
      pdf_hashed_bytes       INTEGER,                    -- N: so viele Bytes deckt der Wert ab
      file_sha256            TEXT,                       -- ganze Datei mit Stempel
      created_at             TEXT NOT NULL,
      updated_at             TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_item ON mat_inspection(item_id, inspected_on)",
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_round ON mat_inspection(round_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_form ON mat_inspection(form_id)",
    # Eine Reservierung ist der offene Entwurf eines Prüfers – höchstens einer je Artikel.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_inspection_offen ON mat_inspection(item_id) WHERE completed_at IS NULL",

    """CREATE TABLE IF NOT EXISTS mat_inspection_result (
      id                INTEGER PRIMARY KEY,
      inspection_id     INTEGER NOT NULL REFERENCES mat_inspection(id) ON DELETE CASCADE,
      checklist_item_id INTEGER REFERENCES mat_checklist_item(id) ON DELETE SET NULL,
      position          INTEGER NOT NULL DEFAULT 0,
      group_name        TEXT NOT NULL DEFAULT '',
      checklist_text    TEXT NOT NULL,             -- Kopie: spätere Formularänderungen verfälschen nichts
      editor            TEXT NOT NULL,
      mandatory         INTEGER NOT NULL DEFAULT 0,
      expected_value    TEXT NOT NULL DEFAULT '',
      is_critical       INTEGER NOT NULL DEFAULT 0,
      finding           TEXT CHECK (finding IN """ + _in(BEFUNDE) + """),
      value             TEXT NOT NULL DEFAULT '',
      note              TEXT NOT NULL DEFAULT '',
      photo             TEXT NOT NULL DEFAULT ''   -- Pflicht bei Mangel
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_result_inspection ON mat_inspection_result(inspection_id, position)",

    """CREATE TABLE IF NOT EXISTS mat_inspection_attachment (
      id               INTEGER PRIMARY KEY,
      inspection_id    INTEGER NOT NULL REFERENCES mat_inspection(id) ON DELETE CASCADE,
      kind             TEXT NOT NULL CHECK (kind IN """ + _in(ANHANGARTEN) + """),
      title            TEXT NOT NULL DEFAULT '',
      file_path        TEXT NOT NULL,
      mime             TEXT NOT NULL DEFAULT '',
      pages            INTEGER,
      sha256           TEXT NOT NULL,
      uploaded_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      uploaded_by_name TEXT NOT NULL DEFAULT '',
      uploaded_at      TEXT NOT NULL,
      in_pdf           INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_attachment_inspection ON mat_inspection_attachment(inspection_id)",

    """CREATE TABLE IF NOT EXISTS mat_folder_grant (
      id          INTEGER PRIMARY KEY,
      folder_id   INTEGER NOT NULL REFERENCES mat_folder(id) ON DELETE CASCADE,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      permission  TEXT NOT NULL CHECK (permission IN """ + _in(FREIGABEN) + """),
      valid_until TEXT,
      granted_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_at  TEXT NOT NULL,
      -- Prüfrechte gibt es nur befristet.
      CHECK (permission <> 'pruefen' OR valid_until IS NOT NULL),
      UNIQUE (folder_id, user_id, permission)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_grant_user ON mat_folder_grant(user_id)",

    """CREATE TABLE IF NOT EXISTS mat_reminder_log (
      id      INTEGER PRIMARY KEY,
      item_id INTEGER NOT NULL REFERENCES mat_item(id) ON DELETE CASCADE,
      kind    TEXT NOT NULL CHECK (kind IN """ + _in(ERINNERUNGEN) + """),
      due_on  TEXT,                                -- Fälligkeit, auf die sich die Erinnerung bezieht
      sent_to TEXT NOT NULL DEFAULT '',
      sent_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_reminder_item ON mat_reminder_log(item_id, kind, due_on)",

    """CREATE TABLE IF NOT EXISTS mat_audit (
      id          INTEGER PRIMARY KEY,
      entity      TEXT NOT NULL,                   -- product, item, folder, inspection, document,
                                                   -- category, form, round, user
      entity_id   INTEGER NOT NULL,
      user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
      user_name   TEXT NOT NULL DEFAULT '',
      action      TEXT NOT NULL,
      before_json TEXT,
      after_json  TEXT,
      created_at  TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_audit_entity ON mat_audit(entity, entity_id, id)",
    # Das Journal ist nur fortschreibbar. Gelöscht wird nichts, geändert wird nur die Nutzerkennung –
    # die setzt die Datenbank selbst auf NULL, wenn ein Konto gelöscht wird (der Name bleibt stehen).
    """CREATE TRIGGER IF NOT EXISTS mat_audit_unveraenderlich
       BEFORE UPDATE OF entity, entity_id, user_name, action, before_json, after_json, created_at ON mat_audit
       BEGIN SELECT RAISE(ABORT, 'Das Journal des Moduls Material ist unveränderlich.'); END""",
    """CREATE TRIGGER IF NOT EXISTS mat_audit_unloeschbar
       BEFORE DELETE ON mat_audit
       BEGIN SELECT RAISE(ABORT, 'Das Journal des Moduls Material ist unveränderlich.'); END""",
]

# Volltextindex für die Suche nach Teilnummern (Trigramme: findet auch „234“ in „M-001234“). Er ist
# eine Beschleunigung, keine Voraussetzung: Fehlt FTS5 oder der Trigramm-Zerleger (SQLite < 3.34),
# bleibt mat_meta.volltext auf 0 und die Suche fällt auf LIKE zurück (services/search.py).
VOLLTEXT = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS mat_product_fts USING fts5(
         manufacturer, model, article_no, norm, content='mat_product', content_rowid='id', tokenize='trigram')""",
    """CREATE TRIGGER IF NOT EXISTS mat_product_fts_ai AFTER INSERT ON mat_product BEGIN
         INSERT INTO mat_product_fts(rowid, manufacturer, model, article_no, norm)
         VALUES (new.id, new.manufacturer, new.model, new.article_no, new.norm); END""",
    """CREATE TRIGGER IF NOT EXISTS mat_product_fts_ad AFTER DELETE ON mat_product BEGIN
         INSERT INTO mat_product_fts(mat_product_fts, rowid, manufacturer, model, article_no, norm)
         VALUES ('delete', old.id, old.manufacturer, old.model, old.article_no, old.norm); END""",
    """CREATE TRIGGER IF NOT EXISTS mat_product_fts_au AFTER UPDATE OF manufacturer, model, article_no, norm ON mat_product BEGIN
         INSERT INTO mat_product_fts(mat_product_fts, rowid, manufacturer, model, article_no, norm)
         VALUES ('delete', old.id, old.manufacturer, old.model, old.article_no, old.norm);
         INSERT INTO mat_product_fts(rowid, manufacturer, model, article_no, norm)
         VALUES (new.id, new.manufacturer, new.model, new.article_no, new.norm); END""",
    """CREATE VIRTUAL TABLE IF NOT EXISTS mat_item_fts USING fts5(
         serial_no, inventory_no, content='mat_item', content_rowid='id', tokenize='trigram')""",
    """CREATE TRIGGER IF NOT EXISTS mat_item_fts_ai AFTER INSERT ON mat_item BEGIN
         INSERT INTO mat_item_fts(rowid, serial_no, inventory_no) VALUES (new.id, new.serial_no, new.inventory_no); END""",
    """CREATE TRIGGER IF NOT EXISTS mat_item_fts_ad AFTER DELETE ON mat_item BEGIN
         INSERT INTO mat_item_fts(mat_item_fts, rowid, serial_no, inventory_no)
         VALUES ('delete', old.id, old.serial_no, old.inventory_no); END""",
    """CREATE TRIGGER IF NOT EXISTS mat_item_fts_au AFTER UPDATE OF serial_no, inventory_no ON mat_item BEGIN
         INSERT INTO mat_item_fts(mat_item_fts, rowid, serial_no, inventory_no)
         VALUES ('delete', old.id, old.serial_no, old.inventory_no);
         INSERT INTO mat_item_fts(rowid, serial_no, inventory_no) VALUES (new.id, new.serial_no, new.inventory_no); END""",
    "INSERT INTO mat_product_fts(mat_product_fts) VALUES ('rebuild')",
    "INSERT INTO mat_item_fts(mat_item_fts) VALUES ('rebuild')",
]

# --- Schritt 2: Prüfungen (Lieferung 2) ----------------------------------------------------------------
# mat_inspection in ihrer neuen Form: Prüfart „eingang“ und basis_inspection_id – eine Aussonderung, die
# aus einer Prüfung folgt, verweist auf diese. {name} ist beim Umbau zuerst mat_inspection_neu.
INSPECTION_2 = """CREATE TABLE {name} (
      id                     INTEGER PRIMARY KEY AUTOINCREMENT,
      item_id                INTEGER NOT NULL REFERENCES mat_item(id),
      round_id               INTEGER REFERENCES mat_round(id),
      protocol_id            TEXT UNIQUE,
      inspector_user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      inspector_name         TEXT NOT NULL DEFAULT '',
      inspector_certificate  TEXT NOT NULL DEFAULT '',   -- Urkundennummer zum Prüfzeitpunkt
      form_id                INTEGER REFERENCES mat_form(id),
      form_version           INTEGER,
      inspected_on           TEXT NOT NULL,
      kind                   TEXT NOT NULL CHECK (kind IN """ + _in(PRUEFARTEN) + """),
      result                 TEXT CHECK (result IN """ + _in(ERGEBNISSE) + """),
      reason                 TEXT NOT NULL DEFAULT '',   -- Grund einer Sperre oder Aussonderung
      remarks                TEXT NOT NULL DEFAULT '',
      next_due_on            TEXT,
      signature_png          BLOB,                       -- Kopie der Profil-Unterschrift
      corrects_inspection_id INTEGER REFERENCES mat_inspection(id),
      basis_inspection_id    INTEGER REFERENCES mat_inspection(id),   -- Aussonderung: aus dieser Prüfung
      documents_json         TEXT NOT NULL DEFAULT '[]', -- zum Prüfzeitpunkt gültige Produktdokumente
      completed_at           TEXT,                       -- abgeschlossen (Ergebnis wirkt)
      locked_at              TEXT,                       -- festgeschrieben (unveränderlich)
      pdf_path               TEXT,
      pdf_sha256             TEXT,                       -- aufgedruckter Wert
      pdf_hashed_bytes       INTEGER,                    -- N: so viele Bytes deckt der Wert ab
      file_sha256            TEXT,                       -- ganze Datei mit Stempel
      created_at             TEXT NOT NULL,
      updated_at             TEXT NOT NULL
    )"""
ROUND_2 = """CREATE TABLE {name} (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      folder_id        INTEGER NOT NULL REFERENCES mat_folder(id),
      title            TEXT NOT NULL,
      opened_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
      opened_by_name   TEXT NOT NULL DEFAULT '',
      opened_on        TEXT NOT NULL,
      closed_on        TEXT,
      closed_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
      closed_by_name   TEXT NOT NULL DEFAULT '',
      protocol_id      TEXT UNIQUE,
      pdf_path         TEXT,
      pdf_sha256       TEXT,
      pdf_hashed_bytes INTEGER,
      file_sha256      TEXT
    )"""
ROUND_INDIZES = ["CREATE INDEX IF NOT EXISTS idx_mat_round_folder ON mat_round(folder_id)"]
INSPECTION_INDIZES = [
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_item ON mat_inspection(item_id, inspected_on)",
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_round ON mat_inspection(round_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_form ON mat_inspection(form_id)",
    # Eine Reservierung ist der offene Entwurf eines Prüfers – höchstens einer je Artikel.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_inspection_offen ON mat_inspection(item_id) WHERE completed_at IS NULL",
]


def _spalten(conn, tabelle):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]


def _umbauen(conn, tabelle, sql, indizes, entitaet):
    """Eine Tabelle in neuer Form aufbauen, alle Zeilen behalten (Fremdschlüssel sind aus, siehe
    migrieren). Mit AUTOINCREMENT: Die nächste Kennung liegt über jeder je vergebenen – auch über
    gelöschten, die das Journal unter entitaet noch kennt."""
    alt = _spalten(conn, tabelle)
    conn.execute(f"DROP TABLE IF EXISTS {tabelle}_neu")
    conn.execute(sql.format(name=f"{tabelle}_neu"))
    neu = _spalten(conn, f"{tabelle}_neu")
    gemeinsam = ", ".join(s for s in alt if s in neu)
    conn.execute(f"INSERT INTO {tabelle}_neu ({gemeinsam}) SELECT {gemeinsam} FROM {tabelle}")
    conn.execute(f"DROP TABLE {tabelle}")
    conn.execute(f"ALTER TABLE {tabelle}_neu RENAME TO {tabelle}")
    for befehl in indizes:
        conn.execute(befehl)
    hoechste = max(conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {tabelle}").fetchone()[0],
                   conn.execute("SELECT COALESCE(MAX(entity_id), 0) FROM mat_audit WHERE entity = ?",
                                (entitaet,)).fetchone()[0])
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN (?, ?)", (tabelle, f"{tabelle}_neu"))
    conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (tabelle, hoechste))


def _schritt_2(conn):
    """Prüfart „Eingangsprüfung“, Verweis auf die Prüfung hinter einer Aussonderung und Kennungen, die nie
    wiederkommen (Umbau von mat_inspection und mat_round, alle Zeilen bleiben), sowie
    mat_item.last_inspected_on: der Tag der letzten abgeschlossenen Prüfung. Fehlt er, hat der Artikel
    noch keine – sein Status ist „neu“."""
    vorher = _fk_verletzungen(conn)
    _umbauen(conn, "mat_round", ROUND_2, ROUND_INDIZES, "round")
    _umbauen(conn, "mat_inspection", INSPECTION_2, INSPECTION_INDIZES, "inspection")
    if "last_inspected_on" not in _spalten(conn, "mat_item"):
        conn.execute("ALTER TABLE mat_item ADD COLUMN last_inspected_on TEXT")
    # Was schon abgeschlossen ist, zählt (bis Lieferung 1 gab es nichts – die Zeile schadet nicht).
    conn.execute("UPDATE mat_item SET last_inspected_on = (SELECT MAX(x.inspected_on) FROM mat_inspection x "
                 "WHERE x.item_id = mat_item.id AND x.completed_at IS NOT NULL AND x.kind <> 'aussonderung') "
                 "WHERE last_inspected_on IS NULL")
    # Der Umbau darf keinen Verweis brechen. Was schon vorher verletzt war, ist nicht seine Sache und soll
    # den Start nicht für immer blockieren – gezählt wird nur, was neu dazukommt.
    neu_verletzt = _fk_verletzungen(conn) - vorher
    if neu_verletzt:
        raise sqlite3.IntegrityError(f"Fremdschlüssel nach dem Umbau verletzt: {sorted(neu_verletzt)[:5]}")


def _fk_verletzungen(conn, tabellen=("mat_round", "mat_round_item", "mat_inspection", "mat_inspection_result",
                                     "mat_inspection_attachment")):
    """Verletzte Fremdschlüssel in den Tabellen, die ein Umbau berührt: (Tabelle, Zeile, Ziel)."""
    out = set()
    for tabelle in tabellen:
        for r in conn.execute(f"PRAGMA foreign_key_check({tabelle})"):
            out.add((r[0], r[1], r[2]))
    return out


# --- Schritt 3: Dokumente an Kategorien ----------------------------------------------------------------
# Ein Dokument hängt an einem Produkt ODER an einer Kategorie; dann gilt es für alle Produkte darin und in
# ihren Unterkategorien (Pflegehinweise, allgemeine Anleitungen). product_id wird dafür nullbar – auch das
# geht in SQLite nur mit einer neuen Tabelle. Kennungen kommen wie bei Prüfungen nie wieder.
DOCUMENT_3 = """CREATE TABLE {name} (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id       INTEGER REFERENCES mat_product(id) ON DELETE CASCADE,
      category_id      INTEGER REFERENCES mat_category(id) ON DELETE CASCADE,
      kind             TEXT NOT NULL CHECK (kind IN """ + _in(DOKUMENTARTEN) + """),
      title            TEXT NOT NULL,
      file_path        TEXT,                        -- Datei unter media/material/dok
      url              TEXT,
      mime             TEXT NOT NULL DEFAULT '',
      size             INTEGER NOT NULL DEFAULT 0,
      sha256           TEXT NOT NULL DEFAULT '',
      version          TEXT NOT NULL DEFAULT '',
      valid_from       TEXT NOT NULL,               -- 'YYYY-MM-DD'
      replaces_id      INTEGER REFERENCES mat_product_document(id),   -- Vorgängerversion
      withdrawn_on     TEXT,                        -- zurückgezogen ab diesem Tag
      uploaded_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      uploaded_by_name TEXT NOT NULL DEFAULT '',
      uploaded_at      TEXT NOT NULL,
      CHECK ((file_path IS NULL) <> (url IS NULL)),
      CHECK ((product_id IS NULL) <> (category_id IS NULL))
    )"""
DOCUMENT_INDIZES = [
    "CREATE INDEX IF NOT EXISTS idx_mat_document_product ON mat_product_document(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_document_category ON mat_product_document(category_id)",
    # Jede Version hat höchstens einen Nachfolger – auch wenn zwei gleichzeitig „Neue Version“ drücken.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_document_nachfolger ON mat_product_document(replaces_id) "
    "WHERE replaces_id IS NOT NULL",
]


def _schritt_3(conn):
    """Dokumente auch an Kategorien (Umbau von mat_product_document, alle Zeilen bleiben) und die Art
    „Pflegehinweis“."""
    tabellen = ("mat_product_document",)
    vorher = _fk_verletzungen(conn, tabellen)
    _umbauen(conn, "mat_product_document", DOCUMENT_3, DOCUMENT_INDIZES, "document")
    neu_verletzt = _fk_verletzungen(conn, tabellen) - vorher
    if neu_verletzt:
        raise sqlite3.IntegrityError(f"Fremdschlüssel nach dem Umbau verletzt: {sorted(neu_verletzt)[:5]}")


# Je Version die Schritte, die von der Vorversion dorthin führen: eine Liste von SQL-Befehlen (für sich
# wiederholbar, IF NOT EXISTS) oder eine Funktion. Alle Schritte eines Starts laufen in EINER
# Transaktion – bricht einer ab, bleibt die Datenbank, wie sie war, und der nächste Start versucht es neu.
SCHRITTE = {1: SCHRITT_1, 2: _schritt_2, 3: _schritt_3}


def _meta(conn, schluessel, vorgabe=None):
    row = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = ?", (schluessel,)).fetchone()
    return row[0] if row else vorgabe


def _meta_setzen(conn, schluessel, wert):
    conn.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
                 "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, str(wert)))


def _volltext_anlegen(conn):
    """Volltextindex samt Triggern – in einem Sicherungspunkt, damit ein SQLite ohne FTS5 oder ohne
    Trigramme nur den Index verliert, nicht die ganze Migration."""
    conn.execute("SAVEPOINT mat_volltext")
    try:
        for sql in VOLLTEXT:
            conn.execute(sql)
    except sqlite3.OperationalError:
        conn.execute("ROLLBACK TO mat_volltext")
        conn.execute("RELEASE mat_volltext")
        return False
    conn.execute("RELEASE mat_volltext")
    return True


def migrieren(conn):
    """Bringt das Schema auf SCHEMA_VERSION. Läuft bei jedem Start in jedem Arbeitsprozess; die
    Arbeit macht nur, wer die Schreibsperre zuerst bekommt – die anderen finden danach die neue
    Version vor und tun nichts. Liefert die Version nach dem Lauf."""
    conn.execute("CREATE TABLE IF NOT EXISTS mat_meta (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)")
    conn.commit()
    if int(_meta(conn, "schema_version", 0)) >= SCHEMA_VERSION:
        return int(_meta(conn, "schema_version"))
    # Ein Umbau löscht eine Tabelle, auf die andere verweisen. Mit eingeschalteten Fremdschlüsseln
    # löschte DROP TABLE vorher jede abhängige Zeile (ON DELETE CASCADE) – deshalb aus, und zwar vor
    # BEGIN: Innerhalb einer Transaktion wirkt das Pragma nicht.
    fremdschluessel = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        stand = int(_meta(conn, "schema_version", 0))      # unter der Sperre noch einmal lesen
        for version in range(stand + 1, SCHEMA_VERSION + 1):
            schritt = SCHRITTE[version]
            if callable(schritt):
                schritt(conn)
            else:
                for sql in schritt:
                    conn.execute(sql)
            if version == 1:
                _meta_setzen(conn, "volltext", 1 if _volltext_anlegen(conn) else 0)
                if _meta(conn, "inventar_zaehler") is None:
                    _meta_setzen(conn, "inventar_zaehler", 0)
            _meta_setzen(conn, "schema_version", version)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys = {1 if fremdschluessel else 0}")
    return int(_meta(conn, "schema_version"))
