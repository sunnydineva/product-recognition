package org.sunnydineva.inventory;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Boots production configuration, but never accepts an external database URL.
 * Requires a cached pgvector:pg17 image; no Testcontainers dependency/download.
 */
@EnabledIfEnvironmentVariable(named = "RUN_INVENTORY_DATABASE_STARTUP_TEST", matches = "1")
class DatabaseStartupTest {

    @Test
    void startupCreatesDataSourceAndMigratesInventory() throws Exception {
        String container = "inventory-startup-test-" + UUID.randomUUID();
        try {
            docker("run", "--detach", "--pull=never", "--name", container,
                    "--tmpfs", "/var/lib/postgresql/data",
                    "--publish", "127.0.0.1::5432",
                    "--env", "POSTGRES_DB=inventory_startup_test",
                    "--env", "POSTGRES_USER=inventory_test",
                    "--env", "POSTGRES_PASSWORD=disposable_test_password",
                    "pgvector/pgvector:pg17");
            awaitPostgres(container);
            String binding = docker("port", container, "5432/tcp").trim();
            assertTrue(binding.matches("127\\.0\\.0\\.1:[0-9]+"), binding);
            String port = binding.substring(binding.lastIndexOf(':') + 1);
            String databaseUrl = "jdbc:postgresql://127.0.0.1:" + port + "/inventory_startup_test";
            // Upgrade a genuine V2 database containing stock without an initial movement.
            org.flywaydb.core.Flyway.configure()
                    .dataSource(databaseUrl, "inventory_test", "disposable_test_password")
                    .target("2").load().migrate();
            try (var connection = java.sql.DriverManager.getConnection(databaseUrl,
                    "inventory_test", "disposable_test_password");
                 var statement = connection.createStatement()) {
                statement.executeUpdate("insert into products (sku, name) values ('legacy', 'Legacy')");
                statement.executeUpdate("insert into stock (product_id, quantity) "
                        + "select id, 77 from products where sku = 'legacy'");
            }

            SpringApplication application = new SpringApplication(InventoryServiceApplication.class);
            application.addPrimarySources(java.util.List.of(TestTime.class));
            application.setWebApplicationType(WebApplicationType.SERVLET);
            // Production has a custom listener factory, so the Boot auto-startup
            // property alone does not disable it. Modify only the test context.
            application.addInitializers(context -> context.addBeanFactoryPostProcessor(
                    beanFactory -> beanFactory.addBeanPostProcessor(new BeanPostProcessor() {
                        @Override
                        public Object postProcessBeforeInitialization(Object bean, String beanName) {
                            if (bean instanceof ConcurrentKafkaListenerContainerFactory<?, ?> factory) {
                                factory.setAutoStartup(false);
                            }
                            return bean;
                        }
                    })));

            try (ConfigurableApplicationContext context = application.run(
                    "--server.address=127.0.0.1",
                    "--server.port=0",
                    "--spring.datasource.url=" + databaseUrl,
                    "--spring.datasource.username=inventory_test",
                    "--spring.datasource.password=disposable_test_password",
                    "--spring.flyway.url=" + databaseUrl,
                    "--spring.flyway.user=inventory_test",
                    "--spring.flyway.password=disposable_test_password",
                    "--spring.kafka.bootstrap-servers=127.0.0.1:1",
                    "--spring.kafka.consumer.properties.schema.registry.url=http://127.0.0.1:1")) {
                DataSource dataSource = context.getBean(DataSource.class);
                try (Connection connection = dataSource.getConnection();
                     Statement statement = connection.createStatement()) {
                    try (ResultSet result = statement.executeQuery(
                            "SELECT count(*) FROM flyway_schema_history WHERE version = '4' AND success")) {
                        assertTrue(result.next());
                        assertEquals(1, result.getInt(1));
                    }
                    try (ResultSet result = statement.executeQuery(
                            "SELECT to_regclass('public.products') IS NOT NULL, "
                                    + "to_regclass('public.stock') IS NOT NULL, "
                                    + "to_regclass('public.global_stock_settings') IS NOT NULL, "
                                    + "to_regclass('public.product_stock_policies') IS NOT NULL, "
                                    + "to_regclass('public.stock_movements') IS NOT NULL, "
                                    + "to_regclass('public.alerts') IS NOT NULL, "
                                    + "to_regclass('public.idempotency_records') IS NOT NULL, "
                                    + "EXISTS (SELECT 1 FROM information_schema.columns "
                                    + "WHERE table_schema = 'public' AND table_name = 'products' "
                                    + "AND column_name = 'note' AND is_nullable = 'YES')")) {
                        assertTrue(result.next());
                        assertTrue(result.getBoolean(1), "products table missing");
                        assertTrue(result.getBoolean(2), "stock table missing");
                        assertTrue(result.getBoolean(3), "global_stock_settings table missing");
                        assertTrue(result.getBoolean(4), "product_stock_policies table missing");
                        assertTrue(result.getBoolean(5), "stock_movements table missing");
                        assertTrue(result.getBoolean(6), "alerts table missing");
                        assertTrue(result.getBoolean(7), "idempotency_records table missing");
                        assertTrue(result.getBoolean(8), "nullable products.note column missing");
                    }
                }
                verifyRapidDrop(context);
                verifyHttpSettings(context);
                KafkaListenerEndpointRegistry registry = context.getBean(KafkaListenerEndpointRegistry.class);
                assertFalse(registry.getListenerContainers().isEmpty());
                registry.getListenerContainers().forEach(listener -> assertFalse(listener.isRunning()));
            }
        } finally {
            // Unique test-owned container only; -v also removes anonymous volumes.
            docker("rm", "--force", "--volumes", container);
        }
    }

