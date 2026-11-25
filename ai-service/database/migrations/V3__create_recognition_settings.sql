-- One global camera-recognition threshold, expressed as a cosine similarity ratio.
CREATE TABLE recognition_settings (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    min_similarity DOUBLE PRECISION NOT NULL DEFAULT 0.30
        CHECK (min_similarity >= 0 AND min_similarity <= 1)
);

INSERT INTO recognition_settings (id, min_similarity) VALUES (1, 0.30);
