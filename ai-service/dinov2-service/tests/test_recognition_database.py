"""Offline repository tests; psycopg connections are mocked."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recognition import database


class RecognitionDatabaseTests(unittest.TestCase):
    def test_similarity_results_include_optional_name_and_note(self):
        connection = unittest.mock.MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            (7, "SKU-1", "Product one", "Aisle 2", 0.91),
            (8, "SKU-2", None, None, 0.82),
        ]

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(database.psycopg, "connect", return_value=connection):
            result = database.find_similar_products([0.0] * 384, limit=2)

        self.assertEqual(result, [
            {
                "product_id": 7,
                "sku": "SKU-1",
                "name": "Product one",
                "note": "Aisle 2",
                "similarity": 0.91,
            },
            {
                "product_id": 8,
                "sku": "SKU-2",
                "name": None,
                "note": None,
                "similarity": 0.82,
            },
        ])
        sql, params = cursor.execute.call_args.args
        self.assertIn("p.name", sql)
        self.assertIn("p.note", sql)
        self.assertEqual(params[1], 2)


if __name__ == "__main__":
    unittest.main()
