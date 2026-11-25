package org.sunnydineva.inventory.alert;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.math.BigDecimal;
import org.sunnydineva.inventory.dto.RapidDropPolicy;

@Embeddable
public class RapidDropMetadata {
    @Column(name = "rapid_drop_baseline")
    private Long baseline;
    @Column(name = "rapid_drop_current")
    private Long current;
    @Column(name = "rapid_drop_percent")
    private Integer percent;
    @Column(name = "rapid_drop_window_hours")
    private Integer windowHours;
    @Column(name = "rapid_drop_minimum_drop")
    private Long minimumDrop;
    @Column(name = "rapid_drop_measured_percent", precision = 12, scale = 6)
    private BigDecimal measuredPercent;

    public RapidDropMetadata() {
    }

    public RapidDropMetadata(RapidDropMeasurement measurement, RapidDropPolicy policy) {
        baseline = measurement.baseline();
        current = measurement.current();
        percent = policy.percent();
        windowHours = policy.windowHours();
        minimumDrop = policy.minimumDrop();
        measuredPercent = measurement.measuredPercent();
    }

    public Long getBaseline() { return baseline; }
    public Long getCurrent() { return current; }
    public Integer getPercent() { return percent; }
    public Integer getWindowHours() { return windowHours; }
    public Long getMinimumDrop() { return minimumDrop; }
    public BigDecimal getMeasuredPercent() { return measuredPercent; }
}
