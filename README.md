
# FINDMY BRIGE

![Python Version](https://shields.io)
![Database](https://shields.io)
![Infrastructure](https://shields.io)
![Code Style](https://shields.io)
[![License](https://shields.io)](LICENSE)

Python service to poll the Apple Find My network, decrypt BLE tag reports, </br>
and forward locations to a backend.

## FEATURES

- Persists Apple authentication via a one-time 2FA login.
- Loads active tags and cryptographic material from PostgreSQL.
- Fetches and decrypts Apple Find My reports in batches.
- Publishes the latest position for each tag to a backend endpoint.
- Exposes a `/health` endpoint for monitoring.

## ARCHITECTURE

```text
├── main.py                # Application startup and graceful shutdown
├── setup.py               # One-time Apple login and session persistence
├── config/                # Environment loading and validation
├── domain/                # Core models and protocol interfaces
├── apple/                 # Apple Find My session management and report fetching
├── infrastructure/        # PostgreSQL repository and backend publisher
├── notifications/         # Notification contract, dispatcher, and providers
├── application/           # Polling orchestration and publish workflow
├── health/                # Healthcheck HTTP endpoint
├── migrations/            # Database schema and seed data
└── mock_backend/          # Local backend emulator for testing
```

## PREREQUISITES & QUICK START

Ensure you have Python 3.10+ and PostgreSQL installed.

1. Initialize the environment:
```bash
make venv
```

2. Configure environment variables:
```bash
cp .env.example .env
```

3. Perform the initial interactive Apple 2FA login:
```bash
make setup
```

4. Run database migrations and seed test data:
```bash
make migrate
make seed
```

5. Start the service in development mode:
```bash
make dev
```

## ENVIRONMENT VARIABLES

| Variable | Required | Default | Description |
|---|---|---|---|
| `APPLE_ID` | Yes | — | Apple iCloud email |
| `APPLE_PASSWORD` | Yes | — | App-specific password |
| `BACKEND_URL` | Yes | — | Backend service base URL |
| `BACKEND_API_KEY` | Yes | — | Internal API key (`X-API-Key`) |
| `DATABASE_URL` | Yes | — | PostgreSQL DSN |
| `POLL_INTERVAL_MINUTES` | No | `20` | Polling interval in minutes |
| `MAX_CONCURRENT_TAGS` | No | `10` | Max tags fetched in parallel |
| `HEALTH_PORT` | No | `8080` | Health server port |
| `ENV` | No | `development` | `development` or `production` |
| `LOG_LEVEL` | No | `info` | `debug`, `info`, `warning`, `error` |
| `SLACK_WEBHOOK_URL` | No | — | Slack Incoming Webhook for alerts |

## MAKEFILE COMMANDS

- `make venv` : Create `.venv` environment and install dependencies.
- `make setup` : Run interactive Apple 2FA login (execute once).
- `make migrate` : Apply database schema migrations.
- `make seed` : Insert a development test tag.
- `make dev` : Run the service locally.
- `make lint` : Lint code quality using ruff.
- `make format` : Format code files using black.
- `make test` : Execute unit tests via pytest.
- `make clean` : Remove `__pycache__` directories and build caches.

## LOGGING

### Development (`ENV=development`)
Standard human-readable output:
```text
2026-05-18 00:25:56  INFO      apple.session                Session restored — user@email.com
2026-05-18 00:25:56  INFO      application.poll_cycle       [a3f2c1b0] Cycle started — 42 active tags
2026-05-18 00:25:56  INFO      infrastructure.pusher        [a3f2c1b0] Position published  tag=abc-123
```

### Production (`ENV=production`)
Structured JSON output for aggregation tools (ELK, Datadog, CloudWatch):
```json
{"ts": "2026-05-18T00:25:56Z", "level": "INFO", "logger": "apple.session", "msg": "Session restored"}
{"ts": "2026-05-18T00:25:56Z", "level": "INFO", "logger": "application.poll_cycle", "msg": "Cycle started — 42 active tags", "cycle_id": "a3f2c1b0"}
```
*Note: All logs within the same polling cycle share a unique `cycle_id` for distributed tracing.*

## SESSION MANAGEMENT

The session is persisted locally in `account_session.json` after the initial authentication. A background watchdog verifies session health every 30 minutes and re-authenticates proactively before the 24-hour token expiry.

**Security Warning:** Never commit `account_session.json` to version control. It contains active authentication credentials.

## SCALABILITY

| Tag Volume | Architecture Strategy |
|---|---|
| `< 5,000` | Default architecture. Optimize via `MAX_CONCURRENT_TAGS`. |
| `5,000 – 20,000` | Multi-account distribution. Run one worker process per Apple account. |
| `> 20,000` | Distributed queue. Deploy ARQ, Redis, and Kubernetes autoscaling. |

*Note: Transitioning to an official MFi Find My Network certification removes account pooling restrictions by granting direct access to Apple's enterprise REST API.*
