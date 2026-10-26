"""Änderungsanträge an den Stammdaten eines geprüften Artikels (Entscheidungen vom 21.10.2026; seit dem Wunsch vom
24.10.2026 an allen Stammdaten, Freigabe durch die zuständigen Materialwarte – Entscheidungen E1–E8).

Seit der ersten abgeschlossenen Prüfung stehen die Stammdaten eines Artikels fest (bestand.FREIGABEPFLICHTIG, Trigger
mat_item_stammdaten_fest und mat_item_produkt_fest) – sie stehen im Prüfprotokoll: Produkt, Seriennummer, Herstellung,
Kauf, Erstgebrauch, Lebensende (vorziehen und wieder nach hinten) und das Prüfintervall am Artikel (E1). Direkt bleiben Bemerkung, Länge
und das Vorziehen der nächsten Prüfung – durch Materialwart und Prüfer (E2, bestand.artikel_aendern). Jede andere
Änderung – auch eine STR-Nummer durch die echte Herstellernummer ersetzen, auch ein leeres Feld nachtragen (E3), auch das
Produkt wechseln (E4) – wird mit BEGRÜNDUNG BEANTRAGT.

Beantragen darf, wer den Artikel verwaltet (Materialwart, die Material-Verwaltung eingeschlossen) oder an ihm prüfen
darf (Prüfer); die Route prüft das (requires_folder), der Dienst in der Transaktion am frisch gelesenen Artikel noch
einmal. Ein Antrag nennt alle Felder, die sich ändern sollen, als EIN Sammelantrag: Kopfzeile in mat_item_change
(group_id NULL – ihre Kennung ist die Antrag-Nr.), je weiteres Feld eine Zeile mit group_id = Kopf; alle mit
derselben Begründung. Höchstens ein offener Antrag je Artikel (Trigger mat_item_change_gruppe). Ein ausgesonderter
Artikel bekommt keinen Antrag mehr, ein ungeprüfter braucht keinen (dort geht es direkt).

Entscheiden dürfen die Materialwarte des Ordners: Konten mit Modulzugang und EIGENER gültiger Freigabe „verwalten“ an
der Heimat des Artikels oder darüber, gleich aus welcher Gliederung (rechte „freigeben“). Die Material- und
Plattform-Verwaltung nur mit so einer Freigabe – sie darf sie sich selbst geben, das steht in Freigaben und Journal (E6).
Wer zuständig ist, entscheidet auch seinen eigenen Antrag (kein Vier-Augen, E5). Was ein Konto sieht – die Liste
„Änderungsanträge“ im Bestand, die Zahl an ihrem Knopf, der Hinweis auf der Übersicht und die Mail –, hängt an diesem
Ordnerrecht (E7): die eigenen Anträge (solange es den Artikel liest) und die, die es entscheiden darf. Artikelseite und
Journal zeigen offene Anträge wie bisher jedem, der den Artikel liest (ohne Begründung und Namen für Leser).

Geprüft wird beim Antrag UND beim Bestätigen (der Stand kann sich geändert haben) – der GESAMTE neue Stand nach den
Regeln des Anlegens (bestand.artikel_werte): Herstellung nicht in der Zukunft, nicht nach Kauf und Erstgebrauch, bei
textil Pflicht, nie leer; Seriennummer nicht leer, keine STR-Nummer, je Produkt frei; Intervall nicht über der
Herstellervorgabe; Lebensende nur textil und höchstens bis zur Rechnung aus Herstellung und Lebensdauer (Wunsch vom
25.10.2026: auch wieder nach hinten); Produkt nicht mit offenem Prüfentwurf, nicht über die DEMO-Grenze. Beim Bestätigen muss der Artikel jeden alten Wert noch tragen,
sonst 409 – der Antrag lässt sich dann nur noch ablehnen. Bestätigt oder abgelehnt wird der ganze Sammelantrag, in einer
Transaktion; der Trigger lässt genau die beantragten Änderungen zu und markiert jede Zeile als angewendet (applied_at).
Folgen eines Produktwechsels: Lebensende nach dem neuen Produkt, die Länge fällt weg, wenn seine Kategorie keine
vorsieht, ein kürzeres Intervall rückt die Fälligkeit vor (faelligkeit.kappen), Rückrufe gelten nach dem neuen Produkt,
die nächste Prüfung nimmt sein Formular.

Einen offenen Antrag zieht der Antragsteller selbst zurück (zurueckziehen) – nur seinen eigenen und nur, solange er den
Artikel liest. „zurückgezogen“ ist ein Endzustand wie bestätigt und abgelehnt; keine Mail.

Journal des Artikels: je Vorgang EIN Eintrag (antrag_gestellt, antrag_bestaetigt, antrag_abgelehnt,
antrag_zurueckgezogen) mit allen Feldern, beim Produkt mit lesbarem Namen; der Lebenslauf ebenso. Wer den Artikel nur
liest, sieht dort weder Begründung, Namen, Anmerkung noch Ablehnungsgrund (journal_verbergen). Festgeschriebene
Protokolle bleiben, wie sie sind; ein Sammelprotokoll, das erst danach entsteht, nennt „vormals …“ (protokoll._vormals).

Mails: ein neuer Antrag an die zuständigen Materialwarte (ohne den Antragsteller, höchstens MAX_EMPFAENGER, Rolle
„verwalter“); gibt es GAR kein zuständiges Konto, an die Material-Verwaltung (Rolle „verwaltung“, mit dem Hinweis auf die
Verwalterfreigabe) – fehlen nur Adressen, an niemanden. Die Entscheidung an den Antragsteller (nicht, wenn er selbst
entschieden hat, und nur, solange er den Artikel noch lesen darf). Bei DEMO-Artikeln, unter der Umgebungssperre (dev) und
ohne Mailserver stehen sie im Log statt im Postfach.

Anträge sind nach der Entscheidung (oder dem Zurückziehen) unveränderlich (Trigger), lassen sich nicht löschen und bleiben
unbefristet mit dem Artikel; beim Löschen eines Kontos setzt die Datenbank nur die Kontokennung auf NULL, die Namen
bleiben (Handelnde, wie bei Prüfungen und Mangelmeldungen)."""
import json
import unicodedata

from flask import current_app

from ... import db
from ...auth import _im_hintergrund
from ..models import ANTRAGSFELDER, ANTRAGSSTATUS
from . import Abgelehnt, akteur, datum, ganzzahl, kennung, monat_oder_datum, text
from . import bestand, erinnerung, faelligkeit, journal, katalog, mailprotokoll, nummern, rechte, rueckruf
from .interval import lebensende, wirksam

BEGRUENDUNG_MAX = 1000
MAX_EMPFAENGER = 10
FILTER = {"offen": ("offen",), "erledigt": ("bestaetigt", "abgelehnt", "zurueckgezogen"), "alle": tuple(ANTRAGSSTATUS)}
# Monatsfelder (Monat oder Tag wie im Dialog „Bearbeiten“; das Lebensende ist ein Tag).
MONATSFELDER = {"manufactured_on": "Herstelldatum", "purchased_on": "Kaufdatum", "first_use_on": "Erstgebrauch"}
SEITE = "/materialablage/bestand/antraege"
FEHLT = "Änderungsantrag nicht gefunden."
NICHT_FEST = "Der Artikel ist noch nicht geprüft – seine Stammdaten änderst du direkt im Dialog „Bearbeiten“."
AUSGESONDERT = "Der Artikel ist ausgesondert – an ihm ändert sich nichts mehr."
NICHTS = "Bitte mindestens ein Feld mit einem neuen Wert angeben."
STR_GESPERRT = "Seriennummern der Form „STR-…“ vergibt nur das System – bitte die Herstellernummer eintragen."
SCHON_BEANTRAGT = ("Für diesen Artikel läuft schon ein Änderungsantrag (vom {datum}) – er wartet auf einen Materialwart des "
                   "Ordners. Weitere Felder gehören in denselben Antrag: zurückziehen und neu stellen.")
