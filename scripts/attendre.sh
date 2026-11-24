#!/usr/bin/env bash
# Attend le prochain multiple de CADENCE minutes, plus 90 secondes
# (la Régie publie un fichier toutes les 5 minutes; il est en ligne moins d'une minute après).
c=$(( ${CADENCE:-10} * 60 ))
maintenant=$(date +%s)
cible=$(( (maintenant / c + 1) * c + 90 ))
echo "Prochaine mise à jour à $(date -u -d @$cible +%H:%M:%S) UTC"
sleep $(( cible - maintenant ))
