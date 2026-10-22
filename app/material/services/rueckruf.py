"""Rückrufe: Der Hersteller ruft ein Produkt zurück oder warnt davor.

Die Material-Verwaltung legt den Rückruf am Produkt an: Titel, was betroffen ist und was zu tun
ist, ein Link auf die Meldung des Herstellers und – wenn der Hersteller sie nennt – die betroffenen Seriennummern,
eine je Zeile; ohne Seriennummern gilt er für alle Artikel des Produkts. Sichtbar ist er für alle mit Zugang zum
Modul: am Produkt, als Banner an jedem betroffenen Artikel und als Kasten auf der Übersicht.

Seit Phase 2 gehört jeder betroffene Artikel zu einem Bereich (Freigaben je Ordner, über seine Heimat): Liste und
Zahlen zeigen jedem nur, was er sieht. Eine Mail geht je betroffenem Artikel an die Verwalter seiner Heimat und an die
Prüfer, die ihn geprüft haben und dort heute prüfen dürfen; hat er keinen Verwalter, an die Material-Verwaltung (gibt
es keine, an die Plattform-Verwaltung). Jeder Empfänger bekommt eine Mail mit genau den betroffenen Artikeln, die er
sehen darf. Wie viele Mails hinausgingen und welche Seriennummern zu keinem Artikel passen, erfährt nur, wer alle
Bestände sieht (die Material-Verwaltung) – sonst taugte ein Rückruf (auch einer ohne Mail, gleich wieder beendet) als
Abfrage fremder Bestände. Verschickt wird über mailprotokoll.senden (Phase 4 · L1): Ohne Mailserver, unter der
Umgebungssperre (dev) und an DEMO-Adressen geht nichts hinaus (zählt in mat_recall als gescheitert, wie bisher ohne
Mailserver); was der Mailserver nicht annimmt, steht im Mailfehler-Protokoll – je Gliederung der Artikel in der Mail
eine Zeile, mit der Rolle des Empfängers (Verwalter, Prüfer oder Verwaltung im Rückfall).

Gesperrt wird nichts automatisch – sperren dürfen ohne Prüfung nur Prüfer (pruefung.sperren), dafür gibt es den
Sperrgrund „Rückruf“. Je Artikel wird der Zustand abgeleitet, nie gespeichert:

  erledigt   der Artikel ist gesperrt, verloren oder ausgesondert – oder nach dem Anlegen des Rückrufs wurde
             eine Prüfung an ihm abgeschlossen (eine Berichtigung zählt nicht: sie ändert eine alte Prüfung)
  offen      sonst

Ausgesonderte Artikel sind außer Dienst und zählen nicht als betroffen. Beendet wird ein Rückruf mit einem
Vermerk; danach steht kein Hinweis mehr an den Artikeln, am Produkt bleibt er sichtbar. Das Journal führt beides
am Produkt (Aktionen „rueckruf“ und „rueckruf_beendet“) – so steht es auch im Lebenslauf jedes Artikels."""
import re

from flask import current_app, g

from ... import db
from ...auth import _im_hintergrund
from . import OHNE_NAMEN, Abgelehnt, akteur, text, wahr
from . import bestand, journal, katalog, mailprotokoll, rechte

TITEL_MAX = 200
BESCHREIBUNG_MAX = 4000
LINK_MAX = 500
SERIE_MAX = 80              # wie die Seriennummer am Artikel (bestand.artikel_werte)
MAX_SERIEN = 2000
VERMERK_MAX = 1000
MAIL_ARTIKEL_MAX = 100      # so viele betroffene Artikel stehen in der Mail; den Rest zeigt die Produktseite
UNBESTAETIGT_MINUTEN = 10   # so lange gilt ein Versand ohne Ergebnis als „läuft noch“ (Oberfläche)

# Mails gehen neben der Anfrage hinaus (wie bei Produktmeldungen); Tests setzen hier einen direkten Aufruf ein.
HINTERGRUND = _im_hintergrund

_LINK = re.compile(r"https?://[^\s/?#]+\S*", re.IGNORECASE)


# --- Eingaben -------------------------------------------------------------------------------------------

def _norm(serie):
    """Vergleichsform einer Seriennummer: Leerraum wie am Artikel (außen weg, innen – auch geschützte Leerzeichen
    aus kopierten Listen – ein Leerzeichen), ohne Rücksicht auf Groß/klein."""
    return " ".join((serie or "").split()).casefold()


