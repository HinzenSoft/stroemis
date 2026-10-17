"""Übersicht des Moduls: Fälligkeiten je Ordner und der Hinweis, der nach einem QR-Scan sofort steht.

Die Zahlen sind dieselben wie in der Ordnerleiste und im Bestand – bestand.baum() zählt mit status_sql je
Artikel und rechnet auf alle Vorfahren hoch. Eine zweite Zählung gibt es hier nicht; dazu kommt nur die
Form der Tabelle:

  - Zeilen sind die Ordner in Baumreihenfolge, Gliederungen oben, Unterordner darunter eingerückt (tiefe).
    Die Systemordner „Gesperrt“ und „Ausgesondert“ sind keine eigenen Zeilen: Ihr Inhalt zählt bei ihrer
    Gliederung, denn dort liegt er. Ein gesperrter Artikel zählt also nicht mehr in seinem Herkunftsordner,
    sondern in der Gliederung – genau wie in der Ordnerleiste.
  - Eine Gliederung innerhalb einer Gliederung ist eine eingerückte Zeile ihres Oberordners. Die Summe der
    obersten Zeilen ist der Gesamtbestand; nichts zählt doppelt.
  - „Nächste Fälligkeit“ ist das früheste next_due_on im Zweig unter den Artikeln, deren Status an diesem
    Datum hängt (einsatzbereit, bald fällig, überfällig). Neue warten auf die Eingangsprüfung (ihr Datum ist
    nur ein Vorschlag), gesperrte auf die Freiprüfung, Artikel am Lebensende auf die Aussonderung, und
    ausgesonderte werden nie mehr geprüft – sie alle stehen in ihren eigenen Spalten.
"""
from ... import db
from . import bestand
from . import status as st

NACH_DATUM = ("einsatzbereit", "bald_faellig", "ueberfaellig")


def _frueheste(eltern):
    """Frühestes next_due_on je Ordner, über den ganzen Unterbaum (eltern: Ordner → Oberordner)."""
    params = dict(st.parameter(), **{f"s{k}": s for k, s in enumerate(NACH_DATUM)})
    marken = ",".join(f":s{k}" for k in range(len(NACH_DATUM)))
    gesamt = {}
    for r in db.query(f"SELECT i.folder_id, MIN(i.next_due_on) AS tag FROM mat_item i WHERE i.next_due_on IS NOT NULL "
                      f"AND {st.status_sql('i')} IN ({marken}) GROUP BY i.folder_id", params):
        p, gesehen = r["folder_id"], set()
        while p and p not in gesehen:
            gesehen.add(p)
            if gesamt.get(p) is None or r["tag"] < gesamt[p]:
                gesamt[p] = r["tag"]
            p = eltern.get(p)
    return gesamt


def ordner_uebersicht(alle=None):
    """Fälligkeiten je Ordner für die Übersicht (/start): eine Zeile je Ordner außer den Systemordnern, in
    Baumreihenfolge, mit Bestand und Zählung des ganzen Zweigs und der nächsten Fälligkeit. alle: das
    Ergebnis von bestand.baum(), wenn der Aufrufer es schon hat."""
    alle = bestand.baum() if alle is None else alle
    eltern = {o["id"]: o["parent_id"] for o in alle}
    frueh = _frueheste(eltern)
    kinder = {}
    for o in alle:                                   # baum() liefert schon nach Position und Name sortiert
        if not o["system_kind"]:
            kinder.setdefault(o["parent_id"], []).append(o)
    zeilen, gesehen = [], set()
    stapel = [(o, 0) for o in reversed(kinder.get(None, []))]
    while stapel:
        o, tiefe = stapel.pop()
        if o["id"] in gesehen:
            continue
        gesehen.add(o["id"])
        tag = frueh.get(o["id"])
        zeilen.append({"id": o["id"], "parent_id": o["parent_id"], "name": o["name"], "kind": o["kind"],
                       "demo": o["demo"], "tiefe": tiefe, "unterordner": len(kinder.get(o["id"], [])),
                       "bestand": o["bestand"], "zaehlung": o["zaehlung"], "naechste": tag,
                       # Wie dringend das Datum ist – nach derselben Regel wie der Status eines Artikels.
                       "naechste_status": st.status({"lock_state": "frei", "retire_by": None, "last_inspected_on": tag,
                                                     "next_due_on": tag}) if tag else None})
        stapel.extend((k, tiefe + 1) for k in reversed(kinder.get(o["id"], [])))
    return zeilen


# Was die Artikelseite schon im HTML zeigt, bevor material.js zeichnet – nach einem QR-Scan das Erste, was
# man sieht. Die Texte sind die der Banner in material.js.
WARNUNG = {
    "ausgesondert": "AUSGESONDERT – {nr} ist außer Dienst und darf nicht mehr verwendet werden.",
    "gesperrt": "GESPERRT{grund} – {nr} nicht verwenden, bis eine Freiprüfung ihn freigibt.",
    "lebensdauer": "LEBENSDAUER ERREICHT – {nr} nicht mehr verwenden, aussondern.",
}


def warnung(iid):
    """Hinweis für die Seite eines ausgesonderten, gesperrten oder abgelaufenen Artikels – sonst None."""
    i = db.query("SELECT * FROM mat_item WHERE id = ?", (iid,), one=True)
    if not i:
        return None
    s = st.status(i)
    if s not in WARNUNG:
        return None
    grund = f" ({i['lock_reason']})" if s == "gesperrt" and i["lock_reason"] else ""
    return {"status": s, "text": WARNUNG[s].format(nr=i["inventory_no"], grund=grund)}
