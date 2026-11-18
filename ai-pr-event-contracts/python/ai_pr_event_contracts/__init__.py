"""Shared Avro event contracts for Kafka.

Schemas live in ``../schemas``. Python classes are generated from the
``.avsc`` files; see ``generate.py`` for regeneration instructions.
"""

from .events import ProductCreationRequested, StockAdjustmentRequested

__all__ = ["ProductCreationRequested", "StockAdjustmentRequested"]
