"""Lesbare Beschriftungen des Journals für PDF und Export – das Python-Gegenstück zu FELD, AKTION, ENTITAET und
wert() in static/material.js. Wer dort eine Beschriftung ergänzt, ergänzt sie hier auch: Oberfläche und
Lebenslauf-PDF sollen dasselbe Wort für dasselbe Feld benutzen.

Was hier nicht steht, erscheint mit seinem technischen Namen – wie in der Oberfläche.

Betroffene stehen im Journal nur als Kontoverweis („konto“, Phase 2); das PDF nennt sie nie – nicht einmal den Namen,
den journal.lesen beim Lesen auflöst: Dort steht „(Person)“. Der Lebenslauf geht weiter, an wen er auch geht. Ebenso
steht bei „Mangel gemeldet“ als Handelnder „(Person)“ – der Melder kann die zugeordnete Person sein (Phase 3 · L1)."""
import json

from ..models import ANHANGARTEN, ERGEBNISSE, MATERIALARTEN, ORDNERARTEN, PRUEFARTEN
from . import laenge_text
from .protokoll import datum_text, zeit_text

FELD = {
    "manufacturer": "Hersteller", "model": "Modell", "article_no": "Artikelnummer", "norm": "Norm",
    "material_kind": "Materialart", "interval_months": "Prüfintervall (Monate)", "lifetime_years": "Lebensdauer (Jahre)",
    "lifetime_source": "Fundstelle Lebensdauer", "description": "Beschreibung", "category_id": "Kategorie", "image": "Bild",
    "serial_no": "Seriennummer", "serial_generated": "Seriennummer vom System", "inventory_no": "Inventarnummer",
    "manufactured_on": "Herstellung", "purchased_on": "Kauf", "first_use_on": "Erstgebrauch", "retire_by": "Lebensende",
    "next_due_on": "Nächste Prüfung", "notes": "Bemerkung", "folder_id": "Ordner", "ordner": "Ordner",
    "product_id": "Produkt", "name": "Name", "kind": "Art", "parent_id": "Oberordner", "pfad": "Ablage", "photo": "Foto",
    "title": "Titel", "version": "Version", "valid_from": "Gültig ab", "withdrawn_on": "Zurückgezogen ab",
    "active": "Aktiv", "punkte": "Prüfpunkte", "default_material_kind": "Materialart (Vorgabe)",
    "default_interval_months": "Prüfintervall (Vorgabe)", "default_lifetime_years": "Lebensdauer (Vorgabe)",
    "recht_material": "Stufe Material", "mat_pruefer": "Prüfer", "mat_katalog": "Katalogpfleger",
    "urkundennummer": "Urkundennummer", "system_kind": "Systemordner", "url": "Adresse", "file_path": "Datei",
    "sha256": "SHA-256", "size": "Größe", "lock_state": "Sperrzustand", "lock_reason": "Grund der Sperre",
    "origin_folder_id": "Herkunftsordner", "herkunft": "Herkunftsordner", "last_inspected_on": "Zuletzt geprüft",
    "pruefung": "Prüfung", "ergebnis": "Ergebnis", "art": "Art", "grund": "Grund", "datum": "Datum",
    "aussonderung": "Aussonderung", "pruefer": "Prüfer", "result": "Ergebnis", "inspected_on": "Prüftag",
    "reason": "Grund", "maengel": "Mängel", "item_id": "Artikel Nr.", "round_id": "Durchgang Nr.",
    "form_id": "Formular Nr.", "form_version": "Formularversion", "inspector_name": "Prüfer", "begonnen": "begonnen",
    "seiten": "Seiten", "dateien": "Dateien", "basis": "aus Prüfung", "erledigt": "erledigt",
    "ausgenommen": "ausgenommen", "links": "Links", "fotos": "Fotos", "note": "Bemerkung", "answer": "Antwort",
    "status": "Status", "von": "Kopie von Produkt Nr.", "kopie_von": "Kopie von Dokument Nr.",
    "dokumente": "Dokumente übernommen", "protocol_id": "Protokoll-ID", "pdf_sha256": "Prüfsumme",
    "pdf_hashed_bytes": "Bytes", "file_sha256": "Prüfsumme der Datei", "anhaenge_angefuegt": "Anhänge angefügt",
    "login": "Anmeldung", "berichtigung": "Berichtigung", "berichtigt": "berichtigt", "unterschrift": "Unterschrift",
    "nicht_geprueft": "nicht geprüft", "uid": "Katalogkennung", "rueckruf": "Rückruf Nr.", "serials": "Seriennummern",
    "mail": "Mail an Materialwarte und Prüfer", "close_note": "Vermerk",
    # Phase 2: Freigaben je Ordner und Personenzuordnung
    "freigabe": "Freigabe Nr.", "konto": "Person", "recht": "Recht", "bis": "bis", "notiz_geaendert": "Notiz geändert",
    # Phase 2 · Lieferung 2: Erinnerungen
    "reminders_off": "Erinnerungsmails aus",
    # Phase 2 · Lieferung 3: Bestandsimport und Prüfanleitung aus dem Wiki
    "bestandsimport": "Bestandsimport Nr.", "datei": "Datei", "zeile": "Zeile", "zeilen": "Zeilen",
    "artikel_angelegt": "Artikel angelegt", "schon_im_bestand": "schon im Bestand", "nacharbeit": "Nacharbeit (Zeilen)",
    "ersetzt": "neu eingelesen (Zeilen)", "aus_nacharbeit": "aus der Nacharbeit",
    "liste_inventarnummer": "bisherige Inventarnummer", "liste_zuletzt_geprueft": "zuletzt geprüft laut Liste",
    "liste_naechste_pruefung": "nächste Prüfung laut Liste", "seite": "Wiki-Seite Nr.",
    # Phase 3 · Lieferung 1: Mangelmeldung
    "mangel": "Mangelmeldung Nr.",
    # Änderungsanträge an festen Stammdaten (Entscheidungen vom 21.10.2026)
    "antrag": "Änderungsantrag Nr.", "begruendung": "Begründung", "beantragt_von": "beantragt von",
    "anmerkung": "Anmerkung", "ablehnung": "Begründung der Ablehnung", "feld": "Feld",
    "rueckruf_nicht_mehr": "Rückruf trifft ihn nicht mehr", "rueckruf_neu": "Rückruf trifft ihn jetzt",
    # Artikellänge (Schritt 20)
    "length_m": "Länge (m)", "items_have_length": "Artikel haben eine Länge",
    # Hersteller-Sets (Schritt 21)
    "is_set": "Hersteller-Set", "bestandteile": "Bestandteile", "teile": "Teile", "set": "Set Nr.",
    "set_inventar": "Set", "stueckliste": "Stückliste übernommen",
}
AKTION = {
    "angelegt": "angelegt", "geaendert": "geändert", "geloescht": "gelöscht", "verschoben": "verschoben",
    "bild": "Bild geändert", "foto": "Foto geändert", "neue_version": "neue Version", "zurueckgezogen": "zurückgezogen",
    "aktiviert": "aktiviert", "deaktiviert": "deaktiviert", "lebensende": "Lebensende nachgezogen", "rollen": "Rollen",
    "begonnen": "Prüfung begonnen", "abgeschlossen": "Prüfung abgeschlossen", "verworfen": "Prüfung verworfen",
    "reservierung_freigegeben": "Reservierung aufgehoben", "geprueft": "geprüft", "freigeprueft": "freigeprüft",
    "gesperrt": "gesperrt", "ausgesondert": "ausgesondert", "anhang": "Anhang", "anhang_entfernt": "Anhang entfernt",
    "eroeffnet": "Durchgang eröffnet", "ausgenommen": "ausgenommen", "einbezogen": "wieder einbezogen",
    "geschlossen": "Durchgang abgeschlossen", "faelligkeit": "Fälligkeit vorgezogen", "umbenannt": "umbenannt",
    "eingepflegt": "eingepflegt", "abgelehnt": "abgelehnt", "variante": "als Variante angelegt",
    "festgeschrieben": "festgeschrieben", "berichtigt": "berichtigt", "berichtigung_begonnen": "Berichtigung begonnen",
    "unterschrift": "Unterschrift geändert", "urkundennummer": "Urkundennummer geändert",
    "abgebrochen": "Durchgang abgebrochen",
    "rueckruf": "Rückruf angelegt", "rueckruf_beendet": "Rückruf beendet",
    "freigabe_erteilt": "Freigabe erteilt", "freigabe_geaendert": "Freigabe geändert",
    "freigabe_entzogen": "Freigabe entzogen", "freigabe_entfernt": "Freigabe entfernt",
    "freigabe_abgelaufen": "Freigabe abgelaufen",
    # Im Lebenslauf ohne Namen: Wem der Artikel zugeordnet war, gehört nicht in ein Dokument zur Weitergabe.
    "zugeordnet": "Zuordnung geändert", "zuordnung_geloest": "Zuordnung geändert",
    "bestandsimport": "Bestandsimport", "nacharbeit_uebernommen": "Nacharbeit übernommen",
    "nacharbeit_verworfen": "Nacharbeit verworfen", "wiki": "Prüfanleitung (Wiki) geändert",
    "mangel_gemeldet": "Mangel gemeldet",
    "antrag_gestellt": "Änderung beantragt", "antrag_bestaetigt": "Änderung bestätigt (Antrag)",
    "antrag_abgelehnt": "Änderungsantrag abgelehnt", "antrag_zurueckgezogen": "Änderungsantrag zurückgezogen",
    "laenge_geaendert": "Länge geändert",
    "set_angelegt": "Set mit Teilen angelegt", "stueckliste": "Stückliste geändert",
}
ENTITAET = {"item": "Artikel", "product": "Produkt", "document": "Dokument", "form": "Formular", "folder": "Ordner",
            "category": "Kategorie", "user": "Konto", "inspection": "Prüfung", "round": "Durchgang",
            "request": "Produktmeldung"}
