"""Stückliste der Sets (Phase 4 · Lieferung 2, Entwurf A; seit dem 24.10.2026 „Set anlegen“): Ein Set (mat_product.is_set)
ist vom Hersteller als Einheit festgelegt – ab Werk zusammengestellt oder als Kombination zugelassen (etwa Sitz- und
Brustgurt); seine Artikelnummer ist die des Herstellers oder aus den Nummern der Teile abgeleitet. Es führt eine
Stückliste (mat_product_component). Der Set-Artikel ist das tragende PSA-Produkt und wird nach seinem Produkt- bzw.
Kategorieformular geprüft wie jedes Produkt (kein eigener Formulartyp). Nicht zu verwechseln mit der Ordnerart
„Set-Ordner“ (ein Ordner, in dem Material zusammen liegt).

Regeln, wie sie hier umgesetzt sind (die Trigger aus Schritt 21 fangen, was an ihnen vorbeiginge):
  - Ob ein Produkt ein Set ist, legt das Anlegen fest („Produkt anlegen“ / „Set anlegen“, katalog.produkt_anlegen mit
    der Stückliste in derselben Transaktion; Entscheidung S2). Umschalten nur noch über die Katalogdatei
    (set_umschalten, Katalogimport) und nur, solange es keine Artikel des Produkts gibt. Ein Produkt, das in einer
    Stückliste steht, wird kein Set; ein Set enthält kein Set. Ausschalten nimmt die Stückliste mit (Journal am Produkt).
  - Je Position: Bezeichnung (eine Zeile, höchstens 120 Zeichen), Anzahl 1–20, „einzeln geführt“ und „Austausch laut
    Hersteller“ (ja | nein | nicht belegt; Vorgabe nicht belegt). Einzeln geführt wird ein Bestandteil nur mit eigener
    individueller Kennzeichnung und eigenem Katalogprodukt – dann ist das Produkt Pflicht und jedes Stück wird beim
    Anlegen eines Sets ein eigener Artikel (ein Teil). Nicht einzeln geführte Bestandteile (Tasche, Seilsatz, Prusiks)
    sind nur Text, ohne Produkt – so trifft ein Rückruf keinen Bestandteil ins Leere.
  - Mindestens EINE einzeln geführte Position (Entscheidung S3) – beim Anlegen, als Variante, beim Ersetzen und im
    Katalogimport; ohne sie wäre es kein Set, sondern ein Produkt mit Zubehör.
  - Grenzen: höchstens 30 Positionen, zusammen höchstens 50 einzeln geführte Stück (Teile je Set).
  - Kein DEMO-Bestandteil in einem echten Set (der Katalog-Export nennt Altfälle im Bericht, „set_verstoesse“).
  - Die Stückliste wird als Ganzes ersetzt (Oberfläche wie Katalogimport) – mit einem Eintrag „stueckliste“ im Journal
    des Produkts (vorher, nachher). Angelegte Sets behalten ihre Kopie (mat_item_set_slot); „Stückliste übertragen“
    (setkopie.py) bringt die geänderte auf vorhandene Sets – nur die Material-Verwaltung (Entscheidung S7).
  - Ein Produkt, das Bestandteil ist (oder in der Kopie eines angelegten Sets steht), lässt sich nicht löschen: 409 mit
    dem Set statt eines Fremdschlüsselfehlers.

Pflegen darf die Material-Verwaltung (Routen an katalog_required); lesen jeder mit Modulzugang (produkt_json)."""
from ... import db
from ..models import AUSTAUSCH, BESTANDTEIL_ANZAHL_MAX, BEZEICHNUNG_MAX, SET_TEILE_MAX, STUECKLISTE_POSITIONEN_MAX
from . import Abgelehnt, auswahl, ganzzahl, kennung, text, wahr
from . import journal, katalog

SET_MIT_ARTIKELN = ("Ob ein Produkt ein Set ist, lässt sich nur ändern, solange es keine Artikel dieses Produkts gibt – "
                    "daran hängt, ob ein Artikel Teile hat.")
NUR_SET = "Eine Stückliste hat nur ein Set."
KEIN_SET_IM_SET = "Ein Set enthält kein Set – „{name}“ ist selbst eins."
# Entscheidung S3 (24.10.2026): ohne einzeln geführtes Teil kein Set.
EINZELN_PFLICHT = "Ein Set braucht mindestens ein einzeln geführtes Teil."
# Entscheidung S2: Produkt ↔ Set nur über die Katalogdatei.
UMSTELLEN = ("Ob ein Produkt ein Set ist, legt das Anlegen fest („Produkt anlegen“ / „Set anlegen“). Umstellen geht nur "
             "über die Katalogdatei, solange es keine Artikel gibt.")
