package org.sunnydineva.inventory.settings;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

import java.time.Instant;

@Entity
@Table(name = "global_stock_settings")
public class GlobalStockSettings {
    @jakarta.persistence.Embedded
    private org.sunnydineva.inventory.policy.RapidDropColumns rapidDrop =
            new org.sunnydineva.inventory.policy.RapidDropColumns(
                    new org.sunnydineva.inventory.dto.RapidDropPolicy(true, 50, 24, 1L));

    public org.sunnydineva.inventory.dto.RapidDropPolicy getRapidDrop() {
        return rapidDrop.toPolicy();
    }

    public void setRapidDrop(org.sunnydineva.inventory.dto.RapidDropPolicy policy) {
        rapidDrop = new org.sunnydineva.inventory.policy.RapidDropColumns(policy);
    }

    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "default_low_stock_threshold", nullable = false)
    private long defaultLowStockThreshold;

    @Column(name = "default_alert_enabled", nullable = false)
    private boolean defaultAlertEnabled;

    @Column(name = "default_reorder_quantity")
    private Long defaultReorderQuantity;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    public GlobalStockSettings() {
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

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public long getDefaultLowStockThreshold() {
        return defaultLowStockThreshold;
    }

    public void setDefaultLowStockThreshold(long defaultLowStockThreshold) {
        this.defaultLowStockThreshold = defaultLowStockThreshold;
    }

    public boolean isDefaultAlertEnabled() {
        return defaultAlertEnabled;
    }

    public void setDefaultAlertEnabled(boolean defaultAlertEnabled) {
        this.defaultAlertEnabled = defaultAlertEnabled;
    }

    public Long getDefaultReorderQuantity() {
        return defaultReorderQuantity;
    }

    public void setDefaultReorderQuantity(Long defaultReorderQuantity) {
        this.defaultReorderQuantity = defaultReorderQuantity;
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
