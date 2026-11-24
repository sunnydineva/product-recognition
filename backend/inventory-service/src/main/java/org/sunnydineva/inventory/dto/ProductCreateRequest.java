package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public record ProductCreateRequest(
        @NotBlank String name,
        @NotBlank String sku,
        String barcode,
        @Min(0) Long initialQuantity,
        Boolean active
) {
}
