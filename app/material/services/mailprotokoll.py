"""Versand-Wrapper des Moduls mit Fehlerprotokoll (Phase 4 · Lieferung 1): Jede Modul-Mail – Erinnerung, Mangel,
Änderungsantrag, Produktmeldung, Rückruf – geht über senden(). Scheitert sie, steht eine Zeile in mat_mail_fehler, die
die Verwaltung auf der Übersicht sieht und abhakt (routes_mailfehler.py). Erfolge werden nicht protokolliert:
Erinnerungen stehen im Erinnerungslog, Rückrufe zählen in mat_recall.

Stille – einheitlich hier, nicht in den Diensten (Entscheidung Nr. 6 vom 22.10.2026, gilt damit auch für Rückruf- und
Produktmeldungs-Mails): Ohne Mailserver (SMTP_HOST leer), unter der Umgebungssperre (erinnerung.gesperrt, dev), bei
einem DEMO-Artikel oder an eine DEMO-Adresse (…@….invalid) geht nichts hinaus und es entsteht keine Zeile – nur eine
Logzeile mit Grund, Betreff und Text (wie send_mail ohne Mailserver), Rückgabe False. Die Dienste fragen still() nur
noch für ihre Quittung („mail“: false).

Zwei getrennte Schritte, jeder in eigenem try: (1) der Versand über die Nahtstelle versand (= mailer.versand; Tests
ersetzen genau diese und liefern (ok, meldung)) – eine Ausnahme zählt als Fehlschlag der Klasse „ausnahme“; (2) die
Protokollzeile: Reinigung der Meldung, Kontoverweis (journal.konto_ref schreibt ihn, wenn er fehlt) und INSERT in einer
eigenen kurzen Transaktion. Schritt 2 wirft nie – die Mailschleife der übrigen Empfänger läuft weiter –, und er läuft
nie innerhalb einer äußeren Transaktion (g.tx_depth): Die Dienste rufen senden erst nach ihrem Commit, meist im
Hintergrund-Thread (auth._im_hintergrund, eigener App-Kontext).

Die Zeile trägt nie eine Adresse: Die Serverantwort nennt den abgewiesenen Empfänger, oft in spitzen Klammern, bei
Verbindungsfehlern Host und Port des Mailservers und bei einer abgelehnten Anmeldung oft den Anmeldenamen (Exim:
„535 … (set_id=<SMTP_USER>)“). reinigen() ersetzt die Empfängeradresse, den Anmeldenamen, jede weitere Adresse,
„<…@…>“ und „Host:Port“ durch Platzhalter und kürzt auf MAILMELDUNG_MAX; der Betreff läuft durch dieselbe Reinigung
(Rückruf-Titel und Produktmeldungen sind freier Text) und wird auf MAILBETREFF_MAX gekürzt. Die CHECKs
instr(meldung, '@') = 0 und instr(betreff, '@') = 0 in der Tabelle sind das Netz dahinter. Der Empfänger steht als
Kontoverweis (users.mat_ref) und Rolle da; die Oberfläche löst den Verweis zum Namen auf (journal.konto_namen –
„(gelöschtes Konto)“ ohne Konto). Den Bezug einer Zeile liefert uebersicht() als Weg ins Modul (_bezuege: Artikel bzw.
Mangelmeldung → Artikel, Rückruf → Produkt, Ordner und Erinnerung → Ordner, Antrag und Produktmeldung →
Meldungen-Seite), aus Kennungen gebaut – nie aus Datenbanktexten.

Einzelmails (Mangel, Änderungsantrag, Produktmeldung) tragen als folder_id die Heimat des Artikels bzw. den Ordner der
Meldung: Die Freigabe „verwalten“ gilt nach unten – wer nur einen Unterordner verwaltet, sieht den Fehlschlag seiner Mail
und hakt ihn ab, der Gliederungs-Verwalter ebenso. Sammelmails ohne einen Ordner (Erinnerung, Rückruf: Artikel mehrerer
Gliederungen in einer Mail) bekommen je betroffener Gliederung eine Zeile mit folder_id = Gliederung (Entscheidung
Nr. 5); dafür nimmt senden für folder_id auch eine Menge von Kennungen. Ihre Betreffe nennen nur Zahlen bzw. Produkt
und Titel – nichts aus einer fremden Gliederung.

Nachholen: Gelingt später eine Erinnerungsmail an dasselbe Konto, schließt senden dessen offene Erinnerungs-Fehler mit
erledigt_von_name „nachgeholt“ – der nächste Lauf wiederholt, was scheiterte (erinnerung.py), die Zeile wäre sonst
überholt. Pflege: Zeilen älter als 13 Monate, erledigte älter als 3 Monate und Waisen (Kontoverweis ohne Konto) löscht
aufraeumen() im Tageslauf und beim Start; loeschung.konto_loeschen_vorbereiten nimmt die Zeilen des Kontos mit.
Arbeitsdaten, kein Nachweis."""
import re

