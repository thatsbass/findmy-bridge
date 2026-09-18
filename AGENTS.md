# AGENTS.md

## Project

This repository is `findmy-bridge`, a Python service that collects Apple Find My reports, processes location data, stores relevant information, and publishes data to an external backend.

The project also exposes an API and runs a polling worker.

The goal is to perform a **complete architectural and code refactoring** of the existing project while preserving its required functionality and external behavior.

The objective is to obtain a **clean, maintainable, testable modular monolith**.

---

# 1. Refactoring Objective

This is a **real refactoring**, not a cosmetic cleanup.

The agent is allowed and expected to:

* rewrite existing functions;
* rewrite existing classes;
* split large classes;
* split large functions;
* merge unnecessary classes or modules;
* move files;
* rename modules, classes, and functions when justified;
* remove duplicated code;
* remove dead code;
* replace poor abstractions;
* change internal architecture;
* introduce clearer interfaces/contracts where useful;
* simplify overly complex implementations;
* reorganize dependencies.

Do not preserve bad code simply because it already exists.

However, preserve the application's required functionality and externally expected behavior unless a change is explicitly requested.

The goal is:

> **Keep what the application must do. Rebuild how the application does it when necessary.**

---

# 2. Core Principles

Follow these principles throughout the refactoring:

* Prefer simple solutions over clever solutions.
* Prefer explicit code over excessive abstraction.
* Keep responsibilities clear.
* Keep functions and classes focused.
* Remove duplicated business logic.
* Avoid hidden side effects.
* Avoid unnecessary global state.
* Prefer dependency injection through function or constructor parameters.
* Keep external integrations isolated from business logic.
* Keep HTTP/API concerns separate from business logic.
* Keep database concerns separate from business logic.
* Make important behavior easy to test.
* Prefer maintainability over preserving the current implementation.
* Do not introduce complexity without a concrete reason.

---

# 3. No Spaghetti Code

Do not introduce or preserve spaghetti code.

Avoid:

* giant functions;
* giant classes;
* deeply nested conditionals;
* duplicated business rules;
* unrelated responsibilities inside the same module;
* database queries scattered throughout business logic;
* HTTP requests scattered throughout the application;
* external API calls directly from FastAPI routes;
* polling logic directly inside API routes;
* business logic inside CLI or worker entrypoints;
* global mutable state;
* circular dependencies;
* hidden side effects;
* generic utility modules containing unrelated functionality;
* classes that only wrap a function without a real responsibility;
* generic `Manager`, `Helper`, `Utils`, or `CommonService` classes without a clear purpose.

If a component is difficult to understand, redesign it rather than adding more code around it.

---

# 4. Architecture

Use a **modular monolith**.

The preferred architecture is:

```text
src/
└── findmy_bridge/
    ├── api/
    │   ├── routes/
    │   ├── schemas/
    │   └── app.py
    │
    ├── domain/
    │   ├── tags/
    │   ├── positions/
    │   └── exceptions.py
    │
    ├── services/
    │   ├── polling.py
    │   ├── positions.py
    │   └── publishing.py
    │
    ├── integrations/
    │   ├── apple/
    │   ├── backend/
    │   ├── anisette/
    │   └── notifications/
    │
    ├── infrastructure/
    │   ├── database/
    │   ├── logging.py
    │   └── health.py
    │
    ├── worker/
    │   ├── scheduler.py
    │   └── runner.py
    │
    ├── config/
    │   └── settings.py
    │
    └── cli/
        └── main.py
```

This structure is a guideline, not a requirement to create every file.

The agent may adapt the structure when analysis shows a better organization.

Do not create artificial modules simply to satisfy the diagram.

---

# 5. Domain

The domain contains business concepts and rules.

Examples:

* tags;
* positions;
* reports;
* domain exceptions;
* repository contracts where useful;
* business validation;
* domain transformations.

The domain must not depend on:

* FastAPI;
* SQLAlchemy;
* HTTP clients;
* Apple runtime libraries;
* Slack;
* environment variables;
* Docker.

The domain should remain independent from infrastructure and external services.

---

# 6. Services

The service layer contains application use cases and orchestration.

Examples:

* polling;
* processing reports;
* processing positions;
* publishing positions;
* coordinating repositories and integrations.

Services should express application behavior clearly.

For example:

```text
PollingService
    ↓
Apple integration
    ↓
Report processing
    ↓
Position repository
    ↓
PublishingService
    ↓
Backend integration
```

Do not create one huge service responsible for the entire application.

Do not turn services into generic containers for unrelated methods.

---

# 7. API

FastAPI is an HTTP delivery layer.

Routes should:

1. validate input;
2. call the appropriate service;
3. translate the result into an HTTP response.

Routes must not contain complex business workflows.

Avoid:

```text
Route
 ├── database query
 ├── Apple request
 ├── data transformation
 ├── backend request
 └── business logic
```

Prefer:

```text
Route
   ↓
Service
   ↓
Domain / Repository / Integration
```

---

