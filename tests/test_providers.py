import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from agentprobe.adapters import CallableAgent, HttpAgent, load_callable
from agentprobe.models import Message, Reply, Tool
from agentprobe.providers import OpenAIProvider, ProviderError


@contextmanager
def endpoint(response, status=200):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(
                (
                    self.path,
                    self.headers.get("Authorization"),
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            body = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def completion(message):
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", **message}}]}


@pytest.mark.asyncio
async def test_http_chat_uses_real_wire_contract():
    with endpoint(completion({"content": "Hello"})) as (url, received):
        async with httpx.AsyncClient(trust_env=False) as client:
            provider = OpenAIProvider(client, url, "secret-test", "local-model")
            reply = await provider.chat([Message(role="user", content="Hi")], json_mode=True)
    assert reply.content == "Hello"
    path, auth, body = received[0]
    assert path == "/v1/chat/completions"
    assert auth == "Bearer secret-test"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [{"role": "user", "content": "Hi"}]


@pytest.mark.asyncio
async def test_http_agent_records_attempted_tools():
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "lookup", "arguments": '{"id": "A"}'},
    }
    with endpoint(completion({"content": None, "tool_calls": [call]})) as (url, received):
        async with httpx.AsyncClient(trust_env=False) as client:
            agent = HttpAgent(OpenAIProvider(client, url + "/chat/completions", "", "local"))
            reply = await agent.respond(
                [Message(role="user", content="Find A")],
                [Tool(name="lookup", description="Find item")],
            )
    assert reply.tool_calls[0].arguments == {"id": "A"}
    assert received[0][1] is None
    assert received[0][2]["tools"][0]["function"]["name"] == "lookup"


@pytest.mark.parametrize(
    "response,status",
    [
        ({"choices": []}, 200),
        ({"error": "secret-test"}, 401),
        (completion({"content": ""}), 200),
        ({"choices": [{"finish_reason": "length", "message": {"content": "cut"}}]}, 200),
    ],
)
@pytest.mark.asyncio
async def test_http_failures_do_not_leak_response_or_key(response, status):
    with endpoint(response, status) as (url, _):
        async with httpx.AsyncClient(trust_env=False) as client:
            with pytest.raises(ProviderError) as exc:
                await OpenAIProvider(client, url, "secret-test", "model").chat([])
    assert "secret-test" not in str(exc.value)


@pytest.mark.parametrize(
    "url",
    ["file:///tmp/secret", "ftp://host", "https://user:pass@host/v1", "https://host/v1?key=secret"],
)
def test_provider_rejects_unsafe_base_urls(url):
    with pytest.raises(ValueError):
        OpenAIProvider(None, url, "", "m")


@pytest.mark.asyncio
async def test_sync_and_async_callable_adapters():
    def sync(messages):
        return "answer to " + messages[-1].content

    async def asynchronous(messages):
        return Reply(content="async " + messages[-1].content)

    for function, expected in [(sync, "answer to hi"), (asynchronous, "async hi")]:
        reply = await CallableAgent(function, "test").respond(
            [Message(role="user", content="hi")], []
        )
        assert reply.content == expected


@pytest.mark.asyncio
async def test_callable_invalid_return_fails_closed():
    with pytest.raises(ValueError, match="string or Reply"):
        await CallableAgent(lambda _: 7, "bad").respond([], [])


@pytest.mark.parametrize("target", ["missingcolon", "json:missing", "json:__name__"])
def test_invalid_import_is_actionable(target):
    with pytest.raises(ValueError, match="callable"):
        load_callable(target)
