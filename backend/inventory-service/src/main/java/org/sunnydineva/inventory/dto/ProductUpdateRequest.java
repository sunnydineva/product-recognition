package org.sunnydineva.inventory.dto;

public record ProductUpdateRequest(
        String name,
        String barcode,
        Boolean active
) {
}
