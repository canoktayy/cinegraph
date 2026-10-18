"""HTTP API, polished local demo and structured failure handling."""

from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from time import monotonic
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Path as PathParameter, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from app.agent.assistant import AssistantClient, AssistantTurn, answer_turn
from app.agent.client import LLMClient, local_model_status
from app.agent.workflow import answer
from app.config import get_settings
from app.database import GraphStore
from app.models import MAX_GRAPH_ID, AskRequest, AskResponse, ExplanationResponse, RankingResponse
from app.repository import CatalogRepository
from app.services import RecommendationService
from app.taste import TasteRequest, recommend as taste_recommend, rounds as taste_rounds

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Share driver sockets; database readiness is checked separately."""
    application.state.store = GraphStore(get_settings())
    application.state.budgets = defaultdict(deque)
    yield
    application.state.store.close()


app = FastAPI(
    title="Cinegraph API",
    version="1.1.1",
    lifespan=lifespan,
    description="Evidence-backed movie recommendations. Scores are not confidence probabilities.",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def service(request: Request) -> RecommendationService:
    """Dependency boundary that API tests can replace with a controlled fixture."""
    return RecommendationService(CatalogRepository(request.app.state.store))


Service = Annotated[RecommendationService, Depends(service)]
Limit = Annotated[int, Query(ge=1, le=50)]
Identifier = Annotated[int, PathParameter(gt=0, le=MAX_GRAPH_ID)]


@app.middleware("http")
async def trace_request(request: Request, call_next):
    """Expose a trace ID without recording private questions or credentials."""
    request.state.trace_id = uuid4().hex
    response = await call_next(request)
    response.headers["X-Trace-ID"] = request.state.trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(Neo4jError)
@app.exception_handler(ServiceUnavailable)
@app.exception_handler(SessionExpired)
async def database_error(request: Request, _error):
    """Hide internal topology, query text and credentials from failure responses."""
    return JSONResponse(
        status_code=503,
        content={
            "code": "database_unavailable",
            "message": "Graph database is unavailable",
            "trace_id": request.state.trace_id,
        },
    )


def protect_ask(request: Request, x_api_key: Annotated[str | None, Header()] = None):
    """Optionally require a key, and always apply a small per-client minute budget to model calls."""
    settings = get_settings()
    if settings.require_api_key:
        if not settings.app_api_key:
            raise HTTPException(503, "Set APP_API_KEY before enabling the natural-language endpoint")
        if not x_api_key or not compare_digest(x_api_key, settings.app_api_key):
            raise HTTPException(401, "A valid X-API-Key is required")
    address = request.client.host if request.client else "local"
    budget = request.app.state.budgets[address]
    now = monotonic()
    while budget and budget[0] <= now - 60:
        budget.popleft()
    maximum = 24 if request.url.path == "/api/assistant/turn" else 12
    if len(budget) >= maximum:
        raise HTTPException(429, "Model request limit reached. Wait one minute; your choices are kept.")
    budget.append(now)


@app.get("/", include_in_schema=False)
def home():
    """Serve a dependency-free catalog and recommendation demo."""
    return FileResponse(STATIC / "index.html")


@app.get("/health/live", tags=["Health"])
def live():
    """A live process may still be waiting for the database."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
def ready(recommender: Service):
    """Require both a Neo4j round trip and a seeded dataset."""
    recommender.repository.store.healthy()
    if not recommender.repository.state():
        raise HTTPException(503, "Database is connected; dataset has not been seeded")
    return {"status": "ready"}


@app.get("/api/system/status", tags=["Catalog"])
def system_status(recommender: Service):
    """Return actual graph counts and snapshot metadata, never secrets."""
    return recommender.repository.statistics()


@app.get("/api/genres", tags=["Catalog"])
def genres(recommender: Service):
    """Canonical genres used by UI filters and the query planner."""
    return recommender.repository.genres()


