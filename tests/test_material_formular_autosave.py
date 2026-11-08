"""Prüfformular-Editor ohne „Speichern“ – Änderungen werden von selbst übernommen (Wunsch vom 06.11.2026: „Entferne den
Speichern-Knopf, Änderungen sollen automatisch übernommen werden.“; Bauauftrag planung/formular-autosave/auftrag.md):
python tests/test_material_formular_autosave.py  oder  pytest tests/test_material_formular_autosave.py

1. Statisch: kein Knopf „Speichern“, „Gruppe anlegen“ grau, kein neues Rot; Speicherstand als Live-Region; Tippen nach
   einer Sekunde Ruhe, Strukturänderungen sofort, höchstens eine Anfrage; keepalive beim Verlassen; feldFehler ohne
   Fokus; die Übung wartet auf das automatische Speichern statt auf einen Klick.
2. Journal (Dienst, ohne Browser): höchstens ein Eintrag „geändert“ je Version und Bearbeiter in zehn Minuten; ein anderes
   Konto bekommt sofort einen eigenen, der Rest des ersten wird vorher in dessen Namen nachgetragen; nach zehn Minuten
   (Uhr verstellt) nennt der neue Eintrag alles seit dem letzten Stand im Journal; Aktivieren, Deaktivieren, eine neue
   Version und die erste Prüfung tragen den Rest nach – das Journal ergibt dann genau den Stand der Datenbank; eine
   benutzte Version bleibt unveränderlich (409); Zeitstempel ohne Zeitzone stören nicht.
3. Browser bei 1280×900 (Maus) und 360×740 (Touch): Tippen → „Ungespeichert“, danach „Gespeichert HH:MM“ und in der
   Datenbank; Menü, „optional“, Art, Ziehen, Anlegen, Entfernen gehen sofort (ein leerer neuer Punkt erst mit Text); Titel
   leer und Untergruppe ohne Namen am Feld, ohne den Fokus zu nehmen, nichts geht verloren, danach geht es weiter; eine
   Ablehnung des Servers („Prüfpunkt n …“) am Feld des Punkts; Reihenfolge bei schnellen Änderungen (die erste Anfrage
   angehalten: keine zweite gleichzeitig, danach genau der neueste Stand); 10 s ohne Antwort und kein Netz (nur 1280);
   Verlassen der Seite gleich nach dem Tippen (Adresse und Link) speichert noch; mit einem Fehler fragt der Browser vor
   dem Verlassen; „Aktivieren“ wartet auf das Speichern; Journal mit einem Eintrag statt vieler; am Finger 44 px
   (gemessen), kein waagerechter Bildlauf, keine Konsolenfehler außer den erwarteten Ablehnungen.
4. Zusatz vom 08.11.2026 (Browser, beide Größen): „Zuweisen“ ohne aktive Version ausgegraut mit sichtbarem Grund „Erst
   aktivieren – dann zuweisen.“ und grauem „Aktivieren“ daneben – auf der Formularseite (Klick auf „Zuweisen“ öffnet
   nichts, hebt den Grund hervor; „Aktivieren“ gleich nach dem Tippen speichert erst, danach ist „Zuweisen“ frei) und je
   Zeile der Seite „Prüfformulare“ (aktiviert die neueste Version, Datenbank, Fokus auf „Zuweisen“); 44 px am Finger.
Alle Inhalte sind Platzhalter."""
import json
import os
import re
import sys
import tempfile
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROESSEN = ((1280, 900, False), (360, 740, True))
PUNKTE = [{"gruppe": "Gruppe A", "text": "Platzhalter 1", "art": "yesno", "soll": "ja"},
          {"gruppe": "Gruppe A", "text": "Platzhalter 2", "art": "text"},
          {"gruppe": "Gruppe B", "untergruppe": "Untergruppe B1", "text": "Platzhalter 3", "art": "yesno", "soll": "nein"},
          {"gruppe": "Gruppe B", "text": "Platzhalter 4", "art": "number"}]


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i + len(anfang))]


# --- 1. Statisch ---------------------------------------------------------------------------------------------------------

