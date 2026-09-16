/* Karte mit Thumbnail-Markern, Clustern, Alben und Bild-Details */
(function () {
  const { esc, api, toast, dialog, fmtDate, fmtCoord, CAT } = S;
  const me = STROEMIS.user;
  const isAdmin = me.role === "admin";

  const state = {
    map: null, cluster: null, photos: [], markers: new Map(), filter: "",
    album: null, lbIndex: 0, locateQueue: [], locating: null, tempMarker: null, meMarker: null,
  };

  const $ = (sel) => document.querySelector(sel);
  const panel = $("#panel"), panelTitle = $("#panel-title"), panelBody = $("#panel-body");
  const fileInput = $("#file-input");

  /* --- Karte ------------------------------------------------------------ */
  function initMap() {
    const c = STROEMIS.mapCenter.split(",").map(Number);
    state.map = L.map("map", { zoomControl: false }).setView(c, STROEMIS.mapZoom);
    L.control.zoom({ position: "bottomright" }).addTo(state.map);
    const strasse = L.tileLayer(STROEMIS.tileUrl, { maxZoom: 19, attribution: STROEMIS.tileAttribution });
    /* Das Luftbild steht zuerst und ist die Startebene: Wer einen Spot sucht, erkennt darauf Stege,
       Slipstellen, Kiesbänke und Wehre – auf der Straßenkarte ist an dieser Stelle nur Blau. */
    const satellit = STROEMIS.satUrl
      ? L.tileLayer(STROEMIS.satUrl, { maxZoom: 19, attribution: STROEMIS.satAttribution })
      : null;
    /* Beschriftung über dem Luftbild: Ohne Straßen-, Orts- und Gewässernamen ist ein Luftbild
       zur Orientierung mühsam – man sieht die Kiesbank, weiß aber nicht, an welchem Fluss.
       Die Ebenen liegen in einer eigenen Schicht über den Kacheln (350 steht zwischen
       Kachel- und Markierungsebene), damit die Reihenfolge unabhängig davon stimmt, wann
       welche Ebene dazukommt. Sie gehören zum Luftbild und gehen mit ihm. */
    state.map.createPane("beschriftung");
    state.map.getPane("beschriftung").style.zIndex = 350;
    state.map.getPane("beschriftung").style.pointerEvents = "none";
    const beschriftung = L.layerGroup(
      (STROEMIS.satLabelsUrl || "").split(",").map((u) => u.trim()).filter(Boolean)
        .map((u) => L.tileLayer(u, { maxZoom: 19, pane: "beschriftung" })));

    const layers = {};
    if (satellit) layers["Satellit"] = satellit;
    layers["Karte"] = strasse;
    if (STROEMIS.topoUrl) {
      layers["Gelände (OpenTopoMap)"] = L.tileLayer(STROEMIS.topoUrl, { maxZoom: 17, attribution: STROEMIS.topoAttribution });
    }
    (satellit || strasse).addTo(state.map);
    const beschriftungFuehren = (ebene) => {
      if (ebene === satellit && beschriftung.getLayers().length) beschriftung.addTo(state.map);
      else state.map.removeLayer(beschriftung);
    };
    beschriftungFuehren(satellit || strasse);
    state.map.on("baselayerchange", (e) => beschriftungFuehren(e.layer));
    if (Object.keys(layers).length > 1) L.control.layers(layers, null, { position: "bottomright" }).addTo(state.map);
    // Eigener Standort – im Gelände praktisch, um Bilder ohne Geotag direkt hier zu platzieren
    const LocateCtl = L.Control.extend({
      onAdd() {
        const div = L.DomUtil.create("div", "leaflet-bar");
        const a = L.DomUtil.create("a", "locate-me", div);
        a.href = "#"; a.title = "Meinen Standort anzeigen"; a.textContent = "◎"; a.setAttribute("role", "button");
        L.DomEvent.on(a, "click", (e) => {
          L.DomEvent.preventDefault(e);
          state.map.locate({ setView: true, maxZoom: 17, enableHighAccuracy: true });
        });
        return div;
      },
    });
    new LocateCtl({ position: "bottomright" }).addTo(state.map);
    state.map.on("locationerror", () => toast("Standort konnte nicht ermittelt werden.", true));
    state.map.on("locationfound", (e) => {
      if (state.meMarker) state.map.removeLayer(state.meMarker);
      state.meMarker = L.circleMarker(e.latlng, { radius: 7, color: "#fff", weight: 2, fillColor: "#0069b4", fillOpacity: .95 }).addTo(state.map);
      if (state.locating) onMapClick({ latlng: e.latlng });
    });
    state.cluster = L.markerClusterGroup({
      maxClusterRadius: 72,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      zoomToBoundsOnClick: true,
      iconCreateFunction: clusterIcon,
    });
    state.map.addLayer(state.cluster);
    state.map.on("click", onMapClick);
  }

  function clusterIcon(cluster) {
    const kids = cluster.getAllChildMarkers();
    const n = kids.length;
    // Ein festgelegtes Albumdeckblatt liegt obenauf – sonst zeigt der Stapel das, was der Zufall
    // der Reihenfolge gerade nach vorn spült. sort() ist stabil, die übrige Folge bleibt also.
    const geordnet = kids.slice().sort((x, y) => (y.options.photo.cover ? 1 : 0) - (x.options.photo.cover ? 1 : 0));
    const thumbs = geordnet.slice(0, 3).map((m) => m.options.photo.thumb);
    let html = '<div class="cm">';
    if (thumbs[2]) html += `<div class="stack s3" style="background-image:url('${thumbs[2]}')"></div>`;
    if (thumbs[1]) html += `<div class="stack s2" style="background-image:url('${thumbs[1]}')"></div>`;
    html += `<div class="stack s1" style="background-image:url('${thumbs[0]}')"></div>`;
    html += `<div class="count" title="${n} Bilder zusammengefasst">${n}</div></div>`;
    return L.divIcon({ className: "cluster-marker", html, iconSize: [71, 71], iconAnchor: [33, 33] });
  }

  function photoMarker(p) {
    const icon = L.divIcon({
      className: "thumb-marker",
      html: `<div class="tm ${esc(p.category)}" style="background-image:url('${p.thumb}')" title="${esc(p.album_title)}">${p.kind === "video" ? '<span class="play" aria-hidden="true">▶</span>' : ""}</div>`,
      iconSize: [64, 64], iconAnchor: [32, 32],
    });
    const m = L.marker([p.lat, p.lon], { icon, photo: p, title: p.album_title });
    m.on("click", () => {
      if (state.locating) return;
      openAlbum(p.album_id, p.id, true);
    });
    return m;
  }

  async function loadMap() {
    // Scheitert der Abruf (Netz weg, Server neu gestartet), bleibt die Karte stehen, wie sie ist,
    // und sagt es. Vorher brach der Aufruf still ab – mitten in einer Kette, deren Rest damit
    // ebenfalls ausfiel, ohne dass irgendwo etwas zu sehen war.
    let d;
    try { d = await api("/api/map"); } catch (e) { return toast("Die Karte ließ sich nicht laden: " + e.message, true); }
    state.photos = d.photos;
    state.markers.clear();
    for (const p of state.photos) state.markers.set(p.id, photoMarker(p));
    applyFilter();
  }

  function applyFilter() {
    state.cluster.clearLayers();
    const list = [];
    for (const [, m] of state.markers) {
      if (!state.filter || m.options.photo.category === state.filter) list.push(m);
    }
    state.cluster.addLayers(list);
  }

  document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.filter = b.dataset.cat;
    applyFilter();
  }));

  function fitAlbum(album) {
    const pts = album.photos.filter((p) => p.lat != null).map((p) => [p.lat, p.lon]);
    if (!pts.length) return toast("Dieses Album hat noch keine Bilder mit Position.", true);
    if (pts.length === 1) state.map.setView(pts[0], Math.max(state.map.getZoom(), 17));
    else state.map.fitBounds(L.latLngBounds(pts), { padding: [60, 60], maxZoom: 18 });
  }

  /* --- Seitenleiste ------------------------------------------------------ */
  function openPanel(title, html) {
    panelTitle.textContent = title;
    panelBody.innerHTML = html;
    panel.classList.add("open");
  }
  function closePanel() {
    panel.classList.remove("open");
    state.album = null;
    if (location.hash.startsWith("#album=")) history.replaceState(null, "", location.pathname);
  }
  $("#panel-close").addEventListener("click", closePanel);

  $("#btn-albums").addEventListener("click", showAlbums);
  async function showAlbums() {
    let d;
    try { d = await api("/api/albums"); } catch (e) { return toast("Die Alben ließen sich nicht laden: " + e.message, true); }
    state.album = null;
    if (!d.albums.length) {
      return openPanel("Alben", `<div class="empty"><strong>Noch keine Alben</strong>Lege ein Album an und lade Bilder hoch – Bilder mit Geotag erscheinen sofort auf der Karte.</div>`);
    }
    openPanel("Alben", `<ul class="album-list">${d.albums.map((a) => `
      <li data-id="${a.id}">
        ${a.cover ? `<img src="${a.cover}" alt="">` : '<div class="noimg"></div>'}
        <div>
          <div class="t">${esc(a.title)}</div>
          <div class="small"><span class="cat ${esc(a.category)}">${CAT[a.category] || a.category}</span>
            ${a.photo_count} Bilder${a.unlocated_count ? ` <span class="badge" title="Bilder ohne Position">${a.unlocated_count} ohne Position</span>` : ""}</div>
          <div class="meta">${esc(a.owner_name || "")}${a.contact_name ? " · Ansprechpartner: " + esc(a.contact_name) : ""}</div>
        </div>
      </li>`).join("")}</ul>`);
    panelBody.querySelectorAll("li").forEach((li) => li.addEventListener("click", () => openAlbum(+li.dataset.id)));
  }

  async function openAlbum(id, highlightId, openBig) {
    let d;
    try { d = await api(`/api/albums/${id}`); } catch (e) { return toast(e.message, true); }
    const a = d.album;
    state.album = a;
    history.replaceState(null, "", `#album=${a.id}`);
    const contact = [];
    if (a.contact_name) contact.push(["Name", esc(a.contact_name)]);
    if (a.contact_org) contact.push(["Gliederung", esc(a.contact_org)]);
    if (a.contact_phone) contact.push(["Telefon", `<a href="tel:${esc(a.contact_phone.replace(/\s+/g, ""))}">${esc(a.contact_phone)}</a>`]);
    if (a.contact_email) contact.push(["E-Mail", `<a href="mailto:${esc(a.contact_email)}">${esc(a.contact_email)}</a>`]);
    if (a.contact_notes) contact.push(["Hinweise", esc(a.contact_notes)]);

    openPanel(a.title, `
      <div class="btn-row">
        <span class="cat ${esc(a.category)}">${CAT[a.category] || a.category}</span>
        ${a.photos.some((p) => p.lat != null) ? '<button class="btn ghost small" id="a-fit">Auf Karte zeigen</button>' : ""}
        ${a.can_edit ? '<button class="btn ghost small" id="a-edit">Bearbeiten</button>' : ""}
      </div>
      ${a.description ? `<h3>Beschreibung</h3><div style="white-space:pre-wrap">${esc(a.description)}</div>` : ""}
      <h3>Ansprechpartner</h3>
      ${contact.length ? `<dl class="contact">${contact.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`
                       : `<div class="muted small">Kein Ansprechpartner eingetragen.${a.can_edit ? " Über „Bearbeiten“ nachtragen." : ""}</div>`}
      <h3>Bilder (${a.photos.length})${a.unlocated_count ? ` <span class="badge">${a.unlocated_count} ohne Position</span>` : ""}</h3>
      ${a.can_edit ? `<div class="btn-row"><button class="btn small" id="a-upload">Bilder / Videos hochladen</button>
        ${a.unlocated_count ? '<button class="btn yellow small" id="a-locate">Bilder ohne Position lokalisieren</button>' : ""}</div>` : ""}
      ${a.photos.length ? `<div class="photo-grid">${a.photos.map((p, i) => `
        <button data-i="${i}" ${p.id === highlightId ? 'class="hi"' : ""} title="${esc(p.title || p.original_name)}">
          <img src="${p.thumb}" alt="${esc(p.title || p.original_name)}" loading="lazy">
          ${p.kind === "video" ? '<span class="play" aria-hidden="true">▶</span>' : ""}
          ${p.lat == null ? '<span class="badge nogeo" title="Keine Position">ohne Ort</span>' : ""}
          ${p.title ? `<span class="cap">${esc(p.title)}</span>` : ""}
        </button>`).join("")}</div>`
        : `<div class="empty"><strong>Noch keine Bilder</strong>${a.can_edit ? "Lade Bilder hoch – Geotags werden automatisch ausgelesen." : ""}</div>`}
      <div class="meta" style="margin-top:16px">Angelegt von ${esc(a.owner_name || "")}${a.owner_gliederung ? " (" + esc(a.owner_gliederung) + ")" : ""}, zuletzt geändert ${fmtDate(a.updated_at, true)}</div>
      ${a.can_edit ? '<div class="btn-row" style="margin-top:14px"><button class="btn danger small" id="a-delete">Album löschen</button></div>' : ""}
    `);
    panelBody.querySelectorAll(".photo-grid button").forEach((b) => b.addEventListener("click", () => openLightbox(+b.dataset.i)));
    const hi = panelBody.querySelector(".photo-grid .hi");
    if (hi) hi.scrollIntoView({ block: "center" });
    if (openBig && highlightId) { const idx = a.photos.findIndex((p) => p.id === highlightId); if (idx >= 0) openLightbox(idx); }
    const fit = $("#a-fit"); if (fit) fit.onclick = () => fitAlbum(a);
    const ed = $("#a-edit"); if (ed) ed.onclick = () => albumDialog(a);
    const up = $("#a-upload"); if (up) up.onclick = () => { fileInput.value = ""; fileInput.click(); };
    const lo = $("#a-locate"); if (lo) lo.onclick = () => startLocate(a.photos.filter((p) => p.lat == null));
    const del = $("#a-delete"); if (del) del.onclick = async () => {
      if (!(await S.confirm(`Album „${a.title}“ mit allen ${a.photos.length} Bildern endgültig löschen?`))) return;
      try { await api(`/api/albums/${a.id}`, { method: "DELETE" }); toast("Album gelöscht"); closePanel(); loadMap(); }
      catch (e) { toast(e.message, true); }
    };
  }

  /* --- Album anlegen / bearbeiten --------------------------------------- */
  function albumDialog(a) {
    a = a || { category: "seil" };
    const isNew = !a.id;
    dialog(`<h2>${isNew ? "Neues Album" : "Album bearbeiten"}</h2>
      <p class="help">Ein Album ist ein Übungsobjekt oder ein Übungsgewässer. Alle angemeldeten Nutzer können es sehen.</p>
      <label>Titel</label><input type="text" id="al-title" value="${esc(a.title)}" placeholder="z. B. Wehr Musterstadt, Brücke B12" required>
      <label>Art</label>
      <select id="al-cat">
        <option value="seil" ${a.category === "seil" ? "selected" : ""}>Übungsobjekt Seiltechnik</option>
        <option value="wasser" ${a.category === "wasser" ? "selected" : ""}>Übungsgewässer Strömungsrettung</option>
        <option value="sonstiges" ${a.category === "sonstiges" ? "selected" : ""}>Sonstiges</option>
      </select>
      <label>Allgemeine Infos</label>
      <textarea id="al-desc" placeholder="Zufahrt, Parken, Besonderheiten, Genehmigungen, Gefahren …">${esc(a.description)}</textarea>
      <h3 style="margin-top:18px">Ansprechpartner für das Objekt</h3>
      <div class="field-row">
        <div><label>Name</label><input type="text" id="al-cname" value="${esc(a.contact_name)}"></div>
        <div><label>Gliederung / Organisation</label><input type="text" id="al-corg" value="${esc(a.contact_org)}"></div>
        <div><label>Telefon</label><input type="tel" id="al-cphone" value="${esc(a.contact_phone)}"></div>
        <div><label>E-Mail</label><input type="email" id="al-cemail" value="${esc(a.contact_email)}"></div>
      </div>
      <label>Hinweise zur Kontaktaufnahme</label>
      <textarea id="al-cnotes" style="min-height:60px" placeholder="z. B. Übungen bitte 2 Wochen vorher anmelden">${esc(a.contact_notes)}</textarea>
      ${isNew ? '<label class="inline" style="margin-top:14px"><input type="checkbox" id="al-upload" checked> Danach direkt Bilder hochladen</label>' : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="al-save" type="button">${isNew ? "Album anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        body.querySelector("#al-save").onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;          // zweiter Klick, während die Anfrage läuft
          knopf.disabled = true;
          const d = {
            title: body.querySelector("#al-title").value, category: body.querySelector("#al-cat").value,
            description: body.querySelector("#al-desc").value, contact_name: body.querySelector("#al-cname").value,
            contact_org: body.querySelector("#al-corg").value, contact_phone: body.querySelector("#al-cphone").value,
            contact_email: body.querySelector("#al-cemail").value, contact_notes: body.querySelector("#al-cnotes").value,
          };
          try {
            const r = isNew ? await api("/api/albums", { method: "POST", body: d })
                            : await api(`/api/albums/${a.id}`, { method: "PUT", body: d });
            const wantUpload = isNew && body.querySelector("#al-upload").checked;
            dlg.close();
            toast(isNew ? "Album angelegt" : "Gespeichert");
            await openAlbum(r.album.id);
            if (wantUpload) {
              fileInput.value = "";
              // iOS öffnet den Dateidialog nur direkt aus einer Berührung – nach den Wartezeiten
              // hier ist die Geste verbraucht. Dann zeigt ein Hinweis auf den Knopf.
              if (window.matchMedia("(pointer: coarse)").matches) { const up = $("#a-upload"); if (up) up.focus(); toast("Jetzt über „Bilder / Videos hochladen“ Bilder hinzufügen."); }
              else fileInput.click();
            }
          } catch (e) { toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
      });
  }
  $("#btn-new-album").addEventListener("click", () => albumDialog());

  /* --- Upload ------------------------------------------------------------ */
  fileInput.addEventListener("change", () => {
    if (!state.album || !fileInput.files.length) return;
    uploadFiles(state.album.id, Array.from(fileInput.files));
  });

  /* Standbild aus einem Video ziehen (Canvas) – dient als Vorschau auf Karte und im Album */
  function posterFor(file) {
    return new Promise((resolve) => {
      const v = document.createElement("video");
      const url = URL.createObjectURL(file);
      let done = false;
      const finish = (blob) => { if (done) return; done = true; URL.revokeObjectURL(url); resolve(blob); };
      v.muted = true; v.playsInline = true; v.preload = "auto";
      v.onloadeddata = () => { try { v.currentTime = Math.min(1, (v.duration || 2) / 2); } catch (e) { finish(null); } };
      v.onseeked = () => {
        try {
          const c = document.createElement("canvas");
          const scale = Math.min(1, 1600 / Math.max(v.videoWidth, 1));
          c.width = Math.round(v.videoWidth * scale); c.height = Math.round(v.videoHeight * scale);
          c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
          c.toBlob((b) => finish(b), "image/jpeg", 0.85);
        } catch (e) { finish(null); }
      };
      v.onerror = () => finish(null);
      setTimeout(() => finish(null), 10000);
      v.src = url;
    });
  }
  const isVideo = (f) => /^video\//.test(f.type) || /\.(mp4|m4v|mov|webm)$/i.test(f.name);
  // „bis 0 GB“ half niemandem: unter einem Gigabyte in Megabyte, sonst mit einer Stelle.
  const groesse = (mb) => (mb >= 1024 ? `${(mb / 1024).toFixed(mb % 1024 ? 1 : 0).replace(".", ",")} GB` : `${mb} MB`);

  /* albumId: Ziel eines gewöhnlichen Hochladens. neu: {title, category} – dann entsteht aus den
     Dateien ein neues Album (Einwurf von der Karte), und der Server sagt dazu, ob in der Nähe
     schon eines liegt. */
  async function uploadFiles(albumId, files, neu) {
    // Erst das Fenster zeigen, dann die Standbilder ziehen: bei mehreren Videos dauert das
    // spürbar lange, und ohne Rückmeldung sähe die Seite so lange aus wie eingefroren.
    const dlg = dialog(`<h2>${neu ? `Neues Album „${esc(neu.title)}“` : "Dateien hochladen"}</h2>
      <p id="up-step">${files.length} ${files.length === 1 ? "Datei" : "Dateien"} werden vorbereitet …</p>
      <progress id="up-prog" max="100" value="0"></progress>
      <ul class="upload-list">${files.map((f) => `<li><span>${esc(f.name)}</span><span class="muted">${(f.size / 1048576).toFixed(1)} MB</span></li>`).join("")}</ul>
      <div class="help">Bilder und Videos (MP4, MOV, WebM) bis ${groesse(STROEMIS.maxUploadMb)} je Hochladevorgang. Geotags aus den EXIF-Daten werden automatisch ausgelesen. Bilder ohne Position kannst du gleich im Anschluss auf der Karte setzen.</div>
      <div class="dlg-actions"><button class="btn secondary" id="up-abbruch" type="button">Abbrechen</button></div>`);
    const prog = dlg.querySelector("#up-prog");
    // Escape darf den Dialog nicht wegdrücken: Der Upload liefe unsichtbar weiter und schlösse am
    // Ende, was inzwischen im selben Dialog geöffnet wurde. Abbrechen heißt abbrechen.
    const festhalten = (e) => e.preventDefault();
    dlg.addEventListener("cancel", festhalten);
    let xhr = null, abgebrochen = false;
    const loslassen = () => { dlg.removeEventListener("cancel", festhalten); if (dlg.querySelector("#up-prog") === prog) dlg.close(); };
    dlg.querySelector("#up-abbruch").onclick = () => { abgebrochen = true; if (xhr) xhr.abort(); else loslassen(); };
    const step = dlg.querySelector("#up-step");
    const videos = files.filter(isVideo).length;
    const posters = [];
    let done = 0;
    for (const f of files) {
      if (isVideo(f)) {
        step.textContent = `Vorschaubild ${++done} von ${videos} wird erzeugt …`;
        posters.push(await posterFor(f));
      } else {
        posters.push(null);
      }
    }
    if (abgebrochen) return;
    step.textContent = `${files.length} ${files.length === 1 ? "Datei" : "Dateien"} werden hochgeladen und verarbeitet …`;
    const fd = new FormData();
    files.forEach((f, i) => { fd.append("files", f); fd.append("posters", posters[i] || new Blob(), posters[i] ? "poster.jpg" : ""); });
    if (neu) { fd.append("title", neu.title); fd.append("category", neu.category); }
    xhr = new XMLHttpRequest();
    xhr.onabort = () => { loslassen(); toast("Hochladen abgebrochen"); };
    xhr.open("POST", neu ? "/api/albums/einwurf" : `/api/albums/${albumId}/photos`);
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) prog.value = Math.round((e.loaded / e.total) * 100); };
    xhr.onload = async () => {
      let d = {};
      try { d = JSON.parse(xhr.responseText); } catch (e) { /* leer */ }
      loslassen();
      if (xhr.status === 401) { location.href = "/login"; return; }
      if (xhr.status >= 400) return toast(d.error || "Hochladen fehlgeschlagen", true);
      if (d.errors && d.errors.length) toast(d.errors.join(" "), true);
      else toast(`${d.photos.length} ${d.photos.length === 1 ? "Bild" : "Bilder"} hochgeladen`);
      await loadMap();
      if (neu) {
        albumId = d.album.id;
        // Liegt in der Nähe schon ein Album, das man selbst führt, gehören die Bilder womöglich
        // dorthin. Die Frage kommt erst jetzt: Vorher kannte niemand die Geotags.
        if (d.nahe.some((n) => n.can_edit)) albumId = await naheFrage(d);
        // Nach dem Zusammenlegen tragen die Bilder das Zielalbum – das Lokalisieren unten
        // kehrt am Ende dorthin zurück, nicht in das aufgelöste Album.
        d.photos.forEach((p) => { p.album_id = albumId; });
      }
      await openAlbum(albumId);
      if (d.unlocated.length) {
        const unl = d.photos.filter((p) => d.unlocated.includes(p.id));
        dialog(`<h2>${unl.length === 1 ? "Ein Bild ohne Geotag" : unl.length + " Bilder ohne Geotag"}</h2>
          <p>${unl.length === 1 ? "Dieses Bild enthält" : "Diese Bilder enthalten"} keine Positionsdaten. Möchtest du ${unl.length === 1 ? "es" : "sie"} jetzt auf der Karte platzieren?</p>
          <div class="photo-grid">${unl.map((p) => `<button type="button" disabled><img src="${p.thumb}" alt=""></button>`).join("")}</div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Später</button><button class="btn yellow" id="loc-start" type="button">Jetzt auf der Karte platzieren</button></div>`,
          (dl2, body) => { body.querySelector("#loc-start").onclick = () => { dl2.close(); startLocate(unl); }; });
      }
    };
    xhr.onerror = () => { dlg.close(); toast("Upload fehlgeschlagen – Verbindung unterbrochen.", true); };
    xhr.send(fd);
  }

  /* --- Einwurf: Dateien auf die Karte ziehen ------------------------------ */
  /* Was der Browser hier annimmt, entscheidet dieselbe Liste wie beim Dateidialog (accept
     des versteckten Eingabefelds) – nur eben am Dateinamen, denn eine gezogene HEIC-Datei
     kommt ohne brauchbaren MIME-Typ an. */
  const ANNEHMBAR = /\.(jpe?g|png|gif|webp|tiff?|bmp|heic|heif|avif|mp4|m4v|mov|webm)$/i;
  const ablage = (dateien) => Array.from(dateien).filter((f) => ANNEHMBAR.test(f.name) || /^(image|video)\//.test(f.type));
  const abstandText = (m) => (m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1).replace(".", ",")} km`);

  function einwurfDialog(files) {
    dialog(`<h2>Neues Album aus ${files.length} ${files.length === 1 ? "Datei" : "Dateien"}</h2>
      <p class="help">Die Dateien werden hochgeladen und als neues Album abgelegt. Liegt in der Nähe
        (2 km) schon ein Album von dir, fragt die Anwendung danach, ob die Bilder dorthin gehören.</p>
      <ul class="upload-list">${files.map((f) => `<li><span>${esc(f.name)}</span><span class="muted">${(f.size / 1048576).toFixed(1)} MB</span></li>`).join("")}</ul>
      <label>Titel</label><input type="text" id="ew-title" placeholder="z. B. Wehr Musterstadt, Brücke B12" required>
      <label>Art</label>
      <select id="ew-cat">
        <option value="seil">Übungsobjekt Seiltechnik</option>
        <option value="wasser">Übungsgewässer Strömungsrettung</option>
        <option value="sonstiges">Sonstiges</option>
      </select>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ew-go" type="button">Album anlegen und hochladen</button></div>`,
      (dlg, body) => {
        const titel = body.querySelector("#ew-title");
        titel.focus();
        const los = () => {
          const title = titel.value.trim();
          if (!title) { titel.focus(); return toast("Bitte einen Titel für das Album angeben.", true); }
          const category = body.querySelector("#ew-cat").value;
          dlg.close();
          uploadFiles(null, files, { title, category });
        };
        body.querySelector("#ew-go").onclick = los;
        titel.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); los(); } });
      });
  }

  /* Liefert die Kennung des Albums, in dem die Bilder am Ende liegen: das Zielalbum nach dem
     Zusammenlegen – oder das neue, wenn es dabei bleibt (auch bei Escape: Nichts zu tun ist
     der sichere Ausgang, das neue Album steht ja schon). */
  function naheFrage(d) {
    const eigene = d.nahe.filter((n) => n.can_edit), fremde = d.nahe.filter((n) => !n.can_edit);
    const n = d.photos.length;
    return new Promise((resolve) => {
      let ergebnis = null;                          // gesetzt, sobald zusammengelegt wurde
      const dlg = dialog(`<h2>In der Nähe liegt schon ein Album</h2>
        <p>${n === 1 ? "Das Bild liegt" : "Die Bilder liegen"} nach ${n === 1 ? "seinem" : "ihrem"} Geotag nahe an
          ${eigene.length === 1 ? "einem Album, das du führst" : "Alben, die du führst"}.
          ${n === 1 ? "Gehört es" : "Gehören sie"} dorthin?</p>
        <ul class="nahe-liste">${eigene.map((a) => `<li><button type="button" class="btn secondary" data-ziel="${a.id}">
            Zu „${esc(a.title)}“ hinzufügen</button>
            <span class="muted small">${abstandText(a.abstand_m)} entfernt · ${a.photo_count} ${a.photo_count === 1 ? "Bild" : "Bilder"}</span></li>`).join("")}</ul>
        ${fremde.length ? `<p class="help">Ebenfalls in der Nähe, aber nicht von dir zu bearbeiten: ${fremde.map((a) =>
          `„${esc(a.title)}“ (${abstandText(a.abstand_m)}, von ${esc(a.owner_name || "")})`).join(", ")}.</p>` : ""}
        <div class="dlg-actions"><button class="btn" id="nahe-neu" type="button">Als eigenes Album „${esc(d.album.title)}“ behalten</button></div>`,
        (dl, body) => {
          body.querySelector("#nahe-neu").onclick = () => dl.close();
          body.querySelectorAll("[data-ziel]").forEach((b) => b.onclick = async () => {
            if (b.disabled) return;
            b.disabled = true;
            try {
              const r = await api(`/api/albums/${d.album.id}/zusammenlegen`, { method: "POST", body: { ziel: +b.dataset.ziel } });
              ergebnis = r.album.id;
              toast(`${n} ${n === 1 ? "Bild" : "Bilder"} zu „${r.album.title}“ hinzugefügt`);
              await loadMap();
              dl.close();
            } catch (e) { b.disabled = false; toast(e.message, true); }
          });
        });
      // Das Schließen entscheidet – gleich ob per Knopf, Zusammenlegen oder Escape.
      dlg.addEventListener("close", () => resolve(ergebnis || d.album.id), { once: true });
    });
  }

  /* Die Ablagefläche: Dateien über der Karte ergeben ein neues Album; über der Seitenleiste
     mit einem Album, das man selbst führt, kommen sie dorthin. Gezählt wird das Betreten und
     Verlassen, weil jedes Kind der Fläche beide Ereignisse noch einmal auslöst – sonst
     flackerte die Kennzeichnung bei jeder Bewegung. */
  const schale = $(".map-shell");
  let ziehTiefe = 0;
  const hatDateien = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
  const ueberAlbum = (e) => !!(state.album && state.album.can_edit && panel.classList.contains("open") && panel.contains(e.target));
  const ablageZeigen = (e) => {
    const zuAlbum = ueberAlbum(e);
    schale.classList.add("drop-aktiv");
    schale.dataset.drop = zuAlbum ? `Loslassen: zu „${state.album.title}“ hinzufügen` : "Loslassen: neues Album aus den Dateien";
    panel.classList.toggle("drop-ziel", zuAlbum);
  };
  const ablageWeg = () => { ziehTiefe = 0; schale.classList.remove("drop-aktiv"); panel.classList.remove("drop-ziel"); };
  schale.addEventListener("dragenter", (e) => { if (!hatDateien(e)) return; e.preventDefault(); ziehTiefe++; ablageZeigen(e); });
  schale.addEventListener("dragover", (e) => { if (!hatDateien(e)) return; e.preventDefault(); e.dataTransfer.dropEffect = "copy"; ablageZeigen(e); });
  schale.addEventListener("dragleave", (e) => { if (!hatDateien(e)) return; if (--ziehTiefe <= 0) ablageWeg(); });
  schale.addEventListener("drop", (e) => {
    if (!hatDateien(e)) return;
    e.preventDefault();
    const zuAlbum = ueberAlbum(e);
    ablageWeg();
    if (state.locating) return toast("Erst die Position setzen oder abbrechen – dann Dateien ablegen.", true);
    const files = ablage(e.dataTransfer.files);
    if (!files.length) return toast("Darunter war kein Bild und kein Video.", true);
    if (zuAlbum) uploadFiles(state.album.id, files);
    else einwurfDialog(files);
  });
  // Ein Bild, das neben der Fläche landet, öffnete der Browser sonst als Seite – die Karte wäre weg.
  document.addEventListener("dragover", (e) => { if (hatDateien(e)) e.preventDefault(); });
  document.addEventListener("drop", (e) => { if (hatDateien(e)) e.preventDefault(); });

  /* --- Lokalisieren ------------------------------------------------------- */
  const banner = $("#locate-banner");

  function startLocate(photos) {
    if (!photos.length) return;
    state.locateQueue = photos.slice();
    panel.classList.remove("open");
    $("#map").classList.add("locating");
    nextLocate();
  }

  function nextLocate() {
    clearTemp();
    const p = state.locateQueue.shift();
    if (!p) return finishLocate();
    state.locating = p;
    const albumPos = !!state.letztePos || (state.album && state.album.lat != null);
    const rest = state.locateQueue.length;
    banner.classList.remove("hidden");
    banner.innerHTML = `<img src="${p.thumb}" alt="">
      <div><strong>Auf die Karte tippen, um die Position zu setzen</strong>
        <span class="small">${esc(p.title || p.original_name)}${rest ? ` · danach noch ${rest}` : ""}</span></div>
      <form class="loc-suche" id="loc-form">
        <input type="search" id="loc-q" placeholder="Adresse oder Ort" aria-label="Adresse oder Ort suchen"
               autocomplete="off" enterkeyhint="search">
        <button class="btn secondary small" type="submit">Suchen</button>
      </form>
      <div class="btn-row">
        ${albumPos ? '<button class="btn secondary small" id="loc-album">Album-Position übernehmen</button>' : ""}
        <button class="btn secondary small" id="loc-me">Mein Standort</button>
        <button class="btn secondary small" id="loc-skip">Überspringen</button>
        <button class="btn ghost small" id="loc-cancel">Abbrechen</button>
      </div>
      <ul class="loc-treffer hidden" id="loc-treffer"></ul>`;
    /* Adresssuche: Sie fährt die Karte nur an die Stelle – gesetzt wird die Position weiterhin
       mit einem Tippen. Eine Hausnummer ist selten der Ort, an dem das Bild entstand. */
    const treffer = $("#loc-treffer");
    $("#loc-form").onsubmit = async (e) => {
      e.preventDefault();
      const frage = $("#loc-q").value.trim();
      if (frage.length < 3) return;
      treffer.classList.remove("hidden");
      treffer.innerHTML = '<li class="muted">wird gesucht …</li>';
      try {
        const d = await api(`/api/geocode?q=${encodeURIComponent(frage)}`);
        if (!d.results.length) return (treffer.innerHTML = '<li class="muted">Nichts gefunden.</li>');
        treffer.innerHTML = d.results.map((t, i) => `<li><button type="button" data-i="${i}">${esc(t.name)}</button></li>`).join("");
        treffer.querySelectorAll("button").forEach((b) => b.onclick = () => {
          const t = d.results[+b.dataset.i];
          state.map.setView([t.lat, t.lon], Math.max(state.map.getZoom(), 17));
          treffer.classList.add("hidden");
        });
      } catch (err) {
        treffer.innerHTML = `<li class="muted">${esc(err.message)}</li>`;
      }
    };
    if (albumPos) $("#loc-album").onclick = () => setLocation(p, state.album.lat, state.album.lon);
    $("#loc-me").onclick = () => state.map.locate({ setView: true, maxZoom: 17, enableHighAccuracy: true });
    $("#loc-skip").onclick = nextLocate;
    $("#loc-cancel").onclick = () => { state.locateQueue = []; finishLocate(); };
    if (albumPos && !state.map.getBounds().contains([state.album.lat, state.album.lon])) {
      state.map.setView([state.album.lat, state.album.lon], Math.max(state.map.getZoom(), 15));
    }
  }

  function clearTemp() {
    if (state.tempMarker) { state.map.removeLayer(state.tempMarker); state.tempMarker = null; }
  }

  async function finishLocate() {
    const albumId = state.locating && state.locating.album_id;
    state.locating = null;
    clearTemp();
    banner.classList.add("hidden");
    $("#map").classList.remove("locating");
    await loadMap();
    if (albumId) openAlbum(albumId);
  }

  function onMapClick(e) {
    if (!state.locating) return;
    const p = state.locating;
    clearTemp();
    state.tempMarker = L.marker(e.latlng, {
      icon: L.divIcon({ className: "thumb-marker", html: `<div class="tm temp" style="background-image:url('${p.thumb}')"></div>`, iconSize: [64, 64], iconAnchor: [32, 32] }),
    }).addTo(state.map);
    banner.querySelector("strong").textContent = `Position: ${fmtCoord(e.latlng.lat, e.latlng.lng)}`;
    let ok = banner.querySelector("#loc-ok");
    if (!ok) {
      ok = document.createElement("button");
      ok.id = "loc-ok"; ok.className = "btn small"; ok.textContent = "Position speichern";
      banner.querySelector(".btn-row").prepend(ok);
    }
    ok.onclick = () => setLocation(p, e.latlng.lat, e.latlng.lng);
  }

  async function setLocation(p, lat, lon) {
    try {
      await api(`/api/photos/${p.id}`, { method: "PUT", body: { lat, lon } });
      // Ab jetzt gibt es eine Albumposition – auch wenn das Album beim Öffnen noch keine hatte.
      state.letztePos = [lat, lon];
      toast("Position gespeichert");
      nextLocate();
    } catch (e) { toast(e.message, true); }
  }

  /* --- Bild-Detail ------------------------------------------------------- */
  const lb = $("#lightbox"), lbBody = $("#lb-body");

  function openLightbox(i) {
    state.lbIndex = i;
    renderLightbox();
    if (!lb.open) lb.showModal();
  }

  function renderLightbox(editing) {
    const a = state.album;
    const p = a.photos[state.lbIndex];
    if (!p) return lb.close();
    const canEdit = a.can_edit || isAdmin || p.owner_id === me.id;
    const kv = [];
    if (p.taken_at) kv.push(["Aufgenommen", esc(fmtDate(p.taken_at, true))]);
    kv.push(["Position", p.lat != null ? `<a href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=18/${p.lat}/${p.lon}" target="_blank" rel="noopener">${fmtCoord(p.lat, p.lon)}</a> <span class="muted">(${p.geo_source === "exif" ? "aus Bild" : "manuell"})</span>` : '<span class="badge">keine Position</span>']);
    if (p.altitude != null) kv.push(["Höhe ü. NN", `${Math.round(p.altitude)} m`]);
    if (p.height_m != null) kv.push(["Objekthöhe", `${String(p.height_m).replace(".", ",")} m`]);
    if (p.kind === "video") kv.push(["Video", `${esc(p.original_name)} – <a href="${p.orig}" target="_blank" rel="noopener">herunterladen</a>`]);
    else if (p.width) kv.push(["Original", `${p.width} × ${p.height} px – <a href="${p.orig}" target="_blank" rel="noopener">herunterladen</a>`]);

    const view = `
      <h2>${esc(p.title || p.original_name)}</h2>
      <div class="meta">Bild ${state.lbIndex + 1} von ${a.photos.length} · ${esc(a.title)}</div>
      ${p.note ? `<div class="note-box">${esc(p.note)}</div>` : ""}
      <dl class="kv">${kv.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      ${p.details ? `<h3 class="small muted">Weitere Infos</h3><div style="white-space:pre-wrap;font-size:.92rem">${esc(p.details)}</div>` : ""}
      <div class="lb-aktionen">
        <div class="btn-row">
          ${canEdit ? '<button class="btn small" id="lb-edit">Bearbeiten</button>' : ""}
          ${canEdit ? `<button class="btn secondary small" id="lb-loc">${p.lat != null ? "Position ändern" : "Auf Karte platzieren"}</button>` : ""}
          ${p.lat != null ? '<button class="btn secondary small" id="lb-fit">Auf Karte zeigen</button>' : ""}
          ${canEdit && a.can_edit ? `<button class="btn secondary small" id="lb-cover"${a.cover_photo_id === p.id ? " disabled" : ""}>${
            a.cover_photo_id === p.id ? "Ist das Deckblatt" : "Als Deckblatt"}</button>` : ""}
        </div>
        ${canEdit ? '<div class="btn-row lb-aktionen-weg"><button class="btn danger small" id="lb-del">Löschen</button></div>' : ""}
      </div>`;

    const form = `
      <h2>Bild bearbeiten</h2>
      <label>Titel</label><input type="text" id="p-title" value="${esc(p.title)}" placeholder="z. B. Ankerpunkt Nordseite">
      <label>Notiz</label><textarea id="p-note" placeholder="Was ist hier zu sehen, worauf ist zu achten?">${esc(p.note)}</textarea>
      <div class="field-row">
        <div><label>Objekthöhe (m)</label><input type="text" id="p-height" inputmode="decimal" value="${p.height_m ?? ""}"></div>
        <div><label>Höhe ü. NN (m)</label><input type="text" id="p-alt" inputmode="decimal" value="${p.altitude != null ? Math.round(p.altitude * 10) / 10 : ""}"></div>
        <div><label>Breite (°)</label><input type="text" id="p-lat" inputmode="decimal" value="${p.lat ?? ""}"></div>
        <div><label>Länge (°)</label><input type="text" id="p-lon" inputmode="decimal" value="${p.lon ?? ""}"></div>
      </div>
      <label>Aufnahmezeit</label><input type="datetime-local" id="p-taken" value="${p.taken_at ? p.taken_at.slice(0, 16) : ""}">
      <label>Weitere Infos</label><textarea id="p-details" placeholder="Bruchlast, Zugang, Material, Genehmigung …">${esc(p.details)}</textarea>
      <div class="dlg-actions"><button class="btn secondary" id="p-cancel">Abbrechen</button><button class="btn" id="p-save">Speichern</button></div>`;

    lbBody.innerHTML = `
      <div class="lb-img">
        ${p.kind === "video" ? `<video controls playsinline preload="metadata" poster="${p.web}" src="${p.orig}"></video>` : `<img src="${p.web}" alt="${esc(p.title || p.original_name)}">`}
        ${a.photos.length > 1 ? '<button class="lb-nav prev" id="lb-prev" aria-label="Vorheriges">‹</button><button class="lb-nav next" id="lb-next" aria-label="Nächstes">›</button>' : ""}
      </div>
      <div class="lb-side"><button class="close" id="lb-close" aria-label="Schließen">×</button>${editing ? form : view}</div>`;
    // Das zuvor fokussierte Element (ein Pfeilknopf) ist mit dem Neuzeichnen verschwunden; ohne
    // Fokus im Dialog kämen die Pfeiltasten nicht mehr an – Blättern ginge nur einmal.
    lb.tabIndex = -1;
    if (!editing) lb.focus();
    lbBody.classList.toggle("editing", !!editing);   // Telefon: Bild weicht dem Formular (CSS)
    // Wischen blättert – Pfeiltasten gibt es auf dem Telefon nicht.
    const flaeche = lbBody.querySelector(".lb-img");
    let x0 = null;
    flaeche.addEventListener("touchstart", (e) => { if (e.target.tagName === "VIDEO") return; x0 = e.touches[0].clientX; }, { passive: true });
    flaeche.addEventListener("touchend", (e) => {
      if (x0 == null) return;
      const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) < 50 || editing) return;
      const ziel = $(dx < 0 ? "#lb-next" : "#lb-prev"); if (ziel) ziel.click();
    }, { passive: true });

    $("#lb-close").onclick = () => lb.close();
    const prev = $("#lb-prev"), next = $("#lb-next");
    if (prev) prev.onclick = () => { state.lbIndex = (state.lbIndex - 1 + a.photos.length) % a.photos.length; renderLightbox(); };
    if (next) next.onclick = () => { state.lbIndex = (state.lbIndex + 1) % a.photos.length; renderLightbox(); };

    if (editing) {
      $("#p-cancel").onclick = () => renderLightbox(false);
      $("#p-save").onclick = async () => {
        const g = (id) => lbBody.querySelector(id).value.trim();
        const body = {
          title: g("#p-title"), note: g("#p-note"), details: g("#p-details"), taken_at: g("#p-taken"),
          height_m: g("#p-height") || null, altitude: g("#p-alt") || null,
        };
        const lat = g("#p-lat").replace(",", "."), lon = g("#p-lon").replace(",", ".");
        if (lat || lon) { body.lat = lat; body.lon = lon; } else { body.lat = null; body.lon = null; }
        try {
          const r = await api(`/api/photos/${p.id}`, { method: "PUT", body });
          a.photos[state.lbIndex] = Object.assign({}, p, r.photo);
          toast("Gespeichert");
          renderLightbox(false);
          loadMap();
        } catch (e) { toast(e.message, true); }
      };
      return;
    }

    const fit = $("#lb-fit"); if (fit) fit.onclick = () => {
      state.leiseSchliessen = true;
      lb.close();
      // Auf dem Telefon deckt die Seitenleiste die Karte fast ganz ab – dann muss sie weichen.
      if (window.matchMedia("(max-width: 640px)").matches) panel.classList.remove("open");
      state.map.setView([p.lat, p.lon], Math.max(state.map.getZoom(), 17));
      flash(p.id);
    };
    const ed = $("#lb-edit"); if (ed) ed.onclick = () => renderLightbox(true);
    const loc = $("#lb-loc"); if (loc) loc.onclick = () => { state.leiseSchliessen = true; lb.close(); startLocate([p]); };
    const cov = $("#lb-cover"); if (cov) cov.onclick = async () => {
      try {
        await api(`/api/albums/${a.id}/cover`, { method: "PUT", body: { photo_id: p.id } });
        a.cover_photo_id = p.id;
        toast("Deckblatt festgelegt");
        renderLightbox();
        // Die Karte zeigt das Deckblatt im Bilderstapel eines Haufens – dafür neu einlesen.
        await loadMap();
      } catch (e) { toast(e.message, true); }
    };
    const del = $("#lb-del"); if (del) del.onclick = async () => {
      if (!(await S.confirm(`Bild „${p.title || p.original_name}“ endgültig löschen?`))) return;
      try {
        await api(`/api/photos/${p.id}`, { method: "DELETE" });
        toast("Bild gelöscht");
        lb.close();
        await loadMap();
        openAlbum(a.id);
      } catch (e) { toast(e.message, true); }
    };
  }

  lb.addEventListener("keydown", (e) => {
    // Im Formular bewegen die Pfeiltasten den Cursor, im Videoplayer spulen sie – dort darf
    // kein Bildwechsel dazwischenfahren, der das Formular samt Eingaben wegzeichnet.
    const t = e.target;
    if ((t && /^(INPUT|TEXTAREA|SELECT|VIDEO)$/.test(t.tagName)) || lbBody.querySelector("#p-save")) return;
    if (e.key === "ArrowLeft") { const b = $("#lb-prev"); if (b) b.click(); }
    if (e.key === "ArrowRight") { const b = $("#lb-next"); if (b) b.click(); }
  });
  lb.addEventListener("click", (e) => { if (e.target === lb) lb.close(); });
  // Nach dem Schließen zeigt die Seitenleiste das Album wieder – außer der Leuchtkasten ging
  // zu, um den Blick auf die Karte freizugeben (Position setzen, „Auf Karte zeigen“).
  lb.addEventListener("close", () => {
    const leise = state.leiseSchliessen;
    state.leiseSchliessen = false;
    if (state.album && !state.locating && !leise) openAlbum(state.album.id);
  });

  function flash(photoId) {
    const m = state.markers.get(photoId);
    if (!m) return;
    const el = m.getElement && m.getElement();
    if (el) { el.classList.add("hi"); setTimeout(() => el.classList.remove("hi"), 2500); }
  }

  /* --- Start ------------------------------------------------------------- */
  initMap();
  loadMap().then(() => {
    const m = location.hash.match(/^#album=(\d+)/);
    if (m) openAlbum(+m[1]);
    else if (!state.photos.length) showAlbums();
    else state.cluster.getBounds().isValid() && state.map.fitBounds(state.cluster.getBounds(), { padding: [40, 40], maxZoom: 14 });
  }).catch((e) => toast(e.message, true));
})();
