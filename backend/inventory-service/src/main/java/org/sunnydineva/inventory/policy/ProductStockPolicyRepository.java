package org.sunnydineva.inventory.policy;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ProductStockPolicyRepository extends JpaRepository<ProductStockPolicy, Long> {
}
