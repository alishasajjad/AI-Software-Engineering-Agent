import json
import uuid
from typing import Any

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.context import EngineeringAgentContext
from app.agent.engineer import (
    build_plan_formatter_agent,
    build_repository_inspector_agent,
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


def _extract_json_object(
    text: str,
) -> str:
    """
    Extract a JSON object from model output.

    Groq normally returns clean JSON when instructed correctly,
    but this protects the application if the model accidentally
    wraps the response in Markdown or adds surrounding text.
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

    start_index = cleaned.find("{")
    end_index = cleaned.rfind("}")

    if (
        start_index == -1
        or end_index == -1
        or end_index < start_index
    ):
        raise PlanGenerationError(
            "Plan formatter did not return a valid JSON object."
        )

    return cleaned[
        start_index : end_index + 1
    ]


def _parse_implementation_plan(
    output: Any,
) -> ImplementationPlan:
    """
    Convert the formatter output into a validated
    ImplementationPlan.

    Supported outputs:
    - ImplementationPlan
    - dict
    - JSON string
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
            return ImplementationPlan.model_validate(
                output
            )

        except ValidationError as exc:
            raise PlanGenerationError(
                "Plan formatter returned an object that does not "
                "match the implementation plan schema."
            ) from exc

    if isinstance(
        output,
        str,
    ):
        json_text = _extract_json_object(
            output
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
                "Plan formatter JSON must contain one JSON object."
            )

        try:
            return ImplementationPlan.model_validate(
                payload
            )

        except ValidationError as exc:
            raise PlanGenerationError(
                "Plan formatter returned JSON that does not match "
                "the implementation plan schema."
            ) from exc

    raise PlanGenerationError(
        "Plan formatter returned an unsupported output type: "
        f"{type(output).__name__}."
    )


async def create_implementation_plan(
    db: Session,
    task_id: uuid.UUID,
) -> ImplementationPlan:
    """
    Inspect a task repository and generate a validated
    implementation plan.
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
            "Unable to initialize the secure repository workspace: "
            f"{exc}"
        ) from exc

    context = EngineeringAgentContext(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        workspace=workspace,
    )

    inspector = (
        build_repository_inspector_agent()
    )

    inspection_input = (
        "Software task title:\n"
        f"{task.title}\n\n"
        "Task description:\n"
        f"{task.description}\n\n"
        "Inspect the repository only as much as necessary to understand "
        "this software task.\n\n"
        "Identify:\n"
        "1. The main implementation related to the requested change.\n"
        "2. Directly related routes, services, models, schemas, settings, "
        "or dependencies.\n"
        "3. Existing tests related to the behavior.\n"
        "4. Any implementation constraints visible in the repository.\n\n"
        "Tool rules:\n"
        "- Use only list_directory, read_file, and search_code.\n"
        "- Never invent another tool.\n"
        "- Prefer search_code before broad directory exploration.\n"
        "- Do not repeat identical tool calls.\n"
        "- Do not inspect unrelated files.\n"
        "- Stop using tools once sufficient evidence is available.\n\n"
        "Return a concise final repository inspection report when done."
    )

    try:
        inspection_result = await Runner.run(
            inspector,
            inspection_input,
            context=context,
            max_turns=settings.agent_max_turns,
        )

    except MaxTurnsExceeded as exc:
        raise PlanGenerationError(
            "Repository inspection exceeded the allowed number "
            "of agent turns."
        ) from exc

    except Exception as exc:
        raise PlanGenerationError(
            "Repository inspection failed: "
            f"{exc}"
        ) from exc

    inspection_output = (
        inspection_result.final_output
    )

    if inspection_output is None:
        raise PlanGenerationError(
            "Repository inspector did not return a result."
        )

    inspection_text = str(
        inspection_output
    ).strip()

    if not inspection_text:
        raise PlanGenerationError(
            "Repository inspector returned an empty report."
        )

    formatter = (
        build_plan_formatter_agent()
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
        "Using only the information above, create the implementation plan.\n\n"
        "Return exactly one valid JSON object.\n"
        "Return no Markdown and no explanatory text.\n\n"
        "The JSON object must contain exactly these top-level keys:\n"
        '\"summary\"\n'
        '\"relevant_files\"\n'
        '\"steps\"\n'
        '\"assumptions\"\n'
        '\"risks\"\n'
        '\"needs_clarification\"\n'
        '\"clarifying_questions\"\n\n'
        "Each object inside steps must contain exactly:\n"
        '\"order\"\n'
        '\"action\"\n'
        '\"files\"\n'
        '\"verification\"\n\n'
        "Use actual repository-relative paths from the inspection evidence "
        "whenever possible."
    )

    try:
        plan_result = await Runner.run(
            formatter,
            formatter_input,
            max_turns=(
                settings.agent_formatter_max_turns
            ),
        )

    except MaxTurnsExceeded as exc:
        raise PlanGenerationError(
            "Plan formatter exceeded the allowed number "
            "of agent turns."
        ) from exc

    except Exception as exc:
        raise PlanGenerationError(
            "Plan formatter failed: "
            f"{exc}"
        ) from exc

    formatter_output = (
        plan_result.final_output
    )

    if formatter_output is None:
        raise PlanGenerationError(
            "Plan formatter returned no output."
        )

    return _parse_implementation_plan(
        formatter_output
    )