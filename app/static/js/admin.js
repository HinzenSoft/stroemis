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
        <td class="rolle" data-l="Rolle">${u.role === "admin" ? '<span class="badge">Admin</span>'
          : u.role === "editor" ? '<span class="badge">Redakteur</span>' : "Nutzer"}${u.is_pruefer ? ' <span class="badge grey" title="Zusatzrecht: darf Prüfungen abnehmen">Prüfer</span>' : ""}</td>
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

  function userForm(u) {
    u = u || {};
    return `
      <div class="field-row">
        <div><label>Name</label><input type="text" id="u-name" value="${S.esc(u.name)}"></div>
        <div><label>Gliederung</label><input type="text" id="u-gl" value="${S.esc(u.gliederung)}"></div>
      </div>
      <label>E-Mail-Adresse</label><input type="email" id="u-email" value="${S.esc(u.email)}" required>
      <div class="field-row">
        <div><label>Telefon</label><input type="tel" id="u-phone" value="${S.esc(u.phone)}"></div>
        <div><label>Rolle</label><select id="u-role">
          <option value="user" ${u.role !== "admin" && u.role !== "editor" ? "selected" : ""}>Nutzer</option>
          <option value="editor" ${u.role === "editor" ? "selected" : ""}>Redakteur</option>
          <option value="admin" ${u.role === "admin" ? "selected" : ""}>Administrator</option>
        </select>
        <div class="help">Redakteur: darf alle Seiten und Alben bearbeiten, aber keine Nutzer verwalten
          und nichts ohne Anmeldung veröffentlichen.</div></div>
      </div>
      <label class="inline"><input type="checkbox" id="u-pruefer" ${u.is_pruefer ? "checked" : ""}> Prüfer – darf Prüfungen abnehmen (zusätzlich zur Rolle)</label>
      <div class="help">Schaltet den Reiter „Prüfungen“ frei: Lehrgänge, Teilnehmende, Bewertungen und Medien. Gilt unabhängig von der Rolle – auch ein Administrator braucht das Häkchen.</div>
      <label>${u.id ? "Neues Passwort (leer lassen, um es zu behalten)" : "Passwort (leer lassen, um eines zu erzeugen)"}</label>
      <input type="text" id="u-pw" autocomplete="off">
      ${u.id ? `<label class="inline"><input type="checkbox" id="u-active" ${u.active ? "checked" : ""}> Konto aktiv</label>`
             : `<label class="inline"><input type="checkbox" id="u-invite" checked> Einladung per E-Mail schicken (Link zum Passwort setzen)</label>`}`;
  }

  function read(body) {
    return {
      name: body.querySelector("#u-name").value, gliederung: body.querySelector("#u-gl").value,
      email: body.querySelector("#u-email").value, phone: body.querySelector("#u-phone").value,
      role: body.querySelector("#u-role").value, password: body.querySelector("#u-pw").value || undefined,
      is_pruefer: body.querySelector("#u-pruefer").checked,
    };
  }

  document.getElementById("btn-new-user").addEventListener("click", () => {
    S.dialog(`<h2>Nutzer anlegen</h2>${userForm()}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="u-save" type="button">Anlegen</button></div>`,
      (dlg, body) => {
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

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = +btn.closest("tr").dataset.id;
    const u = users.find((x) => x.id === id);
    if (btn.dataset.act === "edit") {
      S.dialog(`<h2>${S.esc(u.name || u.email)}</h2>${userForm(u)}
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="u-save" type="button">Speichern</button></div>`,
        (dlg, body) => {
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
      if (!(await S.confirm(`Nutzer ${u.email} löschen? Alben, Bilder und Wiki-Seiten bleiben erhalten und gehen auf dich über.`))) return;
      try { await S.api(`/api/admin/users/${id}`, { method: "DELETE" }); await load(); S.toast("Nutzer gelöscht"); }
      catch (err) { S.toast(err.message, true); }
    }
  });

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
