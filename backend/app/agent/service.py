from __future__ import annotations

import json
import uuid
from typing import Any

from agents.exceptions import MaxTurnsExceeded
from openai import (
    AsyncOpenAI,
    BadRequestError,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.context import EngineeringAgentContext
from app.agent.engineer import (
    build_repository_inspector_agent,
)
from app.agent.model_router import (
    ModelFallbackExhaustedError,
    run_agent_with_fallback,
    run_async_model_call_with_fallback,
)
from app.agent.schemas import ImplementationPlan
from app.core.config import settings
from app.models.task import Task
from app.tools.repository import SecureWorkspace


class PlanGenerationError(RuntimeError):
    """
    Raised when the AI agent cannot generate a usable
    implementation plan.
    """


class _PlanSchemaValidationError(ValueError):
    """
    Internal error raised when formatter JSON is valid JSON
    but does not satisfy the ImplementationPlan schema.

    The error retains Pydantic validation details so the same
    model can receive one focused schema-repair request.
    """

    def __init__(
        self,
        *,
        message: str,
        validation_details: str,
    ) -> None:
        self.validation_details = validation_details

        super().__init__(
            message
        )


def _extract_json_object(
    text: str,
) -> str:
    """
    Extract one JSON object from model output.

    This protects the application when a model accidentally
    wraps otherwise valid JSON in Markdown or explanatory text.
    """

    cleaned = text.strip()

    if not cleaned:
        raise PlanGenerationError(
            "Plan formatter returned an empty response."
        )

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

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
        raise PlanGenerationError(
            "Plan formatter did not return "
            "a valid JSON object."
        )

    return cleaned[
        start_index : end_index + 1
    ]


def _validation_details(
    exc: ValidationError,
) -> str:
    """
    Convert Pydantic validation errors into compact JSON that
    can be supplied to the schema-repair request.
    """

    return json.dumps(
        exc.errors(),
        indent=2,
        ensure_ascii=False,
        default=str,
    )


def _parse_implementation_plan(
    output: Any,
) -> ImplementationPlan:
    """
    Convert formatter output into a validated
    ImplementationPlan.

    Supported values:
    - ImplementationPlan
    - dict
    - JSON string

    A valid JSON object that fails the Pydantic schema raises
    _PlanSchemaValidationError so one schema-repair request can
    be attempted.
    """

    if isinstance(
        output,
        ImplementationPlan,
    ):
        return output

    if isinstance(
        output,
        dict,
    ):
        try:
            return (
                ImplementationPlan.model_validate(
                    output
                )
            )

        except ValidationError as exc:
            raise _PlanSchemaValidationError(
                message=(
                    "Plan formatter returned an object "
                    "that does not match the "
                    "implementation plan schema."
                ),
                validation_details=(
                    _validation_details(
                        exc
                    )
                ),
            ) from exc

    if isinstance(
        output,
        str,
    ):
        json_text = (
            _extract_json_object(
                output
            )
        )

        try:
            payload = json.loads(
                json_text
            )

        except json.JSONDecodeError as exc:
            raise PlanGenerationError(
                "Plan formatter returned invalid JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise PlanGenerationError(
                "Plan formatter JSON must contain "
                "one JSON object."
            )

        try:
            return (
                ImplementationPlan.model_validate(
                    payload
                )
            )

        except ValidationError as exc:
            raise _PlanSchemaValidationError(
                message=(
                    "Plan formatter returned JSON "
                    "that does not match the "
                    "implementation plan schema."
                ),
                validation_details=(
                    _validation_details(
                        exc
                    )
                ),
            ) from exc

    raise PlanGenerationError(
        "Plan formatter returned an unsupported "
        "output type: "
        f"{type(output).__name__}."
    )


def _serialize_formatter_output(
    output: Any,
) -> str:
    """
    Serialize invalid formatter output for a repair prompt.
    """

    if isinstance(
        output,
        str,
    ):
        return output

    try:
        return json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    except Exception:
        return str(
            output
        )


def _is_qwen_model(
    model_name: str,
) -> bool:
    """
    Return True when the selected model belongs to the
    Qwen family.
    """

    return (
        model_name.strip()
        .lower()
        .startswith("qwen/")
    )


def _is_json_validation_failure(
    exc: Exception,
) -> bool:
    """
    Detect Groq provider-side JSON Object Mode failures.

    These failures are handled with a plain-JSON retry on
    the same Qwen model.

    They are not treated as rate-limit conditions and
    therefore do not directly cause a model switch.
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
        "json_validate_failed" in message
        or "failed to validate json" in message
        or "failed to generate json" in message
        or (
            "max completion tokens reached"
            in message
            and "json"
            in message
        )
    )


def _formatter_system_prompt() -> str:
    """
    Shared concise implementation-plan formatter prompt.
    """

    return (
        "You are an implementation-plan formatter.\n\n"
        "Convert the supplied software task and repository "
        "inspection evidence into exactly one concise JSON "
        "object.\n\n"
        "STRICT RULES:\n"
        "1. Return JSON only.\n"
        "2. Return exactly one JSON object.\n"
        "3. Do not return Markdown.\n"
        "4. Do not use code fences.\n"
        "5. Do not add commentary before or after the JSON.\n"
        "6. Use double quotes for JSON strings.\n"
        "7. Use true and false for JSON booleans.\n"
        "8. Do not use trailing commas.\n"
        "9. Include every required property.\n"
        "10. Do not add properties outside the schema.\n"
        "11. Keep descriptions concise.\n"
        "12. Use repository-relative paths only.\n"
        "13. Use files supported by repository evidence.\n"
        "14. Do not invent files unless creating a new file "
        "is genuinely required.\n"
        "15. Steps must be concrete and verifiable.\n"
        "16. Every step object must contain order, action, "
        "files, and verification.\n"
        "17. relevant_files, assumptions, risks, and "
        "clarifying_questions must always be arrays.\n"
        "18. needs_clarification must always be a boolean.\n\n"
        "Return exactly this structure:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "relevant_files": ["string"],\n'
        '  "steps": [\n'
        "    {\n"
        '      "order": 1,\n'
        '      "action": "string",\n'
        '      "files": ["string"],\n'
        '      "verification": "string"\n'
        "    }\n"
        "  ],\n"
        '  "assumptions": ["string"],\n'
        '  "risks": ["string"],\n'
        '  "needs_clarification": false,\n'
        '  "clarifying_questions": []\n'
        "}\n"
    )


async def _request_qwen_json_formatter(
    *,
    client: AsyncOpenAI,
    model_name: str,
    formatter_input: str,
) -> str:
    """
    Request a Qwen implementation plan using Groq JSON
    Object Mode.

    If Groq rejects JSON generation at provider level,
    retry once on the same model without response_format.

    Genuine provider rate-limit errors are allowed to
    propagate to the central model router.
    """

    try:
        response = await (
            client.chat.completions.create(
                model=model_name,
                temperature=0.2,
                top_p=0.8,
                max_completion_tokens=2048,
                response_format={
                    "type": "json_object",
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
                            _formatter_system_prompt()
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            formatter_input
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

        fallback_input = (
            formatter_input
            + "\n\n"
            "FALLBACK OUTPUT REQUIREMENT:\n"
            "Return one compact valid JSON object only.\n"
            "The first character must be { and the last "
            "character must be }.\n"
            "Do not use Markdown or code fences.\n"
            "Keep every string short."
        )

        response = await (
            client.chat.completions.create(
                model=model_name,
                temperature=0.1,
                top_p=0.8,
                max_completion_tokens=2048,
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
                            _formatter_system_prompt()
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            fallback_input
                        ),
                    },
                ],
            )
        )

    content = (
        response.choices[
            0
        ].message.content
    )

    if not content:
        raise PlanGenerationError(
            "Plan formatter returned "
            "an empty response."
        )

    return content


async def _request_standard_formatter(
    *,
    client: AsyncOpenAI,
    model_name: str,
    formatter_input: str,
) -> str:
    """
    Formatter request for non-Qwen models.

    Model routing is handled centrally.
    """

    response = await (
        client.chat.completions.create(
            model=model_name,
            temperature=0,
            max_completion_tokens=2048,
            messages=[
                {
                    "role": "system",
                    "content": (
                        _formatter_system_prompt()
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        formatter_input
                    ),
                },
            ],
        )
    )

    content = (
        response.choices[
            0
        ].message.content
    )

    if not content:
        raise PlanGenerationError(
            "Plan formatter returned "
            "an empty response."
        )

    return content


async def _request_formatter_for_model(
    *,
    client: AsyncOpenAI,
    model_name: str,
    formatter_input: str,
) -> str:
    """
    Dispatch formatter generation according to model family.
    """

    if _is_qwen_model(
        model_name
    ):
        return (
            await _request_qwen_json_formatter(
                client=client,
                model_name=model_name,
                formatter_input=(
                    formatter_input
                ),
            )
        )

    return (
        await _request_standard_formatter(
            client=client,
            model_name=model_name,
            formatter_input=(
                formatter_input
            ),
        )
    )


def _build_schema_repair_input(
    *,
    original_formatter_input: str,
    invalid_output: Any,
    validation_details: str,
) -> str:
    """
    Build one tightly scoped schema-repair request.

    The model is instructed to preserve the original semantic
    plan and repair only structural/schema problems.
    """

    schema = (
        ImplementationPlan.model_json_schema()
    )

    return (
        "The previous implementation-plan response was "
        "valid JSON, but it failed the required Pydantic "
        "schema validation.\n\n"
        "Repair ONLY the JSON structure, missing fields, "
        "extra fields, or incorrect field types.\n"
        "Preserve the original software-task intent.\n"
        "Do not invent new implementation work unless it is "
        "required to make the existing plan structurally "
        "valid.\n"
        "Return exactly one JSON object and nothing else.\n\n"
        "ORIGINAL FORMATTER INPUT:\n"
        "--------------------------------\n"
        f"{original_formatter_input}\n"
        "--------------------------------\n\n"
        "INVALID PREVIOUS OUTPUT:\n"
        "--------------------------------\n"
        f"{_serialize_formatter_output(invalid_output)}\n"
        "--------------------------------\n\n"
        "PYDANTIC VALIDATION ERRORS:\n"
        "--------------------------------\n"
        f"{validation_details}\n"
        "--------------------------------\n\n"
        "EXACT IMPLEMENTATION PLAN JSON SCHEMA:\n"
        "--------------------------------\n"
        f"{json.dumps(schema, indent=2, ensure_ascii=False)}\n"
        "--------------------------------\n\n"
        "Return the corrected implementation plan now.\n"
        "JSON only. No Markdown. No explanation."
    )


async def _repair_implementation_plan_schema(
    *,
    selected_model_name: str,
    formatter_input: str,
    invalid_output: Any,
    validation_error: _PlanSchemaValidationError,
) -> ImplementationPlan:
    """
    Give the selected formatter model one focused
    schema-repair attempt.

    The same model is always attempted first.

    A different configured model may only be used if the
    selected model itself becomes rate limited during the
    repair request.
    """

    repair_input = (
        _build_schema_repair_input(
            original_formatter_input=(
                formatter_input
            ),
            invalid_output=(
                invalid_output
            ),
            validation_details=(
                validation_error
                .validation_details
            ),
        )
    )

    async def repair_request_factory(
        client: AsyncOpenAI,
        model_name: str,
    ) -> tuple[str, str]:
        content = (
            await _request_formatter_for_model(
                client=client,
                model_name=model_name,
                formatter_input=(
                    repair_input
                ),
            )
        )

        return (
            model_name,
            content,
        )

    try:
        (
            repair_model_name,
            repaired_output,
        ) = (
            await run_async_model_call_with_fallback(
                operation_name=(
                    "implementation_plan_schema_repair"
                ),
                request_factory=(
                    repair_request_factory
                ),
                primary_model=(
                    selected_model_name
                ),
            )
        )

    except ModelFallbackExhaustedError as exc:
        raise PlanGenerationError(
            "Plan formatter schema repair could not run "
            "because all configured AI models are currently "
            f"rate limited: {exc}"
        ) from exc

    except PlanGenerationError:
        raise

    except Exception as exc:
        raise PlanGenerationError(
            "Plan formatter schema repair failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        return (
            _parse_implementation_plan(
                repaired_output
            )
        )

    except _PlanSchemaValidationError as exc:
        raise PlanGenerationError(
            "Plan formatter schema repair returned JSON "
            "that still does not match the implementation "
            "plan schema. "
            f"Repair model: {repair_model_name}."
        ) from exc

    except PlanGenerationError as exc:
        raise PlanGenerationError(
            "Plan formatter schema repair did not return "
            "a usable implementation plan. "
            f"Repair model: {repair_model_name}. "
            f"{exc}"
        ) from exc


async def _run_plan_formatter_with_fallback(
    formatter_input: str,
) -> ImplementationPlan:
    """
    Generate the implementation plan with automatic
    model fallback.

    Model fallback occurs only for genuine provider
    rate-limit/quota failures.

    If the selected model returns valid JSON that fails the
    ImplementationPlan schema, that model receives one
    focused schema-repair attempt instead of immediately
    switching models.
    """

    async def request_factory(
        client: AsyncOpenAI,
        model_name: str,
    ) -> tuple[str, str]:
        content = (
            await _request_formatter_for_model(
                client=client,
                model_name=model_name,
                formatter_input=(
                    formatter_input
                ),
            )
        )

        return (
            model_name,
            content,
        )

    try:
        (
            selected_model_name,
            formatter_output,
        ) = (
            await run_async_model_call_with_fallback(
                operation_name=(
                    "implementation_plan_formatter"
                ),
                request_factory=(
                    request_factory
                ),
            )
        )

    except ModelFallbackExhaustedError as exc:
        raise PlanGenerationError(
            "Plan formatter could not run because all "
            "configured AI models are currently "
            f"rate limited: {exc}"
        ) from exc

    except PlanGenerationError:
        raise

    except Exception as exc:
        raise PlanGenerationError(
            "Plan formatter failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        return (
            _parse_implementation_plan(
                formatter_output
            )
        )

    except _PlanSchemaValidationError as exc:
        return (
            await _repair_implementation_plan_schema(
                selected_model_name=(
                    selected_model_name
                ),
                formatter_input=(
                    formatter_input
                ),
                invalid_output=(
                    formatter_output
                ),
                validation_error=exc,
            )
        )


async def create_implementation_plan(
    db: Session,
    task_id: uuid.UUID,
) -> ImplementationPlan:
    """
    Inspect a task repository and generate a validated
    implementation plan.

    Repository inspection and plan formatting both support
    automatic model fallback.

    Model fallback occurs only for genuine rate-limit or
    quota-exhaustion conditions.
    """

    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    try:
        workspace = SecureWorkspace(
            task.repository_path
        )

    except Exception as exc:
        raise PlanGenerationError(
            "Unable to initialize the secure "
            "repository workspace: "
            f"{exc}"
        ) from exc

    context = EngineeringAgentContext(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        workspace=workspace,
    )

    inspection_input = (
        "Software task title:\n"
        f"{task.title}\n\n"
        "Task description:\n"
        f"{task.description}\n\n"
        "Inspect the repository only as much as necessary "
        "to understand this software task.\n\n"
        "Identify:\n"
        "1. The main implementation related to the "
        "requested change.\n"
        "2. Directly related routes, services, models, "
        "schemas, settings, or dependencies.\n"
        "3. Existing tests related to the behavior.\n"
        "4. Any implementation constraints visible in "
        "the repository.\n\n"
        "Tool rules:\n"
        "- Use only list_directory, read_file, and "
        "search_code.\n"
        "- Never invent another tool.\n"
        "- Prefer search_code before broad directory "
        "exploration.\n"
        "- Do not repeat identical tool calls.\n"
        "- Do not inspect unrelated files.\n"
        "- Stop using tools once sufficient evidence "
        "is available.\n\n"
        "Return a concise final repository inspection "
        "report when done."
    )

    try:
        inspection_result = (
            await run_agent_with_fallback(
                operation_name=(
                    "repository_inspection"
                ),
                agent_factory=(
                    build_repository_inspector_agent
                ),
                input_data=(
                    inspection_input
                ),
                context=context,
                max_turns=(
                    settings.agent_max_turns
                ),
            )
        )

    except MaxTurnsExceeded as exc:
        raise PlanGenerationError(
            "Repository inspection exceeded the "
            "allowed number of agent turns."
        ) from exc

    except ModelFallbackExhaustedError as exc:
        raise PlanGenerationError(
            "Repository inspection could not run because "
            "all configured AI models are currently "
            f"rate limited: {exc}"
        ) from exc

    except Exception as exc:
        raise PlanGenerationError(
            "Repository inspection failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    inspection_output = (
        inspection_result.final_output
    )

    if inspection_output is None:
        raise PlanGenerationError(
            "Repository inspector did not "
            "return a result."
        )

    inspection_text = str(
        inspection_output
    ).strip()

    if not inspection_text:
        raise PlanGenerationError(
            "Repository inspector returned "
            "an empty report."
        )

    formatter_input = (
        "Software task title:\n"
        f"{task.title}\n\n"
        "Task description:\n"
        f"{task.description}\n\n"
        "Repository inspection evidence:\n"
        "--------------------------------\n"
        f"{inspection_text}\n"
        "--------------------------------\n\n"
        "Using only the information above, create "
        "the implementation plan.\n\n"
        "Return exactly one valid JSON object.\n"
        "Return no Markdown and no explanatory text.\n\n"
        "The JSON object must contain exactly these "
        "top-level keys:\n"
        '"summary"\n'
        '"relevant_files"\n'
        '"steps"\n'
        '"assumptions"\n'
        '"risks"\n'
        '"needs_clarification"\n'
        '"clarifying_questions"\n\n'
        "Each object inside steps must contain exactly:\n"
        '"order"\n'
        '"action"\n'
        '"files"\n'
        '"verification"\n\n'
        "Field types are strict:\n"
        '- "summary": string\n'
        '- "relevant_files": array of strings\n'
        '- "steps": array of objects\n'
        '- "order": integer\n'
        '- "action": string\n'
        '- "files": array of strings\n'
        '- "verification": string\n'
        '- "assumptions": array of strings\n'
        '- "risks": array of strings\n'
        '- "needs_clarification": boolean\n'
        '- "clarifying_questions": array of strings\n\n'
        "Do not add any other top-level or step-level "
        "properties.\n"
        "Use actual repository-relative paths from the "
        "inspection evidence whenever possible."
    )

    return (
        await _run_plan_formatter_with_fallback(
            formatter_input
        )
    )


__all__ = [
    "PlanGenerationError",
    "create_implementation_plan",
]