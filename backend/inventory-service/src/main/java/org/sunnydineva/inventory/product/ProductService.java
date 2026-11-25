package org.sunnydineva.inventory.product;

import org.sunnydineva.inventory.alert.AlertService;
import org.sunnydineva.inventory.common.EffectiveSettings;
import org.sunnydineva.inventory.common.exception.ConflictException;
import org.sunnydineva.inventory.common.exception.NotFoundException;
import org.sunnydineva.inventory.dto.ProductCreateRequest;
import org.sunnydineva.inventory.dto.ProductResponse;
import org.sunnydineva.inventory.dto.ProductUpdateRequest;
import org.sunnydineva.inventory.dto.StockMovementResponse;
import org.sunnydineva.inventory.dto.StockPolicyRequest;
import org.sunnydineva.inventory.dto.StockPolicyResponse;
import org.sunnydineva.inventory.settings.EffectiveSettingsService;
import org.sunnydineva.inventory.stock.Stock;
import org.sunnydineva.inventory.stock.StockMovement;
import org.sunnydineva.inventory.stock.StockMovementRepository;
import org.sunnydineva.inventory.stock.StockMovementSpecifications;
import org.sunnydineva.inventory.stock.StockRepository;
import org.sunnydineva.inventory.policy.ProductStockPolicy;
import org.sunnydineva.inventory.policy.ProductStockPolicyRepository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Service
public class ProductService {

    private final ProductRepository productRepository;
    private final StockRepository stockRepository;
    private final StockMovementRepository movementRepository;
    private final ProductStockPolicyRepository policyRepository;
    private final EffectiveSettingsService effectiveSettingsService;
    private final AlertService alertService;
    private final java.time.Clock clock;

    public ProductService(ProductRepository productRepository,
                          StockRepository stockRepository,
                          StockMovementRepository movementRepository,
                          ProductStockPolicyRepository policyRepository,
                          EffectiveSettingsService effectiveSettingsService,
                          AlertService alertService, java.time.Clock clock) {
        this.productRepository = productRepository;
        this.stockRepository = stockRepository;
        this.movementRepository = movementRepository;
        this.policyRepository = policyRepository;
        this.effectiveSettingsService = effectiveSettingsService;
        this.alertService = alertService;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public Page<ProductResponse> list(String search, Boolean active, Boolean hasActiveAlert, Pageable pageable) {
        Specification<Product> spec = ProductSpecifications.filter(search, active, hasActiveAlert);
        return productRepository.findAll(spec, pageable).map(product -> toResponse(product));
    }

    @Transactional
    public ProductResponse create(ProductCreateRequest request) {
        if (productRepository.existsBySku(request.sku())) {
            throw new ConflictException("SKU already exists: " + request.sku());
        }
        Instant now = clock.instant().truncatedTo(java.time.temporal.ChronoUnit.MICROS);
        Product product = new Product();
        product.setName(request.name());
        product.setSku(request.sku());
        product.setBarcode(request.barcode());
        product.setActive(request.active() == null ? true : request.active());
        product.setCreatedAt(now);
        product.setUpdatedAt(now);
        product = productRepository.save(product);

        Stock stock = new Stock();
        stock.setProductId(product.getId());
        stock.setQuantity(request.initialQuantity() == null ? 0L : request.initialQuantity());
        stock.setUpdatedAt(now);
        stock.setHistoryStartedAt(now);
        stock.setHistoryInitialQuantity(stock.getQuantity());
        stockRepository.save(stock);

        alertService.evaluate(product.getId());
        return toResponse(product);
    }

    @Transactional(readOnly = true)
    public ProductResponse get(Long id) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Product not found: " + id));
        return toResponse(product);
    }

    @Transactional
    public ProductResponse update(Long id, ProductUpdateRequest request) {
        stockRepository.findByProductIdForUpdate(id);
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Product not found: " + id));
        if (request.name() != null) {
            if (request.name().isBlank()) {
                throw new org.sunnydineva.inventory.common.exception.BadRequestException("name must not be blank");
            }
            product.setName(request.name());
        }
        if (request.barcode() != null) {
            product.setBarcode(request.barcode());
        }
        if (request.active() != null) {
            product.setActive(request.active());
        }
        product.setUpdatedAt(Instant.now());
        productRepository.save(product);
        // settings/policy unchanged but stock threshold maybe product active? Evaluate anyway.
        alertService.evaluate(product.getId());
        return toResponse(product);
    }

