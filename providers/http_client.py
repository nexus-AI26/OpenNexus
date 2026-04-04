from __future__ import annotations

import threading

import httpx

_local = threading.local()


def get_shared_http_client() -> httpx.AsyncClient:
    client = getattr(_local, "client", None)
    if client is None or client.is_closed:
        _local.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=5.0),
            limits=httpx.Limits(
                max_keepalive_connections=48,
                max_connections=100,
            ),
        )
    return _local.client
