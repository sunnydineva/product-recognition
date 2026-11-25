package org.sunnydineva.inventory.product;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

public interface ProductRepository extends JpaRepository<Product, Long>, JpaSpecificationExecutor<Product> {
    boolean existsBySku(String sku);

    @org.springframework.data.jpa.repository.Query("select p.id from Product p where p.id > :after order by p.id")
    java.util.List<Long> findIdsAfter(@org.springframework.data.repository.query.Param("after") long after,
                                    org.springframework.data.domain.Pageable pageable);
}
