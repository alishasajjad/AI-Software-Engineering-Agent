import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.correction import (
    FailureAnalysisResponse,
)
from app.schemas.correction_loop import (
    CorrectionLoopResponse,
)
from app.schemas.correction_patch import (
    CorrectionPatchPreparationResponse,
)
from app.schemas.correction_proposal import (
    CorrectionProposalResponse,
)
from app.schemas.correction_reverification import (
    CorrectionReverificationResponse,
)
from app.schemas.verification import (
    VerificationRequest,
    VerificationRunResponse,
)
from app.services.correction_loop_service import (
    CorrectionLoopStateError,
    advance_correction_loop,
    get_correction_loop_status,
)
from app.services.correction_patch_service import (
    CorrectionPatchGenerationError,
    CorrectionPendingPatchConflictError,
    ExistingCorrectionPatchesError,
    create_correction_patches,
)
from app.services.correction_reverification_service import (
    CorrectionAttemptLimitError,
    CorrectionReverificationError,
    reverify_correction,
)
from app.services.correction_service import (
    CorrectionProposalGenerationError,
    CorrectionSessionNotFoundError,
    ExistingCorrectionSessionError,
    InvalidCorrectionSessionStateError,
    InvalidVerificationStateError,
    create_correction_proposal,
    create_failure_analysis,
)
from app.services.failure_analyzer import (
    FailureAnalysisError,
)
from app.services.verification_service import (
    get_verification_history as get_verification_history_service,
)
from app.services.verification_service import (
    get_verification_run as get_verification_run_service,
)
from app.services.verification_service import (
    verify_task as verify_task_service,
)

