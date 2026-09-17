(function () {
  const tbody = document.querySelector("#users tbody");
  let users = [];

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
        <td data-l="Rolle">${u.role === "admin" ? '<span class="badge">Admin</span>'
          : u.role === "editor" ? '<span class="badge">Redakteur</span>' : "Nutzer"}</td>
        <td class="small" data-l="Inhalte">${u.album_count} Alben, ${u.photo_count} Bilder</td>
        <td class="btn-row">
          <button class="btn ghost small" data-act="edit">Bearbeiten</button>
          <button class="btn ghost small" data-act="reset">Reset-Mail</button>
          ${u.id !== STROEMIS.user.id ? '<button class="btn ghost small" data-act="delete">Löschen</button>' : ""}
        </td>
      </tr>`).join("");
  }

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
})();
