# Hinweise für Claude

## Pull Requests

- Nach dem Öffnen eines Pull Requests sofort Auto-Merge einschalten, Methode „Merge-Commit“ (Wunsch des Nutzers vom
  21.11.2026). GitHub führt ihn dann von selbst zusammen, sobald die Pflichtprüfung `Tests` grün ist – ein Merge nach
  `main` rollt die Produktion aus (`.github/workflows/deploy.yml`).
