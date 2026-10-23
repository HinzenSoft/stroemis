"""Kommandozeile des Moduls:  flask --app "app:create_app()" material <befehl>

Im Container:
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material import-catalog /data/import/katalog.json --trocken
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material export-catalog /data/import/katalog.zip
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material remind --trocken
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material dok-zusammenfuehren --probe
    docker compose exec -e VIDEOPFLEGE=0 stroemis \
        flask --app "app:create_app()" material dev-zuruecksetzen --trocken      (nur dev, README)
(Die Datei muss im Datenordner liegen, nur der ist im Container sichtbar. VIDEOPFLEGE=0 hält den
Hintergrundlauf für Videos aus diesem kurzen Prozess heraus.)"""
import os
import sqlite3
import sys
from datetime import date, datetime

import click
from flask import current_app, g
from flask.cli import with_appcontext

from .services import (ZONE, Abgelehnt, datum, dokablage, erinnerung, heute, importer, katalog, katalog_export,
                       zuruecksetzen)


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
    # Stücklisten der Hersteller-Sets (Schritt 21): neu, geändert, unverändert – wie der Bericht in der App.
    teile = ("kategorien", "produkte", "formulare") + (("bilder", "dokumente") if bericht.get("version") == 2 else ()) + (
        ("stuecklisten",) if any(bericht.get("stuecklisten", {}).values()) else ())
    for teil in teile:
        zahlen = ", ".join(f"{k} {v}" for k, v in bericht[teil].items())
        click.echo(f"{'Stücklisten' if teil == 'stuecklisten' else teil.capitalize():<11} {zahlen}")
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


def _trocken(stichtag, demo=False):
    """Probelauf auf der Kommandozeile: wie in der Übersicht, aber mit Adressen – wer bekäme welche Mail. demo: den
    DEMO-Bestand einbeziehen (nur Ansicht, erinnerung.planen)."""
    if stichtag is None:
        stichtag, morgen = erinnerung.naechster_stichtag()
        click.echo(f"Probelauf für {'morgen' if morgen else 'heute'}, den {_tag_text(stichtag)}"
                   + (" – der Versand lief heute schon." if morgen else "."))
    else:
        click.echo(f"Probelauf für den {_tag_text(stichtag)}. Fälligkeiten und Freigabenende gelten für diesen Tag, "
                   f"die Rechte mit dem Stand von heute ({_tag_text(heute())}).")
    click.echo("Nichts wird verschickt oder vermerkt.")
    if demo:
        click.echo("DEMO-Bestand einbezogen – nur zur Ansicht. Mails mit DEMO gehen nie hinaus; der echte Lauf lässt "
                   "DEMO weiter aus.")
    if not erinnerung.versand_an():
        grund = ("gesperrt (MATERIAL_ERINNERUNGEN_SPERRE)" if erinnerung.gesperrt()
                 else "ausgeschaltet (Verwaltung → Einstellungen)")
        click.echo(f"Hinweis: Erinnerungsmails sind {grund} – so gingen sie hinaus, wenn sie an wären.")
    plan = erinnerung.planen(stichtag, demo=demo)
    if not plan.mails:
        click.echo("Es stünde nichts an.")
    for m in plan.mails:
        artikel, freigaben, eigene, psa = erinnerung.zahlen(m)
        zahl = f"{artikel} Artikel, {freigaben} {'Freigabe' if freigaben == 1 else 'Freigaben'}"
        if eigene:                                   # Abschnitt „Deine Freigaben“ (der Empfänger ist ihr Inhaber)
            zahl += f", {eigene} {'eigene Freigabe' if eigene == 1 else 'eigene Freigaben'}"
        if psa:                                      # Abschnitt „Deine PSA“ (der Empfänger ist die zugeordnete Person)
            zahl += f", {psa} PSA"
        click.echo("")
        click.echo("=" * 78)
        click.echo(f"An: {m.name} <{m.adresse}> ({zahl})" + ("  [DEMO – geht nie hinaus]" if m.demo else ""))
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
        teile.append(f"{aus['demo']} DEMO-Artikel")
    if aus.get("demo_freigaben"):
        teile.append(f"{aus['demo_freigaben']} DEMO-{'Freigabe' if aus['demo_freigaben'] == 1 else 'Freigaben'}")
    if teile:
        click.echo("Ausgelassen: " + "; ".join(teile))
    if not demo and (aus["demo"] or aus.get("demo_freigaben")):
        click.echo("DEMO-Bestand ansehen: remind --trocken --demo (nur Ansicht).")
    if plan.fehlerhaft:
        click.echo(f"ACHTUNG {plan.fehlerhaft} Datenzeilen ließen sich nicht lesen – siehe Log.", err=True)


