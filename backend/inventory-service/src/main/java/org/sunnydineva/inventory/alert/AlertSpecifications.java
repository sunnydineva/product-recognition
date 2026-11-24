package org.sunnydineva.inventory.alert;

import jakarta.persistence.criteria.Predicate;

import org.sunnydineva.inventory.enums.AlertStatus;

import org.springframework.data.jpa.domain.Specification;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public final class AlertSpecifications {

    private AlertSpecifications() {
    }

    public static Specification<Alert> filter(AlertStatus status, Long productId, Instant from, Instant to) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (status != null) {
                predicates.add(cb.equal(root.get("status"), status));
            }
            if (productId != null) {
                predicates.add(cb.equal(root.get("productId"), productId));
            }
            if (from != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("triggeredAt"), from));
            }
            if (to != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("triggeredAt"), to));
            }
            if (predicates.isEmpty()) {
                return cb.conjunction();
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }
}
