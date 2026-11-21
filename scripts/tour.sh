#!/usr/bin/env bash
# Une mise à jour : prix de la Régie, historique, alertes, puis enregistrement des données.
set -u
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git pull -q --rebase --autostash origin main || true

if python scripts/maj.py site/stations.json; then etat=success; else etat=failure; fi
python scripts/heures.py || true
python scripts/historique.py || true
python scripts/alertes.py "$etat" || true

# Enregistre l'état des alertes et la copie quotidienne de l'historique.
# Ces commits gardent aussi le dépôt actif (GitHub met en pause les tâches
# programmées d'un dépôt public inactif depuis 60 jours).
git add data/
if ! git diff --cached --quiet; then
  git commit -q -m "Données $(date -u +'%F %H:%M')"
  git pull -q --rebase --autostash -X theirs origin main || true
  git push -q || true
fi
exit 0
