Nexa Beeper Connector
======================

Description
-----------
Nexa Beeper Connector

This repository implements a small connector that listens for messages (e.g., from Matrix), runs a lightweight AI pipeline to decide actions, persists those actions, and exposes an API for inspection. It is structured into a few logical areas described below.

Directory roles
---------------
- ai/  🔧
  - Contains the AI pipeline: classification, normalization, and policy decision code. The modules are intentionally small and easily replaceable with more sophisticated models.

- sidecar/  🚀
  - Implements the AI sidecar service that accepts messages via an HTTP API, runs the AI worker, persists actions, and provides endpoints to inspect stored actions and metrics.

- bridge/  🔁
  - Contains the execution bridge that claims pending actions, executes them (e.g., notify, escalate), and maintains a cursor so actions are processed in order and survive restarts.

- tests/  ✅
  - Small scripts for integration-style tests that exercise the message -> action -> execution flow.

- docs/ (not present yet)
  - Suggested place for longer design documents or migration notes.

Notes
-----
- The project uses SQLite for lightweight persistence so the system can be run locally or in small deployments.
- There are deliberate helpers to allow backward-compatible schema changes (best-effort fallbacks) to avoid forcing immediate migrations in development environments.

Contributing
------------
- Add or update unit/integration tests when changing behavior around persistence, duplicate detection, and execution semantics.
- If you modify the DB schema, add a migration and tests to the `tests/` directory.
