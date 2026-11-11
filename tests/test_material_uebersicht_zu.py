"""„Fälligkeiten je Ordner“ beginnt zugeklappt (Wunsch des Nutzers, 11.11.2026):
python tests/test_material_uebersicht_zu.py  oder  pytest tests/test_material_uebersicht_zu.py

Jeder Ordner mit Unterordnern steht beim Laden der Übersicht zugeklappt da – zuerst sieht man nur die Gliederungen, egal
wie groß der Baum ist (vorher erst ab 30 Zeilen und ab der zweiten Ebene). Ein grauer Pfad-Knoten (Oberordner ohne eigene
Freigabe) bleibt offen, sonst stünde nur sein Name ohne Zahlen da. ordnerUebersichtHtml aus material.js mit Node.js
gerendert (ohne Node.js übersprungen). Keine Konten, keine Mails."""
import json
import os
import re
import shutil
import subprocess

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKRIPT = r"""
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const esc = new Function(`${fs.readFileSync(process.argv[2], "utf8").match(/const esc = .*;/)[0]} return esc;`)();
const teil = (a, b) => js.slice(js.indexOf(a), js.indexOf(b));
const html = new Function("esc", "schloss", "pfadKnoten", "ORDNERART", "demoMarke", "fmtTag",
  teil("  const UE_SPALTEN", "  const ordnerUebersichtInfo") + "; return ordnerUebersichtHtml;")(
  esc, () => "", (n) => `<span class="mat-pfad">${esc(n)}</span>`, { gliederung: "Gliederung", lager: "Lager" }, () => "",
  (t) => t);
const zeile = (id, parent_id, tiefe, unterordner, extra) => ({ id, parent_id, tiefe, unterordner, name: `Ordner ${id}`,
  kind: tiefe ? "lager" : "gliederung", bestand: 1, zaehlung: { neu: 1 }, ...extra });
// Klein (weit unter 30 Zeilen): Bezirk → OG → Lager → Regal, daneben eine Gliederung ohne Unterordner.
const klein = [zeile(1, null, 0, true), zeile(2, 1, 1, true), zeile(3, 2, 2, true), zeile(4, 3, 3, false),
               zeile(5, null, 0, false)];
// Ohne eigene Freigabe oben: grauer Pfad-Knoten 10 → Gliederung 11 (mit Zahlen) → Lager 12.
const pfad = [zeile(10, null, 0, true, { nur_pfad: true }), zeile(11, 10, 1, true, { kind: "gliederung" }),
              zeile(12, 11, 2, false)];
console.log(JSON.stringify([html(klein), html(pfad)]));
"""


def zeilen(tabelle):
    """[(Ordner-ID der Zeile, verborgen?)] in Tabellenreihenfolge, dazu {ID: aria-expanded} der Klappknöpfe."""
    reihen = re.findall(r'<tr data-weg="[^"]*"[^>]*>.*?</tr>', tabelle, re.S)
    # Der Name verlinkt den Ordner; ein Pfad-Knoten hat keinen Link, nur seinen Klappknopf.
    ids = [int((re.search(r'href="/materialablage/ordner/(\d+)"', r) or re.search(r'data-ue-klapp="(\d+)"', r)).group(1))
           for r in reihen]
    verborgen = [bool(re.match(r'<tr[^>]* hidden>', r)) for r in reihen]
    knoepfe = {int(i): z for i, z in re.findall(r'data-ue-klapp="(\d+)" aria-expanded="(true|false)"', tabelle)}
    return list(zip(ids, verborgen)), knoepfe


def test_beginnt_zugeklappt():
    node = shutil.which("node")
    js = open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8").read()
    assert "UE_GROSS" not in js, "keine Schwelle mehr – der Baum beginnt immer zugeklappt"
    if not node:
        print("Gerendert übersprungen (kein Node.js).")
        return
    aus = subprocess.run([node, "-e", SKRIPT, os.path.join(WURZEL, "app/material/static/material.js"),
                          os.path.join(WURZEL, "app/static/js/common.js")], capture_output=True, text=True,
                         check=True).stdout
    klein, pfad = json.loads(aus)

    # Kleiner Baum: alle Klappknöpfe zu, sichtbar nur die beiden Gliederungen.
    reihen, knoepfe = zeilen(klein)
    assert knoepfe == {1: "false", 2: "false", 3: "false"}, knoepfe
    assert reihen == [(1, False), (2, True), (3, True), (4, True), (5, False)], reihen
    assert 'data-ue-klapp="5"' not in klein  # ohne Unterordner kein Knopf

    # Pfad-Knoten bleibt offen, die Gliederung darunter (mit Zahlen) ist zu.
    reihen, knoepfe = zeilen(pfad)
    assert knoepfe == {10: "true", 11: "false"}, knoepfe
    assert reihen == [(10, False), (11, False), (12, True)], reihen


if __name__ == "__main__":
    test_beginnt_zugeklappt()
    print("ok")
