CREATE TABLE products (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK (id > 0),
    sku VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    barcode VARCHAR(128),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE stock (
    product_id BIGINT PRIMARY KEY REFERENCES products(id),
    quantity BIGINT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Future writers must maintain updated_at; no stock rows are created implicitly.
-- No cascading deletion of stock; retire catalog products with active = false.
