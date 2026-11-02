"""Startseite über alle Module (Wunsch und Entscheidung des Nutzers vom 02.11.2026: „Start über alle Module“).

„/“ zeigt jedem angemeldeten Konto mit mindestens einem Modul (oder dem Lesemodus der Strömipedia) diese Seite: je Modul
eine Kachel mit Zahlen, die zum Handeln führen, darunter „Zuletzt besucht“ und „Neu und geändert“ über die Module und die
obersten Abschnitte der Strömipedia als Karten. Alles kommt über GET /api/start, nach den Rechten des Kontos gefiltert –
ein Modul ohne Zugang taucht weder als Kachel noch in einer Liste auf. Die Zahlen rechnet jeweils der Dienst, der sie im
Modul selbst zeigt (Materialablage: bestand.zaehlung, mangel.anzahl_offen, antrag.zu_entscheiden, psa.kurz – dieselben
Aufrufe wie GET /api/material/start); hier werden sie nur zusammengetragen.

„Neu seit deinem letzten Besuch“: verglichen wird mit dem vorigen Besuch der Startseite. Ein Besuch endet erst nach
BESUCH_PAUSE ohne Aufruf der Startseite – wer zwischendurch in ein Modul springt und über das Logo zurückkommt oder die
Seite neu lädt, sieht dieselben Zahlen wie eben (sonst wären sie nach dem ersten Blick schon fort). Gemerkt wird mit
POST /api/start/besuch (schreibt – also mit dem CSRF-Schutz der Schnittstelle), die Seite ruft ihn nach dem Zeichnen.

Merker ohne Schemaschritt in mat_meta, der Schlüssel-Wert-Tabelle, die auch das Willkommen der Materialablage nutzt
(beide gehen mit dem Konto, konto_vergessen in api_admin.delete_user; ein Zurücksetzen der Materialablage auf dev leert
sie mit):
  start:besuch:<Konto>  {"bisher": Zeitpunkt, "zuletzt": Zeitpunkt} – Vergleichspunkt und letzter Aufruf der Startseite
  start:ziele:<Konto>   [[modul, kennung, Zeitpunkt], …] – zuletzt geöffnete Alben, Lehrgänge und Artikel, höchstens
                        ZIELE_MAX, neueste zuerst
Seiten der Strömipedia stehen weiter in wiki_views (wie für „Zuletzt besucht“ der Übersicht der Strömipedia, seit dem
02.11.2026 auch die des Lesemodus). Beim Zeigen wird jedes Ziel erneut nach den Rechten von jetzt gefiltert: Was das
Konto nicht mehr sehen darf oder was gelöscht ist, fällt weg. Kein localStorage – Geräte werden geteilt."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify

from . import api_pruefungen, api_wiki, auth, db, module

bp = Blueprint("start", __name__, url_prefix="/api/start")
auth.eingabefehler_abfangen(bp)

BESUCH = "start:besuch:{uid}"
ZIELE = "start:ziele:{uid}"
ZIELE_MAX = 20                  # gemerkte Ziele je Konto (Alben, Lehrgänge, Artikel)
LISTE_MAX = 8                   # Einträge in „Zuletzt besucht“ und „Neu und geändert“
BESUCH_PAUSE = timedelta(minutes=30)
ZIEL_MODULE = ("karte", "pruefungen", "material")
WIKI_KARTEN = 6                 # Abschnitte der Strömipedia auf der Startseite (alle unter „alle →“)
WIKI_UNTERSEITEN = 3            # Unterseiten je Karte


# --- Wer die Startseite bekommt --------------------------------------------------------------------------------------

def zugang(user=None):
    """Hat das Konto die Startseite? Ein Modul mit Stufe (die Materialablage mit Stufe und Namen, rechte.zugang), „Meine
    PSA“ oder der Lesemodus der Strömipedia. Sonst bleibt die Hinweisseite „noch kein Bereich freigeschaltet“."""
    from .material.services import psa
    from .material.services import rechte as mat_rechte
    user = user or auth.current_user()
    if not user:
        return False
    return bool(any(auth.nutzt(m, user) for m in ("wiki", "karte", "pruefungen", "verwaltung"))
                or mat_rechte.zugang(user) or auth.wiki_lesemodus(user) or psa.kopfleiste(user))


# --- Merker ----------------------------------------------------------------------------------------------------------

def _zeit(text):
    try:
        t = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _merker(schluessel, vorgabe):
    row = db.query("SELECT wert FROM mat_meta WHERE schluessel = ?", (schluessel,), one=True)
    try:
        wert = json.loads(row["wert"]) if row else vorgabe
    except ValueError:
        return vorgabe
    return wert if isinstance(wert, type(vorgabe)) else vorgabe


def _merken(schluessel, wert):
    db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
               "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, json.dumps(wert)))


def _vergleichspunkt(besuch, jetzt):
    """Seit wann „neu“ zählt: der vorige Besuch. Liegt der letzte Aufruf weniger als BESUCH_PAUSE zurück, läuft der Besuch
    noch – dann gilt weiter der Punkt davor. Beim allerersten Besuch None (es gibt kein „seit“)."""
    zuletzt = _zeit(besuch.get("zuletzt"))
    if zuletzt and jetzt - zuletzt < BESUCH_PAUSE:
        return besuch.get("bisher")
    return besuch.get("zuletzt")


def seit(user):
    return _vergleichspunkt(_merker(BESUCH.format(uid=int(user["id"])), {}), datetime.now(timezone.utc))


@bp.post("/besuch")
@auth.login_required
def besuch():
    """Die Startseite wurde gezeigt: Vergleichspunkt fortschreiben (siehe _vergleichspunkt). Unter der Schreibsperre – zwei
    Reiter gleichzeitig sollen den Punkt nicht zweimal weiterschieben."""
    uid = int(auth.current_user()["id"])
    jetzt = datetime.now(timezone.utc)
    with db.transaction(sofort=True):
        alt = _merker(BESUCH.format(uid=uid), {})
        _merken(BESUCH.format(uid=uid), {"bisher": _vergleichspunkt(alt, jetzt), "zuletzt": db.now()})
    return jsonify(ok=True)


def ziel_merken(modul, kennung, user=None):
    """Ein geöffnetes Ziel für „Zuletzt besucht“ vormerken (Album, Lehrgang, Artikel der Materialablage) – aufgerufen von der
    Route, die es zeigt, nachdem sie das Recht geprüft hat. Höchstens ZIELE_MAX je Konto, ein Ziel steht nur einmal da.
    Scheitert das Merken (Datenbank gesperrt), bleibt es diesmal ungemerkt – die Seite kommt trotzdem."""
    user = user or auth.current_user()
    if not user or modul not in ZIEL_MODULE:
        return
    schluessel = ZIELE.format(uid=int(user["id"]))
    try:
        with db.transaction(sofort=True):
            liste = [z for z in _merker(schluessel, []) if isinstance(z, list) and len(z) == 3
                     and [z[0], z[1]] != [modul, int(kennung)]]
            _merken(schluessel, [[modul, int(kennung), db.now()], *liste][:ZIELE_MAX])
    except sqlite3.Error as exc:
        current_app.logger.warning("Startseite: Besuch von %s %s nicht gemerkt (Konto %s) – %s", modul, kennung,
                                   user["id"], exc)


def konto_vergessen(uid):
    """Beim Löschen eines Kontos (api_admin.delete_user): beide Merker gehen mit – users.id wird sonst womöglich neu
    vergeben, und ein Nachfolger erbte die Liste."""
    db.execute("DELETE FROM mat_meta WHERE schluessel IN (?, ?)", (BESUCH.format(uid=int(uid)), ZIELE.format(uid=int(uid))))


# --- Kacheln ---------------------------------------------------------------------------------------------------------

def _zeile(art, zahl, href, **zusatz):
    return dict(art=art, zahl=zahl or 0, href=href, **zusatz)


def _kachel(modul, zeilen, ruhig, name=None, pfad=None):
    """Eine Kachel: Kopf mit Modulname und Link, darunter die Zeilen mit einer Zahl über 0 – sonst der ruhige Satz."""
    return {"modul": modul, "name": name or module.NAME[modul], "pfad": pfad or module.PFAD[modul],
            "zeilen": [z for z in zeilen if z["zahl"]], "ruhig": ruhig}


def _wiki_kachel(seiten, lesemodus, uid, ab):
    """seiten: sichtbare_seiten (nach Rechten). „neu oder geändert seit deinem letzten Besuch“ ohne das, was das Konto selbst
    zuletzt geändert hat. Genau eine Seite: der Link geht gleich zu ihr, sonst zur Übersicht (dort „Zuletzt geändert“)."""
    neu = [s for s in seiten if s["updated_at"] > ab and s["updated_by"] != uid] if ab else []
    pfad = module.PFAD["wiki"]
    return _kachel("wiki", [
        _zeile("seiten_frei" if lesemodus else "seiten", len(seiten), pfad),
        _zeile("wiki_neu", len(neu), f"{pfad}/{neu[0]['slug']}" if len(neu) == 1 else pfad),
    ], "Nichts Neues seit deinem letzten Besuch." if seiten else
        ("Derzeit sind keine Seiten freigegeben." if lesemodus else "Die Strömipedia ist noch leer."))


def _karte_kachel(uid, ab):
    """Alben gesamt (jedes Konto mit Stufe sieht alle Alben, wie /api/albums); neue Alben und Bilder anderer seit dem
    letzten Besuch. Betrifft das Neue genau ein Album, führt der Link dorthin (/ankerplaetze#album=…)."""
    pfad = module.PFAD["karte"]
    alben = db.query("SELECT COUNT(*) AS n FROM albums", one=True)["n"]
    neue_alben = db.query("SELECT id FROM albums WHERE created_at > ? AND owner_id <> ?", (ab, uid)) if ab else []
    bilder = db.query("SELECT COUNT(*) AS n, COUNT(DISTINCT album_id) AS a, MIN(album_id) AS album FROM photos "
                      "WHERE created_at > ? AND owner_id <> ?", (ab, uid), one=True) if ab else {"n": 0}
    return _kachel("karte", [
        _zeile("alben", alben, pfad),
        _zeile("alben_neu", len(neue_alben), f"{pfad}#album={neue_alben[0]['id']}" if len(neue_alben) == 1 else pfad),
        _zeile("bilder_neu", bilder["n"], f"{pfad}#album={bilder['album']}" if bilder["n"] and bilder["a"] == 1 else pfad),
    ], "Nichts Neues seit deinem letzten Besuch." if alben else "Noch keine Alben.")


def _lehrgang_sicht(uid):
    """Bedingung über pruef_lehrgaenge l: die Lehrgänge, die das Konto sieht – wie api_pruefungen.list_lehrgaenge (die
    Verwaltung alle, sonst die, in denen es mit seinem Konto als Ausbilder steht)."""
    if auth.verwaltet("pruefungen"):
        return "1", ()
    return "l.id IN (SELECT lehrgang_id FROM pruef_ausbilder WHERE user_id = ?)", (uid,)


def _pruefungen_kachel(uid):
    """Laufende Lehrgänge, die das Konto sieht, und darin die Zahlen der Lehrgangsliste (_LEHRGANG_SQL): Leistungen ohne
    Abnahme (Zellen gesamt − abgenommen, wie „x/y Leistungen abgenommen“) und offene Mängel. Bei genau einem laufenden
    Lehrgang führen die Zeilen in ihn (Reiter Bewertung bzw. Mängel)."""
    bedingung, args = _lehrgang_sicht(uid)
    rows = db.query(api_pruefungen._LEHRGANG_SQL + f"WHERE l.status = 'laufend' AND {bedingung}", args)
    pfad = module.PFAD["pruefungen"]
    einer = f"{pfad}/{rows[0]['id']}" if len(rows) == 1 else None
    offen = sum(max(0, r["tn_anzahl"] * r["leistungen_anzahl"] - r["zellen_abgenommen"]) for r in rows)
    return _kachel("pruefungen", [
        _zeile("laufend", len(rows), einer or pfad),
        _zeile("leistungen_offen", offen, f"{einer}#bewertung" if einer else pfad),
        _zeile("lehrgang_maengel", sum(r["offene_maengel"] for r in rows), f"{einer}#maengel" if einer else pfad),
    ], "Kein laufender Lehrgang.")


def _material_kachel(user):
    """Mit Bestand im eigenen Bereich dieselben Zahlen wie die Übersicht der Materialablage (GET /api/material/start):
    überfällig, neu (Eingangsprüfung offen) und bald fällig aus bestand.zaehlung (wie ihre Statuskacheln), gemeldete
    Mängel aus mangel.anzahl_offen (= „maengel_gesamt“),
    zu entscheidende Änderungsanträge aus antrag.zu_entscheiden. Ohne Bestand die eigene PSA (psa.kurz, wie der Kasten
    der Übersicht)."""
    from .material.services import antrag, bestand, mangel, psa
    from .material.services import rechte as mat_rechte
    from .material.services import status as st
    pfad = module.PFAD["material"]
    if mat_rechte.sicht(user).irgendwo("lesen"):
        z = bestand.zaehlung()
        return _kachel("material", [
            _zeile("ueberfaellig", z["ueberfaellig"], "/materialablage/pruefungen?status=ueberfaellig#zu-pruefen"),
            _zeile("neu", z["neu"], "/materialablage/pruefungen?status=neu#zu-pruefen"),
            _zeile("bald_faellig", z["bald_faellig"], "/materialablage/pruefungen?status=bald_faellig#zu-pruefen",
                   tage=st.schwelle_tage()),
            _zeile("maengel", mangel.anzahl_offen(), pfad),
            _zeile("antraege", antrag.zu_entscheiden(user), "/materialablage/bestand/antraege"),
        ], "Keine fälligen Prüfungen.")
    return _psa_kachel(psa.kurz(user), "material", "Für dich ist noch kein Bestand freigegeben.")


def _psa_kachel(k, modul, ruhig):
    """„Meine PSA“: zugeordnete Artikel und davon nicht einsatzbereit (gesperrt, überfällig, Lebensdauer erreicht, neu –
    psa.DRINGEND), beides mit Link auf „Meine PSA“."""
    ziel = module.PFAD["material"] + "/meine-psa"
    k = k or {"anzahl": 0, "dringend": 0}
    return _kachel(modul, [_zeile("psa", k["anzahl"], ziel), _zeile("psa_dringend", k["dringend"], ziel)], ruhig,
                   name="Meine PSA" if modul == "meine_psa" else None, pfad=ziel if modul == "meine_psa" else None)


def _verwaltung_kachel():
    """Offene Kontoanfragen – dieselbe Auswahl wie der Kasten „Offene Kontoanfragen“ der Leitstelle (status pending)."""
    n = db.query("SELECT COUNT(*) AS n FROM users WHERE status = 'pending'", one=True)["n"]
    return _kachel("verwaltung", [_zeile("anfragen", n, module.PFAD["verwaltung"] + "#pending")],
                   "Keine offenen Kontoanfragen.")


# --- Listen ----------------------------------------------------------------------------------------------------------

def _eintrag(modul, titel, href, zeit, zusatz=""):
    return {"modul": modul, "modulname": module.NAME[modul], "titel": titel, "zusatz": zusatz, "href": href, "zeit": zeit}


def _artikel_titel(r):
    return " ".join(x for x in (r["manufacturer"], r["model"]) if x)


def _zuletzt_besucht(user, wiki):
    """Die zuletzt geöffneten Ziele über die Module, neueste zuerst, höchstens LISTE_MAX – jedes erneut nach den Rechten
    von jetzt gefiltert (Seiten: lesbar bzw. freigegeben; Alben: Stufe Ankerplätze; Lehrgänge: sichtbar; Artikel: im
    eigenen Bereich, rechte.artikel_filter wie die Artikelseite). Gelöschtes fällt mit den Zeilen weg."""
    uid = int(user["id"])
    out = []
    if wiki is not None:
        sichtbar = {s["id"]: s for s in wiki["seiten"]}
        for v in db.query("SELECT page_id, seen_at FROM wiki_views WHERE user_id = ? ORDER BY seen_at DESC LIMIT ?",
                          (uid, ZIELE_MAX)):
            s = sichtbar.get(v["page_id"])
            if s:
                out.append(_eintrag("wiki", s["title"], f"{module.PFAD['wiki']}/{s['slug']}", v["seen_at"]))
    ziele = {}
    for z in _merker(ZIELE.format(uid=uid), []):
        if isinstance(z, list) and len(z) == 3 and z[0] in ZIEL_MODULE and isinstance(z[1], int):
            ziele.setdefault(z[0], {})[z[1]] = z[2]

    def ids(modul):
        return json.dumps(sorted(ziele.get(modul, {})))
    if ziele.get("karte") and auth.nutzt("karte", user):
        for r in db.query("SELECT id, title FROM albums WHERE id IN (SELECT value FROM json_each(?))", (ids("karte"),)):
            out.append(_eintrag("karte", r["title"], f"{module.PFAD['karte']}#album={r['id']}", ziele["karte"][r["id"]]))
    if ziele.get("pruefungen") and auth.is_pruefer(user):
        bedingung, args = _lehrgang_sicht(uid)
        for r in db.query(f"SELECT l.id, l.titel FROM pruef_lehrgaenge l WHERE l.id IN (SELECT value FROM json_each(?)) "
                          f"AND {bedingung}", (ids("pruefungen"), *args)):
            out.append(_eintrag("pruefungen", r["titel"], f"{module.PFAD['pruefungen']}/{r['id']}",
                                ziele["pruefungen"][r["id"]]))
    from .material.services import rechte as mat_rechte
    if ziele.get("material") and mat_rechte.zugang(user):
        for r in db.query("SELECT i.id, i.inventory_no, p.manufacturer, p.model FROM mat_item i "
                          "JOIN mat_product p ON p.id = i.product_id WHERE i.id IN (SELECT value FROM json_each(?)) "
                          f"AND {mat_rechte.artikel_filter('i', user=user)}", (ids("material"),)):
            out.append(_eintrag("material", r["inventory_no"], f"{module.PFAD['material']}/artikel/{r['id']}",
                                ziele["material"][r["id"]], _artikel_titel(r)))
    out.sort(key=lambda e: e["zeit"] or "", reverse=True)
    return out[:LISTE_MAX]


def _neu_und_geaendert(user, wiki):
    """Die letzten Änderungen über die Module, neueste zuerst, höchstens LISTE_MAX: Seiten der Strömipedia (nur sichtbare),
    Alben (mit Stufe Ankerplätze alle), Lehrgänge (nur sichtbare). Die Materialablage nicht: Ihr Journal verzeichnet jeden
    Handgriff – als „neu und geändert“ wäre es nur Rauschen; ihre Zahlen stehen in der Kachel."""
    out = []
    if wiki is not None:
        for s in sorted(wiki["seiten"], key=lambda s: s["updated_at"], reverse=True)[:LISTE_MAX]:
            out.append(dict(_eintrag("wiki", s["title"], f"{module.PFAD['wiki']}/{s['slug']}", s["updated_at"]),
                            neu=s["created_at"] == s["updated_at"]))
    if auth.nutzt("karte", user):
        for r in db.query("SELECT id, title, created_at, updated_at FROM albums ORDER BY updated_at DESC LIMIT ?",
                          (LISTE_MAX,)):
            out.append(dict(_eintrag("karte", r["title"], f"{module.PFAD['karte']}#album={r['id']}", r["updated_at"]),
                            neu=r["created_at"] == r["updated_at"]))
    if auth.is_pruefer(user):
        bedingung, args = _lehrgang_sicht(int(user["id"]))
        for r in db.query(f"SELECT l.id, l.titel, l.created_at, l.updated_at FROM pruef_lehrgaenge l WHERE {bedingung} "
                          "ORDER BY l.updated_at DESC LIMIT ?", (*args, LISTE_MAX)):
            out.append(dict(_eintrag("pruefungen", r["titel"], f"{module.PFAD['pruefungen']}/{r['id']}", r["updated_at"]),
                            neu=r["created_at"] == r["updated_at"]))
    out.sort(key=lambda e: e["zeit"] or "", reverse=True)
    return out[:LISTE_MAX]


# --- Schnittstelle ---------------------------------------------------------------------------------------------------

@bp.get("")
@auth.login_required
def lesen():
    """Alles für die Startseite, nach den Rechten des Kontos: „kacheln“ in der Reihenfolge der Navigation (Strömipedia,
    Ankerplätze, Riegenkarten, Materialablage bzw. „Meine PSA“, Leitstelle) – nur Module, die das Konto nutzt; „zuletzt“
    und „neu“ (je höchstens LISTE_MAX); „abschnitte“ der Strömipedia (oder null ohne Zugang, auch nicht im Lesemodus);
    „lesemodus“; „seit“ (Vergleichspunkt für „neu“, null beim ersten Besuch). Ohne Startseite (kein Modul) 403."""
    from .material.services import psa
    from .material.services import rechte as mat_rechte
    user = auth.current_user()
    if not zugang(user):
        return jsonify(error="Für dein Konto ist noch kein Bereich freigeschaltet."), 403
    uid = int(user["id"])
    ab = seit(user)
    lesemodus = auth.wiki_lesemodus(user)
    wiki = {"seiten": api_wiki.sichtbare_seiten(lesemodus)} if auth.nutzt("wiki", user) or lesemodus else None
    kacheln = []
    if wiki is not None:
        kacheln.append(_wiki_kachel(wiki["seiten"], lesemodus, uid, ab))
    if auth.nutzt("karte", user):
        kacheln.append(_karte_kachel(uid, ab))
    if auth.is_pruefer(user):
        kacheln.append(_pruefungen_kachel(uid))
    if mat_rechte.zugang(user):
        kacheln.append(_material_kachel(user))
    elif psa.kopfleiste(user):
        kacheln.append(_psa_kachel(psa.kurz(user), "meine_psa", "Dir ist keine PSA zugeordnet."))
    if auth.is_admin(user):
        kacheln.append(_verwaltung_kachel())
    abschnitte = api_wiki.abschnitte(wiki["seiten"], lesemodus, WIKI_UNTERSEITEN) if wiki is not None else None
    return jsonify(kacheln=kacheln, zuletzt=_zuletzt_besucht(user, wiki), neu=_neu_und_geaendert(user, wiki),
                   abschnitte=abschnitte[:WIKI_KARTEN] if abschnitte is not None else None,
                   abschnitte_gesamt=len(abschnitte or ()), lesemodus=lesemodus, seit=ab)
