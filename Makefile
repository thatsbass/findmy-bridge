PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3.12)

.PHONY: setup dev install lint format test clean venv migrate seed mock

venv:
	python3.12 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

setup:
	$(PYTHON) setup.py

dev:
	$(PYTHON) main.py

install:
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m black .

test:
	$(PYTHON) -m pytest tests/ -v

mock:
	node mock_backend/server.js

migrate:
	$(PYTHON) migrate.py migrations/001_initial_schema.sql

seed:
	$(PYTHON) migrate.py migrations/seed_dev.sql

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name ".pytest_cache" -exec rm -rf {} +
	find . -name ".ruff_cache" -exec rm -rf {} +
