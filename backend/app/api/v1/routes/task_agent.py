import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.schemas import ImplementationPlan
from app.agent.service import (
    PlanGenerationError,
    create_implementation_plan,
)
from app.db.session import get_db

router = APIRouter(
    tags=["Agent"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


@router.post(
    "/{task_id}/plan",
    response_model=ImplementationPlan,
    status_code=status.HTTP_200_OK,
    summary="Create Task Plan",
)
async def create_task_plan(
    task_id: uuid.UUID,
    db: DatabaseSession,
) -> ImplementationPlan:
    try:
        return await create_implementation_plan(
            db=db,
            task_id=task_id,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc