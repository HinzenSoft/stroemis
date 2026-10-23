"""Demodaten für das Modul Material – NUR für Entwicklung und Tests, nie für echte Prüfungen.

Eigenständiges Werkzeug außerhalb von app/ (wie scripts/beispieldaten.py): Es läuft nie im
Docker-Image mit, denn das Dockerfile kopiert nur app/. Geladen wird nur mit ausdrücklichem Schalter:

    python scripts/material_demo.py --demo [--konten]

Ohne Angabe landen die Daten wie bei run.py in ./data; für eine andere Datenbank vorher DATA_DIR setzen.
Seit Phase 2 gibt es eine zweite Gliederung („DEMO-Gliederung Nachbarstadt“ mit „DEMO-Lager NS“) – zum Ausprobieren
der Trennung je Gliederung und der globalen Suche (Seriennummer DEMO-NS-4711); sie kommt auch zu einem vorhandenen
Demo-Bestand dazu. --konten legt einmalig fünf DEMO-Konten mit Namen, zufälligem Passwort (wird einmal ausgedruckt),
Stufe im Modul Material und Freigaben an: zwei Materialwarte (je Gliederung), einen Prüfer (lesen und prüfen in der
DEMO-Gliederung, beides dauerhaft) und einen externen Prüfer (nur prüfen im DEMO-Lager, befristet) – alle mit Stufe
Mitglied – sowie die DEMO-Material-Verwaltung (Stufe Verwaltung, keine Plattform-Verwaltung, keine Freigaben: Katalog
pflegen, alle Bestände, Gliederungen anlegen). Sonst haben die Konten die Vorgabe neuer Konten. Nur für dev. Stammt
der DEMO-Prüfer noch aus der Zeit, als auch er befristet prüfte, stellt --konten seine DEMO-Prüffreigabe auf dauerhaft
(siehe demo_konten).
Seit Phase 4 · Lieferung 2 (Hersteller-Sets) gibt es dazu ein DEMO-Set-Produkt („DEMO Verbindungsmittel-Set“) mit
Stückliste aus DEMO-Bestandteilen (zwei einzeln geführte DEMO HMS-Karabiner, eine DEMO-Tasche als Bestandteil ohne
eigenen Artikel) und im DEMO-Lager einen DEMO-Set-Artikel mit seinen beiden Teilen (DEMO-SET-1 mit DEMO-SET-K1 und
DEMO-SET-K2) – auch zu einem vorhandenen Demo-Bestand, einmal (demo_set). Keine echten Herstellerdaten: Hersteller,
Lebensdauer, Intervall und Stückliste sind Platzhalter.
Alles, was das Skript anlegt, trägt das Kennzeichen demo und „DEMO“ im Namen – die Oberfläche zeigt
es überall als „DEMO – nicht für echte Prüfungen“. Prüfpunkte, Intervalle, Lebensdauern und Hersteller
sind Platzhalter: Der echte Katalog entsteht in Phase 0 mit den Sachkundigen und kommt über
`flask material import-catalog` ins System. Die Normen je Kategorie stammen aus den DLRG
Standardverfahren Grundlagen V1.9.
"""
import os
import sys
from datetime import timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.environ.setdefault("DATA_DIR", os.path.join(REPO_ROOT, "data"))
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("VIDEOPFLEGE", "0")

