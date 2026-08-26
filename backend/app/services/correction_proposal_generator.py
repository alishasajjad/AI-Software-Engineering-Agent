from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from openai import (
    BadRequestError,
    OpenAI,
)

from app.agent.model_router import (
    ModelFallbackExhaustedError,
    run_sync_model_call_with_fallback,
)
from app.schemas.correction_proposal import (
    CorrectionProposal,
)
from app.tools.repository import SecureWorkspace
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
    """
    Correction proposal could not be generated.
    """


def _normalize_candidate_path(
    value: str,
) -> str | None:
    normalized = (
        value.strip()
        .replace("\\", "/")
    )

    while normalized.startswith(
        "./"
    ):
        normalized = normalized[
            2:
        ]

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

    for match in (
        PYTHON_PATH_PATTERN.finditer(
            text
        )
    ):
        normalized = (
            _normalize_candidate_path(
                match.group(
                    "path"
                )
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
        for match in (
            pattern.finditer(
                content
            )
        ):
            module_name = (
                match.group(
                    "module"
                )
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
    Collect relevant repository files referenced by
    verification output.

    Simple local Python imports are also followed so that
    failing tests can lead to their corresponding
    implementation files.
    """

    evidence = (
        stdout
        + "\n"
        + stderr
    )

    queue = (
        _extract_python_paths(
            evidence
        )
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
        path = queue.pop(
            0
        )

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

        result = (
            repository_read_file(
                workspace,
                relative_path=(
                    normalized
                ),
            )
        )

        content = (
            result.content[
                :MAX_FILE_CHARACTERS
            ]
        )

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

        for imported_path in (
            imported_paths
        ):
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


def _extract_json_object(
    text: str,
) -> str:
    """
    Extract one JSON object from a model response.

    This is primarily useful for Qwen's plain-JSON fallback,
    where the provider is not enforcing response_format.
    """

    cleaned = text.strip()

    if not cleaned:
        raise (
            CorrectionProposalGenerationError(
                "Groq returned an empty "
                "correction proposal."
            )
        )

    if cleaned.startswith(
        "```"
    ):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[
                1:
            ]

        if (
            lines
            and lines[-1].strip()
            == "```"
        ):
            lines = lines[
                :-1
            ]

        cleaned = "\n".join(
            lines
        ).strip()

    start_index = cleaned.find(
        "{"
    )

    end_index = cleaned.rfind(
        "}"
    )

    if (
        start_index == -1
        or end_index == -1
        or end_index < start_index
    ):
        raise (
            CorrectionProposalGenerationError(
                "Correction proposal did not "
                "contain a JSON object."
            )
        )

    return cleaned[
        start_index : end_index + 1
    ]


def _is_qwen_model(
    model_name: str,
) -> bool:
    """
    Return True for Qwen-family models.
    """

    return (
        model_name.strip()
        .lower()
        .startswith(
            "qwen/"
        )
    )


def _is_json_validation_failure(
    exc: Exception,
) -> bool:
    """
    Detect provider-side structured JSON failures.

    This is not a rate-limit condition.

    The same model gets one plain-JSON retry before the
    error is surfaced.
    """

    if not isinstance(
        exc,
        BadRequestError,
    ):
        return False

    message = str(
        exc
    ).lower()

    return (
        "json_validate_failed"
        in message
        or "failed to validate json"
        in message
        or "failed to generate json"
        in message
        or (
            "max completion tokens reached"
            in message
            and "json"
            in message
        )
    )


def _build_system_prompt() -> str:
    """
    Build the correction-planning system prompt.
    """

    return """
You are the correction-planning component of an autonomous
software engineering system.

Your job is to analyze a failed automated verification run and
produce a conservative correction proposal.

Important rules:

1. Do not modify files.
2. Do not output unified diffs.
3. Do not output full replacement source code.
4. Propose only the minimum changes needed to address the failure.
5. Preserve the original software task intent.
6. Treat the original task description as an important source of truth.
7. Do not blindly change implementation code merely to satisfy a test.
8. Do not blindly change tests merely to make verification pass.
9. If repository evidence shows that implementation behavior violates
   the original requirement, propose an implementation correction.
10. If repository evidence clearly shows that a test contradicts the
    original requirement, identify that conflict conservatively.
11. Never delete tests simply to make verification pass.
12. Use only repository files supported by the supplied evidence.
13. pytest_targets must contain repository-relative test paths.
14. Mention uncertainty in risks.
15. needs_human_review should normally remain true.
16. Return JSON only.
17. Return exactly one JSON object.
18. The JSON must match the supplied schema exactly.
19. Do not wrap JSON in Markdown or code fences.
20. Keep the response concise.
""".strip()


def _build_user_prompt(
    *,
    task_title: str,
    task_description: str,
    failure_type: str,
    failure_summary: str,
    failed_command: str,
    stdout: str,
    stderr: str,
    repository_context: str,
    schema: dict,
) -> str:
    """
    Build the evidence-grounded correction request.
    """

    return f"""
TASK TITLE:

{task_title}

ORIGINAL TASK DESCRIPTION:

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

Preserve the original task intent.

Use only files justified by the supplied repository evidence.

Return exactly one valid JSON object matching the schema.
""".strip()


def _request_qwen_correction(
    *,
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
):
    """
    Request a correction proposal from Qwen.

    Attempt 1:
        Groq JSON Object Mode.

    If Groq rejects structured JSON generation:
        Retry once on the same Qwen model using plain JSON.

    Rate-limit errors are not swallowed here. They propagate
    back to the central model router so another configured
    model can be attempted.
    """

    try:
        return (
            client.chat.completions.create(
                model=model_name,
                temperature=0.6,
                top_p=0.8,
                max_completion_tokens=4096,
                response_format={
                    "type": (
                        "json_object"
                    ),
                },
                extra_body={
                    "reasoning_effort": (
                        "none"
                    ),
                    "reasoning_format": (
                        "hidden"
                    ),
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            system_prompt
                            + "\n\n"
                            "Keep the JSON compact. "
                            "Do not repeat repository "
                            "evidence unnecessarily."
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
        if not _is_json_validation_failure(
            exc
        ):
            raise

    fallback_prompt = (
        user_prompt
        + "\n\n"
        "FALLBACK OUTPUT REQUIREMENT:\n"
        "Return one compact syntactically valid "
        "JSON object only.\n"
        "Start with { and end with }.\n"
        "No Markdown.\n"
        "No code fences.\n"
        "No explanatory text outside the JSON."
    )

    return (
        client.chat.completions.create(
            model=model_name,
            temperature=0.3,
            top_p=0.8,
            max_completion_tokens=4096,
            extra_body={
                "reasoning_effort": (
                    "none"
                ),
                "reasoning_format": (
                    "hidden"
                ),
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
                        fallback_prompt
                    ),
                },
            ],
        )
    )


def _request_standard_correction(
    *,
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
):
    """
    Request a correction proposal from non-Qwen models.

    The primary GPT-OSS model keeps JSON Object Mode.
    """

    return (
        client.chat.completions.create(
            model=model_name,
            temperature=0,
            max_completion_tokens=4096,
            response_format={
                "type": "json_object",
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
    """
    Generate and validate a conservative correction proposal.

    Automatic model routing:

        primary model
            ↓ rate limit
        fallback model

    Model switching occurs only for provider rate-limit or
    quota exhaustion errors.

    Qwen additionally receives its own same-model JSON
    compatibility fallback.
    """

    schema = (
        CorrectionProposal
        .model_json_schema()
    )

    system_prompt = (
        _build_system_prompt()
    )

    user_prompt = (
        _build_user_prompt(
            task_title=task_title,
            task_description=(
                task_description
            ),
            failure_type=(
                failure_type
            ),
            failure_summary=(
                failure_summary
            ),
            failed_command=(
                failed_command
            ),
            stdout=stdout,
            stderr=stderr,
            repository_context=(
                repository_context
            ),
            schema=schema,
        )
    )

    def request_factory(
        client: OpenAI,
        model_name: str,
    ):
        if _is_qwen_model(
            model_name
        ):
            return (
                _request_qwen_correction(
                    client=client,
                    model_name=(
                        model_name
                    ),
                    system_prompt=(
                        system_prompt
                    ),
                    user_prompt=(
                        user_prompt
                    ),
                )
            )

        return (
            _request_standard_correction(
                client=client,
                model_name=(
                    model_name
                ),
                system_prompt=(
                    system_prompt
                ),
                user_prompt=(
                    user_prompt
                ),
            )
        )

    try:
        response = (
            run_sync_model_call_with_fallback(
                operation_name=(
                    "correction_proposal"
                ),
                request_factory=(
                    request_factory
                ),
            )
        )

    except ModelFallbackExhaustedError as exc:
        raise (
            CorrectionProposalGenerationError(
                "Correction proposal could not "
                "be generated because all "
                "configured AI models are "
                "currently rate limited: "
                f"{exc}"
            )
        ) from exc

    except Exception as exc:
        raise (
            CorrectionProposalGenerationError(
                "Groq correction proposal "
                "request failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )
        ) from exc

    content = (
        response.choices[
            0
        ].message.content
    )

    if not content:
        raise (
            CorrectionProposalGenerationError(
                "Groq returned an empty "
                "correction proposal."
            )
        )

    try:
        json_content = (
            _extract_json_object(
                content
            )
        )

        return (
            CorrectionProposal
            .model_validate_json(
                json_content
            )
        )

    except (
        CorrectionProposalGenerationError
    ):
        raise

    except Exception as exc:
        raise (
            CorrectionProposalGenerationError(
                "Groq returned an invalid "
                "correction proposal: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )
        ) from exc


__all__ = [
    "CorrectionProposalGenerationError",
    "collect_correction_context",
    "generate_correction_proposal",
]