ERLEDIGT = "Dieser Antrag ist schon entschieden oder zurückgezogen. Bitte neu laden."
STAND_ANDERS = ("Der Artikel trägt inzwischen nicht mehr den Wert, den der Antrag ändern wollte – bitte ablehnen; der "
                "Antragsteller kann neu beantragen.")
NUR_ABLEHNEN = "Der Artikel ist inzwischen ausgesondert – den Antrag kannst du nur noch ablehnen."
HERSTELLUNG_BLEIBT = "Das Herstelldatum lässt sich nicht entfernen – nur auf Antrag ändern (neues Datum angeben)."
LEBENSENDE_BLEIBT = "Das Lebensende lässt sich nicht entfernen – bitte ein neues Datum angeben."
LEBENSENDE_SCHON = ("Dieses Lebensende ergibt sich schon aus den übrigen Änderungen – bitte das Feld „Lebensende“ "
                    "unverändert lassen.")
LEBENSENDE_GESETZT = ("Das Lebensende {datum} ist am Artikel schon von Hand gesetzt – bitte das Feld „Lebensende“ "
                      "unverändert lassen.")
NICHT_ANGEWENDET = ("Der Antrag ließ sich nicht vollständig anwenden – bitte ablehnen; der Antragsteller kann neu "
                    "beantragen.")
SERIE_BLEIBT = "Die Seriennummer lässt sich nicht entfernen – bitte die neue Nummer angeben."
NUR_TEXTIL = "Ein Lebensende gibt es nur bei textilem Material."
ENTFERNEN_ALT = ("Ein Herstelldatum lässt sich nicht mehr entfernen (Entscheidung vom 21.10.2026) – diesen älteren Antrag "
                 "kannst du nur noch ablehnen.")
BEANTRAGEN_NICHT = "Beantragen dürfen Materialwarte und Prüfer dieses Artikels."
# Seriennummern der Bestandteile (Schritt 25).
TEILE_UND_PRODUKT = ("Seriennummern der Bestandteile gehören zum heutigen Produkt – ein anderes Produkt und neue Nummern "
                     "bitte in getrennten Anträgen.")
TEIL_WEG = ("Die Bestandteil-Liste des Produkts hat sich seit dem Antrag geändert – diese Position gibt es so nicht mehr. "
            "Bitte ablehnen; der Antragsteller kann neu beantragen.")

# Journal der Anträge: Was darin nur sieht, wer beantragen darf (wie antrag_json mit inhalt) – Begründung, Namen,
# Anmerkung und Ablehnungsgrund. Felder, alte und neue Werte und der Zeitpunkt bleiben: Die Stammdaten sieht der Leser
# ohnehin, und die Antragsansicht zeigt ihm dieselben Werte.
AKTIONEN = ("antrag_gestellt", "antrag_bestaetigt", "antrag_abgelehnt", "antrag_zurueckgezogen")
JOURNAL_INHALT = ("begruendung", "beantragt_von", "anmerkung", "ablehnung")

# Mails gehen neben der Anfrage hinaus (wie bei der Mangelmeldung); Tests setzen hier einen direkten Aufruf ein. Ob ein
# Mailserver da ist, weiß mailprotokoll.MAILSERVER; verschickt wird über mailprotokoll.senden (Mailfehler-Protokoll).
HINTERGRUND = _im_hintergrund


# --- Werte ----------------------------------------------------------------------------------------------------------

def _als_text(wert):
    """Ein Wert, wie mat_item_change ihn speichert: Text (Produkt und Intervall als Zahl in Textform) oder NULL."""
    return None if wert is None or wert == "" else str(wert)


def wert_am_artikel(item, feld):
    """Der heutige Wert des Feldes am Artikel als Text – beim Lebensende das wirksame (retire_by)."""
    return _als_text(item[feld])


def alt_am_artikel(item, r):
    """Der heutige Wert, den die Antragszeile r ändern will – bei der Seriennummer eines Bestandteils (Schritt 25) die
    Nummer dieses Stücks (None ohne)."""
    if r["field"] == "component_serial":
        from . import teilnummern
        return teilnummern.nummern(item["id"]).get((r["component_id"], r["stueck"])) or None
    return wert_am_artikel(item, r["field"])


def teil_passt(item, r, positionen=None):
    """Gibt es die Position und das Stück einer Antragszeile component_serial noch am Produkt des Artikels – mit derselben
    Bezeichnung (teilnummern.gleiche_position)? Andere Zeilen passen immer. positionen: {Kennung: Position} (sonst
    gelesen)."""
    if r["field"] != "component_serial":
        return True
    from . import stueckliste, teilnummern
    if positionen is None:
        positionen = {z["id"]: z for z in stueckliste.kurzliste(item["product_id"])}
    return teilnummern.gleiche_position(r["component_label"], positionen.get(r["component_id"]), r["stueck"])


def feld_text(r):
    """Das Feld einer Antragszeile, wie Liste, Mail und Journal es nennen – bei einem Bestandteil mit seiner Bezeichnung
    zum Zeitpunkt des Antrags („Seriennummer Bestandteil „Tasche (Stück 2 von 3)““)."""
    if r["field"] == "component_serial":
        return f"{ANTRAGSFELDER['component_serial']} „{r.get('component_label') or 'Nr. ' + str(r.get('component_id'))}“"
    return ANTRAGSFELDER[r["field"]]


def _wert_lesen(feld, wert):
    """Ein gespeicherter Antragswert zurück im Typ der Artikelspalte."""
    if wert is None:
        return None
    return int(wert) if feld in ("product_id", "interval_months") else wert


def _tag(iso):
    teile = iso.split("-")
    return f"{teile[1]}/{teile[0]}" if len(teile) == 2 else f"{teile[2]}.{teile[1]}.{teile[0]}"


def wert_text(feld, wert):
    """Ein Wert, wie Mail und Oberfläche ihn zeigen: Daten als MM/JJJJ bzw. TT.MM.JJJJ, das Produkt mit Namen (und
    Artikelnummer), das Intervall in Monaten, leer als „(leer)“."""
    if wert is None or wert == "":
        return "(leer)"
    if feld == "product_id":
        p = db.query("SELECT * FROM mat_product WHERE id = ?", (int(wert),), one=True)
        return bestand._produkt_text(p) if p else f"Produkt Nr. {wert}"
    if feld == "interval_months":
        return f"{wert} Monat" if str(wert) == "1" else f"{wert} Monate"
    if feld in MONATSFELDER or feld == "retire_by":
        return _tag(str(wert))
    return str(wert)


# --- Lesen ----------------------------------------------------------------------------------------------------------

def antrag(aid):
    """Eine Zeile (Kopf oder Folgezeile)."""
    r = db.query("SELECT * FROM mat_item_change WHERE id = ?", (aid,), one=True)
    if not r:
        raise Abgelehnt(FEHLT, 404)
    return r


def kopf(aid):
    """Der Kopf des Sammelantrags, zu dem die Zeile aid gehört (die Antrag-Nr. ist seine Kennung)."""
    r = antrag(aid)
    return antrag(r["group_id"]) if r["group_id"] else r


def gruppe(kid):
    """Alle Zeilen des Sammelantrags mit dem Kopf kid, Kopf zuerst."""
    return db.query("SELECT * FROM mat_item_change WHERE id = ? OR group_id = ? ORDER BY id", (kid, kid))


