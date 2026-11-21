# Hinweise für Claude

## Pull Requests

- Nach dem Öffnen eines Pull Requests sofort Auto-Merge einschalten, Methode „Merge-Commit“ (Wunsch des Nutzers vom
  21.11.2026). GitHub führt ihn dann von selbst zusammen, sobald die Pflichtprüfung `Tests` grün ist – ein Merge nach
  `main` rollt die Produktion aus (`.github/workflows/deploy.yml`).

## dev zieht mit

- Was nach `main` geht, kommt gleich danach auch nach `dev` (dev.strömis.de; Wunsch des Nutzers vom 21.11.2026): Liegt
  `dev` nur hinter `main`, vorspulen (`git push origin origin/main:dev`), hat `dev` eigene Commits, `main` hineinmergen.
  Ein Push nach `dev` rollt die Entwicklungsumgebung aus.
- Nur wenn der Nutzer es ausdrücklich sagt, geht eine Änderung allein nach `dev` und nicht nach `main` – dann als Pull
  Request gegen `dev`.
