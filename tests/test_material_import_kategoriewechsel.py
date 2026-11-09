"""Katalogimport: Warnung, wenn Produkte die Kategorie wechseln (Wunsch des Nutzers vom 09.11.2026, Bauauftrag
planung/import-warnung-kategorie/auftrag.md) – ohne Browser:
python tests/test_material_import_kategoriewechsel.py  oder  pytest tests/test_material_import_kategoriewechsel.py

Anlass: Eine alte Katalog-ZIP (Kategorien am Namen erkannt) legt nach dem Umbenennen die alte Kategorie neu an und
schiebt ihre Produkte dorthin zurück. Der Import verhält sich weiter so; er meldet es nur: je Produkt mit Artikeln eine
Warnung (alte → neue Kategorie, Zahl der Artikel, was aus dem geltenden Prüfformular wird), oben im Bericht eine
Zusammenfassung samt Hinweis auf eine alte Datei, gelöste Produkt-Zuweisungen unter „zuweisungen“ → „geloest“ – im
Probelauf, im echten Lauf und auf der Kommandozeile. Alle Namen, Hersteller und Prüfpunkte sind erfunden."""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import formular_neu, gliederung, umgebung  # noqa: E402
from test_material_katalog import importieren  # noqa: E402

PUNKT = [{"text": "Testpunkt", "art": "yesno", "soll": "ja"}]


def _datei(produkte, kategorien):
    """Eine Datei wie die Katalogserie (Format 2, ohne uid, nur JSON). produkte: (Modell, Kategoriepfad)."""
    return json.dumps({"format": "stroemis-material-katalog", "version": 2, "kategorien": kategorien, "produkte": [
        {"kategorie": list(pfad), "hersteller": "Testwerk", "modell": modell, "artikelnummer": f"T-{i}",
         "materialart": "textil", "lebensdauer_jahre": 10, "lebensdauer_quelle": "Testquelle S. 1"}
        for i, (modell, pfad) in enumerate(produkte)]}, ensure_ascii=False).encode()


def _kat(name, *unter):
    return {"name": name, "materialart": "textil", "intervall_monate": 12, "unterkategorien": list(unter)}


def _ids(app, tabelle, spalte, werte):
    from app import db
    with app.app_context():
        return [db.query(f"SELECT id FROM {tabelle} WHERE {spalte} = ?", (w,), one=True)["id"] for w in werte]


def _artikel(w, pid, gid, n=1):
    out = []
    for _ in range(n):
        r = w.post("/api/material/artikel", json={"product_id": pid, "folder_id": gid, "manufactured_on": "2025-01"})
        assert r.status_code == 201, r.get_json()
        out.append(r.json["artikel"]["id"])
    return out


def _stand(app):
    from app import db
    with app.app_context():
        return {t: db.query(f"SELECT * FROM {t} ORDER BY id") for t in (
            "mat_category", "mat_product", "mat_formular_zuweisung", "mat_formular", "mat_form", "mat_item")}


SCHLINGEN, ALT, ANDERE = ("PSA (Test)", "Schlingen (Test)"), ("PSA (Test)", "Alt (Test)"), ("PSA (Test)", "Andere (Test)")
MODELLE = ("Delta", "Epsilon", "Zeta", "Eta", "Theta")


