import hashlib
import uuid

import pytest

from app.schemas.correction_proposal import (
    CorrectionFileProposal,
    CorrectionProposal,
)
from app.schemas.patch import PendingPatch
from app.services.correction_patch_service import (
    CorrectionPatchGenerationError,
    validate_generated_correction_patches,
)


def _proposal(
    path: str = "test_sample.py",
) -> CorrectionProposal:
    return CorrectionProposal(
        summary="Correct the failing test.",
        root_cause="The expected value is incorrect.",
        files=[
            CorrectionFileProposal(
                path=path,
                reason=(
                    "This file contains the failing "
                    "expectation."
                ),
                change_instructions=[
                    "Replace the incorrect expected value."
                ],
            )
        ],
        pytest_targets=[
            "test_sample.py"
        ],
        risks=[
            "Confirm the expected behavior before applying."
        ],
        needs_human_review=True,
    )


def _patch(
    path: str = "test_sample.py",
) -> PendingPatch:
    original_content = (
        "assert VALUE == 999\n"
    )

    proposed_content = (
        "assert VALUE == 2\n"
    )

    return PendingPatch(
        task_id=uuid.uuid4(),
        path=path,
        original_content=(
            original_content
        ),
        proposed_content=(
            proposed_content
        ),
        diff=(
            "--- test_sample.py\n"
            "+++ test_sample.py\n"
            "-assert VALUE == 999\n"
            "+assert VALUE == 2\n"
        ),
        original_sha256=(
            hashlib.sha256(
                original_content.encode(
                    "utf-8"
                )
            ).hexdigest()
        ),
    )


def test_correction_patch_validation_accepts_allowed_file() -> None:
    validate_generated_correction_patches(
        proposal=_proposal(),
        patches=[
            _patch()
        ],
    )


def test_correction_patch_validation_rejects_unapproved_file() -> None:
    with pytest.raises(
        CorrectionPatchGenerationError,
        match=(
            "outside the approved correction proposal"
        ),
    ):
        validate_generated_correction_patches(
            proposal=_proposal(),
            patches=[
                _patch(
                    "unrelated.py"
                )
            ],
        )


def test_correction_patch_validation_rejects_empty_patch_set() -> None:
    with pytest.raises(
        CorrectionPatchGenerationError,
        match=(
            "did not prepare any pending patches"
        ),
    ):
        validate_generated_correction_patches(
            proposal=_proposal(),
            patches=[],
        )