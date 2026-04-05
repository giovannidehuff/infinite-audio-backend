import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes.launch_pack import router as launch_pack_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="Infinite Audio — AI Beat Launch System",
    description="Generate a complete beat launch pack from beat metadata.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
async def health():
    return {
        "status": "ok",
        "provider": settings.ai_provider,
        "model": settings.active_model,
        "env": settings.app_env,
    }


app.include_router(launch_pack_router, tags=["Launch Pack"])
