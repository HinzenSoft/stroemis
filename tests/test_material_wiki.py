"""Prüfanleitung aus dem Wiki – entfernt am 04.11.2026:  python tests/test_material_wiki.py  oder  pytest …

Bis zum 04.11.2026 (Phase 2 · Lieferung 3) konnte die Material-Verwaltung eine Seite der Strömipedia als Prüfanleitung
an eine Formularversion knüpfen; offene Prüfungen blendeten deren Abschnitt „Prüfung“ ein. Wunsch des Nutzers
(04.11.2026): „Entferne die Prüfanleitung im Wiki Funktion.“ Festlegungen (planung/ohne-pruefanleitung/auftrag.md):
Oberfläche, beide Routen, Dienst wikiverweis, formular.wiki/wiki_aendern, pruefung.anleitung und die Kopie in neue
Versionen sind weg; Journal-Einträge „wiki“ bleiben lesbar. Die Spalte mat_form.wiki_page_id samt Index blieb dabei
zunächst stehen – Schritt 37 (Aufräumen, 04.11.2026) entfernt sie (Migration: test_material_aufraeumen.py). Diese Tests
prüfen das Gegenteil der früheren: Route 404, kein Feld im JSON, keine Zeile, keine Einblendung. Seiten, Titel und
Konten sind Platzhalter."""
import io
import json
import os
import sys
import tempfile
import zipfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, festschreiben, gliederung, import_abwarten, katalog_grund, neuer_artikel,  # noqa: E402
                           neues_konto, pdf_seiten, pruef_formulare, protokoll_zeile, starten, umgebung, unterschreiben)
from test_material_trennung import zeilen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITEL = "Platzhalter Anleitung Alt"


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as f:
        return f.read()


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json(silent=True))
    return r.get_json()


def aufbau(tmp):
    """Material-Verwaltung mit Wiki-Stufe (mvw, hätte früher verknüpfen dürfen), Material-Verwaltung ohne (mv),
    Materialwart, Prüfer mit Wiki-Stufe (pw); eine öffentliche Wiki-Seite mit Abschnitt „Prüfung“; ein Lager mit zwei
    Karabinern. Eine Verknüpfung aus der Zeit vor dem 04.11.2026 lässt sich nicht mehr anlegen – die Spalte gibt es seit
    Schritt 37 nicht mehr."""
    app, k = umgebung(tmp)
    adm = k["adm"]
    mvw, _ = neues_konto(app, "mvwiki@example.org", name="MV Wiki", rechte={"material": 3, "wiki": 1})
    pw, _ = neues_konto(app, "pruefer3@example.org", "lesen", name="Prüfer Drei", mat_pruefer=True,
                        urkundennummer="1012-4720", rechte={"material": 1, "wiki": 1})
    ids = katalog_grund(adm)
    formulare = pruef_formulare(k["katalog"], ids)
    gid, _ = gliederung(adm)
    lager = ordner_neu(k["wart"], gid, "Lager Musterstadt")
    art = [neuer_artikel(k["wart"], ids["hms"], lager, serial_no=f"WK-000{n}")["id"] for n in range(1, 3)]
    unterschreiben(pw)
    seite = ok(adm.post("/api/wiki/pages", json={"title": TITEL, "content": "## Prüfung\n\nSchritt eins\n"}), 201)["page"]
    ok(adm.put(f"/api/wiki/pages/{seite['id']}/share", json={"is_public": True, "public_children": False}))
    fid = formulare["karabiner"]
    return SimpleNamespace(app=app, k=k, adm=adm, mv=k["katalog"], mvw=mvw, pw=pw, ids=ids, fid=fid, art=art,
                           seite=seite)


# --- 1. Schnittstelle -----------------------------------------------------------------------------------------------

