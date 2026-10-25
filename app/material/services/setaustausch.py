"""Teile entnehmen, tauschen, einsetzen und löschen, Set aussondern (Phase 4 · Lieferung 2, Entwurf G, C und D, Paket K2).

Regeln, wie sie hier umgesetzt sind:
  - Teil entnehmen (Materialwart, entnehmen): Verbleib „weiterfuehren“ – aus einem gesperrten Set mit eigener Sperre „aus
    gesperrtem Set entnommen“ (Herkunft bleibt die Heimat des Sets; eine eigene Sperre behält ihren Grund), aus einem
    freien Set frei im Ordner des Sets – oder „aussondern“, nur mit den Vorbedingungen von pruefung.aussondern (eigene
    Sperre durch einen Prüfer oder verloren, keine ungeprüfte Mangelmeldung, Datumsgrenzen; Kritik A15, S11). Bedingtes
    UPDATE … WHERE id = ? AND parent_item_id = ? mit Zeilenzahl-Prüfung (Doppelklick, Wettlauf); offener Entwurf am Teil
    → 409; seine Zeile im Durchgang bleibt. Das entnommene Teil verliert seine Zuordnung (Journal, S16); das Set ist
    danach unvollständig und gesperrt (Entwurf D, A25). An einer Position mit „Austausch laut Hersteller: nein“ geht
    Entnehmen nicht (409 – dann das Set aussondern, Entwurf G; Nachbesserung, Ablauf N3).
  - Teil tauschen bzw. einsetzen (einsetzen): altes Teil entnehmen wie oben (beim Tauschen) und ein neues Teil anlegen –
    Produkt laut Kopie der Stückliste, nie aus der Anfrage, Daten wie beim Set anlegen, Ordner die Heimat des Sets.
    „Austausch laut Hersteller“ der Position: „nein“ → 409 (dann nur Set aussondern), „nicht belegt“ → Pflichtbestätigung
    „laut Herstellerunterlagen zulässig“ („bestaetigt“, Journal am Set – nach der Katalog-Recherche ist bei Petzl und Kong
    alles „nicht belegt“), „ja“ ohne. Das neue Teil übernimmt Lage, Sperre und Zuordnung des Sets und ist im Freigabe-Lauf
    zu prüfen; das Set ist gesperrt („Teil getauscht – Set prüfen“ bzw. „Teil eingesetzt – Set prüfen“).
  - Teil löschen (teil_loeschen, aus bestand.artikel_loeschen): nur ohne Prüfung, Mangelmeldung und Durchgangszeile; das
    Set ist danach unvollständig und gesperrt.
  - Set aussondern (Materialwart über pruefung.aussondern am Set-Artikel – dazu: mindestens ein eigener Grund im Set oder
    verloren, keine ungeprüfte Meldung an Set oder Teil, Datumsgrenzen auch der mit ausgesonderten Teile) und Ergebnis
    „aussondern“ am Set-Artikel (setlauf.wirkung): je Teil „mit aussondern“ oder „entnehmen und gesperrt weiterführen“
    (Vorbelegung sets.verbleib_vorschlag). Ein nur mitgesperrtes Teil darf mit ausgesondert werden – das Set als Ganzes
    hat ein Prüfer gesperrt bzw. ausgesondert (Entwurf L Nr. 8). Mit ausgesonderte Teile bleiben am Set (Lebenslauf),
    jedes mit eigenem Aussonderungsprotokoll; weitergeführte sind gesperrt mit eigenem Grund „aus ausgesondertem Set
    entnommen“, Herkunft die Heimat des Sets, bis zur Freiprüfung durch einen Prüfer.
  - Ergebnis „aussondern“ an einem Teil (teil_aus_pruefung): Das Teil verlässt das Set und ist ausgesondert – wie
    entnehmen mit Verbleib „aussondern“, der Sachkundige hat es eben gesehen; das Set ist unvollständig und gesperrt. Bei
    „Austausch laut Hersteller: nein“ bleibt das Teil gesperrt im Set (eigene Sperre, pruefung._wirkung_im_set) – der
    Materialwart sondert dann das Set aus.
  - Set aussondern beendet eine offene Set-Prüfung (abgebrochen, Journal mit Grund „Set ausgesondert“; Sicherheit 4).
  - Eine Teil-Kennung, die nicht zu diesem Set gehört (fremd oder unbekannt): 404 wie unbekannt. Journal an Set und Teil;
    der Lebenslauf des Sets zeigt nur Einträge am Set selbst („teil_entnommen“, „teil_eingesetzt“, „teil_geloescht“,
    „teil_gesperrt“, „bestandteil_ersetzt“) – nie Teil-Journale per Kennung (S15).

Seit P4-L2b (Entwurf A und B, Kritiken T1–T16 und U1–U16):
  - Vorhandenen Artikel einsetzen (vorhandenen_einsetzen) – beim Set anlegen („teile[].item_id“, sets.set_anlegen) und
    bei „Teil einsetzen“ („item_id“), nie beim Tauschen (400). Alles in der Transaktion am frisch gelesenen Artikel, in
    dieser Reihenfolge (T6): Sicht (verwalten an seiner Heimat, sonst 404 wie unbekannt) → Produkt der Position (409 mit
    beiden Namen) → dieselbe Gliederung und DEMO-Grenze (409, „erst verschieben“) → Zustände (409): frei, kein Teil, kein
    Set, kein offener Entwurf, keine offene Meldung, kein offener Rückruf (frisch, ungefiltert), nicht „Lebensdauer
    erreicht“, eine Lücke an der Position, keine Prüfung im offenen Lauf dieses Sets (T2). Dann EIN bedingtes UPDATE mit
    dem gelesenen Ordner und der gelesenen Zuordnung (U9), danach – außer beim Anlegen – sets.sperren(…, neu=[Artikel]),
    erst danach durchgang.nach_verschieben und faelligkeit.kappen nach der Heimat des Sets (T3). Journal am Teil
    („verschoben“, „zuordnung_geloest“/„zugeordnet“, „eingesetzt“), am Set „teil_eingesetzt“ mit „vorhanden“ ohne
    Herkunftspfad (T14). Auswahl: kandidaten (Kennung, Nummern, Produkt, Ordnerpfad, Status, Zuordnung).
  - Set auflösen (aufloesen): nur ein freies Set (T1, U1), das allein löschbar ist (keine Prüfung, Meldung,
    Durchgangszeile, kein Antrag, kein Set-Lauf mit Prüfung – ein offener ohne Prüfung endet), ohne offenen Entwurf an
    einem Teil und ohne abgeschlossene Prüfung an einem Teil, seit es im Set ist (deren Protokoll nennt das Set). Die Teile
    bleiben frei im Ordner des Sets mit ihrer Zuordnung (Journal „aus_set_geloest“), der Set-Artikel wird gelöscht – sein
    letzter Eintrag ist „geloescht“ (T7, S15).
  - „Bestandteil ersetzt“ (bestandteil_ersetzt) an einer nicht einzeln geführten Position: „Austausch laut Hersteller“
    „ja“, „nicht belegt“ nur mit Bestätigung, „nein“ 409; nicht bei offenem Entwurf am Set-Artikel (T5, U5). Journal am
    Set, Sperre wie beim Tausch (set_grund „bestandteil“), danach die Marke an der Set-Zeile (sets.bestandteil_markieren,
    T4). Das Lebensende des Sets bleibt."""
import json
import re
from datetime import datetime, timedelta, timezone

from ... import db
from ..models import AUSSONDERUNGSGRUENDE
from . import Abgelehnt, auswahl, datum, heute, kennung, text, wahr
from . import bestand, journal, katalog, protokoll, rechte, sets
from . import status as st

