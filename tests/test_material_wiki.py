"""Prüfanleitung aus dem Wiki (Phase 2 · Lieferung 3):  python tests/test_material_wiki.py  oder  pytest …

Testplan 6.2 des Bauentwurfs L3 mit der Entscheidung vom 19.10.2026: Verknüpfen darf nur die Material-Verwaltung mit
Stufe Mitglied im Wiki. Eine Wiki-Seite je Formularversion; eingeblendet nur in offenen Prüfungen, jeder sieht nur, was
er im Wiki lesen darf, nichts davon kommt ins Protokoll. Alle Seiten, Titel und Konten sind Platzhalter."""
import io
import json
import os
import sys
import tempfile
import zipfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, festschreiben, freigeben, gliederung, import_abwarten, katalog_grund,  # noqa: E402
                           neuer_artikel, neues_konto, pdf_seiten, pruef_formulare, protokoll_zeile, starten, umgebung,
                           unterschreiben)
from test_material_trennung import zeilen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402
from test_wiki_lesemodus import konto  # noqa: E402

NUR_MIT_WIKI = "dir fehlt die Stufe in der Strömipedia"
FEHLT = "Seite der Strömipedia nicht gefunden."
GEHEIM = "Geheimtitel Platzhalter"


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json(silent=True))
    return r.get_json()


def aufbau(tmp):
    """Konten: Material-Verwaltung mit Wiki-Stufe (mvw) und ohne (katalog aus umgebung), Prüfer mit Wiki-Stufe (pw),
    externer Prüfer ohne Wiki-Stufe (extern, befristete Prüffreigabe), ein neues Konto mit der Vorgabe für neue Konten
    (neu, Leserecht am Ordner), Führungskraft und Materialwart aus umgebung. Wiki-Seiten (vom Admin): offen
    (öffentlich, mit Abschnitt „Prüfung“), intern, geheim (lesebeschränkt), weg (Papierkorb), vorlage. Ein Lager mit
    drei Karabinern; aktive Formulare aus pruef_formulare."""
    app, k = umgebung(tmp)
    adm = k["adm"]
    mvw, mvw_id = neues_konto(app, "mvwiki@example.org", name="MV Wiki", rechte={"material": 2, "wiki": 1})
    pw, pw_id = neues_konto(app, "pruefer3@example.org", "lesen", name="Prüfer Drei", mat_pruefer=True,
                            urkundennummer="1012-4720", rechte={"material": 1, "wiki": 1})
    extern, extern_id = neues_konto(app, "extern@example.org", name="Extern Platzhalter", mat_pruefer=True,
                                    urkundennummer="1012-4721")
    ids = katalog_grund(adm)
    formulare = pruef_formulare(k["katalog"], ids)
    gid, _ = gliederung(adm)
    neu, neu_id = konto(app, adm, "neu@example.org", "Neues Konto Platzhalter")
    freigeben(adm, gid, neu_id, "lesen")
    lager = ordner_neu(k["wart"], gid, "Lager Musterstadt")
    art = [neuer_artikel(k["wart"], ids["hms"], lager, serial_no=f"WK-000{n}")["id"] for n in range(1, 4)]
    for c in (pw, extern):
        unterschreiben(c)

    def seite(titel, inhalt):
        return ok(adm.post("/api/wiki/pages", json={"title": titel, "content": inhalt}), 201)["page"]
    p = SimpleNamespace(
        offen=seite("Platzhalter Anleitung Offen", "# Karabiner\n\nEinleitung\n\n## Prüfung\n\nSchritt eins\n\n## Pflege\n"),
        intern=seite("Platzhalter Anleitung Intern", "## Prüfung\n\nINTERN-MARKE\n"),
        geheim=seite(GEHEIM, "## Prüfung\n\nGEHEIM-MARKE\n"),
        weg=seite("Platzhalter Anleitung Weg", "## Prüfung\n"),
        vorlage=seite("Platzhalter Anleitung Vorlage", "## Prüfung\n"))
    ok(adm.put(f"/api/wiki/pages/{p.offen['id']}/share", json={"is_public": True, "public_children": False}))
    ok(adm.put(f"/api/wiki/pages/{p.geheim['id']}/restrict", json={"read_restricted": True}))
    ok(adm.put(f"/api/wiki/pages/{p.vorlage['id']}/options", json={"is_template": True}))
    ok(adm.delete(f"/api/wiki/pages/{p.weg['id']}", headers=H))
    return SimpleNamespace(app=app, k=k, adm=adm, mv=k["katalog"], mvw=mvw, mvw_id=mvw_id, pw=pw, pw_id=pw_id,
                           extern=extern, extern_id=extern_id, neu=neu, ids=ids, formulare=formulare, gid=gid,
                           lager=lager, art=art, p=p)


