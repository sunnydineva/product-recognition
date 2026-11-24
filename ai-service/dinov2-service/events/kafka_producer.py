import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "ai-pr-event-contracts" / "schemas"


def _load_schema(name: str) -> str:
    return (SCHEMAS_DIR / name).read_text()


class EventProducer:
    def __init__(self) -> None:
        bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        schema_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8087")

        self._schema_registry = SchemaRegistryClient({"url": schema_url})

        self._stock_serializer = AvroSerializer(
            self._schema_registry,
            _load_schema("StockAdjustmentRequested.avsc"),
            to_dict=lambda obj, ctx: obj,
            conf={"auto.register.schemas": False, "use.latest.version": True},
        )
        self._key_serializer = StringSerializer("utf_8")

        self._producer = SerializingProducer(
            {
                "bootstrap.servers": bootstrap,
                "value.serializer": self._stock_serializer,
                "key.serializer": self._key_serializer,
            }
        )

    def _delivery_report(self, err, msg) -> None:
        if err is not None:
            logger.error("Kafka delivery failed: %s", err)
        else:
            logger.info(
                "Kafka delivered to %s [%d] offset %d",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    def send_stock_adjustment(
        self,
        product_id: int,
        quantity: int,
        operation: str,
        note: str | None = None,
    ) -> None:
        value = {
            "eventId": str(uuid.uuid4()),
            "productId": product_id,
            "quantity": quantity,
            "operation": operation,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "note": note,
        }
        self._producer.produce(
            topic="ai.product.stock-adjustment-requested",
            key=str(product_id),
            value=value,
            on_delivery=self._delivery_report,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)


_producer = None


def get_producer() -> EventProducer:
    global _producer
    if _producer is None:
        _producer = EventProducer()
    return _producer
