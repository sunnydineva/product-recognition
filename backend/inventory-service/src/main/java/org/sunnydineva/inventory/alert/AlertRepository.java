package org.sunnydineva.inventory.alert;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.List;
import java.util.Optional;

public interface AlertRepository extends JpaRepository<Alert, Long>, JpaSpecificationExecutor<Alert> {
    Optional<Alert> findFirstByProductIdAndTypeAndStatusIn(Long productId,
            org.sunnydineva.inventory.enums.AlertType type,
            List<org.sunnydineva.inventory.enums.AlertStatus> statuses);

    List<Alert> findByProductId(Long productId);

    @org.springframework.data.jpa.repository.Query("select a.productId from Alert a where a.id = :id")
    Optional<Long> findProductId(@org.springframework.data.repository.query.Param("id") Long id);
}
