"""Formular-Pool je Kategorie (Schritt 38, Wunsch vom 04.11.2026):  python tests/test_material_formular_pool.py  oder
pytest tests/test_material_formular_pool.py

Grundlage: planung/formular-pool/entwurf.md, Abschnitt 6 „Entscheidungen des Nutzers“ (S1–S2, Z1–Z6, O1–O7, M1–M3,
R1, E1–E3, U1) und der Bauauftrag mit Nachtrag. Ersetzt test_material_formular_uebernahme.py (Schritt 35/36).
  - Auflösung: Zuweisung am Produkt → Standard der Kategorie → der nächsten Oberkategorie (S1) → keins (S2); eine neue
    aktive Version gilt sofort für alle Zuweisungen; eine laufende Prüfung behält ihre Version.
  - Zuweisen (vollständige Menge je Formular): nur im Teilbaum der Heimat (Z1), Standard einer Unterkategorie aus dem
    Pool darüber (Z2), ausdrücklich auch das Standardformular (Z3), nur mit aktiver Version, Deaktivieren und Löschen
    gesperrt, solange zugewiesen (Z4), ein Haken holt eine Zuweisung her (Z5), Länge, Journal; Verschieben löst, was aus
    dem Teilbaum fiele (Z6), und sagt es vorher (…/formular-pool/folgen).
  - Titel Pflicht (O5), „Prüfpunkte übernehmen von“ und „Kopie anlegen“ (O4), Produkt und Kategorie löschen.
  - Rechte je Rolle (O6 B: die Seite „Prüfformulare“ nur für die Material-Verwaltung, Formularseiten für alle mit
    Modulzugang); die Übernehmen-Routen aus Schritt 35 antworten 404.
  - Trigger gegen Zuweisungen außerhalb des Teilbaums per SQL von Hand.
  - Migration 37 → 38 mit Altbestand (generisch aktiv/inaktiv, spezifisch aktiv/inaktiv, Verweis gleiche Kategorie,
    Unterkategorie, andere Kategorie im selben Baum und in einem anderen, Quelle ohne aktive Version, Titel leer
    benutzt/unbenutzt, DEMO): je Produkt dieselbe Version, Kennungen und Prüfungen unverändert, Journal, Startprotokoll,
    Integrität; zweiter Lauf ändert nichts; Abbruch bei Abweichung lässt die Datenbank, wie sie war.
  - Zähler katalog_stand (Nachtrag: Zwischenspeicher der Übung erkennt zwei Änderungen in derselben Sekunde).
Export und Import (Format 3, alte Formate) stehen in test_material_formular_transfer.py. Alle Namen, Hersteller und
Prüfpunkte hier sind erfundene Platzhalter."""
import contextlib
import json
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, abschluss, anmelden, formular_neu, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, neues_konto, pdf_seiten, protokoll_zeile, starten, umgebung)
from test_material_trennung import bis_schritt  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "/api/material"
JA = [{"text": "Platzhalter Ja", "art": "yesno", "soll": "ja"}]


def produkt_neu(c, kategorie, modell, nr, **felder):
    r = c.post(f"{API}/produkte", json=dict({"category_id": kategorie, "manufacturer": "Testwerk", "model": modell,
                                             "article_no": nr, "material_kind": "metall_hardware",
                                             "interval_months": 12}, **felder))
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def kategorie_neu(c, name, parent=None, **felder):
    r = c.post(f"{API}/kategorien", json=dict({"name": name, "parent_id": parent}, **felder))
    assert r.status_code == 201, r.get_json()
    return r.json["kategorie"]["id"]


def pool_neu(c, kategorie, titel, punkte=JA, aktivieren=True, **d):
    """Ein Formular im Pool – liefert (Formular, Version)."""
    r = c.post(f"{API}/formular-pool", json=dict({"kategorie_id": kategorie, "titel": titel, "punkte": punkte}, **d))
    assert r.status_code == 201, r.get_json()
    f = r.json["formular"]
    if aktivieren:
        assert c.post(f"{API}/formulare/{f['id']}/aktivieren", json={}).status_code == 200
    return f["formular_id"], f["id"]


def zuweisen(c, pf, kategorien=(), produkte=()):
    return c.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": list(kategorien), "produkte": list(produkte)})


def geltend(c, pid):
    r = c.get(f"{API}/produkte/{pid}")
    assert r.status_code == 200, r.get_json()
    return r.json["produkt"]["formular"]


def aufbau(tmp):
    """katalog_grund (PSA gegen Absturz › Gurte, Karabiner) und darunter „Karabiner › Verschluss (Test)“, je ein
    Produkt A und B in Karabiner, C in der Unterkategorie."""
    app, k = umgebung(tmp)
    kp = k["katalog"]
    ids = katalog_grund(k["adm"])
    ids["unter"] = kategorie_neu(kp, "Verschluss (Test)", ids["karabiner"])
    ids["a"] = produkt_neu(kp, ids["karabiner"], "Platzhalter A", "PA-1")
    ids["b"] = produkt_neu(kp, ids["karabiner"], "Platzhalter B", "PB-1")
    ids["c"] = produkt_neu(kp, ids["unter"], "Platzhalter C", "PC-1")
    return app, k, ids


