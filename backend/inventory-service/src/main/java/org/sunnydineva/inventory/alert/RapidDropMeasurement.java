package org.sunnydineva.inventory.alert;

import java.math.BigDecimal;
import java.math.RoundingMode;
import org.sunnydineva.inventory.dto.RapidDropPolicy;

public record RapidDropMeasurement(long baseline, long current, BigDecimal measuredPercent) {
    public static RapidDropMeasurement measure(long baseline, long current) {
        BigDecimal percentage = baseline == 0 ? BigDecimal.ZERO :
                BigDecimal.valueOf(baseline).subtract(BigDecimal.valueOf(current))
                        .multiply(BigDecimal.valueOf(100))
                        .divide(BigDecimal.valueOf(baseline), 6, RoundingMode.HALF_UP);
        return new RapidDropMeasurement(baseline, current, percentage);
    }

    public boolean qualifies(RapidDropPolicy policy) {
        // Compare exact products, never the rounded display percentage.
        BigDecimal drop = BigDecimal.valueOf(baseline).subtract(BigDecimal.valueOf(current));
        return policy.enabled() && baseline > 0
                && drop.compareTo(BigDecimal.valueOf(policy.minimumDrop())) >= 0
                && drop.multiply(BigDecimal.valueOf(100)).compareTo(
                        BigDecimal.valueOf(baseline).multiply(BigDecimal.valueOf(policy.percent()))) >= 0;
    }
}
