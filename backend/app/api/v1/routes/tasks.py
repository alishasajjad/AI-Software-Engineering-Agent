import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DBSession
from app.schemas.task import TaskCreate, TaskResponse
from app.services.task_service import create_task, get_task, get_tasks

router = APIRouter()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_endpoint(
    task_data: TaskCreate,
    db: DBSession,
) -> TaskResponse:
    task = create_task(db, task_data)

    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=list[TaskResponse],
)
def list_tasks_endpoint(
    db: DBSession,
) -> list[TaskResponse]:
    tasks = get_tasks(db)

    return [TaskResponse.model_validate(task) for task in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
def get_task_endpoint(
    task_id: uuid.UUID,
    db: DBSession,
) -> TaskResponse:
    task = get_task(db, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskResponse.model_validate(task)