"""Sets, Oberfläche (Phase 4 · Lieferung 2, Pakete O1 und O2):  python tests/test_material_sets_oberflaeche.py

Statisch: material.js, suche.js, global.js und material.css – O1 für den Stand K1: Produkt-Dialog mit „Set“
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
    # Sets anlegen (24.10.2026): Pflichttext und Ordnerart „Set-Ordner“ wie auf dem Server.
    assert re.search(r'const EINZELN_PFLICHT = "([^"]*)";', js).group(1) == stueckliste.EINZELN_PFLICHT
    block = js[js.index("const ORDNERART = {"):]
    assert dict(re.findall(r'([a-z_]+): "([^"]*)"', block[:block.index("}")])) == models.ORDNERARTEN
    print("Werte wie auf dem Server bestanden.")


def test_oberflaeche_statisch():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    such, glob = lies("app/material/static/suche.js"), lies("app/material/static/global.js")
    # Katalog (seit „Set anlegen“, 24.10.2026): Set-Modus ohne Häkchen – Reiter immer, neu in EINER Anfrage mit
    # „bestandteile“, Bearbeiten mit PUT …/bestandteile; kein Umschalten, keine „Stückliste übernehmen“.
    dlg = funktion(js, "produktDialog")
    for haken in ('role="tablist"', 'data-reiter="bestandteile"', "/bestandteile`, { method: \"PUT\"",
                  "{ bestandteile: stueck.liste() }", "is_set: true", '"Set anlegen"', '"Set bearbeiten"',
                  '"Set aus Meldung anlegen"', "SET_ERKLAERUNG", "stueck.fehlerZeigen(e.message)", "sets_aelter"):
        assert haken in dlg, haken
    for weg in ('id="pd-set"', "set_umschalt", "pd-stueckliste", "stueckliste: !!(", "daten.is_set = alsSet"):
        assert weg not in dlg, weg
    assert "const istSet = !opt.danach && !!(p.is_set || (p.variante_von && p.variante_von.is_set));" in dlg
    # Knopf „Set anlegen“ im Katalogkopf: grau umrandet, Anlegen-Markup, Set-Modus.
    assert ('<button class="btn secondary" data-act="set-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ '
            '</span>Set<span class="k-anlegen"> anlegen</span></span></button>') in js
    assert '"set-neu": () => produktDialog({ category_id: kategorie, is_set: true })' in js
    # „Stückliste übertragen“: Hinweis und Knopf auf der Produktseite, Dialog mit einer Hauptaktion.
    sl = funktion(js, "stuecklisteHtml")
    assert "p.sets_aelter" in sl and 'data-act="uebertragen">Auf vorhandene Sets übertragen …</button>' in sl
    assert '<button class="btn secondary small" data-act="uebertragen">' in sl
    ue = funktion(js, "uebertragenDialog")
    for haken in ("/stueckliste-uebertragen`", "set_ids:", "stand: v.stand", "esc(x.grund)", "esc(x.wirkung)",
                  "esc(z.bisher)" if "esc(z.bisher)" in ue else "zelle(z.bisher)", "e.status === 409", "aria-live"):
        assert haken in ue, haken
    assert ue.count('class="btn"') == 1 and "btn danger" not in ue and "btn ghost" not in ue
    # Set-Kasten: ein Teil ohne Position nur entnehmen.
    kasten0 = funktion(js, "setKasten")
    assert "!t.slot_id ?" in kasten0 and "uebrigHinweis(t, sb)" in kasten0
    # Nachbesserung 25.10.2026: Gibt es die Position noch (nur weniger Stück), sagt der Hinweis das neutral.
    hw = funktion(js, "uebrigHinweis")
    assert "steht nicht mehr in der Stückliste" in hw and "Anzahl in der Stückliste verringert" in hw
    # Melden (S8): Wahl Produkt | Set, Teile Pflicht, Titel und Auslöser nennen beides; Karte mit Marke und „Set anlegen“.
    md = funktion(js, "meldungDialog")
    for haken in ('name="me-art" value="set"', 'id="me-teile"', 'is_set: "1"', "Fehlendes Produkt oder Set melden",
                  "Sitz- und Brustgurt", "sobald du Artikel davon anlegen kannst"):
        assert haken in md, haken
    assert "Fehlendes Produkt oder Set melden</button>" in js and "Als fehlendes Produkt oder Set melden" in js
    karte = funktion(js, "meldeKarte")
    assert 'm.is_set ? "Set anlegen" : "Produkt anlegen"' in karte and "setMarke(m.is_set)" in karte
    assert "is_set: m.is_set" in js and "Teile des Sets" in funktion(js, "meldeDetails")
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
    teil = css[css.index("/* Phase 4 – Lieferung 2: Sets (Oberfläche O1) */"):]
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
        assert {"is_set", "bestandteile", "bestandteil_von", "sets_aelter", "stueckliste_grenzen"} <= set(p)
        assert "set_umschaltbar" not in p and "set_umschalt_grund" not in p
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
    # Ein roter Knopf: „Set-Prüfung beginnen“ ist seit der Nachbesserung (V5) nur rot, wenn das Set fällig oder gesperrt ist.
    assert lauf.count('class="btn"') + lauf.count('class="btn${rot ? "" : " secondary"}"') == 1
    assert "btn danger" not in lauf and "btn ghost" not in lauf
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
    assert "teilBlockHtml(z, k, `at-${n}`, felder, null, true)" in js      # seit L2b mit „aus dem Bestand wählen“
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
    teil = css[css.index("/* Phase 4 – Lieferung 2: Sets (Oberfläche O2) */"):]
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


def test_oberflaeche_nachbesserung_statisch():
    """Nachbesserung nach der Browser-Prüfung (B1–B8, V1–V17): je Befund der Haken im Quelltext."""
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    teil = css[css.index("/* Phase 4 – Lieferung 2: Nachbesserung nach den drei Prüfungen */"):]
    # B1: hidden gegen .c-tabs { display: flex } abgesichert; seit „Set anlegen“ stehen die Reiter im Set-Modus immer da.
    assert ".c-tabs[hidden], .mat-reiter[hidden] { display: none; }" in teil
    assert '<div class="c-tabs mat-reiter" role="tablist" aria-labelledby="pd-titel">' in js
    # B2: Server-Fehler am einen Feld (Stück und Seriennummer aus sets.teil_wo), aria-invalid über teilFehler, Fokus.
    tsf = js[js.index("function teileServerFehler("):js.index('$("#an-ende").addEventListener')]
    assert "(\\d+) von \\d+" in tsf and "teilFehler(sn, text); amBlock(block, sn);" in tsf      # seit L2b-Nachbesserung V5
    assert 'feld.setAttribute("aria-invalid", "true")' in js
    # B3/V2: ausgesondert ohne Unvollständig-Banner und „fehlt“-Zeilen; unvollständig im einen GESPERRT-Banner.
    banner = funktion(js, "setBanner")
    assert 'if (a.lock_state === "ausgesondert") return "";' in banner and "UNVOLLSTÄNDIG" not in banner
    assert "GESPERRT – Set unvollständig, es fehlt:" in funktion(js, "setGesperrtBanner")
    kasten = funktion(js, "setKasten")
    assert "(aus ? [] : fehlt).map(" in kasten
    # B5: Fokus zurück auf den Menüknopf, wenn ein Untermenü-Eintrag einen Dialog öffnete.
    assert 'const menue = b.closest("details.mat-menue");' in js and 'if (knopf.isConnected) knopf.focus();' in js
    # B6: keine „Nächste Prüfung“ am gesperrten Set.
    assert "setzt die Freiprüfung („Set prüfen“)" in kasten
    # B8: Rot auf Grau dunkel.
    assert "table.list.mat-runde tr.mat-teilzeile strong { color: var(--rot-auf-flaeche); }" in teil
    # V1: Begründung für „Set aussondern“ im Dialog, kein „Prüfen dürfen …“ am Set.
    assert '"aussondern-warum": () => dialog(' in js and "aus || darf.pruefen || sb ?" in js
    assert '${aussonderKnopf && aussonderAus && !sb ?' in js
    # V3: Gesamtergebnis im Kopf der Prüfansicht.
    assert "<strong>Gesamtergebnis des Sets:</strong>" in js
    # V4: Trenner zwischen Marke und Satz; Gründe als ganze Sätze vom Server.
    assert ' – ${esc(v.text.slice(i + 3))}' in js
    # V5: Seite „Set prüfen“.
    lauf = funktion(js, "setLaufAnsicht")
    for haken in ("Regelprüfung (alle Teile)", "x.gesamtergebnis", "x.protokoll_id", 'class="mat-lauf-auftrag', "t.zu_pruefen",
                  "lf.eigen || darf.verwalten"):
        assert haken in lauf, haken
    assert "Periodisch" not in lauf
    # V6/V7: Fällige mit „Set prüfen“ und Marke „Set“.
    assert '/set-pruefung${q}">Set prüfen</a>' in funktion(js, "pruefKnopf")
    assert "return `${setMarke(true)}<div class=\"small mat-set-info\">Set" in js
    # V8/V12: „Entfernen“ als Text, Hilfe aufklappbar.
    st = funktion(js, "stuecklisteEditor")
    assert ">Entfernen</button>" in st and "✕" not in st and 'class="mat-auf mat-bt-hilfe"' in st
    # V9: Produkt-Dialog oben.
    assert "dialog.mat-produkt-reiter { margin-top:" in teil
    # V10: Meine PSA – Genus, Hilfe unter dem Textfeld, Fokus auf die Wahl.
    md = funktion(js, "mangelDialog")
    assert md.index('id="mg-text"') < md.index('id="mg-text-hilfe"') and "fokus($('input[name=\"mg-wahl\"]:checked', body) || text);" in md
    assert "BEISEITE_SET" in md and "Leg das Set beiseite und gib es" in funktion(js, "mangelQuittung")
    # V11: „entnehmen“, nicht „herausnehmen“; „das Set selbst“ statt „Set-Artikel“ in Oberflächentexten.
    assert "erausnehmen" not in js
    for satz in ('"Set-Artikel prüfen"', '>Set-Artikel</span>', '"Set-Artikel (das Set selbst)"'):
        assert satz not in js, satz
    # V13: 44 px am Finger nur unter (pointer: coarse).
    grob = teil[teil.index("@media (pointer: coarse)"):]
    assert ".mat-arten .mat-art-wahl { min-height: 44px" in grob and "a.mat-ziel" in grob
    # V14: ausgegrauter Eintrag fokussierbar.
    assert 'role="menuitem" aria-disabled="true" tabindex="0"' in kasten
    # V15/V16/V17.
    assert ".mat-psa-teil h4 { margin: 0 0 4px; font-size: var(--fs-mittel);" in css
    assert '<span class="mat-nowrap">im Umfang geprüft</span>' in lauf and ".mat-lauf-fortschritt .mat-fortschritt" in teil
    assert "– bitte wählen –" in funktion(js, "aussonderDialog")
    print("Oberfläche Nachbesserung (statisch) bestanden.")


def test_oberflaeche_l2b_statisch():
    """P4-L2b (Sets, Teil 2): „aus dem Bestand wählen“ beim Anlegen und bei „Teil einsetzen“ (nicht beim Tauschen), Set
    auflösen und Löschen mit vorhandenen Teilen, „Bestandteil ersetzt“, Zählsätze und Zusatz an Statuslisten, „Sperren“
    und „Melden und sperren“ als btn, Journal. Knopfsprache: höchstens ein roter Knopf je Dialog, „btn danger“ nur für
    „Set auflösen“ (S.confirm), kein „btn ghost“, keine Erklärtexte unter Knöpfen."""
    from app.material.services import bestand, beschriftung, setaustausch
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    # Teilblock: die Wahl und die Auswahl; das Wort ist „aus dem Bestand wählen“, nicht „übernehmen“ (U15).
    block = funktion(js, "teilBlockHtml")
    for haken in ('value="neu" checked> neu erfassen', 'value="bestand"> aus dem Bestand wählen', "mitBestand ?",
                  "at-bestand-fehler", "esc(BESTAND_HILFE)"):
        assert haken in block, haken
    assert re.search(r'const BESTAND_HILFE = "Lebenslauf und Protokolle gehen mit', js)
    wahl = funktion(js, "bestandWahl")
    for haken in ("q.length < 2", "await api(adresse(q))", "fehlerZeigen(e.message)", "r.weitere", "Weitere Treffer",
                  "belegt(x.id, f)", "WAHL.set(f, x)", "anderen wählen", 'setAttribute("aria-invalid", "true")'):
        assert haken in wahl, haken
    kandidat = funktion(js, "kandidatHtml")
    for feld in ("x.inventory_no", "x.serial_no", "x.bisherige_inventarnummer", "x.produkt", "x.ordner", "x.status",
                 "x.zugeordnet.name"):
        assert f"esc({feld})" in kandidat or f"statusMarke({feld})" in kandidat, feld
    for teil in (block, wahl, kandidat, funktion(js, "zuordnungEndet")):
        assert "übernehm" not in teil.lower()
    assert "{ item_id: x.id }" in funktion(js, "teilBlockDaten")
    # Anlegen: gesucht im Ablageordner, ein Artikel nur für ein Teil, Fehler des Servers am Block, Rückfrage Zuordnung.
    for haken in ("teilBlockHtml(z, k, `at-${n}`, felder, null, true)",
                  '`${API}/ordner/${$("#an-ordner").value}/kandidaten?${new URLSearchParams({ product_id: f.dataset.produkt, q })}`',
                  "ist für zwei Teile gewählt.", "text.includes(f.dataset.inv)", 'rueckfrage("Zuordnung endet", endet, "Anlegen")',
                  "f.bestandZuruecksetzen()"):
        assert haken in js, haken
    # Teil einsetzen mit Auswahl, Tauschen ohne (T9); Rückfrage, wenn die Zuordnung endet (U10).
    td = funktion(js, "teilDialog")
    for haken in ('art === "einsetzen" ? "Teil" : "Neues Teil", art === "einsetzen")',
                  "`${API}/artikel/${a.id}/kandidaten?${new URLSearchParams({ slot_id: z.id, q })}`",
                  "zuordnungEndet([WAHL.get(block)], a.zugeordnet || null)", 'rueckfrage("Zuordnung endet", endet, TEIL_KNOPF[art])',
                  "block.bestandFehler(e.message)"):
        assert haken in td, haken
    rf = funktion(js, "rueckfrage")
    assert '<button class="btn" id="rf-ja" type="button">' in rf and "danger" not in rf and "ghost" not in rf
    # Set auflösen und Löschen mit vorhandenen Teilen.
    for haken in ('data-act="set-aufloesen"><strong>Set auflösen …</strong>', '<details class="mat-menue mat-set-menue">',
                  '"set-aufloesen": () => (sb.aufloesen_hindernis ? dialog(', "esc(sb.aufloesen_hindernis)",
                  'data-act="${a.darf_loeschen ? "loeschen" : "loeschen-verweis"}"><strong>Set löschen …</strong>',
                  "(sb.vorhandene_teile || []).length > 0 && !sb.aufloesen_hindernis",
                  '<button class="btn" id="lv-aufloesen" type="button">Set auflösen …</button>'):
        assert haken in js, haken
    auf = funktion(js, "setAufloesen")
    assert 'confirm(frage, "Set auflösen")' in auf and "/aufloesen`, { method: \"POST\", body: {} }" in auf
    # „Bestandteil ersetzt“: Untermenü „Austausch“ an der Position ohne eigenen Artikel, Dialog mit Grenze, Bestätigung,
    # Lebensende-Hinweis und gesperrtem Knopf während der Anfrage.
    kasten = funktion(js, "setKasten")
    for haken in ('data-act="bestandteil-ersetzt"', 'ausEintrag("Bestandteil ersetzt")', "mat-ohne-zeile", "ohneMenue(z)"):
        assert haken in kasten, haken
    be = funktion(js, "bestandteilDialog")
    assert re.search(r"const ERSETZT_BEMERKUNG_MAX = (\d+);", js).group(1) == str(setaustausch.BEMERKUNG_MAX)
    for haken in ("/bestandteil-ersetzt`", 'maxlength="${ERSETZT_BEMERKUNG_MAX}"', "keine Personennamen",
                  "Ist der Ersatz älter als das Set, das Lebensende am Set vorziehen", 'z.austausch === "nicht_belegt"',
                  "ok.disabled = true;", 'daten.bestaetigt = $("#be-best", body).checked', "pflicht.fehlt()"):
        assert haken in be, haken
    assert be.count('class="btn"') == 1 and "btn danger" not in be and "btn ghost" not in be
    # Zahlen: Zählsatz wie bestand.zaehlsatz, Zusatz unter Statuslisten (Ordner und Fällige).
    assert bestand.zaehlsatz(5, {"anzahl": 1, "teile": 1}) == "5 Artikel, darunter 1 Teil in 1 Set"
    assert bestand.zaehlsatz(7, {"anzahl": 2, "teile": 4}) == "7 Artikel, darunter 4 Teile in 2 Sets"
    assert 'const SETS_SATZ = (s) => `${plural(s.teile, "Teil", "Teile")} in ${plural(s.anzahl, "Set", "Sets")}`;' in js
    assert '`${plural(n, "Artikel", "Artikel")}, darunter ${SETS_SATZ(s)}`' in js
    for haken in ("zaehlSatz(d.bestand, d.bestand_sets)", "zaehlSatz(o.bestand, o.bestand_sets)", "SETS_SATZ(o.bestand_sets)",
                  "SETS_SATZ(d.bestand_sets)", "esc(bst.sets_satz)"):
        assert haken in js, haken
    andere = funktion(js, "andereSetsHtml")
    assert "x.sets_gesamt" in andere and "/material/artikel/${z.id}" in andere and "esc(z.inventory_no)" in andere
    # Knöpfe (F): „Sperren“ und „Melden und sperren“ rot gefüllt, nicht btn danger.
    assert '<button class="btn" id="sd-ok" type="button">Sperren</button>' in js and 'danger" id="sd-ok"' not in js
    assert '<button class="btn" id="mg-ok" type="button">Melden und sperren</button>' in js and 'danger" id="mg-ok"' not in js
    # Journal: vorhandene Teile in Listen lesbar, gleich wie im Lebenslauf-PDF.
    assert '${x.vorhanden ? ", vorhandener Artikel" : ""}' in funktion(js, "listenWert")
    assert beschriftung.wert_text([{"inventory_no": "M-1", "serial_no": "SN-1", "bestandteil": "Rolle", "vorhanden": True}],
                                  "teile") == "M-1 (SN SN-1) – Rolle, vorhandener Artikel"
    assert "btn ghost" not in js
    teil = css[css.index("/* Phase 4 – Lieferung 2b: Sets, Teil 2 (Oberfläche) */"):]
    assert "@container mat-seite" in teil and "@media (pointer: coarse)" in teil
    assert "min-height: 44px" in teil[teil.index("@media (pointer: coarse)"):]
    assert ".mat-journal > li { max-width: 90ch; }" in teil
    assert "mat-set-ohne" not in js and "mat-set-ohne" not in css
    print("Oberfläche L2b (statisch) bestanden.")


def test_vertrag_l2b():
    """Was die Oberfläche von L2b liest, liefert der Server (KERN A und KERN Z): Auswahl (Treffer, weitere, Fehlertext),
    Set-Block (vorhandene_teile, aufloesen_hindernis, Bestandteile ohne eigenen Artikel mit Austausch), Antworten von
    „Teil einsetzen“ mit item_id, „Bestandteil ersetzt“ (Sperrgrund „bestandteil“) und „Set auflösen“; bestand_sets an
    Übersicht, Ordner-Übersicht, Baum und Ordnerkopf; andere_set_status an Ordnerliste mit Status und Fälligen;
    sets_satz im Jahresbericht."""
    from test_material_sets import set_neu
    from test_material_sets_pruefung import eingangsgeprueft
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, s, fid = t.wart_a, t.s["id"], t.lager_a
        hms = t.ids["hms"]
        # Auswahl im Ordner (Anlegen) und am Set (Teil einsetzen).
        r = ok(w.get(f"/api/material/ordner/{fid}/kandidaten", query_string={"product_id": hms, "q": "FREI-A"}))
        assert set(r) == {"treffer", "weitere", "hinweis"} and r["treffer"][0]["id"] == t.f["id"]
        assert {"id", "inventory_no", "serial_no", "bisherige_inventarnummer", "produkt", "ordner", "status",
                "zugeordnet"} <= set(r["treffer"][0])
        r = ok(w.get(f"/api/material/ordner/{fid}/kandidaten", query_string={"product_id": hms, "q": "GIBTESNICHT"}))
        assert r == {"treffer": [], "weitere": False, "hinweis": None}, r                # seit der Nachbesserung (B3)
        sb = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]
        assert sb["vorhandene_teile"] == [] and sb["aufloesen_hindernis"] is None
        ohne = next(b for b in sb["bestandteile"] if not b["einzeln"])
        assert {"id", "bezeichnung", "anzahl", "austausch"} <= set(ohne)
        # Teil entnehmen, dann den freien Artikel F dort einsetzen (vorhandener Artikel) – Antwort wie bisher.
        eingangsgeprueft(t)
        k2 = t.teile[1]
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", headers=H, json={"teil_id": k2}))
        slot = next(b for b in ok(w.get(f"/api/material/artikel/{s}"))["artikel"]["set"]["bestandteile"] if b["einzeln"] and b["fehlt"])
        r = ok(w.get(f"/api/material/artikel/{s}/kandidaten", query_string={"slot_id": slot["id"], "q": "FREI-A"}))
        assert r["treffer"][0]["id"] == t.f["id"]
        r = ok(w.post(f"/api/material/artikel/{s}/teil-einsetzen", headers=H,
                      json={"slot_id": slot["id"], "item_id": t.f["id"], "bestaetigt": True}), 201)
        assert {"artikel", "teil", "hinweise"} <= set(r) and r["teil"]["inventory_no"] == t.f["inventory_no"]
        sb = r["artikel"]["set"]
        assert sb["vorhandene_teile"] == [t.f["inventory_no"]] and isinstance(sb["aufloesen_hindernis"], str)
        assert r["artikel"]["darf_loeschen"] is False
        # „Bestandteil ersetzt“ an einem neuen, freien Set: Sperrgrund „bestandteil“.
        s2 = set_neu(w, t.set_p, fid, t.liste, "SET-A-L2B", ("SET-A-L2B-K1", "SET-A-L2B-K2", "SET-A-L2B-R1"))["artikel"]
        tasche = next(b for b in s2["set"]["bestandteile"] if not b["einzeln"])
        r = ok(w.post(f"/api/material/artikel/{s2['id']}/bestandteil-ersetzt", headers=H,
                      json={"slot_id": tasche["id"], "datum": None, "bemerkung": "Platzhalter", "bestaetigt": True}))
        assert set(r) == {"artikel"} and any(g["art"] == "bestandteil" for g in r["artikel"]["set"]["sperrgruende"])
        assert "Bestandteil ersetzt" in r["artikel"]["lock_reason"]
        # Set auflösen.
        s3 = set_neu(w, t.set_p, fid, t.liste, "SET-A-AUF", ("SET-A-AUF-K1", "SET-A-AUF-K2", "SET-A-AUF-R1"))["artikel"]
        r = ok(w.post(f"/api/material/artikel/{s3['id']}/aufloesen", headers=H, json={}))
        assert r["ok"] is True and len(r["teile"]) == 3 and set(r["teile"][0]) == {"id", "inventory_no"}
        # Zahlen.
        st = ok(w.get("/api/material/start"))
        assert set(st["bestand_sets"]) == {"anzahl", "teile"}
        assert all(set(o["bestand_sets"]) == {"anzahl", "teile"} for o in st["ordner_uebersicht"] if not o.get("nur_pfad"))
        knoten = ok(w.get("/api/material/ordner"))
        knoten = knoten.get("ordner", knoten)
        assert any((o.get("bestand_sets") or {}).get("anzahl") for o in knoten)
        o = ok(w.get(f"/api/material/ordner/{fid}"))["ordner"]
        assert set(o["bestand_sets"]) == {"anzahl", "teile"} and o["andere_set_status"] is None   # Sets jetzt in „Gesperrt“
        o = ok(w.get(f"/api/material/ordner/{fid}", query_string={"status": "einsatzbereit"}))["ordner"]
        assert set(o["andere_set_status"]) == {"teile", "sets", "sets_gesamt"}
        f = ok(w.get("/api/material/faellig", query_string={"status": "einsatzbereit"}))
        a = f["andere_set_status"]
        assert set(a) == {"teile", "sets", "sets_gesamt"} and all(set(x) == {"id", "inventory_no", "teile", "status", "status_text"} for x in a["sets"])
        b = ok(w.get(f"/api/material/ordner/{fid}/bericht"))["bericht"]
        assert "sets_satz" in b["bestand"] and "sets" in b["bestand"]
    print("Vertrag mit dem Server (L2b) bestanden.")


def test_oberflaeche_l2b_nachbesserung_statisch():
    """P4-L2b, Nachbesserung nach den drei Prüfungen: je Befund der Haken im Quelltext (B3, B4, V1–V13, V15–V17)."""
    from app.material.services import bestandsimport, setaustausch
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    # B3: kein Treffer ist eine normale Antwort; „hinweis“ mit Link (V12); Text gleich dem Dienst.
    wahl = funktion(js, "bestandWahl")
    assert "if (!liste.length)" in wahl and "r.hinweis ? r.hinweis.text : KEIN_KANDIDAT" in wahl
    assert 'target="_blank" rel="noopener">${esc(artikel.inventory_no)} öffnen</a>' in wahl
    assert f'const KEIN_KANDIDAT = "{setaustausch.KEIN_KANDIDAT}";' in js
    assert "Produkt am Artikel korrigieren" not in setaustausch.ANDERES_PRODUKT
    # B3/V17: Datumsfelder mit Grenzen, Fehler am Feld.
    assert 'data-max="${esc(grenzen.max)}"' in js and "feld.dataset.max && iso > feld.dataset.max" in funktion(js, "datumWert")
    be = funktion(js, "bestandteilDialog")
    for haken in ('datumFeld("be-datum", tag, "tag", { min: ab, max: tag })', 'id="be-datum-fehler"', "amDatum(e.message)",
                  'feld.setAttribute("aria-invalid", "true")'):
        assert haken in be, haken
    # B4: „Schließen“ in den reinen Hinweis-Dialogen grau.
    assert '"btn" data-close type="button">Schließen' not in js
    assert js.count('<button class="btn secondary" data-close type="button">Schließen</button>') >= 2
    # V1: Hinweiskasten mit Set-Status und Liste.
    andere = funktion(js, "andereSetsHtml")
    for haken in ('class="notice small mat-andere-sets"', "statusMarke(z.status)", "steht in der Liste „${esc(z.status_text)}“",
                  "/material/artikel/${z.id}"):
        assert haken in andere, haken
    assert js.count("andereSetsHtml(d.andere_set_status, filter)") == 2
    # V2: Pflichtbestätigung antippbar (aria-disabled statt disabled), Fokus und Hinweis.
    pb = funktion(js, "pflichtBestaetigung")
    assert 'ok.setAttribute("aria-disabled", "true")' in pb and "best.focus()" in pb and "scrollIntoView" in pb
    assert "if (pflicht.fehlt()) return;" in funktion(js, "teilDialog") and "pflicht.fehlt()" in be
    assert ".btn.mat-aus" in css
    # V3: Quittung nach „Set auflösen“ auf der Zielseite.
    assert "quittungMitnehmen(satz)" in funktion(js, "setAufloesen") and "quittungAbholen();" in js
    assert "${quittungHtml()}<div class=\"mat-pfad\"><a href=\"/material/bestand\">Bestand</a>" in js
    # V4: „Set löschen …“ im Menü „Auflösen / Löschen“, am Set kein eigener Löschknopf mehr.
    assert '${setLoeschen ? "Auflösen / Löschen" : "Auflösen"}</summary>' in js and "a.darf_loeschen && !sb ?" in js
    assert 'data-act="loeschen-verweis">Löschen …</button>' not in js
    # V5: der Absatz über dem Knopf entfällt, wenn der Fehler am Block steht.
    assert "allg.hidden = true; block.scrollIntoView" in js
    # V6/V7: ein Hinweiskasten, kein Lebensende-Link, kein doppelter Gedankenstrich im Banner.
    assert be.count('class="notice small"') == 1 and "be-lebensende" not in be and "(dlg, body) => { $(\"#be-lebensende\"" not in be
    assert "GESPERRT${a.lock_reason ? `: ${esc(a.lock_reason)}`" in funktion(js, "setGesperrtBanner")
    # V8, V9, V10, V15.
    assert '<span class="mat-vorlesen"> Artikel, darunter ${esc(SETS_SATZ(o.bestand_sets))}</span>' in js
    assert ".mat-ue-sets { display: block; font-size: var(--fs-klein); font-weight: 400; color: var(--grau); white-space: nowrap;" in css
    assert "Führst du ein Teil schon im Bestand, wähle es aus dem Bestand." in js and "Führt ihr" not in js
    grob = css[css.index("/* Phase 4 – Lieferung 2b: Sets, Teil 2 (Oberfläche) */"):]
    grob = grob[grob.index("@media (pointer: coarse)"):]
    assert ".mat-an-teil-quelle { flex-wrap: nowrap;" in grob and "min-height: 44px" in grob
    # V13: keine Piktogramme in Knöpfen des Moduls.
    assert "📷" not in js and "📖" not in js
    # V16: kurzer Hinweis an der Set-Zeile der Nacharbeit.
    assert len(bestandsimport.SET_PRODUKT) < 130 and "aus dem Bestand wählen" in bestandsimport.SET_PRODUKT
    print("Oberfläche L2b, Nachbesserung (statisch) bestanden.")


def test_produktsuche_set_und_kategorie_statisch():
    """Produktsuche beim Anlegen (24.10.2026): Set-Marke wie im Katalog, Treffer nach Kategorie mit leisem Trennkopf."""
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    such = funktion(js, "produktTreffer")
    assert "&sort=kategorie&" in such
    assert "${demoMarke(p.demo)}${setMarke(p.is_set)}</button>" in such
    assert 'k !== kategorie ? `<div class="mat-treffer-kat">${esc(k || "ohne Kategorie")}</div>` : ""' in such
    # Der Kopf trägt die Kategorie – die Zeile nicht mehr.
    assert "esc(p.category_name)" not in such
    assert ".mat-treffer-kat { flex: 0 0 auto;" in css and ".mat-treffer-kat:first-child { border-top: 0; }" in css
    print("Produktsuche mit Set-Marke und Kategorie-Köpfen (statisch) bestanden.")

if __name__ == "__main__":
    test_werte_wie_server()
    test_oberflaeche_statisch()
    test_vertrag_mit_dem_server()
    test_oberflaeche_o2_statisch()
    test_vertrag_k2()
    test_server_ergaenzungen_o2()
    test_oberflaeche_nachbesserung_statisch()
    test_oberflaeche_l2b_statisch()
    test_vertrag_l2b()
    test_oberflaeche_l2b_nachbesserung_statisch()
    test_produktsuche_set_und_kategorie_statisch()
