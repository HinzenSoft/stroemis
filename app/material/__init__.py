"""Modul Material: Ausrüstungsbestand der Gliederungen und Prüfnachweise je Ausrüstungsteil.

Verwaltet PSA gegen Absturz, Seiltechnik und Wasser-Material (Schwimmwesten, Wasserrettungshelme,
Wurfsäcke, Neopren- und Trockenanzüge). Lampen, Pumpen, Funk, Verbrauchsmaterial, Ausleihe und
Fahrzeuginventar werden nie aufgenommen – das Modul ist kein Lagerverwaltungssystem.

Aufbau:
  models.py      Tabellen mat_*, Schemaversion in mat_meta, Migrationsschritte
  routes.py      Seiten (/material/…, /m/<token>), Schnittstelle (/api/material/…), Medien
  routes_export.py, routes_katalog.py, routes_rueckruf.py
                 Routen der Lieferung 4: Export (CSV, Protokoll-ZIP, Lebenslauf), Katalogaustausch, Rückrufe
  cli.py         flask material import-catalog, export-catalog
  services/      Fachregeln: rechte, katalog, bestand, status, interval, search, nummern, qr, journal,
                 importer, katalog_export, pruefung, durchgang, anhang, meldung, protokoll (Festschreiben,
                 Prüfseite), pdf (WeasyPrint), stempel (Prüfsumme), unterschrift, ueberblick (Fälligkeiten je
                 Ordner), export, lebenslauf, beschriftung (Journal als Text), rueckruf; seit Phase 2 dazu
                 globalprotokoll (Protokoll der Blicke über den eigenen Bereich) und globalsuche
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


def schema_anmelden():
    """Die Migration dieses Moduls beim Start mitlaufen lassen (db.init_db ruft sie auf) – danach das Protokoll der
    globalen Suche auf seine Frist kürzen, die Protokolldateien mit der Datenbank abgleichen und durchsichtige Bilder
    einmalig reparieren."""
    for schritt in (models.migrieren, _suchprotokoll_aufraeumen, _verwaiste_protokolle, _bilder_reparieren):
        if schritt not in db.SCHEMA_MODULE:
            db.SCHEMA_MODULE.append(schritt)


def init_app(app):
    """Blueprints, Kommandozeile und Vorgaben eintragen. Wird in create_app vor db.init_db gerufen."""
    from . import cli
    from .routes import api, seiten
    schema_anmelden()
    cli.anmelden(seiten)
    app.config.setdefault("MATERIAL_BALD_FAELLIG_TAGE", MATERIAL_BALD_FAELLIG_TAGE)
    app.register_blueprint(seiten)
    app.register_blueprint(api)


def upload_grenzen():
    from .routes import UPLOAD_GRENZEN
    return UPLOAD_GRENZEN
