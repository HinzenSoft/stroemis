#!/usr/bin/env bash
# strömis.de – inkrementelle Sicherung des Datenordners auf ein NAS (oder in einen lokalen Ordner).
#
#   scripts/sicherung.sh stuendlich   # aus dem Cron (scripts/sicherung-einrichten.sh)
#   scripts/sicherung.sh deploy       # aus .github/workflows/deploy.yml, vor dem Neustart
#   scripts/sicherung.sh hand         # von Hand
#
# Läuft auf dem Host, nicht im Container: Der Container ist schreibgeschützt und kennt kein NAS.
# Jeder Lauf legt auf dem Ziel einen eigenen Ordner <JJJJ-MM-TT_HHMM[-grund]> an, der den ganzen
# Datenordner enthält. Unveränderte Dateien sind Hardlinks auf den vorigen Schnappschuss
# (rsync --link-dest): Ein Lauf kostet nur, was sich geändert hat, und trotzdem ist jeder Ordner
# für sich vollständig – zurückspielen heißt kopieren, ohne Werkzeug und ohne Kette.
# Die Datenbank wird nicht als Datei kopiert (WAL-Modus, läuft gerade), sondern über SQLites
# Online-Backup in einen Stand gebracht, der in sich stimmt, und vor dem Übertragen geprüft.
#
# Einstellungen stehen in der .env neben docker-compose.yml:
#   BACKUP_ZIEL=sicherung@nas.local:/volume1/sicherung/stroemis   (oder ein lokaler Pfad)
#   BACKUP_SSH_KEY=~/.ssh/id_ed25519   BACKUP_SSH_PORT=22
#   BACKUP_BEHALTEN_STUNDEN=48  BACKUP_BEHALTEN_TAGE=30  BACKUP_BEHALTEN_MONATE=12
# Ohne BACKUP_ZIEL tut das Skript nichts (Rückgabe 0): Ein Deploy soll nicht daran scheitern,
# dass noch kein NAS eingerichtet ist. Ist ein Ziel eingetragen und die Sicherung schlägt fehl,
# endet das Skript mit Fehler – und das Deploy bricht davor ab.
set -euo pipefail

GRUND="${1:-hand}"
case "$GRUND" in stuendlich|deploy|hand) ;; *) echo "Unbekannter Grund „$GRUND“ (stuendlich|deploy|hand)" >&2; exit 2 ;; esac

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATEN="${DATA_DIR:-$WURZEL/data}"
ENV_DATEI="$WURZEL/.env"

sag() { printf '%s sicherung[%s]: %s\n' "$(date '+%F %T')" "$GRUND" "$*"; }
fehler() { sag "FEHLER: $*" >&2; exit 1; }

