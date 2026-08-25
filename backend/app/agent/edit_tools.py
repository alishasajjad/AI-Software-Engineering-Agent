import hashlib

from agents import function_tool
from agents.tool_context import ToolContext

from app.agent.context import EngineeringAgentContext
from app.schemas.patch import (
    PendingPatch,
    PendingPatchStatus,
    PreparedEditResult,
)
from app.tools.patch import PatchError, SafePatchEngine


def _normalize_repository_path(
    path: str,
) -> str:
    return path.strip().replace(
        "\\",
        "/",
    )


def _has_pending_patch_for_path(
    ctx: ToolContext[EngineeringAgentContext],
    path: str,
) -> bool:
    normalized_path = (
        _normalize_repository_path(path)
    )

    return any(
        _normalize_repository_path(
            patch.path
        )
        == normalized_path
        and patch.status
        == PendingPatchStatus.PENDING
        for patch in ctx.context.pending_patches
    )


@function_tool(strict_mode=False)
def prepare_file_edit(
    ctx: ToolContext[EngineeringAgentContext],
    path: str,
    old_text: str,
    new_text: str,
) -> str:
    """
    Prepare a safe code edit without modifying the repository.

    The tool validates an exact old_text replacement, generates a
    unified diff, and stores the proposed edit as a pending patch.

    Args:
        path:
            Repository-relative path of the file to edit.

        old_text:
            Exact existing text that must appear once in the file.

        new_text:
            Replacement text. This may be empty when deleting text.
    """

    normalized_path = (
        _normalize_repository_path(path)
    )

    if not normalized_path:
        return (
            "PATCH_REJECTED: "
            "A repository-relative path is required."
        )

    if not old_text:
        return (
            "PATCH_REJECTED: "
            "old_text cannot be empty."
        )

    if (
        len(ctx.context.pending_patches)
        >= ctx.context.max_pending_patches
    ):
        return (
            "PATCH_REJECTED: "
            "The maximum number of pending patches "
            "for this agent run has been reached."
        )

    if _has_pending_patch_for_path(
        ctx,
        normalized_path,
    ):
        return (
            "PATCH_REJECTED: "
            f"A pending patch already exists for "
            f"'{normalized_path}'. "
            "Only one pending patch per file is allowed "
            "during this phase."
        )

    patch_engine = SafePatchEngine(
        ctx.context.workspace,
    )

    try:
        preview = (
            patch_engine.prepare_replacement(
                path=normalized_path,
                old_text=old_text,
                new_text=new_text,
            )
        )

    except PatchError as exc:
        return (
            "PATCH_REJECTED: "
            f"{exc}"
        )

    original_sha256 = hashlib.sha256(
        preview.original_content.encode(
            "utf-8"
        )
    ).hexdigest()

    pending_patch = PendingPatch(
        task_id=ctx.context.task_id,
        path=preview.path,
        original_content=(
            preview.original_content
        ),
        proposed_content=(
            preview.proposed_content
        ),
        diff=preview.diff,
        original_sha256=original_sha256,
    )

    ctx.context.pending_patches.append(
        pending_patch,
    )

    result = PreparedEditResult(
        patch_id=pending_patch.id,
        path=pending_patch.path,
        diff=pending_patch.diff,
        status=pending_patch.status,
    )

    return result.model_dump_json(
        indent=2,
    )