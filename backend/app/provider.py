from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from rapidfuzz.fuzz import WRatio

from .models import GameDetails, PlatformScore, SearchResult


API_BASE = "https://backend.metacritic.com"
SITE_BASE = "https://www.metacritic.com"


class SourceUnavailable(RuntimeError):
    pass


@dataclass
class CacheItem:
    expires_at: float
    value: dict


class MetacriticProvider:
    """Adapter for the JSON backend used by Metacritic's own website."""

    def __init__(self, ttl_seconds: int = 900, min_request_interval: float = 1.0):
        self.ttl_seconds = ttl_seconds
        self.min_request_interval = min_request_interval
        self._cache: dict[str, CacheItem] = {}
        self._request_lock = asyncio.Lock()
        self._last_request = 0.0
        self._client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Android; MetacriticFinder/0.2)",
                "Accept": "application/json,*/*;q=0.8",
                "Referer": f"{SITE_BASE}/",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _json(self, url: str) -> dict:
        cached = self._cache.get(url)
        now = time.monotonic()
        if cached and cached.expires_at > now:
            return cached.value
        async with self._request_lock:
            delay = self.min_request_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                response = await self._client.get(url)
                self._last_request = time.monotonic()
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise SourceUnavailable("Metacritic data is temporarily unavailable") from exc
        if not isinstance(payload, dict):
            raise SourceUnavailable("Metacritic returned an unexpected response")
        self._cache[url] = CacheItem(now + self.ttl_seconds, payload)
        return payload

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        normalized = " ".join(query.split()).strip()
        url = f"{API_BASE}/finder/metacritic/search/{quote(normalized)}/web?limit=30&offset=0"
        candidates: list[SearchResult] = []
        for item in self._items(await self._json(url)):
            if item.get("type") != "game-title":
                continue
            slug = self._text(item.get("slug"))
            title = self._text(item.get("title"))
            if not slug or not title:
                continue
            candidates.append(
                SearchResult(
                    id=slug,
                    title=title,
                    year=self._integer(item.get("premiereYear")),
                    image_url=self._image_url(item),
                    metacritic_url=f"{SITE_BASE}/game/{slug}/",
                    confidence=WRatio(normalized.casefold(), title.casefold()) / 100,
                )
            )
        candidates.sort(key=lambda item: item.confidence, reverse=True)
        return candidates[:limit]

    async def details(self, game_id: str) -> GameDetails:
        slug = self._validate_slug(game_id)
        url = f"{API_BASE}/games/metacritic/{slug}/web?componentName=product&componentType=Product"
        payload = await self._json(url)
        data = payload.get("data")
        item = data.get("item") if isinstance(data, dict) else None
        if not isinstance(item, dict):
            raise SourceUnavailable("Metacritic returned no game details")
        title = self._text(item.get("title"))
        if not title:
            raise SourceUnavailable("Metacritic returned an incomplete game record")
        critic = item.get("criticScoreSummary")
        critic = critic if isinstance(critic, dict) else {}
        score = self._integer(critic.get("score"))
        review_count = self._integer(critic.get("reviewCount"))
        platforms = item.get("platforms")
        platform_names: list[str] = []
        if isinstance(platforms, list):
            for platform in platforms:
                if isinstance(platform, dict) and (name := self._text(platform.get("name"))):
                    platform_names.append(name)
        if not platform_names:
            platform_names = ["All platforms"]
        source_url = f"{SITE_BASE}/game/{slug}/"
        return GameDetails(
            id=slug,
            title=title,
            year=self._integer(item.get("premiereYear")),
            image_url=self._image_url(item),
            platforms=[
                PlatformScore(
                    platform=platform,
                    metascore=score,
                    review_count=review_count,
                    release_date=self._text(item.get("releaseDate")),
                    metacritic_url=source_url,
                )
                for platform in platform_names
            ],
        )

    @staticmethod
    def _items(payload: dict) -> list[dict]:
        data = payload.get("data")
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise SourceUnavailable("Metacritic returned no search results")
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _image_url(item: dict) -> str | None:
        images = item.get("images")
        if not isinstance(images, list):
            return None
        ordered = sorted(
            (image for image in images if isinstance(image, dict)),
            key=lambda image: image.get("bucketType") != "poster",
        )
        for image in ordered:
            path = image.get("bucketPath")
            if isinstance(path, str) and path.startswith("/"):
                return f"{SITE_BASE}{path}"
        return None

    @staticmethod
    def _text(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _integer(value: object) -> int | None:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return parsed if parsed != 0 else None

    @staticmethod
    def _validate_slug(game_id: str) -> str:
        value = game_id.strip("/")
        if not value or not re.fullmatch(r"[a-zA-Z0-9-]+", value):
            raise ValueError("Invalid game id")
        return value
