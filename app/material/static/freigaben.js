/* Freigaben je Ordner (Phase 2 · Lieferung 1, Abschnitt 4.2): der Reiter „Freigaben“ im Dialog „Ordner bearbeiten“ mit
   Rollen (Führungskraft, Materialwart, Prüfer, Externer Prüfer …; bis 02.11.2026 „Vorlagen“), den Listen „Hier
   vergeben“, „Geerbt von oben“, „In Unterordnern“ und „Verlauf“, dem Knopf „Alle Prüffreigaben verlängern“ – dazu der
   Hinweis „Meine Freigaben“ auf der Übersicht. Seit dem 02.11.2026 (Wunsch des Nutzers) eine Zeile je Person in allen drei Listen
   (geerbt und unten je Person und Ordner) mit EINEM „Ändern“ – Dialog „Rechte ändern“ mit denselben Rollenkarten wie
   „Freigabe anlegen“ (seltene Fälle unter „Einzeln“), Gültigkeit und Notiz, gespeichert in einer Transaktion
   (PUT …/freigaben/person/<konto>) – und „Entziehen“ für alle Rechte der Person dort; Verlauf, „Meine Freigaben“ und
   die Leitstelle bleiben je Freigabe. Stellt window.MatFreigaben bereit:
     inhalt(element, ordner, optionen?)  füllt element (den Reiter) mit Hinweis, „Freigabe anlegen“ und den Listen; Dialog,
                                Reiter und Knopfzeile („Schließen“) gehören material.js. ordner: das Objekt der
                                Ordneransicht (oder seine Kennung). optionen:
                                  vorlage    die Rolle „materialwart“ usw. (?freigaben=<rolle> nach „Gliederung anlegen“) oder
                                             „verlaengern“ (springt zum Knopf „Alle Prüffreigaben verlängern“)
                                  fokus      nach dem Laden ins Formular (bzw. auf „verlängern“) – sonst bleibt der
                                             Fokus, wo er ist (etwa auf dem Reiter)
                                  geaendert  wird nach jedem Schreiben gerufen (Erteilen, Ändern, Entziehen,
                                             Verlängern) – die Ordneransicht lädt nach dem Schließen neu
                                  dort(id)   „Dort öffnen“ an einer geerbten Zeile; ohne: zur Ordneransicht mit
                                             ?freigaben (öffnet dort „Ordner bearbeiten“ auf diesem Reiter)
     hinweis(element)           „Meine Freigaben“ auf der Übersicht – eigene Freigaben, gelb, was bald abläuft
     kopfhinweis(element, ordner, verlaengern?)  „n Freigaben laufen in den nächsten 30 Tagen ab“ im Ordnerkopf (nur
                                für Verwalter); der Knopf „Verlängern“ ruft verlaengern() – ohne gibt es ihn nicht
   material.js ruft sie auf. Der Server prüft jede Regel selbst (services/freigaben.py); ausgeblendet wird hier nur,
   was ohnehin scheitern würde. */