    @Transactional
    public org.sunnydineva.inventory.dto.StockMovementResponse adjustStock(Long productId,
                                                                           org.sunnydineva.inventory.dto.StockAdjustmentRequest request) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new NotFoundException("Product not found: " + productId));
        Stock stock = stockRepository.findByProductIdForUpdate(productId).orElse(null);
        if (stock == null) {
            stock = new Stock();
            stock.setProductId(productId);
            stock.setQuantity(0L);
            stock.setHistoryStartedAt(clock.instant().truncatedTo(java.time.temporal.ChronoUnit.MICROS));
            stock.setHistoryInitialQuantity(0L);
            stock.setUpdatedAt(Instant.now());
            stock = stockRepository.save(stock);
        }
        long delta = request.operation() == org.sunnydineva.inventory.enums.StockOperation.INCREASE
                ? request.quantity()
                : -request.quantity();
        long newQuantity;
        try {
            newQuantity = Math.addExact(stock.getQuantity(), delta);
        } catch (ArithmeticException exception) {
            throw new org.sunnydineva.inventory.common.exception.BadRequestException("Stock quantity overflow");
        }
        if (newQuantity < 0) {
            throw new org.sunnydineva.inventory.common.exception.BadRequestException("Insufficient stock");
        }
        stock.setQuantity(newQuantity);
        stock.setUpdatedAt(Instant.now());
        stockRepository.save(stock);

        StockMovement movement = new StockMovement();
        movement.setProductId(productId);
        movement.setQuantityDelta(delta);
        movement.setQuantityAfter(newQuantity);
        movement.setOperation(request.operation());
        movement.setSource(request.source());
        movement.setNote(request.note());
        movement.setCreatedAt(clock.instant().truncatedTo(java.time.temporal.ChronoUnit.MICROS));
        movement = movementRepository.save(movement);

        alertService.evaluate(productId);
        return new org.sunnydineva.inventory.dto.StockMovementResponse(
                movement.getId(),
                movement.getProductId(),
                movement.getQuantityDelta(),
                movement.getQuantityAfter(),
                movement.getOperation(),
                movement.getSource(),
                movement.getNote(),
                movement.getCreatedAt());
    }

    @Transactional(readOnly = true)
    public Page<org.sunnydineva.inventory.dto.StockMovementResponse> movements(Long productId, Instant from, Instant to,
                                                                               String source,
                                                                               org.sunnydineva.inventory.enums.StockOperation operation,
                                                                               Pageable pageable) {
        if (!productRepository.existsById(productId)) {
            throw new NotFoundException("Product not found: " + productId);
        }
        Specification<StockMovement> spec = StockMovementSpecifications.filter(productId, from, to, source, operation);
        return movementRepository.findAll(spec, pageable).map(m -> new org.sunnydineva.inventory.dto.StockMovementResponse(
                m.getId(),
                m.getProductId(),
                m.getQuantityDelta(),
                m.getQuantityAfter(),
                m.getOperation(),
                m.getSource(),
                m.getNote(),
                m.getCreatedAt()));
    }

    @Transactional
    public StockPolicyResponse updatePolicy(Long productId, StockPolicyRequest request) {
        stockRepository.findByProductIdForUpdate(productId);
        if (!productRepository.existsById(productId)) {
            throw new NotFoundException("Product not found: " + productId);
        }
        ProductStockPolicy policy = policyRepository.findById(productId).orElse(null);
        if (policy == null) {
            policy = new ProductStockPolicy();
            policy.setProductId(productId);
        }
        policy.setLowStockThreshold(request.lowStockThreshold());
        policy.setAlertEnabled(request.alertEnabled());
        policy.setReorderQuantity(request.reorderQuantity());
        if (request.rapidDrop() != null) {
            policy.setRapidDrop(request.rapidDrop());
        }
        policy.setUpdatedAt(Instant.now());
        policyRepository.save(policy);
        alertService.evaluate(productId);
        return new StockPolicyResponse(
                policy.getProductId(),
                policy.getLowStockThreshold(),
                policy.getAlertEnabled(),
                policy.getReorderQuantity(),
                policy.getUpdatedAt(), policy.getRapidDrop());
    }

    private ProductResponse toResponse(Product product) {
        Stock stock = stockRepository.findByProductId(product.getId()).orElse(null);
        long quantity = stock != null ? stock.getQuantity() : 0L;
        Instant stockUpdatedAt = stock != null ? stock.getUpdatedAt() : product.getUpdatedAt();
        EffectiveSettings es = effectiveSettingsService.get(product.getId());
        return new ProductResponse(
                product.getId(),
                product.getSku(),
                product.getName(),
                product.getBarcode(),
                product.isActive(),
                product.getCreatedAt(),
                product.getUpdatedAt(),
                new ProductResponse.StockResponse(quantity, stockUpdatedAt),
                new ProductResponse.EffectiveSettingsResponse(
                        es.lowStockThreshold(),
                        es.alertEnabled(),
                        es.reorderQuantity(),
                        es.source(), es.rapidDrop()));
    }
}
