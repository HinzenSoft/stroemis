/* Verwaltung – Abschnitt „Globale Suchen (Modul Material)“: das Protokoll der Blicke über den eigenen Bereich hinaus
   (globale Seriennummernsuche, QR-Steckbrief eines fremden Artikels, fremde Dublette beim Anlegen), neueste zuerst,
   je Seite 50 Zeilen. Geladen wird erst beim Aufklappen – der Abschnitt ist selten gebraucht. Was älter als zwölf
   Monate ist, hat der Server beim Lesen schon gelöscht. Die Tabelle wird auf schmalen Bildschirmen zur Karte
   (table.list in app.css). */
(function () {
  const box = document.getElementById("mat-globalsuche");
  const ziel = document.getElementById("mat-globalsuche-liste");
  if (!box || !ziel) return;
  const ART = { suche: "Seriennummernsuche", qr: "QR-Steckbrief", dublette: "Dublette beim Anlegen" };
  let seite = 1;
  let geladen = false;

  function zeile(e) {
    const gl = e.gliederungen.length ? e.gliederungen.map(S.esc).join(", ") : '<span class="muted">–</span>';
    return `<tr><td data-l="Zeit">${S.esc(S.fmtDate(e.zeit, true))}</td><td data-l="Name">${S.esc(e.name || "–")}</td>
      <td data-l="Art">${S.esc(ART[e.art] || e.art)}</td><td data-l="Anfrage" class="mail">${S.esc(e.anfrage)}</td>
      <td data-l="Treffer">${e.treffer}</td><td data-l="Gliederungen">${gl}</td></tr>`;
  }

  async function laden() {
    ziel.innerHTML = '<p class="help">Wird geladen …</p>';
    let d;
    try { d = await S.api(`/api/material/globalsuche/protokoll?seite=${seite}`); }
    catch (e) { ziel.innerHTML = `<p class="notice">${S.esc(e.message)}</p>`; return; }
    geladen = true;
    if (!d.gesamt) { ziel.innerHTML = '<p class="muted">Keine globalen Suchen in den letzten zwölf Monaten.</p>'; return; }
    const seiten = Math.max(1, Math.ceil(d.gesamt / d.pro_seite));
    ziel.innerHTML = `<table class="list">
        <colgroup><col style="width:15%"><col style="width:17%"><col style="width:15%"><col style="width:21%"><col style="width:8%"><col style="width:24%"></colgroup>
        <thead><tr><th>Zeit</th><th>Name</th><th>Art</th><th>Anfrage</th><th>Treffer</th><th>Gliederungen</th></tr></thead>
        <tbody>${d.eintraege.map(zeile).join("")}</tbody></table>
      <div class="btn-row" style="margin-top:10px">
        <button class="btn secondary small" type="button" data-seite="${d.seite - 1}"${d.seite <= 1 ? " disabled" : ""}>Neuere</button>
        <span class="small muted">Seite ${d.seite} von ${seiten} · ${d.gesamt} ${d.gesamt === 1 ? "Eintrag" : "Einträge"}</span>
        <button class="btn secondary small" type="button" data-seite="${d.seite + 1}"${d.seite >= seiten ? " disabled" : ""}>Ältere</button>
      </div>`;
  }

  ziel.addEventListener("click", (e) => {
    const b = e.target.closest("[data-seite]");
    if (!b || b.disabled) return;
    seite = Math.max(1, +b.dataset.seite);
    laden();
  });
  box.addEventListener("toggle", () => { if (box.open && !geladen) laden(); });
})();