# 8. Integrations

External systems belong under:

```text
integrations/
```

This includes:

```text
integrations/apple/
integrations/backend/
integrations/anisette/
integrations/notifications/
```

External clients are responsible for external communication.

The rest of the application should not depend unnecessarily on external library details.

If an external library changes, the impact should be localized whenever practical.

---

# 9. Apple Find My

Apple-specific implementation must remain isolated.

This includes:

* Apple authentication;
* session management;
* Find My requests;
* report retrieval;
* report parsing;
* decryption;
* Apple-specific protocols.

Do not spread Apple-specific implementation details throughout the application.

Expose clean application/domain data to the rest of the system.

---

# 10. Anisette

Anisette providers must be isolated.

The existing modes are:

```text
local
http
```

Provider selection should happen in one clear location.

Do not duplicate provider-selection logic throughout the project.

Provider-specific implementation belongs under:

```text
integrations/anisette/
```

---

# 11. Backend Integration

External backend communication belongs under:

```text
integrations/backend/
```

The backend client handles:

* HTTP communication;
* authentication headers;
* serialization;
* response parsing;
* HTTP-specific errors;
* appropriate transport retries.

Application services decide **what** should be published.

The backend client decides **how** to communicate with the backend.

Do not scatter backend requests throughout the application.

---

# 12. Database

Database access must be centralized.

Prefer:

```text
Service
   ↓
Repository
   ↓
Database
```

Avoid database queries directly inside:

* API routes;
* workers;
* external integrations;
* random utility functions.

Repository implementations belong in infrastructure.

Do not introduce unnecessary repository abstractions when they provide no real value.

---

# 13. Polling

Polling is an application use case, not merely a background loop.

Separate:

1. scheduling;
2. report retrieval;
3. report processing;
4. persistence;
5. publishing;
6. error handling.

Prefer:

```text
Worker
   ↓
PollingService
   ↓
Apple integration
   ↓
Processing
   ↓
Repository
   ↓
PublishingService
   ↓
Backend integration
```

The worker should handle lifecycle and scheduling.

The service should contain polling business logic.

The polling loop must not become a giant function.

---

# 14. Idempotency

Publishing must avoid unintended duplicate data where the backend contract requires idempotency.

Do not invent arbitrary idempotency keys.

For example, do not automatically assume:

```text
tag_id + timestamp + latitude + longitude
```

is a valid universal identifier.

Use stable domain identity or the backend's actual idempotency mechanism.

The same report should not be published repeatedly simply because the polling process runs again.

---

# 15. Configuration

Keep configuration centralized.

The existing typed `Settings` approach should be preserved or improved unless there is a concrete reason to replace it.

Current environment variable names should remain consistent unless a deliberate migration is required.

Examples:

```text
DATABASE_URL
BACKEND_URL
BACKEND_API_KEY
APPLE_ID
APPLE_PASSWORD
POLL_INTERVAL_SECONDS
HEALTH_PORT
ANISETTE_PROVIDER
ANISETTE_URL
ANISETTE_LIBS_PATH
APPLE_SESSION_PATH
SLACK_WEBHOOK_URL
```

Configuration must:

* validate required values;
* validate allowed values;
* validate numeric values;
* avoid logging secrets;
* distinguish required and optional settings;
* support development/test defaults where appropriate.

---

# 16. Error Handling

Do not silently swallow errors.

Avoid:

```python
except Exception:
    pass
```

Catch the narrowest useful exception.

When catching an exception:

* add useful context;
* log appropriately;
* decide whether to retry;
* decide whether to continue;
* decide whether to fail.

Do not expose credentials or secrets in errors.

---

# 17. Retries

Retries must be intentional.

Retry appropriate temporary failures such as:

* network errors;
* temporary upstream failures;
* rate limiting when supported.

Do not retry deterministic failures such as:

* invalid credentials;
* invalid configuration;
* malformed requests;
* validation errors.

Retries must have:

* maximum attempts;
* sensible delays;
* clear logging;
* no infinite loops.

---

# 18. Security

Never expose or log:

* passwords;
* API keys;
* session tokens;
* authentication cookies;
* webhook secrets;
* private credentials.

Never commit secrets.

Do not disable TLS verification without a documented reason.

Validate external input.

Do not trust external responses blindly.

Do not add debug endpoints that expose sensitive application state.

---

# 19. Python Code Quality

Use modern Python typing supported by the project version.

Prefer:

```python
str | None
```

where supported.

Use:

* type hints;
* dataclasses where appropriate;
* focused functions;
* meaningful names;
* immutable structures where useful;
* explicit return types for important functions.

Do not create classes when a simple function is clearer.

Do not use classes only for the sake of object-oriented style.

---

# 20. Classes and Functions

A function should have a clear responsibility.

A class should represent a meaningful responsibility or stateful dependency.

The agent is explicitly allowed to rewrite existing classes and functions.

If an existing class is doing too much, split it.

If several classes are unnecessary, merge or remove them.

If a function is too complex, redesign it.

