# Database foundation (infrastructure-owned)

Infrastructure owns the **single** `pgvector/pgvector:pg17` server and its
`postgres_data` volume. Compose lives at repository-root `docker-compose.yml`,
with `name: ai-service` preserving the existing project and volume identity.
Keep that project name and volume; never use `down -v`
to upgrade. AI owns its existing database (default `product_recognition`) and
`ai-service/database/migrations`; inventory owns `inventory` and
`backend/inventory-service/src/main/resources/db/migration`. There are no
cross-database foreign keys. Each database has its own Flyway history.

## Fresh volume

Set real, distinct passwords in the untracked repository-root `.env` using
the root `.env.example` as the template. The example values are placeholders.
`POSTGRES_USER` is the infrastructure administrator, **not** a fresh service
login. Set `AI_DB_USER`/`AI_DB_PASSWORD` and inventory credentials separately;
set AI `DATABASE_URL` consistently (URL-encode password characters).
Identifiers in provisioning must be lowercase SQL identifiers, at most 63 bytes.

From repository root, use the established Compose project:

```sh
docker compose up -d postgres
docker compose run --rm flyway
docker compose up -d inventory-service
```

The image initializes only empty volumes. Infrastructure creates the service
roles/databases and preinstalls vector as administrator. AI Flyway can then run
V1/V2 as the AI database owner without superuser privileges. Inventory Boot
Flyway runs its independent V1 at application startup; JPA only validates,
never creates/updates tables. Application SQL and migrations currently share
each service's database-owner login; separate runtime/migrator grants are a
future hardening step. Inventory joins the default database network **and**
external `shared-net` for Kafka/schema registry; that external network must
already exist. PostgreSQL is exposed on loopback only.

## Existing volume: deliberate provisioning, not automatic conversion

1. Back up the databases and verify restore procedures. Record the actual
   cluster administrator, AI database owner, application login, Compose project,
   and volume. Do not change `POSTGRES_DB`, `POSTGRES_USER`, or the existing
   password to try to rename/migrate the live cluster. Image environment changes
   do **not** change existing roles/passwords/databases.
2. Keep AI `DATABASE_URL` and its existing credentials unchanged. If the legacy
   AI owner is `POSTGRES_USER`, leave `AI_DB_USER` and `AI_DB_PASSWORD` unset/empty
   so AI Flyway retains that login. Do not copy the fresh-volume AI credentials
   blindly. Set the new inventory database, dedicated role and password.
3. After operator approval, recreate just the PostgreSQL container with the same
   volume to load the provisioning mounts/environment, then explicitly provision
   from repository root:

   ```sh
   docker compose up -d postgres
   docker compose exec -T postgres sh /opt/database/provision.sh --existing
   ```

   This path does not initialize, alter ownership of, or migrate the AI database.
   It creates the inventory role/database if absent and restricts its database
   access. It rejects foreign database owners and privileged/member roles.
   Rerunning does **not** reset an existing role's password; supply its actual
   password, or rotate it separately under operator control. A partially failed
   role/database creation can be rerun after review; no DROP is issued.
   Use a dedicated role/name: provisioning is not an adoption mechanism for
   unrelated databases. It requires a real cluster administrator over the
   container's local socket; nonstandard socket authentication may need an
   operator-managed `.pgpass` (never weaken authentication).
4. Review/back up, then explicitly run AI Flyway for V2 and start inventory as
   above. These commands apply schema changes, not catalog/data backfills.
   Do not baseline a populated, unmanaged inventory schema automatically.

The legacy `POSTGRES_USER` created by the image is often a superuser. Retaining
it for AI is compatibility, **not** least privilege or database isolation from
that legacy role. Moving an existing AI database to a dedicated non-superuser
requires a separately reviewed ownership/grant migration, including tables,
identity sequences, Flyway history, extension privileges, and default grants.
Merely granting CONNECT is insufficient for Flyway ALTER TABLE. The fresh
provisioning path must never be run on an existing volume. Existing AI PUBLIC
CONNECT grants are not silently revoked either: inventory receives no explicit
AI object privileges, but operators must audit legacy PUBLIC grants.