def test_aufloesung_und_zuweisen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        # S2: ohne alles kein Formular.
        assert geltend(kp, ids["c"]) is None
        # S1: Standard an „PSA gegen Absturz“ gilt in jeder Unterkategorie ohne eigenen.
        psa, psa_v = pool_neu(kp, ids["psa"], "Platzhalter PSA")
        assert zuweisen(kp, psa, kategorien=[ids["psa"]]).json["geaendert"] == 1
        f = geltend(kp, ids["c"])
        assert f["id"] == psa_v and f["art"] == "standard" and f["quelle"] == "Standard der Kategorie „PSA gegen Absturz“"
        assert f["formular"] == {"id": psa, "titel": "Platzhalter PSA", "heimat": {"id": ids["psa"],
                                                                                   "name": "PSA gegen Absturz"}}
        assert f["standard_von"] == {"id": ids["psa"], "name": "PSA gegen Absturz"}
        # Z2: Unterkategorie „Karabiner“ bekommt als Standard ein Formular aus dem Pool von „PSA gegen Absturz“.
        kara, kara_v = pool_neu(kp, ids["psa"], "Platzhalter Karabiner")
        assert zuweisen(kp, kara, kategorien=[ids["karabiner"]]).status_code == 200
        assert geltend(kp, ids["c"])["id"] == kara_v and geltend(kp, ids["a"])["id"] == kara_v
        # Zuweisung an ein Produkt geht dem Standard vor.
        eigen, eigen_v = pool_neu(kp, ids["karabiner"], "Platzhalter Eigen")
        r = zuweisen(kp, eigen, produkte=[ids["a"]])
        assert r.status_code == 200 and r.json["geaendert"] == 1, r.get_json()
        assert r.json["formular"]["zugewiesen"][0]["id"] == ids["a"] and r.json["formular"]["wirksam_n"] == 1
        f = geltend(kp, ids["a"])
        assert f["id"] == eigen_v and f["art"] == "zugewiesen" and f["quelle"] == "dem Produkt zugewiesen"
        # Eine neue aktive Version gilt sofort für alle Zuweisungen.
        neu = kp.post(f"{API}/formulare", json={"formular_id": eigen, "vorlage_id": eigen_v}).json["formular"]
        assert neu["version"] == 2 and neu["titel"] == "Platzhalter Eigen"
        assert geltend(kp, ids["a"])["id"] == eigen_v                      # Entwurf gilt noch nicht
        assert kp.post(f"{API}/formulare/{neu['id']}/aktivieren", json={}).status_code == 200
        assert geltend(kp, ids["a"])["id"] == neu["id"]
        # Z1: nur im Teilbaum der Heimat – Gurt (in Gurte) liegt nicht unter „Karabiner“.
        r = zuweisen(kp, eigen, produkte=[ids["a"], ids["gurt"]])
        assert r.status_code == 409 and "liegt nicht unter „PSA gegen Absturz / Karabiner“" in r.json["error"], r.json
        r = zuweisen(kp, eigen, kategorien=[ids["gurte"]], produkte=[ids["a"]])
        assert r.status_code == 409 and "Gurte" in r.json["error"], r.json
        # Z5: Ein Haken holt die Zuweisung her – Karabiner-Standard wechselt zu „Platzhalter Eigen“.
        r = zuweisen(kp, eigen, kategorien=[ids["karabiner"]], produkte=[ids["a"]])
        assert r.status_code == 200 and r.json["geaendert"] == 1, r.get_json()
        assert geltend(kp, ids["b"])["id"] == neu["id"] and geltend(kp, ids["b"])["art"] == "standard"
        kand = kp.get(f"{API}/formular-pool/{kara}/kandidaten").json
        zeile = next(x for x in kand["kategorien"] if x["id"] == ids["karabiner"])
        assert zeile["bisher"] == {"id": eigen, "titel": "Platzhalter Eigen"} and not zeile["gewaehlt"]
        # Journal am Formular, das die Zuweisung verlor, und am Produkt.
        journal = kp.get(f"{API}/formulare/{kara_v}").json["formular"]["journal"]
        assert any(j["action"] == "zuweisung_geloest" and j["entity"] == "formular" for j in journal), journal
        pj = kp.get(f"{API}/produkte/{ids['a']}").json["produkt"]["journal"]
        assert any(j["action"] == "formular_zugewiesen" and j["nachher"]["formular"] == "Platzhalter Eigen"
                   for j in pj), pj
        # Z3: B ausdrücklich dem Formular zuweisen, das ohnehin Standard ist – bleibt bei einem Wechsel des Standards.
        kand = kp.get(f"{API}/formular-pool/{eigen}/kandidaten").json
        b = next(x for x in kand["produkte"] if x["id"] == ids["b"])
        assert b["ueber_standard"] and b["standard"] == {"id": eigen, "titel": "Platzhalter Eigen"} and not b["gewaehlt"]
        assert zuweisen(kp, eigen, kategorien=[ids["karabiner"]], produkte=[ids["a"], ids["b"]]).json["geaendert"] == 1
        assert zuweisen(kp, kara, kategorien=[ids["karabiner"]]).json["geaendert"] == 1
        assert geltend(kp, ids["b"])["id"] == neu["id"] and geltend(kp, ids["c"])["id"] == kara_v
        # Lösen: A fällt auf den Standard zurück.
        assert zuweisen(kp, eigen, produkte=[ids["b"]]).json["geaendert"] == 1
        assert geltend(kp, ids["a"])["id"] == kara_v
        # Z4: ohne aktive Version nicht zuweisen; zugewiesen nicht deaktivieren, nicht löschen.
        ent, ent_v = pool_neu(kp, ids["karabiner"], "Platzhalter Entwurf", aktivieren=False)
        r = zuweisen(kp, ent, produkte=[ids["a"]])
        assert r.status_code == 409 and "aktiver Version" in r.json["error"], r.json
        assert kp.get(f"{API}/formular-pool/{ent}/kandidaten").json["grund"]
        r = kp.post(f"{API}/formulare/{neu['id']}/deaktivieren", json={})
        assert r.status_code == 409 and "Testwerk Platzhalter B" in r.json["error"], r.json
        r = kp.delete(f"{API}/formulare/{neu['id']}", headers=H)
        assert r.status_code == 409, (r.status_code, r.get_json())
        # Ein unbenutzter Entwurf als letzte Version: Löschen nimmt das Formular mit aus dem Pool.
        r = kp.delete(f"{API}/formulare/{ent_v}", headers=H)
        assert r.status_code == 200 and r.json["formular_geloescht"] is True, r.get_json()
        assert kp.get(f"{API}/formular-pool/{ent}/kandidaten").status_code == 404
        # Länge: Ein Formular mit „Länge (m)“ lässt sich keinem Produkt ohne Artikellänge zuweisen.
        lang, _ = pool_neu(kp, ids["karabiner"], "Platzhalter Länge", punkte=[{"text": "Platzhalter Länge",
                                                                             "art": "laenge"}])
        kand = kp.get(f"{API}/formular-pool/{lang}/kandidaten").json
        assert kand["laenge"] and "keine Länge" in next(x for x in kand["produkte"] if x["id"] == ids["b"])["grund"]
        r = zuweisen(kp, lang, produkte=[ids["b"]])
        assert r.status_code == 409 and "Länge" in r.json["error"], r.json
        # Pool-Seite: Baum mit Standard (eigen oder geerbt) und den Formularen je Pool.
        pool = kp.get(f"{API}/formular-pool").json
        kats = {x["name"]: x for x in pool["kategorien"]}
        assert kats["Gurte"]["standard"]["geerbt_von"] == {"id": ids["psa"], "name": "PSA gegen Absturz"}
        assert kats["Verschluss (Test)"]["standard"]["titel"] == "Platzhalter Karabiner"
        titel = {f["titel"]: f for f in kats["Karabiner"]["formulare"]}
        assert set(titel) == {"Platzhalter Eigen", "Platzhalter Länge"}, titel
        assert titel["Platzhalter Eigen"]["zugewiesen"][0]["id"] == ids["b"]
        assert titel["Platzhalter Eigen"]["wirksam_n"] == 1 and titel["Platzhalter Eigen"]["versionen"] == 2
        assert titel["Platzhalter Länge"]["aktive_version"]["version"] == 1 and titel["Platzhalter Länge"]["wirksam_n"] == 0
        nur = kp.get(f"{API}/formular-pool?kategorie={ids['karabiner']}").json
        assert [x["name"] for x in nur["kategorien"]] == ["Karabiner", "Verschluss (Test)"], nur
        # Formularseite: „Gilt für“ und die Liste der Produkte.
        f = kp.get(f"{API}/formulare/{kara_v}").json["formular"]
        assert f["formular"]["standard_fuer"] == [{"id": ids["karabiner"], "name": "PSA gegen Absturz / Karabiner"}]
        assert f["formular"]["wirksam_n"] == 3 and f["formular"]["heimat"]["name"] == "PSA gegen Absturz", f["formular"]
        assert [p["name"] for p in kp.get(f"{API}/formulare/{kara_v}/wirksam").json["produkte"]] == [
            "Testwerk HMS Beta", "Testwerk Platzhalter A", "Testwerk Platzhalter C"]
        assert [v["version"] for v in kp.get(f"{API}/formulare?formular={eigen}").json["formulare"]] == [2, 1]
    print("Auflösung und Zuweisen bestanden.")


