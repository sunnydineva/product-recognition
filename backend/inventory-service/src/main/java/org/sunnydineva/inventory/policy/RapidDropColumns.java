package org.sunnydineva.inventory.policy;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import org.sunnydineva.inventory.dto.RapidDropPolicy;

@Embeddable
public class RapidDropColumns {
    @Column(name = "rapid_drop_enabled")
    private Boolean enabled;
    @Column(name = "rapid_drop_percent")
    private Integer percent;
    @Column(name = "rapid_drop_window_hours")
    private Integer windowHours;
    @Column(name = "rapid_drop_minimum_drop")
    private Long minimumDrop;

    public RapidDropColumns() {
    }

    public RapidDropColumns(RapidDropPolicy policy) {
        enabled = policy.enabled();
        percent = policy.percent();
        windowHours = policy.windowHours();
        minimumDrop = policy.minimumDrop();
    }

    public RapidDropPolicy toPolicy() {
        return new RapidDropPolicy(enabled, percent, windowHours, minimumDrop);
    }

    public static RapidDropPolicy merge(RapidDropPolicy override, RapidDropPolicy defaults) {
        if (override == null) {
            return defaults;
        }
        return new RapidDropPolicy(
                override.enabled() == null ? defaults.enabled() : override.enabled(),
                override.percent() == null ? defaults.percent() : override.percent(),
                override.windowHours() == null ? defaults.windowHours() : override.windowHours(),
                override.minimumDrop() == null ? defaults.minimumDrop() : override.minimumDrop());
    }
}
