"""Meine PSA (Phase 3 · Lieferung 1, Bauentwurf 2 und 7.1):  python tests/test_material_meine_psa.py  oder  pytest

Jedes aktive Konto mit Namen sieht unter „Meine PSA“ die Artikel, die ihm zugeordnet sind – auch ohne Stufe im Modul
Material, nur die eigenen, nicht ausgesonderten und von ihnen nur die Karte (feste Liste von Schlüsseln). Der QR-Link
der eigenen PSA landet dort; Medien nur, was die Karte zeigt (Produktbild nur Web- und Vorschaufassung, Dokumente nur
Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung, Datenblatt). Kopfleiste nur für Konten, die nirgends im
Bestand lesen dürfen; sonst ein Kasten auf der Übersicht. Die Zuordnung öffnet keinen anderen Weg ins Modul.

Die Helfer aufbau, post_mangel und melden nutzt auch tests/test_material_mangel.py. Alle Namen, Hersteller, Nummern
und Texte hier sind Platzhalter und nur für den Test da."""
import io
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, freigeben, gliederung, jpeg, katalog_grund, neuer_artikel,  # noqa: E402
                           neues_konto, pruef_formulare, starten, umgebung, mails_abfangen, mails_zurueck)
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post, ordner_neu, sperren, zustand  # noqa: E402

# Mangel-Mails rechnen ohne Umgebungssperre (test_material_mangel setzt sie gezielt).
for _name in ("MATERIAL_ERINNERUNGEN_SPERRE", "STROEMIS_NAME"):
    os.environ.pop(_name, None)

ZU = "/api/material/artikel/{}/zuordnung"
LISTE = "/api/material/meine-psa"
KARTE = {"id", "inventory_no", "serial_no", "serial_generated", "produkt", "status", "status_text", "next_due_on",
         "retire_by", "last_inspected_on", "gesperrt", "verloren", "lock_reason", "notes", "gliederung", "demo", "mangel",
         "eigene_maengel", "artikel_link", "dokumente", "rueckruf", "length_m", "laenge_text",   # Länge: Schritt 20
         "bestandteile"}                                                # Bestandteil-Liste mit Seriennummern: Schritt 25
PRODUKT = {"manufacturer", "model", "description", "article_no", "material_kind", "bild", "vorschau"}


# --- Helfer (auch für test_material_mangel) ------------------------------------------------------------------------

