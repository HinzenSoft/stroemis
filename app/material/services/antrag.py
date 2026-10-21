"""Änderungsanträge zu den festen Stammdaten (Entscheidungen des Nutzers vom 21.10.2026).

Seit der ersten abgeschlossenen Prüfung stehen Seriennummer und Herstelldatum eines Artikels fest (bestand.STAMMDATEN_FEST,
Trigger mat_item_stammdaten_fest) – beide stehen im Prüfprotokoll. Zwei Wege führen seitdem noch zu einer Änderung:

  1. Herstelldatum NACHTRAGEN (vorher leer → Wert) bei Material „Metall“: direkt im Dialog „Artikel … bearbeiten“, ohne
     Antrag (bestand.artikel_aendern). Bei textil (dort ohnehin Pflicht) und „sonstiges“ nicht; ändern und entfernen
     eines vorhandenen Herstelldatums bleibt gesperrt.
  2. Jede andere Änderung – ausdrücklich auch eine vom System vergebene STR-Nummer durch die echte Herstellernummer zu
     ersetzen – mit BEGRÜNDUNG BEANTRAGEN, ähnlich der Produktmeldung (meldung.py): Die Material-Verwaltung (die
     Plattform-Verwaltung zählt wie sie) bestätigt oder lehnt ab, im Katalog unter „Meldungen“ → „Änderungsanträge“.

Beantragen darf, wer den Artikel verwaltet (Materialwart) oder an ihm prüfen darf (Prüfer – sie sehen Abweichungen beim
Prüfen); die Route prüft das (requires_folder), der Dienst in der Transaktion am frisch gelesenen Artikel noch einmal.
Je Feld eine Zeile in mat_item_change (alter und neuer Wert, Begründung); höchstens ein offener Antrag je Artikel und
Feld. Ein ausgesonderter Artikel bekommt keinen Antrag mehr, ein ungeprüfter braucht keinen (dort geht es direkt).

Geprüft wird beim Antrag UND beim Bestätigen (der Stand kann sich geändert haben): Seriennummer nicht leer, nicht in der
Form „STR-…“ (die vergibt nur das System), je Produkt eindeutig (bestand._serie_frei – fremde Dublette protokolliert wie
beim Bearbeiten); Herstelldatum als Monat oder Tag, nicht in der Zukunft, nicht nach Kauf und Erstgebrauch, bei textil
nicht leer. Beim Bestätigen muss der Artikel noch den alten Wert tragen, sonst 409.

Bestätigt die Material-Verwaltung, schreibt der Dienst die Änderung in derselben Transaktion an den Artikel (eine
Herstellernummer ist danach keine STR-Nummer mehr; bei textil rechnet das Lebensende neu), der Trigger lässt genau diese
Änderung zu und markiert den Antrag als angewendet (applied_at) – er wirkt einmal. Das Journal des Artikels zeigt
Antrag, Bestätigung (alter und neuer Wert, Antragsteller, Bestätiger, Begründung) bzw. Ablehnung (mit Begründung); der
Lebenslauf ebenso. Festgeschriebene Protokolle und ihre PDFs bleiben, wie sie sind – sie nennen weiter den alten Wert.
Der Rückrufabgleich liest die Seriennummer am Artikel, trifft also die neue.

Ihren eigenen Antrag darf die Material-Verwaltung selbst bestätigen (einfachste Lösung; das Journal nennt beide Namen –
„Bitte bestätigen“ im CHANGELOG). Mails: neuer Antrag an die Material-Verwaltung (ohne sie die Plattform-Verwaltung, nicht an den
Antragsteller), Entscheidung an den Antragsteller (nicht, wenn er selbst entschieden hat). Bei DEMO-Artikeln, unter der
Umgebungssperre (dev) und ohne Mailserver stehen sie im Log statt im Postfach – wie bei der Mangelmeldung.

Anträge sind nach der Entscheidung unveränderlich (Trigger, models.TRIGGER_15_ANTRAG), lassen sich nicht löschen und
bleiben unbefristet mit dem Artikel; beim Löschen eines Kontos setzt die Datenbank nur die Kontokennung auf NULL, die
Namen bleiben (Handelnde, wie bei Prüfungen und Mangelmeldungen)."""
from flask import current_app

