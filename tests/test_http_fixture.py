"""The local HTTP fixture must accept a runner-sized burst before its thread is scheduled."""

import asyncio
import threading
from http.server import ThreadingHTTPServer

import pytest
from test_providers import completion, endpoint


@pytest.mark.asyncio
async def test_listener_queues_six_connections_before_accept_thread_runs(monkeypatch):
    serve = ThreadingHTTPServer.serve_forever
    allow_accept = threading.Event()
    writers = []

    def delayed_accept(server):
        allow_accept.wait()
        serve(server)

    # Control thread scheduling, not HTTP or provider behavior. The listener is real.
    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", delayed_accept)
    with endpoint(completion({"content": "ok"})) as (url, _):
        port = int(url.split(":")[2].split("/")[0])

        async def connect():
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writers.append(writer)

        try:
            outcomes = await asyncio.wait_for(
                asyncio.gather(*(connect() for _ in range(6)), return_exceptions=True), timeout=2
            )
            assert all(outcome is None for outcome in outcomes), outcomes
        finally:
            for writer in writers:
                writer.close()
            allow_accept.set()
