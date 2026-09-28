"""Beispieldaten für den Prüfungsbereich: ein SR1- und ein SR2-Lehrgang mit erfundenen Personen.

Gedacht zum Ausprobieren und Vorführen – die Namen sind frei erfunden, die Voraussetzungen und
Prüfungsleistungen orientieren sich an der Prüfungsordnung Strömungsrettung und an der Checkliste
„Beurteilung Strömungsretter 2“. Angelegt wird über die Nutzerverwaltung (Knopf in der
Lehrgangsliste, nur Administration) oder von der Kommandozeile:

    DATA_DIR=./data python -m app.beispieldaten

Alles läuft über dieselben Tabellen und Regeln wie die Oberfläche; der aufrufende Nutzer steht als
Lehrgangsleitung und als Prüfer in den Daten."""
from . import db

SR1_VORAUSSETZUNGEN = [
    "Mindestalter 16 Jahre zu Beginn der Veranstaltung",
    "Mitgliedschaft in der DLRG",
    "Ärztliche Tauglichkeitsuntersuchung oder Selbsterklärung zum Gesundheitszustand",
    "Erfolgreiche Teilnahme am Coopertest (Prüfung zu Lehrgangsbeginn)",
    "Deutsches Rettungsschwimmabzeichen Silber (152), nicht älter als 2 Jahre",
    "Sanitätsausbildung A (331), nicht älter als 4 Jahre",
    "Basisausbildung Einsatzdienste (401)",
    "Modul Umgang mit Rettungsgeräten und Überwachung von Wasserflächen (402)",
    "Modul Schwimmen in fließenden Gewässern (403)",
    "400 m Schwimmen in 8 Minuten",
    "Einverständniserklärung bei minderjährigen Teilnehmenden",
    "Abschlusstest Theoriemodul",
    "Selbsterklärung zur persönlichen Schutzausrüstung",
    "Knoten aus der 401-Basisausbildung in unter 15 Sekunden",
]

SR1_LEISTUNGEN = [
    ("Wurfsackwurf auf Ziel", "# Ablauf\n\nDrei Würfe auf eine Person im Kehrwasser in 12 m Entfernung. "
     "Der Sack muss die Person erreichen; nach jedem Wurf wird der Sack **treibend** wieder gepackt.\n\n"
     "## Kriterien\n\n- mindestens zwei Treffer\n- sicherer Stand, Seil nie um die Hand gewickelt\n- Einholen mit Körpereinsatz", 90),
    ("Standardknoten (Achter, Palstek, Prusik, Halbmastwurf)", "Alle vier Knoten hintereinander, jeder in unter 15 Sekunden, "
     "ohne Nachbessern. Der Knoten muss **ansprechbar** sein: sauber gelegt, Sicherung gesetzt.", 60),
    ("Defensives Schwimmen", "Rückenlage, Füße voraus, Blick stromab. Sicherer Ausstieg im Kehrwasser ohne Aufstehen in der Strömung.", None),
    ("Aggressives Schwimmen mit Kehrwasserwechsel", "Bauchlage, kräftiger Kraul, Kehrwasserlinie im spitzen Winkel kreuzen, "
     "Ausstieg im Kehrwasser gegenüber. Zwei Wechsel hintereinander.", None),
    ("Rettung einer Person mit dem Wurfsack", "Person treibt an; Ansprache, Wurf, Seilführung ins Kehrwasser, "
     "Landung an der Böschung. Die Zeit läuft vom Ruf „Person im Wasser“ bis zur Landung.", 120),
    ("Zugseil mit Umlenkung spannen", "Ankerpunkte wählen, Seil über den Fluss bringen, Flaschenzug 3:1 aufbauen, "
     "Spannung prüfen, Rückbau. Zeit inklusive Materialkontrolle.", 300),
    ("Selbstrettung nach Kenterung", "Bewusstes Kentern aus dem Raft, Orientierung, defensive Lage, Ausstieg.", None),
    ("Eigensicherung und Ausrüstungscheck", "Weste, Helm, Messer, Pfeife, Wurfsack: vollständig und funktionsfähig, "
     "Partnercheck durchgeführt. Wird zu Beginn jeder Prüfung wiederholt.", None),
    ("Theorie: Gefahren am fließenden Gewässer", "Mündliche Prüfung zu Walzen, Siphons, Strainern, Wehren und "
     "Rettungsgrundsätzen (Reach – Throw – Row – Go).", None),
]

