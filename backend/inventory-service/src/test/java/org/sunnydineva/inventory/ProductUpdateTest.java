package org.sunnydineva.inventory;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.sunnydineva.inventory.alert.AlertService;
import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.dto.ProductResponse;
import org.sunnydineva.inventory.dto.ProductUpdateRequest;
import org.sunnydineva.inventory.policy.ProductStockPolicyRepository;
import org.sunnydineva.inventory.product.Product;
import org.sunnydineva.inventory.product.ProductRepository;
import org.sunnydineva.inventory.product.ProductService;
import org.sunnydineva.inventory.settings.EffectiveSettingsService;
import org.sunnydineva.inventory.stock.StockMovementRepository;
import org.sunnydineva.inventory.stock.StockRepository;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ProductUpdateTest {

    private static final Instant NOW = Instant.parse("2026-11-26T12:00:00Z");
    private static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);

    private final ProductRepository products = mock(ProductRepository.class);
    private final StockRepository stocks = mock(StockRepository.class);
    private final AlertService alerts = mock(AlertService.class);
    private final EffectiveSettingsService effectiveSettings = mock(EffectiveSettingsService.class);
    private final ProductService service = new ProductService(
            products,
            stocks,
            mock(StockMovementRepository.class),
            mock(ProductStockPolicyRepository.class),
            effectiveSettings,
            alerts,
            CLOCK);

    @Test
    void updatePersistsAndTrimsCanonicalNote() {
        Product product = product(5L, "old note");
        when(stocks.findByProductIdForUpdate(5L)).thenReturn(Optional.empty());
        when(products.findById(5L)).thenReturn(Optional.of(product));
        when(products.save(any(Product.class))).thenAnswer(call -> call.getArgument(0));
        when(stocks.findByProductId(5L)).thenReturn(Optional.empty());
        when(effectiveSettings.get(5L))
                .thenReturn(new EffectiveSettings(10L, true, null, "GLOBAL", null));

        ProductResponse response = service.update(
                5L, new ProductUpdateRequest(null, null, "  Aisle 9  ", null));

        ArgumentCaptor<Product> saved = ArgumentCaptor.forClass(Product.class);
        verify(products).save(saved.capture());
        assertEquals("Aisle 9", saved.getValue().getNote());
        assertEquals("Aisle 9", response.note());
        verify(alerts).evaluate(5L);
    }

    @Test
    void blankNoteClearsAndOmittedNoteLeavesItUnchanged() {
        Product product = product(5L, "keep me");
        when(stocks.findByProductIdForUpdate(5L)).thenReturn(Optional.empty());
        when(products.findById(5L)).thenReturn(Optional.of(product));
        when(products.save(any(Product.class))).thenAnswer(call -> call.getArgument(0));
        when(stocks.findByProductId(5L)).thenReturn(Optional.empty());
        when(effectiveSettings.get(5L))
                .thenReturn(new EffectiveSettings(10L, true, null, "GLOBAL", null));

        ProductResponse unchanged = service.update(
                5L, new ProductUpdateRequest(null, null, null, null));
        assertEquals("keep me", unchanged.note());

        ProductResponse cleared = service.update(
                5L, new ProductUpdateRequest(null, null, "   ", null));
        assertNull(cleared.note());
        assertNull(product.getNote());
    }

    private static Product product(Long id, String note) {
        Product product = new Product();
        product.setId(id);
        product.setSku("SKU-" + id);
        product.setName("Product " + id);
        product.setNote(note);
        product.setActive(true);
        product.setCreatedAt(NOW);
        product.setUpdatedAt(NOW);
        return product;
    }
}
