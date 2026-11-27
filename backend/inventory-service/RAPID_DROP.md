# Rapid-drop alerts

`RAPID_DROP` is independent of `LOW_STOCK` (whose default threshold stays **10**).
Defaults: enabled, **50%** net decline over **24 hours**, minimum absolute decline
**1**. Percent is an integer 1–100, windowHours 1–8760, minimumDrop a positive
signed 64-bit integer.

Example `PUT /api/inventory/v1/settings`:

```json
{
  "defaultLowStockThreshold": 10,
  "defaultAlertEnabled": true,
  "defaultReorderQuantity": null,
  "rapidDrop": {"enabled": true, "percent": 50, "windowHours": 24, "minimumDrop": 1}
}
```

Example `PUT /api/inventory/v1/products/123/stock-policy`:

```json
{
  "lowStockThreshold": null,
  "alertEnabled": null,
  "reorderQuantity": null,
  "rapidDrop": {"percent": 60, "windowHours": null, "minimumDrop": null, "enabled": null}
}
```

Global rapid-drop members omitted/null retain current values. Omitting/nulling
the whole product rapidDrop object preserves existing overrides (old clients
continue to work); a present object replaces rapid overrides, and its null/omitted
members inherit global values. Send `"rapidDrop": {}` to reset all rapid overrides.
The pre-existing low-stock PUT semantics are unchanged.
Product responses include effective rapid settings; policy responses contain raw
overrides. `alertEnabled` controls LOW_STOCK only; `rapidDrop.enabled` controls
RAPID_DROP.

## Calculation and coverage

For evaluation time `t`, baseline is quantity **at** `t - windowHours`.
Net decline is `baseline - current`; receipts offset decreases. Both minimum
drop and percentage must qualify inclusively. Baseline zero, incomplete coverage,
disabled policy, or a recovered/expired signal cannot trigger an alert.
The interval is **(cutoff, t]**: movements exactly at cutoff are already reflected
in baseline. Applied timestamps are UTC clock instants truncated to PostgreSQL
microseconds, not event timestamps; ties use highest movement ID. Percentage
comparison is exact and overflow-safe; response percentage is rounded to six
decimals. One indexed latest-snapshot lookup reconstructs baseline without
loading or summing an unbounded movement history.

V3 snapshots existing stock quantity and starts coverage at migration time.
It deliberately does **not** infer complete history from old movements or invent
an initial movement. New products snapshot initial stock at creation. Thus a
full configured window must elapse after migration/creation before qualification.
Changing to a longer window may temporarily suppress/resolve rapid alerts.
Deploy the migration and new application together with old writers stopped;
all future stock writers must maintain movement history and coverage invariants.
Direct database edits or deleting movement history invalidate these assumptions.
No live database was migrated during development.

## Lifecycle and concurrency

Stock/policy changes evaluate immediately in their transaction. Global settings
changes trigger a paginated sweep after commit, using independent per-product
transactions; failures are logged and retried on the next sweep. A fixed-delay
scheduler runs every five minutes after the prior run completes
(`inventory.alerts.sweep-delay-ms`, default `300000`).
It scans IDs in batches of 100, not all entities at once. Transactions lock the
stock row before settings/alert access; a partial unique index protects one open
alert per `(product, type)`. Scheduler and stock updates serialize on that lock.

ACKNOWLEDGED is still open: continuing signals update metadata without creating
duplicates or resetting acknowledgement. Recovery, disablement, insufficient
coverage, and window expiry resolve only the applicable alert type. A later
signal creates a new alert. Rapid metadata stores baseline/current, effective
percent/window/minimum, and measured percentage. Metadata retains the last
qualifying measurement on resolution. `threshold` remains LOW_STOCK-specific and
is null for RAPID_DROP; `quantity` remains observed quantity.

## Tests

From this directory, with Java 25:

```sh
export JAVA_HOME="$HOME/.jdks/openjdk-25"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -q -Dtest=RapidDropTest test
mvn -q test
RUN_INVENTORY_DATABASE_STARTUP_TEST=1 mvn -q -Dtest=DatabaseStartupTest test
```

The opt-in database test uses only a unique disposable Docker PostgreSQL container,
cached `pgvector/pgvector:pg17`, and explicit test credentials/URLs, never `.env`.
It upgrades V2 data to V3, exercises production services/queries and independent
alert lifecycle, checks concurrent evaluation/mutation and database validation,
and removes its container in `finally`. Kafka listeners remain stopped.