def aufbau(tmp):
    """Umgebung mit Katalog, Formularen und der Gliederung „OG Musterstadt“ (Standardfreigaben: wart verwaltet,
    fuehrung und katalog lesen, pruefer liest und prüft) samt Lager mit drei Karabinern. Dazu person (aktiv, mit Namen,
    ohne Modulstufe), person2 (ebenso) und mitglied (Stufe Mitglied, keine Freigabe). Liefert ein SimpleNamespace."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    gid, system = gliederung(k["adm"])
    lager = ordner_neu(k["wart"], gid, "Lager Platzhalter")
    art = [neuer_artikel(k["wart"], ids["hms"], lager, serial_no=f"PSA-{n}")["id"] for n in (1, 2, 3)]
    person, person_id = neues_konto(app, "person@example.org", name="Person Platzhalter", stufe=0)
    person2, person2_id = neues_konto(app, "person2@example.org", name="Person Zwei", stufe=0)
    mitglied, mitglied_id = neues_konto(app, "mitglied@example.org", name="Mitglied Platzhalter", stufe=1)
    return SimpleNamespace(app=app, k=k, adm=k["adm"], ids=ids, gid=gid, system=system, lager=lager, art=art,
                           w=k["wart"], person=person, person_id=person_id, person2=person2, person2_id=person2_id,
                           mitglied=mitglied, mitglied_id=mitglied_id)


def zuordnen(t, iid, uid):
    r = t.w.put(ZU.format(iid), json={"user_id": uid})
    assert r.status_code == 200, r.get_json()


@contextmanager
def post_mangel():
    """Mangel-Mails direkt statt im Hintergrund und nur in eine Liste – nie hinaus. Die Liste spielt den Mailserver
    (ohne ihn gingen die Mails nur ins Log, mailprotokoll.MAILSERVER)."""
    from app.material.services import mangel
    liste = []
    alt = mails_abfangen(mangel, lambda an, betreff, inhalt: liste.append((an, betreff, inhalt)) or True)
    try:
        yield liste
    finally:
        mails_zurueck(alt)


def melden(c, iid, text="Platzhalter: Mangel am Testartikel", fotos=0, namen=None):
    """POST …/mangel – mit Fotos als Formular (jpeg), sonst als JSON."""
    url = f"/api/material/artikel/{iid}/mangel"
    if fotos or namen:
        dateien = [(jpeg(), n) for n in (namen or [f"foto{i}.jpg" for i in range(fotos)])]
        return c.post(url, headers=H, content_type="multipart/form-data", data={"beschreibung": text, "fotos": dateien})
    return c.post(url, headers=H, json={"beschreibung": text})


def seite(r):
    """Der Inhalt einer Antwort ohne die Nonce der CSP (sie wechselt je Anfrage)."""
    return re.sub(rb'nonce="[^"]*"', b"", r.get_data())


def token_von(app, iid):
    return zeilen(app, "SELECT qr_token FROM mat_item WHERE id = ?", (iid,))[0]["qr_token"]


def _dokument(kp, pid, kind, name, kategorie=False, inhalt=None):
    """Ein Dokument mit eigenem Inhalt je Art und Name: Seit Schritt 18 liegt gleicher Inhalt nur einmal und gehört allen
    Dokumenten, die ihn nennen – mit demselben PDF überall ließe sich die Art nicht mehr prüfen."""
    url = f"/api/material/{'kategorien' if kategorie else 'produkte'}/{pid}/dokumente"
    r = kp.post(url, headers=H, content_type="multipart/form-data",
                data={"kind": kind, "title": f"Platzhalter {kind}",
                      "file": (io.BytesIO(inhalt or PDF + f"%{kind}-{name}".encode()), name)})
    assert r.status_code == 201, r.get_json()
    return next(d["datei"] for d in r.json["dokumente"] if d["id"] == r.json["dokument_id"])


# --- 7.1 ------------------------------------------------------------------------------------------------------------

def test_zugang():
    """Person ohne Stufe mit zwei Zuordnungen: Seite ohne Modulnavigation und Ordnerleiste, API mit genau den zwei,
    dringende zuerst; ohne Zuordnung leere Liste; ohne Namen 403; deaktiviert Anmeldung bzw. 401; ausgesondert fehlt."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        zuordnen(t, a1, t.person_id)
        zuordnen(t, a2, t.person_id)
        zustand(t.app, a1, last_inspected_on="2025-01-15", next_due_on="2099-01-01")        # einsatzbereit
        sperren(t.k["pruefer"], a2)                                                            # gesperrt: zuerst
        r = t.person.get("/materialablage/meine-psa")
        html = r.get_data(as_text=True)
        assert r.status_code == 200 and 'data-ansicht="meine_psa"' in html, r.status_code
        assert 'class="mat-nav"' not in html and 'id="mat-side"' not in html
        assert "data-daten='{&#34;id&#34;: null}'" in html or 'data-daten="{&#34;id&#34;: null}"' in html, html[:2000]
        d = t.person.get(LISTE).json
        assert [a["id"] for a in d["artikel"]] == [a2, a1] and d["gesamt"] == 2, d
        assert d["artikel"][0]["status"] == "gesperrt" and d["artikel"][0]["gesperrt"] is True
        assert d["mails"] is True and isinstance(d["schwelle_tage"], int)
        # Ohne Zuordnung: die Seite öffnet sich, die Liste ist leer.
        assert t.person2.get("/materialablage/meine-psa").status_code == 200
        assert t.person2.get(LISTE).json["artikel"] == []
        # Ohne Namen: 403 mit Klartext (Seite und Schnittstelle).
        sql(t.app, "UPDATE users SET name = '' WHERE id = ?", (t.person2_id,))
        r = t.person2.get(LISTE)
        assert r.status_code == 403 and "Namen" in r.json["error"], r.get_json()
        r = t.person2.get("/materialablage/meine-psa")
        assert r.status_code == 403 and "Namen" in r.get_data(as_text=True)
        # Ausgesondert (Altbestand mit stehen gebliebener Zuordnung): fehlt.
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert', assigned_user_id = ? WHERE id = ?",
            (t.person_id, a3))
        assert {a["id"] for a in t.person.get(LISTE).json["artikel"]} == {a1, a2}
        assert t.person.get(LISTE).json["gesamt"] == 2
        # Deaktiviert: Anmeldung bzw. 401.
        assert t.adm.put(f"/api/admin/users/{t.person_id}", json={"active": False}).status_code == 200
        r = t.person.get("/materialablage/meine-psa")
        assert r.status_code == 302 and "/login" in r.headers["Location"], r.status_code
        assert t.person.get(LISTE).status_code == 401
    print("Zugang bestanden.")