def serien_lesen(wert):
    """Betroffene Seriennummern: ein Text mit einer je Zeile oder eine Liste. Leer heißt: alle Artikel des
    Produkts. Doppelte (gleich bis auf Groß/klein) fallen weg, die Schreibweise der ersten bleibt."""
    if wert is None or wert == "":
        return []
    if isinstance(wert, str):
        teile = wert.splitlines()
    elif isinstance(wert, list) and all(isinstance(x, str) for x in wert):
        teile = wert
    else:
        raise Abgelehnt("„Seriennummern“ müssen Text sein – eine je Zeile.")
    serien, gesehen = [], set()
    for t in teile:
        t = re.sub(r"[\x00-\x1f\x7f]+", " ", t).strip()
        if not t:
            continue
        if len(t) > SERIE_MAX:
            raise Abgelehnt(f"Die Seriennummer „{t[:40]}…“ ist zu lang (höchstens {SERIE_MAX} Zeichen).")
        if _norm(t) not in gesehen:
            gesehen.add(_norm(t))
            serien.append(t)
    if len(serien) > MAX_SERIEN:
        raise Abgelehnt(f"Höchstens {MAX_SERIEN} Seriennummern – bei mehr bitte „alle Artikel“ wählen und die "
                        "Seriennummern in der Beschreibung nennen.")
    return serien


def _link(d):
    """Die Meldung des Herstellers: nur http(s) – ein „javascript:“-Link am Produkt wäre eine Falle. „www.…“ ohne
    Schema bekommt https:// vorangestellt."""
    u = text(d, "url", "Link", LINK_MAX + 8)
    if not u:
        return ""
    if u.lower().startswith("www."):
        u = "https://" + u
    if len(u) > LINK_MAX:
        raise Abgelehnt(f"Der Link ist zu lang (höchstens {LINK_MAX} Zeichen).")
    if not _LINK.fullmatch(u):
        raise Abgelehnt("„Link“ muss eine Adresse sein, die mit http:// oder https:// beginnt.")
    return u


def werte(d):
    return {
        "title": text(d, "title", "Titel", TITEL_MAX, pflicht=True),
        "description": text(d, "description", "Beschreibung", BESCHREIBUNG_MAX, einzeilig=False),
        "url": _link(d),
        "serien": serien_lesen(d.get("serials")),
    }


# --- Lesen ----------------------------------------------------------------------------------------------

def rueckruf(ruid):
    r = db.query("SELECT * FROM mat_recall WHERE id = ?", (ruid,), one=True)
    if not r:
        raise Abgelehnt("Rückruf nicht gefunden.", 404)
    return r


def serien(r):
    return [s for s in (r["serials"] or "").split("\n") if s.strip()]


def _passt(serien_norm, artikel):
    return not serien_norm or _norm(artikel["serial_no"]) in serien_norm


def _artikel_im_bestand(pid, iid=None, sichtbar=True):
    """Artikel des Produkts im Bestand (nicht ausgesondert) mit dem Zeitpunkt ihrer letzten abgeschlossenen
    Prüfung. Berichtigungen zählen nicht – sie ändern eine alte Prüfung, sie sind keine neue. sichtbar: nur die, die das
    Konto der Anfrage sieht (über die Heimat, rechte.artikel_filter); False für die Mails, für die Auskunft an die
    Verwaltung und für einen einzelnen Artikel, dessen Recht der Aufrufer schon geprüft hat."""
    sql = ("SELECT i.id, i.inventory_no, i.serial_no, i.serial_generated, i.lock_state, i.lock_reason, i.folder_id, "
           "i.origin_folder_id, (SELECT MAX(x.completed_at) FROM mat_inspection x WHERE x.item_id = i.id "
           "AND x.completed_at IS NOT NULL AND x.corrects_inspection_id IS NULL) AS geprueft_um "
           "FROM mat_item i WHERE i.product_id = ? AND i.lock_state <> 'ausgesondert'")
    if sichtbar:
        sql += f" AND {rechte.artikel_filter('i')}"
    args = [pid]
    if iid is not None:
        sql += " AND i.id = ?"
        args.append(iid)
    return db.query(sql + " ORDER BY i.inventory_no", args)