HINWEIS = "DEMO – nicht für echte Prüfungen"
GLIEDERUNG = "DEMO-Gliederung"
LAGER = "DEMO-Lager"
NACHBARSTADT = "DEMO-Gliederung Nachbarstadt"
LAGER_NS = "DEMO-Lager NS"
# --konten: E-Mail, Name, Gliederung (Freitext im Profil), Stufe im Modul Material (1 Mitglied, 2 Verwaltung),
# Urkundennummer (mit Häkchen „Prüfer“) oder None und die Freigaben als (Ordner, Recht, Tage bis zum Ende – None heißt
# dauerhaft). Befristet ist nur der externe Prüfer (seit
# der Nachbesserung vom 18.10.2026); seine Prüffreigabe läuft kurz, damit der Hinweis „läuft bald ab“ und das
# Verlängern zu sehen sind. Der interne Prüfer prüft dauerhaft – er hat dort lesen.
DEMO_KONTEN = [
    ("demo-wart-a@example.invalid", "DEMO-Materialwart A", GLIEDERUNG, 1, None, [(GLIEDERUNG, "verwalten", None)]),
    ("demo-wart-b@example.invalid", "DEMO-Materialwart B", NACHBARSTADT, 1, None, [(NACHBARSTADT, "verwalten", None)]),
    ("demo-pruefer@example.invalid", "DEMO-Prüfer", GLIEDERUNG, 1, "DEMO-1012",
     [(GLIEDERUNG, "lesen", None), (GLIEDERUNG, "pruefen", None)]),
    ("demo-extern@example.invalid", "DEMO-Prüfer extern", "DEMO-extern", 1, "DEMO-2024", [(LAGER, "pruefen", 30)]),
    ("demo-mv@example.invalid", "DEMO-Material-Verwaltung", "DEMO", 2, None, []),
]


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
            {"name": "DEMO Kletterhelme", "norm": "EN 12492", "materialart": "sonstiges", "intervall_monate": 12},
            # Phase 4 · L2: Hersteller-Sets – Kategorie, Norm und Intervall sind Platzhalter.
            {"name": "DEMO Verbindungsmittel-Sets", "norm": "DEMO-Norm (Platzhalter)", "materialart": "textil",
             "intervall_monate": 12}]},
        {"name": "DEMO Wasserrettung", "unterkategorien": [
            {"name": "DEMO Schwimmhilfen", "norm": "EN 12402-5, Panikverschluss, mindestens 50 N",
             "materialart": "sonstiges", "intervall_monate": 12},
            {"name": "DEMO Wassersporthelme", "norm": "EN 1385", "materialart": "sonstiges", "intervall_monate": 12}]},
    ],
    # Die Beschreibung ist ein kurzer Zusatz hinter dem Namen (grau dahinter, etwa die Verschlussart). Die
    # DEMO-Produkte haben keine: Den Hinweis trägt die DEMO-Marke, als Zusatz stünde er doppelt („DEMO Gurt A | DEMO –
    # nicht für echte Prüfungen“, Prüfung der Nachbesserung vom 18.10.2026). Der Leerwert steht ausdrücklich da – so
    # leert ein neuer Lauf auch die Beschreibung aus einem älteren DEMO-Katalog.
    "produkte": [
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Gurte"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Gurt A", "artikelnummer": "DEMO-G-100", "materialart": "textil", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": ""},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Statikseile"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Statikseil 11 mm", "artikelnummer": "DEMO-S-11", "materialart": "textil", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": ""},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO HMS-Karabiner"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO HMS-Karabiner", "artikelnummer": "DEMO-K-1", "materialart": "metall_hardware",
         "beschreibung": ""},
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Kletterhelme"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Helm", "artikelnummer": "DEMO-H-1", "materialart": "sonstiges", "lebensdauer_jahre": 10,
         "lebensdauer_quelle": "Platzhalter", "beschreibung": ""},
        {"kategorie": ["DEMO Wasserrettung", "DEMO Schwimmhilfen"], "hersteller": "DEMO-Hersteller",
         "modell": "DEMO Rettungsweste", "artikelnummer": "DEMO-W-1", "materialart": "sonstiges", "beschreibung": ""},
        # Hersteller-Set (Phase 4 · L2): Stückliste aus DEMO-Bestandteilen – zwei einzeln geführte DEMO HMS-Karabiner
        # (je ein Teil-Artikel) und eine Tasche ohne eigenen Artikel. Alles Platzhalter.
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Verbindungsmittel-Sets"],
         "hersteller": "DEMO-Hersteller", "modell": "DEMO Verbindungsmittel-Set", "artikelnummer": "DEMO-VS-1",
         "materialart": "textil", "lebensdauer_jahre": 10, "lebensdauer_quelle": "Platzhalter", "beschreibung": "",
         "set": True, "bestandteile": [
             {"produkt": {"hersteller": "DEMO-Hersteller", "modell": "DEMO HMS-Karabiner", "artikelnummer": "DEMO-K-1"},
              "bezeichnung": "DEMO-Verbindungselement (Platzhalter)", "anzahl": 2, "einzeln": True,
              "austausch": "nicht_belegt"},
             {"bezeichnung": "DEMO-Tasche (Platzhalter)", "anzahl": 1, "einzeln": False, "austausch": "nicht_belegt"}]},
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
        {"kategorie": ["DEMO PSA gegen Absturz und Seiltechnik", "DEMO Verbindungsmittel-Sets"],
         "titel": "DEMO-Formular Verbindungsmittel-Sets", "punkte": _punkte(3)},
    ],
}


