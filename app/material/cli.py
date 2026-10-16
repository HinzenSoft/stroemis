"""Kommandozeile des Moduls:  flask --app "app:create_app()" material <befehl>

Im Container:
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material import-catalog /data/import/katalog.json --trocken
(Die Datei muss im Datenordner liegen, nur der ist im Container sichtbar. VIDEOPFLEGE=0 hält den
Hintergrundlauf für Videos aus diesem kurzen Prozess heraus.)"""
import json
import os
import sys

import click
from flask.cli import with_appcontext

from .services import importer


@click.command("import-catalog")
@click.argument("datei", type=click.Path(exists=True, dir_okay=False))
@click.option("--trocken", is_flag=True, help="Nur prüfen und berichten – nichts speichern.")
@with_appcontext
def import_catalog(datei, trocken):
    """Kategorien, Produkte und Prüfformulare aus einer JSON-Datei übernehmen (Format: CHANGELOG-Material.md)."""
    try:
        with open(datei, encoding="utf-8") as fh:
            daten = json.load(fh)
    except (OSError, ValueError) as exc:
        click.echo(f"Die Datei ließ sich nicht als JSON lesen: {exc}", err=True)
        sys.exit(2)
    bericht = importer.importieren(daten, trocken=trocken, quelle=os.path.basename(datei))
    for teil in ("kategorien", "produkte", "formulare"):
        zahlen = ", ".join(f"{k} {v}" for k, v in bericht[teil].items())
        click.echo(f"{teil.capitalize():<11} {zahlen}")
    for f in bericht["fehler"]:
        click.echo(f"FEHLER  {f}", err=True)
    if bericht["fehler"]:
        click.echo("Nichts gespeichert – erst alle Fehler beheben.", err=True)
        sys.exit(1)
    click.echo("Trockenlauf – nichts gespeichert." if trocken else "Gespeichert.")


def anmelden(blueprint):
    """Die Befehle an der Kommandozeilengruppe des Blueprints eintragen („flask material …“)."""
    if "import-catalog" not in blueprint.cli.commands:
        blueprint.cli.add_command(import_catalog)
