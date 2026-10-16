#!/usr/bin/env bash
# Richtet die Entwicklungsumgebung ein: Zweig dev, eigene Domain (Vorgabe dev.strömis.de), eigener Port
# (Vorgabe 8008), eigene Daten – als zweiter Klon neben der Produktion auf demselben VPS. Einmalig, als
# Deploy-Nutzer. Solange die Produktion (Zweig main) das Skript noch nicht hat, holt man es aus dem
# Zweig dev, ohne an der Produktion etwas zu ändern:
#
#     git -C /pfad/zur/produktion fetch origin dev
#     git -C /pfad/zur/produktion show origin/dev:scripts/dev-einrichten.sh > ~/dev-einrichten.sh
#     bash ~/dev-einrichten.sh /pfad/zur/produktion [ZIELORDNER]
#
# Liegt das Skript schon im Klon der Produktion, genügt dort:  scripts/dev-einrichten.sh
# Ohne Zielordner entsteht der Klon neben der Produktion, mit „-dev“ am Ordnernamen – genau dort sucht
# ihn der Deploy-Workflow, solange das Secret DEPLOY_PATH_DEV nicht gesetzt ist. Domain und Port lassen
# sich mit DEV_DOMAIN=… und DEV_PORT=… ändern; DEV_KEIN_START=1 richtet nur ein, ohne zu bauen und zu
# starten.
#
# Was das Skript tut:
#   1. den Zweig dev aus demselben GitHub-Repository klonen, aus dem auch die Produktion holt;
#   2. die .env der Produktion kopieren und umstellen: eigener Projekt-, Container- und Abbildname,
#      eigener Port, eigene Adressen, „(DEV)“ im Seitennamen, eigener Sitzungsschlüssel, KEINE Sicherung
#      aufs NAS (sonst mischten sich die Schnappschüsse beider Umgebungen in einem Ordner);
#   3. den leeren Datenordner anlegen und dem Nutzer 1000 geben, unter dem der Container läuft;
#   4. bauen und starten.
# Die Produktion wird dabei nicht angefasst. Daten werden nicht kopiert – die Entwicklung beginnt leer,
# mit dem Administrator aus ADMIN_EMAIL/ADMIN_PASSWORD.
set -euo pipefail

fehler() { echo "FEHLER: $*" >&2; exit 1; }

# Produktionsordner: erstes Argument – sonst der Klon, in dem dieses Skript liegt.
QUELLE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
[ -d "$QUELLE" ] || fehler "$QUELLE ist kein Ordner."
QUELLE="$(cd "$QUELLE" && pwd)"
ZIEL="${2:-$QUELLE-dev}"
DOMAIN="${DEV_DOMAIN:-dev.strömis.de}"
PORT="${DEV_PORT:-8008}"

[ -f "$QUELLE/.env" ] && [ -f "$QUELLE/docker-compose.yml" ] || \
    fehler "$QUELLE ist nicht der Ordner der Produktion (dort fehlen .env oder docker-compose.yml)."
[ -e "$ZIEL" ] && fehler "$ZIEL gibt es schon. Nichts verändert."
command -v git >/dev/null || fehler "git fehlt."

URL="$(git -C "$QUELLE" remote get-url origin)"
echo "Klone den Zweig dev von $URL nach $ZIEL …"
git clone --branch dev "$URL" "$ZIEL" || fehler "Klonen fehlgeschlagen – gibt es den Zweig dev auf GitHub?"

# --- .env: Kopie der Produktion, umgestellt auf die Entwicklung ------------------------------------
cp "$QUELLE/.env" "$ZIEL/.env"
chmod 600 "$ZIEL/.env"
setze() {   # Schlüssel Wert – vorhandene Zeile ersetzen, sonst anhängen
    local tmp
    tmp="$(mktemp)"
    awk -v k="$1" -v v="$2" 'BEGIN { fertig = 0 }
        index($0, k "=") == 1 { if (!fertig) print k "=" v; fertig = 1; next }
        { print }
        END { if (!fertig) print k "=" v }' "$ZIEL/.env" > "$tmp"
    cat "$tmp" > "$ZIEL/.env"
    rm -f "$tmp"
}
{
    echo ""
    echo "# --- Entwicklungsumgebung (eingetragen von scripts/dev-einrichten.sh am $(date +%F)) ---"
} >> "$ZIEL/.env"
setze COMPOSE_PROJECT_NAME stroemis-dev
setze STROEMIS_NAME stroemis-dev
setze STROEMIS_PORT "$PORT"
setze BASE_URL "https://$DOMAIN"
setze PUBLIC_HOST "wiki.$DOMAIN"
setze PUBLIC_URL "https://$DOMAIN/oeffentlich"
setze SITE_NAME "strömis.de (DEV)"
setze SECRET_KEY ""
setze BACKUP_ZIEL ""

# --- Datenordner für den Nutzer im Container ----------------------------------------------------------
mkdir -p "$ZIEL/data"
if [ "$(stat -c %u "$ZIEL/data")" != "1000" ]; then
    if [ "$(id -u)" = "0" ]; then
        chown -R 1000:1000 "$ZIEL/data"
    else
        echo "Der Datenordner muss dem Nutzer 1000 gehören – dafür einmal sudo:"
        sudo chown -R 1000:1000 "$ZIEL/data" || fehler "chown fehlgeschlagen. Von Hand: sudo chown -R 1000:1000 '$ZIEL/data'"
    fi
fi

# --- Bauen und starten -------------------------------------------------------------------------------
if [ "${DEV_KEIN_START:-}" = "1" ]; then
    echo "Eingerichtet, nicht gestartet (DEV_KEIN_START=1). Starten:  cd '$ZIEL' && docker compose up -d --build"
else
    command -v docker >/dev/null || fehler "docker fehlt."
    (cd "$ZIEL" && docker compose up -d --build)
fi

cat <<HINWEIS

Fertig: $ZIEL (Zweig dev) – Container stroemis-dev auf Port $PORT.
Noch offen, falls nicht erledigt:
  1. DNS: $DOMAIN als A/AAAA-Eintrag auf diesen Server.
  2. Reverse-Proxy um diesen Block ergänzen und neu laden (Caddy):
       $DOMAIN, $(python3 -c "import sys; print(sys.argv[1].encode('idna').decode())" "$DOMAIN" 2>/dev/null || echo "$DOMAIN") {
           reverse_proxy 127.0.0.1:$PORT
           request_body {
               max_size 5GB
           }
           header X-Robots-Tag "noindex, nofollow"
       }
  3. Anmelden mit ADMIN_EMAIL/ADMIN_PASSWORD aus der .env. Danach rollt jeder Push auf dev automatisch aus.
HINWEIS