SR2_VORAUSSETZUNGEN = [
    "Formale Voraussetzungen gem. PO",
    "Fitness-Test (mind. 2100 m in 12 Minuten)",
    "Nachweis 400 m Schwimmen",
    "Selbsterklärung zum Gesundheitszustand",
    "Selbsterklärung zur PSA",
]

SR2_LEISTUNGEN = [
    ("Beherrschen der Standardknoten für SR", "Alle Standardknoten der Strömungsrettung sicher und schnell, "
     "inklusive Prusik und Halbmastwurf mit Sicherung.", 90),
    ("Beherrschen der Anker", "Ringanker, Bandschlingenanker, Kräfteausgleich. Anker werden auf Lastrichtung und "
     "Redundanz geprüft.", None),
    ("Standardverfahren Flachseilbrücke", "Aufbau mit Spannsystem, Lastprobe, Übergang einer Person, Rückbau. "
     "Zeit ab Kommando bis zur ersten Lastprobe.", 600),
    ("Standardverfahren Schräghangrettung", "Zugang zur verletzten Person, Lagerung, Rückführung mit Seilsicherung.", None),
    ("Standardverfahren Abseilen", "Abseilen über eine Kante mit Hintersicherung; Kommandos und Umbau am Stand.", None),
    ("Notverfahren", "Blockierter Abseilvorgang lösen, Lastübernahme, Selbstrettung aus dem System.", 240),
    ("Führungsverhalten (Fachtechnisch)", "Leitet einen seiltechnischen Aufbau: klare Kommandos, Sicherheitschecks, "
     "Zuordnung der Aufgaben.", None),
    ("Sicherheitsbewusstsein (Gefährdungsbeurteilung, Schaffen von Sicherheit, Eigensicherung)",
     "Gefährdungsbeurteilung vor jedem Aufbau, Absicherung der Kante, Eigensicherung ohne Aufforderung.", None),
    ("Teamfähigkeit (Seiltechnik)", "Arbeitet im Team, übernimmt Aufgaben, gibt Rückmeldung.", None),
    ("Wurfsack", "Wurfsackwurf auf Ziel und Wurfsackrettung wie im SR1 – als Wiederholungsprüfung.", 90),
    ("Springersperre", "Aufbau und Betrieb einer Springersperre mit zwei Springern, Kommandos, Rettung einer Person.", None),
    ("Grundlagen Raft", "Paddelkommandos, Trimm, Fähre queren, Ein- und Aussteigen in Strömung.", None),
    ("Raftfähre", "Aufbau einer Raftfähre am Zugseil, Übersetzen von Personen, Rückbau.", 900),
    ("Einsätze bei Nacht", "Orientierung, Lichtdisziplin, Kommunikation und Rettung im Dunkeln.", None),
    ("Rettungstechniken im/am strömenden Gewässer", "Kontaktrettung, Rettung mit Rettungsboje und Leine, Rettung aus "
     "der Walze mit Seilsicherung.", None),
    ("Führungsverhalten (Wasser)", "Leitet einen Wassereinsatz: Lagebild, Zuordnung, Sicherung stromab.", None),
    ("Teamfähigkeit (Wasser)", "Arbeitet im Wasserteam zuverlässig zusammen, Rückmeldungen, gegenseitige Sicherung.", None),
]

