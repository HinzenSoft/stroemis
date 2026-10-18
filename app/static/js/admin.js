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

  /* Rechte je Modul: Jeder Nutzer hat in jedem der vier Module eine Stufe – kein Zugriff,
     Mitglied oder Verwaltung. Was die Stufe im Modul bedeutet, steht hier an EINER Stelle und
     erscheint als Titel am Auswahlfeld, in der Tabelle wie im Dialog. Im Modul Verwaltung gibt
     es kein „Mitglied“: Nutzer, Rechte und Einstellungen pflegt man ganz oder gar nicht.
     Material ist seit Phase 2 nur Anzeige (nurAnzeige): Rechte am Bestand vergibt der Verwalter eines
     Ordners als Freigabe – hier steht, was daraus folgt („alles“, „n Freigaben“ oder „–“). */
  const MODULE = [
    { k: "karte", t: "Spots", hilfe: "Mitglied: eigene Alben anlegen und bearbeiten. Verwaltung: alle Alben." },
    { k: "wiki", t: "Wiki", hilfe: "Mitglied: eigene und freigegebene Seiten. Verwaltung: alle Seiten, beschränkte lesen, veröffentlichen, HTML-Bausteine, Ersteller ändern." },
    { k: "pruefungen", t: "Prüfungen", hilfe: "Mitglied: Prüfungen abnehmen (Prüfer). Verwaltung: zusätzlich Kataloge pflegen und jeden Lehrgang leiten." },
    { k: "material", t: "Material", nurAnzeige: true, hilfe: "Rechte am Bestand vergibt der Verwalter eines Ordners unter Bestand → Ordner → Bearbeiten → Freigaben. Die Verwaltung sieht alles und legt Gliederungen an. Prüfer und Katalogpflege sind Häkchen; beide geben allein keinen Bestand zu sehen. Prüfen braucht zusätzlich eine Prüffreigabe (befristet nur für externe Prüfer)." },
    { k: "verwaltung", t: "Verwaltung", nurVoll: true,
      hilfe: "Verwaltung: Nutzer, Rechte und Einstellungen – schließt alle Rechte in allen Modulen ein." },
  ];
  const STUFEN = [[0, "–"], [1, "Mitglied"], [2, "Verwaltung"]];
  const VORGABE = { karte: 1, wiki: 1, pruefungen: 0, material: 0, verwaltung: 0 };   // neues Konto
  const ERGIBT_SICH = "ergibt sich aus Verwaltung";

  /* Ein Auswahlfeld für die Stufe eines Moduls. Steht die Verwaltung auf „Verwaltung“, sind die
     übrigen drei Felder nur noch Anzeige: Der Server speichert dort ohnehin 2, und ein Feld, das
     man umstellt und das sofort zurückspringt, wäre verwirrender als ein abgeschaltetes. Das
     eigene Konto kann sich die Verwaltung nicht entziehen – der Server lehnt es ab, also wird
     es gar nicht erst angeboten. */
  function rechtFeld(m, rechte, opts) {
    opts = opts || {};
    rechte = rechte || {};
    if (m.nurAnzeige) return materialAnzeige(Object.assign({}, opts.konto, { rechte }), opts.id);
    const voll = (rechte.verwaltung | 0) === 2;
    let wert = rechte[m.k] | 0, aus = false, titel = m.hilfe;
    if (m.k !== "verwaltung" && voll) { wert = 2; aus = true; titel = ERGIBT_SICH; }
    if (m.k === "verwaltung" && opts.eigenes) { aus = true; titel = "Dein eigenes Konto: Die Verwaltung kannst du dir nicht selbst entziehen."; }
    const stufen = STUFEN.filter(([v]) => !(m.nurVoll && v === 1));
    return `<select class="recht-wahl" data-modul="${m.k}"${opts.id ? ` id="${opts.id}"` : ""} aria-label="${S.esc(m.t)}"
      title="${S.esc(titel)}"${aus ? " disabled" : ""}>${stufen.map(([v, l]) => `<option value="${v}"${v === wert ? " selected" : ""}>${l}</option>`).join("")}</select>`;
  }

  /* Die Anzeige im Feld Material: „alles“ für die Verwaltung, sonst die Zahl der gültigen Freigaben – oder „–“. Als
     <output>, damit die Beschriftung im Dialog dazugehört. */
  function materialAnzeige(u, id) {
    const n = u.mat_freigaben | 0;
    const text = ((u.rechte || {}).verwaltung | 0) === 2 ? "alles" : n ? `${n} Freigabe${n === 1 ? "" : "n"}` : "–";
    const m = MODULE.find((x) => x.k === "material");
    return `<output class="recht-anzeige"${id ? ` id="${id}"` : ""} title="${S.esc(m.hilfe)}">${text}</output>`;
  }

  /* Die vier Zellen einer Zeile neu zeichnen – nach jeder Antwort des Servers, ob Erfolg oder
     Fehler: So zeigt die Zeile immer das, was gespeichert ist, und bei verwaltung = 2 ziehen
     die anderen drei Felder von selbst nach. */
  function zeichneRechte(tr, u) {
    MODULE.forEach((m) => {
      tr.querySelector(`td.recht[data-modul="${m.k}"]`).innerHTML = rechtZelle(m, u);
    });
  }

  /* Das Material-Feld trägt darunter die beiden Kennzeichen des Moduls. Gesetzt werden sie im
     Dialog „Bearbeiten“. Die Urkundennummer trägt der Prüfer selbst im Profil ein – bis dahin darf
     er nicht prüfen, und seine Marke sagt das (gelb statt grau). Gelb ist auch ein Konto mit einer
     Stufe aus Phase 1, aber ohne Freigabe: Es sah früher Bestand und sieht jetzt keinen. */
  function rechtZelle(m, u) {
    const feld = rechtFeld(m, u.rechte, { eigenes: u.id === STROEMIS.user.id, konto: u });
    if (m.k !== "material") return feld;
    const marken = [];
    if (u.mat_stufe_alt > 0 && !u.mat_freigaben && ((u.rechte || {}).verwaltung | 0) !== 2) {
      marken.push(`<span class="badge" title="In Phase 1 hatte das Konto die Stufe „${u.mat_stufe_alt === 2 ? "Verwaltung" : "Mitglied"}“ im Modul Material. Sie wirkt nicht mehr – den Bestand zeigen nur Freigaben, vergeben am Ordner (Bestand → Ordner → Bearbeiten → Freigaben).">Stufe aus Phase 1 – ohne Frei&shy;gabe</span>`);
    }
    if (u.mat_pruefer && u.urkunde_gueltig) marken.push(`<span class="badge grey" title="Prüfer (Sachkundiger), Urkundennummer ${S.esc(u.urkundennummer)}">Prüfer</span>`);
    else if (u.mat_pruefer) marken.push('<span class="badge urkunde-fehlt" title="Häkchen „Prüfer“ gesetzt, aber noch keine Urkundennummer – die trägt der Prüfer selbst im Profil ein. Bis dahin darf er nicht prüfen.">Prüfer – Urkunden&shy;nummer fehlt</span>');
    if (u.mat_katalog) marken.push('<span class="badge grey" title="Produktkatalogpfleger">Katalog</span>');
    return feld + (marken.length ? `<div class="recht-marken">${marken.join(" ")}</div>` : "");
  }

  async function load() {
    try { users = (await S.api("/api/admin/users")).users; }
    catch (e) { S.toast("Die Nutzerliste ließ sich nicht laden: " + e.message, true); return; }
    const pend = users.filter((u) => u.status === "pending");
    const box = document.getElementById("pending");
    box.innerHTML = pend.length ? `<h2>Offene Kontoanfragen <span class="badge">${pend.length}</span></h2>${pend.map((u) => `
      <div class="request" data-id="${u.id}">
        <div><strong>${S.esc(u.name)}</strong> · ${S.esc(u.email)}<br><span class="small">${S.esc(u.gliederung)}${u.phone ? " · " + S.esc(u.phone) : ""} · angefragt ${S.fmtDate(u.created_at, true)}</span>
          ${u.reason ? `<div class="c-quote" style="margin-top:6px">${S.esc(u.reason)}</div>` : ""}</div>
        <div class="btn-row"><button class="btn small" data-act="approve">Freigeben</button><button class="btn danger small" data-act="reject">Ablehnen</button></div>
      </div>`).join("")}` : "";
    tbody.innerHTML = users.filter((u) => u.status !== "pending").map((u) => `
      <tr data-id="${u.id}" ${u.active ? "" : 'class="muted"'}>
        <td data-l="Name">${S.esc(u.name) || "<span class='muted'>–</span>"}${u.active ? "" : ' <span class="badge grey">deaktiviert</span>'}</td>
        <td class="mail" data-l="E-Mail">${S.esc(u.email)}</td>
        <td data-l="Gliederung">${S.esc(u.gliederung)}</td>
        ${MODULE.map((m) => `<td class="recht" data-l="${m.t}" data-modul="${m.k}">${rechtZelle(m, u)}</td>`).join("")}
        <td class="small" data-l="Zuletzt da">${letzterLogin(u)}</td>
        <td class="small" data-l="Inhalte">${u.page_count} Artikel, ${u.album_count} Alben, ${u.photo_count} Bilder</td>
        <td class="tabelle-aktionen"><div class="btn-row">
          <button class="btn ghost small" data-act="edit">Bearbeiten</button>
          <button class="btn ghost small" data-act="reset">Reset-Mail</button>
          ${u.id !== STROEMIS.user.id ? '<button class="btn ghost small" data-act="delete">Löschen</button>' : ""}
        </div></td>
      </tr>`).join("");
  }

  /* Probemail: Kommt bei jemandem nichts an, sagt der Mailserver hier wörtlich, woran es liegt –
     keine Verbindung, Anmeldung abgelehnt, Empfänger abgewiesen. Die Antwort steht im Dialog
     und nicht in einem Kurzhinweis: Sie ist zum Lesen und Weitergeben da. */
  document.getElementById("btn-testmail").addEventListener("click", () => {
    S.dialog(`<h2>Testmail senden</h2>
      <p class="help">Verschickt eine Probemail über den eingerichteten Mailserver und zeigt, was er
        dazu sagt. Kommt sie an, funktioniert der Weg bis zu diesem Postfach; landet sie im Spam oder
        gar nicht, liegt es meist an SPF, DKIM oder DMARC der Absenderdomain.</p>
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
        S.toast(r.mailed ? `${u.name} freigegeben – E-Mail verschickt` : `${u.name} freigegeben (keine E-Mail: SMTP nicht konfiguriert)`);
      } else {
        if (!(await S.confirm(`Anfrage von ${u.name} ablehnen und löschen?`, "Ablehnen"))) return;
        await S.api(`/api/admin/users/${id}/reject`, { method: "POST", body: {} });
        S.toast("Anfrage abgelehnt");
      }
      load();
    } catch (err) { S.toast(err.message, true); }
  });

  /* Die Urkundennummer zeigt der Dialog nur – eintragen und ändern kann sie allein der Prüfer im
     eigenen Profil (PUT /api/material/urkundennummer). */
  function urkundeLesend(u) {
    if (!u.id) return "Urkundennummer: trägt der Prüfer nach der ersten Anmeldung selbst im Profil ein – solange darf er nicht prüfen.";
    if (u.urkunde_gueltig) return `Urkundennummer: <strong>${S.esc(u.urkundennummer)}</strong> – trägt der Prüfer selbst im Profil ein.`;
    return "Urkundennummer: noch keine – solange darf er nicht prüfen. Er trägt sie selbst im Profil ein.";
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
      <label>Rechte</label>
      <div class="rechte-reihe">${MODULE.map((m) => `<div><label for="u-r-${m.k}">${m.t}</label>${rechtFeld(m, rechte, { id: "u-r-" + m.k, eigenes, konto: u })}</div>`).join("")}</div>
      <div class="help">„–“ kein Zugriff · „Mitglied“ eigene Inhalte, bei Prüfungen: Prüfungen abnehmen ·
        „Verwaltung“ alles im Modul. Verwaltung im Modul „Verwaltung“ schließt alle Rechte ein.
        Was eine Stufe genau umfasst, steht als Hinweis am Feld. Material ist nur Anzeige: Rechte am Bestand vergibt der
        Verwalter eines Ordners unter Bestand → Ordner → Bearbeiten → Freigaben; die Verwaltung sieht alles und legt Gliederungen an.</div>
      <fieldset class="mat-rollen"><legend>Modul Material</legend>
        <label class="inline"><input type="checkbox" id="u-mat-pruefer" ${u.mat_pruefer ? "checked" : ""}> Prüfer (Sachkundiger, Qualifikation 1012)</label>
        <p class="mat-urkunde" ${u.mat_pruefer ? "" : "hidden"}>${urkundeLesend(u)}</p>
        <div class="help">Das Häkchen macht das Konto zum Prüfer. Urkundennummer und Unterschrift trägt der Prüfer selbst in seinem Profil ein
          („Urkundennummer und Unterschrift“); beides steht später auf jedem Prüfprotokoll. Prüfen kann er erst mit Urkundennummer
          und einer Prüffreigabe am Ordner (befristet nur für externe Prüfer) – auch die Verwaltung prüft nur mit eigenem Häkchen,
          eigener Urkundennummer und eigener Prüffreigabe.</div>
        <label class="inline"><input type="checkbox" id="u-mat-katalog" ${u.mat_katalog ? "checked" : ""}> Produktkatalogpfleger – Kategorien, Produkte, Herstellerdokumente und Prüfformulare (plattformweit)</label>
        <div class="help">Beide Häkchen geben Zugang zum Modul (Katalog, Profil), aber keinen Bestand – den zeigen erst Freigaben.
          Sie brauchen einen Namen: Prüfer und Katalogpfleger stehen namentlich in Journal und Protokollen.</div>
      </fieldset>
      ${u.id ? `<fieldset class="mat-rollen"><legend>Freigaben im Modul Material</legend>
        <div id="u-freigaben"><p class="help">Wird geladen …</p></div>
        <div class="help">Angelegt wird eine Freigabe am Ordner (Bestand → Ordner → Bearbeiten → Freigaben), nicht hier.</div>
      </fieldset>` : ""}
      <label>${u.id ? "Neues Passwort (leer lassen, um es zu behalten)" : "Passwort (leer lassen, um eines zu erzeugen)"}</label>
      <input type="text" id="u-pw" autocomplete="off">
      ${u.id ? `<label class="inline"><input type="checkbox" id="u-active" ${u.active ? "checked" : ""}> Konto aktiv</label>`
             : `<label class="inline"><input type="checkbox" id="u-invite" checked> Einladung per E-Mail schicken (Link zum Passwort setzen)</label>`}`;
  }

  function read(body) {
    const rechte = {};
    // Material schickt der Dialog nicht mit: Die Stufe dort ist Anzeige, der Server übergeht sie.
    MODULE.filter((m) => !m.nurAnzeige).forEach((m) => { rechte[m.k] = +body.querySelector("#u-r-" + m.k).value; });
    return {
      name: body.querySelector("#u-name").value, gliederung: body.querySelector("#u-gl").value,
      email: body.querySelector("#u-email").value, phone: body.querySelector("#u-phone").value,
      password: body.querySelector("#u-pw").value || undefined, rechte,
      // Die Urkundennummer schickt der Dialog nicht mit: Sie gehört dem Prüfer (Profil).
      mat_pruefer: body.querySelector("#u-mat-pruefer").checked, mat_katalog: body.querySelector("#u-mat-katalog").checked,
    };
  }

  /* Im Dialog gilt dieselbe Regel wie in der Tabelle, nur ohne Server dazwischen: Wer die
     Verwaltung auf „Verwaltung“ stellt, sieht die drei anderen Felder sofort auf „Verwaltung“
     springen und erstarren – und bekommt beim Zurückstellen seine vorherigen Werte wieder. */
  function koppleRechte(body, u) {
    // Der Hinweis zur Urkundennummer gehört nur zu einem Prüfer – er erscheint mit dem Häkchen.
    body.querySelector("#u-mat-pruefer").addEventListener("change", (e) => { body.querySelector(".mat-urkunde").hidden = !e.target.checked; });
    const chef = body.querySelector("#u-r-verwaltung");
    chef.addEventListener("change", () => {
      const voll = chef.value === "2";
      // Die Anzeige Material geht mit: Die Verwaltung sieht alles.
      body.querySelector("#u-r-material").outerHTML = materialAnzeige(Object.assign({}, u, { rechte: { verwaltung: voll ? 2 : 0 } }), "u-r-material");
      MODULE.filter((m) => m.k !== "verwaltung" && !m.nurAnzeige).forEach((m) => {
        const f = body.querySelector("#u-r-" + m.k);
        if (voll) { f.dataset.vorher = f.value; f.value = "2"; f.disabled = true; f.title = ERGIBT_SICH; }
        else { f.disabled = false; f.title = m.hilfe; if (f.dataset.vorher !== undefined) f.value = f.dataset.vorher; }
      });
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
            const mail = d.send_invite ? (r.invite_sent ? "<p>Die Einladung wurde per E-Mail verschickt.</p>" : "<p class='notice'>SMTP ist nicht konfiguriert – der Einladungslink steht im Server-Log (docker logs).</p>") : "";
            S.dialog(`<h2>Nutzer angelegt</h2><p>${S.esc(d.email)}</p>${info}${mail}<div class="dlg-actions"><button class="btn" data-close type="button">Schließen</button></div>`);
          } catch (e) { S.toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
      });
  });

  /* Rechte direkt in der Tabelle ändern: ein Wechsel, ein PUT mit nur diesem Modul. Die Antwort
     trägt die vollständigen Rechte – bei verwaltung = 2 also auch die drei nachgezogenen –, und
     daraus wird die Zeile gezeichnet. Schlägt es fehl (etwa weil man sich selbst die Verwaltung
     entzieht), bleibt der alte Stand und das Feld springt zurück. */
  tbody.addEventListener("change", async (e) => {
    const sel = e.target.closest("select[data-modul]");
    if (!sel) return;
    const tr = sel.closest("tr");
    const u = users.find((x) => x.id === +tr.dataset.id);
    if (!u) return;
    sel.disabled = true;      // kein zweiter Wechsel, solange der erste unterwegs ist
    try {
      const r = await S.api(`/api/admin/users/${u.id}`, { method: "PUT", body: { rechte: { [sel.dataset.modul]: +sel.value } } });
      u.rechte = (r.user && r.user.rechte) || Object.assign({}, u.rechte, { [sel.dataset.modul]: +sel.value });
      S.toast("Gespeichert");
    } catch (err) { S.toast(err.message, true); }
    zeichneRechte(tr, u);
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
          body.querySelector("#u-save").onclick = async (ev) => {
            const knopf = ev.currentTarget;
            if (knopf.disabled) return;
            knopf.disabled = true;
            const d = read(body);
            d.active = body.querySelector("#u-active").checked;
            try { await S.api(`/api/admin/users/${id}`, { method: "PUT", body: d }); dlg.close(); await load(); S.toast("Gespeichert"); }
            catch (err) { S.toast(err.message, true); }
            finally { knopf.disabled = false; }
          };
        });
    } else if (btn.dataset.act === "reset") {
      try { const r = await S.api(`/api/admin/users/${id}/reset-mail`, { method: "POST", body: {} }); S.toast(r.message); }
      catch (err) { S.toast(err.message, true); }
    } else if (btn.dataset.act === "delete") {
      loeschDialog(u);
    }
  });

  /* --- Modul Material im Dialog „Bearbeiten“: die Freigaben des Kontos -------------------------- */
  const RECHT = { lesen: "lesen", verwalten: "verwalten", pruefen: "prüfen" };
  // „2027-12-31“ → „31.12.2027“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const tag = (iso) => { const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}.${m[2]}.${m[1]}` : ""; };
  const mehrzahl = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;

  function zustand(f) {
    if (!f.gueltig) return `<span class="muted">abgelaufen am ${tag(f.bis)}</span>`;
    if (!f.wirkt) {
      const quali = f.recht === "pruefen" && !f.konto.qualifiziert;
      // Eine dauerhafte Prüffreigabe wirkt nur zusammen mit lesen oder verwalten dort (nur externe Prüfer sind befristet).
      const grund = !quali && f.recht === "pruefen" && f.bis === null && f.grundrecht_dort === false;
      const titel = quali ? "Ohne Häkchen und Urkundennummer wirkt eine Prüffreigabe nicht."
        : grund ? "Dauerhaft prüft nur, wer dort auch lesen oder verwalten hat." : "Das Konto ist deaktiviert oder hat keinen Namen.";
      return `<span class="badge" title="${titel}">wirkt nicht${quali ? " – Qualifikation fehlt" : grund ? " – dauerhaft nur mit lesen oder verwalten" : ""}</span>`;
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
        <td data-l="Ordner"><a href="/material/ordner/${f.ordner.id}?freigaben" title="Freigaben dieses Ordners öffnen">${S.esc(f.ordner.pfad)}</a>${f.notiz ? `<div class="small muted">${S.esc(f.notiz)}</div>` : ""}</td>
        <td data-l="Recht">${S.esc(RECHT[f.recht] || f.recht)}</td>
        <td data-l="bis">${f.bis ? tag(f.bis) : "dauerhaft"}</td>
        <td data-l="Zustand">${zustand(f)}</td>
        <td class="tabelle-aktionen"><button class="btn secondary small" type="button" data-entziehen="${f.id}">Entziehen</button></td>
      </tr>`).join("")}</tbody></table>`
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
            des Kontos unter <a href="/material/pruefungen">Material → Prüfungen</a> → Offene Prüfungen freigeben.</p>`);
        }
        load();
      } catch (e) { S.toast(e.message, true); b.disabled = false; }
    }));
  }

  /* Löschen: Was im Modul Material daraus folgt, steht vorher da (GET …/material-folgen). Fehlt die Auskunft, lässt
     sich trotzdem löschen – der Dialog sagt dann nur, dass er die Folgen nicht kennt. */
  function folgenText(f) {
    const n = (x) => x | 0;
    return `${mehrzahl(n(f.freigaben), "Freigabe wird", "Freigaben werden")} entfernt, ${mehrzahl(n(f.zuordnungen), "Artikel verliert seine", "Artikel verlieren ihre")} Zuordnung,
      ${mehrzahl(n(f.entwuerfe), "offene Prüfung wird zur Reservierung", "offene Prüfungen werden zu Reservierungen")} ohne Prüfer.
      Festgeschriebene Prüfungen (${n(f.pruefungen)}) behalten den Namen – Nachweis nach EN 365.`;
  }

  function loeschDialog(u) {
    S.dialog(`<h2>Nutzer löschen</h2>
      <p>${S.esc(u.name || u.email)} (${S.esc(u.email)}) löschen? Alben, Bilder und Wiki-Seiten bleiben erhalten und gehen auf dich über.</p>
      <div id="u-folgen"><p class="help">Folgen im Modul Material werden ermittelt …</p></div>
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
        el.innerHTML = `<p class="notice">Modul Material: ${folgenText(await S.api(`/api/admin/users/${u.id}/material-folgen`))}</p>`;
      } catch (e) {
        el.innerHTML = `<p class="help">Was das Löschen im Modul Material entfernt (Freigaben, Zuordnungen, offene Prüfungen), ließ sich
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
    // „Nutzer anlegen“ gehört zur Liste. Die Probemail bleibt auf beiden Reitern stehen: Sie ist
    // die Gegenprobe zu den Mail-Einstellungen und gerade dort am nötigsten.
    document.getElementById("btn-new-user").classList.toggle("hidden", name !== "nutzer");
    if (name !== "nutzer" && !felder.length) ladeEinstellungen();
    // Der Reiter gehört in die Adresse: Wer die Einstellungen offen hatte und neu lädt, landet
    // sonst wieder bei den Nutzern.
    history.replaceState(null, "", name === "nutzer" ? "/admin" : "/admin#einstellungen");
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
      ? `<button type="button" class="btn ghost small" data-zurueck="${f.schluessel}">Zurücksetzen</button>` : "";
    let eingabe;
    if (f.art === "schalter") {
      eingabe = `<label class="einst-schalter"><input type="checkbox" id="${id}" data-k="${f.schluessel}"`
        + `${f.wert === "true" || f.wert === "True" || f.wert === "1" ? " checked" : ""}> ${S.esc(f.titel)}</label>`;
    } else if (f.art === "mehrzeilig") {
      eingabe = `<textarea id="${id}" data-k="${f.schluessel}" rows="2" placeholder="${S.esc(f.platzhalter)}">${S.esc(f.wert)}</textarea>`;
    } else {
      const typ = f.art === "passwort" ? "password" : f.art === "zahl" ? "number" : "text";
      eingabe = `<input type="${typ}" id="${id}" data-k="${f.schluessel}" autocomplete="off"`
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
})();