NUR_MIT_SET = "„bestandteile“ gibt es nur mit „is_set“: true (Set anlegen)."
SET_OHNE_LISTE = "Ein Set legst du mit seiner Stückliste an („bestandteile“: eine Liste mit mindestens einer Position)."
DEMO_IM_SET = ("„{name}“ ist ein DEMO-Produkt – in der Stückliste eines echten Sets stünde sonst nach dem Katalog-Export ein "
               "Verweis ins Leere.")
NUR_TEXT = ("Ein nicht einzeln geführter Bestandteil ist nur Text (Bezeichnung) – ein Produkt gehört nur zu einem "
            "einzeln geführten.")
PRODUKT_PFLICHT = ("Ein einzeln geführter Bestandteil braucht ein Katalogprodukt – einzeln geführt wird nur, was eine eigene "
                   "Kennzeichnung (Serien- oder Einzelnummer) und ein eigenes Produkt hat.")
HILFE_EINZELN = ("Einzeln geführt nur bei eigener individueller Kennzeichnung (Serien- oder Einzelnummer) und eigenem "
                 "Katalogprodukt – jedes Stück wird beim Anlegen ein eigener Artikel mit Inventarnummer und Etikett. "
                 "Alles andere (Tasche, Seilsatz, Prusiks) ist ein Bestandteil ohne eigenen Artikel.")


def ist_set(pid):
    r = db.query("SELECT is_set FROM mat_product WHERE id = ?", (pid,), one=True)
    return bool(r and r["is_set"])


def zeilen(pid):
    """Die Positionen der Stückliste in ihrer Reihenfolge, mit Produktangaben des Bestandteils (oder None)."""
    return db.query(
        "SELECT c.*, p.manufacturer, p.model, p.description, p.article_no, p.material_kind, p.category_id, p.demo, "
        "p.lifetime_years, p.uid FROM mat_product_component c LEFT JOIN mat_product p ON p.id = c.component_product_id "
        "WHERE c.set_product_id = ? ORDER BY c.position, c.id", (pid,))


def _produkt_kurz(r):
    """Das Bestandteil-Produkt einer Zeile (zeilen, Kopie eines Sets) für Antworten – oder None (nur Text)."""
    if not r.get("component_product_id") and not r.get("product_id"):
        return None
    pid = r.get("component_product_id") or r.get("product_id")
    return {"id": pid, "name": katalog.produktname(r), "manufacturer": r["manufacturer"], "model": r["model"],
            "description": r["description"] or "", "article_no": r["article_no"] or "",
            "material_kind": r["material_kind"], "lifetime_years": r["lifetime_years"],
            "laenge_moeglich": katalog.laenge_wirksam(r["category_id"]), "demo": bool(r["demo"])}


def zeile_json(r):
    return {"id": r["id"], "position": r["position"], "bezeichnung": r["bezeichnung"], "anzahl": r["anzahl"],
            "einzeln": bool(r["einzeln"]), "austausch": r["austausch"], "austausch_text": AUSTAUSCH[r["austausch"]],
            "produkt": _produkt_kurz(r)}


def stueckliste_json(pid):
    return [zeile_json(r) for r in zeilen(pid)]


def bestandteil_von(pid):
    """Die Sets, in deren Stückliste dieses Produkt steht: [{id, name}] (eindeutig, nach Namen)."""
    rows = db.query("SELECT DISTINCT p.* FROM mat_product_component c JOIN mat_product p ON p.id = c.set_product_id "
                    "WHERE c.component_product_id = ? ORDER BY p.manufacturer COLLATE NOCASE, p.model COLLATE NOCASE",
                    (pid,))
    return [{"id": r["id"], "name": katalog.produktname(r)} for r in rows]


def in_angelegten_sets(pid):
    """Steht das Produkt in der Kopie der Stückliste eines angelegten Sets (mat_item_set_slot)?"""
    return bool(db.query("SELECT 1 FROM mat_item_set_slot WHERE product_id = ? LIMIT 1", (pid,), one=True))


def produkt_json_ergaenzen(out, p, voll=False):
    """Set-Angaben an katalog.produkt_json: is_set immer; voll dazu die Stückliste und wo das Produkt Bestandteil ist –
    an einem Set für die Material-Verwaltung auch sets_aelter (angelegte Sets mit einer älteren Stückliste,
    setkopie.aelter; Materialwarte und Führungskräfte sehen die Zahl nicht – sie ändern die Zusammensetzung nie, S7)."""
    from . import rechte, setkopie
    out["is_set"] = bool(p.get("is_set"))
    if not voll:
        return out
    out["bestandteile"] = stueckliste_json(p["id"]) if out["is_set"] else []
    out["bestandteil_von"] = bestandteil_von(p["id"])
    if out["is_set"] and rechte.ist_material_verwaltung():
        out["sets_aelter"] = setkopie.aelter(p["id"])
    out["stueckliste_grenzen"] = {"positionen": STUECKLISTE_POSITIONEN_MAX, "anzahl": BESTANDTEIL_ANZAHL_MAX,
                                  "teile": SET_TEILE_MAX, "bezeichnung": BEZEICHNUNG_MAX}
    return out


