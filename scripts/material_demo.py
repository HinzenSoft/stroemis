"""Demodaten für das Modul Material – NUR für Entwicklung und Tests, nie für echte Prüfungen.

Eigenständiges Werkzeug außerhalb von app/ (wie scripts/beispieldaten.py): Es läuft nie im
Docker-Image mit, denn das Dockerfile kopiert nur app/. Geladen wird nur mit ausdrücklichem Schalter:

    python scripts/material_demo.py --demo

Ohne Angabe landen die Daten wie bei run.py in ./data; für eine andere Datenbank vorher DATA_DIR setzen.
Alles, was das Skript anlegt, trägt das Kennzeichen demo und „DEMO“ im Namen – die Oberfläche zeigt
es überall als „DEMO – nicht für echte Prüfungen“. Prüfpunkte, Intervalle, Lebensdauern und Hersteller
sind Platzhalter: Der echte Katalog entsteht in Phase 0 mit den Sachkundigen und kommt über
`flask material import-catalog` ins System. Die Normen je Kategorie stammen aus den DLRG
Standardverfahren Grundlagen V1.9.
"""
import os
import sys
from datetime import date, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.environ.setdefault("DATA_DIR", os.path.join(REPO_ROOT, "data"))
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("VIDEOPFLEGE", "0")

HINWEIS = "DEMO – nicht für echte Prüfungen"


def _punkte(n_janein, mit_text=True):
    """Platzhalter-Prüfpunkte: bewusst ohne Inhalt, damit niemand sie für echte hält."""
    punkte = [{"gruppe": "DEMO-Gruppe", "text": f"DEMO-Prüfpunkt {i} (Ja/Nein, Platzhalter)", "art": "yesno",
               "soll": "nein" if i > 1 else "ja", "kritisch": i <= 2} for i in range(1, n_janein + 1)]
    if mit_text:
        punkte.append({"gruppe": "DEMO-Gruppe", "text": "DEMO-Bemerkung (Platzhalter)", "art": "text", "pflicht": False})
    return punkte


KATALOG = {
    "format": "stroemis-material-katalog", "version": 1, "demo": True,
    "kategorien": [
        {"name": "DEMO PSA gegen Absturz und Seiltechnik", "unterkategorien": [
            {"name": "DEMO Gurte", "norm": "EN 361, EN 12277 oder EN 813", "materialart": "textil", "intervall_monate": 12},
            {"name": "DEMO Statikseile", "norm": "EN 1891 Typ A/B", "materialart": "textil", "intervall_monate": 12},
            {"name": "DEMO Bandschlingen", "norm": "EN 354 (22 kN)", "materialart": "textil", "intervall_monate": 12},
            {"name": "DEMO HMS-Karabiner", "norm": "EN 362 oder EN 12275", "materialart": "metall_hardware",
             "intervall_monate": 12},
            {"name": "DEMO Kletterhelme", "norm": "EN 12492", "materialart": "sonstiges", "intervall_monate": 12}]},
        {"name": "DEMO Wasserrettung", "unterkategorien": [
            {"name": "DEMO Schwimmhilfen", "norm": "EN 12402-5, Panikverschluss, mindestens 50 N",
             "materialart": "sonstiges", "intervall_monate": 12},
            {"name": "DEMO Wassersporthelme", "norm": "EN 1385", "materialart": "sonstiges", "intervall_monate": 12}]},
    ],
    "produkte": [
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Gurte"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Gurt A", "artikelnummer": "DEMO-G-100", "materialart": "textil", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": HINWEIS},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Statikseile"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Statikseil 11 mm", "artikelnummer": "DEMO-S-11", "materialart": "textil", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": HINWEIS},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO HMS-Karabiner"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO HMS-Karabiner", "artikelnummer": "DEMO-K-1", "materialart": "metall_hardware",
         "beschreibung": HINWEIS},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Kletterhelme"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Helm", "artikelnummer": "DEMO-H-1", "materialart": "sonstiges", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": HINWEIS},
        {"kategorie": ["DEMO Wasserrettung", "DEMO Schwimmhilfen"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Rettungsweste", "artikelnummer": "DEMO-W-1", "materialart": "sonstiges", "beschreibung": HINWEIS},
    ],
    "formulare": [
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Gurte"], "titel": "DEMO-Formular Gurte",
         "punkte": _punkte(4)},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO HMS-Karabiner"], "titel": "DEMO-Formular Karabiner",
         "punkte": _punkte(3)},
        {"kategorie": ["DEMO Wasserrettung", "DEMO Schwimmhilfen"], "titel": "DEMO-Formular Schwimmhilfen",
         "punkte": _punkte(3)},
        {"produkt": {"hersteller": "DEMO-Hersteller", "modell": "DEMO Statikseil 11 mm", "artikelnummer": "DEMO-S-11"},
         "titel": "DEMO-Formular Statikseil (spezifisch)", "punkte": _punkte(2)},
    ],
}


