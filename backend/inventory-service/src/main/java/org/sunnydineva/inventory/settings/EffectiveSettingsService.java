package org.sunnydineva.inventory.settings;

import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.policy.ProductStockPolicy;
import org.sunnydineva.inventory.policy.ProductStockPolicyRepository;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EffectiveSettingsService {

    private final GlobalStockSettingsRepository globalRepository;
    private final ProductStockPolicyRepository policyRepository;

    public EffectiveSettingsService(GlobalStockSettingsRepository globalRepository,
                                    ProductStockPolicyRepository policyRepository) {
        this.globalRepository = globalRepository;
        this.policyRepository = policyRepository;
    }

    @Transactional(readOnly = true)
    public EffectiveSettings get(Long productId) {
        GlobalStockSettings global = globalRepository.findById(1L)
                .orElseThrow(() -> new IllegalStateException("Global stock settings not initialized"));
        ProductStockPolicy policy = policyRepository.findById(productId).orElse(null);

        boolean hasOverride = policy != null
                && (policy.getLowStockThreshold() != null
                || policy.getAlertEnabled() != null
                || policy.getReorderQuantity() != null);

        long threshold = (policy != null && policy.getLowStockThreshold() != null)
                ? policy.getLowStockThreshold()
                : global.getDefaultLowStockThreshold();
        boolean alertEnabled = (policy != null && policy.getAlertEnabled() != null)
                ? policy.getAlertEnabled()
                : global.isDefaultAlertEnabled();
        Long reorderQuantity = (policy != null && policy.getReorderQuantity() != null)
                ? policy.getReorderQuantity()
                : global.getDefaultReorderQuantity();
        String source = hasOverride ? "PRODUCT" : "GLOBAL";
        return new EffectiveSettings(threshold, alertEnabled, reorderQuantity, source);
    }
}