def test_statisch():
    js = lies("app/material/static/material.js")
    editor = abschnitt(js, "  async function formular() {", "\n  }\n")
    assert 'data-act="speichern"' not in editor and "speichern," not in editor and "ugPruefen" not in editor
    # „Gruppe anlegen“ bleibt grau, die Hauptaktion im Kopf ist im Editor grau – kein neues Rot.
    assert '<button class="btn secondary" data-act="gruppe-neu">' in editor
    assert 'const klasse = bearbeitbar ? "btn secondary small" : "btn small";' in editor
    assert not re.search(r'class="btn"[^>]*data-act', editor)
    # Stand: Live-Region im Kopf vor den Knöpfen, dieselbe über jedes Neuzeichnen.
    for teil in ('standEl.id = "fp-stand";', 'standEl.setAttribute("role", "status");', 'standEl.setAttribute("aria-live", "polite");',
                 "<span id=\"fp-stand-platz\"></span>", 'if (platz) platz.replaceWith(standEl);',
                 'zeige("Ungespeichert")', 'zeige("Speichert …")', "gespeichertText = `Gespeichert ${uhrzeit()}`;",
                 'zeige("Noch nicht gespeichert – keine Antwort vom Server", true), 10000);',
                 '"keine Verbindung"', "`Nicht gespeichert – ${fehler.kurz}`"):
        assert teil in editor, teil
    # Tippen nach einer Sekunde Ruhe, sonst sofort; höchstens eine Anfrage (nochmal).
    assert "const TIPP_MS = 1000;" in editor and "if (lauf) { nochmal = true; return lauf; }" in editor
    assert "if (bearbeitbar && gezeichnet) senden();" in editor
    # Verlassen: keepalive, Rückfrage nur, wenn es nicht ginge; Aktionen warten auf den letzten Stand.
    assert 'window.addEventListener("pagehide"' in editor and 'window.addEventListener("beforeunload"' in editor
    assert "keepalive: json.length < KEEPALIVE_MAX" in editor
    for act in ("aktivieren: async () => { if (!(await gesichert())) return;", "deaktivieren: async () => { if (!(await gesichert())) return;",
                "kopie: async () => { if (await gesichert())", "if (await gesichert()) zeigen(formular);"):
        assert act in editor, act
    assert editor.count("await gesichert()") == 5     # Aktivieren, Deaktivieren, Neue Version, Kopie, Zuweisen
    # Fehler am Feld ohne Fokuswechsel (common.js).
    common = lies("app/static/js/common.js")
    assert "function feldFehler(feld, text, opt = {}) {" in common and "if (opt.fokus !== false) feld.focus();" in common
    assert "S.feldFehler(feld, text, { fokus: false })" in editor
    # CSS: Stand klein und grau, Fehler rot.
    css = lies("app/material/static/material.css")
    assert ".mat-speicherstand { flex: 0 1 auto; min-width: 0; max-width: 40ch; text-align: right; color: var(--grau); font-size: var(--fs-klein); }" in css
    assert ".page-head .btn-row.fp-kopfknoepfe { margin-left: auto; flex-wrap: nowrap; }" in css
    assert ".mat-speicherstand.mat-warn { color: var(--rot); }" in css
    # Übung: wartet auf das automatische Speichern, kein Klick auf „Speichern“.
    uebung = lies("app/static/js/uebung/material.js")
    assert "[data-act=speichern]" not in uebung and 'ziel: "#fp-stand"' in uebung
    assert "„Platzhalter“ – gespeichert wird von selbst.\", warten: { anfrage: `PUT ${API}/formulare/${formGurt.id}` }" in uebung
    # Zusatz vom 08.11.2026: „Zuweisen“ ohne aktive Version ausgegraut mit sichtbarem Grund, daneben grau „Aktivieren“ –
    # auf der Formularseite (wartet über aktionen.aktivieren auf das letzte Speichern) und je Zeile der Seite „Prüfformulare“.
    assert 'const NUR_AKTIV_ZUWEISEN = "Erst aktivieren – dann zuweisen.";' in js
    knoepfe = abschnitt(js, "  const zuweisenKnoepfe = ", "\n  };\n")
    assert "grundSatz(id, NUR_AKTIV_ZUWEISEN)" in knoepfe and "knopfAus(id, NUR_AKTIV_ZUWEISEN)" in knoepfe
    assert 'class="btn secondary small" type="button" data-act="aktivieren"' in knoepfe and 'class="btn"' not in knoepfe
    assert 'zuweisenKnoepfe("fp-zw-grund", Boolean(pool.aktive_version))' in editor
    pool = abschnitt(js, "  async function formulare() {", "\n  }\n")
    assert "zuweisenKnoepfe(`pool-zw-grund-${x.id}`, Boolean(x.aktive_version), {" in pool
    assert "await api(`${API}/formulare/${b.dataset.version}/aktivieren`, { method: \"POST\", body: {} });" in pool
    assert ".mat-pool-aktion .mat-zw-aktion { align-items: flex-start; }" in css
    print("Statisch bestanden.")


# --- 2. Journal ----------------------------------------------------------------------------------------------------------

def journal(app, fid):
    with app.app_context():
        from app import db
        zeilen = db.query("SELECT user_name, action, before_json, after_json FROM mat_audit WHERE entity = 'form' "
                          "AND entity_id = ? ORDER BY id", (fid,))
    return [(z["user_name"], z["action"], json.loads(z["before_json"]) if z["before_json"] else None,
             json.loads(z["after_json"]) if z["after_json"] else None) for z in zeilen]


def journal_stand(eintraege):
    """Titel und Prüfpunkte, wie das Journal sie nennt (angelegt, danach je „geändert“ das Geänderte)."""
    stand = {}
    for _w, _a, _v, nachher in eintraege:
        stand.update({k: nachher[k] for k in ("title", "punkte") if nachher and k in nachher})
    return stand


def db_stand(app, fid):
    with app.app_context():
        from app.material.services import katalog
        return katalog._form_stand(fid)


def put(c, fid, **d):
    r = c.put(f"{API}/formulare/{fid}", json=d)
    assert r.status_code == 200, r.get_json()
    return r.json["formular"]