def zustand(r, artikel):
    """(Zustand, Grund) eines betroffenen Artikels – abgeleitet aus Sperre und Prüfungen, nie gespeichert.
    Gleiche Sekunde zählt als vorher: Ob die Prüfung den Rückruf schon kannte, ist dann nicht zu sagen."""
    if artikel["lock_state"] in ("gesperrt", "verloren", "ausgesondert"):
        return "erledigt", "gesperrt" if artikel["lock_state"] != "ausgesondert" else "ausgesondert"
    if artikel["geprueft_um"] and artikel["geprueft_um"] > r["created_at"]:
        return "erledigt", "geprueft"
    return "offen", None


def betroffene(r, alle=None):
    """Die betroffenen Artikel eines Rückrufs, je mit Zustand. alle: die Artikel des Produkts im Bestand, wenn
    der Aufrufer sie schon hat – sonst die, die das Konto der Anfrage sieht."""
    alle = _artikel_im_bestand(r["product_id"]) if alle is None else alle
    filt = {_norm(s) for s in serien(r)}
    out = []
    for a in alle:
        if _passt(filt, a):
            z, grund = zustand(r, a)
            out.append(dict(a, zustand=z, grund=grund))
    return out


def nicht_gefunden(r, alle=None):
    """Seriennummern des Rückrufs, zu denen kein Artikel im Bestand passt – ein Tippfehler oder Material, das
    die Organisation nicht hat. Ein Hinweis, kein Fehler – und nur für die Material-Verwaltung: Für alle anderen
    hieße „nicht gefunden“ auch „nicht in fremden Gliederungen“."""
    alle = _artikel_im_bestand(r["product_id"], sichtbar=False) if alle is None else alle
    da = {_norm(a["serial_no"]) for a in alle}
    return [s for s in serien(r) if _norm(s) not in da]


def _zahlen(liste):
    return {"betroffen": len(liste), "offen": sum(1 for a in liste if a["zustand"] == "offen")}


def rueckruf_json(r, mit_artikel=False):
    """Ein Rückruf für das Konto der Anfrage: betroffene Artikel und ihre Zahlen nur aus dem eigenen Bereich. „mail“
    sagt, ob eine Mail angefordert war; wie viele hinausgingen (mailed_at, mail_count, mail_failed) und welche
    Seriennummern zu keinem Artikel passen (nicht_gefunden), steht nur für die Material-Verwaltung darin."""
    verwaltung = rechte.sicht().alles
    out = {f: r[f] for f in ("id", "product_id", "title", "description", "url", "created_by_name", "created_at",
                             "closed_at", "closed_by_name", "close_note")}
    # Angefordert heißt: _benachrichtigen lief – mit Empfängern steht ihre Zahl da, ohne ist mailed_at gleich gesetzt.
    out["mail"] = bool(r["mailed_at"] or r["mail_count"])
    if verwaltung:
        out.update({f: r[f] for f in ("mailed_at", "mail_count", "mail_failed")})
    out["serien"] = serien(r)
    out["alle"] = not out["serien"]
    out["aktiv"] = r["closed_at"] is None
    out["unbestaetigt_minuten"] = UNBESTAETIGT_MINUTEN
    if mit_artikel and out["aktiv"]:
        alle = _artikel_im_bestand(r["product_id"])
        liste = betroffene(r, alle)
        out.update(_zahlen(liste))
        out["artikel"] = [{"id": a["id"], "inventory_no": a["inventory_no"], "serial_no": a["serial_no"],
                           "serial_generated": bool(a["serial_generated"]), "lock_state": a["lock_state"],
                           "zustand": a["zustand"], "grund": a["grund"], "pfad": bestand._pfad_text(a["folder_id"])}
                          for a in liste]
        if verwaltung:
            out["nicht_gefunden"] = nicht_gefunden(r, alle)          # alle: die Verwaltung sieht jeden Artikel
    return out


def fuer_produkt(pid):
    """Alle Rückrufe eines Produkts: laufende zuerst (mit ihren Artikeln aus dem eigenen Bereich), dann beendete – je
    neueste zuerst."""
    rows = db.query("SELECT * FROM mat_recall WHERE product_id = ? ORDER BY closed_at IS NOT NULL, id DESC", (pid,))
    return [rueckruf_json(r, mit_artikel=True) for r in rows]


