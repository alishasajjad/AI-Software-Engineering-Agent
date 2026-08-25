from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from openai import OpenAI

from app.core.config import settings
from app.schemas.correction_proposal import (
    CorrectionProposal,
)
from app.tools.repository import (
    SecureWorkspace,
)
from app.tools.repository import (
    read_file as repository_read_file,
)

MAX_CONTEXT_FILES = 8
MAX_FILE_CHARACTERS = 10_000
MAX_TOTAL_CONTEXT_CHARACTERS = 40_000

PYTHON_PATH_PATTERN = re.compile(
    r"(?P<path>"
    r"(?:[A-Za-z0-9_.-]+[/\\])*"
    r"[A-Za-z0-9_.-]+\.py"
    r")"
)

FROM_IMPORT_PATTERN = re.compile(
    r"^\s*from\s+"
    r"(?P<module>[A-Za-z_][A-Za-z0-9_.]*)"
    r"\s+import\s+",
    re.MULTILINE,
)

IMPORT_PATTERN = re.compile(
    r"^\s*import\s+"
    r"(?P<module>[A-Za-z_][A-Za-z0-9_.]*)",
    re.MULTILINE,
)


class CorrectionProposalGenerationError(
    RuntimeError
):
    """Correction proposal could not be generated."""


def _secret_value(
    value: object,
) -> str:
    if hasattr(
        value,
        "get_secret_value",
    ):
        return str(
            value.get_secret_value()
        )

    return str(value)


def _normalize_candidate_path(
    value: str,
) -> str | None:
    normalized = (
        value.strip()
        .replace("\\", "/")
    )

    while normalized.startswith("./"):
        normalized = normalized[2:]

    if not normalized:
        return None

    path = PurePosixPath(
        normalized
    )

    if path.is_absolute():
        return None

    if ".." in path.parts:
        return None

    if ":" in normalized:
        return None

    if not normalized.endswith(
        ".py"
    ):
        return None

    return normalized


def _extract_python_paths(
    text: str,
) -> list[str]:
    paths: list[str] = []

    for match in PYTHON_PATH_PATTERN.finditer(
        text
    ):
        normalized = (
            _normalize_candidate_path(
                match.group("path")
            )
        )

        if (
            normalized is not None
            and normalized not in paths
        ):
            paths.append(
                normalized
            )

    return paths


def _extract_local_import_paths(
    content: str,
) -> list[str]:
    candidates: list[str] = []

    for pattern in (
        FROM_IMPORT_PATTERN,
        IMPORT_PATTERN,
    ):
        for match in pattern.finditer(
            content
        ):
            module_name = match.group(
                "module"
            )

            module_path = (
                module_name.replace(
                    ".",
                    "/",
                )
                + ".py"
            )

            if (
                module_path
                not in candidates
            ):
                candidates.append(
                    module_path
                )

    return candidates


def _candidate_exists(
    workspace: SecureWorkspace,
    relative_path: str,
) -> bool:
    root = Path(
        workspace.root
    )

    candidate = root.joinpath(
        *PurePosixPath(
            relative_path
        ).parts
    )

    try:
        resolved = (
            candidate.resolve()
        )

        resolved.relative_to(
            root.resolve()
        )

    except ValueError:
        return False

    return resolved.is_file()


