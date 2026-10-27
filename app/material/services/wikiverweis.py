"""Prüfanleitung aus dem Wiki (Phase 2 · Lieferung 3): eine Wiki-Seite je Formularversion (mat_form.wiki_page_id).

In offenen Prüfungen blendet die Oberfläche den Abschnitt „Prüfung“ der verknüpften Seite ein – geholt vom Browser über
die Endpunkte des Wikis selbst (GET /api/wiki/pages/<slug>?leise=1 bzw. /api/public/pages/<slug>), mit deren Rechten;
hier gibt es keinen Markdown- oder HTML-Parser und keine eigene Route für den Inhalt. Jeder sieht nur, was er im Wiki
lesen darf (darf_lesen – dieselbe Regel wie die beiden Endpunkte); ohne Leserecht nie den Titel. Titel und Slug gehen nur
an Konten, für die darf_lesen gilt; das Journal nennt nur die Seitennummer.

Verknüpfen darf, wer Stufe Verwaltung in der Materialablage hat (Material-Verwaltung, die Plattform-Verwaltung zählt mit)
UND mindestens Stufe Mitglied im Wiki (Entscheidung vom 19.10.2026; die Plattform-Verwaltung hat im Wiki ohnehin
Verwaltung) – auch an benutzten Formularen: Die Verknüpfung ist Hilfe zum Prüfen, kein Prüfinhalt, und steht in keinem
Protokoll. Geschrieben wird genau diese eine Spalte.

Die Wiki-Funktionen (api_wiki.can_read, is_public, restricted_ids) und auth.nutzt werden in den Funktionen eingebunden –
keine Ringabhängigkeit beim Start."""
from urllib.parse import quote

from flask import has_request_context

from ... import db
from . import Abgelehnt, journal, katalog, kennung

FEHLT = "Seite der Strömipedia nicht gefunden."          # nicht vorhanden, im Papierkorb und nicht lesbar antworten gleich
NUR_MIT_WIKI = ("Prüfanleitungen verknüpft, wer in der Materialablage die Stufe „Verwaltung“ und in der Strömipedia "
                "mindestens die Stufe „Mitglied“ hat – dir fehlt die Stufe in der Strömipedia (Leitstelle).")
TREFFER_MAX = 30


def _user(user=None):
    if user is not None:
        return user
    if not has_request_context():
        return None
    from ...auth import current_user
    return current_user()


def darf_verknuepfen(user=None):
    """Material-Verwaltung UND Stufe Mitglied im Wiki (auth.nutzt – die Plattform-Verwaltung hat sie überall)."""
    from ...auth import nutzt
    from .rechte import ist_material_verwaltung
    user = _user(user)
    return bool(user and ist_material_verwaltung(user) and nutzt("wiki", user))


def seite(page_id):
    """Die Zeile aus wiki_pages (auch im Papierkorb) oder None."""
    if not page_id:
        return None
    return db.query("SELECT * FROM wiki_pages WHERE id = ?", (page_id,), one=True)


def darf_lesen(page, user=None):
    """Genau die Regel des Wikis: keine Seite oder im Papierkorb – nein; mit Wiki-Stufe api_wiki.can_read (Beschränkung
    samt Vererbung, Ersteller, Freigegebene, Wiki-Verwaltung); ohne Wiki-Stufe (Lesemodus) nur, was der öffentliche Teil
    zeigt (api_wiki.is_public – eine beschränkte Seite ist nie öffentlich)."""
    from ...api_wiki import can_read, is_public
    from ...auth import nutzt
    user = _user(user)
    if not page or page.get("deleted_at") or not user:
        return False
    if nutzt("wiki", user):
        return can_read(page, user)
    return is_public(page)


def reichweite(page):
    """„beschraenkt“ (lesebeschränkt, auch über einen Abschnitt darüber), „oeffentlich“ oder „intern“ – für den Hinweis
    im Editor der Material-Verwaltung."""
    from ...api_wiki import is_public, restricted_ids
    if restricted_ids(page)[1]:
        return "beschraenkt"
    return "oeffentlich" if is_public(page) else "intern"