def test_journal_regel():
    from test_material import (_heute, gliederung, katalog_grund, neuer_artikel, starten, umgebung)
    from test_material_untergruppen import pool_neu
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        a, b = k["katalog"], k["adm"]              # zwei Konten der Material-Verwaltung
        name_a = a.get("/api/me").json["user"]["name"]
        name_b = b.get("/api/me").json["user"]["name"]
        pf, fid = pool_neu(a, ids["gurte"], "Platzhalter Journal", PUNKTE, aktivieren=False)
        geaendert = lambda: [e for e in journal(app, fid) if e[1] == "geaendert"]   # noqa: E731
        assert journal(app, fid)[-1][1] == "angelegt"

        # Der erste Speichervorgang nach „angelegt“ schreibt einen Eintrag …
        put(a, fid, titel="Platzhalter T1")
        assert [(e[0], e[2], e[3]) for e in geaendert()] == [(name_a, {"title": "Platzhalter Journal"}, {"title": "Platzhalter T1"})]
        # … weitere derselben Person binnen zehn Minuten keinen (Titel, Punkte, noch einmal Titel).
        put(a, fid, titel="Platzhalter T2")
        put(a, fid, punkte=PUNKTE + [{"gruppe": "Gruppe B", "text": "Platzhalter 5", "art": "text"}])
        put(a, fid, titel="Platzhalter T3")
        assert len(geaendert()) == 1
        # Ein anderes Konto: zuerst der Rest von A in A's Namen (T1 → T3 und der neue Punkt), dann B's eigener Eintrag.
        put(b, fid, titel="Platzhalter T4")
        g = geaendert()
        assert len(g) == 3, g
        assert g[1][0] == name_a and g[1][2]["title"] == "Platzhalter T1" and g[1][3]["title"] == "Platzhalter T3"
        assert any("Platzhalter 5" in p for p in g[1][3]["punkte"]) and not any("Platzhalter 5" in p for p in g[1][2]["punkte"])
        assert (g[2][0], g[2][2], g[2][3]) == (name_b, {"title": "Platzhalter T3"}, {"title": "Platzhalter T4"})
        assert journal_stand(journal(app, fid)) == db_stand(app, fid)

        # B binnen zehn Minuten: kein Eintrag; mit der Uhr elf Minuten weiter einer, der alles seit T4 nennt.
        put(b, fid, titel="Platzhalter T5")
        assert len(geaendert()) == 3
        from app.material.services import katalog
        echt = katalog._jetzt_utc
        katalog._jetzt_utc = lambda: echt() + timedelta(minutes=11)
        try:
            put(b, fid, titel="Platzhalter T6")
        finally:
            katalog._jetzt_utc = echt
        g = geaendert()
        assert len(g) == 4 and (g[3][0], g[3][2], g[3][3]) == (name_b, {"title": "Platzhalter T4"}, {"title": "Platzhalter T6"}), g[3]

        # A speichert zweimal (ein Eintrag), B aktiviert: der Rest von A in A's Namen, dann „aktiviert“ von B – das
        # Journal nennt danach genau den Stand der Datenbank.
        put(a, fid, titel="Platzhalter T7")
        put(a, fid, titel="Platzhalter T8")
        assert len(geaendert()) == 5
        assert b.post(f"{API}/formulare/{fid}/aktivieren", json={}).status_code == 200
        alle = journal(app, fid)
        assert [(e[0], e[1]) for e in alle[-2:]] == [(name_a, "geaendert"), (name_b, "aktiviert")], alle[-2:]
        assert alle[-2][2:] == ({"title": "Platzhalter T7"}, {"title": "Platzhalter T8"})
        assert journal_stand(alle) == db_stand(app, fid)
        # Nichts offen: Aktivieren ohne Rest schreibt keinen Nachtrag.
        with app.app_context():
            from app import db
            with db.transaction():
                assert not katalog.journal_nachziehen(fid)

        # Eine neue Version aus einer Version mit Rest: erst der Nachtrag an der Vorlage.
        put(a, fid, titel="Platzhalter T9")
        put(a, fid, titel="Platzhalter T10")
        r = b.post(f"{API}/formulare", json={"formular_id": pf, "vorlage_id": fid})
        assert r.status_code == 201, r.get_json()
        neu = r.json["formular"]["id"]
        assert journal(app, fid)[-1][:2] == (name_a, "geaendert") and journal(app, fid)[-1][3] == {"title": "Platzhalter T10"}
        assert journal_stand(journal(app, fid)) == db_stand(app, fid)
        assert journal(app, neu)[-1][1] == "angelegt"

        # Die erste Prüfung friert die Version ein – der Rest kommt vorher ins Journal (im Namen des Bearbeiters, nicht
        # des Prüfers).
        assert a.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [ids["gurte"]], "produkte": []}).status_code == 200
        put(a, fid, titel="Platzhalter T11")
        put(a, fid, titel="Platzhalter T12")
        gid, _ = gliederung(k["wart"])
        art = neuer_artikel(k["wart"], ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        r = starten(k["pruefer"], art["id"])
        assert r.status_code == 201, r.get_json()
        assert r.json["pruefung"]["formular"]["id"] == fid
        assert journal(app, fid)[-1][:2] == (name_a, "geaendert") and journal(app, fid)[-1][3] == {"title": "Platzhalter T12"}
        assert journal_stand(journal(app, fid)) == db_stand(app, fid)
        # Benutzte Versionen bleiben unveränderlich wie bisher.
        r = a.put(f"{API}/formulare/{fid}", json={"titel": "Platzhalter T13"})
        assert r.status_code == 409 and db_stand(app, fid)["title"] == "Platzhalter T12"

        # Deaktivieren trägt ebenso nach (an der neuen Version, aktiviert und wieder deaktiviert).
        assert b.post(f"{API}/formulare/{neu}/aktivieren", json={}).status_code == 200
        assert a.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [], "produkte": []}).status_code == 200
        put(a, neu, titel="Platzhalter N1")
        put(a, neu, titel="Platzhalter N2")
        assert b.post(f"{API}/formulare/{neu}/deaktivieren", json={}).status_code == 200
        assert [(e[0], e[1]) for e in journal(app, neu)[-2:]] == [(name_a, "geaendert"), (name_b, "deaktiviert")]
        assert journal_stand(journal(app, neu)) == db_stand(app, neu)

        # Ein älterer Eintrag mit Zeitstempel ohne Zeitzone (SQLite) stört den Vergleich nicht.
        with app.app_context():
            from app import db
            uid = db.query("SELECT id FROM users WHERE email = 'katalog@example.org'", one=True)["id"]
            db.execute("INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, after_json, "
                       "created_at) VALUES ('form', ?, ?, ?, 'geaendert', '{}', '{}', ?)",
                       (neu, uid, name_a, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())))
        put(a, neu, titel="Platzhalter N3")
        assert journal(app, neu)[-1][3] == {}       # binnen zehn Minuten nach dem eigenen (alten) Eintrag: keiner
    print("Journal bestanden.")


