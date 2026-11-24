package org.sunnydineva.inventory.stock;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import org.sunnydineva.inventory.enums.StockOperation;

import java.time.Instant;

@Entity
@Table(name = "stock_movements")
public class StockMovement {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "product_id", nullable = false)
    private Long productId;

    @Column(name = "quantity_delta", nullable = false)
    private long quantityDelta;

    @Column(name = "quantity_after", nullable = false)
    private long quantityAfter;

    @Enumerated(EnumType.STRING)
    @Column(name = "operation", nullable = false, length = 16)
    private StockOperation operation;

    @Column(name = "source", length = 128)
    private String source;

    @Column(name = "note", columnDefinition = "TEXT")
    private String note;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public StockMovement() {
    }

    @PrePersist
    void prePersist() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public long getQuantityDelta() {
        return quantityDelta;
    }

    public void setQuantityDelta(long quantityDelta) {
        this.quantityDelta = quantityDelta;
    }

    public long getQuantityAfter() {
        return quantityAfter;
    }

    public void setQuantityAfter(long quantityAfter) {
        this.quantityAfter = quantityAfter;
    }

    public StockOperation getOperation() {
        return operation;
    }

    public void setOperation(StockOperation operation) {
        this.operation = operation;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }
}