# Wie PRUEFART_KURZ in material.js: im Journal kurz („periodisch“ statt „periodische Prüfung“).
PRUEFART_KURZ = PRUEFARTEN
SPERRZUSTAND = {"frei": "frei", "gesperrt": "gesperrt", "verloren": "verloren (gesperrt)", "ausgesondert": "ausgesondert"}
RECHT = {"lesen": "lesen", "pruefen": "prüfen", "verwalten": "verwalten"}
PERSON = "(Person)"
# „mat_katalog“ bleibt für alte Einträge stehen (das Häkchen gibt es seit Schritt 10 nicht mehr).
_JA_NEIN = ("serial_generated", "active", "mat_pruefer", "mat_katalog", "notiz_geaendert", "reminders_off", "items_have_length",
            "aus_nacharbeit", "is_set")
# Stufe im Modul Material – mit der Zahl dahinter: Einträge vor „Migration Schritt 10“ meinten die Stufen aus Phase 1
# (1 Führungskraft, 2 Materialwart), die Zahl hält das eindeutig.
STUFE_MATERIAL = {0: "kein Zugriff", 1: "Mitglied", 2: "Verwaltung"}
_VERWEISE = ("pruefung", "aussonderung", "basis", "berichtigung", "berichtigt")


def feld_name(feld, eintrag):
    """Die Beschriftung eines Feldes in einem Journaleintrag – wie feldName() in material.js. „description“ ist am
    Produkt der kurze Zusatz hinter dem Namen und heißt dort seit dem Wunsch vom 18.10.2026 „Bemerkung“; an Ordnern und
    in den Einträgen eines Rückrufs (auch sie stehen am Produkt) bleibt es die Beschreibung."""
    if (feld == "description" and eintrag.get("entity") == "product"
            and not str(eintrag.get("action")).startswith("rueckruf")):
        return "Bemerkung"
    return FELD.get(feld, feld)


