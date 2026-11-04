/* Übungsdatei der Einführung: Riegenkarten (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.4; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile, Titel der Abläufe und Startadresse des ersten Ablaufs
   stehen auch in app/einfuehrung.py, TEILE – tests/test_einfuehrung.py vergleicht beide).

   Übungsbestand: der „Übungslehrgang“ (laufend) mit Übungsperson A als Leitung und dem eigenen Konto als Ausbilder (in
   den Teilen „Leitung“ und „Redakteur“ ebenfalls als Leitung – darf_leiten), drei „Teilnehmer Übung 1–3“, zwei
   Voraussetzungen und zwei Leistungen mit je zwei Kriterien – alles nur als „Platzhalter“, keine Prüfungsleistungen der
   DLRG, keine Zeitansätze (also auch keine Stoppuhr in der Übung). Ein mangelhafter Versuch steht schon da (Reiter
   „Mängel“), dazu der „Übungskatalog“ für das Anlegen. Kennungen 930000001–930000099; was in der Übung neu entsteht,
   bekommt eine freie Kennung aus demselben Bereich (neueKennung). Profilbilder gibt es keine – die Seite zeigt Initialen
   (Bilder nähme sie nur aus der Medienablage des Servers, und die erreicht die Übung nie).

   Die Antworten bilden die Schnittstelle app/api_pruefungen.py nach (dieselben JSON-Formen: _lehrgang_kurz,
   _lehrgang_detail, _teilnehmer_liste, _versuche_json, maengel, nutzer …) und spielen Schreibvorgänge im Übungsbestand
   nach. Was die Übung nicht kennt (Löschen, Import, Kopieren, Kataloge bearbeiten, Medien, Profilbilder, Voraussetzungen
   und Leistungen verwalten), beantwortet einfuehrung.js mit „In der Übung nicht verfügbar.“; Druckansichten öffnet sie
   nicht (window.open → Toast). */