def main():
    if "--demo" not in sys.argv[1:]:
        print(__doc__)
        print("Abgebrochen: Demodaten werden nur mit dem Schalter --demo geladen.")
        sys.exit(2)
    konten = "--konten" in sys.argv[1:]
    from flask import g

    from app import create_app, db
    from app.material.services import importer

    app = create_app()
    with app.app_context():
        bericht = importer.importieren(KATALOG, quelle="Demodaten")
        if bericht["fehler"]:
            for f in bericht["fehler"]:
                print("FEHLER", f)
            sys.exit(1)
        print("Katalog:", {k: v for k, v in bericht.items() if k in ("kategorien", "produkte", "formulare")})
        g.mat_akteur = "Demodaten"
        produkt = {p["model"]: p["id"] for p in db.query("SELECT id, model FROM mat_product WHERE demo = 1")}
        # Die erste Gliederung: jede DEMO-Gliederung auf oberster Ebene außer der Nachbarstadt (Phase 2).
        if db.query("SELECT 1 FROM mat_folder WHERE demo = 1 AND parent_id IS NULL AND name <> ? LIMIT 1", (NACHBARSTADT,),
                    one=True):
            print("Demo-Bestand ist schon da – dort nichts weiter angelegt.")
            demo_pruefungen()
            demo_protokolle_nachreichen()
        else:
            demo_bestand(produkt)
            demo_pruefungen()
        demo_set(produkt)
        demo_nachbarstadt(produkt)
        if konten:
            demo_konten()


def demo_bestand(produkt):
    """Die DEMO-Gliederung mit Lager, Fahrzeug und Seilrucksack und neun Artikeln – jeder Status kommt einmal vor."""
    from app.material.services import bestand, heute
    gl = bestand.ordner_anlegen({"name": GLIEDERUNG, "kind": "gliederung",
                                 "description": HINWEIS}, demo=True)
    lager = bestand.ordner_anlegen({"name": LAGER, "kind": "standort", "parent_id": gl}, demo=True)
    fahrzeug = bestand.ordner_anlegen({"name": "DEMO-Fahrzeug", "kind": "fahrzeug", "parent_id": gl,
                                       "interval_months": 6, "description": "Kürzeres Intervall als Beispiel"}, demo=True)
    rucksack = bestand.ordner_anlegen({"name": "DEMO-Seilrucksack", "kind": "set", "parent_id": fahrzeug}, demo=True)
    h = heute()                      # Kalendertag in Deutschland, wie überall im Modul
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


def demo_set(produkt):
    """Phase 4 · L2: ein DEMO-Set-Artikel mit seinen Teilen im DEMO-Lager – über denselben Weg wie „Artikel anlegen“
    (bestand.anlegen, Teile aus der Stückliste). Gibt es schon einen Artikel des DEMO-Set-Produkts oder fehlt das Lager,
    bleibt alles, wie es ist."""
    from app import db
    from app.material.services import bestand, heute, stueckliste
    pid = produkt.get("DEMO Verbindungsmittel-Set")
    lager = _demo_ordner(LAGER, _demo_ordner(GLIEDERUNG))
    if not pid or not lager or db.query("SELECT 1 FROM mat_item WHERE product_id = ? LIMIT 1", (pid,), one=True):
        print("DEMO-Set ist schon da (oder das DEMO-Lager fehlt) – nichts weiter angelegt.")
        return
    serien = iter(("DEMO-SET-K1", "DEMO-SET-K2"))
    teile = [{"bestandteil_id": z["id"], "serial_no": next(serien, "")}
             for z in stueckliste.zeilen(pid) if z["einzeln"] for _ in range(z["anzahl"])]
    h = heute()
    sid, _ = bestand.anlegen({"product_id": pid, "folder_id": lager, "serial_no": "DEMO-SET-1",
                              "manufactured_on": f"{h.year - 1}-02", "notes": HINWEIS, "teile": teile})
    n = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE parent_item_id = ?", (sid,), one=True)["n"]
    print(f"Bestand: DEMO-Set mit {n} Teilen im {LAGER} angelegt.")


