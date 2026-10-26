from contextlib import asynccontextmanager
from urllib.parse import urlencode, urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from .models import ErrorBody, GameDetails, SearchResult
from .provider import MetacriticProvider, SourceUnavailable


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.provider = MetacriticProvider()
    yield
    await app.state.provider.close()


app = FastAPI(title="Metacritic Finder API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(SourceUnavailable)
async def source_unavailable(_: Request, exc: SourceUnavailable):
    return JSONResponse(
        status_code=503,
        content=ErrorBody(code="SOURCE_UNAVAILABLE", message=str(exc)).model_dump(),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/games/search", response_model=list[SearchResult])
async def search_games(request: Request, q: str = Query(min_length=2, max_length=80)):
    results = await request.app.state.provider.search(q)
    for result in results:
        if result.image_url:
            parsed = urlparse(str(result.image_url))
            if parsed.hostname in {"metacritic.com", "www.metacritic.com"}:
                result.image_url = f"/v1/images?{urlencode({'path': parsed.path})}"
    return results


@app.get("/v1/images", name="game_image")
async def game_image(request: Request, path: str = Query(min_length=5, max_length=500)):
    try:
        content, media_type = await request.app.state.provider.image(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/v1/games/{game_id:path}", response_model=GameDetails)
async def game_details(request: Request, game_id: str):
    try:
        return await request.app.state.provider.details(game_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