from ... import db
from ...auth import _im_hintergrund
from ...mailer import send_mail                    # Tests ersetzen antrag.send_mail
from ..models import ANTRAGSFELDER, ANTRAGSSTATUS
from . import Abgelehnt, akteur, erster_tag, heute, monat_oder_datum, text
from . import bestand, erinnerung, journal, katalog, nummern, rechte
from .interval import lebensende

BEGRUENDUNG_MAX = 1000
MAX_EMPFAENGER = 10
FILTER = {"offen": ("offen",), "erledigt": ("bestaetigt", "abgelehnt"), "alle": tuple(ANTRAGSSTATUS)}
FEHLT = "Änderungsantrag nicht gefunden."
NICHT_FEST = ("Der Artikel ist noch nicht geprüft – Seriennummer und Herstellung änderst du direkt im Dialog "
              "„Bearbeiten“.")
AUSGESONDERT = "Der Artikel ist ausgesondert – an ihm ändert sich nichts mehr."
NICHTS = "Bitte eine neue Seriennummer oder ein neues Herstelldatum angeben."
STR_GESPERRT = ("Seriennummern der Form „STR-…“ vergibt nur das System – bitte die Herstellernummer eintragen.")
NACHTRAGEN_DIREKT = ("Bei Metall trägt der Materialwart ein fehlendes Herstelldatum direkt im Dialog „Bearbeiten“ nach – "
                     "dafür braucht es keinen Antrag.")
SCHON_BEANTRAGT = "Für {feld} dieses Artikels läuft schon ein Antrag (vom {datum}) – er wartet auf die Material-Verwaltung."
ERLEDIGT = "Dieser Antrag ist schon entschieden. Bitte neu laden."
STAND_ANDERS = ("Der Artikel trägt inzwischen nicht mehr den Wert, den der Antrag ändern wollte – bitte ablehnen; der "
                "Antragsteller kann neu beantragen.")
NUR_ABLEHNEN = "Der Artikel ist inzwischen ausgesondert – den Antrag kannst du nur noch ablehnen."

# Mails gehen neben der Anfrage hinaus (wie bei der Mangelmeldung); Tests setzen hier einen direkten Aufruf ein.
HINTERGRUND = _im_hintergrund
# Ist ein Mailserver eingerichtet? Tests, die send_mail ersetzen, setzen hier lambda: True.
MAILSERVER = erinnerung.smtp_da


# --- Lesen ----------------------------------------------------------------------------------------------------------

def antrag(aid):
    r = db.query("SELECT * FROM mat_item_change WHERE id = ?", (aid,), one=True)
    if not r:
        raise Abgelehnt(FEHLT, 404)
    return r


def offene(iid):
    """Offene Anträge des Artikels, je Feld höchstens einer."""
    return db.query("SELECT * FROM mat_item_change WHERE item_id = ? AND status = 'offen' ORDER BY id", (iid,))


def darf_beantragen(item, user=None):
    """Materialwart (verwalten) oder Prüfer (wirksames Prüfrecht) an der Heimat des Artikels – die Material- und
    Plattform-Verwaltung zählen wie verwalten."""
    return rechte.darf_artikel("verwalten", item, user) or rechte.darf_artikel("pruefen", item, user)


def _datum(iso):
    from .protokoll import ortszeit
    return ortszeit(iso).strftime("%d.%m.%Y")


def wert_text(feld, wert):
    """Ein Wert, wie Mail und Oberfläche ihn zeigen: Herstelldatum als MM/JJJJ bzw. TT.MM.JJJJ, leer als „(leer)“."""
    if wert is None or wert == "":
        return "(leer)"
    if feld == "manufactured_on":
        teile = wert.split("-")
        return f"{teile[1]}/{teile[0]}" if len(teile) == 2 else f"{teile[2]}.{teile[1]}.{teile[0]}"
    return wert