def offene(iid):
    """Offene Köpfe am Artikel – seit Schritt 23 höchstens einer (Altanträge aus der Zeit davor können mehrere sein).
    Die Folgezeilen fallen in Python heraus: So liest die Artikelansicht auch eine Datenbank vor Schritt 23 (Tests, die
    einen älteren Stand nachstellen, haben keine Spalte group_id und keine Anträge)."""
    return [r for r in db.query("SELECT * FROM mat_item_change WHERE item_id = ? AND status = 'offen' ORDER BY id",
                                (iid,)) if not r.get("group_id")]


def darf_beantragen(item, user=None):
    """Materialwart (verwalten) oder Prüfer (wirksames Prüfrecht) an der Heimat des Artikels – die Material- und
    Plattform-Verwaltung zählen wie verwalten."""
    return rechte.darf_artikel("verwalten", item, user) or rechte.darf_artikel("pruefen", item, user)


def darf_entscheiden(item, user=None):
    """Die Materialwarte des Ordners: eigene gültige Freigabe „verwalten“ an der Heimat oder darüber (rechte „freigeben“) –
    auch die Material-Verwaltung nur so (E6); den eigenen Antrag eingeschlossen (E5)."""
    return rechte.darf_artikel("freigeben", item, user)


def zustaendige(item):
    """Wer Anträge am Artikel entscheiden darf – als Konten (Zeilen von users): eigene gültige Verwalterfreigabe an der
    Heimat oder darüber (erinnerung.ordnerverwalter, die Verwaltung eingeschlossen, wenn sie eingetragen ist) und
    Modulzugang (Stufe und Name) – dieselbe Regel wie darf_entscheiden."""
    return zustaendige_ordner(bestand.heimat(item))


def zustaendige_ordner(fid):
    """Dasselbe für einen Ordner (die Heimat der Artikel)."""
    ids = erinnerung.ordnerverwalter(fid)
    if not ids:
        return []
    rows = db.query(f"SELECT * FROM users WHERE id IN ({','.join('?' * len(ids))}) ORDER BY name COLLATE NOCASE, id",
                    tuple(ids))
    return [dict(u) for u in rows if rechte.zugang(dict(u))]


def _datum(iso):
    from .protokoll import ortszeit
    return ortszeit(iso).strftime("%d.%m.%Y")


def _wuensche_der(rows):
    """{feld: neuer Wert im Typ der Spalte} aus den Zeilen eines Sammelantrags – Seriennummern der Bestandteile unter
    „component_serial“ als {(Position, Stück): neu}."""
    out = {}
    for r in rows:
        if r["field"] == "component_serial":
            out.setdefault("component_serial", {})[(r["component_id"], r["stueck"])] = r["new_value"]
        else:
            out[r["field"]] = _wert_lesen(r["field"], r["new_value"])
    return out


def antrag_json(k, item=None, inhalt=True, rows=None):
    """Ein Sammelantrag (k: sein Kopf) mit seinen Änderungen. item: die Artikelzeile (sonst gelesen). inhalt=False (nur
    Leserecht am Artikel): ohne Begründung, Namen und Antwort – nur Felder, Werte, Stand und Zeitpunkte. „entscheiden“:
    das Konto der Anfrage darf ihn bestätigen oder ablehnen (offen, zuständig); „ohne_zustaendige“: offen, und für den
    Ordner gibt es gar kein zuständiges Konto (dann bekam die Material-Verwaltung die Mail)."""
    uid, _ = akteur()
    item = item or bestand.artikel(k["item_id"])
    rows = rows or gruppe(k["id"])
    offen = k["status"] == "offen"
    aenderungen = [{"feld": r["field"], "feld_text": feld_text(r), "alt": r["old_value"],
                    "neu": r["new_value"], "alt_text": wert_text(r["field"], r["old_value"]),
                    "neu_text": wert_text(r["field"], r["new_value"]),
                    # Trägt der Artikel noch den alten Wert (an derselben Position)? Sonst lässt sich der offene Antrag
                    # nur noch ablehnen.
                    "passt": teil_passt(item, r) and alt_am_artikel(item, r) == r["old_value"]} for r in rows]
    out = {f: k[f] for f in ("id", "item_id", "status", "created_at", "resolved_at", "applied_at")}
    out.update({"aenderungen": aenderungen, "felder_text": ", ".join(a["feld_text"] for a in aenderungen),
                "status_text": ANTRAGSSTATUS[k["status"]], "inhalt": inhalt,
                "eigen": bool(uid and k["created_by"] == uid),
                "passt": all(a["passt"] for a in aenderungen),
                # Ein Antrag aufs Entfernen des Herstelldatums (nur bis Schritt 16 gestellt): nur noch ablehnen.
                "entfernen": any(r["field"] == "manufactured_on" and not r["new_value"] for r in rows),
                "entscheiden": offen and darf_entscheiden(item),
                "ohne_zustaendige": offen and not zustaendige(item)})
    out["begruendung"] = k["reason"] if inhalt else None
    out["antwort"] = k["answer"] if inhalt else None
    out["antragsteller"] = k["created_by_name"] if inhalt else None
    out["entschieden_von"] = k["resolved_by_name"] if inhalt and not offen else None
    # Offen und Seriennummer oder Produkt: Fällt der Artikel damit aus einem laufenden Rückruf oder kommt hinein? (Titel
    # laufender Rückrufe sieht jedes Konto mit Modulzugang ohnehin am Produkt.)
    out["rueckruf"] = rueckruf_folgen(item, _wuensche_der(rows)) if offen else None
    return out


def rueckruf_folgen(item, wuensche):
    """Was eine neue Seriennummer und/oder ein anderes Produkt an laufenden Rückrufen ändert: {"nicht_mehr": […],
    "neu": […]} mit {id, title} – Rückrufe, die den Artikel heute treffen und danach nicht mehr, und umgekehrt (Vorbild
    bestand.produktwechsel_eintragen). Ein ausgesonderter Artikel zählt nicht (rueckruf)."""
    if not ({"serial_no", "product_id"} & set(wuensche)) or item["lock_state"] == "ausgesondert":
        return {"nicht_mehr": [], "neu": []}
    vorher = {r["id"]: r for r in rueckruf.betrifft(item["product_id"], item["serial_no"])}
    nachher = {r["id"]: r for r in rueckruf.betrifft(wuensche.get("product_id", item["product_id"]),
                                                     wuensche.get("serial_no", item["serial_no"]))}
    return {"nicht_mehr": [{"id": i, "title": r["title"]} for i, r in vorher.items() if i not in nachher],
            "neu": [{"id": i, "title": r["title"]} for i, r in nachher.items() if i not in vorher]}


def journal_verbergen(eintraege):
    """Für Konten ohne Inhaltsrecht (darf_beantragen – dieselbe Regel wie antrag_json mit inhalt=False): In den
    Journaleinträgen der Anträge stehen danach weder Begründung, Antragsteller, Anmerkung noch Ablehnungsgrund, als
    Handelnder „(Person)“ – wie beim Melder eines Mangels (bestand._melder_verbergen). Ändert die Einträge an Ort und
    Stelle (Artikelansicht und Lebenslauf)."""
    from .beschriftung import PERSON
    for e in eintraege:
        # Dazu die vorgezogene Fälligkeit, die ein bestätigter Antrag nach sich zieht (faelligkeit.kappen mit „antrag“) –
        # sonst stünde der Entscheider dort mit Namen (Prüfung Sicherheit, Befund 2).
        if e["action"] in AKTIONEN or (e["action"] == "faelligkeit" and "antrag" in (e.get("nachher") or {})):
            e["user_name"] = PERSON
            if e.get("nachher"):
                e["nachher"] = {k: v for k, v in e["nachher"].items() if k not in JOURNAL_INHALT}


