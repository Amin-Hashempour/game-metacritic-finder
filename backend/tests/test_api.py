from pathlib import Path

import httpx
import pytest

from app.main import app
from app.provider import MetacriticProvider


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_search_ranks_typo(monkeypatch):
    provider = MetacriticProvider(min_request_interval=0)
    monkeypatch.setattr(provider, "_html", lambda _: async_value(FIXTURES.joinpath("search.html").read_text()))
    results = await provider.search("eldn rng")
    await provider.close()
    assert results[0].title == "Elden Ring"
    assert results[0].year == 2022
    assert results[0].confidence > 0.7


@pytest.mark.asyncio
async def test_all_platform_scores(monkeypatch):
    provider = MetacriticProvider(min_request_interval=0)
    monkeypatch.setattr(provider, "_html", lambda _: async_value(FIXTURES.joinpath("details.html").read_text()))
    details = await provider.details("elden-ring")
    await provider.close()
    assert [(x.platform, x.metascore) for x in details.platforms] == [("PlayStation 5", 96), ("PC", 94)]


async def async_value(value):
    return value