def antrag_json(r, item=None, inhalt=True):
    """Ein Antrag. item: die Artikelzeile (sonst gelesen). inhalt=False (nur Leserecht am Artikel): ohne Begründung,
    Namen und Antwort – nur Feld, Werte, Stand und Zeitpunkte."""
    uid, _ = akteur()
    item = item or bestand.artikel(r["item_id"])
    out = {f: r[f] for f in ("id", "item_id", "status", "created_at", "resolved_at", "applied_at")}
    out.update({"feld": r["field"], "feld_text": ANTRAGSFELDER[r["field"]], "alt": r["old_value"], "neu": r["new_value"],
                "status_text": ANTRAGSSTATUS[r["status"]], "inhalt": inhalt,
                "eigen": bool(uid and r["created_by"] == uid),
                # Trägt der Artikel noch den alten Wert? Sonst lässt sich der offene Antrag nur noch ablehnen.
                "passt": item[r["field"]] == r["old_value"]})
    out["begruendung"] = r["reason"] if inhalt else None
    out["antwort"] = r["answer"] if inhalt else None
    out["antragsteller"] = r["created_by_name"] if inhalt else None
    out["entschieden_von"] = r["resolved_by_name"] if inhalt and r["status"] != "offen" else None
    return out


def _artikel_kurz(item):
    """Was die Liste der Anträge über den Artikel zeigt – für die Material-Verwaltung (sieht alles) und den
    Antragsteller (nur, solange er den Artikel liest: liste filtert)."""
    p = katalog.produkt(item["product_id"])
    gl = bestand.gliederung_von(item["folder_id"])
    return {"id": item["id"], "inventory_no": item["inventory_no"], "serial_no": item["serial_no"],
            "serial_generated": bool(item["serial_generated"]), "manufactured_on": item["manufactured_on"],
            "lock_state": item["lock_state"], "demo": bestand.ist_demo(item["id"]),
            "produkt": katalog.produkt_json(p), "gliederung": gl["name"] if gl else "",
            "pfad": bestand._pfad_text(bestand.heimat(item))}


def _sichtbar(user=None):
    """SQL-Bedingung über mat_item_change c (mit mat_item i) und ihre Parameter: Die Material-Verwaltung sieht alle
    Anträge, jedes andere Konto seine eigenen – solange es den Artikel liest."""
    from ...auth import current_user
    user = user or current_user()
    if not user or not rechte.zugang(user):
        return "0", []
    if rechte.ist_material_verwaltung(user):
        return "1", []
    return f"(c.created_by = ? AND {rechte.artikel_filter('i', user=user)})", [user["id"]]


def liste(filter_="offen", grenze=200):
    """Anträge nach Stand, soweit das Konto der Anfrage sie sehen darf: offene der Reihe nach (älteste zuerst),
    erledigte neueste zuerst. Je Eintrag mit dem Artikel (artikel)."""
    stati = FILTER.get(filter_) or FILTER["offen"]
    sichtbar, args = _sichtbar()
    rows = db.query(
        f"SELECT c.* FROM mat_item_change c JOIN mat_item i ON i.id = c.item_id "
        f"WHERE c.status IN ({','.join('?' * len(stati))}) AND {sichtbar} "
        + ("ORDER BY c.id" if stati == FILTER["offen"] else "ORDER BY COALESCE(c.resolved_at, c.created_at) DESC, c.id DESC")
        + " LIMIT ?", (*stati, *args, grenze))
    out = []
    for r in rows:
        item = bestand.artikel(r["item_id"])
        j = antrag_json(r, item)
        j["artikel"] = _artikel_kurz(item)
        out.append(j)
    return out