from flask import current_app, g

from ... import db, mailer
from ..models import MAILARTEN, MAILBETREFF_MAX, MAILBEZUEGE, MAILKLASSEN, MAILMELDUNG_MAX, MAILROLLEN
from . import Abgelehnt, heute
from . import erinnerung, journal, rechte
from .interval import plus_monate

# Die Nahtstelle: Tests ersetzen genau diese Funktion (liefert (ok, meldung) wie mailer.versand).
versand = mailer.versand


def mailserver_da():
    return erinnerung.smtp_da()


# Ist ein Mailserver eingerichtet? Tests, die versand ersetzen, setzen hier lambda: True (eine eigene Funktion statt
# erinnerung.smtp_da selbst: die Module laden sich gegenseitig).
MAILSERVER = mailserver_da

AUFBEWAHRUNG_MONATE = 13                            # wie das Erinnerungslog
ERLEDIGT_MONATE = 3
NACHGEHOLT = "nachgeholt"                           # erledigt_von_name einer später gelungenen Erinnerung
LISTE_MAX = 20                                      # Zeilen im Kasten der Übersicht
LISTE_ALLE = 200                                    # Zeilen hinter „Weitere anzeigen“ (GET /api/material/mailfehler)
ADRESSE, MAILSERVER_TEXT, ANMELDUNG_TEXT = "[Adresse]", "[Mailserver]", "[Anmeldename]"
ART_TEXT = {"erinnerung": "Erinnerung", "mangel": "Mangel", "antrag": "Änderungsantrag", "meldung": "Produktmeldung",
            "rueckruf": "Rückruf"}
# Zeilen dieser Rollen sieht nur die Material-Verwaltung: Rückfall-Empfänger und Einzelpersonen, die ein Zweig-Verwalter
# nichts angehen (Entwurf B4).
NUR_VERWALTUNG = ("verwaltung", "antragsteller", "melder")
NUR_VERWALTER = "Mailfehler haken Materialwarte und die Material-Verwaltung ab."

_ADRESSE = re.compile(r'[^\s<>@"]+@[^\s<>@"]+')
_SPITZ = re.compile(r"<[^<>]*@[^<>]*>")


# --- Stille ---------------------------------------------------------------------------------------------------------

def still(demo=False):
    """Warum keine Modul-Mail hinausgeht – oder None: DEMO-Artikel, Umgebungssperre, kein Mailserver. Dieselbe Antwort
    für die Quittung der Dienste und für senden()."""
    return ("DEMO-Artikel" if demo else "Umgebungssperre" if erinnerung.gesperrt()
            else "kein Mailserver" if not MAILSERVER() else None)


# --- Reinigung ------------------------------------------------------------------------------------------------------

def _saeubern(t, an=None):
    """Einzeilig, ohne Adressen, ohne Anmeldenamen und ohne Mailserver – für Meldung und Betreff: erst die
    Empfängeradresse (ohne Rücksicht auf Groß- und Kleinschreibung), dann der Anmeldename aus der Konfiguration (als
    ganzes Wort; enthält er ein „@“, ist er eine Adresse und fällt spätestens im nächsten Schritt), dann „<…@…>“ und
    jede weitere Adresse, dann „Host:Port“ und der Host. Ein „@“, das danach noch steht, wird ebenfalls ersetzt – die
    Tabelle nimmt keins an."""
    t = " ".join(str(t or "").split())
    adr = (an or "").strip()
    if adr:
        t = re.sub(re.escape(adr), ADRESSE, t, flags=re.IGNORECASE)
    cfg = current_app.config
    nutzer = (cfg.get("SMTP_USER") or "").strip()
    if nutzer:
        t = re.sub(rf"(?<![\w.@-]){re.escape(nutzer)}(?![\w.@-])", ANMELDUNG_TEXT, t, flags=re.IGNORECASE)
    t = _SPITZ.sub(ADRESSE, t)
    t = _ADRESSE.sub(ADRESSE, t)
    host = (cfg.get("SMTP_HOST") or "").strip()
    if host:
        port = int(cfg.get("SMTP_PORT") or (465 if cfg.get("SMTP_SSL") else 587))
        t = re.sub(re.escape(f"{host}:{port}"), MAILSERVER_TEXT, t, flags=re.IGNORECASE)
        t = re.sub(re.escape(host), MAILSERVER_TEXT, t, flags=re.IGNORECASE)
    return t.replace("@", ADRESSE)