def test_titel_kopie_und_vorlage():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        # O5: Titel Pflicht – beim Anlegen, Speichern und einer neuen Version ohne Titel.
        r = kp.post(f"{API}/formular-pool", json={"kategorie_id": ids["karabiner"], "titel": "  "})
        assert r.status_code == 400 and "Titel" in r.json["error"], r.json
        pf, v1 = pool_neu(kp, ids["karabiner"], "Platzhalter Vorlage", punkte=[
            {"gruppe": "Platzhalter Gruppe", "text": "Platzhalter Eins", "art": "yesno", "soll": "nein"},
            {"text": "Platzhalter Zwei", "art": "text", "pflicht": False}], aktivieren=False)
        r = kp.put(f"{API}/formulare/{v1}", json={"titel": ""})
        assert r.status_code == 400 and "Titel" in r.json["error"], r.json
        # Bis Schema 37: Ziel statt Formular – abgelehnt mit dem neuen Weg.
        r = kp.post(f"{API}/formulare", json={"kategorie_id": ids["karabiner"]})
        assert r.status_code == 400 and "formular-pool" in r.json["error"], r.json
        # O4: „Prüfpunkte übernehmen von …“ (vorlage_id) und „Kopie anlegen“ – ein neues Formular mit den Punkten.
        r = kp.post(f"{API}/formular-pool", json={"kategorie_id": ids["unter"], "titel": "Platzhalter Kopie",
                                                   "vorlage_id": v1})
        assert r.status_code == 201, r.get_json()
        kopie = r.json["formular"]
        assert kopie["version"] == 1 and kopie["formular_id"] != pf and not kopie["aktiv"]
        assert [(p["gruppe"], p["text"], p["art"], p["soll"], p["pflicht"]) for p in kopie["punkte"]] == [
            ("Platzhalter Gruppe", "Platzhalter Eins", "yesno", "nein", True),
            ("", "Platzhalter Zwei", "text", "", False)], kopie["punkte"]
        # Ohne Vorlage leer; die Heimat muss es geben.
        r = kp.post(f"{API}/formular-pool", json={"kategorie_id": ids["unter"], "titel": "Platzhalter Leer"})
        assert r.status_code == 201 and r.json["formular"]["punkte"] == []
        assert kp.post(f"{API}/formular-pool", json={"kategorie_id": 99999, "titel": "X"}).status_code == 404
        # Journal des Formulars: angelegt mit Heimat.
        j = kp.get(f"{API}/formulare/{kopie['id']}").json["formular"]["journal"]
        assert any(x["entity"] == "formular" and x["action"] == "angelegt"
                   and x["nachher"]["heimat"] == "PSA gegen Absturz / Karabiner / Verschluss (Test)" for x in j), j
    print("Titel, Kopie und Vorlage bestanden.")


