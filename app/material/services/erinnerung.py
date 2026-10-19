"""Erinnerungen (Phase 2 · Lieferung 2): eine Sammelmail am Morgen an die Materialwarte – zu Prüffristen, zum Lebensende
und zu Freigaben, die bald ablaufen.

Ein Tageslauf (tageslauf, gestartet vom Thread in tageslauf.py oder von „flask material remind“) prüft einmal am Tag ab
6 Uhr deutscher Zeit alle Artikel und befristeten Freigaben:

  30_tage      Fälligkeit (next_due_on) in höchstens 30 Tagen
  7_tage       Fälligkeit in höchstens 7 Tagen
  faellig      Fälligkeit überschritten (in der Mail „überfällig“) – einmal je Fälligkeitsdatum, nicht jeden Tag
  lebensdauer  Lebensende (retire_by, nur textiles Material) in höchstens 90 Tagen oder erreicht – einmal je Lebensende
  freigabe_ablauf  eine befristete Freigabe endet in höchstens 30 Tagen – einmal je Freigabe und Enddatum

Die Stufen sind fest (Konzept), unabhängig von der Einstellung „bald fällig“. Gemeldet wird je Ziel nur die höchste
erreichte Stufe, die für das Konto noch nicht im Log steht (mat_reminder_log, UNIQUE je Ziel, Stufe, Fälligkeit und
Konto) – so holt der nächste Lauf ausgefallene Tage nach, ohne eine Stufe doppelt zu melden. Eine Log-Zeile entsteht
nur, wenn der Mailserver die Mail angenommen hat; was scheitert, kommt am nächsten Tag wieder.

Gemahnt werden nur Artikel im Zustand „frei“, nie DEMO-Artikel (bestand.demo_sql) und nie Artikel in Ordnern mit
„Erinnerungen aus“ (mat_folder.reminders_off, vererbt auf alle Unterordner). Freigaben nur befristete, die heute wirken,
nie an DEMO-Ordnern oder von DEMO-Konten; der Schalter am Ordner hält sie nicht an.

Empfänger sind, wer an der Heimat (bzw. am Anker der Freigabe) oder darüber gültig verwaltet – Material- und
Plattform-Verwaltung eingeschlossen, wenn sie dort eingetragen sind (ordnerverwalter, anders als rechte.verwalter_von).
Verwaltet dort niemand, bekommt es die Material-Verwaltung, ohne sie die Plattform-Verwaltung; die Mail kennzeichnet
solche Gruppen mit „kein Materialwart eingetragen“ – bzw. „nur der Inhaber selbst verwaltet hier“, wenn bei einer
Freigabe allein ihr Inhaber dort verwaltet. Nur aktive Konten mit Namen, Modulzugang und Adresse, nie
DEMO-Konten (Adresse …@….invalid), jeder nur mit dem, was er sieht. Zugeordnete Personen, Prüfer und der Inhaber einer
ablaufenden Freigabe bekommen nichts. Je Empfänger und Tag eine Mail, gruppiert nach Ordnerpfad.

Der Versand hängt am Schalter MATERIAL_ERINNERUNGEN (Verwaltung → Einstellungen, Vorgabe aus) und an der Sperre
MATERIAL_ERINNERUNGEN_SPERRE (nur Umgebung, ohne Eintrag an, wenn STROEMIS_NAME auf -dev endet). Der Pflegeteil
(Journal „freigabe_abgelaufen“, Aufräumen des Logs nach 13 Monaten und des Suchprotokolls) läuft unabhängig davon
täglich, der Probelauf immer. Einmaligkeit: Tagesmarken und Herzschlag in mat_meta unter BEGIN IMMEDIATE, dazu die
UNIQUE-Indizes des Logs – Arbeitsprozesse, Neustarts und Kommandozeile mahnen nie doppelt. Ausnahme: Endet ein
Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk (etwa beim Neustart nach einem Deploy – der Thread ist
ein Daemon), fehlt die Log-Zeile, und diese eine Mail kommt am nächsten Morgen noch einmal. Erst senden, dann vermerken
lässt diese Lücke; umgekehrt ginge bei einem Abbruch eine Mahnung verloren.

Probelauf mit DEMO (nur Ansicht): Auf dev ist der ganze Bestand DEMO, der Probelauf zeigte dort nichts. planen(…,
demo=True) – erreichbar nur über probelauf(demo=True) und „remind --trocken --demo“ – nimmt DEMO-Artikel, DEMO-Freigaben
und DEMO-Konten als Empfänger dazu, nach denselben Regeln. Solche Einträge, Mails und der ganze Plan tragen ein
Kennzeichen (Eintrag.demo, Mail.demo, Plan.nur_ansicht); Betreff und Text sagen „DEMO – geht nie hinaus“. verschicken
und vermerken lehnen jeden Plan und jede Mail mit Kennzeichen oder DEMO-Adresse ab, und der Tageslauf ruft planen nie
mit demo – so führt kein Weg von der Ansicht zu Versand, Log oder Journal.

Das Erinnerungslog ist kein Prüfnachweis: Es dient nur dazu, nicht doppelt zu mahnen."""
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from flask import current_app, g

from ... import db
from ...mailer import send_mail                    # Tests ersetzen erinnerung.send_mail
from .. import services as dienste
from . import bestand, globalprotokoll, journal, katalog, rechte
from .interval import plus_monate

STUFEN_RANG = {"30_tage": 1, "7_tage": 2, "faellig": 3}   # „faellig“ heißt in Mails „überfällig“
VORLAUF_30, VORLAUF_7 = 30, 7                      # fest, unabhängig von MATERIAL_BALD_FAELLIG_TAGE
LEBENSDAUER_VORLAUF = 90                            # Konzept
FREIGABE_VORLAUF = 30                               # Vorgabe aus L1
STARTZEIT = time(6, 0)                              # deutsche Zeit
WARNZEIT = time(7, 0)                               # danach gilt ein fehlender Lauf als „steht“ (stand)
MAIL_ARTIKEL_MAX, MAIL_FREIGABEN_MAX = 100, 50     # Einzelzeilen je Mail; Ordnergruppen stehen immer da
AUFBEWAHRUNG_MONATE = 13
HERZSCHLAG_MINUTEN = 30
FEHLER_MAX = 300                                    # so lang steht ein Fehlertext im Laufstand
DEMO_POSTFACH = ".invalid"                          # DEMO-Konten beider Skripte: …@example.invalid (RFC 2606)
AKTEUR = "Tageslauf"                                # user_name der Journaleinträge des Laufs
SPERRE = "MATERIAL_ERINNERUNGEN_SPERRE"             # nur Umgebung (siehe gesperrt)

# Schlüssel in mat_meta – fehlt einer, heißt das „noch nie“.
M_LAEUFT, M_PFLEGE, M_MAILS, M_STAND = "tageslauf_laeuft", "tageslauf_pflege_tag", "erinnerung_tag", "tageslauf_stand"

RUECKFALL_TEXT = {"material": "Material-Verwaltung", "plattform": "Plattform-Verwaltung"}
# Warum eine Gruppe im Rückfall steht – Kennung „<Stelle>_inhaber“: Am Anker verwaltet nur der Inhaber der ablaufenden
# Freigabe selbst (er bekommt sie nicht, siehe empfaenger).
RUECKFALL_GRUND = {"": "kein Materialwart eingetragen", "inhaber": "nur der Inhaber selbst verwaltet hier"}
RECHT_TEXT = {"lesen": "lesen", "pruefen": "prüfen", "verwalten": "verwalten"}


