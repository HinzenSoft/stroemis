"""Hersteller-Sets, Oberfläche (Phase 4 · Lieferung 2, Pakete O1 und O2):  python tests/test_material_sets_oberflaeche.py

Statisch: material.js, suche.js, global.js und material.css – O1 für den Stand K1: Produkt-Dialog mit „Hersteller-Set“
und Reiter „Bestandteile“ (Werte und Grenzen gleich wie auf dem Server), Produktseite mit Stückliste, Artikel anlegen mit
Teilblöcken, Set-Seite und Teil-Seite (keine Knöpfe, die am Teil 409 gäben), Listen mit Set-Zeile und Kopf, Meine PSA
mit Teilen, Steckbrief, Importbericht und Export-Vorschau. O2 für den Stand K2: Seite „Set prüfen“, Prüfansicht im Lauf
(Teil n von m, Gesamtergebnis vorab, „vorhanden/fehlt“, Wahl je Teil bei „aussondern“), Teil tauschen, entnehmen und
einsetzen, Set aussondern, Teil löschen, Durchgang mit Set-Gruppierung, Mangel melden mit Teil-Wahl, Werte im Journal.
Knopfsprache und Container-Abfragen.
Dazu Vertragstests: Die Schlüssel, die die Oberfläche liest, stehen in den Antworten des Servers (K1 und K2), und die
kleinen Server-Ergänzungen aus O2 (Seite „Set prüfen“, Teil-Dublette mit Präfix, Zahlen der Statusfilter je Set-Zeile,
Listen aus Objekten im Lebenslauf-PDF, lock_cause, teile_anzahl).

Alle Hersteller, Modelle und Nummern hier sind erfunden und nur für den Test da."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, neues_konto  # noqa: E402
from test_material_import import ok  # noqa: E402
from test_material_sets import set_aufbau, teile_fuer  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(rel):
    return open(os.path.join(WURZEL, rel), encoding="utf-8").read()


def funktion(js, name):
    """Der Quelltext einer Funktion (bis zur schließenden Klammer auf Einrückungstiefe 2)."""
    anfang = js.index(f"function {name}(")
    ende = js.index("\n  }\n", anfang)
    return js[anfang:ende]


def test_werte_wie_server():
    """AUSTAUSCH, HILFE_EINZELN und die Grenzen der Stückliste in material.js gleich wie in models.py und
    stueckliste.py – die Produktantwort trägt den Hilfetext nicht, ein neues Produkt keine Grenzen."""
    from app.material import models
    from app.material.services import stueckliste
    js = lies("app/material/static/material.js")
    block = js[js.index("const AUSTAUSCH = {"):]
    block = block[:block.index("}")]
    assert dict(re.findall(r'([a-z_]+): "([^"]*)"', block)) == models.AUSTAUSCH
    hilfe = re.search(r'const HILFE_EINZELN = "([^"]*)";', js).group(1)
    assert hilfe == stueckliste.HILFE_EINZELN
    grenzen = re.search(r"const STUECK_GRENZEN = \{ positionen: (\d+), anzahl: (\d+), teile: (\d+), bezeichnung: (\d+) \};", js)
    assert tuple(int(x) for x in grenzen.groups()) == (models.STUECKLISTE_POSITIONEN_MAX, models.BESTANDTEIL_ANZAHL_MAX,
                                                         models.SET_TEILE_MAX, models.BEZEICHNUNG_MAX)
    # O2: Werte im Journal, Gruppe der Bestandteil-Zeilen, Felder eines neuen Teils, Wahl je Teil.
    from app.material.services import beschriftung, sets, setlauf
    block = js[js.index("const SET_WERTE = {"):]
    block = block[:block.index("\n  };")]
    werte = {feld: dict(re.findall(r'([a-z_]+): "([^"]*)"', innen))
             for feld, innen in re.findall(r"\n    ([a-z_]+): \{([^}]*)\}", block)}
    assert werte == beschriftung.SET_WERTE, werte
    assert re.search(r'const SET_GRUPPE = "([^"]*)";', js).group(1) == setlauf.SET_GRUPPE
    felder = re.search(r"const TEIL_FELDER = \[([^\]]*)\];", js).group(1)
    assert tuple(re.findall(r'"([a-z_]+)"', felder)) == sets.TEIL_FELDER
    block = js[js.index("const VERBLEIB = {"):]
    assert dict(re.findall(r'([a-z_]+): "([^"]*)"', block[:block.index("}")])) == sets.VERBLEIB
    print("Werte wie auf dem Server bestanden.")


def test_oberflaeche_statisch():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    such, glob = lies("app/material/static/suche.js"), lies("app/material/static/global.js")
    # Katalog: Häkchen, Reiter, Speichern der Stückliste als Ganzes, Variante mit „Stückliste übernehmen“.
    dlg = funktion(js, "produktDialog")
    for haken in ('id="pd-set"', "set_umschalt_grund", 'role="tablist"', 'data-reiter="bestandteile"',
                  "/bestandteile`, { method: \"PUT\"", "stueckliste: !!(", "daten.is_set = alsSet", "confirm("):
        assert haken in dlg, haken
    # Häkchen nur senden, wenn es sich umschalten lässt; keine Set-Steuerung aus Meldung oder Nacharbeit.
    assert "if (setFeld && !setFeld.disabled)" in dlg and "const mitSet = !p.variante_von && !p.meldung && !opt.danach;" in dlg
    ed = funktion(js, "stuecklisteEditor")
    for haken in ("HILFE_EINZELN", "produktTreffer(", "prod.is_set", "AUSTAUSCH", "Position (\\d+)", 'data-bt="hoch"',
                  '<span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Bestandteil<span class="k-anlegen"> anlegen</span></span>'):
        assert haken in ed, haken
    assert 'class="btn"' not in ed and "btn ghost" not in ed and "btn danger" not in ed
    assert "stuecklisteHtml(p, k)" in js and "bestandteil_von" in js and 'data-act="stueckliste"' in js
    # Importbericht und Export-Vorschau.
    assert "b.stuecklisten" in js and "v.set_verstoesse" in js
    # Artikel anlegen: Teilblöcke aus dem Vorschlag, Hinweise der Antwort, Fehler am Feld.
    for haken in ("v.set && teileFuer !== produkt.id", "teil_felder", "daten.teile = teileDaten()", "r.hinweise",
                  "teileServerFehler(e.message)", 'setAttribute("aria-invalid", "true")', "STR-Nummer"):
        assert haken in js, haken
    # Set-Seite und Teil-Seite: am Teil kein Verschieben, Zuordnen, Aussondern – stattdessen der Hinweis aufs Set.
    for haken in ("${frei && !tv ? '<button class=\"btn secondary small\" data-act=\"verschieben\">", "${tv ? \"\" : zuKnoepfe}",
                  "&& !a.entwurf && !tv;", "mat-teil-hinweis", "Teil von Set", "setKasten(sb, a)", "setBanner(sb, a)",
                  "rueckrufe_teile", "sb.vollstaendig", "faellig_durch", "lebensende_durch"):
        assert haken in js, haken
    kasten = funktion(js, "setKasten")
    assert "esc(" in kasten and "btn danger" not in kasten and 'class="btn"' not in kasten
    # Listen: Set-Zeile und Kopf in Ordner und Fälligen, Teil mit Set in der Suche.
    assert "setKopf(d.artikel_gesamt, d.sets)" in js and "setKopf(d.gesamt, d.sets)" in js
    assert "a.teil_von" in js and "a.set.mangel_teile" in js and "a.set.rueckruf_teile" in js
    assert "a.teil_von" in such and "a.set" in such
    assert "t.teil_eines_sets" in glob
    # Meine PSA: Teile in der Set-Karte, Einzelansicht eines Teils zeigt sein Set.
    assert "psaTeil(t, banner[0])" in js and "(k.teile || []).some((t) => t.id === DATEN.id)" in js
    # Journal: Listen aus Objekten (Teile, Positionen) lesbar.
    assert "listenWert(x)" in js
    # Knopfsprache: kein btn ghost; CSS mit Container-Abfrage und Touch-Regeln unter pointer: coarse.
    assert "btn ghost" not in js
    teil = css[css.index("/* Phase 4 – Lieferung 2: Hersteller-Sets (Oberfläche O1) */"):]
    assert "@container mat-seite" in teil and "@media (pointer: coarse)" in teil
    assert "min-height: 44px" in teil[teil.index("@media (pointer: coarse)"):]
    print("Oberfläche (statisch) bestanden.")


def test_vertrag_mit_dem_server():
    """Was die Oberfläche liest, liefert der Server (Stand K1): Produkt, Vorschlag, Set- und Teil-Seite, Listen mit
    Kopf, Suche, Meine PSA."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, mv = t.wart_a, t.k["katalog"]
        p = ok(mv.get(f"/api/material/produkte/{t.set_p}"))["produkt"]
        assert {"is_set", "bestandteile", "bestandteil_von", "set_umschaltbar", "set_umschalt_grund",
                "stueckliste_grenzen"} <= set(p)
        assert set(p["stueckliste_grenzen"]) == {"positionen", "anzahl", "teile", "bezeichnung"}
        assert {"id", "bezeichnung", "anzahl", "einzeln", "austausch", "austausch_text", "produkt"} <= set(p["bestandteile"][0])
        h = ok(mv.get(f"/api/material/produkte/{t.ids['hms']}"))["produkt"]
        assert h["bestandteil_von"] and {"id", "name"} == set(h["bestandteil_von"][0])
        assert "is_set" in ok(mv.get("/api/material/produkte?q=Testset"))["produkte"][0]
        v = ok(w.get(f"/api/material/artikel/vorschlag?product_id={t.set_p}&folder_id={t.lager_a}"))["vorschlag"]
        assert {"bestandteile", "teil_felder"} <= set(v["set"])
        assert {"laenge_moeglich", "material_kind", "demo", "id"} <= set(v["set"]["bestandteile"][0]["produkt"])
        a = ok(w.get(f"/api/material/artikel/{t.s['id']}"))["artikel"]
        sb = a["set"]
        assert {"status", "next_due_on", "faellig_durch", "retire_by", "lebensende_durch", "eigen", "teile", "teile_anzahl",
                "bestandteile", "vollstaendig", "fehlend", "rueckrufe_teile"} <= set(sb)
        assert {"id", "inventory_no", "serial_no", "serial_generated", "produkt", "bestandteil", "status", "next_due_on",
                "retire_by", "lock_state", "lock_reason", "mangel", "rueckruf"} <= set(sb["teile"][0])
        assert {"name", "manufacturer", "model", "description", "article_no"} <= set(sb["teile"][0]["produkt"])
        assert {"vorhanden", "fehlt"} <= set(next(b for b in sb["bestandteile"] if b["einzeln"]))
        tv = ok(w.get(f"/api/material/artikel/{t.teile[0]}"))["artikel"]["teil_von"]
        assert {"id", "inventory_no", "produkt", "status", "bestandteil"} <= set(tv)
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        assert o["sets"] == {"anzahl": 1, "teile": 3} and "artikel_gesamt" in o
        zeile = next(x for x in o["artikel"] if x["id"] == t.s["id"])
        assert {"teile", "vollstaendig", "mangel_teile", "rueckruf_teile", "faellig_durch"} <= set(zeile["set"])
        f = ok(w.get(f"/api/material/faellig?ordner={t.lager_a}&status=neu"))
        assert f["sets"]["anzahl"] == 1 and "gesamt" in f
        s = ok(w.get("/api/material/suche?q=SET-A-K1"))["treffer"]
        assert s and {"id", "inventory_no", "produkt"} == set(s[0]["teil_von"])
        person, person_id = neues_konto(t.app, "psa_o1@example.org", name="PSA O1", stufe=0)
        ok(w.put(f"/api/material/artikel/{t.s['id']}/zuordnung", json={"user_id": person_id}))
        k = ok(person.get("/api/material/meine-psa"))["artikel"][0]
        assert len(k["teile"]) == 3 and {"artikel_link", "rueckruf", "produkt"} <= set(k["teile"][0])
    print("Vertrag mit dem Server bestanden.")