def _demo_ordner(name, parent=None):
    """Ein DEMO-Ordner nach Namen – auf oberster Ebene oder direkt unter parent; None, wenn es ihn nicht gibt."""
    from app import db
    if parent is None:
        r = db.query("SELECT id FROM mat_folder WHERE demo = 1 AND parent_id IS NULL AND name = ? ORDER BY id LIMIT 1",
                     (name,), one=True)
    else:
        r = db.query("SELECT id FROM mat_folder WHERE demo = 1 AND parent_id = ? AND name = ? ORDER BY id LIMIT 1",
                     (parent, name), one=True)
    return r["id"] if r else None


def demo_nachbarstadt(produkt):
    """Phase 2: eine zweite Gliederung mit eigenem Lager und drei Artikeln – einer davon mit der Seriennummer
    DEMO-NS-4711, nach der die globale Suche aus der DEMO-Gliederung heraus fragen kann. Fehlt sie, kommt sie dazu,
    auch zu einem vorhandenen Demo-Bestand; sonst bleibt alles, wie es ist."""
    from app.material.services import bestand, heute
    if _demo_ordner(NACHBARSTADT):
        print(f"{NACHBARSTADT} ist schon da – nichts weiter angelegt.")
        return
    gl = bestand.ordner_anlegen({"name": NACHBARSTADT, "kind": "gliederung", "description": HINWEIS}, demo=True)
    lager = bestand.ordner_anlegen({"name": LAGER_NS, "kind": "standort", "parent_id": gl}, demo=True)
    h = heute()
    artikel = [
        ("DEMO Gurt A", {"manufactured_on": f"{h.year - 1}-04", "first_use_on": (h - timedelta(days=90)).isoformat()}),
        ("DEMO HMS-Karabiner", {"serial_no": "DEMO-NS-4711"}),
        ("DEMO Rettungsweste", {"first_use_on": (h - timedelta(days=60)).isoformat()}),
    ]
    for modell, felder in artikel:
        bestand.artikel_anlegen(dict(felder, product_id=produkt[modell], folder_id=lager, notes=HINWEIS))
    print(f"Bestand: {len(artikel)} Artikel in {NACHBARSTADT} angelegt.")


def _demo_ziel(ordner):
    """Der DEMO-Ordner einer Freigabe aus DEMO_KONTEN (das DEMO-Lager unter der DEMO-Gliederung) oder None."""
    return _demo_ordner(ordner) if ordner != LAGER else _demo_ordner(LAGER, _demo_ordner(GLIEDERUNG))


def demo_konten():
    """--konten: die DEMO-Konten aus DEMO_KONTEN – je einmalig, mit Namen, zufälligem Passwort (nur hier, einmal
    ausgedruckt) und ihren Freigaben (Journal am Ordner unter „Demodaten“, das Konto pseudonym). Gibt es ein Konto
    schon, bleibt es samt Passwort und Freigaben, wie es ist – bis auf eine DEMO-Prüffreigabe, die DEMO_KONTEN jetzt
    dauerhaft vorsieht (_demo_pruefen_dauerhaft)."""
    import secrets

    from werkzeug.security import generate_password_hash

    from app import db
    from app.auth import MODULE, VORGABE_NEU
    from app.material.services import heute, journal
    for mail, name, gliederung, stufe, urkunde, freigaben in DEMO_KONTEN:
        konto = db.query("SELECT * FROM users WHERE email = ?", (mail,), one=True)
        if konto:
            dauerhaft = _demo_pruefen_dauerhaft(konto, freigaben)
            print(f"Konto {mail} ist schon da – " + (
                f"Prüffreigabe {', '.join(dauerhaft)} jetzt dauerhaft (befristet nur noch der externe Prüfer), sonst "
                "unverändert." if dauerhaft else "unverändert."))
            continue
        ziele, fehlt = [], None
        for ordner, recht, tage in freigaben:
            fid = _demo_ziel(ordner)
            if not fid:
                fehlt = ordner
                break
            ziele.append((fid, ordner, recht, (heute() + timedelta(days=tage)).isoformat() if tage else None))
        if fehlt:
            print(f"Konto {mail} nicht angelegt: Ordner „{fehlt}“ fehlt (umbenannt oder gelöscht?).")
            continue
        passwort = secrets.token_urlsafe(12)
        # Die Vorgabe neuer Konten (Mitglied im Modul Material, sonst nichts) – Material mit der Stufe aus DEMO_KONTEN.
        stufen = dict(VORGABE_NEU, material=stufe)
        with db.transaction():
            uid = db.execute("INSERT INTO users (email, password_hash, name, gliederung, mat_pruefer, urkundennummer, "
                             f"{', '.join(f'recht_{m}' for m in MODULE)}, created_at) "
                             f"VALUES (?,?,?,?,?,?,{','.join('?' * len(MODULE))},?)",
                             (mail, generate_password_hash(passwort), name, gliederung, int(bool(urkunde)), urkunde or "",
                              *(stufen[m] for m in MODULE), db.now()))
            rollen = {"recht_material": stufe, "mat_pruefer": int(bool(urkunde))}
            if urkunde:
                rollen["urkundennummer"] = urkunde
            journal.eintragen("user", uid, "rollen", None, rollen)
            for fid, _, recht, bis in ziele:
                gid = db.execute("INSERT INTO mat_folder_grant (folder_id, user_id, permission, valid_until, granted_by, "
                                 "created_at, note) VALUES (?,?,?,?,NULL,?,?)", (fid, uid, recht, bis, db.now(), "DEMO"))
                journal.eintragen("folder", fid, "freigabe_erteilt", None,
                                  {"freigabe": gid, "konto": journal.konto_ref(uid), "recht": recht, "bis": bis})
        rechte = ", ".join(f"{recht} {ordner}" + (f" bis {bis}" if bis else " dauerhaft") for _, ordner, recht, bis in ziele)
        print(f"Konto {mail} ({name}) angelegt – Passwort: {passwort} (wird nicht erneut angezeigt). Material: "
              f"{'Verwaltung' if stufe == 2 else 'Mitglied'}. Freigaben: {rechte or 'keine'}.")