@dataclass
class Eintrag:            # eine Erinnerung für eine Mail
    art: str              # "artikel" | "freigabe"
    kennung: int          # mat_item.id | mat_folder_grant.id
    stufe: str            # aus models.ERINNERUNGEN
    faellig_am: str       # due_on: next_due_on, retire_by bzw. valid_until
    ordner_id: int        # Heimat (bei frei = folder_id) bzw. Anker
    daten: dict           # was die Zeile zeigt (Nummern, Produkt, Name, Recht, offene Prüfungen, neu)
    rueckfall: str = ""   # "" | "material" | "plattform": Empfänger nur, weil am Ordner niemand verwaltet;
                          # "material_inhaber" | "plattform_inhaber": niemand außer dem Inhaber der Freigabe
    demo: bool = False    # DEMO-Artikel bzw. -Freigabe – nur im Probelauf mit DEMO (planen(…, demo=True))

    @property
    def schluessel(self):
        return self.art, self.kennung, self.stufe, self.faellig_am


@dataclass
class Mail:
    konten: list          # users-Zeilen derselben Adresse (meist eine)
    adresse: str
    name: str
    eintraege: list       # [Eintrag], schon nach Rechten geschnitten und gegen das Log geprüft
    betreff: str = ""
    text: str = ""
    je_konto: dict = field(default_factory=dict)     # Kennung des Kontos → seine Einträge (fürs Log)
    demo: bool = False    # DEMO-Empfänger oder DEMO-Einträge – nur zur Ansicht, geht nie hinaus


@dataclass
class Plan:
    stichtag: date
    mails: list           # [Mail]
    ohne_empfaenger: list # [Eintrag] – niemand Zulässiges sieht sie
    ausgelassen: dict     # {"ordner_aus": [{"id", "pfad", "artikel"}], "demo": n Artikel, "demo_freigaben": n} – der
                          # Stand speichert nur Zahlen; mit DEMO einbezogen sind beide DEMO-Zahlen 0
    fehlerhaft: int = 0   # Datenzeilen, die beim Planen übersprungen wurden
    pfade: dict = field(default_factory=dict)        # Ordnerkennung → Pfadtext (aus dem einmal geladenen Baum)
    nur_ansicht: bool = False                        # mit DEMO geplant – verschicken lehnt ab


# --- Schalter --------------------------------------------------------------------------------------------------

def gesperrt():
    """Die Sperre aus der Umgebung – kein Wert in der Datenbank (Verwaltung → Einstellungen) übersteuert sie. Wahr bei
    1/true/yes/on, falsch bei 0/false/no/off; ohne Eintrag wahr, wenn STROEMIS_NAME auf „-dev“ endet – so bleibt die
    Entwicklung still, auch wenn dort jemand den Schalter einschaltet oder eine Datenbank der Produktion einspielt."""
    roh = (os.environ.get(SPERRE) or "").strip().lower()
    if roh in ("0", "false", "no", "off"):
        return False
    if roh:
        return True                                  # auch Unklares sperrt
    return (os.environ.get("STROEMIS_NAME") or "").strip().endswith("-dev")


def versand_an():
    """Gehen Erinnerungsmails hinaus? Schalter an und nicht gesperrt."""
    return bool(current_app.config.get("MATERIAL_ERINNERUNGEN")) and not gesperrt()


def smtp_da():
    return bool((current_app.config.get("SMTP_HOST") or "").strip())


# --- mat_meta ----------------------------------------------------------------------------------------------------

def _meta(schluessel, vorgabe=None):
    r = db.query("SELECT wert FROM mat_meta WHERE schluessel = ?", (schluessel,), one=True)
    return r["wert"] if r else vorgabe


def _metas(*schluessel):
    gefunden = {r["schluessel"]: r["wert"] for r in db.query(
        f"SELECT schluessel, wert FROM mat_meta WHERE schluessel IN ({','.join('?' * len(schluessel))})", schluessel)}
    return [gefunden.get(s) for s in schluessel]


def _meta_setzen(schluessel, wert):
    db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
               "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, str(wert)))


def _utc(jetzt=None):
    """Zeitstempel wie db.now() (UTC, Sekunden), aber aus services.jetzt() – Tests stellen die Uhr dort um."""
    return (jetzt or dienste.jetzt()).astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _laeuft_noch(herzschlag, jetzt):
    """Ist der Herzschlag jünger als HERZSCHLAG_MINUTEN? Ein unlesbarer gilt als alt."""
    if not herzschlag:
        return False
    try:
        zeit = datetime.fromisoformat(herzschlag)
    except ValueError:
        return False
    if zeit.tzinfo is None:
        zeit = zeit.replace(tzinfo=timezone.utc)
    return jetzt - zeit < timedelta(minutes=HERZSCHLAG_MINUTEN)


def _herzschlag():
    _meta_setzen(M_LAEUFT, dienste.jetzt().isoformat())


def _fehlertext(exc):
    return f"{type(exc).__name__}: {exc}"[:FEHLER_MAX]


# --- Stufen und Auswahl ------------------------------------------------------------------------------------------

def _tag(iso):
    """'JJJJ-MM-TT' → date. Alles andere wirft ValueError (die Zeile gilt dann als fehlerhaft)."""
    if not isinstance(iso, str) or len(iso) != 10:
        raise ValueError(f"kein Datum: {iso!r}")
    return date.fromisoformat(iso)


def stufe(faellig_am, stichtag):
    """Die Stufe einer Fälligkeit am Stichtag: faellig, wenn sie vorbei ist (wie status.py: next_due_on < heute);
    7_tage bis 7 Tage vorher, 30_tage bis 30 Tage vorher; sonst None."""
    d = _tag(faellig_am)
    if d < stichtag:
        return "faellig"
    if d <= stichtag + timedelta(days=VORLAUF_7):
        return "7_tage"
    if d <= stichtag + timedelta(days=VORLAUF_30):
        return "30_tage"
    return None


def _ordnerbaum():
    """Alle Ordner einmal: Kennung → (Oberordner, Name). Pfadtexte und Zweige entstehen daraus ohne weitere Abfrage."""
    return {o["id"]: (o["parent_id"], o["name"]) for o in db.query("SELECT id, parent_id, name FROM mat_folder")}


def _pfad(fid, baum):
    namen, gesehen = [], set()
    while fid is not None and fid in baum and fid not in gesehen:
        gesehen.add(fid)
        namen.insert(0, baum[fid][1])
        fid = baum[fid][0]
    return " / ".join(namen) if namen else "(oberste Ebene)"


def _zweig(fid, baum):
    kinder = {}
    for k, (eltern, _) in baum.items():
        kinder.setdefault(eltern, []).append(k)
    gesehen, offen = set(), [fid]
    while offen:
        x = offen.pop()
        if x not in gesehen:
            gesehen.add(x)
            offen.extend(kinder.get(x, ()))
    return gesehen