(function () {
  const STROEMIS = window.STROEMIS || {};
  const API = "/api/pruefungen";
  const LG = 930000001;
  const TN = [930000011, 930000012, 930000013];
  const VOR = [930000021, 930000022];
  const LEI = [930000031, 930000032];
  const PERSON_A = 930000071;
  const KATALOG = 930000081;
  // Dieselben Sätze wie im Server (api_pruefungen.py).
  const KOMMENTAR_PFLICHT = "Bei „mangelhaft“ ist ein Kommentar Pflicht.";
  const SCHON_BEWERTET = "Für diese Leistung gibt es schon eine Bewertung – bearbeite sie oder lege eine Nachprüfung an.";
  const NUR_NACH_MANGEL = "Eine Nachprüfung gibt es nur nach einer mangelhaften Bewertung.";
  const EINGEFROREN = "Für diese Person ist das Lehrgangsergebnis vermerkt – die Prüfungsdaten sind eingefroren. "
    + "Die Lehrgangsleitung kann das Ergebnis aufheben.";
  const NUR_LEITUNG = "Nur die Lehrgangsleitung oder die Verwaltung der Riegenkarten darf das.";
  const ERGEBNIS_WAEHLEN = "Bitte „bestanden“ oder „mangelhaft“ wählen.";
  const NICHT_GEFUNDEN = { status: 404, error: "Lehrgang nicht gefunden" };
  let abgehakt = null;          // {tid, vid} des zuletzt abgehakten Kastens (Ziel des Schritts danach)
  let angelegt = null;          // Kennung der zuletzt angelegten Person (ebenso)
  const STATUS_WERTE = ["geplant", "laufend", "abgeschlossen"];

  const ich = () => {
    const u = STROEMIS.user || {};
    return { id: u.id, name: u.name || u.email || "" };
  };
  const jetzt = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
  const heute = () => jetzt().slice(0, 10);
  // Im Grundteil prüft das Konto nur mit; in „Leitung“ und „Redakteur“ leitet es den Übungslehrgang.
  const leitet = () => (STROEMIS.einfuehrung || {}).uebung !== "grund";
  const text = (d, feld, grenze) => (d && typeof d[feld] === "string" ? d[feld].trim().slice(0, grenze) : "");
  const klein = (t) => String(t || "").normalize("NFKC").toLowerCase();

  /* --- Übungsbestand (frisch je Ablauf) ---------------------------------------------------------------------------- */
  function bestand() {
    const i = ich();
    const am = jetzt();
    const kriterien = (lid, a, b) => [{ id: a, leistung_id: lid, bezeichnung: "Kriterium 1 (Platzhalter)", sortierung: 0 },
      { id: b, leistung_id: lid, bezeichnung: "Kriterium 2 (Platzhalter)", sortierung: 1 }];
    const person = (id, nr) => ({ id, lehrgang_id: LG, name: `Übung ${nr}`, vorname: "Teilnehmer", geburtsdatum: null,
      gliederung: "Übung", email: "", bemerkung: "", sortierung: nr - 1, kommentar: "", ergebnis: null,
      ergebnis_von_name: "", ergebnis_am: null });
    return {
      lehrgaenge: [{ id: LG, titel: "Übungslehrgang", nummer: "", datum_von: heute(), datum_bis: heute(), ort: "",
        status: "laufend", beschreibung: "", created_by_name: "Übungsperson A", created_at: am, updated_at: am }],
      ausbilder: [
        { id: 930000051, lehrgang_id: LG, user_id: PERSON_A, name: "Übungsperson A", gliederung: "Übung", funktion: "",
          ist_leitung: true },
        { id: 930000052, lehrgang_id: LG, user_id: i.id, name: i.name, gliederung: "", funktion: "", ist_leitung: leitet() }],
      voraussetzungen: [{ id: VOR[0], lehrgang_id: LG, bezeichnung: "Platzhalter-Voraussetzung 1", sortierung: 0 },
        { id: VOR[1], lehrgang_id: LG, bezeichnung: "Platzhalter-Voraussetzung 2", sortierung: 1 }],
      leistungen: [
        { id: LEI[0], lehrgang_id: LG, bezeichnung: "Platzhalter-Leistung A", beschreibung_md: "", zeitansatz_sekunden: null,
          sortierung: 0 },
        { id: LEI[1], lehrgang_id: LG, bezeichnung: "Platzhalter-Leistung B", beschreibung_md: "", zeitansatz_sekunden: null,
          sortierung: 1 }],
      kriterien: kriterien(LEI[0], 930000041, 930000042).concat(kriterien(LEI[1], 930000043, 930000044)),
      teilnehmer: [person(TN[0], 1), person(TN[1], 2), person(TN[2], 3)],
      // Teilnehmer Übung 2 hat beide Voraussetzungen erfüllt, Teilnehmer Übung 1 und 3 noch keine.
      status: VOR.map((vid) => ({ teilnehmer_id: TN[1], voraussetzung_id: vid, erfuellt: true,
        gesetzt_von_name: "Übungsperson A", gesetzt_am: am, quelle: "manuell" })),
      verlauf: VOR.map((vid) => ({ teilnehmer_id: TN[1], voraussetzung_id: vid, erfuellt: true,
        user_name: "Übungsperson A", zeit: am, quelle: "manuell" })),
      // Ein Versuch: Teilnehmer Übung 2 in Leistung A mangelhaft – er steht im Reiter „Mängel“.
      versuche: [{ id: 930000061, teilnehmer_id: TN[1], leistung_id: LEI[0], versuch_nr: 1, ist_nachpruefung: false,
        ergebnis: "mangelhaft", zeit_sekunden: null, kommentar: "Platzhalter-Kommentar der Übung.",
        geprueft_von_name: "Übungsperson A", geprueft_am: am, bearbeitet_von_name: null, bearbeitet_am: null,
        kriterien: { 930000041: true, 930000042: false }, verlauf: [] }],
      // Konten für die Ausbilder-Suche – nur Übungspersonen.
      konten: [{ id: PERSON_A, name: "Übungsperson A", gliederung: "Übung" },
        { id: 930000072, name: "Übungsperson B", gliederung: "Übung" }],
      kataloge: [{ id: KATALOG, titel: "Übungskatalog", beschreibung: "Platzhalter für die Übung.",
        created_by_name: "Übungsperson A", created_at: am, updated_at: am,
        leistungen: [{ id: 930000082, bezeichnung: "Platzhalter-Leistung aus dem Katalog", beschreibung_md: "",
          zeitansatz_sekunden: null, sortierung: 0,
          kriterien: [{ id: 930000083, bezeichnung: "Kriterium 1 (Platzhalter)", sortierung: 0 }] }] }],
    };
  }

  /* Eine freie Kennung im Bereich der Riegenkarten: zuerst 930000090–099, dann, was darunter frei ist. */
  function neueKennung(z) {
    const belegt = new Set(JSON.stringify(z).match(/\b9300000\d\d\b/g) || []);
    const reihe = [];
    for (let id = 930000090; id <= 930000099; id++) reihe.push(id);
    for (let id = 930000089; id >= 930000001; id--) reihe.push(id);
    const frei = reihe.find((id) => !belegt.has(String(id)));
    if (!frei) throw new Error("Die Übung hat keine freie Kennung mehr – fang den Ablauf neu an.");
    return frei;
  }

  /* --- JSON-Formen wie api_pruefungen.py --------------------------------------------------------------------------- */
  const lehrgangVon = (z, lid) => z.lehrgaenge.find((l) => l.id === lid) || null;
  const tnVon = (z, tid) => z.teilnehmer.find((t) => t.id === tid) || null;
  const leistungVon = (z, lid) => z.leistungen.find((l) => l.id === lid) || null;
  const sortiert = (liste) => liste.slice().sort((a, b) => a.sortierung - b.sortierung || a.id - b.id);
  const tnSortiert = (liste) => liste.slice().sort((a, b) => a.sortierung - b.sortierung
    || klein(a.name).localeCompare(klein(b.name)) || klein(a.vorname).localeCompare(klein(b.vorname)));
  // Sichtbar ist ein Lehrgang, in dem das Konto als Ausbilder steht; leiten darf es mit dem Kennzeichen „Leitung“.
  const sichtbar = (z, lid) => z.ausbilder.some((a) => a.lehrgang_id === lid && a.user_id === ich().id);
  const darfLeiten = (z, lid) => z.ausbilder.some((a) => a.lehrgang_id === lid && a.user_id === ich().id && a.ist_leitung);
  const zellstatus = (v) => (v ? (v.ist_nachpruefung ? "nachpruefung_" : "") + v.ergebnis : "offen");
  const versucheVon = (z, tid, lid) => z.versuche.filter((v) => v.teilnehmer_id === tid && v.leistung_id === lid)
    .sort((a, b) => a.versuch_nr - b.versuch_nr);

  function lehrgangKurz(z, lg) {
    const tns = z.teilnehmer.filter((t) => t.lehrgang_id === lg.id);
    const ls = z.leistungen.filter((l) => l.lehrgang_id === lg.id);
    const vor = z.voraussetzungen.filter((v) => v.lehrgang_id === lg.id);
    const letzte = {};          // je Zelle der Versuch mit der höchsten Nummer
    z.versuche.filter((v) => tns.some((t) => t.id === v.teilnehmer_id)).forEach((v) => {
      const k = `${v.teilnehmer_id}:${v.leistung_id}`;
      if (!letzte[k] || letzte[k].versuch_nr < v.versuch_nr) letzte[k] = v;
    });
    const erfuellt = (t, v) => z.status.some((s) => s.teilnehmer_id === t.id && s.voraussetzung_id === v.id && s.erfuellt);
    const leiten = darfLeiten(z, lg.id);
    return {
      id: lg.id, titel: lg.titel, nummer: lg.nummer, datum_von: lg.datum_von, datum_bis: lg.datum_bis, ort: lg.ort,
      status: lg.status, created_by_name: lg.created_by_name, created_at: lg.created_at, updated_at: lg.updated_at,
      tn_anzahl: tns.length, leistungen_anzahl: ls.length, zellen_abgenommen: Object.keys(letzte).length,
      offene_maengel: Object.values(letzte).filter((v) => v.ergebnis === "mangelhaft").length,
      voraussetzungen_offen: tns.filter((t) => vor.some((v) => !erfuellt(t, v))).length,
      ergebnis_bestanden: tns.filter((t) => t.ergebnis === "bestanden").length,
      ergebnis_nicht_bestanden: tns.filter((t) => t.ergebnis === "nicht_bestanden").length,
      zellen_gesamt: tns.length * ls.length, darf_leiten: leiten,
      // Kopieren ist ein Anlegen: nur die Leitung ab Redakteur (die Liste zeigt es, kopiert wird in der Übung nicht).
      darf_kopieren: leiten && S.stufe("pruefungen") >= S.STUFE.redakteur,
    };
  }

  const kriterienVon = (z, lid) => sortiert(z.kriterien.filter((k) => k.leistung_id === lid))
    .map((k) => ({ id: k.id, bezeichnung: k.bezeichnung, sortierung: k.sortierung }));
  const leistungVoll = (z, l) => ({ id: l.id, bezeichnung: l.bezeichnung, beschreibung_md: l.beschreibung_md,
    zeitansatz_sekunden: l.zeitansatz_sekunden, sortierung: l.sortierung, kriterien: kriterienVon(z, l.id),
    kriterien_eingefroren: z.versuche.some((v) => v.leistung_id === l.id && Boolean((tnVon(z, v.teilnehmer_id) || {}).ergebnis)) });

  function teilnehmerListe(z, lid, nurTid) {
    const vor = z.voraussetzungen.filter((v) => v.lehrgang_id === lid);
    const tns = z.teilnehmer.filter((t) => t.lehrgang_id === lid && (nurTid === undefined || t.id === nurTid));
    return tnSortiert(tns).map((t) => {
      const vs = {};
      z.status.filter((s) => s.teilnehmer_id === t.id && vor.some((v) => v.id === s.voraussetzung_id)).forEach((s) => {
        vs[String(s.voraussetzung_id)] = { erfuellt: s.erfuellt, gesetzt_von_name: s.gesetzt_von_name,
          gesetzt_am: s.gesetzt_am, quelle: s.quelle };
      });
      const zellen = {};
      z.versuche.filter((v) => v.teilnehmer_id === t.id).sort((a, b) => a.versuch_nr - b.versuch_nr).forEach((v) => {
        const k = String(v.leistung_id);
        const zelle = zellen[k] || (zellen[k] = { versuche: 0, medien_anzahl: 0 });
        const stand = Object.assign({}, v.kriterien || {});
        zelle.versuche += 1;
        Object.assign(zelle, { status: zellstatus(v), letzter_versuch_id: v.id, letztes_ergebnis: v.ergebnis,
          letzte_zeit_sekunden: v.zeit_sekunden, letzter_kommentar: v.kommentar, geprueft_von_name: v.geprueft_von_name,
          geprueft_am: v.geprueft_am, kriterien_erfuellt: Object.values(stand).filter(Boolean).length, kriterien_stand: stand });
      });
      const erfuellt = Object.values(vs).filter((s) => s.erfuellt).length;
      return { id: t.id, name: t.name, vorname: t.vorname, geburtsdatum: t.geburtsdatum, gliederung: t.gliederung,
        email: t.email, bemerkung: t.bemerkung, extra: {}, sortierung: t.sortierung, bild: null, kommentar: t.kommentar,
        ergebnis: t.ergebnis, ergebnis_von_name: t.ergebnis_von_name, ergebnis_am: t.ergebnis_am,
        eingefroren: Boolean(t.ergebnis), voraussetzungen: vs, voraussetzungen_offen: Math.max(0, vor.length - erfuellt),
        leistungen: zellen };
    });
  }
  const tnJson = (z, tid) => teilnehmerListe(z, tnVon(z, tid).lehrgang_id, tid)[0];

  function lehrgangDetail(z, lid) {
    const lg = lehrgangVon(z, lid);
    if (!lg || !sichtbar(z, lid)) return null;
    return Object.assign(lehrgangKurz(z, lg), {
      beschreibung: lg.beschreibung,
      ausbilder: z.ausbilder.filter((a) => a.lehrgang_id === lid).map((a) => ({ id: a.id, user_id: a.user_id, name: a.name,
        gliederung: a.gliederung, funktion: a.funktion, ist_leitung: a.ist_leitung, zugriff: true, ohne_zugriff: null })),
      voraussetzungen: sortiert(z.voraussetzungen.filter((v) => v.lehrgang_id === lid))
        .map((v) => ({ id: v.id, bezeichnung: v.bezeichnung, sortierung: v.sortierung })),
      leistungen: sortiert(z.leistungen.filter((l) => l.lehrgang_id === lid)).map((l) => leistungVoll(z, l)),
      teilnehmer: teilnehmerListe(z, lid),
    });
  }

  function versuchJson(z, v) {
    const t = tnVon(z, v.teilnehmer_id) || {};
    const l = leistungVon(z, v.leistung_id) || {};
    return { id: v.id, teilnehmer_id: v.teilnehmer_id, leistung_id: v.leistung_id, versuch_nr: v.versuch_nr,
      ist_nachpruefung: v.ist_nachpruefung, ergebnis: v.ergebnis, zeit_sekunden: v.zeit_sekunden, kommentar: v.kommentar,
      geprueft_von_name: v.geprueft_von_name, geprueft_am: v.geprueft_am, bearbeitet_von_name: v.bearbeitet_von_name,
      bearbeitet_am: v.bearbeitet_am, medien: [], verlauf: (v.verlauf || []).slice(),
      kriterien: Object.assign({}, v.kriterien || {}), leistung_bezeichnung: l.bezeichnung || "",
      teilnehmer_name: `${t.vorname || ""} ${t.name || ""}`.trim() };
  }

  /* Kriterien-Haken aus dem Body eines Versuchs – Unbekanntes fällt still weg (wie _kriterien_map). */
  function kriterienMap(z, d, lid) {
    const out = {};
    const gueltig = new Set(z.kriterien.filter((k) => k.leistung_id === lid).map((k) => String(k.id)));
    const roh = d && d.kriterien && typeof d.kriterien === "object" ? d.kriterien : {};
    Object.entries(roh).forEach(([k, w]) => { if (gueltig.has(String(+k)) && typeof w === "boolean") out[String(+k)] = w; });
    return out;
  }
  const zeitWert = (w) => (Number.isInteger(w) && w >= 0 && w <= 86400 ? w : null);
  const bewertungPruefen = (ergebnis, kommentar) => {
    if (ergebnis !== "bestanden" && ergebnis !== "mangelhaft") return { status: 400, error: ERGEBNIS_WAEHLEN };
    if (ergebnis === "mangelhaft" && !kommentar) return { status: 400, error: KOMMENTAR_PFLICHT };
    return null;
  };
  // Eine Person, die das Konto sehen darf – sonst dieselbe 404 wie der Server.
  const tnPruefen = (z, tid) => {
    const t = tnVon(z, tid);
    return t && sichtbar(z, t.lehrgang_id) ? [t, null] : [null, NICHT_GEFUNDEN];
  };

  /* --- Antworten ---------------------------------------------------------------------------------------------------- */
  const antworten = [
    // Lehrgangsliste: nur, wo das Konto als Ausbilder steht; ?q= und ?jahr= wie list_lehrgaenge, neueste zuerst.
    ["GET", `${API}/lehrgaenge`, (m, body, z, url) => {
      const q = klein((url.searchParams.get("q") || "").trim());
      const jahr = (url.searchParams.get("jahr") || "").trim();
      const liste = z.lehrgaenge.filter((l) => sichtbar(z, l.id) && (!jahr || String(l.datum_von || "").startsWith(jahr))
        && (!q || klein(`${l.titel} ${l.nummer} ${l.ort}`).includes(q)));
      liste.sort((a, b) => (a.datum_von ? 0 : 1) - (b.datum_von ? 0 : 1)
        || String(b.datum_von || "").localeCompare(String(a.datum_von || "")) || b.id - a.id);
      return { lehrgaenge: liste.map((l) => lehrgangKurz(z, l)) };
    }],
    // Lehrgang anlegen (Teil „Redakteur“): Ausbilder aus dem Dialog, die anlegende Person ist Leitung; ein Katalog gibt
    // seine Leistungen samt Kriterien einmalig mit.
    ["POST", `${API}/lehrgaenge`, (m, d, z) => {
      const titel = text(d, "titel", 200);
      if (!titel) return { status: 400, error: "Bitte einen Titel angeben." };
      const von = (d && d.datum_von) || null;
      const bis = (d && d.datum_bis) || null;
      if (von && bis && bis < von) return { status: 400, error: "„Datum bis“ liegt vor „Datum von“." };
      const i = ich();
      const lid = neueKennung(z);
      const am = jetzt();
      z.lehrgaenge.push({ id: lid, titel, nummer: text(d, "nummer", 60), datum_von: von, datum_bis: bis, ort: text(d, "ort", 200),
        status: STATUS_WERTE.includes(d.status) ? d.status : "geplant", beschreibung: text(d, "beschreibung", 20000),
        created_by_name: i.name, created_at: am, updated_at: am });
      const zeilen = (Array.isArray(d.ausbilder) ? d.ausbilder : []).filter((a) => a && a.user_id != null);
      if (!zeilen.some((a) => a.user_id === i.id)) zeilen.unshift({ user_id: i.id, funktion: "", ist_leitung: true });
      zeilen.forEach((a) => {
        const konto = a.user_id === i.id ? { name: i.name, gliederung: "" } : z.konten.find((k) => k.id === a.user_id);
        if (!konto) return;
        z.ausbilder.push({ id: neueKennung(z), lehrgang_id: lid, user_id: a.user_id, name: konto.name,
          gliederung: konto.gliederung, funktion: text(a, "funktion", 80), ist_leitung: a.user_id === i.id || Boolean(a.ist_leitung) });
      });
      const katalog = z.kataloge.find((k) => k.id === d.katalog_id);
      (katalog ? katalog.leistungen : []).forEach((p, n) => {
        const neu = neueKennung(z);
        z.leistungen.push({ id: neu, lehrgang_id: lid, bezeichnung: p.bezeichnung, beschreibung_md: p.beschreibung_md,
          zeitansatz_sekunden: p.zeitansatz_sekunden, sortierung: n });
        p.kriterien.forEach((k, j) => z.kriterien.push({ id: neueKennung(z), leistung_id: neu, bezeichnung: k.bezeichnung, sortierung: j }));
      });
      return { lehrgang: lehrgangDetail(z, lid) };
    }],
    ["GET", /^\/api\/pruefungen\/lehrgaenge\/(\d+)$/, (m, body, z) => {
      const lg = lehrgangDetail(z, +m[1]);
      return lg ? { lehrgang: lg } : NICHT_GEFUNDEN;
    }],
    // Lehrgang bearbeiten (Menü „Mehr“ der Leitung): die mitgeschickten Felder; die Ausbilderliste ersetzt die bisherige.
    ["PUT", /^\/api\/pruefungen\/lehrgaenge\/(\d+)$/, (m, d, z) => {
      const lid = +m[1];
      const lg = lehrgangVon(z, lid);
      if (!lg || !sichtbar(z, lid)) return NICHT_GEFUNDEN;
      if (!darfLeiten(z, lid)) return { status: 403, error: NUR_LEITUNG };
      if ("titel" in d && !text(d, "titel", 200)) return { status: 400, error: "Bitte einen Titel angeben." };
      [["titel", 200], ["nummer", 60], ["ort", 200], ["beschreibung", 20000]].forEach(([k, n]) => { if (k in d) lg[k] = text(d, k, n); });
      ["datum_von", "datum_bis"].forEach((k) => { if (k in d) lg[k] = d[k] || null; });
      if (STATUS_WERTE.includes(d.status)) lg.status = d.status;
      if (Array.isArray(d.ausbilder)) {
        const alt = z.ausbilder.filter((a) => a.lehrgang_id === lid);
        z.ausbilder = z.ausbilder.filter((a) => a.lehrgang_id !== lid);
        d.ausbilder.filter((a) => a && a.user_id != null).forEach((a) => {
          const vorher = alt.find((x) => x.user_id === a.user_id);
          const konto = vorher || z.konten.find((k) => k.id === a.user_id);
          if (!konto) return;
          z.ausbilder.push({ id: vorher ? vorher.id : neueKennung(z), lehrgang_id: lid, user_id: a.user_id, name: konto.name,
            gliederung: konto.gliederung || "", funktion: text(a, "funktion", 80),
            ist_leitung: a.user_id === ich().id || Boolean(a.ist_leitung) });
        });
      }
      lg.updated_at = jetzt();
      return { lehrgang: lehrgangDetail(z, lid) };
    }],
    // Ausbilder-Suche: nur Übungspersonen (ab zwei Zeichen, Teil des Namens).
    ["GET", `${API}/nutzer`, (m, body, z, url) => {
      const q = (url.searchParams.get("q") || "").trim();
      if (q.length < 2) return { status: 400, error: "Bitte mindestens 2 Zeichen des Namens oder der E-Mail-Adresse eingeben." };
      return { nutzer: z.konten.filter((k) => klein(k.name).includes(klein(q))), mehr: false };
    }],
    // Teilnehmende anlegen und ändern (Teil „Leitung“).
    ["POST", /^\/api\/pruefungen\/lehrgaenge\/(\d+)\/teilnehmer$/, (m, d, z) => {
      const lid = +m[1];
      if (!lehrgangVon(z, lid) || !sichtbar(z, lid)) return NICHT_GEFUNDEN;
      if (!darfLeiten(z, lid)) return { status: 403, error: NUR_LEITUNG };
      const name = text(d, "name", 200);
      if (!name) return { status: 400, error: "Bitte einen Nachnamen angeben." };
      const tid = neueKennung(z);
      const sortierung = Math.max(-1, ...z.teilnehmer.filter((t) => t.lehrgang_id === lid).map((t) => t.sortierung)) + 1;
      z.teilnehmer.push({ id: tid, lehrgang_id: lid, name, vorname: text(d, "vorname", 200), geburtsdatum: d.geburtsdatum || null,
        gliederung: text(d, "gliederung", 200), email: text(d, "email", 200), bemerkung: text(d, "bemerkung", 5000), sortierung,
        kommentar: "", ergebnis: null, ergebnis_von_name: "", ergebnis_am: null });
      angelegt = tid;
      return { teilnehmer: tnJson(z, tid) };
    }],
    ["PUT", /^\/api\/pruefungen\/teilnehmer\/(\d+)$/, (m, d, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      if (!darfLeiten(z, t.lehrgang_id)) return { status: 403, error: NUR_LEITUNG };
      if ("name" in d && !text(d, "name", 200)) return { status: 400, error: "Bitte einen Nachnamen angeben." };
      ["name", "vorname", "gliederung", "email", "bemerkung"].forEach((k) => { if (k in d) t[k] = text(d, k, 5000); });
      if ("geburtsdatum" in d) t.geburtsdatum = d.geburtsdatum || null;
      return { teilnehmer: tnJson(z, t.id) };
    }],
    ["PUT", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/kommentar$/, (m, d, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      if (t.ergebnis) return { status: 409, error: EINGEFROREN };
      t.kommentar = text(d, "kommentar", 5000);
      return { teilnehmer: tnJson(z, t.id) };
    }],
    // Lehrgangsergebnis (Teil „Leitung“): bestanden, nicht bestanden oder null zum Aufheben.
    ["PUT", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/ergebnis$/, (m, d, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      if (!darfLeiten(z, t.lehrgang_id)) return { status: 403, error: NUR_LEITUNG };
      const erg = d ? d.ergebnis : null;
      if (erg === null || erg === undefined || erg === "") Object.assign(t, { ergebnis: null, ergebnis_von_name: "", ergebnis_am: null });
      else if (erg === "bestanden" || erg === "nicht_bestanden") Object.assign(t, { ergebnis: erg, ergebnis_von_name: ich().name, ergebnis_am: jetzt() });
      else return { status: 400, error: "Das Ergebnis muss „bestanden“, „nicht_bestanden“ oder leer sein." };
      return { teilnehmer: tnJson(z, t.id) };
    }],
    // Alle Bewertungen einer Person (Reiter „Mängel“ → „Alle Bewertungen“).
    ["GET", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/versuche$/, (m, body, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      const ls = sortiert(z.leistungen.filter((l) => l.lehrgang_id === t.lehrgang_id)).map((l) => l.id);
      const versuche = z.versuche.filter((v) => v.teilnehmer_id === t.id)
        .sort((a, b) => ls.indexOf(a.leistung_id) - ls.indexOf(b.leistung_id) || a.versuch_nr - b.versuch_nr);
      return { teilnehmer: tnJson(z, t.id), versuche: versuche.map((v) => versuchJson(z, v)) };
    }],
    // Voraussetzung abhaken (Grundteil): aktueller Stand und ein Eintrag im Verlauf.
    ["PUT", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/voraussetzungen\/(\d+)$/, (m, d, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      const vid = +m[2];
      const v = z.voraussetzungen.find((x) => x.id === vid);
      if (!v) return { status: 404, error: "Voraussetzung nicht gefunden" };
      if (v.lehrgang_id !== t.lehrgang_id) return { status: 400, error: "Die Voraussetzung gehört nicht zum Lehrgang dieser Person." };
      if (t.ergebnis) return { status: 409, error: EINGEFROREN };
      const stand = { erfuellt: Boolean(d && d.erfuellt === true), gesetzt_von_name: ich().name, gesetzt_am: jetzt(), quelle: "manuell" };
      z.status = z.status.filter((s) => !(s.teilnehmer_id === t.id && s.voraussetzung_id === vid));
      z.status.push(Object.assign({ teilnehmer_id: t.id, voraussetzung_id: vid }, stand));
      z.verlauf.push({ teilnehmer_id: t.id, voraussetzung_id: vid, erfuellt: stand.erfuellt, user_name: stand.gesetzt_von_name,
        zeit: stand.gesetzt_am, quelle: "manuell" });
      abgehakt = { tid: t.id, vid };
      return { status: stand };
    }],
    ["GET", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/voraussetzungen\/(\d+)\/verlauf$/, (m, body, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      return { verlauf: z.verlauf.filter((e) => e.teilnehmer_id === t.id && e.voraussetzung_id === +m[2]).reverse()
        .map((e) => ({ erfuellt: e.erfuellt, user_name: e.user_name, zeit: e.zeit, quelle: e.quelle })) };
    }],
    // Eine Zelle (Teilnehmende × Leistung): Versuche lesen und bewerten (Grundteil).
    ["GET", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/leistungen\/(\d+)\/versuche$/, (m, body, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      const l = leistungVon(z, +m[2]);
      if (!l) return { status: 404, error: "Prüfungsleistung nicht gefunden" };
      if (l.lehrgang_id !== t.lehrgang_id) return { status: 400, error: "Die Prüfungsleistung gehört nicht zum Lehrgang dieser Person." };
      const rows = versucheVon(z, t.id, l.id);
      return { versuche: rows.map((v) => versuchJson(z, v)), status: zellstatus(rows[rows.length - 1]),
        teilnehmer: tnJson(z, t.id), leistung: leistungVoll(z, l) };
    }],
    ["POST", /^\/api\/pruefungen\/teilnehmer\/(\d+)\/leistungen\/(\d+)\/versuche$/, (m, d, z) => {
      const [t, fehler] = tnPruefen(z, +m[1]);
      if (fehler) return fehler;
      const l = leistungVon(z, +m[2]);
      if (!l || l.lehrgang_id !== t.lehrgang_id) return { status: 400, error: "Die Prüfungsleistung gehört nicht zum Lehrgang dieser Person." };
      if (t.ergebnis) return { status: 409, error: EINGEFROREN };
      const ergebnis = text(d, "ergebnis", 20);
      const kommentar = text(d, "kommentar", 5000);
      const falsch = bewertungPruefen(ergebnis, kommentar);
      if (falsch) return falsch;
      const bisher = versucheVon(z, t.id, l.id);
      const letzter = bisher[bisher.length - 1];
      if (letzter && d.nachpruefung !== true) return { status: 409, error: SCHON_BEWERTET };
      if (letzter && letzter.ergebnis !== "mangelhaft") return { status: 409, error: NUR_NACH_MANGEL };
      const v = { id: neueKennung(z), teilnehmer_id: t.id, leistung_id: l.id, versuch_nr: letzter ? letzter.versuch_nr + 1 : 1,
        ist_nachpruefung: Boolean(letzter), ergebnis, zeit_sekunden: zeitWert(d.zeit_sekunden), kommentar,
        geprueft_von_name: ich().name, geprueft_am: jetzt(), bearbeitet_von_name: null, bearbeitet_am: null,
        kriterien: kriterienMap(z, d, l.id), verlauf: [] };
      z.versuche.push(v);
      return { versuch: versuchJson(z, v) };
    }],
    // Einen Versuch bearbeiten: Der bisherige Stand wandert in den Verlauf (wie update_versuch).
    ["PUT", /^\/api\/pruefungen\/versuche\/(\d+)$/, (m, d, z) => {
      const v = z.versuche.find((x) => x.id === +m[1]);
      if (!v) return { status: 404, error: "Versuch nicht gefunden" };
      const [t, fehler] = tnPruefen(z, v.teilnehmer_id);
      if (fehler) return fehler;
      if (t.ergebnis) return { status: 409, error: EINGEFROREN };
      const ergebnis = text(d, "ergebnis", 20) || v.ergebnis;
      const kommentar = "kommentar" in d ? text(d, "kommentar", 5000) : v.kommentar;
      const falsch = bewertungPruefen(ergebnis, kommentar);
      if (falsch) return falsch;
      const am = jetzt();
      v.verlauf = (v.verlauf || []).concat({ ergebnis: v.ergebnis, zeit_sekunden: v.zeit_sekunden, kommentar: v.kommentar,
        von_name: v.bearbeitet_von_name || v.geprueft_von_name, stand_ab: v.bearbeitet_am || v.geprueft_am, ersetzt_am: am });
      Object.assign(v, { ergebnis, kommentar, zeit_sekunden: "zeit_sekunden" in d ? zeitWert(d.zeit_sekunden) : v.zeit_sekunden,
        bearbeitet_von_name: ich().name, bearbeitet_am: am });
      if (d.kriterien && typeof d.kriterien === "object") v.kriterien = kriterienMap(z, d, v.leistung_id);
      return { versuch: versuchJson(z, v) };
    }],
    // Reiter „Mängel“: alle mangelhaften Versuche mit dem Stand der Nachprüfung (wie maengel()).
    ["GET", /^\/api\/pruefungen\/lehrgaenge\/(\d+)\/maengel$/, (m, body, z, url) => {
      const lid = +m[1];
      if (!lehrgangVon(z, lid) || !sichtbar(z, lid)) return NICHT_GEFUNDEN;
      const nurTn = +url.searchParams.get("teilnehmer") || null;
      const nurL = +url.searchParams.get("leistung") || null;
      const nurOffen = ["1", "true", "ja"].includes((url.searchParams.get("nur_offen") || "").toLowerCase());
      const tns = z.teilnehmer.filter((t) => t.lehrgang_id === lid);
      const ls = sortiert(z.leistungen.filter((l) => l.lehrgang_id === lid));
      const stelle = (v) => ls.findIndex((l) => l.id === v.leistung_id);
      const rows = z.versuche.filter((v) => tns.some((t) => t.id === v.teilnehmer_id) && (!nurTn || v.teilnehmer_id === nurTn)
        && (!nurL || v.leistung_id === nurL));
      rows.sort((a, b) => {
        const ta = tnVon(z, a.teilnehmer_id), tb = tnVon(z, b.teilnehmer_id);
        return klein(ta.name).localeCompare(klein(tb.name)) || klein(ta.vorname).localeCompare(klein(tb.vorname))
          || ta.id - tb.id || stelle(a) - stelle(b) || a.versuch_nr - b.versuch_nr;
      });
      const maengel = [];
      rows.filter((v) => v.ergebnis === "mangelhaft").forEach((v) => {
        const zelle = versucheVon(z, v.teilnehmer_id, v.leistung_id);
        const letzter = zelle[zelle.length - 1];
        const istLetzter = letzter.id === v.id;
        const zs = zellstatus(letzter);
        if (nurOffen && !(istLetzter && (zs === "mangelhaft" || zs === "nachpruefung_mangelhaft"))) return;
        const t = tnVon(z, v.teilnehmer_id);
        const l = leistungVon(z, v.leistung_id);
        maengel.push({ versuch: versuchJson(z, v),
          teilnehmer: { id: t.id, name: t.name, vorname: t.vorname, gliederung: t.gliederung },
          leistung: { id: l.id, bezeichnung: l.bezeichnung, zeitansatz_sekunden: l.zeitansatz_sekunden },
          nachpruefung_status: istLetzter ? "offen" : letzter.ergebnis === "bestanden" ? "bestanden" : "erneut_mangelhaft",
          zellstatus: zs });
      });
      return { maengel, teilnehmer: tnSortiert(tns).map((t) => ({ id: t.id, name: t.name, vorname: t.vorname })),
        leistungen: ls.map((l) => ({ id: l.id, bezeichnung: l.bezeichnung })) };
    }],
    // Kataloge (in der Übung nur im Teil „Redakteur“ erreichbar): lesen ja, bearbeiten nicht (darf_bearbeiten falsch).
    ["GET", `${API}/kataloge`, (m, body, z) => ({ kataloge: z.kataloge.map((k) => ({ id: k.id, titel: k.titel,
      beschreibung: k.beschreibung, created_by_name: k.created_by_name, created_at: k.created_at, updated_at: k.updated_at,
      leistungen_anzahl: k.leistungen.length, darf_bearbeiten: false })) })],
    ["GET", /^\/api\/pruefungen\/kataloge\/(\d+)$/, (m, body, z) => {
      const k = z.kataloge.find((x) => x.id === +m[1]);
      if (!k) return { status: 404, error: "Katalog nicht gefunden" };
      return { katalog: { id: k.id, titel: k.titel, beschreibung: k.beschreibung, created_by_name: k.created_by_name,
        created_at: k.created_at, updated_at: k.updated_at, leistungen_anzahl: k.leistungen.length, darf_bearbeiten: false,
        leistungen: k.leistungen.map((p) => ({ id: p.id, bezeichnung: p.bezeichnung, beschreibung_md: p.beschreibung_md,
          zeitansatz_sekunden: p.zeitansatz_sekunden, sortierung: p.sortierung, kriterien: p.kriterien.slice() })) } };
    }],
  ];

  /* --- Ziele, die erst nach einer Aktion feststehen ----------------------------------------------------------------- */
  // Die Seite zeichnet nach jedem Laden und Speichern neu und schließt dabei Dialoge – ein Ziel zählt erst, wenn sie
  // damit fertig ist und der Dialog samt seinem Verlaufseintrag weg ist (S.dialogVerlauf; das Zurück stellt sonst den
  // Bildlauf nach dem Hinrollen noch einmal um); sonst stünde die Blase kurz an einem Element, das gleich ersetzt wird.
  const da = (el) => Boolean(el && el.getClientRects().length && !el.closest("[hidden], [inert]"));
  const ohneDialog = () => !document.querySelector("dialog[open]")
    && !(history.state && typeof history.state.stroemisOverlay === "number");
  const sichtbares = (sel) => [...document.querySelectorAll(sel)].find(da) || null;
  // Eine Liste, die nicht mehr „Wird geladen …“ zeigt.
  const geladen = (sel) => () => { const el = sichtbares(sel); return el && !el.querySelector(":scope > p.help") ? el : null; };
  // Zeile der eben angelegten Person (Tabelle am Rechner) bzw. der Kopf ihrer Karte (Telefon – die ganze Karte passte
  // neben der Leiste der Führung nicht ins Bild).
  const neuePerson = () => {
    if (!angelegt || !ohneDialog()) return null;
    const zeile = sichtbares(`.tn-desktop tr[data-tid="${angelegt}"]`);
    const knopf = zeile ? null : sichtbares(`.tn-mobil [data-tid="${angelegt}"]`);
    return zeile || (knopf ? knopf.closest(".tn-kopf") : null);
  };
  // Der Stand unter dem Kasten, der eben abgehakt wurde – erst, wenn er nicht mehr „Wird gespeichert …“ sagt.
  const abgehakterStand = () => {
    const cb = abgehakt && sichtbares(`input[data-vk][data-tid="${abgehakt.tid}"][data-vid="${abgehakt.vid}"]`);
    const stand = cb ? cb.closest(".vk, .vk-zeile").querySelector(".vk-stand") : null;
    return stand && !stand.classList.contains("speichert") ? stand : null;
  };
  // Die bewertete Zelle (Matrix: der Knopf selbst, „je Leistung“: die Zeile mit der Zelle darin), sobald sie nicht mehr
  // „offen“ ist und der Dialog zu.
  const bewerteteZelle = () => {
    const el = ohneDialog() ? sichtbares(zelle) : null;
    return el && !el.matches(".st-offen") && !el.querySelector(".st-offen") ? el : null;
  };
  // Das Ergebnis der Person in „je Teilnehmende“, sobald es vermerkt ist.
  const vermerkt = () => {
    const el = ohneDialog() ? sichtbares(".tn-block .erg-block") : null;
    return el && el.querySelector(".erg-knopf.sel") ? el : null;
  };
  const kasten = `input[data-vk][data-tid="${TN[0]}"][data-vid="${VOR[0]}"]`;
  const zelle = `[data-act=zelle][data-tid="${TN[0]}"][data-lid="${LEI[0]}"]`;
  const titelLink = `tr[data-id="${LG}"] a.titel`;
  const ergebnisKnopf = ".erg-knopf[data-act=tn-ergebnis][data-erg=bestanden]";
  // Anlegen-Knöpfe heißen bis 600 px Breite „+ XY“, sonst „XY anlegen“ (app.css, .k-plus/.k-anlegen) – der Text der
  // Blase nennt, was dasteht (deshalb als Getter: gelesen, wenn die Blase zeichnet).
  const anlegen = (wort) => (window.matchMedia("(max-width: 600px)").matches ? `„+ ${wort}“` : `„${wort} anlegen“`);

  /* Jedes Ziel kommt ohne weichen Bildlauf ins Bild, am Telefon über der Leiste der Führung. Die Führung rollt es sonst
     weich (und mittig im ganzen Fenster, also teils unter die Leiste) und meldet den Schritt schon bereit, solange es
     noch unterwegs ist – der Durchlauftest prüfte die Lage dann zu früh und tippte daneben (Bewertungsdialog, Dialog
     „Lehrgang anlegen“, Reiter am Telefon). Für das Grundgerüst: einfuehrung.js sollte das Ende des Bildlaufs abwarten
     und die Leiste mitrechnen (scroll-padding-bottom); dann kann das hier weg. */
  const insBild = (ziel) => () => {
    const el = typeof ziel === "function" ? ziel() : sichtbares(ziel);
    if (!el) return null;
    const wurzel = document.documentElement;
    // Die Leiste wächst mit dem Text des nächsten Schritts – mindestens ein gutes Drittel des Fensters einplanen.
    const leiste = window.innerWidth < 600 ? Math.max(Math.round(window.innerHeight * 0.36),
      parseFloat(getComputedStyle(wurzel).getPropertyValue("--fuehrung-hoehe")) || 0) : 0;
    const imDialog = Boolean(el.closest("dialog"));
    const r = el.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight - leiste) {
      // Ein offener Dialog endet über der Leiste (app.css) und schrumpft mit ihr – dort an den oberen Rand.
      el.scrollIntoView({ block: imDialog && leiste ? "start" : "center", behavior: "auto" });
      // Auf der Seite noch um die halbe Leiste höher.
      if (leiste && !imDialog) {
        window.scrollBy({ top: Math.min(leiste / 2, Math.max(0, el.getBoundingClientRect().top - 80)), behavior: "auto" });
      }
    }
    return el;
  };
  const teile = {
    grund: { ablaeufe: [
      { titel: "Lehrgang öffnen", start: "/riegenkarten", schritte: [
        { ziel: geladen("#lg-liste"), text: "Hier stehen die Lehrgänge, in denen du eingetragen bist." },
        { ziel: titelLink, text: "Öffne den Übungslehrgang.", warten: { klick: titelLink } },
        { ziel: ".c-tabs.reiter", text: "Teilnehmende, Leistungen, Bewertung und Mängel stehen in Reitern." },
      ] },
      { titel: "Voraussetzung abhaken", start: `/riegenkarten/${LG}#teilnehmer`, schritte: [
        { ziel: kasten, text: "Hak eine Voraussetzung ab – sie wird sofort gespeichert.",
          warten: { anfrage: /^PUT \/api\/pruefungen\/teilnehmer\/\d+\/voraussetzungen\/\d+$/ }, probe: { klick: kasten } },
        { ziel: abgehakterStand, text: "Darunter steht, wer wann abgehakt hat – jede Änderung bleibt im Verlauf nachlesbar." },
      ] },
      { titel: "Bewerten", start: `/riegenkarten/${LG}#bewertung`, schritte: [
        // Folgt der Ablauf auf derselben Seite, bleibt der Reiter stehen – der Wechsel gehört deshalb dazu.
        { ziel: "[data-reiter=bewertung]", text: "Bewertet wird im Reiter „Bewertung“. Tippe darauf.",
          warten: { klick: "[data-reiter=bewertung]" } },
        { ziel: zelle, text: "Tippe auf eine Zelle, um die Leistung zu bewerten.", warten: { klick: zelle } },
        { ziel: "#bw-kriterien .krit-zeile", text: "Kreuz die Kriterien an.", warten: { klick: "#bw-kriterien .krit-zeile" } },
        { ziel: "#bw-wahl button[data-erg=bestanden]", text: "Wähle „bestanden“. Bei „mangelhaft“ ist ein Kommentar Pflicht.",
          warten: { klick: "#bw-wahl button[data-erg=bestanden]" } },
        { ziel: "#bw-save", text: "Speichere die Bewertung.",
          warten: { anfrage: `POST ${API}/teilnehmer/${TN[0]}/leistungen/${LEI[0]}/versuche` }, probe: { klick: "#bw-save" } },
        { ziel: bewerteteZelle, text: "In der Zelle steht jetzt, wer wann abgenommen hat." },
      ] },
      { titel: "Mängel", start: `/riegenkarten/${LG}#maengel`, schritte: [
        { ziel: "[data-reiter=maengel]", text: "Tippe auf den Reiter „Mängel“.", warten: { klick: "[data-reiter=maengel]" } },
        { ziel: geladen("#maengel-liste"), text: "Hier stehen alle mangelhaften Versuche zum Nacharbeiten." },
      ] },
    ] },
    leitung: { ablaeufe: [
      { titel: "Teilnehmende eintragen", start: `/riegenkarten/${LG}#teilnehmer`, schritte: [
        { ziel: "[data-act=tn-neu]", get text() { return `Als Leitung trägst du Teilnehmende ein. Tippe auf ${anlegen("Teilnehmende")}.`; },
          warten: { klick: "[data-act=tn-neu]" } },
        { ziel: "#tn-vorname", text: "Trag den Vornamen ein, hier „Teilnehmer“.", warten: { wert: ["#tn-vorname", /\S/] },
          probe: { tippen: ["#tn-vorname", "Teilnehmer"] } },
        { ziel: "#tn-name", text: "Und den Nachnamen, hier „Übung 4“. Geburtsdatum und Gliederung sind freiwillig.",
          warten: { wert: ["#tn-name", /\S/] }, probe: { tippen: ["#tn-name", "Übung 4"] } },
        { ziel: "#tn-save", text: "Leg die Person an.", warten: { anfrage: `POST ${API}/lehrgaenge/${LG}/teilnehmer` },
          probe: { klick: "#tn-save" } },
        { ziel: neuePerson,
          text: "Die Person steht jetzt in der Liste. Viele auf einmal übernimmst du über „Mehr“ → „Import“ aus der Excel-Teilnehmerliste." },
      ] },
      { titel: "Lehrgangsergebnis", start: `/riegenkarten/${LG}#bewertung`, schritte: [
        { ziel: "[data-reiter=bewertung]", text: "Das Lehrgangsergebnis vermerkst du in der Bewertung. Tippe auf den Reiter „Bewertung“.",
          warten: { klick: "[data-reiter=bewertung]" } },
        { ziel: "[data-act=bew-ansicht][data-a=tn]", text: "Wechsle zur Ansicht „je Teilnehmende“.",
          warten: { klick: "[data-act=bew-ansicht][data-a=tn]" } },
        { ziel: ergebnisKnopf, text: "Am Ende des Lehrgangs vermerkst du hier das Ergebnis der Person. Tippe auf „bestanden“.",
          warten: { klick: ergebnisKnopf } },
        { ziel: "#c-ok", text: "Mit dem Ergebnis ist die Person eingefroren. Bestätige mit „Vermerken“.",
          warten: { anfrage: /^PUT \/api\/pruefungen\/teilnehmer\/\d+\/ergebnis$/ }, probe: { klick: "#c-ok" } },
        { ziel: vermerkt,
          text: "Bewertungen, Häkchen und Kommentar dieser Person lassen sich jetzt nicht mehr ändern. Ein zweiter Tipp auf „bestanden“ hebt das Ergebnis wieder auf." },
      ] },
    ] },
    redakteur: { ablaeufe: [
      { titel: "Lehrgang anlegen", start: "/riegenkarten", schritte: [
        { ziel: "[data-act=lg-neu]", get text() { return `Als Redakteur legst du Lehrgänge an. Tippe auf ${anlegen("Lehrgang")}.`; },
          warten: { klick: "[data-act=lg-neu]" } },
        { ziel: "#lg-titel", text: "Gib dem Lehrgang einen Titel, hier „Übungslehrgang 2“.", warten: { wert: ["#lg-titel", /\S{3}/] },
          probe: { tippen: ["#lg-titel", "Übungslehrgang 2"] } },
        { ziel: () => { const f = document.getElementById("lg-von"); return f ? f.closest(".field-row") : null; },
          text: "Nummer, Ort und Zeitraum sind freiwillig – ohne Datum steht der Lehrgang in der Liste ganz unten." },
        { ziel: "#ausb-plus",
          get text() { return `Du stehst schon als Leitung darin. Wer mitprüft, kommt als weitere Person dazu – tippe auf ${anlegen("Person")}.`; },
          warten: { klick: "#ausb-plus" } },
        { ziel: ".ausb-suche", text: "Such „Übungsperson“ – Ausbilder brauchen ein Konto mit Stufe in den Riegenkarten.",
          warten: { da: ".ausb-treffer .ausb-konto" }, probe: { tippen: [".ausb-suche", "Übungsperson"] } },
        { ziel: ".ausb-treffer .ausb-konto", text: "Wähle „Übungsperson A“.", warten: { klick: ".ausb-treffer .ausb-konto" } },
        { ziel: "#lg-katalog", text: "Prüfungsleistungen kannst du einmalig aus einem Katalog übernehmen, etwa aus dem Übungskatalog." },
        { ziel: "#lg-save", text: "Leg den Lehrgang an.", warten: { anfrage: `POST ${API}/lehrgaenge` }, probe: { klick: "#lg-save" } },
        { ziel: () => (ohneDialog() && sichtbares("#reiter-inhalt .leerzustand") ? sichtbares("[data-reiter=teilnehmer]") : null),
          text: "Der neue Lehrgang beginnt bei den Teilnehmenden: Als Leitung legst du sie hier an oder importierst die Excel-Teilnehmerliste." },
      ] },
    ] },
  };
  Object.values(teile).forEach((t) => t.ablaeufe.forEach((a) => a.schritte.forEach((x) => { if (x.ziel) x.ziel = insBild(x.ziel); })));

  S.einfuehrung.modul("pruefungen", {
    bestand,
    antworten,
    // Druckansichten (…/druck) sind Seiten, keine Dateien: window.open meldet „In der Übung nicht verfügbar.“
    dateien: [],
    teile,
  });
})();