def _artikel_kurz(item):
    """Was die Liste der Anträge über den Artikel zeigt – für die zuständigen Materialwarte und den Antragsteller (nur,
    solange er den Artikel liest: liste filtert)."""
    p = katalog.produkt(item["product_id"])
    gl = bestand.gliederung_von(item["folder_id"])
    return {"id": item["id"], "inventory_no": item["inventory_no"], "serial_no": item["serial_no"],
            "serial_generated": bool(item["serial_generated"]), "manufactured_on": item["manufactured_on"],
            "lock_state": item["lock_state"], "demo": bestand.ist_demo(item["id"]),
            "produkt": katalog.produkt_json(p), "gliederung": gl["name"] if gl else "",
            "pfad": bestand._pfad_text(bestand.heimat(item))}


def _sichtbar(user=None):
    """SQL-Bedingung über mat_item_change c (mit mat_item i) und ihre Parameter: die eigenen Anträge, solange das Konto
    den Artikel liest, und die, die es entscheiden darf (E7) – die Material-Verwaltung ohne eigene Verwalterfreigabe also
    nur ihre eigenen."""
    from ...auth import current_user
    user = user or current_user()
    if not user or not rechte.zugang(user):
        return "0", []
    eigene = rechte.artikel_filter("i", "lesen", user=user)
    zustaendig = rechte.artikel_filter("i", "freigeben", user=user)
    return f"((c.created_by = ? AND {eigene}) OR {zustaendig})", [user["id"]]


def liste(filter_="offen", grenze=200):
    """Sammelanträge nach Stand, soweit das Konto der Anfrage sie sehen darf: offene der Reihe nach (älteste zuerst),
    erledigte neueste zuerst. Je Eintrag mit dem Artikel (artikel)."""
    stati = FILTER.get(filter_) or FILTER["offen"]
    sichtbar, args = _sichtbar()
    rows = db.query(
        f"SELECT c.* FROM mat_item_change c JOIN mat_item i ON i.id = c.item_id "
        f"WHERE c.group_id IS NULL AND c.status IN ({','.join('?' * len(stati))}) AND {sichtbar} "
        + ("ORDER BY c.id" if stati == FILTER["offen"] else "ORDER BY COALESCE(c.resolved_at, c.created_at) DESC, c.id DESC")
        + " LIMIT ?", (*stati, *args, grenze))
    out = []
    for r in rows:
        item = bestand.artikel(r["item_id"])
        j = antrag_json(r, item)
        j["artikel"] = _artikel_kurz(item)
        out.append(j)
    return out


def zu_entscheiden(user=None):
    """Offene Sammelanträge, die das Konto entscheiden darf (eigene eingeschlossen, E5) – die Zahl am Knopf
    „Änderungsanträge“ und auf der Übersicht."""
    from ...auth import current_user
    user = user or current_user()
    if not user or not rechte.zugang(user):
        return 0
    zustaendig = rechte.artikel_filter("i", "freigeben", user=user)
    return db.query(f"SELECT COUNT(*) AS n FROM mat_item_change c JOIN mat_item i ON i.id = c.item_id "
                    f"WHERE c.group_id IS NULL AND c.status = 'offen' AND {zustaendig}", one=True)["n"]


def fuer_artikel(item, inhalt):
    """Offene Anträge am Artikel für die Artikelansicht (inhalt: Begründung und Namen – nur wer beantragen darf)."""
    return [antrag_json(k, item, inhalt) for k in offene(item["id"])]


# --- Prüfen ---------------------------------------------------------------------------------------------------------

def _zustand(item):
    if item["lock_state"] == "ausgesondert":
        raise Abgelehnt(AUSGESONDERT, 409)
    if not bestand.stammdaten_fest(item["id"]):
        raise Abgelehnt(NICHT_FEST, 409)


def _wuensche(d, item):
    """{feld: neuer Wert im Typ der Spalte} aus der Anfrage – nur Felder, die sie nennt und die vom Artikel abweichen
    (die Oberfläche schickt nur geänderte). Leer heißt bei Kauf, Erstgebrauch und Intervall „entfernen“; Seriennummer,
    Herstellung und Lebensende lassen sich nicht entfernen, das Produkt nicht leeren."""
    if d.get("herstellung_entfernen") in (True, 1, "1", "ja", "true"):
        raise Abgelehnt(HERSTELLUNG_BLEIBT)
    out = {}
    if d.get("product_id") not in (None, ""):
        pid = kennung(d.get("product_id"), "Produkt")
        if pid != item["product_id"]:
            out["product_id"] = pid
    if "serial_no" in d:
        sn = text(d, "serial_no", "Seriennummer", 80)
        if sn and sn != item["serial_no"]:
            out["serial_no"] = sn
    for feld, name in MONATSFELDER.items():
        if feld in d:
            wert = monat_oder_datum(d.get(feld), name)
            if wert is None and feld == "manufactured_on" and item[feld]:
                raise Abgelehnt(HERSTELLUNG_BLEIBT)
            if wert != item[feld]:
                out[feld] = wert
    if "retire_by" in d:
        wert = datum(d.get("retire_by"), "Lebensende")
        if wert is None and item["retire_by"]:
            raise Abgelehnt(LEBENSENDE_BLEIBT)
        if wert != item["retire_by"]:
            out["retire_by"] = wert
    if "interval_months" in d:
        wert = ganzzahl(d.get("interval_months"), "Prüfintervall (Monate)", 1, 120)
        if wert != item["interval_months"]:
            out["interval_months"] = wert
    if "bestandteil_nummern" in d:
        # Seriennummern der Bestandteile (Schritt 25): je geändertem Stück eine Zeile; leer heißt „Nummer entfernen“.
        from . import teilnummern
        werte = teilnummern.lesen(d.get("bestandteil_nummern"), item["product_id"])
        teile = {(cid, st): (neu or None) for cid, st, _, neu in teilnummern.aenderungen(item["id"], werte)}
        if teile:
            if "product_id" in out:
                raise Abgelehnt(TEILE_UND_PRODUKT)
            out["component_serial"] = teile
    if not out:
        raise Abgelehnt(NICHTS)
    return out


def _teile_journal(item, teile, neu=True):
    """Seriennummern der Bestandteile im Journal eines Antrags: [{bestandteil, seriennummer}] – alt (neu=False) oder neu."""
    from . import teilnummern
    positionen = teilnummern._beschriftungen(item["product_id"])
    jetzt = teilnummern.nummern(item["id"])
    return [teilnummern.journal_form(positionen, cid, st, wert if neu else jetzt.get((cid, st), ""))
            for (cid, st), wert in sorted(teile.items())]