def test_oberflaeche_o2_statisch():
    """O2 (Stand K2): die Haken der neuen Wege und die Knopfsprache – je Ansicht und Dialog höchstens ein roter Knopf,
    „btn danger“ nur zum Bestätigen endgültiger Aktionen, kein „btn ghost“, seltenes im Untermenü."""
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    # Seite „Set prüfen“: Lesen, Eröffnen (mit Durchgang), Abbrechen mit Rückfrage, Umfang je Teil, Fortschritt,
    # „auch prüfen“, die nächste Prüfung als einziger roter Knopf, frühere Set-Prüfungen.
    lauf = funktion(js, "setLaufAnsicht")
    for haken in ("/set-lauf${q}", "/set-lauf`, { method: \"POST\", body: { durchgang_id: DATEN.durchgang || null } }",
                  "/set-lauf`, { method: \"DELETE\" }", "confirm(text, \"Set-Prüfung abbrechen\")", "lf.umfang.map(karte)",
                  "Teil ${i + 1} von ${lf.umfang.length}", "auch prüfen", "u.uebernommen", "lf.hinweis_tage",
                  "lf.freigabe_gruende", "lf.bereit", "lf.abschluss", "laufWeiter(lf, a.id)", "?lauf=${x.id}",
                  "details class=\"mat-menue\"", "reservierungFreigeben("):
        assert haken in lauf, haken
    assert lauf.count('class="btn"') == 1 and "btn danger" not in lauf and "btn ghost" not in lauf
    assert "set_lauf: setLaufAnsicht" in js and 'set_lauf: "pruefungen"' in js
    # Prüfung starten: Set-Artikel nur über „Set prüfen“, Teil n von m, zurück in die Set-Prüfung.
    neu = funktion(js, "pruefungNeu")
    for haken in ("/set-pruefung", "teilNr(lf, a.id)", "Teil ${nr.n} von ${nr.m}", "href=\"${zurueck}\">Abbrechen",
                  'a.lock_cause === "set"'):
        assert haken in neu, haken
    # Prüfansicht im Lauf: Kopf, Weg zur nächsten Prüfung, Stand und Gesamtergebnis vorab, „vorhanden/fehlt“,
    # Wahl je Teil bei „aussondern“, Teiletabelle.
    for haken in ("${setKopfHtml()}${setWeiterHtml()}", "${setAbschlussHtml()}", "${setProtokollHtml()}",
                  "x.gruppe === SET_GRUPPE ? { ja: \"vorhanden\", nein: \"fehlt\" }", "setVorab(daten.ergebnis)",
                  "pr.set_abschluss.verbleib_vorschlag.map(", "daten.verbleib = verbleibLesen(body)",
                  "await setLaufLaden();", "pr.set_protokoll ? ` – Set: ${pr.set_protokoll.gesamt_text}`"):
        assert haken in js, haken
    # Teil tauschen, entnehmen, einsetzen: ein Dialog, Felder wie beim Anlegen, Bestätigung, Hinweise als Dialog.
    td = funktion(js, "teilDialog")
    for haken in ("/teil-${art}`", "teilBlockHtml(pos, 0, \"td\", new Set(TEIL_FELDER)", "teilBlockDaten(", "daten.bestaetigt",
                  'pos.austausch === "nicht_belegt"', "eigeneUnterschrift(HINWEIS)", 'ok.classList.toggle("danger", aus)',
                  "r.hinweise", 't.verbleib_vorschlag === "aussondern"'):
        assert haken in td, haken
    assert td.count('class="btn"') == 2 and "btn ghost" not in td      # Hauptknopf und „OK“ im Hinweis-Dialog
    assert "teilBlockHtml(z, k, `at-${n}`, felder)" in js
    kasten = funktion(js, "setKasten")
    for haken in ('data-act="teil-tauschen"', 'data-act="teil-entnehmen"', 'data-act="teil-einsetzen"', "mat-menue",
                  't.austausch === "nein"', 'z.austausch === "nein"', "sb.sperrgruende", "sb.letzte_pruefung",
                  "berichtigte_teile", "sb.lauf", "pflege"):
        assert haken in kasten, haken
    # Set-Seite: „Set prüfen“ statt „Prüfung starten“ (rot nur fällig/gesperrt), Sperren auch mitgesperrt, Set aussondern
    # nur mit eigenem Grund, Teil löschen nennt die Sperre, Sperren und Mangel melden wirken über das Set.
    knopf = funktion(js, "setPruefKnopf")
    assert "SET_ROT.includes(sb.status)" in knopf and '" secondary"' in knopf
    for haken in ("${sb ? setPruefKnopf(a, sb)", '(frei || a.lock_cause === "set") && darf.pruefen', "SET_OHNE_GRUND",
                  "ist danach unvollständig und gesperrt", "{ set: setVerbund(a) }", "setSperrSatz(v)"):
        assert haken in js, haken
    aus = funktion(js, "aussonderDialog")
    assert "if (sb) daten.verbleib = verbleibLesen(body);" in aus and "verbleibWahl(" in aus
    # Durchgang: Teile unter der Set-Zeile, „Set prüfen“ mit durchgang_id, Zeile mit set_lauf.
    for haken in ("gruppiert(sortiert(", "/set-pruefung?durchgang=${d.id}", "mat-teilzeile", "a.set_lauf.round_id === d.id"):
        assert haken in js, haken
    # Meine PSA: Mangel melden an der Set-Karte mit Wahl des Artikels.
    md = funktion(js, "mangelDialog")
    assert 'name="mg-wahl"' in md and "gewaehlt ? gewaehlt.value : a.id" in md
    assert "mangelDialog(k, (r, q) => { quittung = q; return zeigen(meinePsa); }, opt)" in js
    # Werte und Journal, Rückruf mit Set.
    assert "SET_WERTE[feld][v]" in funktion(js, "wert") and "x.set_inventar" in funktion(js, "rueckrufKarte")
    assert "btn ghost" not in js
    teil = css[css.index("/* Phase 4 – Lieferung 2: Hersteller-Sets (Oberfläche O2) */"):]
    assert "@container mat-seite" in teil and "@media (pointer: coarse)" in teil
    assert "min-height: 44px" in teil[teil.index("@media (pointer: coarse)"):]
    print("Oberfläche O2 (statisch) bestanden.")


