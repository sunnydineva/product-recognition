package org.sunnydineva.inventory.alert;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionalEventListener;
import org.sunnydineva.inventory.product.ProductRepository;
import org.sunnydineva.inventory.settings.SettingsChanged;

@Component
public class AlertSweep {
    private static final Logger log = LoggerFactory.getLogger(AlertSweep.class);
    private final ProductRepository products;
    private final AlertEvaluationWorker worker;

    public AlertSweep(ProductRepository products, AlertEvaluationWorker worker) {
        this.products = products;
        this.worker = worker;
    }

    @TransactionalEventListener
    public void settingsChanged(SettingsChanged event) {
        evaluateAll();
    }

    @Scheduled(fixedDelayString = "${inventory.alerts.sweep-delay-ms:300000}",
            initialDelayString = "${inventory.alerts.sweep-delay-ms:300000}")
    public void evaluateAll() {
        long after = 0;
        while (true) {
            var ids = products.findIdsAfter(after, PageRequest.of(0, 100));
            if (ids.isEmpty()) {
                return;
            }
            for (Long id : ids) {
                try {
                    worker.evaluate(id);
                } catch (RuntimeException exception) {
                    log.error("Alert evaluation failed for product {}; next sweep will retry", id, exception);
                }
            }
            after = ids.getLast();
        }
    }
}
