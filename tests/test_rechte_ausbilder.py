"""Riegenkarten: Ausbilder nur noch mit Konto (Auftrag planung/rechte-redakteur/auftrag_ausbilder_konten.md, Wunsch des
Nutzers vom 01.11.2026): python tests/test_rechte_ausbilder.py  oder  pytest …

Anlegen und Bearbeiten nur mit Konten, die eine Stufe in den Riegenkarten haben (sonst 400 mit Klartext und Zeile),
die Kontosuche, verknüpfte Konten ohne Stufe (bleiben, markiert), Konto löschen, die Sichtbarkeit für ein Mitglied als
Ausbilder, die Zuordnung im Excel-Import (E-Mail, eindeutiger Name, mehrdeutig/unbekannt → nicht übernommen) und
Schema-Schritt 34 (verknüpfen, entfernen ohne Text in der Beschreibung, Startprotokoll, zweiter Start, Abbruch). Nur
erfundene Namen; es geht keine Mail hinaus (ohne SMTP_HOST)."""
import hashlib
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_rechte_redakteur import (H, MITGLIED, REDAKTEUR, VERWALTUNG, anmelden, konto, make_app,  # noqa: E402
                                   stufe_setzen, xlsx)

API = "/api/pruefungen"


def _ausbilder(lg):
    return [(a["name"], a["funktion"], a["ist_leitung"]) for a in lg["ausbilder"]]


