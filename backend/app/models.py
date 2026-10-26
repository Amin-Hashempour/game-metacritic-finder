from pydantic import BaseModel, Field, HttpUrl


class SearchResult(BaseModel):
    id: str
    title: str
    year: int | None = None
    image_url: HttpUrl | None = None
    metacritic_url: HttpUrl
    confidence: float = Field(ge=0, le=1)


class PlatformScore(BaseModel):
    platform: str
    metascore: int | None = Field(default=None, ge=0, le=100)
    review_count: int | None = Field(default=None, ge=0)
    release_date: str | None = None
    metacritic_url: HttpUrl


class GameDetails(BaseModel):
    id: str
    title: str
    year: int | None = None
    image_url: HttpUrl | None = None
    platforms: list[PlatformScore]


class ErrorBody(BaseModel):
    code: str
    message: str
