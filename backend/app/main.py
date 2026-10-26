from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

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
    return await request.app.state.provider.search(q)


@app.get("/v1/games/{game_id:path}", response_model=GameDetails)
async def game_details(request: Request, game_id: str):
    try:
        return await request.app.state.provider.details(game_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
