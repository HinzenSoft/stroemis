# strömis.de – ein Container: Flask/Gunicorn liefert API, Oberfläche und Bilder aus.
# Stufe 1 lädt die JavaScript-Bibliotheken mit festen Versionen, damit zur Laufzeit kein CDN nötig ist.
FROM python:3.12-slim AS vendor
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG LEAFLET=1.9.4
ARG MARKERCLUSTER=1.5.3
ARG MARKED=12.0.2
ARG DOMPURIFY=3.4.17
ARG TOASTUI=3.2.2
ARG SIGNATURE_PAD=5.1.4
# Prüfsumme der optionalen deutschen Sprachdatei (siehe unten – sie darf fehlen, der Rest nicht).
ARG DE_DE_SHA=a904840fa6f6e0983570e0aa258f7b0bddcc83133969a3e69df526c7cb905a8e
WORKDIR /vendor
COPY vendor.sha256 .
# Toast UI Editor kommt vom Hersteller-CDN: die -all-Bündel liegen nicht im npm-Paket (unpkg → 404).
# Jede Datei wird gegen vendor.sha256 geprüft: feste Versionsnummern allein bewahren nicht davor,
# dass ein Paketspiegel andere Inhalte ausliefert als erwartet.
RUN set -eux; \
    mkdir -p leaflet/images markercluster marked dompurify toastui signature_pad; \
    for f in leaflet.js leaflet.css; do curl -fsSL -o leaflet/$f "https://unpkg.com/leaflet@${LEAFLET}/dist/$f"; done; \
    for f in layers.png layers-2x.png marker-icon.png marker-icon-2x.png marker-shadow.png; do \
        curl -fsSL -o leaflet/images/$f "https://unpkg.com/leaflet@${LEAFLET}/dist/images/$f"; done; \
    for f in leaflet.markercluster.js MarkerCluster.css MarkerCluster.Default.css; do \
        curl -fsSL -o markercluster/$f "https://unpkg.com/leaflet.markercluster@${MARKERCLUSTER}/dist/$f"; done; \
    curl -fsSL -o marked/marked.min.js "https://unpkg.com/marked@${MARKED}/marked.min.js"; \
    curl -fsSL -o dompurify/purify.min.js "https://unpkg.com/dompurify@${DOMPURIFY}/dist/purify.min.js"; \
    # Signatur-Pad für die Unterschrift im Profil und die Unterschriftsfelder der Prüfformulare (Modul Material).
    curl -fsSL -o signature_pad/signature_pad.umd.min.js \
        "https://unpkg.com/signature_pad@${SIGNATURE_PAD}/dist/signature_pad.umd.min.js"; \
    curl -fsSL -o toastui/toastui-editor-all.min.js "https://uicdn.toast.com/editor/${TOASTUI}/toastui-editor-all.min.js"; \
    curl -fsSL -o toastui/toastui-editor.min.css "https://uicdn.toast.com/editor/${TOASTUI}/toastui-editor.min.css"; \
    # Zusammengefasste Tabellenzellen: Die Erweiterung liegt nur unter "latest"; festgehalten
    # wird sie über ihre Prüfsumme in vendor.sha256.
    for f in toastui-editor-plugin-table-merged-cell.min.js toastui-editor-plugin-table-merged-cell.min.css; do \
        curl -fsSL -o toastui/$f "https://uicdn.toast.com/editor-plugin-table-merged-cell/latest/$f"; done; \
    sha256sum -c vendor.sha256; \
    # Die deutsche Sprachdatei darf fehlen – dann läuft der Editor auf Englisch weiter.
    if curl -fsSL -o toastui/de-de.js "https://uicdn.toast.com/editor/${TOASTUI}/i18n/de-de.js"; then \
        echo "${DE_DE_SHA}  toastui/de-de.js" | sha256sum -c -; \
    else \
        echo "/* keine deutsche Sprachdatei gefunden – Editor läuft auf Englisch */" > toastui/de-de.js; \
    fi; \
    rm vendor.sha256

