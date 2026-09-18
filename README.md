# findmy-bridge

Python service that retrieves Apple Find My reports, extracts tag positions,
and publishes the latest position to a backend.

## Features

- Apple authentication with session persistence and 2FA support;
- selection of active tags from PostgreSQL;
- batched retrieval and decryption of Find My reports;
- publication of new positions to the configured backend;
- HTTP endpoint `GET /health` for monitoring;
- immediate polling at startup, then on a fixed interval.

## Architecture

The project is a modular monolith. The worker orchestrates the application
services, which use the domain layer, repositories, and external integrations.

```text
main.py
├── worker/              polling lifecycle and scheduling
├── services/            polling and publishing use cases
├── domain/              models, rules and application contracts
├── infrastructure/     PostgreSQL access and technical details
├── integrations/        Apple, Anisette, backend and notifications
├── api/                 FastAPI app and HTTP endpoints
├── config/              configuration and logging
├── cli/                 Apple authentication and migrations
└── migrations/          schema and development data
```

## Requirements

- Python 3.12 or newer;
- PostgreSQL;
- an Apple account compatible with Apple Find My;
- a backend that accepts `POST /api/internal/positions` with the `X-API-Key`
  header.

## Installation and startup

Create the virtual environment and install dependencies:

```bash
make venv
```

Create a `.env` file at the project root with the required variables (see the
configuration table below). Secrets must never be committed.

Initialize the Apple session:

```bash
make setup
```

Apply the PostgreSQL schema:

```bash
make migrate
```

For a local environment, sample data can be added with:

```bash
make seed
```

Start the worker and the API:

```bash
make dev
```

The health API is available at `http://localhost:8080/health`, unless
`HEALTH_PORT` is configured differently.

## Configuration

| Variable | Required | Default | Description |
|---|---:|---|---|
| `APPLE_ID` | Yes | — | Apple iCloud identifier |
| `APPLE_PASSWORD` | Yes | — | Apple app-specific password |
| `BACKEND_URL` | No | `http://localhost:5000` | Base URL of the backend |
| `BACKEND_API_KEY` | Yes | — | Key sent in `X-API-Key` |
| `DATABASE_URL` | Yes | — | PostgreSQL connection URL |
| `POLL_INTERVAL_MINUTES` | No | `20` | Time between polling cycles |
| `HEALTH_PORT` | No | `8080` | Port for the health API |
| `ENV` | No | `development` | `development` or `production` |
| `LOG_LEVEL` | No | `info` | `debug`, `info`, `warning` or `error` |
| `SLACK_WEBHOOK_URL` | No | — | Slack webhook for 2FA/session alerts |
| `ANISETTE_PROVIDER` | No | `local` | Provider: `local` or `http` |
| `ANISETTE_URL` | Conditional | — | URL required when using the `http` provider |
| `ANISETTE_LIBS_PATH` | No | `.anisette_libs` | Path to local Anisette libraries |
| `APPLE_SESSION_PATH` | No | `account_session.json` | Persisted Apple session file |

Configuration is validated at startup. Numeric values must be strictly positive
integers, and enumerated values must match the allowed options.

## API

### `GET /health`

Normal response:

```json
{"status": "ok"}
```

The API is a monitoring HTTP layer. Tag processing and publication remain in
services used by the worker.

## Polling

Each cycle follows this flow:

```text
PollingWorker
  → PollingService
  → PostgreSQL repository
  → Apple integration
  → PublishingService
  → backend integration
```

The first cycle runs immediately on startup. Errors in a report, tag, or
publication are isolated as much as possible so they do not unnecessarily stop
other work. Network retries are capped and reserved for temporary failures.

## Apple session

The session is saved to `APPLE_SESSION_PATH` after the initial authentication.
The Apple integration includes a watchdog that renews the session when it is
close to expiration.

Do not share the session file, Apple password, or API keys.

## Development commands

```text
make venv      Create the virtual environment and install dependencies
make setup     Run interactive Apple authentication
make migrate   Apply the SQL migration
make seed      Add local demo data
make dev       Start the worker and API
make lint      Run Ruff if installed
make format    Run Black if installed
make test      Run the unittest suite
make clean     Remove Python caches and tooling artifacts
```

Automated tests must not depend on a real Apple server, PostgreSQL instance, or
backend. Integrations use injectable contracts so they remain testable locally.

## Troubleshooting

- `Missing required environment variable`: check the `.env` file and the
  required variables.
- `2FA required — run 'make setup' first`: create or refresh the Apple session.
- PostgreSQL connection errors: verify `DATABASE_URL`, the PostgreSQL service,
  and the migrations.
- Publication errors: verify `BACKEND_URL`, `BACKEND_API_KEY`, and the backend
  endpoint availability.

Production logs are structured as JSON when `ENV=production`. No secrets should
appear in logs.
