"""Personenzuordnung (Phase 2 · Lieferung 1, Abschnitt 6): Ein Artikel – meist PSA, die eine Person dauerhaft nutzt –
lässt sich einem Konto zuordnen.

Regeln, wie sie hier umgesetzt sind:
  - Zuordnen an jedes aktive Konto mit Namen auf der Plattform (rechte.waehlbares_konto) – PSA-Nutzer haben meist
    keinen Modulzugang, und eine Leserfreigabe nur für die Zuordnung zeigte ihnen den ganzen Ordner. Nicht vorhanden,
    deaktiviert und ohne Namen antworten gleich (404 „Konto nicht gefunden.“).
  - Setzen, ändern und lösen darf, wer den Artikel verwaltet (verwalten an der Heimat). Ausgesonderten Artikeln ordnet
    niemand mehr jemanden zu (409); das Aussondern löst die Zuordnung selbst (pruefung._aussondern). Eine Zuordnung an
    ein später deaktiviertes Konto bleibt stehen, die Anzeige vermerkt es.
  - Sehen nur mit Grundrecht (bestand.artikel_json, artikel_kurz) – nicht in der Prüfsicht, nicht in Prüf-,
    Aussonderungs- und Sammelprotokoll, nicht im Lebenslauf, nicht im globalen Steckbrief.
  - Kein Namensschnappschuss: Den Stand hält der Artikel (assigned_user_id), die Geschichte das Journal am Artikel. Dort
    steht die Person nur als Kontoverweis (journal.konto_ref) – nie mit Namen oder Kennung. Wer zuordnet, steht wie
    immer mit Namen da."""
from ... import db
from . import Abgelehnt, kennung
from . import bestand, journal, rechte, sets

MAX_ARTIKEL = 500
AUSGESONDERT = "Ausgesonderte Artikel lassen sich niemandem mehr zuordnen."
NUR_VERWALTER = "Personen zuordnen darf nur, wer die Artikel verwaltet."
OHNE_NAMEN = "(ohne Namen)"


def _konto(d):
    """Die Person aus der Anfrage: user_id ordnet zu, null (oder leer) löst die Zuordnung. Ein Konto zählt nur, wenn es
    aktiv ist und einen Namen hat – sonst dieselbe 404 wie für eines, das es nicht gibt. Liefert die Kennung oder
    None."""
    if not isinstance(d, dict) or "user_id" not in d:
        raise Abgelehnt("Bitte die Person angeben („user_id“) – null löst die Zuordnung.")
    uid = kennung(d.get("user_id"), "Konto", leer_erlaubt=True)
    return None if uid is None else rechte.waehlbares_konto(uid)["id"]


def _recht(i):
    """Das Recht am frisch gelesenen Artikel – in der Transaktion, denn er kann inzwischen woanders liegen: nicht
    sichtbar → 404 wie für einen, den es nicht gibt, ohne Verwalten → 403."""
    if not rechte.darf_artikel("lesen", i):
        raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)
    if not rechte.darf_artikel("verwalten", i):
        raise Abgelehnt(NUR_VERWALTER, 403)


def _eintrag(i, alt, uid, zusatz=None):
    if uid is None:
        journal.eintragen("item", i["id"], "zuordnung_geloest", None, dict({"konto": journal.konto_ref(alt)}, **(zusatz or {})))
    else:
        journal.eintragen("item", i["id"], "zugeordnet", {"konto": journal.konto_ref(alt)} if alt else None,
                          dict({"konto": journal.konto_ref(uid)}, **(zusatz or {})))


def _schreiben(i, uid):
    """Innerhalb der Transaktion: die Zuordnung eines Artikels setzen (uid) oder lösen (None) – mit Eintrag im Journal
    am Artikel, nur wenn sich etwas ändert. Lösen geht auch an einem ausgesonderten Artikel (Altbestand), zuordnen
    nicht. Ein Teil eines Sets nicht einzeln (409, Schritt 21); ein Set nimmt seine Teile mit (sets.set_lage, je Teil
    ein Eintrag mit {"set": Kennung}). Liefert, ob sich etwas geändert hat."""
    sets.teil_weiche(i, "eine Zuordnung")
    alt = i["assigned_user_id"]
    if alt == uid:
        return False
    if uid is not None and i["lock_state"] == "ausgesondert":
        raise Abgelehnt(AUSGESONDERT, 409)
    teile = db.query("SELECT * FROM mat_item WHERE parent_item_id = ? ORDER BY id", (i["id"],))
    if teile:
        sets.set_lage(i["id"], assigned_user_id=uid)
    else:
        db.execute("UPDATE mat_item SET assigned_user_id = ?, updated_at = ? WHERE id = ?", (uid, db.now(), i["id"]))
    _eintrag(i, alt, uid)
    for t in teile:
        if t["assigned_user_id"] != uid:
            _eintrag(t, t["assigned_user_id"], uid, {"set": i["id"]})
    return True


