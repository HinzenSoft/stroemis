"""Mangelmeldung (Phase 3 · Lieferung 1, Bauentwurf Abschnitt 3): Die zugeordnete Person und jeder mit Leserecht am
Artikel (lesen, verwalten oder prüfen an seiner Heimat) meldet einen Mangel – mit Beschreibung (Pflicht) und bis zu drei
Fotos. Jede Meldung sperrt sofort in derselben Transaktion (Systemordner „Gesperrt“, Herkunft gemerkt, Grund „Mangel
gemeldet am TT.MM.JJJJ“), auch bei offenem Prüfentwurf; war der Artikel schon gesperrt oder verloren, bleibt die Sperre
mit ihrem Grund. Zurück bringt ihn nur eine Freiprüfung (Prüfung mit „einsatzbereit“, je Meldung abgehakt „Gemeldeten
Mangel geprüft“) – sie oder eine Aussonderung erledigt die Meldung (gespeichert, nicht abgeleitet). „instandsetzen“
erledigt nicht. Aussondern durch den Materialwart geht nach einer reinen Mangelsperre erst, wenn ein Prüfer den
Artikel seitdem geprüft hat (nur_gemeldet, pruefung.aussondern).

Recht, Zustand und eigene offene Meldung werden vor dem Verarbeiten der Fotos geprüft und in der Transaktion am frisch
gelesenen Artikel wiederholt – ein Konto ohne Recht oder mit offener Meldung bringt den Server nicht dazu, Bilder zu
dekodieren. Höchstens eine offene Meldung je Konto und Artikel (409), keine Tagesgrenze: Kontrolle ist der Name im
Journal (wie bei der globalen Suche). Fotos: nur Web- und Vorschaufassung bleiben (ohne EXIF), jedes Original geht gleich
nach seiner Verarbeitung (F4).

Mails sofort, im Hintergrund: an die Verwalter der Heimat (ohne sie die Material-, ohne diese die Plattform-Verwaltung)
und die Prüfer mit wirksamer Prüffreigabe dort – den Namen des Melders nur, wer am Artikel ein Grundrecht hat; dazu die
zugeordnete Person, wenn ein anderer ihre PSA meldet (kurz, ohne Melder und Text, nicht abbestellbar). Nie an den Melder,
nie an DEMO-Adressen. Bei DEMO-Artikeln und unter der Umgebungssperre (erinnerung.gesperrt, dev) stehen die Mails im Log
statt im Postfach. Die Mails hängen nicht am Schalter der Erinnerungsmails – sie sind die Nachricht zu einer Sperre.

Meldungen sind unveränderlich (Trigger, models.TRIGGER_13), lassen sich nicht löschen und bleiben unbefristet mit dem
Artikel; beim Löschen eines Kontos setzt die Datenbank nur die Kontokennung auf NULL, der Name bleibt (F3)."""
import json
import os

from flask import current_app, g

from ... import db
from ...auth import _im_hintergrund, current_user
from ...images import _rm, delete_photo_files
from ...mailer import send_mail                    # Tests ersetzen mangel.send_mail
from . import OHNE_NAMEN, Abgelehnt, heute, text
from . import bestand, erinnerung, journal, katalog, psa, rechte

TEXT_MAX = 2000
MAX_FOTOS = 3
LISTE_MAX = 50               # Meldungen am Artikel und Zeilen im Kasten der Übersicht
KURZ_MAX = 160               # Kurztext im Kasten der Übersicht

AUSGESONDERT = "Der Artikel ist ausgesondert – an ihm gibt es nichts mehr zu melden."
SCHON_GEMELDET = ("Du hast für diesen Artikel schon einen Mangel gemeldet (am {datum}). Ein Prüfer sieht ihn sich an – "
                  "Ergänzungen bitte direkt an den Materialwart.")
MANGEL_NEU = ("Am Artikel ist ein gemeldeter Mangel offen, den du nicht als geprüft abgehakt hast – lade die Prüfung "
              "neu, sieh ihn dir an und hake ihn ab, bevor du freigibst.")