    @org.springframework.context.annotation.Configuration
    static class TestTime {
        @org.springframework.context.annotation.Bean
        @org.springframework.context.annotation.Primary
        MutableClock testClock() { return new MutableClock(); }
    }

    static class MutableClock extends java.time.Clock {
        volatile java.time.Instant now = java.time.Instant.parse("2026-11-24T12:00:00.123456Z");
        public java.time.ZoneId getZone() { return java.time.ZoneOffset.UTC; }
        public java.time.Clock withZone(java.time.ZoneId zone) { return this; }
        public java.time.Instant instant() { return now; }
    }

    private void verifyRapidDrop(ConfigurableApplicationContext context) throws Exception {
        var products = context.getBean(org.sunnydineva.inventory.product.ProductService.class);
        var alerts = context.getBean(org.sunnydineva.inventory.alert.AlertRepository.class);
        var service = context.getBean(org.sunnydineva.inventory.alert.AlertService.class);
        var sweep = context.getBean(org.sunnydineva.inventory.alert.AlertSweep.class);
        var clock = context.getBean(MutableClock.class);
        var jdbc = new org.springframework.jdbc.core.JdbcTemplate(context.getBean(DataSource.class));
        assertEquals(77L, jdbc.queryForObject("select history_initial_quantity from stock "
                + "join products on products.id = stock.product_id where sku = 'legacy'", Long.class));
        assertEquals(0, jdbc.queryForObject("select count(*) from stock_movements m "
                + "join products p on p.id = m.product_id where p.sku = 'legacy'", Integer.class));
        var product = products.create(new org.sunnydineva.inventory.dto.ProductCreateRequest(
                "Rapid test", "rapid-test", null, 100L, true));
        Long id = product.id();
        assertEquals(0, jdbc.queryForObject("select count(*) from stock_movements where product_id = ?",
                Integer.class, id));
        // Creation coverage is real, but a full window must pass before signaling.
        clock.now = clock.now.plusSeconds(86400);
        products.adjustStock(id, new org.sunnydineva.inventory.dto.StockAdjustmentRequest(
                org.sunnydineva.inventory.enums.StockOperation.DECREASE, 90L, "test", null));
        var rows = alerts.findByProductId(id);
        assertEquals(2, rows.size());
        var rapid = rows.stream().filter(a -> a.getType() ==
                org.sunnydineva.inventory.enums.AlertType.RAPID_DROP).findFirst().orElseThrow();
        assertEquals(100L, rapid.getRapidDrop().getBaseline());
        assertEquals(10L, rapid.getRapidDrop().getCurrent());
        org.junit.jupiter.api.Assertions.assertNull(rapid.getThreshold());
        var acknowledged = service.acknowledge(rapid.getId(),
                new org.sunnydineva.inventory.dto.AcknowledgeAlertRequest("test", "Investigating decline"));
        assertEquals(clock.now, acknowledged.acknowledgedAt());
        // Concurrent scheduler calls and stock mutations must serialize and deduplicate.
        try (var executor = java.util.concurrent.Executors.newFixedThreadPool(4)) {
            var tasks = new java.util.ArrayList<java.util.concurrent.Callable<Void>>();
            for (int i = 0; i < 12; i++) {
                tasks.add(() -> { service.evaluate(id); return null; });
            }
            tasks.add(() -> {
                products.adjustStock(id, new org.sunnydineva.inventory.dto.StockAdjustmentRequest(
                        org.sunnydineva.inventory.enums.StockOperation.INCREASE, 1L, "test", null));
                return null;
            });
            for (var future : executor.invokeAll(tasks)) future.get(30, TimeUnit.SECONDS);
        }
        // A later evaluation must not silently refresh the acknowledgement timestamp.
        clock.now = clock.now.plusSeconds(1);
        service.evaluate(id);
        assertEquals(2, alerts.findByProductId(id).size());
        var continuing = alerts.findById(rapid.getId()).orElseThrow();
        assertEquals(acknowledged.id(), continuing.getId());
        assertEquals(org.sunnydineva.inventory.enums.AlertStatus.ACKNOWLEDGED, continuing.getStatus());
        assertEquals(acknowledged.triggeredAt(), continuing.getTriggeredAt());
        assertEquals(acknowledged.acknowledgedAt(), continuing.getAcknowledgedAt());
        assertEquals("test", continuing.getAcknowledgedBy());
        assertEquals("Investigating decline", continuing.getNote());
        assertEquals(100L, continuing.getRapidDrop().getBaseline());
        assertEquals(11L, continuing.getRapidDrop().getCurrent());
        assertEquals(new java.math.BigDecimal("89.000000"), continuing.getRapidDrop().getMeasuredPercent());
        // Both same-microsecond movements become baseline at exactly the cutoff,
        // with the highest movement id winning the tie. No new stock mutation.
        clock.now = clock.now.plusSeconds(86399);
        sweep.evaluateAll();
        var resolved = alerts.findById(rapid.getId()).orElseThrow();
        assertEquals(org.sunnydineva.inventory.enums.AlertStatus.RESOLVED, resolved.getStatus());
        assertEquals(clock.now, resolved.getResolvedAt());
        assertEquals(continuing.getId(), resolved.getId());
        assertEquals(continuing.getTriggeredAt(), resolved.getTriggeredAt());
        assertEquals(continuing.getAcknowledgedAt(), resolved.getAcknowledgedAt());
        assertEquals(continuing.getAcknowledgedBy(), resolved.getAcknowledgedBy());
        assertEquals(continuing.getNote(), resolved.getNote());
        var lastMeasurement = continuing.getRapidDrop();
        var retainedMeasurement = resolved.getRapidDrop();
        assertEquals(lastMeasurement.getBaseline(), retainedMeasurement.getBaseline());
        assertEquals(lastMeasurement.getCurrent(), retainedMeasurement.getCurrent());
        assertEquals(lastMeasurement.getPercent(), retainedMeasurement.getPercent());
        assertEquals(lastMeasurement.getWindowHours(), retainedMeasurement.getWindowHours());
        assertEquals(lastMeasurement.getMinimumDrop(), retainedMeasurement.getMinimumDrop());
        assertEquals(lastMeasurement.getMeasuredPercent(), retainedMeasurement.getMeasuredPercent());
        var baseline = context.getBean(org.sunnydineva.inventory.stock.StockMovementRepository.class)
                .findFirstByProductIdAndCreatedAtGreaterThanEqualAndCreatedAtLessThanEqualOrderByCreatedAtDescIdDesc(
                        id, clock.now.minusSeconds(172800), clock.now.minusSeconds(86400)).orElseThrow();
        assertEquals(11L, baseline.getQuantityAfter());
        org.junit.jupiter.api.Assertions.assertThrows(org.springframework.dao.DataIntegrityViolationException.class,
                () -> jdbc.update("update global_stock_settings set rapid_drop_percent = 101 where id = 1"));
        org.junit.jupiter.api.Assertions.assertThrows(org.springframework.dao.DataIntegrityViolationException.class,
                () -> jdbc.update("update global_stock_settings set rapid_drop_minimum_drop = 0 where id = 1"));
        // Legacy clients omit the new object; global values remain unchanged.
        var settings = context.getBean(org.sunnydineva.inventory.settings.SettingsService.class);
        assertEquals(50, settings.update(new org.sunnydineva.inventory.dto.GlobalSettingsRequest(
                10L, true, null, null)).rapidDrop().percent());
        var policyProduct = products.create(new org.sunnydineva.inventory.dto.ProductCreateRequest(
                "Policy test", "policy-test", null, 100L, true));
        clock.now = clock.now.plusSeconds(86400);
        products.adjustStock(policyProduct.id(), new org.sunnydineva.inventory.dto.StockAdjustmentRequest(
                org.sunnydineva.inventory.enums.StockOperation.DECREASE, 50L, "test", null));
        assertEquals(1L, openRapidCount(alerts, policyProduct.id()));
        settings.update(new org.sunnydineva.inventory.dto.GlobalSettingsRequest(10L, true, null,
                new org.sunnydineva.inventory.dto.RapidDropPolicy(null, 60, null, null)));
        assertEquals(0L, openRapidCount(alerts, policyProduct.id()));
        products.updatePolicy(policyProduct.id(), new org.sunnydineva.inventory.dto.StockPolicyRequest(
                null, null, null, new org.sunnydineva.inventory.dto.RapidDropPolicy(null, 50, null, null)));
        assertEquals(1L, openRapidCount(alerts, policyProduct.id()));
        assertEquals(50, products.get(policyProduct.id()).effectiveSettings().rapidDrop().percent());
        // An old client must not erase an existing rapid override.
        products.updatePolicy(policyProduct.id(), new org.sunnydineva.inventory.dto.StockPolicyRequest(
                null, null, null, null));
        assertEquals(1L, openRapidCount(alerts, policyProduct.id()));
        products.updatePolicy(policyProduct.id(), new org.sunnydineva.inventory.dto.StockPolicyRequest(
                null, null, null, new org.sunnydineva.inventory.dto.RapidDropPolicy(null, null, null, null)));
        assertEquals(0L, openRapidCount(alerts, policyProduct.id()));
        assertEquals(60, products.get(policyProduct.id()).effectiveSettings().rapidDrop().percent());
    }

