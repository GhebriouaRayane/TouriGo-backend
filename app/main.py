from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.api.api import api_router
from app.core.config import settings
from app.db.session import engine, Base

MEDIA_DIR = Path(__file__).resolve().parents[1] / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Création automatique des tables uniquement en environnement local.
if settings.AUTO_CREATE_TABLES:
    Base.metadata.create_all(bind=engine)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API pour la plateforme  - Immobilier, Véhicules et Activités",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

allow_credentials = settings.CORS_ALLOW_CREDENTIALS and "*" not in settings.ALLOWED_HOSTS

# Configuration de la sécurité CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes de l'API
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": f"Bienvenue sur l'API {settings.PROJECT_NAME}",
        "docs": "/docs",
        "version": settings.VERSION
    }
