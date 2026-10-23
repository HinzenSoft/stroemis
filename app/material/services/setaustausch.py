"""Teile entnehmen, tauschen, einsetzen und löschen, Set aussondern (Phase 4 · Lieferung 2, Entwurf G, C und D, Paket K2).

Regeln, wie sie hier umgesetzt sind:
  - Teil entnehmen (Materialwart, entnehmen): Verbleib „weiterfuehren“ – aus einem gesperrten Set mit eigener Sperre „aus
    gesperrtem Set entnommen“ (Herkunft bleibt die Heimat des Sets; eine eigene Sperre behält ihren Grund), aus einem
    freien Set frei im Ordner des Sets – oder „aussondern“, nur mit den Vorbedingungen von pruefung.aussondern (eigene
    Sperre durch einen Prüfer oder verloren, keine ungeprüfte Mangelmeldung, Datumsgrenzen; Kritik A15, S11). Bedingtes
    UPDATE … WHERE id = ? AND parent_item_id = ? mit Zeilenzahl-Prüfung (Doppelklick, Wettlauf); offener Entwurf am Teil
    → 409; seine Zeile im Durchgang bleibt. Das entnommene Teil verliert seine Zuordnung (Journal, S16); das Set ist
    danach unvollständig und gesperrt (Entwurf D, A25).
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
    entnehmen mit Verbleib „aussondern“, der Sachkundige hat es eben gesehen; das Set ist unvollständig und gesperrt.
  - Eine Teil-Kennung, die nicht zu diesem Set gehört (fremd oder unbekannt): 404 wie unbekannt. Journal an Set und Teil;
    der Lebenslauf des Sets zeigt nur Einträge am Set selbst („teil_entnommen“, „teil_eingesetzt“, „teil_geloescht“,
    „teil_gesperrt“) – nie Teil-Journale per Kennung (S15)."""
from ... import db
from ..models import AUSSONDERUNGSGRUENDE
from . import Abgelehnt, auswahl, datum, heute, kennung, text, wahr
from . import bestand, journal, katalog, protokoll, sets

AUS_GESPERRTEM_SET = "aus gesperrtem Set entnommen"
AUS_AUSGESONDERTEM_SET = "aus ausgesondertem Set entnommen"
NUR_SET = "Teile gibt es nur an einem Set-Artikel eines Hersteller-Sets."
NICHT_AUSTAUSCHBAR = ("„{bez}“ ist laut Hersteller nicht austauschbar – fällt ein solches Teil aus, wird das ganze Set "
                      "ausgesondert (die übrigen Teile lassen sich dabei entnehmen und weiterführen).")
BESTAETIGEN = ("Für „{bez}“ ist nicht belegt, ob der Hersteller den Austausch zulässt – bitte bestätigen, dass er laut "
               "Herstellerunterlagen zulässig ist.")
BESTAETIGT = "laut Herstellerunterlagen zulässig"
NUR_MIT_PRUEFERSPERRE = ("Aussondern lässt sich ein Teil nur mit eigener Sperre durch einen Prüfer oder wenn es verloren "
                         "ist – sonst „weiterführen“; danach sperrt ein Prüfer oder prüft mit „aussondern“.")
SCHON_ENTNOMMEN = "Das Teil wurde inzwischen anderswo entnommen – bitte neu laden."


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
        bez = _bezeichnung(set_id, t)
        _entnehmen(s, t, verbleib, aus, akteur)
        journal.eintragen("item", set_id, "teil_entnommen", None,
                          {"teil": t["inventory_no"], "bestandteil": bez, "verbleib": verbleib})
        sets.sperren(set_id, set_grund="unvollstaendig",
                     anlass=sets.UNVOLLSTAENDIG.format(bez=f"„{bez}“", was="ausgesondert" if aus else "entnommen"))
    return tid


def einsetzen(set_id, d, akteur, tausch):
    """„Teil tauschen“ (tausch: altes Teil „teil_id“ entnehmen mit „verbleib“ wie entnehmen) bzw. „Teil einsetzen“ in eine
    Position, an der eines fehlt („slot_id“ – bei genau einer fehlenden Position darf sie fehlen) – und ein neues Teil
    anlegen: Felder wie beim Set anlegen (sets.TEIL_FELDER), "bestaetigt" bei „Austausch laut Hersteller: nicht belegt“.
    Liefert (Kennung des neuen Teils, Hinweise)."""
    alt_id = kennung(d.get("teil_id"), "Teil") if tausch else None
    slot_id = None if tausch else kennung(d.get("slot_id"), "Position", leer_erlaubt=True)
    verbleib = auswahl(d.get("verbleib") or "weiterfuehren", sets.VERBLEIB, "Verbleib") if tausch else None
    aus = aussondern_angaben(d, akteur) if verbleib == "aussondern" else None
    bestaetigt = wahr(d, "bestaetigt", "Austausch laut Herstellerunterlagen zulässig")
    felder = {f: d[f] for f in sets.TEIL_FELDER if f in d}
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


def set_aussondern(s, grund, bemerkung, tag, akteur, verbleib, basis_id=None, ts=None):
    """Set aussondern mit der Wahl je Teil (verbleib {Teil: „aussondern“ | „weiterfuehren“}, siehe Kopf) – in der
    Transaktion des Aufrufers und innerhalb von protokoll.dateien_sichern(). Weitergeführte Teile verlassen das Set
    zuerst; dann EIN UPDATE über Set und verbleibende Teile nach „Ausgesondert“ (sets.set_lage) und je Artikel das
    Aussonderungsprotokoll (pruefung._aussondern ohne eigene Bewegung). Liefert die Kennung der Aussonderung des Sets."""
    from . import pruefung
    set_id = s["id"]
    s, tz = sets.zeilen(set_id)
    for x in [s] + tz:
        offen = pruefung.offener_entwurf(x["id"])
        if offen:
            raise Abgelehnt(f"{x['inventory_no']}: " + pruefung.reserviert_text(offen) + " Erst abschließen oder die "
                            "Reservierung aufheben.", 409)
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
                          dict({"set": None, "verbleib": "weiterfuehren", "lock_state": zustand, "lock_cause": "eigen",
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
        raise Abgelehnt("Das Set ist nur gesperrt, weil es unvollständig ist oder ein Teil getauscht wurde – aussondern "
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
