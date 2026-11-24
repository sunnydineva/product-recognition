package org.sunnydineva.inventory.dto;

import org.sunnydineva.inventory.enums.StockOperation;

import java.time.Instant;

public record StockMovementResponse(
        Long id,
        Long productId,
        long quantityDelta,
        long quantityAfter,
        StockOperation operation,
        String source,
        String note,
        Instant createdAt
) {
}
