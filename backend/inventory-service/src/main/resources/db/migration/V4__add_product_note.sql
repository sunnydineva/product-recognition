-- Inventory is canonical; AI metadata is only a creation hint.
-- Existing products are not backfilled.
ALTER TABLE products ADD COLUMN note TEXT;