def test_verschieben_loeschen_trigger():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        pf, v = pool_neu(kp, ids["karabiner"], "Platzhalter Karabiner")
        assert zuweisen(kp, pf, kategorien=[ids["unter"]], produkte=[ids["a"], ids["c"]]).status_code == 200
        # Z6 Produkt: Vorher sagt …/folgen, was gelöst würde – innerhalb des Teilbaums nichts.
        r = kp.get(f"{API}/formular-pool/folgen?produkt={ids['c']}&kategorie={ids['karabiner']}")
        assert r.status_code == 200 and r.json["folgen"] == [], r.json
        r = kp.get(f"{API}/formular-pool/folgen?produkt={ids['a']}&kategorie={ids['gurte']}")
        assert r.json["folgen"] == [{"formular_id": pf, "formular": "Platzhalter Karabiner",
                                     "ziel": "„Testwerk Platzhalter A“"}], r.json
        r = kp.put(f"{API}/produkte/{ids['a']}", json={"category_id": ids["gurte"], "material_kind": "metall_hardware"})
        assert r.status_code == 200, r.get_json()
        assert r.json["produkt"]["formular"] is None                          # Gurte hat keinen Standard
        pj = kp.get(f"{API}/produkte/{ids['a']}").json["produkt"]["journal"]
        assert any(j["action"] == "formular_zuweisung_geloest" and j["nachher"] == {
            "grund": "Produkt in eine andere Kategorie verschoben"} for j in pj), pj
        # Z6 Kategorie: „Verschluss“ unter „Gurte“ – Standard dort und die Zuweisung an C fallen aus dem Teilbaum.
        r = kp.get(f"{API}/formular-pool/folgen?kategorie={ids['unter']}&parent={ids['gurte']}")
        assert sorted(x["ziel"] for x in r.json["folgen"]) == [
            "Kategorie „PSA gegen Absturz / Karabiner / Verschluss (Test)“", "„Testwerk Platzhalter C“"], r.json
        r = kp.put(f"{API}/kategorien/{ids['unter']}", json={"parent_id": ids["gurte"]})
        assert r.status_code == 200, r.get_json()
        assert geltend(kp, ids["c"]) is None
        assert kp.get(f"{API}/formulare/{v}").json["formular"]["formular"]["zugewiesen"] == []
        # Zurück unter Karabiner: nichts kommt von selbst wieder; Umhängen innerhalb des Teilbaums löst nichts.
        assert kp.put(f"{API}/kategorien/{ids['unter']}", json={"parent_id": ids["karabiner"]}).status_code == 200
        assert zuweisen(kp, pf, kategorien=[ids["unter"]], produkte=[ids["c"]]).status_code == 200
        kp.put(f"{API}/kategorien/{ids['karabiner']}", json={"name": "Karabiner"})        # nur Name: nichts
        assert geltend(kp, ids["c"])["id"] == v
        # Trigger gegen SQL von Hand (das Netz hinter den Diensten).
        with app.app_context():
            from app import db
            for sql, args in (
                    ("INSERT INTO mat_formular_zuweisung (formular_id, product_id, created_at) VALUES (?, ?, 'x')",
                     (pf, ids["gurt"])),
                    ("INSERT INTO mat_formular_zuweisung (formular_id, category_id, created_at) VALUES (?, ?, 'x')",
                     (pf, ids["gurte"])),
                    ("UPDATE mat_product SET category_id = ? WHERE id = ?", (ids["gurte"], ids["c"])),
                    ("UPDATE mat_category SET parent_id = ? WHERE id = ?", (ids["gurte"], ids["unter"])),
                    ("UPDATE mat_formular SET category_id = ? WHERE id = ?", (ids["gurte"], pf))):
                try:
                    with db.transaction():
                        db.execute(sql, args)
                    raise AssertionError(sql)
                except sqlite3.IntegrityError as exc:
                    assert "nur in seiner Kategorie" in str(exc), exc
            # Umhängen, das alles im Teilbaum lässt, geht auch von Hand; ebenso ein Formular eine Ebene höher.
            with db.transaction():
                db.execute("UPDATE mat_formular SET category_id = ? WHERE id = ?", (ids["psa"], pf))
                db.execute("UPDATE mat_formular SET category_id = ? WHERE id = ?", (ids["karabiner"], pf))
        # Produkt löschen: Die Zuweisung geht mit (Journal am Formular).
        assert zuweisen(kp, pf, kategorien=[ids["unter"]], produkte=[ids["c"], ids["b"]]).status_code == 200
        assert kp.delete(f"{API}/produkte/{ids['b']}", headers=H).status_code == 200
        j = kp.get(f"{API}/formulare/{v}").json["formular"]["journal"]
        assert any(x["action"] == "zuweisung_geloest" and x["vorher"] == {"produkt": "Testwerk Platzhalter B"}
                   and x["nachher"] == {"grund": "Produkt gelöscht"} for x in j), j
        # Kategorie löschen: ihre Formulare (unbenutzt) und ein Standard aus dem Pool darüber gehen mit.
        leer = kategorie_neu(kp, "Leer (Test)", ids["karabiner"])
        lf, _ = pool_neu(kp, leer, "Platzhalter Leer")
        assert zuweisen(kp, lf, kategorien=[leer]).status_code == 200
        assert zuweisen(kp, pf, kategorien=[ids["unter"], leer], produkte=[ids["c"]]).status_code == 200
        assert kp.delete(f"{API}/kategorien/{leer}", headers=H).status_code == 200
        assert kp.get(f"{API}/formular-pool/{lf}/kandidaten").status_code == 404
        assert kp.get(f"{API}/formulare/{v}").json["formular"]["formular"]["standard_fuer"] == [
            {"id": ids["unter"], "name": "PSA gegen Absturz / Karabiner / Verschluss (Test)"}]
    print("Verschieben, Löschen und Trigger bestanden.")


