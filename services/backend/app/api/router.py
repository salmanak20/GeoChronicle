from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
router=APIRouter(prefix="/api/v1")
router.include_router(health_router,tags=["health"])
router.include_router(projects_router)
