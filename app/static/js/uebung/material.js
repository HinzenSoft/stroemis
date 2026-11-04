/* Übungsdatei der Einführung: Materialablage (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.1; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide; Durchläufe in tests/test_einfuehrung_material.py).

   Übungsbestand: die Gliederung „Übung – Gliederung“ mit den Ordnern „Übung – Lager“ und „Übung – Fahrzeug 1“ (dazu
   ihre Systemordner „Gesperrt“ und „Ausgesondert“), drei Produkte der Kategorie „Übung“ vom Hersteller „Übung“, drei
   Artikel (Ü-0001 einsatzbereit, Ü-0002 Prüfung fällig, Ü-0003 neu), ein Prüfformular mit drei Platzhalter-Punkten,
   Übungsperson A und B für Freigaben. Nur Platzhalter: keine echten Produkte, Hersteller, Prüfpunkte, Intervalle oder
   Lebensdauern – das Prüfintervall bleibt leer, die Fälligkeiten stehen als Tage um heute. Kennungen 900000001–900000099.

   Die Antworten bilden die Form der Schnittstellen (app/material/routes*.py, services/) nach, so weit material.js,
   suche.js, freigaben.js und global.js sie auf den Seiten der Abläufe lesen; was die Abläufe schreiben (Mangel,
   Prüfung, Artikel, Freigabe, Durchgang, Formular), spielen sie im Übungsbestand nach. Alles Übrige beantwortet
   einfuehrung.js mit „In der Übung nicht verfügbar.“ */