    private long openRapidCount(org.sunnydineva.inventory.alert.AlertRepository alerts, Long productId) {
        return alerts.findByProductId(productId).stream().filter(a ->
                a.getType() == org.sunnydineva.inventory.enums.AlertType.RAPID_DROP
                        && a.getStatus() != org.sunnydineva.inventory.enums.AlertStatus.RESOLVED).count();
    }

    private void verifyHttpSettings(ConfigurableApplicationContext context) throws Exception {
        var products = context.getBean(org.sunnydineva.inventory.product.ProductService.class);
        var settings = context.getBean(org.sunnydineva.inventory.settings.SettingsService.class);
        var product = products.create(new org.sunnydineva.inventory.dto.ProductCreateRequest(
                "HTTP policy test", "http-policy-test", null, 100L, true));
        String policyPath = "/api/v1/products/" + product.id() + "/stock-policy";
        String globalPrefix = "\"defaultLowStockThreshold\":10,\"defaultAlertEnabled\":true";
        var globalPolicy = new org.sunnydineva.inventory.dto.RapidDropPolicy(true, 65, 12, 3L);
        var override = new org.sunnydineva.inventory.dto.RapidDropPolicy(false, 70, 6, 5L);
        try (var client = java.net.http.HttpClient.newHttpClient()) {
            putJson(context, client, "/api/v1/settings",
                    "{" + globalPrefix + ",\"rapidDrop\":{\"enabled\":true,\"percent\":65,"
                            + "\"windowHours\":12,\"minimumDrop\":3}}", 200);
            // Global omission, explicit null, empty object and null members all retain values.
            for (String suffix : java.util.List.of("", ",\"rapidDrop\":null", ",\"rapidDrop\":{}",
                    ",\"rapidDrop\":{\"enabled\":null,\"percent\":null,\"windowHours\":null,\"minimumDrop\":null}")) {
                putJson(context, client, "/api/v1/settings", "{" + globalPrefix + suffix + "}", 200);
                assertEquals(globalPolicy, settings.get().rapidDrop());
            }
            putJson(context, client, policyPath,
                    "{\"rapidDrop\":{\"enabled\":false,\"percent\":70,\"windowHours\":6,\"minimumDrop\":5}}", 200);
            assertEquals(override, products.get(product.id()).effectiveSettings().rapidDrop());
            for (String body : java.util.List.of("{}", "{\"rapidDrop\":null}")) {
                putJson(context, client, policyPath, body, 200);
                assertEquals(override, products.get(product.id()).effectiveSettings().rapidDrop());
            }
            // Product empty object resets overrides instead of retaining them.
            putJson(context, client, policyPath, "{\"rapidDrop\":{}}", 200);
            assertEquals(globalPolicy, products.get(product.id()).effectiveSettings().rapidDrop());
            putJson(context, client, policyPath,
                    "{\"rapidDrop\":{\"percent\":80,\"enabled\":null,\"windowHours\":null,\"minimumDrop\":null}}", 200);
            assertEquals(new org.sunnydineva.inventory.dto.RapidDropPolicy(true, 80, 12, 3L),
                    products.get(product.id()).effectiveSettings().rapidDrop());

            // Both real MVC endpoints must reject every invalid nested bound before mutation.
            var beforeGlobal = settings.get().rapidDrop();
            var beforeProduct = products.get(product.id()).effectiveSettings().rapidDrop();
            for (String invalid : java.util.List.of("\"percent\":0", "\"percent\":101",
                    "\"windowHours\":0", "\"windowHours\":8761", "\"minimumDrop\":0", "\"minimumDrop\":-1")) {
                for (String path : java.util.List.of("/api/v1/settings", policyPath)) {
                    String prefix = path.equals("/api/v1/settings") ? globalPrefix + "," : "";
                    String response = putJson(context, client, path,
                            "{" + prefix + "\"rapidDrop\":{" + invalid + "}}", 400);
                    var json = new com.fasterxml.jackson.databind.ObjectMapper().readTree(response);
                    assertEquals("VALIDATION_ERROR", json.get("errorCode").asText());
                    String field = invalid.substring(1, invalid.indexOf('"', 1));
                    assertTrue(json.get("errors").has("rapidDrop." + field), response);
                    assertEquals(beforeGlobal, settings.get().rapidDrop());
                    assertEquals(beforeProduct, products.get(product.id()).effectiveSettings().rapidDrop());
                }
            }
        }
    }

