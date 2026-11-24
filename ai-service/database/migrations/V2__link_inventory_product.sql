-- Logical reference only: inventory products live in a separate database.
-- NULL means unresolved. Existing local IDs and embedding references are unchanged.
ALTER TABLE products
    ADD COLUMN inventory_product_id BIGINT,
    ADD CONSTRAINT products_inventory_product_id_unique UNIQUE (inventory_product_id),
    ADD CONSTRAINT products_inventory_product_id_positive CHECK (inventory_product_id > 0);
