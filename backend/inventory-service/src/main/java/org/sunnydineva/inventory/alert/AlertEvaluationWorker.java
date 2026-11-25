package org.sunnydineva.inventory.alert;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AlertEvaluationWorker {
    private final AlertService alerts;

    public AlertEvaluationWorker(AlertService alerts) {
        this.alerts = alerts;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void evaluate(Long productId) {
        alerts.evaluate(productId);
    }
}
