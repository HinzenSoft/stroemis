(function () {
  const tbody = document.querySelector("#users tbody");
  let users = [];

  /* Wann jemand zuletzt da war – die Antwort auf „wer arbeitet hier eigentlich noch mit?“.
     Das Datum allein sagt wenig, solange man nicht nachrechnet; deshalb steht der Abstand
     davor und das genaue Datum im Titel. Ein Konto, das sich noch nie angemeldet hat, ist
     etwas anderes als eines, das lange nicht da war – das darf nicht dasselbe aussehen. */
  function letzterLogin(u) {
    if (!u.last_login) {
      return u.status === "pending"
        ? '<span class="muted">wartet auf Freigabe</span>'
        : '<span class="muted">noch nie</span>';
    }
    const tage = Math.floor((Date.now() - new Date(u.last_login)) / 86400000);
    const text = tage <= 0 ? "heute" : tage === 1 ? "gestern"
      : tage < 31 ? `vor ${tage} Tagen`
      : tage < 365 ? `vor ${Math.round(tage / 30)} Monaten`
      : `vor ${Math.floor(tage / 365)} Jahr${Math.floor(tage / 365) > 1 ? "en" : ""}`;
    // Über einem halben Jahr nichts mehr: Das ist der Fall, den man in der Liste sehen will.
    const alt = tage >= 180 ? " muted" : "";
    return `<span class="${alt.trim()}" title="${S.esc(S.fmtDate(u.last_login, true))}">${text}</span>`;
  }

  /* Rechte je Modul: Jeder Nutzer hat in jedem der fünf Module eine Stufe – kein Zugriff,
     Mitglied oder Verwaltung. Was die Stufe im Modul bedeutet, steht hier an EINER Stelle und
     erscheint als Titel am Auswahlfeld, in der Tabelle wie im Dialog. In der Leitstelle gibt
     es kein „Mitglied“: Nutzer, Rechte und Einstellungen pflegt man ganz oder gar nicht.
     In der Materialablage ist die Stufe der Zugang (Mitglied) bzw. die Material-Verwaltung; den Bestand
     zeigen einem Mitglied erst Freigaben, die der Verwalter eines Ordners vergibt.
     Die sichtbaren Namen (t) kommen aus app/module.py (STROEMIS.module) – die Schlüssel k bleiben. */
  const NAME = (STROEMIS.module || {}).name || {};
  const PFAD = (STROEMIS.module || {}).pfad || {};
  // Reihenfolge wie die Kopfleiste (Strömipedia, Ankerplätze, Riegenkarten, Materialablage, Leitstelle).
  const MODULE = [
    { k: "wiki", t: NAME.wiki, hilfe: "Ohne Zugriff (–): nur die öffentlich freigegebenen Seiten lesen. Mitglied: eigene und freigegebene Seiten. Verwaltung: alle Seiten, beschränkte lesen, veröffentlichen, HTML-Bausteine, Ersteller ändern." },
    { k: "karte", t: NAME.karte, hilfe: "Mitglied: eigene Alben anlegen und bearbeiten. Verwaltung: alle Alben." },
    { k: "pruefungen", t: NAME.pruefungen, hilfe: "Mitglied: Prüfungen abnehmen (Prüfer). Verwaltung: zusätzlich Kataloge pflegen und jeden Lehrgang leiten." },
    { k: "material", t: NAME.material, hilfe: "Mitglied: die Materialablage nutzen – Katalog, Suche, Profil; Bestand nur über Freigaben, die der Verwalter eines Ordners vergibt. Verwaltung: zusätzlich Produktkatalog pflegen (Kategorien, Produkte, Dokumente, Prüfformulare, Meldungen, Rückrufe), alle Bestände aller Gliederungen, Gliederungen anlegen, jede Freigabe. Prüfen nur mit Häkchen „Prüfer“, Urkundennummer und Prüffreigabe." },
    { k: "verwaltung", t: NAME.verwaltung, nurVoll: true,
      hilfe: "Verwaltung: Nutzer, Rechte und Einstellungen – schließt alle Rechte in allen Modulen ein." },
  ];
  const STUFEN = [[0, "–"], [1, "Mitglied"], [2, "Verwaltung"]];
  const VORGABE = { karte: 0, wiki: 0, pruefungen: 0, material: 1, verwaltung: 0 };   // neues Konto (wie auth.VORGABE_NEU)
  const ERGIBT_SICH = "ergibt sich aus Verwaltung";

  /* Ein Auswahlfeld für die Stufe eines Moduls. Steht die Verwaltung auf „Verwaltung“, sind die
     übrigen vier Felder nur noch Anzeige: Der Server speichert dort ohnehin 2, und ein Feld, das
     man umstellt und das sofort zurückspringt, wäre verwirrender als ein abgeschaltetes. Das
     eigene Konto kann sich die Verwaltung nicht entziehen – der Server lehnt es ab, also wird
     es gar nicht erst angeboten. */
  function rechtFeld(m, rechte, opts) {
    opts = opts || {};
    rechte = rechte || {};
    const voll = (rechte.verwaltung | 0) === 2;
    let wert = rechte[m.k] | 0, aus = false, titel = m.hilfe;
    if (m.k !== "verwaltung" && voll) { wert = 2; aus = true; titel = ERGIBT_SICH; }
    if (m.k === "verwaltung" && opts.eigenes) { aus = true; titel = "Dein eigenes Konto: Die Verwaltung kannst du dir nicht selbst entziehen."; }
    const stufen = STUFEN.filter(([v]) => !(m.nurVoll && v === 1));
    return `<select class="recht-wahl" data-modul="${m.k}"${opts.id ? ` id="${opts.id}"` : ""} aria-label="${S.esc(m.t)}"
      title="${S.esc(titel)}"${aus ? " disabled" : ""}>${stufen.map(([v, l]) => `<option value="${v}"${v === wert ? " selected" : ""}>${l}</option>`).join("")}</select>`;
  }

  /* Die fünf Zellen einer Zeile neu zeichnen – nach jeder Antwort des Servers, ob Erfolg oder
     Fehler: So zeigt die Zeile immer das, was gespeichert ist, und bei verwaltung = 2 ziehen
     die anderen vier Felder von selbst nach. */
  function zeichneRechte(tr, u) {
    MODULE.forEach((m) => {
      tr.querySelector(`td.recht[data-modul="${m.k}"]`).innerHTML = rechtZelle(m, u);
    });
  }

  /* Unter dem Material-Feld: das Häkchen „Prüfer“ (gesetzt im Dialog „Bearbeiten“; gelb, solange die
     Urkundennummer fehlt – die trägt der Prüfer selbst im Profil ein) und klein die Zahl gültiger
     Freigaben. Gelb, was nicht wirkt: Häkchen oder Freigaben ohne Stufe in der Materialablage, eine Stufe
     ohne Namen – beides gibt keinen Zugang. */
  function rechtZelle(m, u) {
    const feld = rechtFeld(m, u.rechte, { eigenes: u.id === STROEMIS.user.id, konto: u });
    if (m.k !== "material") return feld;
    const marken = [];
    const stufe = (u.rechte || {}).material | 0, n = u.mat_freigaben | 0;
    if (u.mat_pruefer && u.urkunde_gueltig) marken.push(`<span class="badge grey" title="Prüfer (Sachkundiger), Urkundennummer ${S.esc(u.urkundennummer)}">Prüfer</span>`);
    else if (u.mat_pruefer) marken.push('<span class="badge urkunde-fehlt" title="Häkchen „Prüfer“ gesetzt, aber noch keine Urkundennummer – die trägt der Prüfer selbst im Profil ein. Bis dahin darf er nicht prüfen.">Prüfer – Urkunden&shy;nummer fehlt</span>');
    if (!stufe && (u.mat_pruefer || n)) {
      marken.push('<span class="badge kein-zugang" title="Ohne Stufe Mitglied oder Verwaltung in der Materialablage wirken Häkchen und Freigaben nicht.">wirkt nicht – kein Zugang</span>');
    } else if (stufe && !String(u.name || "").trim()) {
      marken.push('<span class="badge kein-zugang" title="In der Materialablage steht jeder mit Namen in Journal und Protokollen – ohne Namen kein Zugang.">ohne Namen – kein Zugang</span>');
    }
    if (n) marken.push(`<span class="recht-klein" title="Gültige Freigaben in der Materialablage – vergeben am Ordner (Bestand → Ordner → Bearbeiten → Freigaben)">${n} Frei&shy;gabe${n === 1 ? "" : "n"}</span>`);
    return feld + (marken.length ? `<div class="recht-marken">${marken.join(" ")}</div>` : "");
  }

  /* Zeilenaktionen nach der Knopfregel (Browserprüfung vor dem Merge, V5): „Bearbeiten“ als grauer Knopf, die seltenen
     „Reset-Mail senden“ und „Löschen“ im Zeilenmenü „Mehr“ – vorher drei rote Textlinks (btn ghost) je Zeile. Schließen
     per Klick daneben, Escape oder Eintrag: app-weit in common.js (seit der Lieferung nach dem Merge auch Riegenkarten). */
  // Eine E-Mail bricht in ihrer schmalen Spalte am „@“ um (und vor Punkten der Domain), nicht mitten im Wort (V5).
  const mailUmbruch = (mail) => S.esc(mail).replace(/@/, "<wbr>@").replace(/\.(?=[^@]*$)/g, "<wbr>.");

  async function load() {
    try { users = (await S.api("/api/admin/users")).users; }
    catch (e) { S.toast("Die Nutzerliste ließ sich nicht laden: " + e.message, true); return; }
    const pend = users.filter((u) => u.status === "pending");
    const box = document.getElementById("pending");
    box.innerHTML = pend.length ? `<h2>Offene Kontoanfragen <span class="badge">${pend.length}</span></h2>${pend.map((u) => `
      <div class="request" data-id="${u.id}">
        <div><strong>${S.esc(u.name)}</strong> · ${S.esc(u.email)}<br><span class="small">${S.esc(u.gliederung)}${u.phone ? " · " + S.esc(u.phone) : ""} · angefragt ${S.fmtDate(u.created_at, true)}</span>
          ${u.reason ? `<div class="c-quote" style="margin-top:6px">${S.esc(u.reason)}</div>` : ""}</div>
        <div class="btn-row"><button class="btn secondary small" data-act="approve">Freigeben</button><button class="btn secondary small" data-act="reject">Ablehnen</button></div>
      </div>`).join("")}` : "";
    tbody.innerHTML = users.filter((u) => u.status !== "pending").map((u) => `
      <tr data-id="${u.id}" ${u.active ? "" : 'class="muted"'}>
        <td data-l="Name">${S.esc(u.name) || "<span class='muted'>–</span>"}${u.active ? "" : ' <span class="badge grey">deaktiviert</span>'}</td>
        <td class="mail" data-l="E-Mail">${mailUmbruch(u.email)}</td>
        <td data-l="Gliederung">${S.esc(u.gliederung)}</td>
        ${MODULE.map((m) => `<td class="recht" data-l="${m.t}" data-modul="${m.k}">${rechtZelle(m, u)}</td>`).join("")}
        <td class="small" data-l="Zuletzt da">${letzterLogin(u)}</td>
        <td class="small" data-l="Inhalte">${u.page_count} Artikel, ${u.album_count} Alben, ${u.photo_count} Bilder</td>
        <td class="tabelle-aktionen"><div class="btn-row">
          <button class="btn secondary small" data-act="edit">Bearbeiten</button>
          <details class="zeilenmenue"><summary class="btn secondary small" aria-haspopup="true">Mehr</summary>
            <div class="zeilenmenue-liste">
              <button type="button" data-act="reset">Reset-Mail senden</button>
              ${u.id !== STROEMIS.user.id ? '<button type="button" data-act="delete">Löschen</button>' : ""}
            </div></details>
        </div></td>
      </tr>`).join("");
  }

  /* Probemail: Kommt bei jemandem nichts an, sagt der Mailserver hier wörtlich, woran es liegt –
     keine Verbindung, Anmeldung abgelehnt, Empfänger abgewiesen. Die Antwort steht im Dialog
     und nicht in einem Kurzhinweis: Sie ist zum Lesen und Weitergeben da. */
  document.getElementById("btn-testmail").addEventListener("click", () => {
    S.dialog(`<h2>Testmail senden</h2>
      <p class="help">Verschickt eine Probemail über den eingerichteten Mailserver und zeigt, was er
        dazu sagt.${S.info("SPF, DKIM, DMARC", "Kommt sie an, funktioniert der Weg bis zu diesem Postfach; landet sie im Spam oder gar nicht, liegt es meist an SPF, DKIM oder DMARC der Absenderdomain.")}</p>
      <label for="tm-to">Empfänger</label>
      <input type="email" id="tm-to" value="${S.esc(STROEMIS.user.email || "")}" autocomplete="off">
      <div id="tm-out"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
      <button class="btn" id="tm-go" type="button">Senden</button></div>`,
      (dlg, body) => {
        const raus = body.querySelector("#tm-out");
        body.querySelector("#tm-go").onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          knopf.disabled = true;
          raus.innerHTML = '<p class="help">wird verschickt …</p>';
          try {
            const d = await S.api("/api/admin/testmail", { method: "POST", body: { to: body.querySelector("#tm-to").value } });
            raus.innerHTML = `<div class="mail-bericht ${d.ok ? "ok" : "fehler"}">
              <strong>${d.ok ? "Angenommen" : "Nicht hinausgegangen"}</strong>
              <p>${S.esc(d.meldung)}</p>
              <dl class="kv"><dt>An</dt><dd>${S.esc(d.an)}</dd>
                <dt>Absender</dt><dd>${S.esc(d.absender)}</dd>
                ${d.umschlag ? `<dt>Umschlag</dt><dd>${S.esc(d.umschlag)}</dd>` : ""}</dl></div>`;
          } catch (e) {
            raus.innerHTML = `<div class="mail-bericht fehler"><strong>Fehlgeschlagen</strong><p>${S.esc(e.message)}</p></div>`;
          }
          knopf.disabled = false;
        };
      });
  });

  /* Videopflege: Bestandsvideos werden nach dem Start im Hintergrund gewandelt. Die Zeile
     erscheint nur, solange etwas läuft oder etwas zu berichten ist – sonst bleibt die Seite
     ruhig. Solange es läuft, wird nachgesehen. */
  async function videopflege() {
    const el = document.getElementById("videopflege");
    let d;
    try { d = await S.api("/api/admin/videos"); } catch (e) { return; }
    const teile = [];
    if (d.laeuft) teile.push(`Videos werden im Hintergrund aufbereitet – ${d.geprueft} geprüft, ${d.gewandelt} gewandelt …`);
    else if (d.gewandelt || d.fehler) teile.push(`Videopflege: ${d.geprueft} geprüft, ${d.gewandelt} gewandelt${d.fehler ? `, ${d.fehler} nicht lesbar` : ""}.`);
    el.textContent = teile.join(" ");
    el.classList.toggle("hidden", !teile.length);
    if (d.laeuft) setTimeout(videopflege, 5000);
  }
  videopflege();

  document.getElementById("pending").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const id = +b.closest(".request").dataset.id;
    const u = users.find((x) => x.id === id);
    try {
      if (b.dataset.act === "approve") {
        const r = await S.api(`/api/admin/users/${id}/approve`, { method: "POST", body: {} });
        S.toast(r.mailed ? `${u.name} freigegeben – E-Mail verschickt` : `${u.name} freigegeben (keine E-Mail: kein Mailserver eingerichtet)`);
      } else {
        if (!(await S.confirm(`Anfrage von ${u.name} ablehnen und löschen?`, "Ablehnen"))) return;
        await S.api(`/api/admin/users/${id}/reject`, { method: "POST", body: {} });
        S.toast("Anfrage abgelehnt");
      }
      load();
    } catch (err) { S.toast(err.message, true); }
  });

  /* Die Urkundennummer zeigt der Dialog nur – eintragen und ändern kann sie allein der Prüfer im
     eigenen Profil (PUT /api/material/urkundennummer). Hier steht nur der Zustand; dass er sie selbst im Profil
     einträgt, sagt der Hilfetext darunter (sonst stand es zweimal untereinander). */
  function urkundeLesend(u) {
    if (u.id && u.urkunde_gueltig) return `Urkundennummer: <strong>${S.esc(u.urkundennummer)}</strong>`;
    return "Urkundennummer: noch keine – solange darf er nicht prüfen.";
  }

  function userForm(u) {
    u = u || {};
    const rechte = u.rechte || VORGABE;
    const eigenes = !!u.id && u.id === STROEMIS.user.id;
    return `
      <div class="field-row">
        <div><label>Name</label><input type="text" id="u-name" value="${S.esc(u.name)}"></div>
        <div><label>Gliederung</label><input type="text" id="u-gl" value="${S.esc(u.gliederung)}"></div>
      </div>
      <label>E-Mail-Adresse</label><input type="email" id="u-email" value="${S.esc(u.email)}" required>
      <label>Telefon</label><input type="tel" id="u-phone" value="${S.esc(u.phone)}">
      <label>Rechte${S.info("Rechte", `„–“ kein Zugriff (in der Strömipedia: nur die öffentlichen Seiten lesen) · „Mitglied“ eigene Inhalte, bei den Riegenkarten:
        Prüfungen abnehmen, bei der Materialablage: sie nutzen (Bestand über Freigaben je Ordner) · „Verwaltung“ alles im Modul,
        bei der Materialablage auch Produktkatalog und alle Bestände. Verwaltung in der Leitstelle schließt alle Rechte ein.
        Was eine Stufe genau umfasst, steht als Hinweis am Feld.`)}</label>
      <div class="rechte-reihe">${MODULE.map((m) => `<div><label for="u-r-${m.k}">${m.t}</label>${rechtFeld(m, rechte, { id: "u-r-" + m.k, eigenes, konto: u })}</div>`).join("")}</div>
      <fieldset class="mat-rollen"><legend>Materialablage</legend>
        <label class="inline"><input type="checkbox" id="u-mat-pruefer" ${u.mat_pruefer ? "checked" : ""}> Prüfer (Sachkundiger)${S.info("Prüfer", `Das Häkchen wirkt nur mit Stufe „Mitglied“ oder „Verwaltung“ in der Materialablage. Urkundennummer und Unterschrift
          trägt der Prüfer selbst in seinem Profil ein („Urkundennummer und Unterschrift“); beides steht später auf jedem Prüfprotokoll.
          Prüfen kann er erst mit Urkundennummer und einer Prüffreigabe am Ordner (befristet nur für externe Prüfer) – auch die
          Verwaltung. Das Konto braucht einen Namen, damit es in der Materialablage handeln kann.`)}</label>
        <p class="mat-urkunde" ${u.mat_pruefer ? "" : "hidden"}>${urkundeLesend(u)}</p>
        <p class="help mat-stufe-auto" role="status" hidden>Materialablage steht jetzt auf „Mitglied“ – ohne Stufe wirkt das Häkchen nicht. Gespeichert wird beim Speichern.</p>
      </fieldset>
      ${u.id ? `<fieldset class="mat-rollen"><legend>Freigaben in der Materialablage${S.info("Freigaben in der Materialablage", "Angelegt wird eine Freigabe am Ordner (Bestand → Ordner → Bearbeiten → Freigaben), nicht hier.")}</legend>
        <p class="notice u-freigaben-kein-zugang" ${(rechte.material | 0) || !(u.mat_freigaben | 0) ? "hidden" : ""}>Diese Freigaben wirken nicht – das Konto hat keinen Zugang zur Materialablage.</p>
        <div id="u-freigaben"><p class="help">Wird geladen …</p></div>
      </fieldset>
      <details class="accordion" id="u-verlauf"><summary>Verlauf (Materialablage)${S.info("Verlauf", "Änderungen an Stufe, Häkchen „Prüfer“, Urkundennummer und Unterschrift (ohne Bild) – die letzten 50, neueste zuerst.")}</summary>
        <div class="accordion-body"><div id="u-verlauf-liste" aria-live="polite"><p class="help">Wird geladen …</p></div></div></details>` : ""}
      <label>${u.id ? "Neues Passwort (leer lassen, um es zu behalten)" : "Passwort (leer lassen, um eines zu erzeugen)"}</label>
      <input type="text" id="u-pw" autocomplete="off">
      ${u.id ? `<label class="inline"><input type="checkbox" id="u-active" ${u.active ? "checked" : ""}> Konto aktiv</label>`
             : `<label class="inline"><input type="checkbox" id="u-invite" checked> Einladung per E-Mail schicken (Link zum Passwort setzen)</label>`}`;
  }

  function read(body) {
    const rechte = {};
    MODULE.forEach((m) => { rechte[m.k] = +body.querySelector("#u-r-" + m.k).value; });
    return {
      name: body.querySelector("#u-name").value, gliederung: body.querySelector("#u-gl").value,
      email: body.querySelector("#u-email").value, phone: body.querySelector("#u-phone").value,
      password: body.querySelector("#u-pw").value || undefined, rechte,
      // Die Urkundennummer schickt der Dialog nicht mit: Sie gehört dem Prüfer (Profil).
      mat_pruefer: body.querySelector("#u-mat-pruefer").checked,
    };
  }

  /* Im Dialog gilt dieselbe Regel wie in der Tabelle, nur ohne Server dazwischen: Wer die
     Verwaltung auf „Verwaltung“ stellt, sieht die vier anderen Felder sofort auf „Verwaltung“
     springen und erstarren – und bekommt beim Zurückstellen seine vorherigen Werte wieder.
     Dazu in der Materialablage: Wer das Häkchen „Prüfer“ setzt, während Material auf „–“ steht, sieht
     die Auswahl auf „Mitglied“ springen (ohne Stufe wirkte das Häkchen nicht; gespeichert wird erst
     mit „Speichern“). Wer Material danach ausdrücklich auf „–“ stellt, behält das Häkchen – es wirkt
     dann nur nicht. Setzt man das Häkchen, während die Verwaltung auf „Verwaltung“ steht (Material zeigt
     „Verwaltung“ und ist aus), kommt die Hebung beim Zurückstellen der Verwaltung, falls Material dann auf
     „–“ stünde. Solange Material überdeckt ist, steht der Hinweis nicht da. */
  function koppleRechte(body, u) {
    const material = body.querySelector("#u-r-material");
    const pruefer = body.querySelector("#u-mat-pruefer");
    const auto = body.querySelector(".mat-stufe-auto");
    let gehoben = false;      // steht Material gerade wegen des Häkchens auf „Mitglied“ (noch nicht gespeichert)?
    let offen = false;        // Häkchen gesetzt, während die Verwaltung Material überdeckte – Hebung beim Zurückstellen
    // Über den Freigaben des Kontos: Sie wirken nicht, solange Material auf „–“ steht.
    const ohneZugang = () => {
      const hinweis = body.querySelector(".u-freigaben-kein-zugang");
      if (hinweis) hinweis.hidden = material.value !== "0" || !(u.mat_freigaben | 0);
    };
    // Der Hinweis zur Hebung steht, solange der Wert von ihr kommt und die Verwaltung das Feld nicht überdeckt.
    const zeigen = () => { auto.hidden = !gehoben || material.disabled; ohneZugang(); };
    const heben = () => { if (material.value === "0") { material.value = "1"; gehoben = true; } };
    // Ausdrücklich gewählt: Ein „–“ von Hand bleibt, auch über ein Hin und Her der Verwaltung hinweg.
    material.addEventListener("change", () => { gehoben = false; offen = false; zeigen(); });
    // Der Hinweis zur Urkundennummer gehört nur zu einem Prüfer – er erscheint mit dem Häkchen.
    pruefer.addEventListener("change", () => {
      body.querySelector(".mat-urkunde").hidden = !pruefer.checked;
      if (!pruefer.checked) offen = false;
      else if (material.disabled) offen = true;
      else heben();
      zeigen();
    });
    const chef = body.querySelector("#u-r-verwaltung");
    chef.addEventListener("change", () => {
      const voll = chef.value === "2";
      MODULE.filter((m) => m.k !== "verwaltung").forEach((m) => {
        const f = body.querySelector("#u-r-" + m.k);
        if (voll) { f.dataset.vorher = f.value; f.value = "2"; f.disabled = true; f.title = ERGIBT_SICH; }
        else { f.disabled = false; f.title = m.hilfe; if (f.dataset.vorher !== undefined) f.value = f.dataset.vorher; }
      });
      if (!voll && offen) { offen = false; heben(); }
      zeigen();
    });
  }

  document.getElementById("btn-new-user").addEventListener("click", () => {
    S.dialog(`<h2>Nutzer anlegen</h2>${userForm()}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="u-save" type="button">Anlegen</button></div>`,
      (dlg, body) => {
        koppleRechte(body, {});
        body.querySelector("#u-save").onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;          // Doppelklick legte den Nutzer zweimal an
          knopf.disabled = true;
          const d = read(body);
          d.send_invite = body.querySelector("#u-invite").checked;
          try {
            const r = await S.api("/api/admin/users", { method: "POST", body: d });
            await load();
            const info = r.initial_password
              ? `<p>Erzeugtes Passwort: <code>${S.esc(r.initial_password)}</code></p><p class="help">Bitte sicher weitergeben – es wird nicht erneut angezeigt.</p>`
              : "";
            const mail = d.send_invite ? (r.invite_sent ? "<p>Die Einladung wurde per E-Mail verschickt.</p>" : "<p class='notice'>Kein Mailserver eingerichtet – der Einladungslink steht im Protokoll des Servers.</p>") : "";
            S.dialog(`<h2>Nutzer angelegt</h2><p>${S.esc(d.email)}</p>${info}${mail}<div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`);
          } catch (e) { S.toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
      });
  });

  /* Rechte direkt in der Tabelle ändern: ein Wechsel, ein PUT mit nur diesem Modul. Die Antwort
     trägt die vollständigen Rechte – bei verwaltung = 2 also auch die drei nachgezogenen –, und
     daraus wird die Zeile gezeichnet. Schlägt es fehl (etwa weil man sich selbst die Verwaltung
     entzieht), bleibt der alte Stand und das Feld springt zurück. Material auf „–“ beim einzigen
     Materialwart einer Gliederung erst nach der Rückfrage (materialwartBleibt) – Abbrechen ebenso.
     Gesperrt und neu gezeichnet verliert die Auswahl den Fokus, und die Rückfrage findet beim Schließen
     nicht zu ihr zurück – die neue Auswahl des Moduls bekommt ihn, solange er nicht woanders steht. */
  tbody.addEventListener("change", async (e) => {
    const sel = e.target.closest("select[data-modul]");
    if (!sel) return;
    const tr = sel.closest("tr");
    const u = users.find((x) => x.id === +tr.dataset.id);
    if (!u) return;
    sel.disabled = true;      // kein zweiter Wechsel, solange der erste unterwegs ist
    try {
      if (sel.dataset.modul !== "material" || await materialwartBleibt(u, +sel.value)) {
        const r = await S.api(`/api/admin/users/${u.id}`, { method: "PUT", body: { rechte: { [sel.dataset.modul]: +sel.value } } });
        u.rechte = (r.user && r.user.rechte) || Object.assign({}, u.rechte, { [sel.dataset.modul]: +sel.value });
        S.toast("Gespeichert");
      }
    } catch (err) { S.toast(err.message, true); }
    zeichneRechte(tr, u);
    const neu = tr.querySelector(`select[data-modul="${sel.dataset.modul}"]`);
    if (neu && (!document.activeElement || document.activeElement === document.body)) neu.focus();
  });

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = +btn.closest("tr").dataset.id;
    const u = users.find((x) => x.id === id);
    if (btn.dataset.act === "edit") {
      S.dialog(`<h2>${S.esc(u.name || u.email)}</h2>${userForm(u)}
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="u-save" type="button">Speichern</button></div>`,
        (dlg, body) => {
          koppleRechte(body, u);
          freigabenZeigen(body.querySelector("#u-freigaben"), u);
          verlaufAnbinden(body.querySelector("#u-verlauf"), u);
          body.querySelector("#u-save").onclick = async (ev) => {
            const knopf = ev.currentTarget;
            if (knopf.disabled) return;
            knopf.disabled = true;
            const d = read(body);
            d.active = body.querySelector("#u-active").checked;
            try {
              // Einziger Materialwart einer Gliederung: erst die Rückfrage – Abbrechen lässt den Dialog offen, nichts gespeichert.
              if (!(await materialwartBleibt(u, d.rechte.material, d.active))) return;
              await S.api(`/api/admin/users/${id}`, { method: "PUT", body: d }); dlg.close(); await load(); S.toast("Gespeichert");
            }
            catch (err) { S.toast(err.message, true); }
            finally {
              knopf.disabled = false;
              // Gesperrt verliert „Speichern“ den Fokus, und die Rückfrage gibt ihn beim Schließen nicht zurück (der Knopf
              // ist dann noch gesperrt) – bleibt der Dialog offen (Abbrechen, Fehler), kommt er auf den Knopf zurück,
              // sonst stünde er auf der Seite, und Tab finge oben im Dialog an.
              if (dlg.open && !dlg.contains(document.activeElement)) knopf.focus();
            }
          };
        });
    } else if (btn.dataset.act === "reset") {
      // Rückfrage: Ein Versehen im Zeilenmenü schickte sofort eine Passwort-Mail (Browserprüfung vor dem Merge,
      // Verbesserung 14).
      if (!(await S.confirm(`Eine Mail zum Zurücksetzen des Passworts an ${u.email} senden?`, "Senden"))) return;
      try { const r = await S.api(`/api/admin/users/${id}/reset-mail`, { method: "POST", body: {} }); S.toast(r.message); }
      catch (err) { S.toast(err.message, true); }
    } else if (btn.dataset.act === "delete") {
      loeschDialog(u);
    }
  });

  /* --- Materialablage im Dialog „Bearbeiten“: die Freigaben des Kontos -------------------------- */
  const RECHT = { lesen: "lesen", verwalten: "verwalten", pruefen: "prüfen" };
  // „2027-12-31“ → „31.12.2027“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const tag = (iso) => { const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}.${m[2]}.${m[1]}` : ""; };
  const mehrzahl = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;

  function zustand(f) {
    if (!f.gueltig) return `<span class="muted">abgelaufen am ${tag(f.bis)}</span>`;
    if (!f.wirkt) {
      // Der Grund kommt vom Server (wirkt_nicht) – in fester Reihenfolge: deaktiviert, ohne Namen, kein Zugang zum Modul
      // Material, Qualifikation fehlt, dauerhaft nur mit lesen oder verwalten.
      const titel = {
        "kein Zugang zur Materialablage": "Ohne Stufe Mitglied oder Verwaltung in der Materialablage wirkt keine Freigabe.",
        "Qualifikation fehlt": "Ohne Häkchen und Urkundennummer wirkt eine Prüffreigabe nicht.",
        "dauerhaft nur mit lesen oder verwalten": "Dauerhaft prüft nur, wer dort auch lesen oder verwalten hat.",
      }[f.wirkt_nicht] || "";
      return `<span class="badge"${titel ? ` title="${titel}"` : ""}>wirkt nicht${f.wirkt_nicht ? ` – ${S.esc(f.wirkt_nicht)}` : ""}</span>`;
    }
    const t = f.laeuft_ab_in_tagen;
    if (t != null) return `<span class="badge">läuft ${t === 0 ? "heute" : t === 1 ? "morgen" : `in ${t} Tagen`} ab</span>`;
    return "gültig";
  }

  /* Ordnerpfad (Link), Recht, bis, Zustand und „Entziehen“ – angelegt und geändert wird am Ordner: Der Link öffnet dort
     „Ordner bearbeiten“ im Reiter „Freigaben“ (?freigaben). Die Notiz sieht die Verwaltung hier mit, der Inhaber nie
     unter „Meine Freigaben“ (nur als Verwalter des Ordners im Reiter). */
  async function freigabenZeigen(el, u) {
    if (!el) return;
    let liste;
    try { liste = (await S.api(`/api/material/freigaben?user_id=${u.id}`)).freigaben; }
    catch (e) { el.innerHTML = `<p class="help">Die Freigaben ließen sich nicht laden: ${S.esc(e.message)}</p>`; return; }
    el.innerHTML = liste.length ? `<table class="list"><thead><tr><th>Ordner</th><th>Recht</th><th>bis</th><th>Zustand</th><th></th></tr></thead><tbody>
      ${liste.map((f) => `<tr>
        <td data-l="Ordner"><a href="/materialablage/ordner/${f.ordner.id}?freigaben" title="Freigaben dieses Ordners öffnen">${S.esc(f.ordner.pfad)}</a>${f.notiz ? `<div class="small muted">${S.esc(f.notiz)}</div>` : ""}</td>
        <td data-l="Recht">${S.esc(RECHT[f.recht] || f.recht)}</td>
        <td data-l="bis">${f.bis ? tag(f.bis) : "dauerhaft"}</td>
        <td data-l="Zustand">${zustand(f)}</td>
        <td class="tabelle-aktionen"><button class="btn secondary small" type="button" data-entziehen="${f.id}">Entziehen</button></td>
      </tr>`).join("")}</tbody></table>`
      : ((u.rechte || {}).material | 0) === 2
        ? '<p class="help">Keine Freigaben – als Material-Verwaltung sieht das Konto ohnehin alle Bestände; prüfen nur mit eigener Prüffreigabe.</p>'
        : '<p class="help">Keine Freigaben – das Konto sieht keinen Bestand.</p>';
    el.querySelectorAll("[data-entziehen]").forEach((b) => b.addEventListener("click", async () => {
      const f = liste.find((x) => x.id === +b.dataset.entziehen);
      // An einem Grundrecht können dauerhafte Prüffreigaben hängen, die ohne es nicht mehr wirken – die Rückfrage sagt es.
      const haengt = !f.traegt_pruefen ? "" : f.traegt_pruefen === 1
        ? " Daran hängt eine dauerhafte Prüffreigabe – ohne dieses Grundrecht wirkt sie nicht mehr."
        : ` Daran hängen ${f.traegt_pruefen} dauerhafte Prüffreigaben – ohne dieses Grundrecht wirken sie nicht mehr.`;
      if (!(await S.confirm(`Freigabe „${RECHT[f.recht] || f.recht}“ für ${f.ordner.pfad} entziehen?${haengt}`, "Entziehen"))) return;
      b.disabled = true;
      try {
        const r = await S.api(`/api/material/freigaben/${f.id}`, { method: "DELETE" });
        S.toast("Freigabe entzogen");
        await freigabenZeigen(el, u);
        // Offene Prüfungen, die das Konto danach nicht fortsetzen darf, gibt ein Verwalter im Modul frei – der Hinweis
        // bleibt stehen und führt hin (wie im Reiter „Freigaben“ am Ordner).
        if (r.offene_entwuerfe) {
          el.insertAdjacentHTML("afterbegin", `<p class="notice">Entzogen – ${mehrzahl(r.offene_entwuerfe, "offene Prüfung", "offene Prüfungen")}
            des Kontos unter <a href="/materialablage/pruefungen">Materialablage → Prüfungen</a> → „Offene Prüfungen“ mit „Reservierung aufheben“.</p>`);
        }
        load();
      } catch (e) { S.toast(e.message, true); b.disabled = false; }
    }));
  }

  /* --- Materialablage im Dialog „Bearbeiten“: Verlauf des Kontos (Entscheidung E3 A, 26.10.2026) ----------------------
     Das Journal am Konto, geladen erst beim Aufklappen (selten gebraucht). Der Server liefert fertige Zeilen – Namen statt
     E-Mail, die Unterschrift nur als „hinterlegt“/„–“. */
  function verlaufAnbinden(box, u) {
    if (!box) return;
    const ziel = box.querySelector("#u-verlauf-liste");
    let geladen = false;
    const feld = (f) => `${S.esc(f.feld)}: ${f.nur_nachher ? "" : `${S.esc(f.vorher)} → `}${S.esc(f.nachher)}`;
    box.addEventListener("toggle", async () => {
      if (!box.open || geladen) return;
      geladen = true;
      let d;
      try { d = await S.api(`/api/admin/users/${u.id}/journal`); }
      catch (e) { geladen = false; ziel.innerHTML = `<p class="notice">Der Verlauf ließ sich nicht laden: ${S.esc(e.message)}</p>`; return; }
      const zeilen = d.eintraege || [];
      ziel.innerHTML = zeilen.length ? `<table class="list"><thead><tr><th>Zeit</th><th>Was</th><th>Von</th><th>Änderung</th></tr></thead><tbody>
        ${zeilen.map((z) => `<tr><td data-l="Zeit">${S.esc(z.zeit)}</td><td data-l="Was">${S.esc(z.aktion)}</td>
          <td data-l="Von">${S.esc(z.von)}</td><td data-l="Änderung">${z.felder.length ? z.felder.map(feld).join("<br>") : "–"}</td></tr>`).join("")}
        </tbody></table>` : '<p class="help">Noch keine Einträge.</p>';
    });
  }

  /* --- Materialablage: einziger Materialwart einer Gliederung ------------------------------------ */
  // „der Gliederung „A““, „der Gliederungen „A“ und „B““, „… „A“, „B“ und „C““ – Pfad, damit eine verschachtelte
  // Gliederung nicht mit einer gleichnamigen verwechselt wird.
  function gliederungenText(gl) {
    const namen = gl.map((x) => `„${S.esc(x.pfad || x.name)}“`);
    const liste = namen.length > 1 ? `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}` : namen[0];
    return `${namen.length > 1 ? "der Gliederungen" : "der Gliederung"} ${liste}`;
  }

  /* Rückfrage mit dem roten Hauptknopf – ein eigenes <dialog> wie S.confirm, damit „Bearbeiten“ darunter offen bleibt,
     aber ohne dessen Knopf für Endgültiges: „Trotzdem speichern“ löscht nichts. Abbrechen steht vorn und hat den
     Fokus, auch am Touchgerät; Esc bricht ab. */
  function rueckfrage(titel, html, okLabel) {
    return new Promise((resolve) => {
      let ja = false;
      const dlg = document.createElement("dialog");
      dlg.setAttribute("aria-labelledby", "rf-titel");
      dlg.innerHTML = `<div class="dlg-body"><h2 id="rf-titel">${S.esc(titel)}</h2>${html}
        <div class="dlg-actions"><button class="btn secondary" id="rf-nein" type="button">Abbrechen</button>
        <button class="btn" id="rf-ja" type="button">${S.esc(okLabel)}</button></div></div>`;
      document.body.appendChild(dlg);
      dlg.querySelector("#rf-ja").onclick = () => { ja = true; dlg.close(); };
      dlg.querySelector("#rf-nein").onclick = () => dlg.close();
      dlg.addEventListener("close", () => { dlg.remove(); resolve(ja); }, { once: true });
      dlg.showModal();
      dlg.querySelector("#rf-nein").focus();
    });
  }

  /* Material von „Mitglied“ oder „Verwaltung“ auf „–“ oder das Konto deaktiviert: Ist es heute der einzige Materialwart
     einer Gliederung (letzter_materialwart aus GET …/material-folgen, gezählt wie die Regel „keine Gliederung ohne
     Verwalter“ am Ordner), fragt die Nutzerverwaltung vorher nach – danach verwaltet dort nur noch die
     Material-Verwaltung. Nur eine Warnung, keine Sperre. Ohne Senkung, ohne betroffene Gliederung oder wenn die
     Auskunft fehlt: keine Rückfrage. true heißt speichern. */
  async function materialwartBleibt(u, material, aktiv) {
    const senkt = ((u.rechte || {}).material | 0) >= 1 && (material | 0) === 0;
    const aus = !!u.active && aktiv === false;
    if (!senkt && !aus) return true;
    let gl;
    try { gl = (await S.api(`/api/admin/users/${u.id}/material-folgen`)).letzter_materialwart || []; }
    catch (e) { return true; }
    if (!gl.length) return true;
    const wie = senkt && aus ? "Mit Materialablage „–“ und dem Deaktivieren" : senkt ? "Mit Materialablage „–“" : "Mit dem Deaktivieren";
    return rueckfrage("Einziger Materialwart", `<p><strong>${S.esc(u.name || u.email)}</strong> ist der einzige
        Materialwart ${gliederungenText(gl)}. ${wie} verwaltet dort danach nur noch die Material-Verwaltung und vergibt
        Freigaben.</p>
      <p class="help">Soll dort weiter jemand aus der Gliederung verwalten, vorher einen zweiten Materialwart eintragen:
        Bestand → Gliederung → Bearbeiten → Freigaben, Vorlage „Materialwart“.</p>`, "Trotzdem speichern");
  }

  /* Löschen: Was in der Materialablage daraus folgt, steht vorher da (GET …/material-folgen) – auch, wenn das Konto der
     einzige Materialwart einer Gliederung ist. Fehlt die Auskunft, lässt sich trotzdem löschen – der Dialog sagt dann
     nur, dass er die Folgen nicht kennt. */
  function folgenText(f) {
    const n = (x) => x | 0;
    return `${mehrzahl(n(f.freigaben), "Freigabe wird", "Freigaben werden")} entfernt, ${mehrzahl(n(f.zuordnungen), "Artikel verliert seine", "Artikel verlieren ihre")} Zuordnung,
      ${mehrzahl(n(f.entwuerfe), "offene Prüfung wird zur Reservierung", "offene Prüfungen werden zu Reservierungen")} ohne Prüfer.
      Festgeschriebene Prüfungen (${n(f.pruefungen)}) behalten den Namen – Nachweis nach EN 365.${n(f.maengel)
        ? ` ${mehrzahl(n(f.maengel), "Mangelmeldung behält", "Mangelmeldungen behalten")} den Namen.` : ""}${n(f.antraege)
        ? ` ${mehrzahl(n(f.antraege), "Änderungsantrag behält", "Änderungsanträge behalten")} den Namen.` : ""}`;
  }

  function loeschDialog(u) {
    S.dialog(`<h2>Nutzer löschen</h2>
      <p>${S.esc(u.name || u.email)} (${S.esc(u.email)}) löschen? Alben, Bilder und Seiten der Strömipedia bleiben erhalten und gehen auf dich über.</p>
      <div id="u-folgen"><p class="help">Folgen in der Materialablage werden ermittelt …</p></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn danger" id="u-del" type="button">Löschen</button></div>`,
    async (dlg, body) => {
      body.querySelector("#u-del").onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        knopf.disabled = true;
        try { await S.api(`/api/admin/users/${u.id}`, { method: "DELETE" }); dlg.close(); await load(); S.toast("Nutzer gelöscht"); }
        catch (err) { S.toast(err.message, true); knopf.disabled = false; }
      };
      const el = body.querySelector("#u-folgen");
      try {
        const f = await S.api(`/api/admin/users/${u.id}/material-folgen`);
        const gl = f.letzter_materialwart || [];
        el.innerHTML = `<p class="notice">Materialablage: ${folgenText(f)}</p>${gl.length ? `<p class="notice">${S.esc(u.name || u.email)}
          ist der einzige Materialwart ${gliederungenText(gl)} – danach verwaltet dort nur noch die Material-Verwaltung und
          vergibt Freigaben.</p>` : ""}`;
      } catch (e) {
        el.innerHTML = `<p class="help">Was das Löschen in der Materialablage entfernt (Freigaben, Zuordnungen, offene Prüfungen), ließ sich
          nicht ermitteln${e.status === 404 ? "" : `: ${S.esc(e.message)}`}. Festgeschriebene Prüfungen behalten den Namen des Prüfers.</p>`;
      }
    });
  }

  load().catch((e) => S.toast(e.message, true));

  /* --- Reiter: Nutzer und Einstellungen ------------------------------------------------ */
  const reiter = (name) => {
    document.querySelectorAll("[data-reiter]").forEach((b) => b.classList.toggle("sel", b.dataset.reiter === name));
    document.getElementById("bereich-nutzer").classList.toggle("hidden", name !== "nutzer");
    document.getElementById("bereich-einstellungen").classList.toggle("hidden", name === "nutzer");
    document.getElementById("seitentitel").textContent = name === "nutzer" ? "Nutzerverwaltung" : "Einstellungen";
    document.querySelectorAll("[data-titel-info]").forEach((el) => el.classList.toggle("hidden", el.dataset.titelInfo !== name));
    S.titel(name === "nutzer" ? "Nutzerverwaltung" : "Einstellungen", "verwaltung");   // Reiter des Browsers (V2)
    // „Nutzer anlegen“ gehört zur Liste. Die Probemail bleibt auf beiden Reitern stehen: Sie ist
    // die Gegenprobe zu den Mail-Einstellungen und gerade dort am nötigsten.
    document.getElementById("btn-new-user").classList.toggle("hidden", name !== "nutzer");
    if (name !== "nutzer" && !felder.length) ladeEinstellungen();
    // Der Reiter gehört in die Adresse: Wer die Einstellungen offen hatte und neu lädt, landet
    // sonst wieder bei den Nutzern.
    history.replaceState(null, "", name === "nutzer" ? PFAD.verwaltung : PFAD.verwaltung + "#einstellungen");
  };
  document.querySelectorAll("[data-reiter]").forEach((b) => b.onclick = () => reiter(b.dataset.reiter));

  /* --- Einstellungen ------------------------------------------------------------------- */
  /* Die Felder kommen vom Server, nicht aus dieser Datei: Was einstellbar ist, steht in
     app/einstellungen.py – an einer Stelle, zusammen mit Erklärung, Art und Ziel in der
     Konfiguration. Sonst müsste jede neue Einstellung an zwei Orten gepflegt werden. */
  let felder = [], gruppen = [];
  const form = document.getElementById("einst-form");

  const QUELLE = {
    gespeichert: ["hier gesetzt", "Gilt vorrangig vor der .env."],
    umgebung: ["aus der .env", "Steht in der Datei auf dem Server."],
    vorgabe: ["Vorgabe", "Eingebauter Wert – nirgends gesetzt."],
  };

  function zeichneEinstellungen() {
    form.innerHTML = gruppen.map((g) => {
      const meine = felder.filter((f) => f.gruppe === g);
      return `<fieldset class="einst-gruppe"><legend>${S.esc(g)}</legend>${meine.map(feldHtml).join("")}</fieldset>`;
    }).join("") + `<div class="btn-row einst-aktionen">
        <button class="btn" type="submit">Speichern</button>
        <span class="help" id="einst-stand"></span></div>`;
  }

  function feldHtml(f) {
    const id = "e-" + f.schluessel;
    const [kurz, titel] = QUELLE[f.quelle] || QUELLE.vorgabe;
    const marke = `<span class="einst-quelle q-${f.quelle}" title="${S.esc(titel)}">${kurz}</span>`;
    const zurueck = f.quelle === "gespeichert"
      ? `<button type="button" class="btn secondary small" data-zurueck="${f.schluessel}">Zurücksetzen</button>` : "";
    let eingabe;
    if (f.art === "schalter") {
      eingabe = `<label class="einst-schalter"><input type="checkbox" id="${id}" data-k="${f.schluessel}"`
        + `${f.wert === "true" || f.wert === "True" || f.wert === "1" ? " checked" : ""}> ${S.esc(f.titel)}</label>`;
    } else if (f.art === "mehrzeilig") {
      eingabe = `<textarea id="${id}" data-k="${f.schluessel}" rows="2" placeholder="${S.esc(f.platzhalter)}">${S.esc(f.wert)}</textarea>`;
    } else {
      const typ = f.art === "passwort" ? "password" : f.art === "zahl" ? "number" : "text";
      const bereich = f.bereich ? ` min="${Number(f.bereich[0])}" max="${Number(f.bereich[1])}" step="1"` : "";
      eingabe = `<input type="${typ}" id="${id}" data-k="${f.schluessel}" autocomplete="off"${bereich}`
        + ` value="${S.esc(f.wert)}" placeholder="${S.esc(f.platzhalter)}">`;
    }
    const hilfe = f.geheim && f.gesetzt ? (f.hilfe + " Zurzeit ist eines hinterlegt.") : f.hilfe;
    return `<div class="einst-feld">
      <div class="einst-kopf">${f.art === "schalter" ? "" : `<label for="${id}">${S.esc(f.titel)}</label>`}
        ${marke}<code class="einst-name">${S.esc(f.schluessel)}</code>${zurueck}</div>
      ${eingabe}
      ${hilfe ? `<div class="help">${S.esc(hilfe)}</div>` : ""}
    </div>`;
  }

  function uebernehmen(d) {
    felder = d.felder || [];
    gruppen = d.gruppen || [];
    document.getElementById("einst-aus").classList.toggle("hidden", !d.aus);
    zeichneEinstellungen();
  }

  async function ladeEinstellungen() {
    form.innerHTML = '<p class="help">Wird geladen …</p>';
    try { uebernehmen(await S.api("/api/admin/einstellungen")); }
    catch (e) { form.innerHTML = `<p class="notice">Die Einstellungen ließen sich nicht laden: ${S.esc(e.message)}</p>`; }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const knopf = form.querySelector('button[type=submit]');
    if (knopf.disabled) return;
    knopf.disabled = true;
    /* Nur Geändertes schicken. Würde das Formular alles senden, schriebe ein einziges Speichern
       JEDEN Wert fest – auch die unberührten. Von da an stünde alles auf „hier gesetzt“, und die
       .env hätte keine Wirkung mehr, ohne dass jemand das gewollt hätte. */
    const werte = {};
    form.querySelectorAll("[data-k]").forEach((el) => {
      const f = felder.find((x) => x.schluessel === el.dataset.k);
      if (!f) return;
      if (el.type === "checkbox") {
        if (el.checked !== (f.wert === "true")) werte[f.schluessel] = el.checked;
      } else if (f.geheim) {
        if (el.value) werte[f.schluessel] = el.value;      // leer heißt „unverändert“
      } else if (el.value !== f.wert) {
        werte[f.schluessel] = el.value;
      }
    });
    if (!Object.keys(werte).length) { knopf.disabled = false; return S.toast("Nichts geändert."); }
    try {
      const d = await S.api("/api/admin/einstellungen", { method: "PUT", body: { werte } });
      uebernehmen(d);
      S.toast("Einstellungen gespeichert");
    } catch (err) { S.toast(err.message, true); }
    finally { knopf.disabled = false; }
  });

  form.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-zurueck]");
    if (!b) return;
    e.preventDefault();
    const f = felder.find((x) => x.schluessel === b.dataset.zurueck);
    if (!(await S.confirm(`„${f ? f.titel : b.dataset.zurueck}“ zurücksetzen? Danach gilt wieder, `
                          + "was in der .env steht – oder die eingebaute Vorgabe.", "Zurücksetzen"))) return;
    try {
      uebernehmen(await S.api(`/api/admin/einstellungen/${encodeURIComponent(b.dataset.zurueck)}`, { method: "DELETE" }));
      S.toast("Zurückgesetzt");
    } catch (err) { S.toast(err.message, true); }
  });

  if (location.hash === "#einstellungen") reiter("einstellungen");
  else S.titel("Nutzerverwaltung", "verwaltung");
})();
