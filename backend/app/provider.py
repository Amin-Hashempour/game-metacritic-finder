from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from rapidfuzz.fuzz import WRatio

from .models import GameDetails, PlatformScore, SearchResult


BASE_URL = "https://www.metacritic.com"
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


class SourceUnavailable(RuntimeError):
    pass


@dataclass
class CacheItem:
    expires_at: float
    value: object


class MetacriticProvider:
    """Metacritic HTML adapter. Keep markup assumptions isolated in this class."""

    def __init__(self, ttl_seconds: int = 900, min_request_interval: float = 1.0):
        self.ttl_seconds = ttl_seconds
        self.min_request_interval = min_request_interval
        self._cache: dict[str, CacheItem] = {}
        self._request_lock = asyncio.Lock()
        self._last_request = 0.0
        self._client = httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Android; MetacriticFinder/0.1)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _html(self, url: str) -> str:
        cached = self._cache.get(url)
        now = time.monotonic()
        if cached and cached.expires_at > now:
            return str(cached.value)
        async with self._request_lock:
            delay = self.min_request_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                response = await self._client.get(url)
                self._last_request = time.monotonic()
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SourceUnavailable("Metacritic is temporarily unavailable") from exc
        self._cache[url] = CacheItem(now + self.ttl_seconds, response.text)
        return response.text

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        normalized = " ".join(query.split()).strip()
        url = f"{BASE_URL}/search/{quote(normalized)}/?category=13"
        soup = BeautifulSoup(await self._html(url), "html.parser")
        candidates: dict[str, SearchResult] = {}
        selectors = "a.c-pageSiteSearch-results-item, a[href*='/game/']"
        for anchor in soup.select(selectors):
            href = anchor.get("href", "")
            if "/game/" not in href:
                continue
            title_node = anchor.select_one(".c-pageSiteSearch-results-item-title, h3, .c-finderProductCard_title")
            title = (title_node or anchor).get_text(" ", strip=True)
            title = re.sub(r"\s+", " ", title)
            if not title or len(title) > 120:
                continue
            absolute = urljoin(BASE_URL, href)
            game_id = self._id_from_url(absolute)
            year_match = YEAR_RE.search(anchor.get_text(" ", strip=True))
            image = anchor.select_one("img")
            score = WRatio(normalized.casefold(), title.casefold()) / 100
            current = candidates.get(game_id)
            result = SearchResult(
                id=game_id,
                title=title,
                year=int(year_match.group()) if year_match else None,
                image_url=(image.get("src") or image.get("data-src")) if image else None,
                metacritic_url=absolute,
                confidence=score,
            )
            if current is None or result.confidence > current.confidence:
                candidates[game_id] = result
        return sorted(candidates.values(), key=lambda item: item.confidence, reverse=True)[:limit]

    async def details(self, game_id: str) -> GameDetails:
        safe_id = self._validate_id(game_id)
        canonical_url = f"{BASE_URL}/game/{safe_id}/"
        soup = BeautifulSoup(await self._html(canonical_url), "html.parser")
        title_node = soup.select_one("h1, .c-productHero_title")
        if not title_node:
            raise SourceUnavailable("Metacritic page format is not recognized")
        title = title_node.get_text(" ", strip=True)
        image = soup.select_one(".c-productHero_image img, meta[property='og:image']")
        image_url = None
        if image:
            image_url = image.get("src") or image.get("content")
        page_text = soup.get_text(" ", strip=True)
        year_match = YEAR_RE.search(page_text)
        scores: list[PlatformScore] = []
        seen: set[str] = set()
        for block in soup.select("[data-platform], .c-gamePlatformScore, .c-productScoreInfo"):
            platform_node = block.select_one("[data-platform], .c-gamePlatformScore_platform, .c-productScoreInfo_platform")
            score_node = (
                block.select_one(".c-siteReviewScore")
                or block.select_one(".c-gamePlatformScore_score")
                or block.select_one("[data-testid*='score']")
            )
            if not platform_node or not score_node:
                continue
            platform = platform_node.get("data-platform") or platform_node.get_text(" ", strip=True)
            score_match = re.search(r"\b(?:100|[1-9]?\d)\b", score_node.get_text(" ", strip=True))
            if not platform or platform in seen:
                continue
            seen.add(platform)
            scores.append(
                PlatformScore(
                    platform=platform,
                    metascore=int(score_match.group()) if score_match else None,
                    metacritic_url=canonical_url,
                )
            )
        if not scores:
            scores = self._json_ld_scores(soup, canonical_url)
        return GameDetails(
            id=safe_id,
            title=title,
            year=int(year_match.group()) if year_match else None,
            image_url=image_url,
            platforms=scores,
        )

    @staticmethod
    def _json_ld_scores(soup: BeautifulSoup, url: str) -> list[PlatformScore]:
        import json

        output: list[PlatformScore] = []
        for node in soup.select("script[type='application/ld+json']"):
            try:
                payload = json.loads(node.string or "{}")
            except json.JSONDecodeError:
                continue
            entries = payload if isinstance(payload, list) else [payload]
            for entry in entries:
                if not isinstance(entry, dict) or "aggregateRating" not in entry:
                    continue
                rating = entry["aggregateRating"]
                raw_score = rating.get("ratingValue") if isinstance(rating, dict) else None
                try:
                    score = round(float(raw_score))
                except (TypeError, ValueError):
                    continue
                output.append(PlatformScore(platform="All platforms", metascore=score, metacritic_url=url))
        return output

    @staticmethod
    def _id_from_url(url: str) -> str:
        path = urlparse(url).path.strip("/").split("/")
        try:
            index = path.index("game")
            return "/".join(path[index + 1 :])
        except ValueError:
            return path[-1]

    @staticmethod
    def _validate_id(game_id: str) -> str:
        value = game_id.strip("/")
        if not value or not re.fullmatch(r"[a-zA-Z0-9/_-]+", value) or ".." in value:
            raise ValueError("Invalid game id")
        return value