AUS_GESPERRTEM_SET = "aus gesperrtem Set entnommen"
AUS_AUSGESONDERTEM_SET = "aus ausgesondertem Set entnommen"
NUR_SET = "Teile gibt es nur an einem Set."
NICHT_AUSTAUSCHBAR = ("„{bez}“ ist laut Hersteller nicht austauschbar – fällt ein solches Teil aus, wird das ganze Set "
                      "ausgesondert (die übrigen Teile lassen sich dabei entnehmen und weiterführen).")
BESTAETIGEN = ("Für „{bez}“ ist nicht belegt, ob der Hersteller den Austausch zulässt – bitte bestätigen, dass er laut "
               "Herstellerunterlagen zulässig ist.")
BESTAETIGT = "laut Herstellerunterlagen zulässig"
NUR_MIT_PRUEFERSPERRE = ("Aussondern lässt sich ein Teil nur mit eigener Sperre durch einen Prüfer oder wenn es verloren "
                         "ist – sonst „weiterführen“; danach sperrt ein Prüfer oder prüft mit „aussondern“.")
SCHON_ENTNOMMEN = "Das Teil wurde inzwischen anderswo entnommen – bitte neu laden."
# Vorhandenen Artikel einsetzen (L2b, Entwurf A).
NUR_NEU_TAUSCHEN = ("Tauschen geht nur mit einem neuen Teil – einen vorhandenen Artikel setzt du ein, nachdem das alte "
                    "Teil entnommen ist („Teil entnehmen“, dann „Teil einsetzen“).")
NICHT_BEIDES = "Entweder einen vorhandenen Artikel („item_id“) oder die Angaben eines neuen Teils – nicht beides."
# Die Auswahl verlinkt den Artikel (Browser V12). Seit dem Feintuning (L2b Nr. 29, 23.10.2026) hat „Bearbeiten“ ein
# Produktfeld, solange der Artikel ungeprüft ist – dann nennt der Satz den Weg dorthin (PRODUKT_WEG, bestand.produkt_aenderbar).
ANDERES_PRODUKT = "{inv} ist {ist}; an dieser Position steht {soll}. Einsetzen lässt sich nur ein Artikel dieses Produkts."
PRODUKT_WEG = " Ist das Produkt am Artikel falsch: Artikel öffnen → Bearbeiten → Produkt."
ANDERE_GLIEDERUNG = ("{inv} liegt in einer anderen Gliederung als das Set – erst in die Gliederung des Sets verschieben "
                     "(„Verschieben“), dann einsetzen.")
INZWISCHEN_GEAENDERT = "{inv} wurde inzwischen geändert (Ordner, Sperre oder Zuordnung) – bitte neu laden."
KEIN_KANDIDAT = "Kein passender Artikel gefunden."      # zeigt die Oberfläche bei leerer Trefferliste (material.js)
KANDIDATEN_MAX = 20
KANDIDATEN_SEITE = 200                # so viele Zeilen liest die Auswahl je Seite der Vorauswahl (kandidaten)
SUCHE_MIN, SUCHE_MAX = 2, 80
BISHERIGE = "Bisherige Inventarnummer: "             # wie bestandsimport (Zeile der Bemerkung)
_BISHERIGE = re.compile(r"^" + re.escape(BISHERIGE) + r"(.*)$", re.MULTILINE)
# Set auflösen (L2b, Entwurf A; Kritiken T1, T7, U1, U3).
AUFGELOEST = "Set aufgelöst"
NUR_FREIES_SET = ("Auflösen lässt sich nur ein freies Set – ein gesperrtes gibt nur „Set prüfen“ frei; einzelne Teile "
                  "verlassen es über „Teil entnehmen“.")
# „Bestandteil ersetzt“ (L2b, Entwurf B; Kritiken T4, T5, T15, U5, U13; Nachbesserung).
BEMERKUNG_MAX = 200
DOPPELT_SEKUNDEN = 60                 # derselbe Eintrag in dieser Zeit noch einmal: 409 (Doppelklick)
SCHON_EINGETRAGEN = "Der Ersatz von „{bez}“ ist schon eingetragen (eben, mit demselben Datum und derselben Bemerkung)."
VOR_ERFASSUNG = "„Ersetzt am“ liegt vor der Erfassung des Sets ({datum}) – frühestens an diesem Tag."
NICHT_ENTNEHMBAR = ("Laut Hersteller nicht austauschbar – das Set aussondern. „{bez}“ lässt sich nicht einzeln entnehmen; "
                    "beim Aussondern des Sets lassen sich die übrigen Teile entnehmen und weiterführen.")


def _set(set_id):
    s = bestand.artikel(set_id)
    if s["parent_item_id"] or not sets.ist_set_artikel(s):
        raise Abgelehnt(NUR_SET, 409)
    if s["lock_state"] == "ausgesondert":
        raise Abgelehnt("Das Set ist ausgesondert.", 409)
    return s


def _teil(set_id, tid):
    """Das Teil – nur, wenn es (noch) zu diesem Set gehört; sonst 404 wie unbekannt (Entwurf H)."""
    t = db.query("SELECT * FROM mat_item WHERE id = ?", (tid,), one=True)
    if not t or t["parent_item_id"] != set_id:
        raise Abgelehnt(sets.TEIL_FEHLT, 404)
    return t


def _position(set_id, t):
    """Die Position der Kopie, die das Teil belegt (sets._zuteilen) – oder None."""
    _, tz = sets.zeilen(set_id)
    zu, _ = sets._zuteilen(sets.slots(set_id), tz)
    return zu.get(t["id"])


def _bezeichnung(set_id, t):
    z = _position(set_id, t)
    return z["bezeichnung"] if z else katalog.produktname(katalog.produkt(t["product_id"]))


def aussondern_angaben(d, akteur):
    """Grund (AUSSONDERUNGSGRUENDE), Bemerkung und Datum einer Aussonderung durch den Materialwart – wie
    pruefung.aussondern, vor jeder Sperre geprüft."""
    if not akteur.get("unterschrift"):
        raise Abgelehnt("Zum Aussondern fehlt deine Unterschrift – das Aussonderungsprotokoll wird damit festgeschrieben. "
                        "Bitte im Profil hinterlegen.", 403)
    art = auswahl(d.get("grund"), AUSSONDERUNGSGRUENDE, "Grund der Aussonderung")
    tag = datum(d.get("datum"), "Datum") or heute().isoformat()
    if tag > heute().isoformat():
        raise Abgelehnt("Das Datum der Aussonderung liegt in der Zukunft.")
    return {"grund": AUSSONDERUNGSGRUENDE[art], "bemerkung": text(d, "bemerkung", "Bemerkung", 2000, einzeilig=False),
            "tag": tag}


def _aussondern_pruefen(t, tag):
    """Die Vorbedingungen von pruefung.aussondern für ein Teil: eigene Sperre (Prüfer) oder verloren, keine ungeprüfte
    Mangelmeldung (am mitgesperrten Teil stammt der eigene Grund sonst womöglich allein aus ihr), Datumsgrenzen."""
    from . import mangel, pruefung
    if t["lock_state"] not in ("gesperrt", "verloren") or (t["lock_cause"] != "eigen" and t["lock_state"] != "verloren"):
        raise Abgelehnt(NUR_MIT_PRUEFERSPERRE, 409)
    if mangel.ungeprueft(t["id"]):
        raise Abgelehnt(mangel.NUR_GEMELDET, 409)
    pruefung.aussondern_grenzen(t, tag)


