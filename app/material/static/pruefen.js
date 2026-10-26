/* Prüfseite (/materialablage/pruefen): ein PDF hochladen, die Antwort der Schnittstelle zeigen. Öffentlich – deshalb nicht
   material.js, das ohne angemeldetes Konto nichts anzeigt. */
(function () {
  "use strict";
  const root = document.getElementById("pruefen");
  if (!root) return;
  const { esc, api, toast } = S;
  const form = document.getElementById("pr-form");
  const feld = document.getElementById("pr-datei");
  const ablage = document.getElementById("pr-ablage");
  const name = document.getElementById("pr-name");
  const los = document.getElementById("pr-los");
  const box = document.getElementById("pr-ergebnis");
  let datei = null;

  const TEXT = {
    unveraendert: ["ok", "Unverändert", "Die Datei ist genau das Protokoll, das strömis.de festgeschrieben hat."],
    veraendert: ["bad", "Verändert", "Die Datei weicht vom festgeschriebenen Protokoll ab."],
    unbekannt: ["neutral", "Kein Protokoll erkannt", ""],
  };

  const WAHL = "PDF-Datei hierher ziehen oder <u>auswählen</u>";
  function waehlen(f) {
    datei = f || null;
    name.innerHTML = datei ? `<strong>${esc(datei.name)}</strong><br><span class="small muted">Andere Datei hierher ziehen oder <u>auswählen</u></span>` : WAHL;
    los.disabled = !datei;
    box.hidden = true;
  }

  feld.addEventListener("change", () => waehlen(feld.files[0]));
  ["dragenter", "dragover"].forEach((t) => ablage.addEventListener(t, (e) => { e.preventDefault(); ablage.classList.add("ueber"); }));
  ["dragleave", "drop"].forEach((t) => ablage.addEventListener(t, () => ablage.classList.remove("ueber")));
  ablage.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer.files.length) waehlen(e.dataTransfer.files[0]); });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!datei) return;
    los.disabled = true;
    los.textContent = "Wird geprüft …";
    const fd = new FormData();
    fd.append("datei", datei, datei.name);
    try {
      const r = await api("/api/material/pruefen", { method: "POST", body: fd });
      const [klasse, titel, satz] = TEXT[r.ergebnis] || TEXT.unbekannt;
      box.className = "mat-pruefergebnis " + klasse;
      // Der Hinweis des Servers sagt genauer, was los ist; der eigene Satz springt nur ein, wenn er fehlt.
      box.innerHTML = `<strong>${esc(titel)}</strong>`
        + (r.protokoll_id ? `<p>${esc(r.art || "Protokoll")} <span class="mat-hash">${esc(r.protokoll_id)}</span></p>` : "")
        + ((r.hinweis || satz) ? `<p>${esc(r.hinweis || satz)}</p>` : "")
        + (r.link ? `<p><a href="${esc(r.link)}">Zum Vorgang in strömis.de</a></p>` : "");
      box.hidden = false;
    } catch (err) {
      // Auch im Ergebniskasten, nicht nur im Toast: Er bleibt stehen (etwa „zu viele Anfragen – bitte warten“).
      box.className = "mat-pruefergebnis fehler";
      box.innerHTML = `<strong>Nicht geprüft</strong><p>${esc(err.message)}</p>`;
      box.hidden = false;
      toast(err.message, true);
    } finally {
      los.disabled = !datei;
      los.textContent = "Prüfen";
    }
  });
})();
