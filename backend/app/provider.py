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
COMPOSER_BASE = f"{API_BASE}/composer/metacritic/pages"
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
        base_url = f"{COMPOSER_BASE}/games/{slug}/web"
        payload = await self._json(base_url)
        item = self._component_item(payload, "product")
        if not isinstance(item, dict):
            raise SourceUnavailable("Metacritic returned no game details")
        title = self._text(item.get("title"))
        if not title:
            raise SourceUnavailable("Metacritic returned an incomplete game record")
        platforms = item.get("platforms")
        platform_names: list[str] = []
        if isinstance(platforms, list):
            for platform in platforms:
                if isinstance(platform, dict) and (name := self._text(platform.get("name"))):
                    platform_names.append(name)
        if not platform_names:
            platform_names = ["All platforms"]
        source_url = f"{SITE_BASE}/game/{slug}/"
        scores = await asyncio.gather(
            *(self._platform_score(base_url, platform, source_url) for platform in platform_names)
        )
        return GameDetails(
            id=slug,
            title=title,
            year=self._integer(item.get("premiereYear")),
            image_url=self._image_url(item),
            platforms=scores,
        )

    async def _platform_score(
        self, base_url: str, platform: str, source_url: str
    ) -> PlatformScore:
        platform_slug = re.sub(r"[^a-z0-9]+", "-", platform.casefold()).strip("-")
        payload = await self._json(f"{base_url}?platform={quote(platform_slug)}")
        item = self._component_item(payload, "critic-score-summary") or {}
        product = self._component_item(payload, "product") or {}
        return PlatformScore(
            platform=platform,
            metascore=self._integer(item.get("score")),
            review_count=self._integer(item.get("reviewCount")),
            release_date=self._text(product.get("releaseDate")),
            metacritic_url=f"{source_url}?platform={platform_slug}",
        )

    async def platform_diagnostics(self, game_id: str) -> dict:
        """Compare upstream platform selectors; temporary support diagnostic."""
        slug = self._validate_slug(game_id)
        base_url = f"{COMPOSER_BASE}/games/{slug}/web"
        base = await self._json(base_url)
        product = self._component_item(base, "product") or {}
        platforms = product.get("platforms")
        if not isinstance(platforms, list):
            platforms = []
        results = []
        for platform in platforms:
            if not isinstance(platform, dict):
                continue
            name = self._text(platform.get("name"))
            platform_id = self._integer(platform.get("id"))
            if not name:
                continue
            platform_slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
            candidates = {
                "composer_slug": f"{base_url}?platform={quote(platform_slug)}",
                "stats_slug": (
                    f"{API_BASE}/reviews/metacritic/critic/games/{slug}/stats/web"
                    f"?componentName=critic-score-summary&componentType=MetaScoreSummary"
                    f"&platform={quote(platform_slug)}"
                ),
                "stats_id": (
                    f"{API_BASE}/reviews/metacritic/critic/games/{slug}/stats/web"
                    f"?componentName=critic-score-summary&componentType=MetaScoreSummary"
                    f"&platformId={platform_id}"
                ),
            }
            readings = {}
            for label, url in candidates.items():
                try:
                    payload = await self._json(url)
                    if label.startswith("composer"):
                        score_item = self._component_item(payload, "critic-score-summary") or {}
                    else:
                        data = payload.get("data")
                        score_item = data.get("item") if isinstance(data, dict) else {}
                    readings[label] = {
                        "score": self._integer(score_item.get("score")),
                        "review_count": self._integer(score_item.get("reviewCount")),
                    }
                except SourceUnavailable as exc:
                    readings[label] = {"error": str(exc)}
            results.append(
                {"platform": name, "platform_id": platform_id, "readings": readings}
            )
        return {"game": slug, "platforms": results}

    @staticmethod
    def _component_item(payload: dict, name: str) -> dict | None:
        components = payload.get("components")
        if not isinstance(components, list):
            return None
        for component in components:
            if not isinstance(component, dict):
                continue
            meta = component.get("meta")
            data = component.get("data")
            if (
                isinstance(meta, dict)
                and meta.get("componentName") == name
                and isinstance(data, dict)
                and isinstance(data.get("item"), dict)
            ):
                return data["item"]
        return None

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