def _entnehmen(s, t, verbleib, aus, akteur, ts=None):
    """Ein Teil aus dem Set nehmen (in der Transaktion des Aufrufers) – siehe Kopf. Das Set sperrt der Aufrufer."""
    from . import pruefung
    offen = pruefung.offener_entwurf(t["id"])
    if offen:
        raise Abgelehnt(pruefung.reserviert_text(offen) + " Erst abschließen oder die Reservierung aufheben.", 409)
    if verbleib == "aussondern":
        _aussondern_pruefen(t, aus["tag"])
    gesperrt = s["lock_state"] != "frei"
    ursache = "eigen" if gesperrt else None
    grund = (t["lock_reason"] if t["lock_cause"] == "eigen" else AUS_GESPERRTEM_SET) if gesperrt else ""
    if not db.execute_zeilen("UPDATE mat_item SET parent_item_id = NULL, assigned_user_id = NULL, lock_cause = ?, "
                             "lock_reason = ?, set_pruefen = 0, updated_at = ? WHERE id = ? AND parent_item_id = ?",
                             (ursache, grund, db.now(), t["id"], s["id"])):
        raise Abgelehnt(SCHON_ENTNOMMEN, 409)
    nachher = {"set": None, "verbleib": verbleib}
    if gesperrt:
        nachher.update(lock_cause="eigen", lock_reason=grund)
    journal.eintragen("item", t["id"], "entnommen",
                      {"set": s["id"], "set_inventar": s["inventory_no"], "lock_cause": t["lock_cause"]}, nachher)
    if t["assigned_user_id"]:
        journal.eintragen("item", t["id"], "zuordnung_geloest", None,
                          {"konto": journal.konto_ref(t["assigned_user_id"]), "grund": "aus dem Set entnommen"})
    if verbleib == "aussondern":
        pruefung._aussondern(bestand.artikel(t["id"]), aus["grund"], aus["bemerkung"], aus["tag"], akteur, ts=ts)


def entnehmen(set_id, d, akteur):
    """„Teil entnehmen“: {"teil_id", "verbleib": "weiterfuehren" (Vorgabe) | "aussondern", bei „aussondern“ dazu "grund"
    (AUSSONDERUNGSGRUENDE), "bemerkung", "datum"}. Liefert die Kennung des Teils."""
    tid = kennung(d.get("teil_id"), "Teil")
    verbleib = auswahl(d.get("verbleib") or "weiterfuehren", sets.VERBLEIB, "Verbleib")
    aus = aussondern_angaben(d, akteur) if verbleib == "aussondern" else None
    with protokoll.dateien_sichern(), db.transaction(sofort=True):
        s = _set(set_id)
        t = _teil(set_id, tid)
        z = _position(set_id, t)
        bez = z["bezeichnung"] if z else _bezeichnung(set_id, t)
        if z and z["austausch"] == "nein":
            raise Abgelehnt(NICHT_ENTNEHMBAR.format(bez=bez), 409)
        _entnehmen(s, t, verbleib, aus, akteur)
        journal.eintragen("item", set_id, "teil_entnommen", None,
                          {"teil": t["inventory_no"], "bestandteil": bez, "verbleib": verbleib})
        sets.sperren(set_id, set_grund="unvollstaendig",
                     anlass=sets.UNVOLLSTAENDIG.format(bez=f"„{bez}“", was="ausgesondert" if aus else "entnommen"))
    return tid


# Die Oberfläche schickt zur Position deren Produkt bzw. Bezeichnung mit; passt die Position nicht mehr (die Stückliste
# wurde inzwischen übertragen – neue Kennungen, eine alte kann später einer anderen Position gehören), 409 statt eines
# stillen Treffers (Prüfung Sicherheit, Befund 1). Ohne die Angabe bleibt es bei 404 für eine unbekannte Position.
UEBERTRAGEN = "Die Stückliste dieses Sets wurde inzwischen übertragen – bitte die Seite neu laden."


def _position_passt(z, d, einzeln):
    """z: die Position zur Kennung (oder None). d: Anfrage mit „produkt_id“ (einzeln geführt) bzw. „bezeichnung“."""
    if einzeln:
        roh = d.get("produkt_id")
        erwartet = kennung(roh, "Produkt der Position", leer_erlaubt=True)
        if erwartet is None:
            return
        if not z or z["product_id"] != erwartet:
            raise Abgelehnt(UEBERTRAGEN, 409)
        return
    erwartet = d.get("bezeichnung")
    if erwartet in (None, ""):
        return
    if not z or z["bezeichnung"] != str(erwartet):
        raise Abgelehnt(UEBERTRAGEN, 409)


def einsetzen(set_id, d, akteur, tausch):
    """„Teil tauschen“ (tausch: altes Teil „teil_id“ entnehmen mit „verbleib“ wie entnehmen) bzw. „Teil einsetzen“ in eine
    Position, an der eines fehlt („slot_id“ – bei genau einer fehlenden Position darf sie fehlen) – und ein neues Teil
    anlegen: Felder wie beim Set anlegen (sets.TEIL_FELDER), "bestaetigt" bei „Austausch laut Hersteller: nicht belegt“.
    Beim Einsetzen statt der Felder „item_id“: einen vorhandenen Artikel einsetzen (vorhandenen_einsetzen; mit Feldern
    400). Beim Tauschen gibt es „item_id“ nicht (400 – erst entnehmen, dann einsetzen). Liefert (Kennung des neuen bzw.
    eingesetzten Teils, Hinweise)."""
    if tausch and d.get("item_id") not in (None, ""):
        raise Abgelehnt(NUR_NEU_TAUSCHEN)
    alt_id = kennung(d.get("teil_id"), "Teil") if tausch else None
    slot_id = None if tausch else kennung(d.get("slot_id"), "Position", leer_erlaubt=True)
    verbleib = auswahl(d.get("verbleib") or "weiterfuehren", sets.VERBLEIB, "Verbleib") if tausch else None
    aus = aussondern_angaben(d, akteur) if verbleib == "aussondern" else None
    bestaetigt = wahr(d, "bestaetigt", "Austausch laut Herstellerunterlagen zulässig")
    felder = {f: d[f] for f in sets.TEIL_FELDER if f in d}
    vorhanden_id = None if tausch else kennung(d.get("item_id"), "Artikel", leer_erlaubt=True)
    if vorhanden_id is not None and any(v not in (None, "") for v in felder.values()):
        raise Abgelehnt(NICHT_BEIDES)
    hinweise = []
    with protokoll.dateien_sichern(), db.transaction(sofort=True):
        s = _set(set_id)
        _, tz = sets.zeilen(set_id)
        sz = sets.slots(set_id)
        zu, vorhanden = sets._zuteilen(sz, tz)
        t = None
        if tausch:
            t = _teil(set_id, alt_id)
            z = zu.get(t["id"])
            if not z:
                raise Abgelehnt("Zu diesem Teil steht keine Position in der Stückliste des Sets – tauschen geht nicht, "
                                "entnehmen geht.", 409)
        else:
            offen = [x for x in sz if x["einzeln"] and vorhanden.get(x["id"], 0) < x["anzahl"]]
            if slot_id is not None:
                z = next((x for x in sz if x["id"] == slot_id and x["einzeln"]), None)
                _position_passt(z, d, True)
                if not z:
                    raise Abgelehnt("Position nicht gefunden.", 404)
                if z not in offen:
                    raise Abgelehnt(f"An „{z['bezeichnung']}“ fehlt kein Teil – ein vorhandenes ersetzt „Teil tauschen“.", 409)
            elif not offen:
                raise Abgelehnt("Das Set ist vollständig – ein vorhandenes Teil ersetzt „Teil tauschen“.", 409)
            elif len(offen) > 1:
                raise Abgelehnt("Bitte die Position wählen („slot_id“) – es fehlen Teile an mehreren Positionen.")
            else:
                z = offen[0]
        if z["austausch"] == "nein":
            raise Abgelehnt(NICHT_AUSTAUSCHBAR.format(bez=z["bezeichnung"]), 409)
        if z["austausch"] == "nicht_belegt" and not bestaetigt:
            raise Abgelehnt(BESTAETIGEN.format(bez=z["bezeichnung"]))
        if vorhanden_id is not None:
            n = vorhandenen_einsetzen(s, z["product_id"], z["bezeichnung"], vorhanden_id, bestand.heimat(s))
            eintrag = {"teil": n["inventory_no"], "serial_no": n["serial_no"], "bestandteil": z["bezeichnung"],
                       "austausch": z["austausch"], "vorhanden": True}
            if z["austausch"] == "nicht_belegt":
                eintrag["bestaetigt"] = BESTAETIGT
            journal.eintragen("item", set_id, "teil_eingesetzt", None, eintrag)
            sets.set_stimmig(set_id)
            return n["id"], hinweise
        try:
            plan = bestand.artikel_plan(dict(felder, product_id=z["product_id"], folder_id=bestand.heimat(s)))
        except Abgelehnt as exc:
            raise Abgelehnt(f"Neues Teil „{z['bezeichnung']}“: {exc}", exc.code)
        if t:
            _entnehmen(s, t, verbleib, aus, akteur)
        neu = sets.teil_schreiben(plan, z["bezeichnung"], "Neues Teil",
                                  journal_zusatz={"set": set_id, "set_inventar": s["inventory_no"]}, parent_id=set_id)
        n = bestand.artikel(neu)
        if n["serial_generated"]:
            hinweise.append(sets._hinweis_str(sets.STR_HINWEIS, n["inventory_no"], plan["p"], n["serial_no"]))
        if s["assigned_user_id"]:
            if s["lock_state"] == "frei":
                sets.set_lage(set_id, assigned_user_id=s["assigned_user_id"])
            journal.eintragen("item", neu, "zugeordnet", None,
                              {"konto": journal.konto_ref(s["assigned_user_id"]), "grund": "Zuordnung des Sets"})
        eintrag = {"teil": n["inventory_no"], "serial_no": n["serial_no"], "bestandteil": z["bezeichnung"],
                   "austausch": z["austausch"]}
        if t:
            eintrag.update(ersetzt_teil=t["inventory_no"], verbleib=verbleib)
        if z["austausch"] == "nicht_belegt":
            eintrag["bestaetigt"] = BESTAETIGT
        journal.eintragen("item", set_id, "teil_eingesetzt", None, eintrag)
        sets.sperren(set_id, set_grund="tausch", anlass=sets.GETAUSCHT if tausch else sets.EINGESETZT, neu=[neu])
    return neu, hinweise


