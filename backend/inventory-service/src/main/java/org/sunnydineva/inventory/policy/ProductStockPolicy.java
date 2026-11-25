package org.sunnydineva.inventory.policy;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

import java.time.Instant;

@Entity
@Table(name = "product_stock_policies")
public class ProductStockPolicy {
    @jakarta.persistence.Embedded
    private RapidDropColumns rapidDrop;

    public org.sunnydineva.inventory.dto.RapidDropPolicy getRapidDrop() {
        return rapidDrop == null ? null : rapidDrop.toPolicy();
    }

    public void setRapidDrop(org.sunnydineva.inventory.dto.RapidDropPolicy policy) {
        rapidDrop = policy == null ? null : new RapidDropColumns(policy);
    }

    @Id
    @Column(name = "product_id")
    private Long productId;

    @Column(name = "low_stock_threshold")
    private Long lowStockThreshold;

    @Column(name = "alert_enabled")
    private Boolean alertEnabled;

    @Column(name = "reorder_quantity")
    private Long reorderQuantity;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    public ProductStockPolicy() {
    }

    @PrePersist
    void prePersist() {
        if (updatedAt == null) {
            updatedAt = Instant.now();
        }
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public Long getLowStockThreshold() {
        return lowStockThreshold;
    }

    public void setLowStockThreshold(Long lowStockThreshold) {
        this.lowStockThreshold = lowStockThreshold;
    }

    public Boolean getAlertEnabled() {
        return alertEnabled;
    }

    public void setAlertEnabled(Boolean alertEnabled) {
        this.alertEnabled = alertEnabled;
    }

    public Long getReorderQuantity() {
        return reorderQuantity;
    }

    public void setReorderQuantity(Long reorderQuantity) {
        this.reorderQuantity = reorderQuantity;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }

    public Long getVersion() {
        return version;
    }

    public void setVersion(Long version) {
        this.version = version;
    }
}
