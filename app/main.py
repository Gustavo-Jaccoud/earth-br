from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Field Shift API",
        description="Dados da NASA e do IBGE traduzidos para o produtor rural do Nordeste.",
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/health", tags=["sistema"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (farms, climate, signals, satellite, crops, rotation, regional, maps,
                   reports, quiz):
        app.include_router(module.router)

    return app


app = create_app()
