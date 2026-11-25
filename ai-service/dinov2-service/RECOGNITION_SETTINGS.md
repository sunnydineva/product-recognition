# Global camera recognition threshold

DINOv2 owns one global setting for all products, persisted in the **AI**
PostgreSQL database (`DATABASE_URL`). Apply the additive AI Flyway migration
`ai-service/database/migrations/V3__create_recognition_settings.sql` through the
existing deployment migration process before using these endpoints. V1/V2 and
inventory settings are unchanged. The singleton is seeded with `0.30`.

```sh
curl http://localhost:18102/api/recognition/settings
# {"minSimilarity":0.3}
curl -X PATCH http://localhost:18102/api/recognition/settings \
  -H 'Content-Type: application/json' -d '{"minSimilarity":0.20}'
```

`minSimilarity` is a **ratio from 0 to 1**, not a percent wire value:
`0.30` means a cosine similarity threshold of 30%, `0.20` means 20%.
Cosine similarity is **not a calibrated probability or certainty**. Lower
thresholds accept more weak matches and can increase false positives.
PATCH requires this numeric field; empty, null, boolean, string, nonfinite,
out-of-range and unknown fields return 422. GET/PATCH return the same field.
Successful PATCH means the transaction committed; settings survive restarts.
Interactive OpenAPI documentation is at `/recognize/docs`.

Each `/recognize` request reads the persisted setting without a cache.
A finite numeric candidate score **greater than or equal to** the threshold
is accepted. Lower/invalid scores or no candidate return the existing
`{"status":"unknown","matches":[]}` response and publish no stock event.
Settings storage errors (including a missing singleton/migration) return 503,
not a default threshold, and publish no stock event. Database connection and
statement timeouts are three seconds each. A concurrent update takes effect
on subsequent reads; an in-flight recognition uses its initial read.
Enrollment and `/encode` are unchanged.

## Unresolved inventory integration risks

Accepted matches still use the existing AI-local `product_id` for the stock
event; this is not necessarily the canonical inventory ID. The existing
producer/consumer topic mismatch is also unresolved. This change does not
backfill IDs, reconcile topics, or establish authoritative inventory counts.
Even accepted visual matches are not proof of a warehouse stock decrease.

## Offline tests

From `ai-service/`:

```sh
.venv/bin/python -B -m unittest discover -s dinov2-service/tests -p test_recognition_settings.py
.venv/bin/python -B -m unittest discover -s dinov2-service/tests -p test_encoder.py
```

These mock external boundaries and never load the root `.env`. Do not run
`test_recognition_integration.py` as an offline check; it uses live services.