def test_routen_und_formular():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        # Beide Routen antworten wie unbekannte Wege – für jedes Konto, auch die Plattform-Verwaltung.
        for c in (t.adm, t.mvw, t.mv, t.k["wart"], t.pw):
            assert c.get("/api/material/wiki/seiten").status_code == 404
            assert c.get("/api/material/wiki/seiten?q=anleitung").status_code == 404
            assert c.put(f"/api/material/formulare/{t.fid}/wiki", json={"seite": None}).status_code == 404
            assert c.put(f"/api/material/formulare/{t.fid}/wiki", json={"seite": t.seite["id"]}).status_code == 404
        regeln = {r.rule for r in t.app.url_map.iter_rules()}
        assert not any(r.startswith("/api/material/wiki") or (r.endswith("/wiki") and "/formulare/" in r)
                       for r in regeln)
        # formular_json ohne wiki und wiki_aendern.
        for c in (t.adm, t.mvw, t.mv, t.k["wart"]):
            text = c.get(f"/api/material/formulare/{t.fid}").get_data(as_text=True)
            f = json.loads(text)["formular"]
            assert "wiki" not in f and "wiki_aendern" not in f and TITEL not in text, sorted(f)
        # Neue Version (mit und ohne Vorlage): nichts von einer Verknüpfung.
        f2 = ok(t.mvw.post("/api/material/formulare", json={"kategorie_id": t.ids["karabiner"]}), 201)["formular"]
        f3 = ok(t.mvw.post("/api/material/formulare", json={"kategorie_id": t.ids["karabiner"], "vorlage_id": t.fid}),
                201)["formular"]
        assert "wiki" not in f2 and "wiki" not in f3
        # Alte Journal-Einträge „wiki“ bleiben lesbar (beschriftung.py und material.js).
        from app.material.services import beschriftung
        assert beschriftung.AKTION["wiki"] == "Prüfanleitung (Strömipedia) geändert"
        assert 'wiki: "Prüfanleitung (Strömipedia) geändert",' in lesen("app/material/static/material.js")
    print("Routen und Formular bestanden.")


def test_pruefung_ohne_anleitung():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        pid = ok(starten(t.pw, t.art[0]), 201)["pruefung"]["id"]
        for c in (t.pw, t.adm):
            text = c.get(f"/api/material/pruefungen/{pid}").get_data(as_text=True)
            pr = json.loads(text)["pruefung"]
            assert pr["entwurf"] and "anleitung" not in pr and TITEL not in text and t.seite["slug"] not in text
        assert ok(festschreiben(t.pw, pid, ergebnis="einsatzbereit"))
        text = t.pw.get(f"/api/material/pruefungen/{pid}").get_data(as_text=True)
        assert "anleitung" not in json.loads(text)["pruefung"] and TITEL not in text
        # Festgeschriebenes Protokoll: nichts von der Anleitung (wie vorher).
        zeile = protokoll_zeile(t.app, pid)
        assert "wiki" not in zeile["documents_json"].lower()
        pdf = " ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"])))
        for wort in (TITEL, "Prüfanleitung", "Wiki", "wiki", t.seite["slug"]):
            assert wort not in pdf, wort
    print("Prüfung ohne Anleitung bestanden.")


