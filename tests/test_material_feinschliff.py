"""Feinschliff aus den Fragen des Wiki-Artikels (26.10.2026):  python tests/test_material_feinschliff.py  oder
pytest tests/test_material_feinschliff.py

Bauentwurf entwurf_feinschliff_wiki_fragen.md mit den Entscheidungen E1 A (E-Mail im Feld „Anmeldung“ bleibt, Texte
ehrlich), E2 B („Deine PSA“ läuft auch in Ordnern mit „Erinnerungsmails aus“), E3 A (Verlauf des Kontos für die
Leitstelle), E6 C („Qualifikation 1012“ entfällt). Geprüft: E2 B im Plan und im Tageslauf, E3 A je Rolle und Inhalt,
neue Protokolle mit „Artikel online“, die Texte von K9, K19, K21 und T statisch. Alle Namen, Seiten und Prüfpunkte sind
Platzhalter."""
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _flach, festschreiben, gliederung, katalog_grund, neuer_artikel, neues_konto,  # noqa: E402
                           pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung, unterschrift_daten)
from test_material_erinnerung import (T0, an, artikel, aufbau, lauf, planen, post, psa_log, psa_mail,  # noqa: E402
                                      psa_person, sql, uhr, um, versand, zuordnen_sql)

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def test_e2_psa_trotz_ordner_aus():
    """E2 B: In einem Ordner mit „Erinnerungsmails aus“ bekommen die Verwalter keine Sammelmail, die zugeordnete Person
    aber „Deine PSA“ – auch wenn sie den Ordner selbst verwaltet; abbestellt (Profil) bekommt sie nichts. Der Ordner zählt
    weiter als ausgelassen; ein nicht zugeordneter Artikel dort bleibt ganz still."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        with uhr(um(T0)):
            _, pid = psa_person(app, k["adm"])
            a = artikel(app, k["wart"], ids["hms"], lager, "AUS-1", faellig=T0 + timedelta(days=10))
            b = artikel(app, k["wart"], ids["hms"], lager, "AUS-2", faellig=T0 + timedelta(days=10))
            c = artikel(app, k["wart"], ids["hms"], lager, "AUS-3", faellig=T0 + timedelta(days=10))
            zuordnen_sql(app, a["id"], pid)
            zuordnen_sql(app, b["id"], k["wart_id"])                 # der Materialwart trägt selbst ein Teil
            assert k["wart"].put(f"/api/material/ordner/{lager}", json={"reminders_off": True}).status_code == 200
            p = planen(app)
            person = psa_mail(p)
            assert person and [(e.kennung, e.psa) for e in person.eintraege] == [(a["id"], True)], person
            assert "DEINE PSA" in person.text and "AUS-1" in person.text
            wart = psa_mail(p, "wart@example.org")
            assert wart and [(e.kennung, e.psa) for e in wart.eintraege] == [(b["id"], True)], wart
            assert "\nARTIKEL\n" not in wart.text and "AUS-2" in wart.text and "AUS-3" not in wart.text
            assert all("AUS-3" not in m.text for m in p.mails)
            assert all(e.kennung != c["id"] for e in p.ohne_empfaenger)
            assert [(o["id"], o["artikel"]) for o in p.ausgelassen["ordner_aus"]] == [(lager, 3)], p.ausgelassen
            # Der Tageslauf verschickt und vermerkt sie wie jede „Deine PSA“ – einmal je Stufe.
            with versand(app), post() as liste:
                lauf(app)
            assert len(an(liste, "person@example.org")) == 1 and psa_log(app, pid) == [(a["id"], "30_tage")]
            assert len(an(liste, "wart@example.org")) == 1 and "\nARTIKEL\n" not in an(liste, "wart@example.org")[0][2]
            with versand(app), post() as liste:
                lauf(app)
            assert an(liste, "person@example.org") == []
            # Abbestellt: nichts, auch nicht als Verwalter (der Ordner ist ja aus).
            sql(app, "UPDATE users SET mat_psa_mails = 0 WHERE id = ?", (k["wart_id"],))
            sql(app, "DELETE FROM mat_reminder_log")
            p = planen(app)
            assert psa_mail(p, "wart@example.org") is None and psa_mail(p) is not None
            # Schalter wieder an: wie vorher – Verwalter unter ARTIKEL, Person unter „Deine PSA“.
            assert k["wart"].put(f"/api/material/ordner/{lager}", json={"reminders_off": False}).status_code == 200
            p = planen(app)
            assert "AUS-3" in psa_mail(p, "wart@example.org").text and psa_mail(p).eintraege[0].psa
            assert p.ausgelassen["ordner_aus"] == []
    print("E2 B bestanden.")


def test_e3_verlauf_des_kontos():
    """E3 A: GET /api/admin/users/<id>/journal – nur die Plattform-Verwaltung; die letzten 50 Einträge am Konto, mit
    Namen statt E-Mail, die Unterschrift nur als „hinterlegt“; Einträge eines gelöschten Vorgängers mit derselben
    Kennung bleiben draußen."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        uid = k["pruefer_id"]
        url = f"/api/admin/users/{uid}/journal"
        assert app.test_client().get(url).status_code == 401
        for wer in ("wart", "katalog", "pruefer", "nutzer"):              # Mitglied, Material-Verwaltung, ohne Stufe
            assert k[wer].get(url).status_code == 403, wer
        assert k["adm"].get("/api/admin/users/999999/journal").status_code == 404
        # Urkundennummer ändern (Verwaltung), Unterschrift neu (Profil) – beides steht im Journal am Konto.
        assert k["adm"].put(f"/api/admin/users/{uid}", json={"urkundennummer": "Platzhalter-2"}).status_code == 200
        assert k["pruefer"].put("/api/material/unterschrift", json={"bild": unterschrift_daten("U")}).status_code == 200
        r = k["adm"].get(url)
        assert r.status_code == 200, r.get_json()
        d = r.json
        assert d["max"] == 50
        aktionen = [z["aktion"] for z in d["eintraege"]]
        assert aktionen[0] == "Unterschrift geändert" and "Rollen" in aktionen, aktionen
        unterschrift = d["eintraege"][0]["felder"]
        assert unterschrift == [{"feld": "Unterschrift", "vorher": "hinterlegt", "nachher": "hinterlegt",
                                 "nur_nachher": False}], unterschrift
        text = r.get_data(as_text=True)
        assert "data:image" not in text and "pruefer@example.org" not in text and "admin@example.org" not in text
        assert "Platzhalter-2" in text and all(z["von"] and "@" not in z["von"] for z in d["eintraege"]), d
        # Höchstens 50, neueste zuerst.
        with app.app_context():
            from app import db
            with db.transaction():
                for i in range(60):
                    db.execute("INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, "
                               "after_json, created_at) VALUES ('user', ?, NULL, 'System', 'urkundennummer', ?, ?, ?)",
                               (uid, '{"urkundennummer": ""}', f'{{"urkundennummer": "P-{i}"}}', db.now()))
        d = k["adm"].get(url).json
        assert len(d["eintraege"]) == 50 and "P-59" in str(d["eintraege"][0]), d["eintraege"][0]
        # Ein Eintrag eines Vorgängers mit derselben Kennung (vor der Anlage des Kontos) – gehört nicht dazu.
        _, nid = neues_konto(app, "nachfolger@example.org", name="Nachfolger Platzhalter")
        with app.app_context():
            from app import db
            with db.transaction():
                db.execute("INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, "
                           "after_json, created_at) VALUES ('user', ?, NULL, 'System', 'urkundennummer', NULL, ?, ?)",
                           (nid, '{"urkundennummer": "VORGAENGER"}', "2000-01-01T00:00:00+00:00"))
        d = k["adm"].get(f"/api/admin/users/{nid}/journal").json
        assert "VORGAENGER" not in str(d), d
        # Dieselbe Kennung in derselben Sekunde (Sicherheitsprüfung, Befund 1): Löschen setzt einen Grenzstein
        # „geloescht“ am Konto, der Nachfolger sieht nichts davor – unabhängig von der Uhr. Ebenso eine abgelehnte Anfrage.
        from app.material.services import journal as mat_journal
        for weg in ("loeschen", "ablehnen"):
            adm = k["adm"]
            if weg == "loeschen":
                r = adm.post("/api/admin/users", json={"email": f"vorg-{weg}@example.org", "password": "passwort1",
                                                       "name": "Vorgänger Platzhalter", "mat_pruefer": True,
                                                       "urkundennummer": "VORG-1"})
                alt_id = r.json["user"]["id"]
                assert adm.delete(f"/api/admin/users/{alt_id}", headers=H).status_code == 200
            else:
                c = app.test_client()
                c.post("/api/auth/register", json={"email": f"vorg-{weg}@example.org", "password": "passwort1",
                                                   "name": "Anfrage Platzhalter", "gliederung": "OG Platzhalter"})
                alt_id = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == f"vorg-{weg}@example.org"][0]["id"]
                assert adm.put(f"/api/admin/users/{alt_id}", json={"mat_pruefer": True, "urkundennummer": "VORG-2"}).status_code == 200
                assert adm.post(f"/api/admin/users/{alt_id}/reject", json={}).status_code == 200
            r = adm.post("/api/admin/users", json={"email": f"nach-{weg}@example.org", "password": "passwort1",
                                                   "name": "Nachfolger Platzhalter"})
            neu_id = r.json["user"]["id"]
            assert neu_id == alt_id, (neu_id, alt_id)                    # dieselbe Kennung wird neu vergeben
            with app.app_context():
                from app import db
                # Der Schnitt hängt an der Journalkennung, nicht an der Uhr: journal.lesen allein lässt den Vorgänger weg.
                assert "VORG" not in str(mat_journal.lesen([("user", neu_id)]))
                # Anlage des Nachfolgers „vor“ allen Einträgen – so ließe der Zeitvergleich allein den Vorgänger durch.
                with db.transaction():
                    db.execute("UPDATE users SET created_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (neu_id,))
            d = adm.get(f"/api/admin/users/{neu_id}/journal").json
            assert "VORG" not in str(d) and d["eintraege"], (weg, d)
    # Oberfläche: eingeklappt im Dialog „Bearbeiten“, geladen erst beim Aufklappen.
    js = lesen("app/static/js/admin.js")
    assert '<details class="accordion" id="u-verlauf"><summary>Verlauf (Materialablage)</summary>' in js
    assert "verlaufAnbinden(body.querySelector(\"#u-verlauf\"), u);" in js and "/journal`" in js
    print("E3 A bestanden.")


def test_protokoll_artikel_online():
    """T12: Der QR-Code neuer Prüfprotokolle heißt „Artikel online“ (er führt zur Artikelseite bzw. „Meine PSA“)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["wart"])
        a = neuer_artikel(k["wart"], ids["hms"], gid)
        pid = starten(k["pruefer"], a["id"]).json["pruefung"]["id"]
        assert festschreiben(k["pruefer"], pid, ergebnis="einsatzbereit").status_code == 200
        zeile = protokoll_zeile(app, pid)
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"]))))
        assert "Artikel online" in text and "Lebenslauf online" not in text, text[:600]
        # Für veraPDF (Browserprobe/Abschluss): eine Kopie, wenn ST_PDF_KOPIE gesetzt ist.
        ziel = os.environ.get("ST_PDF_KOPIE")
        if ziel:
            with open(os.path.join(tmp, zeile["pdf_path"]), "rb") as q, open(ziel, "wb") as z:
                z.write(q.read())
    print("Protokoll „Artikel online“ bestanden.")


def test_texte_statisch():
    """Alte Wortlaute fehlen, neue stehen da (K9, K19, K21, T12, T20, T24, E1 A, E2 B, E6 C)."""
    mjs, fjs, ajs = lesen("app/material/static/material.js"), lesen("app/material/static/freigaben.js"), \
        lesen("app/static/js/admin.js")
    profil, basis, bericht = lesen("app/templates/profil.html"), lesen("app/material/templates/material/pdf/basis.html"), \
        lesen("app/material/templates/material/pdf/bericht.html")
    weg = {
        "freigaben.js": (fjs, ["Offene Prüfungen freigeben"]),
        "admin.js": (ajs, ["Offene Prüfungen freigeben", "Qualifikation 1012"]),
        "material.js": (mjs, ["ausgesonderte bei ihrer Gliederung", "Sperren und Freigaben im Jahr",
                              "Das geht nur, solange er leer ist.", "ohne Unterordner, Artikel und Prüfdurchgänge;"]),
        "basis.html": (basis, ["Lebenslauf online"]),
        "bericht.html": (bericht, ["Sperren und Freigaben im Jahr"]),
        "profil.html": (profil, ["Qualifikation 1012"]),
    }
    for name, (text, alt) in weg.items():
        for w in alt:
            assert w not in text, (name, w)
    da = {
        "freigaben.js": (fjs, ["→ „Offene Prüfungen“ mit „Reservierung aufheben“."]),
        "admin.js": (ajs, ["→ „Offene Prüfungen“ mit „Reservierung aufheben“.", "> Prüfer (Sachkundiger)</label>"]),
        "material.js": (mjs, [
            "auch die von hier gesperrten und ausgesonderten, mit Status, Fälligkeiten und Stammdaten – für Excel.",
            "Sperren und Freiprüfungen im Jahr",
            "ohne Unterordner und Artikel, ohne Prüfdurchgänge und Set-Protokolle, ohne offene Nacharbeit eines "
            "Bestandsimports und ohne gesperrte Artikel, die hierher zurückkehren; vorher wird nachgefragt.",
            "endgültig löschen? Danach ist er weg. Das geht nur bei einem leeren Ordner – ohne Unterordner und Artikel, "
            "ohne Prüfdurchgänge und Set-Protokolle,",
            "„Deine PSA“ an die Personen, denen hier etwas zugeordnet ist",
            # K9: geerbtes generisches Formular in der Angabenzeile der Kategorie.
            "pfad.slice(0, -1).reverse().find((x) => x.aktives_formular)", "generisches Prüfformular von ${DARF.katalog",
            'data-act="kategorie" data-id="${geerbt.id}">„${esc(geerbt.name)}“</a>',
            '<a href="/materialablage/katalog/formular/${geerbt.aktives_formular}">„${esc(geerbt.name)}“</a>']),
        "basis.html": (basis, ['<div class="qr-titel">Artikel online</div>']),
        "bericht.html": (bericht, ["Sperren und Freiprüfungen im Jahr"]),
        "profil.html": (profil, ["Urkundennummer (Prüfernummer)</label>", "zusammen mit deiner Anmeldung (E-Mail-Adresse)",
                                 "auch wenn der Materialwart für den Ordner die Erinnerungsmails abgeschaltet hat"]),
    }
    for name, (text, neu) in da.items():
        for w in neu:
            assert w in text, (name, w)
    print("Texte bestanden.")


if __name__ == "__main__":
    test_e2_psa_trotz_ordner_aus()
    test_e3_verlauf_des_kontos()
    test_protokoll_artikel_online()
    test_texte_statisch()