def artikel_kandidaten(stichtag, demo=False):
    """Auswahl der Artikel (frei, mit Fälligkeit in 30 Tagen oder Lebensende in 90 Tagen): je Artikel bis zu zwei
    Einträge – Fälligkeit und Lebensende. Dazu die Zahlen des Ausgelassenen: {"ordner_aus": {Ordner: Zahl}, "demo": n,
    "fehlerhaft": n}. Eine Zeile, die sich nicht lesen lässt, wird geloggt und übersprungen. demo (nur Probelauf): auch
    DEMO-Artikel, als Eintrag mit demo=True – sie zählen dann nicht als ausgelassen."""
    rows = db.query(
        "WITH RECURSIVE aus(id) AS (SELECT id FROM mat_folder WHERE reminders_off = 1 "
        "UNION SELECT f.id FROM mat_folder f JOIN aus a ON f.parent_id = a.id) "
        "SELECT i.id, i.inventory_no, i.serial_no, i.folder_id, i.next_due_on, i.retire_by, i.last_inspected_on, "
        "p.manufacturer, p.model, p.description AS product_description, p.article_no, "
        f"{bestand.demo_sql('i', 'p')} AS ist_demo, i.folder_id IN (SELECT id FROM aus) AS ist_aus "
        "FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
        "WHERE i.lock_state = 'frei' "
        "AND ((i.next_due_on IS NOT NULL AND i.next_due_on <= :bis_30) "
        "OR (i.retire_by IS NOT NULL AND i.retire_by <= :bis_90)) ORDER BY i.id",
        {"bis_30": (stichtag + timedelta(days=VORLAUF_30)).isoformat(),
         "bis_90": (stichtag + timedelta(days=LEBENSDAUER_VORLAUF)).isoformat()})
    eintraege, info = [], {"ordner_aus": {}, "demo": 0, "fehlerhaft": 0}
    bis_90 = (stichtag + timedelta(days=LEBENSDAUER_VORLAUF)).isoformat()
    for r in rows:
        if r["ist_demo"] and not demo:
            info["demo"] += 1
            continue
        if r["ist_aus"]:
            info["ordner_aus"][r["folder_id"]] = info["ordner_aus"].get(r["folder_id"], 0) + 1
            continue
        try:
            daten = {"inventory_no": r["inventory_no"], "serial_no": r["serial_no"],
                     "produkt": katalog.produktname(r, r["product_description"]),
                     "neu": not r["last_inspected_on"]}
            neu = []
            if r["next_due_on"]:
                s = stufe(r["next_due_on"], stichtag)
                if s:
                    neu.append(Eintrag("artikel", r["id"], s, r["next_due_on"], r["folder_id"], daten,
                                       demo=bool(r["ist_demo"])))
            if r["retire_by"] and r["retire_by"] <= bis_90 and _tag(r["retire_by"]):
                neu.append(Eintrag("artikel", r["id"], "lebensdauer", r["retire_by"], r["folder_id"], daten,
                                   demo=bool(r["ist_demo"])))
        except (ValueError, TypeError) as exc:
            current_app.logger.error("Erinnerungen: Artikel %s übersprungen – %s", r["id"], exc)
            info["fehlerhaft"] += 1
            continue
        eintraege += neu
    return eintraege, info


def _konten(ids):
    """Aktive Konten zu diesen Kennungen – ganze Zeilen (Sicht, Zugang, Qualifikation brauchen Stufen und Häkchen)."""
    ids = sorted({int(i) for i in ids})
    if not ids:
        return {}
    return {u["id"]: u for u in db.query("SELECT * FROM users WHERE id IN (SELECT value FROM json_each(?)) "
                                         "AND active = 1 AND status = 'active'", (json.dumps(ids),))}


def freigaben_kandidaten(stichtag, baum=None, demo=False):
    """Auswahl der befristeten Freigaben, die in höchstens 30 Tagen enden und heute wirken (Konto aktiv, mit Namen und
    Zugang; prüfen nur qualifiziert) – nie an DEMO-Ordnern, nie von DEMO-Konten. Je Freigabe ein Eintrag
    freigabe_ablauf mit den offenen Prüfungen des Kontos im Zweig des Ankers – bei jeder Art: Mit einem befristeten
    lesen oder verwalten endet auch eine dauerhafte Prüffreigabe, die daran hängt (L1). Liefert
    (Einträge, {"fehlerhaft": n, "demo": n}). demo (nur Probelauf): DEMO-Freigaben auch, als Eintrag mit demo=True."""
    rows = db.query(
        f"SELECT g.*, (lower(u.email) LIKE '%{DEMO_POSTFACH}' OR {bestand.demo_ordner_sql('g.folder_id')}) AS ist_demo "
        "FROM mat_folder_grant g JOIN users u ON u.id = g.user_id "
        "WHERE g.valid_until IS NOT NULL AND g.valid_until >= :heute AND g.valid_until <= :bis "
        "AND u.active = 1 AND u.status = 'active' AND trim(u.name) <> '' "
        "ORDER BY g.valid_until, g.id",
        {"heute": stichtag.isoformat(), "bis": (stichtag + timedelta(days=FREIGABE_VORLAUF)).isoformat()})
    konten = _konten(r["user_id"] for r in rows)
    baum = _ordnerbaum() if baum is None else baum
    eintraege, info, offen_je_konto = [], {"fehlerhaft": 0, "demo": 0}, {}
    for r in rows:
        u = konten.get(r["user_id"])
        if not u or not rechte.zugang(u) or (r["permission"] == "pruefen" and not rechte.qualifiziert(u)):
            continue                                 # wirkt ohnehin nicht
        if r["ist_demo"] and not demo:
            info["demo"] += 1
            continue
        try:
            ende = _tag(r["valid_until"])
            daten = {"name": (u["name"] or "").strip(), "recht": r["permission"], "bis": r["valid_until"],
                     "tage": (ende - stichtag).days, "inhaber": u["id"], "offen": 0}
            if u["id"] not in offen_je_konto:
                offen_je_konto[u["id"]] = (
                    db.query("SELECT i.* FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id "
                             "WHERE x.inspector_user_id = ? AND x.completed_at IS NULL", (u["id"],)),
                    [x["folder_id"] for x in db.query("SELECT folder_id FROM mat_folder_grant WHERE user_id = ? "
                                                      "AND permission = 'pruefen' AND valid_until IS NULL", (u["id"],))])
            offen, dauerhaft = offen_je_konto[u["id"]]
            zweig = _zweig(r["folder_id"], baum)
            if r["permission"] != "pruefen":
                # Mit dem Grundrecht endet das dauerhafte Prüfen an diesem Anker und darunter – dort hängen die Entwürfe.
                zweig = set().union(*(_zweig(f, baum) for f in dauerhaft if f in zweig))
            daten["offen"] = sum(1 for i in offen if bestand.heimat(i) in zweig)
        except (ValueError, TypeError) as exc:
            current_app.logger.error("Erinnerungen: Freigabe %s übersprungen – %s", r["id"], exc)
            info["fehlerhaft"] += 1
            continue
        eintraege.append(Eintrag("freigabe", r["id"], "freigabe_ablauf", r["valid_until"], r["folder_id"], daten,
                                 demo=bool(r["ist_demo"])))
    return eintraege, info


# --- Empfänger ---------------------------------------------------------------------------------------------------

def ordnerverwalter(fid, ohne=None, stichtag=None):
    """Konten mit gültigem verwalten an fid oder darüber – aktiv, mit Namen, Material- und Plattform-Verwaltung
    eingeschlossen, wenn sie dort eingetragen sind (anders als rechte.verwalter_von: Bei einer täglichen Mail fiele
    sonst ein eingetragener Materialwart mit Stufe Verwaltung heraus). ohne: dieses Konto nicht (der Inhaber einer
    ablaufenden Freigabe). Kennungen, nach Namen sortiert."""
    tag = (stichtag or dienste.heute()).isoformat()
    rows = db.query(
        "WITH RECURSIVE kette(id) AS (SELECT ? UNION SELECT f.parent_id FROM mat_folder f JOIN kette k ON f.id = k.id "
        "WHERE f.parent_id IS NOT NULL) "
        "SELECT DISTINCT u.id, u.name FROM mat_folder_grant x JOIN users u ON u.id = x.user_id "
        "WHERE x.folder_id IN (SELECT id FROM kette) AND x.permission = 'verwalten' "
        "AND (x.valid_until IS NULL OR x.valid_until >= ?) AND u.active = 1 AND u.status = 'active' "
        "AND trim(u.name) <> '' AND u.id IS NOT ? ORDER BY u.name COLLATE NOCASE, u.id", (fid, tag, ohne))
    return [r["id"] for r in rows]


