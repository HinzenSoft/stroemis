"""Meine PSA (Phase 3 · Lieferung 1, Bauentwurf Abschnitt 2): Jedes aktive Konto mit Namen sieht die Artikel, die ihm
zugeordnet sind – auch ohne Stufe im Modul Material.

Ein eigener, enger Zugangsweg neben rechte.zugang: Er öffnet nur die eigenen, nicht ausgesonderten Artikel und von ihnen
nur die Karte (artikel_json – eine feste Liste von Schlüsseln): Status, Fälligkeit, Lebensende, Länge (Schritt 20),
Tag der letzten Prüfung, Produkt (Bild nur als Web- und Vorschaufassung), Nummern, Sperre mit Sperrgrund, Bemerkung, Name der
Gliederung, offener Mangel, Bestandteil-Liste mit den Seriennummern der Bestandteile (Schritt 25), Herstellerdokumente
(Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung, Datenblatt)
und die Titel laufender Rückrufe (Sperrgrund, Bemerkung, letzte Prüfung und Gliederung: Entscheidung A vom 20.10.2026).
Kein Ordnerpfad, keine Protokolle, keine Prüfhistorie, kein Journal. requires_folder und
die 404-Regel bleiben unberührt; die Zuordnung ist keine Freigabe (rechte.sicht kennt sie nicht).

Wer zuordnen darf und an wen, regelt zuordnung.py (rechte.waehlbares_konto: dieselben Bedingungen wie konto())."""
import json

from flask import g, has_request_context

from ... import db
from ...auth import current_user
from . import Abgelehnt, heute, laenge_text
from . import bestand, katalog, rechte, teilnummern
from . import status as st

MAX_ARTIKEL = 200            # Karten auf der Seite; mehr kommen nur nach einer Sammelzuordnung vor
EIGENE_MAX = 10              # eigene Meldungen je Karte
PSA_DOKUMENTARTEN = ("gebrauchsanleitung", "pflegehinweis", "konformitaetserklaerung", "datenblatt")
PSA_NAME_FEHLT = "Für „Meine PSA“ braucht dein Konto einen Namen – trag ihn im Profil ein."
# Was als „nicht einsatzbereit“ zählt (Übersicht, Profil) – und die Reihenfolge der Karten.
DRINGEND = ("gesperrt", "ueberfaellig", "lebensdauer", "neu")
_REIHE = ("CASE {s} WHEN 'gesperrt' THEN 0 WHEN 'ueberfaellig' THEN 1 WHEN 'lebensdauer' THEN 2 WHEN 'neu' THEN 3 "
          "WHEN 'bald_faellig' THEN 4 ELSE 5 END")
# Seit wann der Artikel zuletzt (ohne Berichtigung) geprüft wurde – für den Zustand eines Rückrufs (rueckruf.zustand).
_GEPRUEFT_UM = ("(SELECT MAX(x.completed_at) FROM mat_inspection x WHERE x.item_id = i.id AND x.completed_at IS NOT NULL "
                "AND x.corrects_inspection_id IS NULL)")


def konto(user=None):
    """PSA-Konto: angemeldet, aktiv, freigeschaltet und mit Namen – ohne Blick auf die Modulstufe (Entscheidung 1).
    Wer zuordnen darf, regelt rechte.waehlbares_konto mit denselben Bedingungen."""
    user = user or (current_user() if has_request_context() else None)
    return bool(user and user["active"] and (user.get("status") or "active") == "active"
                and (user["name"] or "").strip())


def anzahl(uid):
    """Zugeordnete, nicht ausgesonderte Artikel (eine Abfrage über idx_mat_item_assigned)."""
    return db.query("SELECT COUNT(*) AS n FROM mat_item WHERE assigned_user_id = ? AND lock_state <> 'ausgesondert'",
                    (uid,), one=True)["n"]


def kopfleiste(user=None):
    """Die Zahl für den Eintrag „Meine PSA“ der Kopfleiste – sonst 0 (F1, präzisiert): PSA-Konto mit Zuordnung, das
    nirgends im Bestand lesen darf – ohne Modulstufe ebenso wie Mitglied ohne Freigabe. Materialwarte, Prüfer und Leser
    finden ihre PSA als Kasten auf der Übersicht. Einmal je Anfrage (g.mat_psa_kopf); ohne Zuordnung keine Sicht."""
    user = user or (current_user() if has_request_context() else None)
    if not user or not konto(user):
        return 0
    speicher = g.setdefault("mat_psa_kopf", {})
    if user["id"] not in speicher:
        n = anzahl(user["id"])
        if n and rechte.zugang(user) and rechte.sicht(user).irgendwo("lesen"):
            n = 0
        speicher[user["id"]] = n
    return speicher[user["id"]]