def anzahl_offen():
    """Offene Anträge, die das Konto der Anfrage sehen darf (die Material-Verwaltung: alle)."""
    sichtbar, args = _sichtbar()
    return db.query(f"SELECT COUNT(*) AS n FROM mat_item_change c JOIN mat_item i ON i.id = c.item_id "
                    f"WHERE c.status = 'offen' AND {sichtbar}", args, one=True)["n"]


def fuer_artikel(item, inhalt):
    """Offene Anträge am Artikel für die Artikelansicht (inhalt: Begründung und Namen – nur wer beantragen darf)."""
    return [antrag_json(r, item, inhalt) for r in offene(item["id"])]


# --- Prüfen ---------------------------------------------------------------------------------------------------------

def _seriennummer(item, neu):
    """Neue Seriennummer prüfen (beim Antrag und beim Bestätigen): nicht leer, nicht STR-…, je Produkt frei."""
    if not neu:
        raise Abgelehnt("Die neue Seriennummer fehlt.")
    if neu == item["serial_no"]:
        raise Abgelehnt("Die neue Seriennummer ist dieselbe wie die bisherige.")
    if nummern.sieht_generiert_aus(neu):
        raise Abgelehnt(STR_GESPERRT)
    bestand._serie_frei(item["product_id"], neu, ausser=item["id"])


def _herstellung(item, produkt, neu):
    """Neues Herstelldatum prüfen (beim Antrag und beim Bestätigen) – die Regeln aus bestand.artikel_werte."""
    if neu == item["manufactured_on"]:
        raise Abgelehnt("Das neue Herstelldatum ist dasselbe wie das bisherige.")
    if not neu:
        if produkt["material_kind"] == "textil":
            raise Abgelehnt("Bei textilem Material ist das Herstelldatum Pflicht – an ihm hängt die Lebensdauer.")
        return
    if erster_tag(neu) > heute():
        raise Abgelehnt("Das Herstelldatum liegt in der Zukunft.")
    for feld, name in (("purchased_on", "Kaufdatum"), ("first_use_on", "Erstgebrauch")):
        if item[feld] and bestand._vor(item[feld], neu):
            raise Abgelehnt(f"{name} ({wert_text('manufactured_on', item[feld])}) liegt vor dem neuen Herstelldatum.")


def _zustand(item):
    if item["lock_state"] == "ausgesondert":
        raise Abgelehnt(AUSGESONDERT, 409)
    if not bestand.stammdaten_fest(item["id"]):
        raise Abgelehnt(NICHT_FEST, 409)


def _wuensche(d, item, produkt):
    """{feld: neuer Wert} aus der Anfrage. serial_no: Text (leer = keine Änderung beantragt). manufactured_on: Monat
    oder Tag; mit herstellung_entfernen = ja das Entfernen (nur außer textil)."""
    out = {}
    sn = text(d, "serial_no", "Seriennummer", 80)
    if sn:
        out["serial_no"] = sn
    entfernen = d.get("herstellung_entfernen") in (True, 1, "1", "ja", "true")
    herst = monat_oder_datum(d.get("manufactured_on"), "Herstelldatum")
    if herst and entfernen:
        raise Abgelehnt("Herstelldatum ändern oder entfernen – nicht beides.")
    if herst or entfernen:
        out["manufactured_on"] = herst
    if not out:
        raise Abgelehnt(NICHTS)
    return out


# --- Beantragen -----------------------------------------------------------------------------------------------------