def _like(t):
    return "%" + t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def seiten(q, user=None):
    """Seitenwahl für die Verknüpfung: Titelsuche (jedes Wort muss im Titel stehen, höchstens sechs), ohne Papierkorb
    und Vorlagen, nur lesbare Seiten, höchstens TREFFER_MAX; ohne q (oder kürzer als 2 Zeichen) die zuletzt geänderten.
    lesemodus: das Konto hat keine Wiki-Stufe (seit der Entscheidung vom 19.10.2026 kommt es hier nicht mehr an – die
    Route verlangt die Stufe)."""
    from ...auth import nutzt
    user = _user(user)
    q = " ".join((q or "").split())
    worte = q.split(" ")[:6] if len(q) >= 2 else []
    bedingung = " AND ".join(["title LIKE ? ESCAPE '\\'"] * len(worte)) or "1"
    rows = db.query(f"SELECT * FROM wiki_pages WHERE deleted_at IS NULL AND is_template = 0 AND {bedingung} "
                    f"ORDER BY updated_at DESC, title COLLATE NOCASE LIMIT 500", [_like(w) for w in worte])
    out = []
    for p in rows:
        if darf_lesen(p, user):
            out.append({"id": p["id"], "titel": p["title"], "icon": p.get("icon") or "", "reichweite": reichweite(p)})
            if len(out) >= TREFFER_MAX:
                break
    return {"seiten": out, "lesemodus": not nutzt("wiki", user)}


def editor_json(page_id, user=None):
    """Die Verknüpfung, wie die Material-Verwaltung sie am Formular sieht: {seite, titel, url, reichweite, zustand} –
    Titel, Adresse der Seite im Wiki (für den Link in der Formularansicht, Bauentwurf 4.4) und Reichweite nur bei „ok“;
    „papierkorb“ (die Seite liegt im Wiki-Papierkorb) oder „kein_zugang“ (dieses Konto darf sie nicht lesen). None, wenn
    nichts verknüpft ist."""
    if not page_id:
        return None
    p = seite(page_id)
    if p and p.get("deleted_at"):
        return {"seite": page_id, "titel": None, "url": None, "reichweite": None, "zustand": "papierkorb"}
    if not darf_lesen(p, user):
        return {"seite": page_id, "titel": None, "url": None, "reichweite": None, "zustand": "kein_zugang"}
    return {"seite": page_id, "titel": p["title"], "url": f"/stroemipedia/{quote(p['slug'], safe='')}",
            "reichweite": reichweite(p), "zustand": "ok"}


def setzen(fid, d):
    """PUT …/formulare/<fid>/wiki mit {"seite": id | null}. null entfernt die Verknüpfung. Die Seite muss für das
    speichernde Konto lesbar sein – sonst 404 FEHLT (gleich für „gibt es nicht“, „Papierkorb“, „darfst du nicht lesen“).
    Unverändert wird ohne Leseprüfung angenommen und nicht ins Journal geschrieben. Auch an benutzten Formularen;
    geschrieben wird genau diese eine Spalte (kein updated_at), mit dem Journal in einer Transaktion – dort nur die
    Seitennummer, nie der Titel."""
    if not isinstance(d, dict) or "seite" not in d:
        raise Abgelehnt("„seite“ fehlt (Kennung der Seite in der Strömipedia oder null).")
    neu = kennung(d.get("seite"), "Seite der Strömipedia", leer_erlaubt=True)
    with db.transaction(sofort=True):
        f = katalog.formular(fid)
        alt = f.get("wiki_page_id")
        if neu == alt:
            return
        if neu is not None and not darf_lesen(seite(neu)):
            raise Abgelehnt(FEHLT, 404)
        db.execute("UPDATE mat_form SET wiki_page_id = ? WHERE id = ?", (neu, fid))
        journal.eintragen("form", fid, "wiki", {"seite": alt}, {"seite": neu})


def anleitung(form_id, user=None):
    """Für pruefung_json (nur Entwürfe): None (nichts verknüpft, Seite im Papierkorb), {"kein_zugang": true} (für dieses
    Konto nicht lesbar – ohne Titel) oder {"titel", "url", "quelle"}: url öffnet die Seite im Wiki (ohne Wiki-Stufe im
    Lesemodus), quelle ist der Endpunkt, über den der Browser den Inhalt holt – mit Wiki-Stufe /api/wiki/pages/<slug>
    mit leise=1 (kein Besuch der Seite), sonst der öffentliche."""
    from ...auth import nutzt
    if not form_id:
        return None
    f = db.query("SELECT wiki_page_id FROM mat_form WHERE id = ?", (form_id,), one=True)
    p = seite(f["wiki_page_id"]) if f else None
    if not p or p.get("deleted_at"):
        return None
    user = _user(user)
    if not darf_lesen(p, user):
        return {"kein_zugang": True}
    slug = quote(p["slug"], safe="")
    quelle = f"/api/wiki/pages/{slug}?leise=1" if nutzt("wiki", user) else f"/api/public/pages/{slug}"
    return {"titel": p["title"], "url": f"/stroemipedia/{slug}", "quelle": quelle}
