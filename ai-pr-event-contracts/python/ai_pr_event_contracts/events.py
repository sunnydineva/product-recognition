"""Python dataclasses mirroring the Avro event contracts."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class StockOperation(str, Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


@dataclass
class ProductCreationRequested:
    event_id: str
    name: str
    initial_quantity: int
    timestamp: int  # epoch millis
    barcode: Optional[str] = None
    note: Optional[str] = None

    @staticmethod
    def new(
        name: str,
        initial_quantity: int,
        barcode: Optional[str] = None,
        note: Optional[str] = None,
    ) -> "ProductCreationRequested":
        return ProductCreationRequested(
            event_id=str(uuid.uuid4()),
            name=name,
            initial_quantity=initial_quantity,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            barcode=barcode,
            note=note,
        )


@dataclass
class StockAdjustmentRequested:
    event_id: str
    product_id: int
    quantity: int
    operation: StockOperation
    timestamp: int  # epoch millis
    note: Optional[str] = None

    @staticmethod
    def new(
        product_id: int,
        quantity: int,
        operation: StockOperation,
        note: Optional[str] = None,
    ) -> "StockAdjustmentRequested":
        return StockAdjustmentRequested(
            event_id=str(uuid.uuid4()),
            product_id=product_id,
            quantity=quantity,
            operation=operation,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            note=note,
        )
