ALTER TABLE stock ADD COLUMN version BIGINT NOT NULL DEFAULT 0;

CREATE TABLE global_stock_settings (
    id BIGINT PRIMARY KEY CHECK (id > 0),
    default_low_stock_threshold BIGINT NOT NULL CHECK (default_low_stock_threshold >= 0),
    default_alert_enabled BOOLEAN NOT NULL,
    default_reorder_quantity BIGINT CHECK (default_reorder_quantity IS NULL OR default_reorder_quantity >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version BIGINT NOT NULL DEFAULT 0
);

INSERT INTO global_stock_settings (id, default_low_stock_threshold, default_alert_enabled, default_reorder_quantity, updated_at, version)
VALUES (1, 10, TRUE, NULL, NOW(), 0);

CREATE TABLE product_stock_policies (
    product_id BIGINT PRIMARY KEY REFERENCES products(id),
    low_stock_threshold BIGINT CHECK (low_stock_threshold IS NULL OR low_stock_threshold >= 0),
    alert_enabled BOOLEAN,
    reorder_quantity BIGINT CHECK (reorder_quantity IS NULL OR reorder_quantity >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE stock_movements (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK (id > 0),
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity_delta BIGINT NOT NULL,
    quantity_after BIGINT NOT NULL CHECK (quantity_after >= 0),
    operation VARCHAR(16) NOT NULL CHECK (operation IN ('INCREASE', 'DECREASE')),
    source VARCHAR(128),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stock_movements_product_created ON stock_movements(product_id, created_at DESC);

CREATE TABLE alerts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK (id > 0),
    product_id BIGINT NOT NULL REFERENCES products(id),
    type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    threshold BIGINT NOT NULL,
    quantity BIGINT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(255),
    resolved_at TIMESTAMPTZ,
    note TEXT,
    version BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_product_triggered ON alerts(product_id, triggered_at DESC);
CREATE UNIQUE INDEX uq_alerts_active_per_product ON alerts(product_id) WHERE status IN ('ACTIVE', 'ACKNOWLEDGED');

CREATE TABLE idempotency_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK (id > 0),
    scope VARCHAR(128) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    request_hash VARCHAR(128) NOT NULL,
    response_status INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_idempotency_scope_key ON idempotency_records(scope, idempotency_key);