def test_anlegen_und_bearbeiten():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        red, red_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"pruefungen": REDAKTEUR})
        mit, mit_id = konto(app, adm, "mats@example.org", "Mats Mitglied", {"pruefungen": MITGLIED})
        fremd, _ = konto(app, adm, "fritz@example.org", "Fritz Fremd", {"pruefungen": MITGLIED})
        _, ohne_id = konto(app, adm, "olaf@example.org", "Olaf Ohnestufe", {"pruefungen": 0})
        _, aus_id = konto(app, adm, "doris@example.org", "Doris Deaktiviert", {"pruefungen": MITGLIED})
        assert adm.put(f"/api/admin/users/{aus_id}", json={"active": False}).status_code == 200

        # Kontosuche: Name (Teil) oder E-Mail (nur ganz – zweite Durchsicht vor dem Merge), nur passende Konten, keine
        # E-Mail in der Antwort; ein Mitglied ohne Leitung sucht nicht (es trägt nirgends Ausbilder ein).
        r = red.get(f"{API}/nutzer?q=MATS@example.org")
        assert r.status_code == 200 and [n["name"] for n in r.json["nutzer"]] == ["Mats Mitglied"], r.get_json()
        assert red.get(f"{API}/nutzer?q=MATS@").json["nutzer"] == []
        assert all(set(n) == {"id", "name", "gliederung"} for n in r.json["nutzer"])
        assert red.get(f"{API}/nutzer?q=olaf").json["nutzer"] == []           # ohne Stufe
        assert red.get(f"{API}/nutzer?q=doris").json["nutzer"] == []          # deaktiviert
        assert red.get(f"{API}/nutzer?q=x").status_code == 400
        r = mit.get(f"{API}/nutzer?q=rita")
        assert r.status_code == 403 and "leitet oder anlegt" in r.json["error"], r.get_json()

        # Anlegen: Freitext, Konto ohne Stufe, deaktiviertes Konto → 400 mit Zeile; nichts angelegt.
        for zeile, text in (({"name": "Erna Extern", "funktion": "Wasser"}, "nur mit Konto"),
                            ({"user_id": ohne_id}, "„Olaf Ohnestufe“ hat keine Stufe in den Riegenkarten"),
                            ({"user_id": aus_id}, "„Doris Deaktiviert“ hat keine Stufe"),
                            ({"user_id": "abc"}, "nur mit Konto"), ({"user_id": True}, "nur mit Konto")):
            r = red.post(f"{API}/lehrgaenge", json={"titel": "Abgewiesen", "ausbilder": [{"user_id": mit_id}, zeile]})
            assert r.status_code == 400 and text in r.json["error"] and r.json["zeile"] == 1, (zeile, r.get_json())
        assert adm.get(f"{API}/lehrgaenge").json["lehrgaenge"] == []
        # Leere Zeilen aus dem Dialog zählen nicht; die anlegende Person wird Leitung.
        r = red.post(f"{API}/lehrgaenge", json={"titel": "SR2", "beschreibung": "Ablauf", "ausbilder": [
            {"user_id": mit_id, "funktion": "Wasser"}, {"user_id": None, "name": "", "funktion": ""}]})
        assert r.status_code == 201, r.get_json()
        lg = r.json["lehrgang"]
        lid = lg["id"]
        assert _ausbilder(lg) == [("Rita Redakteurin", "", True), ("Mats Mitglied", "Wasser", False)], lg["ausbilder"]
        assert all(a["zugriff"] and a["gliederung"] == "OG Beispielstadt" for a in lg["ausbilder"]), lg["ausbilder"]

        # Sichtbarkeit: Das Mitglied sieht den Lehrgang, in dem es Ausbilder ist (Liste, Detail, Seite), ein anderes
        # Mitglied nicht.
        assert [x["id"] for x in mit.get(f"{API}/lehrgaenge").json["lehrgaenge"]] == [lid]
        assert mit.get(f"{API}/lehrgaenge/{lid}").status_code == 200 and mit.get(f"/riegenkarten/{lid}").status_code == 200
        assert fremd.get(f"{API}/lehrgaenge").json["lehrgaenge"] == []
        assert fremd.get(f"{API}/lehrgaenge/{lid}").status_code == 404

        # Der Name kommt aus dem Konto – auch nach einer Umbenennung.
        assert adm.put(f"/api/admin/users/{mit_id}", json={"name": "Mats Umbenannt"}).status_code == 200
        assert _ausbilder(red.get(f"{API}/lehrgaenge/{lid}").json["lehrgang"])[1] == ("Mats Umbenannt", "Wasser", False)

        # Verliert ein Ausbilder die Stufe, bleibt er eingetragen (markiert) und der Lehrgang speicherbar; neu
        # eintragen lässt er sich nicht.
        stufe_setzen(adm, mit_id, pruefungen=0)
        lg = red.get(f"{API}/lehrgaenge/{lid}").json["lehrgang"]
        mats = lg["ausbilder"][1]
        assert mats["user_id"] == mit_id and mats["zugriff"] is False and mats["ohne_zugriff"] == "stufe", mats
        liste = [{"user_id": a["user_id"], "funktion": a["funktion"], "ist_leitung": a["ist_leitung"]}
                 for a in lg["ausbilder"]]
        r = red.put(f"{API}/lehrgaenge/{lid}", json={"titel": "SR2 neu", "ausbilder": liste})
        assert r.status_code == 200 and r.json["lehrgang"]["ausbilder"][1]["user_id"] == mit_id, r.get_json()
        r2 = red.post(f"{API}/lehrgaenge", json={"titel": "Neu", "ausbilder": [{"user_id": mit_id}]})
        assert r2.status_code == 400 and "keine Stufe" in r2.json["error"], r2.get_json()
        assert adm.put(f"/api/admin/users/{mit_id}", json={"active": False}).status_code == 200
        mats = red.get(f"{API}/lehrgaenge/{lid}").json["lehrgang"]["ausbilder"][1]
        assert mats["zugriff"] is False and mats["ohne_zugriff"] == "deaktiviert", mats
        # Ein noch nicht eingetragenes Konto ohne Stufe weist auch das Bearbeiten ab.
        r = red.put(f"{API}/lehrgaenge/{lid}", json={"ausbilder": liste + [{"user_id": ohne_id}]})
        assert r.status_code == 400 and r.json["zeile"] == 2, r.get_json()

        # Mitglied als Leitung: sucht Konten und trägt Ausbilder ein.
        assert adm.put(f"/api/admin/users/{mit_id}", json={"active": True}).status_code == 200
        stufe_setzen(adm, mit_id, pruefungen=MITGLIED)
        mit = anmelden(app, "mats@example.org")
        r = red.put(f"{API}/lehrgaenge/{lid}", json={"ausbilder": [{"user_id": mit_id, "ist_leitung": True}]})
        assert r.status_code == 200, r.get_json()
        fritz = mit.get(f"{API}/nutzer?q=fritz").json["nutzer"]
        assert [n["name"] for n in fritz] == ["Fritz Fremd"]
        r = mit.put(f"{API}/lehrgaenge/{lid}", json={"ausbilder": [{"user_id": red_id, "ist_leitung": True},
                                                                   {"user_id": mit_id, "ist_leitung": True},
                                                                   {"user_id": fritz[0]["id"]}]})
        assert r.status_code == 200 and fremd.get(f"{API}/lehrgaenge/{lid}").status_code == 200, r.get_json()

        # Konto löschen: seine Einträge als Ausbilder gehen mit (kein Freitext bleibt zurück).
        assert adm.delete(f"/api/admin/users/{fritz[0]['id']}", headers=H).status_code == 200
        with app.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM pruef_ausbilder WHERE user_id IS NULL", one=True)["n"] == 0
        assert [a["name"] for a in red.get(f"{API}/lehrgaenge/{lid}").json["lehrgang"]["ausbilder"]] == [
            "Rita Redakteurin", "Mats Umbenannt"]
        # Die Oberfläche kennt keinen Freitext mehr (kein Häkchen „extern“), dafür die Kontosuche und die Marke.
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "js",
                               "pruefungen.js"), encoding="utf-8").read()
        assert "ausb-extern" not in js and "extern (Freitext)" not in js
        assert "ohne Zugriff – Stufe in der Leitstelle vergeben" in js and "/nutzer?q=" in js
        print("Anlegen-/Bearbeiten-Test bestanden.")


