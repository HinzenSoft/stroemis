"""Meldungen fehlender Produkte.

Wer Artikel anlegt (Materialwart), findet nicht jedes Produkt im Katalog. Anlegen darf es nur die
Material-Verwaltung – der Katalog gilt plattformweit und soll einheitlich bleiben. Der Materialwart meldet
es deshalb: Hersteller, Modell, was er sonst weiß, Links (Herstellerseite, Gebrauchsanleitung, Händler)
und Fotos (Etikett, Typenschild). Die Material-Verwaltung bekommt eine Mail (gibt es keine, die
Plattform-Verwaltung) und arbeitet die Meldungen ab:

  - einpflegen: ein neues Produkt aus der Meldung anlegen oder ein vorhandenes zuordnen,
  - ablehnen: nur mit Begründung.

Der Melder bekommt in beiden Fällen eine Mail, nach dem Einpflegen mit einem Link, der „Artikel
anlegen“ mit Produkt und Ordner öffnet – kam die Meldung aus der Nacharbeit eines Bestandsimports, mit dem Link dorthin. Löschen kann eine Meldung nur, wer sie gemacht hat – offen oder
erledigt; ein Produkt, das aus ihr entstand, bleibt. Sonst bleibt sie stehen: Sie ist der Weg eines
Produkts in den Katalog und steht im Journal (entity „request“, am Produkt mit angezeigt).

Sehen darf eine Meldung seit Phase 2 nur, wer Material-Verwaltung ist, sie gemacht hat oder den Ordner sieht, für
den sie gemacht wurde (rechte.darf_meldung) – eine Meldung nennt Material und Ordner einer Gliederung. Den Ordnerpfad
zeigt sie nur, wer den Ordner sieht (die Material-Verwaltung immer); sonst steht nur die Gliederung da. Die Mail an die
Material-Verwaltung nennt nur die Gliederung – eine Mail ist schlechter geschützt als die Seite.

Verschickt wird über mailprotokoll.senden (Phase 4 · L1): Ohne Mailserver, unter der Umgebungssperre (dev) und an
DEMO-Adressen geht nichts hinaus; was der Mailserver nicht annimmt, steht im Mailfehler-Protokoll (Rolle Verwaltung
bzw. Melder, Gliederung die des Ordners der Meldung – nur die Material-Verwaltung sieht diese Zeilen)."""
import json
import os
import re

from flask import current_app

from ... import db
from ...auth import _im_hintergrund, current_user
from ...images import delete_photo_files
from ..models import MELDUNGSSTATUS
from . import Abgelehnt, akteur, kennung, text
from . import bestand, journal, katalog, mailprotokoll, rechte

MAX_LINKS = 5
LINK_MAX = 500
MAX_FOTOS = 3
NOTIZ_MAX = 2000
ANTWORT_MAX = 1000
MAX_EMPFAENGER = 10
FILTER = {"offen": ("offen",), "erledigt": ("eingepflegt", "abgelehnt"), "alle": tuple(MELDUNGSSTATUS)}
FEHLT = "Meldung nicht gefunden."

# Mails gehen neben der Anfrage hinaus (wie bei Kontoanfragen); Tests setzen hier einen direkten Aufruf ein.
HINTERGRUND = _im_hintergrund

_LINK = re.compile(r"https?://[^\s/?#]+\S*", re.IGNORECASE)


def links_lesen(wert):
    """Adressen aus der Meldung: eine Liste oder ein Text mit einer je Zeile. Nur http(s) – ein
    „javascript:“-Link in der Liste der Material-Verwaltung wäre eine Falle. „www.…“ ohne Schema bekommt
    https:// vorangestellt, so tippen Leute Adressen."""
    if wert is None or wert == "":
        return []
    if isinstance(wert, str):
        teile = wert.splitlines()
    elif isinstance(wert, list) and all(isinstance(x, str) for x in wert):
        teile = wert
    else:
        raise Abgelehnt("„Links“ müssen Text sein – eine Adresse je Zeile.")
    links = []
    for t in (x.strip() for x in teile):
        if not t:
            continue
        if t.lower().startswith("www."):
            t = "https://" + t
        if len(t) > LINK_MAX:
            raise Abgelehnt(f"Ein Link ist zu lang (höchstens {LINK_MAX} Zeichen).")
        if re.search(r"[\x00-\x1f\x7f]", t) or not _LINK.fullmatch(t):
            raise Abgelehnt(f"„{t[:80]}“ ist keine Adresse, die mit http:// oder https:// beginnt.")
        if t not in links:
            links.append(t)
    if len(links) > MAX_LINKS:
        raise Abgelehnt(f"Höchstens {MAX_LINKS} Links.")
    return links