NUR_GEMELDET = ("Der Artikel ist durch eine Mangelmeldung gesperrt und seitdem nicht geprüft – aussondern kann ihn jetzt "
                "nur ein Prüfer (Prüfung mit Ergebnis „aussondern“). Nach einer Prüfung mit „instandsetzen“ geht es "
                "auch hier.")
NUR_NEUE_PRUEFUNG = "Am Artikel ist ein Mangel gemeldet – freigeben kann ihn nur eine neue Prüfung."

# Mails gehen neben der Anfrage hinaus (wie beim Rückruf); Tests setzen hier einen direkten Aufruf ein.
HINTERGRUND = _im_hintergrund

# Offene Meldung d, nach der noch keine Prüfung des Artikels abgeschlossen wurde. Berichtigungen und Aussonderungen
# zählen nicht; gleiche Sekunde zählt als vorher (wie rueckruf.zustand) – im Zweifel gilt sie als ungeprüft.
UNGEPRUEFT = ("d.closed_at IS NULL AND NOT EXISTS (SELECT 1 FROM mat_inspection x WHERE x.item_id = d.item_id "
              "AND x.completed_at > d.created_at AND x.kind <> 'aussonderung' AND x.corrects_inspection_id IS NULL)")

# Warum ein Empfänger die Mail bekommt – der letzte Satz der Mail.
WARUM = {"verwalter": "weil du diesen Ordner verwaltest.",
         "pruefer": "weil du hier prüfen darfst.",
         "material": "weil du zur Material-Verwaltung gehörst und für diesen Ordner kein Materialwart eingetragen ist.",
         "plattform": "weil du zur Plattform-Verwaltung gehörst und für diesen Ordner kein Materialwart eingetragen ist."}

# Die Meldung mit der Art der Prüfung, die sie erledigt hat (Freiprüfung oder Aussonderung).
_MELDUNG_SQL = ("SELECT d.*, x.kind AS closed_kind FROM mat_defect_report d "
                "LEFT JOIN mat_inspection x ON x.id = d.closed_inspection_id ")


def _ortszeit(iso):
    from .protokoll import ortszeit
    return ortszeit(iso)


def _datum(iso):
    return _ortszeit(iso).strftime("%d.%m.%Y")


# --- Lesen ----------------------------------------------------------------------------------------------------------

def meldung(mid):
    r = db.query(_MELDUNG_SQL + "WHERE d.id = ?", (mid,), one=True)
    if not r:
        raise Abgelehnt("Mangelmeldung nicht gefunden.", 404)
    return r


def fotos_json(r):
    """Die Fotos einer Meldung – nur Vorschau- und Webfassung (ein Original gibt es nicht, F4)."""
    return [{"vorschau": katalog.bild_url(n, "thumb"), "web": katalog.bild_url(n, "web")}
            for n in json.loads(r["photos_json"] or "[]")]


def darf_name(item, user=None):
    """Sieht das Konto den Namen des Melders? Mit Grundrecht oder Prüfrecht am Artikel – auch der externe Prüfer mit
    befristeter Prüffreigabe (Entscheidung B vom 20.10.2026). Den Text der Meldung sieht jeder, der die Meldung sieht."""
    return rechte.darf_artikel("grund", item, user) or rechte.darf_artikel("pruefen", item, user)


def mangel_json(r, darf_grund):
    """Eine Meldung, überall in derselben Gestalt. darf_grund: darf_name(item) des anfragenden Kontos – Grundrecht oder
    Prüfrecht am Artikel; sonst kein Name des Melders."""
    erledigt = None
    if r["closed_at"]:
        erledigt = {"am": r["closed_at"], "pruefung": r["closed_inspection_id"],
                    "art": "aussonderung" if r.get("closed_kind") == "aussonderung" else "freipruefung"}
    return {"id": r["id"], "created_at": r["created_at"], "description": r["description"], "fotos": fotos_json(r),
            "melder": r["reporter_name"] if darf_grund else None, "offen": r["closed_at"] is None,
            "lock_before": r["lock_before"], "erledigt": erledigt}