    private String putJson(ConfigurableApplicationContext context, java.net.http.HttpClient client,
                           String path, String body, int expectedStatus) throws Exception {
        int port = context.getEnvironment().getRequiredProperty("local.server.port", Integer.class);
        var request = java.net.http.HttpRequest.newBuilder(java.net.URI.create("http://127.0.0.1:" + port + path))
                .timeout(java.time.Duration.ofSeconds(20))
                .header("Content-Type", "application/json")
                .PUT(java.net.http.HttpRequest.BodyPublishers.ofString(body)).build();
        var response = client.send(request, java.net.http.HttpResponse.BodyHandlers.ofString());
        assertEquals(expectedStatus, response.statusCode(), path + ": " + response.body());
        return response.body();
    }

    private static void awaitPostgres(String container) throws Exception {
        for (int attempt = 0; attempt < 120; attempt++) {
            // The image's temporary initialization server does not listen on TCP.
            String ready = docker("exec", container, "sh", "-c",
                    "pg_isready -h 127.0.0.1 -U inventory_test -d inventory_startup_test >/dev/null; echo $?");
            if ("0".equals(ready.trim())) {
                return;
            }
            Thread.sleep(250);
        }
        throw new IllegalStateException("Disposable PostgreSQL did not become ready");
    }

    private static String docker(String... arguments) throws Exception {
        String[] command = new String[arguments.length + 1];
        command[0] = "docker";
        System.arraycopy(arguments, 0, command, 1, arguments.length);
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        if (!process.waitFor(60, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            throw new IllegalStateException("Docker command timed out: " + arguments[0]);
        }
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (process.exitValue() != 0) {
            throw new IllegalStateException("Docker command failed: " + output);
        }
        return output;
    }
}