def _groesse(f):
    pos = f.stream.tell()
    f.stream.seek(0, os.SEEK_END)
    n = f.stream.tell()
    f.stream.seek(pos)
    return n


def fotos_ablegen(dateien):
    """Fotos durch die Bildverarbeitung des Katalogs. Scheitert eins, gehen die schon abgelegten wieder."""
    dateien = [f for f in dateien or () if f and f.filename]
    if len(dateien) > MAX_FOTOS:
        raise Abgelehnt(f"Höchstens {MAX_FOTOS} Fotos.")
    for f in dateien:
        if _groesse(f) > katalog.BILD_MAX_BYTES:
            raise Abgelehnt(f"„{f.filename}“ ist zu groß (höchstens {katalog.BILD_MAX_BYTES // (1024 * 1024)} MB je Foto).")
    abgelegt = []
    try:
        for f in dateien:
            abgelegt.append(katalog.foto_ablegen(f))
    except BaseException:
        for name in abgelegt:
            delete_photo_files(katalog.medien_dir(), name)
        raise
    return abgelegt


def meldung(mid):
    r = db.query("SELECT * FROM mat_product_request WHERE id = ?", (mid,), one=True)
    if not r:
        raise Abgelehnt(FEHLT, 404)
    return r


def lesbar(mid):
    """Die Meldung, wenn das Konto der Anfrage sie sehen darf (rechte.darf_meldung) – sonst dieselbe 404 wie für eine,
    die es nicht gibt."""
    r = meldung(mid)
    if not rechte.darf_meldung(r):
        raise Abgelehnt(FEHLT, 404)
    return r


def _sichtbar(user=None):
    """SQL-Bedingung über mat_product_request (ohne Kürzel) und ihre Parameter: die Meldungen, die das Konto sehen darf –
    dieselbe Regel wie rechte.darf_meldung, als Filter statt je Zeile."""
    user = user or current_user()
    if not user or not rechte.zugang(user):
        return "0", []
    if rechte.ist_material_verwaltung(user):
        return "1", []
    return (f"(created_by = ? OR (folder_id IS NOT NULL AND {rechte.ordner_filter('folder_id', user=user)}))",
            [user["id"]])


def anlegen(d, dateien=()):
    """Eine Meldung anlegen und die Material-Verwaltung benachrichtigen. Steht das Produkt schon im Katalog
    (gleiche Dublette wie dort: Hersteller + Modell + Artikelnummer), gibt es nichts zu melden."""
    w = {
        "manufacturer": text(d, "manufacturer", "Hersteller", 120, pflicht=True),
        "model": text(d, "model", "Modell", 160, pflicht=True),
        "article_no": katalog.artikelnummer(text(d, "article_no", "Artikelnummer", 80)),
        "norm": text(d, "norm", "Norm", 200),
        "category_id": kennung(d.get("category_id"), "Kategorie", leer_erlaubt=True),
        "folder_id": kennung(d.get("folder_id"), "Ordner", leer_erlaubt=True),
        "links": links_lesen(d.get("links")),
        "note": text(d, "note", "Bemerkung", NOTIZ_MAX, einzeilig=False),
    }
    if w["category_id"]:
        katalog.kategorie(w["category_id"])
    if w["folder_id"]:
        bestand.ordner(w["folder_id"])
    key = katalog.dedupe_key(w["manufacturer"], w["model"], w["article_no"])
    da = db.query("SELECT manufacturer, model, description FROM mat_product WHERE dedupe_key = ?", (key,), one=True)
    if da:
        raise Abgelehnt(f"„{katalog.produktname(da)}“ steht schon im Katalog – bitte in der Produktsuche "
                        "danach suchen.", 409)
    # Dieselbe Artikelnummer bei diesem Hersteller (seit dem 22.10.2026 nur je Hersteller eindeutig – bei einem anderen
    # Hersteller ist sie ein anderes Produkt).
    da = katalog.artikelnummer_vergeben(w["article_no"], w["manufacturer"])
    if da:
        raise Abgelehnt(f"Die Artikelnummer „{w['article_no']}“ gehört im Katalog zu „{katalog.produktname(da)}“ – "
                        "bitte in der Produktsuche danach suchen.", 409)
    fotos = fotos_ablegen(dateien)
    uid, name = akteur()
    try:
        with db.transaction():
            mid = db.execute(
                "INSERT INTO mat_product_request (manufacturer, model, article_no, dedupe_key, norm, category_id, folder_id, "
                "links_json, photos_json, note, created_by, created_by_name, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w["manufacturer"], w["model"], w["article_no"], key, w["norm"], w["category_id"], w["folder_id"],
                 json.dumps(w["links"], ensure_ascii=False), json.dumps(fotos), w["note"], uid, name, db.now()))
            journal.eintragen("request", mid, "angelegt", None, dict(w, fotos=len(fotos)))
    except BaseException:
        for f in fotos:
            delete_photo_files(katalog.medien_dir(), f)
        raise
    _verwaltung_benachrichtigen(meldung(mid))
    return mid


