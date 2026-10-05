"""Shared pytest config for backend tests.

`pytest-asyncio` 1.x defaults to per-function event loops, but our codebase
holds a Motor `AsyncIOMotorClient` at module-import time (`server.db`).
Rebinding it to a new loop per test breaks every async test that touches
the shared client. Loop scope is forced to `session` via `pytest.ini`.
"""