def aktive_fuer_artikel(item):
    """Laufende Rückrufe, die diesen Artikel betreffen – für das Banner am Artikel. Ein ausgesonderter Artikel ist
    außer Dienst und bekommt keins."""
    if item["lock_state"] == "ausgesondert":
        return []
    rows = db.query("SELECT * FROM mat_recall WHERE product_id = ? AND closed_at IS NULL ORDER BY id DESC",
                    (item["product_id"],))
    if not rows:
        return []
    a = _artikel_im_bestand(item["product_id"], item["id"], sichtbar=False)
    if not a:
        return []
    out = []
    for r in rows:
        if _passt({_norm(s) for s in serien(r)}, a[0]):
            z, grund = zustand(r, a[0])
            out.append({"id": r["id"], "title": r["title"], "description": r["description"], "url": r["url"],
                        "created_at": r["created_at"], "alle": not serien(r), "zustand": z, "grund": grund})
    return out


def betrifft(produkt_id, serie):
    """Laufende Rückrufe des Produkts, die einen (noch nicht angelegten) Artikel mit dieser Seriennummer betreffen –
    alle Artikel des Produkts oder S in der Seriennummernliste (Vergleich wie _passt). Für den Probelauf des
    Bestandsimports: [{"id", "title", "alle"}], neueste zuerst. Titel von Rückrufen sieht jedes Konto mit Modulzugang
    ohnehin am Produkt."""
    out = []
    for r in db.query("SELECT * FROM mat_recall WHERE product_id = ? AND closed_at IS NULL ORDER BY id DESC",
                      (produkt_id,)):
        if _passt({_norm(s) for s in serien(r)}, {"serial_no": serie}):
            out.append({"id": r["id"], "title": r["title"], "alle": not serien(r)})
    return out


def fuer_lebenslauf(item):
    """Alle Rückrufe des Produkts, die diesen Artikel betreffen (Seriennummer passt oder alle) – laufende und beendete,
    älteste zuerst; für den Lebenslauf. Laufende tragen den Zustand für den Artikel (bei ausgesonderten keinen)."""
    rows = db.query("SELECT * FROM mat_recall WHERE product_id = ? ORDER BY id", (item["product_id"],))
    bestand_zeile = None
    out = []
    for r in rows:
        if not _passt({_norm(s) for s in serien(r)}, item):
            continue
        z = grund = None
        if r["closed_at"] is None and item["lock_state"] != "ausgesondert":
            if bestand_zeile is None:
                bestand_zeile = (_artikel_im_bestand(item["product_id"], item["id"], sichtbar=False) or [None])[0]
            if bestand_zeile:
                z, grund = zustand(r, bestand_zeile)
        out.append(dict(r, alle=not serien(r), zustand=z, grund=grund))
    return out


def offene_artikel():
    """Kennung → Titel der Rückrufe (mit „ · “ verbunden) für jeden Artikel, an dem ein laufender Rückruf noch offen ist – für die Marke
    „Rückruf“ in Artikellisten – gerechnet über das, was das Konto sieht (mehr zeigen die Listen nicht). Einmal je Anfrage
    gerechnet (g): Eine Liste fragt sonst je Zeile."""
    if "mat_rueckruf_offen" not in g:
        offen = {}
        for r in db.query("SELECT * FROM mat_recall WHERE closed_at IS NULL ORDER BY id"):
            for a in betroffene(r):
                if a["zustand"] == "offen":
                    offen[a["id"]] = f"{offen[a['id']]} · {r['title']}" if a["id"] in offen else r["title"]
        g.mat_rueckruf_offen = offen
    return g.mat_rueckruf_offen


def uebersicht(nur_bestand=True):
    """Laufende Rückrufe mit Produkt und Zahlen: betroffene Artikel im eigenen Bereich, davon offen. Für die Übersicht
    (nur_bestand: nur, was Artikel im eigenen Bereich betrifft – sonst gibt es dort nichts zu tun)."""
    rows = db.query("SELECT r.*, p.manufacturer, p.model, p.description AS product_description, p.article_no "
                    "FROM mat_recall r "
                    "JOIN mat_product p ON p.id = r.product_id WHERE r.closed_at IS NULL ORDER BY r.id DESC")
    out = []
    for r in rows:
        z = _zahlen(betroffene(r))
        if nur_bestand and not z["betroffen"]:
            continue
        out.append(dict(z, id=r["id"], title=r["title"], created_at=r["created_at"], alle=not serien(r),
                        produkt={"id": r["product_id"], "manufacturer": r["manufacturer"], "model": r["model"],
                                 "description": r["product_description"], "article_no": r["article_no"]}))
    # Wo noch etwas zu tun ist, zuerst.
    out.sort(key=lambda x: not x["offen"])
    return out


