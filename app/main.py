from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    climate,
    crops,
    farms,
    maps,
    quiz,
    regional,
    reports,
    rotation,
    satellite,
    signals,
)
from app.api_docs import DESCRIPTION, TAGS, apply_docs
from app.clients.power import PowerClient, PowerUnavailable
from app.db import init_db, make_engine
from app.repositories.gaez import GaezRepository
from app.repositories.rasters import RasterStore
from app.repositories.region import load_region
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.var_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(engine, settings.var_dir)
        yield

    app = FastAPI(
        lifespan=lifespan,
        title="Field Shift API",
        version="0.1.0",
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.region = load_region(settings.data_dir)
    app.state.rasters = RasterStore(settings.data_dir)
    app.state.gaez = GaezRepository(settings.data_dir)
    app.state.power = PowerClient(settings.data_dir / "cache" / "power", live=settings.power_live)

    @app.exception_handler(PowerUnavailable)
    async def power_unavailable(_: Request, exc: PowerUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/health", tags=["sistema"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/static/maps", StaticFiles(directory=settings.data_dir / "maps", check_dir=False),
              name="maps")

    for module in (farms, climate, signals, satellite, crops, rotation, regional, maps,
                   reports, quiz):
        app.include_router(module.router)
    apply_docs(app)

    return app


app = create_app()
