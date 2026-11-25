from fastapi import APIRouter,Depends,HTTPException,Header,Request
from secrets import compare_digest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_session
from app.schemas.health import HealthResponse
from app.core.config import settings
router=APIRouter()
def authorize(x_geo_token:str|None=Header(default=None)):
 if not settings.auth_token:return
 if not x_geo_token or not compare_digest(x_geo_token,settings.auth_token): raise HTTPException(401,detail={"code":"unauthorized","message":"Authentication required"})
@router.get("/health",response_model=HealthResponse,dependencies=[Depends(authorize)])
def health(db:Session=Depends(get_session)):
 try:db.execute(text("SELECT 1"));state="connected"
 except Exception:state="disconnected"
 return HealthResponse(status="ok",application=settings.app_name,api_version="1.0.0",database=state)
@router.get("/health/ready",response_model=HealthResponse,dependencies=[Depends(authorize)])
def ready(db:Session=Depends(get_session)):
 try:db.execute(text("SELECT 1"))
 except Exception:raise HTTPException(503,detail={"code":"database_unavailable","message":"Database unavailable"})
 return HealthResponse(status="ready",application=settings.app_name,api_version="1.0.0",database="connected")

@router.post("/internal/shutdown", status_code=202)
async def shutdown(request: Request, x_geo_token: str | None = Header(default=None)):
 # Shutdown remains unavailable unless the desktop supplied a per-launch secret.
 if not settings.auth_token or not x_geo_token or not compare_digest(x_geo_token, settings.auth_token):
  raise HTTPException(401, detail={"code":"unauthorized","message":"Authentication required"})
 server = getattr(request.app.state, "uvicorn_server", None)
 if server is None:
  raise HTTPException(503, detail={"code":"shutdown_unavailable","message":"Backend server is not ready to stop"})
 server.should_exit = True
 return {"status":"stopping"}
