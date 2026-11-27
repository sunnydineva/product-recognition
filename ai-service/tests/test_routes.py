"""Offline route contracts; no models, cameras, database, Kafka or HTTP services."""

import asyncio
import ast
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOST = "ai-product-recognition.my-expenses.xyz"
DINO = {
    "/api/recognition/health": ("get", ["/health", "/recognize/health"]),
    "/api/recognition/encode": ("post", ["/encode"]),
    "/api/recognition/recognize": ("post", ["/recognize"]),
    "/api/recognition/catalog/skus": ("get", ["/catalog/skus"]),
    "/api/recognition/catalog/{sku}/images": ("post", ["/catalog/{sku}/images"]),
    "/api/recognition/settings": ("get", []),
}
YOLO = {
    **{f"/api/yolo/{name}": ("post", [f"/{name}"])
       for name in ("detect", "track", "track-video")},
    "/api/yolo/health": ("get", ["/health"]),
    "/api/yolo/names": ("get", ["/yolo-names"]),
    **{f"/api/yolo/products/{name}": (method, [f"/api/products/{name}"])
       for name, method in (("preview", "post"), ("approve", "post"),
                            ("db-status/{sku}", "get"))},
    **{f"/api/yolo/camera/{name}": (method, [f"/camera/{name}"])
       for name, method in (("status", "get"), ("start", "post"),
                            ("stop", "post"), ("stream", "get"), ("ws", "websocket"))},
}


def stub(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_api(service):
    """Import actual route modules while replacing only external boundaries."""
    mocks = {
        "events.kafka_producer": stub("events.kafka_producer", get_producer=MagicMock()),
    }
    if service == "dinov2-service":
        mocks.update({
            "dinov2_encoder": stub("dinov2_encoder", get_encoder=MagicMock(),
                                  InvalidImageError=type("InvalidImageError", (ValueError,), {})),
            "recognition.database": stub("recognition.database", find_similar_products=MagicMock()),
        })
    else:
        mocks.update({
            "ultralytics": stub("ultralytics", YOLO=MagicMock()),
            "enrollment.database": stub("enrollment.database",
                                       save_product_embeddings=MagicMock(),
                                       count_product_embeddings=MagicMock(return_value=2)),
            "camera_control.manager": stub("camera_control.manager", camera_manager=MagicMock()),
            "camera_control.browser_camera": stub(
                "camera_control.browser_camera", BrowserCameraSession=MagicMock()),
        })
    spec = importlib.util.spec_from_file_location(
        service.replace("-", "_") + "_route_test", ROOT / service / "api.py")
    api = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, mocks), patch.object(sys, "path", [str(ROOT / service), *sys.path]), \
         patch("dotenv.load_dotenv"):
        spec.loader.exec_module(api)
        # Keep references before patch.dict restores imported modules.
        api.test_modules = dict(sys.modules)
    return api