def _ist_datumsfeld(feld):
    return feld.endswith("_on") or feld in ("valid_from", "retire_by", "datum", "begonnen", "bis")


def wert_text(v, feld, verweise=None):
    """Ein Wert aus dem Journal als Text – wie wert() in material.js, nur ohne HTML. verweise: Kennung einer Prüfung →
    Protokoll-ID; im PDF gibt es keinen Link, die Protokoll-ID findet man dafür im Verzeichnis wieder."""
    if feld == "konto":
        return PERSON if v else "–"
    if v is None or v == "":
        return "–" if feld != "bis" else "unbefristet"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "–"
    if isinstance(v, bool) or (feld in _JA_NEIN and v in (0, 1)):
        return "ja" if v else "nein"
    if feld in ("material_kind", "default_material_kind"):
        return MATERIALARTEN.get(v, str(v))
    if feld in ("kind", "art"):
        return PRUEFART_KURZ.get(v) or ORDNERARTEN.get(v) or ANHANGARTEN.get(v) or str(v)
    if feld in ("result", "ergebnis"):
        return ERGEBNISSE.get(v, str(v))
    if feld in _VERWEISE and isinstance(v, int):
        return (verweise or {}).get(v) or f"Nr. {v}"
    if feld == "lock_state":
        return SPERRZUSTAND.get(v, str(v))
    if feld == "recht_material" and isinstance(v, int) and not isinstance(v, bool):
        return f"{STUFE_MATERIAL.get(v, '?')} ({v})"
    if feld == "recht":
        return RECHT.get(v, str(v))
    if feld == "length_m" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return laenge_text(v)
    if _ist_datumsfeld(feld) and isinstance(v, str):
        return datum_text(v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def journal_zeilen(eintraege, verweise=None, mit_entitaet=False):
    """Journaleinträge (journal.lesen) als fertige Zeilen fürs PDF: {zeit, aktion, von, felder: [(Feld, vorher,
    nachher)]}. Wie journalHtml(): Bei „angelegt“ und „gelöscht“ keine Felder – nur die Ablage, wenn bekannt –, und
    die technische Ordnerkennung fällt weg, wo der Pfad dabeisteht."""
    out = []
    for j in eintraege:
        vorher, nachher = j.get("vorher") or {}, j.get("nachher") or {}
        alle = dict(vorher, **nachher)
        if j["action"] in ("angelegt", "geloescht"):
            felder = ["ordner"] if alle.get("ordner") else []
        else:
            felder = [f for f in alle if not (f == "folder_id" and "ordner" in alle)
                      and not (f == "origin_folder_id" and "herkunft" in alle) and not (f == "parent_id" and "pfad" in alle)]
        aktion = AKTION.get(j["action"], j["action"])
        if mit_entitaet:
            aktion = f"{ENTITAET.get(j['entity'], j['entity'])} {aktion}"
        # Wer einen Mangel meldet, kann die zugeordnete Person sein – im Lebenslauf ohne Namen.
        von = PERSON if j["action"] == "mangel_gemeldet" else (j.get("user_name") or "–")
        out.append({"zeit": zeit_text(j["created_at"]), "aktion": aktion, "von": von,
                    "felder": [{"feld": feld_name(f, j), "vorher": wert_text(vorher.get(f), f, verweise),
                                "nachher": wert_text(nachher.get(f), f, verweise),
                                "nur_nachher": j["action"] in ("angelegt",) or f not in vorher}
                               for f in felder]})
    return out