def test_felder():
    """Die Karte hat genau die Schlüssel aus 2.3 samt Sperrgrund, Bemerkung, letzter Prüfung und Gliederung
    (Entscheidung A vom 20.10.2026); kein Ordnerpfad, kein Ordner, kein Journal, keine Prüfungen, keine Namen."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, _ = t.art
        for iid in (a1, a2):
            zuordnen(t, iid, t.person_id)
        sql(t.app, "UPDATE mat_item SET notes = 'Bemerkung-Geheimtext' WHERE id IN (?, ?)", (a1, a2))
        r = t.k["pruefer"].post(f"/api/material/artikel/{a2}/sperren", json={"grund": "beschaedigung",
                                                                             "text": "Sperrgrund-Geheimtext"})
        assert r.status_code == 200, r.get_json()
        assert melden(t.person, a1, "Eigene Platzhaltermeldung").status_code == 201
        d = t.person.get(LISTE).json
        text = json.dumps(d, ensure_ascii=False)
        for k in d["artikel"]:
            assert set(k) == KARTE, set(k) ^ KARTE
            assert set(k["produkt"]) == PRODUKT, k["produkt"]
            assert isinstance(k["dokumente"], list) and isinstance(k["rueckruf"], list)
        for merkmal in ("Lager Platzhalter", "Gesperrt", "journal", "pruefungen", "folder", "pfad", "qr",
                        "Person Platzhalter", "assigned", "manufactured", "purchased", "interval"):
            assert merkmal not in text, (merkmal, text)
        for k in d["artikel"]:
            assert k["notes"] == "Bemerkung-Geheimtext" and k["gliederung"] == "OG Musterstadt", k
            assert k["last_inspected_on"] is None
        gesperrt = next(k for k in d["artikel"] if k["id"] == a2)
        assert gesperrt["lock_reason"] == "Beschädigung: Sperrgrund-Geheimtext", gesperrt
        zustand(t.app, a2, last_inspected_on="2025-01-15")
        assert next(k for k in t.person.get(LISTE).json["artikel"] if k["id"] == a2)["last_inspected_on"] == "2025-01-15"
        karte = next(k for k in d["artikel"] if k["id"] == a1)
        assert karte["lock_reason"].startswith("Mangel gemeldet am ")
        assert karte["mangel"] and set(karte["mangel"]) == {"seit"}
        assert [set(m) for m in karte["eigene_maengel"]] == [{"id", "created_at", "description", "offen", "fotos"}]
        assert karte["eigene_maengel"][0]["description"] == "Eigene Platzhaltermeldung"
        assert karte["artikel_link"] is False and karte["status"] == "gesperrt"
    print("Felder der Karte bestanden.")


def test_qr():
    """QR-Link: ohne Stufe führt der eigene Artikel zu „Meine PSA“, fremd und unbekannt antworten gleich (403); mit
    Stufe ohne Leserecht ebenso „Meine PSA“, mit Leserecht die Artikelseite, fremd wie bisher „fremd“."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        zuordnen(t, a1, t.person_id)
        zuordnen(t, a2, t.mitglied_id)
        zuordnen(t, a3, t.k["fuehrung_id"])
        r = t.person.get(f"/m/{token_von(t.app, a1)}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/materialablage/meine-psa/{a1}"), r.headers
        fremd = t.person.get(f"/m/{token_von(t.app, a2)}")
        unbekannt = t.person.get("/m/gibtesnicht0000")
        assert fremd.status_code == unbekannt.status_code == 403
        assert seite(fremd) == seite(unbekannt)
        # Mit Stufe, ohne Leserecht: der eigene Artikel unter „Meine PSA“, ein fremder „fremd“ wie bisher.
        r = t.mitglied.get(f"/m/{token_von(t.app, a2)}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/materialablage/meine-psa/{a2}"), r.headers
        r = t.mitglied.get(f"/m/{token_von(t.app, a1)}")
        assert r.status_code == 200 and 'data-ansicht="fremd"' in r.get_data(as_text=True)
        assert t.mitglied.get("/m/gibtesnicht0000").status_code == 404
        # Mit Leserecht: die volle Artikelseite, auch für den eigenen Artikel.
        r = t.k["fuehrung"].get(f"/m/{token_von(t.app, a3)}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/materialablage/artikel/{a3}"), r.headers
        # Ausgesondert ist nicht mehr „eigen“.
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a1,))
        r = t.person.get(f"/m/{token_von(t.app, a1)}")
        assert r.status_code == 403 and seite(r) == seite(t.person.get("/m/gibtesnicht0000"))
    print("QR bestanden.")