@click.command("remind")
@click.option("--trocken", is_flag=True, help="Nur zeigen, wer welche Mail bekäme – nichts verschicken oder vermerken.")
@click.option("--stichtag", default=None, metavar="JJJJ-MM-TT", help="Mit --trocken: für diesen Tag rechnen.")
@click.option("--erneut", is_flag=True, help="Den Mailteil heute noch einmal – nur, was noch nicht gemeldet ist.")
@click.option("--demo", is_flag=True, help="Nur mit --trocken: den DEMO-Bestand einbeziehen (nur Ansicht, geht nie hinaus).")
@with_appcontext
def remind(trocken, stichtag, erneut, demo):
    """Erinnerungsmails an die Materialwarte: der Tageslauf, wie ihn die Anwendung jeden Morgen ab 6 Uhr selbst
    anstößt (Pflege und Mails). Mehrfach aufgerufen mahnt er nie doppelt (zur einen Ausnahme siehe erinnerung.py).
    Exit 1, wenn eine Mail scheiterte oder ein Fehler auftrat; 2, wenn der Versand aus, gesperrt oder kein Mailserver
    eingerichtet ist oder der Aufruf nicht stimmt (--stichtag oder --demo ohne --trocken, unlesbares Datum). --demo
    zeigt den DEMO-Bestand nur im Probelauf; ein echter Lauf lässt DEMO immer aus."""
    from .. import einstellungen
    einstellungen.anwenden()
    g.mat_akteur = erinnerung.AKTEUR
    if stichtag is not None and not trocken:
        click.echo("Ein echter Lauf gilt immer für heute.", err=True)
        sys.exit(2)
    if demo and not trocken:
        click.echo("--demo nur mit --trocken: DEMO-Bestand wird nie gemahnt, nur angesehen.", err=True)
        sys.exit(2)
    if trocken:
        try:
            tag = date.fromisoformat(datum(stichtag, "Stichtag")) if stichtag else None
        except Abgelehnt as exc:
            click.echo(str(exc), err=True)
            sys.exit(2)
        _trocken(tag, demo=demo)
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
        mf = p.get("mailfehler") or {}
        click.echo(f"Pflege: {p['abgelaufen']} abgelaufene Freigaben ins Journal, Log {p['log']} alte und "
                   f"{p['waisen']} verwaiste Zeilen, Suchprotokoll {p['suche']} Zeilen, Mailfehler "
                   f"{mf.get('alt', 0) + mf.get('erledigt', 0) + mf.get('waisen', 0)} Zeilen entfernt.")
        if p.get("fehler"):
            click.echo(f"FEHLER  Pflege: {p['fehler']}", err=True)
            fehler = True
    m = erg.get("mails")
    if m:
        davon = f", davon {m['psa']} PSA" if m.get("psa") else ""
        click.echo(f"Mails: {m['mails']} verschickt ({m['artikel']} Artikel{davon}, {m['freigaben']} "
                   f"{'Freigabe' if m['freigaben'] == 1 else 'Freigaben'}), "
                   f"{m['fehlgeschlagen']} gescheitert, {m['ohne_empfaenger']} ohne Empfänger.")
        if m["fehlgeschlagen"]:
            click.echo("Gescheitert – an wen, steht im Mailfehler-Protokoll auf der Übersicht; geht morgen erneut.",
                       err=True)
        for schluessel, text in (("fehlerhaft", "Datenzeilen ließen sich nicht lesen – siehe Log."),
                                 ("vermerk_fehler", "angenommene Mails ließen sich nicht vermerken – siehe Log.")):
            if m.get(schluessel):
                click.echo(f"ACHTUNG {m[schluessel]} {text}", err=True)
        if m.get("fehler"):
            click.echo(f"FEHLER  Mails: {m['fehler']}", err=True)
        fehler = fehler or bool(m["fehlgeschlagen"] or m.get("fehler") or m.get("fehlerhaft") or m.get("vermerk_fehler"))
    if fehler:
        sys.exit(1)