def demo_adresse(adr):
    """Ist das die Adresse eines DEMO-Kontos (…@….invalid)?"""
    return (adr or "").strip().casefold().endswith(DEMO_POSTFACH)


def _zulaessig(u, demo=False):
    """Darf dieses Konto eine Erinnerung bekommen? Adresse (keine DEMO-Adresse – außer im Probelauf mit DEMO) und
    Modulzugang (Stufe und Name)."""
    adr = (u.get("email") or "").strip()
    return bool(adr) and (demo or not demo_adresse(adr)) and rechte.zugang(u)


def _verwaltung(zwischen, ohne=None):
    """Rückfall, wenn am Ordner niemand verwaltet: die Material-Verwaltung (Stufe 2, ohne die Plattform-Verwaltung), ohne
    sie die Plattform-Verwaltung – je nach Abzug unzulässiger Konten (DEMO, ohne Adresse, ohne Zugang). Liefert
    (Konten, "material" | "plattform")."""
    if "verwaltung" not in zwischen:
        mv = db.query("SELECT * FROM users WHERE active = 1 AND status = 'active' AND trim(name) <> '' "
                      "AND recht_material >= 2 AND recht_verwaltung < 2 ORDER BY name COLLATE NOCASE, id")
        pv = db.query("SELECT * FROM users WHERE active = 1 AND status = 'active' AND recht_verwaltung >= 2 "
                      "ORDER BY name COLLATE NOCASE, id")
        demo = zwischen.get("demo", False)
        zwischen["verwaltung"] = ([u for u in mv if _zulaessig(u, demo)], [u for u in pv if _zulaessig(u, demo)])
    mv, pv = zwischen["verwaltung"]
    mv = [u for u in mv if u["id"] != ohne]
    if mv:
        return mv, "material"
    return [u for u in pv if u["id"] != ohne], "plattform"


def empfaenger(eintrag, zwischen):
    """Wer den Eintrag bekommt – vor dem Rechteschnitt – und die Art des Rückfalls ("" = Verwalter des Ordners; mit
    „_inhaber“, wenn bei einer Freigabe nur ihr Inhaber selbst dort verwaltet). zwischen hält je Plan die Verwalter je
    Ordner, die Verwaltung, den Stichtag und ob DEMO-Konten mitzählen (demo, nur Probelauf)."""
    ohne = eintrag.daten.get("inhaber") if eintrag.art == "freigabe" else None
    schluessel = (eintrag.ordner_id, ohne)
    verwalter = zwischen.setdefault("verwalter", {})
    if schluessel not in verwalter:
        ids = ordnerverwalter(eintrag.ordner_id, ohne=ohne, stichtag=zwischen.get("stichtag"))
        konten = _konten(ids)
        verwalter[schluessel] = [konten[i] for i in ids if i in konten and _zulaessig(konten[i], zwischen.get("demo"))]
    if verwalter[schluessel]:
        return verwalter[schluessel], ""
    konten, stelle = _verwaltung(zwischen, ohne)
    if ohne is not None:
        alle = zwischen.setdefault("verwalter_ids", {})
        if eintrag.ordner_id not in alle:
            alle[eintrag.ordner_id] = ordnerverwalter(eintrag.ordner_id, stichtag=zwischen.get("stichtag"))
        if ohne in alle[eintrag.ordner_id]:
            return konten, f"{stelle}_inhaber"
    return konten, stelle


# --- Planen ------------------------------------------------------------------------------------------------------

def _log(eintraege):
    """Die vorhandenen Log-Zeilen zu diesen Zielen als Menge (art, Kennung, Stufe, Fälligkeit, Kontoverweis)."""
    artikel = sorted({e.kennung for e in eintraege if e.art == "artikel"})
    freigaben = sorted({e.kennung for e in eintraege if e.art == "freigabe"})
    out = set()
    if artikel:
        for r in db.query("SELECT item_id, kind, due_on, konto_ref FROM mat_reminder_log "
                          "WHERE item_id IN (SELECT value FROM json_each(?))", (json.dumps(artikel),)):
            out.add(("artikel", r["item_id"], r["kind"], r["due_on"], r["konto_ref"]))
    if freigaben:
        for r in db.query("SELECT grant_id, kind, due_on, konto_ref FROM mat_reminder_log "
                          "WHERE grant_id IN (SELECT value FROM json_each(?))", (json.dumps(freigaben),)):
            out.add(("freigabe", r["grant_id"], r["kind"], r["due_on"], r["konto_ref"]))
    return out


def _offen(e, ref, log):
    """Steht für dieses Konto noch keine Zeile derselben oder einer höheren Stufe im Log? Ohne Kontoverweis gibt es noch
    kein Log – dann ist alles offen."""
    if not ref:
        return True
    if e.stufe in STUFEN_RANG:
        return not any((e.art, e.kennung, s, e.faellig_am, ref) in log
                       for s, rang in STUFEN_RANG.items() if rang >= STUFEN_RANG[e.stufe])
    return (e.art, e.kennung, e.stufe, e.faellig_am, ref) not in log


def planen(stichtag, demo=False):
    """Wer heute (am Stichtag) welche Mail bekäme: Kandidaten, Empfänger, Rechteschnitt, Abgleich mit dem Log, Texte.
    Schreibt nichts – auch keinen Kontoverweis. Fehlerhafte Datenzeilen werden übersprungen und gezählt.
    demo: DEMO-Artikel, DEMO-Freigaben und DEMO-Konten zählen wie echte – NUR für die Ansicht (probelauf, remind
    --trocken --demo). Der Plan heißt dann nur_ansicht, Mails mit DEMO tragen demo; verschicken lehnt beides ab."""
    rechte.sicht_verwerfen()                         # Freigaben können sich seit dem letzten Plan geändert haben
    demo = demo is True                              # nur ein echtes True schaltet DEMO ein
    baum = _ordnerbaum()
    artikel, info_a = artikel_kandidaten(stichtag, demo=demo)
    freigaben, info_f = freigaben_kandidaten(stichtag, baum, demo=demo)
    eintraege = artikel + freigaben
    log = _log(eintraege)
    zwischen = {"stichtag": stichtag, "demo": demo}
    post, ohne = {}, []                              # Adresse (casefold) → Mail
    for e in eintraege:
        konten, e.rueckfall = empfaenger(e, zwischen)
        erreicht = False
        for u in konten:
            s = rechte.sicht(u)
            if not s.darf("lesen" if e.art == "artikel" else "verwalten", e.ordner_id):
                continue
            erreicht = True
            if not _offen(e, u.get("mat_ref"), log):
                continue
            adr = u["email"].strip()
            m = post.get(adr.casefold())
            if m is None:
                m = post[adr.casefold()] = Mail(konten=[], adresse=adr, name=(u["name"] or "").strip(), eintraege=[])
            if u["id"] not in m.je_konto:
                m.konten.append(u)
                m.je_konto[u["id"]] = []
            m.je_konto[u["id"]].append(e)
            if all(x.schluessel != e.schluessel for x in m.eintraege):
                m.eintraege.append(e)
        if not erreicht:
            ohne.append(e)
    mails = sorted(post.values(), key=lambda m: (m.name.casefold(), m.adresse.casefold()))
    for m in mails:
        m.demo = _mit_demo(m)
    plan = Plan(stichtag=stichtag, mails=mails, ohne_empfaenger=ohne, nur_ansicht=demo,
                ausgelassen={"ordner_aus": [{"id": fid, "pfad": _pfad(fid, baum), "artikel": n}
                                            for fid, n in sorted(info_a["ordner_aus"].items(),
                                                                 key=lambda x: _pfad(x[0], baum).casefold())],
                             "demo": info_a["demo"], "demo_freigaben": info_f["demo"]},
                fehlerhaft=info_a["fehlerhaft"] + info_f["fehlerhaft"],
                pfade={fid: _pfad(fid, baum) for fid in {e.ordner_id for e in eintraege}})
    for m in mails:
        m.betreff, m.text = mailtext(m, stichtag, plan.pfade)
    return plan


