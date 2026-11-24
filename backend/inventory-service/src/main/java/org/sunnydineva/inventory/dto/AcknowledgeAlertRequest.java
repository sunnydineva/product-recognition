package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.NotBlank;

public record AcknowledgeAlertRequest(
        @NotBlank String acknowledgedBy,
        String note
) {
}