def fuer_artikel(item, darf_grund):
    """Alle Meldungen eines Artikels: offene zuerst, dann erledigte – je neueste zuerst, höchstens LISTE_MAX."""
    rows = db.query(_MELDUNG_SQL + "WHERE d.item_id = ? ORDER BY d.closed_at IS NOT NULL, d.created_at DESC, d.id DESC "
                    "LIMIT ?", (item["id"], LISTE_MAX))
    return [mangel_json(r, darf_grund) for r in rows]


def offene_json(item, darf_grund):
    """Die offenen Meldungen eines Artikels (älteste zuerst) – für den Entwurf einer Prüfung (Häkchen je Meldung)."""
    rows = db.query(_MELDUNG_SQL + "WHERE d.item_id = ? AND d.closed_at IS NULL ORDER BY d.created_at, d.id",
                    (item["id"],))
    return [mangel_json(r, darf_grund) for r in rows]


def offene_ids(iid):
    """Kennungen der offenen Meldungen eines Artikels – frisch, auch mitten in einer Transaktion."""
    return {r["id"] for r in db.query("SELECT id FROM mat_defect_report WHERE item_id = ? AND closed_at IS NULL", (iid,))}


def offene_artikel():
    """Kennungen der Artikel im eigenen Bereich mit offener Meldung – für die Marke „Mangel“ in Listen. Einmal je
    Anfrage gerechnet (g.mat_mangel_offen); melden und erledigen verwerfen den Zwischenspeicher."""
    if "mat_mangel_offen" not in g:
        g.mat_mangel_offen = {r["item_id"] for r in db.query(
            "SELECT DISTINCT d.item_id FROM mat_defect_report d JOIN mat_item i ON i.id = d.item_id "
            f"WHERE d.closed_at IS NULL AND {rechte.artikel_filter('i')}")}
    return g.mat_mangel_offen


def offene_liste():
    """Für den Kasten „Gemeldete Mängel“ der Übersicht: offene Meldungen im eigenen Bereich, nach denen noch kein Prüfer
    geprüft hat (UNGEPRUEFT – nach „instandsetzen“ fällt die Zeile heraus, Marke und Banner bleiben), neueste zuerst,
    höchstens LISTE_MAX. Liefert (Zeilen, gesamt); den Namen des Melders je Zeile nur mit Grund- oder Prüfrecht am
    Artikel (darf_name)."""
    bedingung = f"WHERE {UNGEPRUEFT} AND {rechte.artikel_filter('i')}"
    gesamt = db.query(f"SELECT COUNT(*) AS n FROM mat_defect_report d JOIN mat_item i ON i.id = d.item_id {bedingung}",
                      one=True)["n"]
    rows = db.query("SELECT d.*, i.inventory_no, i.folder_id, i.origin_folder_id, i.lock_state, p.manufacturer, p.model, "
                    "p.description AS product_description FROM mat_defect_report d JOIN mat_item i ON i.id = d.item_id "
                    f"JOIN mat_product p ON p.id = i.product_id {bedingung} ORDER BY d.created_at DESC, d.id DESC "
                    "LIMIT ?", (LISTE_MAX,))
    out = []
    for r in rows:
        kurz = " ".join(r["description"].split())
        out.append({"id": r["id"], "item_id": r["item_id"], "inventory_no": r["inventory_no"],
                    "produkt": {"manufacturer": r["manufacturer"], "model": r["model"],
                                "description": r["product_description"] or ""},
                    "created_at": r["created_at"],
                    "kurz": kurz if len(kurz) <= KURZ_MAX else kurz[:KURZ_MAX - 1].rstrip() + "…",
                    "fotos": len(json.loads(r["photos_json"] or "[]")),
                    "melder": r["reporter_name"] if darf_name(r) else None})
    return out, gesamt


def ungeprueft(iid):
    """Gibt es am Artikel eine offene Meldung, nach der noch keine Prüfung abgeschlossen wurde?"""
    return bool(db.query(f"SELECT 1 FROM mat_defect_report d WHERE d.item_id = ? AND {UNGEPRUEFT} LIMIT 1", (iid,),
                         one=True))