def reinigen(meldung, an=None):
    """Die Serverantwort gesäubert (_saeubern), höchstens MAILMELDUNG_MAX Zeichen."""
    return _saeubern(meldung, an)[:MAILMELDUNG_MAX]


def _betreff(betreff, an=None):
    """Der Betreff gesäubert wie die Meldung (Rückruf-Titel, Hersteller und Modell sind freier Text), höchstens
    MAILBETREFF_MAX Zeichen."""
    return _saeubern(betreff, an)[:MAILBETREFF_MAX]


# --- Senden ---------------------------------------------------------------------------------------------------------

def senden(an, betreff, text, *, art, konto_id, rolle, bezug_art="none", bezug_id=None, folder_id=None, demo=False):
    """Eine Mail verschicken und einen Fehlschlag protokollieren. Liefert, ob der Mailserver sie angenommen hat.
    art: aus models.MAILARTEN; konto_id: das Konto des Empfängers (Kontoverweis); rolle: aus MAILROLLEN; bezug_art und
    bezug_id: der Gegenstand (Artikel, Meldung, Antrag, Produktmeldung, Rückruf – „none“ für die Erinnerung);
    folder_id: der Ordner, dessen Verwalter die Zeile sehen (Einzelmail: die Heimat) – eine Kennung, None oder eine
    Menge von Kennungen (Sammelmail: je Gliederung eine Zeile); demo: der Gegenstand ist DEMO (dann still). Wirft nur
    bei einer unbekannten Art, Rolle oder Bezugsart (Programmfehler) – Versand und Protokoll werfen nie."""
    if art not in MAILARTEN or rolle not in MAILROLLEN or bezug_art not in MAILBEZUEGE:
        raise ValueError(f"Mailprotokoll: unbekannt – art {art!r}, rolle {rolle!r}, bezug {bezug_art!r}")
    grund = still(demo or erinnerung.demo_adresse(an))
    if grund == "DEMO-Artikel" and not demo:
        grund = "DEMO-Adresse"
    if grund:
        current_app.logger.warning("%s: Mail nicht verschickt (%s) – an %s\nBetreff: %s\n%s", ART_TEXT[art], grund, an,
                                   betreff, text)
        return False
    try:
        ok, meldung = versand(an, betreff, text)
        klasse = None if ok else mailer.klasse(meldung)
    except Exception as exc:                         # versand wirft nicht – ein Ersatz in Tests oder ein Fehler darin doch
        ok, meldung, klasse = False, f"Ausnahme beim Versand: {exc}", "ausnahme"
    if ok:
        current_app.logger.info("%s: Mail an Konto %s – %s", ART_TEXT[art], konto_id, meldung)
        if art == "erinnerung":
            _nachgeholt(konto_id)
        return True
    current_app.logger.error("%s: Mail an Konto %s ging nicht hinaus – %s", ART_TEXT[art], konto_id, meldung)
    try:
        _protokollieren(an, betreff, meldung, klasse, art=art, konto_id=konto_id, rolle=rolle, bezug_art=bezug_art,
                        bezug_id=bezug_id, folder_id=folder_id)
    except Exception as exc:
        current_app.logger.exception("Mailprotokoll: Zeile zu %s (Konto %s) nicht geschrieben – %s", art, konto_id, exc)
    return False


