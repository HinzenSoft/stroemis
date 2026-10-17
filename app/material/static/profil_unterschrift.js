/* Profil, Abschnitt „Unterschrift“: die eigene Unterschrift für das Modul Material zeichnen, ersetzen oder
   entfernen. Beim Festschreiben einer Prüfung oder Aussonderung wird eine Kopie ins Protokoll übernommen;
   eine spätere Änderung wirkt nur auf künftige Protokolle. */
(function () {
  "use strict";
  const vorschau = document.getElementById("us-vorschau");
  if (!vorschau) return;
  const zeichnenKnopf = document.getElementById("us-zeichnen");
  const weg = document.getElementById("us-weg");
  const API = "/api/material/unterschrift";
  let bild = null;

  function zeige(url) {
    bild = url || null;
    vorschau.innerHTML = bild ? `<img src="${S.esc(bild)}" alt="Deine hinterlegte Unterschrift">`
      : '<span class="muted">Noch keine Unterschrift hinterlegt.</span>';
    vorschau.classList.toggle("leer", !bild);
    zeichnenKnopf.textContent = bild ? "Neu unterschreiben" : "Unterschreiben";
    zeichnenKnopf.disabled = false;
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
      zeichnenKnopf.focus({ preventScroll: true });     // „Entfernen“ ist jetzt ausgeblendet
      S.toast("Unterschrift entfernt");
    }
    catch (e) { S.toast(e.message, true); }
  });

  S.api(API).then((r) => zeige(r.unterschrift)).catch((e) => {
    vorschau.innerHTML = `<span class="error">${S.esc(e.message)}</span>`;
  });
})();