def nur_gemeldet(iid):
    """Dasselbe – nur Meldungen, die gesperrt haben (lock_before = frei): Die Sperre stammt allein aus einer Meldung,
    und seitdem hat kein Prüfer den Artikel geprüft."""
    return bool(db.query(f"SELECT 1 FROM mat_defect_report d WHERE d.item_id = ? AND d.lock_before = 'frei' "
                         f"AND {UNGEPRUEFT} LIMIT 1", (iid,), one=True))


# --- Melden ---------------------------------------------------------------------------------------------------------

def _recht(item, user):
    """Das Recht am frisch gelesenen Artikel: „zugeordnet“ (PSA-Konto, auch ohne Modulstufe) oder „lesen“ (Grundrecht
    oder wirksame Prüffreigabe an der Heimat, nur mit Modulzugang) – sonst 404 wie für einen unbekannten Artikel."""
    if item["assigned_user_id"] is not None and item["assigned_user_id"] == user["id"] and psa.konto(user):
        return "zugeordnet"
    if rechte.zugang(user) and rechte.darf_artikel("lesen", item, user):
        return "lesen"
    raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)


def _pruefen(iid, user):
    """Was billig ist und vor den Fotos stehen muss – vor der Transaktion und in ihr noch einmal: Artikel und Recht
    (404), ausgesondert (409), eigene offene Meldung (409). Liefert (Artikel, Recht)."""
    item = bestand.artikel(iid)
    art = _recht(item, user)
    if item["lock_state"] == "ausgesondert":
        raise Abgelehnt(AUSGESONDERT, 409)
    eigen = db.query("SELECT created_at FROM mat_defect_report WHERE item_id = ? AND reporter_id = ? AND closed_at IS NULL "
                     "ORDER BY id LIMIT 1", (iid, user["id"]), one=True)
    if eigen:
        raise Abgelehnt(SCHON_GEMELDET.format(datum=_datum(eigen["created_at"])), 409)
    return item, art


def fotos_ablegen(dateien):
    """Wie Produktmeldungen (höchstens 3, Größe, HEIC, EXIF-Drehung über katalog.foto_ablegen) – aber jedes Original
    wird sofort nach seinem store_upload gelöscht (F4): Es trägt die EXIF-Daten samt Aufnahmeort. Web- und
    Vorschaufassung schreibt Pillow ohne EXIF. Scheitert ein Foto, gehen die schon abgelegten wieder."""
    dateien = [f for f in dateien or () if f and f.filename]        # Zahl und Größe prüft melden() vorher
    abgelegt = []
    try:
        for f in dateien:
            name = katalog.foto_ablegen(f)
            try:
                abgelegt.append(name)
            finally:
                _rm(os.path.join(katalog.medien_dir(), "orig", name))
    except BaseException:
        for n in abgelegt:
            delete_photo_files(katalog.medien_dir(), n)
        raise
    return abgelegt


def _dateien_pruefen(dateien):
    """Zahl, Art (nach der Endung) und Größe der Fotos – ohne ein Bild zu dekodieren."""
    from .meldung import _groesse
    if len(dateien) > MAX_FOTOS:
        raise Abgelehnt(f"Höchstens {MAX_FOTOS} Fotos.")
    for f in dateien:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in katalog.ALLOWED_EXT:
            raise Abgelehnt(f"Dateityp {ext or '(ohne Endung)'} ist kein Foto (JPEG, PNG, WebP, HEIC, TIFF).")
        if _groesse(f) > katalog.BILD_MAX_BYTES:
            raise Abgelehnt(f"„{f.filename}“ ist zu groß (höchstens {katalog.BILD_MAX_BYTES // (1024 * 1024)} MB je "
                            "Foto).")


