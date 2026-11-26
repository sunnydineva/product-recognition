"""Kafka logging checks with a mocked producer; no broker/registry connections."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock


spec = importlib.util.spec_from_file_location(
    "dinov2_kafka_logging_test",
    Path(__file__).resolve().parents[1] / "events" / "kafka_producer.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KafkaLoggingTests(unittest.TestCase):
    def setUp(self):
        self.producer = module.EventProducer.__new__(module.EventProducer)
        self.producer._producer = MagicMock()

    def test_queue_and_confirmed_delivery_are_distinct_and_correlated(self):
        with self.assertLogs(module.logger, level="DEBUG") as logs:
            self.producer.send_stock_adjustment(21, 1, "DECREASE")
        args = self.producer._producer.produce.call_args.kwargs
        self.assertIn("sending StockAdjustmentRequested", logs.output[0])
        self.assertIn("queued (delivery pending)", logs.output[1])
        self.assertEqual([record.levelname for record in logs.records], ["DEBUG", "DEBUG"])
        self.assertNotIn("Kafka delivered:", "\n".join(logs.output))
        message = MagicMock()
        message.topic.return_value = args["topic"]
        message.partition.return_value = 0
        message.offset.return_value = 42
        with self.assertLogs(module.logger, level="INFO") as delivered:
            args["on_delivery"](None, message)
        self.assertIn(args["value"]["eventId"], delivered.output[0])
        self.assertIn("productId=21", delivered.output[0])
        self.assertIn("offset=42", delivered.output[0])
        self.assertEqual(delivered.records[0].levelname, "INFO")
        with self.assertLogs(module.logger, level="ERROR") as failed:
            args["on_delivery"]("broker unavailable", message)
        self.assertIn("delivery failed", failed.output[0])
        self.assertIn(args["value"]["eventId"], failed.output[0])

    def test_enqueue_failure_does_not_log_success(self):
        self.producer._producer.produce.side_effect = ValueError("serialization failed")
        with self.assertLogs(module.logger, level="DEBUG") as logs:
            with self.assertRaises(ValueError):
                self.producer.send_stock_adjustment(21, 1, "DECREASE")
        self.assertIn("enqueue failed", "\n".join(logs.output))
        self.assertNotIn("Kafka queued", "\n".join(logs.output))
        self.producer._producer.poll.assert_not_called()

    def test_flush_timeout_warns_without_claiming_delivery(self):
        self.producer._producer.flush.return_value = 1
        with self.assertLogs(module.logger, level="WARNING") as logs:
            self.producer.flush(5)
        self.assertIn("delivery not confirmed", logs.output[0])