def stellen(iid, d):
    """Antrag stellen – je beantragtem Feld eine Zeile, alle mit derselben Begründung, ganz oder gar nicht. Liefert
    (Kennungen, mail)."""
    begruendung = text(d, "begruendung", "Begründung", BEGRUENDUNG_MAX, pflicht=True, einzeilig=False)
    uid, name = akteur()
    ids = []
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if not darf_beantragen(item):
            raise Abgelehnt("Beantragen dürfen Materialwarte und Prüfer dieses Artikels.", 403)
        _zustand(item)
        produkt = katalog.produkt(item["product_id"])
        wuensche = _wuensche(d, item, produkt)
        for feld in wuensche:
            da = db.query("SELECT created_at FROM mat_item_change WHERE item_id = ? AND field = ? AND status = 'offen'",
                          (iid, feld), one=True)
            if da:
                raise Abgelehnt(SCHON_BEANTRAGT.format(feld="die Seriennummer" if feld == "serial_no" else
                                                       "das Herstelldatum", datum=_datum(da["created_at"])), 409)
        if "serial_no" in wuensche:
            _seriennummer(item, wuensche["serial_no"])
        if "manufactured_on" in wuensche:
            if item["manufactured_on"] is None and produkt["material_kind"] == "metall_hardware":
                raise Abgelehnt(NACHTRAGEN_DIREKT, 409)
            _herstellung(item, produkt, wuensche["manufactured_on"])
        for feld, neu in wuensche.items():
            aid = db.execute(
                "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, created_by_name, "
                "created_at) VALUES (?,?,?,?,?,?,?,?)", (iid, feld, item[feld], neu, begruendung, uid, name, db.now()))
            ids.append(aid)
            journal.eintragen("item", iid, "antrag_gestellt", {feld: item[feld]},
                              {feld: neu, "antrag": aid, "begruendung": begruendung})
    return ids, _verwaltung_benachrichtigen(ids)


# --- Entscheiden (nur die Material-Verwaltung, die Route prüft das) ----------------------------------------------------

def _entscheiden(aid, status, antwort):
    """Innerhalb der Transaktion: Nur ein offener Antrag lässt sich entscheiden – wer zweitens kommt, erfährt es."""
    uid, name = akteur()
    if not db.execute_zeilen(
            "UPDATE mat_item_change SET status = ?, answer = ?, resolved_by = ?, resolved_by_name = ?, resolved_at = ? "
            "WHERE id = ? AND status = 'offen'", (status, antwort, uid, name, db.now(), aid)):
        raise Abgelehnt(ERLEDIGT, 409)


def bestaetigen(aid, d):
    """Antrag bestätigen und die Änderung übernehmen – in einer Transaktion, nach erneuter Prüfung am frisch gelesenen
    Artikel. Eine Anmerkung (antwort) ist freiwillig; sie steht in der Mail an den Antragsteller."""
    antwort = text(d, "antwort", "Anmerkung", BEGRUENDUNG_MAX, einzeilig=False)
    antrag(aid)
    with db.transaction(sofort=True):
        r = antrag(aid)
        if r["status"] != "offen":
            raise Abgelehnt(ERLEDIGT, 409)
        item = bestand.artikel(r["item_id"])
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt(NUR_ABLEHNEN, 409)
        feld, alt, neu = r["field"], r["old_value"], r["new_value"]
        if item[feld] != alt:
            raise Abgelehnt(STAND_ANDERS, 409)
        produkt = katalog.produkt(item["product_id"])
        vorher, nachher = {feld: alt}, {feld: neu}
        if feld == "serial_no":
            _seriennummer(item, neu)
            # Eine echte Herstellernummer ersetzt die vergebene – danach ist sie keine STR-Nummer mehr.
            setzen, werte = "serial_no = ?, serial_generated = 0", [neu]
            if item["serial_generated"]:
                vorher["serial_generated"], nachher["serial_generated"] = True, False
        else:
            _herstellung(item, produkt, neu)
            setzen, werte = "manufactured_on = ?", [neu]
            if produkt["material_kind"] == "textil":
                # Das Lebensende hängt am Herstelldatum: neu rechnen, ein von Hand vorgezogenes bleibt, wenn es früher liegt.
                rechnung = lebensende(neu, produkt["lifetime_years"])
                ende = bestand._lebensende_wirksam(rechnung, item["retire_by_manual"])
                if ende != item["retire_by"]:
                    setzen += ", retire_by = ?"
                    werte.append(ende)
                    vorher["retire_by"], nachher["retire_by"] = item["retire_by"], ende
        _entscheiden(aid, "bestaetigt", antwort)
        db.execute(f"UPDATE mat_item SET {setzen}, updated_at = ? WHERE id = ?", (*werte, db.now(), item["id"]))
        if not antrag(aid)["applied_at"]:              # der Trigger hat die Änderung gedeckt und den Antrag verbraucht
            raise RuntimeError("Änderungsantrag nicht angewendet.")
        nachher.update({"antrag": aid, "beantragt_von": r["created_by_name"], "begruendung": r["reason"]})
        if antwort:
            nachher["anmerkung"] = antwort
        journal.eintragen("item", item["id"], "antrag_bestaetigt", vorher, nachher)
    _antragsteller_benachrichtigen(aid)


