"""Vor dem ersten Merge dev → main: was der erste Start mit den Riegenkarten der Produktion tut – nur lesend.

Zwei Listen für die Plattform-Verwaltung (README „Ausbilder nur mit Konto“ – „Vor dem Merge“):
1. Vorschau auf Schritt 34: je Freitext-Ausbilder, ob er mit einem Konto verknüpft wird (mit welchem), mit einer
   vorhandenen Zeile desselben Kontos zusammengelegt wird oder wegfällt (und warum). Dieselbe Regel wie
   app/material/models.py _schritt_34/_namensschluessel_34: aktives Konto mit Stufe in den Riegenkarten (oder
   Plattform-Verwaltung), Name eindeutig (NFKC, Groß/klein und Leerraum egal, „Nachname, Vorname“ wie „Vorname
   Nachname“). Verknüpft über den Namen sieht das Konto danach Teilnehmende, Bewertungen und Medien des Lehrgangs –
   die Liste zeigt deshalb Konto, Name und Gliederung zum Gegenlesen.
2. Wer bewertet hat, ohne mit seinem Konto als Ausbilder im Lehrgang zu stehen (und keine Verwaltung der Riegenkarten
   ist): Diese Konten sehen den Lehrgang nach dem Merge nicht mehr – außer Schritt 34 verknüpft sie (steht dabei).

Nur für die Datenbank der Produktion VOR dem Merge (Stufen 0/1/2, Verwaltung = 2); auf einer schon migrierten
Datenbank (Schemaversion ab 33) rechnet es mit der neuen Skala und sagt das. Ändert nichts, braucht nur Python
(kein sqlite3 auf dem Rechner). Im laufenden Container der Produktion, ohne die Datei dorthin zu kopieren:

    git fetch origin && git show origin/dev:scripts/vor_merge_riegenkarten.py \\
        | docker exec -i stroemis python - /data/stroemis.db

An einer Kopie: python3 -I scripts/vor_merge_riegenkarten.py <kopie>/stroemis.db
Werkzeug aus der zweiten Durchsicht vor dem Merge (01./02.11.2026, Migrationsprüfung V1/V2)."""
import sqlite3
import sys
import unicodedata


def schluessel(text):
    """Vergleichsform eines Namens wie models._namensschluessel_34."""
    t = unicodedata.normalize("NFKC", str(text or ""))
    if t.count(",") == 1:
        nach, vor = t.split(",")
        t = f"{vor} {nach}"
    return " ".join(t.casefold().split())