def test_import_zuordnung():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        red, red_id = konto(app, adm, "rita@example.org", "Rita Redakteurin", {"pruefungen": REDAKTEUR})
        _, mail_id = konto(app, adm, "mira@example.org", "Mira Mailbekannt", {"pruefungen": MITGLIED})
        _, name_id = konto(app, adm, "nils@example.org", "Nils Namensgleich", {"pruefungen": MITGLIED})
        konto(app, adm, "doppel1@example.org", "Dora Doppel", {"pruefungen": MITGLIED})
        konto(app, adm, "doppel2@example.org", "Dora Doppel", {"pruefungen": MITGLIED})
        konto(app, adm, "sven@example.org", "Sven Stufenlos", {"pruefungen": 0})
        # Eine E-Mail-Adresse, die einem Konto ohne Stufe gehört, entscheidet – der Namensvetter mit Stufe wird es nicht.
        konto(app, adm, "pia.alt@example.org", "Pia Parallel", {"pruefungen": 0})
        konto(app, adm, "pia@example.org", "Pia Parallel", {"pruefungen": MITGLIED})
        datei = [["Vorname", "Nachname", "E-Mail", "Rolle"],
                 ["Ida", "Teilnehmerin", "", "TN"],
                 ["Anders", "Geschrieben", "MIRA@example.org", "Lehrgangsleitung"],      # E-Mail → Mira
                 ["Nils", "namensgleich", "", "Referent"],                               # Name → Nils
                 ["Dora", "Doppel", "", "Referentin"],                                   # mehrdeutig
                 ["Ulla", "Unbekannt", "ulla@example.org", "Ausbilderin"],              # kein Konto
                 ["Sven", "Stufenlos", "", "Referent"],                                  # ohne Stufe
                 ["Pia", "Parallel", "pia.alt@example.org", "Referentin"],               # E-Mail eines Kontos ohne Stufe
                 ["Rita", "Redakteurin", "", "Lehrgangsleitung"]]                        # steht schon (importiert)
        nicht = [{"name": "Dora Doppel", "funktion": "Referentin"}, {"name": "Ulla Unbekannt", "funktion": "Ausbilderin"},
                 {"name": "Sven Stufenlos", "funktion": "Referent"}, {"name": "Pia Parallel", "funktion": "Referentin"}]

        def senden(url, **felder):
            data = {"file": (xlsx(datei), "liste.xlsx")}
            data.update(felder)
            return red.post(url, data=data, headers=H, content_type="multipart/form-data")

        r = senden(f"{API}/import/vorschau")
        assert r.status_code == 200, r.get_json()
        v = r.json
        assert [(a["name"], a["konto"]["name"] if a["konto"] else None) for a in v["ausbilder"]] == [
            ("Anders Geschrieben", "Mira Mailbekannt"), ("Nils namensgleich", "Nils Namensgleich"), ("Dora Doppel", None),
            ("Ulla Unbekannt", None), ("Sven Stufenlos", None), ("Pia Parallel", None),
            ("Rita Redakteurin", "Rita Redakteurin")], v["ausbilder"]
        assert all("email" not in a for a in v["ausbilder"])
        # Die importierende Redakteurin steht schon (als Leitung des neuen Lehrgangs) – die Vorschau sagt es.
        assert [a["konto"]["eingetragen"] for a in v["ausbilder"] if a["konto"]] == [False, False, True]
        assert v["ausbilder_nicht_uebernommen"] == nicht, v["ausbilder_nicht_uebernommen"]

        r = senden(f"{API}/import")
        assert r.status_code == 201, r.get_json()
        e = r.json
        assert e["ausbilder_neu"] == 2 and e["ausbilder_nicht_uebernommen"] == nicht, e
        lg = e["lehrgang"]
        assert [(a["user_id"], a["name"], a["ist_leitung"]) for a in lg["ausbilder"]] == [
            (red_id, "Rita Redakteurin", True), (mail_id, "Mira Mailbekannt", True), (name_id, "Nils Namensgleich", False)]
        # Erneut in denselben Lehrgang: niemand doppelt, dieselbe Liste „nicht übernommen“.
        r = senden(f"{API}/import", lehrgang_id=str(lg["id"]))
        assert r.status_code == 201 and r.json["ausbilder_neu"] == 0, r.get_json()
        assert r.json["ausbilder_nicht_uebernommen"] == nicht and len(r.json["lehrgang"]["ausbilder"]) == 3
        # Nur Ausbilder, die alle nicht passen, und keine Teilnehmenden: nichts zu übernehmen – mit den Namen.
        datei[:] = [["Vorname", "Nachname", "Rolle"], ["Ulla", "Unbekannt", "Ausbilderin"]]
        r = senden(f"{API}/import")
        assert r.status_code == 400 and "kein Konto mit Riegenkarten-Stufe: Ulla Unbekannt" in r.json["error"], r.get_json()
        print("Import-Zuordnungs-Test bestanden.")


