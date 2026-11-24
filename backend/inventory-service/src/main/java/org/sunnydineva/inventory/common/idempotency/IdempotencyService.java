package org.sunnydineva.inventory.common.idempotency;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.SerializationFeature;

import org.sunnydineva.inventory.common.exception.ConflictException;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Optional;

@Service
public class IdempotencyService {

    private final IdempotencyRecordRepository repository;
    private final ObjectMapper objectMapper;

    public IdempotencyService(IdempotencyRecordRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    public record Result<T>(boolean replayed, int status, T body) {
    }

    @Transactional
    public <T> Result<T> execute(String scope, String key, Object request, Class<T> responseType,
                                 int successStatus, java.util.function.Supplier<T> action) {
        if (key == null || key.isBlank()) {
            T response = action.get();
            return new Result<>(false, successStatus, response);
        }
        String hash = hash(request);
        Optional<IdempotencyRecord> existing = repository.findByScopeAndIdempotencyKey(scope, key);
        if (existing.isPresent()) {
            IdempotencyRecord record = existing.get();
            if (!record.getRequestHash().equals(hash)) {
                throw new ConflictException("Idempotency key reused with a different request");
            }
            T body = deserialize(record.getResponseBody(), responseType);
            return new Result<>(true, record.getResponseStatus(), body);
        }
        T response = action.get();
        IdempotencyRecord record = new IdempotencyRecord();
        record.setScope(scope);
        record.setIdempotencyKey(key);
        record.setRequestHash(hash);
        record.setResponseStatus(successStatus);
        record.setResponseBody(serialize(response));
        try {
            repository.saveAndFlush(record);
        } catch (org.springframework.dao.DataIntegrityViolationException ex) {
            IdempotencyRecord current = repository.findByScopeAndIdempotencyKey(scope, key)
                    .orElseThrow(() -> ex);
            if (!current.getRequestHash().equals(hash)) {
                throw new ConflictException("Idempotency key reused with a different request");
            }
            T body = deserialize(current.getResponseBody(), responseType);
            return new Result<>(true, current.getResponseStatus(), body);
        }
        return new Result<>(false, successStatus, response);
    }

    private String hash(Object request) {
        try {
            ObjectMapper mapper = objectMapper.copy();
            mapper.configure(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY, true);
            mapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
            String json = mapper.writeValueAsString(request);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(json.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to hash idempotency request", e);
        }
    }

    private String serialize(Object response) {
        try {
            return objectMapper.writeValueAsString(response);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize idempotency response", e);
        }
    }

    private <T> T deserialize(String json, Class<T> type) {
        try {
            return objectMapper.readValue(json, type);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to deserialize idempotency response", e);
        }
    }
}
