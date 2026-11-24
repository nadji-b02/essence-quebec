# Essence au meilleur prix

Trouve la station la moins chère et la plus proche, à partir des prix publiés par la Régie de l'énergie du Québec (Régie essence Québec).

- `site/` : la page (GPS, tri par prix, distance ou meilleur choix).
- `scripts/maj.py` : télécharge le fichier Excel le plus récent de la Régie et le convertit en `site/stations.json`.
- `scripts/historique.py` : garde le prix moyen par région, chaque heure (onglet Tendance).
- `scripts/alertes.py` : lit les alertes enregistrées dans l'appli et envoie les notifications ntfy.
- `data/` : copie de secours de l'historique et état des alertes (mis à jour par le workflow).
- `.github/workflows/maj-prix.yml` : republie la page avec les nouveaux prix toutes les 10 minutes, en continu (séries d'environ 2 h qui se relaient).

Réglage requis une seule fois : **Settings → Pages → Source : GitHub Actions**.