def tabellen(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def verwaltungsstufe(conn):
    """Vor Schritt 33 (main) ist Verwaltung 2, danach 3."""
    if "mat_meta" in tabellen(conn):
        row = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()
        if row and int(row[0]) >= 33:
            return 3
    return 2


def vorschau(conn, verwaltung):
    """Liefert (zeilen, zaehler, verknuepft) – verknuepft: {(lehrgang, konto)}, die nach Schritt 34 eingetragen sind."""
    konten = {u[0]: u for u in conn.execute(
        "SELECT id, name, gliederung, active, status, recht_pruefungen, recht_verwaltung FROM users")}
    passend = {}
    alle = {}
    for uid, name, _, aktiv, status, rp, rv in konten.values():
        if not (name or "").strip():
            continue
        alle.setdefault(schluessel(name), []).append(uid)
        if aktiv == 1 and status == "active" and ((rp or 0) >= 1 or (rv or 0) >= verwaltung):
            passend.setdefault(schluessel(name), []).append(uid)
    eingetragen = {(lid, uid) for lid, uid in conn.execute(
        "SELECT lehrgang_id, user_id FROM pruef_ausbilder WHERE user_id IS NOT NULL")}
    zeilen, zaehler = [], {"verknüpfen": 0, "zusammenlegen": 0, "ENTFERNEN": 0}
    for lid, titel, name, funktion in conn.execute(
            "SELECT l.id, l.titel, a.name, a.funktion FROM pruef_ausbilder a JOIN pruef_lehrgaenge l "
            "ON l.id = a.lehrgang_id WHERE a.user_id IS NULL ORDER BY a.lehrgang_id, a.sortierung, a.id"):
        wer = f"{name} ({funktion})" if funktion else name
        treffer = passend.get(schluessel(name), [])
        if len(treffer) == 1:
            uid = treffer[0]
            k = konten[uid]
            art = "zusammenlegen" if (lid, uid) in eingetragen else "verknüpfen"
            eingetragen.add((lid, uid))
            zeilen.append(f"{art:<13} Lehrgang {lid} „{titel}“: {wer} → Konto {uid} „{k[1]}“ "
                          f"({k[2] or 'ohne Gliederung'})")
        else:
            art = "ENTFERNEN"
            if treffer:
                grund = "mehrdeutig – Konten " + ", ".join(map(str, treffer))
            elif schluessel(name) in alle:
                grund = "nur Konten ohne Stufe, deaktiviert oder wartend – " + ", ".join(
                    map(str, alle[schluessel(name)]))
            else:
                grund = "kein Konto mit diesem Namen"
            zeilen.append(f"{art:<13} Lehrgang {lid} „{titel}“: {wer} – {grund}")
        zaehler[art] += 1
    return zeilen, zaehler, eingetragen


def bewertende_ohne_eintrag(conn, verwaltung, nach_34):
    zeilen = []
    for lid, titel, status, uid, name, n in conn.execute(
            "SELECT l.id, l.titel, l.status, u.id, u.name, count(*) FROM pruef_versuche v "
            "JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id JOIN pruef_lehrgaenge l ON l.id = t.lehrgang_id "
            "JOIN users u ON u.id = v.geprueft_von "
            "WHERE coalesce(u.recht_pruefungen, 0) < ? AND coalesce(u.recht_verwaltung, 0) < ? "
            "AND NOT EXISTS (SELECT 1 FROM pruef_ausbilder a WHERE a.lehrgang_id = l.id AND a.user_id = u.id) "
            "GROUP BY l.id, u.id ORDER BY l.id, u.id", (verwaltung, verwaltung)):
        folge = "wird über Schritt 34 verknüpft – sieht ihn weiter" if (lid, uid) in nach_34 else "sieht ihn danach NICHT mehr"
        zeilen.append(f"Lehrgang {lid} „{titel}“ ({status or 'ohne Status'}): Konto {uid} „{name}“, "
                      f"{n} Bewertung{'' if n == 1 else 'en'} – {folge}")
    return zeilen


def main(pfad):
    # mode=ro: liest auch die laufende Datenbank samt WAL (als Besitzer der Datei, im Container uid 1000); nichts wird
    # geschrieben. immutable=1 ginge nur an einer ruhenden Kopie – an der laufenden fehlte, was noch im WAL steht.
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        if "pruef_ausbilder" not in tabellen(conn):
            print("Keine Riegenkarten in dieser Datenbank – nichts zu tun.")
            return 0
        verwaltung = verwaltungsstufe(conn)
        if verwaltung == 3:
            print("Hinweis: Diese Datenbank ist schon migriert (Schemaversion ab 33) – gerechnet mit Verwaltung = 3.\n")
        zeilen, zaehler, nach_34 = vorschau(conn, verwaltung)
        vorher = conn.execute("SELECT count(*) FROM pruef_ausbilder").fetchone()[0]
        print("1. Vorschau auf Schritt 34 (Freitext-Ausbilder)")
        print("\n".join(zeilen) if zeilen else "Keine Freitext-Ausbilder – Schritt 34 ändert nichts.")
        print(f"Summe: {zaehler['verknüpfen']} verknüpfen, {zaehler['zusammenlegen']} zusammenlegen, "
              f"{zaehler['ENTFERNEN']} entfernen; pruef_ausbilder {vorher} → "
              f"{vorher - zaehler['zusammenlegen'] - zaehler['ENTFERNEN']} Zeilen")
        print("\n2. Bewertet, aber nicht mit dem Konto als Ausbilder eingetragen")
        ohne = bewertende_ohne_eintrag(conn, verwaltung, nach_34)
        print("\n".join(ohne) if ohne else "Niemand – alle Bewertenden stehen mit ihrem Konto im Lehrgang.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Aufruf: python3 -I scripts/vor_merge_riegenkarten.py <pfad/zu/stroemis.db>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
