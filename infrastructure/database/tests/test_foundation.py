"""Offline guards; opt-in Docker tests use only a disposable, network-isolated DB."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[3]
INFRA = ROOT / "infrastructure/database"
AI = ROOT / "ai-service/database/migrations"
INVENTORY = ROOT / "backend/inventory-service/src/main/resources/db/migration"


class ProvisioningGuardsTest(unittest.TestCase):
    def run_script(self, args, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "calls"
            fake = Path(directory) / "psql"
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\nexit "${PSQL_EXIT:-0}"\n')
            fake.chmod(0o700)
            env = {
                "PATH": f"{directory}:/usr/bin:/bin", "CALLS": str(log),
                "POSTGRES_USER": "legacy_owner", "POSTGRES_DB": "product_recognition",
                "INVENTORY_DB": "inventory", "INVENTORY_DB_USER": "inventory_service",
                "INVENTORY_DB_PASSWORD": "secret'with quotes",
                **overrides,
            }
            result = subprocess.run(
                ["sh", str(INFRA / "provision.sh"), *args], env=env,
                capture_output=True, text=True,
            )
            return result, log.read_text() if log.exists() else ""

    def test_opt_in_required(self):
        result, calls = self.run_script([])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")

    def test_invalid_configuration_never_calls_database(self):
        for overrides in [
            {"INVENTORY_DB": "product_recognition"},
            {"INVENTORY_DB": "postgres"},
            {"INVENTORY_DB_USER": "legacy_owner"},
            {"INVENTORY_DB": "bad;DROP"},
            {"INVENTORY_DB": "a" * 64},
            {"INVENTORY_DB_PASSWORD": ""},
            {"AI_DB_USER": "inventory_service"},
        ]:
            with self.subTest(overrides=overrides):
                result, calls = self.run_script(["--existing"], **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, "")

    def test_existing_never_runs_ai_initialization_or_exposes_password(self):
        result, calls = self.run_script(["--existing"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("provision-inventory.sql", calls)
        self.assertNotIn("provision-ai-fresh.sql", calls)
        self.assertNotIn("secret", calls + result.stdout + result.stderr)

    def test_fresh_requires_separate_ai_role(self):
        for overrides in [{}, {"AI_DB_USER": "legacy_owner", "AI_DB_PASSWORD": "test"}]:
            result, calls = self.run_script(["--fresh"], **overrides)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, "")

    def test_provisioning_failure_stops_before_ai_initialization(self):
        result, calls = self.run_script(
            ["--fresh"], AI_DB_USER="ai_service", AI_DB_PASSWORD="test", PSQL_EXIT="3"
        )
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("provision-ai-fresh.sql", calls)


@unittest.skipUnless(os.environ.get("RUN_ISOLATED_POSTGRES_TESTS") == "1",
                     "Set RUN_ISOLATED_POSTGRES_TESTS=1; requires cached pgvector:pg17 and Docker")
class IsolatedPostgresTest(unittest.TestCase):
    @classmethod
    def docker(cls, *args, check=True, input=None):
        return subprocess.run(["docker", *args], input=input, capture_output=True,
                              text=True, check=check)

    @classmethod
    def setUpClass(cls):
        cls.container = "database-foundation-test-" + uuid.uuid4().hex
        cls.addClassCleanup(lambda: cls.docker("rm", "-fv", cls.container, check=False))
        cls.docker(
            "run", "--detach", "--pull=never", "--name", cls.container,
            "--network=none", "--tmpfs", "/var/lib/postgresql/data",
            "--mount", f"type=bind,src={INFRA},dst=/opt/database,readonly",
            "--mount", f"type=bind,src={INFRA / 'init-fresh.sh'},dst=/docker-entrypoint-initdb.d/10-services.sh,readonly",
            "-e", "POSTGRES_USER=foundation_admin", "-e", "POSTGRES_PASSWORD=test_admin",
            "-e", "POSTGRES_DB=product_recognition",
            "-e", "AI_DB_USER=ai_service", "-e", "AI_DB_PASSWORD=test_ai",
            "-e", "INVENTORY_DB=inventory", "-e", "INVENTORY_DB_USER=inventory_service",
            "-e", "INVENTORY_DB_PASSWORD=test_inventory",
            "pgvector/pgvector:pg17",
        )
        for _ in range(120):
            ready = cls.docker("exec", cls.container, "pg_isready", "-h", "127.0.0.1",
                               "-U", "foundation_admin", "-d", "postgres", check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(cls.docker("logs", cls.container).stdout)
        cls.sql("product_recognition", (AI / "V1__create_product_embedding_tables.sql").read_text(),
                user="ai_service", password="test_ai")
        cls.sql("product_recognition", "INSERT INTO products(sku) VALUES ('old'), ('unlinked');")
        cls.sql("product_recognition", """
            INSERT INTO product_embeddings(product_id, image_id, embedding)
            SELECT id, '00000000-0000-0000-0000-000000000001',
                   array_fill(0.1::real, ARRAY[384])::vector
            FROM products WHERE sku='old';
        """)
        cls.sql("product_recognition", (AI / "V2__link_inventory_product.sql").read_text(),
                user="ai_service", password="test_ai")
        cls.sql("inventory", (INVENTORY / "V1__create_inventory_catalog.sql").read_text(),
                user="inventory_service", password="test_inventory")

    @classmethod
    def sql(cls, database, sql, user="foundation_admin", password="test_admin", check=True):
        return cls.docker("exec", "-i", "-e", f"PGPASSWORD={password}", cls.container,
                          "psql", "-X", "-h", "127.0.0.1", "-U", user, "-d", database,
                          "-v", "ON_ERROR_STOP=1", "-At", input=sql, check=check)

    def test_additive_ai_link_constraints(self):
        self.assertEqual(self.sql("product_recognition",
            "SELECT count(*) FROM products WHERE inventory_product_id IS NULL;").stdout.strip(), "2")
        self.sql("product_recognition", "UPDATE products SET inventory_product_id=42 WHERE sku='old';")
        for statement in [
            "UPDATE products SET inventory_product_id=42 WHERE sku='unlinked';",
            "UPDATE products SET inventory_product_id=0 WHERE sku='unlinked';",
            "UPDATE products SET inventory_product_id=-1 WHERE sku='unlinked';",
        ]:
            self.assertNotEqual(self.sql("product_recognition", statement, check=False).returncode, 0)
        self.assertEqual(self.sql("product_recognition",
            "SELECT id FROM products WHERE sku='old';").stdout.strip(), "1")
        self.assertEqual(self.sql("product_recognition",
            "SELECT product_id FROM product_embeddings;").stdout.strip(), "1")

    def test_stock_and_catalog_constraints(self):
        self.sql("inventory", "INSERT INTO products(sku,name) VALUES ('item','Item'); "
                 "INSERT INTO stock(product_id) SELECT id FROM products WHERE sku='item';")
        self.assertEqual(self.sql("inventory", "SELECT quantity FROM stock;").stdout.strip(), "0")
        for statement in [
            "UPDATE stock SET quantity=-1;",
            "INSERT INTO stock(product_id) VALUES (999999);",
            "INSERT INTO stock(product_id) SELECT id FROM products;",
            "INSERT INTO products(sku,name) VALUES ('item','Duplicate');",
            "INSERT INTO products(sku) VALUES ('missing_name');",
            "DELETE FROM products;",
        ]:
            self.assertNotEqual(self.sql("inventory", statement, check=False).returncode, 0)
        self.sql("inventory", "UPDATE stock SET quantity=2147483648;")

    def test_service_roles_cannot_connect_to_other_database(self):
        for db, user, password in [
            ("inventory", "ai_service", "test_ai"),
            ("product_recognition", "inventory_service", "test_inventory"),
        ]:
            self.assertNotEqual(self.sql(db, "SELECT 1;", user, password, check=False).returncode, 0)

    def test_existing_provision_is_repeatable_without_password_rotation(self):
        for _ in range(2):
            self.docker("exec", "-e", "INVENTORY_DB_PASSWORD=not_a_rotation", self.container,
                        "sh", "/opt/database/provision.sh", "--existing")
        self.sql("inventory", "SELECT 1;", "inventory_service", "test_inventory")
        self.assertEqual(self.sql("product_recognition",
            "SELECT count(*) FROM products;").stdout.strip(), "2")

    def test_refuses_foreign_database_and_privileged_role(self):
        self.sql("postgres", "CREATE DATABASE unrelated; CREATE ROLE unsafe_role LOGIN CREATEDB;")
        for settings in [
            ["-e", "INVENTORY_DB=unrelated"],
            ["-e", "INVENTORY_DB=must_not_be_created", "-e", "INVENTORY_DB_USER=unsafe_role"],
        ]:
            result = self.docker("exec", *settings, self.container,
                                 "sh", "/opt/database/provision.sh", "--existing", check=False)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.sql("postgres",
            "SELECT count(*) FROM pg_database WHERE datname='must_not_be_created';").stdout.strip(), "0")
        self.assertEqual(self.sql("postgres",
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='unrelated';").stdout.strip(),
            "foundation_admin")

    def test_existing_legacy_ai_owner_and_data_unchanged(self):
        self.sql("postgres", "CREATE DATABASE legacy_ai OWNER foundation_admin;")
        self.sql("legacy_ai", "CREATE TABLE sentinel(value TEXT); INSERT INTO sentinel VALUES ('keep');")
        self.docker("exec", "-e", "POSTGRES_DB=legacy_ai", "-e", "AI_DB_USER=",
                    "-e", "INVENTORY_DB=another_inventory", "-e", "INVENTORY_DB_USER=another_inventory",
                    "-e", "INVENTORY_DB_PASSWORD=quote'and\\slash", self.container,
                    "sh", "/opt/database/provision.sh", "--existing")
        self.assertEqual(self.sql("legacy_ai", "SELECT value FROM sentinel;").stdout.strip(), "keep")
        self.assertEqual(self.sql("postgres",
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='legacy_ai';").stdout.strip(),
            "foundation_admin")
        self.sql("another_inventory", "SELECT 1;", "another_inventory", "quote'and\\slash")


if __name__ == "__main__":
    unittest.main()