# --- Mailtext ----------------------------------------------------------------------------------------------------

def _datum(iso):
    return _tag(iso).strftime("%d.%m.%Y")


def _in_tagen(n):
    if n == 0:
        return "heute"
    return "in 1 Tag" if n == 1 else f"in {n} Tagen"


def _klasse(e, stichtag):
    """Dringlichkeit (kleiner = dringender) und Zählgruppe im Betreff."""
    if e.stufe == "faellig":
        return 0, "ueberfaellig"
    if e.stufe == "lebensdauer":
        return (1, "lebensdauer_erreicht") if _tag(e.faellig_am) <= stichtag else (3, "lebensende_bald")
    if e.stufe == "7_tage":
        return 2, "7_tage"
    if e.stufe == "30_tage":
        return 4, "30_tage"
    return 5, "freigabe"


def _angabe(e, stichtag):
    tage = (_tag(e.faellig_am) - stichtag).days
    if e.stufe == "faellig":
        return f"überfällig – fällig war der {_datum(e.faellig_am)}"
    if e.stufe == "lebensdauer":
        if tage <= 0:
            return f"Lebensdauer erreicht seit {_datum(e.faellig_am)} – aussondern"
        return f"Lebensende am {_datum(e.faellig_am)} ({_in_tagen(tage)})"
    return f"fällig am {_datum(e.faellig_am)} ({_in_tagen(tage)})"


def _betreff(eintraege, stichtag):
    zahl = {}
    for e in eintraege:
        k = _klasse(e, stichtag)[1]
        zahl[k] = zahl.get(k, 0) + 1
    teile = []
    for k, text in (("ueberfaellig", "{} überfällig"), ("lebensdauer_erreicht", "{} Lebensdauer erreicht"),
                    ("7_tage", "{} in 7 Tagen fällig"), ("30_tage", "{} in 30 Tagen fällig")):
        if zahl.get(k):
            teile.append(text.format(zahl[k]))
    if zahl.get("lebensende_bald"):
        n = zahl["lebensende_bald"]
        teile.append("1 erreicht bald das Lebensende" if n == 1 else f"{n} erreichen bald das Lebensende")
    if zahl.get("freigabe"):
        n = zahl["freigabe"]
        teile.append("1 Freigabe läuft ab" if n == 1 else f"{n} Freigaben laufen ab")
    site = current_app.config.get("SITE_NAME") or "strömis.de"
    # Ein Betreff ist eine Zeile – auch U+2028/U+0085 aus Namen fliegen raus (wie beim Rückruf).
    return " ".join(f"{site} – Material: {', '.join(teile)}".split())


def mailtext(mail, stichtag, pfade=None):
    """Betreff und Text einer Mail: je Ordner (Heimat bzw. Anker) eine Gruppe mit Pfad, Zahl und Link – immer, auch wenn
    ihre Zeilen gekürzt sind. Über die ganze Mail höchstens MAIL_ARTIKEL_MAX Artikel- und MAIL_FREIGABEN_MAX
    Freigabezeilen, vergeben nach Dringlichkeit; der Rest einer Gruppe steht als „… und n weitere in diesem Ordner“.
    Gemeldet (und vermerkt) ist alles, was die Mail nennt – auch die gezählten weiteren."""
    basis = (current_app.config.get("BASE_URL") or "").rstrip("/")
    pfade = pfade if pfade is not None else {}

    def pfad(fid):
        if fid not in pfade:
            pfade[fid] = bestand._pfad_text(fid)
        return pfade[fid]

    # Artikel: eine Zeile je Artikel (Fälligkeit und Lebensende zusammen), Rang = dringendste Angabe.
    zeilen_a = {}
    for e in mail.eintraege:
        if e.art != "artikel":
            continue
        z = zeilen_a.setdefault(e.kennung, {"ordner": e.ordner_id, "eintraege": [], "daten": e.daten,
                                            "rueckfall": e.rueckfall})
        z["eintraege"].append(e)
    for z in zeilen_a.values():
        z["eintraege"].sort(key=lambda e: (_klasse(e, stichtag)[0], e.faellig_am))
        erste = z["eintraege"][0]
        z["rang"] = (_klasse(erste, stichtag)[0], erste.faellig_am, z["daten"]["inventory_no"])
    zeilen_f = {e.kennung: {"ordner": e.ordner_id, "eintraege": [e], "daten": e.daten, "rueckfall": e.rueckfall,
                            "rang": (e.faellig_am, e.daten["name"].casefold(), e.kennung)}
                for e in mail.eintraege if e.art == "freigabe"}

    def gezeigt(zeilen, grenze):
        return {k for k, _ in sorted(zeilen.items(), key=lambda x: x[1]["rang"])[:grenze]}

    zeigen_a, zeigen_f = gezeigt(zeilen_a, MAIL_ARTIKEL_MAX), gezeigt(zeilen_f, MAIL_FREIGABEN_MAX)

    def gruppen(zeilen):
        out = {}
        for k, z in zeilen.items():
            out.setdefault(z["ordner"], []).append((k, z))
        return sorted(out.items(), key=lambda x: (pfad(x[0]).casefold(), x[0]))

    rueckfall_arten, eigene = set(), []

    def kopf(fid, liste):
        rf = next((z["rueckfall"] for _, z in liste if z["rueckfall"]), "")
        text = f"{pfad(fid)} ({len(liste)})"
        if not rf:
            eigene.append(fid)
        if rf:
            rueckfall_arten.add(rf)
            stelle, _, grund = rf.partition("_")
            text += f" – {RUECKFALL_GRUND[grund]}, darum an die {RUECKFALL_TEXT[stelle]}"
        return text, rf

    demo = _mit_demo(mail)
    teile = ["DEMO – geht nie hinaus. Diese Mail zeigt nur der Probelauf mit DEMO-Bestand.", ""] if demo else []
    teile += [f"Hallo {mail.name},", "",
              f"hier steht nur, was seit der letzten Erinnerung neu fällig ist oder eine neue Stufe erreicht hat "
              f"(Stand {stichtag.strftime('%d.%m.%Y')}) – was schon gemeldet wurde, kommt nicht noch einmal. "
              f"Alles Fällige: {basis}/material/pruefungen"]
    if zeilen_a:
        teile += ["", "ARTIKEL"]
        for fid, liste in gruppen(zeilen_a):
            text, rf = kopf(fid, liste)
            teile += ["", text]
            liste.sort(key=lambda x: x[1]["rang"])
            for k, z in liste:
                if k not in zeigen_a:
                    continue
                d = z["daten"]
                angaben = " · ".join(_angabe(e, stichtag) for e in z["eintraege"])
                if d.get("neu"):
                    angaben += " · Eingangsprüfung offen"
                if any(e.demo for e in z["eintraege"]):
                    angaben += " · DEMO"
                teile.append(f"  {d['inventory_no']}  {d['produkt']}, SN {d['serial_no']}   {angaben}")
            rest = sum(1 for k, _ in liste if k not in zeigen_a)
            if rest:
                teile.append(f"  … und {rest} weitere in diesem Ordner")
            teile.append(f"  Ordner: {basis}/material/ordner/{fid}")
            if rf:
                teile.append(f"  Materialwart vergeben: {basis}/material/ordner/{fid}?freigaben=materialwart")
    if zeilen_f:
        teile += ["", "FREIGABEN, DIE BALD ABLAUFEN"]
        for fid, liste in gruppen(zeilen_f):
            text, rf = kopf(fid, liste)
            teile += ["", text]
            liste.sort(key=lambda x: x[1]["rang"])
            for k, z in liste:
                if k not in zeigen_f:
                    continue
                d = z["daten"]
                zeile = f"  {d['name']} – {RECHT_TEXT.get(d['recht'], d['recht'])} bis {_datum(d['bis'])} " \
                        f"({_in_tagen(d['tage'])})"
                if d.get("offen"):
                    zeile += f" · {d['offen']} offene Prüfung{'' if d['offen'] == 1 else 'en'}"
                if z["eintraege"][0].demo:
                    zeile += " · DEMO"
                teile.append(zeile)
            rest = sum(1 for k, _ in liste if k not in zeigen_f)
            if rest:
                teile.append(f"  … und {rest} weitere in diesem Ordner")
            teile.append(f"  Verlängern: {basis}/material/ordner/{fid}?freigaben=verlaengern")
            if rf and not rf.endswith("_inhaber"):
                teile.append(f"  Materialwart vergeben: {basis}/material/ordner/{fid}?freigaben=materialwart")
    # Der erste Satz nur, wenn die Mail auch eigene Ordner nennt – sonst stimmte er für die Verwaltung im Rückfall nicht.
    saetze = ["Du bekommst diese Mail, weil du diese Ordner verwaltest."] if eigene else []
    for stelle in ("material", "plattform"):
        gruende = [g for g in ("", "inhaber") if f"{stelle}_{g}".rstrip("_") in rueckfall_arten]
        if gruende:
            saetze.append(f"Gruppen mit {' oder '.join(f'„{RUECKFALL_GRUND[g]}“' for g in gruende)} bekommst du, weil "
                          f"du zur {RUECKFALL_TEXT[stelle]} gehörst.")
    # Der Schalter am Ordner hält nur Artikel an – ablaufende Freigaben melden sich weiter (Entwurf 2.4 b).
    if zeilen_a:
        saetze.append("Für einen Ordner abschalten: Ordner → Bearbeiten → „Erinnerungsmails aus“."
                      + (" Ablaufende Freigaben melden sich weiter." if zeilen_f else ""))
    else:
        saetze.append("Ablaufende Freigaben melden sich immer – auch in Ordnern mit „Erinnerungsmails aus“.")
    fuss = " ".join(saetze)
    teile += ["", fuss]
    betreff = _betreff(mail.eintraege, stichtag)
    return (f"[DEMO] {betreff}" if demo else betreff), "\n".join(teile) + "\n"


