package org.sunnydineva.inventory.settings;

import org.sunnydineva.inventory.dto.GlobalSettingsRequest;
import org.sunnydineva.inventory.dto.GlobalSettingsResponse;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/v1/settings")
public class SettingsController {

    private final SettingsService settingsService;

    public SettingsController(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    @GetMapping
    public GlobalSettingsResponse get() {
        return settingsService.get();
    }

    @PutMapping
    public GlobalSettingsResponse update(@Valid @RequestBody GlobalSettingsRequest request) {
        return settingsService.update(request);
    }
}
