package org.sunnydineva.inventory.settings;

import org.sunnydineva.inventory.dto.GlobalSettingsRequest;
import org.sunnydineva.inventory.dto.GlobalSettingsResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/v1/settings")
@Tag(name = "Settings", description = "Global inventory settings")
public class SettingsController {

    private final SettingsService settingsService;

    public SettingsController(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    @GetMapping
    @Operation(summary = "Get global settings")
    public GlobalSettingsResponse get() {
        return settingsService.get();
    }

    @PutMapping
    @Operation(summary = "Update global settings")
    public GlobalSettingsResponse update(@Valid @RequestBody GlobalSettingsRequest request) {
        return settingsService.update(request);
    }
}
