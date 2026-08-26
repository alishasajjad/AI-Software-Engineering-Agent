from app.schemas.correction_loop import (
    CorrectionLoopNextAction,
)
from app.services.correction_loop_service import (
    classify_correction_status,
)


def test_analysis_ready_generates_proposal() -> None:
    result = classify_correction_status(
        "analysis_ready"
    )

    assert result.terminal is False
    assert result.safe_stopped is False

    assert (
        result.next_action
        == CorrectionLoopNextAction
        .GENERATE_PROPOSAL
    )


def test_proposal_ready_prepares_patches() -> None:
    result = classify_correction_status(
        "proposal_ready"
    )

    assert result.terminal is False

    assert (
        result.next_action
        == CorrectionLoopNextAction
        .PREPARE_PATCHES
    )


def test_patch_ready_stops_for_human_review() -> None:
    result = classify_correction_status(
        "patch_ready"
    )

    assert result.terminal is False

    assert (
        result.requires_human_action
        is True
    )

    assert (
        result.next_action
        == CorrectionLoopNextAction
        .REVIEW_PATCHES
    )


def test_approved_patches_require_explicit_apply() -> None:
    result = classify_correction_status(
        "patches_approved"
    )

    assert result.terminal is False

    assert (
        result.requires_human_action
        is True
    )

    assert (
        result.next_action
        == CorrectionLoopNextAction
        .APPLY_APPROVED_PATCHES
    )


def test_applied_patches_are_reverified() -> None:
    result = classify_correction_status(
        "patches_applied"
    )

    assert result.terminal is False

    assert (
        result.next_action
        == CorrectionLoopNextAction
        .REVERIFY
    )


def test_completed_workflow_is_terminal_success() -> None:
    result = classify_correction_status(
        "completed"
    )

    assert result.terminal is True

    assert result.safe_stopped is False

    assert result.stop_reason is None

    assert (
        result.next_action
        == CorrectionLoopNextAction.NONE
    )


def test_exhausted_workflow_stops_safely() -> None:
    result = classify_correction_status(
        "exhausted"
    )

    assert result.terminal is True

    assert result.safe_stopped is True

    assert (
        result.stop_reason
        == "maximum_attempts_reached"
    )

    assert (
        result.next_action
        == CorrectionLoopNextAction.NONE
    )


def test_unsafe_states_never_continue_automatically() -> None:
    stale = classify_correction_status(
        "patch_stale"
    )

    unsupported = (
        classify_correction_status(
            "unexpected_state"
        )
    )

    assert stale.terminal is True
    assert stale.safe_stopped is True

    assert (
        stale.next_action
        == CorrectionLoopNextAction.NONE
    )

    assert unsupported.terminal is True
    assert unsupported.safe_stopped is True

    assert (
        unsupported.next_action
        == CorrectionLoopNextAction.NONE
    )