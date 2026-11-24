# Shared project instructions

## Architecture and conventions

- This repository contains Python AI services and a Java inventory-service scaffold. Inspect current code before relying on README roadmaps.
- `ai-service/yolo-service/`: FastAPI detection/tracking APIs, camera capture, Ultralytics YOLO11s/ByteTrack, OpenCV crop extraction and sharpness selection, and a DINOv2 HTTP client.
- `ai-service/dinov2-service/`: FastAPI embedding/catalog APIs, a CPU DINOv2 encoder, FAISS indexing, and local SKU reference images. Some recognition/catalog operations are incomplete.
- `ai-service/ocr-service/` is currently a placeholder.
- `backend/inventory-service/`: Java 25, Spring Boot 4.1.1, Maven, Web MVC, JPA, PostgreSQL, validation, and actuator dependencies. Inventory integration is not yet an implemented contract.
- Follow surrounding Python and Java naming, imports, structure, and formatting. Keep changes focused, modular, and compatible with existing callers.
- Reuse components and dependencies before adding new ones. Avoid unrelated refactoring.
- Preserve existing user changes, including staged and unstaged work. Inspect the working tree before editing. Never reset, overwrite, commit, or push user work without authorization.

## Contracts and data

- DINOv2 currently uses `facebook/dinov2-small` on CPU. Embeddings are contiguous, L2-normalized `float32` vectors of shape `(384,)`, used with FAISS inner-product search. Reuse `get_encoder()` and keep indexing/query preprocessing consistent.
- OpenCV images use BGR; the encoder accepts JPEG/PNG paths or bytes and converts to RGB with EXIF orientation. Make conversions explicit at boundaries.
- Reuse existing bounding-box clipping and crop-quality helpers. Validate invalid/empty inputs and release video/camera resources.
- OpenCV-first detection/cropping is preferred where appropriate for future work; the current YOLO-first pipeline is not authorization for an automatic migration.
- Keep weights, datasets, generated crops, indexes, credentials, and model caches out of commits. Respect existing ignore rules and do not rebuild or overwrite local artifacts incidentally.
- Preserve HTTP request/response contracts unless a breaking change is explicitly approved. Observed product counts are not automatically authoritative warehouse inventory.

## Planning and verification

- Obtain explicit approval before major features, significant architecture changes, breaking contracts, or material scope expansion. State the scope and tradeoffs before implementation.
- Use a short plan for nontrivial changes and only the specialists needed. Independent work may run concurrently when file ownership does not overlap.
- Add meaningful tests for changed behavior and regressions. Prefer deterministic offline fixtures and mocked model/network boundaries.
- Existing encoder tests, from `ai-service/`:
  `.venv/bin/python -B -m unittest discover -s dinov2-service/tests`
  Use a compatible available Python environment if this virtual environment is absent; report missing dependencies rather than claiming success.
- Java checks, from `backend/inventory-service/`: `mvn test`. This requires Java 25 and access to `org.sunnydineva:test-support-cucumber:1.0.0`. The existing feature file is empty; a successful Maven invocation alone does not establish behavioral test coverage.
- Do not use training, camera capture, model downloads, or catalog rebuilds as routine tests. Report separately when real-model, hardware, or integration checks remain necessary.
- Test execution can write artifacts; strictly read-only review requests execution from an authorized implementation agent or coordinator and evaluates the resulting evidence.
- Report changed files/behavior, exact checks and results, checks skipped and why, and unresolved risks. Distinguish baseline issues from newly introduced failures.

## OpenCode configuration

- All individual agent definitions live in `opencode.jsonc` under the native V2 `agents` object. Keep this file limited to shared project guidance.
- Use verified model identifiers and native OpenCode delegation and permissions. Do not introduce a custom orchestration framework or duplicate Markdown agent definitions.
- Never commit or push without explicit user authorization. Always ask before creating commits, and do not amend or rewrite history unless explicitly requested.
