/* Profil, Abschnitt „Meine PSA“ (Modul Material, Phase 3 · Lieferung 1): Erinnerungen zur eigenen PSA per Mail an oder
   aus (users.mat_psa_mails). Die Mail an die zugeordnete Person nach einer fremden Mangelmeldung hängt nicht daran – sie
   lässt sich nicht abbestellen (Text im Abschnitt). */
(function () {
  "use strict";
  const haken = document.getElementById("psa-mails");
  if (!haken) return;
  haken.addEventListener("change", async () => {
    const an = haken.checked;
    haken.disabled = true;
    try {
      const r = await S.api("/api/material/meine-psa/mails", { method: "PUT", body: { an } });
      haken.checked = r.an;
      S.toast("Gespeichert");
    } catch (err) {
      haken.checked = !an;
      S.toast(err.message, true);
    } finally {
      haken.disabled = false;
    }
  });
})();
