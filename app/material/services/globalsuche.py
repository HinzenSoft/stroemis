"""Globale Seriennummernsuche und QR-Steckbrief fremder Artikel (Phase 2 · L1, Abschnitt 3).

Gesucht wird nur nach der exakten Herstellerseriennummer. Angeboten wird die Suche zu jeder Anfrage, die dafür taugt
(suchbar) – auch neben eigenen Treffern, auch wenn ein eigener Artikel genau diese Nummer hat; nur wer ohnehin alles
sieht (Plattform-Verwaltung), bekommt sie nicht. Sie läuft nach Bestätigung, durch die Bremse und ins Protokoll
(globalprotokoll) und findet nur Artikel, die das Konto nicht sieht – die eigenen zeigt die lokale Suche darüber. Ein
Treffer zeigt nur Stammdaten, Zugehörigkeit und ein Sperrwort – genau die Schlüssel in FELDER (Entscheidungen des
Betreibers vom 18.10.2026: Sperrwort ja, Angebot immer, fremde Treffer unter den eigenen).

Oben stehen die Felder, die Normalform und das Angebot (gemeinsamer Unterbau, auch für die lokale Suche), darunter die
Suche selbst (POST /api/material/globalsuche) und der Steckbrief nach einem QR-Scan (POST /api/material/globalsuche/qr);
die Routen stehen in routes_global.py."""
import re

from ... import db
from ..models import MATERIALARTEN
from . import Abgelehnt, bestand, globalprotokoll, katalog, rechte
from .nummern import INVENTAR_VORSATZ, sieht_generiert_aus

# Genau diese Schlüssel hat jeder Treffer (der Test prüft Gleichheit) – keine Kennungen, kein Prüfstatus, keine
# Prüfungen. „sperre“ ist genau ein Wort aus SPERRE oder null (frei).
FELDER = frozenset({"inventory_no", "serial_no", "hersteller", "modell", "artikelnummer", "norm", "materialart",
                    "kategorie", "vorschau", "hergestellt", "lebensende", "gliederung", "ordner", "sperre", "demo"})
MIN_ZEICHEN, MAX_ZEICHEN = 4, 80


def normalform(q):
    """Die Anfrage, wie sie gesucht und protokolliert wird: Leerraum zusammengezogen, außen keiner."""
    return " ".join(str(q or "").split())


def suchbar(q):
    """Taugt die Anfrage für die globale Suche? 4 bis 80 Zeichen und keine vom System vergebene Nummer – Inventar- und
    STR-Nummern sind fortlaufend und ließen sich abzählen."""
    n = normalform(q)
    return (MIN_ZEICHEN <= len(n) <= MAX_ZEICHEN and not sieht_generiert_aus(n)
            and not n.upper().startswith(INVENTAR_VORSATZ))


def sieht_alles():
    """Sieht das Konto jeden Artikel (Plattform-Verwaltung)? Dann gibt es nichts Fremdes – die lokale Suche findet
    alles. Dieselbe Bedingung wie in der Abfrage der Suche (artikel_filter „1“)."""
    return rechte.artikel_filter("i") == "1"


def angebot(q):
    """Soll die Trefferseite (und suche.js) die globale Suche anbieten? Zu jeder Anfrage, die dafür taugt – unabhängig
    von den lokalen Treffern, auch wenn ein eigener Artikel genau diese Seriennummer hat (gesucht wird dann nur bei
    den anderen). Nicht, wer alles sieht."""
    return suchbar(q) and not sieht_alles()


# --- Suche und Steckbrief -----------------------------------------------------------------------------------------

TREFFER_MAX = 10                  # je Suche; ob es mehr gibt, sagt „mehr“ – eine Gesamtzahl gibt es nicht
HINWEIS = "Prüfstatus, Prüfungen und Protokolle sieht nur, wer in der Gliederung eine Freigabe hat."
BESTAETIGEN = "Bitte die globale Suche bestätigen."
BESTAETIGEN_QR = "Bitte den Steckbrief bestätigen."
ZU_KURZ = (f"Mindestens {MIN_ZEICHEN} und höchstens {MAX_ZEICHEN} Zeichen – global wird nur nach der ganzen Seriennummer "
           "gesucht.")