def test_einzelseite():
    """Eigener Artikel 200; fremder, unbekannter und ausgesonderter 404 mit gleichem Text."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, _ = t.art
        zuordnen(t, a1, t.person_id)
        zuordnen(t, a2, t.person2_id)
        r = t.person.get(f"/materialablage/meine-psa/{a1}")
        assert r.status_code == 200 and f"{{&#34;id&#34;: {a1}}}" in r.get_data(as_text=True)
        fremd, unbekannt = t.person.get(f"/materialablage/meine-psa/{a2}"), t.person.get("/materialablage/meine-psa/999999")
        assert fremd.status_code == unbekannt.status_code == 404 and seite(fremd) == seite(unbekannt)
        assert "Artikel nicht gefunden." in fremd.get_data(as_text=True)
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a1,))
        r = t.person.get(f"/materialablage/meine-psa/{a1}")
        assert r.status_code == 404 and seite(r) == seite(t.person.get("/materialablage/meine-psa/999999"))
    print("Einzelseite bestanden.")


def test_medien():
    """Ohne Stufe: Produktbild der eigenen PSA nur web/thumb (orig 403), fremdes Produktbild 403; Ordnerfoto,
    Befundfoto, Anhang, Meldungsfoto 403; eigene Mangelfotos 200, die eines anderen Melders 403; Gebrauchsanleitung,
    Pflegehinweis (auch an der Kategorie), Datenblatt, Konformitätserklärung 200, Prüfanweisung und „Sonstiges“ 403,
    fremdes Dokument 403. Die Karte nennt nur die erlaubten Dokumente und die Webfassung."""
    with ohne_post(), post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        kp, ids = t.k["katalog"], t.ids
        a1, a2, _ = t.art
        zuordnen(t, a1, t.person_id)
        r = kp.post(f"/api/material/produkte/{ids['hms']}/bild", data={"file": (jpeg(), "hms.jpg")}, headers=H,
                    content_type="multipart/form-data")
        bild = r.json["produkt"]["bild"]
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H,
                    content_type="multipart/form-data")
        fremdbild = r.json["produkt"]["bild"]
        erlaubt = [_dokument(kp, ids["hms"], art, f"{art}.pdf") for art in
                   ("gebrauchsanleitung", "datenblatt", "konformitaetserklaerung")]
        erlaubt.append(_dokument(kp, ids["karabiner"], "pflegehinweis", "pflege.pdf", kategorie=True))
        verboten = [_dokument(kp, ids["hms"], art, f"{art}.pdf") for art in ("pruefanweisung", "sonstiges")]
        verboten.append(_dokument(kp, ids["gurt"], "gebrauchsanleitung", "fremd.pdf"))
        # Ordnerfoto, Befundfoto und Anhang einer Prüfung des eigenen Artikels, Meldungsfoto.
        r = t.w.post(f"/api/material/ordner/{t.lager}/foto", data={"file": (jpeg(), "lager.jpg")}, headers=H,
                     content_type="multipart/form-data")
        ordnerfoto = r.json["ordner"]["foto"]
        pr = starten(t.k["pruefer"], a1).json["pruefung"]
        r = t.k["pruefer"].post(f"/api/material/pruefungen/{pr['id']}/punkte/{pr['punkte'][0]['id']}/foto", headers=H,
                                content_type="multipart/form-data", data={"file": (jpeg(), "befund.jpg")})
        befundfoto = r.json["punkt"]["foto"]["web"]
        r = t.k["pruefer"].post(f"/api/material/pruefungen/{pr['id']}/anhaenge", headers=H,
                                content_type="multipart/form-data",
                                data={"file": [(jpeg(), "scan.jpg")], "art": "foto", "titel": "Testscan"})
        anhang = r.json["anhang"]["datei"]
        r = t.w.post("/api/material/meldungen", headers=H, content_type="multipart/form-data",
                     data={"manufacturer": "Meldewerk", "model": "Platzhalter", "folder_id": str(t.lager),
                           "fotos": (jpeg(), "etikett.jpg")})
        meldungsfoto = r.json["meldung"]["fotos"][0]["web"]
        # Mangelfotos: eigene und die eines anderen Melders am selben Artikel.
        r = melden(t.person, a1, fotos=2)
        assert r.status_code == 201, r.get_json()
        eigene = [u for f in r.json["mangel"]["fotos"] for u in (f["web"], f["vorschau"])]
        r = melden(t.k["fuehrung"], a1, fotos=1)
        assert r.status_code == 201, r.get_json()
        fremde = [r.json["mangel"]["fotos"][0]["web"], r.json["mangel"]["fotos"][0]["vorschau"]]
        p = t.person
        assert p.get(bild).status_code == 200 and p.get(bild.replace("/web/", "/thumb/")).status_code == 200
        orig = zeilen(t.app, "SELECT image FROM mat_product WHERE id = ?", (ids["hms"],))[0]["image"]
        assert p.get(f"/media/material/orig/{orig}").status_code == 403
        assert t.k["fuehrung"].get(f"/media/material/orig/{orig}").status_code == 200
        for url in [fremdbild, ordnerfoto, befundfoto, anhang, meldungsfoto] + fremde + verboten:
            assert p.get(url).status_code == 403, url
        for url in eigene + erlaubt:
            assert p.get(url).status_code == 200, url
        # Eine Datei je Inhalt (Schritt 18): Trägt ein „Sonstiges“ am eigenen Produkt denselben Inhalt wie eine fremde
        # Gebrauchsanleitung, ist es dieselbe Datei – und die ist über die eigene Gebrauchsanleitung erlaubt.
        gemeinsam = _dokument(kp, ids["hms"], "gebrauchsanleitung", "g2.pdf", inhalt=PDF + b"%gemeinsam")
        assert _dokument(kp, ids["gurt"], "sonstiges", "s2.pdf", inhalt=PDF + b"%gemeinsam") == gemeinsam
        assert p.get(gemeinsam).status_code == 200, gemeinsam
        erlaubt.append(gemeinsam)                       # auf der Karte wie jede eigene Gebrauchsanleitung
        # Ein Original eines Mangelfotos gibt es nicht.
        name = os.path.basename(eigene[0])
        assert not os.listdir(os.path.join(tmp, "media", "material", "orig")) or not any(
            f.startswith(os.path.splitext(name)[0]) for f in os.listdir(os.path.join(tmp, "media", "material", "orig")))
        assert t.k["fuehrung"].get(f"/media/material/orig/{name}").status_code == 404
        # Mit Zugang: der Melder, Prüfer und Materialwart – nicht, wer den Artikel nur liest (404 wie Unbekanntes,
        # Entscheidung vom 21.10.2026).
        assert t.k["fuehrung"].get(eigene[0]).status_code == 404 and t.k["fuehrung"].get(fremde[0]).status_code == 200
        assert t.w.get(fremde[0]).status_code == 200 and t.k["pruefer"].get(eigene[0]).status_code == 200
        karte = p.get(LISTE).json["artikel"][0]
        assert karte["produkt"]["bild"] == bild and karte["produkt"]["vorschau"] == bild.replace("/web/", "/thumb/")
        assert sorted(d["datei"] for d in karte["dokumente"]) == sorted(erlaubt), karte["dokumente"]
        assert {d["kind"] for d in karte["dokumente"]} == {"gebrauchsanleitung", "datenblatt", "konformitaetserklaerung",
                                                           "pflegehinweis"}
        assert all(set(d) == {"title", "kind", "datei", "url"} for d in karte["dokumente"])
        # Ein anderes Konto ohne Stufe und ohne Zuordnung bekommt nichts.
        for url in [bild] + erlaubt:
            assert t.person2.get(url).status_code == 403, url
    print("Medien bestanden.")


def test_kopfleiste():
    """„Meine PSA“ in der Kopfleiste für: ohne Stufe mit Zuordnung, Mitglied ohne Freigabe, Mitglied mit nur einer
    dauerhaften Prüffreigabe ohne Grundrecht. Nicht für: ohne Zuordnung; Leser, Materialwart, Prüfer, MV – je mit
    Zuordnung. active auf der Seite; eine Wiki-Seite kostet ohne Zuordnung genau eine Abfrage mehr."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k = t.k
        nur_pruef, nur_pruef_id = neues_konto(t.app, "nurpruef@example.org", name="Nur Prüffreigabe", stufe=1,
                                              mat_pruefer=True, urkundennummer="1012-0002")
        fid = freigeben(t.adm, t.gid, nur_pruef_id, "pruefen")
        sql(t.app, "UPDATE mat_folder_grant SET valid_until = NULL WHERE id = ?", (fid,))
        mehr = [neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no=f"KOPF-{n}")["id"] for n in range(5)]
        ja = [(t.person, t.person_id), (t.mitglied, t.mitglied_id), (nur_pruef, nur_pruef_id)]
        nein = [(k["fuehrung"], k["fuehrung_id"]), (k["wart"], k["wart_id"]), (k["pruefer"], k["pruefer_id"]),
                (k["katalog"], k["katalog_id"])]
        link = re.compile(r'href="/materialablage/meine-psa" class="[^"]*">Meine PSA</a>')       # der Eintrag der Kopfleiste
        for c, _ in ja + nein:
            assert not link.search(c.get("/profil").get_data(as_text=True))     # ohne Zuordnung nie
        for (_c, uid), iid in zip(ja + nein, t.art + mehr):
            zuordnen(t, iid, uid)
        for c, _ in ja:
            assert link.search(c.get("/profil").get_data(as_text=True))
            html = c.get("/materialablage/meine-psa").get_data(as_text=True)
            assert re.search(r'href="/materialablage/meine-psa" class="active"', html), html[:1500]
        for c, _ in nein:
            assert not link.search(c.get("/profil").get_data(as_text=True))
            html = c.get("/materialablage/meine-psa").get_data(as_text=True)
            assert re.search(r'href="/materialablage" class="active"', html) and not link.search(html)
        # Abfragen einer Wiki-Seite ohne Zuordnung: genau eine zur Zuordnung, keine Freigaben, kein Ordnerbaum.
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn
        db_mod.get_db = mit_zaehler
        try:
            assert t.person2.get("/stroemipedia").status_code == 200
        finally:
            db_mod.get_db = alt
        assert len([q for q in abfragen if "assigned_user_id" in q]) == 1, abfragen
        assert not [q for q in abfragen if "mat_folder_grant" in q or re.search(r"FROM mat_folder\b(?!_)", q)]
    print("Kopfleiste bestanden.")