def collect_correction_context(
    *,
    workspace: SecureWorkspace,
    stdout: str,
    stderr: str,
) -> str:
    """
    Collect relevant source files referenced by verification output.

    The function also follows simple local Python imports so a
    failing test can lead us to its implementation file.
    """

    evidence = (
        stdout
        + "\n"
        + stderr
    )

    queue = _extract_python_paths(
        evidence
    )

    visited: set[str] = set()

    sections: list[str] = []

    total_characters = 0

    while (
        queue
        and len(visited)
        < MAX_CONTEXT_FILES
        and total_characters
        < MAX_TOTAL_CONTEXT_CHARACTERS
    ):
        path = queue.pop(0)

        normalized = (
            _normalize_candidate_path(
                path
            )
        )

        if normalized is None:
            continue

        if normalized in visited:
            continue

        visited.add(
            normalized
        )

        if not _candidate_exists(
            workspace,
            normalized,
        ):
            continue

        result = repository_read_file(
            workspace,
            relative_path=normalized,
        )

        content = result.content[
            :MAX_FILE_CHARACTERS
        ]

        section = (
            f"FILE: {normalized}\n"
            "CONTENT:\n"
            f"{content}"
        )

        sections.append(
            section
        )

        total_characters += len(
            section
        )

        imported_paths = (
            _extract_local_import_paths(
                content
            )
        )

        for imported_path in imported_paths:
            if (
                imported_path
                not in visited
                and imported_path
                not in queue
            ):
                queue.append(
                    imported_path
                )

    if not sections:
        return (
            "No directly referenced repository "
            "files could be collected."
        )

    return "\n\n---\n\n".join(
        sections
    )


def _build_client() -> OpenAI:
    api_key_value = getattr(
        settings,
        "groq_api_key",
        None,
    )

    if not api_key_value:
        raise CorrectionProposalGenerationError(
            "GROQ_API_KEY is not configured."
        )

    return OpenAI(
        api_key=_secret_value(
            api_key_value
        ),
        base_url=(
            "https://api.groq.com/"
            "openai/v1"
        ),
    )


def generate_correction_proposal(
    *,
    task_title: str,
    task_description: str,
    failure_type: str,
    failure_summary: str,
    failed_command: str,
    stdout: str,
    stderr: str,
    repository_context: str,
) -> CorrectionProposal:
    schema = (
        CorrectionProposal.model_json_schema()
    )

    system_prompt = """
You are the correction-planning component of an autonomous
software engineering system.

Your job is to analyze a failed automated verification run and
produce a conservative correction proposal.

Important rules:

1. Do not modify files.
2. Do not output unified diffs.
3. Do not output full replacement source code.
4. Propose only the minimum changes needed to address the failure.
5. Prefer fixing implementation defects instead of weakening tests.
6. Never recommend deleting tests simply to make verification pass.
7. Use only repository files supported by the supplied evidence.
8. pytest_targets must contain repository-relative test paths.
9. Mention uncertainty in risks.
10. needs_human_review should normally remain true.
11. Return JSON only.
12. The JSON must match the supplied schema exactly.
""".strip()

    user_prompt = f"""
TASK TITLE:
{task_title}

TASK DESCRIPTION:
{task_description}

FAILURE TYPE:
{failure_type}

FAILURE SUMMARY:
{failure_summary}

FAILED COMMAND:
{failed_command}

VERIFICATION STDOUT:
{stdout}

VERIFICATION STDERR:
{stderr}

REPOSITORY EVIDENCE:
{repository_context}

REQUIRED JSON SCHEMA:
{json.dumps(schema, indent=2)}

Create the safest minimal correction proposal.
""".strip()

    client = _build_client()

    model = getattr(
        settings,
        "groq_model",
        "openai/gpt-oss-120b",
    )

    try:
        response = (
            client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={
                    "type": "json_object"
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            system_prompt
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            user_prompt
                        ),
                    },
                ],
            )
        )

    except Exception as exc:
        raise (
            CorrectionProposalGenerationError(
                "Groq correction proposal "
                "request failed."
            )
        ) from exc

    content = (
        response.choices[
            0
        ].message.content
    )

    if not content:
        raise CorrectionProposalGenerationError(
            "Groq returned an empty "
            "correction proposal."
        )

    try:
        return (
            CorrectionProposal.model_validate_json(
                content
            )
        )

    except Exception as exc:
        raise (
            CorrectionProposalGenerationError(
                "Groq returned an invalid "
                "correction proposal."
            )
        ) from exc