package org.sunnydineva.inventory.dto;

public record ProductUpdateRequest(
        String name,
        String barcode,
        String note,
        Boolean active
) {
}
