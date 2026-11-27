package org.sunnydineva.inventory;

import com.aipr.events.ProductCreationRequested;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.sunnydineva.inventory.alert.AlertService;
import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.dto.ProductResponse;
import org.sunnydineva.inventory.events.EventConsumer;
import org.sunnydineva.inventory.policy.ProductStockPolicyRepository;
import org.sunnydineva.inventory.product.Product;
import org.sunnydineva.inventory.product.ProductRepository;
import org.sunnydineva.inventory.product.ProductService;
import org.sunnydineva.inventory.settings.EffectiveSettingsService;
import org.sunnydineva.inventory.stock.Stock;
import org.sunnydineva.inventory.stock.StockMovementRepository;
import org.sunnydineva.inventory.stock.StockRepository;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class ProductCreationEventTest {

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
    void createsProductAndZeroStockWhenSkuIsAbsent() {
        when(products.existsBySku("SKU-1")).thenReturn(false);
        when(products.save(any(Product.class))).thenAnswer(call -> {
            Product product = call.getArgument(0);
            product.setId(42L);
            return product;
        });

        assertTrue(service.createFromAiEvent(" Product one ", " SKU-1 ", " Aisle 2 ", 0));

        ArgumentCaptor<Product> product = ArgumentCaptor.forClass(Product.class);
        verify(products).save(product.capture());
        assertEquals("SKU-1", product.getValue().getSku());
        assertEquals("Product one", product.getValue().getName());
        assertEquals("SKU-1", product.getValue().getBarcode());
        assertEquals("Aisle 2", product.getValue().getNote());
        assertTrue(product.getValue().isActive());
        assertEquals(NOW, product.getValue().getCreatedAt());

        ArgumentCaptor<Stock> stock = ArgumentCaptor.forClass(Stock.class);
        verify(stocks).save(stock.capture());
        assertEquals(42L, stock.getValue().getProductId());
        assertEquals(0L, stock.getValue().getQuantity());
        assertEquals(0L, stock.getValue().getHistoryInitialQuantity());
        assertEquals(NOW, stock.getValue().getHistoryStartedAt());
        verify(alerts).evaluate(42L);
    }

    @Test
    void existingSkuIsNeverOverwritten() {
        when(products.existsBySku("SKU-1")).thenReturn(true);

        assertFalse(service.createFromAiEvent("New name", "SKU-1", "New note", 25));

        verify(products, never()).save(any());
        verifyNoInteractions(stocks, alerts);
    }

    @Test
    void createsInitialStockFromEnrollmentQuantity() {
        when(products.save(any(Product.class))).thenAnswer(call -> {
            Product product = call.getArgument(0);
            product.setId(42L);
            return product;
        });
        assertTrue(service.createFromAiEvent("Product", "NEW", null, 25));
        ArgumentCaptor<Stock> stock = ArgumentCaptor.forClass(Stock.class);
        verify(stocks).save(stock.capture());
        assertEquals(25L, stock.getValue().getQuantity());
        assertEquals(25L, stock.getValue().getHistoryInitialQuantity());
    }

    @Test
    void blankNameFallsBackToSkuAndMissingBarcodeFallsBackToName() {
        when(products.existsBySku(any())).thenReturn(false);
        when(products.save(any(Product.class))).thenAnswer(call -> {
            Product product = call.getArgument(0);
            product.setId(1L);
            return product;
        });

        assertTrue(service.createFromAiEvent(" ", "SKU-1", " ", 0));
        ArgumentCaptor<Product> first = ArgumentCaptor.forClass(Product.class);
        verify(products).save(first.capture());
        assertEquals("SKU-1", first.getValue().getName());
        assertEquals("SKU-1", first.getValue().getBarcode());
        assertNull(first.getValue().getNote());

        assertTrue(service.createFromAiEvent("Name only", null, "note", 0));
        ArgumentCaptor<Product> second = ArgumentCaptor.forClass(Product.class);
        verify(products, org.mockito.Mockito.times(2)).save(second.capture());
        Product secondProduct = second.getAllValues().get(1);
        assertEquals("Name only", secondProduct.getSku());
        assertEquals("Name only", secondProduct.getName());
        assertNull(secondProduct.getBarcode());
        assertEquals("note", secondProduct.getNote());

        assertFalse(service.createFromAiEvent(" ", " ", "note", 0));
        verify(products, org.mockito.Mockito.times(2)).save(any());
    }

    @Test
    void productResponseExposesCanonicalNote() {
        Product product = new Product();
        product.setId(5L);
        product.setSku("SKU-5");
        product.setName("Product five");
        product.setNote("Aisle 2");
        when(products.findById(5L)).thenReturn(Optional.of(product));
        when(stocks.findByProductId(5L)).thenReturn(Optional.empty());
        when(effectiveSettings.get(5L))
                .thenReturn(new EffectiveSettings(10L, true, null, "GLOBAL", null));

        ProductResponse response = service.get(5L);

        assertEquals("Aisle 2", response.note());
    }

    @Test
    void consumerDelegatesAndPropagatesPersistenceFailures() {
        ProductService mockService = mock(ProductService.class);
        EventConsumer consumer = new EventConsumer(mockService);
        ProductCreationRequested event = new ProductCreationRequested(
                "event-1", "Name", "SKU-1", 0, 123L, "note");

        when(mockService.createFromAiEvent("Name", "SKU-1", "note", 0)).thenReturn(true);
        consumer.onProductCreation(event);
        verify(mockService).createFromAiEvent("Name", "SKU-1", "note", 0);

        when(mockService.createFromAiEvent("Name", "SKU-1", "note", 0))
                .thenThrow(new IllegalStateException("database unavailable"));
        assertThrows(IllegalStateException.class, () -> consumer.onProductCreation(event));
    }
}