@click.command("dok-zusammenfuehren")
@click.option("--probe", is_flag=True, help="Nur rechnen und berichten – nichts umbenennen, nichts löschen.")
@with_appcontext
def dok_zusammenfuehren(probe):
    """Herstellerdokumente einmal je Inhalt (Schritt 18): Dateien unter media/material/dok auf ihren Inhaltsnamen
    bringen, Dubletten zusammenführen, Prüfsummen nachtragen. Läuft beim ersten Start nach dem Update von selbst; hier
    noch einmal mit Bericht – etwa mit --probe vorher, oder nachdem die Medien beim Start nicht erreichbar waren."""
    ordner = os.path.join(katalog.medien_dir(), "dok")           # nicht dok_dir(): der Ordner wird hier nicht angelegt
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    try:
        bericht = dokablage.zusammenfuehren(conn, ordner, probe=probe)
    finally:
        conn.close()
    click.echo(dokablage.bericht_text(bericht))
    if bericht["ordner_fehlt"]:
        sys.exit(2)
    if bericht["fehlend"]:
        sys.exit(1)


@click.command("dev-zuruecksetzen")
@click.option("--trocken", is_flag=True, help="Nur zeigen, was gesichert, verschoben und gelöscht würde – nichts ändern.")
@click.option(zuruecksetzen.SCHALTER, "ja", is_flag=True, help="Wirklich zurücksetzen (nur auf dev).")
@with_appcontext
def dev_zuruecksetzen(trocken, ja):
    """Das Modul Material auf dev leeren, um von null an zu testen: erst die ganze Datenbank sichern und media/material
    und pdf/ in die Sicherung verschieben (<DATA_DIR>/sicherung-material-<Zeitstempel>), dann alle mat_-Tabellen samt
    Triggern und Volltextindizes entfernen und das Schema frisch anlegen. Konten, Wiki, Spots, Prüfungen und
    Einstellungen bleiben. Nur auf dev (STROEMIS_NAME endet auf -dev, BASE_URL mit Host dev.… oder localhost) und nur mit
    --ja-alles-loeschen; sonst Exit 2. Exit 1, wenn die Sicherung oder ein späterer Schritt scheiterte – dann ist
    nichts geändert (die Meldung sagt es). Danach: docker compose restart. Siehe services/zuruecksetzen.py."""
    from .. import einstellungen
    einstellungen.anwenden()
    grund = zuruecksetzen.sperrgrund()
    if grund:
        click.echo(f"Abgelehnt: {grund} Dieser Befehl wirkt nur auf dev – nichts geändert.", err=True)
        sys.exit(2)
    if trocken:
        conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=zuruecksetzen.WARTEN)
        try:
            click.echo(zuruecksetzen.trocken_text(zuruecksetzen.bestand(conn), zuruecksetzen.sicherungsziel()))
        finally:
            conn.close()
        return
    if not ja:
        click.echo(f"Abgelehnt: Ohne {zuruecksetzen.SCHALTER} setzt der Befehl nichts zurück – nichts geändert. "
                   "Erst ansehen, was geschähe: dev-zuruecksetzen --trocken", err=True)
        sys.exit(2)
    try:
        ergebnis = zuruecksetzen.zuruecksetzen()
    except zuruecksetzen.Gescheitert as exc:
        click.echo(f"FEHLER  {exc}", err=True)
        sys.exit(1)
    click.echo(zuruecksetzen.bericht_text(ergebnis))


def anmelden(blueprint):
    """Die Befehle an der Kommandozeilengruppe des Blueprints eintragen („flask material …“)."""
    for befehl in (import_catalog, export_catalog, remind, dok_zusammenfuehren, dev_zuruecksetzen):
        if befehl.name not in blueprint.cli.commands:
            blueprint.cli.add_command(befehl)