(function () {
  if (!window.S) return;
  const { esc, api, toast, confirm, info } = S;
  const API = "/api/material";
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const RECHT = { lesen: "lesen", verwalten: "verwalten", pruefen: "prüfen" };
  // Link auf die Anleitung in der Strömipedia am Ende einer Info – nur, wer sie lesen darf (material.js, MatAnleitung).
  const mehrDazu = (thema) => (window.MatAnleitung ? window.MatAnleitung.mehrDazu(thema) : "");
  /* Die Rollen (Nutzer 02.11.2026, „Rollen wie beim Anlegen“): dieselben Karten in „Freigabe anlegen“ und „Rechte
     ändern“ – ein Grundrecht und/oder eine Prüffreigabe. Die Gültigkeit einer Rolle gilt fürs Grundrecht; wer lesen
     oder verwalten mitbekommt, prüft dauerhaft und damit, solange das Grundrecht gilt – seit dem 03.11.2026 auch, wenn
     der Vergebende selbst nur befristet verwaltet („Prüfen folgt dem Grundrecht“). Befristet ist nur der externe
     Prüfer. „Einzeln“ lässt Grundrecht und Prüffreigabe frei, je mit eigener Gültigkeit. kurz steht auf der Karte,
     lang im „i“ an „Rolle“. */
  const ROLLEN = [
    { k: "fuehrungskraft", t: "Führungskraft", grund: "lesen", pruefen: false, kurz: "ansehen, Mängel melden",
      lang: "lesen – Bestand, Protokolle, Export, Lebensläufe und Journal ansehen, Mängel melden (sperrt)" },
    { k: "materialwart", t: "Materialwart", grund: "verwalten", pruefen: false, kurz: "Ordner und Artikel pflegen",
      lang: "verwalten – Ordner und Artikel pflegen, aussondern, Freigaben vergeben; prüfen nur mit eigener Prüffreigabe" },
    { k: "materialwart_pruefer", t: "Materialwart und Prüfer", grund: "verwalten", pruefen: true,
      kurz: "wie Materialwart, dazu prüfen", lang: "verwalten und prüfen – das Prüfen gilt, solange verwalten gilt" },
    { k: "pruefer", t: "Prüfer", grund: "lesen", pruefen: true, kurz: "ansehen und prüfen",
      lang: "lesen und prüfen – das Prüfen gilt, solange lesen gilt" },
    { k: "extern", t: "Externer Prüfer", grund: null, pruefen: true, kurz: "nur prüfen, höchstens 24 Monate",
      lang: "nur prüfen, mit Enddatum – die Prüfsicht: Artikel und Prüfungen, kein Export, kein Journal; höchstens 24 Monate" },
    { k: "einzeln", t: "Einzeln", grund: null, pruefen: false, kurz: "",
      lang: "Grundrecht (lesen oder verwalten) und Prüffreigabe frei wählen, je mit eigener Gültigkeit – für seltene Fälle" },
  ];
  const rolleMit = (k) => ROLLEN.find((r) => r.k === k);
  const OHNE_QUALIFIKATION = "Prüfen erst mit Häkchen durch die Verwaltung und Urkundennummer im Profil.";
  const OHNE_GRUNDRECHT = "Dauerhaft prüft nur, wer hier auch lesen oder verwalten hat – sonst wirkt die Prüffreigabe nicht.";
  // Unter der Gültigkeit einer Rolle mit Prüfen, wenn sie ein Ende hat (bis 03.11.2026 endete das Prüfen dann mit).
  const PRUEFEN_FOLGT = "Prüfen gilt, solange das Grundrecht gilt.";
  // Sätze unter den Rollenkarten: warum eine Rolle nicht geht (rollenGruende).
  const EIGENE_NEU = "Dir selbst vergibst du keine Prüffreigabe – das macht ein anderer Verwalter oder die Material-Verwaltung.";
  const FEST_ROLLE = "Ein Recht der Person reicht weiter als dein eigenes Verwalten – ändern kannst du nur unter „Einzeln“, was dort frei ist.";
  const EIGENE_MEHR = "Mehr Rechte gibt dir ein anderer Verwalter oder die Material-Verwaltung.";
  const NUR_PV_HERAB = "Herabsetzen und entziehen nur über die Material-Verwaltung – sonst verwaltet hier niemand so lange wie du.";
  const OHNE_ZUGANG_MEHR = "Mehr Rechte erst, wenn das Konto aktiv ist und Zugang zur Materialablage hat – den gibt die Plattform-Verwaltung.";
  // Die Erklärungen hinter den „i“ an „Rolle“ und „Gültig“ – mit dem Link in die Strömipedia.
  const rollenInfo = () => ROLLEN.map((r) => `<span class="info-absatz"><strong>${esc(r.t)}:</strong> ${esc(r.lang)}</span>`).join("")
    + mehrDazu("freigaben");
  const gueltigInfo = () => "<span class=\"info-absatz\">„dauerhaft“ gilt, bis jemand die Freigabe ändert oder entzieht; „bis“ "
    + "schließt den letzten Tag ein: „bis 31.12.“ gilt den ganzen 31.12.</span><span class=\"info-absatz\">Bei einer Rolle "
    + "gilt sie für lesen bzw. verwalten – das Prüfen dazu gilt, solange dieses Grundrecht gilt. Nur externe Prüfer brauchen "
    + "ein Enddatum, höchstens 24 Monate.</span>" + mehrDazu("freigaben");

  const plural = S.plural;              // „1 Bild“, „3 Bilder“ – app-weit in common.js (UI/UX vor dem Merge, A11)
  const fokus = (el) => { if (el && !window.matchMedia("(pointer: coarse)").matches) el.focus(); };
  // „2027-12-31“ → „31.12.2027“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const fmtTag = (iso) => { const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}.${m[2]}.${m[1]}` : ""; };
  // Wer selbst nur befristet verwaltet: kein „dauerhaft“ fürs Grundrecht, das Datum trägt er selbst ein.
  const eigenesEndeText = (ende) => (ende ? `Du verwaltest hier bis ${fmtTag(ende)} – länger geht nicht.` : "");
  // Enddaten vergleichen: null heißt unbefristet und ist das späteste.
  const frueher = (a, b) => (a === null || a === undefined ? null : b === null || b === undefined ? a : (a < b ? a : b));

  /* Datumsfelder wie im Modul (material.js setzt beim Tippen die Punkte): TT.MM.JJJJ, gespeichert wird ISO. */
  const datumFeld = (id, iso, label) => `<input type="text" id="${id}" class="mat-datum" data-art="tag" inputmode="numeric"
    autocomplete="off" maxlength="10" placeholder="TT.MM.JJJJ" value="${esc(fmtTag(iso))}"${label ? ` aria-label="${esc(label)}"` : ""}>`;
  function datumWert(feld, name) {
    const s = feld.value.trim();
    if (!s) return "";
    const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m) {
      const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
      if (d.getUTCFullYear() === +m[3] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[1]) {
        return `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
      }
    }
    throw new Error(`„${name}“: bitte als TT.MM.JJJJ angeben, z. B. 31.12.2027.`);
  }

  /* Zustand einer Zeile: gültig · läuft in n Tagen ab (gelb) · abgelaufen am … (grau) · wirkt nicht – mit dem Grund
     vom Server (wirkt_nicht: Konto deaktiviert › Konto ohne Namen › kein Zugang zur Materialablage › Qualifikation
     fehlt › dauerhaft nur mit lesen oder verwalten). */
  function zustand(f) {
    if (!f.gueltig) return `<span class="mf-zustand abgelaufen">abgelaufen am ${fmtTag(f.bis)}</span>`;
    if (f.wirkt === false) {
      return `<span class="mf-zustand wirkt-nicht">wirkt nicht${f.wirkt_nicht ? ` – ${esc(f.wirkt_nicht)}` : ""}</span>`;
    }
    const t = f.laeuft_ab_in_tagen;
    if (t !== null && t !== undefined) {
      return `<span class="mf-zustand bald">läuft ${t === 0 ? "heute" : t === 1 ? "morgen" : `in ${t} Tagen`} ab</span>`;
    }
    return '<span class="mf-zustand gueltig">gültig</span>';
  }
  const bisText = (bis) => (bis ? fmtTag(bis) : "dauerhaft");

  /* --- Untere Dialoge (Ändern, Verlängern) -------------------------------------------------------------------
     Eigene <dialog>-Elemente über dem Dialog „Ordner bearbeiten“ – wie S.confirm: So bleibt der Dialog darunter samt
     halb ausgefülltem „Freigabe anlegen“ und ungespeicherten Eingaben im Reiter „Ordner“ stehen, und man kehrt danach in
     den Reiter „Freigaben“ zurück. */
  function unterDialog(html, onOpen) {
    const dlg = document.createElement("dialog");
    dlg.className = "mf-unter";
    dlg.innerHTML = `<div class="dlg-body">${html}</div>`;
    document.body.appendChild(dlg);
    const body = dlg.firstElementChild;
    $$("[data-close]", body).forEach((b) => b.addEventListener("click", () => dlg.close()));
    const titel = $("h2", body);
    if (titel) {
      titel.id = "mf-unter-titel";
      dlg.setAttribute("aria-labelledby", titel.id);
      // Am Touchgerät der Titel statt des ersten Felds – sonst ginge sofort die Tastatur auf (wie S.dialog).
      if (window.matchMedia("(pointer: coarse)").matches) { titel.tabIndex = -1; titel.autofocus = true; }
    }
    dlg.addEventListener("close", () => dlg.remove());
    dlg.showModal();
    S.dialogVerlauf(dlg);
    if (onOpen) onOpen(dlg, body);
    return dlg;
  }

  /* --- Listen ------------------------------------------------------------------------------------------------ */
  function personHtml(k) {
    return `<strong>${esc(k.name)}</strong>${k.gliederung ? ` <span class="small muted">${esc(k.gliederung)}</span>` : ""}
      ${k.aktiv === false ? ' <span class="badge grey">deaktiviert</span>' : ""}`;
  }

  /* Eine Zeile je Person (Wunsch des Nutzers vom 02.11.2026): Die Antwort des Servers hat je Recht eine Zeile – hier
     werden sie je Person UND Anker-Ordner zusammengefasst (Schlüssel „ordner:konto“). Eine Person hat an einem Ordner
     höchstens ein Grundrecht und eine Prüffreigabe; das Grundrecht steht zuerst. In „Hier vergeben“ ist das eine Zeile
     je Person, in „Geerbt von oben“ und „In Unterordnern“ eine je Person und Ordner. */
  function personen(liste) {
    const je = new Map();
    liste.forEach((f) => {
      const k = `${f.ordner.id}:${f.konto.id}`;
      if (!je.has(k)) je.set(k, { k, ordner: f.ordner, konto: f.konto, eigen: f.eigen, rechte: [] });
      je.get(k).rechte.push(f);
    });
    return Array.from(je.values()).map((p) => {
      p.rechte.sort((a, b) => (a.recht === "pruefen") - (b.recht === "pruefen"));
      p.grund = p.rechte.find((f) => f.recht !== "pruefen") || null;
      p.pruef = p.rechte.find((f) => f.recht === "pruefen") || null;
      return p;
    });
  }
  // „verwalten (dauerhaft)“, „prüfen (bis 31.12.2027)“
  const rechtText = (f) => `${RECHT[f.recht] || f.recht} (${f.bis ? `bis ${fmtTag(f.bis)}` : "dauerhaft"})`;
  const rechteText = (p) => p.rechte.map(rechtText).join(", ");
  // „Entziehen“ in der Zeile nimmt alle Rechte – nur, wenn jedes davon gelingt (änderbar, Nr. 7 vorab gerechnet).
  const ganzEntziehbar = (p) => p.rechte.every((f) => f.aenderbar && f.entziehbar !== false);

  // art: „direkt“ (hier vergeben), „geerbt“ (von oben, nur lesbar), „unten“ (in Unterordnern, mit Pfad).
  function zeileHtml(p, art) {
    const ordner = art === "geerbt" ? `<div class="small muted">geerbt von ${esc(p.ordner.pfad)}</div>`
      : art === "unten" ? `<div class="small muted">${esc(p.ordner.pfad)}</div>` : "";
    // Je Recht eine Textzeile mit seiner Zustandsmarke. Ohne Zugang zum Modul sagt der Zustand den Grund – die Marke
    // „Qualifikation fehlt“ nur, wenn allein die Qualifikation fehlt.
    const rechte = p.rechte.map((f) => `<div class="mf-recht"><span>${esc(rechtText(f))}</span> ${zustand(f)}${
      f.recht === "pruefen" && f.konto.zugang !== false && !f.konto.qualifiziert ? ' <span class="badge">Qualifikation fehlt</span>' : ""}</div>`).join("");
    // Notiz einmal; weichen die beiden ab (Altbestand), beide mit dem Recht davor.
    const notizen = p.rechte.filter((f) => "notiz" in f);
    const verschieden = notizen.length > 1 && notizen[0].notiz !== notizen[1].notiz;
    const notiz = verschieden
      ? notizen.map((f) => `<div><span class="muted">${esc(RECHT[f.recht] || f.recht)}:</span> ${f.notiz ? esc(f.notiz) : "–"}</div>`).join("")
      : (notizen.length && notizen[0].notiz ? esc(notizen[0].notiz) : '<span class="muted">–</span>');
    // Vergeben einmal, wenn beide Rechte von derselben Person am selben Tag stammen, sonst je Recht.
    const vonText = (f) => `${esc(f.vergeben_von || "")}${f.seit ? ` am ${esc(S.fmtDate(f.seit))}` : ""}`;
    const einmal = p.rechte.every((f) => vonText(f) === vonText(p.rechte[0]));
    const vergeben = einmal ? vonText(p.rechte[0])
      : p.rechte.map((f) => `<div><span class="muted">${esc(RECHT[f.recht] || f.recht)}:</span> ${vonText(f)}</div>`).join("");
    let knoepfe = "";
    let nurVerwaltung = "";
    if (art === "geerbt") {
      // Geerbtes ändert man dort, wo es vergeben ist – wer jenen Ordner verwaltet, springt hin.
      if (p.rechte.some((f) => f.aenderbar)) knoepfe = `<button class="btn secondary small" type="button" data-act="dort" data-ordner="${p.ordner.id}">Dort öffnen</button>`;
    } else if (p.rechte.some((f) => f.aenderbar)) {
      // EIN „Ändern“ für alle Rechte der Person. „Entziehen“ nur, wenn es gelingt: Die eigene Verwalterfreigabe bleibt,
      // solange sonst niemand die Gliederung so lange verwaltet (1.6 Nr. 7) – dann steht statt des Knopfs, wer helfen kann.
      knoepfe = `<button class="btn secondary small" type="button" data-act="aendern" data-person="${p.k}">Ändern</button>
        ${ganzEntziehbar(p) ? `<button class="btn secondary small" type="button" data-act="entziehen" data-person="${p.k}">Entziehen</button>` : ""}`;
      if (p.rechte.some((f) => f.aenderbar && f.entziehbar === false)) {
        nurVerwaltung = '<div class="small muted mf-nur-pv">Entziehen nur über die Material-Verwaltung – sonst verwaltet hier niemand so lange wie du.</div>';
      }
    }
    return `<tr data-person="${p.k}"${p.rechte.every((f) => !f.gueltig) ? ' class="mf-alt"' : ""}>
      <td data-l="Person" class="mf-k-person">${personHtml(p.konto)}${p.eigen ? ' <span class="badge grey">du</span>' : ""}${ordner}</td>
      <td data-l="Rechte" class="mf-rechte">${rechte}</td>
      ${art === "geerbt" ? "" : `<td data-l="Notiz" class="mf-notiztext">${notiz}</td>`}
      <td data-l="Vergeben" class="small">${vergeben}</td>
      <td class="tabelle-aktionen"><div class="btn-row">${knoepfe}</div>${nurVerwaltung}</td></tr>`;
  }

  function tabelleHtml(liste, art, leerText) {
    if (!liste.length) return `<p class="leerzustand">${esc(leerText)}</p>`;
    return `<table class="list mf-tabelle"><thead><tr><th>Person</th><th>Rechte</th>
      ${art === "geerbt" ? "" : "<th>Notiz</th>"}<th>Vergeben</th><th></th></tr></thead>
      <tbody>${liste.map((p) => zeileHtml(p, art)).join("")}</tbody></table>`;
  }

  function verlaufHtml(liste) {
    if (!liste.length) return '<p class="leerzustand">Noch nichts vergeben oder geändert.</p>';
    const was = (e) => {
      const recht = `„${RECHT[e.recht] || e.recht || "?"}“`;
      if (e.aktion === "freigabe_erteilt") return `${recht} an ${esc(e.konto)} erteilt – ${bisText(e.bis)}`;
      if (e.aktion === "freigabe_entzogen") return `${recht} von ${esc(e.konto)} entzogen`;
      // Vom Tageslauf eingetragen (wer: „Tageslauf“), sobald das Enddatum vorbei ist.
      if (e.aktion === "freigabe_abgelaufen") return `${recht} von ${esc(e.konto)} abgelaufen (bis ${bisText(e.bis)})`;
      if (e.aktion === "freigabe_entfernt") return `${recht} von ${esc(e.konto)} entfernt${e.grund ? ` (${esc(e.grund)})` : ""}`;
      const teile = [];
      if (e.recht_vorher && e.recht_vorher !== e.recht) teile.push(`${esc(RECHT[e.recht_vorher] || e.recht_vorher)} → ${esc(RECHT[e.recht] || e.recht)}`);
      if (e.bis_vorher !== e.bis) teile.push(`bis ${bisText(e.bis_vorher)} → ${bisText(e.bis)}`);
      if (e.notiz_geaendert) teile.push("Notiz geändert");
      return `${recht} von ${esc(e.konto)} geändert${teile.length ? ": " + teile.join(", ") : ""}${e.grund ? ` (${esc(e.grund)})` : ""}`;
    };
    return `<ul class="mf-verlauf">${liste.map((e) => `<li><span class="small muted">${esc(S.fmtDate(e.zeit, true))} · ${esc(e.wer)}</span>
      <div>${was(e)}</div></li>`).join("")}</ul>`;
  }

  function listenHtml(d) {
    // Verlängern betrifft nur befristete – dauerhafte laufen nicht ab.
    const pruefzeilen = d.direkt.concat(d.unten).filter((f) => f.recht === "pruefen" && f.bis && f.aenderbar);
    // Die Zahl im Kopf zählt Zeilen, also Personen; der Ablaufhinweis zählt weiter Freigaben (einzelne Enddaten).
    const direkt = personen(d.direkt);
    const geerbt = personen(d.geerbt);
    const unten = personen(d.unten);
    return `${d.laeuft_ab ? `<p class="notice mf-ablauf">${plural(d.laeuft_ab, "Freigabe läuft", "Freigaben laufen")} in den nächsten 30 Tagen ab.</p>` : ""}
      <details class="mf-teil" open><summary>Hier vergeben <span class="mf-zahl">${direkt.length}</span></summary>
        ${pruefzeilen.length ? '<div class="btn-row mf-verl-reihe"><button class="btn secondary small" type="button" data-act="verlaengern" id="mf-verlaengern">Alle Prüffreigaben verlängern</button></div>' : ""}
        ${tabelleHtml(direkt, "direkt", "An diesem Ordner selbst ist nichts vergeben.")}</details>
      <details class="mf-teil"><summary>Geerbt von oben <span class="mf-zahl">${geerbt.length}</span>${info("Geerbt von oben", "Freigaben an Oberordnern gelten auch hier. Ändern lassen sie sich nur dort, wo sie vergeben sind.")}</summary>
        ${tabelleHtml(geerbt, "geerbt", "Nichts geerbt.")}</details>
      <details class="mf-teil"><summary>In Unterordnern <span class="mf-zahl">${unten.length}</span></summary>
        ${tabelleHtml(unten, "unten", "In den Unterordnern ist nichts eigens vergeben.")}</details>
      <details class="mf-teil"><summary>Verlauf</summary>${verlaufHtml(d.verlauf)}</details>`;
  }
  // Die Person zum Schlüssel „ordner:konto“ aus allen drei Listen.
  const personZu = (d, k) => personen(d.direkt.concat(d.geerbt, d.unten)).find((p) => p.k === k) || null;

  /* --- Rollen und Gültigkeit (gemeinsam für „Freigabe anlegen“ und „Rechte ändern“) ------------------------------
     Rollenkarten als Radiogruppe (id: Kennung der Gruppe, name: Name der Knöpfe); darunter, warum eine Rolle nicht
     geht – als Satz, nicht im „i“. */
  const rollenHtml = (id, name) => `<fieldset class="mf-vorlagen" id="${id}"><legend>Rolle${info("Rolle", rollenInfo())}</legend>
      ${ROLLEN.map((r) => `<label class="mf-vorlage"><input type="radio" name="${name}" value="${r.k}">
        <span><strong>${esc(r.t)}</strong>${r.kurz ? `<span class="small">${esc(r.kurz)}</span>` : ""}</span></label>`).join("")}
    </fieldset><p class="help mf-gruende" id="${id}-gruende" hidden></p>`;

  // gruende: {rolle: Satz} – diese Rollen sind ausgegraut; je Satz eine Zeile mit den Rollen davor (ihre Knöpfe verweisen
  // mit aria-describedby darauf). Eine gewählte Rolle, die nicht mehr geht, verliert die Wahl.
  function gruendeZeigen(gruppe, gruende) {
    const je = new Map();
    const satz = gruppe.nextElementSibling;
    $$('input[type="radio"]', gruppe).forEach((r) => {
      const g = gruende[r.value] || "";
      r.disabled = !!g;
      if (g && r.checked) r.checked = false;
      if (g) { if (!je.has(g)) je.set(g, []); je.get(g).push(`„${rolleMit(r.value).t}“`); }
      if (g) r.setAttribute("aria-describedby", satz.id); else r.removeAttribute("aria-describedby");
    });
    // Gilt ein Grund für alle Rollen außer „Einzeln“, steht nur der Satz da.
    const html = Array.from(je, ([g, rollen]) => `<span class="mf-grund-satz">${rollen.length < ROLLEN.length - 1
      ? `${esc(rollen.join(", "))}: ` : ""}${esc(g)}</span>`).join("");
    if (satz.innerHTML !== html) satz.innerHTML = html;
    satz.hidden = !je.size;
  }

  /* Die Rolle zu den heutigen Rechten einer Person an einem Ordner (g Grundrecht, pf Prüffreigabe, je Zeile der Liste
     oder null): lesen → Führungskraft, verwalten → Materialwart, dazu dauerhaft prüfen → Prüfer bzw. Materialwart und
     Prüfer, nur befristet prüfen → Externer Prüfer; alles andere (befristet prüfen mit Grundrecht, dauerhaft prüfen
     ohne Grundrecht hier) → „Einzeln“. */
  function rolleZu(g, pf) {
    if (g && pf) return pf.bis !== null ? "einzeln" : g.recht === "verwalten" ? "materialwart_pruefer" : "pruefer";
    if (g) return g.recht === "verwalten" ? "materialwart" : "fuehrungskraft";
    if (pf) return pf.bis !== null ? "extern" : "einzeln";
    return null;
  }

  /* Warum eine Rolle im Dialog nicht geht – {rolle: Satz}. Ausgegraut wird, was der Server ohnehin ablehnte: ein Recht,
     das man nicht ändern darf (Nr. 4, x.fest – dann nur „Einzeln“), mehr für sich selbst (Nr. 5; x.eigen, nicht für die
     Material-Verwaltung), die eigene letzte Verwalterfreigabe herabsetzen oder entziehen (Nr. 7, entziehbar false), mehr
     für ein Konto ohne Zugang (Nr. 12) und eine neue oder längere Prüffreigabe ohne Qualifikation (Nr. 8). Das Datum
     prüft der Server. */
  function rollenGruende(g, pf, x) {
    const out = {};
    ROLLEN.forEach((r) => {
      if (r.k === "einzeln") return;
      const grundMehr = !!r.grund && (!g || (g.recht === "lesen" && r.grund === "verwalten"));
      const pruefMehr = r.pruefen && (!pf || (r.k !== "extern" && pf.bis !== null));
      let grund = "";
      if (x.fest) grund = FEST_ROLLE;
      else if (x.eigen && pruefMehr && !pf) grund = EIGENE_NEU;
      else if (x.eigen && (grundMehr || pruefMehr)) grund = EIGENE_MEHR;
      else if (g && g.entziehbar === false && r.grund !== "verwalten") grund = NUR_PV_HERAB;
      else if ((grundMehr || pruefMehr) && x.ohneZugang) grund = OHNE_ZUGANG_MEHR;
      else if (pruefMehr && !x.qualifiziert) grund = OHNE_QUALIFIKATION;
      if (grund) out[r.k] = grund;
    });
    return out;
  }

  /* Was eine Rolle an die Schnittstelle schickt. bis: die Gültigkeit der Rolle (null = dauerhaft) – fürs Grundrecht;
     das Prüfen der Rollen mit Grundrecht ist immer dauerhaft und gilt, solange das Grundrecht gilt, auch wenn der
     Vergebende selbst nur befristet verwaltet („Prüfen folgt dem Grundrecht“, Nutzer 03.11.2026 – der Server lässt das
     zu, wo die Person dort ein Grundrecht bekommt oder hat); nur der externe Prüfer prüft bis zum Datum. rolleAnlegen
     für POST …/freigaben; rolleAendern für PUT …/freigaben/person/<konto> mit den heutigen Rechten g und pf – was die
     Rolle nicht hat, wird entzogen. */
  const pruefBis = (r, bis) => (r.k === "extern" ? bis : null);
  const rolleAnlegen = (r, bis) => ({ grundrecht: r.grund, grund_bis: r.grund ? bis : null, pruefen: r.pruefen,
    pruefen_bis: r.pruefen ? pruefBis(r, bis) : null });
  function rolleAendern(r, bis, g, pf) {
    const out = {};
    if (r.grund) out.grundrecht = { recht: r.grund, bis };
    else if (g) out.grundrecht = null;
    if (r.pruefen) out.pruefen = { bis: pruefBis(r, bis) };
    else if (pf) out.pruefen = null;
    return out;
  }

  /* Gültigkeit als Radiogruppe „dauerhaft / bis [Datum]“ (Nutzer 02.11.2026) – das Datumsfeld steht immer da, Tippen
     hinein wählt „bis“. name: wofür, fürs Vorlesen und für Fehlermeldungen („Gültig“, „Grundrecht gültig“ …); mitInfo:
     das „i“ an „Gültig“ (bei den Rollen). Wo „dauerhaft“ nicht geht, fehlt es (Klasse nur-bis). */
  const gueltigHtml = (id, name, mitInfo) => `<div class="mf-gueltig feld-gruppe" id="${id}" role="radiogroup" aria-label="${esc(name)}">
      <span class="mf-gueltig-titel"><span aria-hidden="true">Gültig</span>${mitInfo ? info("Gültig", gueltigInfo()) : ""}</span>
      <label class="inline mf-dauerhaft"><input type="radio" name="${id}" value="dauerhaft"> dauerhaft</label>
      <span class="mf-bis"><label class="inline"><input type="radio" name="${id}" value="bis"> bis</label>${datumFeld(`${id}-bis`, "", `${name} bis`)}</span>
    </div><p class="help mf-gueltig-hilfe" id="${id}-hilfe" hidden></p>`;

  // „Einzeln“: Grundrecht und Prüffreigabe untereinander, je mit eigener Gültigkeit (p: Vorsilbe der Kennungen).
  const einzelnHtml = (p, grund, pruef) => `<div class="mf-einzeln" id="${p}-einzeln" hidden>
      <div class="mf-einzel-teil">${grund}</div><div class="mf-einzel-teil">${pruef}</div></div>`;

  // Ein Fehler mit dem Feld, an dem er stehen soll (S.feldFehler).
  const feldFehlerAn = (feld, text) => Object.assign(new Error(text), { feld });

  /* Steuerung einer Gültigkeitszeile. vorschlag(): das Datum, das „bis“ bekommt, wenn das Feld beim Wählen leer ist –
     nur beim externen Prüfer (sonst null): Ein Datum steht nur, wo man es selbst einträgt („Prüfen folgt dem
     Grundrecht“, Nutzer 03.11.2026). geaendert: nach jeder Wahl. vomNutzer(): ob man die Zeile seit dem letzten
     setzen() selbst angefasst hat – dann ändert ein Rollenwechsel sie nicht. */
  function gueltig(wurzel, id, vorschlag, geaendert) {
    const gruppe = $("#" + id, wurzel);
    const dauer = $('input[value="dauerhaft"]', gruppe);
    const bisWahl = $('input[value="bis"]', gruppe);
    const feld = $(`#${id}-bis`, wurzel);
    const hilfeEl = $(`#${id}-hilfe`, wurzel);
    const name = gruppe.getAttribute("aria-label");
    const nurBis = () => gruppe.classList.contains("nur-bis");
    // angefasst: vom Nutzer gesetzt; erzwungen: „dauerhaft“ war gewählt und ging nicht mehr (erlauben) – geht es wieder,
    // kommt es zurück, solange niemand die Zeile angefasst hat.
    let angefasst = false;
    let erzwungen = false;
    const vorschlagen = () => { const v = vorschlag && vorschlag(); if (v && !feld.value) feld.value = fmtTag(v); };
    const bisNehmen = () => {
      angefasst = true;
      erzwungen = false;
      if (bisWahl.checked) return;
      bisWahl.checked = true;
      if (geaendert) geaendert();
    };
    // Tippen oder Schreiben ins Feld wählt „bis“ – nicht schon der Fokus: Wer mit Tab durchgeht, ändert nichts.
    feld.addEventListener("pointerdown", bisNehmen);
    feld.addEventListener("input", bisNehmen);
    [dauer, bisWahl].forEach((r) => r.addEventListener("change", () => {
      angefasst = true;
      erzwungen = false;
      if (bisWahl.checked) vorschlagen();
      if (geaendert) geaendert();
    }));
    return {
      gruppe, feld,
      // wert: null (dauerhaft), "" („bis“ mit leerem Feld) oder ein ISO-Tag (bis, mit Datum).
      setzen(wert) {
        if (wert === null) { dauer.checked = true; feld.value = ""; } else { bisWahl.checked = true; feld.value = fmtTag(wert); }
        feld.classList.remove("ungueltig");
        angefasst = false;
        erzwungen = false;
      },
      // „dauerhaft“ anbieten oder nicht; ohne bleibt „bis“ (mit Vorschlag, wo es einen gibt, sonst leer).
      erlauben(geht) {
        gruppe.classList.toggle("nur-bis", !geht);
        if (!geht && !bisWahl.checked) { bisWahl.checked = true; erzwungen = true; vorschlagen(); }
        else if (geht && erzwungen) { dauer.checked = true; feld.value = ""; feld.classList.remove("ungueltig"); erzwungen = false; }
      },
      vomNutzer: () => angefasst,
      hilfe(text) { hilfeEl.textContent = text || ""; hilfeEl.hidden = !text; },
      zeigen(an) { gruppe.hidden = !an; if (!an) hilfeEl.hidden = true; },
      dauerhaft: () => dauer.checked && !nurBis(),
      // null (dauerhaft) oder das Datum – ohne gültiges Datum ein Fehler am Feld.
      wert() {
        if (dauer.checked && !nurBis()) return null;
        let v;
        try { v = datumWert(feld, name + " bis"); } catch (e) { throw feldFehlerAn(feld, e.message); }
        if (!v) throw feldFehlerAn(feld, `Bitte ein Datum angeben${nurBis() ? "" : " – oder „dauerhaft“"}.`);
        return v;
      },
      // Wohin eine Ablehnung des Servers zum Ende gehört: ans Datumsfeld, wenn „bis“ gewählt ist, sonst an „dauerhaft“.
      fehlerZiel: () => (dauer.checked && !nurBis() ? dauer : feld),
    };
  }
  // Ablehnungen des Servers, die das Ende betreffen (24 Monate, Vergangenheit, länger als das eigene Verwalten, dauerhaft).
  const UM_DAS_ENDE = /Enddatum|Monate|Vergangenheit|[Ll]änger|[Dd]auerhaft/;

  /* --- „Freigabe anlegen“ ------------------------------------------------------------------------------------------ */
  function formHtml(d) {
    return `<details class="mf-teil mf-neu" open><summary><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Freigabe<span class="k-anlegen"> anlegen</span></span></summary>
      <label for="mf-person">Person</label>
      <div class="mf-personwahl">
        <input type="search" id="mf-person" placeholder="Name – ab 3 Zeichen" autocomplete="off" enterkeyhint="search"
          aria-describedby="mf-person-hilfe" aria-controls="mf-treffer">
        <div class="help" id="mf-person-hilfe">Jedes aktive Konto mit Namen und Zugang zur Materialablage, auch aus anderen Gliederungen.</div>
        <ul class="mf-treffer" id="mf-treffer" aria-label="Gefundene Personen" hidden></ul>
        <div class="mf-gewaehlt" id="mf-gewaehlt" hidden></div>
      </div>
      <label for="mf-anker">Gilt für${info("Gilt für", `Freigaben für „${esc(d.ordner.pfad)}“ gelten dort und in allen Unterordnern, bis einschließlich zum letzten Tag. Rechte addieren sich; weiter unten lässt sich nichts entziehen.${mehrDazu("freigaben")}`)}</label>
      <select id="mf-anker">${d.anker_wahl.map((a) => `<option value="${a.id}"${a.id === d.anker_vorgabe ? " selected" : ""}>${esc(a.pfad)}</option>`).join("")}</select>
      <div class="help">… und alle Ordner darunter.</div>
      <p class="notice mf-schon" id="mf-schon" hidden></p>
      ${rollenHtml("mf-rollen", "mf-vorlage")}
      ${einzelnHtml("mf", `<label for="mf-grund">Grundrecht</label><select id="mf-grund"><option value="">–</option>
          <option value="lesen">lesen</option><option value="verwalten">verwalten</option></select>
          ${gueltigHtml("mf-grund-g", "Grundrecht gültig")}`,
        `<div class="feld-gruppe"><label class="inline"><input type="checkbox" id="mf-pruefen"> Prüffreigabe</label></div>
          ${gueltigHtml("mf-pruefen-g", "Prüffreigabe gültig")}`)}
      ${gueltigHtml("mf-gueltig", "Gültig", true)}
      <details class="mf-notiz"><summary>Notiz</summary>
        <input type="text" id="mf-notiz" maxlength="200" aria-label="Notiz" aria-describedby="mf-notiz-hilfe">
        <div class="help" id="mf-notiz-hilfe">Eine Zeile, höchstens 200 Zeichen – sehen nur Verwalter dieses Ordners und die
          Material-Verwaltung, die Person selbst also nur, wenn sie hier mitverwaltet. Keine sensiblen Angaben.</div></details>
      <div class="btn-row mf-erteilen-reihe"><button class="btn" type="button" id="mf-erteilen">Freigabe erteilen</button></div>
    </details>`;
  }

  /* Der Zustand des Formulars: gewählte Person, Rolle und Anker – daraus folgen die sichtbaren Felder, die Vorgaben
     der Gültigkeit und welche Rollen gehen (prüfen nur mit Qualifikation; „dauerhaft“ fürs Grundrecht nur, wer selbst
     dauerhaft verwaltet; prüfen dauerhaft, wo die Person ein Grundrecht bekommt oder schon hat – auch von einem
     befristeten Verwalter; der externe Prüfer nur mit Enddatum). Vorbelegt ist „dauerhaft“, wo es geht, sonst „bis“
     mit leerem Feld – ein Datum nur beim externen Prüfer. */
  function formVerdrahten(body, stand, nachher) {
    const feld = (id) => $("#" + id, body);
    let person = null;
    let suchzeit = null;
    let suchlauf = 0;
    const anker = () => stand.daten.anker_wahl.find((a) => a.id === +feld("mf-anker").value) || stand.daten.anker_wahl[0];
    const rolle = () => rolleMit(($('input[name="mf-vorlage"]:checked', body) || {}).value);
    const grenzen = stand.daten.grenzen;
    // Vorschlag nur für den externen Prüfer: 31.12. des Folgejahres, gekappt auf 24 Monate und das eigene Verwalten.
    const pruefenEnde = () => frueher(frueher(grenzen.vorgabe_bis, grenzen.pruefen_max), anker().ende);
    const gRolle = gueltig(body, "mf-gueltig", () => (rolle() && rolle().k === "extern" ? pruefenEnde() : null), () => zeigen());
    const gGrund = gueltig(body, "mf-grund-g", null, () => zeigen());
    const gPruef = gueltig(body, "mf-pruefen-g", null, () => zeigen());

    // Hat die gewählte Person am Anker oder darüber schon ein gültiges Grundrecht? Die Material-Verwaltung hat es
    // überall (grundrecht_ueberall aus der Personensuche), sonst aus den Listen (direkt und geerbt decken den Ordner und
    // alle Oberordner ab) – verbindlich entscheidet der Server.
    function grundrechtDort(a) {
      if (!person) return false;
      if (person.grundrecht_ueberall) return true;
      const ab = stand.daten.kette.indexOf(a.id);
      const oben = new Set(ab < 0 ? [a.id] : stand.daten.kette.slice(ab));
      return stand.daten.direkt.concat(stand.daten.geerbt).some((f) => f.konto.id === person.id && f.recht !== "pruefen"
        && f.gueltig && oben.has(f.ordner.id));
    }

    // Hat die gewählte Person am gewählten Anker schon Rechte, sagt es der Satz über den Rollen – mit „Rechte ändern“
    // (Dialog der Person). „Freigabe erteilen“ bleibt möglich und ändert wie bisher die vorhandene Zeile derselben Art.
    // Neu gezeichnet nur, wenn sich der Satz ändert – sonst verlöre ein fokussiertes „Rechte ändern“ den Fokus.
    function schonZeigen() {
      const el = feld("mf-schon");
      const p = person ? personZu(stand.daten, `${anker().id}:${person.id}`) : null;
      const html = p ? `${esc(p.konto.name)} hat hier schon: ${esc(rechteText(p))}.${p.rechte.some((f) => f.aenderbar)
        ? ' <button class="lnk" type="button" data-act="person-dialog">Rechte ändern</button>' : ""}` : "";
      el.hidden = !p;
      if (el.dataset.stand === html) return;
      el.dataset.stand = html;
      el.innerHTML = html;
      const b = $("button", el);
      if (b) b.addEventListener("click", () => { const q = personZu(stand.daten, p.k); if (q) personDialog(q, stand, nachher); });
    }

    function zeigen() {
      const a = anker();
      schonZeigen();
      const quali = !person || person.qualifiziert;
      gruendeZeigen(feld("mf-rollen"), quali ? {} : Object.fromEntries(ROLLEN.filter((v) => v.pruefen).map((v) => [v.k, OHNE_QUALIFIKATION])));
      feld("mf-pruefen").disabled = !quali;
      if (!quali) feld("mf-pruefen").checked = false;
      const v = rolle();
      const einzeln = !!v && v.k === "einzeln";
      feld("mf-einzeln").hidden = !einzeln;
      // Das Grundrecht dauerhaft nur, wer hier selbst dauerhaft verwaltet; sonst endet es spätestens mit dem eigenen
      // Verwalten. Das Prüfen folgt dem Grundrecht.
      const dauerhaftGeht = a.ende === null;
      const eigenesEnde = eigenesEndeText(a.ende);
      const spaetestens = `Spätestens ${fmtTag(frueher(grenzen.pruefen_max, a.ende))} – höchstens 24 Monate`
        + (a.ende ? " und nicht länger als deine eigene Verwalterfreigabe." : ".");
      gRolle.zeigen(!!v && !einzeln);
      if (v && !einzeln) {
        gRolle.erlauben(v.k !== "extern" && dauerhaftGeht);
        gRolle.hilfe(v.k === "extern" ? spaetestens
          : [eigenesEnde, v.pruefen && !gRolle.dauerhaft() ? PRUEFEN_FOLGT : ""].filter(Boolean).join(" "));
      }
      // „Einzeln“: Grundrecht und Prüffreigabe je mit eigener Zeile. Prüfen dauerhaft nur mit Grundrecht – hier gewählt
      // oder schon vorhanden –, dann auch von einem befristeten Verwalter.
      const grund = feld("mf-grund").value;
      const pruefen = feld("mf-pruefen").checked;
      gGrund.zeigen(einzeln && !!grund);
      gGrund.erlauben(dauerhaftGeht);
      gGrund.hilfe(eigenesEnde);
      gPruef.zeigen(einzeln && pruefen);
      gPruef.erlauben(!!grund || grundrechtDort(a));
      gPruef.hilfe(gPruef.dauerhaft() ? "" : spaetestens);
      if (!einzeln) { gGrund.hilfe(""); gPruef.hilfe(""); }
    }

    // Vorgaben: „dauerhaft“, wo man selbst dauerhaft verwaltet, sonst „bis“ mit leerem Feld (das Datum trägt man
    // selbst ein); nur der externe Prüfer bekommt ein Datum – den 31.12. des Folgejahres, gekappt. Unter „Einzeln“ ist
    // das Prüfen vorgewählt dauerhaft; geht das nicht (ohne Grundrecht), „bis“ mit leerem Feld (gueltig.erlauben).
    function rolleVorgabe() {
      const v = rolle();
      gRolle.setzen(v && v.k === "extern" ? pruefenEnde() : anker().ende === null ? null : "");
    }
    function vorgabenSetzen() {
      rolleVorgabe();
      gGrund.setzen(anker().ende === null ? null : "");
      gPruef.setzen(null);
    }
    // Rolle gewechselt: Was man an der Gültigkeit selbst gesetzt hat, bleibt; sonst die Vorgabe der neuen Rolle. So steht
    // nie ein Datum da, das man nicht selbst eingetragen hat – außer dem gekappten beim externen Prüfer.
    function rolleGewechselt() {
      if (!gRolle.vomNutzer()) rolleVorgabe();
      zeigen();
    }

    function personWaehlen(p) {
      person = p;
      const gew = feld("mf-gewaehlt");
      feld("mf-treffer").hidden = true;
      if (p) {
        gew.innerHTML = `${personHtml(p)}${p.qualifiziert ? ' <span class="badge grey">Prüfer</span>' : ""}
          <button class="lnk" type="button" data-act="person-weg">andere Person</button>`;
        gew.hidden = false;
        feld("mf-person").hidden = true;
        $('[data-act="person-weg"]', gew).onclick = () => { personWaehlen(null); feld("mf-person").value = ""; fokus(feld("mf-person")); };
      } else {
        gew.hidden = true;
        feld("mf-person").hidden = false;
      }
      zeigen();
    }

    async function suchen() {
      const q = feld("mf-person").value.trim();
      const liste = feld("mf-treffer");
      if (q.length < 3) { liste.hidden = true; return; }
      const lauf = ++suchlauf;
      let r;
      // Nur Konten mit Zugang zum Modul – an andere wirkte keine Freigabe (der Server lehnt sie ab).
      try { r = await api(`${API}/nutzer?q=${encodeURIComponent(q)}&zweck=freigabe`); }
      catch (e) { if (lauf === suchlauf) { liste.innerHTML = `<li class="mf-treffer-leer">${esc(e.message)}</li>`; liste.hidden = false; } return; }
      if (lauf !== suchlauf) return;          // eine neuere Eingabe ist schon unterwegs
      liste.innerHTML = r.nutzer.length ? r.nutzer.map((p) => `<li><button type="button" class="mf-person" data-id="${p.id}">
          ${personHtml(p)}${p.qualifiziert ? ' <span class="badge grey">Prüfer</span>' : ""}</button></li>`).join("")
          + (r.mehr ? '<li class="mf-treffer-leer">Mehr als 20 – bitte genauer.</li>' : "")
        : '<li class="mf-treffer-leer">Niemand gefunden – nur aktive Konten mit Namen und Zugang zur Materialablage (den gibt die Plattform-Verwaltung).</li>';
      liste.hidden = false;
      $$("button.mf-person", liste).forEach((b) => b.addEventListener("click", () => personWaehlen(r.nutzer.find((p) => p.id === +b.dataset.id))));
    }

    feld("mf-person").addEventListener("input", () => { clearTimeout(suchzeit); suchzeit = setTimeout(suchen, 250); });
    feld("mf-person").addEventListener("keydown", (e) => {
      // Enter nimmt den einzigen Treffer; sonst bleibt der Fokus im Feld.
      if (e.key !== "Enter") return;
      e.preventDefault();
      const knoepfe = $$("button.mf-person", feld("mf-treffer"));
      if (knoepfe.length === 1) knoepfe[0].click();
      else if (knoepfe.length) knoepfe[0].focus();
    });
    feld("mf-anker").addEventListener("change", () => { vorgabenSetzen(); zeigen(); });
    $$('input[name="mf-vorlage"]', body).forEach((x) => x.addEventListener("change", rolleGewechselt));
    $$("#mf-grund, #mf-pruefen", body).forEach((x) => x.addEventListener("change", zeigen));

    feld("mf-erteilen").addEventListener("click", async (ev) => {
      const knopf = ev.currentTarget;
      if (knopf.disabled) return;
      // Fehler am Feld (UI/UX vor dem Merge, A2): Satz darunter, Fokus darauf.
      if (!person) { S.feldFehler(feld("mf-person"), "Bitte zuerst eine Person wählen."); return; }
      const v = rolle();
      if (!v) { S.feldFehler($('input[name="mf-vorlage"]:not(:disabled)', body), "Bitte eine Rolle wählen."); return; }
      // pruefen: true mit pruefen_bis null heißt dauerhaft – ob das geht, entscheidet der Server (Grundrecht am Anker).
      const daten = { user_id: person.id, grundrecht: null, grund_bis: null, pruefen: false, pruefen_bis: null };
      let zeile = gRolle;
      try {
        if (v.k === "einzeln") {
          daten.grundrecht = feld("mf-grund").value || null;
          daten.pruefen = feld("mf-pruefen").checked;
          if (!daten.grundrecht && !daten.pruefen) throw feldFehlerAn(feld("mf-grund"), "Bitte ein Grundrecht, eine Prüffreigabe oder beides wählen.");
          if (daten.grundrecht) { zeile = gGrund; daten.grund_bis = gGrund.wert(); }
          if (daten.pruefen) { zeile = gPruef; daten.pruefen_bis = gPruef.wert(); }
        } else {
          // Die eine Zeile gilt fürs Grundrecht; das Prüfen dazu ist dauerhaft (rolleAnlegen).
          Object.assign(daten, rolleAnlegen(v, gRolle.wert()));
        }
      } catch (e) { S.feldFehler(e.feld, e.message); return; }
      const notiz = feld("mf-notiz").value.trim();
      if (notiz) daten.notiz = notiz;
      knopf.disabled = true;
      try {
        const a = anker();
        const r = await api(`${API}/ordner/${a.id}/freigaben`, { method: "POST", body: daten });
        toast(r.freigaben.length > 1 ? `${person.name}: Grundrecht und Prüffreigabe erteilt` : `${person.name}: Freigabe erteilt`);
        personWaehlen(null);
        feld("mf-person").value = "";
        feld("mf-notiz").value = "";
        await nachher();
      } catch (e) {
        // Eine Ablehnung zum Ende (24 Monate, Vergangenheit, länger als das eigene Verwalten) steht an der Gültigkeit.
        S.fehlschlag(knopf, e, UM_DAS_ENDE.test(String((e && e.message) || "")) ? zeile.fehlerZiel() : body);
      }
      finally { knopf.disabled = false; }
    });

    if (stand.vorlage) {
      const r = $(`input[name="mf-vorlage"][value="${CSS.escape(stand.vorlage)}"]`, body);
      if (r) r.checked = true;
    }
    vorgabenSetzen();
    zeigen();
    return { zeigen };
  }

  // An einem Grundrecht hängen dauerhafte Prüffreigaben derselben Person, die ohne es nicht wirken (traegt_pruefen).
  const traegtText = (f) => (f.traegt_pruefen
    ? (f.traegt_pruefen === 1
      ? `Daran hängt eine dauerhafte Prüffreigabe von ${f.konto.name} – ohne dieses Grundrecht wirkt sie nicht mehr.`
      : `Daran hängen ${f.traegt_pruefen} dauerhafte Prüffreigaben von ${f.konto.name} – ohne dieses Grundrecht wirken sie nicht mehr.`)
    : "");

  /* --- „Rechte ändern“, Entziehen, Verlängern -----------------------------------------------------------------
     Der Dialog bearbeitet alle Rechte einer Person an einem Ordner (Grundrecht und Prüffreigabe) und speichert sie über
     PUT …/ordner/<anker>/freigaben/person/<konto> in EINER Transaktion – alles oder nichts. Seit dem 02.11.2026 (Nutzer:
     „Rollen wie beim Anlegen“) wählt man eine Rolle mit EINER Gültigkeit, vorgewählt die zu den heutigen Rechten;
     seltene Fälle unter „Einzeln“ (Grundrecht und Prüffreigabe je mit eigener Gültigkeit). Die Rolle wird hier auf
     grundrecht/pruefen abgebildet – Server und Schnittstelle sind dieselben. Lehnt der Server ab, bleibt der Dialog mit
     allen Eingaben offen; die Meldung beginnt mit „„Grundrecht“: “ bzw. „„Prüffreigabe“: “ und steht an der Gültigkeit
     (Ende betroffen) bzw. an der Rolle oder dem Feld unter „Einzeln“. Ein Recht, das man nicht ändern darf (reicht
     weiter als das eigene Verwalten, Nr. 4), steht unter „Einzeln“ nur als Text da und wird nicht mitgeschickt. */
  const sichtbar = (el) => !!el && el.getClientRects().length > 0;

  // Hat das Konto über dem Anker ein gültiges Grundrecht (oder ist es Material-Verwaltung)? Dann darf eine Prüffreigabe
  // auch ohne Grundrecht hier dauerhaft sein. Aus den Listen geschätzt – verbindlich entscheidet der Server.
  function grundrechtOben(p, d) {
    if (p.pruef && p.pruef.grundrecht_dort && !p.grund) return true;
    const oben = p.ordner.id === d.ordner.id ? d.geerbt : d.direkt.concat(d.geerbt);
    return oben.some((f) => f.konto.id === p.konto.id && f.recht !== "pruefen" && f.gueltig && f.ordner.id !== p.ordner.id);
  }
  // Hinweis nach dem Speichern: offene Prüfungen, die die Person nicht mehr fortsetzen darf.
  const offenHinweis = (r, p) => (r.offene_entwuerfe ? `${plural(r.offene_entwuerfe, "offene Prüfung", "offene Prüfungen")} von ${esc(p.konto.name)} – unter
    <a href="/materialablage/pruefungen">Prüfungen</a> → „Offene Prüfungen“ mit „Reservierung aufheben“.` : "");

  function personDialog(p, stand, nachher) {
    const d = stand.daten;
    const g = p.grund;
    const pf = p.pruef;
    const anker = d.anker_wahl.find((a) => a.id === p.ordner.id);
    // Das eigene Ende am Anker – für Zeilen in Unterordnern das an diesem Ordner (dort gilt mindestens dasselbe).
    const ende = (anker || d.anker_wahl[0] || {}).ende;
    const selbstDauerhaft = ende === null || ende === undefined;
    // Vorschlag nur für den externen Prüfer (wie beim Anlegen).
    const pruefenEnde = frueher(frueher(d.grenzen.vorgabe_bis, d.grenzen.pruefen_max), ende);
    // Die eigene Zeile nur verkürzen, herabsetzen, entziehen (Nr. 5) – nicht für die Material-Verwaltung (Nr. 1).
    const eigen = p.eigen && !d.alles;
    const grundFrei = !g || g.aenderbar;
    const pruefFrei = !pf || pf.aenderbar;
    // Das Grundrecht dauerhaft gibt nur, wer selbst dauerhaft verwaltet – die eigene Zeile nur, wenn sie es schon ist
    // (dann auch ohne das, damit sie unverändert bleiben kann). Das Prüfen dauerhaft folgt dem Grundrecht – das geht
    // auch für befristete Verwalter, die eigene Zeile nur, wenn sie es schon ist.
    const grundDauerGeht = eigen ? !!(g && g.bis === null) : selbstDauerhaft;
    const pruefDauerGeht = eigen ? !!(pf && pf.bis === null) : true;
    // Vorgewählt: die Rolle zu den heutigen Rechten; passt keine oder ist ein Recht nicht änderbar, „Einzeln“.
    const start = grundFrei && pruefFrei ? rolleZu(g, pf) || "einzeln" : "einzeln";
    const gruende = rollenGruende(g, pf, { fest: !grundFrei || !pruefFrei, eigen, qualifiziert: !!p.konto.qualifiziert,
      ohneZugang: p.konto.aktiv === false || p.konto.zugang === false });
    const eigenesEnde = selbstDauerhaft ? "" : eigenesEndeText(ende);
    const spaetestens = `Spätestens ${fmtTag(frueher(d.grenzen.pruefen_max, ende))} – höchstens 24 Monate`
      + (selbstDauerhaft ? "." : " und nicht länger als deine eigene Verwalterfreigabe.");
    const fest = (f) => `<p class="mfp-fest"><strong>${esc(rechtText(f))}</strong> – ändern kann es nur, wer mindestens so lange verwaltet, oder die Material-Verwaltung.</p>`;
    // „Einzeln“ – Grundrecht: die eigene Zeile nur herabsetzen (verwalten → lesen) oder entziehen, neu gibt es für sich
    // selbst keins. Scheitert das Entziehen an Nr. 7 (eigene letzte Verwalterfreigabe), fehlen „–“ und „lesen“.
    let grundHtml;
    if (!grundFrei) {
      grundHtml = `<p class="mfp-titel">Grundrecht</p>${fest(g)}`;
    } else if (eigen && !g) {
      grundHtml = '<p class="mfp-titel">Grundrecht</p><p class="help">Keins – ein Grundrecht vergibt dir ein anderer Verwalter oder die Material-Verwaltung.</p>';
    } else {
      const ohne = !(g && g.entziehbar === false);
      const wahl = !ohne ? ["verwalten"] : eigen ? (g.recht === "verwalten" ? ["lesen", "verwalten"] : ["lesen"]) : ["lesen", "verwalten"];
      grundHtml = `<label for="mfp-grund">Grundrecht</label>
        <select id="mfp-grund">${ohne ? `<option value=""${g ? "" : " selected"}>–</option>` : ""}${wahl.map((r) => `<option value="${r}"${g && g.recht === r ? " selected" : ""}>${RECHT[r]}</option>`).join("")}</select>
        ${ohne ? "" : `<p class="help">${esc(NUR_PV_HERAB)}</p>`}
        ${gueltigHtml("mfp-grund-g", "Grundrecht gültig")}`;
    }
    // Prüffreigabe: neu nur mit Qualifikation und nicht für sich selbst (Nr. 5, 8).
    let pruefHtml;
    if (!pruefFrei) {
      pruefHtml = `<p class="mfp-titel">Prüffreigabe</p>${fest(pf)}`;
    } else {
      const neuGesperrt = !pf && (eigen || !p.konto.qualifiziert);
      pruefHtml = `<div class="feld-gruppe"><label class="inline"><input type="checkbox" id="mfp-pruefen"${pf ? " checked" : ""}${neuGesperrt ? " disabled" : ""}> Prüffreigabe</label></div>
        ${neuGesperrt ? `<p class="help">${esc(eigen ? EIGENE_NEU : OHNE_QUALIFIKATION)}</p>` : ""}
        ${gueltigHtml("mfp-pruefen-g", "Prüffreigabe gültig")}`;
    }
    // Die Notiz: EIN Feld für die Person an diesem Ordner, gespeichert auf jedes Recht, das man hier ändern darf –
    // zugeklappt wie beim Anlegen, offen, wenn es eine gibt.
    const mitNotiz = p.rechte.filter((f) => "notiz" in f && f.aenderbar);
    const notiz = (g && mitNotiz.includes(g) ? g.notiz : (mitNotiz[0] || {}).notiz) || "";
    const abweichend = g && pf && mitNotiz.length === 2 && (g.notiz || "") !== (pf.notiz || "")
      ? `<div class="help">${pf.notiz ? `Die Prüffreigabe hatte die Notiz „${esc(pf.notiz)}“` : "Die Prüffreigabe hatte keine Notiz"} – beim Speichern gilt diese eine Notiz für beide.</div>` : "";
    unterDialog(`<h2>Rechte ändern</h2>
      <p>${personHtml(p.konto)} · ${esc(p.ordner.pfad)}</p>
      ${eigen ? '<p class="help">Deine eigenen Rechte kannst du nur verkürzen, herabsetzen oder entziehen.</p>' : ""}
      ${rollenHtml("mfp-rollen", "mfp-rolle")}
      ${gueltigHtml("mfp-gueltig", "Gültig", true)}
      ${einzelnHtml("mfp", grundHtml, pruefHtml)}
      <p class="help" id="mfp-traegt" hidden>${esc(g ? traegtText(g) : "")}</p>
      <p class="help" id="mfp-ohne-grund" hidden>${esc(OHNE_GRUNDRECHT)}</p>
      ${mitNotiz.length ? `<details class="mf-notiz"${notiz || abweichend ? " open" : ""}><summary>Notiz</summary>
        <input type="text" id="mfp-notiz" maxlength="200" aria-label="Notiz" aria-describedby="mfp-notiz-hilfe" value="${esc(notiz)}">
        ${abweichend}<div class="help" id="mfp-notiz-hilfe">Sehen nur Verwalter dieses Ordners und die Material-Verwaltung – die Person selbst nur, wenn sie hier
          mitverwaltet. Keine sensiblen Angaben.</div></details>` : ""}
      <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Abbrechen</button>
        <button class="btn" type="button" id="mfp-ok">Speichern</button></div>`, (dlg, body) => {
      const feld = (id) => $("#" + id, body);
      const grundWahl = feld("mfp-grund");
      const pruefWahl = feld("mfp-pruefen");
      const rolle = () => rolleMit(($('input[name="mfp-rolle"]:checked', body) || {}).value);
      // Ein Datum schlägt der Dialog nur dem externen Prüfer vor; sonst zeigt er die gespeicherten Daten der Rechte.
      const gRolle = gueltig(body, "mfp-gueltig", () => (rolle() && rolle().k === "extern" ? pruefenEnde : null), () => zeigen());
      const gGrund = grundWahl ? gueltig(body, "mfp-grund-g", null, () => zeigen()) : null;
      const gPruef = pruefWahl ? gueltig(body, "mfp-pruefen-g", null, () => zeigen()) : null;
      // Das Grundrecht nach dem Dialog: aus der Rolle, unter „Einzeln“ gewählt – oder unverändert, wo man es nicht
      // ändern darf.
      const einzeln = () => rolle().k === "einzeln";
      const grundDanach = () => (!einzeln() ? rolle().grund || "" : grundWahl ? grundWahl.value : (g ? g.recht : ""));

      function zeigen() {
        const v = rolle();
        const ez = v.k === "einzeln";
        feld("mfp-einzeln").hidden = !ez;
        gRolle.zeigen(!ez);
        if (!ez) {
          gRolle.erlauben(v.k !== "extern" && grundDauerGeht);
          gRolle.hilfe(v.k === "extern" ? spaetestens
            : [eigen && g && g.bis ? `Deine Freigabe läuft bis ${fmtTag(g.bis)} – länger geht nicht.` : eigenesEnde,
              v.pruefen && !gRolle.dauerhaft() ? PRUEFEN_FOLGT : ""].filter(Boolean).join(" "));
        }
        if (gGrund) {
          gGrund.zeigen(ez && !!grundWahl.value);
          gGrund.erlauben(grundDauerGeht);
          gGrund.hilfe(ez && grundWahl.value ? eigenesEnde : "");
        }
        if (gPruef) {
          // Prüfen dauerhaft nur mit Grundrecht (hier gewählt oder darüber) – oder wenn sie es schon ist.
          gPruef.zeigen(ez && pruefWahl.checked);
          gPruef.erlauben(pruefDauerGeht && (!!grundDanach() || grundrechtOben(p, d) || !!(pf && pf.bis === null)));
          gPruef.hilfe(ez && pruefWahl.checked && !gPruef.dauerhaft() ? spaetestens : "");
        }
        // Was an diesem Grundrecht hängt, sagt der Dialog, sobald es wegfällt oder ein Ende bekommt.
        const dauerDanach = !ez ? gRolle.dauerhaft() : gGrund ? gGrund.dauerhaft() : !!(g && g.bis === null);
        feld("mfp-traegt").hidden = !(g && g.traegt_pruefen && grundFrei && (!grundDanach() || !dauerDanach));
        feld("mfp-ohne-grund").hidden = !(ez && pruefWahl && pruefWahl.checked && gPruef.dauerhaft() && !grundDanach() && !grundrechtOben(p, d));
      }

      // Vorbelegung: die Rolle, ihre Gültigkeit aus den gespeicherten Rechten (fürs Grundrecht, beim externen Prüfer
      // fürs Prüfen); unter „Einzeln“ jedes Recht mit seinem Ende. Ohne gespeichertes Recht „dauerhaft“, wo es geht,
      // sonst „bis“ mit leerem Feld – ein vorgeschlagenes Datum nur beim externen Prüfer.
      const rolleVorgabe = () => (rolle().k === "extern" ? (pf && pf.bis) || pruefenEnde : g ? g.bis : grundDauerGeht ? null : "");
      $(`input[name="mfp-rolle"][value="${start}"]`, body).checked = true;
      gruendeZeigen(feld("mfp-rollen"), gruende);
      gRolle.setzen(rolleVorgabe());
      if (gGrund) gGrund.setzen(g ? g.bis : grundDauerGeht ? null : "");
      if (gPruef) gPruef.setzen(pf ? pf.bis : null);
      $$('input[name="mfp-rolle"]', body).forEach((r) => r.addEventListener("change", () => {
        // Was man an der Gültigkeit selbst gesetzt hat, bleibt; sonst die Vorgabe der neuen Rolle.
        if (!gRolle.vomNutzer()) gRolle.setzen(rolleVorgabe());
        zeigen();
      }));
      [grundWahl, pruefWahl].forEach((x) => { if (x) x.addEventListener("change", zeigen); });
      zeigen();

      // Was gespeichert wird – je Recht wie die Schnittstelle es will (Rolle: rolleAendern); ein Recht, das man nicht
      // ändern darf, fehlt.
      function daten() {
        const v = rolle();
        if (v.k !== "einzeln") return rolleAendern(v, gRolle.wert(), g, pf);
        const out = {};
        if (grundWahl) {
          if (grundWahl.value) out.grundrecht = { recht: grundWahl.value, bis: gGrund.wert() };
          else if (g) out.grundrecht = null;
        }
        if (pruefWahl && !pruefWahl.disabled) {
          if (pruefWahl.checked) out.pruefen = { bis: gPruef.wert() };
          else if (pf) out.pruefen = null;
        }
        return out;
      }
      // Bleibt alles, wie es ist (Rolle, Ende, Notiz), schließt „Speichern“ ohne Anfrage.
      const gleich = (w, alt) => (w === undefined || (w === null ? !alt : !!alt && (!w.recht || w.recht === alt.recht) && w.bis === alt.bis));
      const unveraendert = (x) => gleich(x.grundrecht, g) && gleich(x.pruefen, pf) && (!("notiz" in x) || x.notiz === notiz);

      feld("mfp-ok").onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        let x;
        try { x = daten(); } catch (e) { S.feldFehler(e.feld, e.message); return; }
        if (feld("mfp-notiz")) x.notiz = feld("mfp-notiz").value.trim();
        if (!("grundrecht" in x) && !("pruefen" in x)) {
          // Unter „Einzeln“ nichts gewählt und nichts da: Hinweis am Grundrecht statt einer leeren Anfrage.
          S.feldFehler(grundWahl || pruefWahl, "Bitte ein Grundrecht, eine Prüffreigabe oder beides wählen – oder „Abbrechen“.");
          return;
        }
        if (unveraendert(x)) { dlg.close(); return; }
        // Fällt ein Recht weg (etwa „Materialwart und Prüfer“ → „Materialwart“), vorher fragen – Entziehen vernichtet
        // nichts, neu erteilen geht jederzeit.
        const weg = [g && x.grundrecht === null ? g : null, pf && x.pruefen === null ? pf : null].filter(Boolean);
        if (weg.length) {
          const text = `${weg.map((f) => `„${RECHT[f.recht] || f.recht}“`).join(" und ")} von ${p.konto.name} an ${p.ordner.pfad} entziehen?`
            + (p.eigen ? " Es ist deine eigene Freigabe." : "") + (weg.includes(g) && g.traegt_pruefen ? ` ${traegtText(g)}` : "");
          if (!(await confirm(text, "Entziehen", "", { endgueltig: false }))) return;
        }
        knopf.disabled = true;
        try {
          const r = await api(`${API}/ordner/${p.ordner.id}/freigaben/person/${p.konto.id}`, { method: "PUT", body: x });
          dlg.close();
          toast(`${p.konto.name}: Rechte geändert`);
          stand.hinweis = offenHinweis(r, p);
          await nachher();
        } catch (e) {
          // Die Meldung nennt das Recht: Geht es um das Ende, steht sie an der Gültigkeit, sonst an der Rolle bzw. unter
          // „Einzeln“ an der Auswahl dieses Rechts; eine zur Notiz am Notizfeld.
          const text = String((e && e.message) || "");
          const m = text.match(/^„(Grundrecht|Prüffreigabe|Notiz)“/);
          const ez = einzeln();
          let ziel = null;
          if (m && m[1] === "Notiz" && feld("mfp-notiz")) {
            feld("mfp-notiz").closest("details").open = true;
            ziel = feld("mfp-notiz");
          } else if (m) {
            const zeile = !ez ? gRolle : m[1] === "Grundrecht" ? gGrund : gPruef;
            const wahl = !ez ? $('input[name="mfp-rolle"]:checked', body) : m[1] === "Grundrecht" ? grundWahl : pruefWahl;
            ziel = zeile && UM_DAS_ENDE.test(text) && sichtbar(zeile.gruppe) ? zeile.fehlerZiel() : wahl;
          }
          S.fehlschlag(knopf, e, ziel || body);
        }
      };
    });
  }

  // „Entziehen“ in der Personenzeile: alle Rechte der Person an diesem Ordner, nach einer Rückfrage, die sie nennt.
  async function personEntziehen(p, stand, nachher) {
    // Was am Grundrecht hängt, ohne die Prüffreigabe hier – die geht mit.
    const traegt = p.grund ? Object.assign({}, p.grund, { traegt_pruefen: p.grund.traegt_pruefen - (p.pruef && p.pruef.bis === null ? 1 : 0) }) : null;
    const text = `${p.rechte.map((f) => `„${RECHT[f.recht] || f.recht}“`).join(" und ")} von ${p.konto.name} an ${p.ordner.pfad} entziehen?`
      + (p.eigen ? ` ${p.rechte.length > 1 ? "Es sind deine eigenen Rechte." : "Es ist deine eigene Freigabe."}` : "")
      + (traegt && traegt.traegt_pruefen > 0 ? ` ${traegtText(traegt)}` : "");
    // Entziehen löscht nichts Unwiederbringliches – neu erteilen geht jederzeit (A4: Rückfrage ohne „Endgültig“).
    if (!(await confirm(text, "Entziehen", "", { endgueltig: false }))) return;
    const daten = {};
    if (p.grund) daten.grundrecht = null;
    if (p.pruef) daten.pruefen = null;
    try {
      const r = await api(`${API}/ordner/${p.ordner.id}/freigaben/person/${p.konto.id}`, { method: "PUT", body: daten });
      stand.hinweis = offenHinweis(r, p);
      toast(`${p.konto.name}: ${p.rechte.length > 1 ? "Rechte" : "Freigabe"} entzogen`);
      await nachher();
    } catch (e) { toast(e.message, true); }
  }

  function verlaengernDialog(stand, nachher) {
    const d = stand.daten;
    const eigen = (d.anker_wahl.find((a) => a.id === d.ordner.id) || {}).ende;
    const vorgabe = frueher(frueher(d.grenzen.vorgabe_bis, d.grenzen.pruefen_max), eigen);
    unterDialog(`<h2>Alle Prüffreigaben verlängern</h2>
      <p class="help">Verlängert jede befristete Prüffreigabe an „${esc(d.ordner.pfad)}“ und darunter, die noch gilt oder seit
        höchstens 90 Tagen abgelaufen ist – soweit du sie ändern darfst und das Konto qualifiziert ist. Kürzer wird keine;
        dauerhafte bleiben, wie sie sind.</p>
      <label for="mfv-bis">Neues Ende</label>${datumFeld("mfv-bis", vorgabe)}
      <div class="help">Spätestens ${fmtTag(frueher(d.grenzen.pruefen_max, eigen))}.</div>
      <div id="mfv-ergebnis"></div>
      <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Schließen</button>
        <button class="btn" type="button" id="mfv-ok">Verlängern</button></div>`, (dlg, body) => {
      $("#mfv-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        let bis;
        try { bis = datumWert($("#mfv-bis", body), "Neues Ende"); if (!bis) throw new Error("Bitte ein Enddatum angeben."); }
        catch (e) { S.feldFehler($("#mfv-bis", body), e.message); return; }
        knopf.disabled = true;
        try {
          const r = await api(`${API}/ordner/${d.ordner.id}/freigaben/verlaengern`, { method: "POST", body: { bis } });
          $("#mfv-ergebnis", body).innerHTML = `<p class="notice">${plural(r.verlaengert, "Prüffreigabe", "Prüffreigaben")} bis ${fmtTag(bis)} verlängert.</p>
            ${r.uebersprungen.length ? `<p><strong>Übersprungen:</strong></p><ul class="mf-uebersprungen">${r.uebersprungen.map((u) => `<li>${esc(u.konto)}
              <span class="small muted">${esc(u.ordner)}</span> – ${esc(u.grund)}</li>`).join("")}</ul>` : ""}`;
          knopf.hidden = true;
          await nachher();
        } catch (e) { S.fehlschlag(knopf, e, body); }
      };
    });
  }

  /* --- Der Reiter „Freigaben“ ---------------------------------------------------------------------------------
     Steht im Dialog „Ordner bearbeiten“ (material.js) – Dialog, Reiter und die klebende Knopfzeile unten gehören dort
     hin, hier nur der Inhalt. Die rote Hauptaktion des Reiters ist „Freigabe erteilen“. */
  async function inhalt(el, ordner, optionen) {
    const opt = optionen || {};
    const id = typeof ordner === "object" && ordner ? ordner.id : +ordner;
    if (!el || !id) return;
    el.classList.add("mf");
    el.innerHTML = '<p class="help">Wird geladen …</p>';
    const stand = { vorlage: opt.vorlage && opt.vorlage !== "verlaengern" ? opt.vorlage : null, daten: null, hinweis: "" };
    const dort = opt.dort || ((oid) => { location.href = `/materialablage/ordner/${oid}?freigaben`; });
    try { stand.daten = await api(`${API}/ordner/${id}/freigaben`); }
    catch (e) { el.innerHTML = `<p class="notice">${esc(e.message)}</p>`; return; }
    const d = stand.daten;
    el.innerHTML = `${formHtml(d)}<div id="mf-hinweis"></div><div id="mf-listen">${listenHtml(d)}</div>`;

    // Nach jedem Schreiben: Bescheid an material.js (lädt den Ordner nach dem Schließen neu), dann die Listen frisch.
    async function neuLaden() {
      if (opt.geaendert) opt.geaendert();
      try { stand.daten = await api(`${API}/ordner/${id}/freigaben`); }
      catch (e) {
        // Wer sich selbst herabgesetzt hat, verwaltet den Ordner nicht mehr – der Reiter sagt es, statt leer zu stehen.
        $("#mf-listen", el).innerHTML = `<p class="notice">${esc(e.message)}</p>`;
        $(".mf-neu", el).hidden = true;
        return;
      }
      $("#mf-hinweis", el).innerHTML = stand.hinweis ? `<p class="notice">${stand.hinweis}</p>` : "";
      const offen = $$("details.mf-teil", $("#mf-listen", el)).map((x) => x.open);
      $("#mf-listen", el).innerHTML = listenHtml(stand.daten);
      $$("details.mf-teil", $("#mf-listen", el)).forEach((x, i) => { if (offen[i] !== undefined) x.open = offen[i]; });
      form.zeigen();                        // „… hat hier schon: …“ nach dem neuen Stand
    }

    const form = formVerdrahten(el, stand, neuLaden);
    $("#mf-listen", el).addEventListener("click", (e) => {
      const b = e.target.closest("button[data-act]");
      if (!b) return;
      // Ändern und Entziehen betreffen die Person (Schlüssel „ordner:konto“), nicht eine einzelne Freigabe.
      const p = b.dataset.person ? personZu(stand.daten, b.dataset.person) : null;
      if (b.dataset.act === "aendern" && p) personDialog(p, stand, neuLaden);
      else if (b.dataset.act === "entziehen" && p) personEntziehen(p, stand, neuLaden);
      else if (b.dataset.act === "verlaengern") verlaengernDialog(stand, neuLaden);
      else if (b.dataset.act === "dort") dort(+b.dataset.ordner);
    });
    if (opt.vorlage === "verlaengern") zumAblauf(el, d, opt.fokus);
    else if (opt.fokus) fokus($("#mf-person", el));
  }

  /* „Verlängern“ aus dem Ablaufhinweis im Ordnerkopf. Er zählt alles, was hier und in Unterordnern in 30 Tagen
     abläuft – auch Grundrechte, die „Alle Prüffreigaben verlängern“ nicht betrifft. Läuft eine befristete
     Prüffreigabe ab, die man ändern darf, geht es zu diesem Knopf; sonst zur Personenzeile mit der ersten ablaufenden
     Freigabe (ihr Abschnitt geht auf, der Fokus auf ihr „Ändern“). Läuft inzwischen nichts mehr ab, zum Knopf, sonst wie ohne Rolle. */
  function zumAblauf(el, d, mitFokus) {
    const bald = (f) => f.laeuft_ab_in_tagen !== null && f.laeuft_ab_in_tagen !== undefined;
    const knopf = $("#mf-verlaengern", el);
    const teile = $$("details.mf-teil", $("#mf-listen", el));
    const zeilen = d.direkt.map((f) => [f, teile[0]]).concat(d.unten.map((f) => [f, teile[2]])).filter(([f]) => bald(f));
    let ziel = null;
    if (knopf && (!zeilen.length || zeilen.some(([f]) => f.recht === "pruefen" && f.bis && f.aenderbar))) {
      ziel = knopf;
      knopf.scrollIntoView({ block: "center" });
    } else {
      const [f, teil] = zeilen.find(([x]) => x.aenderbar) || zeilen[0] || [];
      // Die Zeile der Person, zu der die ablaufende Freigabe gehört.
      const zeile = f && teil ? $(`tr[data-person="${f.ordner.id}:${f.konto.id}"]`, teil) : null;
      if (zeile) {
        teil.open = true;
        zeile.scrollIntoView({ block: "center" });
        ziel = $('[data-act="aendern"]', zeile);
        // Ohne „Ändern“ (nicht änderbar) die Zeile selbst – sonst rollte der Fokus aufs Personenfeld zurück nach oben.
        if (!ziel) { zeile.tabIndex = -1; ziel = zeile; }
      }
    }
    if (mitFokus) fokus(ziel || $("#mf-person", el));
  }

  /* --- „Meine Freigaben“ (Übersicht) --------------------------------------------------------------------------
     Jeder Angemeldete, auch ohne Freigabe: Wer keine hat, liest, wer sie vergibt. Gelb, was in 30 Tagen abläuft; bei
     Ablauf steht dabei, wer verlängern kann. */
  async function hinweis(el) {
    if (!el) return;
    let d;
    try { d = await api(`${API}/freigaben/meine`); } catch (e) { el.innerHTML = ""; return; }
    if (!d.freigaben.length) {
      el.innerHTML = d.alles
        ? (d.qualifiziert ? '<p class="help mf-meine-leer">Prüfen kannst du auch als Material-Verwaltung nur mit eigener Prüffreigabe – die gibst du dir am Ordner unter „Bearbeiten“ → „Freigaben“.</p>' : "")
        : '<p class="notice mf-meine-leer">Du hast noch keine Freigabe im Bestand – der Materialwart deiner Gliederung vergibt sie.</p>';
      return;
    }
    const wichtig = d.freigaben.filter((f) => !f.gueltig || f.laeuft_ab_in_tagen !== null || !f.wirkt);
    const wer = (f) => (f.verwalter.length ? f.verwalter.join(", ").replace(/, ([^,]*)$/, " oder $1") : "die Material-Verwaltung");
    el.innerHTML = `<details class="section mat-auf mf-meine"${wichtig.length ? " open" : ""}><summary>Meine Freigaben <span class="mf-zahl">${d.freigaben.length}</span></summary>
      <ul class="mf-meine-liste">${d.freigaben.map((f) => `<li class="${!f.gueltig ? "abgelaufen" : f.laeuft_ab_in_tagen !== null ? "bald" : ""}">
        <span class="mf-meine-ordner">${f.gueltig && f.wirkt ? `<a href="/materialablage/ordner/${f.ordner.id}">${esc(f.ordner.pfad)}</a>` : esc(f.ordner.pfad)}</span>
        <span class="mf-meine-recht">${esc(RECHT[f.recht] || f.recht)} · ${bisText(f.bis)}</span> ${zustand(f)}
        ${!f.gueltig || f.laeuft_ab_in_tagen !== null ? `<div class="small muted">Verlängern kann: ${esc(wer(f))}.</div>` : ""}
        ${f.wirkt_nicht === "Qualifikation fehlt" ? `<div class="small muted">${esc(OHNE_QUALIFIKATION)}</div>`
          : f.wirkt_nicht === "dauerhaft nur mit lesen oder verwalten"
            ? `<div class="small muted">${esc(`${OHNE_GRUNDRECHT} Vergeben kann es: ${wer(f)}.`)}</div>` : ""}</li>`).join("")}</ul>
      ${d.zugang ? "" : '<p class="help">Deine Freigaben wirken erst, wenn die Verwaltung dir die Materialablage freischaltet.</p>'}
    </details>`;
  }

  /* Im Ordnerkopf (nur für Verwalter): wie viele Freigaben im Zweig bald ablaufen – ein Hinweis, kein Menü. Sein Knopf
     „Verlängern“ öffnet über material.js „Ordner bearbeiten“ im Reiter „Freigaben“ beim Verlängern-Knopf. */
  async function kopfhinweis(el, ordner, verlaengern) {
    if (!el || !ordner) return;
    let d;
    try { d = await api(`${API}/ordner/${ordner.id || ordner}/freigaben`); } catch (e) { el.innerHTML = ""; return; }
    el.innerHTML = d.laeuft_ab ? `<p class="notice mf-kopf">${plural(d.laeuft_ab, "Freigabe läuft", "Freigaben laufen")} in den nächsten 30 Tagen ab.
      ${verlaengern ? '<button class="btn secondary small" type="button">Verlängern</button>' : ""}</p>` : "";
    const b = $("button", el);
    if (b) b.addEventListener("click", () => verlaengern());
  }

  window.MatFreigaben = { inhalt, hinweis, kopfhinweis };
})();
