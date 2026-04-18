from fastapi import Depends, FastAPI, Request

from app.api.auth import router as auth_router
from app.api.listings import router as listings_router
from app.api.recommendations import router as recommendations_router
from app.api.scores import router as scores_router
from app.api.signals import router as signals_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import verify_api_key
from app.services.auth_service import log_api_usage
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def usage_logging_middleware(request: Request, call_next):
    response = await call_next(request)
    auth = getattr(request.state, "auth_context", None)
    if auth is not None:
        db = SessionLocal()
        try:
            log_api_usage(
                db,
                organization_id=auth.organization_id,
                api_key_id=auth.api_key_id,
                key_type=auth.key_type,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
            db.commit()
        finally:
            db.close()
    return response


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name}


app.include_router(auth_router, dependencies=[Depends(verify_api_key)])
app.include_router(listings_router, dependencies=[Depends(verify_api_key)])
app.include_router(signals_router, dependencies=[Depends(verify_api_key)])
app.include_router(scores_router, dependencies=[Depends(verify_api_key)])
app.include_router(recommendations_router, dependencies=[Depends(verify_api_key)])
