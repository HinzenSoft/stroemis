"""Löschkonzept (Phase 2 · Lieferung 1, Abschnitt 7): was das Löschen eines Kontos in der Materialablage bewirkt.

Grundsatz – im Verfahrensverzeichnis als Pseudonymisierung, nicht als Anonymisierung:
  - Handelnde bleiben namentlich, wo die Aufzeichnung es verlangt oder als Nachweis dient: Prüfer mit Name,
    Urkundennummer, Unterschrift und Anmeldung in abgeschlossenen und festgeschriebenen Prüfungen und ihren PDFs
    (EN 365), wer eröffnet, ausnimmt, abschließt, aussondert, anlegt, ändert, wer einen Mangel meldet (*_name,
    mat_audit.user_name, mat_defect_report.reporter_name – Entscheidung F3 vom 20.10.2026). Diese
    Zeilen sind per Trigger unveränderlich; die Kontokennung darin setzt die Datenbank beim Löschen auf NULL.
  - Betroffene stehen nur pseudonym im Journal: Freigaben und Zuordnungen tragen {"ref": users.mat_ref}. Mit der
    Kontozeile verschwindet mat_ref – danach führt von keinem Verweis mehr etwas zur Person. Aus dem Zusammenhang
    (Zeitpunkt, wer gleichzeitig handelte) bleibt ein Rückschluss möglich; deshalb Pseudonymisierung.
  - Arbeitsdaten ohne Nachweiszweck werden beim Löschen anonymisiert oder gelöscht.

Was konto_loeschen_vorbereiten tut – in der Transaktion von api_admin.delete_user, vor DELETE FROM users; bricht etwas
ab, bleibt das Konto samt allem stehen:
  Freigaben          je Zeile „freigabe_entfernt“ im Journal des Ordners (grund „Konto gelöscht“), die Zeilen nimmt
                     danach die Datenbank mit (ON DELETE CASCADE)
  Zuordnungen        je Artikel „zuordnung_geloest“ (grund „Konto gelöscht“), dann gelöst
  offene Entwürfe    Prüfername „(gelöschtes Konto)“ und Urkundennummer leer – ein Entwurf ist kein Nachweis; die
                     Kennung setzt die Datenbank auf NULL, der Materialwart hebt die Reservierung auf
  Set-Prüfungen      (bis Schritt 26, nur noch beendete): Name des Eröffners bleibt (Prüfnachweis, per Trigger
                     unveränderlich); die Kennung setzt die Datenbank auf NULL
  Produktmeldungen   Name des Melders und des Bearbeiters „(gelöschtes Konto)“
  Bestandsimporte    Name dessen, der importiert hat (mat_import), und dessen, der eine Zeile der Nacharbeit erledigt
                     hat (mat_import_row), „(gelöschtes Konto)“ – Arbeitsdaten; der Nachweis steht im Journal
  Suchprotokoll      Name „(gelöschtes Konto)“ (nach zwölf Monaten ohnehin weg)
  Erinnerungslog     Zeilen des Kontos gelöscht (sonst nach 13 Monaten weg; kein Prüfnachweis) – auch die aus dem
                     Abschnitt „Deine PSA“
  Mailfehler         Zeilen des Kontos gelöscht (mat_mail_fehler, Phase 4 · L1: gescheiterte Modul-Mails mit Kontoverweis,
                     Rolle, Betreff und gereinigter Serverantwort – Arbeitsdaten, sonst nach 13 Monaten weg, erledigte
                     nach 3 Monaten; kein Prüfnachweis)
  Mangelmeldungen    nichts; die Kennung setzt die Datenbank auf NULL, der Name bleibt (Handelnder, F3) – unbefristet
                     mit dem Artikel; users.mat_psa_mails geht mit der Kontozeile
  Änderungsanträge   nichts; Antragsteller und Entscheider sind Handelnde an festen Stammdaten (Prüfnachweis): Die
                     Kennungen setzt die Datenbank auf NULL, die Namen bleiben – unbefristet mit dem Artikel, wie die
                     Mangelmeldungen (anders als Produktmeldungen, die Arbeitsdaten des Katalogs sind und
                     „(gelöschtes Konto)“ bekommen; Entscheidung vom 21.10.2026, Bitte bestätigen)
Abgeschlossene Prüfungen, Durchgänge, Ausnahmen, Anhänge, Rückrufe und das Journal bleiben, wie sie sind (auch die
Freitext-Bemerkungen früherer Set-Einträge, bis Schritt 26). Deaktivieren
ändert im Modul nichts: Freigaben wirken nicht mehr (current_user verlangt ein aktives Konto), Zuordnungen bleiben und
erscheinen mit „(deaktiviert)“. Ablauf beim Austritt: PSA zurücknehmen (Zuordnung lösen), Konto deaktivieren, nach
Klärung offener Prüfungen löschen. Die Stufe in der Materialablage steht am Konto und geht mit ihm; die Einträge „rollen“
am Konto (Nutzerverwaltung, Profil, „Migration Schritt 10“) bleiben unter der Kontokennung stehen wie bisher.

Prüfnachweise werden unbefristet aufbewahrt, auch nach der Aussonderung (Entscheidung des Betreibers vom 18.10.2026):
abgeschlossene und festgeschriebene Prüfungen samt Befunden, Befundfotos und Anhängen, Aussonderungen, Prüf-,
Aussonderungs- und Sammelprotokolle (DATA_DIR/pdf), Durchgänge mit Geprüftem, das Journal und die Dokumente, die ein
Protokoll nennt. Es gibt keine Löschfrist und keine Löschroutine. In der Datenbank lehnen Trigger und Fremdschlüssel
(models.py) jedes Löschen ab; die Dienste prüfen vorher selbst (Artikel, Ordner, Durchgang, Kategorie) und entfernen
Dateien nur zu offenen Entwürfen – die dürfen verworfen werden, sie sind kein Nachweis
(test_material_zuordnung.test_pruefnachweise_bleiben)."""
from ... import db
from . import bestand, erinnerung, journal, mailprotokoll