def main():
    if "--demo" not in sys.argv[1:]:
        print(__doc__)
        print("Abgebrochen: Demodaten werden nur mit dem Schalter --demo geladen.")
        sys.exit(2)
    from flask import g

    from app import create_app, db
    from app.material.services import bestand, importer

    app = create_app()
    with app.app_context():
        bericht = importer.importieren(KATALOG, quelle="Demodaten")
        if bericht["fehler"]:
            for f in bericht["fehler"]:
                print("FEHLER", f)
            sys.exit(1)
        print("Katalog:", {k: v for k, v in bericht.items() if k in ("kategorien", "produkte", "formulare")})
        g.mat_akteur = "Demodaten"
        if db.query("SELECT 1 FROM mat_folder WHERE demo = 1 LIMIT 1", one=True):
            print("Demo-Bestand ist schon da – nichts weiter angelegt.")
            demo_pruefungen()
            return
        produkt = {p["model"]: p["id"] for p in db.query("SELECT id, model FROM mat_product WHERE demo = 1")}
        gl = bestand.ordner_anlegen({"name": "DEMO-Gliederung", "kind": "gliederung",
                                     "description": HINWEIS}, demo=True)
        lager = bestand.ordner_anlegen({"name": "DEMO-Lager", "kind": "standort", "parent_id": gl}, demo=True)
        fahrzeug = bestand.ordner_anlegen({"name": "DEMO-Fahrzeug", "kind": "fahrzeug", "parent_id": gl,
                                           "interval_months": 6, "description": "Kürzeres Intervall als Beispiel"}, demo=True)
        rucksack = bestand.ordner_anlegen({"name": "DEMO-Seilrucksack", "kind": "set", "parent_id": fahrzeug}, demo=True)
        h = date.today()
        artikel = [
            ("DEMO Gurt A", lager, {"manufactured_on": f"{h.year - 2}-03", "first_use_on": (h - timedelta(days=200)).isoformat()}),
            ("DEMO Gurt A", lager, {"manufactured_on": f"{h.year - 11}-05", "serial_no": "DEMO-ALT-1"}),          # Lebensdauer erreicht
            ("DEMO Gurt A", rucksack, {"manufactured_on": f"{h.year - 1}-01", "first_use_on": (h - timedelta(days=170)).isoformat()}),
            ("DEMO Statikseil 11 mm", rucksack, {"manufactured_on": f"{h.year - 3}-09",
                                                  "purchased_on": (h - timedelta(days=500)).isoformat()}),  # überfällig
            ("DEMO HMS-Karabiner", rucksack, {"first_use_on": (h - timedelta(days=350)).isoformat()}),      # bald fällig
            ("DEMO HMS-Karabiner", rucksack, {}),
            ("DEMO HMS-Karabiner", lager, {"serial_no": "DEMO-K-0815"}),
            ("DEMO Helm", fahrzeug, {"manufactured_on": f"{h.year - 4}-06"}),
            ("DEMO Rettungsweste", fahrzeug, {"first_use_on": (h - timedelta(days=20)).isoformat()}),
        ]
        for modell, ordner_id, felder in artikel:
            bestand.artikel_anlegen(dict(felder, product_id=produkt[modell], folder_id=ordner_id,
                                         notes=HINWEIS))
        print(f"Bestand: {len(artikel)} Artikel in DEMO-Gliederung angelegt.")
        demo_pruefungen()


# Eingangsprüfungen für die Demo – zurückdatiert, damit jeder Status einmal vorkommt. Schlüssel: Modell und
# Seriennummer (None = der erste Artikel des Modells ohne eigene Nummer), Wert: (vor wie vielen Tagen, Ergebnis).
# Ein Artikel bleibt ohne Prüfung („neu“), der Helm ebenso – für ihn gibt es kein DEMO-Formular.
DEMO_PRUEFUNGEN = [
    ("DEMO Gurt A", 200, "einsatzbereit"),            # Lager: noch lange gültig
    ("DEMO Gurt A", 170, "einsatzbereit"),            # Seilrucksack (Fahrzeug, 6 Monate): bald fällig
    ("DEMO Statikseil 11 mm", 500, "einsatzbereit"),  # überfällig
    ("DEMO HMS-Karabiner", 30, "instandsetzen"),      # gesperrt
    ("DEMO HMS-Karabiner", 0, "einsatzbereit"),       # das Exemplar DEMO-K-0815
    ("DEMO Rettungsweste", 20, "einsatzbereit"),
]


def demo_pruefungen():
    """DEMO-Eingangsprüfungen – einmal: Gibt es schon eine Prüfung an einem DEMO-Artikel, bleibt alles, wie es
    ist (ein Bestand aus Lieferung 1 bekommt sie beim nächsten Lauf nachgereicht)."""
    from app import db
    from app.material.services import pruefung
    if db.query("SELECT 1 FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON "
                "p.id = i.product_id WHERE p.demo = 1 LIMIT 1", one=True):
        print("DEMO-Prüfungen sind schon da – nichts weiter angelegt.")
        return
    pruefer = {"id": None, "name": "DEMO-Prüfer", "urkunde": "DEMO"}
    offen = db.query("SELECT i.id, i.serial_no, i.retire_by, p.model FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
                     "WHERE p.demo = 1 AND i.lock_state = 'frei' AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE "
                     "x.item_id = i.id) ORDER BY i.id")
    h = date.today()
    angelegt = 0
    for modell, tage, ergebnis in DEMO_PRUEFUNGEN:
        kandidaten = [i for i in offen if i["model"] == modell and not (i["retire_by"] and i["retire_by"] <= h.isoformat())]
        if not kandidaten:
            continue
        i = next((x for x in kandidaten if x["serial_no"] == "DEMO-K-0815"), None) if tage == 0 else None
        i = i or next(x for x in kandidaten if x["serial_no"] != "DEMO-K-0815")
        offen.remove(i)
        pid, _ = pruefung.starten(i["id"], pruefer)
        d = {"ergebnis": ergebnis, "bemerkung": HINWEIS}
        if ergebnis != "einsatzbereit":
            d["grund"] = "DEMO: Verschluss schließt schwer (Platzhalter)"
        pruefung.abschliessen(pid, d, pruefer, pruefdatum=h - timedelta(days=tage))
        angelegt += 1
    print(f"Prüfungen: {angelegt} DEMO-Eingangsprüfungen angelegt.")


if __name__ == "__main__":
    main()