class RouteTests(unittest.TestCase):
    def test_yolo_loads_root_env_before_service_imports(self):
        source = (ROOT / "yolo-service" / "api.py").read_text()
        tree = ast.parse(source)
        boundary = next(i for i, node in enumerate(tree.body)
                        if isinstance(node, ast.ImportFrom) and node.module == "fastapi")
        bootstrap = ast.Module(body=tree.body[:boundary], type_ignores=[])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "ai-service" / "yolo-service" / "api.py"
            entry.parent.mkdir(parents=True)
            entry.touch()
            (root / ".env").write_text("DINOV2_RECOGNIZE_URL=http://fixture/api/recognition/recognize\n")
            with patch.dict(os.environ, {}, clear=True):
                exec(compile(bootstrap, str(entry), "exec"), {"__file__": str(entry)})
                self.assertEqual(os.environ["DINOV2_RECOGNIZE_URL"],
                                 "http://fixture/api/recognition/recognize")
                os.environ["DINOV2_RECOGNIZE_URL"] = "http://explicit-override"
                exec(compile(bootstrap, str(entry), "exec"), {"__file__": str(entry)})
                self.assertEqual(os.environ["DINOV2_RECOGNIZE_URL"], "http://explicit-override")

    @classmethod
    def setUpClass(cls):
        cls.dino = load_api("dinov2-service")
        cls.yolo = load_api("yolo-service")

    def test_schema_canonical_only_and_alias_handlers(self):
        all_ids = []
        for api, expected in ((self.dino, DINO), (self.yolo, YOLO)):
            schema = api.app.openapi()
            self.assertEqual(set(schema["paths"]),
                             {p for p, (m, _) in expected.items() if m != "websocket"})
            # Newer FastAPI retains included routers lazily rather than flattening.
            route_sources = list(api.app.routes)
            if api is self.yolo:
                route_sources += api.enrollment_router.routes + api.camera_router.routes
            routes = {r.path: r for r in route_sources if hasattr(r, "path")}
            for path, (method, aliases) in expected.items():
                for alias in aliases:
                    self.assertIs(routes[path].endpoint, routes[alias].endpoint)
                    if method != "websocket":
                        self.assertEqual(routes[path].methods, routes[alias].methods)
                        self.assertFalse(routes[alias].include_in_schema)
                if method != "websocket":
                    self.assertIn(method, schema["paths"][path])
            all_ids += [operation["operationId"] for item in schema["paths"].values()
                        for operation in item.values()]
            for path, methods in schema["paths"].items():
                for operation in methods.values():
                    self.assertTrue(operation.get("summary"), path)
                    self.assertTrue(operation.get("description"), path)
                    self.assertTrue(operation.get("tags"), path)
        self.assertEqual(len(all_ids), len(set(all_ids)))
        schema = self.dino.app.openapi()["paths"]
        self.assertEqual(set(schema["/api/recognition/settings"]), {"get", "patch"})
        for path in ("/api/recognition/catalog/skus", "/api/recognition/catalog/{sku}/images"):
            self.assertTrue(next(iter(schema[path].values()))["deprecated"])

    def test_docs_health_and_slashes(self):
        for api, prefix, health in ((self.dino, "/recognize", "/api/recognition/health"),
                                    (self.yolo, "/yolo", "/api/yolo/health")):
            with TestClient(api.app) as client:
                for path in (health, "/health"):
                    self.assertEqual(client.get(path).json(), {"status": "ok"})
                for path in (prefix + "/docs", "/docs", prefix + "/redoc", "/redoc"):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(prefix + "/openapi.json", response.text)
                self.assertEqual(client.get("/openapi.json").json(),
                                 client.get(prefix + "/openapi.json").json())
                for path in (prefix + "/docs/oauth2-redirect", "/docs/oauth2-redirect"):
                    self.assertEqual(client.get(path).status_code, 200)
                response = client.get(health + "/", follow_redirects=False)
                self.assertEqual(response.status_code, 307)
                self.assertTrue(response.headers["location"].endswith(health))
                self.assertEqual(client.get("/api/unknown").status_code, 404)

    def test_all_upload_aliases_dispatch_without_redirect(self):
        # Missing multipart/body input validates without any business side effects.
        for api, expected in ((self.dino, DINO), (self.yolo, YOLO)):
            with TestClient(api.app) as client:
                for path, (method, aliases) in expected.items():
                    if method != "post" or "/camera/" in path:
                        continue
                    for candidate in (path, *aliases):
                        response = client.post(candidate.replace("{sku}", "test"),
                                               follow_redirects=False)
                        self.assertEqual(response.status_code, 422, candidate)

    def test_dino_alias_payloads_without_external_io(self):
        api = self.dino
        embedding = MagicMock()
        embedding.__len__.return_value = 1
        embedding.tolist.return_value = [1.0]
        api.get_encoder.return_value.encode.return_value = embedding
        api.find_similar_products.return_value = []
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(api, "CATALOG_DIR", Path(directory)), \
             patch.object(api, "get_min_similarity", return_value=0.3), \
             TestClient(api.app) as client:
            (Path(directory) / "test").mkdir()
            for path, (_, aliases) in DINO.items():
                if path.endswith("/settings") or path.endswith("/health"):
                    continue
                responses = []
                for candidate in (path, *aliases):
                    candidate = candidate.replace("{sku}", "test")
                    if path.endswith("/skus"):
                        response = client.get(candidate)
                    else:
                        response = client.post(candidate, files={"file": ("test.jpg", b"mock")})
                    self.assertEqual(response.status_code, 200)
                    responses.append(response.json())
                self.assertTrue(all(value == responses[0] for value in responses))
        api.get_producer.assert_not_called()

    def test_yolo_camera_http_ws_and_db_aliases_mocked(self):
        api = self.yolo
        camera = api.test_modules["camera_control.router"]
        manager = camera.camera_manager
        manager.status.return_value = {"status": "stopped"}
        manager.start.return_value = {"status": "mock-start"}
        manager.stop.return_value = {"status": "mock-stop"}
        camera.BrowserCameraSession.return_value.process_frame.return_value = {"tracks": []}
        api.modelYolo.names = {0: "test"}
        with TestClient(api.app) as client:
            for path, (method, aliases) in YOLO.items():
                if method == "post" and "/camera/" not in path:
                    continue
                for candidate in (path, *aliases):
                    candidate = candidate.replace("{sku}", "test")
                    if method == "websocket":
                        with client.websocket_connect(candidate) as ws:
                            ws.send_bytes(b"mock-frame")
                            self.assertEqual(ws.receive_json(), {"tracks": []})
                    else:
                        response = client.request(method, candidate, follow_redirects=False)
                        self.assertEqual(response.status_code, 200, candidate)
                        if candidate.endswith("/stream"):
                            self.assertIn("multipart/x-mixed-replace", response.headers["content-type"])
        self.assertEqual(camera.BrowserCameraSession.return_value.close.call_count, 2)

    def test_frontend_served_urls(self):
        with TestClient(self.yolo.app) as client:
            for path in ("/enroll", "/camera", "/enroll.js", "/camera.js"):
                self.assertEqual(client.get(path).status_code, 200)
            enroll_page = client.get("/enroll").text
            camera_page = client.get("/camera").text
            enroll = client.get("/enroll.js").text
            camera = client.get("/camera.js").text
        for suffix in ("preview", "approve", "db-status/"):
            self.assertIn("/api/yolo/products/" + suffix, enroll)
        self.assertNotIn("/api/products/", enroll)
        self.assertIn("${protocol}//${location.host}/api/yolo/camera/ws", camera)
        self.assertIn('location.protocol === "https:"', camera)
        self.assertIn('id="name"', enroll_page)
        self.assertIn('id="note"', enroll_page)
        for heading in ("Track ID", "SKU", "Име", "Бележка", "Сходство (%)", "Статус", "Час"):
            self.assertIn(f"<th scope=\"col\">{heading}</th>", camera_page)

    def test_enrollment_preview_and_approve_accept_optional_metadata(self):
        routes = self.yolo.test_modules["enrollment.routes"]
        crop = np.zeros((8, 8, 3), dtype=np.uint8)
        product = SimpleNamespace(crop=crop, bbox=(0, 0, 8, 8), score=0.9)
        item = SimpleNamespace(
            timestamp_ms=120, product=product, sharpness=2.0,
            brightness=3.0, quality_score=0.8,
        )
        frame = SimpleNamespace(image=crop, timestamp_ms=120)
        session = SimpleNamespace(
            session_id="session-1", sku="SKU-1", name="Product one",
            note="Aisle 2", images=[SimpleNamespace(image_id="image-1")],
        )

        with patch.object(routes, "extract_frames", return_value=[frame]), \
             patch.object(routes, "localize_product", return_value=product), \
             patch.object(routes, "select_best_crops", return_value=[item]), \
             patch.object(routes, "create_preview_session", return_value=session) as create, \
             TestClient(self.yolo.app) as client:
            response = client.post(
                "/api/yolo/products/preview",
                files={"video": ("clip.webm", b"video")},
                data={"sku": " SKU-1 ", "name": " Product one ", "note": " Aisle 2 "},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(create.call_args.kwargs["sku"], "SKU-1")
        self.assertEqual(create.call_args.kwargs["name"], "Product one")
        self.assertEqual(create.call_args.kwargs["note"], "Aisle 2")

        embeddings = [("image-1", [0.0] * 384)]
        producer = MagicMock()
        with patch.object(routes, "load_approved_images",
                          return_value=(session, [MagicMock()])), \
             patch.object(routes, "generate_embeddings",
                          AsyncMock(return_value=embeddings)), \
             patch.object(routes, "save_product_embeddings") as save, \
             patch.object(routes, "get_producer", return_value=producer), \
             TestClient(self.yolo.app) as client:
            response = client.post(
                "/api/yolo/products/approve",
                json={
                    "session_id": "session-1", "image_ids": ["image-1"],
                    "name": " Updated name ", "note": " Updated note ",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        save.assert_called_once_with(
            "SKU-1", embeddings, name="Updated name", note="Updated note",
        )
        producer.send_product_creation.assert_called_once_with(
            name="Updated name", barcode="SKU-1", initial_quantity=0,
            note="Updated note",
        )

        producer.reset_mock()
        with patch.object(routes, "load_approved_images",
                          return_value=(SimpleNamespace(
                              sku="SKU-2", name=None, note="Session note"), [])), \
             patch.object(routes, "generate_embeddings", AsyncMock(return_value=[])), \
             patch.object(routes, "save_product_embeddings") as save, \
             patch.object(routes, "get_producer", return_value=producer), \
             TestClient(self.yolo.app) as client:
            response = client.post(
                "/api/yolo/products/approve",
                json={"session_id": "session-2", "image_ids": ["image-1"]},
            )

        self.assertEqual(response.status_code, 200, response.text)
        save.assert_called_once_with(
            "SKU-2", [], name=None, note="Session note",
        )
        producer.send_product_creation.assert_called_once_with(
            name="SKU-2", barcode="SKU-2", initial_quantity=0, note="Session note",
        )

    def test_enrollment_encoder_url_and_dimension(self):
        encoder = self.yolo.test_modules["enrollment.dinov2_client"]
        image = MagicMock()
        image.name = "test.png"
        image.read_bytes.return_value = b"offline"
        response = MagicMock()
        response.json.return_value = {"embedding": [0.0] * 384}
        client = AsyncMock()
        client.post.return_value = response
        with patch.object(encoder, "DINOV2_URL", "http://custom.internal:1234/base/"), \
             patch.object(encoder.httpx, "AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            self.assertEqual(len(asyncio.run(encoder.encode_image(image))), 384)
            client.post.assert_awaited_once_with(
                "http://custom.internal:1234/base/api/recognition/encode",
                files={"file": ("test.png", b"offline", "image/png")},
            )
            response.raise_for_status.assert_called_once()


class IngressTests(unittest.TestCase):
    def test_bounded_ingress_routing(self):
        rules = yaml.safe_load((ROOT / "cloudflared/config.yml").read_text())["ingress"]
        self.assertEqual(rules[-1], {"service": "http_status:404"})
        self.assertTrue(all(rule.get("hostname") == HOST and "path" in rule
                            for rule in rules[:-1]))

        def route(path, hostname=HOST):
            for rule in rules:
                if "hostname" not in rule:
                    return rule["service"]
                if hostname == rule["hostname"] and re.search(rule["path"], path):
                    return rule["service"]

        for mapping, port, prefix in ((DINO, 18102, "/recognize"), (YOLO, 18101, "/yolo")):
            paths = [p for p, (_, aliases) in mapping.items() for p in (p, *aliases)]
            paths += [prefix + suffix for suffix in
                      ("/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc")]
            for path in paths:
                path = path.replace("{sku}", "test-sku")
                target = 18101 if path == "/health" else port
                for suffix in ("", "/"):
                    self.assertEqual(route(path + suffix), f"http://127.0.0.1:{target}", path)
        for path in ("/enroll", "/enroll.js", "/camera", "/camera.js", "/docs",
                     "/docs/oauth2-redirect", "/openapi.json", "/redoc"):
            self.assertEqual(route(path), "http://127.0.0.1:18101")
        for path in ("/api/inventory/ui/", "/api/inventory/v1/products",
                     "/api/inventory/v3/api-docs", "/api/inventory/swagger-ui/index.html"):
            self.assertEqual(route(path), "http://127.0.0.1:8080")
        for path in ("/", "/anything", "/api/yolo/unknown", "/recognize/unknown",
                     "/api/recognition/unknown", "/api/yolo/detect/extra",
                     "/camera/ws/extra", "/api/products/preview/session", "/catalog/a/b/images",
                     "/api/recognition/catalog/a/b/images", "/enrollXjs", "/health//"):
            self.assertEqual(route(path), "http_status:404", path)
        self.assertEqual(route("/api/yolo/health", "other.example"), "http_status:404")


if __name__ == "__main__":
    unittest.main()