GELOESCHT = "(gelöschtes Konto)"            # wie journal.konto_name für einen Verweis ohne Konto
GRUND = "Konto gelöscht"


def folgen(uid):
    """Was das Löschen des Kontos in der Materialablage bewirkt – Zahlen für den Dialog der Nutzerverwaltung: Freigaben
    (werden entfernt, auch abgelaufene), Zuordnungen (werden gelöst), offene Entwürfe (werden Reservierungen ohne
    Prüfer), abgeschlossene Prüfungen, Mangelmeldungen und Änderungsanträge (gestellt oder entschieden; behalten den
    Namen)."""
    def zahl(sql):
        return db.query(sql, (uid,), one=True)["n"]
    return {"freigaben": zahl("SELECT COUNT(*) AS n FROM mat_folder_grant WHERE user_id = ?"),
            "zuordnungen": zahl("SELECT COUNT(*) AS n FROM mat_item WHERE assigned_user_id = ?"),
            "entwuerfe": zahl("SELECT COUNT(*) AS n FROM mat_inspection WHERE inspector_user_id = ? "
                              "AND completed_at IS NULL"),
            "pruefungen": zahl("SELECT COUNT(*) AS n FROM mat_inspection WHERE inspector_user_id = ? "
                               "AND completed_at IS NOT NULL"),
            "maengel": zahl("SELECT COUNT(*) AS n FROM mat_defect_report WHERE reporter_id = ?"),
            # Sammelanträge zählen einmal (Kopf und Folgezeilen – Prüfung Sicherheit, Befund 5).
            "antraege": db.query("SELECT COUNT(DISTINCT COALESCE(group_id, id)) AS n FROM mat_item_change "
                                 "WHERE created_by = ? OR resolved_by = ?", (uid, uid), one=True)["n"]}


def konto_loeschen_vorbereiten(uid):
    """Aufräumen vor DELETE FROM users – nur innerhalb der Transaktion, die das Konto löscht (api_admin.delete_user).
    Der Kontoverweis wird hier ein letztes Mal geschrieben; mit der Kontozeile ist er danach unauflösbar. Liefert
    folgen() von vor dem Aufräumen."""
    zahlen = folgen(uid)
    for f in db.query("SELECT * FROM mat_folder_grant WHERE user_id = ? ORDER BY id", (uid,)):
        # Dieselbe Gestalt wie beim Löschen eines Ordners: vorher die Freigabe, nachher der Grund.
        journal.eintragen("folder", f["folder_id"], "freigabe_entfernt", bestand.freigabe_journal(f), {"grund": GRUND})
    ref = journal.konto_ref(uid) if zahlen["zuordnungen"] else None
    for i in db.query("SELECT id FROM mat_item WHERE assigned_user_id = ? ORDER BY id", (uid,)):
        journal.eintragen("item", i["id"], "zuordnung_geloest", None, {"konto": ref, "grund": GRUND})
    db.execute("UPDATE mat_item SET assigned_user_id = NULL, updated_at = ? WHERE assigned_user_id = ?", (db.now(), uid))
    db.execute("UPDATE mat_inspection SET inspector_name = ?, inspector_certificate = '' WHERE inspector_user_id = ? "
               "AND completed_at IS NULL", (GELOESCHT, uid))
    db.execute("UPDATE mat_product_request SET created_by_name = ? WHERE created_by = ?", (GELOESCHT, uid))
    db.execute("UPDATE mat_product_request SET resolved_by_name = ? WHERE resolved_by = ?", (GELOESCHT, uid))
    db.execute("UPDATE mat_global_search SET user_name = ? WHERE user_id = ?", (GELOESCHT, uid))
    db.execute("UPDATE mat_import SET created_by_name = ? WHERE created_by = ?", (GELOESCHT, uid))
    db.execute("UPDATE mat_import_row SET resolved_by_name = ? WHERE resolved_by = ?", (GELOESCHT, uid))
    erinnerung.konto_loeschen(uid)                  # vor dem Löschen der Kontozeile: der Verweis geht über mat_ref
    mailprotokoll.konto_loeschen(uid)
    return zahlen
