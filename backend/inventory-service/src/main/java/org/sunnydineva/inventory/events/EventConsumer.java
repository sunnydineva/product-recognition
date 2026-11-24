package org.sunnydineva.inventory.events;

import com.aipr.events.ProductCreationRequested;
import com.aipr.events.StockAdjustmentRequested;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class EventConsumer {

    private static final Logger log = LoggerFactory.getLogger(EventConsumer.class);

    @KafkaListener(topics = "ai.product.creation-requested", groupId = "inventory-service")
    public void onProductCreation(ProductCreationRequested event) {
        log.info("Received ProductCreationRequested: eventId={}, name={}, barcode={}, initialQuantity={}, timestamp={}, note={}",
                event.getEventId(), event.getName(), event.getBarcode(),
                event.getInitialQuantity(), event.getTimestamp(), event.getNote());
    }

    @KafkaListener(topics = "ai.product.stock-adjustment-requested", groupId = "inventory-service")
    public void onStockAdjustment(StockAdjustmentRequested event) {
        log.info("Received StockAdjustmentRequested: eventId={}, productId={}, quantity={}, operation={}, timestamp={}, note={}",
                event.getEventId(), event.getProductId(), event.getQuantity(),
                event.getOperation(), event.getTimestamp(), event.getNote());
    }
}