# --- Einstellungen aus der .env (nur BACKUP_*, ohne die Datei als Shell auszuführen) ------------
BACKUP_ZIEL=""; BACKUP_SSH_KEY=""; BACKUP_SSH_PORT="22"
BACKUP_BEHALTEN_STUNDEN="48"; BACKUP_BEHALTEN_TAGE="30"; BACKUP_BEHALTEN_MONATE="12"
if [ -f "$ENV_DATEI" ]; then
    while IFS= read -r zeile; do
        zeile="${zeile%%$'\r'}"
        case "$zeile" in BACKUP_*=*) ;; *) continue ;; esac
        name="${zeile%%=*}"; wert="${zeile#*=}"
        wert="${wert#"${wert%%[![:space:]]*}"}"; wert="${wert%"${wert##*[![:space:]]}"}"
        case "$wert" in \"*\") wert="${wert#\"}"; wert="${wert%\"}" ;; \'*\') wert="${wert#\'}"; wert="${wert%\'}" ;; esac
        case "$name" in
            BACKUP_ZIEL|BACKUP_SSH_KEY|BACKUP_SSH_PORT|BACKUP_BEHALTEN_STUNDEN|BACKUP_BEHALTEN_TAGE|BACKUP_BEHALTEN_MONATE)
                printf -v "$name" '%s' "$wert" ;;
        esac
    done < "$ENV_DATEI"
fi
# Umgebungsvariablen (etwa aus dem Deploy-Workflow) gehen vor.
BACKUP_ZIEL="${BACKUP_ZIEL_ENV:-$BACKUP_ZIEL}"

if [ -z "$BACKUP_ZIEL" ]; then
    sag "BACKUP_ZIEL ist nicht gesetzt – keine Sicherung (siehe README, Abschnitt „Daten und Sicherung“)."
    exit 0
fi
[ -d "$DATEN" ] || fehler "Datenordner $DATEN fehlt."
for werkzeug in rsync python3 flock; do command -v "$werkzeug" >/dev/null || fehler "$werkzeug fehlt auf diesem Rechner."; done

# --- Ziel: „nutzer@host:/pfad“ geht per SSH, alles andere ist ein lokaler Pfad ------------------
HOST=""; PFAD="$BACKUP_ZIEL"
case "$BACKUP_ZIEL" in
    *:/*) HOST="${BACKUP_ZIEL%%:*}"; PFAD="${BACKUP_ZIEL#*:}" ;;
esac
SSH_OPTS=(-p "$BACKUP_SSH_PORT" -o BatchMode=yes -o ConnectTimeout=20)
if [ -n "$BACKUP_SSH_KEY" ]; then
    schluessel="${BACKUP_SSH_KEY/#\~/$HOME}"
    [ -r "$schluessel" ] || fehler "SSH-Schlüssel $schluessel ist nicht lesbar."
    SSH_OPTS+=(-i "$schluessel")
fi
# Ein Befehl auf dem Ziel – übers Netz oder hier.
fern() {
    if [ -n "$HOST" ]; then ssh "${SSH_OPTS[@]}" "$HOST" "$1"; else bash -c "$1"; fi
}
RSYNC_FERN=()
[ -n "$HOST" ] && RSYNC_FERN=(-e "ssh ${SSH_OPTS[*]}")
ziel() { if [ -n "$HOST" ]; then printf '%s:%s' "$HOST" "$1"; else printf '%s' "$1"; fi; }

# --- Nur ein Lauf zugleich: Der stündliche wartet, wenn gerade das Deploy sichert ---------------
mkdir -p "$DATEN/tmp/sicherung"
exec 9>"$DATEN/tmp/sicherung/sperre"
flock -w 900 9 || fehler "Eine andere Sicherung läuft seit über 15 Minuten."

STEMPEL="$(date '+%F_%H%M')"
[ "$GRUND" = stuendlich ] || STEMPEL="$STEMPEL-$GRUND"
NEU="$PFAD/$STEMPEL"
TEIL="$NEU.teil"
sag "Sicherung nach $(ziel "$NEU") beginnt."

# --- Datenbank in sich stimmig abziehen und prüfen ----------------------------------------------
ABZUG="$DATEN/tmp/sicherung/stroemis.db"
rm -f "$ABZUG"
if ! python3 - "$DATEN/stroemis.db" "$ABZUG" <<'PY'
import sqlite3, sys
quelle, ziel = sys.argv[1], sys.argv[2]
# Nur lesen: Das Online-Backup kopiert seitenweise und wartet Schreiber ab – der Dienst läuft weiter.
src = sqlite3.connect(f"file:{quelle}?mode=ro", uri=True, timeout=60)
dst = sqlite3.connect(ziel)
with dst:
    src.backup(dst)
src.close()
stand = dst.execute("PRAGMA quick_check").fetchone()[0]
dst.close()
if stand != "ok":
    sys.exit(f"Abzug der Datenbank ist nicht in Ordnung: {stand}")
PY
then
    # Gehört der Datenordner einem anderen Nutzer (uid 1000 im Container), liest der Dienst selbst.
    sag "Datenbank direkt nicht lesbar – versuche es über den laufenden Container."
    (cd "$WURZEL" && docker compose exec -T stroemis python3 -c '
import sqlite3
src = sqlite3.connect("file:/data/stroemis.db?mode=ro", uri=True, timeout=60)
dst = sqlite3.connect("/data/tmp/sicherung/stroemis.db")
with dst:
    src.backup(dst)
stand = dst.execute("PRAGMA quick_check").fetchone()[0]
assert stand == "ok", stand
') || fehler "Die Datenbank ließ sich nicht abziehen."
fi
[ -s "$ABZUG" ] || fehler "Der Datenbankabzug ist leer."

# --- Übertragen: Datenordner ohne die lebende Datenbank und ohne Zwischendateien ----------------
fern "mkdir -p '$PFAD' && rm -rf '$TEIL'"
LINK=()
if fern "[ -d '$PFAD/latest' ]"; then LINK=(--link-dest="../latest"); fi
RSYNC=(rsync -a --delete --no-inc-recursive --stats --human-readable "${RSYNC_FERN[@]}" "${LINK[@]}")
"${RSYNC[@]}" \
    --exclude='/stroemis.db' --exclude='/stroemis.db-wal' --exclude='/stroemis.db-shm' \
    --exclude='/videopflege.lock' --exclude='/tmp/' \
    "$DATEN/" "$(ziel "$TEIL/")" | grep -E 'Number of (regular )?files|transferred|Total transferred|Literal data' | sed 's/^/    /'
# Der Abzug kommt an die Stelle der lebenden Datenbank: Der Schnappschuss sieht aus wie /data.
"${RSYNC[@]}" "$ABZUG" "$(ziel "$TEIL/stroemis.db")" >/dev/null
rm -f "$ABZUG"
# Erst wenn alles da ist, bekommt der Ordner seinen Namen und wird „latest“ – ein abgebrochener
# Lauf hinterlässt nur einen .teil-Ordner, den der nächste Lauf wegräumt.
fern "mv '$TEIL' '$NEU' && ln -sfn '$STEMPEL' '$PFAD/latest'"
sag "Schnappschuss $STEMPEL steht, latest zeigt darauf."

# --- Aufbewahren: alle der letzten Stunden, je Tag einer, je Monat einer ------------------------
# Deploy- und Handsicherungen zählen wie die stündlichen; .teil-Reste älter als einen Tag fliegen.
LISTE="$(fern "ls -1 '$PFAD'")"
# Die Liste geht über die Umgebung hinein – die Standardeingabe trägt das Python-Programm.
WEG="$(LISTE="$LISTE" python3 - "$BACKUP_BEHALTEN_STUNDEN" "$BACKUP_BEHALTEN_TAGE" "$BACKUP_BEHALTEN_MONATE" <<'PY'
import os, re, sys
from datetime import datetime, timedelta
stunden, tage, monate = (int(a) for a in sys.argv[1:4])
jetzt = datetime.now()
eintraege = []
for name in os.environ.get("LISTE", "").split():
    m = re.match(r"^(\d{4}-\d{2}-\d{2}_\d{4})(-[a-z]+)?(\.teil)?$", name)
    if not m:
        continue
    zeit = datetime.strptime(m.group(1), "%Y-%m-%d_%H%M")
    if m.group(3):
        if jetzt - zeit > timedelta(days=1):
            print(name)
        continue
    eintraege.append((zeit, name))
eintraege.sort()
behalten = set()
erster_je_tag, erster_je_monat = {}, {}
for zeit, name in eintraege:
    if jetzt - zeit <= timedelta(hours=stunden):
        behalten.add(name)
    erster_je_tag.setdefault(zeit.date(), name)
    erster_je_monat.setdefault((zeit.year, zeit.month), name)
for tag, name in erster_je_tag.items():
    if jetzt.date() - tag <= timedelta(days=tage):
        behalten.add(name)
for (jahr, monat), name in erster_je_monat.items():
    if (jetzt.year - jahr) * 12 + jetzt.month - monat < monate:
        behalten.add(name)
if eintraege:
    behalten.add(eintraege[-1][1])      # der jüngste bleibt immer – er ist „latest“
for zeit, name in eintraege:
    if name not in behalten:
        print(name)
PY
)"
anzahl=0
for alt in $WEG; do
    case "$alt" in */*|.|..|"") fehler "Unerwarteter Ordnername „$alt“ – nichts gelöscht." ;; esac
    fern "rm -rf '$PFAD/$alt'"
    anzahl=$((anzahl + 1))
done
[ "$anzahl" -gt 0 ] && sag "$anzahl alte Schnappschüsse entfernt."
sag "Fertig: $(printf '%s\n' "$LISTE" | grep -cE '^[0-9]{4}-' || true) Schnappschüsse vor dem Aufräumen, Ziel $(ziel "$PFAD")."