# Erfundene Personen: (Vorname, Name, Geburtsdatum, Gliederung)
SR1_TEILNEHMENDE = [
    ("Anna", "Beispiel", "2002-10-03", "OG Musterstadt"),
    ("Bert", "Muster", "2004-05-06", "OG Musterstadt"),
    ("Clara", "Probe", "2005-01-15", "OG Beispielhausen"),
    ("Dario", "Test", "2009-01-27", "OG Beispielhausen"),
    ("Emil", "Fiktiv", "2001-07-07", "OG Flussdorf"),
    ("Frida", "Erdacht", "2003-03-30", "OG Flussdorf"),
    ("Gero", "Phantasie", "1998-11-11", "OG Musterstadt"),
    ("Hanna", "Vorlage", "2006-12-20", "OG Wehrbach"),
]
SR2_TEILNEHMENDE = [
    ("Ida", "Muster", "1999-02-02", "OG Musterstadt"),
    ("Jonas", "Beispiel", "1995-06-16", "OG Beispielhausen"),
    ("Kira", "Probe", "2000-09-09", "OG Flussdorf"),
    ("Lars", "Fiktiv", "1992-04-04", "OG Wehrbach"),
    ("Mira", "Erdacht", "1997-08-21", "OG Musterstadt"),
    ("Nils", "Vorlage", "2001-01-30", "OG Beispielhausen"),
]


def _titel_frei(titel):
    """Mehrfaches Anlegen bekommt eine Nummer im Titel – so bleibt erkennbar, was Beispiel ist."""
    n = db.query("SELECT COUNT(*) AS n FROM pruef_lehrgaenge WHERE titel = ? OR titel LIKE ?",
                 (titel, titel + " (%"), one=True)["n"]
    return titel if not n else f"{titel} ({n + 1})"


def _lehrgang(uid, name, titel, nummer, von, bis, ort, status, beschreibung, ts):
    lid = db.execute(
        "INSERT INTO pruef_lehrgaenge (titel, nummer, datum_von, datum_bis, ort, beschreibung, status, "
        "created_by, created_by_name, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (_titel_frei(titel), nummer, von, bis, ort, beschreibung, status, uid, name, ts, ts))
    db.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, sortierung) VALUES (?,?,?,?,0)",
               (lid, uid, name, "Lehrgangsleitung"))
    db.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, sortierung) VALUES (?,NULL,?,?,1)",
               (lid, "Renate Referierend (extern)", "Referierende:r"))
    return lid


def _voraussetzungen(lid, liste):
    return [db.execute("INSERT INTO pruef_voraussetzungen (lehrgang_id, bezeichnung, sortierung) VALUES (?,?,?)",
                       (lid, bez, i)) for i, bez in enumerate(liste)]


def _leistungen(lid, liste):
    return [db.execute("INSERT INTO pruef_leistungen (lehrgang_id, bezeichnung, beschreibung_md, zeitansatz_sekunden, "
                       "sortierung) VALUES (?,?,?,?,?)", (lid, bez, md, zeit, i)) for i, (bez, md, zeit) in enumerate(liste)]


