from typing import Any

from agents import function_tool
from agents.tool_context import ToolContext
from pydantic import BaseModel

from app.agent.context import EngineeringAgentContext
from app.tools.repository import (
    list_directory as repository_list_directory,
)
from app.tools.repository import (
    read_file as repository_read_file,
)
from app.tools.repository import (
    search_code as repository_search_code,
)

MAX_EVIDENCE_CHARACTERS = 12_000


def _render_repository_result(
    result: Any,
) -> str:
    if isinstance(result, BaseModel):
        return result.model_dump_json(
            indent=2,
        )

    if isinstance(result, str):
        return result

    return str(result)


def _start_repository_tool_call(
    ctx: ToolContext[EngineeringAgentContext],
    signature: str,
) -> str | None:
    context = ctx.context

    if signature in context.seen_repository_calls:
        return (
            "DUPLICATE REPOSITORY TOOL CALL BLOCKED. "
            "This repository operation has already been performed. "
            "Use the evidence already collected and continue toward "
            "the final repository inspection report."
        )

    if (
        context.repository_tool_calls
        >= context.max_repository_tool_calls
    ):
        return (
            "REPOSITORY INSPECTION BUDGET EXHAUSTED. "
            "Do not call more repository tools. "
            "Return the final repository inspection report now."
        )

    context.seen_repository_calls.add(
        signature,
    )

    context.repository_tool_calls += 1

    return None


def _record_repository_evidence(
    ctx: ToolContext[EngineeringAgentContext],
    tool_name: str,
    arguments: str,
    output: str,
) -> None:
    trimmed_output = output[
        :MAX_EVIDENCE_CHARACTERS
    ]

    evidence = (
        f"TOOL: {tool_name}\n"
        f"ARGUMENTS: {arguments}\n"
        f"RESULT:\n{trimmed_output}"
    )

    ctx.context.repository_evidence.append(
        evidence,
    )


@function_tool(strict_mode=False)
def list_directory(
    ctx: ToolContext[EngineeringAgentContext],
    path: str = ".",
) -> str:
    """
    List files and directories inside a repository-relative path.

    Args:
        path:
            Repository-relative directory to inspect.
            Use "." for the repository root.
    """

    signature = (
        f"list_directory:{path}"
    )

    blocked_message = (
        _start_repository_tool_call(
            ctx,
            signature,
        )
    )

    if blocked_message is not None:
        return blocked_message

    result = repository_list_directory(
        ctx.context.workspace,
        relative_path=path,
    )

    output = _render_repository_result(
        result,
    )

    _record_repository_evidence(
        ctx=ctx,
        tool_name="list_directory",
        arguments=f"path={path!r}",
        output=output,
    )

    return output


@function_tool(strict_mode=False)
def read_file(
    ctx: ToolContext[EngineeringAgentContext],
    path: str,
) -> str:
    """
    Read a text file from the secure repository workspace.

    Args:
        path:
            Repository-relative path of the source file to read.
    """

    signature = (
        f"read_file:{path}"
    )

    blocked_message = (
        _start_repository_tool_call(
            ctx,
            signature,
        )
    )

    if blocked_message is not None:
        return blocked_message

    result = repository_read_file(
        ctx.context.workspace,
        relative_path=path,
    )

    output = _render_repository_result(
        result,
    )

    _record_repository_evidence(
        ctx=ctx,
        tool_name="read_file",
        arguments=f"path={path!r}",
        output=output,
    )

    return output


@function_tool(strict_mode=False)
def search_code(
    ctx: ToolContext[EngineeringAgentContext],
    query: str,
    path: str = ".",
    max_results: int = 20,
    case_sensitive: bool = False,
) -> str:
    """
    Search repository source code for a function, class, route, or keyword.

    Args:
        query:
            Function, class, route, keyword, or text to search for.
        path:
            Repository-relative location to search.
        max_results:
            Maximum number of search matches to return.
        case_sensitive:
            Whether matching should be case-sensitive.
    """

    signature = (
        "search_code:"
        f"{query}:"
        f"{path}:"
        f"{max_results}:"
        f"{case_sensitive}"
    )

    blocked_message = (
        _start_repository_tool_call(
            ctx,
            signature,
        )
    )

    if blocked_message is not None:
        return blocked_message

    result = repository_search_code(
        ctx.context.workspace,
        query=query,
        relative_path=path,
        max_results=max_results,
        case_sensitive=case_sensitive,
    )

    output = _render_repository_result(
        result,
    )

    _record_repository_evidence(
        ctx=ctx,
        tool_name="search_code",
        arguments=(
            f"query={query!r}, "
            f"path={path!r}, "
            f"max_results={max_results}, "
            f"case_sensitive={case_sensitive}"
        ),
        output=output,
    )

    return output