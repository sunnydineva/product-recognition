package org.sunnydineva.inventory.common;

public record EffectiveSettings(
        long lowStockThreshold,
        boolean alertEnabled,
        Long reorderQuantity,
        String source
) {
}