def _plan(item, wuensche):
    """Der neue Stand des Artikels nach allen Wünschen – geprüft wie beim Anlegen (beim Antrag und beim Bestätigen).
    Liefert die Spalten, die sich ändern ({spalte: wert}, mit den Folgen – Lebensende, Länge, STR-Kennzeichen). Wirft
    Abgelehnt."""
    if "component_serial" in wuensche:
        # Die Positionen müssen noch zum Produkt gehören (die Liste kann sich seit dem Antrag geändert haben).
        from . import stueckliste
        positionen = {z["id"]: z for z in stueckliste.kurzliste(item["product_id"])}
        if any(cid not in positionen or st > positionen[cid]["anzahl"] for cid, st in wuensche["component_serial"]):
            raise Abgelehnt(TEIL_WEG, 409)
    d = {f: item[f] for f in bestand.ARTIKEL_FELDER}
    d.update({f: v for f, v in wuensche.items() if f not in ("retire_by", "component_serial")})
    d["retire_by"] = None                         # das Lebensende rechnet unten – artikel_werte prüft nur sein Format
    w, p = bestand.artikel_werte(d, alt=item)
    if "product_id" in wuensche:
        bestand.produktwechsel_pruefen(item, p, antrag=True)
    if "serial_no" in wuensche and nummern.sieht_generiert_aus(wuensche["serial_no"]):
        raise Abgelehnt(STR_GESPERRT)
    if {"serial_no", "product_id"} & set(wuensche):
        bestand._serie_frei(p["id"], w["serial_no"], ausser=item["id"])
    if not wirksam(p, bestand.heimat(item), w["interval_months"])["monate"]:
        raise Abgelehnt(katalog.KEIN_INTERVALL, 409)
    setzen = {f: w[f] for f in wuensche if f not in ("retire_by", "component_serial")}
    if "serial_no" in wuensche and item["serial_generated"]:
        setzen["serial_generated"] = 0            # eine echte Herstellernummer ersetzt die vergebene
    # Lebensende (nur textil): Rechnung aus Herstellung und Lebensdauer; ein von Hand gesetztes gilt, solange es früher
    # liegt. Beantragt wird ein Datum bis höchstens zur Rechnung – vorziehen oder ein vorgezogenes wieder nach hinten
    # (Wunsch vom 25.10.2026). Genau die Rechnung heißt: nicht mehr von Hand gesetzt (retire_by_manual leer, es folgt
    # wieder Herstellung und Katalog). Textiles Material hat immer Herstellung und Lebensdauer (Pflicht, CHECK).
    textil = p["material_kind"] == "textil"
    manuell = item["retire_by_manual"]
    if "retire_by" in wuensche:
        if not textil:
            raise Abgelehnt(NUR_TEXTIL)
        rechnung = lebensende(w["manufactured_on"], p["lifetime_years"])
        wunsch = wuensche["retire_by"]
        if rechnung and wunsch > rechnung:
            raise Abgelehnt(f"Das Lebensende lässt sich höchstens bis zur Rechnung aus Herstellung und Lebensdauer "
                            f"setzen ({wert_text('retire_by', rechnung)}).")
        manuell = None if wunsch == rechnung else wunsch
        if manuell == item["retire_by_manual"]:
            # Der Trigger verlangt, dass ein Antrag auf das Lebensende das von Hand gesetzte ändert (sonst bliebe die
            # Zeile unangewendet und das Bestätigen scheiterte): gleich bleibt es, wenn dieses Datum schon von Hand
            # gesetzt ist (wirksam ist eine frühere Rechnung, etwa mit einem anderen Produkt im selben Antrag – Prüfung
            # Sicherheit, Befund 3) oder eine andere Änderung das Lebensende schon dahin bringt.
            raise Abgelehnt(LEBENSENDE_GESETZT.format(datum=wert_text("retire_by", manuell)) if manuell
                            else LEBENSENDE_SCHON)
    if textil and {"retire_by", "product_id", "manufactured_on"} & set(wuensche):
        ende = bestand._lebensende_wirksam(lebensende(w["manufactured_on"], p["lifetime_years"]), manuell)
        if ende != item["retire_by"]:
            setzen["retire_by"] = ende
        if manuell != item["retire_by_manual"]:
            setzen["retire_by_manual"] = manuell
    elif not textil and "product_id" in wuensche:
        # Zu einem nicht textilen Produkt: kein Lebensende mehr (wie bestand.artikel_aendern).
        for spalte in ("retire_by", "retire_by_manual"):
            if item[spalte] is not None:
                setzen[spalte] = None
    if w["length_m"] != item["length_m"]:
        setzen["length_m"] = w["length_m"]        # die Kategorie des neuen Produkts sieht keine Länge vor
    return setzen


def _produktnamen(vorher, nachher, item, wuensche):
    """Beim Produktwechsel dazu der lesbare Name (die Oberfläche blendet die Kennung dann aus)."""
    if "product_id" in wuensche:
        vorher["produkt"] = wert_text("product_id", item["product_id"])
        nachher["produkt"] = wert_text("product_id", wuensche["product_id"])


# --- Beantragen -----------------------------------------------------------------------------------------------------

def _begruendung(d):
    """Die Begründung (Pflicht) – eine aus nur unsichtbaren Format- und Leerzeichen (etwa U+200B) zählt als leer
    (Prüfung Sicherheit, Verbesserung)."""
    b = text(d, "begruendung", "Begründung", BEGRUENDUNG_MAX, pflicht=True, einzeilig=False)
    if not "".join(z for z in b if not z.isspace() and unicodedata.category(z) != "Cf"):
        raise Abgelehnt("„Begründung“ fehlt.")
    return b


