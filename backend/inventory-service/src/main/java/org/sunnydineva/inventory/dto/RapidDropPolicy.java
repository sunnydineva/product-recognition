package org.sunnydineva.inventory.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

/** Null members inherit (product policy) or retain existing values (global update). */
public record RapidDropPolicy(
        Boolean enabled,
        @Min(1) @Max(100) Integer percent,
        @Min(1) @Max(8760) Integer windowHours,
        @Min(1) Long minimumDrop
) {
}
