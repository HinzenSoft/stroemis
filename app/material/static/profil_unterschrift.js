/* Profil, Abschnitt „Urkundennummer und Unterschrift“ (Modul Material).
   Urkundennummer: nur mit dem Häkchen „Prüfer“, das die Verwaltung setzt – eintragen, ändern oder leer entfernen; erst
   mit ihr darf der Prüfer prüfen, ohne sie steht ein Hinweis darüber.
   Unterschrift: zeichnen, ersetzen oder entfernen. Beim Festschreiben einer Prüfung oder Aussonderung wird eine Kopie
   ins Protokoll übernommen; eine spätere Änderung wirkt nur auf künftige Protokolle. Wer weder Prüfer noch Materialwart
   ist (data-setzen="0"), sieht nur eine alte Unterschrift und kann sie entfernen. */
(function () {
  "use strict";
  const urkundeForm = document.getElementById("f-urkunde");
  if (urkundeForm) {
    const feld = document.getElementById("urkundennummer");
    const hinweis = document.getElementById("ur-hinweis");
    const knopf = urkundeForm.querySelector("button[type=submit]");
    let gespeichert = feld.value.trim();
    urkundeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (knopf.disabled) return;
      const neu = feld.value.trim();
      if (!neu && gespeichert && !(await S.confirm("Deine Urkundennummer entfernen? Danach kannst du nicht mehr prüfen, bis du wieder eine einträgst. Festgeschriebene Protokolle behalten ihre Nummer.", "Entfernen"))) return;
      knopf.disabled = true;
      try {
        const r = await S.api("/api/material/urkundennummer", { method: "PUT", body: { urkundennummer: feld.value } });
        feld.value = gespeichert = r.urkundennummer;
        hinweis.classList.toggle("hidden", r.pruefen);
        S.toast(r.urkundennummer ? (r.pruefen ? "Urkundennummer gespeichert – du kannst prüfen" : "Urkundennummer gespeichert")
          : "Urkundennummer entfernt");
      } catch (err) { S.toast(err.message, true); feld.focus(); }
      finally { knopf.disabled = false; }
    });
  }

  const vorschau = document.getElementById("us-vorschau");
  if (!vorschau) return;
  const zeichnenKnopf = document.getElementById("us-zeichnen");
  const weg = document.getElementById("us-weg");
  const abschnitt = document.getElementById("unterschrift");
  const darfSetzen = !abschnitt || abschnitt.dataset.setzen !== "0";
  const API = "/api/material/unterschrift";
  let bild = null;

  function zeige(url) {
    bild = url || null;
    vorschau.innerHTML = bild ? `<img src="${S.esc(bild)}" alt="Deine hinterlegte Unterschrift">`
      : `<span class="muted">${darfSetzen ? "Noch keine Unterschrift hinterlegt." : "Keine Unterschrift hinterlegt."}</span>`;
    vorschau.classList.toggle("leer", !bild);
    zeichnenKnopf.textContent = bild ? "Neu unterschreiben" : "Unterschreiben";
    zeichnenKnopf.disabled = false;
    zeichnenKnopf.classList.toggle("hidden", !darfSetzen);
    weg.classList.toggle("hidden", !bild);
  }

  zeichnenKnopf.addEventListener("click", async () => {
    const neu = await MatUnterschrift.zeichnen({
      titel: bild ? "Neu unterschreiben" : "Unterschreiben",
      hinweis: "Unterschreibe so, wie du es auf Papier tust – mit Finger, Stift oder Maus. Die Unterschrift wird in jedes Protokoll übernommen, das du festschreibst.",
      bestehend: bild,
      speichern: async (b) => { zeige((await S.api(API, { method: "PUT", body: { bild: b } })).unterschrift); },
    });
    if (neu) S.toast("Unterschrift gespeichert");
  });

  weg.addEventListener("click", async () => {
    if (!(await S.confirm("Deine Unterschrift entfernen? Festgeschriebene Protokolle behalten ihre Kopie. Festschreiben und Aussondern gehen erst wieder, wenn du neu unterschrieben hast.", "Entfernen"))) return;
    try {
      await S.api(API, { method: "DELETE" });
      zeige(null);
      if (darfSetzen) zeichnenKnopf.focus({ preventScroll: true });     // „Entfernen“ ist jetzt ausgeblendet
      S.toast("Unterschrift entfernt");
    }
    catch (e) { S.toast(e.message, true); }
  });

  S.api(API).then((r) => zeige(r.unterschrift)).catch((e) => {
    vorschau.innerHTML = `<span class="error">${S.esc(e.message)}</span>`;
  });
})();