def setzen(iid, d):
    """PUT /artikel/<iid>/zuordnung: {"user_id": 17} ordnet zu, {"user_id": null} löst. Das Recht prüft die Route
    (requires_folder) und – am frisch gelesenen Artikel – noch einmal die Transaktion. Liefert die Artikelzeile."""
    uid = _konto(d)
    with db.transaction(sofort=True):
        i = bestand.artikel(iid)
        _recht(i)
        _schreiben(i, uid)
    return bestand.artikel(iid)


def sammeln(d):
    """POST /artikel/zuordnen: {"ids": [...] (1 bis MAX_ARTIKEL), "user_id": 17 | null} – ganz oder gar nicht. Je
    Artikel: Kennung wie im Dienst („7“ und 7.0 gelten), nicht sichtbar → 404 wie für einen, den es nicht gibt, ohne
    Verwalten → 403; erst danach zählt die Person. Ein Teil eines Sets → 409; ein Set zählt mit seinen Teilen gegen
    MAX_ARTIKEL (Schritt 21). Liefert die Zahl der geänderten Artikel (ein Set mit Teilen zählt wie seine Zeilen)."""
    ids = d.get("ids") if isinstance(d, dict) else None
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_ARTIKEL:
        raise Abgelehnt(f"Bitte 1 bis {MAX_ARTIKEL} Artikel auswählen.")
    ids = list(dict.fromkeys(kennung(x, "Artikel") for x in ids))
    with db.transaction(sofort=True):
        zeilen = {i["id"]: i for i in db.query(f"SELECT * FROM mat_item WHERE id IN ({','.join('?' * len(ids))})", ids)}
        # Erst alle sehen, dann alle verwalten: Ein fremder Artikel antwortet 404, wo er auch in der Liste steht.
        for iid in ids:
            if iid not in zeilen or not rechte.darf_artikel("lesen", zeilen[iid]):
                raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)
        for iid in ids:
            _recht(zeilen[iid])
        for iid in ids:
            sets.teil_weiche(zeilen[iid], "eine Zuordnung")
        mit_teilen = len(ids) + db.query(f"SELECT COUNT(*) AS n FROM mat_item WHERE parent_item_id IN "
                                         f"({','.join('?' * len(ids))})", ids, one=True)["n"]
        if mit_teilen > MAX_ARTIKEL:
            raise Abgelehnt(f"Bitte 1 bis {MAX_ARTIKEL} Artikel auswählen – mit den Teilen der Sets sind es {mit_teilen}.")
        uid = _konto(d)
        n = 0
        for iid in ids:
            vorher = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE (id = ? OR parent_item_id = ?) "
                              "AND assigned_user_id IS NOT ?", (iid, iid, uid), one=True)["n"]
            if _schreiben(zeilen[iid], uid):
                n += vorher
        return n


def zugeordnete(fid):
    """GET /ordner/<fid>/zugeordnete: die Personen, denen Artikel zugeordnet sind, die im Zweig des Ordners zu Hause
    sind (Heimat), je mit der Zahl – für den Filter „Zugeordnet an …“. Das Grundrecht am Ordner prüft die Route; der
    Filter in der Abfrage hält zusätzlich alles heraus, was das Konto nicht mit Grundrecht sieht. Ein Set zählt einmal
    (seine Teile nicht – die Listen zeigen nur die Set-Zeile, Schritt 21)."""
    rows = db.query(
        "WITH RECURSIVE zweig(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f JOIN zweig z ON f.parent_id = z.id) "
        "SELECT u.id, u.name, u.active, u.status, COUNT(*) AS anzahl FROM mat_item i "
        "JOIN users u ON u.id = i.assigned_user_id "
        f"WHERE {bestand.heimat_sql('i')} IN (SELECT id FROM zweig) AND i.parent_item_id IS NULL "
        f"AND {rechte.artikel_filter('i', 'grund')} "
        "GROUP BY u.id ORDER BY u.name COLLATE NOCASE, u.id", (fid,))
    return [{"id": r["id"], "name": (r["name"] or "").strip() or OHNE_NAMEN, "anzahl": r["anzahl"],
             "aktiv": bool(r["active"]) and r["status"] == "active"} for r in rows]
