package org.sunnydineva.inventory.settings;

import org.sunnydineva.inventory.dto.GlobalSettingsRequest;
import org.sunnydineva.inventory.dto.GlobalSettingsResponse;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Service
public class SettingsService {

    private final GlobalStockSettingsRepository repository;
    private final org.springframework.context.ApplicationEventPublisher events;

    public SettingsService(GlobalStockSettingsRepository repository,
                           org.springframework.context.ApplicationEventPublisher events) {
        this.repository = repository;
        this.events = events;
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
                settings.getUpdatedAt(), settings.getRapidDrop());
    }

    @Transactional
    public GlobalSettingsResponse update(GlobalSettingsRequest request) {
        GlobalStockSettings settings = getGlobalEntity();
        settings.setDefaultLowStockThreshold(request.defaultLowStockThreshold());
        settings.setDefaultAlertEnabled(request.defaultAlertEnabled());
        settings.setDefaultReorderQuantity(request.defaultReorderQuantity());
        settings.setRapidDrop(org.sunnydineva.inventory.policy.RapidDropColumns.merge(
                request.rapidDrop(), settings.getRapidDrop()));
        settings.setUpdatedAt(Instant.now());
        repository.save(settings);
        events.publishEvent(new SettingsChanged());
        return new GlobalSettingsResponse(
                settings.getDefaultLowStockThreshold(),
                settings.isDefaultAlertEnabled(),
                settings.getDefaultReorderQuantity(),
                settings.getUpdatedAt(), settings.getRapidDrop());
    }
}
