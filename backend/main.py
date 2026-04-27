import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import asyncio

from backend.config import get_settings
from backend.session_store import evict_expired_sessions
from backend.routers import auth, upload, ledger, form16, gst, chat, companies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("financial_audit")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Financial Audit AI backend starting up")

    async def _evict_loop():
        while True:
            await asyncio.sleep(1800)  # every 30 min
            n = evict_expired_sessions()
            if n:
                logger.info("Evicted %d expired sessions", n)

    task = asyncio.create_task(_evict_loop())
    yield
    task.cancel()
    logger.info("Financial Audit AI backend shutting down")


settings = get_settings()

app = FastAPI(
    title="Financial Audit AI",
    description=(
        "Agentic AI Financial Auditor — Ledger Screening, Form 16 Generation & GST Filing. "
        "Powered by OpenAI GPT-4o-mini and LangChain."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    logger.info("→ %s %s [%s]", request.method, request.url.path, request_id)
    response = await call_next(request)
    logger.info("← %s %s %d [%s]", request.method, request.url.path, response.status_code, request_id)
    return response


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(auth.router,   prefix=PREFIX)
app.include_router(upload.router, prefix=PREFIX)
app.include_router(ledger.router, prefix=PREFIX)
app.include_router(form16.router, prefix=PREFIX)
app.include_router(gst.router,    prefix=PREFIX)
app.include_router(chat.router,      prefix=PREFIX)
app.include_router(companies.router, prefix=PREFIX)


# ── Health & info ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health():
    return {"status": "ok", "version": app.version, "service": "financial-audit-ai"}


@app.get("/api/v1/session/stats", tags=["System"])
async def session_stats_endpoint():
    from backend.session_store import session_stats
    return session_stats()


# ── Serve React frontend in production ───────────────────────────────────────
import os
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(_dist, "index.html"))
