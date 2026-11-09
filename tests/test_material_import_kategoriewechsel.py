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

WARNUNGEN = [
    "produkte[0] (Testwerk Delta): Kategorie „PSA (Test) / Schlingen (Test)“ → „PSA (Test) / Alt (Test)“ – betrifft 2 "
    "Artikel hier; sie haben danach kein Prüfformular mehr (bisher „Schlingen-Prüfung (Test)“, Standard der Kategorie "
    "„Schlingen (Test)“) und lassen sich nicht prüfen.",
    "produkte[1] (Testwerk Epsilon): Kategorie „PSA (Test) / Schlingen (Test)“ → „PSA (Test) / Alt (Test)“ – betrifft 1 "
    "Artikel hier; die Zuweisung von „Epsilon-Prüfung (Test)“ an das Produkt wird gelöst; er hat danach kein "
    "Prüfformular mehr (bisher „Epsilon-Prüfung (Test)“, dem Produkt zugewiesen) und lässt sich nicht prüfen.",
    "produkte[3] (Testwerk Eta): Kategorie „PSA (Test) / Schlingen (Test)“ → „PSA (Test) / Andere (Test)“ – betrifft 1 "
    "Artikel hier; künftig gilt „Andere-Prüfung (Test)“ (Standard der Kategorie „Andere (Test)“) statt "
    "„Schlingen-Prüfung (Test)“ (Standard der Kategorie „Schlingen (Test)“).",
]
ZAHLEN = {"produkte": 4, "mit_artikeln": 3, "artikel": 4, "ohne_formular": 3, "anderes_formular": 1,
          "zuweisungen_geloest": 2, "neue_kategorien": [{"kategorie": "PSA (Test) / Alt (Test)", "produkte": 3,
                                                         "aus": ["PSA (Test) / Schlingen (Test)"]}]}


def _zahlen(kw):
    return {s: kw[s] for s in ZAHLEN}


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
        assert kw["zusammenfassung"] == ("4 Produkte wechseln die Kategorie – davon 3 mit Artikeln hier (4 Artikel); "
                                         "3 Artikel verlieren ihr Prüfformular, 1 Artikel bekommt ein anderes, "
                                         "2 Produkt-Zuweisungen werden gelöst."), kw
        assert kw["alte_datei"] == ("Neu angelegt: „PSA (Test) / Alt (Test)“ nimmt 3 Produkte aus „PSA (Test) / "
                                    "Schlingen (Test)“ auf. Vielleicht ist die Datei älter und nennt eine Kategorie noch "
                                    "mit ihrem früheren Namen – dann nicht übernehmen, sondern eine aktuelle Datei "
                                    "nehmen."), kw
        # Die Zeile „geändert (Kategorie)“ bleibt – auch für Zeta ohne Artikel.
        assert "Produkt „Testwerk Zeta“: geändert (Kategorie)" in ber["aenderungen"], ber["aenderungen"]
        assert _stand(app) == vorher                                   # Probelauf: nichts gespeichert

        ber = importieren(kp, ALTE_DATEI, False, name="serie-alt.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["warnungen"] == WARNUNGEN, ber["warnungen"]
        assert ber["zuweisungen"]["geloest"] == 2, ber["zuweisungen"]
        kw = ber["kategoriewechsel"]
        assert _zahlen(kw) == ZAHLEN, kw
        assert kw["zusammenfassung"] == ("4 Produkte haben die Kategorie gewechselt – davon 3 mit Artikeln hier "
                                         "(4 Artikel); 3 Artikel haben ihr Prüfformular verloren, 1 Artikel hat ein "
                                         "anderes bekommen, 2 Produkt-Zuweisungen wurden gelöst."), kw
        assert kw["alte_datei"].endswith("– dann die Produkte über „Bearbeiten“ zurückverschieben und ihre Zuweisungen "
                                         "neu setzen."), kw
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
        assert kw["zusammenfassung"] == ("4 Produkte wechseln die Kategorie – davon 3 mit Artikeln hier (4 Artikel); "
                                         "1 Artikel bekommt ein anderes."), kw
        assert ("produkte[0] (Testwerk Delta): Kategorie „PSA (Test) / Alt (Test)“ → „PSA (Test) / Schlingen (Test)“ – "
                "betrifft 2 Artikel hier; künftig gilt „Schlingen-Prüfung (Test)“ (Standard der Kategorie „Schlingen "
                "(Test)“), bisher keins.") in ber["warnungen"], ber["warnungen"]
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
            "produkte[0] (Testwerk Pi): Kategorie „Ober (Test) / A (Test)“ → „Ober (Test) / B (Test)“ – betrifft 1 "
            "Artikel hier; das Prüfformular „Ober-Prüfung (Test)“ gilt weiter (Standard der Kategorie „Ober (Test)“).",
            "produkte[2] (Testwerk Sigma): Kategorie „C (Test)“ → „D (Test)“ – betrifft 1 Artikel hier; ein "
            "Prüfformular hat er weiterhin nicht."], ber["warnungen"]
        kw = ber["kategoriewechsel"]
        assert kw["zusammenfassung"] == "3 Produkte wechseln die Kategorie – davon 2 mit Artikeln hier (2 Artikel).", kw
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
            assert achtung[0].startswith(f"ACHTUNG {satz} – davon 3 mit Artikeln hier"), r.output
            assert achtung[1].startswith("ACHTUNG Neu angelegt: „PSA (Test) / Alt (Test)“"), r.output
            assert achtung[2:] == [f"ACHTUNG {w}" for w in WARNUNGEN], r.output
            assert zeilen[-1] == schluss, r.output
    print("Kommandozeile bestanden.")


if __name__ == "__main__":
    test_alte_datei_probelauf_und_echter_lauf()
    test_gilt_weiter_und_ohne_formular()
    test_kommandozeile()
