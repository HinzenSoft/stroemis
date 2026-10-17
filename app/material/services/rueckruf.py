"""Rückrufe: Der Hersteller ruft ein Produkt zurück oder warnt davor.

Ein Katalogpfleger (oder die Verwaltung) legt den Rückruf am Produkt an: Titel, was betroffen ist und was zu tun
ist, ein Link auf die Meldung des Herstellers und – wenn der Hersteller sie nennt – die betroffenen Seriennummern,
eine je Zeile; ohne Seriennummern gilt er für alle Artikel des Produkts. Sichtbar ist er für alle mit Zugang zum
Modul: am Produkt, als Banner an jedem betroffenen Artikel und als Kasten auf der Übersicht. Eine Mail geht an
alle Materialwarte und an die Prüfer, die einen betroffenen Artikel schon geprüft haben.

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
from ...mailer import send_mail
from . import Abgelehnt, akteur, text, wahr
from . import bestand, journal, katalog
from .rechte import ist_pruefer

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


def _artikel_im_bestand(pid, iid=None):
    """Artikel des Produkts im Bestand (nicht ausgesondert) mit dem Zeitpunkt ihrer letzten abgeschlossenen
    Prüfung. Berichtigungen zählen nicht – sie ändern eine alte Prüfung, sie sind keine neue."""
    sql = ("SELECT i.id, i.inventory_no, i.serial_no, i.serial_generated, i.lock_state, i.lock_reason, i.folder_id, "
           "(SELECT MAX(x.completed_at) FROM mat_inspection x WHERE x.item_id = i.id AND x.completed_at IS NOT NULL "
           "AND x.corrects_inspection_id IS NULL) AS geprueft_um "
           "FROM mat_item i WHERE i.product_id = ? AND i.lock_state <> 'ausgesondert'")
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
    der Aufrufer sie schon hat."""
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
    die Organisation nicht hat. Ein Hinweis, kein Fehler."""
    alle = _artikel_im_bestand(r["product_id"]) if alle is None else alle
    da = {_norm(a["serial_no"]) for a in alle}
    return [s for s in serien(r) if _norm(s) not in da]


def _zahlen(liste):
    return {"betroffen": len(liste), "offen": sum(1 for a in liste if a["zustand"] == "offen")}


def rueckruf_json(r, mit_artikel=False):
    out = {f: r[f] for f in ("id", "product_id", "title", "description", "url", "created_by_name", "created_at",
                             "closed_at", "closed_by_name", "close_note", "mailed_at", "mail_count", "mail_failed")}
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
        out["nicht_gefunden"] = nicht_gefunden(r, alle)
    return out


def fuer_produkt(pid):
    """Alle Rückrufe eines Produkts: laufende zuerst (mit ihren Artikeln), dann beendete – je neueste zuerst."""
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
    a = _artikel_im_bestand(item["product_id"], item["id"])
    if not a:
        return []
    out = []
    for r in rows:
        if _passt({_norm(s) for s in serien(r)}, a[0]):
            z, grund = zustand(r, a[0])
            out.append({"id": r["id"], "title": r["title"], "description": r["description"], "url": r["url"],
                        "created_at": r["created_at"], "alle": not serien(r), "zustand": z, "grund": grund})
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
                bestand_zeile = (_artikel_im_bestand(item["product_id"], item["id"]) or [None])[0]
            if bestand_zeile:
                z, grund = zustand(r, bestand_zeile)
        out.append(dict(r, alle=not serien(r), zustand=z, grund=grund))
    return out


def offene_artikel():
    """Kennung → Titel der Rückrufe (mit „ · “ verbunden) für jeden Artikel, an dem ein laufender Rückruf noch offen ist – für die Marke
    „Rückruf“ in Artikellisten. Einmal je Anfrage gerechnet (g): Eine Liste fragt sonst je Zeile."""
    if "mat_rueckruf_offen" not in g:
        offen = {}
        for r in db.query("SELECT * FROM mat_recall WHERE closed_at IS NULL ORDER BY id"):
            for a in betroffene(r):
                if a["zustand"] == "offen":
                    offen[a["id"]] = f"{offen[a['id']]} · {r['title']}" if a["id"] in offen else r["title"]
        g.mat_rueckruf_offen = offen
    return g.mat_rueckruf_offen


def uebersicht(nur_bestand=True):
    """Laufende Rückrufe mit Produkt und Zahlen: betroffene Artikel im Bestand, davon offen. Für die Übersicht
    (nur_bestand: nur, was Artikel im Bestand betrifft – sonst gibt es dort nichts zu tun)."""
    rows = db.query("SELECT r.*, p.manufacturer, p.model, p.article_no FROM mat_recall r "
                    "JOIN mat_product p ON p.id = r.product_id WHERE r.closed_at IS NULL ORDER BY r.id DESC")
    out = []
    for r in rows:
        z = _zahlen(betroffene(r))
        if nur_bestand and not z["betroffen"]:
            continue
        out.append(dict(z, id=r["id"], title=r["title"], created_at=r["created_at"], alle=not serien(r),
                        produkt={"id": r["product_id"], "manufacturer": r["manufacturer"], "model": r["model"],
                                 "article_no": r["article_no"]}))
    # Wo noch etwas zu tun ist, zuerst.
    out.sort(key=lambda x: not x["offen"])
    return out


# --- Anlegen und beenden (nur Katalogpfleger, routes_rueckruf.py prüft das) -------------------------------

def anlegen(pid, d, nutzer=None):
    """Einen Rückruf am Produkt anlegen und – wenn gewünscht („mail“, Vorgabe ja) – Materialwarte und Prüfer
    benachrichtigen. Liefert (Kennung, Rückmeldung): betroffene und offene Artikel, Zahl der Empfänger und die
    Seriennummern, zu denen kein Artikel im Bestand passt."""
    katalog.produkt(pid)
    w = werte(d)
    mail = True if d.get("mail") is None else wahr(d, "mail", "Mail an Materialwarte und Prüfer")
    uid, name = (nutzer["id"], nutzer["name"] or nutzer["email"]) if nutzer else akteur()
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
    alle = _artikel_im_bestand(pid)
    liste = betroffene(r, alle)
    info = dict(_zahlen(liste), nicht_gefunden=nicht_gefunden(r, alle), empfaenger=0, mail=mail)
    if mail:
        info["empfaenger"] = _benachrichtigen(r, liste)
    return ruid, info


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

def materialwarte():
    """Alle aktiven Materialwarte; gibt es keinen, die Verwaltung (sie ist dann der Materialwart)."""
    rows = db.query("SELECT id, email, name FROM users WHERE active = 1 AND recht_material = 2 ORDER BY id")
    if not rows:
        rows = db.query("SELECT id, email, name FROM users WHERE active = 1 AND recht_verwaltung = 2 ORDER BY id")
    return rows


def pruefer_der(pid, artikel_ids):
    """Aktive Prüfer (mit gültiger Urkundennummer – das prüft nur Python, siehe rechte.ist_pruefer), die an einem
    dieser Artikel des Produkts schon eine Prüfung abgeschlossen haben."""
    ids = set(artikel_ids)
    if not ids:
        return []
    wer = {x["inspector_user_id"] for x in db.query(
        "SELECT DISTINCT x.item_id, x.inspector_user_id FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id "
        "WHERE i.product_id = ? AND x.completed_at IS NOT NULL AND x.inspector_user_id IS NOT NULL", (pid,))
        if x["item_id"] in ids}
    return [u for u in db.query("SELECT * FROM users WHERE active = 1 AND mat_pruefer = 1 ORDER BY id")
            if u["id"] in wer and ist_pruefer(u)]


def empfaenger(r, liste):
    """Adressen für die Benachrichtigung: alle Materialwarte und die Prüfer betroffener Artikel, jede nur einmal.
    Keine Obergrenze – ein Rückruf muss alle erreichen."""
    an, gesehen = [], set()
    for u in materialwarte() + pruefer_der(r["product_id"], [a["id"] for a in liste]):
        adr = (u["email"] or "").strip()
        if adr and adr.casefold() not in gesehen:
            gesehen.add(adr.casefold())
            an.append(adr)
    return an


def _mailtext(r, p, liste):
    cfg = current_app.config
    basis = cfg["BASE_URL"].rstrip("/")
    s = serien(r)
    name = f"{p['manufacturer']} {p['model']}"
    zeilen = [f"{r['created_by_name'] or 'Ein Katalogpfleger'} hat einen Rückruf für ein Produkt im Katalog angelegt:", "",
              f"Produkt:      {name}" + (f" (Art.-Nr. {p['article_no']})" if p["article_no"] else ""),
              f"Rückruf:      {r['title']}",
              "Betroffen:    " + ("alle Artikel dieses Produkts" if not s else f"{len(s)} Seriennummer{'' if len(s) == 1 else 'n'} (unten)"),
              f"Im Bestand:   {len(liste)} betroffene{'r' if len(liste) == 1 else ''} Artikel"]
    if r["description"]:
        zeilen += ["", "Was betroffen ist und was zu tun ist:", r["description"]]
    if r["url"]:
        zeilen += ["", f"Meldung des Herstellers: {r['url']}"]
    if s:
        zeilen += ["", "Betroffene Seriennummern:"] + [f"  {x}" for x in s]
    if liste:
        zeilen += ["", "Betroffene Artikel im Bestand:"]
        zeilen += [f"  {a['inventory_no']}  SN {a['serial_no']}  {bestand._pfad_text(a['folder_id'])}"
                   for a in liste[:MAIL_ARTIKEL_MAX]]
        if len(liste) > MAIL_ARTIKEL_MAX:
            zeilen.append(f"  … und {len(liste) - MAIL_ARTIKEL_MAX} weitere (siehe Produktseite)")
    zeilen += ["", "Sperren: Prüfer sperren betroffene Artikel ohne Prüfung mit dem Grund „Rückruf“ (am Artikel: "
               "„Sperren (Rückruf)“). Eine Prüfung nach diesem Rückruf erledigt ihn für den Artikel ebenso.", "",
               f"Produkt und betroffene Artikel: {basis}/material/katalog/produkt/{p['id']}",
               f"Übersicht: {basis}/material"]
    betreff = " ".join(f"Rückruf: {name} – {r['title']}".split())       # auch U+2028/U+0085: ein Betreff ist eine Zeile
    return betreff, "\n".join(zeilen) + "\n"


def _benachrichtigen(r, liste):
    """Mails vorbereiten und neben der Anfrage verschicken. Bis das Ergebnis da ist, steht in mail_count die Zahl
    der Empfänger und mailed_at ist leer („wird verschickt“); danach mailed_at, die Zahl der angenommenen und der
    gescheiterten Mails. Liefert die Zahl der Empfänger."""
    an = empfaenger(r, liste)
    if not an:
        db.execute("UPDATE mat_recall SET mailed_at = ?, mail_count = 0, mail_failed = 0 WHERE id = ?", (db.now(), r["id"]))
        return 0
    betreff, inhalt = _mailtext(r, katalog.produkt(r["product_id"]), liste)
    db.execute("UPDATE mat_recall SET mail_count = ?, mail_failed = 0 WHERE id = ?", (len(an), r["id"]))
    HINTERGRUND(_versenden, r["id"], [(a, betreff, inhalt) for a in an])
    return len(an)


def _versenden(ruid, mails):
    """Läuft im Hintergrund – mit eigenem App-Kontext und damit eigener Datenbankverbindung (_im_hintergrund).
    Jede Mail einzeln; eine Adresse, an der es scheitert, hält die anderen nicht auf."""
    gut = schlecht = 0
    for an, betreff, inhalt in mails:
        try:
            ok = send_mail(an, betreff, inhalt)
        except Exception as exc:                     # send_mail wirft nicht – eine Ausnahme soll trotzdem nur zählen
            current_app.logger.error("Rückruf %s: Mail an %s gescheitert: %s", ruid, an, exc)
            ok = False
        if ok:
            gut += 1
        else:
            schlecht += 1
    db.execute("UPDATE mat_recall SET mailed_at = ?, mail_count = ?, mail_failed = ? WHERE id = ?",
               (db.now(), gut, schlecht, ruid))
    if schlecht:
        current_app.logger.warning("Rückruf %s: %s von %s Mails gingen nicht hinaus.", ruid, schlecht, gut + schlecht)
