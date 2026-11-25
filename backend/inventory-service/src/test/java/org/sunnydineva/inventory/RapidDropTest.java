package org.sunnydineva.inventory;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import org.sunnydineva.inventory.alert.*;
import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.dto.RapidDropPolicy;
import org.sunnydineva.inventory.dto.StockPolicyRequest;
import org.sunnydineva.inventory.enums.*;
import org.sunnydineva.inventory.policy.RapidDropColumns;
import org.sunnydineva.inventory.product.ProductRepository;
import org.sunnydineva.inventory.settings.EffectiveSettingsService;
import org.sunnydineva.inventory.stock.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class RapidDropTest {
    private static final RapidDropPolicy DEFAULT = new RapidDropPolicy(true, 50, 24, 1L);
    private static final Instant NOW = Instant.parse("2026-11-24T12:00:00Z");

    @Test
    void exactThresholdAndMinimumAndOverflowSafeComparison() {
        assertTrue(RapidDropMeasurement.measure(100, 50).qualifies(DEFAULT));
        assertTrue(RapidDropMeasurement.measure(1, 0).qualifies(DEFAULT));
        assertFalse(RapidDropMeasurement.measure(100, 51).qualifies(DEFAULT));
        assertFalse(RapidDropMeasurement.measure(0, 0).qualifies(DEFAULT));
        assertFalse(RapidDropMeasurement.measure(100, 120).qualifies(DEFAULT));
        assertTrue(RapidDropMeasurement.measure(Long.MAX_VALUE, 0).qualifies(DEFAULT));
        assertFalse(RapidDropMeasurement.measure(Long.MAX_VALUE, Long.MAX_VALUE / 2 + 1).qualifies(DEFAULT));
        assertFalse(RapidDropMeasurement.measure(100, 50)
                .qualifies(new RapidDropPolicy(true, 50, 24, 51L)));
    }

    @Test
    void inheritanceAndValidation() {
        assertEquals(DEFAULT, RapidDropColumns.merge(null, DEFAULT));
        assertEquals(new RapidDropPolicy(false, 50, 1, 1L),
                RapidDropColumns.merge(new RapidDropPolicy(false, null, 1, null), DEFAULT));
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var validator = factory.getValidator();
            assertTrue(validator.validate(new StockPolicyRequest(null, null, null,
                    new RapidDropPolicy(null, null, null, null))).isEmpty());
            assertEquals(3, validator.validate(new StockPolicyRequest(null, null, null,
                    new RapidDropPolicy(true, 101, 0, 0L))).size());
        }
    }

    @Test
    void legacyJsonOmitsNewObjectAndEmptyObjectResetsOverrides() throws Exception {
        var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
        var global = mapper.readValue("{\"defaultLowStockThreshold\":10,\"defaultAlertEnabled\":true}",
                org.sunnydineva.inventory.dto.GlobalSettingsRequest.class);
        assertNull(global.rapidDrop());
        var legacy = mapper.readValue("{\"lowStockThreshold\":5}", StockPolicyRequest.class);
        assertNull(legacy.rapidDrop());
        var reset = mapper.readValue("{\"rapidDrop\":{}}", StockPolicyRequest.class);
        assertEquals(new RapidDropPolicy(null, null, null, null), reset.rapidDrop());
    }

    @Test
    void schedulerUsesBoundedKeysetPagesAndContinuesAfterOneProductFails() {
        var products = mock(ProductRepository.class);
        var worker = mock(AlertEvaluationWorker.class);
        var page = org.springframework.data.domain.PageRequest.of(0, 100);
        when(products.findIdsAfter(0, page)).thenReturn(List.of(1L, 2L));
        when(products.findIdsAfter(2, page)).thenReturn(List.of(4L));
        when(products.findIdsAfter(4, page)).thenReturn(List.of());
        doThrow(new IllegalStateException("Expected test failure")).when(worker).evaluate(1L);
        new AlertSweep(products, worker).evaluateAll();
        verify(worker).evaluate(1L);
        verify(worker).evaluate(2L);
        verify(worker).evaluate(4L);
        verify(products).findIdsAfter(0, page);
        verify(products).findIdsAfter(2, page);
        verify(products).findIdsAfter(4, page);
        verifyNoMoreInteractions(products, worker);
    }

    @Test
    void independentTypesAcknowledgeDeduplicateRecoverAndDisable() {
        Fixture f = new Fixture(100, 10, NOW.minusSeconds(86400));
        f.service.evaluate(1L);
        assertEquals(2, f.saved.size());
        Alert low = f.active(AlertType.LOW_STOCK);
        Alert rapid = f.active(AlertType.RAPID_DROP);
        assertNull(rapid.getThreshold());
        assertEquals(100, rapid.getRapidDrop().getBaseline());
        rapid.setStatus(AlertStatus.ACKNOWLEDGED);
        f.service.evaluate(1L);
        assertEquals(2, f.saved.size());
        assertEquals(AlertStatus.ACKNOWLEDGED, rapid.getStatus());
        f.stock.setQuantity(60); // Net receipts offset the earlier decline.
        f.service.evaluate(1L);
        assertEquals(AlertStatus.RESOLVED, rapid.getStatus());
        assertEquals(AlertStatus.RESOLVED, low.getStatus());
        f.stock.setQuantity(10);
        f.service.evaluate(1L);
        assertEquals(4, f.saved.size());
        when(f.settings.get(1L)).thenReturn(new EffectiveSettings(10, true, null, "GLOBAL",
                new RapidDropPolicy(false, 50, 24, 1L)));
        f.service.evaluate(1L);
        assertNotNull(f.active(AlertType.LOW_STOCK));
        assertNull(f.active(AlertType.RAPID_DROP));
    }

    @Test
    void insufficientCoverageAndZeroBaselineDoNotSignal() {
        Fixture partial = new Fixture(100, 10, NOW.minusSeconds(86399));
        partial.service.evaluate(1L);
        assertNull(partial.active(AlertType.RAPID_DROP));
        verifyNoInteractions(partial.movements);
        Fixture zero = new Fixture(0, 0, NOW.minusSeconds(86400));
        zero.service.evaluate(1L);
        assertNull(zero.active(AlertType.RAPID_DROP));
    }

    @Test
    void windowExpiryUsesLatestSnapshotAtInclusiveCutoffWithoutNewMovements() {
        Fixture f = new Fixture(100, 40, NOW.minusSeconds(172800));
        f.service.evaluate(1L);
        Alert rapid = f.active(AlertType.RAPID_DROP);
        assertNotNull(rapid);
        StockMovement oldDrop = new StockMovement();
        oldDrop.setQuantityAfter(40);
        when(f.movements
                .findFirstByProductIdAndCreatedAtGreaterThanEqualAndCreatedAtLessThanEqualOrderByCreatedAtDescIdDesc(
                        1L, f.stock.getHistoryStartedAt(), NOW.minusSeconds(86400)))
                .thenReturn(Optional.of(oldDrop));
        f.service.evaluate(1L);
        assertEquals(AlertStatus.RESOLVED, rapid.getStatus());
    }

    private static class Fixture {
        final AlertRepository alerts = mock(AlertRepository.class);
        final StockRepository stocks = mock(StockRepository.class);
        final StockMovementRepository movements = mock(StockMovementRepository.class);
        final EffectiveSettingsService settings = mock(EffectiveSettingsService.class);
        final Stock stock = new Stock();
        final List<Alert> saved = new java.util.ArrayList<>();
        final AlertService service;

        Fixture(long baseline, long current, Instant coverage) {
            stock.setHistoryStartedAt(coverage);
            stock.setHistoryInitialQuantity(baseline);
            stock.setQuantity(current);
            when(stocks.findByProductIdForUpdate(1L)).thenReturn(Optional.of(stock));
            when(settings.get(1L)).thenReturn(new EffectiveSettings(10, true, null, "GLOBAL", DEFAULT));
            when(alerts.findFirstByProductIdAndTypeAndStatusIn(eq(1L), any(), anyList()))
                    .thenAnswer(call -> Optional.ofNullable(active(call.getArgument(1))));
            when(alerts.save(any())).thenAnswer(call -> {
                Alert alert = call.getArgument(0);
                if (!saved.contains(alert)) saved.add(alert);
                return alert;
            });
            service = new AlertService(alerts, mock(ProductRepository.class), stocks, settings, movements,
                    Clock.fixed(NOW, ZoneOffset.UTC));
        }

        Alert active(AlertType type) {
            return saved.stream().filter(a -> a.getType() == type && a.getStatus() != AlertStatus.RESOLVED)
                    .findFirst().orElse(null);
        }
    }
}
