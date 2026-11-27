package org.sunnydineva.inventory.events;

import com.aipr.events.ProductCreationRequested;
import com.aipr.events.StockAdjustmentRequested;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.sunnydineva.inventory.product.ProductService;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class EventConsumer {

    private static final Logger log = LoggerFactory.getLogger(EventConsumer.class);

    private final ProductService productService;

    public EventConsumer(ProductService productService) {
        this.productService = productService;
    }

    @KafkaListener(topics = "ai.product.creation-requested", groupId = "inventory-service")
    public void onProductCreation(ProductCreationRequested event) {
        log.info("Received ProductCreationRequested: eventId={}, name={}, barcode={}, initialQuantity={}, timestamp={}, note={}",
                event.getEventId(), event.getName(), event.getBarcode(),
                event.getInitialQuantity(), event.getTimestamp(), event.getNote());

        boolean created = productService.createFromAiEvent(
                event.getName(), event.getBarcode(), event.getNote(), event.getInitialQuantity());

        if (created) {
            log.info("Created inventory product from AI event: eventId={}, barcode={}, name={}",
                    event.getEventId(), event.getBarcode(), event.getName());
        } else {
            log.info("Skipped AI product creation because the SKU already exists or no identifier was supplied: "
                    + "eventId={}, barcode={}, name={}", event.getEventId(), event.getBarcode(), event.getName());
        }
    }

    @KafkaListener(topics = "ai.product.stock-adjustment-requested", groupId = "inventory-service")
    public void onStockAdjustment(StockAdjustmentRequested event) {
        log.info("Received StockAdjustmentRequested: eventId={}, productId={}, quantity={}, operation={}, timestamp={}, note={}",
                event.getEventId(), event.getProductId(), event.getQuantity(),
                event.getOperation(), event.getTimestamp(), event.getNote());
    }
}
