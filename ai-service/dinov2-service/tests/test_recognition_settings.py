"""Offline HTTP/repository tests: no dotenv, model, Kafka or database connections."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recognition import settings


def load_api():
    encoder = ModuleType("dinov2_encoder")
    encoder.get_encoder = MagicMock()
    encoder.InvalidImageError = type("InvalidImageError", (ValueError,), {})
    database = ModuleType("recognition.database")
    database.find_similar_products = MagicMock()
    producer = ModuleType("events.kafka_producer")
    producer.get_producer = MagicMock()
    spec = importlib.util.spec_from_file_location(
        "recognition_api_under_test", Path(__file__).resolve().parents[1] / "api.py"
    )
    api = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "dinov2_encoder": encoder,
        "recognition.database": database,
        "events.kafka_producer": producer,
    }), patch("dotenv.load_dotenv"):
        spec.loader.exec_module(api)
    return api


class RecognitionHttpTests(unittest.TestCase):
    def setUp(self):
        self.api = load_api()
        self.client = TestClient(self.api.app)
        self.api.get_encoder.return_value.encode.return_value.tolist.return_value = [1.0]

    def test_health_routes_and_swagger_path(self):
        for path in ("/health", "/recognize/health", "/api/recognition/health"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})
        paths = self.client.get("/recognize/openapi.json").json()["paths"]
        self.assertIn("/api/recognition/health", paths)
        self.assertNotIn("/recognize/health", paths)
        self.assertNotIn("/health", paths)

    def test_settings_get_patch_and_subsequent_read(self):
        # Simulated persistent database state, not a service-side cache.
        state = [0.30]
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value

        def execute(sql, params=None):
            if params:
                state[0] = params[0]

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = lambda: (state[0],)
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(settings.psycopg, "connect") as connect:
            connect.return_value.__enter__.return_value = connection
            self.assertEqual(self.client.get("/api/recognition/settings").json(),
                             {"minSimilarity": 0.30})
            response = self.client.patch("/api/recognition/settings", json={"minSimilarity": 0.20})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"minSimilarity": 0.20})
            # A newly constructed app also reads the persisted value.
            with TestClient(load_api().app) as restarted:
                self.assertEqual(restarted.get("/api/recognition/settings").json(),
                                 {"minSimilarity": 0.20})
            self.assertEqual(connect.call_count, 3)

    def test_patch_validation(self):
        with patch.object(self.api, "set_min_similarity") as write:
            for body in ["{}", '{"minSimilarity":null}', '{"minSimilarity":true}',
                         '{"minSimilarity":"0.2"}', '{"minSimilarity":-0.01}',
                         '{"minSimilarity":1.01}', '{"minSimilarity":NaN}',
                         '{"minSimilarity":Infinity}', '{"minSimilarity":-Infinity}',
                         '{"minSimilarity":0.2,"productId":1}']:
                with self.subTest(body=body):
                    response = self.client.patch(
                        "/api/recognition/settings", content=body,
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(response.status_code, 422)
            write.assert_not_called()
            for value in [0, 1, 0.20]:
                write.return_value = value
                self.assertEqual(self.client.patch(
                    "/api/recognition/settings", json={"minSimilarity": value}
                ).status_code, 200)

    def test_recognition_threshold_and_invalid_candidates(self):
        for threshold, score, accepted in [
            (0.30, 0.2999, False), (0.30, 0.30, True), (0.30, 0.31, True),
            (0.20, 0.20, True), (0.20, 0.1999, False),
            (0.30, float("nan"), False), (0.30, float("inf"), False),
            (0.30, float("-inf"), False), (0.30, True, False),
            (0.30, "0.9", False), (0.30, None, False),
        ]:
            with self.subTest(threshold=threshold, score=score):
                candidate = {"product_id": 7, "sku": "test", "similarity": score}
                self.api.find_similar_products.return_value = [candidate]
                self.api.get_producer.reset_mock()
                with patch.object(self.api, "get_min_similarity", return_value=threshold):
                    response = self.client.post("/api/recognition/recognize", files={"file": ("image.jpg", b"image")})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    "status": "matched" if accepted else "unknown",
                    "matches": [candidate] if accepted else [],
                })
                if accepted:
                    self.api.get_producer.return_value.send_stock_adjustment.assert_called_once_with(
                        product_id=7, quantity=1, operation="DECREASE", note="recognized via dinov2"
                    )
                else:
                    self.api.get_producer.assert_not_called()
        for matches in [[], [{"product_id": 7}]]:
            self.api.find_similar_products.return_value = matches
            self.api.get_producer.reset_mock()
            with patch.object(self.api, "get_min_similarity", return_value=0.30):
                response = self.client.post("/api/recognition/recognize", files={"file": ("image.jpg", b"image")})
            self.assertEqual(response.json(), {"status": "unknown", "matches": []})
            self.api.get_producer.assert_not_called()

    def test_settings_failures_are_503_and_no_stock_event(self):
        with patch.object(self.api, "get_min_similarity", side_effect=settings.SettingsUnavailableError), \
             patch.object(self.api, "set_min_similarity", side_effect=settings.SettingsUnavailableError):
            self.assertEqual(self.client.get("/api/recognition/settings").status_code, 503)
            self.assertEqual(self.client.patch(
                "/api/recognition/settings", json={"minSimilarity": 0.2}
            ).status_code, 503)
            self.assertEqual(self.client.post(
                "/api/recognition/recognize", files={"file": ("image.jpg", b"image")}
            ).status_code, 503)
        self.api.get_encoder.assert_not_called()
        self.api.find_similar_products.assert_not_called()
        self.api.get_producer.assert_not_called()

    def test_encode_and_catalog_add_do_not_read_settings(self):
        embedding = MagicMock()
        embedding.__len__.return_value = 1
        embedding.tolist.return_value = [1.0]
        self.api.get_encoder.return_value.encode.return_value = embedding
        with patch.object(self.api, "get_min_similarity", side_effect=AssertionError):
            response = self.client.post("/api/recognition/encode", files={"file": ("image.jpg", b"image")})
            self.assertEqual(response.json(), {"embedding_dimension": 1, "embedding": [1.0]})
            response = self.client.post("/api/recognition/catalog/test/images", files={"file": ("image.jpg", b"image")})
            self.assertEqual(response.json(), {"status": "todo", "sku": "test"})
        self.api.get_producer.assert_not_called()


class SettingsRepositoryTests(unittest.TestCase):
    def test_read_rejects_missing_and_invalid_persisted_value(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(settings.psycopg, "connect") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            for row in [None, (None,), (True,), ("0.3",), (float("nan"),), (float("inf"),), (-1,), (1.1,)]:
                cursor.fetchone.return_value = row
                with self.subTest(row=row), self.assertRaises(settings.SettingsUnavailableError):
                    settings.get_min_similarity()

    def test_connection_and_commit_failures_do_not_report_success(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://offline"}), \
             patch.object(settings.psycopg, "connect") as connect:
            connect.side_effect = psycopg.OperationalError("offline")
            for operation in [settings.get_min_similarity, lambda: settings.set_min_similarity(0.2)]:
                with self.assertRaises(settings.SettingsUnavailableError):
                    operation()
            connect.side_effect = None
            connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = (0.2,)
            connect.return_value.__exit__.side_effect = psycopg.OperationalError("commit failed")
            with self.assertRaises(settings.SettingsUnavailableError):
                settings.set_min_similarity(0.2)

    def test_invalid_writes_do_not_connect(self):
        with patch.object(settings.psycopg, "connect") as connect:
            for value in [None, True, "0.2", float("nan"), float("inf"), -0.1, 1.1]:
                with self.assertRaises(ValueError):
                    settings.set_min_similarity(value)
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