def melden(iid, d, dateien=()):
    """POST /artikel/<iid>/mangel: Beschreibung (Pflicht) und 0 bis 3 Fotos. Reihenfolge: Beschreibung, Zahl, Art und
    Größe der Fotos (400) – Vorprüfung ohne Sperre (404, 409) – Fotos ablegen – in der Transaktion noch einmal prüfen,
    Meldung schreiben und sperren (ein Journaleintrag „mangel_gemeldet“) – nach dem Commit die Mails. Liefert
    (Kennung, diese Meldung hat gesperrt, eine Mail an Materialwart, Prüfer oder Verwaltung ging an den Versand)."""
    from . import pruefung
    u = current_user()
    beschreibung = text(d, "beschreibung", "Beschreibung des Mangels", TEXT_MAX, pflicht=True, einzeilig=False)
    dateien = [f for f in dateien or () if f and f.filename]
    _dateien_pruefen(dateien)
    _pruefen(iid, u)
    fotos = fotos_ablegen(dateien)
    try:
        with db.transaction(sofort=True):
            item, _ = _pruefen(iid, u)            # inzwischen verschoben, ausgesondert, entzogen, schon gemeldet?
            mid = db.execute(
                "INSERT INTO mat_defect_report (item_id, description, photos_json, reporter_id, reporter_name, "
                "lock_before, created_at) VALUES (?,?,?,?,?,?,?)",
                (iid, beschreibung, json.dumps(fotos), u["id"], (u["name"] or "").strip() or OHNE_NAMEN,
                 item["lock_state"], db.now()))
            gesperrt = item["lock_state"] == "frei"
            if gesperrt:
                pruefung._sperren(item, "gesperrt", f"Mangel gemeldet am {heute().strftime('%d.%m.%Y')}",
                                  aktion="mangel_gemeldet", zusatz={"mangel": mid})
            else:
                journal.eintragen("item", iid, "mangel_gemeldet", None, {"mangel": mid})
    except BaseException:
        for n in fotos:
            delete_photo_files(katalog.medien_dir(), n)
        raise
    g.pop("mat_mangel_offen", None)
    g.pop("mat_psa_kopf", None)
    return mid, gesperrt, _benachrichtigen(mid)


def erledigen(iid, pruefung_id):
    """Alle offenen Meldungen des Artikels erledigen – durch diese Freiprüfung oder Aussonderung, in der Transaktion
    des Aufrufers. Ein UPDATE für beide Spalten (CHECK); der Trigger mat_defect_erledigt_durch verlangt eine
    abgeschlossene Prüfung desselben Artikels. Liefert die Zahl."""
    n = db.execute_zeilen("UPDATE mat_defect_report SET closed_inspection_id = ?, closed_at = ? WHERE item_id = ? "
                          "AND closed_at IS NULL", (pruefung_id, db.now(), iid))
    g.pop("mat_mangel_offen", None)
    return n


# --- Mails ----------------------------------------------------------------------------------------------------------

def _pruefer_von(h, demo):
    """Konten mit gültiger Prüffreigabe an h oder darüber, die dort heute wirkt (Qualifikation, dauerhafte nur mit
    Grundrecht – rechte.sicht), aktiv und zulässig (Adresse, keine DEMO-Adresse außer bei DEMO, Modulzugang)."""
    rows = db.query(
        "WITH RECURSIVE kette(id) AS (SELECT ? UNION SELECT f.parent_id FROM mat_folder f JOIN kette k ON f.id = k.id "
        "WHERE f.parent_id IS NOT NULL) SELECT DISTINCT user_id FROM mat_folder_grant WHERE permission = 'pruefen' "
        "AND folder_id IN (SELECT id FROM kette) AND (valid_until IS NULL OR valid_until >= ?) ORDER BY user_id",
        (h, heute().isoformat()))
    konten = erinnerung._konten(r["user_id"] for r in rows)
    return [konten[r["user_id"]] for r in rows if r["user_id"] in konten
            and erinnerung._zulaessig(konten[r["user_id"]], demo) and rechte.sicht(konten[r["user_id"]]).darf("pruefen", h)]


