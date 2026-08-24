import uuid
from pathlib import Path

from agents.tool_context import ToolContext

from app.agent.context import EngineeringAgentContext
from app.agent.tools import (
    list_directory,
    read_file,
    search_code,
)
from app.tools.repository import SecureWorkspace


def build_context(
    repository: Path,
) -> ToolContext[EngineeringAgentContext]:
    context = EngineeringAgentContext(
        task_id=uuid.uuid4(),
        task_title="Test task",
        task_description="Test description",
        workspace=SecureWorkspace(repository),
    )

    return ToolContext(
        context=context,
        tool_name="test_tool",
        tool_call_id="test-call",
        tool_arguments="{}",
    )


def test_agent_list_directory_tool(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    result = list_directory.__wrapped__(
        ctx,
        ".",
    )

    assert "main.py" in result


def test_agent_read_file_tool(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    result = read_file.__wrapped__(
        ctx,
        "main.py",
    )

    assert "def hello" in result


def test_agent_search_code_tool(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "def authenticate_user():\n"
        "    pass\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    result = search_code.__wrapped__(
        ctx,
        "authenticate_user",
    )

    assert "main.py" in result


def test_search_code_tool_schema() -> None:
    schema = (
        search_code.params_json_schema
    )

    properties = schema[
        "properties"
    ]

    assert set(properties) == {
        "query",
        "path",
        "max_results",
        "case_sensitive",
    }

    assert schema["required"] == [
        "query",
    ]


def test_repository_tool_call_is_recorded(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    read_file.__wrapped__(
        ctx,
        "main.py",
    )

    assert (
        ctx.context.repository_tool_calls
        == 1
    )

    assert len(
        ctx.context.repository_evidence
    ) == 1

    evidence = (
        ctx.context.repository_evidence[0]
    )

    assert "read_file" in evidence
    assert "main.py" in evidence
    assert "def hello" in evidence


def test_duplicate_repository_call_is_blocked(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    first_result = read_file.__wrapped__(
        ctx,
        "main.py",
    )

    second_result = read_file.__wrapped__(
        ctx,
        "main.py",
    )

    assert "hello" in first_result

    assert (
        "DUPLICATE REPOSITORY TOOL CALL BLOCKED"
        in second_result
    )

    assert (
        ctx.context.repository_tool_calls
        == 1
    )


def test_repository_tool_budget_is_enforced(
    tmp_path: Path,
) -> None:
    (tmp_path / "first.py").write_text(
        "print('first')",
        encoding="utf-8",
    )

    (tmp_path / "second.py").write_text(
        "print('second')",
        encoding="utf-8",
    )

    ctx = build_context(
        tmp_path,
    )

    ctx.context.max_repository_tool_calls = 1

    first_result = read_file.__wrapped__(
        ctx,
        "first.py",
    )

    second_result = read_file.__wrapped__(
        ctx,
        "second.py",
    )

    assert "first" in first_result

    assert (
        "REPOSITORY INSPECTION BUDGET EXHAUSTED"
        in second_result
    )

    assert (
        ctx.context.repository_tool_calls
        == 1
    )