def ablehnen(aid, d):
    """Antrag ablehnen – nur mit Begründung; am Artikel ändert sich nichts."""
    antwort = text(d, "antwort", "Begründung", BEGRUENDUNG_MAX, pflicht=True, einzeilig=False)
    antrag(aid)
    with db.transaction(sofort=True):
        r = antrag(aid)
        if r["status"] != "offen":
            raise Abgelehnt(ERLEDIGT, 409)
        _entscheiden(aid, "abgelehnt", antwort)
        journal.eintragen("item", r["item_id"], "antrag_abgelehnt", None,
                          {"antrag": aid, "feld": ANTRAGSFELDER[r["field"]], "ablehnung": antwort})
    _antragsteller_benachrichtigen(aid)


# --- Mails ----------------------------------------------------------------------------------------------------------

def _still(demo):
    """Warum keine Mail hinausgeht (dann steht sie im Log) – oder None."""
    return ("DEMO-Artikel" if demo else "Umgebungssperre" if erinnerung.gesperrt()
            else "kein Mailserver" if not MAILSERVER() else None)


def _verschicken(art, aid, mails, demo):
    """mails: [(an, betreff, text)]. Liefert, ob etwas an den Versand ging."""
    if not mails:
        return False
    still = _still(demo)
    if still:
        for an, betreff, inhalt in mails:
            current_app.logger.warning("Änderungsantrag %s (%s): Mail nicht verschickt (%s) – an %s\nBetreff: %s\n%s",
                                       aid, art, still, an, betreff, inhalt)
        return False
    HINTERGRUND(_versenden, aid, mails)
    return True


def _versenden(aid, mails):
    """Läuft im Hintergrund (eigener App-Kontext). Jede Mail einzeln; eine Adresse, an der es scheitert, hält die
    anderen nicht auf."""
    for an, betreff, inhalt in mails:
        try:
            if not send_mail(an, betreff, inhalt):
                current_app.logger.error("Änderungsantrag %s: Mail an %s gescheitert", aid, an)
        except Exception as exc:                     # send_mail wirft nicht – eine Ausnahme hält trotzdem nichts auf
            current_app.logger.error("Änderungsantrag %s: Mail an %s gescheitert: %s", aid, an, exc)


def _kopf(item):
    produkt = katalog.produkt(item["product_id"])
    gl = bestand.gliederung_von(item["folder_id"])
    return produkt, [f"Artikel:      {item['inventory_no']} – {katalog.produktname(produkt)}",
                     f"Gliederung:   {gl['name'] if gl else '(ohne Gliederung)'}"]