def _demo_pruefen_dauerhaft(konto, freigaben):
    """Seit der Nachbesserung vom 18.10.2026 prüft der interne DEMO-Prüfer dauerhaft. Hat ein früherer Lauf (etwa auf
    dev) seine DEMO-Prüffreigabe noch befristet angelegt, wird sie dauerhaft – wie Migration Schritt 9 es mit den
    Prüffreigaben aus Phase 1 macht: nur Zeilen, die die Demodaten selbst angelegt haben (Notiz „DEMO“, ohne
    vergebendes Konto, Journal „Demodaten“) und die seitdem niemand geändert hat (kein updated_at, kein „geändert“ im
    Journal), und nur, wo DEMO_KONTEN sie dauerhaft vorsieht und das Konto dort ein Grundrecht hat. Je Zeile ein
    Journaleintrag unter „Demodaten“. Liefert die Ordner der umgestellten Freigaben."""
    from app import db
    from app.material.services import journal, rechte
    out = []
    for ordner, recht, tage in freigaben:
        fid = _demo_ziel(ordner) if recht == "pruefen" and tage is None else None
        if not fid or not rechte.grundrecht_an(konto, fid):
            continue
        r = db.query(
            "SELECT * FROM mat_folder_grant g WHERE g.folder_id = ? AND g.user_id = ? AND g.permission = 'pruefen' "
            "AND g.valid_until IS NOT NULL AND g.granted_by IS NULL AND g.note = 'DEMO' AND g.updated_at IS NULL "
            "AND EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'folder' AND a.entity_id = g.folder_id "
            "AND a.action = 'freigabe_erteilt' AND a.user_id IS NULL AND a.user_name = 'Demodaten' "
            "AND json_extract(a.after_json, '$.freigabe') = g.id) "
            "AND NOT EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'folder' AND a.entity_id = g.folder_id "
            "AND a.action = 'freigabe_geaendert' AND json_extract(a.after_json, '$.freigabe') = g.id)",
            (fid, konto["id"]), one=True)
        if not r:
            continue
        with db.transaction():
            spur = {"freigabe": r["id"], "konto": journal.konto_ref(konto["id"]), "recht": "pruefen"}
            db.execute("UPDATE mat_folder_grant SET valid_until = NULL, updated_at = ? WHERE id = ?", (db.now(), r["id"]))
            journal.eintragen("folder", fid, "freigabe_geaendert", dict(spur, bis=r["valid_until"]),
                              dict(spur, bis=None, grund="nur externe Prüfer befristet"))
        out.append(ordner)
    return out


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
    from app.material.services import heute, pruefung
    if db.query("SELECT 1 FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON "
                "p.id = i.product_id WHERE p.demo = 1 LIMIT 1", one=True):
        print("DEMO-Prüfungen sind schon da – nichts weiter angelegt.")
        return
    pruefer = demo_pruefer()
    offen = db.query("SELECT i.id, i.serial_no, i.retire_by, p.model FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
                     "WHERE p.demo = 1 AND i.lock_state = 'frei' AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE "
                     "x.item_id = i.id) ORDER BY i.id")
    h = heute()
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
    print(f"Prüfungen: {angelegt} DEMO-Eingangsprüfungen angelegt und festgeschrieben.")


