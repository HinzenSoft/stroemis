"""Kommandozeile des Moduls:  flask --app "app:create_app()" material <befehl>

Im Container:
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material import-catalog /data/import/katalog.json --trocken
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material export-catalog /data/import/katalog.zip
(Die Datei muss im Datenordner liegen, nur der ist im Container sichtbar. VIDEOPFLEGE=0 hält den
Hintergrundlauf für Videos aus diesem kurzen Prozess heraus.)"""
import os
import sys

import click
from flask.cli import with_appcontext

from .services import Abgelehnt, importer, katalog_export


@click.command("import-catalog")
@click.argument("datei", type=click.Path(exists=True, dir_okay=False))
@click.option("--trocken", is_flag=True, help="Nur prüfen und berichten – nichts speichern.")
@with_appcontext
def import_catalog(datei, trocken):
    """Kategorien, Produkte und Prüfformulare übernehmen – aus einer JSON-Datei oder einem Katalog-Export (ZIP mit
    Bildern und Dokumenten, an der Signatur „PK“ erkannt). Format: CHANGELOG-Material.md."""
    try:
        with open(datei, "rb") as fh:
            bericht = importer.datei_importieren(fh, trocken=trocken, quelle=os.path.basename(datei))
    except OSError as exc:
        click.echo(f"Die Datei ließ sich nicht lesen: {exc}", err=True)
        sys.exit(2)
    except Abgelehnt as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)
    teile = ("kategorien", "produkte", "formulare") + (("bilder", "dokumente") if bericht.get("version") == 2 else ())
    for teil in teile:
        zahlen = ", ".join(f"{k} {v}" for k, v in bericht[teil].items())
        click.echo(f"{teil.capitalize():<11} {zahlen}")
    for h in bericht["hinweise"]:
        click.echo(f"HINWEIS {h}")
    for w in bericht["warnungen"]:
        click.echo(f"ACHTUNG {w}")
    for f in bericht["fehler"]:
        click.echo(f"FEHLER  {f}", err=True)
    if bericht["fehler"]:
        click.echo("Nichts gespeichert – erst alle Fehler beheben.", err=True)
        sys.exit(1)
    click.echo("Trockenlauf – nichts gespeichert." if trocken else "Gespeichert.")


@click.command("export-catalog")
@click.argument("ziel", type=click.Path(dir_okay=False))
@with_appcontext
def export_catalog(ziel):
    """Den Katalog dieser Instanz ohne DEMO als ZIP (Format 2) schreiben – für import-catalog in einer anderen.
    Bestand und Prüfungen kommen nie mit."""
    teil = ziel + ".teil"
    try:
        with open(teil, "wb") as fh:
            bericht = katalog_export.zip_bauen(fh)
        os.replace(teil, ziel)
    except (Abgelehnt, OSError) as exc:
        try:
            os.remove(teil)
        except OSError:
            pass
        click.echo(f"Kein Export: {exc}", err=True)
        sys.exit(1)
    click.echo(katalog_export.bericht_text(bericht))
    click.echo(f"Geschrieben: {ziel}")


def anmelden(blueprint):
    """Die Befehle an der Kommandozeilengruppe des Blueprints eintragen („flask material …“)."""
    for befehl in (import_catalog, export_catalog):
        if befehl.name not in blueprint.cli.commands:
            blueprint.cli.add_command(befehl)
