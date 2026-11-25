package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.Min;

public record StockPolicyRequest(
        @Min(0) Long lowStockThreshold,
        Boolean alertEnabled,
        @Min(0) Long reorderQuantity,
        @jakarta.validation.Valid RapidDropPolicy rapidDrop
) {
}