def test_katalog_ignoriert_altes_feld():
    """Der Export schrieb die Verknüpfung nie; ein Feld „wiki“ oder „wiki_page_id“ in einer älteren oder fremden Datei
    übergeht der Import ohne Fehler, und eine neue Formularversion aus dem Import erbt nichts mehr."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = t.mv.get("/api/material/katalog/export")
        assert r.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            daten = json.loads(z.read("katalog.json"))
            assert "wiki" not in json.dumps(daten), daten.keys()
            for e in daten["formulare"]:
                if e.get("kategorie") and e["punkte"]:
                    e["punkte"][0]["text"] += " (geändert)"
                    e["wiki"] = t.seite["id"]
                    e["wiki_page_id"] = t.seite["id"]
            aus = io.BytesIO()
            with zipfile.ZipFile(aus, "w") as neu:
                for info in z.infolist():
                    neu.writestr(info.filename, json.dumps(daten).encode() if info.filename == "katalog.json"
                                 else z.read(info))
        vorher = {f["id"] for f in zeilen(t.app, "SELECT id FROM mat_form")}
        r = t.mv.post("/api/material/katalog/import", headers=H, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(aus.getvalue()), "katalog.zip"), "trocken": "0"})
        assert import_abwarten(t.mv, r)["bericht"]["gespeichert"]
        neue = zeilen(t.app, "SELECT * FROM mat_form WHERE id NOT IN (SELECT value FROM json_each(?)) ORDER BY id",
                      (json.dumps(sorted(vorher)),))
        assert any(f["category_id"] == t.ids["karabiner"] for f in neue), neue
        assert all("wiki_page_id" not in f for f in neue), neue
    print("Katalog ignoriert das alte Feld bestanden.")


# --- 2. Schema und Quelltext ----------------------------------------------------------------------------------------

def test_spalte_entfernt():
    """Seit Schritt 37 (Aufräumen): Spalte und Index sind weg."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        assert "wiki_page_id" not in [s["name"] for s in zeilen(t.app, "PRAGMA table_info(mat_form)")]
        assert not zeilen(t.app, "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_mat_form_wiki'")
        from app.material import models
        assert models.SCHEMA_VERSION >= 37 and ("mat_form", "wiki_page_id") in models.SPALTEN_WEG_37
    print("Spalte entfernt bestanden.")


def test_quelltext_ohne_funktion():
    for pfad in ("app/material/services/wikiverweis.py", "app/material/routes_wiki.py"):
        assert not os.path.exists(os.path.join(WURZEL, pfad)), pfad
    js, css, app_css = (lesen("app/material/static/material.js"), lesen("app/material/static/material.css"),
                        lesen("app/static/css/app.css"))
    for wort in ("wikiZeile", "wikiWahl", "wiki-waehlen", "fp-wiki", "/wiki/seiten", "/wiki`", "wiki_aendern",
                 "f.wiki", "anleitungBauen", "anleitungLaden", "anleitungEinsetzen", "abschnittPruefung",
                 "ANLEITUNG_REINIGUNG", "markdownBereit", "pr.anleitung", "mat-anleitung\"", ".mat-anleitung",
                 "mat-wikizeile", "mat-wikiwahl", "Prüfanleitung aus der Strömipedia", "Prüfanleitung in der Strömipedia",
                 "Prüfanleitung verknüpft", 'mehrDazu("pruefanleitung")'):
        assert wort not in js, wort
    for wort in ("mat-wikizeile", "mat-wikiwahl", ".mat-anleitung {", ".mat-anleitung >", ".mat-anleitung-"):
        assert wort not in css and wort not in app_css, wort
    # Übung: keine Felder der Funktion in den Antworten, keine Schritte dazu.
    uebung = lesen("app/static/js/uebung/material.js")
    assert "wiki_aendern" not in uebung and "anleitung: null" not in uebung and "wiki: null" not in uebung
    assert "Prüfanleitung" not in uebung and "Prüfanleitung" not in lesen("app/einfuehrung.py")
    # Thema der Anleitung entfällt; die Leseregel der Strömipedia steht jetzt in app/anleitung.py.
    assert '"pruefanleitung"' not in lesen("app/material/services/anleitung.py")
    assert "def darf_lesen(page, user=None):" in lesen("app/anleitung.py")
    for pfad in ("app/anleitung.py", "app/material/services/katalog.py", "app/material/services/pruefung.py",
                 "app/material/routes.py"):
        assert "wikiverweis import" not in lesen(pfad) and "import wikiverweis" not in lesen(pfad), pfad
    print("Quelltext ohne Funktion bestanden.")


if __name__ == "__main__":
    test_routen_und_formular()
    test_pruefung_ohne_anleitung()
    test_katalog_ignoriert_altes_feld()
    test_spalte_entfernt()
    test_quelltext_ohne_funktion()
    print("Alle Tests zur entfernten Prüfanleitung bestanden.")
