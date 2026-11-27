# Inventory control UI

Open `/api/inventory/ui/` on the inventory origin or shared tunnel hostname.
No JavaScript build or Node backend is required. Camera/enrollment navigation
uses the shared tunnel hostname; those links are not served by local port 8080.

- Product search and paging use canonical inventory data.
- Selecting a product loads its stock and paginated movement history.
- Manual corrections use positive integer INCREASE/DECREASE deltas, not absolute
  counts, with source `MANUAL_UI`, optional note and an explicit confirmation.
- A correction is marked applied only after a successful stock-movement response.
  Refresh failures do not revoke that confirmation; refresh the list/history again.
- While an outcome is uncertain, no new correction can be submitted in that tab.
  An explicit retry reuses the exact body and Idempotency-Key. Pending requests
  survive reload via sessionStorage, but not closing the tab. Do not clear storage
  or open another tab to repeat an uncertain operation; inspect movement history.
- No polling, camera calls, recognition calls, or Kafka changes are introduced.
  AI Kafka delivery and inventory application remain **unconfirmed**, not inferred
  from recognition success or a matching SKU.

This UI adds no authentication. Existing network/access restrictions still apply.
UI corrections mutate real stock; automated tests must use mocks or disposable DBs.

Offline JavaScript checks (Node built-ins only), from this directory:

```sh
node --test src/test/ui/control.test.mjs
```

The opt-in `DatabaseStartupTest` checks page/assets on an isolated server/database.
