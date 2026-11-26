import logging
import os
import uuid
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

logger = logging.getLogger("uvicorn.error.dinov2.kafka")

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

    def _delivery_report(self, err, msg, *, event_id=None, product_id=None) -> None:
        if err is not None:
            logger.error(
                "DINOv2 Kafka delivery failed: eventId=%s productId=%s error=%s",
                event_id,
                product_id,
                err,
            )
        else:
            logger.info(
                "DINOv2 Kafka delivered: eventId=%s productId=%s topic=%s partition=%d offset=%d",
                event_id,
                product_id,
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
        topic = "ai.product.stock-adjustment-requested"
        logger.debug(
            "DINOv2 Kafka sending StockAdjustmentRequested: eventId=%s productId=%s "
            "operation=%s quantity=%s topic=%s",
            value["eventId"],
            product_id,
            operation,
            quantity,
            topic,
        )
        try:
            self._producer.produce(
                topic=topic,
                key=str(product_id),
                value=value,
                on_delivery=partial(
                    self._delivery_report,
                    event_id=value["eventId"],
                    product_id=product_id,
                ),
            )
        except Exception:
            logger.exception(
                "DINOv2 Kafka enqueue failed: eventId=%s productId=%s topic=%s",
                value["eventId"],
                product_id,
                topic,
            )
            raise
        logger.debug(
            "DINOv2 Kafka queued (delivery pending): eventId=%s productId=%s topic=%s",
            value["eventId"],
            product_id,
            topic,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        remaining = self._producer.flush(timeout)
        if remaining:
            logger.warning(
                "DINOv2 Kafka flush timed out: %s message(s) still pending; delivery not confirmed",
                remaining,
            )


_producer = None


def get_producer() -> EventProducer:
    global _producer
    if _producer is None:
        _producer = EventProducer()
    return _producer
