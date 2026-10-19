"""Kommandozeile des Moduls:  flask --app "app:create_app()" material <befehl>

Im Container:
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material import-catalog /data/import/katalog.json --trocken
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material export-catalog /data/import/katalog.zip
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material remind --trocken
(Die Datei muss im Datenordner liegen, nur der ist im Container sichtbar. VIDEOPFLEGE=0 hält den
Hintergrundlauf für Videos aus diesem kurzen Prozess heraus.)"""
import os
import sys
from datetime import date, datetime

import click
from flask import current_app, g
from flask.cli import with_appcontext

from .services import ZONE, Abgelehnt, datum, erinnerung, heute, importer, journal, katalog_export


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


def _uhrzeit(utc):
    """'2026-10-19T04:02:11+00:00' → '06:02' (deutsche Zeit); unlesbar → der Text selbst."""
    try:
        return datetime.fromisoformat(utc).astimezone(ZONE).strftime("%H:%M")
    except (TypeError, ValueError):
        return utc or "?"


def _tag_text(t):
    return t.strftime("%d.%m.%Y")


def _trocken(stichtag):
    """Probelauf auf der Kommandozeile: wie in der Übersicht, aber mit Adressen – wer bekäme welche Mail."""
    if stichtag is None:
        stichtag, morgen = erinnerung.naechster_stichtag()
        click.echo(f"Probelauf für {'morgen' if morgen else 'heute'}, den {_tag_text(stichtag)}"
                   + (" – der Versand lief heute schon." if morgen else "."))
    else:
        click.echo(f"Probelauf für den {_tag_text(stichtag)}. Fälligkeiten und Freigabenende gelten für diesen Tag, "
                   f"die Rechte mit dem Stand von heute ({_tag_text(heute())}).")
    click.echo("Nichts wird verschickt oder vermerkt.")
    if not erinnerung.versand_an():
        grund = ("gesperrt (MATERIAL_ERINNERUNGEN_SPERRE)" if erinnerung.gesperrt()
                 else "ausgeschaltet (Verwaltung → Einstellungen)")
        click.echo(f"Hinweis: Erinnerungsmails sind {grund} – so gingen sie hinaus, wenn sie an wären.")
    plan = erinnerung.planen(stichtag)
    if not plan.mails:
        click.echo("Es stünde nichts an.")
    for m in plan.mails:
        artikel = len({e.kennung for e in m.eintraege if e.art == "artikel"})
        freigaben = len({e.kennung for e in m.eintraege if e.art == "freigabe"})
        click.echo("")
        click.echo("=" * 78)
        click.echo(f"An: {m.name} <{m.adresse}> ({artikel} Artikel, {freigaben} Freigaben)")
        click.echo(f"Betreff: {m.betreff}")
        click.echo("")
        click.echo(m.text.rstrip("\n"))
    click.echo("")
    ohne = {}
    for e in plan.ohne_empfaenger:
        ohne.setdefault(plan.pfade.get(e.ordner_id, str(e.ordner_id)), set()).add((e.art, e.kennung))
    if ohne:
        click.echo("Ohne Empfänger: " + "; ".join(f"{pfad} ({len(z)})" for pfad, z in sorted(ohne.items())))
    aus = plan.ausgelassen
    teile = [f"Erinnerungen aus in {o['pfad']} ({o['artikel']} Artikel)" for o in aus["ordner_aus"]]
    if aus["demo"]:
        teile.append(f"{aus['demo']} DEMO")
    if teile:
        click.echo("Ausgelassen: " + "; ".join(teile))
    if plan.fehlerhaft:
        click.echo(f"ACHTUNG {plan.fehlerhaft} Datenzeilen ließen sich nicht lesen – siehe Log.", err=True)