def teil_loeschen(t):
    """Ein Teil einzeln löschen (bestand.artikel_loeschen, in dessen Transaktion, nach dessen Prüfungen: keine Prüfung,
    keine Durchgangszeile, keine Meldung) – das Set ist danach unvollständig und gesperrt."""
    set_id = t["parent_item_id"]
    bez = _bezeichnung(set_id, t)
    db.execute("DELETE FROM mat_item WHERE id = ?", (t["id"],))
    journal.eintragen("item", t["id"], "geloescht", dict(t, ordner=bestand._pfad_text(t["folder_id"])),
                      {"set": set_id, "grund": "einzeln aus dem Set gelöscht"})
    journal.eintragen("item", set_id, "teil_geloescht", None, {"teil": t["inventory_no"], "bestandteil": bez})
    sets.sperren(set_id, set_grund="unvollstaendig", anlass=sets.UNVOLLSTAENDIG.format(bez=f"„{bez}“", was="gelöscht"))


def teil_aus_pruefung(t, p, grund, tag, pruefer, ts):
    """Ergebnis „aussondern“ an einem Teil (pruefung._wirkung_im_set): entnehmen und aussondern (Aussonderungsprotokoll
    mit der Prüfung als Grundlage), das Set unvollständig sperren. In der Transaktion des Festschreibens."""
    from . import pruefung
    set_id = t["parent_item_id"]
    bez = _bezeichnung(set_id, t)
    if not db.execute_zeilen("UPDATE mat_item SET parent_item_id = NULL, assigned_user_id = NULL, lock_cause = NULL, "
                             "set_pruefen = 0, updated_at = ? WHERE id = ? AND parent_item_id = ?",
                             (db.now(), t["id"], set_id)):
        raise Abgelehnt(SCHON_ENTNOMMEN, 409)
    s = bestand.artikel(set_id)
    journal.eintragen("item", t["id"], "entnommen", {"set": set_id, "set_inventar": s["inventory_no"]},
                      {"set": None, "verbleib": "aussondern", "pruefung": p["id"]})
    if t["assigned_user_id"]:
        journal.eintragen("item", t["id"], "zuordnung_geloest", None,
                          {"konto": journal.konto_ref(t["assigned_user_id"]), "grund": "aus dem Set entnommen"})
    pruefung._aussondern(bestand.artikel(t["id"]), grund, "", tag, pruefer, basis_id=p["id"], ts=ts)
    journal.eintragen("item", set_id, "teil_entnommen", None,
                      {"teil": t["inventory_no"], "bestandteil": bez, "verbleib": "aussondern", "pruefung": p["id"]})
    sets.sperren(set_id, set_grund="unvollstaendig", anlass=sets.UNVOLLSTAENDIG.format(bez=f"„{bez}“", was="ausgesondert"))


SET_AUSSONDERN_HINWEIS = " – laut Hersteller nicht austauschbar: das Set aussondern"


def nicht_austauschbar(t):
    """Steht das Teil an einer Position mit „Austausch laut Hersteller: nein“?"""
    z = _position(t["parent_item_id"], t)
    return bool(z) and z["austausch"] == "nein"


def teil_bleibt_gesperrt(t, p, grund):
    """Ergebnis „aussondern“ an einem nicht austauschbaren Teil (pruefung._wirkung_im_set): Es bleibt im Set, gesperrt mit
    eigenem Grund (grund nennt „das Set aussondern“) – auch eine schon vorhandene eigene Sperre bekommt diesen Grund, damit
    der Materialwart ihn sieht. In der Transaktion des Festschreibens; das Set sperrt mit (Kaskade)."""
    set_id = t["parent_item_id"]
    # Am Sperrzustand festgemacht, nicht an der Ursache allein: ein freies Teil mit Altwert „eigen“ ist nicht gesperrt
    # (Prüfung Sicherheit, H1) – dann sperrt die Kaskade wie bei jedem freien Teil.
    if sets._eigen_gesperrt(t):
        sets.set_lage(set_id, je_zeile={"lock_reason": ({t["id"]: grund}, sets.BLEIBT)})
        journal.eintragen("item", t["id"], "geprueft", {"lock_reason": t["lock_reason"]},
                          {"lock_reason": grund, "pruefung": p["id"], "ergebnis": "aussondern", "set": set_id})
        sets.gruende_nachziehen(set_id)
        return
    sets.sperren(set_id, eigen=t["id"], grund=grund, zusatz={"pruefung": p["id"]})


