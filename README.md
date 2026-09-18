# findmy-bridge

Service Python qui récupère les rapports Apple Find My, extrait les positions
des tags, puis publie la position la plus récente vers un backend.

## Fonctionnalités

- authentification Apple avec persistance de session et prise en charge de la 2FA ;
- sélection des tags actifs depuis PostgreSQL ;
- récupération et déchiffrement des rapports Find My par lots ;
- publication des nouvelles positions vers le backend configuré ;
- endpoint HTTP `GET /health` pour la supervision ;
- polling immédiat au démarrage, puis à intervalle fixe.

## Architecture

Le projet est un modular monolith. Le worker orchestre les services applicatifs,
qui utilisent le domaine, les repositories et les intégrations externes.

```text
main.py
├── worker/              lifecycle et planification du polling
├── services/            cas d’utilisation polling et publication
├── domain/              modèles, règles et contrats applicatifs
├── infrastructure/     accès PostgreSQL et détails techniques
├── integrations/        Apple, Anisette, backend et notifications
├── api/                 application FastAPI et endpoints HTTP
├── config/              configuration et logging
├── cli/                 authentification Apple et migrations
└── migrations/          schéma et données de développement
```

## Prérequis

- Python 3.12 ou supérieur ;
- PostgreSQL ;
- un compte Apple compatible avec Apple Find My ;
- un backend qui accepte `POST /api/internal/positions` avec l’en-tête
  `X-API-Key`.

## Installation et démarrage

Créer l’environnement virtuel et installer les dépendances :

```bash
make venv
```

Créer un fichier `.env` à la racine avec les variables nécessaires (voir la
table ci-dessous). Les secrets ne doivent jamais être commités.

Initialiser la session Apple :

```bash
make setup
```

Appliquer le schéma PostgreSQL :

```bash
make migrate
```

Pour un environnement local, les données de démonstration peuvent être ajoutées
avec :

```bash
make seed
```

Démarrer le worker et l’API :

```bash
make dev
```

L’API de supervision est disponible sur `http://localhost:8080/health`, sauf si
`HEALTH_PORT` est configuré autrement.

## Configuration

| Variable | Requise | Valeur par défaut | Description |
|---|---:|---|---|
| `APPLE_ID` | Oui | — | Identifiant Apple iCloud |
| `APPLE_PASSWORD` | Oui | — | Mot de passe applicatif Apple |
| `BACKEND_URL` | Non | `http://localhost:5000` | URL de base du backend |
| `BACKEND_API_KEY` | Oui | — | Clé envoyée dans `X-API-Key` |
| `DATABASE_URL` | Oui | — | URL de connexion PostgreSQL |
| `POLL_INTERVAL_MINUTES` | Non | `20` | Intervalle entre deux cycles |
| `HEALTH_PORT` | Non | `8080` | Port de l’API health |
| `ENV` | Non | `development` | `development` ou `production` |
| `LOG_LEVEL` | Non | `info` | `debug`, `info`, `warning` ou `error` |
| `SLACK_WEBHOOK_URL` | Non | — | Webhook Slack pour les alertes 2FA/session |
| `ANISETTE_PROVIDER` | Non | `local` | Provider `local` ou `http` |
| `ANISETTE_URL` | Conditionnelle | — | URL requise avec le provider `http` |
| `ANISETTE_LIBS_PATH` | Non | `.anisette_libs` | Chemin des bibliothèques Anisette locales |
| `APPLE_SESSION_PATH` | Non | `account_session.json` | Fichier de session Apple persisté |

La configuration est validée au démarrage. Les valeurs numériques doivent être
des entiers strictement positifs et les valeurs énumérées doivent respecter les
valeurs autorisées.

## API

### `GET /health`

Réponse normale :

```json
{"status": "ok"}
```

L’API est une couche HTTP de supervision. Le traitement des tags et la
publication restent dans les services utilisés par le worker.

## Polling

Chaque cycle suit ce flux :

```text
PollingWorker
  → PollingService
  → repository PostgreSQL
  → intégration Apple
  → PublishingService
  → intégration backend
```

Le premier cycle est exécuté immédiatement au démarrage. Les erreurs d’un
rapport, d’un tag ou d’une publication sont isolées autant que possible afin de
ne pas interrompre inutilement les autres traitements. Les retries réseau sont
bornés et réservés aux erreurs temporaires.

## Session Apple

La session est enregistrée dans `APPLE_SESSION_PATH` après l’authentification
initiale. L’intégration Apple possède un watchdog qui renouvelle la session
lorsqu’elle approche de son expiration.

Ne partagez ni le fichier de session, ni le mot de passe Apple, ni les clés API.

## Commandes de développement

```text
make venv      Crée l’environnement virtuel et installe les dépendances
make setup     Effectue l’authentification Apple interactive
make migrate   Applique une migration SQL
make seed      Ajoute les données locales de démonstration
make dev       Lance le worker et l’API
make lint      Exécute Ruff s’il est installé
make format    Exécute Black s’il est installé
make test      Lance la suite unittest
make clean     Supprime les caches Python et outils
```

Les tests automatisés ne doivent pas dépendre d’un serveur Apple, PostgreSQL ou
backend réel. Les intégrations utilisent des contrats injectables pour rester
testables localement.

## Dépannage

- `Missing required environment variable` : vérifier le fichier `.env` et les
  variables obligatoires.
- `2FA required — run 'make setup' first` : créer ou renouveler la session Apple.
- erreur de connexion PostgreSQL : vérifier `DATABASE_URL`, le service PostgreSQL
  et les migrations.
- erreur de publication : vérifier `BACKEND_URL`, `BACKEND_API_KEY` et la
  disponibilité du endpoint backend.

Les logs de production sont structurés en JSON lorsque `ENV=production`. Aucun
secret ne doit apparaître dans les logs.
