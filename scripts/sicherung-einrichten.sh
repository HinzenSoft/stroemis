#!/usr/bin/env bash
# Trägt die stündliche Sicherung in den Cron des aufrufenden Nutzers ein – mehrfach aufrufbar,
# der Eintrag wird ersetzt statt verdoppelt. Das Deploy ruft es mit, damit ein neuer Server
# oder ein Nutzerwechsel den Zeitplan nicht verliert.
set -euo pipefail
# Je Klon ein eigener Eintrag: Produktion und Entwicklung können auf demselben Host liegen. Ersetzt
# wird nur der Eintrag dieses Ordners (auch ein älterer ohne Ordner in der Marke).
WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKE="# stroemis-sicherung"
ZEILE="7 * * * * cd '$WURZEL' && scripts/sicherung.sh stuendlich >> sicherung.log 2>&1 $MARKE $WURZEL"
alt="$(crontab -l 2>/dev/null || true)"
neu="$(printf '%s\n' "$alt" | grep -vF "cd '$WURZEL' && scripts/sicherung.sh" || true)"
printf '%s\n%s\n' "$neu" "$ZEILE" | sed '/^$/d' | crontab -
echo "Stündliche Sicherung eingetragen (Minute 7): $ZEILE"
