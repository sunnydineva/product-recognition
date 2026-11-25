package org.sunnydineva.inventory.dto;

import java.time.Instant;

public record StockPolicyResponse(
        Long productId,
        Long lowStockThreshold,
        Boolean alertEnabled,
        Long reorderQuantity,
        Instant updatedAt,
        RapidDropPolicy rapidDrop
) {
}