def empfaenger(item, melder_id, demo=False):
    """Wer die Mail zu einer Meldung bekommt – [(Konto, warum, mit_name)]: die Verwalter der Heimat
    (erinnerung.ordnerverwalter – Material- und Plattform-Verwaltung eingeschlossen, wenn dort eingetragen), ohne sie
    die Material-, ohne diese die Plattform-Verwaltung; dazu die Prüfer mit wirksamer Prüffreigabe dort (auch weit
    oben – anders als beim Rückruf, Entscheidung 4). Jeder muss den Artikel lesen dürfen; den Namen des Melders bekommt,
    wer ein Grund- oder Prüfrecht hat (darf_name). Zuletzt die zugeordnete Person, wenn ein anderer meldet (warum „zugeordnet“, ohne
    Namen) – ohne Modulstufe und ohne Blick auf die Abmeldung der Erinnerungen. Nie der Melder; jede Adresse einmal
    (wer verwaltet oder prüft, bekommt nur die volle Mail)."""
    h = bestand.heimat(item)
    ids = erinnerung.ordnerverwalter(h)
    konten = erinnerung._konten(ids)
    kandidaten = [(konten[i], "verwalter") for i in ids if i in konten and erinnerung._zulaessig(konten[i], demo)]
    if not kandidaten:
        verwaltung, stelle = erinnerung._verwaltung({"demo": demo})
        kandidaten = [(u, stelle) for u in verwaltung]
    kandidaten += [(u, "pruefer") for u in _pruefer_von(h, demo)]
    out, adressen, gesehen = [], set(), set()
    for u, warum in kandidaten:
        adr = (u.get("email") or "").strip().casefold()
        if u["id"] == melder_id or u["id"] in gesehen or not adr or adr in adressen:
            continue
        if not rechte.darf_artikel("lesen", item, u):
            continue
        gesehen.add(u["id"])
        adressen.add(adr)
        out.append((u, warum, darf_name(item, u)))
    z = item["assigned_user_id"]
    if z and z != melder_id and z not in gesehen:
        u = erinnerung._konten([z]).get(z)
        adr = ((u or {}).get("email") or "").strip().casefold()
        if u and psa.konto(u) and erinnerung._erreichbar(u, demo) and adr not in adressen:
            out.append((u, "zugeordnet", False))
    return out


def _produkt_kurz(p):
    return " ".join(t for t in (p["manufacturer"], p["model"]) if t)


def _mailtext(r, item, produkt, warum, mit_name):
    """Betreff und Text an Materialwarte, Prüfer und Verwaltung."""
    basis = (current_app.config.get("BASE_URL") or "").rstrip("/")
    site = current_app.config.get("SITE_NAME") or "strömis.de"
    zeit = _ortszeit(r["created_at"])
    wann = f"am {zeit.strftime('%d.%m.%Y')} um {zeit.strftime('%H:%M')}"
    wer = r["reporter_name"] if mit_name else "Jemand mit Zugriff auf den Artikel"
    gesperrt = r["lock_before"] == "frei"
    gl = bestand.gliederung_von(item["folder_id"])
    zeilen = [f"{wer} hat {wann} einen Mangel gemeldet."]
    if gesperrt:
        zeilen[0] += (f" Der Artikel ist damit gesperrt und liegt in „Gesperrt“ der Gliederung "
                      f"{gl['name'] if gl else '(ohne Gliederung)'}. Freigeben kann ihn nur ein Prüfer mit einer "
                      "Prüfung („einsatzbereit“).")
    else:
        grund = f" ({item['lock_reason']})" if item["lock_reason"] else ""
        zeilen[0] += f" Er war schon gesperrt{grund}; die Sperre bleibt."
    zeilen.append("Bitte sorg dafür, dass er aus Fahrzeug oder Lager genommen wird und zum Materialwart kommt.")
    n = len(json.loads(r["photos_json"] or "[]"))
    zeilen += ["",
               f"Artikel:    {item['inventory_no']} – {katalog.produktname(produkt)}, SN {item['serial_no']}",
               f"Ordner:     {bestand._pfad_text(bestand.heimat(item))}",
               f"Fotos:      {n}" + (" (am Artikel)" if n else ""),
               "", "Beschreibung:", r["description"], "",
               f"Artikel ansehen: {basis}/material/artikel/{item['id']}", "",
               f"Du bekommst diese Mail, {WARUM[warum]}"]
    betreff = (f"{site} – Mangel gemeldet: {item['inventory_no']} {_produkt_kurz(produkt)} – "
               + ("gesperrt" if gesperrt else "war schon gesperrt"))
    return " ".join(betreff.split()), "\n".join(zeilen) + "\n"