def set_aussondern(s, grund, bemerkung, tag, akteur, verbleib, basis_id=None, ts=None, ausser_lauf=None):
    """Set aussondern mit der Wahl je Teil (verbleib {Teil: „aussondern“ | „weiterfuehren“}, siehe Kopf) – in der
    Transaktion des Aufrufers und innerhalb von protokoll.dateien_sichern(). Eine offene Set-Prüfung endet „abgebrochen“
    (außer ausser_lauf – der Lauf, den diese Aussonderung gerade abschließt). Weitergeführte Teile verlassen das Set
    zuerst; dann EIN UPDATE über Set und verbleibende Teile nach „Ausgesondert“ (sets.set_lage) und je Artikel das
    Aussonderungsprotokoll (pruefung._aussondern ohne eigene Bewegung) – mit dem jetzigen Sperrgrund
    (sets.gruende_nachziehen, nie dem eines Teils, das nicht mehr dazugehört). Liefert die Kennung der Aussonderung des
    Sets."""
    from . import pruefung, setlauf
    set_id = s["id"]
    s, tz = sets.zeilen(set_id)
    for x in [s] + tz:
        offen = pruefung.offener_entwurf(x["id"])
        if offen:
            raise Abgelehnt(f"{x['inventory_no']}: " + pruefung.reserviert_text(offen) + " Erst abschließen oder die "
                            "Reservierung aufheben.", 409)
    lf = setlauf.offener(set_id)
    if lf and lf["id"] != ausser_lauf:
        setlauf.beenden(lf, grund="Set ausgesondert")
    sets.gruende_nachziehen(set_id)
    s, tz = sets.zeilen(set_id)
    ts = ts or db.now()
    heimat = bestand.heimat(s)
    gl = bestand.gliederung_von(s["folder_id"])
    gesperrt = bestand.systemordner(gl["id"], "gesperrt") if gl else None
    if not gesperrt:
        raise Abgelehnt("Der Systemordner „Gesperrt“ der Gliederung fehlt – bitte den Ordnerbaum prüfen.", 409)
    weiter = [t for t in tz if verbleib.get(t["id"]) == "weiterfuehren"]
    mit = [t for t in tz if verbleib.get(t["id"]) != "weiterfuehren"]
    for t in weiter:
        grund_t = t["lock_reason"] if t["lock_cause"] == "eigen" else AUS_AUSGESONDERTEM_SET
        zustand = "verloren" if t["lock_state"] == "verloren" else "gesperrt"
        if not db.execute_zeilen("UPDATE mat_item SET parent_item_id = NULL, assigned_user_id = NULL, lock_state = ?, "
                                 "lock_cause = 'eigen', lock_reason = ?, set_pruefen = 0, folder_id = ?, "
                                 "origin_folder_id = ?, updated_at = ? WHERE id = ? AND parent_item_id = ?",
                                 (zustand, grund_t, gesperrt["id"], heimat, ts, t["id"], set_id)):
            raise Abgelehnt(SCHON_ENTNOMMEN, 409)
        journal.eintragen("item", t["id"], "entnommen",
                          {"set": set_id, "set_inventar": s["inventory_no"], "lock_state": t["lock_state"],
                           "lock_cause": t["lock_cause"], "folder_id": t["folder_id"],
                           "ordner": bestand._pfad_text(t["folder_id"])},
                          dict({"set": None, "verbleib": "weiterfuehren", "set_grund": "ausgesondert",
                                "lock_state": zustand, "lock_cause": "eigen",
                                "lock_reason": grund_t, "folder_id": gesperrt["id"],
                                "ordner": bestand._pfad_text(gesperrt["id"]), "origin_folder_id": heimat,
                                "herkunft": bestand._pfad_text(heimat)}, **({"pruefung": basis_id} if basis_id else {})))
        if t["assigned_user_id"]:
            journal.eintragen("item", t["id"], "zuordnung_geloest", None,
                              {"konto": journal.konto_ref(t["assigned_user_id"]), "grund": "aus dem Set entnommen"})
        journal.eintragen("item", set_id, "teil_entnommen", None,
                          {"teil": t["inventory_no"], "verbleib": "weiterfuehren", "grund": "Set ausgesondert"})
    vorher = {x["id"]: x for x in [s] + mit}
    ziel = pruefung._systemziel(s, "ausgesondert")
    mit_grund = f"mit dem Set {s['inventory_no']} ausgesondert: {grund}"
    sets.set_lage(set_id, folder_id=ziel, origin_folder_id=heimat, lock_state="ausgesondert", assigned_user_id=None,
                  je_zeile={"lock_cause": ({}, None), "lock_reason": ({set_id: grund}, mit_grund),
                            "set_pruefen": ({}, 0), "set_lock_origin": ({}, None)})
    aid = pruefung._aussondern(vorher[set_id], grund, bemerkung, tag, akteur, basis_id=basis_id, ts=ts, bewegen=False)
    for t in mit:
        pruefung._aussondern(vorher[t["id"]], mit_grund, bemerkung, tag, akteur, basis_id=basis_id, ts=ts, bewegen=False)
    return aid


def set_aussondern_wart(s, grund, bemerkung, tag, akteur, roh_verbleib):
    """„Set aussondern“ durch den Materialwart (pruefung.aussondern am Set-Artikel, nach dessen Prüfungen am Set-Artikel):
    dazu ein eigener Grund im Set (Prüfer-Sperre, „instandsetzen“) oder verloren – eine Sperre nur aus Unvollständigkeit
    oder Tausch hat kein Sachkundiger gesehen –, keine ungeprüfte Meldung an Set oder Teil, die Datumsgrenzen der mit
    ausgesonderten Teile. Liefert die Kennung der Aussonderung des Sets."""
    from . import mangel, pruefung, setlauf
    s, tz = sets.zeilen(s["id"])
    if not any(x["lock_cause"] == "eigen" or x["lock_state"] == "verloren" for x in [s] + tz):
        raise Abgelehnt("Das Set ist nur gesperrt, weil es unvollständig ist, ein Teil getauscht, ein Bestandteil "
                        "ersetzt oder die Stückliste übertragen wurde – aussondern "
                        "kann es jetzt nur ein Prüfer („Set prüfen“ mit dem Ergebnis „aussondern“) oder nach einer Sperre "
                        "durch einen Prüfer.", 409)
    for x in [s] + tz:
        if mangel.ungeprueft(x["id"]):
            raise Abgelehnt(f"{x['inventory_no']}: " + mangel.NUR_GEMELDET, 409)
    vb = setlauf._verbleib(roh_verbleib, tz)
    for t in tz:
        if vb[t["id"]] == "aussondern":
            pruefung.aussondern_grenzen(t, tag, wer=f"{t['inventory_no']}: ")
    return set_aussondern(s, grund, bemerkung, tag, akteur, vb)


# --- Vorhandenen Artikel einsetzen (L2b, Entwurf A) --------------------------------------------------------------------

def _zustand_text(a):
    return {"gesperrt": "gesperrt", "verloren": "verloren gemeldet", "ausgesondert": "ausgesondert"}.get(
        a["lock_state"], a["lock_state"])


