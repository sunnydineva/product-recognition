-- Do not infer historical coverage from incomplete pre-migration movements.
ALTER TABLE stock ADD COLUMN history_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE stock ADD COLUMN history_initial_quantity BIGINT;
UPDATE stock SET history_initial_quantity = quantity, history_started_at = clock_timestamp();
ALTER TABLE stock ALTER COLUMN history_initial_quantity SET NOT NULL;
ALTER TABLE stock ADD CHECK (history_initial_quantity >= 0);

ALTER TABLE global_stock_settings
    ADD COLUMN rapid_drop_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN rapid_drop_percent INTEGER NOT NULL DEFAULT 50 CHECK (rapid_drop_percent BETWEEN 1 AND 100),
    ADD COLUMN rapid_drop_window_hours INTEGER NOT NULL DEFAULT 24 CHECK (rapid_drop_window_hours BETWEEN 1 AND 8760),
    ADD COLUMN rapid_drop_minimum_drop BIGINT NOT NULL DEFAULT 1 CHECK (rapid_drop_minimum_drop >= 1);
ALTER TABLE product_stock_policies
    ADD COLUMN rapid_drop_enabled BOOLEAN,
    ADD COLUMN rapid_drop_percent INTEGER CHECK (rapid_drop_percent BETWEEN 1 AND 100),
    ADD COLUMN rapid_drop_window_hours INTEGER CHECK (rapid_drop_window_hours BETWEEN 1 AND 8760),
    ADD COLUMN rapid_drop_minimum_drop BIGINT CHECK (rapid_drop_minimum_drop >= 1);

DROP INDEX uq_alerts_active_per_product;
CREATE UNIQUE INDEX uq_alerts_active_per_product_type ON alerts(product_id, type)
    WHERE status IN ('ACTIVE', 'ACKNOWLEDGED');
ALTER TABLE alerts ALTER COLUMN threshold DROP NOT NULL;
ALTER TABLE alerts
    ADD COLUMN rapid_drop_baseline BIGINT CHECK (rapid_drop_baseline >= 0),
    ADD COLUMN rapid_drop_current BIGINT CHECK (rapid_drop_current >= 0),
    ADD COLUMN rapid_drop_percent INTEGER CHECK (rapid_drop_percent BETWEEN 1 AND 100),
    ADD COLUMN rapid_drop_window_hours INTEGER CHECK (rapid_drop_window_hours BETWEEN 1 AND 8760),
    ADD COLUMN rapid_drop_minimum_drop BIGINT CHECK (rapid_drop_minimum_drop >= 1),
    ADD COLUMN rapid_drop_measured_percent NUMERIC(12,6);
ALTER TABLE alerts ADD CONSTRAINT ck_rapid_drop_metadata CHECK (
    type <> 'RAPID_DROP' OR (
        threshold IS NULL AND rapid_drop_baseline IS NOT NULL AND rapid_drop_baseline > 0
        AND rapid_drop_current IS NOT NULL AND rapid_drop_percent IS NOT NULL
        AND rapid_drop_window_hours IS NOT NULL AND rapid_drop_minimum_drop IS NOT NULL
        AND rapid_drop_measured_percent IS NOT NULL
    )
);
CREATE INDEX idx_stock_movements_baseline ON stock_movements(product_id, created_at DESC, id DESC)
    INCLUDE (quantity_after);