NUR_HERSTELLER = "Global wird nur nach Herstellerseriennummern gesucht."
# Die Plattform-Verwaltung sieht jeden Artikel – für sie gäbe es nichts Fremdes zu finden.
SIEHT_ALLES = "Du siehst den Bestand aller Gliederungen – die normale Suche findet jeden Artikel."
# Was unter einem persönlichen Ordner liegt, heißt im Steckbrief nur so – wem er gehört, geht Fremde nichts an.
PERSOENLICH = "persönlicher Ordner"
# Der Sperrzustand als genau ein Wort – kein Grund, kein Datum, keine Sperre wegen eines Rückrufs; frei ist null.
SPERRE = {"gesperrt": "gesperrt", "ausgesondert": "ausgesondert", "verloren": "verloren gemeldet"}

# Was ein Steckbrief braucht – Artikel mit Heimat (lock_state, folder_id, origin_folder_id) und Produkt; nichts sonst.
_STECKBRIEF_SQL = ("SELECT i.id, i.inventory_no, i.serial_no, i.manufactured_on, i.retire_by, i.lock_state, i.folder_id, "
                   "i.origin_folder_id, p.manufacturer, p.model, p.article_no, p.norm, p.material_kind, p.image, p.demo, "
                   "p.category_id FROM mat_item i JOIN mat_product p ON p.id = i.product_id ")


def _bestaetigt(d, meldung):
    """Ohne ausdrückliches „bestaetigt: true“ läuft nichts – weder Bremse noch Protokoll."""
    if not isinstance(d, dict) or d.get("bestaetigt") is not True:
        raise Abgelehnt(meldung)


def anfrage(q):
    """Die Anfrage geprüft und in Normalform – sonst 400 mit dem Grund. Steuerzeichen gelten als Leerraum (gespeicherte
    Seriennummern haben keine)."""
    n = normalform(re.sub(r"[\x00-\x1f\x7f]", " ", q) if isinstance(q, str) else "")
    if not MIN_ZEICHEN <= len(n) <= MAX_ZEICHEN:
        raise Abgelehnt(ZU_KURZ)
    if not suchbar(n):
        raise Abgelehnt(NUR_HERSTELLER)
    return n


def zugehoerigkeit(fid):
    """(Gliederung, Ordner) zum Ordner fid – der Name der nächsten Gliederung und der Pfad darunter. Systemordner fallen
    weg (ein Ausgesonderter ohne Herkunft gehört nur zur Gliederung: Ordner leer), ab einem persönlichen Ordner steht nur
    noch PERSOENLICH."""
    kette = bestand.pfad(fid)
    oben = max((n for n, o in enumerate(kette) if o["kind"] == "gliederung" and not o["system_kind"]), default=-1)
    namen = []
    for o in kette[oben + 1:]:
        if o["system_kind"]:
            continue
        if o["kind"] == "persoenlich":
            namen.append(PERSOENLICH)
            break
        namen.append(o["name"])
    return (kette[oben]["name"] if oben >= 0 else ""), " / ".join(namen)