def verknuepfen(c, fid, seite):
    return c.put(f"/api/material/formulare/{fid}/wiki", json={"seite": seite})


# --- 1. Seitenwahl --------------------------------------------------------------------------------------------------

def test_seitenwahl():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p = t.p
        r = ok(t.mvw.get("/api/material/wiki/seiten"))
        seiten = {s["id"]: s for s in r["seiten"]}
        assert not r["lesemodus"] and p.offen["id"] in seiten and p.intern["id"] in seiten
        assert p.geheim["id"] not in seiten and p.weg["id"] not in seiten and p.vorlage["id"] not in seiten
        assert (seiten[p.offen["id"]]["reichweite"], seiten[p.intern["id"]]["reichweite"]) == ("oeffentlich", "intern")
        assert set(seiten[p.offen["id"]]) == {"id", "titel", "icon", "reichweite"}
        assert GEHEIM not in json.dumps(r, ensure_ascii=False)
        r = ok(t.mvw.get("/api/material/wiki/seiten?q=anleitung off"))
        assert [s["id"] for s in r["seiten"]] == [p.offen["id"]]
        # Freigegeben zum Bearbeiten: dann auch die beschränkte Seite.
        ok(t.adm.put(f"/api/wiki/pages/{p.geheim['id']}/editors", json={"user_ids": [t.mvw_id]}))
        seiten = {s["id"]: s for s in ok(t.mvw.get("/api/material/wiki/seiten"))["seiten"]}
        assert seiten[p.geheim["id"]]["reichweite"] == "beschraenkt"
        # Die Plattform-Verwaltung (Wiki-Verwaltung) sieht alles außer Papierkorb und Vorlagen.
        seiten = {s["id"] for s in ok(t.adm.get("/api/material/wiki/seiten"))["seiten"]}
        assert {p.offen["id"], p.intern["id"], p.geheim["id"]} <= seiten and p.weg["id"] not in seiten
        # Material-Verwaltung ohne Wiki-Stufe: 403 mit Klartext (Entscheidung vom 19.10.2026); alle anderen 403.
        r = t.mv.get("/api/material/wiki/seiten")
        assert r.status_code == 403 and NUR_MIT_WIKI in r.json["error"], r.get_json()
        for c in (t.k["wart"], t.k["fuehrung"], t.pw, t.extern, t.neu):
            r = c.get("/api/material/wiki/seiten")
            assert r.status_code == 403 and GEHEIM not in r.get_data(as_text=True), r.get_json()
    print("Seitenwahl bestanden.")


# --- 2. Setzen ------------------------------------------------------------------------------------------------------