def _protokollieren(an, betreff, meldung, klasse, *, art, konto_id, rolle, bezug_art, bezug_id, folder_id):
    """Die Zeile(n) zu einem Fehlschlag – in eigener kurzer Transaktion, nie in einer äußeren (dann nur eine Logzeile:
    die Dienste rufen senden nach dem Commit). Je Ordner aus folder_id eine Zeile; ohne Konto keine."""
    if getattr(g, "tx_depth", 0):
        current_app.logger.error("Mailprotokoll: senden innerhalb einer Transaktion gerufen – Zeile zu %s nicht "
                                 "geschrieben.", art)
        return
    if klasse not in MAILKLASSEN:
        klasse = "sonstiges"
    text = reinigen(meldung, an)
    ordner = sorted({int(f) for f in folder_id if f is not None}) if isinstance(folder_id, (set, frozenset, list, tuple)) \
        else [folder_id]
    with db.transaction():
        ref = journal.konto_ref(konto_id)["ref"] if konto_id else None
        if not ref:
            current_app.logger.error("Mailprotokoll: kein Konto %s – Zeile zu %s nicht geschrieben.", konto_id, art)
            return
        jetzt = db.now()
        for fid in ordner or [None]:
            # Der Ordner kann inzwischen gelöscht sein (Fremdschlüssel): dann ohne Ordner.
            if fid is not None and not db.query("SELECT 1 FROM mat_folder WHERE id = ?", (fid,), one=True):
                fid = None
            db.execute("INSERT INTO mat_mail_fehler (art, klasse, bezug_art, bezug_id, folder_id, konto_ref, rolle, "
                       "betreff, meldung, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (art, klasse, bezug_art, bezug_id, fid, ref, rolle, _betreff(betreff, an), text, jetzt))


def _nachgeholt(konto_id):
    """Offene Erinnerungs-Fehler dieses Kontos schließen – eine Erinnerung ist gerade angenommen worden. Ein Fehler hier
    hält nichts auf."""
    try:
        db.execute("UPDATE mat_mail_fehler SET erledigt_at = ?, erledigt_von_name = ? WHERE art = 'erinnerung' "
                   "AND erledigt_at IS NULL AND konto_ref = (SELECT mat_ref FROM users WHERE id = ?)",
                   (db.now(), NACHGEHOLT, konto_id))
    except Exception as exc:
        current_app.logger.error("Mailprotokoll: Nachholen für Konto %s nicht vermerkt – %s", konto_id, exc)


# --- Sicht und Erledigen ----------------------------------------------------------------------------------------

def sichtfilter(alias="m", user=None):
    """SQL-Bedingung: welche Zeilen das Konto sieht und abhakt. Material- und Plattform-Verwaltung alles; wer einen Zweig
    verwaltet, die Zeilen mit Ordner in seiner Sicht (rechte.ordner_filter mit verwalten – nach unten vererbt) – ohne die Rollen, die nur
    die Verwaltung angehen (NUR_VERWALTUNG); sonst nichts."""
    if not alias.isidentifier():
        raise ValueError(alias)
    s = rechte.sicht(user)
    if s.alles:
        return "1"
    ordner = rechte.ordner_filter(f"{alias}.folder_id", "verwalten", user)
    if ordner == "0":
        return "0"
    rollen = ",".join(f"'{r}'" for r in NUR_VERWALTUNG)
    return f"({alias}.folder_id IS NOT NULL AND {ordner} AND {alias}.rolle NOT IN ({rollen}))"


# Der Bezug einer Zeile als Weg ins Modul (nur Modul-Routen, aus Kennungen gebaut – nie aus Datenbanktexten).
BEZUG_TEXT = {"item": "Artikel", "folder": "Ordner", "report": "Mangelmeldung", "change": "Änderungsantrag",
              "request": "Produktmeldung", "recall": "Rückruf", "none": ""}
BEZUG_PFAD = {"change": "/material/bestand/antraege", "request": "/material/katalog/meldungen"}


def _nach_id(sql, ids):
    """Zeilen zu einer Menge von Kennungen – oder nichts, wenn die Menge leer ist."""
    ids = sorted(i for i in ids if i is not None)
    if not ids:
        return []
    return db.query(sql.format(ids=",".join("?" * len(ids))), tuple(ids))


def _bezuege(rows):
    """Je Zeile {text, pfad}: Artikel und Mangelmeldung führen zum Artikel (mit Inventarnummer), Ordner und Erinnerung
    zum Ordner bzw. zur Gliederung (mit Namen), der Rückruf zum Produkt, der Antrag zur Liste „Änderungsanträge“ im
    Bestand, die Produktmeldung zur Meldungen-Seite.
    Was es nicht mehr gibt (gelöschter Artikel, Ordner, Rückruf), bleibt Text ohne Weg. Höchstens vier Abfragen für
    alle Zeilen – der Kasten zeigt LISTE_MAX davon."""
    meldung_artikel = {z["id"]: z["item_id"] for z in _nach_id(
        "SELECT id, item_id FROM mat_defect_report WHERE id IN ({ids})",
        {r["bezug_id"] for r in rows if r["bezug_art"] == "report"})}
    artikel = {z["id"]: z["inventory_no"] for z in _nach_id(
        "SELECT id, inventory_no FROM mat_item WHERE id IN ({ids})",
        {r["bezug_id"] for r in rows if r["bezug_art"] == "item"} | set(meldung_artikel.values()))}
    produkte = {z["id"]: z["product_id"] for z in _nach_id(
        "SELECT id, product_id FROM mat_recall WHERE id IN ({ids})",
        {r["bezug_id"] for r in rows if r["bezug_art"] == "recall"})}
    ordner = {z["id"]: z["name"] for z in _nach_id(
        "SELECT id, name FROM mat_folder WHERE id IN ({ids})",
        {r["bezug_id"] for r in rows if r["bezug_art"] == "folder"} | {r["folder_id"] for r in rows})}
    out = {}
    for r in rows:
        art, bid = r["bezug_art"], r["bezug_id"]
        text, pfad = BEZUG_TEXT.get(art, ""), BEZUG_PFAD.get(art)
        iid = meldung_artikel.get(bid) if art == "report" else bid if art == "item" else None
        if iid is not None and iid in artikel:
            text, pfad = f"{text} {artikel[iid]}", f"/material/artikel/{int(iid)}"
        elif art == "recall" and bid in produkte:
            pfad = f"/material/katalog/produkt/{int(produkte[bid])}"
        elif art in ("folder", "none"):
            fid = bid if art == "folder" else r["folder_id"]
            if fid in ordner:
                text, pfad = ordner[fid], f"/material/ordner/{int(fid)}"
        out[r["id"]] = {"text": text, "pfad": pfad}
    return out


def _json(r, namen, bezuege):
    return {"id": r["id"], "created_at": r["created_at"], "art": r["art"], "art_text": ART_TEXT.get(r["art"], r["art"]),
            "klasse": r["klasse"], "empfaenger": namen[r["konto_ref"]], "rolle": r["rolle"],
            "bezug_art": r["bezug_art"], "bezug_id": r["bezug_id"], "folder_id": r["folder_id"], "betreff": r["betreff"],
            "meldung": r["meldung"], "erledigt_at": r["erledigt_at"], "erledigt_von_name": r["erledigt_von_name"],
            "bezug": bezuege.get(r["id"], {"text": "", "pfad": None})}


def uebersicht(user=None):
    """Der Block „mailfehler“ für GET /api/material/start: Zahl der offenen Zeilen in der Sicht, die letzten LISTE_MAX
    (Empfänger als Name) und – nur für die Verwaltung – ob ein Mailserver fehlt (dann geht keine Modul-Mail hinaus).
    None, wenn es nichts zu zeigen gibt: keine Zeile in der Sicht und (für die Verwaltung) ein Mailserver da."""
    filt = sichtfilter("m", user)
    verwaltung = rechte.sicht(user).alles
    kein_server = verwaltung and not MAILSERVER()
    if filt == "0":
        return {"offen": 0, "zeilen": [], "kein_mailserver": True, "alle": True} if kein_server else None
    offen, zeilen = _offene(filt, LISTE_MAX)
    if not zeilen and not kein_server:
        return None
    return {"offen": offen, "zeilen": zeilen, "kein_mailserver": kein_server, "alle": verwaltung}


def _offene(filt, grenze):
    """(Zahl der offenen Zeilen, die neuesten grenze davon als JSON) unter der Sichtbedingung filt."""
    offen = db.query(f"SELECT COUNT(*) AS n FROM mat_mail_fehler m WHERE m.erledigt_at IS NULL AND {filt}",
                     one=True)["n"]
    rows = db.query(f"SELECT m.* FROM mat_mail_fehler m WHERE m.erledigt_at IS NULL AND {filt} "
                    f"ORDER BY m.created_at DESC, m.id DESC LIMIT ?", (grenze,))
    namen = journal.konto_namen(r["konto_ref"] for r in rows)
    bezuege = _bezuege(rows)
    return offen, [_json(r, namen, bezuege) for r in rows]


def liste(user=None):
    """„Weitere anzeigen“ im Kasten: die neuesten LISTE_ALLE offenen Zeilen der Sicht und ihre Zahl – wer keine Sicht
    hat (nirgends verwaltet), 403 wie bei „Alle erledigt“."""
    filt = sichtfilter("m", user)
    if filt == "0":
        raise Abgelehnt(NUR_VERWALTER, 403)
    offen, zeilen = _offene(filt, LISTE_ALLE)
    return {"offen": offen, "zeilen": zeilen, "grenze": LISTE_ALLE}


def zeile(fid, user=None):
    """Eine Zeile in der Sicht des Kontos – oder None (unbekannt wie unsichtbar)."""
    return db.query(f"SELECT m.* FROM mat_mail_fehler m WHERE m.id = ? AND {sichtfilter('m', user)}", (fid,), one=True)


def erledigen(fid, name):
    """Eine Zeile abhaken – nur in der eigenen Sicht (sonst None); schon erledigt bleibt, wie es ist (idempotent). Liefert
    die Zeile danach als JSON."""
    r = zeile(fid)
    if not r:
        return None
    db.execute("UPDATE mat_mail_fehler SET erledigt_at = ?, erledigt_von_name = ? WHERE id = ? AND erledigt_at IS NULL",
               (db.now(), name, fid))
    r = zeile(fid)
    return _json(r, journal.konto_namen([r["konto_ref"]]), _bezuege([r]))


def alle_erledigen(name):
    """Alle offenen Zeilen der eigenen Sicht abhaken – wer keine Sicht hat (nirgends verwaltet), 403. Liefert die Zahl."""
    filt = sichtfilter("m")
    if filt == "0":
        raise Abgelehnt(NUR_VERWALTER, 403)
    return db.execute_zeilen(f"UPDATE mat_mail_fehler SET erledigt_at = ?, erledigt_von_name = ? WHERE erledigt_at IS NULL "
                             f"AND id IN (SELECT m.id FROM mat_mail_fehler m WHERE {filt})", (db.now(), name))


# --- Pflege ---------------------------------------------------------------------------------------------------------

_ALT = "DELETE FROM mat_mail_fehler WHERE created_at < ?"
_ERLEDIGT = "DELETE FROM mat_mail_fehler WHERE erledigt_at IS NOT NULL AND erledigt_at < ?"
_WAISEN = "DELETE FROM mat_mail_fehler WHERE konto_ref NOT IN (SELECT mat_ref FROM users WHERE mat_ref IS NOT NULL)"


def _grenzen():
    tag = heute()
    return plus_monate(tag, -AUFBEWAHRUNG_MONATE).isoformat(), plus_monate(tag, -ERLEDIGT_MONATE).isoformat()


def aufraeumen(conn=None):
    """Zeilen älter als 13 Monate, erledigte älter als 3 Monate und Waisen (Kontoverweis ohne Konto) löschen – im
    Tageslauf (erinnerung.tageslauf) und beim Start (schema_anmelden, mit conn: die Verbindung des Startlaufs; vor
    Schritt 19 gibt es die Tabelle nicht – dann nichts). Liefert {"alt", "erledigt", "waisen"}."""
    alt, erledigt = _grenzen()
    if conn is not None:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'mat_mail_fehler'").fetchone():
            return {"alt": 0, "erledigt": 0, "waisen": 0}
        a = conn.execute(_ALT, (alt,)).rowcount
        e = conn.execute(_ERLEDIGT, (erledigt,)).rowcount
        w = conn.execute(_WAISEN).rowcount
        conn.commit()
        return {"alt": a, "erledigt": e, "waisen": w}
    with db.transaction():
        a = db.execute_zeilen(_ALT, (alt,))
        e = db.execute_zeilen(_ERLEDIGT, (erledigt,))
        w = db.execute_zeilen(_WAISEN)
    return {"alt": a, "erledigt": e, "waisen": w}


def konto_loeschen(uid):
    """Die Zeilen eines Kontos – aus loeschung.konto_loeschen_vorbereiten, vor dem Löschen der Kontozeile."""
    db.execute("DELETE FROM mat_mail_fehler WHERE konto_ref = (SELECT mat_ref FROM users WHERE id = ?)", (uid,))