Do not preserve an existing abstraction merely because it already exists.

---

# 21. Testing

Tests must protect required behavior during the refactoring.

Prioritize:

### Unit tests

For:

* domain rules;
* transformations;
* configuration;
* services;
* error handling.

### Integration tests

For:

* database behavior;
* API endpoints;
* important integration boundaries.

Do not make unit tests depend on real external services.

Tests should validate behavior rather than implementation details.

When rewriting a component, update its tests rather than forcing the new implementation to satisfy obsolete tests.

---

# 22. Refactoring Strategy

The refactoring can be large, but it should be executed in **controlled stages**.

Before modifying an important component:

1. understand its current behavior;
2. identify dependencies;
3. identify callers;
4. identify tests;
5. identify external contracts;
6. design the replacement;
7. implement the change;
8. run relevant tests;
9. review the diff;
10. continue to the next component.

The agent may perform substantial rewrites when justified.

Do not limit a refactoring to superficial renaming or file movement.

At the same time, avoid changing unrelated parts of the application without a reason.

---

# 23. Preserve Behavior, Not Implementation

During the refactoring:

**Preserve required behavior. Do not preserve bad implementation.**

The following may be redesigned:

* internal classes;
* internal functions;
* module boundaries;
* dependencies;
* repositories;
* services;
* internal data flow;
* internal abstractions.

The following should remain compatible unless explicitly changed:

* external API contracts;
* required environment variables;
* database compatibility where required;
* Apple authentication behavior;
* backend contracts;
* expected polling behavior;
* externally visible functionality.

When a breaking change is technically necessary, identify it clearly before making it.

---

# 24. Avoid Over-Engineering

Do not introduce:

* microservices;
* CQRS;
* event sourcing;
* message brokers;
* event buses;
* elaborate dependency injection containers;
* unnecessary abstract base classes;
* excessive design patterns;
* unnecessary generic repositories;
* distributed systems;
* premature abstractions.

The target architecture is a **modular monolith**.

Architecture should solve actual problems in this repository.

---

# 25. File Organization

Do not create files only to make the architecture look sophisticated.

Avoid unnecessary files such as:

```text
interfaces.py
abstract.py
base.py
factory.py
manager.py
helper.py
utils.py
```

unless each has a clear responsibility.

Prefer a smaller number of meaningful modules.

---

# 26. Logging

Logs should answer:

* what happened;
* where it happened;
* why it failed;
* which operation was running;
* which external dependency was involved.

Use appropriate log levels:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Do not log secrets.

Do not log sensitive external responses unnecessarily.

---

# 27. Docker

Keep Docker configuration simple.

Containers should:

* receive configuration through environment variables;
* never contain secrets;
* expose only required ports;
* have predictable startup behavior;
* support graceful shutdown where applicable.

Do not add unnecessary Docker services.

---

# 28. Dependencies

Do not add dependencies without a concrete reason.

Before adding one, check whether:

* the standard library is sufficient;
* an existing dependency already solves the problem;
* the dependency adds unnecessary complexity.

Do not replace existing libraries merely because another library is more fashionable.

---

# 29. Documentation

Update documentation when architecture or behavior changes significantly.

Documentation should cover:

* installation;
* configuration;
* running the application;
* database;
* polling;
* integrations;
* testing;
* architecture;
* troubleshooting.

Avoid documenting implementation details that will quickly become obsolete.

---

# 30. Git and Repository Safety

The coding agent must **never commit or push changes automatically**.

## Forbidden without explicit user approval

Never perform:

* `git commit`;
* `git push`;
* `git push --force`;
* branch creation;
* branch deletion;
* `git reset`;
* `git rebase`;
* `git merge`;
* commit amendment;
* history rewriting;
* tag creation;
* release creation.

The user controls all Git operations that modify repository history, branches, or the remote repository.

## Allowed Git operations

Read-only commands may be used when necessary:

```text
git status
git log
git diff
git show
git branch --show-current
git remote -v
```

Never use destructive Git operations to solve a coding problem.

If a Git operation requires user approval, stop and ask before executing it.

---

# 31. Coding Agent Workflow

When starting work:

1. Read `AGENTS.md`.
2. Analyze the current repository.
3. Understand the main execution flows.
4. Identify architectural problems.
5. Identify important external contracts.
6. Propose a refactoring plan.
7. Wait for approval when the task requires architectural decisions.
8. Implement the approved refactoring.
9. Run relevant tests and quality checks.
10. Review the final diff.
11. Explain what changed.

The agent must not silently make major architectural decisions.

Do not perform unrelated cleanup.

Do not commit or push.

---

# 32. Final Principle

The goal is not to make the project look architecturally sophisticated.

The goal is to make it **cleaner than it is today**.

The final system should be:

* modular;
* readable;
* testable;
* maintainable;
* explicit;
* reasonably simple;
* easy to extend.

The most important rule is:

> **Preserve what the application must do, but freely redesign how the application does it when the current implementation is not clean, maintainable, or testable.**
