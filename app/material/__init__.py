"""Modul Material: Ausrüstungsbestand der Gliederungen und Prüfnachweise je Ausrüstungsteil.

Verwaltet PSA gegen Absturz, Seiltechnik und Wasser-Material (Schwimmwesten, Wasserrettungshelme,
Wurfsäcke, Neopren- und Trockenanzüge). Lampen, Pumpen, Funk, Verbrauchsmaterial, Ausleihe und
Fahrzeuginventar werden nie aufgenommen – das Modul ist kein Lagerverwaltungssystem.

Aufbau:
  models.py      Tabellen mat_*, Schemaversion in mat_meta, Migrationsschritte
  routes.py      Seiten (/material/…, /m/<token>), Schnittstelle (/api/material/…), Medien
  cli.py         flask material import-catalog
  services/      Fachregeln: rechte, katalog, bestand, status, interval, search, nummern, qr, journal,
                 importer, pruefung, durchgang, anhang, meldung, protokoll (Festschreiben, Prüfseite),
                 pdf (WeasyPrint), stempel (Prüfsumme), unterschrift
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


def schema_anmelden():
    """Die Migration dieses Moduls beim Start mitlaufen lassen (db.init_db ruft sie auf) – danach den Abgleich der
    Protokolldateien mit der Datenbank und die einmalige Reparatur durchsichtiger Bilder."""
    for schritt in (models.migrieren, _verwaiste_protokolle, _bilder_reparieren):
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
