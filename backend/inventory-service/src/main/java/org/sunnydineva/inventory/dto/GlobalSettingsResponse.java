package org.sunnydineva.inventory.dto;

import java.time.Instant;

public record GlobalSettingsResponse(
        long defaultLowStockThreshold,
        boolean defaultAlertEnabled,
        Long defaultReorderQuantity,
        Instant updatedAt,
        RapidDropPolicy rapidDrop
) {
}