# Stufe 2 holt ffmpeg. Es wandelt hochgeladene Videos nach H.264/AAC und zieht das
# Vorschaubild aus einem Bild des Films; ohne das blieben Aufnahmen vom iPhone (.mov mit HEVC)
# in Chrome und Firefox stumm bei 0:00 stehen.
# Aus der Paketverwaltung kostete ffmpeg rund 630 MB, weil es die ganze Bibliothekskette
# mitzieht. Die statisch gebundene Ausgabe bringt alles im Programm selbst mit: zwei Dateien,
# und in der Laufzeitstufe bleibt keine einzige Bibliothek zurück.
# Quelle seit 21.10.2026 ist das Abbild mwader/static-ffmpeg (Docker Hub), festgenagelt über seine Prüfsumme
# (Digest des Index für amd64 und arm64): Die bisherige Quelle johnvansickle.com war nicht erreichbar und ließ
# den Deploy scheitern; Docker Hub ist ohnehin die Quelle der Basisabbilder. Wie bei den JavaScript-Bibliotheken
# entscheidet die Prüfsumme, nicht der Name. Neue Fassung: Tag und Digest gemeinsam ersetzen
# (Digest: docker buildx imagetools inspect mwader/static-ffmpeg:<tag>).
FROM mwader/static-ffmpeg:7.0.2@sha256:d9b22f65c2049d73bf8ae556bb4c5c7d45e9fb85939d87951ed98f22b0f19105 AS ffmpeg

FROM python:3.12-slim
# XDG_CACHE_HOME: Fontconfig (für WeasyPrint) legt seinen Zwischenspeicher dort ab – das Wurzeldateisystem ist
# zur Laufzeit schreibgeschützt (docker-compose.yml), /tmp ein flüchtiger Speicherbereich.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PIP_NO_CACHE_DIR=1 XDG_CACHE_HOME=/tmp/cache
# WeasyPrint (Protokolle des Moduls Material als PDF/A) braucht Pango und HarfBuzz. Die Protokolle setzen die
# eigene Schrift „DLRG Univers“ (app/static/fonts); DejaVu springt für Zeichen ein, die sie nicht hat, und setzt
# Prüfsummen in Festbreite.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
# ffmpeg und ffprobe sind eigenständige Programme; sie werden aufgerufen, nicht eingebunden.
# Ihre Lizenz (GPLv3) liegt daneben.
# Den Lizenztext (GPLv3) bringt das Debian-Grundabbild mit; das ffmpeg-Abbild enthält keinen.
COPY --from=ffmpeg /ffmpeg /ffprobe /usr/local/bin/
RUN mkdir -p /usr/local/share/ffmpeg \
    && { cp /usr/share/common-licenses/GPL-3 /usr/local/share/ffmpeg/GPLv3.txt \
         || echo "GNU General Public License v3: https://www.gnu.org/licenses/gpl-3.0.txt" > /usr/local/share/ffmpeg/GPLv3.txt; } \
    && ffprobe -version | head -1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=vendor /vendor ./app/static/vendor
# Nur /data gehört dem Laufzeitnutzer. Der Programmcode unter /srv bleibt root und damit für den
# laufenden Dienst unveränderlich – ein Fehler in der Anwendung kann so nicht ihren eigenen Code
# umschreiben. Bytecode wird ohnehin nicht geschrieben (PYTHONDONTWRITEBYTECODE).
RUN useradd --system --uid 1000 --create-home stroemis && mkdir -p /data && chown -R stroemis:stroemis /data
USER stroemis
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" || exit 1
# Das Zugriffsprotokoll führt nur den Pfad, nicht die Abfrage: sonst stünden dort Einmal-Links
# (etwa aus älteren Passwort-E-Mails) im Klartext. Aus demselben Grund fehlt der Referer –
# er trägt Pfad und Abfrage der verweisenden Seite vollständig mit.
# Gunicorn ab 25 öffnet von sich aus einen Steuer-Socket (gunicornc) unter $HOME/.gunicorn; das
# Wurzeldateisystem ist schreibgeschützt (docker-compose.yml, read_only), und gebraucht wird die
# Schnittstelle nicht – also aus.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "3600", \
     "--forwarded-allow-ips", "*", "--no-control-socket", "--access-logfile", "-", \
     "--access-logformat", "%(h)s %(l)s %(u)s %(t)s \"%(m)s %(U)s %(H)s\" %(s)s %(b)s \"%(a)s\"", \
     "app:create_app()"]