def liste(filter_="offen", uid=None, grenze=200):
    """Meldungen nach Status, soweit das Konto der Anfrage sie sehen darf: offene der Reihe nach (älteste zuerst),
    erledigte neueste zuerst. Mit uid nur die eigenen – so sieht ein Materialwart, was aus seinen Meldungen geworden
    ist."""
    stati = FILTER.get(filter_) or FILTER["offen"]
    sichtbar, args = _sichtbar()
    sql = f"SELECT * FROM mat_product_request WHERE status IN ({','.join('?' * len(stati))}) AND {sichtbar}"
    args = list(stati) + args
    if uid is not None:
        sql += " AND created_by = ?"
        args.append(uid)
    sql += " ORDER BY id" if stati == FILTER["offen"] else " ORDER BY COALESCE(resolved_at, created_at) DESC, id DESC"
    return db.query(sql + " LIMIT ?", (*args, grenze))


def anzahl_offen():
    """Offene Meldungen, die das Konto der Anfrage sehen darf."""
    sichtbar, args = _sichtbar()
    return db.query(f"SELECT COUNT(*) AS n FROM mat_product_request WHERE status = 'offen' AND {sichtbar}", args,
                    one=True)["n"]


def _gliederung(fid):
    gl = bestand.gliederung_von(fid)
    return gl["name"] if gl else ""


def meldung_json(r):
    uid, _ = akteur()
    out = {f: r[f] for f in ("id", "manufacturer", "model", "article_no", "norm", "note", "status", "answer",
                             "created_by_name", "created_at", "resolved_by_name", "resolved_at")}
    out["eigen"] = bool(uid and r["created_by"] == uid)
    k = db.query("SELECT id FROM mat_category WHERE id = ?", (r["category_id"],), one=True) if r["category_id"] else None
    out["kategorie"] = ({"id": k["id"], "pfad": " / ".join(x["name"] for x in katalog.kategorie_pfad(k["id"]))}
                        if k else None)
    o = db.query("SELECT id FROM mat_folder WHERE id = ?", (r["folder_id"],), one=True) if r["folder_id"] else None
    # Den Ordner (Kennung und Pfad) nur, wer ihn sieht – ein Melder, der den Ordner nicht mehr sieht, liest nur die
    # Gliederung.
    if not o:
        out["ordner"] = None
    elif rechte.darf("lesen", o["id"]):
        out["ordner"] = {"id": o["id"], "pfad": " / ".join(x["name"] for x in bestand.pfad(o["id"]))}
    else:
        out["ordner"] = {"gliederung": _gliederung(o["id"])}
    out["links"] = json.loads(r["links_json"] or "[]")
    out["fotos"] = [{"vorschau": katalog.bild_url(f, "thumb"), "web": katalog.bild_url(f), "original": katalog.bild_url(f, "orig")}
                    for f in json.loads(r["photos_json"] or "[]")]
    p = db.query("SELECT * FROM mat_product WHERE id = ?", (r["product_id"],), one=True) if r["product_id"] else None
    out["produkt"] = katalog.produkt_json(p) if p else None
    out["produkt_geloescht"] = r["status"] == "eingepflegt" and not p
    # Steht das Produkt inzwischen im Katalog (angelegt aus einer anderen Meldung oder direkt; gleiche Dublette
    # oder gleiche Artikelnummer beim selben Hersteller – bei einem anderen ist es ein anderes Produkt), genügt ein
    # Klick.
    t = None
    if r["status"] == "offen":
        t = db.query("SELECT * FROM mat_product WHERE dedupe_key = ?", (r["dedupe_key"],), one=True)
        v = None if t else katalog.artikelnummer_vergeben(r["article_no"], r["manufacturer"])
        t = t or (katalog.produkt(v["id"]) if v else None)
    out["treffer"] = katalog.produkt_json(t) if t else None
    return out


# --- Abarbeiten (nur die Material-Verwaltung, routes.py prüft das) ------------------------------------

