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
    """Thin wrapper around a Confluent Kafka producer with Avro serialization."""

    def __init__(self) -> None:
        bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        schema_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8087")

        self._schema_registry = SchemaRegistryClient({"url": schema_url})

        self._stock_serializer = AvroSerializer(
            self._schema_registry,
            _load_schema("StockAdjustmentRequested.avsc"),
            to_dict=lambda obj, ctx: obj,
        )
        self._creation_serializer = AvroSerializer(
            self._schema_registry,
            _load_schema("ProductCreationRequested.avsc"),
            to_dict=lambda obj, ctx: obj,
        )
        self._key_serializer = StringSerializer("utf_8")

        self._stock_producer = SerializingProducer(
            {
                "bootstrap.servers": bootstrap,
                "value.serializer": self._stock_serializer,
                "key.serializer": self._key_serializer,
            }
        )
        self._creation_producer = SerializingProducer(
            {
                "bootstrap.servers": bootstrap,
                "value.serializer": self._creation_serializer,
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
        self._stock_producer.produce(
            topic="ai.product.stock-adjustment-requested",
            key=str(product_id),
            value=value,
            on_delivery=self._delivery_report,
        )
        self._stock_producer.poll(0)

    def send_product_creation(
        self,
        name: str,
        initial_quantity: int,
        barcode: str | None = None,
        note: str | None = None,
    ) -> None:
        value = {
            "eventId": str(uuid.uuid4()),
            "name": name,
            "barcode": barcode,
            "initialQuantity": initial_quantity,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "note": note,
        }
        self._creation_producer.produce(
            topic="ai.product.creation-requested",
            key=name,
            value=value,
            on_delivery=self._delivery_report,
        )
        self._creation_producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        self._stock_producer.flush(timeout)
        self._creation_producer.flush(timeout)


_producer: EventProducer | None = None


def get_producer() -> EventProducer:
    global _producer
    if _producer is None:
        _producer = EventProducer()
    return _producer