def vorhandenen_einsetzen(s, pid, bez, item_id, ziel, sperren=True):
    """Einen vorhandenen Artikel als Teil in das Set s einsetzen – in der Transaktion des Aufrufers (BEGIN IMMEDIATE), am
    frisch gelesenen Artikel, Reihenfolge und Wirkung siehe Kopf. pid/bez: Produkt und Bezeichnung der Position; ziel: die
    Heimat des Sets (beim Anlegen sein Ablageordner). sperren: False beim Anlegen – das Set ist neu und frei, sein erster
    Lauf prüft ohnehin alle Teile (setlauf.umfang). Den Eintrag „teil_eingesetzt“ am Set und set_stimmig schreibt der
    Aufrufer. Liefert die Zeile des Artikels nach dem Einsetzen."""
    from . import durchgang, faelligkeit, mangel, pruefung, rueckruf, setlauf
    a = db.query("SELECT * FROM mat_item WHERE id = ?", (item_id,), one=True)
    # 1. Sicht: nicht verwaltbar heißt wie unbekannt (auch ein lesbarer Artikel, auch das Teil eines fremden Sets).
    if not a or not rechte.darf_artikel("verwalten", a) or not rechte.darf("verwalten", ziel):
        raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)
    inv = a["inventory_no"]
    # 2. Produkt der Position.
    if a["product_id"] != pid:
        raise Abgelehnt(ANDERES_PRODUKT.format(inv=inv, ist=katalog.produktname(katalog.produkt(a["product_id"])),
                                               soll=katalog.produktname(katalog.produkt(pid)))
                        + (PRODUKT_WEG if bestand.produkt_aenderbar(a) else ""), 409)
    # 3. Dieselbe Gliederung (aus einer anderen erst verschieben – dort gelten dessen Regeln, T8) und die DEMO-Grenze.
    heim = bestand.heimat(a)
    gq, gz = bestand.gliederung_von(heim), bestand.gliederung_von(ziel)
    if (gq or {}).get("id") != (gz or {}).get("id"):
        raise Abgelehnt(ANDERE_GLIEDERUNG.format(inv=inv), 409)
    if bestand.ordner_ist_demo(heim) != bestand.ordner_ist_demo(ziel):
        raise Abgelehnt(bestand.DEMO_GRENZE, 409)
    # 4. Zustände.
    if a["parent_item_id"]:
        alt_set = sets.set_zeile(a["parent_item_id"], gefiltert=False)
        raise Abgelehnt(f"{inv} ist Teil des Sets {sets._set_text(alt_set) if alt_set else ''} – erst dort „Teil "
                        "entnehmen“, dann einsetzen.", 409)
    if sets.ist_set_artikel(a):
        raise Abgelehnt(f"{inv} ist selbst ein Set – ein Set wird kein Teil.", 409)
    if a["lock_state"] != "frei":
        raise Abgelehnt(f"{inv} ist {_zustand_text(a)} – einsetzen lassen sich nur freie Artikel.", 409)
    offen = pruefung.offener_entwurf(a["id"])
    if offen:
        raise Abgelehnt(f"{inv}: " + pruefung.reserviert_text(offen) + " Erst abschließen oder die Reservierung aufheben.",
                        409)
    if mangel.offene_ids(a["id"]):
        raise Abgelehnt(f"An {inv} ist ein gemeldeter Mangel offen – erst prüfen lassen, dann einsetzen.", 409)
    rr = [r for r in rueckruf.aktive_fuer_artikel(a) if r["zustand"] == "offen"]
    if rr:
        raise Abgelehnt(f"Für {inv} ist ein Rückruf offen („{rr[0]['title']}“) – erst den Rückruf klären (Artikel prüfen), "
                        "dann einsetzen.", 409)
    if st.status(a) == "lebensdauer":
        raise Abgelehnt(f"{inv} hat die Lebensdauer erreicht – aussondern statt einsetzen.", 409)
    _, tz = sets.zeilen(s["id"])
    soll = sum(z["anzahl"] for z in sets.slots(s["id"]) if z["einzeln"] and z["product_id"] == pid)
    if sum(1 for t in tz if t["product_id"] == pid) >= soll:
        raise Abgelehnt(f"An „{bez}“ fehlt kein Teil – ein vorhandenes ersetzt „Teil tauschen“.", 409)
    lf = setlauf.offener(s["id"])
    if lf and db.query("SELECT 1 FROM mat_inspection WHERE set_lauf_id = ? AND item_id = ? LIMIT 1", (lf["id"], a["id"]),
                       one=True):
        raise Abgelehnt(f"{inv} wurde in der offenen Set-Prüfung dieses Sets schon geprüft – erst die Set-Prüfung "
                        "abschließen oder abbrechen, dann einsetzen.", 409)
    # Wirkung: Lage und Zuordnung wie das Set – nur, wenn der Artikel noch so ist, wie er eben gelesen wurde (U9). Ein
    # freier Artikel hat keine Sperrursache: ein Altwert (etwa „eigen“ nach Entnehmen aus einem gesperrten Set und
    # Einzel-Freiprüfung vor dieser Nachbesserung) fiele sonst im Set als eigene Sperre aus (Prüfung Sicherheit, H1).
    if not db.execute_zeilen("UPDATE mat_item SET parent_item_id = ?, folder_id = ?, origin_folder_id = ?, "
                             "assigned_user_id = ?, lock_cause = NULL, lock_reason = '', set_pruefen = 0, updated_at = ? "
                             "WHERE id = ? AND parent_item_id IS NULL "
                             "AND lock_state = 'frei' AND folder_id = ? AND assigned_user_id IS ?",
                             (s["id"], s["folder_id"], s["origin_folder_id"], s["assigned_user_id"], db.now(), a["id"],
                              a["folder_id"], a["assigned_user_id"])):
        raise Abgelehnt(INZWISCHEN_GEAENDERT.format(inv=inv), 409)
    if a["folder_id"] != ziel:
        journal.eintragen("item", a["id"], "verschoben", {"folder_id": a["folder_id"], "ordner": bestand._pfad_text(a["folder_id"])},
                          {"folder_id": ziel, "ordner": bestand._pfad_text(ziel), "set": s["id"]})
    if a["assigned_user_id"] != s["assigned_user_id"]:
        if a["assigned_user_id"]:
            journal.eintragen("item", a["id"], "zuordnung_geloest", None,
                              {"konto": journal.konto_ref(a["assigned_user_id"]), "grund": "in ein Set eingesetzt"})
        if s["assigned_user_id"]:
            journal.eintragen("item", a["id"], "zugeordnet", None,
                              {"konto": journal.konto_ref(s["assigned_user_id"]), "grund": "Zuordnung des Sets"})
    journal.eintragen("item", a["id"], "eingesetzt", None,
                      {"set": s["id"], "set_inventar": s["inventory_no"], "bestandteil": bez})
    if sperren:
        sets.sperren(s["id"], set_grund="tausch", anlass=sets.EINGESETZT, neu=[a["id"]])
        # Erst nach der Sperre: Durchgang und Fälligkeit rechnen mit der Heimat des Sets, nicht mit „Gesperrt“ (T3).
        durchgang.nach_verschieben([a["id"]], heute())
        faelligkeit.kappen("i.id = ?", (a["id"],))
    return bestand.artikel(a["id"])