class _Protokoll(logging.Handler):
    def __init__(self):
        super().__init__()
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append(record.getMessage())


def test_migration_34():
    """Vorversion (Schema 33) mit Freitext-Ausbildern: eindeutig (mit und ohne Leitung) → verknüpft, Funktion und
    Leitung bleiben; zweimal derselbe Name und schon verknüpft → eine Zeile; mehrdeutig, unbekannt, Konto ohne Stufe,
    deaktiviert → entfernt, die Beschreibung bleibt unverändert, das Startprotokoll nennt die Entfernten je Lehrgang;
    ein verknüpftes Konto ohne Stufe bleibt (markiert). Abbruch: alles wie vorher. Zweiter Start: nichts ändert sich."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        from app.material import models
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        konten = {}
        for mail, name, stufe, aktiv in (("e@example.org", "Eva Eindeutig", MITGLIED, 1),
                                         ("l@example.org", "Leo Leitung", REDAKTEUR, 1),
                                         ("d1@example.org", "Dana Doppelt", MITGLIED, 1),
                                         ("d2@example.org", "Dana Doppelt", VERWALTUNG, 1),
                                         ("o@example.org", "Otto Ohnestufe", 0, 1),
                                         ("x@example.org", "Xenia Deaktiviert", MITGLIED, 0),
                                         ("k@example.org", "Karl Konto", 0, 1)):
            konten[name if name != "Dana Doppelt" else mail] = conn.execute(
                "INSERT INTO users (email, password_hash, name, recht_pruefungen, active, created_at) "
                "VALUES (?,?,?,?,?,?)", (mail, "x", name, stufe, aktiv, "2026-01-01T00:00:00")).lastrowid

        def lehrgang(titel):
            return conn.execute("INSERT INTO pruef_lehrgaenge (titel, beschreibung, created_at, updated_at) "
                                "VALUES (?, 'Treffpunkt am Wehr', '2026-01-01', '2026-01-01')", (titel,)).lastrowid

        def ausbilder(lid, uid, name, funktion="", leit=0, sort=0):
            conn.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, ist_leitung, sortierung) "
                         "VALUES (?,?,?,?,?,?)", (lid, uid, name, funktion, leit, sort))
        a = lehrgang("SR1 Alt")
        ausbilder(a, None, "eva  EINDEUTIG", "Wasser", 0, 0)                 # Schreibweise egal
        ausbilder(a, None, "Leitung, Leo", "Lehrgangsleitung", 1, 1)         # „Nachname, Vorname“
        ausbilder(a, None, "Dana Doppelt", "Seil", 0, 2)                     # mehrdeutig
        ausbilder(a, None, "Ulf Unbekannt", "", 1, 3)                        # unbekannt, Leitung
        ausbilder(a, konten["Karl Konto"], "Karl Konto", "Boot", 0, 4)      # verknüpft, ohne Stufe
        b = lehrgang("SR2 Alt")
        ausbilder(b, konten["Eva Eindeutig"], "Eva Eindeutig", "", 0, 0)     # schon verknüpft …
        ausbilder(b, None, "Eva Eindeutig", "Leitung Wasser", 1, 1)          # … und als Freitext dazu
        ausbilder(b, None, "Otto Ohnestufe", "Referent", 0, 2)               # Konto ohne Stufe
        ausbilder(b, None, "Xenia Deaktiviert", "", 0, 3)                    # Konto deaktiviert
        c = lehrgang("Ohne Freitext")
        ausbilder(c, konten["Leo Leitung"], "Leo Leitung", "", 1, 0)
        conn.execute("UPDATE mat_meta SET wert = '33' WHERE schluessel = 'schema_version'")
        conn.commit()

        def abzug():
            k = sqlite3.connect(pfad)
            try:
                return "\n".join(k.iterdump())
            finally:
                k.close()

        def zeilen(lid):
            k = sqlite3.connect(pfad)
            try:
                return [tuple(z) for z in k.execute("SELECT user_id, name, funktion, ist_leitung FROM pruef_ausbilder "
                                                    "WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,))]
            finally:
                k.close()
        vorher = abzug()

        # Abbruch mitten im Schritt: nichts ändert sich, nichts steht im Protokoll.
        protokoll = _Protokoll()
        logging.getLogger("app.material.models").addHandler(protokoll)
        try:
            alt = models.SCHRITTE[34]

            def bricht(k):
                alt(k)
                raise RuntimeError("Abbruch (Probe)")
            models.SCHRITTE[34] = bricht
            try:
                try:
                    models.migrieren(conn)
                    raise AssertionError("Der Abbruch hätte durchschlagen müssen.")
                except RuntimeError:
                    pass
            finally:
                models.SCHRITTE[34] = alt
            conn.close()
            assert abzug() == vorher and protokoll.zeilen == [], protokoll.zeilen

            make_app(tmp)                                       # Neustart: Schritt 34 läuft
        finally:
            logging.getLogger("app.material.models").removeHandler(protokoll)
        assert zeilen(a) == [(konten["Eva Eindeutig"], "eva  EINDEUTIG", "Wasser", 0),
                             (konten["Leo Leitung"], "Leitung, Leo", "Lehrgangsleitung", 1),
                             (konten["Karl Konto"], "Karl Konto", "Boot", 0)], zeilen(a)
        assert zeilen(b) == [(konten["Eva Eindeutig"], "Eva Eindeutig", "Leitung Wasser", 1)], zeilen(b)
        assert zeilen(c) == [(konten["Leo Leitung"], "Leo Leitung", "", 1)]
        k = sqlite3.connect(pfad)
        assert {r[0] for r in k.execute("SELECT beschreibung FROM pruef_lehrgaenge")} == {"Treffpunkt am Wehr"}
        assert k.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "34"
        k.close()
        assert protokoll.zeilen == [
            # Je Verknüpfung eine Zeile (Lehrgang, Freitext → Konto; Datenschutz-Hinweis der zweiten Durchsicht).
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR1 Alt“ – Freitext „eva  EINDEUTIG“ (Wasser) mit Konto "
            f"{konten['Eva Eindeutig']} verknüpft",
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR1 Alt“ – Freitext „Leitung, Leo“ (Lehrgangsleitung) mit Konto "
            f"{konten['Leo Leitung']} verknüpft",
            f"Schritt 34 (Riegenkarten): Lehrgang {b} „SR2 Alt“ – Freitext „Eva Eindeutig“ (Leitung Wasser) mit der "
            f"vorhandenen Zeile von Konto {konten['Eva Eindeutig']} zusammengelegt",
            f"Schritt 34 (Riegenkarten): Lehrgang {a} „SR1 Alt“ – Ausbilder ohne passendes Konto entfernt: "
            "Dana Doppelt (Seil), Ulf Unbekannt",
            f"Schritt 34 (Riegenkarten): Lehrgang {b} „SR2 Alt“ – Ausbilder ohne passendes Konto entfernt: "
            "Otto Ohnestufe (Referent), Xenia Deaktiviert",
            "Schritt 34 (Riegenkarten): 2 Freitext-Ausbilder mit Konten verknüpft, 1 mit einer vorhandenen Zeile "
            "zusammengelegt, 4 entfernt."], protokoll.zeilen

        # Die Oberfläche zeigt die Namen der Konten und markiert Karl (ohne Stufe).
        app = make_app(tmp)
        adm = anmelden(app, "admin@example.org", "geheim123")
        lg = adm.get(f"{API}/lehrgaenge/{a}").json["lehrgang"]
        assert [(x["name"], x["zugriff"]) for x in lg["ausbilder"]] == [
            ("Eva Eindeutig", True), ("Leo Leitung", True), ("Karl Konto", False)], lg["ausbilder"]
        assert lg["beschreibung"] == "Treffpunkt am Wehr"

        # Zweiter Start: nichts ändert sich.
        erst = hashlib.sha256(abzug().encode()).hexdigest()
        make_app(tmp)
        assert hashlib.sha256(abzug().encode()).hexdigest() == erst
        print("Migrations-Test (Schritt 34) bestanden.")


if __name__ == "__main__":
    test_anlegen_und_bearbeiten()
    test_import_zuordnung()
    test_migration_34()