def _abschliessen(mid, status, pid, antwort):
    """Innerhalb der Transaktion: Nur eine offene Meldung lässt sich erledigen – wer zweitens kommt, erfährt es."""
    uid, name = akteur()
    if not db.execute_zeilen(
            "UPDATE mat_product_request SET status = ?, product_id = ?, answer = ?, resolved_by = ?, resolved_by_name = ?, "
            "resolved_at = ? WHERE id = ? AND status = 'offen'", (status, pid, antwort, uid, name, db.now(), mid)):
        if not db.query("SELECT 1 FROM mat_product_request WHERE id = ?", (mid,), one=True):
            raise Abgelehnt("Diese Meldung hat ihr Melder inzwischen gelöscht.", 404)
        raise Abgelehnt("Diese Meldung ist schon erledigt. Bitte neu laden.", 409)
    journal.eintragen("request", mid, status, {"status": "offen"}, {"status": status, "product_id": pid, "answer": antwort})


def _antwort(d, pflicht=False):
    return text(d, "antwort", "Begründung" if pflicht else "Antwort an den Melder", ANTWORT_MAX, pflicht=pflicht,
                einzeilig=False)


def produkt_anlegen(mid, d):
    """Ein neues Produkt aus der Meldung. Anlegen und Erledigen in einer Transaktion: Ist die Meldung
    inzwischen erledigt, entsteht auch kein Produkt."""
    meldung(mid)
    antwort = _antwort(d)
    with db.transaction(sofort=True):
        # Erst die Meldung, dann das Produkt: Wer eine erledigte nachbearbeitet, soll das erfahren – nicht, dass
        # die Artikelnummer inzwischen vergeben ist.
        if meldung(mid)["status"] != "offen":
            raise Abgelehnt("Diese Meldung ist schon erledigt. Bitte neu laden.", 409)
        pid = katalog.produkt_anlegen(d)
        _abschliessen(mid, "eingepflegt", pid, antwort)
    _melder_benachrichtigen(meldung(mid))
    return pid


def zuordnen(mid, d):
    """Das Produkt steht schon im Katalog (anders geschrieben, mit anderer Artikelnummer …)."""
    meldung(mid)
    pid = kennung(d.get("product_id"), "Produkt")
    katalog.produkt(pid)
    antwort = _antwort(d)
    with db.transaction(sofort=True):
        _abschliessen(mid, "eingepflegt", pid, antwort)
    _melder_benachrichtigen(meldung(mid))


def ablehnen(mid, d):
    meldung(mid)
    antwort = _antwort(d, pflicht=True)
    with db.transaction(sofort=True):
        _abschliessen(mid, "abgelehnt", None, antwort)
    _melder_benachrichtigen(meldung(mid))


def loeschen(mid):
    """Der Melder löscht seine Meldung – offen (sie verschwindet bei der Material-Verwaltung) oder erledigt. Ein
    Produkt, das aus ihr entstand, bleibt; die Fotos gehen mit. Die eigene auch ohne Zugang zum Modul: Lesen kann er
    sie dann nicht mehr, aber es sind seine Angaben. Wer eine fremde Meldung nicht sehen darf, bekommt dieselbe 404
    wie für eine, die es nicht gibt (lesbar); 403 nur, wer sie sieht, aber nicht gemacht hat."""
    uid, _ = akteur()
    r = meldung(mid)
    if not uid or r["created_by"] != uid:
        lesbar(mid)
        raise Abgelehnt("Löschen kann eine Meldung nur, wer sie gemacht hat.", 403)
    with db.transaction(sofort=True):
        if not db.execute_zeilen("DELETE FROM mat_product_request WHERE id = ?", (mid,)):
            raise Abgelehnt("Meldung nicht gefunden.", 404)
        journal.eintragen("request", mid, "geloescht", {f: r[f] for f in ("manufacturer", "model", "article_no", "status",
                                                                         "product_id")}, None)
    for f in json.loads(r["photos_json"] or "[]"):
        delete_photo_files(katalog.medien_dir(), f)


# --- Mails ----------------------------------------------------------------------------------------------

def _gliederung_id(fid):
    gl = bestand.gliederung_von(fid) if fid else None
    return gl["id"] if gl else None


def _senden(mails, mid, folder_id=None):
    """Läuft im Hintergrund. mails: [(an, betreff, inhalt, Konto, Rolle)] – jede einzeln über mailprotokoll.senden (Bezug
    die Meldung, Gliederung die des Ordners, für den gemeldet wurde)."""
    for an, betreff, inhalt, konto_id, rolle in mails:
        try:
            mailprotokoll.senden(an, betreff, inhalt, art="meldung", konto_id=konto_id, rolle=rolle, bezug_art="request",
                                 bezug_id=mid, folder_id=folder_id)
        except Exception as exc:                     # senden wirft nicht – eine Ausnahme hält trotzdem nichts auf
            current_app.logger.error("Produktmeldung %s: Mail an Konto %s gescheitert: %s", mid, konto_id, exc)