def test_pruefung_und_protokoll():
    """Eine Prüfung nimmt das zugewiesene Formular; eine laufende behält ihre Version, auch wenn die Zuweisung wechselt;
    eine benutzte Version bleibt unverändert; das Protokoll nennt die Heimat; Kategorie mit benutzter Version → 409."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        pf, v = pool_neu(kp, ids["unter"], "Platzhalter Verschluss", punkte=[
            {"text": "Platzhalter Verschluss", "art": "yesno", "soll": "ja"}])
        assert zuweisen(kp, pf, produkte=[ids["c"]]).status_code == 200
        gid, _ = gliederung(w)
        a1 = neuer_artikel(w, ids["c"], gid)
        a2 = neuer_artikel(w, ids["c"], gid)
        artikel = w.get(f"{API}/artikel/{a1['id']}").json["artikel"]
        assert artikel["formular"]["id"] == v and artikel["formular"]["quelle"] == "dem Produkt zugewiesen"
        pr = starten(p1, a1["id"]).json["pruefung"]
        assert pr["formular"]["id"] == v
        laufend = starten(p1, a2["id"]).json["pruefung"]
        # Zuweisung wechselt während die zweite Prüfung läuft: sie behält ihre Version.
        anders, anders_v = pool_neu(kp, ids["unter"], "Platzhalter Anders")
        assert zuweisen(kp, anders, produkte=[ids["c"]]).status_code == 200
        assert p1.get(f"{API}/pruefungen/{laufend['id']}").json["pruefung"]["formular"]["id"] == v
        assert geltend(kp, ids["c"])["id"] == anders_v
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        zeile = protokoll_zeile(app, pr["id"])
        text = " ".join(" ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"]))).split())
        assert "„Platzhalter Verschluss“, Version 1 (Prüfformular der Kategorie „Verschluss (Test)“)" in text, text[:3000]
        # Benutzt: unveränderlich, nicht löschbar; die Kategorie seines Pools auch nicht – auch nachdem das Produkt
        # fortgezogen ist (seine Zuweisung fällt dabei, Z6).
        assert kp.put(f"{API}/formulare/{v}", json={"titel": "Anders"}).status_code == 409
        assert kp.get(f"{API}/formulare/{v}").json["formular"]["benutzt"] is True
        assert kp.put(f"{API}/produkte/{ids['c']}", json={"category_id": ids["karabiner"]}).status_code == 200
        r = kp.delete(f"{API}/kategorien/{ids['unter']}", headers=H)
        assert r.status_code == 409 and "Prüfungen benutzt" in r.json["error"], r.get_json()
    print("Prüfung und Protokoll bestanden.")


def test_rechte_und_routen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp, adm = k["katalog"], k["adm"]
        pf, v = pool_neu(kp, ids["karabiner"], "Platzhalter Rechte")
        demo, _ = neues_konto(app, "demo-konto@example.invalid", "lesen")
        gliederung(adm)
        # Ohne Modulzugang: 403 überall; Mitglied (auch DEMO-Konto): Formularseite lesen, Pool nicht.
        for c, pool_code, lesen_code in ((k["nutzer"], 403, 403), (k["fuehrung"], 403, 200), (k["pruefer"], 403, 200),
                                         (demo, 403, 200), (k["wart"], 403, 200), (kp, 200, 200), (adm, 200, 200)):
            assert c.get(f"{API}/formular-pool").status_code == pool_code
            assert c.get(f"{API}/formular-pool/{pf}/kandidaten").status_code == pool_code
            assert c.get(f"{API}/formular-pool/folgen?produkt={ids['a']}&kategorie={ids['gurte']}").status_code == pool_code
            assert c.get(f"{API}/formulare/{v}").status_code == lesen_code
            assert c.get(f"{API}/formulare/{v}/wirksam").status_code == lesen_code
            seite = c.get("/materialablage/katalog/formulare")
            assert seite.status_code == (200 if pool_code == 200 else 403), seite.status_code
            if pool_code != 200:
                assert c.post(f"{API}/formular-pool", json={"kategorie_id": ids["karabiner"], "titel": "X"}).status_code == 403
                assert zuweisen(c, pf, produkte=[ids["a"]]).status_code == 403
                assert c.post(f"{API}/formulare", json={"formular_id": pf}).status_code == 403
        assert "nur die Material-Verwaltung" in k["fuehrung"].get("/materialablage/katalog/formulare").get_data(as_text=True)
        assert zuweisen(adm, pf, produkte=[ids["a"]]).status_code == 200            # Plattform-Verwaltung darf
        # Die Übernehmen-Routen aus Schritt 35 gibt es nicht mehr.
        assert kp.get(f"{API}/produkte/{ids['a']}/formularquellen").status_code == 404
        assert kp.put(f"{API}/produkte/{ids['b']}/formular-von", json={"quelle": ids["a"]}).status_code in (404, 405)
        assert kp.delete(f"{API}/produkte/{ids['b']}/formular-von", headers=H).status_code in (404, 405)
        p = kp.get(f"{API}/produkte/{ids['a']}").json["produkt"]
        assert not {"formular_von", "formular_genutzt_von", "formulare"} & set(p), sorted(p)
        assert kp.get(f"{API}/formulare?kategorie={ids['karabiner']}").status_code == 400
        # Seite ohne Anmeldung: zur Anmeldung.
        with app.test_client() as anonym:
            assert anonym.get("/materialablage/katalog/formulare").status_code == 302
            assert anonym.get(f"{API}/formular-pool").status_code == 401
    print("Rechte und Routen bestanden.")


def test_katalog_stand():
    """Nachtrag: Der Zähler mat_meta.katalog_stand ändert sich bei jeder Änderung an Formularen, Zuweisungen und
    Produkten – auch zweimal in derselben Sekunde –, Lesen schreibt nichts; der Schlüssel der Übung folgt ihm."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        with app.app_context():
            from app import db
            from app.einfuehrung import _KATALOG_STAND

            def stand():
                return db.query("SELECT wert FROM mat_meta WHERE schluessel = 'katalog_stand'", one=True)["wert"]

            def schluessel():
                return db.query(_KATALOG_STAND, one=True)["stand"]
            vorher, s0 = stand(), schluessel()
        pf, v = pool_neu(kp, ids["karabiner"], "Platzhalter Stand", aktivieren=False)
        with app.app_context():
            s1, n1 = schluessel(), stand()
            assert s1 != s0 and int(n1) > int(vorher)
        kp.get(f"{API}/formular-pool")
        kp.get(f"{API}/produkte/{ids['a']}")
        with app.app_context():
            assert schluessel() == s1                                           # Lesen schreibt nichts
            # Zwei Änderungen in derselben Sekunde ohne updated_at (SQL von Hand): der Zähler sieht beide.
            with db.transaction():
                db.execute("UPDATE mat_checklist_item SET label = 'Platzhalter A' WHERE form_id = ?", (v,))
            s2 = schluessel()
            with db.transaction():
                db.execute("UPDATE mat_checklist_item SET label = 'Platzhalter B' WHERE form_id = ?", (v,))
            s3 = schluessel()
            assert len({s1, s2, s3}) == 3, (s1, s2, s3)
            for tabelle in ("mat_formular", "mat_formular_zuweisung", "mat_form", "mat_product", "mat_category"):
                assert {f"trg_{tabelle}_stand_{a}" for a in ("insert", "update", "delete")} <= {r["name"] for r in db.query(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'")}, tabelle
        assert kp.post(f"{API}/formulare/{v}/aktivieren", json={}).status_code == 200
        assert zuweisen(kp, pf, produkte=[ids["a"]]).status_code == 200
        with app.app_context():
            assert schluessel() != s3
    print("Katalog-Stand bestanden.")


# --- Migration 37 → 38 -------------------------------------------------------------------------------------------------

@contextlib.contextmanager
def startprotokoll():
    out = []
    h = logging.Handler()
    h.emit = lambda r: out.append(r.getMessage())
    log = logging.getLogger("app.material.models")
    log.addHandler(h)
    try:
        yield out
    finally:
        log.removeHandler(h)


def altbestand_37(tmp):
    """Stand 37 mit Altbestand (generisch/spezifisch/formular_von) – Katalog über die Dienste, Formulare per SQL in der
    alten Form. Liefert (Pfad, Kennungen)."""
    app = bis_schritt(37, nachruesten=False)(make_app, tmp)
    pfad = os.path.join(tmp, "stroemis.db")
    with app.test_request_context():
        from flask import g

        from app.material.services import katalog
        g.mat_akteur = "Test"
        ids = {}
        for name, oben in (("r1", None), ("k1", "r1"), ("k1a", "k1"), ("k2", "r1"), ("r2", None), ("k3", "r2"),
                           ("d", None)):
            ids[name] = katalog.kategorie_anlegen({"name": f"Platzhalter {name.upper()}", "parent_id": ids.get(oben)},
                                                  demo=name == "d")
        for name, kat in (("p1", "k1"), ("p2", "k1"), ("p3", "k1a"), ("p4", "k2"), ("p5", "k3"), ("p6", "k1"),
                          ("p7", "k2"), ("p8", "k3"), ("p9", "k3"), ("pd", "d"), ("pd2", "d")):
            ids[name] = katalog.produkt_anlegen({"category_id": ids[kat], "manufacturer": "Testwerk",
                                                 "model": f"Platzhalter {name.upper()}", "article_no": name.upper(),
                                                 "material_kind": "metall_hardware", "interval_months": 12})
    conn = sqlite3.connect(pfad)
    assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "37"
    assert "category_id" in [r[1] for r in conn.execute("PRAGMA table_info(mat_form)")]

    def form(spalte, ziel, version, titel, aktiv, punkte, demo=0):
        fid = conn.execute(f"INSERT INTO mat_form ({spalte}, version, title, valid_from, active, demo, created_at, "
                           "updated_at) VALUES (?,?,?,?,?,?,'2026-11-01T10:00:00+00:00','2026-11-01T10:00:00+00:00')",
                           (ziel, version, titel, "2026-11-01" if aktiv else None, aktiv, demo)).lastrowid
        for n, text in enumerate(punkte, 1):
            conn.execute("INSERT INTO mat_checklist_item (form_id, group_name, position, label, editor, mandatory, "
                         "expected_value) VALUES (?, '', ?, ?, 'yesno', 1, 'ja')", (fid, n, text))
        return fid
    ids["g1v1"] = form("category_id", ids["k1"], 1, "", 0, ["Platzhalter G1 alt"])        # benutzt, ohne Titel
    ids["g1v2"] = form("category_id", ids["k1"], 2, "Generisch K1", 1, ["Platzhalter G1"])
    ids["g3"] = form("category_id", ids["k3"], 1, "", 1, ["Platzhalter G3"])               # unbenutzt, ohne Titel
    ids["s1"] = form("product_id", ids["p1"], 1, "Spezifisch P1", 1, ["Platzhalter S1 a", "Platzhalter S1 b"])
    ids["s6"] = form("product_id", ids["p6"], 1, "", 0, ["Platzhalter S6"])                # ohne aktive Version
    ids["s9"] = form("product_id", ids["p9"], 1, "Spezifisch P9", 0, ["Platzhalter S9"])
    ids["gd"] = form("category_id", ids["d"], 1, "DEMO Platzhalter", 1, ["Platzhalter D"], demo=1)
    ids["sd"] = form("product_id", ids["pd"], 1, "DEMO spezifisch", 1, ["Platzhalter SD"], demo=1)
    for b, a in (("p2", "p1"), ("p3", "p1"), ("p4", "p1"), ("p5", "p1"), ("p8", "p9"), ("pd2", "pd")):
        conn.execute("UPDATE mat_product SET formular_von = ? WHERE id = ?", (ids[a], ids[b]))
    # g1v1 benutzt: ein Entwurf einer Prüfung (Ordner und Artikel von Hand).
    ordner = conn.execute("INSERT INTO mat_folder (name, created_at, updated_at) VALUES ('Platzhalter', 'x', 'x')").lastrowid
    item = conn.execute("INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, qr_token, created_at, "
                        "updated_at) VALUES (?, ?, 'PLATZ-1', 'M-900001', 'platzhalter1', 'x', 'x')",
                        (ids["p6"], ordner)).lastrowid
    ids["pruefung"] = conn.execute("INSERT INTO mat_inspection (item_id, form_id, form_version, inspected_on, kind, "
                                   "created_at, updated_at) VALUES (?, ?, 1, '2026-11-01', 'periodisch', 'x', 'x')",
                                   (item, ids["g1v1"])).lastrowid
    conn.commit()
    conn.close()
    return pfad, ids


def _formulare(conn):
    return conn.execute("SELECT id, version, title, valid_from, active, demo, created_at FROM mat_form ORDER BY id").fetchall()


def test_migration_37_38():
    with tempfile.TemporaryDirectory() as tmp:
        pfad, ids = altbestand_37(tmp)
        conn = sqlite3.connect(pfad)
        from app.material import models
        vorher = models._geltend_vorher_38(conn)
        assert vorher[ids["p2"]] == vorher[ids["p5"]] == ids["s1"] and vorher[ids["p6"]] == ids["g1v2"]
        assert vorher[ids["p7"]] is None and vorher[ids["p8"]] == ids["g3"]
        formen_vorher = _formulare(conn)
        punkte_vorher = conn.execute("SELECT * FROM mat_checklist_item ORDER BY id").fetchall()
        # Die Spalten von Stand 37 – Schritt 39 (Untergruppe) kommt beim Start gleich mit dazu.
        punkt_spalten = ", ".join(r[1] for r in conn.execute("PRAGMA table_info(mat_checklist_item)"))
        pruefung_vorher = conn.execute("SELECT * FROM mat_inspection ORDER BY id").fetchall()
        conn.close()
        with startprotokoll() as log:
            app = make_app(tmp)                                            # Start: Schritt 38
        conn = sqlite3.connect(pfad)
        conn.row_factory = sqlite3.Row
        assert (conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0]
                == str(models.SCHEMA_VERSION))                              # seit Schritt 39 nicht mehr das Ende
        spalten = [r[1] for r in conn.execute("PRAGMA table_info(mat_form)")]
        assert "category_id" not in spalten and "product_id" not in spalten and "formular_id" in spalten
        assert "formular_von" not in [r[1] for r in conn.execute("PRAGMA table_info(mat_product)")]
        namen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert not set(models.TRIGGER_WEG_38) & namen and "idx_mat_product_formular_von" not in namen
        assert {models._trigger_name(x) for x in models.TRIGGER_38} <= namen
        # Kennungen, Titel (bis auf M3), Prüfpunkte und Prüfungen unverändert.
        nachher = {r["id"]: r for r in conn.execute("SELECT * FROM mat_form")}
        for r in formen_vorher:
            n = nachher[r[0]]
            assert (n["version"], n["valid_from"], n["active"], n["demo"], n["created_at"]) == (r[1], r[3], r[4], r[5],
                                                                                                 r[6]), r
            if r[0] not in (ids["g3"], ids["s6"]):
                assert n["title"] == r[2], (r, dict(n))
        assert nachher[ids["g3"]]["title"] == "Prüfformular Platzhalter K3"            # M3: unbenutzt
        assert nachher[ids["s6"]]["title"] == "Prüfformular Testwerk Platzhalter P6"
        assert nachher[ids["g1v1"]]["title"] == ""                                       # M3: benutzt bleibt
        assert [tuple(r) for r in conn.execute(f"SELECT {punkt_spalten} FROM mat_checklist_item WHERE form_id IN "
                                               "(SELECT value FROM json_each(?)) ORDER BY id",
                                               (json.dumps([r[0] for r in formen_vorher]),))
                ] == [tuple(r) for r in punkte_vorher]
        assert [tuple(r) for r in conn.execute("SELECT * FROM mat_inspection ORDER BY id")] == [tuple(r) for r in
                                                                                                 pruefung_vorher]
        # Formulare und Zuweisungen.
        heimat = {r["id"]: r for r in conn.execute("SELECT * FROM mat_formular")}
        pf = {r[0]: nachher[r[0]]["formular_id"] for r in formen_vorher}
        assert pf[ids["g1v1"]] == pf[ids["g1v2"]] and heimat[pf[ids["g1v2"]]]["category_id"] == ids["k1"]
        assert heimat[pf[ids["g1v2"]]]["herkunft"] == "Kategorie „Platzhalter K1“"
        assert heimat[pf[ids["s1"]]]["category_id"] == ids["r1"]                       # M1: gemeinsame Oberkategorie
        assert heimat[pf[ids["s6"]]]["category_id"] == ids["k1"] and heimat[pf[ids["s9"]]]["category_id"] == ids["k3"]
        assert heimat[pf[ids["gd"]]]["demo"] == 1 and heimat[pf[ids["s1"]]]["demo"] == 0
        assert all(len(r["uid"]) == 32 for r in heimat.values())
        zuw = {(r["category_id"], r["product_id"]): r["formular_id"] for r in conn.execute(
            "SELECT * FROM mat_formular_zuweisung")}
        assert zuw[(ids["k1"], None)] == pf[ids["g1v2"]] and zuw[(ids["k3"], None)] == pf[ids["g3"]]
        for p in ("p1", "p2", "p3", "p4"):
            assert zuw[(None, ids[p])] == pf[ids["s1"]], p
        assert (None, ids["p6"]) not in zuw and (None, ids["p8"]) not in zuw and (None, ids["p9"]) not in zuw   # M2
        kopie = zuw[(None, ids["p5"])]
        assert kopie not in pf.values() and heimat[kopie]["category_id"] == ids["k3"]               # M1: Kopie
        kv = conn.execute("SELECT * FROM mat_form WHERE formular_id = ?", (kopie,)).fetchone()
        assert kv["active"] == 1 and kv["title"] == "Spezifisch P1" and kv["id"] > max(r[0] for r in formen_vorher)
        assert [r["label"] for r in conn.execute("SELECT label FROM mat_checklist_item WHERE form_id = ? ORDER BY position",
                                                 (kv["id"],))] == ["Platzhalter S1 a", "Platzhalter S1 b"]
        neu = models.geltend_je_produkt(conn)
        for p, alt in vorher.items():
            if p == ids["p5"]:
                assert neu[p][0] == kv["id"]
            else:
                assert neu.get(p, (None,))[0] == alt, (p, alt, neu.get(p))
        # Journal und Startprotokoll.
        journal = conn.execute("SELECT entity, action, after_json FROM mat_audit WHERE user_name = 'Migration Schritt 38'"
                               ).fetchall()
        assert sum(1 for j in journal if j["entity"] == "formular" and j["action"] == "angelegt") == len(heimat)
        assert any(j["entity"] == "product" and j["action"] == "formular_zugewiesen" for j in journal)
        assert any(j["entity"] == "category" and j["action"] == "standard_gesetzt" for j in journal)
        assert any(j["entity"] == "formular" and j["action"] == "verschoben" for j in journal)
        text = "\n".join(log)
        assert ("Schritt 38 (Materialablage): 8 Prüfformulare im Pool, 3 Standards von Kategorien, 7 Zuweisungen an "
                "Produkte" in text), text
        assert "aus einem anderen Kategorienbaum" in text and "gemeinsamen Oberkategorie" in text, text
        assert "keine aktive Version hat" in text and "ohne aktive Version" in text and "ohne Titel ist schon benutzt" in text
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Zweiter Lauf des Schritts und zweiter Start ändern nichts.
        stand = [tuple(r) for t in ("mat_form", "mat_formular", "mat_formular_zuweisung", "mat_checklist_item",
                                    "mat_audit") for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
        models._schritt_38(conn)
        conn.commit()
        assert [tuple(r) for t in ("mat_form", "mat_formular", "mat_formular_zuweisung", "mat_checklist_item",
                                   "mat_audit") for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")] == stand
        conn.close()
        make_app(tmp)
        # Mit der App: Produktseite wie vorher, Pool zeigt die benutzte Version ohne Titel mit Herkunft.
        adm = anmelden(app, "admin@example.org", "geheim123")
        assert geltend(adm, ids["p8"])["quelle"] == "Standard der Kategorie „Platzhalter K3“"
        k1 = next(x for x in adm.get(f"{API}/formular-pool").json["kategorien"] if x["id"] == ids["k1"])
        assert {f["titel"] for f in k1["formulare"]} == {"Generisch K1", "Prüfformular Testwerk Platzhalter P6"}
    print("Migration 37 → 38 bestanden.")


def test_migration_abbruch():
    """Gälte nach dem Umbau für ein Produkt eine andere Version, bricht der Schritt ab – die Datenbank bleibt auf 37."""
    with tempfile.TemporaryDirectory() as tmp:
        pfad, ids = altbestand_37(tmp)
        from app.material import models
        conn = sqlite3.connect(pfad)
        vorher = [tuple(r) for r in conn.execute("SELECT * FROM mat_form ORDER BY id")]
        echt = models.geltend_je_produkt
        models.geltend_je_produkt = lambda c: {p: (None, None, None) for p, in c.execute("SELECT id FROM mat_product")}
        try:
            models.migrieren(conn)
            raise AssertionError("kein Abbruch")
        except sqlite3.IntegrityError as exc:
            assert "anderes Prüfformular" in str(exc), exc
        finally:
            models.geltend_je_produkt = echt
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "37"
        assert [tuple(r) for r in conn.execute("SELECT * FROM mat_form ORDER BY id")] == vorher
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_formular'").fetchone()
        assert models.migrieren(conn) == models.SCHEMA_VERSION                         # danach regulär
        conn.close()
    print("Abbruch der Migration bestanden.")


def test_migration_frisch():
    """Frisch: Tabellen, Trigger, kein formular_von, Zähler katalog_stand; kein Startprotokoll ohne Formulare."""
    with tempfile.TemporaryDirectory() as tmp:
        with startprotokoll() as log:
            make_app(tmp)
        assert not any("Schritt 38" in z for z in log), log
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        from app.material import models
        namen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert {"mat_formular", "mat_formular_zuweisung", "ux_mat_form_aktiv", "ux_mat_zuweisung_produkt",
                "ux_mat_zuweisung_kategorie", "trg_mat_formular_uid"} <= namen
        assert {models._trigger_name(x) for x in models.TRIGGER_38 + models.STAND_TRIGGER_38} <= namen
        assert not set(models.TRIGGER_WEG_38) & namen
        assert "formular_von" not in [r[1] for r in conn.execute("PRAGMA table_info(mat_product)")]
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'katalog_stand'").fetchone()
        conn.close()
    print("Migration frisch bestanden.")


def test_oberflaeche_statisch():
    """Übernehmen und „Generisches Formular“ sind aus material.js weg; Knopfsprache der neuen Stellen; der Dialog
    „Zuweisen“ füllt am Telefon die Fläche und endet über der Leiste der Übung (Browser: probe in planung/formular-pool)."""
    with open(os.path.join(WURZEL, "app", "material", "static", "material.js"), encoding="utf-8") as fh:
        js = fh.read()
    with open(os.path.join(WURZEL, "app", "material", "static", "material.css"), encoding="utf-8") as fh:
        css = fh.read()
    for weg in ("formular-von", "formularquellen", "kat-formular", "formular-uebernehmen", "formularNutzerHinweis",
                "formular_genutzt_von", "aktives_formular"):
        assert weg not in js, weg
    # Anlegen-Knopf nach dem Muster, Zuweisen als Abschnittsaktion grau, die eine Hauptaktion im Dialog rot.
    assert ('<button class="btn secondary" type="button" data-act="anlegen"><span class="k-text"><span class="k-plus" '
            'aria-hidden="true">+ </span>Prüfformular<span class="k-anlegen"> anlegen</span></span></button>') in js
    assert '<button class="btn secondary small" type="button" data-act="zuweisen">Zuweisen</button>' in js
    assert '<button class="btn" id="zw-ok" type="button"${knopfAus("zw-grund", true)}>Zuweisung speichern</button>' in js
    # 44 px nur am Finger.
    finger = css[css.index("@media (pointer: coarse) {\n  .mat-zw-zeile"):]
    assert ".mat-zw-zeile { min-height: 44px;" in finger[:finger.index("\n}")]
    assert css.count(".mat-zw-zeile { min-height: 44px;") == 1
    assert ("html.fuehrung-leiste dialog.mat-zuweisen[open] .dlg-body { height: calc(100dvh - 6px - var(--fuehrung-hoehe, 0px));"
            in css)
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_aufloesung_und_zuweisen()
    test_titel_kopie_und_vorlage()
    test_verschieben_loeschen_trigger()
    test_pruefung_und_protokoll()
    test_rechte_und_routen()
    test_katalog_stand()
    test_migration_37_38()
    test_migration_abbruch()
    test_migration_frisch()
    test_oberflaeche_statisch()
    print(json.dumps({"ok": True}))
