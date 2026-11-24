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

            SpringApplication application = new SpringApplication(InventoryServiceApplication.class);
            application.setWebApplicationType(WebApplicationType.NONE);
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
                            "SELECT count(*) FROM flyway_schema_history WHERE version = '1' AND success")) {
                        assertTrue(result.next());
                        assertEquals(1, result.getInt(1));
                    }
                    try (ResultSet result = statement.executeQuery(
                            "SELECT to_regclass('public.products') IS NOT NULL, "
                                    + "to_regclass('public.stock') IS NOT NULL")) {
                        assertTrue(result.next());
                        assertTrue(result.getBoolean(1), "products table missing");
                        assertTrue(result.getBoolean(2), "stock table missing");
                    }
                }
                KafkaListenerEndpointRegistry registry = context.getBean(KafkaListenerEndpointRegistry.class);
                assertFalse(registry.getListenerContainers().isEmpty());
                registry.getListenerContainers().forEach(listener -> assertFalse(listener.isRunning()));
            }
        } finally {
            // Unique test-owned container only; -v also removes anonymous volumes.
            docker("rm", "--force", "--volumes", container);
        }
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
