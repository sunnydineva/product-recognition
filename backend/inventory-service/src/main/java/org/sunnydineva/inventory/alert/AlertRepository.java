package org.sunnydineva.inventory.alert;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.List;
import java.util.Optional;

public interface AlertRepository extends JpaRepository<Alert, Long>, JpaSpecificationExecutor<Alert> {
    Optional<Alert> findFirstByProductIdAndStatusIn(Long productId, List<org.sunnydineva.inventory.enums.AlertStatus> statuses);

    List<Alert> findByProductId(Long productId);
}