# --- Versand und Log ---------------------------------------------------------------------------------------------

NUR_ANSICHT = "Ein Plan mit DEMO-Bestand ist nur zur Ansicht – er wird nie verschickt oder vermerkt."


def _mit_demo(mail):
    """Hat die Mail etwas mit DEMO zu tun – Kennzeichen, ein DEMO-Eintrag, eine DEMO-Adresse oder ein DEMO-Konto?"""
    return bool(mail.demo or any(e.demo for e in mail.eintraege) or demo_adresse(mail.adresse)
                or any(demo_adresse(u.get("email")) for u in mail.konten))


def vermerken(mail):
    """Die Log-Zeilen einer angenommenen Mail – je Konto seine Einträge, in einer kurzen Transaktion. INSERT OR IGNORE
    hilft gegen UNIQUE (ein zweiter Lauf), WHERE EXISTS gegen einen Artikel oder eine Freigabe, die während des Versands
    gelöscht wurde (sonst „FOREIGN KEY constraint failed“ – dort gibt es ohnehin nichts mehr zu mahnen). Eine Mail mit
    DEMO (nur Probelauf) wird nie vermerkt (ValueError)."""
    if _mit_demo(mail):
        raise ValueError(NUR_ANSICHT)
    jetzt = _utc()
    with db.transaction():
        for u in mail.konten:
            ref = u.get("mat_ref")
            if not ref:
                continue
            for e in mail.je_konto.get(u["id"], ()):
                if e.art == "artikel":
                    db.execute("INSERT OR IGNORE INTO mat_reminder_log (item_id, kind, due_on, konto_ref, sent_at) "
                               "SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM mat_item WHERE id = ?)",
                               (e.kennung, e.stufe, e.faellig_am, ref, jetzt, e.kennung))
                else:
                    db.execute("INSERT OR IGNORE INTO mat_reminder_log (grant_id, kind, due_on, konto_ref, sent_at) "
                               "SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM mat_folder_grant WHERE id = ?)",
                               (e.kennung, e.stufe, e.faellig_am, ref, jetzt, e.kennung))


def verschicken(plan):
    """Die Mails des Plans einzeln verschicken, angenommene vermerken. Vorher bekommt jedes Konto des Plans seinen
    Kontoverweis (journal.konto_ref) – Konten nach Schritt 8 haben sonst keinen, und ein Fehlschlag soll im Stand mit
    Namen stehen. Jede Mail in einem eigenen try: Eine Ausnahme beim Senden zählt als Fehlschlag, eine beim Vermerken
    als vermerk_fehler; die nächste Mail geht trotzdem hinaus. Nach jeder Mail schlägt der Herzschlag. Einen Plan zur
    Ansicht (mit DEMO) lehnt es vorher ganz ab (ValueError) – nichts geht hinaus, kein Kontoverweis entsteht."""
    if plan.nur_ansicht or any(_mit_demo(m) for m in plan.mails):
        raise ValueError(NUR_ANSICHT)
    with db.transaction():
        for m in plan.mails:
            for u in m.konten:
                if not u.get("mat_ref"):
                    u["mat_ref"] = journal.konto_ref(u["id"])["ref"]
    erg = {"mails": 0, "fehlgeschlagen": 0, "fehlgeschlagen_refs": [], "vermerk_fehler": 0, "artikel": 0,
           "freigaben": 0}
    artikel, freigaben = set(), set()
    for m in plan.mails:
        try:
            ok = send_mail(m.adresse, m.betreff, m.text)
        except Exception as exc:                     # send_mail wirft nicht – eine Ausnahme soll trotzdem nur zählen
            current_app.logger.error("Erinnerung an %s gescheitert: %s", m.name, exc)
            ok = False
        if ok:
            erg["mails"] += 1
            artikel |= {e.kennung for e in m.eintraege if e.art == "artikel"}
            freigaben |= {e.kennung for e in m.eintraege if e.art == "freigabe"}
            try:
                vermerken(m)
            except Exception as exc:
                current_app.logger.exception("Erinnerung an %s: Vermerk im Log gescheitert: %s", m.name, exc)
                erg["vermerk_fehler"] += 1
        else:
            erg["fehlgeschlagen"] += 1
            erg["fehlgeschlagen_refs"] += [u["mat_ref"] for u in m.konten[:1] if u.get("mat_ref")]
        try:
            _herzschlag()
        except Exception as exc:
            current_app.logger.error("Tageslauf: Herzschlag nicht geschrieben: %s", exc)
    erg["artikel"], erg["freigaben"] = len(artikel), len(freigaben)
    return erg