## IDs, data and controlled linking

Inventory `products.id` is the canonical global `productId` (positive bigint).
SKU is unique; name required; barcode optional and not assumed globally unique.
`active` supports retirement. `stock` has one optional row per local inventory
product, an FK without cascading delete, and nonnegative bigint `quantity`
defaulting to zero. No stock rows/counts are inferred. Future writers maintain
`updated_at` explicitly; timestamps currently only default on insert.

AI V1 is unchanged. AI `products.id` stays local, including embedding FKs.
V2 adds nullable UNIQUE positive `inventory_product_id`; multiple unresolved
NULLs are allowed. There is deliberately no cross-database FK.

Backfill is **manual and controlled**, not part of provisioning/migrations:
export/review both catalogs, create/approve canonical inventory products through
a separately authorized process, then approve an explicit local-ID-to-canonical-ID
mapping. Verify every target exists, investigate duplicates/conflicts, retain an
audit/rollback mapping, and update only approved rows in an AI transaction.
Never equate numeric IDs, automatically merge by SKU, or invent target IDs.
Uncertain products remain NULL. Cross-database integrity/retirement reconciliation
must be handled by future integration; a database constraint cannot prove the
remote target exists.

**Recognition still returns local `product_id`. Do not send that as canonical
inventory ID.** Adding the link column does not implement runtime linking, stock
operations, REST workflows, UI or alerts. Existing Kafka producer/consumer topic
mismatch and enrollment's `len(embeddings)` stock-count bug are not solved here;
observed/enrollment counts are not authoritative inventory.

## Verification (no live database required)

From repository root:

```sh
python3 -B -m unittest discover -s infrastructure/database/tests -v
RUN_ISOLATED_POSTGRES_TESTS=1 python3 -B -m unittest discover -s infrastructure/database/tests -v
```

The second command requires Docker and an already cached pgvector:pg17 image
(`--pull=never`). It creates a uniquely named, network-isolated container with
tmpfs data, no published ports, and read-only script mounts, then removes it.
It verifies real PostgreSQL constraints, additive AI migration, service isolation,
and provisioning guards/idempotency, not Flyway or Java startup.
No existing Compose service, database or volume is touched.
Java checks: `cd backend/inventory-service && mvn test` (Java 25 and private
Maven artifacts required). Existing AI integration tests read `.env` and connect
to services; they are **not** safe offline foundation checks.

### Opt-in inventory application startup regression

With Java 25, Maven dependencies available, Docker running, and an already cached
`pgvector/pgvector:pg17` image, run from repository root:

```sh
cd backend/inventory-service
RUN_INVENTORY_DATABASE_STARTUP_TEST=1 mvn -B -Dtest=DatabaseStartupTest test
```

Without the environment flag this test is skipped. It boots the actual inventory
application with test-only Kafka listener startup disabled (including the custom
listener factory). It asserts a DataSource bean, successful Flyway V1 history,
`products` and `stock` tables, and stopped Kafka listeners. No new test dependency
is required. The test creates a unique disposable container with tmpfs data and
a random **loopback-only** host port, overrides datasource settings with that
container's address, and removes the container/anonymous volumes in `finally`.
Flyway's connection is also explicitly pinned to that disposable database.
It never reads `.env`, accepts an external database URL, or uses Compose volumes.
Unlike the SQL-only test above, it needs loopback port access from the JVM.
No broker, schema registry, or application HTTP server is started.
If the test JVM is forcibly killed, inspect/remove only the leftover uniquely
named `inventory-startup-test-*` container, never project database volumes.

On this workstation Java 25 is available at `~/.jdks/openjdk-25` (the default
`JAVA_HOME` is Java 21). Select it for this command only, without system changes:

```sh
JAVA_HOME="$HOME/.jdks/openjdk-25" PATH="$HOME/.jdks/openjdk-25/bin:$PATH" \
  RUN_INVENTORY_DATABASE_STARTUP_TEST=1 mvn -B -Dtest=DatabaseStartupTest test
```