# --- 3. Browser ----------------------------------------------------------------------------------------------------------

def stand(s):
    return s.js("document.querySelector('#fp-stand').textContent")


def gespeichert(s, sek=15):
    from test_material_formular_editor import gespeichert as warten
    warten(s, sek)


def titel_db(u, fid):
    return u.sql("SELECT title FROM mat_form WHERE id = ?", (fid,))[0]["title"]


def punkte_db(u, fid):
    return [(z["group_name"], z["untergruppe"], z["label"], z["editor"], z["mandatory"], z["expected_value"])
            for z in u.sql("SELECT * FROM mat_checklist_item WHERE form_id = ? ORDER BY position", (fid,))]


def bis(bedingung, sek=5, schritt=0.05):
    """Bis bedingung() wahr ist – liefert die vergangene Zeit, sonst None."""
    los = time.time()
    while time.time() - los < sek:
        if bedingung():
            return time.time() - los
        time.sleep(schritt)
    return None


def puts(u, fid):
    return sum(1 for m, p, _r in u.protokoll if m == "PUT" and p == f"{API}/formulare/{fid}")


def angehalten(s, sek=5):
    """Die nächste angehaltene Anfrage (Fetch.requestPaused) – oder None."""
    ende = time.time() + sek
    while time.time() < ende:
        for e in list(s.b.ereignisse):
            if e.get("method") == "Fetch.requestPaused":
                s.b.ereignisse.remove(e)
                return e["params"]
        s.b.warten(0.1)
    return None


def erwartete_fehler(s, muster):
    """Konsolenfehler sammeln; die erwarteten (Ablehnungen, abgebrochene Anfragen) fallen heraus."""
    s.sammeln()
    s.fehler = [f for f in s.fehler if not re.search(muster, f)]