def demo_unterschrift():
    """Eine gezeichnete Platzhalter-Unterschrift mit „DEMO“ – als PNG, wie es das Signatur-Pad liefert, und durch
    dieselbe Prüfung wie jede echte Unterschrift (unterschrift.lesen)."""
    import base64
    import io
    import math

    from PIL import Image, ImageDraw

    from app.material.services import unterschrift
    bild = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    zeichnen = ImageDraw.Draw(bild)
    punkte = [(30 + x, 110 + 35 * math.sin(x / 22.0) * math.exp(-x / 500.0)) for x in range(0, 540, 4)]
    zeichnen.line(punkte, fill=(20, 40, 110, 255), width=5, joint="curve")
    zeichnen.text((40, 150), "DEMO – keine echte Unterschrift", fill=(20, 40, 110, 255))
    puffer = io.BytesIO()
    bild.save(puffer, "PNG")
    return unterschrift.lesen(unterschrift.VORSATZ + base64.b64encode(puffer.getvalue()).decode())


def demo_pruefer():
    """Der Prüfer der Demodaten – ohne Konto, mit DEMO-Urkundennummer und DEMO-Unterschrift."""
    return {"id": None, "name": "DEMO-Prüfer", "urkunde": "DEMO", "unterschrift": demo_unterschrift(),
            "login": "Demodaten"}


def demo_protokolle_nachreichen():
    """Ein DEMO-Bestand aus Lieferung 2 hat abgeschlossene, aber nicht festgeschriebene Prüfungen. Die des
    DEMO-Prüfers bekommen hier ihr Protokoll (mit DEMO-Unterschrift); Prüfungen, die jemand auf dev selbst gemacht
    hat – auch an DEMO-Artikeln –, und echte Prüfungen bleiben, wie sie sind."""
    from app import db
    from app.material.services import protokoll
    offen = db.query("SELECT x.id, x.item_id, i.lock_state, i.folder_id, i.origin_folder_id FROM mat_inspection x "
                     "JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON p.id = i.product_id "
                     "WHERE p.demo = 1 AND x.inspector_user_id IS NULL AND x.inspector_name = 'DEMO-Prüfer' "
                     "AND x.completed_at IS NOT NULL AND x.locked_at IS NULL ORDER BY x.id")
    if not offen:
        return
    pruefer = demo_pruefer()
    for x in offen:
        with protokoll.dateien_sichern(), db.transaction(sofort=True):
            protokoll.pruefung_festschreiben(x["id"], db.now(), pruefer["unterschrift"], pruefer["login"],
                                             _ordner_damals(x))
    print(f"Protokolle: {len(offen)} DEMO-Prüfungen nachträglich festgeschrieben.")


def _ordner_damals(x):
    """Der Ordner des Artikels zur Zeit der Prüfung – aus dem Journal des Artikels: der zuletzt eingetragene Ordner
    vor (bzw. mit) dem Eintrag zu dieser Prüfung; vor einer Sperre aus der Prüfung der Ordner davor. Unbekannt:
    None (dann bleibt die Zeile im Protokoll leer, statt einen späteren Ordner zu nennen)."""
    import json

    from app import db
    ordner = None
    for e in db.query("SELECT action, before_json, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                      "ORDER BY id", (x["item_id"],)):
        nachher = json.loads(e["after_json"] or "{}")
        if nachher.get("pruefung") == x["id"]:
            if e["action"] == "gesperrt":
                return json.loads(e["before_json"] or "{}").get("folder_id") or ordner
            return nachher.get("folder_id") or ordner
        if nachher.get("folder_id"):
            ordner = nachher["folder_id"]
    return None


if __name__ == "__main__":
    main()
