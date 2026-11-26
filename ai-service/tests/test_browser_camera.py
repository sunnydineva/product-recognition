"""Offline browser recognition transport tests; all model/HTTP boundaries mocked."""
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np


def load_camera():
    mocks = {}
    for name, attribute in [
        ("ultralytics", "YOLO"),
        ("detection.best_crop", "BestCropSaver"),
        ("detection.recognition", "recognize_crop"),
    ]:
        mocks[name] = ModuleType(name)
        setattr(mocks[name], attribute, MagicMock())
    path = Path(__file__).resolve().parents[1] / "yolo-service/camera_control/browser_camera.py"
    spec = importlib.util.spec_from_file_location("browser_camera_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", mocks):
        spec.loader.exec_module(module)
    return module


class BrowserCameraTests(unittest.TestCase):
    def setUp(self):
        self.module = load_camera()
        with patch.object(self.module, "ThreadPoolExecutor"):
            self.session = self.module.BrowserCameraSession()

    def test_sent_then_matched_once_and_drained(self):
        session = self.session
        session.pending_crops[7] = b"jpeg"
        session._submit_recognition(7)
        sent = session._drain_recognition_events()
        self.assertEqual([(e["track_id"], e["status"]) for e in sent], [(7, "sent")])
        self.assertIn("+00:00", sent[0]["time"])
        self.assertEqual(session._drain_recognition_events(), [])
        self.module.recognize_crop.return_value = {
            "status": "matched", "matches": [{"sku": "SKU", "similarity": .85}],
        }
        fn, *args = session.recognition_worker.submit.call_args.args
        fn(*args)
        result = session._drain_recognition_events()[0]
        self.assertEqual((result["track_id"], result["status"], result["sku"],
                          result["similarity"]), (7, "matched", "SKU", .85))
        session.pending_crops[7] = b"again"
        session._submit_recognition(7)
        session.recognition_worker.submit.assert_called_once()
        self.module.recognize_crop.assert_called_once_with(b"jpeg", 7)
        self.assertEqual(session._drain_recognition_events(), [])

    def test_unknown(self):
        self.module.recognize_crop.return_value = {"status": "unknown", "matches": []}
        self.session._recognize_track(b"jpeg", 3)
        event = self.session._drain_recognition_events()[0]
        self.assertEqual((event["track_id"], event["status"]), (3, "unknown"))
        self.assertNotIn("sku", event)

    def test_missing_and_malformed_results_are_errors(self):
        for result in [
            None, {}, [], {"status": "matched", "matches": []},
            {"status": "unknown", "matches": [{}]},
            *[{"status": "matched", "matches": [{"sku": "S", "similarity": value}]}
              for value in [None, True, "0.9", float("nan"), float("inf"), 2]],
            {"status": "matched", "matches": [{"sku": "", "similarity": .9}]},
        ]:
            with self.subTest(result=result), self.assertLogs(level="ERROR"):
                self.module.recognize_crop.return_value = result
                self.session._recognize_track(b"jpeg", 4)
                event = self.session._drain_recognition_events()[0]
                self.assertEqual((event["track_id"], event["status"]), (4, "error"))

    def test_worker_and_submission_exceptions(self):
        self.module.recognize_crop.side_effect = RuntimeError("offline")
        with self.assertLogs(level="ERROR"):
            self.session._recognize_track(b"jpeg", 5)
        self.assertEqual(self.session._drain_recognition_events()[0]["status"], "error")
        self.session.pending_crops[6] = b"jpeg"
        self.session.recognition_worker.submit.side_effect = RuntimeError("closed")
        with self.assertLogs(level="ERROR"):
            self.session._submit_recognition(6)
        self.assertEqual([e["status"] for e in self.session._drain_recognition_events()],
                         ["sent", "error"])
        self.assertIn(6, self.session.submitted_tracks)

    def test_queue_bound_and_sku_bound(self):
        for track_id in range(150):
            self.session._record_recognition(track_id, "sent")
        events = self.session._drain_recognition_events()
        self.assertEqual([e["track_id"] for e in events], list(range(50, 150)))
        self.module.recognize_crop.return_value = {
            "status": "matched", "matches": [{"sku": "S" * 10000, "similarity": .9}],
        }
        self.session._recognize_track(b"jpeg", 1)
        self.assertEqual(len(self.session._drain_recognition_events()[0]["sku"]), 256)

    def test_concurrent_producers_and_drain(self):
        # Keep each batch below the queue limit so loss/duplication is detectable.
        received = []
        with ThreadPoolExecutor(max_workers=4) as workers:
            for batch in range(10):
                futures = [workers.submit(self.session._record_recognition, i, "sent")
                           for i in range(batch * 50, (batch + 1) * 50)]
                received.extend(self.session._drain_recognition_events())
                for future in futures:
                    future.result()
                received.extend(self.session._drain_recognition_events())
        self.assertEqual(sorted(e["track_id"] for e in received), list(range(500)))

    def test_tracking_payload_preserved_and_events_drained(self):
        box = SimpleNamespace(cls=MagicMock(), id=MagicMock(), conf=MagicMock(),
                              xyxy=[np.array([1, 2, 3, 4])])
        box.cls.item.return_value = 0
        box.id.item.return_value = 8
        box.conf.item.return_value = .8765
        self.session.model.names = {0: "bottle"}
        self.session.model.track.return_value = [SimpleNamespace(boxes=[box])]
        self.session.crop_saver.save_if_better.return_value = None
        self.session._record_recognition(2, "unknown")
        with patch.object(self.module.cv2, "imdecode", return_value=np.zeros((10, 20, 3))):
            result = self.session.process_frame(b"jpeg")
            second = self.session.process_frame(b"jpeg")
        self.assertEqual(result["width"], 20)
        self.assertEqual(result["height"], 10)
        self.assertEqual(result["detections"], [{
            "track_id": 8, "class_name": "bottle", "confidence": .876,
            "bbox": [1, 2, 3, 4],
        }])
        self.assertEqual(result["recognition_events"][0]["track_id"], 2)
        self.assertEqual(second["recognition_events"], [])

    def test_missing_crop_not_submitted(self):
        self.session._submit_recognition(99)
        self.session.recognition_worker.submit.assert_not_called()
        self.assertEqual(self.session._drain_recognition_events(), [])

    def test_close_submits_pending_without_delivering_events(self):
        self.session.pending_crops[9] = b"jpeg"
        self.session.close()
        self.session.recognition_worker.submit.assert_called_once()
        self.session.recognition_worker.shutdown.assert_called_once_with(wait=True)
        self.assertEqual(self.session._drain_recognition_events()[0]["status"], "sent")