def _verwaltung_benachrichtigen(ids):
    """Mail zu einem neuen Antrag an die Material-Verwaltung – gibt es keine, an die Plattform-Verwaltung
    (rechte.material_verwaltung_konten); nicht an den Antragsteller, nie an DEMO-Adressen (außer bei DEMO-Artikeln, dann
    ohnehin nur ins Log). Eine Mail je Antrag (alle Felder zusammen). Liefert, ob sie an den Versand ging."""
    rows = [antrag(a) for a in ids]
    r0 = rows[0]
    item = bestand.artikel(r0["item_id"])
    demo = bestand.ist_demo(item["id"])
    an = [u["email"].strip() for u in rechte.material_verwaltung_konten()
          if (u["email"] or "").strip() and u["id"] != r0["created_by"]
          and (demo or not erinnerung.demo_adresse(u["email"]))][:MAX_EMPFAENGER]
    if not an:
        return False
    cfg = current_app.config
    basis = (cfg.get("BASE_URL") or "").rstrip("/")
    _, kopf = _kopf(item)
    zeilen = [f"{r0['created_by_name']} beantragt eine Änderung an festen Stammdaten (seit der ersten Prüfung Teil "
              "des Prüfnachweises):", ""] + kopf + [""]
    for r in rows:
        zeilen.append(f"{ANTRAGSFELDER[r['field']] + ':':<14}{wert_text(r['field'], r['old_value'])} → "
                      f"{wert_text(r['field'], r['new_value'])}")
    zeilen += ["", "Begründung:", r0["reason"], "",
               f"Bestätigen oder ablehnen: {basis}/material/katalog/meldungen?bereich=antraege", "",
               "Du bekommst diese Mail, weil du zur Material-Verwaltung gehörst."]
    betreff = (f"{cfg.get('SITE_NAME') or 'strömis.de'} – Änderungsantrag: {item['inventory_no']} "
               f"({', '.join(ANTRAGSFELDER[r['field']] for r in rows)})")
    if demo:
        betreff = f"[DEMO] {betreff}"
    return _verschicken("neu", r0["id"], [(a, betreff, "\n".join(zeilen) + "\n") for a in an], demo)


def _antragsteller_benachrichtigen(aid):
    """Bescheid an den Antragsteller – nicht, wenn er selbst entschieden hat; nur an ein aktives Konto mit Adresse (keine
    DEMO-Adresse außer bei DEMO-Artikeln)."""
    r = antrag(aid)
    if not r["created_by"] or r["created_by"] == r["resolved_by"]:
        return False
    u = db.query("SELECT * FROM users WHERE id = ?", (r["created_by"],), one=True)
    item = bestand.artikel(r["item_id"])
    demo = bestand.ist_demo(item["id"])
    if not u or not erinnerung._erreichbar(dict(u), demo):
        return False
    cfg = current_app.config
    basis = (cfg.get("BASE_URL") or "").rstrip("/")
    _, kopf = _kopf(item)
    feld = ANTRAGSFELDER[r["field"]]
    aenderung = f"{feld}: {wert_text(r['field'], r['old_value'])} → {wert_text(r['field'], r['new_value'])}"
    zeilen = [f"Hallo {(u['name'] or '').strip()},", ""]
    if r["status"] == "bestaetigt":
        betreff = f"Änderungsantrag bestätigt: {item['inventory_no']} ({feld})"
        zeilen += [f"{r['resolved_by_name']} hat deinen Antrag vom {_datum(r['created_at'])} bestätigt; die Änderung "
                   "steht jetzt am Artikel. Festgeschriebene Protokolle nennen weiter den alten Wert.", ""]
        zeilen += kopf + [aenderung]
        if r["answer"]:
            zeilen += ["", "Anmerkung:", r["answer"]]
    else:
        betreff = f"Änderungsantrag abgelehnt: {item['inventory_no']} ({feld})"
        zeilen += [f"{r['resolved_by_name']} hat deinen Antrag vom {_datum(r['created_at'])} abgelehnt; am Artikel "
                   "ändert sich nichts.", ""]
        zeilen += kopf + [aenderung, "", "Begründung:", r["answer"]]
    zeilen += ["", f"Artikel ansehen: {basis}/material/artikel/{item['id']}"]
    betreff = f"{cfg.get('SITE_NAME') or 'strömis.de'} – {betreff}"
    if demo:
        betreff = f"[DEMO] {betreff}"
    return _verschicken(r["status"], aid, [(u["email"].strip(), betreff, "\n".join(zeilen) + "\n")], demo)
