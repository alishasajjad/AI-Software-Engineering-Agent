from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.task_agent import router as task_agent_router
from app.api.v1.routes.tasks import router as tasks_router

api_router = APIRouter()

api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    tasks_router,
    prefix="/tasks",
    tags=["Tasks"],
)

api_router.include_router(
    task_agent_router,
    prefix="/tasks",
    tags=["Agent"],
)
