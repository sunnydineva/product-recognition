package org.sunnydineva.inventory.dto;

import java.time.Instant;

public record ProductResponse(
        Long id,
        String sku,
        String name,
        String barcode,
        boolean active,
        Instant createdAt,
        Instant updatedAt,
        StockResponse stock,
        EffectiveSettingsResponse effectiveSettings
) {
    public record StockResponse(
            long quantity,
            Instant updatedAt
    ) {
    }

    public record EffectiveSettingsResponse(
            long lowStockThreshold,
            boolean alertEnabled,
            Long reorderQuantity,
            String source
    ) {
    }
}
