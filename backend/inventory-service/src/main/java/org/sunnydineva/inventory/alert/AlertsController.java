package org.sunnydineva.inventory.alert;

import org.sunnydineva.inventory.dto.AcknowledgeAlertRequest;
import org.sunnydineva.inventory.dto.AlertResponse;
import org.sunnydineva.inventory.enums.AlertStatus;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

import java.time.Instant;

@RestController
@RequestMapping("/api/v1/alerts")
public class AlertsController {

    private final AlertService alertService;

    public AlertsController(AlertService alertService) {
        this.alertService = alertService;
    }

    @GetMapping
    public Page<AlertResponse> list(@RequestParam(required = false) AlertStatus status,
                                    @RequestParam(required = false) Long productId,
                                    @RequestParam(required = false) Instant from,
                                    @RequestParam(required = false) Instant to,
                                    Pageable pageable) {
        return alertService.list(status, productId, from, to, pageable);
    }

    @PostMapping("/{id}/acknowledgement")
    public AlertResponse acknowledge(@PathVariable Long id, @Valid @RequestBody AcknowledgeAlertRequest request) {
        return alertService.acknowledge(id, request);
    }
}