@click.command("remind")
@click.option("--trocken", is_flag=True, help="Nur zeigen, wer welche Mail bekäme – nichts verschicken oder vermerken.")
@click.option("--stichtag", default=None, metavar="JJJJ-MM-TT", help="Mit --trocken: für diesen Tag rechnen.")
@click.option("--erneut", is_flag=True, help="Den Mailteil heute noch einmal – nur, was noch nicht gemeldet ist.")
@with_appcontext
def remind(trocken, stichtag, erneut):
    """Erinnerungsmails an die Materialwarte: der Tageslauf, wie ihn die Anwendung jeden Morgen ab 6 Uhr selbst
    anstößt (Pflege und Mails). Mehrfach aufgerufen mahnt er nie doppelt. Exit 1, wenn eine Mail scheiterte oder ein
    Fehler auftrat; 2, wenn der Versand aus, gesperrt oder kein Mailserver eingerichtet ist."""
    from .. import einstellungen
    einstellungen.anwenden()
    g.mat_akteur = erinnerung.AKTEUR
    if stichtag is not None and not trocken:
        click.echo("Ein echter Lauf gilt immer für heute.", err=True)
        sys.exit(2)
    if trocken:
        try:
            tag = date.fromisoformat(datum(stichtag, "Stichtag")) if stichtag else None
        except Abgelehnt as exc:
            click.echo(str(exc), err=True)
            sys.exit(2)
        _trocken(tag)
        return
    if not current_app.config.get("MATERIAL_ERINNERUNGEN"):
        click.echo("Erinnerungsmails sind ausgeschaltet (Verwaltung → Einstellungen) – nur --trocken.", err=True)
        sys.exit(2)
    if erinnerung.gesperrt():
        click.echo("Erinnerungsmails sind in dieser Umgebung gesperrt (MATERIAL_ERINNERUNGEN_SPERRE) – nur --trocken.",
                   err=True)
        sys.exit(2)
    if not erinnerung.smtp_da():
        click.echo("Kein Mailserver eingerichtet (SMTP_HOST) – nur --trocken.", err=True)
        sys.exit(2)
    erg = erinnerung.tageslauf("kommandozeile", erneut=erneut)
    if erg.get("uebersprungen") == "laeuft":
        seit = erg.get("seit") or ""
        click.echo(f"Ein anderer Lauf ist gerade im Gange (seit {_uhrzeit(seit)}) – nichts getan.")
        return
    if erg.get("uebersprungen") == "erledigt":
        click.echo(f"Heute schon gelaufen ({_uhrzeit(erg.get('um'))}) – mit --erneut geht hinaus, was noch offen ist.")
        return
    fehler = False
    p = erg.get("pflege")
    if p:
        click.echo(f"Pflege: {p['abgelaufen']} abgelaufene Freigaben ins Journal, Log {p['log']} alte und "
                   f"{p['waisen']} verwaiste Zeilen, Suchprotokoll {p['suche']} Zeilen entfernt.")
        if p.get("fehler"):
            click.echo(f"FEHLER  Pflege: {p['fehler']}", err=True)
            fehler = True
    m = erg.get("mails")
    if m:
        click.echo(f"Mails: {m['mails']} verschickt ({m['artikel']} Artikel, {m['freigaben']} Freigaben), "
                   f"{m['fehlgeschlagen']} gescheitert, {m['ohne_empfaenger']} ohne Empfänger.")
        if m["fehlgeschlagen"]:
            namen = journal.konto_namen(m.get("fehlgeschlagen_refs") or [])
            click.echo("Gescheitert an: " + (", ".join(namen.values()) or "?") + " – geht morgen erneut.", err=True)
        for schluessel, text in (("fehlerhaft", "Datenzeilen ließen sich nicht lesen – siehe Log."),
                                 ("vermerk_fehler", "angenommene Mails ließen sich nicht vermerken – siehe Log.")):
            if m.get(schluessel):
                click.echo(f"ACHTUNG {m[schluessel]} {text}", err=True)
        if m.get("fehler"):
            click.echo(f"FEHLER  Mails: {m['fehler']}", err=True)
        fehler = fehler or bool(m["fehlgeschlagen"] or m.get("fehler") or m.get("fehlerhaft") or m.get("vermerk_fehler"))
    if fehler:
        sys.exit(1)


def anmelden(blueprint):
    """Die Befehle an der Kommandozeilengruppe des Blueprints eintragen („flask material …“)."""
    for befehl in (import_catalog, export_catalog, remind):
        if befehl.name not in blueprint.cli.commands:
            blueprint.cli.add_command(befehl)
