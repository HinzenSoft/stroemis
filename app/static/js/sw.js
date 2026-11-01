/* Service Worker von strömis.de (Wunsch vom 28.10.2026, Punkt 1; Entscheidung vom 01.11.2026: ohne Netz nur eine
   Hinweisseite). Ausgeliefert unter /sw.js (app/pwa.py) mit Versionsstempel in STAND – gilt für den ganzen Ursprung „/“.

   Er tut genau zweierlei: Er macht die Seite installierbar, und er zeigt die Hinweisseite /offline, wenn eine Seite
   nicht geladen werden kann. Zwischengespeichert wird NUR diese Seite (sie hat keine weiteren Mittel) – keine Seite,
   keine Antwort der Schnittstelle, kein Bild, nichts Angemeldetes. Jede Seite kommt wie ohne Worker frisch vom Server;
   Fehlerseiten (403, 404, 500 …) kommen unverändert durch, nur ein ausbleibendes Netz ersetzt die Seite.

   Gar nicht angefasst (der Browser lädt wie ohne Worker): alles außer dem Aufruf einer Seite (Skripte, Bilder, fetch),
   alles außer GET (Formulare, Uploads), die Schnittstelle /api/…, Medien /media/…, /static/…, die QR-Adressen /m/…
   und Dateien zum Herunterladen oder Ansehen (Adressen mit Dateiendung wie …/lebenslauf.pdf, …/protokolle.zip,
   …/export/12.csv, dazu …/pdf und …/sammelprotokoll der Materialablage). */
/* global clients */
"use strict";

const STAND = "entwicklung";              // app/pwa.py ersetzt diese Zeile beim Ausliefern durch die Prüfsumme
const SPEICHER = "stroemis-offline-";      // Name des einzigen Zwischenspeichers, mit Stand dahinter
const OFFLINE = "/offline";

self.addEventListener("install", (e) => {
  // Die Hinweisseite frisch vom Server (cache: "reload" umgeht den HTTP-Zwischenspeicher) in den Speicher dieses Stands.
  e.waitUntil(caches.open(SPEICHER + STAND)
    .then((c) => c.add(new Request(OFFLINE, { cache: "reload", credentials: "omit" })))
    .then(() => self.skipWaiting()));
  /* skipWaiting: Der neue Worker übernimmt sofort, ohne dass erst alle Fenster geschlossen sein müssen. Unbedenklich,
     weil er keine Seiten oder Dateien aus einem Speicher liefert – eine offene Seite des alten Stands lädt alles weiter
     vom Server; nur die Hinweisseite wechselt auf den neuen Stand. */
});

self.addEventListener("activate", (e) => {
  // Alte Stände wegräumen, dann die offenen Fenster übernehmen (sonst griff der Worker erst ab dem nächsten Laden).
  e.waitUntil(caches.keys()
    .then((namen) => Promise.all(namen.filter((n) => n.startsWith(SPEICHER) && n !== SPEICHER + STAND)
      .map((n) => caches.delete(n))))
    .then(() => clients.claim()));
});

// Seiten, die der Worker anfasst: nur der Aufruf einer Seite per GET, und nicht die oben genannten Bereiche.
function seite(req) {
  if (req.mode !== "navigate" || req.method !== "GET") return false;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return false;
  const p = url.pathname;
  if (/^\/(api|media|static|m)\//.test(p)) return false;
  if (/\.[A-Za-z0-9]{1,8}$/.test(p.slice(p.lastIndexOf("/") + 1))) return false;    // Datei: .pdf, .csv, .zip …
  if (/\/(pdf|sammelprotokoll)$/.test(p)) return false;                              // Protokolle der Materialablage
  return true;
}

self.addEventListener("fetch", (e) => {
  if (!seite(e.request)) return;
  e.respondWith(fetch(e.request).catch(async () => {
    // Kein Netz (fetch scheitert nur dann – eine Fehlerseite des Servers ist eine Antwort und geht oben durch).
    const hinweis = await caches.match(OFFLINE, { cacheName: SPEICHER + STAND });
    return hinweis || Response.error();
  }));
});