def test_uebersicht():
    """/materialablage ohne Stufe: mit Zuordnung 302 auf „Meine PSA“, sonst 403. Mitglied ohne Freigabe mit Zuordnung: die
    Übersicht und start.meine_psa; ohne Zuordnung null."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, _ = t.art
        zuordnen(t, a1, t.person_id)
        zuordnen(t, a2, t.mitglied_id)
        r = t.person.get("/materialablage")
        assert r.status_code == 302 and r.headers["Location"].endswith("/materialablage/meine-psa"), r.status_code
        assert t.person2.get("/materialablage").status_code == 403
        assert t.person.get("/materialablage/bestand").status_code == 403
        assert t.mitglied.get("/materialablage").status_code == 200
        assert t.mitglied.get("/api/material/start").json["meine_psa"] == {"anzahl": 1, "dringend": 1}  # neu
        zustand(t.app, a2, last_inspected_on="2025-01-15", next_due_on="2099-01-01")
        assert t.mitglied.get("/api/material/start").json["meine_psa"] == {"anzahl": 1, "dringend": 0}
        assert t.k["fuehrung"].get("/api/material/start").json["meine_psa"] is None
    print("Übersicht bestanden.")


def test_profil():
    """Abschnitt „Meine PSA“ im Profil nur mit Zuordnung oder abbestellten Erinnerungen; PUT …/mails wirkt nur am
    eigenen Konto; Unbrauchbares 400."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        assert 'id="psa"' not in t.person.get("/profil").get_data(as_text=True)
        zuordnen(t, a1, t.person_id)
        html = t.person.get("/profil").get_data(as_text=True)
        assert 'id="psa"' in html and 'id="psa-mails" checked' in html and "profil_psa.js" in html
        assert "(1 Artikel)" in html
        url = "/api/material/meine-psa/mails"
        for daten in ({}, {"an": "x"}, {"an": None}, {"an": ""}, {"an": [1]}):
            r = t.person.put(url, json=daten)
            assert r.status_code == 400, (daten, r.get_json())
        r = t.person.put(url, json={"an": False, "user_id": t.person2_id})
        assert r.status_code == 200 and r.json == {"an": False}, r.get_json()
        werte = {z["id"]: z["mat_psa_mails"] for z in zeilen(t.app, "SELECT id, mat_psa_mails FROM users")}
        assert werte[t.person_id] == 0 and werte[t.person2_id] == 1
        assert t.person.get(LISTE).json["mails"] is False
        # Ohne Zuordnung, aber abbestellt: der Abschnitt bleibt (zum Zurücknehmen).
        assert t.w.put(ZU.format(a1), json={"user_id": None}).status_code == 200
        html = t.person.get("/profil").get_data(as_text=True)
        assert 'id="psa"' in html and 'id="psa-mails" checked' not in html and "keine Ausrüstung" in html
        assert t.person.put(url, json={"an": True}).json == {"an": True}
        assert 'id="psa"' not in t.person.get("/profil").get_data(as_text=True)
        assert t.app.test_client().put(url, json={"an": True}).status_code == 401
    print("Profil bestanden.")


