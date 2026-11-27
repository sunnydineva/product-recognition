-- Optional enrollment hints for recognition display only.
-- Inventory remains the canonical owner of product name and note.
ALTER TABLE products
    ADD COLUMN name VARCHAR(255),
    ADD COLUMN note TEXT;