# --- Pflege ------------------------------------------------------------------------------------------------------

def abgelaufene_eintragen(stichtag):
    """Journal „freigabe_abgelaufen“ am Anker für jede Freigabe, die vor dem Stichtag endete und seit ihrer letzten
    Erteilung noch keinen Eintrag mit demselben Ende hat – Form wie die übrigen Freigabe-Einträge (Kontoverweis, ohne
    Notiz und Namen). Die Bedingung mit freigabe_erteilt schützt vor einer wiederverwendeten Kennung. Liefert die Zahl."""
    rows = db.query(
        "SELECT g.* FROM mat_folder_grant g "
        "WHERE g.valid_until IS NOT NULL AND g.valid_until < :heute "
        "AND NOT EXISTS (SELECT 1 FROM mat_audit a WHERE a.entity = 'folder' AND a.entity_id = g.folder_id "
        "AND a.action = 'freigabe_abgelaufen' AND json_extract(a.after_json, '$.freigabe') = g.id "
        "AND json_extract(a.after_json, '$.bis') = g.valid_until "
        "AND a.id > COALESCE((SELECT MAX(e.id) FROM mat_audit e WHERE e.entity = 'folder' AND e.entity_id = g.folder_id "
        "AND e.action = 'freigabe_erteilt' AND json_extract(e.after_json, '$.freigabe') = g.id), 0)) "
        "ORDER BY g.id", {"heute": stichtag.isoformat()})
    if not rows:
        return 0
    with db.transaction():
        for r in rows:
            journal.eintragen("folder", r["folder_id"], "freigabe_abgelaufen", None, bestand.freigabe_journal(r),
                              name=AKTEUR)
    return len(rows)


def _grenze():
    return plus_monate(dienste.heute(), -AUFBEWAHRUNG_MONATE).isoformat()


_ALT = "DELETE FROM mat_reminder_log WHERE sent_at < ?"
_WAISEN = "DELETE FROM mat_reminder_log WHERE konto_ref NOT IN (SELECT mat_ref FROM users WHERE mat_ref IS NOT NULL)"


def aufraeumen(conn=None):
    """Das Erinnerungslog auf seine Frist kürzen (13 Monate) und Zeilen ohne Konto entfernen (falls ein Weg an
    loeschung.py vorbeiführte); ohne conn dazu das Protokoll der globalen Suche. conn: die Verbindung des Startlaufs
    (schema_anmelden) – so hält die Frist auch, wenn der Thread steht. Liefert {"log", "waisen", "suche"}."""
    if conn is not None:
        if "konto_ref" not in [r[1] for r in conn.execute("PRAGMA table_info(mat_reminder_log)")]:
            return {"log": 0, "waisen": 0, "suche": 0}   # Schema vor Schritt 11 (nur in Tests, die früher anhalten)
        n = conn.execute(_ALT, (_grenze(),)).rowcount
        w = conn.execute(_WAISEN).rowcount
        conn.commit()
        return {"log": n, "waisen": w, "suche": 0}
    with db.transaction():
        n = db.execute_zeilen(_ALT, (_grenze(),))
        w = db.execute_zeilen(_WAISEN)
    return {"log": n, "waisen": w, "suche": globalprotokoll.aufraeumen()}


def konto_loeschen(uid):
    """Die Log-Zeilen eines Kontos – aus loeschung.konto_loeschen_vorbereiten, vor dem Löschen der Kontozeile."""
    db.execute("DELETE FROM mat_reminder_log WHERE konto_ref = (SELECT mat_ref FROM users WHERE id = ?)", (uid,))


# --- Tageslauf ---------------------------------------------------------------------------------------------------

def _stand_lesen():
    try:
        return json.loads(_meta(M_STAND) or "{}") or {}
    except ValueError:
        return {}


def tageslauf(ausloeser="automatisch", erneut=False, jetzt=None):
    """Ein ganzer Lauf: Stichtag einmal bestimmen; unter Schreibsperre prüfen, ob ein anderer Lauf im Gange ist
    (Herzschlag jünger als 30 min) und welche Teile heute noch fehlen; Herzschlag und Tagesmarken VOR der Arbeit setzen
    (ein Abbruch soll denselben Tag nicht in Schleife wiederholen – der nächste Tag holt über das Log nach). Dann Pflege
    und Mails, jeder Teil in eigenem try. Liefert {"pflege": …, "mails": …} oder {"uebersprungen": "laeuft"|"erledigt"}.
    erneut: den Mailteil auch dann, wenn er heute schon lief (nur Offenes – das Log entscheidet)."""
    jetzt = jetzt or dienste.jetzt()
    stichtag = jetzt.date()
    tag = stichtag.isoformat()
    with db.transaction(sofort=True):
        laeuft, pflege_tag, mail_tag = _metas(M_LAEUFT, M_PFLEGE, M_MAILS)
        if _laeuft_noch(laeuft, jetzt):
            return {"uebersprungen": "laeuft", "seit": laeuft}
        pflege = (pflege_tag or "") < tag
        mails = versand_an() and smtp_da() and (erneut or (mail_tag or "") < tag)
        if not pflege and not mails:
            return {"uebersprungen": "erledigt", "um": (_stand_lesen().get("letzter") or {}).get("beginn")}
        _meta_setzen(M_LAEUFT, jetzt.isoformat())
        if pflege:
            _meta_setzen(M_PFLEGE, tag)
        if mails:
            _meta_setzen(M_MAILS, tag)
    g.mat_akteur = AKTEUR
    out = {"pflege": None, "mails": None}
    try:
        if pflege:
            p = {"tag": tag, "abgelaufen": 0, "log": 0, "waisen": 0, "suche": 0, "fehler": None}
            try:
                p["abgelaufen"] = abgelaufene_eintragen(stichtag)
                p.update(aufraeumen())
            except Exception as exc:
                current_app.logger.exception("Tageslauf: Pflege gescheitert: %s", exc)
                p["fehler"] = _fehlertext(exc)
            out["pflege"] = p
        if mails:
            m = {"tag": tag, "beginn": _utc(jetzt), "ende": None, "ausloeser": ausloeser, "mails": 0,
                 "fehlgeschlagen": 0, "fehlgeschlagen_refs": [], "artikel": 0, "freigaben": 0, "ohne_empfaenger": 0,
                 "ausgelassen": {"ordner_aus": 0, "demo": 0}, "fehlerhaft": 0, "vermerk_fehler": 0, "fehler": None}
            try:
                plan = planen(stichtag)
                m.update(ohne_empfaenger=len(plan.ohne_empfaenger), fehlerhaft=plan.fehlerhaft,
                         ausgelassen={"ordner_aus": sum(o["artikel"] for o in plan.ausgelassen["ordner_aus"]),
                                      "demo": plan.ausgelassen["demo"]})
                m.update(verschicken(plan))
            except Exception as exc:
                current_app.logger.exception("Tageslauf: Erinnerungsmails gescheitert: %s", exc)
                m["fehler"] = _fehlertext(exc)
            m["ende"] = _utc()
            out["mails"] = m
        stand = _stand_lesen()
        if out["pflege"]:
            stand["pflege"] = out["pflege"]
        if out["mails"]:
            stand["letzter"] = out["mails"]
        _meta_setzen(M_STAND, json.dumps(stand, ensure_ascii=False, sort_keys=True))
    finally:
        try:
            _meta_setzen(M_LAEUFT, "")
        except Exception as exc:
            current_app.logger.error("Tageslauf: Herzschlag nicht zurückgesetzt: %s", exc)
    return out