_PLATZ = re.compile(r"<(?:[^<>:]+:)?(\w+)>")


def _url(regel, iid, token):
    def ersetzen(m):
        name = m.group(1)
        return {"iid": str(iid), "token": token, "art": "web", "dateiname": "x.jpg", "filename": "material.js"}.get(
            name, "1")
    return _PLATZ.sub(ersetzen, regel.rule)


def test_keine_tuer():
    """Person ohne Stufe: Jede GET-Route der Material-Blueprints außer „Meine PSA“, QR, Medien und der Übersicht
    antwortet mit Zuordnung genau wie ohne; GET /api/material/artikel/<eigener> bleibt 403."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        token = token_von(t.app, a1)
        regeln = [r for r in t.app.url_map.iter_rules() if r.endpoint.split(".")[0] in ("material", "material_api")
                  and "GET" in r.methods and r.endpoint not in ("material.static", "material.medien", "material.qr_ziel",
                                                                 "material.dashboard", "material.meine_psa",
                                                                 "material.meine_psa_artikel", "material_api.psa_liste")]

        def antworten():
            # Einziger Unterschied auf Seiten: der Eintrag „Meine PSA“ in der Kopfleiste (test_kopfleiste).
            return {r.rule: (x.status_code, re.sub(rb"\s+", b" ", re.sub(
                rb'<a href="/materialablage/meine-psa" class="[^"]*">Meine PSA</a>', b"", seite(x)))) for r in regeln
                    for x in [t.person.get(_url(r, a1, token))]}
        vorher = antworten()
        zuordnen(t, a1, t.person_id)
        nachher = antworten()
        assert vorher == nachher, {k: (vorher[k][0], nachher[k][0]) for k in vorher if vorher[k] != nachher[k]}
        assert len(regeln) >= 50, len(regeln)                  # Stand P3-L1: 56
        assert all(v[0] in (200, 302, 401, 403) for v in nachher.values())
        r = t.person.get(f"/api/material/artikel/{a1}")
        assert r.status_code == 403, r.status_code
        assert t.person.get(f"/materialablage/artikel/{a1}").status_code == 403
        assert t.person.get(f"/api/material/artikel/{a1}/pruefungen").status_code == 403
    print("Keine Tür bestanden.")


def test_abfragen():
    """GET /api/material/meine-psa mit 1 und mit 20 Artikeln: gleiche Zahl der Abfragen."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        zuordnen(t, t.art[0], t.person_id)
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn

        def zaehlen():
            del abfragen[:]
            db_mod.get_db = mit_zaehler
            try:
                r = t.person.get(LISTE)
            finally:
                db_mod.get_db = alt
            assert r.status_code == 200
            return len(abfragen), len(r.json["artikel"])
        eins = zaehlen()
        with t.app.app_context():
            from app import db
            jetzt = db.now()
            with db.transaction():
                for n in range(19):
                    db.execute("INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, assigned_user_id, "
                               "qr_token, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                               (t.ids["hms"], t.lager, f"ABF-{n}", f"ABF-{n:05d}", t.person_id, f"tok-abf-{n}", jetzt,
                                jetzt))
        zwanzig = zaehlen()
        assert eins[1] == 1 and zwanzig[1] == 20, (eins, zwanzig)
        assert eins[0] == zwanzig[0], (eins, zwanzig)
    print("Abfragezahl bestanden.")


if __name__ == "__main__":
    test_zugang()
    test_felder()
    test_qr()
    test_einzelseite()
    test_medien()
    test_kopfleiste()
    test_uebersicht()
    test_profil()
    test_keine_tuer()
    test_abfragen()
    print("Alle Tests zu „Meine PSA“ bestanden.")
