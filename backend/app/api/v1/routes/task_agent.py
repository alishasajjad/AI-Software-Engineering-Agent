import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.agent.edit_service import (
    PatchPreparationError,
    PendingPatchConflictError,
    list_task_patches,
    prepare_task_patches,
)
from app.agent.patch_review_service import (
    PatchApplicationError,
    PatchNotFoundError,
    PatchStaleConflictError,
    PatchStateConflictError,
    apply_patch,
    approve_patch,
    reject_patch,
)
from app.agent.schemas import ImplementationPlan
from app.agent.service import (
    PlanGenerationError,
    create_implementation_plan,
)
from app.db.session import get_db
from app.schemas.patch import (
    PatchActionResponse,
    PatchPreparationResponse,
    PendingPatchRead,
)

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


@router.post(
    "/{task_id}/patches/prepare",
    response_model=PatchPreparationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Prepare Task Patches",
)
async def prepare_patches(
    task_id: uuid.UUID,
    db: DatabaseSession,
) -> PatchPreparationResponse:
    try:
        return await prepare_task_patches(
            db=db,
            task_id=task_id,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PendingPatchConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except PatchPreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{task_id}/patches",
    response_model=list[PendingPatchRead],
    status_code=status.HTTP_200_OK,
    summary="List Task Patches",
)
def get_task_patches(
    task_id: uuid.UUID,
    db: DatabaseSession,
) -> list[PendingPatchRead]:
    try:
        return list_task_patches(
            db=db,
            task_id=task_id,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{task_id}/patches/{patch_id}/approve",
    response_model=PatchActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Patch",
)
def approve_task_patch(
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: DatabaseSession,
) -> PatchActionResponse:
    try:
        return approve_patch(
            db=db,
            task_id=task_id,
            patch_id=patch_id,
        )

    except (
        LookupError,
        PatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PatchStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{task_id}/patches/{patch_id}/reject",
    response_model=PatchActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Patch",
)
def reject_task_patch(
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: DatabaseSession,
) -> PatchActionResponse:
    try:
        return reject_patch(
            db=db,
            task_id=task_id,
            patch_id=patch_id,
        )

    except (
        LookupError,
        PatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PatchStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{task_id}/patches/{patch_id}/apply",
    response_model=PatchActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply Approved Patch",
)
def apply_task_patch(
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: DatabaseSession,
) -> PatchActionResponse:
    try:
        return apply_patch(
            db=db,
            task_id=task_id,
            patch_id=patch_id,
        )

    except (
        LookupError,
        PatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        PatchStateConflictError,
        PatchStaleConflictError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except PatchApplicationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(exc),
        ) from exc