def tageslauf_versuchen():
    """Was der Thread alle 15 Minuten ruft: vor 6 Uhr deutscher Zeit nichts; danach erst ohne Sperre nachsehen, ob heute
    noch etwas zu tun ist (eine Abfrage), und nur dann tageslauf()."""
    jetzt = dienste.jetzt()
    if jetzt.time() < STARTZEIT:
        return {"uebersprungen": "zu_frueh"}
    tag = jetzt.date().isoformat()
    laeuft, pflege_tag, mail_tag = _metas(M_LAEUFT, M_PFLEGE, M_MAILS)
    if _laeuft_noch(laeuft, jetzt):
        return {"uebersprungen": "laeuft", "seit": laeuft}
    if (pflege_tag or "") >= tag and not (versand_an() and smtp_da() and (mail_tag or "") < tag):
        return {"uebersprungen": "erledigt"}
    return tageslauf(jetzt=jetzt)


# --- Stand und Probelauf -----------------------------------------------------------------------------------------

def _letzter_mit_namen(letzter):
    """Der gespeicherte Mailteil für die Oberfläche: Kontoverweise der Fehlschläge als Namen, die Verweise selbst nicht."""
    if not letzter:
        return None
    out = {k: v for k, v in letzter.items() if k != "fehlgeschlagen_refs"}
    refs = letzter.get("fehlgeschlagen_refs") or []
    namen = journal.konto_namen(refs)
    out["fehlgeschlagen_an"] = [namen[r] for r in refs if r in namen]
    return out


def stand():
    """Laufstand für die Übersicht (nur Material- und Plattform-Verwaltung): Schalter, Sperre, Mailserver, der letzte
    Mail- und Pflegeteil und ob etwas steht – veraltet (Versand an, Mailserver da, nach 7 Uhr und heute kein Mailteil)
    und pflege_veraltet (nach 7 Uhr und heute keine Pflege, unabhängig vom Schalter)."""
    jetzt = dienste.jetzt()
    tag = jetzt.date().isoformat()
    st = _stand_lesen()
    laeuft = _meta(M_LAEUFT)
    letzter, pflege = st.get("letzter"), st.get("pflege")
    spaet = jetzt.time() >= WARNZEIT
    return {"versand": bool(current_app.config.get("MATERIAL_ERINNERUNGEN")), "gesperrt": gesperrt(),
            "smtp": smtp_da(), "startzeit": STARTZEIT.strftime("%H:%M"), "laeuft": _laeuft_noch(laeuft, jetzt),
            "veraltet": bool(versand_an() and smtp_da() and spaet and letzter and letzter.get("tag", "") < tag),
            "pflege_veraltet": bool(spaet and (not pflege or pflege.get("tag", "") < tag)),
            "letzter": _letzter_mit_namen(letzter), "pflege": pflege}


def naechster_stichtag():
    """(Stichtag, morgen): Der nächste echte Lauf – heute, wenn der Mailteil heute noch nicht lief, sonst morgen (mit dem
    heutigen Log)."""
    heute = dienste.heute()
    if (_meta(M_MAILS) or "") >= heute.isoformat():
        return heute + timedelta(days=1), True
    return heute, False


def _ohne_empfaenger(plan):
    gruppen = {}
    for e in plan.ohne_empfaenger:
        z = gruppen.setdefault(e.ordner_id, {"ordner": plan.pfade.get(e.ordner_id) or bestand._pfad_text(e.ordner_id),
                                             "artikel": set(), "freigaben": set()})
        z["artikel" if e.art == "artikel" else "freigaben"].add(e.kennung)
    return sorted(({"ordner": z["ordner"], "artikel": len(z["artikel"]), "freigaben": len(z["freigaben"])}
                   for z in gruppen.values()), key=lambda z: z["ordner"].casefold())


def probelauf(stichtag=None, demo=False):
    """planen() für die Oberfläche: wer bei welchem Lauf welche Mail bekäme – mit Namen und Gliederung statt Adresse,
    Betreff und Text, ohne Empfänger und Ausgelassenes mit Pfaden. Ohne Stichtag der nächste echte Lauf
    (naechster_stichtag). Schreibt nichts: kein Log, kein Journal, keine Meta-Daten, keinen Kontoverweis. demo: den
    DEMO-Bestand einbeziehen (nur Ansicht, siehe planen) – Mails mit DEMO tragen demo: true."""
    heute = dienste.heute()
    if stichtag is None:
        stichtag, morgen = naechster_stichtag()
    else:
        morgen = stichtag == heute + timedelta(days=1)
    plan = planen(stichtag, demo=demo)
    letzter = _letzter_mit_namen(_stand_lesen().get("letzter"))
    return {"stichtag": stichtag.isoformat(), "morgen": morgen, "demo": plan.nur_ansicht,
            "versand": bool(current_app.config.get("MATERIAL_ERINNERUNGEN")), "gesperrt": gesperrt(), "smtp": smtp_da(),
            "letzter": {k: letzter.get(k) for k in ("tag", "beginn", "mails", "fehlgeschlagen", "fehlgeschlagen_an",
                                                    "fehler")} if letzter else None,
            "mails": [{"name": m.name, "gliederung": (m.konten[0].get("gliederung") or "").strip(), "betreff": m.betreff,
                       "text": m.text, "artikel": len({e.kennung for e in m.eintraege if e.art == "artikel"}),
                       "freigaben": len({e.kennung for e in m.eintraege if e.art == "freigabe"}), "demo": m.demo}
                      for m in plan.mails],
            "ohne_empfaenger": _ohne_empfaenger(plan), "ausgelassen": plan.ausgelassen, "fehlerhaft": plan.fehlerhaft}


def ordner_stand(fid):
    """Erinnerungen an einem Ordner: aus (selbst oder geerbt), der eigene Wert und der nächste Oberordner mit
    „Erinnerungen aus“ (mit Pfad und ob das Konto ihn öffnen darf – sonst zeigt die Ansicht ihn ohne Link, wie den
    grauen Pfad im Brotkrumen) – für Ordneransicht und Dialog."""
    rows = db.query(
        "WITH RECURSIVE kette(id, tiefe) AS (SELECT ?, 0 UNION ALL SELECT f.parent_id, k.tiefe + 1 FROM mat_folder f "
        "JOIN kette k ON f.id = k.id WHERE f.parent_id IS NOT NULL AND k.tiefe < 200) "
        "SELECT m.id, m.reminders_off, k.tiefe FROM kette k JOIN mat_folder m ON m.id = k.id ORDER BY k.tiefe", (fid,))
    eigen = bool(rows and rows[0]["tiefe"] == 0 and rows[0]["reminders_off"])
    oben = next((r for r in rows if r["tiefe"] > 0 and r["reminders_off"]), None)
    geerbt = {"id": oben["id"], "pfad": bestand._pfad_text(oben["id"]),
              "sichtbar": rechte.sicht().sichtbar(oben["id"])} if oben else None
    return {"aus": eigen or geerbt is not None, "eigen": eigen, "geerbt_von": geerbt}
