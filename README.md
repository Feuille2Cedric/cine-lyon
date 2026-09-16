# Travelling · cinéma à Lyon

Agenda hebdomadaire des séances de huit cinémas lyonnais, déployable sans serveur sur GitHub Pages.

**[Ouvrir l’application](https://feuille2cedric.github.io/cine-lyon/)**

**Cinémas :** Pathé Bellecour, Pathé Vaise, Pathé Carré de Soie, Lumière Bellecour, Lumière Fourmi, Lumière Terreaux, Institut Lumière et Comœdia.

## Utilisation

- Vue semaine du lundi au dimanche, vue jour et liste exhaustive.
- Couleur par cinéma, filtres mémorisés sur l’appareil, recherche insensible aux accents, VF / VO.
- Navigation par semaine, calendrier miniature, choix d’une date et zoom vertical.
- Les séances simultanées occupent des colonnes distinctes. Les boutons **+N** donnent accès aux autres séances du créneau, sans les supprimer. La vue liste affiche toutes les séances filtrées.
- Détails et liens vers la réservation. Export `.ics` compatible avec Apple Agenda et les autres calendriers.
- Dates et heures toujours affichées dans le fuseau de Lyon, même depuis l’étranger.

## Données réelles

`scripts/collect.py` lit les programmes publics, puis produit `site/data/schedule.json`.

| Source | Cinémas | Collecte |
|---|---|---|
| [Cinémas Lumière](https://www.cinemas-lumiere.com/calendrier-general.html) | Bellecour, Fourmi, Terreaux | Tableau daté et durée des fiches films |
| [Institut Lumière](https://www.institut-lumiere.org/calendrier) | Institut / Villa / Hangar | Calendrier mensuel et mois liés |
| [Comœdia](https://www.cinema-comoedia.com/films/) | Comœdia | Flux public utilisé par le site |
| [AlloCiné](https://www.allocine.fr/) | Les trois Pathé | Calendriers publics, pagination complète, réservation Pathé |

Les Pathé utilisent AlloCiné car leur site officiel renvoyait une page d’erreur lors de la mise en place. Aucune clé API, aucun compte cinéma et aucune donnée fictive. Les flux publics peuvent changer : chaque source dispose d’un état et d’une date d’actualisation dans l’interface.

La hauteur des blocs correspond à la durée du film. La fin est estimée, hors publicités, présentations ou débats. Si la durée manque, un créneau indicatif de 90 minutes est signalé dans les détails. Si une fiche film a disparu, la séance reste visible avec « titre non communiqué » et son lien de réservation.

Les programmes futurs sont affichés uniquement lorsqu’ils sont publiés. Lors du premier lancement, les séances passées qui ont déjà disparu des sites ne peuvent pas être reconstituées. Les collectes suivantes conservent 35 jours d’historique. Si un collecteur échoue, ses dernières données sont conservées avec un statut d’erreur, sans fausse actualisation.

## Développement local

Python 3.12 conseillé. Le site lui-même est en HTML/CSS/JavaScript natif, sans compilation.

```sh
python -m venv .venv
# Activer l’environnement virtuel selon votre système.
pip install -r requirements.txt
python scripts/collect.py
python -m http.server 8765 --directory site
```

Ouvrir http://localhost:8765. Les modules JavaScript nécessitent un serveur HTTP ; ne pas ouvrir directement `index.html`.

## Tests

```sh
python -m unittest discover -s tests -p "test_*.py"
pip install playwright
# Linux/macOS : playwright install chromium
# Windows : le test utilise Microsoft Edge déjà installé.
python tests/browser_check.py
```

Les tests vérifient notamment les changements d’heure, le parsing des séances, les collisions, l’export iCalendar, la navigation, les filtres, les dialogues et l’affichage mobile. Les captures sont écrites dans `test-artifacts/`, hors Git.

## GitHub Pages

Dans **Settings → Pages → Source**, sélectionner **GitHub Actions**. Le workflow `pages.yml` publie `site/` à chaque push sur `main`, sur demande et quatre fois par jour (05:17, 11:17, 17:17 et 23:17 UTC ; l’exécution planifiée peut être retardée par GitHub).

Avant chaque collecte, le workflow récupère le dernier programme déployé pour conserver l’historique. Aucune écriture dans le dépôt ni secret personnel n’est nécessaire. Les permissions du workflow sont limitées à la lecture du dépôt et au déploiement Pages.

Les automatisations planifiées des dépôts publics peuvent être désactivées par GitHub après une longue période sans activité : vérifier l’onglet Actions si la date affichée devient ancienne.
