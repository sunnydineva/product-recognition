package org.sunnydineva.inventory.stock;

import jakarta.persistence.criteria.Predicate;

import org.sunnydineva.inventory.enums.StockOperation;

import org.springframework.data.jpa.domain.Specification;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public final class StockMovementSpecifications {

    private StockMovementSpecifications() {
    }

    public static Specification<StockMovement> filter(Long productId, Instant from, Instant to,
                                                      String source, StockOperation operation) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            predicates.add(cb.equal(root.get("productId"), productId));
            if (from != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), from));
            }
            if (to != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("createdAt"), to));
            }
            if (source != null && !source.isBlank()) {
                predicates.add(cb.equal(root.get("source"), source));
            }
            if (operation != null) {
                predicates.add(cb.equal(root.get("operation"), operation));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }
}
