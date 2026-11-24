package org.sunnydineva.inventory.alert;

import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.common.exception.NotFoundException;
import org.sunnydineva.inventory.dto.AcknowledgeAlertRequest;
import org.sunnydineva.inventory.dto.AlertResponse;
import org.sunnydineva.inventory.enums.AlertStatus;
import org.sunnydineva.inventory.product.Product;
import org.sunnydineva.inventory.product.ProductRepository;
import org.sunnydineva.inventory.settings.EffectiveSettingsService;
import org.sunnydineva.inventory.stock.Stock;
import org.sunnydineva.inventory.stock.StockRepository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

@Service
public class AlertService {

    private final AlertRepository alertRepository;
    private final ProductRepository productRepository;
    private final StockRepository stockRepository;
    private final EffectiveSettingsService effectiveSettingsService;

    public AlertService(AlertRepository alertRepository,
                        ProductRepository productRepository,
                        StockRepository stockRepository,
                        EffectiveSettingsService effectiveSettingsService) {
        this.alertRepository = alertRepository;
        this.productRepository = productRepository;
        this.stockRepository = stockRepository;
        this.effectiveSettingsService = effectiveSettingsService;
    }

    @Transactional(readOnly = true)
    public Page<AlertResponse> list(AlertStatus status, Long productId, Instant from, Instant to, Pageable pageable) {
        Specification<Alert> spec = AlertSpecifications.filter(status, productId, from, to);
        return alertRepository.findAll(spec, pageable).map(this::toResponse);
    }

    @Transactional
    public AlertResponse acknowledge(Long id, AcknowledgeAlertRequest request) {
        Alert alert = alertRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Alert not found: " + id));
        if (alert.getStatus() == AlertStatus.RESOLVED) {
            throw new org.sunnydineva.inventory.common.exception.ConflictException("Alert already resolved");
        }
        alert.setStatus(AlertStatus.ACKNOWLEDGED);
        alert.setAcknowledgedAt(Instant.now());
        alert.setAcknowledgedBy(request.acknowledgedBy());
        if (request.note() != null) {
            alert.setNote(request.note());
        }
        alertRepository.save(alert);
        return toResponse(alert);
    }

    @Transactional
    public void evaluate(Long productId) {
        Stock stock = stockRepository.findByProductId(productId).orElse(null);
        long quantity = stock != null ? stock.getQuantity() : 0L;
        EffectiveSettings settings = effectiveSettingsService.get(productId);
        List<AlertStatus> activeStatuses = List.of(AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED);
        Alert existing = alertRepository.findFirstByProductIdAndStatusIn(productId, activeStatuses).orElse(null);

        if (settings.alertEnabled() && quantity <= settings.lowStockThreshold()) {
            if (existing == null) {
                Alert alert = new Alert();
                alert.setProductId(productId);
                alert.setType(org.sunnydineva.inventory.enums.AlertType.LOW_STOCK);
                alert.setStatus(AlertStatus.ACTIVE);
                alert.setThreshold(settings.lowStockThreshold());
                alert.setQuantity(quantity);
                alert.setTriggeredAt(Instant.now());
                alertRepository.save(alert);
            } else {
                existing.setThreshold(settings.lowStockThreshold());
                existing.setQuantity(quantity);
                alertRepository.save(existing);
            }
        } else if (existing != null) {
            existing.setStatus(AlertStatus.RESOLVED);
            existing.setResolvedAt(Instant.now());
            alertRepository.save(existing);
        }
    }

    private AlertResponse toResponse(Alert alert) {
        Product product = productRepository.findById(alert.getProductId()).orElse(null);
        String sku = product != null ? product.getSku() : null;
        return new AlertResponse(
                alert.getId(),
                alert.getProductId(),
                sku,
                alert.getType(),
                alert.getStatus(),
                alert.getThreshold(),
                alert.getQuantity(),
                alert.getTriggeredAt(),
                alert.getAcknowledgedAt(),
                alert.getAcknowledgedBy(),
                alert.getResolvedAt(),
                alert.getNote());
    }
}