def kurz(user):
    """{"anzahl", "dringend"} für Übersicht und Profil – None ohne Zuordnung (oder ohne PSA-Konto). Dringend: gesperrt,
    überfällig, Lebensdauer erreicht, neu."""
    if not konto(user):
        return None
    r = db.query(f"SELECT COUNT(*) AS n, COALESCE(SUM({st.status_sql('i')} IN ({','.join(repr(s) for s in DRINGEND)})), 0) "
                 "AS d FROM mat_item i WHERE i.assigned_user_id = :uid AND i.lock_state <> 'ausgesondert'",
                 dict(st.parameter(), uid=user["id"]), one=True)
    return {"anzahl": r["n"], "dringend": r["d"]} if r["n"] else None


def eigener(iid, user):
    """Der Artikel, wenn er user zugeordnet und nicht ausgesondert ist – sonst 404 wie für einen unbekannten."""
    i = db.query("SELECT * FROM mat_item WHERE id = ? AND assigned_user_id = ? AND lock_state <> 'ausgesondert'",
                 (iid, user["id"]), one=True)
    if not i:
        raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)
    return i


def _ids(rows):
    return json.dumps(sorted({r["id"] for r in rows}))


def liste(user):
    """(Karten, gesamt): die eigenen Artikel, dringende zuerst, höchstens MAX_ARTIKEL. Eine Abfrage für die Artikel, eine
    für offene Meldungen, eine für die eigenen Meldungen, eine für Rückrufe, je Produkt einmal die Dokumente – die Zahl
    der Abfragen hängt nicht an der Zahl der Artikel."""
    from . import mangel, rueckruf
    rows = db.query(
        "SELECT i.*, p.manufacturer, p.model, p.description AS product_description, p.article_no, p.material_kind, "
        f"p.image AS product_image, {bestand.demo_sql('i', 'p')} AS artikel_demo, {_GEPRUEFT_UM} AS geprueft_um "
        "FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
        "WHERE i.assigned_user_id = :uid AND i.lock_state <> 'ausgesondert' "
        f"ORDER BY {_REIHE.format(s=st.status_sql('i'))}, i.inventory_no LIMIT :lim",
        dict(st.parameter(), uid=user["id"], lim=MAX_ARTIKEL))
    gesamt = anzahl(user["id"])
    ids = _ids(rows)
    # Offen heißt auch: wieder offen nach einer Berichtigung der erledigenden Freiprüfung (mangel.stand) – eine
    # weitere Abfrage nur, wenn es dafür einen Kandidaten gibt.
    offen = {}
    zeilen = db.query(f"SELECT d.id, d.item_id, d.created_at, d.closed_at, d.closed_inspection_id, {mangel.KANDIDAT} "
                      "AS kandidat FROM mat_defect_report d WHERE d.item_id IN (SELECT value FROM json_each(?)) "
                      f"AND {mangel.OFFEN_SQL} ORDER BY d.created_at, d.id", (ids,))
    stand = mangel.stand(zeilen)
    for r in zeilen:
        if stand[r["id"]][0]:
            offen.setdefault(r["item_id"], r["created_at"])
    eigene = {}
    zeilen = db.query(f"SELECT d.*, {mangel.KANDIDAT} AS kandidat FROM mat_defect_report d WHERE d.reporter_id = ? "
                      "AND d.item_id IN (SELECT value FROM json_each(?)) ORDER BY d.created_at DESC, d.id DESC",
                      (user["id"], ids))
    stand = mangel.stand(zeilen)
    for r in zeilen:
        liste_ = eigene.setdefault(r["item_id"], [])
        if len(liste_) < EIGENE_MAX:
            liste_.append({"id": r["id"], "created_at": r["created_at"], "description": r["description"],
                           "offen": stand[r["id"]][0], "fotos": mangel.fotos_json(r)})
    produkte = sorted({r["product_id"] for r in rows})
    rueckrufe = {}
    if produkte:
        for rr in db.query("SELECT * FROM mat_recall WHERE closed_at IS NULL AND product_id IN "
                           "(SELECT value FROM json_each(?)) ORDER BY id", (json.dumps(produkte),)):
            rueckrufe.setdefault(rr["product_id"], []).append(rr)
    # Die Gliederung je Karte aus einem einmal geladenen Baum – keine Abfrage je Artikel.
    baum = {o["id"]: o for o in db.query("SELECT id, parent_id, name, kind, system_kind FROM mat_folder")} if rows else {}
    tag = heute().isoformat()
    dokumente = {pid: [{"title": d["title"], "kind": d["kind"], "datei": d["datei"], "url": d["url"] or ""}
                       for d in katalog.gueltige_dokumente(pid, tag) if d["kind"] in PSA_DOKUMENTARTEN]
                 for pid in produkte}
    # Bestandteil-Liste des Produkts mit den Seriennummern des Artikels (Schritt 25, F3 a) – was zurückzugeben ist.
    bestandteile = teilnummern.listen_json(rows)
    karten = []
    for r in rows:
        titel = []
        for rr in rueckrufe.get(r["product_id"], ()):
            if rueckruf._passt({rueckruf._norm(s) for s in rueckruf.serien(rr)}, r) \
                    and rueckruf.zustand(rr, r)[0] == "offen":
                titel.append(rr["title"])
        karten.append(artikel_json(r, user, offen.get(r["id"]), eigene.get(r["id"], []),
                                   dokumente.get(r["product_id"], []), titel, _gliederung(bestand.heimat(r), baum),
                                   bestandteile.get(r["id"], [])))
    return karten, gesamt


