"""Offline enrollment metadata tests; psycopg and file storage are mocked/isolated."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yolo-service"))

from enrollment import database, sessions


class EnrollmentDatabaseTests(unittest.TestCase):
    def test_upsert_persists_optional_name_and_note(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (7,)
        embedding = [0.0] * 384

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(database.psycopg, "connect", return_value=connection):
            database.save_product_embeddings(
                "SKU-1", [("image-1", embedding)], name="Product one", note="Aisle 2",
            )

        product_sql, product_params = cursor.execute.call_args_list[0].args
        self.assertIn("INSERT INTO products (sku, name, note)", product_sql)
        self.assertIn("COALESCE(EXCLUDED.name, products.name)", product_sql)
        self.assertIn("COALESCE(EXCLUDED.note, products.note)", product_sql)
        self.assertEqual(product_params, ("SKU-1", "Product one", "Aisle 2"))

    def test_omitted_metadata_does_not_clear_existing_hints(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (7,)

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(database.psycopg, "connect", return_value=connection):
            database.save_product_embeddings("SKU-1", [("image-1", [0.0] * 384)])

        _, product_params = cursor.execute.call_args_list[0].args
        self.assertEqual(product_params, ("SKU-1", None, None))


class PreviewSessionMetadataTests(unittest.TestCase):
    def test_session_stores_trimmed_optional_metadata_and_defaults_to_none(self):
        crop = np.zeros((4, 4, 3), dtype=np.uint8)

        first = sessions.create_preview_session(
            sku=" SKU-1 ", crops=[(0, crop)], name=" Product one ", note=" Aisle 2 ",
        )
        second = sessions.create_preview_session(sku="SKU-2", crops=[(0, crop)])

        try:
            self.assertEqual((first.sku, first.name, first.note),
                             ("SKU-1", "Product one", "Aisle 2"))
            self.assertIsNone(second.name)
            self.assertIsNone(second.note)
        finally:
            sessions.delete_preview_session(first.session_id)
            sessions.delete_preview_session(second.session_id)


if __name__ == "__main__":
    unittest.main()