def test_setzen():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p, fid = t.p, t.formulare["karabiner"]

        def journal():
            return [(json.loads(j["before_json"]), json.loads(j["after_json"])) for j in zeilen(
                t.app, "SELECT * FROM mat_audit WHERE entity = 'form' AND entity_id = ? AND action = 'wiki' ORDER BY id",
                (fid,))]
        f = ok(verknuepfen(t.mvw, fid, p.intern["id"]))["formular"]
        assert f["wiki"] == {"seite": p.intern["id"], "titel": "Platzhalter Anleitung Intern", "reichweite": "intern",
                             "url": f"/stroemipedia/{p.intern['slug']}", "zustand": "ok"} and f["wiki_aendern"]
        assert journal() == [({"seite": None}, {"seite": p.intern["id"]})]
        assert "Platzhalter Anleitung" not in json.dumps(zeilen(t.app, "SELECT * FROM mat_audit WHERE entity = 'form'"),
                                                          ensure_ascii=False)
        # Nicht lesbar, Papierkorb, unbekannt: dieselbe 404.
        for seite in (p.geheim["id"], p.weg["id"], 999999):
            r = verknuepfen(t.mvw, fid, seite)
            assert r.status_code == 404 and r.json["error"] == FEHLT, (seite, r.get_json())
        assert t.mvw.put(f"/api/material/formulare/{fid}/wiki", json={}).status_code == 400
        assert ok(verknuepfen(t.mvw, fid, None))["formular"]["wiki"] is None
        assert journal()[-1] == ({"seite": p.intern["id"]}, {"seite": None})
        # Eine andere Verknüpfung, die diese MV nicht lesen darf: unverändert angenommen, ohne Journal.
        ok(verknuepfen(t.adm, fid, p.geheim["id"]))
        n = len(journal())
        f = ok(verknuepfen(t.mvw, fid, p.geheim["id"]))["formular"]
        assert len(journal()) == n and f["wiki"] == {"seite": p.geheim["id"], "titel": None, "url": None,
                                                    "reichweite": None, "zustand": "kein_zugang"}
        assert GEHEIM not in t.mvw.get(f"/api/material/formulare/{fid}").get_data(as_text=True)
        # Ohne Wiki-Stufe: 403; sie sieht den Stand, darf ihn aber nicht ändern. Wer nicht Material-Verwaltung ist,
        # sieht nichts davon.
        r = verknuepfen(t.mv, fid, None)
        assert r.status_code == 403 and NUR_MIT_WIKI in r.json["error"]
        f = ok(t.mv.get(f"/api/material/formulare/{fid}"))["formular"]
        assert f["wiki"]["zustand"] == "kein_zugang" and f["wiki_aendern"] is False
        f = ok(t.k["wart"].get(f"/api/material/formulare/{fid}"))["formular"]
        assert f["wiki"] is None and f["wiki_aendern"] is False
        assert verknuepfen(t.k["wart"], fid, None).status_code == 403
        # Benutztes Formular: Prüfung festgeschrieben – die Verknüpfung lässt sich trotzdem ändern, nichts sonst.
        pid = ok(starten(t.pw, t.art[0]), 201)["pruefung"]["id"]
        assert ok(festschreiben(t.pw, pid, ergebnis="einsatzbereit"))
        vorher = zeilen(t.app, "SELECT * FROM mat_form WHERE id = ?", (fid,))[0]
        punkte = zeilen(t.app, "SELECT * FROM mat_checklist_item WHERE form_id = ? ORDER BY id", (fid,))
        ok(verknuepfen(t.mvw, fid, p.offen["id"]))
        nachher = zeilen(t.app, "SELECT * FROM mat_form WHERE id = ?", (fid,))[0]
        assert nachher.pop("wiki_page_id") == p.offen["id"] and vorher.pop("wiki_page_id") == p.geheim["id"]
        assert nachher == vorher and zeilen(t.app, "SELECT * FROM mat_checklist_item WHERE form_id = ? ORDER BY id",
                                            (fid,)) == punkte
        r = t.mvw.put(f"/api/material/formulare/{fid}", json={"punkte": [{"text": "Anders", "art": "yesno", "soll": "ja"}]})
        assert r.status_code == 409 and "benutzt" in r.json["error"], r.get_json()
    print("Setzen bestanden.")