def umschalt_grund(p, an=None):
    """Warum sich „Set“ an diesem Produkt nicht umschalten lässt (Katalogimport) – oder None. an: Zielzustand (None: der
    jeweils andere)."""
    an = (not p.get("is_set")) if an is None else an
    if bool(p.get("is_set")) == bool(an):
        return None
    if db.query("SELECT 1 FROM mat_item WHERE product_id = ? LIMIT 1", (p["id"],), one=True):
        return SET_MIT_ARTIKELN
    if an:
        sets = bestandteil_von(p["id"])
        if sets:
            return (f"Das Produkt steht in der Stückliste von {', '.join('„' + s['name'] + '“' for s in sets[:3])}"
                    f"{' …' if len(sets) > 3 else ''} – ein Bestandteil ist selbst kein Set.")
    return None


def set_umschalten(pid, an, grund_journal=None):
    """„Set“ setzen (an) oder wegnehmen – nur noch für den Katalogimport (Entscheidung S2; die Oberfläche legt es beim
    Anlegen fest), in der Transaktion des Aufrufers. Wegnehmen entfernt eine vorhandene Stückliste (Journal
    „stueckliste“ vorher → leer). Liefert, ob sich etwas geändert hat."""
    p = katalog.produkt(pid)
    an = bool(an)
    if bool(p["is_set"]) == an:
        return False
    grund = umschalt_grund(p, an)
    if grund:
        raise Abgelehnt(grund, 409)
    if not an:
        _ersetzen(p, [], grund_journal)
    db.execute("UPDATE mat_product SET is_set = ?, updated_at = ? WHERE id = ?", (int(an), db.now(), pid))
    from .sets import set_produkte_vergessen
    set_produkte_vergessen()
    nachher = {"is_set": an}
    if grund_journal:
        nachher["grund"] = grund_journal
    journal.eintragen("product", pid, "geaendert", {"is_set": not an}, nachher)
    return True


def eintraege_lesen(set_produkt, liste, aufloesen=None):
    """Die Positionen aus einer Anfrage (oder einer Katalogdatei) nach den Regeln oben – noch ohne zu schreiben. Jede
    Position: {"produkt_id" | über aufloesen(eintrag) bestimmt, "bezeichnung", "anzahl", "einzeln", "austausch"}.
    aufloesen: für den Katalogimport (Verweis {uid, hersteller, modell, artikelnummer} → Produktzeile). Liefert die
    Liste in der Form der Tabelle (ohne Kennung), Reihenfolge = Position."""
    if not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    if len(liste) > STUECKLISTE_POSITIONEN_MAX:
        raise Abgelehnt(f"Höchstens {STUECKLISTE_POSITIONEN_MAX} Positionen je Stückliste.")
    out, stueck = [], 0
    for n, e in enumerate(liste, start=1):
        if not isinstance(e, dict):
            raise Abgelehnt(f"Position {n}: kein Objekt.")
        try:
            einzeln = wahr(e, "einzeln", "einzeln geführt")
            produkt = aufloesen(e) if aufloesen else None
            if not aufloesen:
                pid = kennung(e.get("produkt_id"), "Produkt", leer_erlaubt=True)
                produkt = katalog.produkt(pid) if pid is not None else None
            if einzeln and not produkt:
                raise Abgelehnt(PRODUKT_PFLICHT)
            if not einzeln and produkt:
                raise Abgelehnt(NUR_TEXT)
            bezeichnung = text(e, "bezeichnung", "Bezeichnung", BEZEICHNUNG_MAX, pflicht=not einzeln)
            if produkt:
                if produkt["id"] == set_produkt["id"] or produkt["is_set"]:
                    raise Abgelehnt(KEIN_SET_IM_SET.format(name=katalog.produktname(produkt)))
                if produkt["demo"] and not set_produkt["demo"]:
                    raise Abgelehnt(DEMO_IM_SET.format(name=katalog.produktname(produkt)))
                if not bezeichnung:
                    bezeichnung = katalog.produktname(produkt)[:BEZEICHNUNG_MAX].strip()
            anzahl = ganzzahl(e.get("anzahl", 1), "Anzahl", 1, BESTANDTEIL_ANZAHL_MAX, leer_erlaubt=False)
            austausch = auswahl(e.get("austausch") or "nicht_belegt", AUSTAUSCH, "Austausch laut Hersteller")
        except Abgelehnt as exc:
            raise Abgelehnt(f"Position {n}: {exc}", exc.code)
        if einzeln:
            stueck += anzahl
        out.append({"component_product_id": produkt["id"] if produkt else None, "bezeichnung": bezeichnung,
                    "anzahl": anzahl, "einzeln": int(einzeln), "austausch": austausch, "position": n})
    if stueck > SET_TEILE_MAX:
        raise Abgelehnt(f"Zusammen höchstens {SET_TEILE_MAX} einzeln geführte Stück je Set (hier {stueck}).")
    if not stueck:
        raise Abgelehnt(EINZELN_PFLICHT)
    return out