def steckbrief(i, kategorien=None):
    """Ein Treffer: genau die Schlüssel aus FELDER. Die Zugehörigkeit kommt aus der Heimat – Gesperrte und
    Ausgesonderte stehen unter ihrem Herkunftsordner; den Sperrzustand sagt nur das eine Wort in „sperre“.
    kategorien: Zwischenspeicher Kategorie → Pfadtext für mehrere Treffer."""
    kategorien = {} if kategorien is None else kategorien
    if i["category_id"] not in kategorien:
        kategorien[i["category_id"]] = " / ".join(k["name"] for k in katalog.kategorie_pfad(i["category_id"]))
    gliederung, ordner = zugehoerigkeit(bestand.heimat(i))
    out = {"inventory_no": i["inventory_no"], "serial_no": i["serial_no"], "hersteller": i["manufacturer"],
           "modell": i["model"], "artikelnummer": i["article_no"] or "", "norm": i["norm"] or "",
           "materialart": MATERIALARTEN.get(i["material_kind"], i["material_kind"]),
           "kategorie": kategorien[i["category_id"]], "vorschau": katalog.bild_url(i["image"], "thumb"),
           "hergestellt": i["manufactured_on"] or None,
           # Das Lebensende folgt aus Herstelldatum und Katalog – nur bei textilem Material.
           "lebensende": (i["retire_by"] or None) if i["material_kind"] == "textil" else None,
           "gliederung": gliederung, "ordner": ordner, "sperre": SPERRE.get(i["lock_state"]),
           "demo": bool(i["demo"])}
    return out


def suchen(d, uid):
    """Die globale Suche nach einer Herstellerseriennummer: bestätigt, 4 bis 80 Zeichen, keine vergebene Nummer, nicht
    für den, der alles sieht (409), dann durch die Bremse (429). Exakt (ohne Groß/klein) und nur unter den Artikeln,
    die das Konto nicht sieht – die eigenen zeigt die lokale Suche; die Bedingung steht in der Abfrage, damit LIMIT
    und „mehr“ nur Fremde zählen. Höchstens TREFFER_MAX Treffer – „mehr“ sagt, ob es weitere gibt. Jede Suche steht
    im Protokoll, mit genau den gezeigten Treffern, auch eine ohne Treffer."""
    _bestaetigt(d, BESTAETIGEN)
    n = anfrage(d.get("q"))
    if sieht_alles():
        raise Abgelehnt(SIEHT_ALLES, 409)
    globalprotokoll.bremse(uid)
    # Nicht sichtbar heißt: der Filter ist nicht wahr. COALESCE, weil er bei fehlender Herkunft NULL ergibt (NULL IN …)
    # – ohne fiele ein Ausgesonderter ohne Herkunft aus beiden Mengen und wäre nirgends zu finden.
    rows = db.query(_STECKBRIEF_SQL + "WHERE i.serial_generated = 0 AND i.serial_no = ? COLLATE NOCASE "
                    f"AND NOT COALESCE(({rechte.artikel_filter('i')}), 0) ORDER BY i.id LIMIT ?", (n, TREFFER_MAX + 1))
    treffer = rows[:TREFFER_MAX]
    globalprotokoll.eintragen("suche", n, [r["id"] for r in treffer])
    kategorien = {}
    return {"treffer": [steckbrief(r, kategorien) for r in treffer], "mehr": len(rows) > TREFFER_MAX,
            "hinweis": HINWEIS}


def steckbrief_qr(d, uid):
    """Der Steckbrief nach einem QR-Scan an einem fremden Artikel (Seite „fremd“): bestätigt, Token bekannt (sonst 404
    wie „gibt es nicht“). Ist der Artikel inzwischen sichtbar, geht es zu ihm („weiter“) – ohne Bremse und Protokoll.
    Sonst Bremse und Protokoll (Art „qr“, Anfrage ist die Inventarnummer) und derselbe Steckbrief wie bei der Suche."""
    _bestaetigt(d, BESTAETIGEN_QR)
    token = d.get("token")
    i = db.query(_STECKBRIEF_SQL + "WHERE i.qr_token = ?", (token,), one=True) if isinstance(token, str) and token else None
    if not i:
        raise Abgelehnt(rechte.ARTIKEL_FEHLT, 404)
    if rechte.darf_artikel("lesen", i):
        return {"weiter": f"/material/artikel/{i['id']}"}
    globalprotokoll.bremse(uid)
    globalprotokoll.eintragen("qr", i["inventory_no"], [i["id"]])
    return {"treffer": [steckbrief(i)], "mehr": False, "hinweis": HINWEIS}