# --- 3. Vererbung und Katalogaustausch ------------------------------------------------------------------------------

def test_vererbung_und_katalog():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p, fid = t.p, t.formulare["karabiner"]
        ok(verknuepfen(t.mvw, fid, p.intern["id"]))
        f2 = ok(t.mvw.post("/api/material/formulare", json={"kategorie_id": t.ids["karabiner"]}), 201)["formular"]
        f3 = ok(t.mvw.post("/api/material/formulare", json={"kategorie_id": t.ids["karabiner"], "vorlage_id": fid}),
                201)["formular"]
        assert f2["wiki"]["seite"] == f3["wiki"]["seite"] == p.intern["id"]
        ok(verknuepfen(t.mvw, f3["id"], None))
        # Katalogaustausch: kein Wiki-Feld im Export; eine neue Version aus dem Import erbt von der letzten Version, ein
        # „wiki“ in der Datei wird übergangen.
        ok(verknuepfen(t.mvw, f3["id"], p.offen["id"]))
        r = t.mv.get("/api/material/katalog/export")
        assert r.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            daten = json.loads(z.read("katalog.json"))
            assert "wiki" not in json.dumps(daten), daten.keys()
            for e in daten["formulare"]:
                if e.get("kategorie") and e["punkte"]:
                    e["punkte"][0]["text"] += " (geändert)"
                    e["wiki"] = t.p.geheim["id"]
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
        karabiner = [f for f in neue if f["category_id"] == t.ids["karabiner"]]
        assert len(karabiner) == 1 and karabiner[0]["wiki_page_id"] == p.offen["id"], karabiner
        assert all(f["wiki_page_id"] != p.geheim["id"] for f in neue)
    print("Vererbung und Katalog bestanden.")


# --- 4. Anleitung und Rechte ----------------------------------------------------------------------------------------