def _teilnehmende(lid, liste, ts):
    return [db.execute("INSERT INTO pruef_teilnehmer (lehrgang_id, name, vorname, geburtsdatum, gliederung, email, "
                       "bemerkung, extra, sortierung, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (lid, name, vorname, geb, glied, "", "", "{}", i, ts))
            for i, (vorname, name, geb, glied) in enumerate(liste)]


def _haken(tid, vid, uid, name, ts, quelle="manuell"):
    db.execute("INSERT INTO pruef_voraussetzung_status (teilnehmer_id, voraussetzung_id, erfuellt, gesetzt_von, "
               "gesetzt_von_name, gesetzt_am, quelle) VALUES (?,?,1,?,?,?,?)", (tid, vid, uid, name, ts, quelle))
    db.execute("INSERT INTO pruef_voraussetzung_verlauf (teilnehmer_id, voraussetzung_id, erfuellt, user_id, user_name, "
               "zeit, quelle) VALUES (?,?,1,?,?,?,?)", (tid, vid, uid, name, ts, quelle))


def _versuch(tid, lid, nr, ergebnis, zeit, kommentar, uid, name, ts):
    return db.execute(
        "INSERT INTO pruef_versuche (teilnehmer_id, leistung_id, versuch_nr, ist_nachpruefung, ergebnis, zeit_sekunden, "
        "kommentar, geprueft_von, geprueft_von_name, geprueft_am) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tid, lid, nr, 1 if nr > 1 else 0, ergebnis, zeit, kommentar, uid, name, ts))


def anlegen(uid, name):
    """Beide Lehrgänge anlegen; liefert die Kennungen. Muss in einer Transaktion des Aufrufers laufen."""
    ts = db.now()
    tag = ts[:10]

    # --- SR1: läuft gerade, ein Teil ist geprüft ---------------------------------------------
    sr1 = _lehrgang(uid, name, "Strömungsretter 1 (SR1)", "2026-0008", "2026-12-04", "2026-12-13",
                    "Rheinisch-Bergischer Kreis", "laufend",
                    "Beispiel-Lehrgang mit erfundenen Personen. Alle Bewertungen und Kommentare sind ausgedacht.", ts)
    v1 = _voraussetzungen(sr1, SR1_VORAUSSETZUNGEN)
    l1 = _leistungen(sr1, SR1_LEISTUNGEN)
    t1 = _teilnehmende(sr1, SR1_TEILNEHMENDE, ts)
    # Voraussetzungen: die ersten drei Personen vollständig, die übrigen mit Lücken.
    for i, tid in enumerate(t1):
        for j, vid in enumerate(v1):
            if i < 3 or (i + j) % 3:
                _haken(tid, vid, uid, name, ts, "import" if j < 6 else "manuell")
    # Bewertungen: Wurfsack, Knoten, Defensiv, Aggressiv für die ersten sechs; Fehler mit Kommentar.
    wurf, knoten, defensiv, aggressiv, rettung = l1[0], l1[1], l1[2], l1[3], l1[4]
    _versuch(t1[0], wurf, 1, "bestanden", 71, "Drei Treffer, ruhiger Stand.", uid, name, ts)
    _versuch(t1[0], knoten, 1, "bestanden", 48, "", uid, name, ts)
    _versuch(t1[0], defensiv, 1, "bestanden", None, "", uid, name, ts)
    _versuch(t1[0], aggressiv, 1, "bestanden", None, "Sauberer Kehrwasserwechsel.", uid, name, ts)
    _versuch(t1[0], rettung, 1, "bestanden", 98, "", uid, name, ts)
    _versuch(t1[1], wurf, 1, "mangelhaft", 105, "Zwei Fehlwürfe: Sack zu früh losgelassen, Blick nicht am Ziel.", uid, name, ts)
    _versuch(t1[1], wurf, 2, "bestanden", 82, "Nachprüfung: drei Treffer, Blick jetzt am Ziel.", uid, name, ts)
    _versuch(t1[1], knoten, 1, "bestanden", 55, "", uid, name, ts)
    _versuch(t1[1], defensiv, 1, "bestanden", None, "", uid, name, ts)
    _versuch(t1[2], wurf, 1, "bestanden", 66, "", uid, name, ts)
    _versuch(t1[2], knoten, 1, "mangelhaft", 75, "Prusik zweimal falsch gelegt, Halbmastwurf ohne Sicherung.", uid, name, ts)
    _versuch(t1[2], defensiv, 1, "bestanden", None, "", uid, name, ts)
    _versuch(t1[3], wurf, 1, "mangelhaft", 110, "Seil um die Hand gewickelt – Sicherheitsfehler, Abbruch.", uid, name, ts)
    _versuch(t1[3], defensiv, 1, "bestanden", None, "", uid, name, ts)
    _versuch(t1[4], wurf, 1, "bestanden", 79, "", uid, name, ts)
    _versuch(t1[4], knoten, 1, "bestanden", 52, "", uid, name, ts)
    _versuch(t1[4], aggressiv, 1, "mangelhaft", None, "Kehrwasserlinie zu flach angeschwommen, abgetrieben.", uid, name, ts)
    _versuch(t1[4], aggressiv, 2, "mangelhaft", None, "Erneut zu flach; Übung mit Referierenden vereinbart.", uid, name, ts)
    _versuch(t1[5], wurf, 1, "bestanden", 88, "", uid, name, ts)
    # Kommentare und ein Ergebnis: Anna hat alles bestanden, was bisher geprüft wurde.
    db.execute("UPDATE pruef_teilnehmer SET kommentar = ? WHERE id = ?",
               ("Sehr sicher im Wasser, übernimmt Verantwortung im Team.", t1[0]))
    db.execute("UPDATE pruef_teilnehmer SET kommentar = ? WHERE id = ?",
               ("Nach der Nachprüfung deutlich ruhiger. Knoten üben.", t1[1]))
    db.execute("UPDATE pruef_teilnehmer SET ergebnis = 'bestanden', ergebnis_von = ?, ergebnis_von_name = ?, "
               "ergebnis_am = ? WHERE id = ?", (uid, name, ts, t1[0]))

    # --- SR2: abgeschlossen, nach der Checkliste „Beurteilung Strömungsretter 2“ ---------------
    sr2 = _lehrgang(uid, name, "Strömungsretter 2 (SR2)", "2025-0031", "2025-06-13", "2025-06-15",
                    "Wupper, Beyenburg", "abgeschlossen",
                    "Beispiel-Lehrgang nach der Checkliste „Beurteilung Strömungsretter 2“ – erfundene Personen.", ts)
    v2 = _voraussetzungen(sr2, SR2_VORAUSSETZUNGEN)
    l2 = _leistungen(sr2, SR2_LEISTUNGEN)
    t2 = _teilnehmende(sr2, SR2_TEILNEHMENDE, ts)
    for i, tid in enumerate(t2):
        for j, vid in enumerate(v2):
            if i != 5 or j < 3:
                _haken(tid, vid, uid, name, ts)
    # Vier Personen vollständig bestanden, eine mit Nachprüfung, eine nicht bestanden.
    for i, tid in enumerate(t2[:4]):
        for j, lid in enumerate(l2):
            zeit = {0: 70 + i * 4, 2: 480 + i * 30, 5: 200 + i * 10, 9: 80 + i * 3, 12: 800 + i * 20}.get(j)
            _versuch(tid, lid, 1, "bestanden", zeit, "" if (i + j) % 4 else "Ruhig und strukturiert.", uid, name, ts)
    for j, lid in enumerate(l2):
        if j == 3:
            _versuch(t2[4], lid, 1, "mangelhaft", None, "Lagerung der verletzten Person ohne Zugentlastung.", uid, name, ts)
            _versuch(t2[4], lid, 2, "bestanden", None, "Nachprüfung: Zugentlastung gesetzt, Rückführung sauber.", uid, name, ts)
        else:
            _versuch(t2[4], lid, 1, "bestanden", None, "", uid, name, ts)
    for j, lid in enumerate(l2[:8]):
        if j in (2, 5):
            _versuch(t2[5], lid, 1, "mangelhaft", 700 if j == 2 else 300,
                     "Spannsystem ohne Lastprobe freigegeben." if j == 2 else "Lastübernahme nicht gelungen, Abbruch.", uid, name, ts)
        else:
            _versuch(t2[5], lid, 1, "bestanden", None, "", uid, name, ts)
    for i, tid in enumerate(t2):
        ergebnis = "nicht_bestanden" if i == 5 else "bestanden"
        db.execute("UPDATE pruef_teilnehmer SET ergebnis = ?, ergebnis_von = ?, ergebnis_von_name = ?, ergebnis_am = ? "
                   "WHERE id = ?", (ergebnis, uid, name, ts, tid))
    db.execute("UPDATE pruef_teilnehmer SET kommentar = ? WHERE id = ?",
               ("Seiltechnik noch unsicher – Wiederholung der Flachseilbrücke und des Notverfahrens im nächsten Jahr.", t2[5]))
    db.execute("UPDATE pruef_teilnehmer SET kommentar = ? WHERE id = ?",
               (f"Auflage: Nachweis Fitness-Test bis {tag} nachreichen.", t2[4]))
    return [sr1, sr2]


def main():
    """Von der Kommandozeile: unter dem ersten Administrator anlegen."""
    from . import create_app
    app = create_app()
    with app.app_context():
        admin = db.query("SELECT id, name, email FROM users WHERE role = 'admin' ORDER BY id LIMIT 1", one=True)
        if not admin:
            raise SystemExit("Kein Administrator vorhanden – zuerst die Anwendung starten (ADMIN_EMAIL/ADMIN_PASSWORD).")
        with db.transaction():
            ids = anlegen(admin["id"], admin["name"] or admin["email"])
        print("Beispiel-Lehrgänge angelegt:", ", ".join(str(i) for i in ids))


if __name__ == "__main__":
    main()
