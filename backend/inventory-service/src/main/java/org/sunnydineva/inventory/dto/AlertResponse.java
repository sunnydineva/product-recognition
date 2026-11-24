package org.sunnydineva.inventory.dto;

import org.sunnydineva.inventory.enums.AlertStatus;
import org.sunnydineva.inventory.enums.AlertType;

import java.time.Instant;

public record AlertResponse(
        Long id,
        Long productId,
        String productSku,
        AlertType type,
        AlertStatus status,
        long threshold,
        long quantity,
        Instant triggeredAt,
        Instant acknowledgedAt,
        String acknowledgedBy,
        Instant resolvedAt,
        String note
) {
}