def test_anleitung_und_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p, fid = t.p, t.formulare["karabiner"]
        ok(verknuepfen(t.mvw, fid, p.intern["id"]))
        e_pw = ok(starten(t.pw, t.art[0]), 201)["pruefung"]["id"]
        e_ex = ok(starten(t.extern, t.art[1]), 201)["pruefung"]["id"]

        def anleitung(c, pid):
            r = c.get(f"/api/material/pruefungen/{pid}")
            assert r.status_code == 200, r.get_json()
            return r.json["pruefung"]["anleitung"], r.get_data(as_text=True)
        a, _ = anleitung(t.pw, e_pw)
        assert a == {"titel": "Platzhalter Anleitung Intern", "url": f"/stroemipedia/{p.intern['slug']}",
                     "quelle": f"/api/wiki/pages/{p.intern['slug']}?leise=1"}, a
        for c, pid in ((t.extern, e_ex), (t.neu, e_pw)):
            a, text = anleitung(c, pid)
            assert a == {"kein_zugang": True} and "Platzhalter Anleitung Intern" not in text and p.intern["slug"] not in text
        # Die Quelle liefert genau diesen Konten die Seite – und ein Abruf mit leise=1 ist kein Besuch.
        besuche = len(zeilen(t.app, "SELECT 1 FROM wiki_views"))
        assert t.pw.get(f"/api/wiki/pages/{p.intern['slug']}?leise=1").status_code == 200
        assert len(zeilen(t.app, "SELECT 1 FROM wiki_views")) == besuche
        assert t.extern.get(f"/api/wiki/pages/{p.intern['slug']}?leise=1").status_code == 403
        assert t.extern.get(f"/api/public/pages/{p.intern['slug']}").status_code == 404
        # Öffentliche Seite: ohne Wiki-Stufe über den öffentlichen Endpunkt.
        ok(verknuepfen(t.mvw, fid, p.offen["id"]))
        a, _ = anleitung(t.extern, e_ex)
        assert a == {"titel": "Platzhalter Anleitung Offen", "url": f"/stroemipedia/{p.offen['slug']}",
                     "quelle": f"/api/public/pages/{p.offen['slug']}"}, a
        assert t.extern.get(a["quelle"]).status_code == 200 and t.neu.get(a["quelle"]).status_code == 200
        assert anleitung(t.neu, e_pw)[0]["quelle"] == f"/api/public/pages/{p.offen['slug']}"
        # Beschränkt: nur für Freigegebene.
        ok(verknuepfen(t.adm, fid, p.geheim["id"]))
        for c, pid in ((t.pw, e_pw), (t.extern, e_ex), (t.neu, e_pw)):
            a, text = anleitung(c, pid)
            assert a == {"kein_zugang": True} and GEHEIM not in text
        ok(t.adm.put(f"/api/wiki/pages/{p.geheim['id']}/editors", json={"user_ids": [t.pw_id]}))
        assert anleitung(t.pw, e_pw)[0]["titel"] == GEHEIM
        # Papierkorb: nichts; wiederhergestellt: wieder da.
        ok(t.adm.delete(f"/api/wiki/pages/{p.geheim['id']}", headers=H))
        assert anleitung(t.pw, e_pw)[0] is None
        assert t.mvw.get(f"/api/material/formulare/{fid}").json["formular"]["wiki"]["zustand"] == "papierkorb"
        ok(t.adm.post(f"/api/wiki/pages/{p.geheim['id']}/restore", json={}))
        assert anleitung(t.pw, e_pw)[0]["titel"] == GEHEIM
        # Abgeschlossen: keine Anleitung.
        assert ok(festschreiben(t.pw, e_pw, ergebnis="einsatzbereit"))
        assert anleitung(t.pw, e_pw)[0] is None
        # Endgültig gelöscht (purge) bei benutztem Formular: Spalte NULL, Prüfung lesbar.
        ok(t.adm.delete(f"/api/wiki/pages/{p.geheim['id']}", headers=H))
        ok(t.adm.delete(f"/api/wiki/trash/{p.geheim['id']}", headers=H))
        assert zeilen(t.app, "SELECT wiki_page_id FROM mat_form WHERE id = ?", (fid,))[0]["wiki_page_id"] is None
        assert anleitung(t.pw, e_pw)[0] is None and anleitung(t.extern, e_ex)[0] is None
    print("Anleitung und Rechte bestanden.")


# --- 5. Kein Nachweis -----------------------------------------------------------------------------------------------

def test_kein_nachweis():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p, fid = t.p, t.formulare["karabiner"]
        ok(verknuepfen(t.mvw, fid, p.offen["id"]))
        pid = ok(starten(t.pw, t.art[2]), 201)["pruefung"]["id"]
        assert ok(festschreiben(t.pw, pid, ergebnis="einsatzbereit"))
        zeile = protokoll_zeile(t.app, pid)
        assert "wiki" not in zeile["documents_json"].lower() and "Platzhalter Anleitung" not in zeile["documents_json"]
        text = " ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"])))
        for wort in ("Platzhalter Anleitung", "Prüfanleitung", "Wiki", "wiki"):
            assert wort not in text, (wort, text[max(0, text.find(wort) - 200):text.find(wort) + 100])
        assert p.offen["slug"] not in text and "Karabiner generisch" in text
    print("Kein Nachweis bestanden.")


