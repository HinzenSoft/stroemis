(function () {
  const fp = document.getElementById("f-profile");
  fp.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await S.api("/api/me", { method: "PUT", body: {
        name: fp.querySelector("#name").value, gliederung: fp.querySelector("#gliederung").value,
        phone: fp.querySelector("#phone").value } });
      S.toast("Profil gespeichert");
      const u = document.querySelector(".nav .user");
      if (u) u.textContent = fp.querySelector("#name").value || STROEMIS.user.email;
    } catch (err) { S.toast(err.message, true); }
  });

  /* Profilbild. Der Dateiwähler bleibt verborgen und wird über den Knopf ausgelöst – ein
     nacktes <input type="file"> fällt sonst aus dem Formularbild der übrigen Seite. */
  const vorschau = document.getElementById("pb-vorschau");
  const datei = document.getElementById("pb-datei");
  const weg = document.getElementById("pb-weg");
  const waehlen = document.getElementById("pb-waehlen");
  waehlen.addEventListener("click", () => datei.click());
  /* Ein Bild vom Telefon hat mehrere Megabyte; über eine schmale Leitung dauert das Hochladen
     spürbar. Solange es läuft, sind beide Knöpfe gesperrt – sonst startet ein zweiter Klick
     einen zweiten Upload, und welcher davon zuletzt ankommt, ist Zufall. */
  let laeuft = false;

  /* Ein Foto aus der Galerie hat schnell zehn Megabyte und 48 Millionen Pixel – für ein Bild,
     das am Ende 256 Pixel breit ist. Der Browser rechnet es deshalb vorher herunter: Das spart
     die Übertragung, hält den Server aus der Schwerarbeit heraus und lässt die Aufnahmedaten
     (Ort, Zeit) gleich hier. Geht das Verkleinern nicht – ein HEIC, das dieser Browser nicht
     kennt –, wandert die Datei unverändert los; die Grenzen des Servers greifen dann. */
  const VOR_KANTE = 1024;
  async function kleinRechnen(f) {
    if (!window.createImageBitmap || !window.HTMLCanvasElement) return f;
    try {
      const bild = await createImageBitmap(f, { imageOrientation: "from-image" });
      const faktor = VOR_KANTE / Math.max(bild.width, bild.height);
      if (faktor >= 1) { bild.close(); return f; }
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(bild.width * faktor));
      c.height = Math.max(1, Math.round(bild.height * faktor));
      c.getContext("2d").drawImage(bild, 0, 0, c.width, c.height);
      bild.close();
      const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
      return blob && blob.size < f.size ? new File([blob], "profilbild.jpg", { type: "image/jpeg" }) : f;
    } catch (e) {
      return f;
    }
  }

  function zeige(url) {
    const kuerzel = vorschau.querySelector(".pb-kuerzel");
    let bild = vorschau.querySelector("img");
    if (url) {
      if (!bild) { bild = document.createElement("img"); bild.alt = ""; vorschau.prepend(bild); }
      bild.src = url;
      if (kuerzel) kuerzel.classList.add("hidden");
    } else {
      if (bild) bild.remove();
      if (kuerzel) kuerzel.classList.remove("hidden");
    }
    weg.classList.toggle("hidden", !url);
  }

  function sperren(an) {
    laeuft = an;
    waehlen.disabled = an;
    weg.disabled = an;
  }

  datei.addEventListener("change", async () => {
    const f = datei.files && datei.files[0];
    datei.value = "";                       // dieselbe Datei soll erneut wählbar bleiben
    if (!f || laeuft) return;
    sperren(true);
    S.toast("Profilbild wird hochgeladen …");
    try {
      const fd = new FormData();
      fd.append("file", await kleinRechnen(f));
      const r = await S.api("/api/me/avatar", { method: "POST", body: fd });
      // Der Dateiname wechselt bei jedem Hochladen, ein Zwischenspeicher kann also nicht stören.
      zeige(r.user.avatar);
      S.toast("Profilbild gespeichert");
    } catch (err) { S.toast(err.message, true); } finally { sperren(false); }
  });

  weg.addEventListener("click", async () => {
    if (laeuft) return;
    if (!(await S.confirm("Profilbild entfernen? Danach werden wieder die Initialen gezeigt.", "Entfernen"))) return;
    sperren(true);
    try {
      await S.api("/api/me/avatar", { method: "DELETE" });
      zeige("");
      S.toast("Profilbild entfernt");
    } catch (err) { S.toast(err.message, true); } finally { sperren(false); }
  });

  const fpw = document.getElementById("f-password");
  fpw.addEventListener("submit", async (e) => {
    e.preventDefault();
    const p1 = fpw.querySelector("#password").value, p2 = fpw.querySelector("#password2").value;
    if (p1 !== p2) return S.toast("Die neuen Passwörter stimmen nicht überein.", true);
    try {
      await S.api("/api/me/password", { method: "PUT", body: { current: fpw.querySelector("#current").value, password: p1 } });
      S.toast("Passwort geändert");
      fpw.reset();
    } catch (err) { S.toast(err.message, true); }
  });
})();
