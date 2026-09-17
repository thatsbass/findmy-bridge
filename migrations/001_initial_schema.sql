-- Migration 001 — initial schema for local development
-- Mirrors the tables the backend service will own in production.

CREATE TABLE IF NOT EXISTS tags (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    private_key     BYTEA       NOT NULL,        -- P-224 private key (28 bytes)
    advertising_key BYTEA       NOT NULL,        -- SHA-256(public_key)[:28]
    status          TEXT        NOT NULL DEFAULT 'unassigned'
                                CHECK (status IN ('unassigned', 'assigned')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id     UUID        NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    active     BOOLEAN     NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tags_status
    ON tags(status);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tag_active_expires
    ON subscriptions(tag_id, active, expires_at);