def _muster(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _bisherige(notes):
    return [m.strip() for m in _BISHERIGE.findall(notes or "") if m.strip()]


def suchtext(roh):
    """Die Suche der Auswahl: mindestens SUCHE_MIN, höchstens SUCHE_MAX Zeichen (400 sonst)."""
    q = roh.strip() if isinstance(roh, str) else ""
    if len(q) < SUCHE_MIN:
        raise Abgelehnt(f"Bitte mindestens {SUCHE_MIN} Zeichen der Inventar- oder Seriennummer eingeben.")
    if len(q) > SUCHE_MAX:
        raise Abgelehnt(f"Die Suche ist zu lang (höchstens {SUCHE_MAX} Zeichen).")
    return q


def kandidaten(ziel, pid, q):
    """Die Auswahl „aus dem Bestand wählen“ (Entwurf A, T10, U8): freie Artikel ohne Set des Produkts pid, die das Konto
    verwaltet (rechte.artikel_filter), in der Gliederung von ziel (Heimat des Sets bzw. Ablageordner) und auf derselben
    Seite der DEMO-Grenze. Suche in Inventar- und Seriennummer und in der Zeile „Bisherige Inventarnummer: …“ der Bemerkung
    (Bestandsimport) – LIKE mit ESCAPE, höchstens KANDIDATEN_MAX Treffer. Antwort: {treffer: [{id, inventory_no,
    serial_no, bisherige_inventarnummer, produkt, ordner, status, status_text, zugeordnet}], weitere, hinweis}.
    Die LIKE-Vorauswahl trifft in der Bemerkung auch Text hinter der Zeile (etwa „Standort: …“); was nur so trifft, fällt
    in Python heraus – darum wird seitenweise weitergelesen, bis KANDIDATEN_MAX + 1 echte Treffer da sind oder nichts
    mehr kommt (Prüfung Ablauf A3: vorher schnitt LIMIT 200 vor dem Nachfiltern ab). Die DEMO-Grenze steht in der Abfrage.
    Ohne Treffer 200 mit leerer Liste (Browser B3 – kein Konsolenfehler im Normalfall), für fremd und unbekannt gleich;
    passt die Nummer genau auf einen verwalteten Artikel mit anderem Produkt, nennt „hinweis“ ihn ({text, artikel: {id,
    inventory_no}}, U8) – das Konto verwaltet ihn, es erfährt nichts Neues. Kein Suchprotokoll, kein Hinweis auf
    Fremdes."""
    gl = bestand.gliederung_von(ziel)
    treffer, weitere = [], False
    nadel = q.casefold()
    if gl:
        zweig, zweig_args = bestand.heimat_im_zweig(gl["id"], "i")
        muster = _muster(q)
        demo = 1 if bestand.ordner_ist_demo(ziel) else 0
        nach = ("", 0)                     # Schlüssel der Seite: (Inventarnummer, Kennung) der letzten gelesenen Zeile
        while not weitere:
            rows = db.query(
                "SELECT i.*, p.manufacturer, p.model, p.description AS product_description, p.article_no FROM mat_item i "
                "JOIN mat_product p ON p.id = i.product_id WHERE i.product_id = ? AND i.lock_state = 'frei' "
                f"AND i.parent_item_id IS NULL AND p.is_set = 0 AND {rechte.artikel_filter('i', 'verwalten')} AND {zweig} "
                f"AND {bestand.demo_ordner_sql('i.folder_id')} = ? "
                "AND (i.inventory_no LIKE ? ESCAPE '\\' OR i.serial_no LIKE ? ESCAPE '\\' OR i.notes LIKE ? ESCAPE '\\') "
                "AND (i.inventory_no > ? OR (i.inventory_no = ? AND i.id > ?)) "
                f"ORDER BY i.inventory_no, i.id LIMIT {KANDIDATEN_SEITE}",
                (pid, *zweig_args, demo, muster, muster, "%" + BISHERIGE + muster, nach[0], nach[0], nach[1]))
            for i in rows:
                alt = [b for b in _bisherige(i["notes"]) if nadel in b.casefold()]
                if not (nadel in i["inventory_no"].casefold() or nadel in i["serial_no"].casefold() or alt):
                    continue
                if len(treffer) == KANDIDATEN_MAX:
                    weitere = True
                    break
                status = st.status(i)
                treffer.append({"id": i["id"], "inventory_no": i["inventory_no"], "serial_no": i["serial_no"],
                                "bisherige_inventarnummer": ", ".join(_bisherige(i["notes"])) or None,
                                "produkt": katalog.produktname(i, i["product_description"]),
                                "ordner": bestand._pfad_text(i["folder_id"]), "status": status,
                                "status_text": st.LABEL[status], "zugeordnet": bestand.zugeordnet_json(i)})
            if len(rows) < KANDIDATEN_SEITE:
                break
            nach = (rows[-1]["inventory_no"], rows[-1]["id"])
    if treffer:
        return {"treffer": treffer, "weitere": weitere, "hinweis": None}
    for i in db.query(f"SELECT i.* FROM mat_item i WHERE i.product_id <> ? AND i.lock_state <> 'ausgesondert' "
                      f"AND {rechte.artikel_filter('i', 'verwalten')} AND (i.inventory_no = ? COLLATE NOCASE "
                      "OR i.serial_no = ? COLLATE NOCASE OR i.notes LIKE ? ESCAPE '\\') ORDER BY i.id LIMIT 50",
                      (pid, q, q, "%" + BISHERIGE + _muster(q)[1:])):
        if (i["inventory_no"].casefold() == nadel or i["serial_no"].casefold() == nadel
                or nadel in (b.casefold() for b in _bisherige(i["notes"]))):
            weg = bestand.produkt_aenderbar(i)
            return {"treffer": [], "weitere": False, "hinweis": {
                "text": ANDERES_PRODUKT.format(inv=i["inventory_no"],
                                               ist=katalog.produktname(katalog.produkt(i["product_id"])),
                                               soll=katalog.produktname(katalog.produkt(pid))) + (PRODUKT_WEG if weg else ""),
                "artikel": {"id": i["id"], "inventory_no": i["inventory_no"], "produkt_aenderbar": weg}}}
    return {"treffer": [], "weitere": False, "hinweis": None}


def kandidaten_am_set(set_id, slot_roh, q_roh, produkt_roh=None):
    """GET /artikel/<Set>/kandidaten: slot_id eine einzeln geführte Position der Kopie dieses Sets (sonst 404);
    produkt_id (die Oberfläche): ihr Produkt – passt es nicht mehr, 409 (UEBERTRAGEN)."""
    slot_id = kennung(slot_roh, "Position")
    q = suchtext(q_roh)
    s = _set(set_id)
    z = next((x for x in sets.slots(set_id) if x["id"] == slot_id and x["einzeln"]), None)
    _position_passt(z, {"produkt_id": produkt_roh}, True)
    if not z:
        raise Abgelehnt("Position nicht gefunden.", 404)
    return kandidaten(bestand.heimat(s), z["product_id"], q)


def kandidaten_im_ordner(fid, produkt_roh, q_roh):
    """GET /ordner/<fid>/kandidaten für den Dialog „Artikel anlegen“ mit Set-Produkt: product_id das Produkt der Position
    (kein Set-Produkt), fid der Ablageordner des neuen Sets."""
    pid = kennung(produkt_roh, "Produkt")
    q = suchtext(q_roh)
    p = katalog.produkt(pid)
    if p["is_set"]:
        raise Abgelehnt("Ein Set ist kein Teil eines Sets.")
    bestand.ablageordner_pruefen(fid)
    return kandidaten(fid, pid, q)


# --- Set auflösen (L2b, Entwurf A) -------------------------------------------------------------------------------------

def _seit_im_set_geprueft(t, set_id):
    """Hat das Teil eine abgeschlossene Prüfung, seit es in diesem Set ist? Deren Protokoll trägt „Teil von Set …“ (Kopie
    beim Festschreiben). Maß ist das Journal: der Eintrag, mit dem es ins Set kam (sets.beitritt), gegen den Eintrag
    „abgeschlossen“ der Prüfung – Zeitstempel sind nur sekundengenau. Ohne Beitritt zählt jede Prüfung."""
    j, _ = sets.beitritt(t["id"], set_id)
    return bool(db.query("SELECT 1 FROM mat_inspection x JOIN mat_audit a ON a.entity = 'inspection' "
                         "AND a.entity_id = x.id AND a.action = 'abgeschlossen' WHERE x.item_id = ? "
                         "AND x.completed_at IS NOT NULL AND a.id > ? LIMIT 1", (t["id"], j or 0), one=True))


def aufloesen_hindernis(set_id):
    """Was gegen „Set auflösen“ spricht – ein Satz mit Grund und Weg, oder None (siehe Kopf). Frisch gelesen, in der
    Transaktion des Aufrufers (aufloesen) bzw. für den Set-Block (sets.set_json: „aufloesen_hindernis“). Ein offener Lauf
    ohne Prüfung spricht nicht dagegen – aufloesen beendet ihn."""
    from . import pruefung, setlauf
    s, tz = sets.zeilen(set_id)
    if s["lock_state"] != "frei" or any(t["lock_state"] != "frei" for t in tz):
        return NUR_FREIES_SET
    weg = " – es bleibt mit seinem Lebenslauf; einzelne Teile verlassen es über „Teil entnehmen“."
    if db.query("SELECT 1 FROM mat_inspection WHERE item_id = ? LIMIT 1", (set_id,), one=True):
        return "Das Set hat eine Prüfung (auch eine begonnene)" + weg
    if db.query("SELECT 1 FROM mat_defect_report WHERE item_id = ? LIMIT 1", (set_id,), one=True):
        return "Am Set ist ein Mangel gemeldet (auch ein erledigter zählt)" + weg
    if db.query("SELECT 1 FROM mat_round_item WHERE item_id = ? LIMIT 1", (set_id,), one=True):
        return "Das Set steht in einem Prüfdurchgang" + weg
    if db.query("SELECT 1 FROM mat_item_change WHERE item_id = ? LIMIT 1", (set_id,), one=True):
        return "Zum Set gibt es einen Änderungsantrag" + weg
    lf = setlauf.offener(set_id)
    if db.query("SELECT 1 FROM mat_set_lauf WHERE set_item_id = ? AND state <> 'offen' LIMIT 1", (set_id,), one=True) \
            or (lf and db.query("SELECT 1 FROM mat_inspection WHERE set_lauf_id = ? LIMIT 1", (lf["id"],), one=True)):
        return "Zum Set gibt es eine Set-Prüfung mit Prüfungen" + weg
    for t in tz:
        offen = pruefung.offener_entwurf(t["id"])
        if offen:
            return f"{t['inventory_no']}: " + pruefung.reserviert_text(offen) + " Erst abschließen oder die Reservierung " \
                "aufheben."
        if _seit_im_set_geprueft(t, set_id):
            return (f"{t['inventory_no']} wurde als Teil dieses Sets geprüft – sein Protokoll nennt das Set. Auflösen geht "
                    "nicht; das Teil verlässt das Set über „Teil entnehmen“.")
    return None


def aufloesen(set_id):
    """„Set auflösen“ (POST /artikel/<Set>/aufloesen) – siehe Kopf. Liefert die Teile [{id, inventory_no}]."""
    from . import setlauf
    with db.transaction(sofort=True):
        _set(set_id)
        hindernis = aufloesen_hindernis(set_id)
        if hindernis:
            raise Abgelehnt(hindernis, 409)
        s, tz = sets.zeilen(set_id)
        lf = setlauf.offener(set_id)
        if lf:
            setlauf.beenden(lf, grund=AUFGELOEST)
        if db.execute_zeilen("UPDATE mat_item SET parent_item_id = NULL, set_pruefen = 0, updated_at = ? "
                             "WHERE parent_item_id = ? AND lock_state = 'frei'", (db.now(), set_id)) != len(tz):
            raise Abgelehnt(SCHON_ENTNOMMEN, 409)
        for t in tz:
            journal.eintragen("item", t["id"], "aus_set_geloest", {"set": set_id, "set_inventar": s["inventory_no"]},
                              {"set": None, "grund": AUFGELOEST})
        db.execute("DELETE FROM mat_item WHERE id = ?", (set_id,))
        # Zuletzt am Set: „geloescht“ schneidet den Verlauf ab (die Kennung wird wiedervergeben, S15).
        journal.eintragen("item", set_id, "geloescht", dict(s, ordner=bestand._pfad_text(s["folder_id"])),
                          {"grund": AUFGELOEST, "teile": [t["inventory_no"] for t in tz]})
    return [{"id": t["id"], "inventory_no": t["inventory_no"]} for t in tz]


# --- „Bestandteil ersetzt“ (L2b, Entwurf B) ------------------------------------------------------------------------------

def bestandteil_ersetzt(set_id, d):
    """„Bestandteil ersetzt“ (POST /artikel/<Set>/bestandteil-ersetzt): {"slot_id" (nicht einzeln geführte Position der
    Kopie dieses Sets, sonst 404), "datum" (höchstens heute, Vorgabe heute), "bemerkung" (einzeilig, höchstens
    BEMERKUNG_MAX Zeichen – keine Personennamen: das Journal ist unveränderlich), "bestaetigt" (Pflicht bei „Austausch
    laut Hersteller: nicht belegt“)}. Siehe Kopf. Liefert nichts."""
    slot_id = kennung(d.get("slot_id"), "Position")
    tag = datum(d.get("datum"), "Datum") or heute().isoformat()
    if tag > heute().isoformat():
        raise Abgelehnt("Das Datum liegt in der Zukunft.")
    bemerkung = text(d, "bemerkung", "Bemerkung", BEMERKUNG_MAX)
    bestaetigt = wahr(d, "bestaetigt", "Austausch laut Herstellerunterlagen zulässig")
    from . import pruefung
    with db.transaction(sofort=True):
        s = _set(set_id)
        z = next((x for x in sets.slots(set_id) if x["id"] == slot_id and not x["einzeln"]), None)
        _position_passt(z, d, False)
        if not z:
            raise Abgelehnt("Position nicht gefunden.", 404)
        # Untergrenze (Prüfung Sicherheit, Hinweis): Was vor der Erfassung des Sets ersetzt wurde, gehört nicht in seinen
        # Verlauf – das Journal ist unveränderlich, „01.01.1900“ bliebe sonst stehen.
        if tag < s["created_at"][:10]:
            raise Abgelehnt(VOR_ERFASSUNG.format(datum=pruefung._fmt(s["created_at"][:10])))
        if z["austausch"] == "nein":
            raise Abgelehnt(NICHT_AUSTAUSCHBAR.format(bez=z["bezeichnung"]), 409)
        if z["austausch"] == "nicht_belegt" and not bestaetigt:
            raise Abgelehnt(BESTAETIGEN.format(bez=z["bezeichnung"]))
        offen = pruefung.offener_entwurf(set_id)
        if offen:
            raise Abgelehnt(pruefung.reserviert_text(offen) + " Erst festschreiben oder verwerfen – die begonnene Prüfung "
                            "hat den ersetzten Bestandteil nicht gesehen.", 409)
        # Doppelklick, zweiter Reiter (Prüfung Sicherheit, Hinweis): Dieselbe Position mit demselben Datum und derselben
        # Bemerkung kurz hintereinander ist schon eingetragen – sonst stünden zwei unveränderliche Einträge im Journal.
        grenze = (datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=DOPPELT_SEKUNDEN)).isoformat()
        for r in db.query("SELECT after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                          "AND action = 'bestandteil_ersetzt' AND created_at >= ?", (set_id, grenze)):
            x = json.loads(r["after_json"] or "{}")
            if (x.get("position"), x.get("datum"), x.get("bemerkung")) == (z["position"], tag, bemerkung):
                raise Abgelehnt(SCHON_EINGETRAGEN.format(bez=z["bezeichnung"]), 409)
        # „position“: die Nummer der Position in der Stückliste (1, 2, …), nicht die Kennung der Kopie (Browser B1).
        eintrag = {"position": z["position"], "bestandteil": z["bezeichnung"], "datum": tag, "bemerkung": bemerkung,
                   "austausch": z["austausch"]}
        if z["austausch"] == "nicht_belegt":
            eintrag["bestaetigt"] = BESTAETIGT
        journal.eintragen("item", set_id, "bestandteil_ersetzt", None, eintrag)
        sets.sperren(set_id, set_grund="bestandteil", anlass=sets.BESTANDTEIL_ERSETZT)
        sets.bestandteil_markieren(set_id)
        sets.set_stimmig(set_id)
