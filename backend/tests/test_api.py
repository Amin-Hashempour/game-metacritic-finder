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
    monkeypatch.setattr(provider, "_json", lambda _: async_value(read_json("search.json")))
    results = await provider.search("eldn rng")
    await provider.close()
    assert results[0].title == "Elden Ring"
    assert results[0].year == 2022
    assert results[0].confidence > 0.7


@pytest.mark.asyncio
async def test_all_platform_scores(monkeypatch):
    provider = MetacriticProvider(min_request_interval=0)
    async def platform_response(url):
        if "platform=playstation-5" in url:
            return read_json("details-ps5.json")
        if "platform=pc" in url:
            return read_json("details-pc.json")
        return read_json("details-base.json")

    monkeypatch.setattr(provider, "_json", platform_response)
    monkeypatch.setattr(
        provider,
        "_platform_scores_html",
        lambda *_: async_value(
            provider._parse_platform_scores(
                FIXTURES.joinpath("platform-cards.html").read_text(),
                "https://www.metacritic.com/game/elden-ring/",
            )
        ),
    )
    details = await provider.details("elden-ring")
    await provider.close()
    assert [(x.platform, x.metascore) for x in details.platforms] == [("PlayStation 5", 96), ("PC", 94)]
    assert details.platforms[0].review_count == 93
    assert details.platforms[1].review_count == 60


def test_platform_card_parser_keeps_scores_separate():
    scores = MetacriticProvider._parse_platform_scores(
        FIXTURES.joinpath("platform-cards.html").read_text(),
        "https://www.metacritic.com/game/elden-ring/",
    )
    assert [(item.platform, item.metascore, item.review_count) for item in scores] == [
        ("PlayStation 5", 96, 93),
        ("PC", 94, 60),
    ]


@pytest.mark.asyncio
async def test_image_proxy_rejects_external_urls():
    provider = MetacriticProvider(min_request_interval=0)
    with pytest.raises(ValueError, match="Invalid image path"):
        await provider.image("https://example.com/image.jpg")
    await provider.close()


def test_image_media_type_handles_cdn_content_types():
    assert MetacriticProvider._image_media_type(b"\xff\xd8\xffpayload", "application/octet-stream", "/provider/a.jpg") == "image/jpeg"
    assert MetacriticProvider._image_media_type(b"xxxxftypavifpayload", "image/avif", "/provider/a.jpg") == "image/avif"
    assert MetacriticProvider._image_media_type(b"<html>blocked</html>", "text/html", "/provider/a.jpg") is None


async def async_value(value):
    return value


def read_json(name):
    import json

    return json.loads(FIXTURES.joinpath(name).read_text())
