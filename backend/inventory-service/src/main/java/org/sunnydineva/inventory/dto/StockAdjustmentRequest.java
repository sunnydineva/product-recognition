package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

import org.sunnydineva.inventory.enums.StockOperation;

public record StockAdjustmentRequest(
        @NotNull StockOperation operation,
        @NotNull @Min(1) Long quantity,
        String source,
        String note
) {
}
