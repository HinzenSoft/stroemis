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
  - mat_product_request (Schritt 4): Meldung eines Produkts, das beim Anlegen eines Artikels im Katalog
    fehlt – mit Links, Fotos und Bemerkung. Ein Katalogpfleger pflegt es ein (neues oder vorhandenes
    Produkt) oder lehnt mit Begründung ab; der Melder bekommt Bescheid.
  - mat_round.aborted (Schritt 5): 1 = der Durchgang wurde vorzeitig beendet („abgebrochen“), nicht
    abgeschlossen; closed_on ist dann der Tag des Abbruchs.
  - Schritt 6 (Lieferung 3, Nachweis): mat_inspection.locked_login (Anmeldung beim Festschreiben) und
    correction_reason (Grund einer Berichtigung), mat_inspection_result.signature_png (Unterschriftsfeld
    eines Formulars), mat_round.locked_at (Sammelprotokoll festgeschrieben); höchstens eine Berichtigung
    je Prüfung; Indizes für die Prüfseite. Dazu Trigger, die festgeschriebene und abgeschlossene Prüfungen,
    ihre Befunde und Anhänge sowie abgeschlossene Durchgänge unveränderlich machen (auch gegen INSERT OR REPLACE
    und gegen Nachschieben in einen geschlossenen Durchgang) – die Service-Schicht
    weist Änderungen vorher mit Klartext ab, die Trigger fangen, was an ihr vorbeiginge. Ausgenommen sind
    nur die Nutzerkennungen, die die Datenbank beim Löschen eines Kontos selbst auf NULL setzt.
    Wer eine dieser Tabellen später neu aufbaut (wie Schritt 2), muss die Trigger danach neu anlegen.
  - Schritt 7 (Lieferung 4, Überblick): mat_recall – Rückruf eines Produkts durch den Hersteller, angelegt von
    einem Katalogpfleger (Titel, Beschreibung mit Empfehlung, Link, optional die betroffenen Seriennummern;
    beendet mit Vermerk); dazu mat_category.uid und mat_product.uid – eine zufällige, dauerhafte Kennung, über
    die der Katalog-Export einer Instanz (dev) Kategorien und Produkte in einer anderen (Produktion) auch nach
    Umbenennen oder Verschieben wiederfindet. Vorhandene Zeilen bekommen sie bei der Migration, neue per
    Trigger, wenn der einfügende Code keine mitgibt.
  - Schritt 8 (Phase 2 · Lieferung 1, Freigaben je Ordner): mat_folder_grant.note (Notiz, nie im Journal) und
    updated_at, höchstens ein Grundrecht (lesen oder verwalten) je Konto und Ordner, keine Freigaben an
    Systemordnern, Enddatum JJJJ-MM-TT (Trigger); mat_global_search – Protokoll der globalen Suche, der
    QR-Steckbriefe und fremder Dubletten (mit Frist, deshalb nicht im Journal); Indizes für Filter und Medien;
    users.mat_ref für alle Konten (pseudonymer Kontoverweis im Journal, Spalte in app/db.py). Dazu die Freigaben aus
    Phase 1: Wer bisher in den vorhandenen Gliederungen sah, sieht weiter (5.3), und die Bereinigung der Altfälle –
    Gesperrte im Systemordner einer fremden Gliederung, offene Durchgangszeilen außerhalb des Zweigs (5.4). Alles
    wiederholbar; ein zweiter Lauf ändert nichts.
  - Schritt 9 (Phase 2 · Lieferung 1, Nachbesserung vom 18.10.2026): Prüffreigaben sind nur noch für externe Prüfer
    befristet. Die Regel „Prüfrechte nur befristet“ aus Schritt 1 (CHECK permission <> 'pruefen' OR valid_until IS
    NOT NULL) fällt – SQLite entfernt ein CHECK nur mit einer neuen Tabelle: mat_folder_grant wird wie in Schritt 2
    neu aufgebaut (GRANT_9), mit denselben Spalten, Constraints, Indizes und Triggern und allen Zeilen. Ob eine
    dauerhafte Prüffreigabe erlaubt ist (nur mit Grundrecht am Anker), prüft der Dienst (freigaben.py), ob sie wirkt,
    die Sicht (rechte.py). Die Prüffreigaben, die Schritt 8 aus dem Häkchen „Prüfer“ gemacht hat, werden dauerhaft,
    wo das Konto dort auch lesen oder verwalten hat (oder Plattform-Verwaltung ist) und die Zeile seitdem niemand
    geändert hat; Journal „Migration Schritt 9“. Schritt 8 legt sie seitdem gleich so an (er baut die Tabelle dafür
    schon selbst um). Wiederholbar.
  - Schritt 10 (Phase 2 · Lieferung 1, Nachbesserung „Modulstufe“ vom 18.10.2026): Die Stufe im Modul Material
    (users.recht_material) wirkt wieder – 1 Mitglied (Modulzugang, Bestand über Freigaben), 2 Verwaltung
    (Material-Verwaltung: Katalog, alle Bestände, Gliederungen, jede Freigabe). Kein neues Schema, nur die Stufen:
    2 für bisherige Produktkatalogpfleger (mat_katalog) und die Plattform-Verwaltung; 1 für eine Stufe aus Phase 1
    (auch den Materialwart mit 2 – er verwaltet weiter über seine Freigaben), eine Freigabe (auch abgelaufen) oder das
    Häkchen Prüfer; sonst 0. mat_katalog bleibt stehen und wird nicht mehr gelesen (Rückweg). Journal „rollen“ am
    Konto je geänderter Stufe und je aufgelöstem Katalog-Häkchen, „Migration Schritt 10“, das Konto im Inhalt nur als
    Verweis. Wiederholbar.
  - Schritt 11 (Phase 2 · Lieferung 2, Erinnerungen): mat_reminder_log wird verworfen und neu angelegt (REMINDER_11) –
    bis dahin hat kein Code hineingeschrieben, es gibt nichts zu übernehmen. Neu: Kontoverweis konto_ref (users.mat_ref
    des Empfängers) statt der Adresse, Artikel ODER Freigabe (grant_id, Stufe „freigabe_ablauf“), due_on Pflicht und
    UNIQUE je Ziel, Stufe, Fälligkeit und Konto – dieselbe Stufe geht nie zweimal an dasselbe Konto, auch nicht bei
    zwei Läufen gleichzeitig. Dazu mat_folder.reminders_off (1 = keine Erinnerungen zu Artikeln in diesem Ordner und
    darunter; die Vererbung rechnet services/erinnerung.py). Wiederholbar.
  - Schritt 12 (Phase 2 · Lieferung 3, Bestandsimport und Prüfanleitung): mat_import – ein Lauf „Übernehmen“ eines
    Bestandsimports (Zielordner, Dateiname und SHA-256, Zahlen, wer, wann; die Datei selbst wird nicht gespeichert) –
    und mat_import_row – eine Zeile der Nacharbeit mit den zugeordneten Werten (nur solange sie offen ist), Gründen,
    Produktangabe, Produktwahl und Meldung; beide mit AUTOINCREMENT (das Journal nennt Importe). Dazu
    mat_form.wiki_page_id: die Wiki-Seite mit der Prüfanleitung zur Formularversion (ON DELETE SET NULL beim
    endgültigen Löschen der Seite). Rein additiv, wiederholbar. Wer mat_folder künftig neu aufbaut, muss den Verweis
    mat_import.folder_id (ON DELETE CASCADE) bedenken – wie mat_reminder_log.grant_id bei mat_folder_grant.
  - Schritt 13 (Phase 3 · Lieferung 1, Mangelmeldung): mat_defect_report – ein Mangel, den die zugeordnete Person oder
    ein Konto mit Leserecht am Artikel meldet: Beschreibung, Fotos (nur Web- und Vorschaufassung, das Original wird
    sofort gelöscht), Melder (Kennung und Namensschnappschuss), Sperrzustand vor der Meldung, Zeitpunkt; erledigt durch
    die Freiprüfung oder Aussonderung, die sie erledigt hat (closed_inspection_id, closed_at). AUTOINCREMENT – das
    Journal nennt Meldungen. Trigger (TRIGGER_13): Inhalt unveränderlich, kein Löschen (auch nicht per INSERT OR
    REPLACE), nur offen einfügbar, einmal erledigen und nur durch eine abgeschlossene Prüfung desselben Artikels; die
    Kontokennung darf nur auf NULL gehen (Konto gelöscht, der Name bleibt). Dazu users.mat_psa_mails (Erinnerungen zur
    eigenen PSA abbestellen) im Kernschema (app/db.py). Rein additiv, wiederholbar. Wer mat_item oder mat_inspection
    künftig neu aufbaut (wie Schritt 2), muss die Verweise item_id und closed_inspection_id bedenken.
  - Schritt 14 (Phase 3 · Lieferung 1, Nachbesserung vom 21.10.2026): Trigger mat_item_stammdaten_fest (TRIGGER_14) –
    Seriennummer und Herstelldatum eines Artikels ändern sich nicht mehr, sobald er eine abgeschlossene Prüfung hat
    (completed_at gesetzt; ein Entwurf zählt nicht). Beide stehen im Prüfprotokoll. Der Dienst (bestand.artikel_aendern)
    weist vorher mit Klartext ab; der Trigger fängt, was an ihm vorbeiginge – wie die Trigger aus Schritt 6. Kein neues
    Schema, rein additiv, wiederholbar. Wer mat_item künftig neu aufbaut, muss den Trigger danach neu anlegen.
  - Schritt 15 (Phase 3 · Lieferung 1, Entscheidungen vom 21.10.2026): mat_item_change – Antrag auf Änderung von
    Seriennummer oder Herstelldatum nach der ersten Prüfung (je Zeile ein Feld mit altem und neuem Wert, Begründung,
    Antragsteller; bestätigt oder abgelehnt von der Material-Verwaltung, abgelehnt nur mit Begründung; applied_at, sobald
    die bestätigte Änderung am Artikel steht). AUTOINCREMENT – das Journal nennt Anträge. Höchstens ein offener Antrag je
    Artikel und Feld (Index). Trigger (TRIGGER_15): Inhalt unveränderlich, nur offen einfügbar, einmal entscheiden, kein
    Löschen (auch nicht per INSERT OR REPLACE), Kontokennungen nur auf NULL (Konto gelöscht, der Name bleibt). Der Trigger
    mat_item_stammdaten_fest aus Schritt 14 wird ersetzt: Er lässt nach der ersten Prüfung nur noch zwei Änderungen
    zu – das Herstelldatum bei Metall nachtragen (leer → Wert) und genau die Änderung eines bestätigten, noch nicht
    angewendeten Antrags (alter UND neuer Wert müssen passen); mat_item_antrag_angewendet setzt danach applied_at, ein
    Antrag wirkt also genau einmal. Rein additiv, wiederholbar. Wer mat_item künftig neu aufbaut, muss beide Trigger
    und den Verweis item_id bedenken.
  - Schritt 16 (Phase 3 · Lieferung 1, Prüfung der Änderungsanträge vom 21.10.2026): Trigger (TRIGGER_16) gegen die
    Umwege an mat_item_stammdaten_fest vorbei, die nur ein direkter Eingriff in die Datenbank nimmt: einen Artikel per
    INSERT OR REPLACE ersetzen (mat_item_ersetzen), seine Kennung ändern (mat_item_kennung), einen geprüften löschen
    (mat_item_geprueft_loeschen – ohne Fremdschlüssel ginge es sonst samt Neuanlage unter derselben Kennung), sein
    Produkt nach der ersten Prüfung wechseln (mat_item_produkt_fest – wie der Dienst, bestand.artikel_aendern) und die
    Materialart eines Produkts mit geprüften Artikeln ändern oder ein Produkt ersetzen (mat_product_materialart_fest,
    mat_product_ersetzen – an der Materialart hängt das Nachtragen bei Metall). Kein App-Weg tut eines davon. Dazu
    (Entscheidung zu Befund 5): mat_item_stammdaten_fest wird ersetzt – Nachtragen bei Metall nur, solange kein
    angewendeter Antrag ein vorhandenes Herstelldatum entfernt hat. Kein neues Schema, rein additiv, wiederholbar. Wer
    mat_item oder mat_product künftig neu aufbaut, muss die Trigger neu anlegen.
  - Schritt 17 (Phase 3 · Lieferung 1, Entscheidungen vom 21.10.2026 zur Prüfung der Anträge): mat_item_change wird
    umgebaut (alle Zeilen und Kennungen bleiben, AUTOINCREMENT-Stand ebenso) – der CHECK kennt den Stand „zurückgezogen“
    (ANTRAGSSTATUS; Schritt 15 bleibt mit ANTRAGSSTATUS_15, wie er ausgeliefert wurde). Trigger (TRIGGER_17): einen
    offenen Antrag zieht nur der Antragsteller selbst zurück (Endzustand wie bestätigt und abgelehnt, einmal); ein
    Herstelldatum lässt sich nach der ersten Prüfung nicht mehr entfernen, auch nicht per Antrag – kein neuer Antrag mit
    leerem Herstelldatum, ein alter offener lässt sich nicht mehr bestätigen, mat_item_stammdaten_fest (ersetzt, gleicher
    Name) lässt das Feld nicht leer werden. Die Regel aus Schritt 16 (Nachtragen nach einem per Antrag entfernten
    Herstelldatum nur per Antrag) bleibt für Altfälle. Wiederholbar: Umgebaut wird nur, wenn der CHECK den neuen Stand
    noch nicht kennt. Wer mat_item_change künftig neu aufbaut, muss ihre Trigger und die beiden Artikeltrigger, die sie
    lesen, neu anlegen.
  - Schritt 18 (Herstellerdokumente einmal je Inhalt, 22.10.2026): Eine Dokumentdatei heißt seither nach ihrem Inhalt
    (<SHA-256><Endung> unter media/material/dok) und gehört allen Zeilen von mat_product_document mit diesem Inhalt
    (katalog._datei_ablegen, _datei_freigeben). Der Schritt selbst ist klein: Index auf file_path (Auslieferung,
    Freigeben) und das Kennzeichen mat_meta.dok_inhalt = „0“ – die Dateiarbeit (Altbestand umbenennen, Dubletten
    zusammenführen, Prüfsummen aus den Dateien nachtragen) macht nicht die Schematransaktion, sondern
    services/dokablage.beim_start gleich danach im selben Start, in eigener Transaktion mit Commit vor dem Entfernen
    der alten Namen; sie setzt das Kennzeichen auf „1“. Sind die Medien beim Start nicht erreichbar, bleibt es auf „0“
    und der nächste Start (oder flask material dok-zusammenfuehren) holt es nach. Wer mat_product_document künftig neu
    aufbaut, muss den Index neu anlegen.
  - Schritt 19 (Phase 4 · Lieferung 1, Mailfehler-Protokoll und Jahresbericht): mat_mail_fehler – je gescheiterter
    Modul-Mail (Erinnerung, Mangel, Antrag, Produktmeldung, Rückruf) eine Zeile mit Art, Fehlerklasse, gereinigter
    Serverantwort (nie eine Adresse: CHECK instr(meldung, '@') = 0), Bezug, Gliederung (folder_id mit ON DELETE SET NULL –
    Ordnerkennungen werden wiedervergeben), Kontoverweis und Rolle des Empfängers; geschrieben von
    services/mailprotokoll.senden, abgehakt von der Verwaltung (nur erledigt_* sind änderbar, Trigger
    mat_mail_fehler_fest). Dazu zwei Indizes für den Jahresbericht (inspected_on; entity, action, created_at im
    Journal). Rein additiv, nur IF NOT EXISTS, wiederholbar.