router = APIRouter(
    prefix=(
        "/tasks/{task_id}/verifications"
    ),
    tags=["Agent"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


@router.post(
    "",
    response_model=VerificationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Automated Verification",
)
def verify_task(
    task_id: uuid.UUID,
    payload: VerificationRequest,
    db: DatabaseSession,
) -> VerificationRunResponse:
    """
    Run automated verification for a task.
    """

    try:
        return verify_task_service(
            db=db,
            task_id=task_id,
            pytest_targets=(
                payload.pytest_targets
            ),
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=(
        list[VerificationRunResponse]
    ),
    status_code=status.HTTP_200_OK,
    summary="List Verification History",
)
def get_verification_history(
    task_id: uuid.UUID,
    db: DatabaseSession,
) -> list[VerificationRunResponse]:
    """
    Return verification history for a task.
    """

    try:
        return (
            get_verification_history_service(
                db=db,
                task_id=task_id,
            )
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc


@router.get(
    "/{verification_id}",
    response_model=VerificationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Verification Run",
)
def get_verification_run(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> VerificationRunResponse:
    """
    Return one verification run with execution steps.
    """

    verification_run = (
        get_verification_run_service(
            db=db,
            task_id=task_id,
            verification_id=(
                verification_id
            ),
        )
    )

    if verification_run is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Verification run not found."
            ),
        )

    return verification_run


@router.post(
    (
        "/{verification_id}"
        "/corrections/analyze"
    ),
    response_model=(
        FailureAnalysisResponse
    ),
    status_code=status.HTTP_201_CREATED,
    summary="Analyze Verification Failure",
)
def analyze_failed_verification(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> FailureAnalysisResponse:
    """
    Analyze a failed verification run.
    """

    verification_run = (
        get_verification_run_service(
            db=db,
            task_id=task_id,
            verification_id=(
                verification_id
            ),
        )
    )

    if verification_run is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Verification run not found."
            ),
        )

    try:
        return create_failure_analysis(
            db=db,
            task_id=task_id,
            verification_run=(
                verification_run
            ),
        )

    except InvalidVerificationStateError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except ExistingCorrectionSessionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except FailureAnalysisError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc


@router.post(
    (
        "/{verification_id}"
        "/corrections/propose"
    ),
    response_model=(
        CorrectionProposalResponse
    ),
    status_code=status.HTTP_201_CREATED,
    summary="Generate Correction Proposal",
)
def propose_verification_correction(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> CorrectionProposalResponse:
    """
    Generate a structured AI correction proposal.
    """

    verification_run = (
        get_verification_run_service(
            db=db,
            task_id=task_id,
            verification_id=(
                verification_id
            ),
        )
    )

    if verification_run is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Verification run not found."
            ),
        )

    try:
        return create_correction_proposal(
            db=db,
            task_id=task_id,
            verification_run=(
                verification_run
            ),
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except (
        InvalidVerificationStateError,
        CorrectionSessionNotFoundError,
        InvalidCorrectionSessionStateError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except CorrectionProposalGenerationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.post(
    (
        "/{verification_id}"
        "/corrections/patches/prepare"
    ),
    response_model=(
        CorrectionPatchPreparationResponse
    ),
    status_code=status.HTTP_201_CREATED,
    summary="Prepare Correction Patches",
)
async def prepare_verification_correction_patches(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> CorrectionPatchPreparationResponse:
    """
    Convert a correction proposal into pending patches.
    """

    verification_run = (
        get_verification_run_service(
            db=db,
            task_id=task_id,
            verification_id=(
                verification_id
            ),
        )
    )

    if verification_run is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Verification run not found."
            ),
        )

    try:
        return await create_correction_patches(
            db=db,
            task_id=task_id,
            verification_run=(
                verification_run
            ),
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except (
        InvalidVerificationStateError,
        CorrectionSessionNotFoundError,
        InvalidCorrectionSessionStateError,
        ExistingCorrectionPatchesError,
        CorrectionPendingPatchConflictError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except FailureAnalysisError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    except CorrectionPatchGenerationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.post(
    (
        "/{verification_id}"
        "/corrections/reverify"
    ),
    response_model=(
        CorrectionReverificationResponse
    ),
    status_code=status.HTTP_201_CREATED,
    summary="Re-verify Applied Correction",
)
def reverify_applied_correction(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> CorrectionReverificationResponse:
    """
    Re-run verification after correction patches are applied.
    """

    source_verification = (
        get_verification_run_service(
            db=db,
            task_id=task_id,
            verification_id=(
                verification_id
            ),
        )
    )

    if source_verification is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Verification run not found."
            ),
        )

    try:
        return reverify_correction(
            db=db,
            task_id=task_id,
            source_verification=(
                source_verification
            ),
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    except (
        CorrectionSessionNotFoundError,
        InvalidCorrectionSessionStateError,
        CorrectionAttemptLimitError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except CorrectionReverificationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(exc),
        ) from exc


@router.get(
    (
        "/{verification_id}"
        "/corrections/status"
    ),
    response_model=(
        CorrectionLoopResponse
    ),
    status_code=status.HTTP_200_OK,
    summary="Get Self-Correction Status",
)
def get_self_correction_status(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> CorrectionLoopResponse:
    """
    Return the latest state, retry lineage, pending patch state,
    next action, and safe-stop information for a self-correction
    workflow.

    The original failed verification id can continue to be used
    after retry child sessions are created.
    """

    try:
        return get_correction_loop_status(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_id
            ),
        )

    except CorrectionSessionNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except CorrectionLoopStateError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc


@router.post(
    (
        "/{verification_id}"
        "/corrections/advance"
    ),
    response_model=(
        CorrectionLoopResponse
    ),
    status_code=status.HTTP_200_OK,
    summary="Advance Self-Correction Loop",
)
async def advance_self_correction(
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
    db: DatabaseSession,
) -> CorrectionLoopResponse:
    """
    Advance all currently safe automatic correction steps.

    Automatic execution stops at:
    - human patch review
    - explicit patch application
    - successful completion
    - maximum attempts
    - verification errors
    - stale or rejected patches
    - unsupported workflow states

    Patch approval and patch application are never performed
    automatically.
    """

    try:
        return await advance_correction_loop(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_id
            ),
        )

    except CorrectionSessionNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    except (
        CorrectionLoopStateError,
        InvalidVerificationStateError,
        InvalidCorrectionSessionStateError,
        CorrectionAttemptLimitError,
        ExistingCorrectionPatchesError,
        CorrectionPendingPatchConflictError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except FailureAnalysisError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    except (
        CorrectionProposalGenerationError,
        CorrectionPatchGenerationError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc

    except CorrectionReverificationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(exc),
        ) from exc