def ablauf(u, kategorie, breite, hoehe, touch):
    from test_material_formular_editor import klick, menue, oeffnen, tippen, tippflaechen, zeile, ziehen
    r = u.adm.post("/api/material/formular-pool", json={"kategorie_id": kategorie, "titel": "Platzhalter Autosave", "punkte": PUNKTE})
    assert r.status_code == 201, r.get_json()
    fid = r.json["formular"]["id"]
    s = u.seite("matverwaltung", breite, hoehe, touch)
    try:
        oeffnen(s, fid)
        # Kein „Speichern“; „Gruppe anlegen“ grau; der Stand im Kopf ist eine Live-Region (noch leer).
        assert not s.js("document.querySelector('[data-act=speichern]')")
        assert s.js("document.querySelector('[data-act=gruppe-neu]').className") == "btn secondary"
        assert s.js("""(() => { const e = document.querySelector('.page-head .btn-row > #fp-stand');
          return e && [e.getAttribute('role'), e.getAttribute('aria-live'), e.textContent]; })()""") == ["status", "polite", ""]
        assert not s.js("[...document.querySelectorAll('#mat-inhalt .btn:not(.secondary)')].filter((b) => b.getClientRects().length).length")

        # Tippen: sofort „Ungespeichert“, nach einer Sekunde Ruhe gespeichert (Datenbank), der Fokus bleibt im Feld. Die
        # Knöpfe im Kopf bleiben dabei stehen, wie lang der Stand auch ist.
        knopf = "(() => { const r = document.querySelector('.page-head [data-act=aktivieren]').getBoundingClientRect(); return [r.left, r.top + scrollY]; })()"
        lage0 = s.js(knopf)
        tippen(s, "#fp-titel", " getippt")
        assert stand(s) == "Ungespeichert"
        assert s.js(knopf) == lage0, (s.js(knopf), lage0, s.js("document.querySelector('.page-head').outerHTML.slice(0, 600)"))
        assert titel_db(u, fid) == "Platzhalter Autosave"
        gespeichert(s)
        assert s.js(knopf) == lage0          # der neue Titel im Kopf ist hier nicht länger als eine Zeile
        assert titel_db(u, fid) == "Platzhalter Autosave getippt"
        assert s.js("document.activeElement.id") == "fp-titel"
        assert s.js("document.querySelector('#fp-kopftitel').textContent") == "Platzhalter Autosave getippt"
        assert "Platzhalter Autosave getippt" in s.js("document.querySelector('.mat-versionen').textContent")
        tippen(s, f"{zeile(0, 1)} .fp-text", " getippt")
        gespeichert(s)
        assert punkte_db(u, fid)[1][2] == "Platzhalter 2 getippt"

        # Strukturänderungen sofort (weit unter der Ruhepause): Menü, „optional“, Art, Ziehen, Entfernen.
        menue(s, zeile(0, 0), "punkt-runter")
        assert bis(lambda: [p[2] for p in punkte_db(u, fid)][:2] == ["Platzhalter 2 getippt", "Platzhalter 1"], 0.9), punkte_db(u, fid)
        klick(s, f"{zeile(0, 0)} .fp-z-pflicht label")
        assert bis(lambda: punkte_db(u, fid)[0][4] == 0, 0.9), punkte_db(u, fid)
        s.js(f"""(() => {{ const a = document.querySelector({json.dumps(zeile(0, 0) + ' .fp-art')}); a.value = 'date';
          a.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
        assert bis(lambda: punkte_db(u, fid)[0][3] == "date", 0.9), punkte_db(u, fid)
        ziehen(s, zeile(0, 1), zeile(0, 0), anteil=0.2)
        assert bis(lambda: [p[2] for p in punkte_db(u, fid)][:2] == ["Platzhalter 1", "Platzhalter 2 getippt"], 0.9), punkte_db(u, fid)
        gespeichert(s)
        # Anlegen: ein leerer Punkt ist kein Fehler und geht noch nicht; mit Text schon.
        vorher = puts(u, fid)
        klick(s, '#fp-tabelle tr.fp-fuss [data-act="punkt-neu"][data-g="0"]')
        s.b.warten(1.4)
        assert puts(u, fid) == vorher and len(punkte_db(u, fid)) == 4 and not stand(s).startswith("Nicht"), stand(s)
        tippen(s, f"{zeile(0, 2)} .fp-text", "Platzhalter neu")
        gespeichert(s)
        assert [p[2] for p in punkte_db(u, fid)][:3] == ["Platzhalter 1", "Platzhalter 2 getippt", "Platzhalter neu"]
        menue(s, zeile(0, 2), "punkt-weg")
        assert bis(lambda: len(punkte_db(u, fid)) == 4, 0.9), punkte_db(u, fid)
        gespeichert(s)

        # Titel leer: am Feld, Fokus bleibt, nichts gespeichert, nichts verloren; danach geht es weiter.
        geschrieben = puts(u, fid)
        s.js("(() => { const t = document.querySelector('#fp-titel'); t.focus(); t.select(); })()")
        s.b.rufen("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
        s.b.rufen("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
        tippen(s, f"{zeile(1, 0)} .fp-text", " ohne Titel")    # woanders weitergetippt – geht erst mit dem Titel
        assert s.warte("document.querySelector('#fp-stand').textContent === 'Nicht gespeichert – Titel fehlt'", 4)
        assert s.js("""(() => { const t = document.querySelector('#fp-titel'); const p = document.getElementById(t.id + '-fehler');
          return [t.getAttribute('aria-invalid'), p && p.textContent, p && p.getAttribute('role')]; })()""") == [
            "true", "Ein Prüfformular braucht einen Titel.", "alert"]
        assert s.js(f"document.activeElement.matches({json.dumps(zeile(1, 0) + ' .fp-text')})")
        assert s.js("document.querySelector('#fp-stand').classList.contains('mat-warn')")
        assert s.js(knopf) == lage0
        assert puts(u, fid) == geschrieben and titel_db(u, fid) == "Platzhalter Autosave getippt"
        tippen(s, "#fp-titel", "Platzhalter neuer Titel")
        gespeichert(s)
        assert titel_db(u, fid) == "Platzhalter neuer Titel" and "Platzhalter 4 ohne Titel" in [p[2] for p in punkte_db(u, fid)]
        assert s.js("document.querySelector('#fp-titel').getAttribute('aria-invalid')") is None

        # Ablehnung des Servers: Ja/Nein ohne Sollwert → am Feld „Soll“ dieses Punkts; mit Sollwert gespeichert.
        punkt_b = '#fp-tabelle tr.fp-punkt[data-g="1"][data-u="0"][data-i="0"]'
        s.js(f"""(() => {{ const a = document.querySelector({json.dumps(punkt_b + ' .fp-soll')}); a.value = '';
          a.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
        assert s.warte("document.querySelector('#fp-stand').textContent.startsWith('Nicht gespeichert – Prüfpunkt 4 (Ja/Nein)')", 4), stand(s)
        assert s.js(f"""(() => {{ const t = document.querySelector({json.dumps(punkt_b + ' .fp-soll')}); const p = document.getElementById(t.id + '-fehler');
          return [t.getAttribute('aria-invalid'), p && p.textContent]; }})()""") == [
            "true", "Prüfpunkt 4 (Ja/Nein) braucht den Sollwert „ja“ oder „nein“."]
        assert punkte_db(u, fid)[3][5] == "nein"
        s.js(f"""(() => {{ const a = document.querySelector({json.dumps(punkt_b + ' .fp-soll')}); a.value = 'ja';
          a.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
        gespeichert(s)
        assert punkte_db(u, fid)[3][5] == "ja"
        erwartete_fehler(s, r"status of 400")

        # Untergruppe ohne Namen: am Namensfeld, gespeichert erst mit Namen.
        ug = '#fp-tabelle tr.fp-ug-zeile[data-g="1"][data-u="0"] .fp-ug-name'
        s.js(f"""(() => {{ const t = document.querySelector({json.dumps(ug)}); t.value = '';
          t.dispatchEvent(new Event('input', {{ bubbles: true }})); }})()""")
        assert s.warte("document.querySelector('#fp-stand').textContent === 'Nicht gespeichert – Untergruppe ohne Namen'", 4)
        tippen(s, ug, "Untergruppe neu")
        gespeichert(s)
        assert punkte_db(u, fid)[3][1] == "Untergruppe neu"

        # Reihenfolge bei schnellen Änderungen: die erste Anfrage angehalten – keine zweite gleichzeitig, danach genau der
        # neueste Stand (Titel und Reihenfolge), in der Datenbank zuletzt der neueste.
        s.sammeln()
        s.b.rufen("Fetch.enable", patterns=[{"urlPattern": f"*{API}/formulare/{fid}", "requestStage": "Request"}])
        try:
            tippen(s, "#fp-titel", " A")
            p1 = angehalten(s)
            assert p1 and p1["request"]["method"] == "PUT" and json.loads(p1["request"]["postData"])["titel"] == "Platzhalter neuer Titel A"
            assert stand(s) == "Speichert …"
            tippen(s, "#fp-titel", " B")
            menue(s, zeile(0, 0), "punkt-runter")
            assert angehalten(s, 1.6) is None, "zweite Anfrage, während die erste läuft"
            assert stand(s) == "Speichert …"
            s.b.rufen("Fetch.continueRequest", requestId=p1["requestId"])
            p2 = angehalten(s)
            koerper = json.loads(p2["request"]["postData"])
            assert koerper["titel"] == "Platzhalter neuer Titel A B" and [p["text"] for p in koerper["punkte"]][:2] == [
                "Platzhalter 2 getippt", "Platzhalter 1"], koerper
            s.b.rufen("Fetch.continueRequest", requestId=p2["requestId"])
            gespeichert(s)
            assert titel_db(u, fid) == "Platzhalter neuer Titel A B"
            assert [p[2] for p in punkte_db(u, fid)][:2] == ["Platzhalter 2 getippt", "Platzhalter 1"]
            if not touch:
                # Keine Antwort: nach 10 s „Noch nicht gespeichert – keine Antwort vom Server“; dann kein Netz: „Nicht
                # gespeichert – keine Verbindung“ – das Getippte bleibt, die nächste Änderung speichert es.
                tippen(s, "#fp-titel", " C")
                p3 = angehalten(s)
                assert p3
                s.b.warten(10.4)
                assert stand(s) == "Noch nicht gespeichert – keine Antwort vom Server"
                s.b.rufen("Fetch.failRequest", requestId=p3["requestId"], errorReason="InternetDisconnected")
                assert s.warte("document.querySelector('#fp-stand').textContent === 'Nicht gespeichert – keine Verbindung'", 3)
                assert s.warte("[...document.querySelectorAll('#toast')].some((t) => t.textContent.includes('keine Verbindung'))", 2)
                assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter neuer Titel A B C"
                assert titel_db(u, fid) == "Platzhalter neuer Titel A B"
        finally:
            s.b.rufen("Fetch.disable")
        if not touch:
            tippen(s, "#fp-titel", " D")
            gespeichert(s)
            assert titel_db(u, fid) == "Platzhalter neuer Titel A B C D"
            erwartete_fehler(s, r"ERR_INTERNET_DISCONNECTED")
        titel = titel_db(u, fid)

        # Am Finger: Tippflächen der Knöpfe am Ende und im Kopf, auch mit einem langen Fehler im Stand kein Bildlauf.
        if touch:
            for sel in ('[data-act="gruppe-neu"]', '.page-head [data-act="aktivieren"]', ".page-head details.mat-menue > summary"):
                tippflaechen(s, sel)
            s.js("document.querySelector('#fp-stand').textContent = 'Nicht gespeichert – Prüfpunkt 4 (Ja/Nein) braucht den Sollwert „ja“ oder „nein“'")
            assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            s.js("document.querySelector('#fp-stand').textContent = ''")
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        # Journal: aus vielen Speichervorgängen ein Eintrag (dieselbe Person, binnen zehn Minuten).
        eintraege = [x for x in u.sql("SELECT action FROM mat_audit WHERE entity = 'form' AND entity_id = ?", (fid,))]
        assert [x["action"] for x in eintraege] == ["angelegt", "geaendert"], eintraege
        assert puts(u, fid) > 10
        s.sammeln()
        assert not s.fehler, s.fehler

        # Verlassen gleich nach dem Tippen (vor der Ruhepause): über die Adresse …
        tippen(s, "#fp-titel", " weg")
        s.b.oeffnen(f"{u.basis}/materialablage/katalog", warten=0.2)
        assert bis(lambda: titel_db(u, fid) == titel + " weg", 4), titel_db(u, fid)
        # … und über einen Link (echter Klick auf die Brotkrume).
        oeffnen(s, fid)
        tippen(s, "#fp-titel", " Link")
        klick(s, ".mat-pfad a")
        assert bis(lambda: titel_db(u, fid) == titel + " weg Link", 4), titel_db(u, fid)
        # Mit einem Fehler fragt der Browser vor dem Verlassen (beforeunload) – „bleiben“ lässt alles stehen.
        oeffnen(s, fid)
        klick(s, "#fp-titel")
        s.js("(() => { const t = document.querySelector('#fp-titel'); t.select(); })()")
        s.b.rufen("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
        s.b.rufen("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
        assert s.warte("document.querySelector('#fp-stand').textContent === 'Nicht gespeichert – Titel fehlt'", 4)
        s.b.ereignisse = []
        s.b.rufen("Runtime.evaluate", expression="setTimeout(() => { location.href = '/materialablage/katalog'; }, 0)")
        frage = None
        ende = time.time() + 5
        while time.time() < ende and not frage:
            s.b.warten(0.1)
            frage = next((e["params"] for e in s.b.ereignisse if e.get("method") == "Page.javascriptDialogOpening"), None)
        assert frage and frage["type"] == "beforeunload", frage
        s.b.rufen("Page.handleJavaScriptDialog", accept=False)
        s.b.warten(0.3)
        assert s.js("location.pathname") == f"/materialablage/katalog/formular/{fid}"
        tippen(s, "#fp-titel", "Platzhalter vor dem Aktivieren")
        gespeichert(s)

        # „Aktivieren“ gleich nach dem Tippen: erst das Speichern, dann aktivieren.
        tippen(s, "#fp-titel", " akt")
        n = len(u.protokoll)
        klick(s, '.page-head [data-act="aktivieren"]')
        assert s.warte("!!document.querySelector('.page-head .s-einsatzbereit')", 6)
        folge = [(m, p) for m, p, _r in u.protokoll[n:] if m in ("PUT", "POST") and p.startswith(f"{API}/formulare/{fid}")]
        assert folge[:2] == [("PUT", f"{API}/formulare/{fid}"), ("POST", f"{API}/formulare/{fid}/aktivieren")], folge
        assert titel_db(u, fid) == "Platzhalter vor dem Aktivieren akt"
        # Nach dem Aktivieren nennt das Journal den ganzen Stand (Nachtrag vor „aktiviert“).
        alle = journal(u.app, fid)
        assert [e[1] for e in alle][-1] == "aktiviert" and journal_stand(alle) == db_stand(u.app, fid), alle
        assert s.js("document.querySelector('#fp-stand').textContent") == ""
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()
    return fid


def ohne_aktive(u, kategorie, breite, hoehe, touch):
    """Zusatz vom 08.11.2026: Ohne aktive Version ist „Zuweisen“ ausgegraut – der Grund steht sichtbar darüber, daneben
    „Aktivieren“ (grau); ein Klick auf „Zuweisen“ öffnet nichts und hebt den Grund hervor. Auf der Formularseite wartet
    „Aktivieren“ auf das letzte automatische Speichern; danach – wie in der Zeile der Seite „Prüfformulare“ – ist
    „Zuweisen“ frei."""
    from test_material_formular_editor import klick, oeffnen, tippen, tippflaechen

    def neu(titel):
        r = u.adm.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": titel, "punkte": PUNKTE})
        assert r.status_code == 201, r.get_json()
        return r.json["formular"]["formular_id"], r.json["formular"]["id"]

    pf, fid = neu(f"Platzhalter ohne aktive {breite}")
    s = u.seite("matverwaltung", breite, hoehe, touch)
    try:
        oeffnen(s, fid)
        zw, akt = ".mat-gilt-fuer [data-act=zuweisen]", ".mat-gilt-fuer [data-act=aktivieren]"
        assert s.js(f"""(() => {{ const z = document.querySelector('{zw}'), g = document.getElementById('fp-zw-grund');
          return [z.getAttribute('aria-disabled'), z.getAttribute('aria-describedby'), g.hidden, g.textContent,
                  document.querySelector('{akt}').className]; }})()""") == [
            "true", "fp-zw-grund", False, "Erst aktivieren – dann zuweisen.", "btn secondary small"]
        if touch:
            tippflaechen(s, zw)
            tippflaechen(s, akt)
        klick(s, zw)
        assert not s.js("document.querySelector('dialog[open]')")
        assert s.js("document.getElementById('fp-zw-grund').classList.contains('betont')")
        # Gleich nach dem Tippen „Aktivieren“ im Abschnitt: erst das Speichern, dann aktivieren; danach „Zuweisen“ frei.
        tippen(s, "#fp-titel", " getippt")
        n = len(u.protokoll)
        klick(s, akt)
        assert s.warte("!!document.querySelector('.page-head .s-einsatzbereit')", 6)
        folge = [(m, p) for m, p, _r in u.protokoll[n:] if m in ("PUT", "POST") and p.startswith(f"{API}/formulare/{fid}")]
        assert folge[:2] == [("PUT", f"{API}/formulare/{fid}"), ("POST", f"{API}/formulare/{fid}/aktivieren")], folge
        assert titel_db(u, fid) == f"Platzhalter ohne aktive {breite} getippt"
        assert s.js(f"""(() => {{ const z = document.querySelector('{zw}');
          return [z.hasAttribute('aria-disabled'), !!document.getElementById('fp-zw-grund'), !!document.querySelector('{akt}')]; }})()""") == [False, False, False]
        klick(s, zw)
        assert s.warte("!!document.querySelector('dialog.mat-zuweisen[open]')")
        s.taste()
        s.b.warten(0.3)

        # Seite „Prüfformulare“: je Zeile ohne aktive Version derselbe Grund und „Aktivieren“ (die neueste Version).
        pf2, fid2 = neu(f"Platzhalter Zeile ohne aktive {breite}")
        s.oeffnen("/materialablage/katalog/formulare", warten=0.6)
        s.warte(f"!!document.querySelector('[data-act=zuweisen][data-id=\"{pf2}\"]')")
        zw2, akt2 = f'[data-act=zuweisen][data-id="{pf2}"]', f'[data-act=aktivieren][data-id="{pf2}"]'
        assert s.js(f"""(() => {{ const z = document.querySelector({json.dumps(zw2)}), a = document.querySelector({json.dumps(akt2)}),
          g = document.getElementById('pool-zw-grund-{pf2}');
          return [z.getAttribute('aria-disabled'), g && !g.hidden && g.textContent, a.className, a.dataset.version, a.getAttribute('aria-label')]; }})()""") == [
            "true", "Erst aktivieren – dann zuweisen.", "btn secondary small", str(fid2), f"„Platzhalter Zeile ohne aktive {breite}“ Version 1 aktivieren"]
        # Eine Zeile mit aktiver Version: nur „Zuweisen“, frei.
        assert s.js(f"""(() => {{ const z = document.querySelector('[data-act=zuweisen][data-id="{pf}"]');
          return [z.hasAttribute('aria-disabled'), !!document.querySelector('[data-act=aktivieren][data-id="{pf}"]')]; }})()""") == [False, False]
        if touch:
            tippflaechen(s, zw2)
            tippflaechen(s, akt2)
        klick(s, zw2)
        assert not s.js("document.querySelector('dialog[open]')")
        klick(s, akt2)
        assert s.warte(f"!document.querySelector({json.dumps(zw2)} + '[aria-disabled]') && !document.getElementById('pool-zw-grund-{pf2}')", 6)
        assert u.sql("SELECT active FROM mat_form WHERE id = ?", (fid2,))[0]["active"] == 1
        if not touch:
            assert s.js(f"document.activeElement.matches({json.dumps(zw2)})")
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        klick(s, zw2)
        assert s.warte("!!document.querySelector('dialog.mat-zuweisen[open]')")
        s.taste()
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()


def uebung(u, breite, hoehe, touch):
    """Die Übung der Material-Verwaltung („Katalog und Prüfformular“) mit dem automatischen Speichern."""
    u.merker_leeren("matverwaltung")
    befunde = u.durchlauf("material", "verwaltung", breite, hoehe, touch)
    assert not befunde, befunde


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_material import katalog_grund
    with Umgebung() as u:
        ids = katalog_grund(u.adm)
        for breite, hoehe, touch in GROESSEN:
            los = time.time()
            ablauf(u, ids["gurte"], breite, hoehe, touch)
            print(f"Automatisches Speichern {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({time.time() - los:.1f} s)")
            ohne_aktive(u, ids["gurte"], breite, hoehe, touch)
            print(f"Zuweisen ohne aktive Version {breite}×{hoehe}: bestanden")
            uebung(u, breite, hoehe, touch)
            print(f"Übung der Material-Verwaltung {breite}×{hoehe}: bestanden")


if __name__ == "__main__":
    test_statisch()
    test_journal_regel()
    test_browser()