def anfrage_lesen(d):
    """POST /produkte und „Set aus Meldung anlegen“: Ein Set kommt mit seiner Stückliste – {"is_set": true,
    "bestandteile": [...]} (nicht leer); ohne is_set ist es ein Produkt, „bestandteile“ dann 400. Liefert die rohe Liste
    oder None (kein Set) – geprüft wird sie in katalog.produkt_anlegen (eintraege_lesen)."""
    ist = wahr(d, "is_set", "Set")
    liste = d.get("bestandteile")
    if not ist:
        if liste is not None:
            raise Abgelehnt(NUR_MIT_SET)
        return None
    if not isinstance(liste, list) or not liste:
        raise Abgelehnt(SET_OHNE_LISTE)
    return liste


def _vergleich(r):
    return (r["component_product_id"], r["bezeichnung"], r["anzahl"], int(r["einzeln"]), r["austausch"])


def _journal_form(r):
    return {"bezeichnung": r["bezeichnung"], "anzahl": r["anzahl"], "einzeln": bool(r["einzeln"]),
            "austausch": r["austausch"], "produkt": r["component_product_id"]}


def _ersetzen(p, neu, grund=None):
    """In der Transaktion des Aufrufers: die Stückliste von p durch neu (eintraege_lesen) ersetzen – nur, wenn sie sich
    ändert; Journal „stueckliste“ am Produkt. Liefert, ob."""
    alt = db.query("SELECT * FROM mat_product_component WHERE set_product_id = ? ORDER BY position, id", (p["id"],))
    if [_vergleich(r) for r in alt] == [_vergleich(r) for r in neu]:
        return False
    db.execute("DELETE FROM mat_product_component WHERE set_product_id = ?", (p["id"],))
    for r in neu:
        db.execute("INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, einzeln, "
                   "austausch, position) VALUES (?,?,?,?,?,?,?)",
                   (p["id"], r["component_product_id"], r["bezeichnung"], r["anzahl"], r["einzeln"], r["austausch"],
                    r["position"]))
    nachher = {"bestandteile": [_journal_form(r) for r in neu]}
    if grund:
        nachher["grund"] = grund
    journal.eintragen("product", p["id"], "stueckliste", {"bestandteile": [_journal_form(r) for r in alt]}, nachher)
    db.execute("UPDATE mat_product SET updated_at = ? WHERE id = ?", (db.now(), p["id"]))
    return True


def ersetzen(pid, liste, aufloesen=None, grund=None):
    """PUT /produkte/<pid>/bestandteile bzw. Katalogimport: die Stückliste als Ganzes ersetzen (unter der Schreibsperre;
    in einer äußeren Transaktion läuft es flach mit) – nie leer, mindestens ein einzeln geführtes Teil (S3). Angelegte
    Sets behalten ihre Kopie (setkopie.aelter zählt sie). Liefert, ob sie sich geändert hat."""
    with db.transaction(sofort=True):
        p = katalog.produkt(pid)
        if not p["is_set"]:
            raise Abgelehnt(NUR_SET, 409)
        return _ersetzen(p, eintraege_lesen(p, liste, aufloesen), grund)


def loeschen_pruefen(pid):
    """Vor dem Löschen eines Produkts: Ist es Bestandteil einer Stückliste oder steht es in der Kopie eines angelegten
    Sets, bleibt es (409 mit Klartext statt Fremdschlüsselfehler)."""
    sets = bestandteil_von(pid)
    if sets:
        namen = ", ".join("„" + s["name"] + "“" for s in sets[:3]) + (" …" if len(sets) > 3 else "")
        raise Abgelehnt(f"Das Produkt ist Bestandteil von {namen} – erst aus der Stückliste nehmen.", 409)
    if in_angelegten_sets(pid):
        raise Abgelehnt("Das Produkt steht in der Stückliste angelegter Sets – es bleibt im Katalog.", 409)