def _gliederung(fid, baum):
    """Name der nächsten Gliederung über fid (oder fid selbst) im geladenen Baum – None ohne Gliederung."""
    gesehen = set()
    while fid is not None and fid in baum and fid not in gesehen:
        gesehen.add(fid)
        o = baum[fid]
        if o["kind"] == "gliederung" and not o["system_kind"]:
            return o["name"]
        fid = o["parent_id"]
    return None


def artikel_json(r, user, offen, eigene, dokumente=(), rueckruf=(), gliederung=None, bestandteile=()):
    """Die Karte eines Artikels – genau diese Schlüssel (Bauentwurf 2.3, Schnittstelle 9.3). offen: Zeitpunkt der
    frühesten offenen Meldung (irgendeines Melders, ohne Text und Namen) oder None; eigene: die eigenen Meldungen."""
    s = st.status(r)
    return {
        "id": r["id"], "inventory_no": r["inventory_no"], "serial_no": r["serial_no"],
        "serial_generated": bool(r["serial_generated"]),
        "produkt": {"manufacturer": r["manufacturer"], "model": r["model"], "description": r["product_description"] or "",
                    "article_no": r["article_no"], "material_kind": r["material_kind"],
                    "bild": katalog.bild_url(r["product_image"], "web"),
                    "vorschau": katalog.bild_url(r["product_image"], "thumb")},
        "status": s, "status_text": st.LABEL[s], "next_due_on": r["next_due_on"], "retire_by": r["retire_by"],
        "last_inspected_on": r["last_inspected_on"],
        "length_m": r["length_m"], "laenge_text": laenge_text(r["length_m"]),
        "gesperrt": r["lock_state"] in ("gesperrt", "verloren"), "verloren": r["lock_state"] == "verloren",
        "lock_reason": (r["lock_reason"] or "") if r["lock_state"] != "frei" else "",
        "notes": r["notes"] or "", "gliederung": gliederung,
        "demo": bool(r["artikel_demo"]),
        "mangel": {"seit": offen} if offen else None,
        "eigene_maengel": list(eigene),
        # Mit Modulzugang und Leserecht verlinkt die Karte die volle Artikelseite (Sicht der Anfrage, keine Abfrage).
        "artikel_link": bool(rechte.zugang(user) and rechte.darf_artikel("lesen", r, user)),
        "dokumente": list(dokumente),
        "rueckruf": list(rueckruf),
        # Bestandteil-Liste des Produkts (Schritt 25): [{id, bezeichnung, anzahl, nummern}] – leer ohne Liste.
        "bestandteile": [dict(b) for b in bestandteile],
    }


def mails_setzen(user, an):
    """Erinnerungen zur eigenen PSA an (True) oder aus (False) – eine Einstellung des Kontos, kein Bestand: ohne
    Journal. Liefert den gespeicherten Wert."""
    db.execute("UPDATE users SET mat_psa_mails = ? WHERE id = ?", (1 if an else 0, user["id"]))
    return bool(an)
