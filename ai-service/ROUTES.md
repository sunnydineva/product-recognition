# AI HTTP routes

Only canonical operations appear in OpenAPI. Legacy API paths call the same
handlers (no POST or WebSocket redirects). No payload or business logic changes.

| Service | Method | Canonical path | Hidden legacy path |
| --- | --- | --- | --- |
| DINOv2 | POST | `/api/recognition/recognize` | `/recognize` |
| DINOv2 | POST | `/api/recognition/encode` | `/encode` |
| DINOv2 | GET | `/api/recognition/health` | `/recognize/health`, local `/health` |
| DINOv2 | GET, PATCH | `/api/recognition/settings` | — |
| DINOv2 | GET | `/api/recognition/catalog/skus` | `/catalog/skus` |
| DINOv2 | POST | `/api/recognition/catalog/{sku}/images` | `/catalog/{sku}/images` |
| YOLO | POST | `/api/yolo/detect` | `/detect` |
| YOLO | POST | `/api/yolo/track` | `/track` |
| YOLO | POST | `/api/yolo/track-video` | `/track-video` |
| YOLO | GET | `/api/yolo/names` | `/yolo-names` |
| YOLO | GET | `/api/yolo/health` | `/health` |
| YOLO | POST | `/api/yolo/products/preview` | `/api/products/preview` |
| YOLO | POST | `/api/yolo/products/approve` | `/api/products/approve` |
| YOLO | GET | `/api/yolo/products/db-status/{sku}` | `/api/products/db-status/{sku}` |
| YOLO | GET | `/api/yolo/camera/status` | `/camera/status` |
| YOLO | POST | `/api/yolo/camera/start`, `/api/yolo/camera/stop` | `/camera/start`, `/camera/stop` |
| YOLO | GET | `/api/yolo/camera/stream` | `/camera/stream` |
| YOLO | WebSocket | `/api/yolo/camera/ws` | `/camera/ws` |

WebSockets are API routes but OpenAPI does not represent WebSocket operations.
YOLO HTML `/enroll`, `/camera` and JS `/enroll.js`, `/camera.js` stay outside
`/api` and are not listed in OpenAPI.

Docs/schema/ReDoc: YOLO `/yolo/docs`, `/yolo/openapi.json`, `/yolo/redoc`;
DINOv2 `/recognize/docs`, `/recognize/openapi.json`, `/recognize/redoc`.
Root `/docs`, `/openapi.json`, `/redoc` remain local compatibility aliases on
each service; publicly these and `/health` belong to YOLO.

## Deprecated file catalog

Both canonical catalog operations are marked deprecated in OpenAPI, but remain
available with their legacy aliases. No current repository production callers
were found; the offline test calls the image placeholder. This is not proof
that external clients do not use them. GET lists local catalog directories;
POST still returns its existing TODO response. `build_index.py` separately
reads that file catalog for FAISS. Current enrollment calls the encoder and
saves embeddings in PostgreSQL; recognition searches PostgreSQL. No catalog
data or indexing behavior was changed.

## Tunnel and deployment

`cloudflared/config.yml` explicitly bounds known paths to the configured host:
DINOv2 → port 18102, YOLO → port 18101, everything else → HTTP 404. Arbitrary
`/api/*`, `/recognize/*` or host paths are not forwarded. WebSocket paths use
the YOLO origin, with the usual HTTP upgrade. Ingress accepts an optional final
slash; FastAPI HTTP routes retain their normal 307 slash normalization.
Use the exact slashless WebSocket URLs (no HTTP redirect handshake).

The frontend's pre-existing DELETE preview-session cleanup has no backend
endpoint; its 404 is tolerated. No cleanup endpoint was added to ingress.
Settings still lack application authentication; this change adds no auth.
Protect public access with deployment policy before untrusted exposure.

After validation, reload/restart both Python services and restart cloudflared
to apply these changes. No restart is part of the offline verification.
Environment overrides remain authoritative; only known default legacy URLs
in the local `.env` may be migrated, never arbitrary custom URLs.
