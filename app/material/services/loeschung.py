"""Löschkonzept (Phase 2 · Lieferung 1, Abschnitt 7): was das Löschen eines Kontos im Modul Material bewirkt.

Grundsatz – im Verfahrensverzeichnis als Pseudonymisierung, nicht als Anonymisierung:
  - Handelnde bleiben namentlich, wo die Aufzeichnung es verlangt oder als Nachweis dient: Prüfer mit Name,
    Urkundennummer, Unterschrift und Anmeldung in abgeschlossenen und festgeschriebenen Prüfungen und ihren PDFs
    (EN 365), wer eröffnet, ausnimmt, abschließt, aussondert, anlegt, ändert (*_name, mat_audit.user_name). Diese
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
                     Kennung setzt die Datenbank auf NULL, der Materialwart gibt die Reservierung frei
  Produktmeldungen   Name des Melders und des Bearbeiters „(gelöschtes Konto)“
  Suchprotokoll      Name „(gelöschtes Konto)“ (nach zwölf Monaten ohnehin weg)
Abgeschlossene Prüfungen, Durchgänge, Ausnahmen, Anhänge, Rückrufe und das Journal bleiben, wie sie sind. Deaktivieren
ändert im Modul nichts: Freigaben wirken nicht mehr (current_user verlangt ein aktives Konto), Zuordnungen bleiben und
erscheinen mit „(deaktiviert)“. Ablauf beim Austritt: PSA zurücknehmen (Zuordnung lösen), Konto deaktivieren, nach
Klärung offener Prüfungen löschen. Die Stufe im Modul Material steht am Konto und geht mit ihm; die Einträge „rollen“
am Konto (Nutzerverwaltung, Profil, „Migration Schritt 10“) bleiben unter der Kontokennung stehen wie bisher.

Prüfnachweise werden unbefristet aufbewahrt, auch nach der Aussonderung (Entscheidung des Betreibers vom 18.10.2026):
abgeschlossene und festgeschriebene Prüfungen samt Befunden, Befundfotos und Anhängen, Aussonderungen, Prüf-,
Aussonderungs- und Sammelprotokolle (DATA_DIR/pdf), Durchgänge mit Geprüftem, das Journal und die Dokumente, die ein
Protokoll nennt. Es gibt keine Löschfrist und keine Löschroutine. In der Datenbank lehnen Trigger und Fremdschlüssel
(models.py) jedes Löschen ab; die Dienste prüfen vorher selbst (Artikel, Ordner, Durchgang, Kategorie) und entfernen
Dateien nur zu offenen Entwürfen – die dürfen verworfen werden, sie sind kein Nachweis
(test_material_zuordnung.test_pruefnachweise_bleiben)."""
from ... import db
from . import bestand, journal

GELOESCHT = "(gelöschtes Konto)"            # wie journal.konto_name für einen Verweis ohne Konto
GRUND = "Konto gelöscht"


def folgen(uid):
    """Was das Löschen des Kontos im Modul Material bewirkt – Zahlen für den Dialog der Nutzerverwaltung: Freigaben
    (werden entfernt, auch abgelaufene), Zuordnungen (werden gelöst), offene Entwürfe (werden Reservierungen ohne
    Prüfer) und abgeschlossene Prüfungen (behalten den Namen)."""
    def zahl(sql):
        return db.query(sql, (uid,), one=True)["n"]
    return {"freigaben": zahl("SELECT COUNT(*) AS n FROM mat_folder_grant WHERE user_id = ?"),
            "zuordnungen": zahl("SELECT COUNT(*) AS n FROM mat_item WHERE assigned_user_id = ?"),
            "entwuerfe": zahl("SELECT COUNT(*) AS n FROM mat_inspection WHERE inspector_user_id = ? "
                              "AND completed_at IS NULL"),
            "pruefungen": zahl("SELECT COUNT(*) AS n FROM mat_inspection WHERE inspector_user_id = ? "
                               "AND completed_at IS NOT NULL")}


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
    return zahlen
