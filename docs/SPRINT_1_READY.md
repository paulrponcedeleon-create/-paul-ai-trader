# Sprint 1 — Readiness and data directory

Adds `PAUL_DATA_DIR` with default `./data`, resolved through application settings. The readiness service validates configuration, current trading mode, data directory availability without creating it, database connectivity, and required tables.

`GET /health` remains unchanged. `GET /ready` returns `200` when ready and `503` with safe public errors when not ready.