(function () {
  const API = "/api/material";
  const ID = {
    lager: 900000001, fahrzeug: 900000002, gliederung: 900000003, gesperrt: 900000004, ausgesondert: 900000005,
    gurt: 900000011, seil: 900000012, helm: 900000013, neuerArtikel: 900000014,
    pGurt: 900000021, pSeil: 900000022, pHelm: 900000023, kategorie: 900000031, formular: 900000041,
    punktJaNein: 900000051, punktText: 900000052, punktZahl: 900000053, punktNeu: 900000054,
    pruefung: 900000061, altGurt: 900000062, altSeil: 900000063, durchgang: 900000071, mangel: 900000081,
    personA: 900000091, personB: 900000092, freigabe: 900000093,
  };
  const BILD = { gurt: "/static/uebung/material/uebungsbild-4.jpg", seil: "/static/uebung/material/uebungsbild-5.jpg",
                 helm: "/static/uebung/material/uebungsbild-6.jpg", mangel: "/static/uebung/material/uebungsbild-7.jpg" };
  const PROTOKOLL = "/static/uebung/uebungsdatei.pdf";
  // Übungsunterschrift („Übung“ mit Strich) – für den Dialog „Prüfung festschreiben“ und das Protokoll.
  const UNTERSCHRIFT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPAAAABQCAQAAACNQDD3AAAFeUlEQVR42u2ae2xURRSHv0UKW5S3FUR6QoTVIqYqaEzEECoEpSoFgsSoYKi2SEkkVTTxgdJoI0F5BATxFSCgoCEEgkYFohGDCIRXQQKGaBxII1gQjEiBtusftHdnt/eWbnfJur3n6z/nzMyde+f+7pw5M1tQFEVRFEVRFEVRFEVRFEVRFEVRFEVRFCXtCCRysYTrjSxTJX34DYCz5hp9rf8f2ugrUIEVFVhRFEVJcRbtZMpO7nzZVifNtU75EiY75WPMOn35ugYrKrCiAqvAigqsqMCKCqyowEpyaZu6W0t/SsgjxEUq+YFVZnOjFvbRyBSzxKpZyeOOU2rm15eWsMgpHWE2yVWM41HuJIs6jvEti02F65Nk8ySjELpxmp2s4DMTlp+5pb76G/OAChy/vC9TVn/3doQIUSibmWSOJdTpP5bdUfqyhtsdP0SIInnLvNroSUopJ7PeySKffIqkgG5OgxMaouOnlPJGH9dwtklOQr1WW3Y/tljyNoz2FXkuRt65zHXkbeA+VtLV8apU4PgZ4lram7XSIYFeL1h2Gb1c28yU7pa8kyh1bVVAe9e4oAI3mzNMow8dyGEBYae0Py8lqf8gNcyiL0Fu40s7dPOgI28X3rZqfmIImdzAC1EfClzUJCt+ask3PwJwmGlynHKnZqrMMmeTco9nzXsAVEgB2xnklOc61kQis3k7eaYaqOQdqeQTq5+wzuD4WVYv7yVmc8SxuzI8KXc4zvsNpqnlc6smy7Ees7MC46zg5lN26z44MdbYjqlhteXmJeUOu0xdlNx28L4UoIMMjNSbbVFXb/CnwLVx9+8V3n6J8fdY9k1JGdlpzyfPcPLsDKfsQMzVh/0pcHWUl+nRKsPzCjwzU3uv2T0pI/NeOQMu9zkV0+Yvfwp8Jsrr7NGqq2Wf9GjTvokNTvAKJ4eBZsSmc74U2FyIEqynR7O+ln3Io03stR2bmE3N+UBawimPjxKgi1+TrB2WfY9HGztJ+s6jzV0xfj/XcF3nOWc7JWHsR6ix9t/R3OpXge3s8mm3UycJMcEKdGs8+pkY4z9s2dtcV+ps6x4BBiS+EzDn2BfpUgZG9T/erwIvpdJ65SskJtGSG9lgraGzjdcafLd9JizDI6dLwNeO9btVmi+RZx1ND6umXYtHv8rei1v9F1uHIf4S2FRTYrlj2S1PSUiCEpDOMlhms5+bIztR3myiqznygeRKe+klU1lrlW80kXV7S1TQXCb9pJ30kGKWR/XUcoGXW2njMNZKrmRKH5nBQloNcWejZr2U8brj5vCRR8NDjDU1nt2c5WqKKGpUfsE+izb7ZSuDHXeCFfy9tmXxjaVKZrDAcQsooNXRgvXLzKSYfy/TaBP3GtNE/XTcz5tLTPQh4dSYrVnDHndOkjLqd/nYtXyrjwUG8yE5LOW8R/U+xpgRnqvvJbYzwlrNG/bMo03M6zb7GEpFoz1qIYvj3Dd7jSRMMa/F/F4Upoz5vg3R9S/mKIXyIqPIYwC96UKAM/zJAXaz3hxsRgd/mz3Sn2d4hByCVFHBFyw1Lr+8mr0yiHGM5w56UsuvfMVCc0zsfet1ibwAU8cbsppJjCSbTvzB9yw0O+SJKMGV1oZMkbDz97zvQrQPyHU9eFGB02yeFlnztNAqv976n83oX7r8sga3EvZa9jwJso4TdGcY5dbZ+EFzIJ2HGPD1DA6w0/pXHjfqGGk2aohOU0yYya777Ej+PD295fV9kmV2MdRzjT3KQ2Zeuo8wgO+RNtzPGAaSTWcyOM8pjrKHjWwwtSl4mrAJqMCp/yiu4OFHcgVuqyK0bgIqQ+pnWcoFTte5YHQBSn2IVhF0NVMURVEURVEURVEURVEURVEURVEU5YrwHy1dXQZ5+M4LAAAAAElFTkSuQmCC";
  const STATUS = { ausgesondert: "ausgesondert", bald_faellig: "bald fällig", einsatzbereit: "einsatzbereit", gesperrt: "gesperrt",
                   lebensdauer: "Lebensdauer erreicht", neu: "neu", ueberfaellig: "überfällig" };
  const ORDNERARTEN = { fahrzeug: "Fahrzeug", gliederung: "Gliederung", persoenlich: "persönlich", set: "Set",
                        sonstiges: "sonstiges", standort: "Standort" };
  const PRUEFART = { eingang: "Eingangsprüfung", periodisch: "periodisch", ausserplanmaessig: "außerplanmäßig", reparatur: "nach Reparatur" };
  const SCHWELLE = 30;

  /* --- Hilfen ----------------------------------------------------------------------------------------------------- */
  // Was die Seite in der Übung darf: data-darf (Rechte des Teils, app/einfuehrung.py DARF_MATERIAL).
  const darf = () => { try { return JSON.parse(document.getElementById("mat").dataset.darf || "{}"); } catch (e) { return {}; } };
  const ordnerDarf = () => { const d = darf(); return { grund: Boolean(d.grund), lesen: Boolean(d.lesen), pruefen: Boolean(d.pruefen), verwalten: Boolean(d.verwalten) }; };
  const ich = () => (window.STROEMIS && window.STROEMIS.user) || { id: 0, name: "" };
  const tag = (plus) => {
    const d = new Date();
    d.setDate(d.getDate() + (plus || 0));
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  const jetzt = () => new Date().toISOString().replace(/\.\d+Z$/, "+00:00");
  const deTag = (iso) => iso.slice(0, 10).split("-").reverse().join(".");
  const nullen = () => ({ ausgesondert: 0, bald_faellig: 0, einsatzbereit: 0, gesperrt: 0, lebensdauer: 0, neu: 0, ueberfaellig: 0 });
  const kopie = (x) => JSON.parse(JSON.stringify(x));
  const sichtbar = (sel) => { const el = document.querySelector(sel); return Boolean(el && el.getClientRects().length && !el.closest("[hidden]")); };
  const ansicht = () => { const m = document.getElementById("mat"); return m ? m.dataset.ansicht : ""; };

  /* --- Übungsbestand ------------------------------------------------------------------------------------------------ */
  function ordner(id, name, kind, parent, position, system) {
    return { id, name, kind, parent_id: parent, position: position || 0, system_kind: system || null, description: "",
             interval_months: null, reminders_off: false, foto: null, original: null, vorschau: null, demo: false,
             created_at: "2026-01-01T00:00:00+00:00", updated_at: "2026-01-01T00:00:00+00:00" };
  }
  function produkt(id, model, bild) {
    return { id, model, manufacturer: "Übung", description: "", article_no: null, norm: "", category_id: ID.kategorie,
             category_name: "Übung", material_kind: "sonstiges", interval_months: null, lifetime_years: null,
             lifetime_source: "", laenge_moeglich: false, bestandteile: [], bild, original: bild, vorschau: bild,
             wiki_page_id: null, demo: false, created_at: "2026-01-01T00:00:00+00:00", updated_at: "2026-01-01T00:00:00+00:00" };
  }
  function artikel(id, nummer, produktId, folder, sn, zuletzt, faellig) {
    return { id, inventory_no: nummer, product_id: produktId, folder_id: folder, origin_folder_id: null, serial_no: sn,
             serial_generated: false, manufactured_on: null, purchased_on: null, first_use_on: null, retire_by: null,
             lock_state: "frei", lock_reason: "", last_inspected_on: zuletzt, next_due_on: faellig, length_m: null,
             notes: "Übung – kein echter Artikel.", maengel: [], mangel_eigen_offen: null,
             created_at: "2026-01-01T00:00:00+00:00", updated_at: "2026-01-01T00:00:00+00:00" };
  }
  const PUNKTE = [
    { id: ID.punktJaNein, position: 1, gruppe: "Platzhalter", text: "Platzhalter: Ja/Nein-Punkt", art: "yesno", soll: "ja", pflicht: true },
    { id: ID.punktText, position: 2, gruppe: "Platzhalter", text: "Platzhalter: Textpunkt", art: "text", soll: "", pflicht: false },
    { id: ID.punktZahl, position: 3, gruppe: "Platzhalter", text: "Platzhalter: Zahlpunkt", art: "number", soll: "", pflicht: true },
  ];
  // Ein Prüfpunkt einer Prüfung, vorbelegt wie auf dem Server: Befund „in Ordnung“, Ja/Nein mit dem Sollwert.
  function punktStand(p) {
    return { id: p.id, position: p.position, gruppe: p.gruppe, text: p.text, art: p.art, soll: p.soll, pflicht: p.pflicht,
             befund: "ok", wert: p.art === "yesno" ? p.soll : "", notiz: "", foto: null, unterschrift: null, nummern: [], bestandteil: false };
  }
  function protokoll(id, wann, anmeldung) {
    return { id: `P-ÜBUNG-${String(id).slice(-2)}`, url: `/materialablage/pruefung/${id}/pdf`, festgeschrieben: wann,
             anmeldung, bytes: 1109, sha256: "0".repeat(64), datei_sha256: "0".repeat(64) };
  }
  // Je Artikel mit Vergangenheit eine frühere, festgeschriebene Prüfung (Übung) – „Prüfungen“ am Artikel steht nicht leer.
  function altePruefung(id, artikelId, datum) {
    return { id, item_id: artikelId, art: "periodisch", entwurf: false, ergebnis: "einsatzbereit", datum, naechste: null,
             bemerkung: "", grund: "", pruefer: "Übungsperson B", pruefer_id: ID.personB, urkunde: "ÜBUNG",
             begonnen_am: `${datum}T08:00:00+00:00`, abgeschlossen_am: `${datum}T08:30:00+00:00`, round_id: null,
             punkte: PUNKTE.map(punktStand), protokoll: protokoll(id, `${datum}T08:30:00+00:00`, "uebung-b@example.invalid") };
  }
  function bestand() {
    return {
      ordner: [ordner(ID.gliederung, "Übung – Gliederung", "gliederung", null),
               ordner(ID.lager, "Übung – Lager", "standort", ID.gliederung, 0),
               ordner(ID.fahrzeug, "Übung – Fahrzeug 1", "fahrzeug", ID.gliederung, 1),
               ordner(ID.gesperrt, "Gesperrt", "sonstiges", ID.gliederung, 100000, "gesperrt"),
               ordner(ID.ausgesondert, "Ausgesondert", "sonstiges", ID.gliederung, 100001, "ausgesondert")],
      produkte: [produkt(ID.pGurt, "Übungsgurt", BILD.gurt), produkt(ID.pHelm, "Übungshelm", BILD.helm),
                 produkt(ID.pSeil, "Übungsseil", BILD.seil)],
      artikel: [artikel(ID.gurt, "Ü-0001", ID.pGurt, ID.fahrzeug, "Ü-SN-0001", tag(-60), tag(300)),
                artikel(ID.seil, "Ü-0002", ID.pSeil, ID.fahrzeug, "Ü-SN-0002", tag(-370), tag(-5)),
                artikel(ID.helm, "Ü-0003", ID.pHelm, ID.lager, "Ü-SN-0003", null, null)],
      formular: { id: ID.formular, titel: "Übungsformular", version: 1, aktiv: true, benutzt: false,
                  punkte: kopie(PUNKTE) },
      pruefungen: [altePruefung(ID.altGurt, ID.gurt, tag(-60)), altePruefung(ID.altSeil, ID.seil, tag(-370))],
      freigaben: [],
      durchgaenge: [],
      naechsteNummer: 4,
    };
  }

  /* --- Sichten auf den Bestand (Form wie bestand.py, katalog.py, pruefung.py, freigaben.py) --------------------------- */
  const ordnerVon = (z, id) => z.ordner.find((o) => o.id === id) || null;
  const produktVon = (z, id) => z.produkte.find((p) => p.id === id) || null;
  const artikelVon = (z, id) => z.artikel.find((a) => a.id === id) || null;
  const pruefungVon = (z, id) => z.pruefungen.find((p) => p.id === id) || null;
  function pfad(z, id) {
    const weg = [];
    for (let o = ordnerVon(z, id); o; o = ordnerVon(z, o.parent_id)) weg.unshift({ id: o.id, kind: o.kind, name: o.name, system_kind: o.system_kind });
    return weg;
  }
  const pfadText = (z, id) => pfad(z, id).map((o) => o.name).join(" / ");
  function status(a) {
    if (a.lock_state === "ausgesondert") return "ausgesondert";
    if (a.lock_state !== "frei") return "gesperrt";
    if (!a.last_inspected_on) return "neu";
    if (a.next_due_on && a.next_due_on < tag(0)) return "ueberfaellig";
    if (a.next_due_on && a.next_due_on <= tag(SCHWELLE)) return "bald_faellig";
    return "einsatzbereit";
  }
  // Der Ordner und alles darunter.
  function zweig(z, id) {
    const ids = new Set([id]);
    let mehr = true;
    while (mehr) {
      mehr = false;
      z.ordner.forEach((o) => { if (ids.has(o.parent_id) && !ids.has(o.id)) { ids.add(o.id); mehr = true; } });
    }
    return ids;
  }
  function zaehlung(z, id, direkt) {
    const ids = direkt ? new Set([id]) : zweig(z, id);
    const n = nullen();
    z.artikel.forEach((a) => { if (ids.has(a.folder_id)) n[status(a)] += 1; });
    return n;
  }
  const summe = (n) => Object.entries(n).reduce((s, [k, v]) => s + (k === "ausgesondert" ? 0 : v), 0);
  function ordnerJson(z, o) {
    const zz = zaehlung(z, o.id);
    return Object.assign({}, o, { darf: ordnerDarf(), zaehlung: zz, direkt: zaehlung(z, o.id, true), bestand: summe(zz) });
  }
  const offenerEntwurf = (z, a) => z.pruefungen.find((p) => p.item_id === a.id && p.entwurf) || null;
  function artikelKurz(z, a, mitPfad) {
    const p = produktVon(z, a.product_id);
    const e = offenerEntwurf(z, a);
    const st = status(a);
    const k = { id: a.id, inventory_no: a.inventory_no, serial_no: a.serial_no, serial_generated: false, folder_id: a.folder_id,
                product_id: a.product_id, manufacturer: p.manufacturer, model: p.model, description: p.description,
                article_no: p.article_no, material_kind: p.material_kind, kategorie: { id: ID.kategorie, name: "Übung" },
                vorschau: p.vorschau, lock_state: a.lock_state, last_inspected_on: a.last_inspected_on, next_due_on: a.next_due_on,
                retire_by: null, length_m: null, laenge_text: "", status: st, status_text: STATUS[st],
                mangel: a.maengel.some((m) => m.offen), aussonderung_empfohlen: false, rueckruf: null, zugeordnet_name: null,
                entwurf: e ? { id: e.id, pruefer: e.pruefer, pruefer_id: e.pruefer_id } : null, demo: false, darf: ordnerDarf() };
    if (mitPfad) k.pfad = pfadText(z, a.folder_id);
    return k;
  }
  function pruefungKurz(x) {
    return { id: x.id, item_id: x.item_id, art: x.art, art_text: PRUEFART[x.art] || x.art, entwurf: x.entwurf, ergebnis: x.ergebnis,
             ergebnis_text: x.ergebnis ? STATUS[x.ergebnis] || x.ergebnis : "", datum: x.datum, naechste: x.naechste,
             bemerkung: x.bemerkung, grund: x.grund, pruefer: x.pruefer, pruefer_id: x.pruefer_id, urkunde: x.urkunde,
             begonnen_am: x.begonnen_am, abgeschlossen_am: x.abgeschlossen_am, round_id: x.round_id, basis_id: null,
             berichtigt: null, berichtigt_durch: null, protokoll: x.protokoll };
  }
  const formularKurz = (z) => ({ id: z.formular.id, title: z.formular.titel, version: z.formular.version, punkte: z.formular.punkte.length,
                                 quelle: "Kategorie „Übung“" });
  const OHNE_INTERVALL = { monate: null, quelle: "", hersteller: [null, null], organisation: [null, null] };
  function artikelVoll(z, a) {
    const p = produktVon(z, a.product_id);
    const st = status(a);
    const e = offenerEntwurf(z, a);
    const gl = ordnerVon(z, ID.gliederung);
    return Object.assign(artikelKurz(z, a), {
      origin_folder_id: a.origin_folder_id, manufactured_on: null, purchased_on: null, first_use_on: null, notes: a.notes,
      lock_reason: a.lock_reason, pfad: pfad(z, a.folder_id), gliederung: { id: gl.id, kind: gl.kind, name: gl.name, system_kind: null },
      produkt: Object.assign({}, p, { intervall: { monate: null, quelle: "" } }), produkt_aenderbar: false, produkt_beantragbar: false,
      intervall: OHNE_INTERVALL, interval_months: null, lebensdauer: null, laenge_moeglich: false, formular: formularKurz(z),
      dokumente: [], rueckrufe: [], antraege: [], antrag_offen: false, darf_antrag: false, darf_entscheiden: false, darf_loeschen: false,
      stammdaten_fest: true, bestandteile: [], bestandteile_direkt: false,
      aussondern: { ok: false, grund: "In der Übung wird nichts ausgesondert." }, aussonderung_empfohlen: null, zugeordnet: null,
      durchgang: null, entwurf: e ? { id: e.id, pruefer: e.pruefer, pruefer_id: e.pruefer_id, seit: e.begonnen_am } : null,
      maengel: kopie(a.maengel), mangel_eigen_offen: a.mangel_eigen_offen, mangel_nur_gemeldet: a.maengel.some((m) => m.offen),
      pruefarten: st === "neu" ? { arten: ["eingang"], vorschlag: "eingang" }
        : { arten: ["periodisch", "ausserplanmaessig", "reparatur"], vorschlag: st === "ueberfaellig" || st === "bald_faellig" ? "periodisch" : "ausserplanmaessig" },
      pruefungen: z.pruefungen.filter((x) => x.item_id === a.id && !x.entwurf).map(pruefungKurz).reverse(),
      journal: [], qr_adresse: "Übung – hier stünde die Adresse vom Etikett", stand: "uebung",
    });
  }
  function pruefungVoll(z, x) {
    const a = artikelVon(z, x.item_id);
    const p = produktVon(z, a.product_id);
    return Object.assign(pruefungKurz(x), {
      artikel: Object.assign(artikelKurz(z, a), { pfad: pfad(z, a.folder_id), origin_folder_id: a.origin_folder_id }),
      produkt: { id: p.id, manufacturer: p.manufacturer, model: p.model, description: p.description, article_no: p.article_no,
                 material_kind: p.material_kind, norm: p.norm, name: `${p.manufacturer} ${p.model}`, demo: false },
      formular: { id: z.formular.id, titel: z.formular.titel, version: z.formular.version }, punkte: kopie(x.punkte),
      arten: x.entwurf ? artikelVoll(z, a).pruefarten.arten : [x.art], anhaenge: [], dokumente: [], anleitung: null, darf: ordnerDarf(),
      eigen: x.pruefer_id === ich().id, durchgang: null, einsatzbereit_gesperrt: [], freipruefung: x.entwurf && a.lock_state !== "frei",
      grund_berichtigung: "", intervall: OHNE_INTERVALL, laenge: { moeglich: false, text: "", wert: null }, lebensdauer: null,
      maengel: kopie(a.maengel.filter((m) => m.offen)), prueftag: x.datum, vorschlag_naechste: null,
      unterschrift: x.entwurf ? null : UNTERSCHRIFT, berichtigbar: { ok: false, grund: "In der Übung wird nichts berichtigt." },
    });
  }
  function startJson(z) {
    const n = nullen();
    z.artikel.forEach((a) => { n[status(a)] += 1; });
    const faellig = z.artikel.filter((a) => ["ueberfaellig", "neu", "bald_faellig", "lebensdauer"].includes(status(a)));
    const zeilen = z.ordner.filter((o) => !o.system_kind).map((o) => {
      const zz = zaehlung(z, o.id);
      const ids = zweig(z, o.id);
      const tage = z.artikel.filter((a) => ids.has(a.folder_id) && ["einsatzbereit", "bald_faellig", "ueberfaellig"].includes(status(a)))
        .sort((x, y) => (x.next_due_on < y.next_due_on ? -1 : 1));
      return { id: o.id, name: o.name, kind: o.kind, parent_id: o.parent_id, tiefe: o.parent_id ? 1 : 0, demo: false,
               unterordner: z.ordner.filter((x) => x.parent_id === o.id && !x.system_kind).length, bestand: summe(zz), zaehlung: zz,
               naechste: tage.length ? tage[0].next_due_on : null, naechste_status: tage.length ? status(tage[0]) : null };
    });
    return { antraege_offen: 0, aussonderung_empfohlen: [], bestand: summe(n), darf: darf(), erinnerungen: null,
             faellig_gesamt: faellig.length, gliederungen: [ordnerJson(z, ordnerVon(z, ID.gliederung))],
             maengel: [], maengel_gesamt: 0, mailfehler: null, meine_psa: null, meldungen_offen: null, nacharbeit: [],
             naechste: faellig.map((a) => artikelKurz(z, a, true)), ordner_uebersicht: zeilen, rueckrufe: [],
             schwelle_tage: SCHWELLE, status_text: STATUS, zaehlung: n };
  }
  function ordnerSeite(z, id, url) {
    const o = ordnerVon(z, id);
    if (!o) return { status: 404, error: "Diesen Ordner gibt es in der Übung nicht." };
    const q = url.searchParams;
    let liste = z.artikel.filter((a) => a.folder_id === id);
    if (q.get("status")) liste = liste.filter((a) => q.get("status").split(",").includes(status(a)));
    const gl = ordnerVon(z, ID.gliederung);
    return { ordner: Object.assign(ordnerJson(z, o), {
      pfad: pfad(z, id), gliederung: { id: gl.id, kind: gl.kind, name: gl.name, system_kind: null },
      unterordner: z.ordner.filter((x) => x.parent_id === id).map((x) => ordnerJson(z, x)),
      artikel: liste.map((a) => artikelKurz(z, a)), artikel_gesamt: liste.length, seite: 1, pro_seite: 200,
      kategorien: liste.length ? [{ id: ID.kategorie, n: liste.length, name: "Übung", pfad: "Übung" }] : [],
      empfohlen: 0, erinnerungen: { aus: false, eigen: false, geerbt_von: null }, intervall: { monate: null }, nacharbeit: 0,
      journal: [], sammelprotokolle: [] }) };
  }
  function produktListe(z, url) {
    const q = (url.searchParams.get("q") || "").trim().toLowerCase();
    const liste = z.produkte.filter((p) => !q || `${p.manufacturer} ${p.model} ${p.description}`.toLowerCase().includes(q))
      .map((p) => Object.assign({}, p, { intervall: { monate: null, quelle: "" }, bestand: z.artikel.filter((a) => a.product_id === p.id).length }));
    return { produkte: liste, gesamt: liste.length, seite: 1, pro_seite: 50 };
  }
  function produktVoll(z, id) {
    const p = produktVon(z, id);
    if (!p) return { status: 404, error: "Dieses Produkt gibt es in der Übung nicht." };
    const n = z.artikel.filter((a) => a.product_id === id).length;
    return { produkt: Object.assign({}, p, { intervall: { monate: null, quelle: "" }, artikel_gesamt: n, bestand: n, dokumente: [],
      kategorie_dokumente: [], kategorie_pfad: [{ id: ID.kategorie, name: "Übung" }], formular: formularKurz(z), formulare: [],
      journal: [], loeschbar: false, rueckrufe: [], stueckliste_grenzen: { anzahl: 20, bezeichnung: 120, positionen: 30 } }) };
  }
  function kategorien(z) {
    return { kategorien: [{ id: ID.kategorie, name: "Übung", norm: "", parent_id: null, position: 0, demo: false,
                            aktives_formular: z.formular.id, formulare: 1, produkte: z.produkte.length, items_have_length: false,
                            laenge_wirksam: false, default_interval_months: null, default_lifetime_years: null, default_material_kind: null }],
             materialarten: { metall_hardware: "Metall", sonstiges: "sonstiges", textil: "textil" } };
  }
  function formularVoll(z) {
    const f = z.formular;
    const ziel = { art: "kategorie", id: ID.kategorie, pfad: [{ id: ID.kategorie, name: "Übung" }] };
    const kopf = { id: f.id, version: f.version, titel: f.titel, aktiv: f.aktiv, benutzt: f.benutzt, aenderbar: !f.benutzt, demo: false,
                   kategorie_id: ID.kategorie, produkt_id: null, gueltig_ab: "2026-01-01", wiki: null, wiki_aendern: false, ziel,
                   created_at: "2026-01-01T00:00:00+00:00", updated_at: "2026-01-01T00:00:00+00:00" };
    return { editoren: { date: "Datum", laenge: "Länge (m)", number: "Zahl", photo: "Foto", signature: "Unterschrift", text: "Text", yesno: "Ja/Nein" },
             formular: Object.assign({}, kopf, { punkte: kopie(f.punkte), journal: [],
                                                 versionen: [Object.assign({}, kopf, { punkte_anzahl: f.punkte.length })] }) };
  }
  // Personen für Freigaben: Übungsperson A (mit Prüfer-Qualifikation) und B.
  const PERSONEN = [{ id: ID.personA, name: "Übungsperson A", gliederung: "Übung – Gliederung", qualifiziert: true, grundrecht_ueberall: false },
                    { id: ID.personB, name: "Übungsperson B", gliederung: "Übung – Gliederung", qualifiziert: false, grundrecht_ueberall: false }];
  const konto = (p) => ({ id: p.id, name: p.name, gliederung: p.gliederung, aktiv: true, zugang: true, haekchen: p.qualifiziert, qualifiziert: p.qualifiziert });
  // Die eigene Verwalterfreigabe an der Gliederung (geerbt in allen Ordnern darunter).
  function eigeneFreigabe(z) {
    const du = { id: ich().id, name: ich().name || "Du", gliederung: "Übung – Gliederung", qualifiziert: false };
    return { id: ID.freigabe + 6, recht: "verwalten", bis: null, gueltig: true, wirkt: true, wirkt_nicht: null, aenderbar: false,
             entziehbar: false, eigen: true, grundrecht_dort: true, laeuft_ab_in_tagen: null, traegt_pruefen: 0, konto: konto(du),
             ordner: { id: ID.gliederung, pfad: pfadText(z, ID.gliederung) }, seit: "2026-01-01T00:00:00+00:00", vergeben_von: "Übung" };
  }
  function freigabenListe(z, id) {
    const o = ordnerVon(z, id) || ordnerVon(z, ID.fahrzeug);
    const kette = pfad(z, o.id).map((x) => x.id).reverse();
    return { alles: Boolean(darf().alles), ordner: { id: o.id, name: o.name, pfad: pfadText(z, o.id), gliederung: o.kind === "gliederung" },
             anker_vorgabe: o.id, anker_wahl: kette.map((k) => ({ id: k, pfad: pfadText(z, k), ende: null, gliederung: ordnerVon(z, k).kind === "gliederung" })),
             kette, direkt: z.freigaben.filter((f) => f.ordner.id === o.id), geerbt: o.id === ID.gliederung ? [] : [eigeneFreigabe(z)],
             unten: [], verlauf: [], laeuft_ab: 0,
             grenzen: { heute: tag(0), pruefen_max: tag(730), vorgabe_bis: `${new Date().getFullYear() + 1}-12-31` } };
  }
  function durchgangVoll(z, d) {
    const ids = zweig(z, d.folder_id);
    const liste = z.artikel.filter((a) => ids.has(a.folder_id) && a.lock_state !== "ausgesondert");
    return Object.assign({}, d, { darf: ordnerDarf(), pfad: pfad(z, d.folder_id), ordner: pfadText(z, d.folder_id),
      zaehlung: { gesamt: liste.length, offen: liste.length, in_pruefung: 0, erledigt: 0, ausgenommen: 0 },
      artikel: liste.map((a) => Object.assign(artikelKurz(z, a, true), { zustand: "offen", zustand_text: "offen", ausnahme: null,
                                                                       pruefung: null, sichtbar: true })),
      abgebrochen: false, abschliessbar: false, geschlossen_am: null, geschlossen_von: "", loeschbar: true, offen: true,
      protokoll: null, pruefer: [], set_ordner: { anzahl: 0, mit_pruefung: 0 }, set_protokolle: [] });
  }
  const durchgangKurz = (z, d) => { const v = durchgangVoll(z, d); delete v.artikel; delete v.pfad; return v; };
  const fehlt = (was) => ({ status: 404, error: `${was} gibt es in der Übung nicht.` });

  /* --- Antworten ---------------------------------------------------------------------------------------------------- */
  const nr = (m, i) => Number(m[i || 1]);
  const antworten = [
    // Seitenleiste, Übersicht, Prüfungen
    ["GET", `${API}/ordner`, (m, b, z) => ({ ordner: z.ordner.map((o) => ordnerJson(z, o)), ordnerarten: ORDNERARTEN })],
    ["GET", `${API}/start`, (m, b, z) => startJson(z)],
    ["GET", `${API}/durchgaenge`, (m, b, z, url) => ({ durchgaenge: url.searchParams.get("abgeschlossen") ? [] : z.durchgaenge.map((d) => durchgangKurz(z, d)) })],
    // „Meine Freigaben“ auf der Übersicht: an der Übungs-Gliederung das Grundrecht des Teils, beim Prüfer dazu die
    // Prüffreigabe (die Material-Verwaltung braucht keine).
    ["GET", `${API}/freigaben/meine`, (m, b, z) => {
      const d = darf();
      const zeile = (recht, n) => ({ id: ID.freigabe + n, recht, bis: null, gueltig: true, wirkt: true, wirkt_nicht: null, grundrecht_dort: true,
                                     laeuft_ab_in_tagen: null, verwalter: [], ordner: { id: ID.gliederung, pfad: pfadText(z, ID.gliederung) } });
      const freigaben = d.alles ? [] : [zeile(d.verwalten ? "verwalten" : "lesen", 6)].concat(d.pruefen ? [zeile("pruefen", 7)] : []);
      return { alles: Boolean(d.alles), qualifiziert: Boolean(d.qualifiziert), zugang: true, freigaben };
    }],
    ["GET", `${API}/antraege`, () => ({ zu_entscheiden: 0, antraege: [] })],
    ["GET", `${API}/entwuerfe`, (m, b, z) => ({ entwuerfe: z.pruefungen.filter((x) => x.entwurf).map((x) => Object.assign(pruefungKurz(x), {
      eigen: x.pruefer_id === ich().id, artikel: artikelKurz(z, artikelVon(z, x.item_id), true) })) })],
    ["GET", `${API}/faellig`, (m, b, z, url) => {
      const arten = (url.searchParams.get("status") || "ueberfaellig,lebensdauer,neu,bald_faellig").split(",");
      const liste = z.artikel.filter((a) => arten.includes(status(a))).map((a) => artikelKurz(z, a, true));
      return { artikel: liste, gesamt: liste.length, ordner: null, schwelle_tage: SCHWELLE };
    }],
    // Ordner und Freigaben
    ["GET", /^\/api\/material\/ordner\/(\d+)$/, (m, b, z, url) => ordnerSeite(z, nr(m), url)],
    ["GET", /^\/api\/material\/ordner\/(\d+)\/zugeordnete$/, () => ({ zugeordnete: [] })],
    ["GET", /^\/api\/material\/ordner\/(\d+)\/freigaben$/, (m, b, z) => freigabenListe(z, nr(m))],
    ["POST", /^\/api\/material\/ordner\/(\d+)\/freigaben$/, (m, body, z) => {
      const p = PERSONEN.find((x) => x.id === Number(body && body.user_id)) || PERSONEN[0];
      const o = ordnerVon(z, nr(m)) || ordnerVon(z, ID.fahrzeug);
      const neu = [];
      const zeile = (recht, bis) => ({ id: ID.freigabe + z.freigaben.length, recht, bis: bis || null, gueltig: true, wirkt: true,
        wirkt_nicht: null, aenderbar: true, entziehbar: true, eigen: false, grundrecht_dort: true, laeuft_ab_in_tagen: null,
        traegt_pruefen: 0, konto: konto(p), ordner: { id: o.id, pfad: pfadText(z, o.id) }, seit: jetzt(),
        vergeben_von: ich().name || "Du", notiz: String((body && body.notiz) || "") });
      [[body && body.grundrecht, body && body.grund_bis], [body && body.pruefen ? "pruefen" : null, body && body.pruefen_bis]]
        .forEach(([recht, bis]) => { if (recht) { const f = zeile(recht, bis); z.freigaben.push(f); neu.push(f); } });
      return { freigaben: neu, liste: freigabenListe(z, o.id), mail: false };
    }],
    ["GET", `${API}/nutzer`, (m, b, z, url) => {
      const q = (url.searchParams.get("q") || "").toLowerCase();
      return { nutzer: PERSONEN.filter((p) => p.name.toLowerCase().includes(q)).map((p) => Object.assign({}, p)), mehr: false };
    }],
    // Artikel, Suche, Mangel
    ["GET", /^\/api\/material\/artikel\/(\d+)$/, (m, b, z) => {
      const a = artikelVon(z, nr(m));
      return a ? { artikel: artikelVoll(z, a) } : fehlt("Diesen Artikel");
    }],
    ["GET", `${API}/suche`, (m, b, z, url) => {
      const q = (url.searchParams.get("q") || "").trim().toLowerCase();
      const treffer = q ? z.artikel.filter((a) => [a.inventory_no, a.serial_no].some((x) => String(x).toLowerCase().includes(q)))
        .map((a) => artikelKurz(z, a, true)) : [];
      return { treffer, gesamt: treffer.length, eindeutig: treffer.length === 1 ? treffer[0].id : null, exakt_lokal: false, global_angebot: false };
    }],
    ["POST", /^\/api\/material\/artikel\/(\d+)\/mangel$/, (m, body, z) => {
      const a = artikelVon(z, nr(m));
      const text = body && typeof body.get === "function" ? String(body.get("beschreibung") || "") : "";
      const fotos = body && typeof body.getAll === "function" ? body.getAll("fotos") : [];
      const wann = jetzt();
      const mangel = { id: ID.mangel, created_at: wann, description: text, erledigt: null, inhalt: true, lock_before: a.lock_state,
                       melder: ich().name || "Du", offen: true, wieder_offen: null,
                       fotos: fotos.map(() => ({ vorschau: BILD.mangel, web: BILD.mangel })) };
      const gesperrt = a.lock_state === "frei";
      // Wie mangel.melden: Der Artikel wird gesperrt und wandert in den Ordner „Gesperrt“ seiner Gliederung.
      if (gesperrt) Object.assign(a, { lock_state: "gesperrt", lock_reason: `Mangel gemeldet am ${deTag(tag(0))}`, origin_folder_id: a.folder_id, folder_id: ID.gesperrt });
      a.maengel.push(mangel);
      a.mangel_eigen_offen = wann;
      // Wie mit Mailserver: Die Quittung sagt, die Mail sei unterwegs – die Führung sagt dazu, dass in der Übung nichts hinausging.
      return { gesperrt, mail: true, mangel: kopie(mangel) };
    }],
    // Prüfung: beginnen, Punkte, Bemerkung, Unterschrift aus dem Profil, festschreiben
    ["POST", /^\/api\/material\/artikel\/(\d+)\/pruefungen$/, (m, body, z) => {
      const a = artikelVon(z, nr(m));
      if (!a) return fehlt("Diesen Artikel");
      const x = { id: ID.pruefung, item_id: a.id, art: (body && body.art) || "periodisch", entwurf: true, ergebnis: null, datum: tag(0),
                  naechste: null, bemerkung: "", grund: "", pruefer: ich().name || "Du", pruefer_id: ich().id,
                  urkunde: darf().urkundennummer || "ÜBUNG", begonnen_am: jetzt(), abgeschlossen_am: null, round_id: null, protokoll: null,
                  punkte: z.formular.punkte.map(punktStand) };
      z.pruefungen = z.pruefungen.filter((p) => p.id !== x.id).concat(x);
      return { pruefung: pruefungVoll(z, x) };
    }],
    ["GET", /^\/api\/material\/pruefungen\/(\d+)$/, (m, b, z) => {
      const x = pruefungVon(z, nr(m));
      return x ? { pruefung: pruefungVoll(z, x) } : fehlt("Diese Prüfung");
    }],
    ["PUT", /^\/api\/material\/pruefungen\/(\d+)$/, (m, body, z) => {
      const x = pruefungVon(z, nr(m));
      if (!x) return fehlt("Diese Prüfung");
      if (body && typeof body.bemerkung === "string") x.bemerkung = body.bemerkung;
      if (body && typeof body.art === "string") x.art = body.art;
      return { pruefung: pruefungVoll(z, x) };
    }],
    ["PUT", /^\/api\/material\/pruefungen\/(\d+)\/punkte\/(\d+)$/, (m, body, z) => {
      const x = pruefungVon(z, nr(m));
      const p = x && x.punkte.find((y) => y.id === nr(m, 2));
      if (!p) return fehlt("Diesen Prüfpunkt");
      ["wert", "befund", "notiz"].forEach((k) => { if (body && typeof body[k] === "string") p[k] = body[k]; });
      // Ja/Nein: der Wert entscheidet den Befund (Soll erfüllt = in Ordnung); „n. z.“ zurückgenommen = wieder der Sollwert.
      if (p.art === "yesno" && body && typeof body.wert === "string") p.befund = !p.soll || body.wert === p.soll ? "ok" : "mangel";
      if (p.art === "yesno" && body && body.befund === "ok") p.wert = p.wert || p.soll;
      return { punkt: kopie(p) };
    }],
    ["GET", `${API}/unterschrift`, () => ({ unterschrift: UNTERSCHRIFT })],
    ["POST", /^\/api\/material\/pruefungen\/(\d+)\/festschreiben$/, (m, body, z) => {
      const x = pruefungVon(z, nr(m));
      if (!x) return fehlt("Diese Prüfung");
      const a = artikelVon(z, x.item_id);
      const wann = jetzt();
      const d = body || {};
      Object.assign(x, { entwurf: false, ergebnis: d.ergebnis, bemerkung: d.bemerkung || "", grund: d.grund || "",
                         naechste: d.next_due_on || null, abgeschlossen_am: wann, protokoll: protokoll(x.id, wann, "") });
      a.last_inspected_on = tag(0);
      if (d.ergebnis === "einsatzbereit") {
        a.next_due_on = d.next_due_on || null;
        if (a.lock_state !== "frei") Object.assign(a, { lock_state: "frei", lock_reason: "", folder_id: a.origin_folder_id || a.folder_id, origin_folder_id: null });
        a.maengel.forEach((mg) => { if (mg.offen) Object.assign(mg, { offen: false, erledigt: { am: wann, pruefung: x.id, art: x.art } }); });
      } else if (a.lock_state === "frei") {
        Object.assign(a, { lock_state: "gesperrt", lock_reason: STATUS[d.ergebnis] || String(d.ergebnis || ""), origin_folder_id: a.folder_id, folder_id: ID.gesperrt });
      }
      return { pruefung: pruefungVoll(z, x) };
    }],
    // Artikel anlegen
    ["GET", `${API}/meldungen`, (m, b, z, url) => ({ meldungen: [], alle: Boolean(darf().katalog), bearbeiten: Boolean(darf().katalog),
      filter: url.searchParams.get("status") || "alle", offen: darf().katalog ? 0 : null })],
    ["GET", `${API}/produkte`, (m, b, z, url) => produktListe(z, url)],
    ["GET", /^\/api\/material\/produkte\/(\d+)$/, (m, b, z) => produktVoll(z, nr(m))],
    ["GET", `${API}/artikel/vorschlag`, () => ({ vorschlag: { bestandteile: [], intervall: OHNE_INTERVALL, lifetime_source: "",
      lifetime_years: null, material_kind: "sonstiges", next_due_on: null, retire_by: null, spaetestens: null } })],
    ["POST", `${API}/artikel`, (m, body, z) => {
      const d = body || {};
      const p = produktVon(z, Number(d.product_id)) || z.produkte[0];
      const nummer = String(z.naechsteNummer).padStart(4, "0");
      const a = artikel(ID.neuerArtikel, `Ü-${nummer}`, p.id, ordnerVon(z, Number(d.folder_id)) ? Number(d.folder_id) : ID.fahrzeug,
                        String(d.serial_no || "").trim() || `Ü-SN-${nummer}`, null, null);
      a.notes = String(d.notes || "");
      z.naechsteNummer += 1;
      z.artikel = z.artikel.filter((x) => x.id !== a.id).concat(a);
      return { artikel: artikelVoll(z, a), hinweise: [] };
    }],
    // Prüfdurchgang anlegen und ansehen
    ["POST", `${API}/durchgaenge`, (m, body, z) => {
      const d = { id: ID.durchgang, titel: String((body && body.titel) || "").trim() || "Übung",
                  folder_id: ordnerVon(z, Number(body && body.folder_id)) ? Number(body.folder_id) : ID.fahrzeug,
                  eroeffnet_am: tag(0), eroeffnet_von: ich().name || "Du" };
      z.durchgaenge = z.durchgaenge.filter((x) => x.id !== d.id).concat(d);
      return { durchgang: durchgangVoll(z, d) };
    }],
    ["GET", /^\/api\/material\/durchgaenge\/(\d+)$/, (m, b, z) => {
      const d = z.durchgaenge.find((x) => x.id === nr(m));
      return d ? { durchgang: durchgangVoll(z, d) } : fehlt("Diesen Prüfdurchgang");
    }],
    // Katalog, Produkt, Prüfformular
    ["GET", `${API}/kategorien`, (m, b, z) => kategorien(z)],
    ["GET", /^\/api\/material\/kategorien\/(\d+)\/dokumente$/, () => ({ dokumente: [] })],
    ["GET", `${API}/katalog/import/aktuell`, () => ({ auftrag: null })],
    ["GET", /^\/api\/material\/formulare\/(\d+)$/, (m, b, z) => (nr(m) === z.formular.id ? formularVoll(z) : fehlt("Dieses Formular"))],
    ["PUT", /^\/api\/material\/formulare\/(\d+)$/, (m, body, z) => {
      if (nr(m) !== z.formular.id) return fehlt("Dieses Formular");
      const f = z.formular;
      if (body && typeof body.titel === "string" && body.titel.trim()) f.titel = body.titel.trim();
      if (body && Array.isArray(body.punkte)) {
        let neu = ID.punktNeu;
        f.punkte = body.punkte.map((p, i) => ({ id: p.id || neu++, position: i + 1, gruppe: String(p.gruppe || ""), text: String(p.text || ""),
                                               art: p.art || "yesno", soll: String(p.soll || ""), pflicht: Boolean(p.pflicht) }));
      }
      return formularVoll(z);
    }],
  ];

  /* --- Abläufe (Bauvorlage 3.1) ------------------------------------------------------------------------------------- */
  // Mit „^=“: einfuehrung.js hängt beim Klick die Kennung an die Adresse eines Links („…?uebung=grund“).
  const artikelLink = (id) => `#mat-inhalt a[href^="/materialablage/artikel/${id}"]`;
  const imBaum = `#mat-baumnav a[href^="/materialablage/ordner/${ID.fahrzeug}"]`;
  const suchFeld = "#mat-suche input[name=q]";
  const produktLink = `#kat-liste a[href^="/materialablage/katalog/produkt/${ID.pGurt}"]`;
  const formularLink = `#mat-inhalt a[href^="/materialablage/katalog/formular/${ID.formular}"]`;
  const neuerPunkt = "#fp-tabelle tbody tr:last-child .fp-text";
  const rolle = "label.mf-vorlage:has(> input[value=pruefer])";
  const nachDialog = (sel) => () => {
    const st = history.state;
    if (document.querySelector("dialog[open]") || (st && typeof st === "object" && typeof st.stroemisOverlay === "number")) return null;
    return document.querySelector(sel);
  };
  // Die Prüfung ist bewertet, wenn kein Pflichtpunkt mehr ohne Befund ist (wie „Pflichtpunkte ohne Befund“ in der Leiste).
  const bewertet = (z) => {
    const x = (z.pruefungen || []).find((p) => p.id === ID.pruefung);
    return Boolean(x && x.punkte.every((p) => !p.pflicht || p.befund === "nicht_zutreffend" || String(p.wert || "").trim()));
  };

  const grund = { ablaeufe: [
    { titel: "Zurechtfinden", start: "/materialablage", schritte: [
      { ziel: ".mat-reiter", text: "Das ist die Materialablage. Oben wechselst du zwischen Übersicht, Prüfungen, Bestand und Katalog." },
      { ziel: ".mat-kachel", text: "Die Übersicht zeigt, was ansteht: fällige Prüfungen, offene Mängel und deine eigene PSA." },
      { ziel: "#mat-side-auf", wenn: () => sichtbar("#mat-side-auf"), text: "Tippe auf „☰ Ordner“, um die Ordner zu sehen.",
        warten: { klick: "#mat-side-auf" } },
      { ziel: imBaum, text: "Links stehen die Ordner deines Bereichs: Lager, Fahrzeuge, Gruppen. Öffne „Übung – Fahrzeug 1“.",
        warten: { klick: imBaum } },
      { ziel: artikelLink(ID.gurt), text: "Hier stehen alle Artikel des Ordners mit Status und nächster Prüfung. Öffne den Übungsgurt.",
        warten: { klick: artikelLink(ID.gurt) } },
      { ziel: ".mat-artikeltitel", text: "Das ist der Übungsgurt. Wie du einen Artikel über seine Nummer findest, zeigt der nächste Ablauf." },
    ] },
    { titel: "Artikel finden", start: "/materialablage", schritte: [
      { ziel: "#mat-lupe", wenn: () => sichtbar("#mat-lupe") && !sichtbar(suchFeld), text: "Tippe auf die Lupe für die Nummernsuche.", warten: { klick: "#mat-lupe" } },
      { ziel: suchFeld, text: "Jeder Artikel hat eine Inventarnummer. Gib „Ü-0001“ ein.", warten: { wert: [suchFeld, /ü-?0*1$/i] },
        probe: { tippen: [suchFeld, "Ü-0001"] } },
      // Gesucht wird mit „Suchen“, der Eingabetaste oder über die Vorschläge unter dem Feld (suche.js) – am Telefon steht
      // kein Knopf „Suchen“. Das Ziel bleibt das Feld, damit die Vorschläge offen bleiben (sie schließen, wenn es den
      // Fokus verliert).
      { ziel: suchFeld, text: "Und such – mit der Eingabetaste oder über die Trefferliste in den Vorschlägen.",
        warten: { klick: "#mat-suche button[type=submit], #mat-vorschlaege a", da: `#mat[data-ansicht=suche] ${artikelLink(ID.gurt)}` },
        // Probe: am Rechner „Suchen“, am Telefon (ohne den Knopf) die Trefferliste in den Vorschlägen.
        probe: { klick: "#mat-suche button[type=submit], #mat-vorschlaege .mv-alle a" } },
      // Nur, wenn ein Vorschlag nicht schon zum Artikel geführt hat. Die Führung fragt „wenn“ gleich nach dem Klick, oft
      // noch auf der alten Seite – darum „nicht auf der Artikelseite“ statt „auf der Trefferseite“.
      { ziel: artikelLink(ID.gurt), wenn: () => ansicht() !== "artikel", text: "Öffne den Treffer.", warten: { klick: artikelLink(ID.gurt) } },
      { ziel: ".mat-artikeltitel", text: "Die Artikelansicht: Status, Stammdaten, Prüfungen und Verlauf. Ein roter Banner hieße: nicht verwenden." },
      { ziel: "#mat-qr", text: "Über den QR-Code auf dem Etikett kommst du direkt hierher – ganz ohne Suche." },
    ] },
    { titel: "Mangel melden", start: `/materialablage/artikel/${ID.gurt}`, schritte: [
      { ziel: "[data-act=mangel]", text: "Ist etwas beschädigt? Tippe auf „Mangel melden“.", warten: { klick: "[data-act=mangel]" } },
      { ziel: "#mg-text", text: "Beschreib kurz, was nicht stimmt. Fotos sind freiwillig.", warten: { wert: ["#mg-text", /\S.*\S.*\S/] },
        datei: { input: "#mg-fotos", bild: "/static/uebung/material/uebungsbild-7.jpg" },
        probe: { tippen: ["#mg-text", "Übung: Platzhalter für einen Mangel"] } },
      { ziel: "#mg-ok", text: "Schick die Meldung ab.", warten: { anfrage: `POST ${API}/artikel/${ID.gurt}/mangel` }, probe: { klick: "#mg-ok" } },
      { ziel: ".mat-mangel-banner", text: "Der Artikel ist jetzt gesperrt, und Materialwart und Prüfer bekommen eine Mail. In der Übung ging nichts raus." },
    ] },
  ] };

  const pruefer = { ablaeufe: [
    { titel: "Prüfung durchführen", start: `/materialablage/artikel/${ID.seil}`, schritte: [
      { ziel: "[data-act=pruefen]", text: "Tippe auf „Prüfung starten“.", warten: { klick: "[data-act=pruefen]" } },
      { ziel: "[data-act=beginnen]", text: "Wähle oben die Art der Prüfung und beginne.", warten: { anfrage: `POST ${API}/artikel/${ID.seil}/pruefungen` },
        probe: { klick: "[data-act=beginnen]" } },
      { ziel: ".mat-punkte", text: "Geh die Prüfpunkte durch: in Ordnung, Mangel oder nicht zutreffend – beim Zahlpunkt trag einen Wert ein. Die Punkte hier sind Platzhalter.",
        warten: { bedingung: bewertet }, probe: { tippen: [`.mat-pwert[data-rid="${ID.punktZahl}"]`, "1"] } },
      { ziel: "#pr-bem", text: "Hast du beim Prüfen selbst etwas behoben, schreib es in die Bemerkung." },
      // Ziele in der Abschlussleiste sind Knöpfe: Bekommen sie den Fokus, steht die Leiste ganz da (sonst eingeklappt).
      { ziel: "[data-act=ergebnis][data-e=einsatzbereit]", text: "Wähle das Ergebnis – hier „einsatzbereit“.", warten: { klick: "[data-act=ergebnis]" },
        probe: { klick: "[data-act=ergebnis][data-e=einsatzbereit]" } },
      { ziel: "#pr-ok", text: "Schreib die Prüfung fest.", warten: { klick: "#pr-ok" } },
      { ziel: "#fs-ok", text: "Mit dem Festschreiben wird das Protokoll unveränderlich und trägt deine Unterschrift. In der Übung wird nichts unterschrieben.",
        warten: { anfrage: /^POST \/api\/material\/pruefungen\/\d+\/festschreiben$/ }, probe: { klick: "#fs-ok" } },
      // Erst, wenn der Dialog samt seinem Verlaufseintrag weg ist: Das Zurück stellt die alte Bildlaufhöhe wieder her und
      // schöbe ein schon ins Bild geholtes Ziel wieder hinaus.
      { ziel: nachDialog(".mat-protokoll a.btn"), text: "Das Protokoll gibt es als PDF – hier eine Übungsdatei." },
    ] },
  ] };

  const materialwart = { ablaeufe: [
    { titel: "Artikel anlegen", start: `/materialablage/artikel/neu?ordner=${ID.fahrzeug}`, schritte: [
      { ziel: "#an-q", text: "Such das Produkt im Katalog – gib „Übung“ ein.", warten: { wert: ["#an-q", /übung/i] }, probe: { tippen: ["#an-q", "Übung"] } },
      { ziel: "#an-treffer", text: "Wähle den Übungshelm.", warten: { klick: "#an-treffer .mat-treffer-wahl" },
        probe: { klick: "#an-treffer .mat-treffer-wahl[data-i=\"1\"]" } },
      { ziel: "#an-sn", text: "Trag die Seriennummer ein, hier „Ü-SN-1“.", warten: { wert: ["#an-sn", /\S/] }, probe: { tippen: ["#an-sn", "Ü-SN-1"] } },
      { ziel: "[data-act=anlegen]", text: "Leg den Artikel an. Neue Artikel stehen auf „neu“, bis die Eingangsprüfung gemacht ist.",
        warten: { anfrage: `POST ${API}/artikel` }, probe: { klick: "[data-act=anlegen]" } },
      { ziel: ".mat-artikeltitel", text: "Da ist er – mit Inventarnummer und Status „neu“. Den QR-Code für das Etikett findest du weiter unten." },
    ] },
    { titel: "Freigabe erteilen", start: `/materialablage/ordner/${ID.fahrzeug}?freigaben`, schritte: [
      { ziel: "#mf-person", text: "Wer darf hier lesen, prüfen oder verwalten? Such „Übungsperson A“.", warten: { wert: ["#mf-person", /\S{3}/] },
        probe: { tippen: ["#mf-person", "Übungsperson A"] } },
      { ziel: "#mf-treffer", text: "Wähle die Person aus.", warten: { klick: "#mf-treffer button.mf-person" },
        probe: { klick: `#mf-treffer button.mf-person[data-id="${ID.personA}"]` } },
      { ziel: rolle, text: "Wähle die Rolle „Prüfer“: ansehen und prüfen.", warten: { klick: "input[name=mf-vorlage][value=pruefer]" }, probe: { klick: rolle } },
      { ziel: "#mf-erteilen", text: "Erteile die Freigabe.", warten: { anfrage: /^POST \/api\/material\/ordner\/\d+\/freigaben$/ }, probe: { klick: "#mf-erteilen" } },
      // Die Zeile der Person erscheint erst, wenn die Liste nach dem Erteilen neu geladen ist.
      { ziel: `#mf-listen tr[data-person$=":${ID.personA}"]`, text: "Hier steht die neue Freigabe – ändern und entziehen geht in ihrer Zeile." },
    ] },
    { titel: "Prüfdurchgang", start: "/materialablage/pruefungen", schritte: [
      { ziel: ".page-head details.mat-menue > summary", text: "Prüfdurchgänge stehen im Menü „Prüfdurchgänge“. Öffne es.",
        warten: { klick: ".page-head details.mat-menue > summary" } },
      { ziel: "[data-act=runde]", text: "Wähle „Prüfdurchgang anlegen“.", warten: { klick: "[data-act=runde]" } },
      { ziel: "#rd-titel", text: "Gib dem Durchgang einen Titel und wähle den Ordner – alle Artikel darin kommen auf eine Liste." },
      { ziel: "#rd-ok", text: "Leg den Prüfdurchgang an.", warten: { anfrage: `POST ${API}/durchgaenge` }, probe: { klick: "#rd-ok" } },
      { ziel: "#dg-liste", text: "Mehrere Prüfer arbeiten diese Liste ab; abgeschlossen wird oben rechts." },
    ] },
  ] };

  const verwaltung = { ablaeufe: [
    { titel: "Katalog und Prüfformular", start: "/materialablage/katalog", schritte: [
      { ziel: "#kat-q", text: "Der Katalog gilt für alle Gliederungen. Such „Übung“.", warten: { wert: ["#kat-q", /übung/i] }, probe: { tippen: ["#kat-q", "Übung"] } },
      { ziel: produktLink, text: "Öffne das Produkt „Übungsgurt“.", warten: { klick: produktLink } },
      { ziel: formularLink, text: "Hier steht, nach welchem Prüfformular geprüft wird. Öffne es.", warten: { klick: formularLink }, probe: { klick: `${formularLink} strong` } },
      { ziel: "#fp-tabelle", text: "Hier pflegst du die Prüfpunkte des Formulars." },
      { ziel: "[data-act=punkt-neu]", text: "Leg einen Prüfpunkt an.", warten: { klick: "[data-act=punkt-neu]" } },
      { ziel: neuerPunkt, text: "Gib ihm einen Text, hier „Platzhalter“.", warten: { wert: [neuerPunkt, /\S/] }, probe: { tippen: [neuerPunkt, "Platzhalter"] } },
      { ziel: "[data-act=speichern]", text: "Speichere das Formular.", warten: { anfrage: `PUT ${API}/formulare/${ID.formular}` }, probe: { klick: "[data-act=speichern]" } },
      { ziel: "#fp-tabelle", text: "Gespeichert. Ist eine Version schon für Prüfungen benutzt, änderst du sie nur über „Neue Version“ – alte Protokolle bleiben, wie sie waren." },
    ] },
  ] };

  S.einfuehrung.modul("material", {
    bestand,
    antworten,
    // Protokolle (Prüfung, Sammelprotokoll) und der Lebenslauf öffnen die Übungsdatei.
    dateien: [[/\/(pdf|sammelprotokoll)$|\.pdf$/, PROTOKOLL]],
    teile: { grund, pruefer, materialwart, verwaltung },
  });
})();