def _vorbereiten(tmp):
    """Katalog wie die neue Serie: „PSA (Test)“ mit „Schlingen (Test)“ (Standard „Schlingen-Prüfung“) und „Andere
    (Test)“ (Standard „Andere-Prüfung“). Delta (2 Artikel, einer davon ausgesondert, dazu einer mehr), Epsilon (1 Artikel,
    eigene Zuweisung), Zeta (ohne Artikel, eigene Zuweisung), Eta (1 Artikel) und Theta (1 Artikel) in „Schlingen (Test)“."""
    app, k = umgebung(tmp)
    kp, w = k["katalog"], k["wart"]
    neu = _datei([(m, SCHLINGEN) for m in MODELLE], [_kat("PSA (Test)", _kat("Schlingen (Test)"), _kat("Andere (Test)"))])
    ber = importieren(kp, neu, False, name="serie-neu.json")
    assert ber["gespeichert"] and ber["produkte"]["neu"] == 5 and ber["kategoriewechsel"] is None, ber
    schlingen, andere = _ids(app, "mat_category", "name", ("Schlingen (Test)", "Andere (Test)"))
    p = dict(zip(MODELLE, _ids(app, "mat_product", "model", MODELLE)))
    formular_neu(kp, {"kategorie_id": schlingen}, "Schlingen-Prüfung (Test)", PUNKT)
    formular_neu(kp, {"kategorie_id": andere}, "Andere-Prüfung (Test)", PUNKT)
    formular_neu(kp, {"produkt_id": p["Epsilon"]}, "Epsilon-Prüfung (Test)", PUNKT)
    formular_neu(kp, {"produkt_id": p["Zeta"]}, "Zeta-Prüfung (Test)", PUNKT)
    gid, _ = gliederung(w, "OG Testdorf")
    delta = _artikel(w, p["Delta"], gid, 3)
    for m in ("Epsilon", "Eta", "Theta"):
        _artikel(w, p[m], gid)
    # Ein ausgesonderter Artikel zählt nicht mit (wie bei den übrigen Folgen-Warnungen).
    with sqlite3.connect(os.path.join(tmp, "stroemis.db")) as conn:
        conn.execute("UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (delta[2],))
    return app, k, p, neu


# Die alte Datei: Delta, Epsilon und Zeta in die neue Kategorie „Alt (Test)“ (wie „Textilmaterial“ nach dem Umbenennen),
# Eta in die bestehende „Andere (Test)“, Theta bleibt.
ALTE_DATEI = _datei([("Delta", ALT), ("Epsilon", ALT), ("Zeta", ALT), ("Eta", ANDERE), ("Theta", SCHLINGEN)],
                    [_kat("PSA (Test)", _kat("Alt (Test)"), _kat("Schlingen (Test)"), _kat("Andere (Test)"))])

# Seit dem Feinschliff (Prüfung Browser r3, Verbesserungen 1 und 9): der gemeinsame Oberpfad einmal („unter …“), „im
# Bestand“ statt „hier“, der Titel einer gelösten eigenen Zuweisung nur einmal.
WARNUNGEN = [
    "produkte[0] (Testwerk Delta): Kategorie „Schlingen (Test)“ → „Alt (Test)“ (unter „PSA (Test)“) – betrifft 2 "
    "Artikel im Bestand; sie haben danach kein Prüfformular mehr (bisher „Schlingen-Prüfung (Test)“, Standard der "
    "Kategorie „Schlingen (Test)“) und lassen sich nicht prüfen.",
    "produkte[1] (Testwerk Epsilon): Kategorie „Schlingen (Test)“ → „Alt (Test)“ (unter „PSA (Test)“) – betrifft 1 "
    "Artikel im Bestand; die Zuweisung von „Epsilon-Prüfung (Test)“ an das Produkt wird gelöst; er hat danach kein "
    "Prüfformular mehr und lässt sich nicht prüfen.",
    "produkte[3] (Testwerk Eta): Kategorie „Schlingen (Test)“ → „Andere (Test)“ (unter „PSA (Test)“) – betrifft 1 "
    "Artikel im Bestand; künftig gilt „Andere-Prüfung (Test)“ (Standard der Kategorie „Andere (Test)“) statt "
    "„Schlingen-Prüfung (Test)“ (Standard der Kategorie „Schlingen (Test)“).",
]
# Nach dem Speichern als Ergebnis (Prüfung Browser r1, B2): „wurde gelöst“, „jetzt gilt“.
WARNUNGEN_GESPEICHERT = [WARNUNGEN[0], WARNUNGEN[1].replace("an das Produkt wird gelöst", "an das Produkt wurde gelöst"),
                         WARNUNGEN[2].replace("; künftig gilt", "; jetzt gilt")]
assert WARNUNGEN_GESPEICHERT != WARNUNGEN
ZAHLEN = {"produkte": 4, "mit_artikeln": 3, "artikel": 4, "ohne_formular": 3, "anderes_formular": 1,
          "zuweisungen_geloest": 2, "neue_kategorien": [{"kategorie": "PSA (Test) / Alt (Test)", "produkte": 3,
                                                         "aus": ["PSA (Test) / Schlingen (Test)"]}]}


def _zahlen(kw):
    return {s: kw[s] for s in ZAHLEN}


def _gruppen(fertig):
    """Die Gruppen der Oberfläche zur alten Datei (Prüfung Browser r3, Verbesserung 1): je alte → neue Kategorie eine Zeile
    mit Zahlen und Folge, aufklappbar je gleicher Folge die Einzelheiten – die Warnungen 0 und 1 bzw. 2 fassen sie zusammen."""
    def zeit(probe, ergebnis):
        return ergebnis if fertig else probe
    pfeil = "Kategorie „Schlingen (Test)“ → „{}“ (unter „PSA (Test)“)"
    return [
        {"zeile": pfeil.format("Alt (Test)") + " – 2 Produkte mit 3 Artikeln im Bestand; 3 Artikel "
                  + zeit("verlieren ihr Prüfformular", "haben ihr Prüfformular verloren") + ", 1 Produkt-Zuweisung "
                  + zeit("wird gelöst", "wurde gelöst") + ".",
         "folgen": [{"zeile": "2 Artikel (Testwerk Delta): sie haben danach kein Prüfformular mehr (bisher „Schlingen-"
                              "Prüfung (Test)“, Standard der Kategorie „Schlingen (Test)“) und lassen sich nicht prüfen.",
                     "einzeln": []},
                    {"zeile": "1 Artikel (Testwerk Epsilon): die Zuweisung von „Epsilon-Prüfung (Test)“ an das Produkt "
                              + zeit("wird gelöst", "wurde gelöst") + "; er hat danach kein Prüfformular mehr und lässt "
                              "sich nicht prüfen.", "einzeln": []}],
         "warnungen": [0, 1]},
        {"zeile": pfeil.format("Andere (Test)") + " – Testwerk Eta mit 1 Artikel im Bestand; 1 Artikel "
                  + zeit("bekommt ein anderes Prüfformular", "hat ein anderes Prüfformular bekommen") + ".",
         "folgen": [{"zeile": "1 Artikel (Testwerk Eta): " + zeit("künftig gilt", "jetzt gilt") + " „Andere-Prüfung "
                              "(Test)“ (Standard der Kategorie „Andere (Test)“) statt „Schlingen-Prüfung (Test)“ (Standard "
                              "der Kategorie „Schlingen (Test)“).", "einzeln": []}],
         "warnungen": [2]}]


def test_alte_datei_probelauf_und_echter_lauf():
    """Probelauf: je Produkt mit Artikeln eine Warnung (Zeta ohne Artikel keine, Theta bleibt), Zusammenfassung mit
    Hinweis auf eine alte Datei, beide gelösten Produkt-Zuweisungen gezählt, nichts gespeichert. Echter Lauf: dasselbe,
    die Zusammenfassung als Ergebnis; die Zuweisungen sind gelöst. Ein zweiter Lauf meldet nichts mehr."""
    from app import db
    from app.material.services import katalog
    with tempfile.TemporaryDirectory() as tmp:
        app, k, p, neu = _vorbereiten(tmp)
        kp = k["katalog"]
        vorher = _stand(app)

        ber = importieren(kp, ALTE_DATEI, True, name="serie-alt.json")
        assert not ber["fehler"] and not ber["gespeichert"], ber
        assert ber["kategorien"]["neu"] == 1 and ber["produkte"]["geaendert"] == 4, ber
        assert ber["warnungen"] == WARNUNGEN, ber["warnungen"]
        assert ber["zuweisungen"] == {"neu": 0, "geloest": 2, "unveraendert": 0}, ber["zuweisungen"]
        kw = ber["kategoriewechsel"]
        assert _zahlen(kw) == ZAHLEN, kw
        assert kw["zusammenfassung"] == ("4 Produkte wechseln die Kategorie – davon 3 mit Artikeln im Bestand (4 "
                                         "Artikel); 3 Artikel verlieren ihr Prüfformular, 1 Artikel bekommt ein anderes "
                                         "Prüfformular, 2 Produkt-Zuweisungen werden gelöst."), kw
        assert kw["davon"] == "davon 2 durch Kategoriewechsel" and kw["verschiebung"] is None, kw
        assert kw["gruppen"] == _gruppen(False), kw["gruppen"]
        assert kw["alte_datei"] == ("Neu angelegt: „PSA (Test) / Alt (Test)“ nimmt 3 Produkte aus „PSA (Test) / "
                                    "Schlingen (Test)“ auf. Vielleicht ist die Datei älter und nennt eine Kategorie noch "
                                    "mit ihrem früheren Namen – dann nicht übernehmen, sondern eine aktuelle Datei "
                                    "nehmen."), kw
        # Die Zeile „geändert (Kategorie)“ bleibt – auch für Zeta ohne Artikel.
        assert "Produkt „Testwerk Zeta“: geändert (Kategorie)" in ber["aenderungen"], ber["aenderungen"]
        assert _stand(app) == vorher                                   # Probelauf: nichts gespeichert

        ber = importieren(kp, ALTE_DATEI, False, name="serie-alt.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["warnungen"] == WARNUNGEN_GESPEICHERT, ber["warnungen"]
        assert ber["zuweisungen"]["geloest"] == 2, ber["zuweisungen"]
        kw = ber["kategoriewechsel"]
        assert _zahlen(kw) == ZAHLEN, kw
        assert kw["zusammenfassung"] == ("4 Produkte haben die Kategorie gewechselt – davon 3 mit Artikeln im Bestand "
                                         "(4 Artikel); 3 Artikel haben ihr Prüfformular verloren, 1 Artikel hat ein "
                                         "anderes Prüfformular bekommen, 2 Produkt-Zuweisungen wurden gelöst."), kw
        assert kw["gruppen"] == _gruppen(True), kw["gruppen"]
        assert kw["alte_datei"].endswith("– dann jedes Produkt auf seiner Seite über „Bearbeiten“ (Feld „Kategorie“) "
                                         "zurückverschieben und seine Zuweisungen neu setzen."), kw
        with app.app_context():
            assert katalog.formular_fuer_produkt(p["Delta"]) is None and katalog.formular_fuer_produkt(p["Epsilon"]) is None
            assert katalog.formular_fuer_produkt(p["Eta"])["title"] == "Andere-Prüfung (Test)"
            assert katalog.formular_fuer_produkt(p["Theta"])["title"] == "Schlingen-Prüfung (Test)"
            assert not db.query("SELECT 1 FROM mat_formular_zuweisung WHERE product_id IN (?, ?)",
                                (p["Epsilon"], p["Zeta"]), one=True)
            for m in ("Epsilon", "Zeta"):
                j = db.query("SELECT after_json FROM mat_audit WHERE entity = 'product' AND entity_id = ? AND "
                             "action = 'formular_zuweisung_geloest'", (p[m],), one=True)
                assert j and "Produkt in eine andere Kategorie verschoben" in j["after_json"], (m, j)

        # Derselbe Lauf noch einmal: kein Wechsel mehr, keine Warnung, nichts gelöst.
        ber = importieren(kp, ALTE_DATEI, True, name="serie-alt.json")
        assert not ber["fehler"] and not ber["warnungen"] and ber["kategoriewechsel"] is None, ber
        assert ber["zuweisungen"]["geloest"] == 0, ber["zuweisungen"]
        # Zurück mit der neuen Serie: Wechsel in eine BESTEHENDE Kategorie – Warnungen, aber kein Hinweis auf eine alte
        # Datei; Delta bekommt wieder ein Prüfformular.
        ber = importieren(kp, neu, True, name="serie-neu.json")
        assert not ber["fehler"], ber
        kw = ber["kategoriewechsel"]
        assert kw["alte_datei"] is None and kw["neue_kategorien"] == [], kw
        assert (kw["produkte"], kw["mit_artikeln"], kw["ohne_formular"], kw["anderes_formular"]) == (4, 3, 0, 1), kw
        assert kw["zusammenfassung"] == ("4 Produkte wechseln die Kategorie – davon 3 mit Artikeln im Bestand (4 "
                                         "Artikel); 1 Artikel bekommt ein anderes Prüfformular."), kw
        assert ("produkte[0] (Testwerk Delta): Kategorie „Alt (Test)“ → „Schlingen (Test)“ (unter „PSA (Test)“) – "
                "betrifft 2 Artikel im Bestand; künftig gilt „Schlingen-Prüfung (Test)“ (Standard der Kategorie "
                "„Schlingen (Test)“), bisher keins.") in ber["warnungen"], ber["warnungen"]
    print("Alte Datei: Probelauf und echter Lauf bestanden.")


def test_gilt_weiter_und_ohne_formular():
    """Wechsel ohne Folgen für das Formular: Der Standard der Oberkategorie gilt weiter; ein Produkt ohne Formular
    bleibt ohne. Ein Produkt ohne Artikel bekommt keine Warnung, zählt aber in der Zusammenfassung mit."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp, w = k["katalog"], k["wart"]
        kategorien = [_kat("Ober (Test)", _kat("A (Test)"), _kat("B (Test)")), _kat("C (Test)"), _kat("D (Test)")]
        ber = importieren(kp, _datei([("Pi", ("Ober (Test)", "A (Test)")), ("Rho", ("Ober (Test)", "A (Test)")),
                                      ("Sigma", ("C (Test)",))], kategorien), False, name="eins.json")
        assert ber["gespeichert"], ber
        ober, = _ids(app, "mat_category", "name", ("Ober (Test)",))
        pi, sigma = _ids(app, "mat_product", "model", ("Pi", "Sigma"))
        formular_neu(kp, {"kategorie_id": ober}, "Ober-Prüfung (Test)", PUNKT)
        gid, _ = gliederung(w, "OG Testdorf")
        _artikel(w, pi, gid)
        _artikel(w, sigma, gid)
        ber = importieren(kp, _datei([("Pi", ("Ober (Test)", "B (Test)")), ("Rho", ("C (Test)",)),
                                      ("Sigma", ("D (Test)",))], kategorien), True, name="zwei.json")
        assert not ber["fehler"] and ber["zuweisungen"]["geloest"] == 0, ber
        assert ber["warnungen"] == [
            "produkte[0] (Testwerk Pi): Kategorie „A (Test)“ → „B (Test)“ (unter „Ober (Test)“) – betrifft 1 Artikel im "
            "Bestand; das Prüfformular „Ober-Prüfung (Test)“ gilt weiter (Standard der Kategorie „Ober (Test)“).",
            "produkte[2] (Testwerk Sigma): Kategorie „C (Test)“ → „D (Test)“ – betrifft 1 Artikel im Bestand; ein "
            "Prüfformular hat er weiterhin nicht."], ber["warnungen"]
        kw = ber["kategoriewechsel"]
        assert kw["zusammenfassung"] == ("3 Produkte wechseln die Kategorie – davon 2 mit Artikeln im Bestand (2 "
                                         "Artikel)."), kw
        assert kw["davon"] is None, kw
        assert kw["alte_datei"] is None, kw
        # Nur ein Produkt ohne Artikel wechselt in eine bestehende Kategorie: keine Warnung, keine Zusammenfassung.
        ber = importieren(kp, _datei([("Pi", ("Ober (Test)", "A (Test)")), ("Rho", ("D (Test)",)),
                                      ("Sigma", ("C (Test)",))], kategorien), False, name="drei.json")
        assert ber["gespeichert"], ber
        ber = importieren(kp, _datei([("Pi", ("Ober (Test)", "A (Test)")), ("Rho", ("C (Test)",)),
                                      ("Sigma", ("C (Test)",))], kategorien), True, name="vier.json")
        assert not ber["warnungen"], ber["warnungen"]
        kw = ber["kategoriewechsel"]
        assert (kw["produkte"], kw["mit_artikeln"], kw["zusammenfassung"], kw["alte_datei"]) == (1, 0, None, None), kw
        # Genau ein Produkt mit mehreren Artikeln (Prüfung Ablauf r1, Befund 1): „mit 2 Artikeln hier“.
        _artikel(w, pi, gid)
        fuenf = _datei([("Pi", ("Ober (Test)", "B (Test)")), ("Rho", ("D (Test)",)), ("Sigma", ("C (Test)",))], kategorien)
        for speichern, satz in ((False, "1 Produkt wechselt die Kategorie – mit 2 Artikeln im Bestand."),
                                (True, "1 Produkt hat die Kategorie gewechselt – mit 2 Artikeln im Bestand.")):
            ber = importieren(kp, fuenf, not speichern, name="fuenf.json")
            assert not ber["fehler"] and ber["gespeichert"] is speichern, ber
            assert ber["kategoriewechsel"]["zusammenfassung"] == satz, ber["kategoriewechsel"]
            assert ber["warnungen"] == [
                "produkte[0] (Testwerk Pi): Kategorie „A (Test)“ → „B (Test)“ (unter „Ober (Test)“) – betrifft 2 "
                "Artikel im Bestand; das Prüfformular „Ober-Prüfung (Test)“ gilt weiter (Standard der Kategorie „Ober "
                "(Test)“)."], ber["warnungen"]
    print("Gilt weiter und ohne Formular bestanden.")


def test_kommandozeile():
    """flask material import-catalog: Zusammenfassung und Hinweis als „ACHTUNG“, die Warnungen je Produkt, die gelösten
    Zuweisungen mit „davon … durch Kategoriewechsel“ – im Trockenlauf und im echten Lauf."""
    with tempfile.TemporaryDirectory() as tmp:
        app, _k, _p, _neu = _vorbereiten(tmp)
        datei = os.path.join(tmp, "serie-alt.json")
        with open(datei, "wb") as fh:
            fh.write(ALTE_DATEI)
        for zusatz, schluss, satz in (
                (["--trocken"], "Trockenlauf – nichts gespeichert.", "4 Produkte wechseln die Kategorie"),
                ([], "Gespeichert.", "4 Produkte haben die Kategorie gewechselt")):
            r = app.test_cli_runner().invoke(args=["material", "import-catalog", datei, *zusatz])
            assert r.exit_code == 0, r.output
            zeilen = r.output.splitlines()
            assert "Zuweisungen neu 0, geloest 2, unveraendert 0 (davon 2 durch Kategoriewechsel)" in zeilen, r.output
            achtung = [z for z in zeilen if z.startswith("ACHTUNG ")]
            assert achtung[0].startswith(f"ACHTUNG {satz} – davon 3 mit Artikeln im Bestand"), r.output
            assert achtung[1].startswith("ACHTUNG Neu angelegt: „PSA (Test) / Alt (Test)“"), r.output
            assert achtung[2:] == [f"ACHTUNG {w}" for w in (WARNUNGEN_GESPEICHERT if not zusatz else WARNUNGEN)], r.output
            assert zeilen[-1] == schluss, r.output
    print("Kommandozeile bestanden.")


def _pool(kp, heimat, titel, kategorien=(), produkte=()):
    """Ein aktives Formular im Pool der Kategorie heimat, zugewiesen an genau diese Kategorien und Produkte."""
    r = kp.post("/api/material/formular-pool", json={"kategorie_id": heimat, "titel": titel, "punkte": PUNKT})
    assert r.status_code == 201, r.get_json()
    f = r.json["formular"]
    assert kp.post(f"/api/material/formulare/{f['id']}/aktivieren", json={}).status_code == 200
    r = kp.put(f"/api/material/formular-pool/{f['formular_id']}/zuweisung",
               json={"kategorien": list(kategorien), "produkte": list(produkte)})
    assert r.status_code == 200, r.get_json()


def test_gruppen():
    """Die Oberfläche bekommt je alte → neue Kategorie EINE Zeile mit Zahlen und Folge (Prüfung Browser r3, Verbesserung
    1), darunter je gleicher Folge eine Zeile: zwei Produkte mit gleichem Standard zusammen, mit ihren Namen; zwei mit
    derselben eigenen Zuweisung zusammen („die Zuweisungen … an die Produkte“). Die Warnungen je Produkt bleiben in
    „warnungen“ (Kommandozeile)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp, w = k["katalog"], k["wart"]
        kategorien = [_kat("Ober (Test)", _kat("A (Test)"), _kat("B (Test)"))]
        a, b = ("Ober (Test)", "A (Test)"), ("Ober (Test)", "B (Test)")
        modelle = ("Kappa", "Lambda", "My", "Ny")
        ber = importieren(kp, _datei([(m, a) for m in modelle], kategorien), False, name="eins.json")
        assert ber["gespeichert"], ber
        ka, kb = _ids(app, "mat_category", "name", ("A (Test)", "B (Test)"))
        p = dict(zip(modelle, _ids(app, "mat_product", "model", modelle)))
        formular_neu(kp, {"kategorie_id": ka}, "A-Prüfung (Test)", PUNKT)
        formular_neu(kp, {"kategorie_id": kb}, "B-Prüfung (Test)", PUNKT)
        _pool(kp, ka, "Eigen-Prüfung (Test)", produkte=(p["My"], p["Ny"]))
        gid, _ = gliederung(w, "OG Testdorf")
        for m, n in (("Kappa", 1), ("Lambda", 2), ("My", 1), ("Ny", 1)):
            _artikel(w, p[m], gid, n)
        zwei = _datei([(m, b) for m in modelle], kategorien)
        for speichern in (False, True):
            ber = importieren(kp, zwei, not speichern, name="zwei.json")
            assert not ber["fehler"] and ber["gespeichert"] is speichern, ber
            gilt, geloest = ("jetzt gilt", "wurden gelöst") if speichern else ("künftig gilt", "werden gelöst")
            pfeil = "Kategorie „A (Test)“ → „B (Test)“ (unter „Ober (Test)“)"
            b_std = "„B-Prüfung (Test)“ (Standard der Kategorie „B (Test)“)"
            verlieren = "haben ein anderes Prüfformular bekommen" if speichern else "bekommen ein anderes Prüfformular"
            assert ber["kategoriewechsel"]["gruppen"] == [{
                "zeile": f"{pfeil} – 4 Produkte mit 5 Artikeln im Bestand; 5 Artikel {verlieren}, 2 Produkt-Zuweisungen "
                         f"{geloest}.",
                "folgen": [
                    {"zeile": f"3 Artikel (2 Produkte): {gilt} {b_std} statt „A-Prüfung (Test)“ (Standard der Kategorie "
                              "„A (Test)“).", "einzeln": ["Testwerk Kappa (1 Artikel)", "Testwerk Lambda (2 Artikel)"]},
                    {"zeile": f"2 Artikel (2 Produkte): die Zuweisungen von „Eigen-Prüfung (Test)“ an die Produkte "
                              f"{geloest}; {gilt} {b_std}.", "einzeln": ["Testwerk My (1 Artikel)", "Testwerk Ny (1 Artikel)"]}],
                "warnungen": [0, 1, 2, 3]}], ber["kategoriewechsel"]["gruppen"]
            assert len(ber["warnungen"]) == 4 and ber["warnungen"][1].startswith(
                f"produkte[1] (Testwerk Lambda): {pfeil} – betrifft 2 Artikel im Bestand; {gilt} {b_std}"), ber["warnungen"]
            assert ber["zuweisungen"]["geloest"] == 2 and ber["kategoriewechsel"]["davon"] == \
                "davon 2 durch Kategoriewechsel", ber
    print("Gruppen bestanden.")


def _kategorien_mit_kennung(schlingen_unter):
    """Format 2 mit Kennung (wie ein Katalog-Export): „PSA (Test)“ mit „Andere (Test)“, „Wasser (Test)“ – „Schlingen
    (Test)“ steht unter schlingen_unter („oben“: auf der obersten Ebene). Nur über die Kennung kann eine Datei eine
    Kategorie verschieben."""
    schlingen = dict(_kat("Schlingen (Test)"), uid="5" * 32)
    psa = dict(_kat("PSA (Test)", *([schlingen] if schlingen_unter == "PSA" else []),
                    dict(_kat("Andere (Test)"), uid="6" * 32)), uid="1" * 32)
    wasser = dict(_kat("Wasser (Test)", *([schlingen] if schlingen_unter == "Wasser" else [])), uid="7" * 32)
    return [psa, wasser] + ([schlingen] if schlingen_unter == "oben" else [])


VERSCHOBEN_MODELLE = ("Delta", "Epsilon", "Eta", "Zeta", "Theta")


def _verschoben_vorbereiten(tmp):
    """„PSA (Test)“ mit „Schlingen (Test)“ (Standard „Schlingen-Prüfung“ aus dem Pool von „PSA“) und „Andere (Test)“,
    daneben „Wasser (Test)“; „PSA-Prüfung“ ist Standard von „PSA“. Delta (2 Artikel), Epsilon (1 Artikel, „Extra-Prüfung“
    aus dem Pool von „PSA“), Eta (1 Artikel, eigenes Formular) und Zeta (ohne Artikel) in „Schlingen“, Theta (1 Artikel)
    in „Andere“. Liefert app, Konten, Produkte und die Kennungen von „PSA“, „Schlingen“, „Wasser“."""
    app, k = umgebung(tmp)
    kp, w = k["katalog"], k["wart"]
    modelle, alt_schl = VERSCHOBEN_MODELLE, ("PSA (Test)", "Schlingen (Test)")
    eins = _datei([(m, alt_schl) for m in modelle[:4]] + [("Theta", ("PSA (Test)", "Andere (Test)"))],
                  _kategorien_mit_kennung("PSA"))
    ber = importieren(kp, eins, False, name="eins.json")
    assert ber["gespeichert"] and not ber["fehler"], ber
    psa, schlingen, wasser = _ids(app, "mat_category", "name", ("PSA (Test)", "Schlingen (Test)", "Wasser (Test)"))
    p = dict(zip(modelle, _ids(app, "mat_product", "model", modelle)))
    formular_neu(kp, {"kategorie_id": psa}, "PSA-Prüfung (Test)", PUNKT)
    _pool(kp, psa, "Schlingen-Prüfung (Test)", kategorien=(schlingen,))
    _pool(kp, psa, "Extra-Prüfung (Test)", produkte=(p["Epsilon"],))
    formular_neu(kp, {"produkt_id": p["Eta"]}, "Eta-Prüfung (Test)", PUNKT)       # Heimat „Schlingen“: bleibt
    gid, _ = gliederung(w, "OG Testdorf")
    for m, n in (("Delta", 2), ("Epsilon", 1), ("Eta", 1), ("Theta", 1)):
        _artikel(w, p[m], gid, n)
    return app, k, p, (psa, schlingen, wasser)


def test_verschobene_kategorie():
    """Eine Datei mit Kennung verschiebt „Schlingen (Test)“ von „PSA (Test)“ unter „Wasser (Test)“ (Wunsch des Nutzers vom
    09.11.2026, Frage 1 des Berichts zu import-warnung-kategorie): Der Standard von „Schlingen“ aus dem Pool von „PSA“ und
    die Zuweisung eines Formulars aus diesem Pool an Epsilon liegen danach außerhalb ihrer Heimat und werden gelöst (Z6)
    – sie zählen unter „gelöst“ („davon 2 durch verschobene Kategorien“), die Warnung „verschoben – betrifft n Artikel“
    der Kategorie nennt die Folgen für die Prüfformulare (Delta und Epsilon verlieren es, Eta behält seins), oben steht
    eine eigene Zusammenfassung. Theta wechselt selbst in die verschobene Kategorie: eigene Warnung, nicht doppelt
    gezählt. Probelauf = echter Lauf, Kommandozeile; ein zweiter Lauf meldet nichts mehr."""
    from app import db
    from app.material.services import katalog
    with tempfile.TemporaryDirectory() as tmp:
        app, k, p, (psa, schlingen, wasser) = _verschoben_vorbereiten(tmp)
        kp, modelle = k["katalog"], VERSCHOBEN_MODELLE
        alt_schl, neu_schl = ("PSA (Test)", "Schlingen (Test)"), ("Wasser (Test)", "Schlingen (Test)")
        vorher = _stand(app)
        zwei = _datei([(m, neu_schl) for m in modelle], _kategorien_mit_kennung("Wasser"))

        def erwartet(fertig):
            wird = "wurden gelöst" if fertig else "werden gelöst"
            folgen = ("2 Artikel haben danach kein Prüfformular mehr (bisher „Schlingen-Prüfung (Test)“, Standard der "
                      "Kategorie „Schlingen (Test)“) und lassen sich nicht prüfen; 1 Artikel hat danach kein Prüfformular "
                      "mehr (bisher „Extra-Prüfung (Test)“, dem Produkt zugewiesen) und lässt sich nicht prüfen; für 1 "
                      "Artikel gilt „Eta-Prüfung (Test)“ weiter (dem Produkt zugewiesen); 2 Zuweisungen " + wird
                      + ": „Schlingen-Prüfung (Test)“ an Kategorie „PSA (Test) / Schlingen (Test)“, „Extra-Prüfung "
                      "(Test)“ an "
                      "„Testwerk Epsilon“.")
            satz = ("verschoben „PSA (Test) / Schlingen (Test)“ → „Wasser (Test) / Schlingen (Test)“ – betrifft 4 Artikel "
                    "im Bestand; " + folgen)
            theta = ("Kategorie „PSA (Test) / Andere (Test)“ → „Wasser (Test) / Schlingen (Test)“ – betrifft 1 Artikel im "
                     "Bestand; er hat danach kein Prüfformular mehr (bisher „PSA-Prüfung (Test)“, Standard der "
                     "Kategorie „PSA (Test)“) und lässt sich nicht prüfen.")
            warnungen = [f"kategorien[1].unterkategorien[0] (Schlingen (Test)): {satz}",
                         "produkte[4] (Testwerk Theta): " + theta]
            verloren = "haben ihr Prüfformular verloren" if fertig else "verlieren ihr Prüfformular"
            gruppen = [{"zeile": "Kategorie „PSA (Test) / Andere (Test)“ → „Wasser (Test) / Schlingen (Test)“ – Testwerk "
                                 "Theta mit 1 Artikel im Bestand; 1 Artikel "
                                 + ("hat sein Prüfformular verloren." if fertig else "verliert sein Prüfformular."),
                        "folgen": [{"zeile": "1 Artikel (Testwerk Theta): er hat danach kein Prüfformular mehr (bisher "
                                             "„PSA-Prüfung (Test)“, Standard der Kategorie „PSA (Test)“) und lässt sich "
                                             "nicht prüfen.", "einzeln": []}], "warnungen": [1]},
                       {"zeile": "Kategorie „Schlingen (Test)“: verschoben „PSA (Test) / Schlingen (Test)“ → „Wasser (Test) "
                                 f"/ Schlingen (Test)“ – betrifft 4 Artikel im Bestand; 3 Artikel {verloren}, 2 Zuweisungen "
                                 f"{wird}.",
                        "folgen": [
                            {"zeile": "2 Artikel (Testwerk Delta): sie haben danach kein Prüfformular mehr (bisher "
                                      "„Schlingen-Prüfung (Test)“, Standard der Kategorie „Schlingen (Test)“) und lassen sich "
                                      "nicht prüfen.", "einzeln": []},
                            {"zeile": "1 Artikel (Testwerk Epsilon): er hat danach kein Prüfformular mehr (bisher "
                                      "„Extra-Prüfung (Test)“, dem Produkt zugewiesen) und lässt sich nicht prüfen.",
                             "einzeln": []},
                            {"zeile": "1 Artikel (Testwerk Eta): das Prüfformular „Eta-Prüfung (Test)“ gilt weiter (dem "
                                      "Produkt zugewiesen).", "einzeln": []},
                            {"zeile": f"2 Zuweisungen {wird}: „Schlingen-Prüfung (Test)“ an Kategorie „PSA (Test) / "
                                      "Schlingen (Test)“, „Extra-Prüfung (Test)“ an „Testwerk Epsilon“.", "einzeln": []}],
                        "warnungen": [0]}]
            return warnungen, gruppen

        for speichern in (False, True):
            ber = importieren(kp, zwei, not speichern, name="zwei.json")
            assert not ber["fehler"] and ber["gespeichert"] is speichern, ber
            assert ber["kategorien"]["geaendert"] == 1 and ber["produkte"]["geaendert"] == 1, ber
            warnungen, gruppen = erwartet(speichern)
            assert ber["warnungen"] == warnungen, ber["warnungen"]
            assert ber["zuweisungen"] == {"neu": 0, "geloest": 2, "unveraendert": 0}, ber["zuweisungen"]
            kw = ber["kategoriewechsel"]
            assert kw["verschoben"] == {"kategorien": 1, "mit_artikeln": 3, "artikel": 4, "ohne_formular": 3,
                                        "anderes_formular": 0, "zuweisungen_geloest": 2}, kw
            assert (kw["produkte"], kw["mit_artikeln"], kw["ohne_formular"], kw["zuweisungen_geloest"]) == (1, 1, 1, 0), kw
            assert kw["davon"] == "davon 2 durch verschobene Kategorien", kw
            assert kw["zusammenfassung"] == (
                "1 Produkt hat die Kategorie gewechselt – mit 1 Artikel im Bestand; 1 Artikel hat sein Prüfformular "
                "verloren." if speichern else
                "1 Produkt wechselt die Kategorie – mit 1 Artikel im Bestand; 1 Artikel verliert sein Prüfformular."), kw
            assert kw["verschiebung"] == (
                "1 Kategorie wurde verschoben – darin 3 Produkte mit Artikeln im Bestand (4 Artikel); 3 Artikel haben "
                "ihr Prüfformular verloren, 2 Zuweisungen wurden gelöst." if speichern else
                "1 Kategorie wird verschoben – darin 3 Produkte mit Artikeln im Bestand (4 Artikel); 3 Artikel verlieren "
                "ihr Prüfformular, 2 Zuweisungen werden gelöst."), kw
            assert kw["alte_datei"] is None and kw["gruppen"] == gruppen, kw
            if not speichern:
                assert _stand(app) == vorher                                   # Probelauf: nichts gespeichert
                # Kommandozeile (Trockenlauf): dieselben Sätze, „davon … durch verschobene Kategorien“.
                datei = os.path.join(tmp, "zwei.json")
                with open(datei, "wb") as fh:
                    fh.write(zwei)
                r = app.test_cli_runner().invoke(args=["material", "import-catalog", datei, "--trocken"])
                assert r.exit_code == 0, r.output
                zeilen = r.output.splitlines()
                assert "Zuweisungen neu 0, geloest 2, unveraendert 0 (davon 2 durch verschobene Kategorien)" in zeilen, \
                    r.output
                assert [z for z in zeilen if z.startswith("ACHTUNG ")] == [
                    f"ACHTUNG {kw['zusammenfassung']}", f"ACHTUNG {kw['verschiebung']}"] + \
                    [f"ACHTUNG {x}" for x in warnungen], r.output
                assert _stand(app) == vorher
        with app.app_context():
            assert db.query("SELECT parent_id FROM mat_category WHERE id = ?", (schlingen,), one=True)["parent_id"] == wasser
            assert katalog.formular_fuer_produkt(p["Delta"]) is None and katalog.formular_fuer_produkt(p["Epsilon"]) is None
            assert katalog.formular_fuer_produkt(p["Eta"])["title"] == "Eta-Prüfung (Test)"
            assert katalog.formular_fuer_produkt(p["Theta"]) is None
            gruende = [r["after_json"] for r in db.query("SELECT after_json FROM mat_audit WHERE entity = 'formular' "
                                                         "AND action = 'zuweisung_geloest'")]
            assert sum("Kategorie „Schlingen (Test)“ verschoben" in g for g in gruende) == 2, gruende

        # Derselbe Lauf noch einmal: nichts verschoben, nichts gelöst, keine Meldung.
        ber = importieren(kp, zwei, True, name="zwei.json")
        assert not ber["fehler"] and not ber["warnungen"] and ber["kategoriewechsel"] is None, ber
        assert ber["zuweisungen"]["geloest"] == 0, ber["zuweisungen"]
        # Zurück unter „PSA“: Niemand verliert etwas (Delta, Epsilon und Theta bekommen den Standard von „PSA“ zurück,
        # Eta behält seins) – die Zusammenfassung nennt nur die Zahlen, die Warnung der Kategorie, was gilt.
        drei = _datei([(m, alt_schl) for m in modelle], _kategorien_mit_kennung("PSA"))
        ber = importieren(kp, drei, True, name="drei.json")
        assert not ber["fehler"] and ber["zuweisungen"]["geloest"] == 0, ber
        kw = ber["kategoriewechsel"]
        assert kw["verschoben"]["mit_artikeln"] == 4 and kw["davon"] is None, kw
        assert kw["verschiebung"] == ("1 Kategorie wird verschoben – darin 4 Produkte mit Artikeln im Bestand (5 "
                                      "Artikel)."), kw
        assert ber["warnungen"] == [
            "kategorien[0].unterkategorien[0] (Schlingen (Test)): verschoben „Wasser (Test) / Schlingen (Test)“ → „PSA "
            "(Test) / Schlingen (Test)“ – betrifft 5 Artikel im Bestand; für 4 Artikel gilt künftig „PSA-Prüfung (Test)“ "
            "(Standard der Kategorie „PSA (Test)“), bisher keins; für 1 Artikel gilt „Eta-Prüfung (Test)“ weiter (dem "
            "Produkt zugewiesen)."], ber["warnungen"]
    print("Verschobene Kategorie bestanden.")


def test_verschobene_kategorie_grenzfaelle():
    """Nachbesserung r1 (Prüfung Ablauf r1, Befunde 1–3; Prüfung Browser r1, Verbesserung 2):
    - Verlässt ein Produkt mit Artikeln die verschobene Kategorie in derselben Datei, zählt „betrifft n Artikel“ wie
      beim Verschieben und sagt „davon m mit eigener Warnung“; seine eigene Warnung nennt als Herkunft den Pfad vor dem
      Import, nicht den schon verschobenen.
    - Verschiebt die Datei eine Kategorie und zugleich eine zweite unter sie, steht jedes Produkt nur bei der inneren.
    - Auf die oberste Ebene: „→ oberste Ebene“; gehen alle Produkte mit Artikeln selbst, „alle mit eigener Warnung“."""
    pfeil = "verschoben „PSA (Test) / Schlingen (Test)“ → "
    extra = ("1 Artikel hat danach kein Prüfformular mehr (bisher „Extra-Prüfung (Test)“, dem Produkt zugewiesen) und "
             "lässt sich nicht prüfen")
    geloest = ("2 Zuweisungen {}: „Schlingen-Prüfung (Test)“ an Kategorie „PSA (Test) / Schlingen (Test)“, "
               "„Extra-Prüfung (Test)“ an „Testwerk Epsilon“.")
    andere, neu_schl = ("PSA (Test)", "Andere (Test)"), ("Wasser (Test)", "Schlingen (Test)")
    with tempfile.TemporaryDirectory() as tmp:
        app, k, p, _ = _verschoben_vorbereiten(tmp)
        kp, modelle = k["katalog"], VERSCHOBEN_MODELLE
        # Delta (2 Artikel) wechselt nach „Andere“, „Schlingen“ wandert unter „Wasser“.
        zwei = _datei([("Delta", andere)] + [(m, neu_schl) for m in modelle[1:]], _kategorien_mit_kennung("Wasser"))
        for speichern in (False, True):
            ber = importieren(kp, zwei, not speichern, name="zwei.json")
            assert not ber["fehler"] and ber["gespeichert"] is speichern, ber
            wird = "wurden gelöst" if speichern else "werden gelöst"
            assert ber["warnungen"][0] == (
                f"kategorien[1].unterkategorien[0] (Schlingen (Test)): {pfeil}„Wasser (Test) / Schlingen (Test)“ – betrifft "
                f"4 Artikel im Bestand, davon 2 mit eigener Warnung; {extra}; für 1 Artikel gilt „Eta-Prüfung (Test)“ "
                "weiter (dem Produkt zugewiesen); " + geloest.format(wird)), ber["warnungen"]
            assert ber["warnungen"][1].startswith(
                "produkte[0] (Testwerk Delta): Kategorie „Schlingen (Test)“ → „Andere (Test)“ (unter „PSA (Test)“) – "
                "betrifft 2 Artikel im Bestand; "), ber["warnungen"]
            kw = ber["kategoriewechsel"]
            assert (kw["verschoben"]["mit_artikeln"], kw["verschoben"]["artikel"]) == (2, 2), kw
            gruppe, = [g for g in kw["gruppen"] if g["warnungen"] == [0]]
            assert gruppe["zeile"].startswith(f"Kategorie „Schlingen (Test)“: {pfeil}„Wasser (Test) / Schlingen (Test)“ "
                                              "– betrifft 4 Artikel im Bestand, davon 2 mit eigener Warnung; 1 Artikel "), \
                gruppe
            assert [f["zeile"].split(":")[0] for f in gruppe["folgen"]] == [
                "1 Artikel (Testwerk Epsilon)", "1 Artikel (Testwerk Eta)", f"2 Zuweisungen {wird}"], gruppe

    with tempfile.TemporaryDirectory() as tmp:
        app, k, p, _ = _verschoben_vorbereiten(tmp)
        kp, w, modelle = k["katalog"], k["wart"], VERSCHOBEN_MODELLE
        # „Wasser“ bekommt Iota (1 Artikel); dann wandert „Wasser“ unter „Seil (Test)“ und „Schlingen“ unter „Wasser“.
        seil = dict(_kat("Seil (Test)"), uid="8" * 32)
        drei = _datei([(m, ("PSA (Test)", "Schlingen (Test)")) for m in modelle[:4]] + [("Theta", andere),
                      ("Iota", ("Wasser (Test)",))], _kategorien_mit_kennung("PSA") + [seil])
        assert importieren(kp, drei, False, name="drei.json")["gespeichert"]
        iota, = _ids(app, "mat_product", "model", ("Iota",))
        gid, _ = gliederung(w, "OG Testdorf 2")
        _artikel(w, iota, gid)
        kategorien = _kategorien_mit_kennung("Wasser")
        kategorien.append(dict(seil, unterkategorien=[kategorien.pop(1)]))
        innen = ("Seil (Test)", "Wasser (Test)", "Schlingen (Test)")
        vier = _datei([(m, innen) for m in modelle[:4]] + [("Theta", andere), ("Iota", innen[:2])], kategorien)
        for speichern in (False, True):
            ber = importieren(kp, vier, not speichern, name="vier.json")
            assert not ber["fehler"] and ber["gespeichert"] is speichern, ber
            assert ber["warnungen"][0] == (
                "kategorien[1].unterkategorien[0] (Wasser (Test)): verschoben „Wasser (Test)“ → „Seil (Test) / Wasser "
                "(Test)“ – betrifft 1 Artikel im Bestand; 1 Artikel hat weiterhin kein Prüfformular."), ber["warnungen"]
            assert ber["warnungen"][1].startswith(
                f"kategorien[1].unterkategorien[0].unterkategorien[0] (Schlingen (Test)): {pfeil}„Seil (Test) / Wasser "
                "(Test) / Schlingen (Test)“ – betrifft 4 Artikel im Bestand; 2 Artikel haben danach kein Prüfformular "
                "mehr"), ber["warnungen"]
            gruppen = ber["kategoriewechsel"]["gruppen"]
            assert [[f["zeile"].split(":")[0] for f in g["folgen"]] for g in gruppen] == [
                ["1 Artikel (Testwerk Iota)"],
                ["2 Artikel (Testwerk Delta)", "1 Artikel (Testwerk Epsilon)", "1 Artikel (Testwerk Eta)",
                 "2 Zuweisungen " + ("wurden gelöst" if speichern else "werden gelöst")]], gruppen
            assert gruppen[0]["zeile"].endswith("– betrifft 1 Artikel im Bestand."), gruppen[0]
            assert ber["kategoriewechsel"]["verschoben"]["artikel"] == 5, ber["kategoriewechsel"]

    with tempfile.TemporaryDirectory() as tmp:
        app, k, p, _ = _verschoben_vorbereiten(tmp)
        kp, modelle = k["katalog"], VERSCHOBEN_MODELLE
        # „Schlingen“ auf die oberste Ebene, Delta, Epsilon und Eta gehen nach „Andere“.
        zwei = _datei([(m, andere) for m in modelle[:3]] + [("Zeta", ("Schlingen (Test)",)), ("Theta", andere)],
                      _kategorien_mit_kennung("oben"))
        ber = importieren(kp, zwei, True, name="zwei.json")
        assert not ber["fehler"], ber
        assert ber["warnungen"][0] == (
            f"kategorien[2] (Schlingen (Test)): {pfeil}oberste Ebene – betrifft 4 Artikel im Bestand, alle mit eigener "
            "Warnung; " + geloest.format("werden gelöst")), ber["warnungen"]
        kw = ber["kategoriewechsel"]
        assert kw["verschiebung"] is None and kw["verschoben"]["mit_artikeln"] == 0, kw
        assert not any(0 in g["warnungen"] for g in kw["gruppen"]), kw["gruppen"]       # steht im Kasten als Warnung
        assert kw["davon"] == "davon 3 durch Kategoriewechsel und verschobene Kategorien", kw
    print("Verschobene Kategorie, Grenzfälle bestanden.")


if __name__ == "__main__":
    test_alte_datei_probelauf_und_echter_lauf()
    test_gilt_weiter_und_ohne_formular()
    test_kommandozeile()
    test_gruppen()
    test_verschobene_kategorie()
    test_verschobene_kategorie_grenzfaelle()