"""
import json
import re
import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 19

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
SPERRGRUENDE = {"sturz": "Sturzbelastung", "beschaedigung": "Beschädigung", "verlust": "Verlust", "rueckruf": "Rückruf"}
AUSSONDERUNGSGRUENDE = {"lebensdauer": "Lebensdauer erreicht", "verlust": "Verlust", "irreparabel": "irreparabel"}
ERGEBNISSE = {"einsatzbereit": "einsatzbereit", "instandsetzen": "instandsetzen", "aussondern": "aussondern"}
BEFUNDE = ("ok", "mangel", "nicht_zutreffend")
ANHANGARTEN = {"externes_pruefformular": "externes Prüfformular", "pruefbericht": "Prüfbericht", "foto": "Foto",
               "sonstiges": "Sonstiges"}
MELDUNGSSTATUS = {"offen": "offen", "eingepflegt": "eingepflegt", "abgelehnt": "abgelehnt"}
# Änderungsanträge zu den festen Stammdaten (Schritt 15): welche Felder, welche Stände.
ANTRAGSFELDER = {"serial_no": "Seriennummer", "manufactured_on": "Herstellung"}
ANTRAGSSTATUS = {"offen": "offen", "bestaetigt": "bestätigt", "abgelehnt": "abgelehnt", "zurueckgezogen": "zurückgezogen"}
# Die Stände, mit denen Schritt 15 die Tabelle angelegt hat – Schritt 17 nahm „zurückgezogen“ dazu.
ANTRAGSSTATUS_15 = ("offen", "bestaetigt", "abgelehnt")
FREIGABEN = ("lesen", "pruefen", "verwalten")
# Die Stufen, mit denen Schritt 1 das Erinnerungslog angelegt hat – Schritt 1 bleibt, wie er ausgeliefert wurde.
ERINNERUNGEN_1 = ("30_tage", "7_tage", "faellig", "lebensdauer")
ERINNERUNGEN = ERINNERUNGEN_1 + ("freigabe_ablauf",)
# Zustand einer Zeile der Nacharbeit (Bestandsimport, Schritt 12) – „ersetzt“: über die Nacharbeits-CSV neu eingelesen.
IMPORT_STATUS = {"offen": "offen", "uebernommen": "übernommen", "im_bestand": "schon im Bestand",
                 "verworfen": "verworfen", "ersetzt": "neu eingelesen"}


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
      kind    TEXT NOT NULL CHECK (kind IN """ + _in(ERINNERUNGEN_1) + """),
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


# Schritt 4: Meldungen fehlender Produkte – eine neue Tabelle, am Bestehenden ändert sich nichts.
SCHRITT_4 = [
    """CREATE TABLE IF NOT EXISTS mat_product_request (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      manufacturer     TEXT NOT NULL,
      model            TEXT NOT NULL,
      article_no       TEXT NOT NULL DEFAULT '',
      -- wie mat_product.dedupe_key: So findet die Liste das Produkt, sobald es im Katalog steht.
      dedupe_key       TEXT NOT NULL,
      norm             TEXT NOT NULL DEFAULT '',
      category_id      INTEGER REFERENCES mat_category(id) ON DELETE SET NULL,   -- Vorschlag des Melders
      folder_id        INTEGER REFERENCES mat_folder(id) ON DELETE SET NULL,     -- wohin die Artikel sollen
      links_json       TEXT NOT NULL DEFAULT '[]',  -- Adressen: Hersteller, Gebrauchsanleitung, Händler
      photos_json      TEXT NOT NULL DEFAULT '[]',  -- Dateien unter media/material/{orig,web,thumb}
      note             TEXT NOT NULL DEFAULT '',
      status           TEXT NOT NULL DEFAULT 'offen' CHECK (status IN """ + _in(MELDUNGSSTATUS) + """),
      product_id       INTEGER REFERENCES mat_product(id) ON DELETE SET NULL,    -- das eingepflegte Produkt
      answer           TEXT NOT NULL DEFAULT '',    -- Antwort des Katalogpflegers; bei Ablehnung Pflicht
      created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name  TEXT NOT NULL DEFAULT '',
      created_at       TEXT NOT NULL,
      resolved_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      resolved_by_name TEXT NOT NULL DEFAULT '',
      resolved_at      TEXT,
      CHECK ((status = 'offen') = (resolved_at IS NULL)),
      CHECK (status <> 'abgelehnt' OR answer <> '')
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_request_status ON mat_product_request(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_request_creator ON mat_product_request(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_mat_request_product ON mat_product_request(product_id)",
]


def _schritt_5(conn):
    """Prüfdurchgänge lassen sich abbrechen: mat_round.aborted."""
    if "aborted" not in _spalten(conn, "mat_round"):
        conn.execute("ALTER TABLE mat_round ADD COLUMN aborted INTEGER NOT NULL DEFAULT 0")


# Schritt 6 (Lieferung 3): Festschreiben, Berichtigung, Unterschriftsfelder, Sammelprotokoll.
# Spalten, die eine festgeschriebene Prüfung festhalten – alles außer inspector_user_id, die beim Löschen
# des Kontos auf NULL geht (Name, Urkundennummer und Unterschrift stehen ohnehin als Kopie in der Zeile).
_PRUEFUNG_FEST = ("item_id, round_id, protocol_id, inspector_name, inspector_certificate, form_id, form_version, "
                  "inspected_on, kind, result, reason, remarks, next_due_on, signature_png, corrects_inspection_id, "
                  "basis_inspection_id, documents_json, completed_at, locked_at, locked_login, correction_reason, "
                  "pdf_path, pdf_sha256, pdf_hashed_bytes, file_sha256, created_at, updated_at")
# Der Inhalt einer abgeschlossenen Prüfung – auch einer aus Lieferung 2, die noch kein Protokoll hat.
_PRUEFUNG_INHALT = ("item_id, round_id, inspector_name, inspector_certificate, form_id, form_version, inspected_on, kind, "
                    "result, reason, remarks, next_due_on, corrects_inspection_id, basis_inspection_id, documents_json, "
                    "completed_at, correction_reason, created_at")
_BEFUND_SPALTEN = ("inspection_id, position, group_name, checklist_text, editor, mandatory, expected_value, is_critical, "
                   "finding, value, note, photo, signature_png")
_ANHANG_SPALTEN = "inspection_id, kind, title, file_path, mime, pages, sha256, uploaded_by_name, uploaded_at, in_pdf"
_DURCHGANG_FEST = ("folder_id, title, opened_by_name, opened_on, closed_on, closed_by_name, protocol_id, pdf_path, "
                   "pdf_sha256, pdf_hashed_bytes, file_sha256, aborted, locked_at")
# Der Inhalt eines abgeschlossenen Durchgangs – auch eines aus Lieferung 2 ohne Sammelprotokoll.
_DURCHGANG_INHALT = "folder_id, title, opened_by_name, opened_on, closed_on, closed_by_name, aborted"
_FEST = "'Eine festgeschriebene Prüfung ist unveränderlich.'"
_ABGESCHLOSSEN = "'Eine abgeschlossene Prüfung ist unveränderlich.'"
_DURCHGANG_ZU = "'Ein abgeschlossener Prüfdurchgang ist unveränderlich.'"
_ELTERN_ZU = "EXISTS (SELECT 1 FROM mat_inspection x WHERE x.id = {}.inspection_id AND x.completed_at IS NOT NULL)"
_RUNDE_ZU = "EXISTS (SELECT 1 FROM mat_round r WHERE r.id = {}.round_id AND r.closed_on IS NOT NULL)"
# Eine andere, abgeschlossene Prüfung trägt schon diese Protokoll-ID oder berichtigt schon dasselbe Original.
_GLEICHE_EINDEUTIGE = (
    "((NEW.protocol_id IS NOT NULL AND EXISTS (SELECT 1 FROM mat_inspection x WHERE x.protocol_id = NEW.protocol_id "
    "AND x.id IS NOT NEW.id AND x.completed_at IS NOT NULL)) OR (NEW.corrects_inspection_id IS NOT NULL AND EXISTS "
    "(SELECT 1 FROM mat_inspection x WHERE x.corrects_inspection_id = NEW.corrects_inspection_id AND x.id IS NOT NEW.id "
    "AND x.completed_at IS NOT NULL)))")
_GLEICHE_RUNDEN_ID = ("(NEW.protocol_id IS NOT NULL AND EXISTS (SELECT 1 FROM mat_round r WHERE r.protocol_id = NEW.protocol_id "
                      "AND r.id IS NOT NEW.id AND r.closed_on IS NOT NULL))")
# INSERT OR REPLACE über die Kennung einer Zeile, die zu einer abgeschlossenen Prüfung gehört.
_ERSETZT_ZU = ("EXISTS (SELECT 1 FROM {} k JOIN mat_inspection x ON x.id = k.inspection_id "
               "WHERE k.id = NEW.id AND x.completed_at IS NOT NULL)")


def _trigger(name, wann, bedingung, meldung):
    return (f"CREATE TRIGGER IF NOT EXISTS {name} {wann} WHEN {bedingung} "
            f"BEGIN SELECT RAISE(ABORT, {meldung}); END")


TRIGGER_6 = [
    _trigger("mat_inspection_festgeschrieben", f"BEFORE UPDATE OF {_PRUEFUNG_FEST} ON mat_inspection",
             "OLD.locked_at IS NOT NULL", _FEST),
    _trigger("mat_inspection_abgeschlossen", f"BEFORE UPDATE OF {_PRUEFUNG_INHALT} ON mat_inspection",
             "OLD.completed_at IS NOT NULL", _ABGESCHLOSSEN),
    _trigger("mat_inspection_unloeschbar", "BEFORE DELETE ON mat_inspection", "OLD.completed_at IS NOT NULL",
             _ABGESCHLOSSEN),
    # Die Kontokennung des Prüfers darf nur auf NULL gehen (Konto gelöscht) – sonst dürfte ein anderes Konto die
    # Prüfung berichtigen, als hätte es sie gemacht.
    _trigger("mat_inspection_pruefer", "BEFORE UPDATE OF inspector_user_id ON mat_inspection",
             "OLD.completed_at IS NOT NULL AND NEW.inspector_user_id IS NOT NULL "
             "AND NEW.inspector_user_id IS NOT OLD.inspector_user_id", _ABGESCHLOSSEN),
    # INSERT OR REPLACE löscht ohne Lösch-Trigger (recursive_triggers ist aus) – deshalb auch beim Einfügen prüfen.
    _trigger("mat_inspection_ersetzen", "BEFORE INSERT ON mat_inspection",
             "EXISTS (SELECT 1 FROM mat_inspection x WHERE x.id = NEW.id AND x.completed_at IS NOT NULL) OR "
             + _GLEICHE_EINDEUTIGE, _ABGESCHLOSSEN),
    # Ebenso über die eindeutigen Spalten: Eine Protokoll-ID oder ein Berichtigungsverweis, den schon eine
    # abgeschlossene Prüfung trägt, ließe die andere per OR REPLACE verschwinden.
    _trigger("mat_inspection_eindeutig", "BEFORE UPDATE OF protocol_id, corrects_inspection_id ON mat_inspection",
             _GLEICHE_EINDEUTIGE, _ABGESCHLOSSEN),
    # Nichts kommt nachträglich in einen abgeschlossenen Durchgang.
    _trigger("mat_inspection_in_runde", "BEFORE INSERT ON mat_inspection",
             "NEW.round_id IS NOT NULL AND " + _RUNDE_ZU.format("NEW"), _DURCHGANG_ZU),
    _trigger("mat_inspection_runde_wechsel", "BEFORE UPDATE OF round_id ON mat_inspection",
             "NEW.round_id IS NOT NULL AND " + _RUNDE_ZU.format("NEW"), _DURCHGANG_ZU),
    _trigger("mat_result_aendern", f"BEFORE UPDATE OF {_BEFUND_SPALTEN} ON mat_inspection_result",
             _ELTERN_ZU.format("OLD") + " OR " + _ELTERN_ZU.format("NEW"), _ABGESCHLOSSEN),
    _trigger("mat_result_neu", "BEFORE INSERT ON mat_inspection_result",
             _ELTERN_ZU.format("NEW") + " OR " + _ERSETZT_ZU.format("mat_inspection_result"), _ABGESCHLOSSEN),
    _trigger("mat_result_loeschen", "BEFORE DELETE ON mat_inspection_result", _ELTERN_ZU.format("OLD"), _ABGESCHLOSSEN),
    _trigger("mat_attachment_aendern", f"BEFORE UPDATE OF {_ANHANG_SPALTEN} ON mat_inspection_attachment",
             _ELTERN_ZU.format("OLD") + " OR " + _ELTERN_ZU.format("NEW"), _ABGESCHLOSSEN),
    _trigger("mat_attachment_neu", "BEFORE INSERT ON mat_inspection_attachment",
             _ELTERN_ZU.format("NEW") + " OR " + _ERSETZT_ZU.format("mat_inspection_attachment"), _ABGESCHLOSSEN),
    _trigger("mat_attachment_loeschen", "BEFORE DELETE ON mat_inspection_attachment", _ELTERN_ZU.format("OLD"),
             _ABGESCHLOSSEN),
    _trigger("mat_round_festgeschrieben", f"BEFORE UPDATE OF {_DURCHGANG_FEST} ON mat_round",
             "OLD.locked_at IS NOT NULL", _DURCHGANG_ZU),
    _trigger("mat_round_abgeschlossen", f"BEFORE UPDATE OF {_DURCHGANG_INHALT} ON mat_round",
             "OLD.closed_on IS NOT NULL", _DURCHGANG_ZU),
    _trigger("mat_round_unloeschbar", "BEFORE DELETE ON mat_round", "OLD.closed_on IS NOT NULL", _DURCHGANG_ZU),
    _trigger("mat_round_ersetzen", "BEFORE INSERT ON mat_round",
             "EXISTS (SELECT 1 FROM mat_round r WHERE r.id = NEW.id AND r.closed_on IS NOT NULL) OR "
             + _GLEICHE_RUNDEN_ID, _DURCHGANG_ZU),
    _trigger("mat_round_eindeutig", "BEFORE UPDATE OF protocol_id ON mat_round", _GLEICHE_RUNDEN_ID, _DURCHGANG_ZU),
    _trigger("mat_round_item_aendern",
             "BEFORE UPDATE OF round_id, item_id, excluded_reason, excluded_by_name, excluded_at ON mat_round_item",
             _RUNDE_ZU.format("OLD") + " OR " + _RUNDE_ZU.format("NEW"), _DURCHGANG_ZU),
    _trigger("mat_round_item_neu", "BEFORE INSERT ON mat_round_item", _RUNDE_ZU.format("NEW"), _DURCHGANG_ZU),
    _trigger("mat_round_item_loeschen", "BEFORE DELETE ON mat_round_item", _RUNDE_ZU.format("OLD"), _DURCHGANG_ZU),
]


def _schritt_6(conn):
    """Lieferung 3: Spalten fürs Festschreiben und Berichtigen, Indizes für die Prüfseite, Trigger."""
    neu = [("mat_inspection", "locked_login", "TEXT NOT NULL DEFAULT ''"),
           ("mat_inspection", "correction_reason", "TEXT NOT NULL DEFAULT ''"),
           ("mat_inspection_result", "signature_png", "BLOB"),
           ("mat_round", "locked_at", "TEXT")]
    for tabelle, spalte, art in neu:
        if spalte not in _spalten(conn, tabelle):
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {art}")
    for sql in [
        # Eine Prüfung wird höchstens einmal berichtigt (auch der Entwurf der Berichtigung zählt);
        # wer weiter korrigieren will, berichtigt die Berichtigung.
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_inspection_berichtigt ON mat_inspection(corrects_inspection_id) "
        "WHERE corrects_inspection_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_mat_inspection_basis ON mat_inspection(basis_inspection_id) "
        "WHERE basis_inspection_id IS NOT NULL",
        # Die Prüfseite sucht ein hochgeladenes PDF über seine Prüfsummen.
        "CREATE INDEX IF NOT EXISTS idx_mat_inspection_datei ON mat_inspection(file_sha256) WHERE file_sha256 IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_mat_inspection_inhalt ON mat_inspection(pdf_sha256) WHERE pdf_sha256 IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_mat_round_datei ON mat_round(file_sha256) WHERE file_sha256 IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_mat_round_inhalt ON mat_round(pdf_sha256) WHERE pdf_sha256 IS NOT NULL",
    ] + TRIGGER_6:
        conn.execute(sql)


RECALL_7 = """CREATE TABLE IF NOT EXISTS mat_recall (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  -- Ein Rückruf gehört zu genau einem Produkt; ohne Produkt (gelöscht, also ohne Artikel) hat er keinen Sinn mehr.
  product_id      INTEGER NOT NULL REFERENCES mat_product(id) ON DELETE CASCADE,
  title           TEXT NOT NULL CHECK (title <> ''),
  description     TEXT NOT NULL DEFAULT '',    -- was betroffen ist und was zu tun ist (Empfehlung des Herstellers)
  url             TEXT NOT NULL DEFAULT '',    -- Meldung des Herstellers
  serials         TEXT NOT NULL DEFAULT '',    -- betroffene Seriennummern, eine je Zeile; leer = alle Artikel
  created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_by_name TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  closed_at       TEXT,                        -- beendet: kein Hinweis mehr an den Artikeln, bleibt am Produkt sichtbar
  closed_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  closed_by_name  TEXT NOT NULL DEFAULT '',
  close_note      TEXT NOT NULL DEFAULT '',
  mailed_at       TEXT,                        -- Benachrichtigung verschickt (Zeitpunkt, Zahl, Fehlschläge)
  mail_count      INTEGER NOT NULL DEFAULT 0,
  mail_failed     INTEGER NOT NULL DEFAULT 0
)"""


def _uid_trigger(tabelle):
    return (f"CREATE TRIGGER IF NOT EXISTS trg_{tabelle}_uid AFTER INSERT ON {tabelle} WHEN NEW.uid IS NULL "
            f"BEGIN UPDATE {tabelle} SET uid = lower(hex(randomblob(16))) WHERE id = NEW.id; END")


def _schritt_7(conn):
    """Lieferung 4: Rückrufe (mat_recall) und dauerhafte Kennungen für den Katalogaustausch (uid)."""
    conn.execute(RECALL_7)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mat_recall_product ON mat_recall(product_id, closed_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mat_recall_offen ON mat_recall(closed_at, created_at)")
    for tabelle in ("mat_category", "mat_product"):
        if "uid" not in _spalten(conn, tabelle):
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN uid TEXT")
        conn.execute(f"UPDATE {tabelle} SET uid = lower(hex(randomblob(16))) WHERE uid IS NULL")
        conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{tabelle}_uid ON {tabelle}(uid)")
        conn.execute(_uid_trigger(tabelle))


# --- Schritt 8 (Phase 2 · Lieferung 1): Freigaben je Ordner ---------------------------------------------------------
_KEINE_SYSTEMFREIGABE = "'Freigaben gibt es nicht für „Gesperrt“ und „Ausgesondert“ – sie gelten über die Gliederung.'"
_FREIGABE_DATUM = "'Enddatum einer Freigabe: JJJJ-MM-TT.'"
_SYSTEMORDNER_NEU = "(SELECT system_kind FROM mat_folder WHERE id = NEW.folder_id) IS NOT NULL"
_DATUM_FALSCH = ("NEW.valid_until IS NOT NULL AND NEW.valid_until NOT GLOB "
                 "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
GLOBAL_SEARCH_8 = """CREATE TABLE IF NOT EXISTS mat_global_search (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  user_name  TEXT NOT NULL DEFAULT '',
  art        TEXT NOT NULL CHECK (art IN ('suche', 'qr', 'dublette')),
  anfrage    TEXT NOT NULL,                -- Normalform der Seriennummer; bei „qr“ die Inventarnummer
  treffer    INTEGER NOT NULL,
  item_ids   TEXT NOT NULL DEFAULT '[]',   -- Kennungen der Treffer (JSON)
  created_at TEXT NOT NULL
)"""
# Indizes und Trigger an mat_folder_grant (Schritt 9 legt sie nach dem Neuaufbau wieder an).
GRANT_8 = [
    "CREATE INDEX IF NOT EXISTS idx_mat_grant_folder ON mat_folder_grant(folder_id)",
    # Je Konto und Ordner höchstens ein Grundrecht (lesen ODER verwalten) und höchstens eine Prüffreigabe (UNIQUE aus
    # Schritt 1).
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_grant_grundrecht ON mat_folder_grant(folder_id, user_id) "
    "WHERE permission IN ('lesen', 'verwalten')",
    _trigger("mat_grant_systemordner", "BEFORE INSERT ON mat_folder_grant", _SYSTEMORDNER_NEU, _KEINE_SYSTEMFREIGABE),
    _trigger("mat_grant_systemordner_aendern", "BEFORE UPDATE OF folder_id ON mat_folder_grant", _SYSTEMORDNER_NEU,
             _KEINE_SYSTEMFREIGABE),
    _trigger("mat_grant_datum", "BEFORE INSERT ON mat_folder_grant", _DATUM_FALSCH, _FREIGABE_DATUM),
    _trigger("mat_grant_datum_aendern", "BEFORE UPDATE OF valid_until ON mat_folder_grant", _DATUM_FALSCH,
             _FREIGABE_DATUM),
]
SCHRITT_8 = GRANT_8 + [
    GLOBAL_SEARCH_8,
    "CREATE INDEX IF NOT EXISTS idx_mat_global_search_zeit ON mat_global_search(created_at)",
    # Filter über die Heimat, globale Suche (exakt, ohne Groß/klein) und Medien je Datei.
    "CREATE INDEX IF NOT EXISTS idx_mat_item_serie_nocase ON mat_item(serial_no COLLATE NOCASE)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_origin ON mat_item(origin_folder_id) WHERE origin_folder_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_assigned ON mat_item(assigned_user_id) WHERE assigned_user_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_mat_folder_photo ON mat_folder(photo) WHERE photo <> ''",
    "CREATE INDEX IF NOT EXISTS idx_mat_product_image ON mat_product(image) WHERE image <> ''",
    "CREATE INDEX IF NOT EXISTS idx_mat_result_photo ON mat_inspection_result(photo) WHERE photo <> ''",
    "CREATE INDEX IF NOT EXISTS idx_mat_attachment_file ON mat_inspection_attachment(file_path)",
]
MIGRATION_8 = "Migration Schritt 8"
# Grundrecht und Notiz je Stufe aus Phase 1 – die Verwaltung (recht_verwaltung = 2) sieht ohnehin alles.
_PHASE_1 = {2: ("verwalten", "aus Phase 1: Stufe Verwaltung"), 1: ("lesen", "aus Phase 1: Stufe Mitglied")}
NOTIZ_PRUEFER_8 = "aus Phase 1: Häkchen Prüfer"


def _jetzt():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _journal_8(conn, entity, entity_id, action, vorher, nachher, wer=MIGRATION_8):
    """Ein Journaleintrag der Migration – direkt über die Verbindung, ohne Anfrage und ohne Konto."""
    def text(d):
        return json.dumps(d, ensure_ascii=False, sort_keys=True, default=str) if d is not None else None
    conn.execute("INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, after_json, "
                 "created_at) VALUES (?,?,NULL,?,?,?,?,?)",
                 (entity, entity_id, wer, action, text(vorher), text(nachher), _jetzt()))


def _schritt_8(conn):
    """Phase 2 · Lieferung 1: Schema der Freigaben und des Suchprotokolls, Kontoverweise, die Freigaben aus Phase 1
    und die Bereinigung der Altfälle (siehe oben). Wiederholbar."""
    if "mat_ref" not in _spalten(conn, "users"):              # legt sonst app/db.py an (MIGRATIONS)
        conn.execute("ALTER TABLE users ADD COLUMN mat_ref TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_mat_ref ON users(mat_ref) WHERE mat_ref IS NOT NULL")
    # 128 Bit Zufall je Konto; neue Konten bekommen ihn beim ersten Journaleintrag (journal.konto_ref).
    conn.execute("UPDATE users SET mat_ref = lower(hex(randomblob(16))) WHERE mat_ref IS NULL OR mat_ref = ''")
    spalten = _spalten(conn, "mat_folder_grant")
    if "note" not in spalten:
        conn.execute("ALTER TABLE mat_folder_grant ADD COLUMN note TEXT NOT NULL DEFAULT ''")
    if "updated_at" not in spalten:
        conn.execute("ALTER TABLE mat_folder_grant ADD COLUMN updated_at TEXT")
    for sql in SCHRITT_8:
        conn.execute(sql)
    # Seit Schritt 9 entstehen dauerhafte Prüffreigaben – dafür muss das CHECK „Prüfrechte nur befristet“ aus Schritt 1
    # vorher weg (sonst verwürfe INSERT OR IGNORE die Zeile stillschweigend). Schritt 9 findet die Tabelle dann schon
    # umgebaut vor.
    _grant_ohne_prueffrist(conn)
    _freigaben_aus_phase_1(conn)
    _altfaelle_bereinigen(conn)


def _freigaben_aus_phase_1(conn):
    """Status quo erhalten (5.3): Stufe 1 → lesen, Stufe 2 → verwalten an jeder vorhandenen obersten Gliederung,
    dauerhaft; jedes Konto mit Häkchen „Prüfer“ (auch Stufe 2 und die Verwaltung) dazu eine Prüffreigabe – seit der
    Nachbesserung (Schritt 9) dauerhaft, wo das Konto dort ein Grundrecht bekommt oder Plattform-Verwaltung ist; nur
    Konten ohne Stufe aus Phase 1 (externe Prüfer) bekommen sie bis zum 31.12. des Folgejahres, höchstens 24 Monate.
    Sie wirkt erst mit Urkundennummer. Je eingefügter Zeile ein Journaleintrag am Ordner – mit Kontoverweis, ohne
    Notiz."""
    from . import services as dienste
    from .services.interval import plus_monate
    tag = dienste.heute()
    bis = min(f"{tag.year + 1}-12-31", plus_monate(tag, 24).isoformat())
    gliederungen = [r[0] for r in conn.execute("SELECT id FROM mat_folder WHERE parent_id IS NULL AND kind = 'gliederung' "
                                               "AND system_kind IS NULL ORDER BY id")]
    if not gliederungen:
        return
    jetzt = _jetzt()
    for uid, ref, verwaltung, material, pruefer in conn.execute(
            "SELECT id, mat_ref, recht_verwaltung, recht_material, mat_pruefer FROM users ORDER BY id").fetchall():
        freigaben = []
        if int(verwaltung or 0) < 2 and int(material or 0) in _PHASE_1:
            recht, notiz = _PHASE_1[int(material)]
            freigaben.append((recht, None, notiz))
        if pruefer:
            mit_grund = bool(freigaben) or int(verwaltung or 0) >= 2
            freigaben.append(("pruefen", None if mit_grund else bis, NOTIZ_PRUEFER_8))
        for gid in gliederungen:
            for recht, ende, notiz in freigaben:
                vorher = conn.total_changes
                cur = conn.execute("INSERT OR IGNORE INTO mat_folder_grant (folder_id, user_id, permission, valid_until, "
                                   "granted_by, created_at, note) VALUES (?,?,?,?,NULL,?,?)",
                                   (gid, uid, recht, ende, jetzt, notiz))
                if conn.total_changes > vorher:
                    _journal_8(conn, "folder", gid, "freigabe_erteilt", None,
                               {"freigabe": cur.lastrowid, "konto": {"ref": ref}, "recht": recht, "bis": ende})


def _altfaelle_bereinigen(conn):
    """5.4: Gesperrte und verlorene Artikel, die im Systemordner einer anderen Gliederung liegen als ihre Heimat,
    kommen nach „Gesperrt“ der Gliederung ihrer Heimat. Offene Zeilen offener Durchgänge, deren Heimat nicht im Zweig
    des Durchgangs liegt, werden ausgenommen; offene Entwürfe dazu verlieren den Durchgang. Ausgesonderte aus Phase 1
    bleiben ohne Herkunft und gehören zu ihrer Gliederung. Journal mit „Migration Schritt 8“."""
    ordner = {r[0]: {"parent_id": r[1], "name": r[2], "kind": r[3], "system_kind": r[4]}
              for r in conn.execute("SELECT id, parent_id, name, kind, system_kind FROM mat_folder")}
    kinder = {}
    for fid, o in ordner.items():
        kinder.setdefault(o["parent_id"], []).append(fid)

    def kette(fid):
        out = []
        while fid is not None and fid in ordner and fid not in out:
            out.append(fid)
            fid = ordner[fid]["parent_id"]
        return out

    def gliederung(fid):
        return next((x for x in kette(fid) if ordner[x]["kind"] == "gliederung" and not ordner[x]["system_kind"]), None)

    def pfad_text(fid):
        return " / ".join(ordner[x]["name"] for x in reversed(kette(fid)))

    def zweig(fid):
        gesehen, offen = set(), [fid]
        while offen:
            x = offen.pop()
            if x not in gesehen:
                gesehen.add(x)
                offen.extend(kinder.get(x, ()))
        return gesehen

    jetzt = _jetzt()
    for iid, folder_id, origin in conn.execute(
            "SELECT id, folder_id, origin_folder_id FROM mat_item WHERE lock_state IN ('gesperrt', 'verloren') "
            "AND origin_folder_id IS NOT NULL ORDER BY id").fetchall():
        hier = ordner.get(folder_id)
        if not hier or not hier["system_kind"] or origin not in ordner:
            continue
        ziel_gl = gliederung(origin)
        if ziel_gl is None or ziel_gl == hier["parent_id"]:
            continue
        ziel = next((k for k in kinder.get(ziel_gl, ()) if ordner[k]["system_kind"] == "gesperrt"), None)
        if ziel is None:
            continue
        conn.execute("UPDATE mat_item SET folder_id = ?, updated_at = ? WHERE id = ?", (ziel, jetzt, iid))
        _journal_8(conn, "item", iid, "verschoben", {"folder_id": folder_id, "ordner": pfad_text(folder_id)},
                   {"folder_id": ziel, "ordner": pfad_text(ziel), "grund": "Bereinigung Schritt 8"})

    grund = "verschoben (Bereinigung Schritt 8)"
    for rid, rfid in conn.execute("SELECT id, folder_id FROM mat_round WHERE closed_on IS NULL ORDER BY id").fetchall():
        im_zweig = zweig(rfid)
        zeilen = conn.execute(
            "SELECT i.id, i.lock_state, i.folder_id, i.origin_folder_id FROM mat_round_item ri "
            "JOIN mat_item i ON i.id = ri.item_id WHERE ri.round_id = ? AND ri.excluded_reason IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.round_id = ri.round_id AND x.item_id = ri.item_id "
            "AND x.completed_at IS NOT NULL) ORDER BY i.id", (rid,)).fetchall()
        for iid, sperre, folder_id, origin in zeilen:
            heimat = origin if sperre != "frei" and origin else folder_id
            if heimat in im_zweig:
                continue
            conn.execute("UPDATE mat_round_item SET excluded_reason = ?, excluded_by = NULL, excluded_by_name = 'System', "
                         "excluded_at = ? WHERE round_id = ? AND item_id = ?", (grund, jetzt, rid, iid))
            _journal_8(conn, "round", rid, "ausgenommen", None, {"item_id": iid, "grund": grund})
            for (xid,) in conn.execute("SELECT id FROM mat_inspection WHERE round_id = ? AND item_id = ? "
                                       "AND completed_at IS NULL", (rid, iid)).fetchall():
                conn.execute("UPDATE mat_inspection SET round_id = NULL WHERE id = ?", (xid,))
                _journal_8(conn, "inspection", xid, "geaendert", {"round_id": rid}, {"round_id": None})


# --- Schritt 9 (Phase 2 · Lieferung 1, Nachbesserung vom 18.10.2026): Prüffreigaben dauerhaft mit Grundrecht -----
# mat_folder_grant ohne das CHECK „Prüfrechte nur befristet“ aus Schritt 1, sonst wie bisher: die Spalten aus Schritt 1
# und 8 in derselben Reihenfolge, ein UNIQUE je Ordner, Konto und Recht, Kennungen ohne AUTOINCREMENT. {name} ist beim
# Umbau zuerst mat_folder_grant_neu. Ob eine Prüffreigabe ohne Ende sein darf, entscheidet der Dienst (nur mit
# Grundrecht am Anker, freigaben.py), ob sie wirkt, die Sicht (rechte.py).
GRANT_9 = """CREATE TABLE {name} (
      id          INTEGER PRIMARY KEY,
      folder_id   INTEGER NOT NULL REFERENCES mat_folder(id) ON DELETE CASCADE,
      user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      permission  TEXT NOT NULL CHECK (permission IN """ + _in(FREIGABEN) + """),
      valid_until TEXT,                         -- leer: dauerhaft (prüfen nur zusammen mit einem Grundrecht)
      granted_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_at  TEXT NOT NULL,
      note        TEXT NOT NULL DEFAULT '',
      updated_at  TEXT,
      UNIQUE (folder_id, user_id, permission)
    )"""
GRANT_INDIZES = ["CREATE INDEX IF NOT EXISTS idx_mat_grant_user ON mat_folder_grant(user_id)"] + GRANT_8
# Das CHECK aus Schritt 1, wie es in sqlite_master steht (Groß/klein und Leerraum egal).
_NUR_BEFRISTET = re.compile(r"permission\s*<>\s*'pruefen'\s+or\s+valid_until\s+is\s+not\s+null", re.IGNORECASE)
MIGRATION_9 = "Migration Schritt 9"


def _grant_ohne_prueffrist(conn):
    """mat_folder_grant ohne das CHECK „Prüfrechte nur befristet“ neu aufbauen – nur, solange es noch da ist (sonst
    nichts). Verfahren wie Schritt 2 (Fremdschlüssel sind aus, siehe migrieren; legacy_alter_table braucht es nicht,
    denn kein Trigger und keine Sicht einer anderen Tabelle nennt mat_folder_grant): neue Tabelle, alle Zeilen
    kopieren, alte löschen, umbenennen. Mit der alten Tabelle gehen ihre Indizes und Trigger – sie entstehen danach
    genau so wieder, wie sie in sqlite_master standen, dazu die bekannten aus Schritt 1 und 8, falls einer fehlte. Fehlt
    danach eine Zeile oder bricht ein Verweis, bricht die Migration ab (die Transaktion rollt zurück).

    Seit Schritt 11 verweist auch mat_reminder_log.grant_id auf mat_folder_grant: Ein künftiger Neuaufbau dieser Tabelle
    muss das bedenken (Fremdschlüssel aus, Kennungen behalten). Auf den Wegen 7→11 und frisch läuft dieser Schritt vor
    Schritt 11 und findet noch das alte Log ohne diesen Verweis vor."""
    tabelle = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                           ("mat_folder_grant",)).fetchone()
    if not tabelle or not _NUR_BEFRISTET.search(tabelle[0] or ""):
        return False
    vorher = _fk_verletzungen(conn, ("mat_folder_grant",))
    zahl = conn.execute("SELECT COUNT(*) FROM mat_folder_grant").fetchone()[0]
    begleiter = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = 'mat_folder_grant' AND type IN ('index', 'trigger') "
        "AND sql IS NOT NULL ORDER BY type, name")]
    alt = _spalten(conn, "mat_folder_grant")
    conn.execute("DROP TABLE IF EXISTS mat_folder_grant_neu")
    conn.execute(GRANT_9.format(name="mat_folder_grant_neu"))
    neu = _spalten(conn, "mat_folder_grant_neu")
    if any(s not in neu for s in alt):
        raise sqlite3.IntegrityError(f"mat_folder_grant hat unbekannte Spalten: {[s for s in alt if s not in neu]}")
    spalten = ", ".join(alt)
    conn.execute(f"INSERT INTO mat_folder_grant_neu ({spalten}) SELECT {spalten} FROM mat_folder_grant")
    conn.execute("DROP TABLE mat_folder_grant")
    conn.execute("ALTER TABLE mat_folder_grant_neu RENAME TO mat_folder_grant")
    for befehl in begleiter + GRANT_INDIZES:
        conn.execute(befehl)
    if conn.execute("SELECT COUNT(*) FROM mat_folder_grant").fetchone()[0] != zahl:
        raise sqlite3.IntegrityError("mat_folder_grant: Beim Neuaufbau fehlen Zeilen.")
    neu_verletzt = _fk_verletzungen(conn, ("mat_folder_grant",)) - vorher
    if neu_verletzt:
        raise sqlite3.IntegrityError(f"Fremdschlüssel nach dem Umbau verletzt: {sorted(neu_verletzt)[:5]}")
    return True


def _pruefer_aus_phase_1_dauerhaft(conn):
    """Die Prüffreigaben, die Schritt 8 aus dem Häkchen „Prüfer“ gemacht hat, werden dauerhaft, wo das Konto am Anker
    oder darüber heute ein Grundrecht hat oder Plattform-Verwaltung ist – externe Prüfer behalten ihr Ende. Nur
    unveränderte: ohne vergebendes Konto, mit der Notiz aus Schritt 8, mit dem Journaleintrag „freigabe_erteilt“ von
    „Migration Schritt 8“, ohne Änderung seitdem (updated_at leer, kein „freigabe_geaendert“). Je Zeile ein
    Journaleintrag „Migration Schritt 9“ am Ordner, das Konto nur als Verweis."""
    from . import services as dienste
    heute = dienste.heute().isoformat()
    kandidaten = conn.execute(
        "SELECT g.id, g.folder_id, g.user_id, g.valid_until, u.mat_ref, u.recht_verwaltung FROM mat_folder_grant g "
        "JOIN users u ON u.id = g.user_id WHERE g.permission = 'pruefen' AND g.valid_until IS NOT NULL "
        "AND g.granted_by IS NULL AND g.note = ? AND g.updated_at IS NULL "
        "AND EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'folder' AND a.entity_id = g.folder_id "
        "AND a.action = 'freigabe_erteilt' AND a.user_id IS NULL AND a.user_name = ? "
        "AND json_extract(a.after_json, '$.freigabe') = g.id) "
        "AND NOT EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'folder' AND a.entity_id = g.folder_id "
        "AND a.action = 'freigabe_geaendert' AND json_extract(a.after_json, '$.freigabe') = g.id) ORDER BY g.id",
        (NOTIZ_PRUEFER_8, MIGRATION_8)).fetchall()
    if not kandidaten:
        return
    eltern = dict(conn.execute("SELECT id, parent_id FROM mat_folder").fetchall())
    grund = {}
    for uid, fid in conn.execute("SELECT user_id, folder_id FROM mat_folder_grant WHERE permission IN ('lesen', "
                                 "'verwalten') AND (valid_until IS NULL OR valid_until >= ?)", (heute,)):
        grund.setdefault(uid, set()).add(fid)

    def kette(fid):
        out = []
        while fid is not None and fid not in out:
            out.append(fid)
            fid = eltern.get(fid)
        return out

    jetzt = _jetzt()
    for gid, fid, uid, bis, ref, verwaltung in kandidaten:
        if int(verwaltung or 0) < 2 and not grund.get(uid, set()) & set(kette(fid)):
            continue
        if not ref:                                   # Schritt 8 gab jedem Konto einen – nur zur Sicherheit
            ref = conn.execute("SELECT lower(hex(randomblob(16)))").fetchone()[0]
            conn.execute("UPDATE users SET mat_ref = ? WHERE id = ?", (ref, uid))
        conn.execute("UPDATE mat_folder_grant SET valid_until = NULL, updated_at = ? WHERE id = ?", (jetzt, gid))
        spur = {"freigabe": gid, "konto": {"ref": ref}, "recht": "pruefen"}
        _journal_8(conn, "folder", fid, "freigabe_geaendert", dict(spur, bis=bis),
                   dict(spur, bis=None, grund="nur externe Prüfer befristet"), wer=MIGRATION_9)


def _schritt_9(conn):
    """Nachbesserung zu Phase 2 · Lieferung 1: Prüffreigaben dauerhaft mit Grundrecht (siehe oben). Wiederholbar."""
    _grant_ohne_prueffrist(conn)
    _pruefer_aus_phase_1_dauerhaft(conn)


MIGRATION_10 = "Migration Schritt 10"
# Die Regel für Schritt 10 in SQL (über users u): bisherige Katalogpfleger und die Plattform-Verwaltung → 2; eine
# Stufe aus Phase 1, irgendeine Freigabe (auch abgelaufen) oder das Häkchen Prüfer → 1; sonst 0.
STUFE_10 = ("CASE WHEN COALESCE(u.mat_katalog, 0) = 1 OR COALESCE(u.recht_verwaltung, 0) >= 2 THEN 2 "
            "WHEN COALESCE(u.recht_material, 0) >= 1 OR COALESCE(u.mat_pruefer, 0) = 1 "
            "OR EXISTS (SELECT 1 FROM mat_folder_grant g WHERE g.user_id = u.id) THEN 1 ELSE 0 END")


def _schritt_10(conn):
    """Nachbesserung „Modulstufe“ (siehe oben): die Stufen im Modul Material nach STUFE_10. Der Code liest seitdem
    wieder recht_material (Kopfleiste, Zugang, Material-Verwaltung) und mat_katalog nicht mehr. Freigaben, Häkchen
    Prüfer, Urkundennummern und mat_katalog selbst bleiben unberührt. Ins Journal („rollen“ am Konto, wie die
    Einträge der Nutzerverwaltung) kommt, wessen Stufe sich ändert oder wessen Katalog-Häkchen in der Stufe aufgeht –
    das Konto nur als Verweis {"ref": mat_ref}, ohne Namen und E-Mail. Wiederholbar: Ein zweiter Lauf findet die
    Stufen schon so vor und schreibt nichts; ein Konto mit Eintrag „Migration Schritt 10“ bekommt keinen zweiten."""
    spalten = _spalten(conn, "users")
    if "recht_material" not in spalten:            # legt sonst app/db.py an (MIGRATIONS) – ohne sie gibt es nichts
        return
    katalog = "u.mat_katalog" if "mat_katalog" in spalten else "0"
    pruefer = "u.mat_pruefer" if "mat_pruefer" in spalten else "0"
    regel = STUFE_10.replace("u.mat_katalog", katalog).replace("u.mat_pruefer", pruefer)
    zeilen = conn.execute(
        f"SELECT u.id, u.mat_ref, COALESCE(u.recht_material, 0), COALESCE({katalog}, 0), {regel}, "
        "EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'user' AND a.entity_id = u.id AND a.action = 'rollen' "
        "AND a.user_id IS NULL AND a.user_name = ?) FROM users u ORDER BY u.id", (MIGRATION_10,)).fetchall()
    for uid, ref, alt, kat, neu, schon in zeilen:
        if alt != neu:
            conn.execute("UPDATE users SET recht_material = ? WHERE id = ?", (neu, uid))
        if schon or (alt == neu and not kat):
            continue
        if not ref:
            ref = conn.execute("SELECT lower(hex(randomblob(16)))").fetchone()[0]
            conn.execute("UPDATE users SET mat_ref = ? WHERE id = ?", (ref, uid))
        vorher = {"recht_material": alt}
        if kat:
            vorher["mat_katalog"] = 1
        _journal_8(conn, "user", uid, "rollen", vorher,
                   {"recht_material": neu, "konto": {"ref": ref}, "grund": "Modulstufe Material (Schritt 10)"},
                   wer=MIGRATION_10)


# --- Schritt 11 (Phase 2 · Lieferung 2, Erinnerungen) ------------------------------------------------------------
# Das Erinnerungslog in seiner Form ab Schritt 11: je Zeile eine Erinnerung an genau ein Ziel (Artikel ODER Freigabe), die
# ein Konto bekommen hat – nur, wenn der Mailserver die Mail angenommen hat. Das Konto steht als Kontoverweis
# (users.mat_ref) da, nie mit Adresse; eine user_id könnte SQLite nach dem Löschen neu vergeben. Auf mat_ref gibt es
# keinen Fremdschlüssel (der UNIQUE-Index dort ist partiell) – die Zeilen eines gelöschten Kontos räumen loeschung.py
# und das Aufräumen des Tageslaufs selbst weg. Wird ein Artikel oder eine Freigabe gelöscht, gehen ihre Zeilen mit.
REMINDER_11 = """CREATE TABLE IF NOT EXISTS {name} (
      id        INTEGER PRIMARY KEY,
      item_id   INTEGER REFERENCES mat_item(id) ON DELETE CASCADE,
      grant_id  INTEGER REFERENCES mat_folder_grant(id) ON DELETE CASCADE,
      kind      TEXT NOT NULL CHECK (kind IN """ + _in(ERINNERUNGEN) + """),
      due_on    TEXT NOT NULL CHECK (due_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
                                                -- Fälligkeit, Lebensende bzw. Enddatum der Freigabe
      konto_ref TEXT NOT NULL CHECK (konto_ref <> ''),   -- users.mat_ref des Empfängers, nie die Adresse
      sent_at   TEXT NOT NULL,                  -- UTC, vom Mailserver angenommen
      CHECK ((item_id IS NULL) <> (grant_id IS NULL)),
      CHECK ((kind = 'freigabe_ablauf') = (grant_id IS NOT NULL))
    )"""
REMINDER_INDIZES = [
    # Dieselbe Stufe zur selben Fälligkeit an dasselbe Konto höchstens einmal – auch bei zwei Läufen gleichzeitig.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_reminder_artikel ON mat_reminder_log(item_id, kind, due_on, konto_ref) "
    "WHERE item_id IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_reminder_freigabe ON mat_reminder_log(grant_id, due_on, konto_ref) "
    "WHERE grant_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_mat_reminder_zeit ON mat_reminder_log(sent_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_reminder_konto ON mat_reminder_log(konto_ref)",
]


def _erinnerungslog_neu(conn):
    """Verwerfen und neu anlegen: Bis Schritt 11 hat kein Code ins Log geschrieben, Zeilen aus Schritt 1 gibt es nicht.
    Ohne Übernahme kann auch keine doppelte Altzeile den UNIQUE-Index (in _schritt_11 danach) scheitern lassen."""
    conn.execute("DROP TABLE IF EXISTS mat_reminder_log")
    conn.execute(REMINDER_11.format(name="mat_reminder_log"))


def _schritt_11(conn):
    """Phase 2 · Lieferung 2: Erinnerungslog mit Kontoverweis und Freigaben (Neuaufbau), Schalter je Ordner. Wiederholbar:
    Ein zweiter Lauf findet Spalte und Tabelle schon vor und legt nur fehlende Indizes an."""
    if "reminders_off" not in _spalten(conn, "mat_folder"):
        conn.execute("ALTER TABLE mat_folder ADD COLUMN reminders_off INTEGER NOT NULL DEFAULT 0 "
                     "CHECK (reminders_off IN (0, 1))")
    if "konto_ref" not in _spalten(conn, "mat_reminder_log"):
        _erinnerungslog_neu(conn)
    for sql in REMINDER_INDIZES:
        conn.execute(sql)


# --- Schritt 12 (Phase 2 · Lieferung 3, Bestandsimport und Prüfanleitung aus dem Wiki) ----------------------------
SCHRITT_12_IMPORT = [
    # Ein Lauf „Übernehmen“ eines Bestandsimports – auch einer, der nur Nacharbeit hinterlässt.
    """CREATE TABLE IF NOT EXISTS mat_import (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      folder_id       INTEGER NOT NULL REFERENCES mat_folder(id) ON DELETE CASCADE,   -- Zielordner
      file_name       TEXT NOT NULL DEFAULT '',          -- Name der Datei, wie hochgeladen (höchstens 200 Zeichen)
      file_sha256     TEXT NOT NULL DEFAULT '',          -- „dieselbe Datei schon importiert?“
      file_kind       TEXT NOT NULL CHECK (file_kind IN ('csv', 'xlsx')),
      rows_total      INTEGER NOT NULL DEFAULT 0,        -- Datenzeilen mit Inhalt
      rows_created    INTEGER NOT NULL DEFAULT 0,        -- beim Übernehmen angelegte Artikel
      rows_existing   INTEGER NOT NULL DEFAULT 0,        -- schon im Bestand oder schon erledigt (übersprungen)
      rows_rework     INTEGER NOT NULL DEFAULT 0,        -- in die Nacharbeit
      created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name TEXT NOT NULL DEFAULT '',
      created_at      TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_import_folder ON mat_import(folder_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_import_datei ON mat_import(folder_id, file_sha256)",
    # Eine Zeile der Nacharbeit. values_json hält nur die zugeordneten Felder (Schlüssel aus bestandsimport.FELDER) als
    # Text, so wie sie gelesen wurden (je Feld gekürzt) – solange die Zeile offen ist; beim Erledigen wird es geleert.
    """CREATE TABLE IF NOT EXISTS mat_import_row (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,                            -- = „Nacharbeit-Nr.“
      import_id        INTEGER NOT NULL REFERENCES mat_import(id) ON DELETE CASCADE,
      line_no          INTEGER NOT NULL CHECK (line_no >= 1),        -- Zeile in der Datei, wie Excel zählt
      values_json      TEXT NOT NULL DEFAULT '{}',
      reason_code      TEXT NOT NULL DEFAULT '',                     -- Codes der Gründe (bestandsimport.GRUENDE), mit
                                                                     -- „,“ getrennt; der erste bestimmt die Gruppe
      reason           TEXT NOT NULL DEFAULT '',                     -- alle Gründe in Klartext, „ · “ getrennt
      offer_key        TEXT NOT NULL DEFAULT '',                     -- Produktangabe vereinheitlicht (katalog.dedupe_key)
      product_id       INTEGER REFERENCES mat_product(id) ON DELETE SET NULL,            -- zugeordnetes Produkt
      request_id       INTEGER REFERENCES mat_product_request(id) ON DELETE SET NULL,    -- „Produkt melden“
      status           TEXT NOT NULL DEFAULT 'offen'
                       CHECK (status IN """ + _in(IMPORT_STATUS) + """),
      item_id          INTEGER REFERENCES mat_item(id) ON DELETE SET NULL,               -- angelegt/gefunden
      resolved_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      resolved_by_name TEXT NOT NULL DEFAULT '',
      resolved_at      TEXT,
      CHECK ((status = 'offen') = (resolved_at IS NULL)),
      UNIQUE (import_id, line_no)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_import_row_status ON mat_import_row(import_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_mat_import_row_angabe ON mat_import_row(import_id, offer_key)",
    "CREATE INDEX IF NOT EXISTS idx_mat_import_row_meldung ON mat_import_row(request_id) WHERE request_id IS NOT NULL",
]
SCHRITT_12_WIKI = [
    # Prüfanleitung zur Formularversion: eine Wiki-Seite. Kein Abschnitt, kein Anker – eingeblendet wird immer der
    # Abschnitt „Prüfung“, wenn die Seite ihn hat. ADD COLUMN mit REFERENCES geht in SQLite nur mit Vorgabe NULL.
    ("mat_form", "wiki_page_id", "INTEGER REFERENCES wiki_pages(id) ON DELETE SET NULL"),
]
WIKI_INDIZES = [
    # ON DELETE SET NULL beim endgültigen Löschen einer Wiki-Seite (purge) sucht hier.
    "CREATE INDEX IF NOT EXISTS idx_mat_form_wiki ON mat_form(wiki_page_id) WHERE wiki_page_id IS NOT NULL",
]


def _schritt_12(conn):
    """Phase 2 · Lieferung 3: Bestandsimport (mat_import, mat_import_row) und Wiki-Verknüpfung am Prüfformular
    (mat_form.wiki_page_id). Rein additiv; ein zweiter Lauf findet alles vor und ändert nichts. Keine Trigger an
    mat_form: Die Unveränderlichkeit benutzter Formulare setzt weiter der Dienst durch, und die Wiki-Route schreibt nur
    diese eine Spalte (das SET NULL eines Wiki-Purge ist ebenfalls ein UPDATE an mat_form)."""
    for sql in SCHRITT_12_IMPORT:
        conn.execute(sql)
    for tabelle, spalte, art in SCHRITT_12_WIKI:
        if spalte not in _spalten(conn, tabelle):
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {art}")
    for sql in WIKI_INDIZES:
        conn.execute(sql)


# --- Schritt 13 (Phase 3 · Lieferung 1, Mangelmeldung) ------------------------------------------------------------
MANGEL_FEST = "'Eine Mangelmeldung lässt sich weder ändern noch löschen.'"
SCHRITT_13 = [
    """CREATE TABLE IF NOT EXISTS mat_defect_report (
      id                   INTEGER PRIMARY KEY AUTOINCREMENT,         -- das Journal nennt Meldungen: nie wiederverwendet
      item_id              INTEGER NOT NULL REFERENCES mat_item(id),  -- kein CASCADE: ein Artikel mit Meldung bleibt
      description          TEXT NOT NULL CHECK (trim(description) <> '' AND length(description) <= 2000),
      photos_json          TEXT NOT NULL DEFAULT '[]',                -- Dateinamen; nur web/thumb liegen vor
      reporter_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
      reporter_name        TEXT NOT NULL CHECK (trim(reporter_name) <> ''),
      lock_before          TEXT NOT NULL CHECK (lock_before IN ('frei', 'gesperrt', 'verloren')),
      created_at           TEXT NOT NULL,                             -- UTC wie db.now()
      closed_inspection_id INTEGER REFERENCES mat_inspection(id),     -- Freiprüfung bzw. Aussonderung, die erledigt
      closed_at            TEXT,
      CHECK ((closed_at IS NULL) = (closed_inspection_id IS NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_defect_item ON mat_defect_report(item_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_defect_offen ON mat_defect_report(item_id) WHERE closed_at IS NULL",
    # Für ON DELETE SET NULL beim Kontolöschen und die Zahl im Dialog „Konto löschen“ (loeschung.folgen).
    "CREATE INDEX IF NOT EXISTS idx_mat_defect_melder ON mat_defect_report(reporter_id)",
]
TRIGGER_13 = [
    # Inhalt einer Meldung: nie ändern.
    _trigger("mat_defect_aendern", "BEFORE UPDATE OF id, item_id, description, photos_json, reporter_name, lock_before, "
             "created_at ON mat_defect_report", "1", MANGEL_FEST),
    # Die Kontokennung darf nur auf NULL gehen (Konto gelöscht, ON DELETE SET NULL).
    _trigger("mat_defect_melder", "BEFORE UPDATE OF reporter_id ON mat_defect_report",
             "NEW.reporter_id IS NOT NULL AND NEW.reporter_id IS NOT OLD.reporter_id", MANGEL_FEST),
    # Erledigt wird einmal – danach steht es fest.
    _trigger("mat_defect_erledigt", "BEFORE UPDATE OF closed_inspection_id, closed_at ON mat_defect_report",
             "OLD.closed_at IS NOT NULL", MANGEL_FEST),
    _trigger("mat_defect_loeschen", "BEFORE DELETE ON mat_defect_report", "1", MANGEL_FEST),
    # INSERT OR REPLACE löscht ohne Lösch-Trigger (recursive_triggers aus) – deshalb auch beim Einfügen prüfen.
    _trigger("mat_defect_ersetzen", "BEFORE INSERT ON mat_defect_report",
             "EXISTS (SELECT 1 FROM mat_defect_report d WHERE d.id = NEW.id)", MANGEL_FEST),
    # Eine Meldung entsteht immer offen – erledigt wird sie nur per UPDATE (mangel.erledigen).
    _trigger("mat_defect_neu_erledigt", "BEFORE INSERT ON mat_defect_report",
             "NEW.closed_at IS NOT NULL OR NEW.closed_inspection_id IS NOT NULL", MANGEL_FEST),
    # Erledigen nur durch eine abgeschlossene Prüfung (oder Aussonderung) desselben Artikels.
    _trigger("mat_defect_erledigt_durch", "BEFORE UPDATE OF closed_inspection_id ON mat_defect_report",
             "NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.id = NEW.closed_inspection_id "
             "AND x.item_id = OLD.item_id AND x.completed_at IS NOT NULL)", MANGEL_FEST),
]


def _schritt_13(conn):
    """Phase 3 · Lieferung 1: Mangelmeldungen (mat_defect_report) mit Triggern. Rein additiv; ein zweiter Lauf findet
    alles vor und ändert nichts. Wer mat_item oder mat_inspection künftig neu aufbaut (wie Schritt 2), muss die
    Verweise item_id und closed_inspection_id bedenken – wie mat_reminder_log.grant_id bei mat_folder_grant.
    users.mat_psa_mails legt das Kernschema an (app/db.py, MIGRATIONS) – init_db läuft vor der Modulmigration."""
    for sql in SCHRITT_13 + TRIGGER_13:
        conn.execute(sql)


# --- Schritt 14 (Phase 3 · Lieferung 1, Nachbesserung vom 21.10.2026): Stammdaten fest seit der ersten Prüfung -------

STAMMDATEN_FEST = "'Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest.'"
TRIGGER_14 = [
    # Nur eine echte Änderung: Derselbe Wert (auch NULL auf NULL) geht durch – artikel_aendern schreibt jede Spalte neu.
    _trigger("mat_item_stammdaten_fest", "BEFORE UPDATE OF serial_no, manufactured_on ON mat_item",
             "(NEW.serial_no IS NOT OLD.serial_no OR NEW.manufactured_on IS NOT OLD.manufactured_on) "
             "AND EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = OLD.id AND x.completed_at IS NOT NULL)",
             STAMMDATEN_FEST),
]


def _schritt_14(conn):
    """Nachbesserung vom 21.10.2026: Seriennummer und Herstelldatum nach der ersten abgeschlossenen Prüfung fest
    (Trigger). Rein additiv; ein zweiter Lauf findet ihn vor und ändert nichts."""
    for sql in TRIGGER_14:
        conn.execute(sql)


# --- Schritt 15 (Phase 3 · Lieferung 1, Entscheidungen vom 21.10.2026): Änderungsanträge zu festen Stammdaten -------

ANTRAG_FEST = "'Ein Änderungsantrag lässt sich nur einmal entscheiden – danach weder ändern noch löschen.'"
SCHRITT_15 = [
    """CREATE TABLE IF NOT EXISTS mat_item_change (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,          -- das Journal nennt Anträge: nie wiederverwendet
      item_id          INTEGER NOT NULL REFERENCES mat_item(id),   -- kein CASCADE: ein Artikel mit Antrag bleibt
      field            TEXT NOT NULL CHECK (field IN """ + _in(ANTRAGSFELDER) + """),
      old_value        TEXT,                                       -- Wert beim Antrag (NULL: Herstelldatum leer)
      new_value        TEXT,                                       -- beantragter Wert (NULL: Herstelldatum entfernen)
      reason           TEXT NOT NULL CHECK (trim(reason) <> '' AND length(reason) <= 1000),
      status           TEXT NOT NULL DEFAULT 'offen' CHECK (status IN """ + _in(ANTRAGSSTATUS_15) + """),
      answer           TEXT NOT NULL DEFAULT '' CHECK (length(answer) <= 1000),  -- bei Ablehnung Pflicht
      created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name  TEXT NOT NULL CHECK (trim(created_by_name) <> ''),
      created_at       TEXT NOT NULL,                              -- UTC wie db.now()
      resolved_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
      resolved_by_name TEXT NOT NULL DEFAULT '',
      resolved_at      TEXT,
      applied_at       TEXT,                                       -- die bestätigte Änderung steht am Artikel
      CHECK (new_value IS NOT old_value),
      CHECK (field <> 'serial_no' OR (new_value IS NOT NULL AND trim(new_value) <> '')),
      CHECK ((status = 'offen') = (resolved_at IS NULL)),
      CHECK (status <> 'abgelehnt' OR trim(answer) <> ''),
      CHECK (applied_at IS NULL OR status = 'bestaetigt')
    )""",
    # Höchstens ein offener Antrag je Artikel und Feld.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mat_item_change_offen ON mat_item_change(item_id, field) WHERE status = 'offen'",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_change_item ON mat_item_change(item_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_change_status ON mat_item_change(status, created_at)",
    # Für ON DELETE SET NULL beim Kontolöschen und die Zahl im Dialog „Konto löschen“ (loeschung.folgen).
    "CREATE INDEX IF NOT EXISTS idx_mat_item_change_antragsteller ON mat_item_change(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_mat_item_change_entscheider ON mat_item_change(resolved_by)",
]
# Eine Änderung eines Feldes, die ein bestätigter, noch nicht angewendeter Antrag genau so deckt (alter und neuer Wert).
_ANTRAG_DECKT = ("EXISTS (SELECT 1 FROM mat_item_change c WHERE c.item_id = OLD.id AND c.field = '{0}' "
                 "AND c.status = 'bestaetigt' AND c.applied_at IS NULL AND c.old_value IS OLD.{0} "
                 "AND c.new_value IS NEW.{0})")
# Herstelldatum bei Metall nachtragen: vorher leer, jetzt ein Wert, das Produkt bleibt und ist aus Metall.
_NACHTRAGEN = ("(OLD.manufactured_on IS NULL AND NEW.manufactured_on IS NOT NULL AND NEW.product_id IS OLD.product_id "
               "AND (SELECT p.material_kind FROM mat_product p WHERE p.id = OLD.product_id) = 'metall_hardware')")
TRIGGER_15_ARTIKEL = [
    # Ersetzt den Trigger aus Schritt 14 (gleicher Name): fest seit der ersten abgeschlossenen Prüfung – außer für das
    # Nachtragen bei Metall und für die Änderung eines bestätigten Antrags.
    _trigger("mat_item_stammdaten_fest", "BEFORE UPDATE OF serial_no, manufactured_on ON mat_item",
             "((NEW.serial_no IS NOT OLD.serial_no AND NOT " + _ANTRAG_DECKT.format("serial_no") + ") "
             "OR (NEW.manufactured_on IS NOT OLD.manufactured_on AND NOT " + _NACHTRAGEN + " AND NOT "
             + _ANTRAG_DECKT.format("manufactured_on") + ")) "
             "AND EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = OLD.id AND x.completed_at IS NOT NULL)",
             STAMMDATEN_FEST),
    # Ein bestätigter Antrag wirkt genau einmal: Die Änderung, die er deckt, setzt in derselben Anweisung applied_at.
    "CREATE TRIGGER IF NOT EXISTS mat_item_antrag_angewendet AFTER UPDATE OF serial_no, manufactured_on ON mat_item "
    "WHEN NEW.serial_no IS NOT OLD.serial_no OR NEW.manufactured_on IS NOT OLD.manufactured_on "
    "BEGIN UPDATE mat_item_change SET applied_at = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now') "
    "WHERE item_id = NEW.id AND status = 'bestaetigt' AND applied_at IS NULL AND ("
    "(field = 'serial_no' AND NEW.serial_no IS NOT OLD.serial_no AND old_value IS OLD.serial_no "
    "AND new_value IS NEW.serial_no) OR (field = 'manufactured_on' AND NEW.manufactured_on IS NOT OLD.manufactured_on "
    "AND old_value IS OLD.manufactured_on AND new_value IS NEW.manufactured_on)); END",
]
TRIGGER_15_ANTRAG = [
    # Inhalt eines Antrags: nie ändern.
    _trigger("mat_item_change_inhalt", "BEFORE UPDATE OF id, item_id, field, old_value, new_value, reason, "
             "created_by_name, created_at ON mat_item_change", "1", ANTRAG_FEST),
    # Kontokennungen dürfen nur auf NULL gehen (Konto gelöscht, ON DELETE SET NULL) – die Namen bleiben.
    _trigger("mat_item_change_antragsteller", "BEFORE UPDATE OF created_by ON mat_item_change",
             "NEW.created_by IS NOT NULL AND NEW.created_by IS NOT OLD.created_by", ANTRAG_FEST),
    _trigger("mat_item_change_entscheider", "BEFORE UPDATE OF resolved_by ON mat_item_change",
             "OLD.status <> 'offen' AND NEW.resolved_by IS NOT NULL AND NEW.resolved_by IS NOT OLD.resolved_by",
             ANTRAG_FEST),
    # Entschieden wird einmal – danach steht es fest.
    _trigger("mat_item_change_entschieden", "BEFORE UPDATE OF status, answer, resolved_by_name, resolved_at "
             "ON mat_item_change", "OLD.status <> 'offen'", ANTRAG_FEST),
    # applied_at setzt nur mat_item_antrag_angewendet: einmal, nach der Bestätigung (nicht in derselben Anweisung).
    _trigger("mat_item_change_angewendet", "BEFORE UPDATE OF applied_at ON mat_item_change",
             "OLD.applied_at IS NOT NULL OR NEW.applied_at IS NULL OR OLD.status <> 'bestaetigt'", ANTRAG_FEST),
    _trigger("mat_item_change_loeschen", "BEFORE DELETE ON mat_item_change", "1", ANTRAG_FEST),
    # INSERT OR REPLACE löscht ohne Lösch-Trigger (recursive_triggers aus) – deshalb auch beim Einfügen prüfen.
    _trigger("mat_item_change_ersetzen", "BEFORE INSERT ON mat_item_change",
             "EXISTS (SELECT 1 FROM mat_item_change c WHERE c.id = NEW.id)", ANTRAG_FEST),
    # Ein Antrag entsteht immer offen – entschieden wird er nur per UPDATE (antrag.bestaetigen, antrag.ablehnen).
    _trigger("mat_item_change_neu", "BEFORE INSERT ON mat_item_change",
             "NEW.status <> 'offen' OR NEW.resolved_at IS NOT NULL OR NEW.resolved_by IS NOT NULL "
             "OR NEW.applied_at IS NOT NULL OR NEW.answer <> ''", ANTRAG_FEST),
]


def _schritt_15(conn):
    """Entscheidungen vom 21.10.2026: Änderungsanträge (mat_item_change) mit Triggern; der Trigger
    mat_item_stammdaten_fest aus Schritt 14 wird durch die Fassung mit den beiden Ausnahmen ersetzt (erst entfernen,
    dann neu anlegen – CREATE TRIGGER IF NOT EXISTS fände sonst die alte Fassung vor). Rein additiv; ein zweiter Lauf
    legt dieselben Trigger neu an und ändert keine Zeile."""
    for sql in SCHRITT_15:
        conn.execute(sql)
    conn.execute("DROP TRIGGER IF EXISTS mat_item_stammdaten_fest")
    for sql in TRIGGER_15_ARTIKEL + TRIGGER_15_ANTRAG:
        conn.execute(sql)


# --- Schritt 16 (Phase 3 · Lieferung 1, Prüfung der Änderungsanträge vom 21.10.2026): Umwege an der Sperre vorbei ----

PRODUKT_FEST = "'Das Produkt eines Artikels steht seit seiner ersten Prüfung fest.'"
MATERIALART_FEST = "'Die Materialart eines Produkts mit geprüften Artikeln steht fest.'"
ERSETZEN = "'Artikel und Produkte lassen sich nicht ersetzen und ihre Kennung nicht ändern.'"
_GEPRUEFT = "EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = OLD.id AND x.completed_at IS NOT NULL)"
# Befund 5, entschieden am 21.10.2026: Nachtragen bei Metall nur, solange der Artikel noch nie ein Herstelldatum hatte –
# nach der ersten Prüfung macht nur ein angewendeter Antrag mit vorhandenem altem Wert das Feld wieder leer.
_NACHTRAGEN_16 = ("(" + _NACHTRAGEN + " AND NOT EXISTS (SELECT 1 FROM mat_item_change c WHERE c.item_id = OLD.id "
                  "AND c.field = 'manufactured_on' AND c.applied_at IS NOT NULL AND c.old_value IS NOT NULL))")
TRIGGER_16_ARTIKEL = [
    # Ersetzt die Fassung aus Schritt 15 (gleicher Name) – nur das Nachtragen ist enger.
    _trigger("mat_item_stammdaten_fest", "BEFORE UPDATE OF serial_no, manufactured_on ON mat_item",
             "((NEW.serial_no IS NOT OLD.serial_no AND NOT " + _ANTRAG_DECKT.format("serial_no") + ") "
             "OR (NEW.manufactured_on IS NOT OLD.manufactured_on AND NOT " + _NACHTRAGEN_16 + " AND NOT "
             + _ANTRAG_DECKT.format("manufactured_on") + ")) "
             "AND EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = OLD.id AND x.completed_at IS NOT NULL)",
             STAMMDATEN_FEST),
]
TRIGGER_16 = [
    # INSERT OR REPLACE löscht ohne Lösch-Trigger (recursive_triggers aus) – deshalb auch beim Einfügen prüfen. Die App
    # legt Artikel nur neu an (bestand.artikel_anlegen, ohne Kennung).
    _trigger("mat_item_ersetzen", "BEFORE INSERT ON mat_item", "EXISTS (SELECT 1 FROM mat_item i WHERE i.id = NEW.id)",
             ERSETZEN),
    # Mit anderer Kennung hinge keine Prüfung mehr am Artikel – und er wäre nicht mehr fest. Die App ändert sie nie.
    _trigger("mat_item_kennung", "BEFORE UPDATE OF id ON mat_item", "NEW.id IS NOT OLD.id", ERSETZEN),
    # Einen geprüften Artikel löscht die App nie (bestand.artikel_loeschen: nur ohne Prüfung); mit Fremdschlüsseln
    # verhindert es schon mat_inspection.item_id, ohne sie ginge es samt Neuanlage unter derselben Kennung.
    _trigger("mat_item_geprueft_loeschen", "BEFORE DELETE ON mat_item", _GEPRUEFT,
             "'Ein geprüfter Artikel bleibt mit seinem Lebenslauf – aussondern statt löschen.'"),
    # Produktwechsel nach der ersten Prüfung – wie der Dienst (bestand.artikel_aendern, 409). Derselbe Wert geht durch:
    # artikel_aendern schreibt jede Spalte neu.
    _trigger("mat_item_produkt_fest", "BEFORE UPDATE OF product_id ON mat_item",
             "NEW.product_id IS NOT OLD.product_id AND " + _GEPRUEFT, PRODUKT_FEST),
    # Materialart: Der Dienst (katalog.produkt_aendern) sperrt sie schon, sobald es Artikel des Produkts gibt; die
    # Datenbank sperrt sie, sobald einer davon geprüft ist (daran hängen Nachtragen bei Metall und Lebensende).
    _trigger("mat_product_materialart_fest", "BEFORE UPDATE OF material_kind ON mat_product",
             "NEW.material_kind IS NOT OLD.material_kind AND EXISTS (SELECT 1 FROM mat_item i JOIN mat_inspection x "
             "ON x.item_id = i.id WHERE i.product_id = OLD.id AND x.completed_at IS NOT NULL)", MATERIALART_FEST),
    _trigger("mat_product_ersetzen", "BEFORE INSERT ON mat_product",
             "EXISTS (SELECT 1 FROM mat_product p WHERE p.id = NEW.id)", ERSETZEN),
    _trigger("mat_product_kennung", "BEFORE UPDATE OF id ON mat_product", "NEW.id IS NOT OLD.id", ERSETZEN),
]


def _schritt_16(conn):
    """Prüfung vom 21.10.2026: Trigger gegen die Umwege an mat_item_stammdaten_fest vorbei (INSERT OR REPLACE, Kennung,
    Löschen, Produktwechsel, Materialart) und mat_item_stammdaten_fest in der Fassung mit engerem Nachtragen (erst
    entfernen, dann neu anlegen – CREATE TRIGGER IF NOT EXISTS fände sonst die alte Fassung vor). Rein additiv; ein
    zweiter Lauf legt dieselben Trigger neu an und ändert keine Zeile."""
    conn.execute("DROP TRIGGER IF EXISTS mat_item_stammdaten_fest")
    for sql in TRIGGER_16_ARTIKEL + TRIGGER_16:
        conn.execute(sql)


# --- Schritt 17 (Phase 3 · Lieferung 1, Entscheidungen vom 21.10.2026 zur Prüfung): zurückziehen, nicht entfernen -----

HERSTELLUNG_BLEIBT = "'Ein Herstelldatum lässt sich nach der ersten Prüfung nicht entfernen – nur auf Antrag ändern.'"
NUR_ANTRAGSTELLER = "'Einen offenen Änderungsantrag zieht nur der Antragsteller selbst zurück.'"
# Die Tabelle aus Schritt 15, nur mit dem Stand „zurückgezogen“ im CHECK (und dem Kommentar zu new_value).
_ANTRAG_TABELLE_15 = SCHRITT_15[0]
ANTRAG_TABELLE_17 = (_ANTRAG_TABELLE_15
                     .replace("CREATE TABLE IF NOT EXISTS mat_item_change (", "CREATE TABLE {name} (", 1)
                     .replace("CHECK (status IN " + _in(ANTRAGSSTATUS_15) + ")", "CHECK (status IN " + _in(ANTRAGSSTATUS) + ")", 1)
                     .replace("-- beantragter Wert (NULL: Herstelldatum entfernen)",
                              "-- beantragter Wert (NULL nur in Anträgen bis Schritt 16: Herstelldatum entfernen)", 1))
ANTRAG_INDIZES = SCHRITT_15[1:]
TRIGGER_17_ARTIKEL = [
    # Ersetzt die Fassung aus Schritt 16 (gleicher Name): Das Herstelldatum wird nach der ersten Prüfung nie mehr leer –
    # nachtragen (Metall, wie Schritt 16) und ändern per bestätigtem Antrag gehen nur auf einen Wert.
    _trigger("mat_item_stammdaten_fest", "BEFORE UPDATE OF serial_no, manufactured_on ON mat_item",
             "((NEW.serial_no IS NOT OLD.serial_no AND NOT " + _ANTRAG_DECKT.format("serial_no") + ") "
             "OR (NEW.manufactured_on IS NOT OLD.manufactured_on AND (NEW.manufactured_on IS NULL OR (NOT "
             + _NACHTRAGEN_16 + " AND NOT " + _ANTRAG_DECKT.format("manufactured_on") + ")))) "
             "AND EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = OLD.id AND x.completed_at IS NOT NULL)",
             STAMMDATEN_FEST),
    TRIGGER_15_ARTIKEL[1],                          # mat_item_antrag_angewendet, unverändert
]
TRIGGER_17 = [
    # Kein Antrag mehr, der das Herstelldatum entfernt (Entscheidung vom 21.10.2026) …
    _trigger("mat_item_change_herstellung_leer", "BEFORE INSERT ON mat_item_change",
             "NEW.field = 'manufactured_on' AND (NEW.new_value IS NULL OR trim(NEW.new_value) = '')", HERSTELLUNG_BLEIBT),
    # … und ein alter offener (bis Schritt 16 gestellt) lässt sich nicht mehr bestätigen – nur ablehnen oder zurückziehen.
    _trigger("mat_item_change_entfernen_bestaetigen", "BEFORE UPDATE OF status ON mat_item_change",
             "OLD.status = 'offen' AND NEW.status = 'bestaetigt' AND OLD.field = 'manufactured_on' "
             "AND OLD.new_value IS NULL", HERSTELLUNG_BLEIBT),
    # Zurückziehen: nur der Antragsteller (Kennung), ohne Antwort; danach steht der Antrag fest wie ein entschiedener
    # (mat_item_change_entschieden). Nur beim Übergang aus „offen“ – ON DELETE SET NULL setzt später beide Kennungen.
    _trigger("mat_item_change_zurueckziehen", "BEFORE UPDATE OF status, resolved_by, answer ON mat_item_change",
             "OLD.status = 'offen' AND NEW.status = 'zurueckgezogen' AND (NEW.resolved_by IS NULL "
             "OR NEW.resolved_by IS NOT OLD.created_by OR NEW.answer <> '')", NUR_ANTRAGSTELLER),
]


def _schritt_17(conn):
    """Entscheidungen vom 21.10.2026 zur Prüfung der Anträge: mat_item_change mit dem Stand „zurückgezogen“ neu aufbauen
    (nur, wenn ihr CHECK ihn noch nicht kennt – alle Zeilen, Kennungen und der AUTOINCREMENT-Stand bleiben) und die
    Trigger anlegen. Die beiden Artikeltrigger, die mat_item_change lesen, werden vorher entfernt (beim Umbau fehlt die
    Tabelle kurz) und danach neu angelegt – mat_item_stammdaten_fest in der Fassung ohne Entfernen. Ein zweiter Lauf
    baut nichts um und ändert keine Zeile."""
    conn.execute("DROP TRIGGER IF EXISTS mat_item_stammdaten_fest")
    conn.execute("DROP TRIGGER IF EXISTS mat_item_antrag_angewendet")
    tabelle = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'mat_item_change'").fetchone()
    if "'zurueckgezogen'" not in tabelle[0]:
        stand = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'").fetchone()
        _umbauen(conn, "mat_item_change", ANTRAG_TABELLE_17, ANTRAG_INDIZES, "item_change")
        if stand:
            conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'mat_item_change'", (stand[0],))
    for sql in TRIGGER_15_ANTRAG + TRIGGER_17 + TRIGGER_17_ARTIKEL:
        conn.execute(sql)


# --- Schritt 18 (22.10.2026): Herstellerdokumente einmal je Inhalt -----------------------------------------------------
# Eine Dokumentdatei heißt nach ihrem Inhalt und gehört allen Zeilen, die sie nennen (katalog._datei_ablegen,
# _datei_freigeben). Der Index trägt die Auslieferung (medien.darf_datei: WHERE file_path = ?) und das Freigeben; das
# Kennzeichen „0“ sagt services/dokablage.beim_start, dass der Altbestand noch zusammenzuführen ist – es setzt „1“, sobald
# das mit erreichbaren Medien einmal durchgelaufen ist. Beides wiederholbar; die Dateiarbeit steht bewusst nicht hier
# (siehe Modulbeschreibung).
SCHRITT_18 = [
    "CREATE INDEX IF NOT EXISTS idx_mat_document_file ON mat_product_document(file_path)",
    "INSERT OR IGNORE INTO mat_meta (schluessel, wert) VALUES ('dok_inhalt', '0')",
]


# --- Schritt 19 (Phase 4 · Lieferung 1): Mailfehler-Protokoll und Indizes für den Jahresbericht ----------------------
# Je gescheiterter Modul-Mail eine Zeile (services/mailprotokoll.senden) – Erfolge stehen nicht hier (Erinnerungen im
# Erinnerungslog, Rückrufe zählen in mat_recall). Der Empfänger steht als Kontoverweis (users.mat_ref) und Rolle da, nie
# mit Adresse; die Serverantwort kommt gereinigt (Adressen und Mailserver ersetzt) – der CHECK auf „@“ ist das Netz
# dahinter. folder_id ist die Gliederung, deren Verwalter die Zeile sehen; der Fremdschlüssel setzt sie beim Löschen des
# Ordners auf NULL, weil mat_folder Kennungen wiedervergibt. Nur erledigt_at und erledigt_von_name sind änderbar.
MAILARTEN = ("erinnerung", "mangel", "antrag", "meldung", "rueckruf")
MAILKLASSEN = ("empfaenger_abgewiesen", "verbindung", "anmeldung", "abgelehnt", "ausnahme", "sonstiges")
MAILBEZUEGE = ("item", "folder", "report", "change", "request", "recall", "none")
MAILROLLEN = ("verwalter", "pruefer", "zugeordnet", "inhaber", "verwaltung", "antragsteller", "melder")
MAILBETREFF_MAX, MAILMELDUNG_MAX = 160, 300
MAILFEHLER_FEST = "'Eine Mailfehler-Zeile lässt sich nur abhaken, nicht ändern.'"
SCHRITT_19 = [
    """CREATE TABLE IF NOT EXISTS mat_mail_fehler (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      art               TEXT NOT NULL CHECK (art IN """ + _in(MAILARTEN) + """),
      klasse            TEXT NOT NULL CHECK (klasse IN """ + _in(MAILKLASSEN) + """),
      bezug_art         TEXT NOT NULL CHECK (bezug_art IN """ + _in(MAILBEZUEGE) + """),
      bezug_id          INTEGER,                                   -- Kennung im Ziel, das selbst prüft (404)
      folder_id         INTEGER REFERENCES mat_folder(id) ON DELETE SET NULL,   -- Gliederung (Sicht der Verwalter)
      konto_ref         TEXT NOT NULL CHECK (konto_ref <> ''),     -- users.mat_ref des Empfängers, nie die Adresse
      rolle             TEXT NOT NULL CHECK (rolle IN """ + _in(MAILROLLEN) + """),
      betreff           TEXT NOT NULL CHECK (length(betreff) <= """ + str(MAILBETREFF_MAX) + """),
      meldung           TEXT NOT NULL CHECK (length(meldung) <= """ + str(MAILMELDUNG_MAX) + """
                                              AND instr(meldung, '@') = 0),
      created_at        TEXT NOT NULL,                             -- UTC wie db.now()
      erledigt_at       TEXT,
      erledigt_von_name TEXT,                                      -- Handelnder (Löschkonzept) bzw. „nachgeholt“
      CHECK ((erledigt_at IS NULL) = (erledigt_von_name IS NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_mat_mail_fehler_offen ON mat_mail_fehler(erledigt_at, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_mat_mail_fehler_ordner ON mat_mail_fehler(folder_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_mail_fehler_konto ON mat_mail_fehler(konto_ref)",
    _trigger("mat_mail_fehler_fest", "BEFORE UPDATE OF id, art, klasse, bezug_art, bezug_id, konto_ref, rolle, betreff, "
             "meldung, created_at ON mat_mail_fehler", "1", MAILFEHLER_FEST),
    # Die Gliederung darf nur auf NULL gehen (Ordner gelöscht, ON DELETE SET NULL).
    _trigger("mat_mail_fehler_ordner", "BEFORE UPDATE OF folder_id ON mat_mail_fehler",
             "NEW.folder_id IS NOT NULL AND NEW.folder_id IS NOT OLD.folder_id", MAILFEHLER_FEST),
    # Jahresbericht (services/bericht.py): Prüfungen je Jahr und Journalzeilen je Art und Zeitraum.
    "CREATE INDEX IF NOT EXISTS idx_mat_inspection_inspected_on ON mat_inspection(inspected_on)",
    "CREATE INDEX IF NOT EXISTS idx_mat_audit_entity_action ON mat_audit(entity, action, created_at)",
]


# Je Version die Schritte, die von der Vorversion dorthin führen: eine Liste von SQL-Befehlen (für sich
# wiederholbar, IF NOT EXISTS) oder eine Funktion. Alle Schritte eines Starts laufen in EINER
# Transaktion – bricht einer ab, bleibt die Datenbank, wie sie war, und der nächste Start versucht es neu.
SCHRITTE = {1: SCHRITT_1, 2: _schritt_2, 3: _schritt_3, 4: SCHRITT_4, 5: _schritt_5, 6: _schritt_6, 7: _schritt_7,
            8: _schritt_8, 9: _schritt_9, 10: _schritt_10, 11: _schritt_11, 12: _schritt_12, 13: _schritt_13,
            14: _schritt_14, 15: _schritt_15, 16: _schritt_16, 17: _schritt_17, 18: SCHRITT_18, 19: SCHRITT_19}


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