@app.get("/api/movies", tags=["Catalog"])
def movies(
    recommender: Service,
    q: str = "",
    genre: str | None = None,
    year: Annotated[int | None, Query(ge=1800, le=2200)] = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    """Full-text catalog search with bounded stable pagination."""
    return {
        "items": recommender.repository.search(
            {"q": q[:200], "genre": genre, "year": year, "limit": limit, "offset": offset}
        )
    }


@app.get("/api/movies/trending", response_model=RankingResponse, tags=["Recommendations"])
def trending(
    recommender: Service,
    metric: Literal["rating", "pagerank"] = "rating",
    window_days: Annotated[int, Query(ge=1, le=36500)] = 365,
    limit: Limit = 10,
):
    """Rank historical rating activity or graph centrality; always return as_of."""
    return recommender.trending({"metric": metric, "window_days": window_days, "limit": limit})


@app.get("/api/movies/{movie_id}/similar", response_model=RankingResponse, tags=["Recommendations"])
def similar(movie_id: Identifier, recommender: Service, limit: Limit = 10):
    """Find films liked by overlapping users, with support shrinkage."""
    return recommender.similar(movie_id, limit)


@app.get("/api/users/{user_id}/favorites", response_model=RankingResponse, tags=["Recommendations"])
def favourites(user_id: Identifier, recommender: Service, limit: Limit = 8):
    """Films the rater scored 4★ or more, highest and most recent first."""
    return recommender.favourites(user_id, limit)


@app.get("/api/users/{user_id}/recommendations", response_model=RankingResponse, tags=["Recommendations"])
def recommendations(user_id: Identifier, recommender: Service, genre: str | None = None, limit: Limit = 10):
    """Weighted item-CF recommendations excluding every previously rated film."""
    if genre and genre not in recommender.repository.genres():
        raise HTTPException(422, "Unknown genre")
    return recommender.recommendations(user_id, limit, genre)


@app.get("/api/users/{user_id}/discover", response_model=RankingResponse, tags=["Recommendations"])
def discover(user_id: Identifier, recommender: Service, limit: Limit = 10):
    """Community-based discovery using the active Louvain run."""
    return recommender.discover(user_id, limit)


@app.get(
    "/api/users/{user_id}/recommendations/{movie_id}/explanation", response_model=ExplanationResponse, tags=["Evidence"]
)
def explanation(user_id: Identifier, movie_id: Identifier, recommender: Service):
    """Return exact rating/similarity paths and their score contributions."""
    return recommender.explanation(user_id, movie_id)


@app.get("/api/model/status", tags=["Natural language"])
def model_status():
    """Tell the interface whether the local model server answers, without sending any prompt."""
    return local_model_status(get_settings())


@app.post("/api/ask", response_model=AskResponse, dependencies=[Depends(protect_ask)], tags=["Natural language"])
def ask(body: AskRequest, request: Request, recommender: Service):
    """Use a real configured local LLM; invalid output is never executed."""
    return answer(body, recommender, LLMClient(get_settings()), request.state.trace_id)


@app.get("/api/taste/rounds", tags=["Personal taste"])
def taste_options(recommender: Service, seed: Annotated[int, Query(ge=0, le=2147483647)] = 42):
    """Offer ten rounds of five distinct films for a new visitor."""
    return taste_rounds(recommender, seed)


@app.post("/api/taste/recommendations", tags=["Personal taste"])
def personal_recommendations(body: TasteRequest, recommender: Service):
    """Recommend from visitor-selected seeds without modifying research data."""
    return taste_recommend(recommender, body)


@app.post("/api/assistant/turn", dependencies=[Depends(protect_ask)], tags=["Film assistant"])
def assistant_turn(body: AssistantTurn, request: Request, recommender: Service):
    """Conversational onboarding and refinements through validated graph tools."""
    return answer_turn(body, recommender, AssistantClient(get_settings()), request.state.trace_id)
