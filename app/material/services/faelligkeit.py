"""Fälligkeiten nachziehen, wenn das wirksame Prüfintervall kürzer wird.

Wird das Intervall kürzer (anderes Produkt, kürzere Vorgabe an Artikel, Ordner, Produkt oder Kategorie,
Verschieben in einen strengeren Ordner), gilt als Grenze „letzte Prüfung + neues Intervall“ – ohne Prüfung
„heute + neues Intervall“ wie beim Anlegen. Eine Fälligkeit dahinter wird auf die Grenze vorgezogen und
im Journal des Artikels vermerkt; liegt die Grenze schon zurück, ist der Artikel damit überfällig. Nach
hinten schiebt diese Regel nie etwas – später setzt eine Fälligkeit nur eine Prüfung.

Ausgesonderte Artikel bleiben, wie sie sind; eine fehlende Fälligkeit bleibt fehlend (der Artikel ist
damit überfällig – ein Lückenfüller würde ihn ohne Prüfung einsatzbereit machen)."""
from datetime import date

from ... import db
from . import journal
from .interval import plus_monate, spaetestens, wirksam


def kappen(bedingung, args=(), zusatz=None):
    """Fälligkeiten der Artikel, auf die die SQL-Bedingung (über i = mat_item, p = mat_product) passt,
    auf letzte Prüfung (ohne Prüfung: heute) + wirksames Intervall begrenzen. Liefert die Zahl der
    vorgezogenen Artikel. Läuft in der Transaktion des Aufrufers mit. zusatz: weitere Angaben im Journaleintrag – beim
    bestätigten Antrag {"antrag": Nr.}, damit Leser dort den Entscheider nicht sehen (antrag.journal_verbergen)."""
    zeilen = db.query(
        "SELECT i.id, i.folder_id, i.origin_folder_id, i.lock_state, i.next_due_on, i.last_inspected_on, "
        "i.interval_months AS i_int, p.interval_months AS p_int, "
        "p.category_id FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
        f"WHERE i.lock_state <> 'ausgesondert' AND i.next_due_on IS NOT NULL AND ({bedingung})", args)
    from .bestand import heimat
    vorgezogen = 0
    for z in zeilen:
        # Gesperrte liegen in „Gesperrt“; ihr Intervall kommt aus der Heimat (wie bei der Prüfung).
        iv = wirksam({"interval_months": z["p_int"], "category_id": z["category_id"]}, heimat(z), z["i_int"])
        if not iv["monate"]:
            continue
        if z["last_inspected_on"]:
            grenze = plus_monate(date.fromisoformat(z["last_inspected_on"]), iv["monate"]).isoformat()
            grund = f"kürzeres Prüfintervall ({iv['monate']} Monate, {iv['quelle']}) ab der letzten Prüfung"
        else:
            grenze = spaetestens(iv["monate"])
            grund = f"kürzeres Prüfintervall ({iv['monate']} Monate, {iv['quelle']})"
        if grenze and z["next_due_on"] > grenze:
            db.execute("UPDATE mat_item SET next_due_on = ?, updated_at = ? WHERE id = ?", (grenze, db.now(), z["id"]))
            journal.eintragen("item", z["id"], "faelligkeit", {"next_due_on": z["next_due_on"]},
                              dict({"next_due_on": grenze, "grund": grund}, **(zusatz or {})))
            vorgezogen += 1
    return vorgezogen


def im_unterbaum(ordner_id):
    """Bedingung für alle Artikel in einem Ordner und seinen Unterordnern."""
    return ("i.folder_id IN (WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f "
            "JOIN baum b ON f.parent_id = b.id) SELECT id FROM baum)", (ordner_id,))


def in_kategorie(kategorie_id):
    """Bedingung für alle Artikel, deren Produkt in der Kategorie oder einer Unterkategorie steht."""
    return ("p.category_id IN (WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT c.id FROM mat_category c "
            "JOIN baum b ON c.parent_id = b.id) SELECT id FROM baum)", (kategorie_id,))
