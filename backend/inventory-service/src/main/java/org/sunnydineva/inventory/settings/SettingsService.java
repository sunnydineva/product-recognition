package org.sunnydineva.inventory.settings;

import org.sunnydineva.inventory.dto.GlobalSettingsRequest;
import org.sunnydineva.inventory.dto.GlobalSettingsResponse;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Service
public class SettingsService {

    private final GlobalStockSettingsRepository repository;
    private final org.sunnydineva.inventory.product.ProductRepository productRepository;
    private final org.sunnydineva.inventory.alert.AlertService alertService;

    public SettingsService(GlobalStockSettingsRepository repository,
                           org.sunnydineva.inventory.product.ProductRepository productRepository,
                           org.sunnydineva.inventory.alert.AlertService alertService) {
        this.repository = repository;
        this.productRepository = productRepository;
        this.alertService = alertService;
    }

    @Transactional(readOnly = true)
    public GlobalStockSettings getGlobalEntity() {
        return repository.findById(1L)
                .orElseThrow(() -> new IllegalStateException("Global stock settings not initialized"));
    }

    @Transactional(readOnly = true)
    public GlobalSettingsResponse get() {
        GlobalStockSettings settings = getGlobalEntity();
        return new GlobalSettingsResponse(
                settings.getDefaultLowStockThreshold(),
                settings.isDefaultAlertEnabled(),
                settings.getDefaultReorderQuantity(),
                settings.getUpdatedAt());
    }

    @Transactional
    public GlobalSettingsResponse update(GlobalSettingsRequest request) {
        GlobalStockSettings settings = getGlobalEntity();
        settings.setDefaultLowStockThreshold(request.defaultLowStockThreshold());
        settings.setDefaultAlertEnabled(request.defaultAlertEnabled());
        settings.setDefaultReorderQuantity(request.defaultReorderQuantity());
        settings.setUpdatedAt(Instant.now());
        repository.save(settings);
        productRepository.findAll().forEach(product -> alertService.evaluate(product.getId()));
        return new GlobalSettingsResponse(
                settings.getDefaultLowStockThreshold(),
                settings.isDefaultAlertEnabled(),
                settings.getDefaultReorderQuantity(),
                settings.getUpdatedAt());
    }
}