# --- Anlegen und beenden (nur die Material-Verwaltung, routes_rueckruf.py prüft das) ----------------------

def anlegen(pid, d, nutzer=None):
    """Einen Rückruf am Produkt anlegen und – wenn gewünscht („mail“, Vorgabe ja) – die Verwalter und Prüfer der
    betroffenen Artikel benachrichtigen. Liefert (Kennung, Rückmeldung). Die Rückmeldung zählt den eigenen Bereich:
    betroffene und offene Artikel und ob für sie eine Mail hinausging („benachrichtigt“). Die Material-Verwaltung
    bekommt stattdessen die Zahlen über alles, die Zahl der Empfänger und die Seriennummern, zu denen kein Artikel im
    Bestand passt."""
    katalog.produkt(pid)
    w = werte(d)
    mail = True if d.get("mail") is None else wahr(d, "mail", "Mail an Materialwarte und Prüfer")
    uid, name = (nutzer["id"], (nutzer["name"] or "").strip() or OHNE_NAMEN) if nutzer else akteur()
    with db.transaction(sofort=True):
        katalog.produkt(pid)                         # inzwischen gelöscht?
        ruid = db.execute(
            "INSERT INTO mat_recall (product_id, title, description, url, serials, created_by, created_by_name, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (pid, w["title"], w["description"], w["url"], "\n".join(w["serien"]), uid, name, db.now()))
        eintrag = {"rueckruf": ruid, "title": w["title"], "serials": w["serien"] or "alle", "mail": mail}
        eintrag.update({f: w[f] for f in ("description", "url") if w[f]})        # leere Felder bleiben draußen
        journal.eintragen("product", pid, "rueckruf", None, eintrag)
    g.pop("mat_rueckruf_offen", None)
    r = rueckruf(ruid)
    alle = _artikel_im_bestand(pid, sichtbar=False)
    liste = betroffene(r, alle)
    an, erreicht = _benachrichtigen(r, liste) if mail else (0, set())
    if rechte.sicht(nutzer).alles:
        return ruid, dict(_zahlen(liste), nicht_gefunden=nicht_gefunden(r, alle), empfaenger=an, mail=mail)
    eigene = [a for a in liste if rechte.darf_artikel("lesen", a, nutzer)]
    return ruid, dict(_zahlen(eigene), mail=mail, benachrichtigt=any(a["id"] in erreicht for a in eigene))


def beenden(ruid, d):
    """Einen laufenden Rückruf mit Vermerk beenden (etwa: alle Artikel geprüft oder getauscht). Wer zweitens
    kommt, erfährt es."""
    rueckruf(ruid)
    vermerk = text(d, "vermerk", "Vermerk", VERMERK_MAX, pflicht=True, einzeilig=False)
    uid, name = akteur()
    with db.transaction(sofort=True):
        r = rueckruf(ruid)
        if not db.execute_zeilen("UPDATE mat_recall SET closed_at = ?, closed_by = ?, closed_by_name = ?, close_note = ? "
                                 "WHERE id = ? AND closed_at IS NULL", (db.now(), uid, name, vermerk, ruid)):
            raise Abgelehnt("Dieser Rückruf ist schon beendet. Bitte neu laden.", 409)
        journal.eintragen("product", r["product_id"], "rueckruf_beendet", None,
                          {"rueckruf": ruid, "title": r["title"], "close_note": vermerk})
    g.pop("mat_rueckruf_offen", None)


# --- Mails ----------------------------------------------------------------------------------------------

def _konten(ids):
    """Aktive Konten zu diesen Kennungen – ganze Zeilen, die Sicht eines Kontos braucht Häkchen und Urkundennummer."""
    if not ids:
        return {}
    return {u["id"]: u for u in db.query(f"SELECT * FROM users WHERE id IN ({','.join('?' * len(ids))}) AND active = 1 "
                                         "AND status = 'active'", sorted(ids))}


def _verwaltung():
    """Die Material-Verwaltung (aktive Konten mit Namen; gibt es keine, die Plattform-Verwaltung) – sie bekommt, was
    keinen Verwalter hat (rechte.material_verwaltung_konten)."""
    return {u["id"] for u in rechte.material_verwaltung_konten()}


def _gepruefte(pid, ids):
    """Kennung des Artikels → Konten, die an ihm eine Prüfung abgeschlossen haben (nur Artikel aus ids)."""
    out = {}
    for x in db.query("SELECT DISTINCT x.item_id, x.inspector_user_id FROM mat_inspection x JOIN mat_item i "
                      "ON i.id = x.item_id WHERE i.product_id = ? AND x.completed_at IS NOT NULL "
                      "AND x.inspector_user_id IS NOT NULL", (pid,)):
        if x["item_id"] in ids:
            out.setdefault(x["item_id"], set()).add(x["inspector_user_id"])
    return out


def empfaenger(r, liste):
    """Wer zum Rückruf eine Mail bekommt (Bauentwurf 2.6): je betroffenem Artikel die Verwalter seiner Heimat
    (rechte.verwalter_von) und die Prüfer, die ihn geprüft haben und dort heute prüfen dürfen (Qualifikation und
    gültige Prüffreigabe); hat ein Artikel keinen Verwalter, die Material-Verwaltung. Nur aktive Konten mit Adresse,
    jedes einmal, keine Obergrenze – ein Rückruf muss alle erreichen.

    Liefert [(Konto, Artikel, Rolle)]: je Empfänger genau die betroffenen Artikel, die er sehen darf – Artikel aus
    Bereichen, die er nicht sieht, stehen nicht in seiner Mail (auch keine Zahl über sie) – und seine Rolle fürs
    Mailfehler-Protokoll (verwalter vor pruefer vor verwaltung, wenn mehrere zutreffen)."""
    if not liste:
        return []
    pruefer = _gepruefte(r["product_id"], {a["id"] for a in liste})
    konten = _konten({uid for wer in pruefer.values() for uid in wer})
    wer, verwalter, verwaltung = {}, {}, None          # Kennung → Rollen
    for a in liste:
        h = bestand.heimat(a)
        if h not in verwalter:
            verwalter[h] = {v["id"] for v in rechte.verwalter_von(h)}
        if verwalter[h]:
            for uid in verwalter[h]:
                wer.setdefault(uid, set()).add("verwalter")
        else:
            verwaltung = _verwaltung() if verwaltung is None else verwaltung
            for uid in verwaltung:
                wer.setdefault(uid, set()).add("verwaltung")
        for uid in pruefer.get(a["id"], ()):
            if uid in konten and rechte.darf_artikel("pruefen", a, konten[uid]):
                wer.setdefault(uid, set()).add("pruefer")
    konten.update(_konten(set(wer) - set(konten)))
    out, gesehen = [], set()
    for uid in sorted(wer):
        u = konten.get(uid)
        adr = ((u or {}).get("email") or "").strip()
        if not adr or adr.casefold() in gesehen:
            continue
        sichtbar = [a for a in liste if rechte.darf_artikel("lesen", a, u)]
        if sichtbar:
            gesehen.add(adr.casefold())
            out.append((u, sichtbar, next(x for x in ("verwalter", "pruefer", "verwaltung") if x in wer[uid])))
    return out


def _mailtext(r, p, liste):
    """Betreff und Text der Mail an einen Empfänger – liste: seine betroffenen Artikel (die er sehen darf)."""
    cfg = current_app.config
    basis = cfg["BASE_URL"].rstrip("/")
    s = serien(r)
    name = katalog.produktname(p)
    zeilen = [f"{r['created_by_name'] or 'Die Material-Verwaltung'} hat einen Rückruf für ein Produkt im Katalog angelegt:", "",
              f"Produkt:      {name}" + (f" (Art.-Nr. {p['article_no']})" if p["article_no"] else ""),
              f"Rückruf:      {r['title']}",
              "Betroffen:    " + ("alle Artikel dieses Produkts" if not s else f"{len(s)} Seriennummer{'' if len(s) == 1 else 'n'} (unten)"),
              f"Dein Bereich: {len(liste)} betroffene{'r' if len(liste) == 1 else ''} Artikel"]
    if r["description"]:
        zeilen += ["", "Was betroffen ist und was zu tun ist:", r["description"]]
    if r["url"]:
        zeilen += ["", f"Meldung des Herstellers: {r['url']}"]
    if s:
        zeilen += ["", "Betroffene Seriennummern:"] + [f"  {x}" for x in s]
    if liste:
        zeilen += ["", "Betroffene Artikel in deinem Bereich:"]
        zeilen += [f"  {a['inventory_no']}  SN {a['serial_no']}  {bestand._pfad_text(a['folder_id'])}"
                   for a in liste[:MAIL_ARTIKEL_MAX]]
        if len(liste) > MAIL_ARTIKEL_MAX:
            zeilen.append(f"  … und {len(liste) - MAIL_ARTIKEL_MAX} weitere (siehe Produktseite)")
    zeilen += ["", "Artikel in Bereichen, die du nicht siehst, gehen an deren Materialwarte."]
    zeilen += ["", "Sperren: Prüfer sperren betroffene Artikel ohne Prüfung mit dem Grund „Rückruf“ (am Artikel: "
               "„Sperren (Rückruf)“). Eine Prüfung nach diesem Rückruf erledigt ihn für den Artikel ebenso.", "",
               f"Produkt und betroffene Artikel: {basis}/material/katalog/produkt/{p['id']}",
               f"Übersicht: {basis}/material"]
    betreff = " ".join(f"Rückruf: {name} – {r['title']}".split())       # auch U+2028/U+0085: ein Betreff ist eine Zeile
    return betreff, "\n".join(zeilen) + "\n"


def _benachrichtigen(r, liste):
    """Mails vorbereiten und neben der Anfrage verschicken – je Empfänger eine mit seinen Artikeln (empfaenger). Bis das
    Ergebnis da ist, steht in mail_count die Zahl der Empfänger und mailed_at ist leer („wird verschickt“); danach
    mailed_at, die Zahl der angenommenen und der gescheiterten Mails. liste: alle betroffenen Artikel, nicht nur die
    sichtbaren. Liefert (Zahl der Empfänger, Kennungen der Artikel, die in einer Mail stehen)."""
    post = empfaenger(r, liste)
    if not post:
        db.execute("UPDATE mat_recall SET mailed_at = ?, mail_count = 0, mail_failed = 0 WHERE id = ?", (db.now(), r["id"]))
        return 0, set()
    p = katalog.produkt(r["product_id"])
    gliederung = {}                                  # Heimat → Gliederung, einmal je Ordner
    mails = []
    for u, artikel, rolle in post:
        gl = set()
        for a in artikel:
            h = bestand.heimat(a)
            if h not in gliederung:
                g_ = bestand.gliederung_von(h)
                gliederung[h] = g_["id"] if g_ else None
            if gliederung[h] is not None:
                gl.add(gliederung[h])
        mails.append((u["email"].strip(), *_mailtext(r, p, artikel), u["id"], rolle, gl))
    db.execute("UPDATE mat_recall SET mail_count = ?, mail_failed = 0 WHERE id = ?", (len(mails), r["id"]))
    HINTERGRUND(_versenden, r["id"], mails)
    return len(mails), {a["id"] for _, artikel, _ in post for a in artikel}


def _versenden(ruid, mails):
    """Läuft im Hintergrund – mit eigenem App-Kontext und damit eigener Datenbankverbindung (_im_hintergrund).
    mails: [(an, betreff, inhalt, Konto, Rolle, Gliederungen)] – jede einzeln über mailprotokoll.senden (Bezug der
    Rückruf, je Gliederung der Artikel in der Mail eine Protokollzeile); eine Adresse, an der es scheitert, hält die
    anderen nicht auf."""
    gut = schlecht = 0
    for an, betreff, inhalt, konto_id, rolle, gl in mails:
        try:
            ok = mailprotokoll.senden(an, betreff, inhalt, art="rueckruf", konto_id=konto_id, rolle=rolle,
                                      bezug_art="recall", bezug_id=ruid, folder_id=gl)
        except Exception as exc:                     # senden wirft nicht – eine Ausnahme soll trotzdem nur zählen
            current_app.logger.error("Rückruf %s: Mail an Konto %s gescheitert: %s", ruid, konto_id, exc)
            ok = False
        if ok:
            gut += 1
        else:
            schlecht += 1
    db.execute("UPDATE mat_recall SET mailed_at = ?, mail_count = ?, mail_failed = ? WHERE id = ?",
               (db.now(), gut, schlecht, ruid))
    if schlecht:
        current_app.logger.warning("Rückruf %s: %s von %s Mails gingen nicht hinaus.", ruid, schlecht, gut + schlecht)
