# AI Product Recognition — Event Contracts

Shared Avro event contracts for Kafka. Single source of truth for events produced
and consumed by the AI service and the inventory service.

## Schemas

| Schema | Purpose |
|--------|---------|
| `ProductCreationRequested` | Create a new product in the inventory catalog. |
| `StockAdjustmentRequested` | Increase or decrease stock for an existing product. |

Both schemas include an `eventId` (UUID) field for idempotent processing.

## Layout

```
ai-pr-event-contracts/
├── schemas/          # Avro .avsc (source of truth)
├── java/             # Maven module generating Java classes
├── python/           # Python package with mirrored dataclasses
└── README.md
```

## Java

Generate and install the jar:

```bash
cd java
mvn clean install
```

Add as dependency in `inventory-service/pom.xml`:

```xml
<dependency>
    <groupId>org.sunnydineva</groupId>
    <artifactId>ai-pr-event-contracts</artifactId>
    <version>1.0.0</version>
</dependency>
```

## Python

Install the package (editable):

```bash
cd python
pip install -e .
```

## Schema Registry

Register both schemas in your Confluent Schema Registry before producing/consuming:

```bash
# Example (adjust URL)
cd /home/sunny/ss/projects/product-recognition/ai-pr-event-contracts
python3 -c 'import json,sys; print(json.dumps({"schema":open(sys.argv[1]).read()}))' \
  schemas/ProductCreationRequested.avsc \
  | curl -X POST \
      http://localhost:8087/subjects/ai.product.creation-requested-value/versions \
      -H "Content-Type: application/vnd.schemaregistry.v1+json" \
      -d @-
```

```bash
# Example (adjust URL)
      
python3 -c 'import json,sys; print(json.dumps({"schema":open(sys.argv[1]).read()}))' \
  schemas/StockAdjustmentRequested.avsc \
  | curl -X POST \
      http://localhost:8087/subjects/ai.stock.adjustment-requested-value/versions \
      -H "Content-Type: application/vnd.schemaregistry.v1+json" \
      -d @-      
```

```bash
curl -X PUT \
  http://localhost:8087/config/stock-adjustment-requests-value \
  -H "Content-Type: application/json" \
  -d '{"compatibility":"BACKWARD"}'
```

## Topics (suggested)

| Topic | Producer | Consumer |
|-------|----------|----------|
| `ai.product.creation-requested` | AI service | Inventory service |
| `ai.product.stock-adjustment-requested` | AI service | Inventory service |