def test_vertrag_k2():
    """Was O2 liest, liefert der Server (Stand K2): Set-Block mit Sperrgründen, Lauf und letzter Set-Prüfung, je Teil
    Position, Austausch, Prüfpflicht und Vorbelegung; Set-Lauf voll und kurz; Prüfung im Lauf (Rolle, Stand des Laufs am
    Entwurf des Set-Artikels, Teiletabelle); Tauschen mit Hinweisen; Abbrechen; Durchgangszeilen; Rückruf; Meine PSA."""
    from test_material import starten
    from test_material_sets_pruefung import lauf_auf, pruefen
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, p = t.wart_a, t.k["pruefer"]
        s, k1, k2, r1 = t.s["id"], *t.teile
        sb = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        assert {"sperrgruende", "lauf", "letzte_pruefung", "ursprung"} <= set(sb)
        assert {"slot_id", "austausch", "set_pruefen", "verbleib_vorschlag", "lock_cause", "lock_reason"} <= set(sb["teile"][0])
        assert {"id", "austausch", "produkt"} <= set(sb["bestandteile"][0])
        assert "laenge_moeglich" in sb["bestandteile"][0]["produkt"]
        # Lauf eröffnen und lesen.
        lauf_kurz = {"id", "state", "round_id", "durchgang", "opened_at", "opened_by_name", "closed_at", "set_inspection_id"}
        lf = lauf_auf(p, s)
        assert lauf_kurz | {"umfang", "set_pruefung", "fortschritt", "bereit", "freigabe_gruende", "hinweis_tage",
                            "abschluss"} <= set(lf)
        u = lf["umfang"][0]
        assert {"teil", "zu_pruefen", "pruefung", "entwurf", "uebernommen"} <= set(u)
        assert {"id", "inventory_no", "serial_no", "bestandteil"} <= set(u["teil"])
        assert {"geprueft", "zu_pruefen", "teile"} <= set(lf["fortschritt"])
        g = ok(p.get(f"/api/material/artikel/{s}/set-lauf"))
        assert g["lauf"]["id"] == lf["id"] and lauf_kurz <= set(g["laeufe"][0])
        assert ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]["lauf"]["id"] == lf["id"]
        # Teilprüfung im Lauf: Rolle „teil“ mit dem Set; Entwurf im Umfang.
        e = ok(starten(p, k1), 201)["pruefung"]
        assert e["set_lauf"]["rolle"] == "teil" and {"id", "inventory_no"} == set(e["set_lauf"]["set"])
        assert {"lock_state", "teil_von"} <= set(e["artikel"]) and e["artikel"]["teil_von"]["id"] == s
        u = ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]["umfang"][0]
        assert {"id", "pruefer", "eigen"} == set(u["entwurf"]) and u["entwurf"]["eigen"] is True
        ok(p.delete(f"/api/material/pruefungen/{e['id']}", headers=H))
        for x in t.teile:
            pruefen(p, x)
        u = ok(p.get(f"/api/material/artikel/{s}/set-lauf"))["lauf"]["umfang"][0]
        assert {"id", "ergebnis", "ergebnis_text", "datum", "pruefer", "protokoll_id"} <= set(u["pruefung"])
        # Entwurf des Set-Artikels: Stand des Laufs, Vorbelegung, Bestandteil-Zeilen in ihrer Gruppe.
        e = ok(starten(p, s), 201)["pruefung"]
        assert e["set_lauf"]["rolle"] == "set"
        sa = e["set_abschluss"]
        assert {"umfang", "fortschritt", "bereit", "freigabe_gruende", "verbleib_vorschlag"} <= set(sa) and sa["bereit"]
        assert {"teil_id", "inventory_no", "verbleib"} == set(sa["verbleib_vorschlag"][0])
        from app.material.services import setlauf
        assert any(x["gruppe"] == setlauf.SET_GRUPPE and x["art"] == "yesno" for x in e["punkte"])
        pr = pruefen(p, s)
        sp = pr["set_protokoll"]
        assert {"zeilen", "gesamt", "gesamt_text", "freigegeben", "gruende", "hinweis", "berichtigung"} <= set(sp)
        assert {"art", "bezeichnung", "inventarnummer", "seriennummer", "ergebnis", "protokoll_id", "pruefsumme",
                "vorhanden", "vorhanden_text", "uebernommen"} <= set(sp["zeilen"][0])
        sb = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        assert {"pruefung_id", "protokoll_id", "datum", "gesamt_text", "berichtigt_durch", "berichtigte_teile"} <= set(
            sb["letzte_pruefung"])
        ab = ok(p.get(f"/api/material/artikel/{s}/set-lauf?lauf={lf['id']}"))["lauf"]["abschluss"]
        assert {"gesamtergebnis", "gesamt_text", "freigegeben", "gruende", "hinweis"} <= set(ab)
        # Sperre am Teil: Sperrgründe am Set, lock_cause am mitgesperrten Teil.
        ok(p.post(f"/api/material/artikel/{k1}/sperren", json={"grund": "sturz", "text": "Teststurz"}))
        sb = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        g = sb["sperrgruende"][0]
        assert {"art", "artikel", "text"} == set(g) and {"id", "inventory_no", "set_artikel"} == set(g["artikel"])
        assert ok(w.get(f"/api/material/artikel/{k2}"))["artikel"]["lock_cause"] == "set"
        # Tauschen (Austausch „ja“) mit Hinweis (STR-Nummer), Abbrechen eines Laufs.
        r = ok(w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": r1, "serial_no": ""}), 201)
        assert {"artikel", "teil", "hinweise"} <= set(r) and r["hinweise"][0].startswith("STR-Nummer am Teil anbringen")
        lauf_auf(p, s)
        assert ok(p.delete(f"/api/material/artikel/{s}/set-lauf", headers=H))["bleibt"] is False
        # Durchgang: Set-Zeile mit set_lauf, Teile mit teil_von.
        d = ok(w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang O2"}), 201)
        z = {a["id"]: a for a in ok(w.get(f"/api/material/durchgaenge/{d['durchgang']['id']}"))["durchgang"]["artikel"]}
        assert z[s]["ist_set"] is True and "set_lauf" in z[s] and z[k2]["teil_von"]["id"] == s
        # Rückruf: betroffene Teile nennen ihr Set.
        rr = ok(t.k["katalog"].post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe",
                                    json={"title": "Testrückruf", "mail": False}), 201)
        liste = ok(w.get(f"/api/material/produkte/{t.ids['hms']}/rueckrufe"))["rueckrufe"]
        artikel = next(x for x in liste if x["id"] == rr["rueckruf"]["id"])["artikel"]
        assert {x["set_inventar"] for x in artikel if x["id"] == k2} == {t.s["inventory_no"]}
        # Meine PSA: je Teil die eigenen Meldungen (Wahl im Dialog).
        person, person_id = neues_konto(t.app, "psa_o2@example.org", name="PSA O2", stufe=0)
        ok(w.put(f"/api/material/artikel/{s}/zuordnung", json={"user_id": person_id}))
        k = ok(person.get("/api/material/meine-psa"))["artikel"][0]
        assert "eigene_maengel" in k and all("eigene_maengel" in x for x in k["teile"])
    print("Vertrag mit dem Server (K2) bestanden.")


def test_server_ergaenzungen_o2():
    """Die kleinen Server-Ergänzungen aus O2: Seite „Set prüfen“ (sehen genügt, fremd 404), eine abgelehnte Seriennummer
    eines Teils nennt das Teil (sichtbare und fremde Dublette – die fremde bleibt protokolliert), die Zahlen an den
    Statusfiltern der Ordnerliste zählen je Set-Zeile mit Set-Status, das Lebenslauf-PDF schreibt Listen aus Objekten
    lesbar, lock_cause am Artikel und teile_anzahl am Teil."""
    from test_material_sets import set_neu
    from test_material_trennung import zeilen
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, s = t.wart_a, t.s["id"]
        r = w.get(f"/material/artikel/{s}/set-pruefung?durchgang=7")
        assert r.status_code == 200 and b'data-ansicht="set_lauf"' in r.data and b"durchgang&#34;: 7" in r.data, r.data[-600:]
        assert t.wart_b.get(f"/material/artikel/{s}/set-pruefung").status_code == 404
        # Dublette eines Teils beim Anlegen: sichtbar (mit Inventarnummer) und fremd (ohne, protokolliert).
        for serien, text in ((("SET-A-K1", "X-2", "X-3"), "(Inventarnummer "), (("SET-B-K1", "X-2", "X-3"), "in einem Bereich")):
            r = w.post("/api/material/artikel", json={"product_id": t.set_p, "folder_id": t.lager_a, "serial_no": "SET-A-9",
                                                      "manufactured_on": f"{_heute().year - 1}-03",
                                                      "teile": teile_fuer(t.liste, serien)})
            # Position, Stück und Seriennummer – die Oberfläche markiert genau dieses Feld (Nachbesserung, Browser B2).
            assert r.status_code == 409 and r.json["error"].startswith(
                f"Teil „Verbindungselement“ 1 von 2 (Seriennummer „{serien[0]}“): Diese Seriennummer gibt es"), r.get_json()
            assert text in r.json["error"], r.get_json()
        assert zeilen(t.app, "SELECT art FROM mat_global_search ORDER BY id DESC LIMIT 1")[0]["art"] == "dublette"
        r = w.post(f"/api/material/artikel/{s}/teil-tauschen", json={"teil_id": t.teile[2], "serial_no": "SET-B-R1"})
        assert r.status_code == 409 and r.json["error"].startswith("Neues Teil „") and "in einem Bereich" in r.json["error"], r.get_json()
        # Statusfilter: Set S (3 Teile) und F sind neu – zwei Zeilen, nicht fünf Artikel.
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        assert o["direkt"]["neu"] == len([a for a in o["artikel"] if a["status"] == "neu"]), (o["direkt"], o["artikel"])
        assert sum(o["direkt"].values()) == o["artikel_gesamt"]
        assert ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["lock_cause"] is None
        assert ok(w.get(f"/api/material/artikel/{t.teile[0]}"))["artikel"]["teil_von"]["teile_anzahl"] == 3
        set_neu(w, t.set_p, t.lager_a, t.liste, "SET-A-2", ("SET-A2-K1", "SET-A2-K2", "SET-A2-R1"))
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        assert sum(o["direkt"].values()) == o["artikel_gesamt"]
        # Lebenslauf: Listen aus Objekten als Satz, Werte der Sets mit ihren Wörtern.
        with t.app.app_context():
            from app.material.services import beschriftung
            text = beschriftung.wert_text([{"inventory_no": "M-1", "serial_no": "SN-1", "bestandteil": "Rolle"}], "teile")
            assert text == "M-1 (SN SN-1) – Rolle", text
            text = beschriftung.wert_text([{"bezeichnung": "Tasche", "anzahl": 2, "einzeln": False, "austausch": "nicht_belegt"}],
                                          "bestandteile")
            assert text == "2 × Tasche, Austausch: nicht belegt", text
            assert beschriftung.wert_text(["a", "b"], "gruende") == "a, b"
            assert beschriftung.wert_text("weiterfuehren", "verbleib") == "entnommen und weitergeführt"
    print("Server-Ergänzungen O2 bestanden.")


if __name__ == "__main__":
    test_werte_wie_server()
    test_oberflaeche_statisch()
    test_vertrag_mit_dem_server()
    test_oberflaeche_o2_statisch()
    test_vertrag_k2()
    test_server_ergaenzungen_o2()