def _mailtext_zugeordnet(item, produkt, r, u):
    """Betreff und Text an die zugeordnete Person – ohne Melder, Beschreibung, Fotos und Ordner: nicht mehr, als „Meine
    PSA“ ihr zeigt."""
    basis = (current_app.config.get("BASE_URL") or "").rstrip("/")
    site = current_app.config.get("SITE_NAME") or "strömis.de"
    zeilen = [f"Hallo {(u['name'] or '').strip()},", "",
              f"an deiner Ausrüstung {item['inventory_no']} – {katalog.produktname(produkt)}, SN {item['serial_no']} "
              f"wurde am {_datum(r['created_at'])} ein Mangel gemeldet. Sie ist damit gesperrt.", "",
              "Bitte nicht mehr verwenden: leg sie sofort beiseite und gib sie deinem Materialwart. Freigeben kann sie "
              "nur ein Prüfer nach einer Prüfung.", "",
              f"Deine PSA: {basis}/material/meine-psa/{item['id']}", "",
              "Du bekommst diese Mail, weil dir diese Ausrüstung im Modul Material zugeordnet ist. Sie kommt einmal je "
              "Meldung und lässt sich nicht abbestellen, weil sie deine Sicherheit betrifft."]
    betreff = f"{site} – Deine PSA {item['inventory_no']} ist gesperrt – nicht verwenden"
    return " ".join(betreff.split()), "\n".join(zeilen) + "\n"


def _benachrichtigen(mid):
    """Nach dem Commit: Mails vorbereiten und neben der Anfrage verschicken. Bei einem DEMO-Artikel oder unter der
    Umgebungssperre geht nichts hinaus – Betreff und Text stehen dann im Log (wie send_mail ohne Mailserver). Liefert,
    ob mindestens eine Mail an Materialwart, Prüfer oder Verwaltung an den Versand ging (die an die zugeordnete Person
    zählt nicht: der Toast spricht vom Materialwart)."""
    r = meldung(mid)
    item = bestand.artikel(r["item_id"])
    produkt = katalog.produkt(item["product_id"])
    demo = bestand.ist_demo(item["id"])
    mails = []
    for u, warum, mit_name in empfaenger(item, r["reporter_id"], demo=demo):
        if warum == "zugeordnet":
            betreff, inhalt = _mailtext_zugeordnet(item, produkt, r, u)
        else:
            betreff, inhalt = _mailtext(r, item, produkt, warum, mit_name)
        mails.append((u["email"].strip(), f"[DEMO] {betreff}" if demo else betreff, inhalt, warum))
    if not mails:
        return False
    still = "DEMO-Artikel" if demo else "Umgebungssperre" if erinnerung.gesperrt() else None
    if still:
        for an, betreff, inhalt, _ in mails:
            current_app.logger.warning("Mangel %s: Mail nicht verschickt (%s) – an %s\nBetreff: %s\n%s", mid, still, an,
                                       betreff, inhalt)
        return False
    HINTERGRUND(_versenden, mid, [(an, betreff, inhalt) for an, betreff, inhalt, _ in mails])
    return any(warum != "zugeordnet" for *_, warum in mails)


def _versenden(mid, mails):
    """Läuft im Hintergrund (eigener App-Kontext). Jede Mail einzeln; eine Adresse, an der es scheitert, hält die
    anderen nicht auf. Kein Zähler an der Meldung – ob der Mailserver annahm, steht im Log."""
    for an, betreff, inhalt in mails:
        try:
            if not send_mail(an, betreff, inhalt):
                current_app.logger.error("Mangel %s: Mail an %s gescheitert", mid, an)
        except Exception as exc:                     # send_mail wirft nicht – eine Ausnahme hält trotzdem nichts auf
            current_app.logger.error("Mangel %s: Mail an %s gescheitert: %s", mid, an, exc)
