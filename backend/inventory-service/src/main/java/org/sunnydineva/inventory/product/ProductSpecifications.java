package org.sunnydineva.inventory.product;

import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Subquery;

import org.sunnydineva.inventory.alert.Alert;
import org.sunnydineva.inventory.enums.AlertStatus;

import org.springframework.data.jpa.domain.Specification;

import java.util.ArrayList;
import java.util.List;

public final class ProductSpecifications {

    private ProductSpecifications() {
    }

    public static Specification<Product> filter(String search, Boolean active, Boolean hasActiveAlert) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (search != null && !search.isBlank()) {
                String like = "%" + search.toLowerCase() + "%";
                predicates.add(cb.or(
                        cb.like(cb.lower(root.get("name")), like),
                        cb.like(cb.lower(root.get("sku")), like),
                        cb.like(cb.lower(root.get("barcode")), like)));
            }
            if (active != null) {
                predicates.add(cb.equal(root.get("active"), active));
            }
            if (hasActiveAlert != null) {
                Subquery<Long> subquery = query.subquery(Long.class);
                var alertRoot = subquery.from(Alert.class);
                subquery.select(alertRoot.get("productId"));
                subquery.where(
                        cb.equal(alertRoot.get("productId"), root.get("id")),
                        cb.or(
                                cb.equal(alertRoot.get("status"), AlertStatus.ACTIVE),
                                cb.equal(alertRoot.get("status"), AlertStatus.ACKNOWLEDGED)));
                if (hasActiveAlert) {
                    predicates.add(cb.exists(subquery));
                } else {
                    predicates.add(cb.not(cb.exists(subquery)));
                }
            }
            if (predicates.isEmpty()) {
                return cb.conjunction();
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }
}
