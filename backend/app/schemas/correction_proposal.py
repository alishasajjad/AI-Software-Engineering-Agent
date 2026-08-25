from __future__ import annotations

import uuid

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CorrectionFileProposal(BaseModel):
    """
    One repository file that may need correction.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    path: str = Field(
        min_length=1,
    )

    reason: str = Field(
        min_length=1,
    )

    change_instructions: list[str] = Field(
        min_length=1,
    )


class CorrectionProposal(BaseModel):
    """
    Structured AI-generated correction proposal.

    This is advisory only. It does not modify repository files.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    summary: str = Field(
        min_length=1,
    )

    root_cause: str = Field(
        min_length=1,
    )

    files: list[CorrectionFileProposal] = Field(
        min_length=1,
        max_length=8,
    )

    pytest_targets: list[str] = Field(
        default_factory=list,
    )

    risks: list[str] = Field(
        default_factory=list,
    )

    needs_human_review: bool = True


class CorrectionProposalResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    session_id: uuid.UUID

    source_verification_run_id: uuid.UUID

    status: str

    proposal: CorrectionProposal