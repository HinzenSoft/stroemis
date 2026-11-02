/* Freigaben je Ordner (Phase 2 · Lieferung 1, Abschnitt 4.2): der Reiter „Freigaben“ im Dialog „Ordner bearbeiten“ mit
   Vorlagen (Führungskraft, Materialwart, Prüfer, Externer Prüfer …), den Listen „Hier vergeben“, „Geerbt von oben“,
   „In Unterordnern“ und „Verlauf“, dem Knopf „Alle Prüffreigaben verlängern“ – dazu der Hinweis „Meine
   Freigaben“ auf der Übersicht. Seit dem 02.11.2026 (Wunsch des Nutzers) eine Zeile je Person in allen drei Listen
   (geerbt und unten je Person und Ordner) mit EINEM „Ändern“ – Dialog „Rechte ändern“ für Grundrecht, Prüffreigabe
   und Notiz, gespeichert in einer Transaktion (PUT …/freigaben/person/<konto>) – und „Entziehen“ für alle Rechte der
   Person dort; Verlauf, „Meine Freigaben“ und die Leitstelle bleiben je Freigabe. Stellt window.MatFreigaben bereit:
     inhalt(element, ordner, optionen?)  füllt element (den Reiter) mit Hinweis, „Freigabe anlegen“ und den Listen; Dialog,
                                Reiter und Knopfzeile („Schließen“) gehören material.js. ordner: das Objekt der
                                Ordneransicht (oder seine Kennung). optionen:
                                  vorlage    „materialwart“ usw. (?freigaben=<vorlage> nach „Gliederung anlegen“) oder
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
  // Die Vorlagen des Reiters: ein Grundrecht (dauerhaft, wenn man selbst dauerhaft verwaltet) und/oder eine
  // Prüffreigabe. Befristet ist nur noch der externe Prüfer; wer lesen oder verwalten mitbekommt, prüft dauerhaft
  // (pruefDauer: „dauerhaft“ vorgewählt – angeboten nur, wer selbst dauerhaft verwaltet). „Einzeln“ lässt alles frei.
  const VORLAGEN = [
    { k: "fuehrungskraft", t: "Führungskraft", grund: "lesen", pruefen: false,
      text: "lesen – Bestand, Protokolle, Export, Lebensläufe und Journal ansehen, Mängel melden (sperrt)" },
    { k: "materialwart", t: "Materialwart", grund: "verwalten", pruefen: false,
      text: "verwalten – Ordner und Artikel pflegen, aussondern, Freigaben vergeben; prüfen nur mit eigener Prüffreigabe" },
    { k: "pruefer", t: "Prüfer", grund: "lesen", pruefen: true, pruefDauer: true, text: "lesen und prüfen" },
    { k: "materialwart_pruefer", t: "Materialwart und Prüfer", grund: "verwalten", pruefen: true, pruefDauer: true,
      text: "verwalten und prüfen" },
    { k: "extern", t: "Externer Prüfer", grund: null, pruefen: true,
      text: "nur prüfen bis … – die Prüfsicht: Artikel und Prüfungen, kein Export, kein Journal; höchstens 24 Monate" },
    { k: "einzeln", t: "Einzeln", grund: null, pruefen: false, text: "Grundrecht und Prüffreigabe frei wählen" },
  ];
  const OHNE_QUALIFIKATION = "Prüfen erst mit Häkchen durch die Verwaltung und Urkundennummer im Profil.";
  const OHNE_GRUNDRECHT = "Dauerhaft prüft nur, wer hier auch lesen oder verwalten hat – sonst wirkt die Prüffreigabe nicht.";
  // Hilfe unter „Prüfen bis“, wenn „dauerhaft“ gewählt ist.
  const PRUEFEN_DAUERHAFT = "Gilt, solange die Person hier lesen oder verwalten hat – nur externe Prüfer brauchen ein Enddatum.";

  const plural = S.plural;              // „1 Bild“, „3 Bilder“ – app-weit in common.js (UI/UX vor dem Merge, A11)
  const fokus = (el) => { if (el && !window.matchMedia("(pointer: coarse)").matches) el.focus(); };
  // „2027-12-31“ → „31.12.2027“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const fmtTag = (iso) => { const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}.${m[2]}.${m[1]}` : ""; };
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
      <fieldset class="mf-vorlagen"><legend>Vorlage</legend>
        ${VORLAGEN.map((v) => `<label class="mf-vorlage"><input type="radio" name="mf-vorlage" value="${v.k}">
          <span><strong>${esc(v.t)}</strong><span class="small">${esc(v.text)}</span></span></label>`).join("")}
      </fieldset>
      <p class="help mf-quali" id="mf-quali" hidden>${esc(OHNE_QUALIFIKATION)}</p>
      <div class="mf-einzeln" id="mf-einzeln" hidden>
        <div class="field-row">
          <div><label for="mf-grund">Grundrecht</label><select id="mf-grund"><option value="">–</option><option value="lesen">lesen</option>
            <option value="verwalten">verwalten</option></select></div>
          <div><label class="inline mf-pruefen-wahl"><input type="checkbox" id="mf-pruefen"> Prüffreigabe</label></div>
        </div>
      </div>
      <div class="field-row mf-enden">
        <div id="mf-grund-ende" hidden><label for="mf-grund-bis">Grundrecht bis</label>
          <label class="inline" id="mf-dauerhaft-wahl"><input type="checkbox" id="mf-dauerhaft" checked> dauerhaft</label>
          ${datumFeld("mf-grund-bis", "", "Grundrecht bis")}
          <div class="help" id="mf-grund-hilfe"></div></div>
        <div id="mf-pruefen-ende" hidden><label for="mf-pruefen-bis">Prüfen bis</label>
          <label class="inline" id="mf-pruefen-dauerhaft-wahl" hidden><input type="checkbox" id="mf-pruefen-dauerhaft"> dauerhaft</label>
          ${datumFeld("mf-pruefen-bis", "", "Prüfen bis")}
          <div class="help" id="mf-pruefen-hilfe"></div></div>
      </div>
      <details class="mf-notiz"><summary>Notiz</summary>
        <input type="text" id="mf-notiz" maxlength="200" aria-label="Notiz" aria-describedby="mf-notiz-hilfe">
        <div class="help" id="mf-notiz-hilfe">Eine Zeile, höchstens 200 Zeichen – sehen nur Verwalter dieses Ordners und die
          Material-Verwaltung, die Person selbst also nur, wenn sie hier mitverwaltet. Keine sensiblen Angaben.</div></details>
      <div class="btn-row mf-erteilen-reihe"><button class="btn" type="button" id="mf-erteilen">Freigabe erteilen</button></div>
    </details>`;
  }

  /* Der Zustand des Formulars: gewählte Person, Vorlage und Anker – daraus folgen die sichtbaren Felder, die Vorgaben
     für „bis“ und welche Vorlagen gehen (prüfen nur mit Qualifikation; „dauerhaft“ nur, wer selbst dauerhaft
     verwaltet – beim Prüfen dazu nur, wo die Person ein Grundrecht bekommt oder schon hat, nie beim externen Prüfer). */
  function formVerdrahten(body, stand, nachher) {
    const feld = (id) => $("#" + id, body);
    let person = null;
    let suchzeit = null;
    let suchlauf = 0;
    const anker = () => stand.daten.anker_wahl.find((a) => a.id === +feld("mf-anker").value) || stand.daten.anker_wahl[0];
    const vorlage = () => VORLAGEN.find((v) => v.k === (($('input[name="mf-vorlage"]:checked', body) || {}).value));
    const pruefenEnde = () => frueher(frueher(stand.daten.grenzen.vorgabe_bis, stand.daten.grenzen.pruefen_max), anker().ende);

    function wunsch() {
      const v = vorlage();
      if (!v) return { grund: null, pruefen: false };
      if (v.k === "einzeln") return { grund: feld("mf-grund").value || null, pruefen: feld("mf-pruefen").checked };
      return { grund: v.grund, pruefen: v.pruefen };
    }

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

    // Hat die gewählte Person am gewählten Anker schon Rechte, sagt es der Satz über den Vorlagen – mit „Rechte ändern“
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
      $$('input[name="mf-vorlage"]', body).forEach((r) => {
        const v = VORLAGEN.find((x) => x.k === r.value);
        r.disabled = v.pruefen && !quali;
        if (r.disabled && r.checked) r.checked = false;
      });
      feld("mf-pruefen").disabled = !quali;
      if (!quali) feld("mf-pruefen").checked = false;
      feld("mf-quali").hidden = quali;
      feld("mf-einzeln").hidden = !(vorlage() && vorlage().k === "einzeln");
      const w = wunsch();
      feld("mf-grund-ende").hidden = !w.grund;
      feld("mf-pruefen-ende").hidden = !w.pruefen;
      // Dauerhaft nur, wer hier selbst dauerhaft verwaltet; sonst endet das Grundrecht spätestens mit dem eigenen.
      const dauerhaftGeht = a.ende === null;
      feld("mf-dauerhaft-wahl").hidden = !dauerhaftGeht;
      if (!dauerhaftGeht) feld("mf-dauerhaft").checked = false;
      feld("mf-grund-bis").hidden = feld("mf-dauerhaft").checked;
      feld("mf-grund-hilfe").textContent = dauerhaftGeht ? "" : `Du verwaltest hier bis ${fmtTag(a.ende)} – länger vergibst du nichts.`;
      // Prüfen dauerhaft: dazu ein Grundrecht – aus dieser Vorlage (bzw. „Einzeln“ mit Grundrecht) oder schon vorhanden.
      // Der externe Prüfer braucht immer ein Enddatum.
      const v = vorlage();
      const pruefDauerGeht = dauerhaftGeht && w.pruefen && !!v && v.k !== "extern" && (!!w.grund || grundrechtDort(a));
      feld("mf-pruefen-dauerhaft-wahl").hidden = !pruefDauerGeht;
      if (!pruefDauerGeht) feld("mf-pruefen-dauerhaft").checked = false;
      const pruefDauer = feld("mf-pruefen-dauerhaft").checked;
      feld("mf-pruefen-bis").hidden = pruefDauer;
      feld("mf-pruefen-hilfe").textContent = pruefDauer ? PRUEFEN_DAUERHAFT
        : `Spätestens ${fmtTag(frueher(stand.daten.grenzen.pruefen_max, a.ende))} – höchstens 24 Monate`
          + (a.ende ? " und nicht länger als deine eigene Verwalterfreigabe." : ".");
    }

    // Vorgaben je Anker: dauerhaft, wo man selbst dauerhaft verwaltet, sonst das eigene Ende; prüfen bis zum 31.12. des
    // Folgejahres, gekappt.
    function vorgabenSetzen() {
      const a = anker();
      feld("mf-pruefen-bis").value = fmtTag(pruefenEnde());
      feld("mf-dauerhaft").checked = a.ende === null;
      feld("mf-grund-bis").value = a.ende === null ? "" : fmtTag(a.ende);
      ["mf-pruefen-bis", "mf-grund-bis"].forEach((id) => feld(id).classList.remove("ungueltig"));
    }
    // Vorlage gewechselt: „dauerhaft“ beim Prüfen vorwählen, wo die Vorlage es vorsieht (Prüfer, Materialwart und
    // Prüfer); angeboten wird es nur, wo es geht (zeigen).
    function vorlageGewechselt() {
      const v = vorlage();
      feld("mf-pruefen-dauerhaft").checked = !!(v && v.pruefDauer);
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
    feld("mf-dauerhaft").addEventListener("change", () => { if (!feld("mf-dauerhaft").checked && !feld("mf-grund-bis").value) feld("mf-grund-bis").value = fmtTag(pruefenEnde()); zeigen(); });
    feld("mf-pruefen-dauerhaft").addEventListener("change", () => { if (!feld("mf-pruefen-dauerhaft").checked && !feld("mf-pruefen-bis").value) feld("mf-pruefen-bis").value = fmtTag(pruefenEnde()); zeigen(); });
    $$('input[name="mf-vorlage"]', body).forEach((x) => x.addEventListener("change", vorlageGewechselt));
    $$("#mf-grund, #mf-pruefen", body).forEach((x) => x.addEventListener("change", zeigen));

    feld("mf-erteilen").addEventListener("click", async (ev) => {
      const knopf = ev.currentTarget;
      if (knopf.disabled) return;
      // Fehler am Feld (UI/UX vor dem Merge, A2): Satz darunter, Fokus darauf.
      if (!person) { S.feldFehler(feld("mf-person"), "Bitte zuerst eine Person wählen."); return; }
      if (!vorlage()) { S.feldFehler($('input[name="mf-vorlage"]', body), "Bitte eine Vorlage wählen."); return; }
      const w = wunsch();
      if (!w.grund && !w.pruefen) { S.feldFehler(feld("mf-grund"), "Bitte ein Grundrecht, eine Prüffreigabe oder beides wählen."); return; }
      // pruefen: true mit pruefen_bis null heißt dauerhaft – ob das geht, entscheidet der Server (Grundrecht am Anker).
      const daten = { user_id: person.id, grundrecht: w.grund, grund_bis: null, pruefen: w.pruefen, pruefen_bis: null };
      let datumFeld = null;
      try {
        if (w.grund && !feld("mf-dauerhaft").checked) {
          datumFeld = feld("mf-grund-bis");
          daten.grund_bis = datumWert(datumFeld, "Grundrecht bis");
          if (!daten.grund_bis) throw new Error("Bitte ein Enddatum für das Grundrecht angeben – oder „dauerhaft“.");
        }
        if (w.pruefen && !feld("mf-pruefen-dauerhaft").checked) {
          datumFeld = feld("mf-pruefen-bis");
          daten.pruefen_bis = datumWert(datumFeld, "Prüfen bis");
          if (!daten.pruefen_bis) {
            throw new Error(`Bitte ein Enddatum für die Prüffreigabe angeben${feld("mf-pruefen-dauerhaft-wahl").hidden ? "" : " – oder „dauerhaft“"}.`);
          }
        }
      } catch (e) { S.feldFehler(datumFeld, e.message); return; }
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
      } catch (e) { S.fehlschlag(knopf, e, body); }
      finally { knopf.disabled = false; }
    });

    if (stand.vorlage) {
      const r = $(`input[name="mf-vorlage"][value="${CSS.escape(stand.vorlage)}"]`, body);
      if (r) r.checked = true;
    }
    vorgabenSetzen();
    vorlageGewechselt();
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
     PUT …/ordner/<anker>/freigaben/person/<konto> in EINER Transaktion – alles oder nichts. Lehnt der Server ab,
     bleibt der Dialog mit allen Eingaben offen; die Meldung beginnt mit „„Grundrecht“: “ bzw. „„Prüffreigabe“: “ und
     steht am Feld dieses Rechts. Ein Recht, das man nicht ändern darf (reicht weiter als das eigene Verwalten, Nr. 4),
     steht nur als Text da und wird nicht mitgeschickt. */
  const EIGENE_NEU = "Dir selbst vergibst du keine Prüffreigabe – das macht ein anderer Verwalter oder die Material-Verwaltung.";
  const NUR_PV = "Entziehen nur über die Material-Verwaltung – sonst verwaltet hier niemand so lange wie du.";
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
    const pruefenEnde = frueher(frueher(d.grenzen.vorgabe_bis, d.grenzen.pruefen_max), ende);
    const grundFrei = !g || g.aenderbar;
    const pruefFrei = !pf || pf.aenderbar;
    const fest = (f) => `<p class="mfp-fest"><strong>${esc(rechtText(f))}</strong> – ändern kann es nur, wer mindestens so lange verwaltet, oder die Material-Verwaltung.</p>`;
    // Grundrecht: Die eigene Zeile nur herabsetzen (verwalten → lesen) oder entziehen, neu gibt es für sich selbst keins.
    // „–“ fehlt, wenn das Entziehen an Nr. 7 scheitert (eigene letzte Verwalterfreigabe).
    let grundHtml;
    if (!grundFrei) {
      grundHtml = `<p class="mfp-titel">Grundrecht</p>${fest(g)}`;
    } else if (p.eigen && !g) {
      grundHtml = '<p class="mfp-titel">Grundrecht</p><p class="help">Keins – ein Grundrecht vergibt dir ein anderer Verwalter oder die Material-Verwaltung.</p>';
    } else {
      const wahl = (p.eigen ? (g.recht === "verwalten" ? ["lesen", "verwalten"] : ["lesen"]) : ["lesen", "verwalten"]);
      const ohne = !(g && g.entziehbar === false);
      const grundDauerGeht = selbstDauerhaft && (!p.eigen || (g && g.bis === null));
      grundHtml = `<label for="mfp-grund">Grundrecht</label>
        <select id="mfp-grund">${ohne ? `<option value=""${g ? "" : " selected"}>–</option>` : ""}${wahl.map((r) => `<option value="${r}"${g && g.recht === r ? " selected" : ""}>${RECHT[r]}</option>`).join("")}</select>
        ${ohne ? "" : `<p class="help">${esc(NUR_PV)}</p>`}
        <div class="mfp-ende" id="mfp-grund-ende"><label for="mfp-grund-bis">Grundrecht bis</label>
          ${grundDauerGeht ? `<label class="inline"><input type="checkbox" id="mfp-grund-dauerhaft"${!g || g.bis === null ? " checked" : ""}> dauerhaft</label>` : ""}
          ${datumFeld("mfp-grund-bis", g && g.bis ? g.bis : (selbstDauerhaft ? pruefenEnde : ende), "Grundrecht bis")}
          ${selbstDauerhaft ? "" : `<div class="help">Du verwaltest hier bis ${fmtTag(ende)} – länger vergibst du nichts.</div>`}</div>
        <p class="help" id="mfp-traegt" hidden>${esc(g ? traegtText(g) : "")}</p>`;
    }
    // Prüffreigabe: neu nur mit Qualifikation und nicht für sich selbst (Nr. 5, 8). „dauerhaft“ nur, wer selbst
    // dauerhaft verwaltet (die eigene nur, wenn sie es schon ist) – und nur mit Grundrecht (im Dialog gewählt, darüber
    // vorhanden) oder wenn sie schon dauerhaft ist.
    let pruefHtml;
    if (!pruefFrei) {
      pruefHtml = `<p class="mfp-titel">Prüffreigabe</p>${fest(pf)}`;
    } else {
      const neuGesperrt = !pf && (p.eigen || !p.konto.qualifiziert);
      pruefHtml = `<div class="feld-gruppe"><label class="inline"><input type="checkbox" id="mfp-pruefen"${pf ? " checked" : ""}${neuGesperrt ? " disabled" : ""}> Prüffreigabe</label></div>
        ${neuGesperrt ? `<p class="help">${esc(p.eigen ? EIGENE_NEU : OHNE_QUALIFIKATION)}</p>` : ""}
        <div class="mfp-ende" id="mfp-pruefen-ende"><label for="mfp-pruefen-bis">Prüfen bis</label>
          <label class="inline" id="mfp-pruefen-dauer-wahl"><input type="checkbox" id="mfp-pruefen-dauerhaft"${pf && pf.bis === null ? " checked" : ""}> dauerhaft</label>
          ${datumFeld("mfp-pruefen-bis", pf && pf.bis ? pf.bis : pruefenEnde, "Prüfen bis")}
          <div class="help" id="mfp-pruefen-hilfe"></div></div>
        <p class="help" id="mfp-ohne-grund" hidden>${esc(OHNE_GRUNDRECHT)}</p>`;
    }
    // Die Notiz: EIN Feld für die Person an diesem Ordner, gespeichert auf jedes Recht, das man hier ändern darf.
    const mitNotiz = p.rechte.filter((f) => "notiz" in f && f.aenderbar);
    const notiz = g && mitNotiz.includes(g) ? g.notiz : (mitNotiz[0] || {}).notiz;
    const abweichend = g && pf && mitNotiz.length === 2 && (g.notiz || "") !== (pf.notiz || "")
      ? `<div class="help">${pf.notiz ? `Die Prüffreigabe hatte die Notiz „${esc(pf.notiz)}“` : "Die Prüffreigabe hatte keine Notiz"} – beim Speichern gilt diese eine Notiz für beide.</div>` : "";
    unterDialog(`<h2>Rechte ändern</h2>
      <p>${personHtml(p.konto)} · ${esc(p.ordner.pfad)}</p>
      ${p.eigen ? '<p class="help">Deine eigenen Rechte kannst du nur verkürzen, herabsetzen oder entziehen.</p>' : ""}
      <div class="mfp-teil">${grundHtml}</div>
      <div class="mfp-teil">${pruefHtml}</div>
      ${mitNotiz.length ? `<label for="mfp-notiz">Notiz</label><input type="text" id="mfp-notiz" maxlength="200" value="${esc(notiz || "")}">
        ${abweichend}<div class="help">Sehen nur Verwalter dieses Ordners und die Material-Verwaltung – die Person selbst nur, wenn sie hier
          mitverwaltet. Keine sensiblen Angaben.</div>` : ""}
      <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Abbrechen</button>
        <button class="btn" type="button" id="mfp-ok">Speichern</button></div>`, (dlg, body) => {
      const feld = (id) => $("#" + id, body);
      const grundWahl = feld("mfp-grund");
      const grundDauer = feld("mfp-grund-dauerhaft");
      const pruefWahl = feld("mfp-pruefen");
      const pruefDauer = feld("mfp-pruefen-dauerhaft");
      // Das Grundrecht nach dem Dialog: gewählt, oder unverändert, wo man es nicht ändern darf.
      const grundDanach = () => (grundWahl ? grundWahl.value : (g ? g.recht : ""));
      function zeigen() {
        if (grundWahl) {
          feld("mfp-grund-ende").hidden = !grundWahl.value;
          feld("mfp-grund-bis").hidden = !!(grundDauer && grundDauer.checked);
          // Was an diesem Grundrecht hängt, sagt der Dialog, sobald es wegfällt oder ein Ende bekommt.
          feld("mfp-traegt").hidden = !(g && g.traegt_pruefen && (!grundWahl.value || !(grundDauer && grundDauer.checked)));
        }
        if (pruefWahl) {
          feld("mfp-pruefen-ende").hidden = !pruefWahl.checked;
          const dauerGeht = selbstDauerhaft && (!p.eigen || (pf && pf.bis === null))
            && (!!grundDanach() || grundrechtOben(p, d) || (pf && pf.bis === null));
          feld("mfp-pruefen-dauer-wahl").hidden = !dauerGeht;
          if (!dauerGeht) pruefDauer.checked = false;
          feld("mfp-pruefen-bis").hidden = pruefDauer.checked;
          feld("mfp-pruefen-hilfe").textContent = pruefDauer.checked ? PRUEFEN_DAUERHAFT
            : `Spätestens ${fmtTag(frueher(d.grenzen.pruefen_max, ende))} – höchstens 24 Monate`
              + (selbstDauerhaft ? "." : " und nicht länger als deine eigene Verwalterfreigabe.");
          feld("mfp-ohne-grund").hidden = !(pruefWahl.checked && pruefDauer.checked && !grundDanach() && !grundrechtOben(p, d));
        }
      }
      [grundWahl, grundDauer, pruefWahl, pruefDauer].forEach((x) => { if (x) x.addEventListener("change", zeigen); });
      zeigen();

      feld("mfp-ok").onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        const daten = {};
        let datum = null;
        try {
          if (grundWahl) {
            if (grundWahl.value) {
              let bis = null;
              if (!(grundDauer && grundDauer.checked)) {
                datum = feld("mfp-grund-bis");
                bis = datumWert(datum, "Grundrecht bis");
                if (!bis) throw new Error(`Bitte ein Enddatum für das Grundrecht angeben${grundDauer ? " – oder „dauerhaft“" : ""}.`);
              }
              daten.grundrecht = { recht: grundWahl.value, bis };
            } else if (g) daten.grundrecht = null;
          }
          if (pruefWahl && !pruefWahl.disabled) {
            if (pruefWahl.checked) {
              let bis = null;
              if (!pruefDauer.checked) {
                datum = feld("mfp-pruefen-bis");
                bis = datumWert(datum, "Prüfen bis");
                if (!bis) {
                  throw new Error(`Bitte ein Enddatum für die Prüffreigabe angeben${feld("mfp-pruefen-dauer-wahl").hidden ? "" : " – oder „dauerhaft“"}.`);
                }
              }
              daten.pruefen = { bis };
            } else if (pf) daten.pruefen = null;
          }
        } catch (e) { S.feldFehler(datum, e.message); return; }
        if (feld("mfp-notiz")) daten.notiz = feld("mfp-notiz").value.trim();
        if (!("grundrecht" in daten) && !("pruefen" in daten)) {
          // Nichts gewählt und nichts da: Hinweis am Grundrecht statt einer leeren Anfrage.
          S.feldFehler(grundWahl || pruefWahl, "Bitte ein Grundrecht, eine Prüffreigabe oder beides wählen – oder „Abbrechen“.");
          return;
        }
        // Fällt ein Recht weg, vorher fragen (Entziehen vernichtet nichts – neu erteilen geht jederzeit).
        const weg = [g && daten.grundrecht === null ? g : null, pf && daten.pruefen === null ? pf : null].filter(Boolean);
        if (weg.length) {
          const text = `${weg.map((f) => `„${RECHT[f.recht] || f.recht}“`).join(" und ")} von ${p.konto.name} an ${p.ordner.pfad} entziehen?`
            + (p.eigen ? " Es ist deine eigene Freigabe." : "") + (weg.includes(g) && g.traegt_pruefen ? ` ${traegtText(g)}` : "");
          if (!(await confirm(text, "Entziehen", "", { endgueltig: false }))) return;
        }
        knopf.disabled = true;
        try {
          const r = await api(`${API}/ordner/${p.ordner.id}/freigaben/person/${p.konto.id}`, { method: "PUT", body: daten });
          dlg.close();
          toast(`${p.konto.name}: Rechte geändert`);
          stand.hinweis = offenHinweis(r, p);
          await nachher();
        } catch (e) {
          // Die Meldung nennt das Recht – an dessen Datumsfeld (wenn sichtbar), sonst an seiner Auswahl.
          const m = String((e && e.message) || "").match(/^„(Grundrecht|Prüffreigabe)“/);
          const ziel = !m ? null : m[1] === "Grundrecht"
            ? (sichtbar(feld("mfp-grund-bis")) ? feld("mfp-grund-bis") : grundWahl)
            : (sichtbar(feld("mfp-pruefen-bis")) ? feld("mfp-pruefen-bis") : pruefWahl);
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
     Freigabe (ihr Abschnitt geht auf, der Fokus auf ihr „Ändern“). Läuft inzwischen nichts mehr ab, zum Knopf, sonst wie ohne Vorlage. */
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