def stellen(iid, d):
    """Einen Sammelantrag stellen – je Feld, das sich ändern soll, eine Zeile, alle mit derselben Begründung, ganz oder
    gar nicht. Ein Journaleintrag, eine Mail. Liefert (Antrag-Nr., mail)."""
    begruendung = _begruendung(d)
    uid, name = akteur()
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if not darf_beantragen(item):
            raise Abgelehnt(BEANTRAGEN_NICHT, 403)
        _zustand(item)
        da = db.query("SELECT created_at FROM mat_item_change WHERE item_id = ? AND status = 'offen' ORDER BY id LIMIT 1",
                      (iid,), one=True)
        if da:
            raise Abgelehnt(SCHON_BEANTRAGT.format(datum=_datum(da["created_at"])), 409)
        wuensche = _wuensche(d, item)
        _plan(item, wuensche)
        ts, kid = db.now(), None
        # In der Reihenfolge der Oberfläche (ANTRAGSFELDER): Der Kopf ist das erste Feld.
        for feld in [f for f in ANTRAGSFELDER if f in wuensche]:
            if feld == "component_serial":
                # Je Stück eine Zeile mit der Position und ihrer Bezeichnung von heute (Schritt 25).
                from . import teilnummern
                positionen = teilnummern._beschriftungen(item["product_id"])
                jetzt = teilnummern.nummern(iid)
                for (cid, st), neu in sorted(wuensche[feld].items()):
                    z = positionen[cid]
                    aid = db.execute(
                        "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                        "created_by_name, created_at, group_id, component_id, stueck, component_label) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (iid, feld, jetzt.get((cid, st)) or None, neu, begruendung, uid, name, ts, kid, cid, st,
                         teilnummern.stueck_text(z["bezeichnung"], st, z["anzahl"])))
                    kid = kid or aid
                continue
            aid = db.execute(
                "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, created_by_name, "
                "created_at, group_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (iid, feld, wert_am_artikel(item, feld), _als_text(wuensche[feld]), begruendung, uid, name, ts, kid))
            kid = kid or aid
        einfach = {f: v for f, v in wuensche.items() if f != "component_serial"}
        vorher, nachher = {f: item[f] for f in einfach}, dict(einfach, antrag=kid, begruendung=begruendung)
        if "component_serial" in wuensche:
            vorher["bestandteil_nummern"] = _teile_journal(item, wuensche["component_serial"], neu=False)
            nachher["bestandteil_nummern"] = _teile_journal(item, wuensche["component_serial"])
        _produktnamen(vorher, nachher, item, wuensche)
        journal.eintragen("item", iid, "antrag_gestellt", vorher, nachher)
        if not zustaendige(item):
            _als_gemeldet(bestand.heimat(item))       # die Mail unten geht dann an die Material-Verwaltung (N5)
    return kid, _zustaendige_benachrichtigen(kid)


# --- Entscheiden (die zuständigen Materialwarte) -----------------------------------------------------------------------

def _entscheider(item):
    """Darf das Konto der Anfrage Anträge am Artikel entscheiden? Liest es den Artikel nicht: 404 wie unbekannt; liest es
    ihn, ist aber nicht zuständig: 403 mit Klartext."""
    if not rechte.darf_artikel("lesen", item):
        raise Abgelehnt(FEHLT, 404)
    if not darf_entscheiden(item):
        raise Abgelehnt(rechte.ENTSCHEIDEN_NUR_ZUSTAENDIG, 403)


def _entscheiden(kid, n, status, antwort):
    """Innerhalb der Transaktion: alle n Zeilen des Sammelantrags auf einmal – nur offene; wer zweitens kommt, erfährt es."""
    uid, name = akteur()
    if db.execute_zeilen(
            "UPDATE mat_item_change SET status = ?, answer = ?, resolved_by = ?, resolved_by_name = ?, resolved_at = ? "
            "WHERE (id = ? OR group_id = ?) AND status = 'offen'", (status, antwort, uid, name, db.now(), kid, kid)) != n:
        raise Abgelehnt(ERLEDIGT, 409)


def bestaetigen(aid, d):
    """Den Sammelantrag bestätigen und alle Änderungen übernehmen – in einer Transaktion, nach erneuter Prüfung des
    ganzen neuen Stands am frisch gelesenen Artikel; danach zieht die Fälligkeit nach (kürzeres Intervall, anderes
    Produkt). Eine Anmerkung (antwort) ist freiwillig; sie steht in der Mail an den Antragsteller. Liefert die
    Antrag-Nr."""
    kid = kopf(aid)["id"]
    with db.transaction(sofort=True):
        k = antrag(kid)
        item = bestand.artikel(k["item_id"])
        _entscheider(item)                       # erst das Recht (404/403), dann die Eingabe
        antwort = text(d, "antwort", "Anmerkung", BEGRUENDUNG_MAX, einzeilig=False)
        if k["status"] != "offen":
            raise Abgelehnt(ERLEDIGT, 409)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt(NUR_ABLEHNEN, 409)
        rows = gruppe(kid)
        if any(r["field"] == "manufactured_on" and not r["new_value"] for r in rows):
            raise Abgelehnt(ENTFERNEN_ALT, 409)
        # Erst die Position (ihre Kennung kann inzwischen eine andere Position tragen – Bezeichnung mit verglichen), dann
        # der Wert: Fehlt die Position, sagt das der Satz (Prüfung Sicherheit, Verbesserung), nicht „Wert anders“.
        if not all(teil_passt(item, r) for r in rows):
            raise Abgelehnt(TEIL_WEG, 409)
        if any(alt_am_artikel(item, r) != r["old_value"] for r in rows):
            raise Abgelehnt(STAND_ANDERS, 409)
        wuensche = _wuensche_der(rows)
        setzen = _plan(item, wuensche)
        folgen = rueckruf_folgen(item, wuensche)
        _entscheiden(kid, len(rows), "bestaetigt", antwort)
        db.execute(f"UPDATE mat_item SET {''.join(f'{s} = ?, ' for s in setzen)}updated_at = ? WHERE id = ?",
                   (*setzen.values(), db.now(), item["id"]))
        if "product_id" in setzen:
            # Nummern an Positionen des bisherigen Produkts gelten nicht mehr (Schritt 25).
            from . import teilnummern
            teilnummern.aufraeumen(dict(item, product_id=setzen["product_id"]), item["product_id"])
        teile = wuensche.get("component_serial") or {}
        if teile:
            # Seriennummern der Bestandteile (Schritt 25): der Trigger deckt jede genau so beantragte Änderung und setzt
            # applied_at; das Journal steht unten im Eintrag „antrag_bestaetigt“.
            from . import teilnummern
            jetzt = teilnummern.nummern(item["id"])
            teilnummern.schreiben(item, [(cid, st, jetzt.get((cid, st), ""), neu or "")
                                         for (cid, st), neu in sorted(teile.items())], journal_an=False)
        # Der Trigger hat jede Änderung gedeckt und ihre Zeile verbraucht – fehlt eine, rollt alles zurück (409 mit Satz
        # statt 500; Prüfung Sicherheit, Befund 3 – _plan weist die bekannten Fälle schon beim Stellen ab).
        if any(not r["applied_at"] for r in gruppe(kid)):
            current_app.logger.error("Änderungsantrag %s: nicht vollständig angewendet", kid)
            raise Abgelehnt(NICHT_ANGEWENDET, 409)
        vorher = {s: item[s] for s in setzen}
        nachher = dict(setzen, antrag=kid, beantragt_von=k["created_by_name"], begruendung=k["reason"])
        if teile:
            vorher["bestandteil_nummern"] = [{"bestandteil": r["component_label"], "seriennummer": r["old_value"] or ""}
                                             for r in rows if r["field"] == "component_serial"]
            nachher["bestandteil_nummern"] = [{"bestandteil": r["component_label"], "seriennummer": r["new_value"] or ""}
                                              for r in rows if r["field"] == "component_serial"]
        if "serial_generated" in setzen:                 # im Journal als ja/nein wie beim Anlegen und Bearbeiten
            vorher["serial_generated"], nachher["serial_generated"] = True, False
        _produktnamen(vorher, nachher, item, wuensche)
        if antwort:
            nachher["anmerkung"] = antwort
        # Laufende Rückrufe, aus denen der Artikel danach fällt (oder in die er kommt) – bewusst entschieden.
        for schluessel, liste_ in (("rueckruf_nicht_mehr", folgen["nicht_mehr"]), ("rueckruf_neu", folgen["neu"])):
            if liste_:
                nachher[schluessel] = [f"{x['title']} (Nr. {x['id']})" for x in liste_]
        journal.eintragen("item", item["id"], "antrag_bestaetigt", vorher, nachher)
        # Ein kürzeres Intervall oder ein anderes Produkt zieht die Fälligkeit nach (eigener Eintrag, wie beim Bearbeiten).
        faelligkeit.kappen("i.id = ?", (item["id"],), zusatz={"antrag": kid})
    _antragsteller_benachrichtigen(kid)
    return kid


def ablehnen(aid, d):
    """Den Sammelantrag ablehnen – nur mit Begründung; am Artikel ändert sich nichts. Liefert die Antrag-Nr."""
    kid = kopf(aid)["id"]
    with db.transaction(sofort=True):
        k = antrag(kid)
        _entscheider(bestand.artikel(k["item_id"]))      # erst das Recht (404/403), dann die Eingabe
        antwort = text(d, "antwort", "Begründung", BEGRUENDUNG_MAX, pflicht=True, einzeilig=False)
        if k["status"] != "offen":
            raise Abgelehnt(ERLEDIGT, 409)
        rows = gruppe(kid)
        _entscheiden(kid, len(rows), "abgelehnt", antwort)
        journal.eintragen("item", k["item_id"], "antrag_abgelehnt", None,
                          {"antrag": kid, "feld": ", ".join(feld_text(r) for r in rows), "ablehnung": antwort})
    _antragsteller_benachrichtigen(kid)
    return kid


def zurueckziehen(aid):
    """Den eigenen offenen Antrag zurückziehen (Entscheidung vom 21.10.2026 zur Prüfung): nur der Antragsteller und nur,
    solange er den Artikel liest – sonst 404 wie unbekannt. Keine Mail; das Journal sagt „Änderungsantrag
    zurückgezogen“. Wer zweitens kommt (schon entschieden oder zurückgezogen), erfährt es (409). Liefert die Antrag-Nr."""
    uid, _ = akteur()
    kid = kopf(aid)["id"]
    with db.transaction(sofort=True):
        k = antrag(kid)
        item = bestand.artikel(k["item_id"])
        if not uid or k["created_by"] != uid or not rechte.darf_artikel("lesen", item):
            raise Abgelehnt(FEHLT, 404)
        if k["status"] != "offen":
            raise Abgelehnt(ERLEDIGT, 409)
        rows = gruppe(kid)
        _entscheiden(kid, len(rows), "zurueckgezogen", "")
        journal.eintragen("item", k["item_id"], "antrag_zurueckgezogen", None,
                          {"antrag": kid, "feld": ", ".join(feld_text(r) for r in rows)})
    return kid


# --- Mails ----------------------------------------------------------------------------------------------------------

def _verschicken(kid, mails, item, demo):
    """mails: [(an, betreff, text, Konto, Rolle)]. Liefert, ob etwas an den Versand ging (unter DEMO, Umgebungssperre oder
    ohne Mailserver geht nichts hinaus – mailprotokoll.senden schreibt Betreff und Text ins Log)."""
    if not mails:
        return False
    HINTERGRUND(_versenden, kid, mails, bestand.heimat(item), demo)
    return not mailprotokoll.still(demo)


def _versenden(kid, mails, folder_id=None, demo=False):
    """Läuft im Hintergrund (eigener App-Kontext). Jede Mail einzeln über mailprotokoll.senden (Bezug der Antrag,
    Ordner die Heimat des Artikels – eine Einzelmail wie beim Mangel); eine Adresse, an der es scheitert, hält die anderen
    nicht auf."""
    for an, betreff, inhalt, konto_id, rolle in mails:
        try:
            mailprotokoll.senden(an, betreff, inhalt, art="antrag", konto_id=konto_id, rolle=rolle, bezug_art="change",
                                 bezug_id=kid, folder_id=folder_id, demo=demo)
        except Exception as exc:                     # senden wirft nicht – eine Ausnahme hält trotzdem nichts auf
            current_app.logger.error("Änderungsantrag %s: Mail an Konto %s gescheitert: %s", kid, konto_id, exc)


def _kopfzeilen(item):
    produkt = katalog.produkt(item["product_id"])
    gl = bestand.gliederung_von(item["folder_id"])
    return [f"Artikel:       {item['inventory_no']} – {katalog.produktname(produkt)}",
            f"Gliederung:    {gl['name'] if gl else '(ohne Gliederung)'}",
            f"Ordner:        {bestand._pfad_text(bestand.heimat(item))}"]


def _aenderungen_text(rows):
    # Auf 15 Zeichen aufgefüllt, mindestens ein Leerzeichen nach dem Doppelpunkt (lange Feldnamen der Bestandteile).
    return [f"{feld_text(r) + ':':<14} {wert_text(r['field'], r['old_value'])} → "
            f"{wert_text(r['field'], r['new_value'])}" for r in rows]


def _adresse(u, demo):
    """Die Adresse eines Kontos für eine Antragsmail – keine DEMO-Adresse außer bei DEMO-Artikeln; sonst None."""
    adr = (u["email"] or "").strip()
    return adr if adr and (demo or not erinnerung.demo_adresse(adr)) else None


# --- Anträge ohne Materialwart (Wunsch vom 25.10.2026, N5) -------------------------------------------------------------

def _offen_je_ordner():
    """Offene Sammelanträge je Heimat ihres Artikels: {Ordner: Zahl}."""
    out = {}
    for r in db.query("SELECT item_id FROM mat_item_change WHERE group_id IS NULL AND status = 'offen'"):
        h = bestand.heimat(bestand.artikel(r["item_id"]))
        out[h] = out.get(h, 0) + 1
    return out


def ohne_verwalter_melden():
    """Ordner, in denen Anträge offen sind, die niemand mehr entscheiden darf (kein Konto mit eigener gültiger Freigabe
    „verwalten“ dort oder darüber, zustaendige_ordner): einmal je Wegfall eine Mail an die Material-Verwaltung
    (rechte.material_verwaltung_konten – dieselbe Regel wie beim Antrag ohne Zuständige und bei Produktmeldungen).
    Aufgerufen nach jedem Vorgang, der eine Verwalterfreigabe wegnehmen kann: Freigabe entziehen oder ändern, Konto
    deaktivieren, Stufe senken oder löschen (sofort, nach dem Commit) und im Tageslauf (abgelaufene Freigaben).
    Einmaligkeit über mat_antrag_ohne_verwalter (Schritt 29): gemeldet wird nur ein Ordner, der dort noch nicht steht;
    hat er wieder einen Verwalter oder keinen offenen Antrag mehr, verschwindet seine Zeile – ein späterer Wegfall meldet
    neu. Die Mail nennt nur Ordnerpfad, Gliederung und die Zahl der Anträge – keine Inhalte, keine Namen. Liefert, ob eine
    Mail an den Versand ging (DEMO, Umgebungssperre, ohne Mailserver: nur ins Log)."""
    if not db.query("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'mat_antrag_ohne_verwalter'", one=True):
        return False                                  # Schema vor Schritt 29 (nur in Tests, die früher anhalten)
    with db.transaction(sofort=True):
        # Unter der Schreibsperre gerechnet (Sicherheitsprüfung vom 26.10.2026): Rechnete ein Vorgang vorher, könnte er mit
        # altem Stand die Zeile eines gleichzeitigen löschen – der nächste Lauf meldete denselben Wegfall dann noch einmal.
        ohne = {fid: n for fid, n in _offen_je_ordner().items() if not zustaendige_ordner(fid)}
        gemeldet = {r["folder_id"] for r in db.query("SELECT folder_id FROM mat_antrag_ohne_verwalter")}
        weg = gemeldet - set(ohne)
        if weg:
            db.execute("DELETE FROM mat_antrag_ohne_verwalter WHERE folder_id IN (SELECT value FROM json_each(?))",
                       (json.dumps(sorted(weg)),))
        neu = sorted(set(ohne) - gemeldet)
        for fid in neu:
            db.execute("INSERT OR IGNORE INTO mat_antrag_ohne_verwalter (folder_id, gemeldet_at) VALUES (?, ?)",
                       (fid, db.now()))
    gesendet = False
    for fid in neu:
        gesendet = _ohne_verwalter_mail(fid, ohne[fid]) or gesendet
    return gesendet


def ohne_verwalter_nach_vorgang():
    """ohne_verwalter_melden nach einem Vorgang außerhalb dieses Dienstes (Freigaben, Konten) – nach dessen Commit; ein
    Fehler hier macht den Vorgang nicht ungeschehen, er steht nur im Protokoll der App. Liefert, ob eine Mail ging."""
    try:
        return ohne_verwalter_melden()
    except Exception as exc:
        current_app.logger.exception("Anträge ohne Materialwart: Prüfung gescheitert: %s", exc)
        return False


def _als_gemeldet(fid):
    """Ein Antrag, für den es schon beim Stellen keinen Zuständigen gab, ging mit seiner Mail an die Material-Verwaltung
    (_zustaendige_benachrichtigen) – der Ordner gilt damit als gemeldet. In der Transaktion des Aufrufers."""
    db.execute("INSERT OR IGNORE INTO mat_antrag_ohne_verwalter (folder_id, gemeldet_at) VALUES (?, ?)", (fid, db.now()))


def _ohne_verwalter_mail(fid, anzahl):
    demo = bestand.ordner_ist_demo(fid)
    an = [(_adresse(u, demo), u["id"]) for u in rechte.material_verwaltung_konten() if _adresse(u, demo)][:MAX_EMPFAENGER]
    if not an:
        current_app.logger.warning("Ordner %s: Anträge ohne Materialwart – niemand in der Material-Verwaltung erreichbar.",
                                   fid)
        return False
    cfg = current_app.config
    basis = (cfg.get("BASE_URL") or "").rstrip("/")
    ordner = bestand._pfad_text(fid)
    gl = bestand.gliederung_von(fid)
    anzahl_text = "1 offener Änderungsantrag wartet" if anzahl == 1 else f"{anzahl} offene Änderungsanträge warten"
    zeilen = [f"Der Ordner „{ordner}“ hat keinen Materialwart mehr (keine gültige Freigabe „verwalten“ dort oder "
              f"darüber). {anzahl_text} auf eine Entscheidung – entscheiden darf nur, wer dort verwaltet.", "",
              f"Gliederung:    {gl['name'] if gl else '(ohne Gliederung)'}", f"Ordner:        {ordner}", "",
              f"Freigabe vergeben (Ordner → Bearbeiten → Freigaben): {basis}/materialablage/ordner/{fid}?freigaben=",
              f"Änderungsanträge: {basis}{SEITE}", "",
              "Du bekommst diese Mail, weil du zur Material-Verwaltung gehörst. Sie kommt je Ordner einmal – erneut erst, "
              "wenn er wieder einen Materialwart hatte und ihn wieder verliert."]
    betreff = f"{cfg.get('SITE_NAME') or 'strömis.de'} – Änderungsanträge ohne Materialwart: {ordner}"
    if demo:
        betreff = f"[DEMO] {betreff}"
    mails = [(a, betreff, "\n".join(zeilen) + "\n", uid, "verwaltung") for a, uid in an]
    HINTERGRUND(_ohne_verwalter_versenden, fid, mails, demo)
    return not mailprotokoll.still(demo)


def _ohne_verwalter_versenden(fid, mails, demo=False):
    for an, betreff, inhalt, konto_id, rolle in mails:
        try:
            mailprotokoll.senden(an, betreff, inhalt, art="antrag", konto_id=konto_id, rolle=rolle, bezug_art="folder",
                                 bezug_id=fid, folder_id=fid, demo=demo)
        except Exception as exc:
            current_app.logger.error("Anträge ohne Materialwart (Ordner %s): Mail an Konto %s gescheitert: %s", fid,
                                     konto_id, exc)


def _zustaendige_benachrichtigen(kid):
    """Mail zu einem neuen Antrag an die zuständigen Materialwarte (zustaendige – ohne den Antragsteller, Rolle
    „verwalter“). Gibt es GAR kein zuständiges Konto, an die Material-Verwaltung (rechte.material_verwaltung_konten,
    Rolle „verwaltung“) mit dem Hinweis, dass sie sich die Verwalterfreigabe geben kann (E5, E6) – ist der Antragsteller
    selbst der einzige zuständige oder fehlen nur Adressen, an niemanden. Nie an DEMO-Adressen (außer bei DEMO-Artikeln,
    dann ohnehin nur ins Log). Eine Mail je Antrag (alle Felder zusammen). Liefert, ob sie an den Versand ging."""
    rows = gruppe(kid)
    k = rows[0]
    item = bestand.artikel(k["item_id"])
    demo = bestand.ist_demo(item["id"])
    zust = zustaendige(item)
    ordner = bestand._pfad_text(bestand.heimat(item))
    if zust:
        konten, rolle = zust, "verwalter"
        fuss = (f"Du bekommst diese Mail, weil du den Ordner „{ordner}“ verwaltest (Freigabe „verwalten“ dort oder "
                "darüber).")
    else:
        konten, rolle = rechte.material_verwaltung_konten(), "verwaltung"
        fuss = (f"Du bekommst diese Mail, weil der Ordner „{ordner}“ keinen Materialwart mit Freigabe „verwalten“ hat – "
                "du gehörst zur Material-Verwaltung. Entscheiden kannst du, sobald du dir dort (oder darüber) die "
                "Freigabe „verwalten“ gibst: Ordner → Bearbeiten → Freigaben.")
    an = [(_adresse(u, demo), u["id"]) for u in konten if u["id"] != k["created_by"] and _adresse(u, demo)]
    an = an[:MAX_EMPFAENGER]
    if not an:
        return False
    cfg = current_app.config
    basis = (cfg.get("BASE_URL") or "").rstrip("/")
    zeilen = [f"{k['created_by_name']} beantragt eine Änderung an den Stammdaten (seit der ersten Prüfung Teil des "
              "Prüfnachweises):", ""] + _kopfzeilen(item) + [""] + _aenderungen_text(rows)
    zeilen += ["", "Begründung:", k["reason"], "", f"Bestätigen oder ablehnen: {basis}{SEITE}", "", fuss]
    betreff = (f"{cfg.get('SITE_NAME') or 'strömis.de'} – Änderungsantrag: {item['inventory_no']} "
               f"({', '.join(feld_text(r) for r in rows)})")
    if demo:
        betreff = f"[DEMO] {betreff}"
    return _verschicken(kid, [(a, betreff, "\n".join(zeilen) + "\n", uid, rolle) for a, uid in an], item, demo)


def _antragsteller_benachrichtigen(kid):
    """Bescheid an den Antragsteller – nicht, wenn er selbst entschieden hat; nur an ein aktives Konto mit Adresse (keine
    DEMO-Adresse außer bei DEMO-Artikeln) und nur, wenn er den Artikel heute noch lesen darf (Grund- oder Prüfrecht an
    seiner Heimat – wie seine Liste der Anträge, _sichtbar). Die Mail nennt Gliederung, Werte und Begründung; hat er das
    Recht verloren (abgelaufene Prüffreigabe, Artikel in eine fremde Gliederung verschoben), geht gar keine hinaus – wie
    bei der Mangelmeldung (Prüfung vom 21.10.2026)."""
    rows = gruppe(kid)
    k = rows[0]
    if not k["created_by"] or k["created_by"] == k["resolved_by"]:
        return False
    u = db.query("SELECT * FROM users WHERE id = ?", (k["created_by"],), one=True)
    item = bestand.artikel(k["item_id"])
    demo = bestand.ist_demo(item["id"])
    if not u or not erinnerung._erreichbar(dict(u), demo):
        return False
    if not rechte.darf_artikel("lesen", item, dict(u)):
        current_app.logger.info("Änderungsantrag %s: kein Bescheid – der Antragsteller liest den Artikel nicht mehr.", kid)
        return False
    cfg = current_app.config
    basis = (cfg.get("BASE_URL") or "").rstrip("/")
    felder = ", ".join(feld_text(r) for r in rows)
    zeilen = [f"Hallo {(u['name'] or '').strip()},", ""]
    if k["status"] == "bestaetigt":
        betreff = f"Änderungsantrag bestätigt: {item['inventory_no']} ({felder})"
        zeilen += [f"{k['resolved_by_name']} hat deinen Antrag vom {_datum(k['created_at'])} bestätigt; die Änderung "
                   "steht jetzt am Artikel. Festgeschriebene Protokolle nennen weiter den alten Wert.", ""]
        zeilen += _kopfzeilen(item) + [""] + _aenderungen_text(rows)
        if k["answer"]:
            zeilen += ["", "Anmerkung:", k["answer"]]
    else:
        betreff = f"Änderungsantrag abgelehnt: {item['inventory_no']} ({felder})"
        zeilen += [f"{k['resolved_by_name']} hat deinen Antrag vom {_datum(k['created_at'])} abgelehnt; am Artikel "
                   "ändert sich nichts.", ""]
        zeilen += _kopfzeilen(item) + [""] + _aenderungen_text(rows) + ["", "Begründung:", k["answer"]]
    zeilen += ["", f"Artikel ansehen: {basis}/materialablage/artikel/{item['id']}"]
    betreff = f"{cfg.get('SITE_NAME') or 'strömis.de'} – {betreff}"
    if demo:
        betreff = f"[DEMO] {betreff}"
    return _verschicken(kid, [(u["email"].strip(), betreff, "\n".join(zeilen) + "\n", u["id"], "antragsteller")], item,
                        demo)
