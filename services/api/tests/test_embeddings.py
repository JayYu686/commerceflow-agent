import json

import httpx
import pytest

from app.core.config import Settings
from app.services.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
    create_embedding_provider,
)


def embedding_payload(count: int, dimensions: int = EMBEDDING_DIMENSION) -> dict:
    return {
        "data": [
            {"index": index, "embedding": [float(index + 1)] * dimensions} for index in range(count)
        ]
    }


def test_openai_compatible_embedding_provider_batches_and_validates_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        return httpx.Response(200, json=embedding_payload(len(body["input"])))

    provider = OpenAICompatibleEmbeddingProvider(
        model="embed-test-v1",
        api_key="test-only-key",
        base_url="https://embedding.example/v1/",
        timeout_seconds=5,
        batch_size=2,
        transport=httpx.MockTransport(handler),
    )

    vectors = provider.embed(["one", "two", "three"])

    assert len(vectors) == 3
    assert all(len(vector) == EMBEDDING_DIMENSION for vector in vectors)
    assert len(requests) == 2
    assert all(request.url.path == "/v1/embeddings" for request in requests)
    assert all(request.headers["authorization"] == "Bearer test-only-key" for request in requests)


@pytest.mark.parametrize(
    "payload",
    [
        embedding_payload(2),
        embedding_payload(1, dimensions=12),
        {"data": [{"index": 1, "embedding": [0.0] * EMBEDDING_DIMENSION}]},
    ],
)
def test_openai_compatible_embedding_provider_rejects_invalid_payload(payload: dict) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        model="embed-test-v1",
        api_key="test-only-key",
        base_url="https://embedding.example/v1",
        timeout_seconds=5,
        batch_size=32,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(EmbeddingProviderError):
        provider.embed(["one"])


def test_openai_compatible_embedding_provider_maps_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    provider = OpenAICompatibleEmbeddingProvider(
        model="embed-test-v1",
        api_key="test-only-key",
        base_url="https://embedding.example/v1",
        timeout_seconds=5,
        batch_size=32,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingProviderError, match="request failed"):
        provider.embed(["one"])


def test_embedding_provider_factory_requires_complete_configuration() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="openai_compatible",
        embedding_model="",
        embedding_api_key="",
        embedding_base_url="",
    )

    with pytest.raises(EmbeddingProviderError, match="incomplete"):
        create_embedding_provider(settings)


def test_embedding_provider_factory_rejects_non_1536_dimension() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="openai_compatible",
        embedding_model="embed-test-v1",
        embedding_api_key="test-only-key",
        embedding_base_url="https://embedding.example/v1",
        embedding_dimensions=1024,
    )

    with pytest.raises(EmbeddingProviderError, match="1536"):
        create_embedding_provider(settings)
