import httpx
import pytest

from agentprobe.cli import parser
from agentprobe.providers import OpenAIProvider, ProviderError


def response(status=200, usage=True):
    body = {
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}]
    }
    if usage:
        body["usage"] = {"prompt_tokens": 100, "completion_tokens": 20}
    return httpx.Response(status, json=body, headers={"Retry-After": "0"})


@pytest.mark.asyncio
async def test_transient_retry_and_explicit_cost_accounting():
    attempts = []

    def remote(request):
        attempts.append(request)
        return response(429 if len(attempts) == 1 else 200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
        provider = OpenAIProvider(
            client, "https://local/v1", "private", "m", retries=2, input_price=2, output_price=10
        )
        assert (await provider.chat([])).content == "ok"
    usage = provider.accounting()
    assert usage["requests"] == 1
    assert usage["attempts"] == 2
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 20
    assert usage["estimated_cost_usd"] == pytest.approx(0.0004)
    assert usage["duration_seconds"] >= 0
    assert "private" not in str(usage)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,retries,expected", [(401, 2, 1), (503, 2, 3), (429, 0, 1)])
async def test_retry_boundaries(status, retries, expected):
    attempts = []

    def remote(request):
        attempts.append(request)
        return response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
        provider = OpenAIProvider(client, "https://local", "", "m", retries=retries)
        with pytest.raises(ProviderError):
            await provider.chat([])
    assert len(attempts) == expected
    assert provider.accounting()["failures"] == 1
    assert provider.accounting()["estimated_cost_usd"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage",
    [
        None,
        {"prompt_tokens": -1, "completion_tokens": 2},
        {"prompt_tokens": True, "completion_tokens": 2},
    ],
)
async def test_missing_or_invalid_usage_never_claims_free_cost(usage):
    def remote(request):
        result = response(usage=False)
        body = result.json()
        if usage is not None:
            body["usage"] = usage
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
        provider = OpenAIProvider(client, "https://local", "", "m", input_price=1, output_price=1)
        await provider.chat([])
    assert provider.accounting()["unknown_usage_requests"] == 1
    assert provider.accounting()["estimated_cost_usd"] is None


@pytest.mark.asyncio
async def test_read_timeout_is_not_replayed():
    attempts = []

    def remote(request):
        attempts.append(request)
        raise httpx.ReadTimeout("secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as client:
        provider = OpenAIProvider(client, "https://local", "", "m", retries=2)
        with pytest.raises(ProviderError, match="transport failure"):
            await provider.chat([])
    assert len(attempts) == 1


@pytest.mark.parametrize(
    "options",
    [
        {"retries": -1},
        {"retries": 6},
        {"input_price": -1},
        {"input_price": float("nan")},
        {"output_price": 1},
    ],
)
def test_invalid_retry_or_price_options(options):
    with pytest.raises(ValueError):
        OpenAIProvider(None, "https://local", "", "m", **options)


def test_mock_is_cli_default():
    assert (
        parser().parse_args(["generate", "contract.yaml", "--out", "suite.json"]).provider == "mock"
    )
