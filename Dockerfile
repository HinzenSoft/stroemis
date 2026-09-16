# strömis.de – ein Container: Flask/Gunicorn liefert API, Oberfläche und Bilder aus.
# Stufe 1 lädt die JavaScript-Bibliotheken mit festen Versionen, damit zur Laufzeit kein CDN nötig ist.
FROM python:3.12-slim AS vendor
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG LEAFLET=1.9.4
ARG MARKERCLUSTER=1.5.3
ARG MARKED=12.0.2
ARG DOMPURIFY=3.1.6
ARG TOASTUI=3.2.2
# Prüfsumme der optionalen deutschen Sprachdatei (siehe unten – sie darf fehlen, der Rest nicht).
ARG DE_DE_SHA=a904840fa6f6e0983570e0aa258f7b0bddcc83133969a3e69df526c7cb905a8e
WORKDIR /vendor
COPY vendor.sha256 .
# Toast UI Editor kommt vom Hersteller-CDN: die -all-Bündel liegen nicht im npm-Paket (unpkg → 404).
# Jede Datei wird gegen vendor.sha256 geprüft: feste Versionsnummern allein bewahren nicht davor,
# dass ein Paketspiegel andere Inhalte ausliefert als erwartet.
RUN set -eux; \
    mkdir -p leaflet/images markercluster marked dompurify toastui; \
    for f in leaflet.js leaflet.css; do curl -fsSL -o leaflet/$f "https://unpkg.com/leaflet@${LEAFLET}/dist/$f"; done; \
    for f in layers.png layers-2x.png marker-icon.png marker-icon-2x.png marker-shadow.png; do \
        curl -fsSL -o leaflet/images/$f "https://unpkg.com/leaflet@${LEAFLET}/dist/images/$f"; done; \
    for f in leaflet.markercluster.js MarkerCluster.css MarkerCluster.Default.css; do \
        curl -fsSL -o markercluster/$f "https://unpkg.com/leaflet.markercluster@${MARKERCLUSTER}/dist/$f"; done; \
    curl -fsSL -o marked/marked.min.js "https://unpkg.com/marked@${MARKED}/marked.min.js"; \
    curl -fsSL -o dompurify/purify.min.js "https://unpkg.com/dompurify@${DOMPURIFY}/dist/purify.min.js"; \
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
# zusammen etwa 155 MB, und in der Laufzeitstufe bleibt keine einzige Bibliothek zurück.
FROM python:3.12-slim AS ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
ARG FFMPEG=7.0.2
# Wie bei den JavaScript-Bibliotheken entscheidet die Prüfsumme, nicht der Dateiname.
# Neue Fassung: FFMPEG hochsetzen und die Prüfsumme des neuen Archivs hier eintragen
# (sha256sum ffmpeg-release-<arch>-static.tar.xz).
ARG FFMPEG_SHA_AMD64=abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67
ARG FFMPEG_SHA_ARM64=f4149bb2b0784e30e99bdda85471c9b5930d3402014e934a5098b41d0f7201b1
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) bogen=amd64; summe="${FFMPEG_SHA_AMD64}" ;; \
        arm64) bogen=arm64; summe="${FFMPEG_SHA_ARM64}" ;; \
        *) echo "Keine statische ffmpeg-Ausgabe für ${TARGETARCH}." >&2; exit 1 ;; \
    esac; \
    # Die jeweils neueste Fassung liegt unter releases/, ältere wandern nach old-releases/.
    # Beide Wege führen zu derselben Datei – welcher gilt, hängt nur am Alter der Fassung.
    curl -fsSL -o ffmpeg.tar.xz \
        "https://johnvansickle.com/ffmpeg/old-releases/ffmpeg-${FFMPEG}-${bogen}-static.tar.xz" \
    || curl -fsSL -o ffmpeg.tar.xz \
        "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${bogen}-static.tar.xz"; \
    echo "${summe}  ffmpeg.tar.xz" | sha256sum -c -; \
    mkdir -p /ffmpeg; \
    tar -xJf ffmpeg.tar.xz --strip-components=1 -C /ffmpeg --wildcards '*/ffmpeg' '*/ffprobe' '*/GPLv3.txt'; \
    chmod 755 /ffmpeg/ffmpeg /ffmpeg/ffprobe; \
    /ffmpeg/ffprobe -version | head -1

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PIP_NO_CACHE_DIR=1
# ffmpeg und ffprobe sind eigenständige Programme; sie werden aufgerufen, nicht eingebunden.
# Ihre Lizenz (GPLv3) liegt daneben.
COPY --from=ffmpeg /ffmpeg/ffmpeg /ffmpeg/ffprobe /usr/local/bin/
COPY --from=ffmpeg /ffmpeg/GPLv3.txt /usr/local/share/ffmpeg/GPLv3.txt
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=vendor /vendor ./app/static/vendor
RUN useradd --system --uid 1000 --create-home stroemis && mkdir -p /data && chown -R stroemis:stroemis /data /srv
USER stroemis
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" || exit 1
# Das Zugriffsprotokoll führt nur den Pfad, nicht die Abfrage: sonst stünden dort Einmal-Links
# (etwa aus älteren Passwort-E-Mails) im Klartext. Aus demselben Grund fehlt der Referer –
# er trägt Pfad und Abfrage der verweisenden Seite vollständig mit.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "3600", \
     "--forwarded-allow-ips", "*", "--access-logfile", "-", \
     "--access-logformat", "%(h)s %(l)s %(u)s %(t)s \"%(m)s %(U)s %(H)s\" %(s)s %(b)s \"%(a)s\"", \
     "app:create_app()"]