def _verwaltung_benachrichtigen(r):
    """Mail zu einer neuen Meldung an die Material-Verwaltung – gibt es keine, an die Plattform-Verwaltung
    (rechte.material_verwaltung_konten); nicht an den Melder selbst."""
    cfg = current_app.config
    an = [(u["email"], u["id"]) for u in rechte.material_verwaltung_konten()
          if u["email"] and u["id"] != r["created_by"]][:MAX_EMPFAENGER]
    if not an:
        return
    m = meldung_json(r)
    zeilen = [f"{r['created_by_name'] or 'Jemand'} hat ein Produkt gemeldet, das im Katalog fehlt:", "",
              f"Hersteller:     {r['manufacturer']}", f"Modell:         {r['model']}"]
    if r["article_no"]:
        zeilen.append(f"Artikelnummer:  {r['article_no']}")
    if r["norm"]:
        zeilen.append(f"Norm:           {r['norm']}")
    if m["kategorie"]:
        zeilen.append(f"Kategorie:      {m['kategorie']['pfad']} (Vorschlag)")
    if m["ordner"]:
        # Nur die Gliederung: Eine Mail ist schlechter geschützt als die Seite (dort steht der Pfad).
        zeilen.append(f"Für:            {_gliederung(r['folder_id'])}")
    if m["fotos"]:
        zeilen.append(f"Fotos:          {len(m['fotos'])} (in der Meldung)")
    if m["links"]:
        zeilen += ["", "Links:"] + [f"  {x}" for x in m["links"]]
    if r["note"]:
        zeilen += ["", "Bemerkung:", r["note"]]
    zeilen += ["", f"Einpflegen oder ablehnen: {cfg['BASE_URL'].rstrip('/')}/material/katalog/meldungen"]
    betreff = f"{cfg['SITE_NAME']} – Produktmeldung: {r['manufacturer']} {r['model']}"
    HINTERGRUND(_senden, [(a, betreff, "\n".join(zeilen) + "\n", uid, "verwaltung") for a, uid in an], r["id"],
                _gliederung_id(r["folder_id"]))


def _melder_benachrichtigen(r):
    """Bescheid an den Melder – nicht, wenn er seine Meldung selbst erledigt hat."""
    if not r["created_by"] or r["created_by"] == r["resolved_by"]:
        return
    u = db.query("SELECT id, email, name, active FROM users WHERE id = ?", (r["created_by"],), one=True)
    if not u or not u["active"] or not u["email"]:
        return
    cfg = current_app.config
    basis = cfg["BASE_URL"].rstrip("/")
    gemeldet = f"{r['manufacturer']} {r['model']}"
    zeilen = [f"Hallo {u['name'] or u['email']},", ""]
    if r["status"] == "eingepflegt":
        p = katalog.produkt(r["product_id"])
        name = katalog.produktname(p) + (f" ({p['article_no']})" if p["article_no"] else "")
        betreff = f"{cfg['SITE_NAME']} – „{gemeldet}“ ist im Katalog"
        zeilen.append(f"das von dir gemeldete Produkt ist jetzt im Katalog: {name}.")
        if r["answer"]:
            zeilen += ["", f"Anmerkung von {r['resolved_by_name']}:", r["answer"]]
        # Kam die Meldung aus der Nacharbeit eines Bestandsimports, führt der Link dorthin (Phase 2 · L3).
        imp = db.query("SELECT i.folder_id FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id "
                       "WHERE r.request_id = ? LIMIT 1", (r["id"],), one=True)
        if imp:
            zeilen += ["", f"Nacharbeit des Bestandsimports: {basis}/material/ordner/{imp['folder_id']}/import"]
        else:
            ziel = f"{basis}/material/artikel/neu?produkt={r['product_id']}" + (f"&ordner={r['folder_id']}" if r["folder_id"] else "")
            zeilen += ["", f"Artikel anlegen: {ziel}"]
    else:
        betreff = f"{cfg['SITE_NAME']} – Produktmeldung „{gemeldet}“ nicht aufgenommen"
        zeilen += [f"{r['resolved_by_name']} hat deine Meldung „{gemeldet}“ nicht in den Katalog aufgenommen.", "",
                   "Begründung:", r["answer"], "", f"Deine Meldungen: {basis}/material/katalog/meldungen"]
    HINTERGRUND(_senden, [(u["email"], betreff, "\n".join(zeilen) + "\n", u["id"], "melder")], r["id"],
                _gliederung_id(r["folder_id"]))
