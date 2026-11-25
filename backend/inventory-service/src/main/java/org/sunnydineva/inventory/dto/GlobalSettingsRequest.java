package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record GlobalSettingsRequest(
        @NotNull @Min(0) Long defaultLowStockThreshold,
        @NotNull Boolean defaultAlertEnabled,
        @Min(0) Long defaultReorderQuantity,
        @jakarta.validation.Valid RapidDropPolicy rapidDrop
) {
}
