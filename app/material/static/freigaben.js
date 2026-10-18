/* Freigaben je Ordner (Phase 2 · Lieferung 1, Abschnitt 4.2): der Reiter „Freigaben“ im Dialog „Ordner bearbeiten“ mit
   Vorlagen (Führungskraft, Materialwart, Prüfer, Externer Prüfer …), den Listen „Hier vergeben“, „Geerbt von oben“,
   „In Unterordnern“ und „Verlauf“, dem Knopf „Alle Prüffreigaben verlängern bis …“ – dazu der Hinweis „Meine
   Freigaben“ auf der Übersicht. Stellt window.MatFreigaben bereit:
     inhalt(element, ordner, optionen?)  füllt element (den Reiter) mit Hinweis, „+ Freigabe“ und den Listen; Dialog,
                                Reiter und Knopfzeile („Schließen“) gehören material.js. ordner: das Objekt der
                                Ordneransicht (oder seine Kennung). optionen:
                                  vorlage    „materialwart“ usw. (?freigaben=<vorlage> nach „+ Gliederung“) oder
                                             „verlaengern“ (springt zum Knopf „Alle Prüffreigaben verlängern“)
                                  fokus      nach dem Laden ins Formular (bzw. auf „verlängern“) – sonst bleibt der
                                             Fokus, wo er ist (etwa auf dem Reiter)
                                  geaendert  wird nach jedem Schreiben gerufen (Erteilen, Ändern, Entziehen,
                                             Verlängern) – die Ordneransicht lädt nach dem Schließen neu
                                  dort(id)   „Dort öffnen“ an einer geerbten Zeile; ohne: zur Ordneransicht mit
                                             ?freigaben (öffnet dort „Ordner bearbeiten“ auf diesem Reiter)
     hinweis(element)           „Meine Freigaben“ auf der Übersicht – eigene Freigaben, gelb, was bald abläuft
     kopfhinweis(element, ordner, verlaengern?)  „n Freigaben laufen in den nächsten 30 Tagen ab“ im Ordnerkopf (nur
                                für Verwalter); der Knopf „Verlängern …“ ruft verlaengern() – ohne gibt es ihn nicht
   material.js ruft sie auf. Der Server prüft jede Regel selbst (services/freigaben.py); ausgeblendet wird hier nur,
   was ohnehin scheitern würde. */
