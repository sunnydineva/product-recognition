package org.sunnydineva.inventory.product;

import org.sunnydineva.inventory.common.idempotency.IdempotencyService;
import org.sunnydineva.inventory.dto.ProductCreateRequest;
import org.sunnydineva.inventory.dto.ProductResponse;
import org.sunnydineva.inventory.dto.ProductUpdateRequest;
import org.sunnydineva.inventory.dto.StockAdjustmentRequest;
import org.sunnydineva.inventory.dto.StockMovementResponse;
import org.sunnydineva.inventory.dto.StockPolicyRequest;
import org.sunnydineva.inventory.dto.StockPolicyResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

import java.time.Instant;

@RestController
@RequestMapping("/v1/products")
@Validated
@Tag(name = "Products", description = "Product catalog, stock and stock policies")
public class ProductController {

    private final ProductService productService;
    private final IdempotencyService idempotencyService;

    public ProductController(ProductService productService, IdempotencyService idempotencyService) {
        this.productService = productService;
        this.idempotencyService = idempotencyService;
    }

    @GetMapping
    @Operation(summary = "List products")
    public Page<ProductResponse> list(@RequestParam(required = false) String search,
                                      @RequestParam(required = false) Boolean active,
                                      @RequestParam(required = false, name = "hasActiveAlert") Boolean hasActiveAlert,
                                      Pageable pageable) {
        return productService.list(search, active, hasActiveAlert, pageable);
    }

    @PostMapping
    @Operation(summary = "Create product")
    public ResponseEntity<ProductResponse> create(@Valid @RequestBody ProductCreateRequest request,
                                                 @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        IdempotencyService.Result<ProductResponse> result = idempotencyService.execute(
                "product:create", idempotencyKey, request, ProductResponse.class, 201,
                () -> productService.create(request));
        return ResponseEntity.status(result.status()).body(result.body());
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get product")
    public ProductResponse get(@PathVariable Long id) {
        return productService.get(id);
    }

    @PatchMapping("/{id}")
    @Operation(summary = "Update product")
    public ProductResponse update(@PathVariable Long id, @Valid @RequestBody ProductUpdateRequest request) {
        return productService.update(id, request);
    }

    @PostMapping("/{id}/stock-adjustments")
    @Operation(summary = "Adjust stock")
    public ResponseEntity<StockMovementResponse> adjustStock(@PathVariable Long id,
                                                            @Valid @RequestBody StockAdjustmentRequest request,
                                                            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        IdempotencyService.Result<StockMovementResponse> result = idempotencyService.execute(
                "stock:adjustment:" + id, idempotencyKey, request, StockMovementResponse.class, 200,
                () -> productService.adjustStock(id, request));
        return ResponseEntity.status(result.status()).body(result.body());
    }

    @GetMapping("/{id}/stock-movements")
    @Operation(summary = "List stock movements")
    public Page<StockMovementResponse> movements(@PathVariable Long id,
                                                @RequestParam(required = false) Instant from,
                                                @RequestParam(required = false) Instant to,
                                                @RequestParam(required = false) String source,
                                                @RequestParam(required = false) org.sunnydineva.inventory.enums.StockOperation operation,
                                                Pageable pageable) {
        return productService.movements(id, from, to, source, operation, pageable);
    }

    @PutMapping("/{id}/stock-policy")
    @Operation(summary = "Update stock policy")
    public StockPolicyResponse updatePolicy(@PathVariable Long id, @Valid @RequestBody StockPolicyRequest request) {
        return productService.updatePolicy(id, request);
    }
}
