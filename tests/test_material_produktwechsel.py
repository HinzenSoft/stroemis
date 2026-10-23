"""Produkt am Artikel ändern (Feintuning nach dem Kommentar-Dokument, Entscheidung zu L2b Nr. 29 vom 23.10.2026):
  python tests/test_material_produktwechsel.py  oder  pytest tests/test_material_produktwechsel.py

„Bearbeiten“ ändert das Produkt eines Artikels, solange er keine abgeschlossene Prüfung hat: Rechte (verwalten an der
Heimat), ungeprüft/geprüft, offener Entwurf (409 „erst festschreiben oder verwerfen“), Set und Teil, Wechsel auf ein
Set-Produkt, DEMO-Grenze, Seriennummer je Produkt; Folgen (Fälligkeit, Lebensende, Länge, Rückrufe, Durchgang, Meine
PSA), Journal „produkt_geaendert“ mit lesbarer Beschriftung (Oberfläche, Lebenslauf-PDF); die Meldung „anderes Produkt“
bei „aus dem Bestand wählen“ nennt den Weg; dazu der statische Oberflächentest des Dialogs.

Alle Hersteller, Modelle, Nummern, Intervalle und Lebensdauern hier sind Platzhalter und nur für den Test da."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, neuer_artikel, neues_konto, pdf_seiten, starten  # noqa: E402
from test_material_import import ok  # noqa: E402
from test_material_laenge import aufbau as laenge_aufbau  # noqa: E402
from test_material_sets import set_aufbau, stimmig  # noqa: E402
from test_material_sets_pruefung import pruefen  # noqa: E402
from test_material_trennung import sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402

ART = "/api/material/artikel"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def produkt_neu(c, **d):
    r = c.post("/api/material/produkte", json=dict({"manufacturer": "Testwerk"}, **d))
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def wechsel(c, iid, pid, **d):
    return c.put(f"{ART}/{iid}", json=dict(d, product_id=pid))


def artikel(c, iid):
    return ok(c.get(f"{ART}/{iid}"))["artikel"]


def journal(app, iid, aktion):
    return [(json.loads(r["before_json"] or "null"), json.loads(r["after_json"] or "null")) for r in zeilen(
        app, "SELECT before_json, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = ? "
             "ORDER BY id", (iid, aktion))]


# --- Regeln ---------------------------------------------------------------------------------------------------------

def test_regeln():
    """Rechte, Set und Teil, Set-Produkt, offener Entwurf, festgeschriebene Prüfung, DEMO-Grenze, Seriennummer je
    Produkt; produkt_aenderbar in der Artikelantwort."""
    from app.material.services import bestand, sets
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1 = t.s["id"], t.teile[0]
        f = t.f["id"]
        assert artikel(w, f)["produkt_aenderbar"] is True
        assert artikel(w, s)["produkt_aenderbar"] is False and artikel(w, k1)["produkt_aenderbar"] is False
        # Rechte: verwalten an der Heimat – Führungskraft und Prüfer lesen bzw. prüfen nur (403), B sieht A nicht (404).
        assert wechsel(t.k["fuehrung"], f, t.rolle).status_code == 403
        assert wechsel(p, f, t.rolle).status_code == 403
        assert wechsel(t.wart_b, f, t.rolle).status_code == 404
        # Set und Teil: das Produkt legt die Stückliste fest; kein Wechsel auf ein Set-Produkt.
        r = wechsel(w, s, t.rolle)
        assert r.status_code == 409 and "Das Produkt eines Sets" in r.json["error"], r.get_json()
        r = wechsel(w, k1, t.rolle)
        assert r.status_code == 409 and "Teil des Sets" in r.json["error"] and "Stückliste" in r.json["error"], r.get_json()
        r = wechsel(w, f, t.set_p)
        assert r.status_code == 409 and r.json["error"] == sets.ZU_SET_PRODUKT, r.get_json()
        assert stimmig(app)
        # Offener Entwurf: erst festschreiben oder verwerfen.
        pr = ok(starten(p, f), 201)["pruefung"]
        r = wechsel(w, f, t.rolle)
        assert r.status_code == 409 and r.json["error"].endswith(bestand.PRODUKT_ENTWURF), r.get_json()
        assert artikel(w, f)["produkt_aenderbar"] is True          # das Feld bleibt, der Dialog sagt es am Feld
        assert p.delete(f"/api/material/pruefungen/{pr['id']}", headers=H).status_code == 200
        # Ungeprüft: der Wechsel geht (Metall → Metall), Journal mit Namen und Artikelnummer.
        ok(wechsel(w, f, t.rolle))
        a = artikel(w, f)
        assert a["product_id"] == t.rolle and a["produkt"]["model"] == "Rolle Gamma", a["produkt"]
        [(vorher, nachher)] = journal(app, f, "produkt_geaendert")
        assert (vorher["product_id"], nachher["product_id"]) == (t.ids["hms"], t.rolle), (vorher, nachher)
        assert vorher["produkt"] == "Testwerk HMS Beta (HB-7)" and nachher["produkt"] == "Testwerk Rolle Gamma (RG-1)"
        assert not journal(app, f, "geaendert")
        # Zurück und andere Felder im selben Speichern: ein Eintrag „produkt_geaendert“ mit allen Feldern.
        ok(wechsel(w, f, t.ids["hms"], notes="Platzhalter-Bemerkung"))
        vorher, nachher = journal(app, f, "produkt_geaendert")[-1]
        assert nachher["notes"] == "Platzhalter-Bemerkung" and nachher["product_id"] == t.ids["hms"], nachher
        # Seriennummer je Produkt: Gibt es sie beim neuen Produkt schon, 409 mit der Inventarnummer.
        andere = neuer_artikel(w, t.rolle, t.lager_a, serial_no="FREI-A-1")
        r = wechsel(w, andere["id"], t.ids["hms"])
        assert r.status_code == 409 and t.f["inventory_no"] in r.json["error"], r.get_json()
        # DEMO-Grenze: ein echter Artikel wechselt nicht auf ein DEMO-Produkt (er würde DEMO).
        demo_p = produkt_neu(t.k["katalog"], category_id=t.ids["karabiner"], model="Demo-Rolle Platzhalter",
                             material_kind="metall_hardware", interval_months=12)
        sql(app, "UPDATE mat_product SET demo = 1 WHERE id = ?", (demo_p,))
        r = wechsel(w, f, demo_p)
        assert r.status_code == 409 and r.json["error"] == bestand.PRODUKT_DEMO, r.get_json()
        # Festgeschrieben: das Produkt steht fest – 409 im Dienst, der Trigger fängt den Rest; das Feld ist weg.
        pruefen(p, f)
        assert artikel(w, f)["produkt_aenderbar"] is False
        r = wechsel(w, f, t.rolle)
        assert r.status_code == 409 and r.json["error"] == bestand.PRODUKT_FEST, r.get_json()
        assert artikel(w, f)["product_id"] == t.ids["hms"]
    print("Regeln des Produktwechsels bestanden.")


# --- Folgen ---------------------------------------------------------------------------------------------------------

def test_folgen():
    """Was der Wechsel nachzieht: Lebensende (aus der Lebensdauer des neuen Produkts bzw. weg), Länge (weg ohne
    vorgesehene Länge – mit Journal), Fälligkeit (kürzeres Intervall rückt sie vor), Rückrufe (produktbezogen, im
    Journal), Durchgang und Meine PSA unverändert, Lebenslauf-PDF und Journalbeschriftung."""
    from app.material.services import beschriftung
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = laenge_aufbau(tmp)
        app, w, kp = t.app, t.w, t.kp
        h = _heute()
        # Platzhalter-Produkte: textil mit kürzerer Lebensdauer, Metall mit kürzerem Intervall.
        gurt_kurz = produkt_neu(kp, category_id=t.ids["gurte"], model="Gurt Kurz", article_no="GK-1",
                                material_kind="textil", lifetime_years=5)
        hms_kurz = produkt_neu(kp, category_id=t.ids["karabiner"], model="HMS Kurz", article_no="HK-1",
                               material_kind="metall_hardware", interval_months=3)
        # Ein Seil mit Länge (textil, 10 Jahre, Kategorie mit Länge).
        seil = neuer_artikel(w, t.seil, t.lager, serial_no="SEIL-PW-1", manufactured_on=t.herst, length_m="50,0")
        assert seil["length_m"] == 50.0 and seil["retire_by"].startswith(str(int(t.herst[:4]) + 10)), seil
        # Durchgang über das Lager und eine Person, der das Seil zugeordnet ist.
        rid = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager, "titel": "Platzhalter-Durchgang"}),
                 201)["durchgang"]["id"]
        person, person_id = neues_konto(app, "person_pw@example.org", name="Person Platzhalter", stufe=0)
        ok(w.put(f"{ART}/{seil['id']}/zuordnung", json={"user_id": person_id}))
        # Rückrufe: einer am Seil-Produkt, einer am neuen Gurt-Produkt (alle Artikel).
        rr_alt = ok(kp.post(f"/api/material/produkte/{t.seil}/rueckrufe", json={"title": "Platzhalter-Rückruf Seil",
                                                                                 "mail": False}), 201)["rueckruf"]["id"]
        rr_neu = ok(kp.post(f"/api/material/produkte/{gurt_kurz}/rueckrufe", json={"title": "Platzhalter-Rückruf Gurt",
                                                                                     "mail": False}), 201)["rueckruf"]["id"]
        assert [r["id"] for r in artikel(w, seil["id"])["rueckrufe"]] == [rr_alt]
        # Seil → Gurt Kurz (textil, 5 Jahre, Kategorie ohne Länge): Lebensende neu, Länge weg, Rückruf gewechselt.
        ok(wechsel(w, seil["id"], gurt_kurz, length_m="50,0"))
        a = artikel(w, seil["id"])
        assert a["retire_by"].startswith(str(int(t.herst[:4]) + 5)) and a["length_m"] is None, a
        assert [r["id"] for r in a["rueckrufe"]] == [rr_neu], a["rueckrufe"]
        [(vorher, nachher)] = journal(app, seil["id"], "produkt_geaendert")
        assert vorher["length_m"] == 50.0 and nachher["length_m"] is None, (vorher, nachher)
        assert vorher["retire_by"] != nachher["retire_by"], (vorher, nachher)
        assert nachher["rueckruf_neu"] == [f"Platzhalter-Rückruf Gurt (Nr. {rr_neu})"], nachher
        assert nachher["rueckruf_nicht_mehr"] == [f"Platzhalter-Rückruf Seil (Nr. {rr_alt})"], nachher
        # Durchgang und Zuordnung bleiben; Meine PSA zeigt das neue Produkt.
        assert a["durchgang"] and a["durchgang"]["id"] == rid and a["zugeordnet"]["name"] == "Person Platzhalter", a
        karten = ok(person.get("/api/material/meine-psa"))["artikel"]
        assert [k["produkt"]["model"] for k in karten if k["id"] == seil["id"]] == ["Gurt Kurz"], karten
        # Gurt Kurz → HMS Kurz (Metall, 3 Monate): Lebensende weg, die Fälligkeit rückt auf heute + 3 Monate vor.
        due_vorher = a["next_due_on"]
        ok(wechsel(w, seil["id"], hms_kurz))
        a = artikel(w, seil["id"])
        assert a["retire_by"] is None and a["intervall"]["monate"] == 3, a
        assert a["next_due_on"] < due_vorher and a["next_due_on"] <= f"{h.year + 1}-{h.month:02d}-31", a["next_due_on"]
        assert journal(app, seil["id"], "faelligkeit"), "Fälligkeit nicht vorgezogen"
        # Beschriftung: „Produkt geändert“, Feld „Produkt“ ohne die technische Kennung – Oberfläche wie PDF.
        e = next(x for x in a["journal"] if x["action"] == "produkt_geaendert")
        zeile = beschriftung.journal_zeilen([e])[0]
        assert zeile["aktion"] == "Produkt geändert", zeile
        felder = {f["feld"]: (f["vorher"], f["nachher"]) for f in zeile["felder"]}
        assert felder["Produkt"] == ("Testwerk Gurt Kurz (GK-1)", "Testwerk HMS Kurz (HK-1)"), felder
        assert "Lebensende" in felder and not any(f.startswith("Produkt") and f != "Produkt" for f in felder), felder
        assert sum(1 for f in zeile["felder"] if f["feld"] == "Produkt") == 1, zeile["felder"]
        # Lebenslauf-PDF nennt den Wechsel.
        r = w.get(f"/material/artikel/{seil['id']}/lebenslauf.pdf")
        assert r.status_code == 200 and r.data.startswith(b"%PDF")
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(s.split()) for s in pdf_seiten(pfad))
        assert "Produkt geändert" in text and "Testwerk HMS Kurz (HK-1)" in text, text[-1500:]
        # Textil ohne Herstelldatum geht nicht: Ein Metallartikel ohne Herstellung wechselt nicht auf textil (400).
        m = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="HMS-PW-1")
        r = wechsel(w, m["id"], t.ids["gurt"])
        assert r.status_code == 400 and "Herstelldatum" in r.json["error"], r.get_json()
        ok(wechsel(w, m["id"], t.ids["gurt"], manufactured_on=t.herst))
        assert artikel(w, m["id"])["retire_by"].startswith(str(int(t.herst[:4]) + 10))
    print("Folgen des Produktwechsels bestanden.")


# --- „aus dem Bestand wählen“: Weg zum Produktfeld ------------------------------------------------------------------

def test_anderes_produkt_nennt_den_weg():
    """Die Auswahl mit genauer Nummer eines Artikels mit anderem Produkt: Hinweis mit Weg „Artikel öffnen → Bearbeiten →
    Produkt“ und produkt_aenderbar, solange er ungeprüft ist; danach ohne Weg. Ebenso der 409 beim Einsetzen. Dazu L2b
    Nr. 3: Ein entnommenes freies Teil lässt sich wieder einsetzen."""
    from app.material.services import setaustausch
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, p = t.wart_a, t.k["pruefer"]
        s = t.s["id"]
        g = neuer_artikel(w, t.ids["hms"], t.lager_a, serial_no="HMS-PW-9")
        url = f"/api/material/ordner/{t.lager_a}/kandidaten?product_id={t.rolle}&q={g['inventory_no']}"
        h = ok(w.get(url))["hinweis"]
        assert h["artikel"] == {"id": g["id"], "inventory_no": g["inventory_no"], "produkt_aenderbar": True}, h
        assert h["text"].endswith(setaustausch.PRODUKT_WEG), h
        # Am Set: an der Rolle eine Lücke schaffen und den Karabiner einsetzen – 409 mit demselben Weg.
        ok(w.post(f"{ART}/{s}/teil-entnehmen", json={"teil_id": t.teile[2]}))          # die Rolle (Austausch „ja“)
        r = w.post(f"{ART}/{s}/teil-einsetzen", json={"item_id": g["id"]})
        assert r.status_code == 409 and r.json["error"].endswith(setaustausch.PRODUKT_WEG), r.get_json()
        # L2b Nr. 3 (bestätigt am 23.10.2026): Ein entnommenes, freies Teil lässt sich wieder einsetzen.
        assert artikel(w, t.teile[2])["lock_state"] == "frei"
        ok(w.post(f"{ART}/{s}/teil-einsetzen", json={"item_id": t.teile[2]}), 201)
        assert artikel(w, t.teile[2])["teil_von"]["id"] == s
        pruefen(p, g["id"])
        h = ok(w.get(url))["hinweis"]
        assert h["artikel"]["produkt_aenderbar"] is False and not h["text"].endswith(setaustausch.PRODUKT_WEG), h
    print("Hinweis „anderes Produkt“ mit Weg bestanden.")


# --- Oberfläche (statisch) ------------------------------------------------------------------------------------------

def _lies(rel):
    return open(os.path.join(WURZEL, rel), encoding="utf-8").read()


def _funktion(js, name):
    anfang = js.index(f"function {name}(")
    return js[anfang:js.index("\n  }\n", anfang)]


def test_oberflaeche_statisch():
    """Dialog „Bearbeiten“ mit Produktfeld (nur mit produkt_aenderbar; mit Entwurf ohne „anderes Produkt“), Suche wie
    beim Anlegen, Folgen-Hinweis, Lebensende und Länge nach dem neuen Produkt, product_id im PUT; Link aus der Auswahl
    („?bearbeiten=produkt“) öffnet den Dialog; Texte gleich dem Dienst; Journal-Beschriftung gleich beschriftung.py;
    Knopfsprache (ein roter Knopf im Dialog, kein btn ghost, kein btn danger); CSS-Block; Jahresbericht mit set_text."""
    from app.material.services import beschriftung, bestand, sets
    js = _lies("app/material/static/material.js")
    css = _lies("app/material/static/material.css")
    d = _funktion(js, "artikelDialog")
    for haken in ("const mitProdukt = !!a.produkt_aenderbar;", 'id="ad-anders">anderes Produkt</button>',
                  "a.entwurf ? \"\" : ' <button class=\"lnk\" type=\"button\" id=\"ad-anders\">", "esc(PRODUKT_ENTWURF)",
                  "produktTreffer($(\"#ad-treffer\", body), q,", "if (p && p.is_set) { produktFehler(PRODUKT_SET); return; }",
                  "produktFolgen(a, neuesProdukt)", "if (neuesProdukt) daten.product_id = neuesProdukt.id;",
                  "if (textil && !neuesProdukt) daten.retire_by", "if (laengeZeile && !laengeZeile.hidden) daten.length_m",
                  "if (produktSuche) suchen();", 'id="ad-zurueck">zurück zum bisherigen</button>'):
        assert haken in d, haken
    assert d.count('class="btn"') == 1 and "btn danger" not in d and "btn ghost" not in d
    assert re.search(r'const PRODUKT_ENTWURF = "([^"]*)";', js).group(1) == bestand.PRODUKT_ENTWURF
    assert re.search(r'const PRODUKT_SET = "([^"]*)";', js).group(1) == sets.ZU_SET_PRODUKT
    folgen = _funktion(js, "produktFolgen")
    assert "p.laenge_moeglich" in folgen and 'p.material_kind === "textil"' in folgen
    # Link aus „aus dem Bestand wählen“ und Öffnen auf der Artikelseite.
    wahl = _funktion(js, "bestandWahl")
    assert "?bearbeiten=produkt\" target=\"_blank\" rel=\"noopener\">Produkt von ${esc(artikel.inventory_no)} ändern</a>" in wahl
    assert 'if (adresse.get("bearbeiten") === "produkt")' in js and "if (darfPflegen && a.produkt_aenderbar) artikelDialog(a, true);" in js
    assert 'adresse.delete("bearbeiten");' in js
    # Journal: Aktion und Feld wie im PDF; die Kennung fällt neben dem Namen weg.
    assert 'produkt_geaendert: "Produkt geändert"' in js and beschriftung.AKTION["produkt_geaendert"] == "Produkt geändert"
    assert 'produkt: "Produkt",' in js and beschriftung.FELD["produkt"] == "Produkt"
    assert '!(f === "product_id" && "produkt" in alle)' in _funktion(js, "journalHtml")
    # Jahresbericht: Zusatz am Set in der Liste der Aussonderungen (Web wie PDF).
    assert '${x.set_text ? ` <span class="muted">· ${esc(x.set_text)}</span>` : ""}' in js
    assert "{% if a.set_text %} · {{ a.set_text }}{% endif %}" in _lies("app/material/templates/material/pdf/bericht.html")
    block = css[css.index("/* Feintuning nach dem Kommentar-Dokument (23.10.2026)"):]
    assert ".mat-ad-produkt" in block and "!important" not in block
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_regeln()
    test_folgen()
    test_anderes_produkt_nennt_den_weg()
    test_oberflaeche_statisch()