(function () {
  if (!window.S) return;
  const { esc, api, toast, confirm } = S;
  const API = "/api/material";
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const RECHT = { lesen: "lesen", verwalten: "verwalten", pruefen: "prüfen" };
  // Die Vorlagen des Dialogs: ein Grundrecht (dauerhaft, wenn man selbst dauerhaft verwaltet) und/oder eine
  // Prüffreigabe bis zu einem Tag. „Einzeln …“ lässt beides frei wählen.
  const VORLAGEN = [
    { k: "fuehrungskraft", t: "Führungskraft", grund: "lesen", pruefen: false,
      text: "lesen – Bestand, Protokolle, Export, Lebensläufe und Journal ansehen" },
    { k: "materialwart", t: "Materialwart", grund: "verwalten", pruefen: false,
      text: "verwalten – Ordner und Artikel pflegen, aussondern, Freigaben vergeben; prüfen nur mit eigener Prüffreigabe" },
    { k: "pruefer", t: "Prüfer", grund: "lesen", pruefen: true, text: "lesen und prüfen bis …" },
    { k: "materialwart_pruefer", t: "Materialwart und Prüfer", grund: "verwalten", pruefen: true, text: "verwalten und prüfen bis …" },
    { k: "extern", t: "Externer Prüfer", grund: null, pruefen: true,
      text: "nur prüfen bis … – die Prüfsicht: Artikel und Prüfungen, kein Export, kein Journal" },
    { k: "einzeln", t: "Einzeln …", grund: null, pruefen: false, text: "Grundrecht und Prüffreigabe frei wählen" },
  ];
  const OHNE_QUALIFIKATION = "Prüfen erst mit Häkchen durch die Verwaltung und Urkundennummer im Profil.";

  const plural = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;
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

  /* Zustand einer Zeile: gültig · läuft in n Tagen ab (gelb) · abgelaufen am … (grau) · wirkt nicht. */
  function zustand(f) {
    if (!f.gueltig) return `<span class="mf-zustand abgelaufen">abgelaufen am ${fmtTag(f.bis)}</span>`;
    if (f.wirkt === false) {
      const grund = f.konto && !f.konto.aktiv ? "Konto deaktiviert" : f.recht === "pruefen" ? "Qualifikation fehlt" : "Konto ohne Namen";
      return `<span class="mf-zustand wirkt-nicht">wirkt nicht – ${grund}</span>`;
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
     halb ausgefülltem „+ Freigabe“ und ungespeicherten Eingaben im Reiter „Ordner“ stehen, und man kehrt danach in
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
    if (onOpen) onOpen(dlg, body);
    return dlg;
  }

  /* --- Listen ------------------------------------------------------------------------------------------------ */
  function personHtml(k) {
    return `<strong>${esc(k.name)}</strong>${k.gliederung ? ` <span class="small muted">${esc(k.gliederung)}</span>` : ""}
      ${k.aktiv === false ? ' <span class="badge grey">deaktiviert</span>' : ""}`;
  }

  // art: „direkt“ (hier vergeben), „geerbt“ (von oben, nur lesbar), „unten“ (in Unterordnern, mit Pfad).
  function zeileHtml(f, art) {
    const quali = f.recht === "pruefen" && !f.konto.qualifiziert ? ' <span class="badge">Qualifikation fehlt</span>' : "";
    const ordner = art === "geerbt" ? `<div class="small muted">geerbt von ${esc(f.ordner.pfad)}</div>`
      : art === "unten" ? `<div class="small muted">${esc(f.ordner.pfad)}</div>` : "";
    let knoepfe = "";
    if (art === "geerbt") {
      // Geerbtes ändert man dort, wo es vergeben ist – wer jenen Ordner verwaltet, springt hin.
      if (f.aenderbar) knoepfe = `<button class="btn secondary small" type="button" data-act="dort" data-ordner="${f.ordner.id}">Dort öffnen</button>`;
    } else if (f.aenderbar) {
      // „Entziehen“ nur, wenn es gelingt: Die eigene Verwalterfreigabe bleibt, solange sonst niemand die Gliederung so
      // lange verwaltet (1.6 Nr. 7) – dann steht statt des Knopfs, wer helfen kann.
      knoepfe = `<button class="btn secondary small" type="button" data-act="aendern" data-id="${f.id}">Ändern</button>
        ${f.entziehbar === false ? "" : `<button class="btn secondary small" type="button" data-act="entziehen" data-id="${f.id}">Entziehen</button>`}`;
    }
    const nurVerwaltung = art !== "geerbt" && f.aenderbar && f.entziehbar === false
      ? '<div class="small muted mf-nur-pv">Entziehen nur über die Plattform-Verwaltung – sonst verwaltet hier niemand so lange wie du.</div>' : "";
    return `<tr${f.gueltig ? "" : ' class="mf-alt"'}>
      <td data-l="Person" class="mf-k-person">${personHtml(f.konto)}${f.eigen ? ' <span class="badge grey">du</span>' : ""}${quali}${ordner}</td>
      <td data-l="Recht" class="mf-k-halb">${esc(RECHT[f.recht] || f.recht)}</td>
      <td data-l="bis" class="mf-k-halb">${bisText(f.bis)}</td>
      <td data-l="Zustand">${zustand(f)}</td>
      ${art === "geerbt" ? "" : `<td data-l="Notiz" class="mf-notiztext">${f.notiz ? esc(f.notiz) : '<span class="muted">–</span>'}</td>`}
      <td data-l="Vergeben" class="small">${esc(f.vergeben_von || "")}${f.seit ? ` am ${esc(S.fmtDate(f.seit))}` : ""}</td>
      <td class="tabelle-aktionen"><div class="btn-row">${knoepfe}</div>${nurVerwaltung}</td></tr>`;
  }

  function tabelleHtml(liste, art, leerText) {
    if (!liste.length) return `<p class="mat-leer">${esc(leerText)}</p>`;
    return `<table class="list mf-tabelle"><thead><tr><th>Person</th><th>Recht</th><th>bis</th><th>Zustand</th>
      ${art === "geerbt" ? "" : "<th>Notiz</th>"}<th>Vergeben</th><th></th></tr></thead>
      <tbody>${liste.map((f) => zeileHtml(f, art)).join("")}</tbody></table>`;
  }

  function verlaufHtml(liste) {
    if (!liste.length) return '<p class="mat-leer">Noch nichts vergeben oder geändert.</p>';
    const was = (e) => {
      const recht = `„${RECHT[e.recht] || e.recht || "?"}“`;
      if (e.aktion === "freigabe_erteilt") return `${recht} an ${esc(e.konto)} erteilt – ${bisText(e.bis)}`;
      if (e.aktion === "freigabe_entzogen") return `${recht} von ${esc(e.konto)} entzogen`;
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
    const pruefzeilen = d.direkt.concat(d.unten).filter((f) => f.recht === "pruefen" && f.aenderbar);
    return `${d.laeuft_ab ? `<p class="notice mf-ablauf">${plural(d.laeuft_ab, "Freigabe läuft", "Freigaben laufen")} in den nächsten 30 Tagen ab.</p>` : ""}
      <details class="mf-teil" open><summary>Hier vergeben <span class="mf-zahl">${d.direkt.length}</span></summary>
        ${pruefzeilen.length ? '<div class="btn-row mf-verl-reihe"><button class="btn secondary small" type="button" data-act="verlaengern" id="mf-verlaengern">Alle Prüffreigaben verlängern bis …</button></div>' : ""}
        ${tabelleHtml(d.direkt, "direkt", "An diesem Ordner selbst ist nichts vergeben.")}</details>
      <details class="mf-teil"><summary>Geerbt von oben <span class="mf-zahl">${d.geerbt.length}</span></summary>
        <p class="help">Freigaben an Oberordnern gelten auch hier. Ändern lassen sie sich nur dort, wo sie vergeben sind.</p>
        ${tabelleHtml(d.geerbt, "geerbt", "Nichts geerbt.")}</details>
      <details class="mf-teil"><summary>In Unterordnern <span class="mf-zahl">${d.unten.length}</span></summary>
        ${tabelleHtml(d.unten, "unten", "In den Unterordnern ist nichts eigens vergeben.")}</details>
      <details class="mf-teil"><summary>Verlauf</summary>${verlaufHtml(d.verlauf)}</details>`;
  }

  /* --- „+ Freigabe“ ------------------------------------------------------------------------------------------ */
  function formHtml(d) {
    return `<details class="mf-teil mf-neu" open><summary>+ Freigabe</summary>
      <label for="mf-person">Person</label>
      <div class="mf-personwahl">
        <input type="search" id="mf-person" placeholder="Name – ab 3 Zeichen" autocomplete="off" enterkeyhint="search"
          aria-describedby="mf-person-hilfe" aria-controls="mf-treffer">
        <div class="help" id="mf-person-hilfe">Jedes aktive Konto mit Namen, auch aus anderen Gliederungen.</div>
        <ul class="mf-treffer" id="mf-treffer" aria-label="Gefundene Personen" hidden></ul>
        <div class="mf-gewaehlt" id="mf-gewaehlt" hidden></div>
      </div>
      <label for="mf-anker">Gilt für</label>
      <select id="mf-anker">${d.anker_wahl.map((a) => `<option value="${a.id}"${a.id === d.anker_vorgabe ? " selected" : ""}>${esc(a.pfad)}</option>`).join("")}</select>
      <div class="help">… und alle Ordner darunter.</div>
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
        <div id="mf-pruefen-ende" hidden><label for="mf-pruefen-bis">Prüfen bis</label>${datumFeld("mf-pruefen-bis", "")}
          <div class="help" id="mf-pruefen-hilfe"></div></div>
      </div>
      <details class="mf-notiz"><summary>Notiz</summary>
        <input type="text" id="mf-notiz" maxlength="200" aria-describedby="mf-notiz-hilfe">
        <div class="help" id="mf-notiz-hilfe">Eine Zeile, höchstens 200 Zeichen – sehen nur Verwalter dieses Ordners und die
          Plattform-Verwaltung, die Person selbst also nur, wenn sie hier mitverwaltet. Keine sensiblen Angaben.</div></details>
      <div class="btn-row mf-erteilen-reihe"><button class="btn" type="button" id="mf-erteilen">Freigabe erteilen</button></div>
    </details>`;
  }

  /* Der Zustand des Formulars: gewählte Person, Vorlage und Anker – daraus folgen die sichtbaren Felder, die Vorgaben
     für „bis“ und welche Vorlagen gehen (prüfen nur mit Qualifikation; „dauerhaft“ nur, wer selbst dauerhaft
     verwaltet). */
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

    function zeigen() {
      const a = anker();
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
      feld("mf-pruefen-hilfe").textContent = `Spätestens ${fmtTag(frueher(stand.daten.grenzen.pruefen_max, a.ende))} – höchstens 24 Monate`
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
      try { r = await api(`${API}/nutzer?q=${encodeURIComponent(q)}`); }
      catch (e) { if (lauf === suchlauf) { liste.innerHTML = `<li class="mf-treffer-leer">${esc(e.message)}</li>`; liste.hidden = false; } return; }
      if (lauf !== suchlauf) return;          // eine neuere Eingabe ist schon unterwegs
      liste.innerHTML = r.nutzer.length ? r.nutzer.map((p) => `<li><button type="button" class="mf-person" data-id="${p.id}">
          ${personHtml(p)}${p.qualifiziert ? ' <span class="badge grey">Prüfer</span>' : ""}</button></li>`).join("")
          + (r.mehr ? '<li class="mf-treffer-leer">Mehr als 20 – bitte genauer.</li>' : "")
        : '<li class="mf-treffer-leer">Niemand gefunden – nur aktive Konten mit Namen.</li>';
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
    $$('input[name="mf-vorlage"], #mf-grund, #mf-pruefen', body).forEach((x) => x.addEventListener("change", zeigen));

    feld("mf-erteilen").addEventListener("click", async (ev) => {
      const knopf = ev.currentTarget;
      if (knopf.disabled) return;
      if (!person) { toast("Bitte zuerst eine Person wählen.", true); fokus(feld("mf-person")); return; }
      if (!vorlage()) { toast("Bitte eine Vorlage wählen.", true); return; }
      const w = wunsch();
      if (!w.grund && !w.pruefen) { toast("Bitte ein Grundrecht, eine Prüffreigabe oder beides wählen.", true); return; }
      const daten = { user_id: person.id, grundrecht: w.grund, grund_bis: null, pruefen_bis: null };
      try {
        if (w.grund && !feld("mf-dauerhaft").checked) {
          daten.grund_bis = datumWert(feld("mf-grund-bis"), "Grundrecht bis");
          if (!daten.grund_bis) throw new Error("Bitte ein Enddatum für das Grundrecht angeben – oder „dauerhaft“.");
        }
        if (w.pruefen) daten.pruefen_bis = datumWert(feld("mf-pruefen-bis"), "Prüfen bis");
      } catch (e) { toast(e.message, true); return; }
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
      } catch (e) { toast(e.message, true); }
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

  /* --- Ändern, Entziehen, Verlängern ------------------------------------------------------------------------- */
  function aendernDialog(f, stand, nachher) {
    const anker = stand.daten.anker_wahl.find((a) => a.id === f.ordner.id);
    // Das eigene Ende am Anker – für Zeilen in Unterordnern das an diesem Ordner (dort gilt mindestens dasselbe).
    const ende = (anker || stand.daten.anker_wahl[0] || {}).ende;
    const grund = f.recht !== "pruefen";
    const dauerhaftGeht = grund && (ende === null || ende === undefined) && (!f.eigen || f.bis === null);
    unterDialog(`<h2>Freigabe ändern</h2>
      <p>${personHtml(f.konto)} · ${esc(f.ordner.pfad)}</p>
      ${f.eigen ? '<p class="help">Deine eigene Freigabe kannst du nur verkürzen, herabsetzen oder entziehen.</p>' : ""}
      <label for="mfa-recht">Recht</label>
      <select id="mfa-recht">${(grund ? ["lesen", "verwalten"] : ["pruefen"]).map((r) => `<option value="${r}"${r === f.recht ? " selected" : ""}>${RECHT[r]}</option>`).join("")}</select>
      <label for="mfa-bis">bis</label>
      ${dauerhaftGeht ? `<label class="inline"><input type="checkbox" id="mfa-dauerhaft"${f.bis === null ? " checked" : ""}> dauerhaft</label>` : ""}
      ${datumFeld("mfa-bis", f.bis || (grund ? "" : stand.daten.grenzen.vorgabe_bis))}
      ${grund ? "" : `<div class="help">Spätestens ${fmtTag(frueher(stand.daten.grenzen.pruefen_max, ende))}.</div>`}
      ${"notiz" in f ? `<label for="mfa-notiz">Notiz</label><input type="text" id="mfa-notiz" maxlength="200" value="${esc(f.notiz || "")}">
        <div class="help">Sehen nur Verwalter dieses Ordners und die Plattform-Verwaltung – die Person selbst nur, wenn sie hier
          mitverwaltet. Keine sensiblen Angaben.</div>` : ""}
      <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Abbrechen</button>
        <button class="btn" type="button" id="mfa-ok">Speichern</button></div>`, (dlg, body) => {
      const bis = $("#mfa-bis", body);
      const dauer = $("#mfa-dauerhaft", body);
      const zeigen = () => { bis.hidden = !!(dauer && dauer.checked); };
      if (dauer) dauer.addEventListener("change", zeigen);
      zeigen();
      $("#mfa-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        const daten = { recht: $("#mfa-recht", body).value };
        try {
          daten.bis = dauer && dauer.checked ? null : datumWert(bis, "bis") || null;
          if (daten.bis === null && !(dauer && dauer.checked)) throw new Error("Bitte ein Enddatum angeben.");
        } catch (e) { toast(e.message, true); return; }
        if ($("#mfa-notiz", body)) daten.notiz = $("#mfa-notiz", body).value.trim();
        knopf.disabled = true;
        try {
          await api(`${API}/freigaben/${f.id}`, { method: "PUT", body: daten });
          dlg.close();
          toast("Freigabe geändert");
          await nachher();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  async function entziehen(f, stand, nachher) {
    const text = `Freigabe „${RECHT[f.recht] || f.recht}“ von ${f.konto.name} an ${f.ordner.pfad} entziehen?`
      + (f.eigen ? " Es ist deine eigene." : "");
    if (!(await confirm(text, "Entziehen"))) return;
    try {
      const r = await api(`${API}/freigaben/${f.id}`, { method: "DELETE" });
      stand.hinweis = r.offene_entwuerfe ? `${plural(r.offene_entwuerfe, "offene Prüfung", "offene Prüfungen")} von ${esc(f.konto.name)} – unter
        <a href="/material/pruefungen">Prüfungen</a> → Offene Prüfungen freigeben.` : "";
      toast("Freigabe entzogen");
      await nachher();
    } catch (e) { toast(e.message, true); }
  }

  function verlaengernDialog(stand, nachher) {
    const d = stand.daten;
    const eigen = (d.anker_wahl.find((a) => a.id === d.ordner.id) || {}).ende;
    const vorgabe = frueher(frueher(d.grenzen.vorgabe_bis, d.grenzen.pruefen_max), eigen);
    unterDialog(`<h2>Alle Prüffreigaben verlängern</h2>
      <p class="help">Verlängert jede Prüffreigabe an „${esc(d.ordner.pfad)}“ und darunter, die noch gilt oder seit höchstens 90 Tagen
        abgelaufen ist – soweit du sie ändern darfst und das Konto qualifiziert ist. Kürzer wird keine.</p>
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
        catch (e) { toast(e.message, true); return; }
        knopf.disabled = true;
        try {
          const r = await api(`${API}/ordner/${d.ordner.id}/freigaben/verlaengern`, { method: "POST", body: { bis } });
          $("#mfv-ergebnis", body).innerHTML = `<p class="notice">${plural(r.verlaengert, "Prüffreigabe", "Prüffreigaben")} bis ${fmtTag(bis)} verlängert.</p>
            ${r.uebersprungen.length ? `<p><strong>Übersprungen:</strong></p><ul class="mf-uebersprungen">${r.uebersprungen.map((u) => `<li>${esc(u.konto)}
              <span class="small muted">${esc(u.ordner)}</span> – ${esc(u.grund)}</li>`).join("")}</ul>` : ""}`;
          knopf.hidden = true;
          await nachher();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
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
    const dort = opt.dort || ((oid) => { location.href = `/material/ordner/${oid}?freigaben`; });
    try { stand.daten = await api(`${API}/ordner/${id}/freigaben`); }
    catch (e) { el.innerHTML = `<p class="notice">${esc(e.message)}</p>`; return; }
    const d = stand.daten;
    el.innerHTML = `<p class="help">Freigaben für „${esc(d.ordner.pfad)}“ gelten dort und in allen Unterordnern, bis
        einschließlich zum letzten Tag. Rechte addieren sich; weiter unten lässt sich nichts entziehen.</p>
      ${formHtml(d)}<div id="mf-hinweis"></div><div id="mf-listen">${listenHtml(d)}</div>`;

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
    }

    formVerdrahten(el, stand, neuLaden);
    $("#mf-listen", el).addEventListener("click", (e) => {
      const b = e.target.closest("button[data-act]");
      if (!b) return;
      const alle = stand.daten.direkt.concat(stand.daten.geerbt, stand.daten.unten);
      const f = alle.find((x) => x.id === +b.dataset.id);
      if (b.dataset.act === "aendern" && f) aendernDialog(f, stand, neuLaden);
      else if (b.dataset.act === "entziehen" && f) entziehen(f, stand, neuLaden);
      else if (b.dataset.act === "verlaengern") verlaengernDialog(stand, neuLaden);
      else if (b.dataset.act === "dort") dort(+b.dataset.ordner);
    });
    if (opt.vorlage === "verlaengern") {
      const knopf = $("#mf-verlaengern", el);
      if (knopf) { knopf.scrollIntoView({ block: "center" }); if (opt.fokus) knopf.focus(); }
    } else if (opt.fokus) {
      fokus($("#mf-person", el));
    }
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
        ? (d.qualifiziert ? '<p class="help mf-meine-leer">Prüfen kannst du auch als Plattform-Verwaltung nur mit eigener Prüffreigabe – die gibst du dir am Ordner unter „Bearbeiten“ → „Freigaben“.</p>' : "")
        : '<p class="notice mf-meine-leer">Du hast noch keine Freigabe im Bestand – der Materialwart deiner Gliederung vergibt sie.</p>';
      return;
    }
    const wichtig = d.freigaben.filter((f) => !f.gueltig || f.laeuft_ab_in_tagen !== null || !f.wirkt);
    const wer = (f) => (f.verwalter.length ? f.verwalter.join(", ").replace(/, ([^,]*)$/, " oder $1") : "die Plattform-Verwaltung");
    el.innerHTML = `<details class="section mat-auf mf-meine"${wichtig.length ? " open" : ""}><summary>Meine Freigaben <span class="mf-zahl">${d.freigaben.length}</span></summary>
      <ul class="mf-meine-liste">${d.freigaben.map((f) => `<li class="${!f.gueltig ? "abgelaufen" : f.laeuft_ab_in_tagen !== null ? "bald" : ""}">
        <span class="mf-meine-ordner">${f.gueltig && f.wirkt ? `<a href="/material/ordner/${f.ordner.id}">${esc(f.ordner.pfad)}</a>` : esc(f.ordner.pfad)}</span>
        <span class="mf-meine-recht">${esc(RECHT[f.recht] || f.recht)} · ${bisText(f.bis)}</span> ${zustand(f)}
        ${!f.gueltig || f.laeuft_ab_in_tagen !== null ? `<div class="small muted">Verlängern kann: ${esc(wer(f))}.</div>` : ""}
        ${f.gueltig && !f.wirkt && f.recht === "pruefen" ? `<div class="small muted">${esc(OHNE_QUALIFIKATION)}</div>` : ""}</li>`).join("")}</ul>
    </details>`;
  }

  /* Im Ordnerkopf (nur für Verwalter): wie viele Freigaben im Zweig bald ablaufen – ein Hinweis, kein Menü. Sein Knopf
     „Verlängern …“ öffnet über material.js „Ordner bearbeiten“ im Reiter „Freigaben“ beim Verlängern-Knopf. */
  async function kopfhinweis(el, ordner, verlaengern) {
    if (!el || !ordner) return;
    let d;
    try { d = await api(`${API}/ordner/${ordner.id || ordner}/freigaben`); } catch (e) { el.innerHTML = ""; return; }
    el.innerHTML = d.laeuft_ab ? `<p class="notice mf-kopf">${plural(d.laeuft_ab, "Freigabe läuft", "Freigaben laufen")} in den nächsten 30 Tagen ab.
      ${verlaengern ? '<button class="btn secondary small" type="button">Verlängern …</button>' : ""}</p>` : "";
    const b = $("button", el);
    if (b) b.addEventListener("click", () => verlaengern());
  }

  window.MatFreigaben = { inhalt, hinweis, kopfhinweis };
})();