# --- 6. Oberfläche (statisch) ---------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    """material.js (Paket OBERFLÄCHE, Bauentwurf 3.5.2 und 4.4): eigene strenge Reinigung der Einblendung, Abschnitt
    „Prüfung“ im <template> ausgeschnitten, geschlossener Shadow-Root, kein MD.enhance; die Klick-Delegation übergeht
    .mat-anleitung, Festschreiben liest Grund, Datum und Bemerkung nur aus den eigenen Behältern; Formularzeile mit
    „Ändern“ nur bei wiki_aendern. Die Wirkung (DOM-Clobbering-Probe) prüft die Durchsicht im Browser."""
    import re
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    rein = js[js.index("const ANLEITUNG_REINIGUNG = {"):js.index("ALLOW_DATA_ATTR: false };")]
    tags = re.search(r"FORBID_TAGS: \[([^\]]*)\]", rein).group(1)
    attr = re.search(r"FORBID_ATTR: \[([^\]]*)\]", rein).group(1)
    for t_ in ("style", "form", "textarea", "select", "button", "dialog", "iframe", "input", "label", "output", "data",
               "object", "embed", "base", "meta", "link"):
        assert f'"{t_}"' in tags, t_
    for a in ("style", "id", "name", "for", "form", "formaction", "target"):
        assert f'"{a}"' in attr, a
    assert '"target"' not in rein[rein.index("ADD_ATTR"):rein.index("FORBID_TAGS")]
    teil = js[js.index("  function anleitungBauen(a) {"):js.index("  async function pruefungAnsicht() {")]
    assert 'attachShadow({ mode: "closed" })' in teil and "DOMPurify.sanitize(MD.render(" in teil
    # Klassen aus app.css mit position: fixed (.md-lightbox) bleiben im Kasten (Prüfung vor Auslieferung, Sicherheit 2).
    assert "const ANLEITUNG_STIL = `:host { display: block; contain: paint; }" in js
    assert "ANLEITUNG_REINIGUNG)" in teil and "MD.enhance" not in js[js.index("const ANLEITUNG_REINIGUNG"):js.index("  async function pruefungAnsicht() {")]
    ab = js[js.index("  function abschnittPruefung(html) {"):js.index("  function anleitungBauen(a) {")]
    assert 'document.createElement("template")' in ab and "/^H[1-5]$/" in ab and 'text(n) === "prüfung"' in ab
    assert 'a.setAttribute("target", "_blank")' in ab and '".md-marker"' in ab and '".einbau"' in ab
    # Härtung der Prüfansicht
    assert 'if (b.closest(".mat-anleitung")) return;' in js
    pr = js[js.index("  async function pruefungAnsicht() {"):js.index("  async function durchgangAnsicht() {")]
    for sel in ('$("#pr-grund")', '$("#pr-due")', '$("#pr-bem")', '$("#pr-abschluss")', '$$("#pr-abschluss'):
        assert sel not in pr, sel
    assert 'grund = ergebnis === "einsatzbereit" ? "" : imAbschluss("#pr-grund").value.trim()' in pr
    # Seit C2 (P4-L1) ist „Nächste Prüfung“ ein Textfeld TT.MM.JJJJ: datumWert mit Toast und Abbruch statt stillem „|| null“.
    assert "bemerkung: bemFeld().value" in pr and "daten.next_due_on = due;" in pr
    assert 'due = datumWert(imAbschluss("#pr-due"), "Nächste Prüfung") || null;' in pr and 'imAbschluss("#pr-due").value || null' not in pr
    assert "anleitungEinsetzen();" in pr and '${pr.anleitung ? \'<div class="mat-anleitung-platz"></div>\' : ""}' in pr
    # Formularzeile und Seitenwahl
    assert 'f.wiki_aendern ? \'<button type="button" class="lnk" data-act="wiki-waehlen">Ändern</button>\'' in js
    assert "Verknüpfen kann, wer in der Strömipedia mindestens Mitglied ist." in js and "Seite Nr. ${esc(w.seite)} – du darfst sie nicht lesen" in js
    ww = js[js.index("  function wikiWahl(formular, danach) {"):js.index("/* --- Suche ---")]
    assert ww.count('class="btn"') == 1 and "Verknüpfung entfernen" in ww and "setTimeout(suchen, 300)" in ww
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_seitenwahl()
    test_setzen()
    test_vererbung_und_katalog()
    test_anleitung_und_rechte()
    test_kein_nachweis()
    test_oberflaeche_statisch()
    print("Alle Tests zur Prüfanleitung aus dem Wiki bestanden.")
