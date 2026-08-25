import json
import uuid
from pathlib import Path

from agents.tool_context import ToolContext

from app.agent.context import (
    EngineeringAgentContext,
)
from app.agent.edit_tools import (
    prepare_file_edit,
)
from app.schemas.patch import (
    PendingPatchStatus,
)
from app.tools.repository import SecureWorkspace


def build_context(
    repository: Path,
) -> ToolContext[EngineeringAgentContext]:
    context = EngineeringAgentContext(
        task_id=uuid.uuid4(),
        task_title="Test edit task",
        task_description="Prepare a safe edit.",
        workspace=SecureWorkspace(
            repository
        ),
    )

    return ToolContext(
        context=context,
        tool_name="prepare_file_edit",
        tool_call_id="test-call",
        tool_arguments="{}",
    )


def test_prepare_file_edit_creates_pending_patch(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    original = (
        "def hello():\n"
        "    return 'hello'\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    result = prepare_file_edit.__wrapped__(
        ctx,
        "main.py",
        "return 'hello'",
        "return 'hello world'",
    )

    payload = json.loads(
        result
    )

    assert (
        payload["path"]
        == "main.py"
    )

    assert (
        payload["status"]
        == "pending"
    )

    assert len(
        ctx.context.pending_patches
    ) == 1

    pending_patch = (
        ctx.context.pending_patches[0]
    )

    assert (
        pending_patch.status
        == PendingPatchStatus.PENDING
    )

    assert (
        "return 'hello world'"
        in pending_patch.proposed_content
    )

    assert pending_patch.original_sha256


def test_prepare_file_edit_does_not_modify_disk(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    original = (
        "value = 1\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    prepare_file_edit.__wrapped__(
        ctx,
        "main.py",
        "value = 1",
        "value = 2",
    )

    assert file_path.read_text(
        encoding="utf-8",
    ) == original


def test_prepare_file_edit_rejects_duplicate_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    first_result = (
        prepare_file_edit.__wrapped__(
            ctx,
            "main.py",
            "value = 1",
            "value = 2",
        )
    )

    second_result = (
        prepare_file_edit.__wrapped__(
            ctx,
            "main.py",
            "value = 1",
            "value = 3",
        )
    )

    assert (
        "PATCH_REJECTED"
        not in first_result
    )

    assert (
        "pending patch already exists"
        in second_result
    )

    assert len(
        ctx.context.pending_patches
    ) == 1


def test_prepare_file_edit_rejects_missing_target(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    result = prepare_file_edit.__wrapped__(
        ctx,
        "main.py",
        "missing = 1",
        "missing = 2",
    )

    assert (
        "PATCH_REJECTED"
        in result
    )

    assert not ctx.context.pending_patches


def test_prepare_file_edit_enforces_patch_limit(
    tmp_path: Path,
) -> None:
    (tmp_path / "first.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    (tmp_path / "second.py").write_text(
        "value = 2\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    ctx.context.max_pending_patches = 1

    first_result = (
        prepare_file_edit.__wrapped__(
            ctx,
            "first.py",
            "value = 1",
            "value = 10",
        )
    )

    second_result = (
        prepare_file_edit.__wrapped__(
            ctx,
            "second.py",
            "value = 2",
            "value = 20",
        )
    )

    assert (
        "PATCH_REJECTED"
        not in first_result
    )

    assert (
        "maximum number of pending patches"
        in second_result
    )

    assert len(
        ctx.context.pending_patches
    ) == 1


def test_prepare_file_edit_tool_schema() -> None:
    schema = (
        prepare_file_edit.params_json_schema
    )

    assert set(
        schema["properties"]
    ) == {
        "path",
        "old_text",
        "new_text",
    }

    assert set(
        schema["required"]
    ) == {
        "path",
        "old_text",
        "new_text",
    }