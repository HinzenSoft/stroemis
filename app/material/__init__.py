"""Modul Material: Ausrüstungsbestand der Gliederungen und Prüfnachweise je Ausrüstungsteil.

Verwaltet PSA gegen Absturz, Seiltechnik und Wasser-Material (Schwimmwesten, Wasserrettungshelme,
Wurfsäcke, Neopren- und Trockenanzüge). Lampen, Pumpen, Funk, Verbrauchsmaterial, Ausleihe und
Fahrzeuginventar werden nie aufgenommen – das Modul ist kein Lagerverwaltungssystem.

Aufbau:
  models.py      Tabellen mat_*, Schemaversion in mat_meta, Migrationsschritte
  routes.py      Seiten (/material/…, /m/<token>), Schnittstelle (/api/material/…), Medien
  routes_export.py, routes_katalog.py, routes_rueckruf.py
                 Routen der Lieferung 4: Export (CSV, Protokoll-ZIP, Lebenslauf), Katalogaustausch, Rückrufe
  routes_import.py, routes_wiki.py
                 Routen der Phase 2 · Lieferung 3: Bestandsimport und Nacharbeit, Prüfanleitung aus dem Wiki
  routes_psa.py  Routen der Phase 3 · Lieferung 1: „Meine PSA“ (auch ohne Modulstufe) und Mangelmeldung
  cli.py         flask material import-catalog, export-catalog, remind, dok-zusammenfuehren
  tageslauf.py   Thread je Arbeitsprozess: einmal am Tag ab 6 Uhr Pflege und Erinnerungsmails (seit Phase 2 · L2)
  services/      Fachregeln: rechte, katalog, bestand, status, interval, search, nummern, qr, journal,
                 importer, katalog_export, pruefung, durchgang, anhang, meldung, protokoll (Festschreiben,
                 Prüfseite), pdf (WeasyPrint), stempel (Prüfsumme), unterschrift, ueberblick (Fälligkeiten je
                 Ordner), export, lebenslauf, beschriftung (Journal als Text), rueckruf; seit Phase 2 dazu
                 globalprotokoll (Protokoll der Blicke über den eigenen Bereich) und globalsuche, seit Lieferung 2
                 erinnerung (Erinnerungsmails, Pflege, Laufstand und Probelauf), seit Lieferung 3 tabelle und
                 bestandsimport (Bestandsimport mit Nacharbeit) und wikiverweis (Prüfanleitung aus dem Wiki); seit
                 Phase 3 psa („Meine PSA“) und mangel (Mangelmeldung mit sofortiger Sperre); seit Schritt 18 dokablage
                 (Herstellerdokumente einmal je Inhalt – Zusammenführen des Altbestands beim Start und von Hand); seit
                 Phase 4 · L2 stueckliste (Stückliste der Hersteller-Sets im Katalog), sets (Set-Artikel mit Teilen,
                 Sperr-Kaskade), setlauf (Set prüfen, Freigabe) und setaustausch (Teile tauschen, entnehmen;
                 Set aussondern)
  templates/, static/   Seite und Oberfläche (material.js, material.css)
"""
from .. import db
from . import models

MATERIAL_BALD_FAELLIG_TAGE = 30


def _verwaiste_protokolle(conn):
    from .services.protokoll import verwaiste_beiseite
    verwaiste_beiseite(conn)


def _bilder_reparieren(conn):
    from .services.katalog import durchsichtige_bilder_reparieren
    durchsichtige_bilder_reparieren(conn)


def _suchprotokoll_aufraeumen(conn):
    from .services.globalprotokoll import aufraeumen
    aufraeumen(conn)


def _erinnerungslog_aufraeumen(conn):
    from .services.erinnerung import aufraeumen
    aufraeumen(conn)


def _nacharbeit_aufraeumen(conn):
    from .services.bestandsimport import aufraeumen
    aufraeumen(conn)


def _mailfehler_aufraeumen(conn):
    from .services.mailprotokoll import aufraeumen
    aufraeumen(conn)


def _sets_pruefen(conn):
    from .services.sets import beim_start
    beim_start(conn)


def _dokumente_zusammenfuehren(conn):
    from .services.dokablage import beim_start
    beim_start(conn)


def schema_anmelden():
    """Die Migration dieses Moduls beim Start mitlaufen lassen (db.init_db ruft sie auf) – gleich danach den Altbestand
    der Herstellerdokumente einmal je Inhalt zusammenführen (Schritt 18, Kennzeichen in mat_meta), dann das Protokoll der
    globalen Suche, das Erinnerungslog, das Mailfehler-Protokoll und die offene Nacharbeit aus Bestandsimporten auf ihre
    Frist kürzen (auch wenn der Tageslauf steht), die Protokolldateien mit der Datenbank abgleichen und durchsichtige
    Bilder einmalig reparieren. Zuletzt die Startprüfung „Sets stimmig“ (Schritt 21, nur Log)."""
    for schritt in (models.migrieren, _dokumente_zusammenfuehren, _suchprotokoll_aufraeumen, _erinnerungslog_aufraeumen,
                    _mailfehler_aufraeumen, _nacharbeit_aufraeumen, _verwaiste_protokolle, _bilder_reparieren,
                    _sets_pruefen):
        if schritt not in db.SCHEMA_MODULE:
            db.SCHEMA_MODULE.append(schritt)


def init_app(app):
    """Blueprints, Kommandozeile und Vorgaben eintragen – dazu den Anstoß des Tageslaufs (startet bei der ersten
    Anfrage, tageslauf.py). Wird in create_app vor db.init_db gerufen."""
    from . import cli, tageslauf
    from .routes import api, seiten
    schema_anmelden()
    cli.anmelden(seiten)
    app.config.setdefault("MATERIAL_BALD_FAELLIG_TAGE", MATERIAL_BALD_FAELLIG_TAGE)
    app.config.setdefault("MATERIAL_ERINNERUNGEN", False)
    app.before_request(tageslauf.anstossen)
    app.register_blueprint(seiten)
    app.register_blueprint(api)


def upload_grenzen():
    from .routes import UPLOAD_GRENZEN
    return UPLOAD_GRENZEN
