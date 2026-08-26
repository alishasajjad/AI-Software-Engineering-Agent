from __future__ import annotations

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
)

from app.agent.context import EngineeringAgentContext
from app.agent.provider import get_groq_model
from app.agent.tools import (
    list_directory,
    read_file,
    search_code,
)


def build_repository_inspector_agent(
    model: OpenAIChatCompletionsModel | None = None,
) -> Agent[EngineeringAgentContext]:
    """
    Build the repository inspection agent.

    A specific model may be injected by the central model router.

    If no model is supplied, the configured primary Groq model
    is used. This preserves the existing application behavior.
    """

    selected_model = (
        model
        if model is not None
        else get_groq_model()
    )

    return Agent[EngineeringAgentContext](
        name="Repository Inspector",
        instructions=(
            "You are a software repository inspection agent.\n\n"
            "Your responsibility is to inspect only the repository files "
            "required to understand the requested software task.\n\n"
            "You have exactly these repository tools available:\n"
            "- list_directory\n"
            "- read_file\n"
            "- search_code\n\n"
            "Important rules:\n"
            "1. Use only the tools listed above.\n"
            "2. Never invent tool names.\n"
            "3. Never call repo_browser, print_tree, shell, terminal, grep, "
            "glob, filesystem, or any tool that is not provided.\n"
            "4. Prefer search_code when looking for a function, class, route, "
            "configuration value, test, or keyword.\n"
            "5. Use list_directory only when repository structure is "
            "necessary.\n"
            "6. Read only files directly relevant to the task.\n"
            "7. Do not repeat an identical tool call.\n"
            "8. Do not explore unrelated directories.\n"
            "9. Stop using tools once sufficient evidence has been "
            "collected.\n"
            "10. Do not attempt to edit or modify repository files.\n"
            "11. Return a concise plain-text inspection report.\n"
            "12. Mention the actual repository-relative file paths "
            "discovered.\n"
            "13. Explain what each relevant file currently does.\n"
            "14. Mention relevant tests when they exist.\n"
            "15. Do not invent files or implementation details that were "
            "not observed in the repository.\n\n"
            "Your final report should contain:\n"
            "- relevant implementation files\n"
            "- relevant tests\n"
            "- important observed behavior\n"
            "- dependencies/configuration relevant to the task\n"
            "- any uncertainty that remains\n"
        ),
        model=selected_model,
        tools=[
            list_directory,
            read_file,
            search_code,
        ],
    )


def build_plan_formatter_agent(
    model: OpenAIChatCompletionsModel | None = None,
) -> Agent:
    """
    Build the implementation-plan formatter agent.

    A specific model may be injected by the central model router.

    If no model is supplied, the configured primary Groq model
    is used.

    We intentionally do not use output_type=ImplementationPlan
    here because provider-level structured-output behavior can
    differ between Groq-hosted models.

    The service layer remains responsible for JSON extraction,
    parsing and Pydantic validation.
    """

    selected_model = (
        model
        if model is not None
        else get_groq_model()
    )

    return Agent(
        name="Implementation Plan Formatter",
        instructions=(
            "You are an implementation-plan formatter.\n\n"
            "You will receive:\n"
            "- a software task title\n"
            "- a software task description\n"
            "- repository inspection evidence\n\n"
            "Convert the supplied repository evidence into exactly one "
            "valid JSON object representing an implementation plan.\n\n"
            "STRICT OUTPUT RULES:\n"
            "1. Return JSON only.\n"
            "2. Do not return Markdown.\n"
            "3. Do not use ```json code fences.\n"
            "4. Do not include commentary before the JSON.\n"
            "5. Do not include commentary after the JSON.\n"
            "6. The response must start with { and end with }.\n"
            "7. Every required property must be present.\n"
            "8. Do not add properties that are not part of the schema.\n"
            "9. Arrays must always be JSON arrays.\n"
            "10. needs_clarification must be true or false, not a string.\n"
            "11. order must be an integer.\n"
            "12. Use repository-relative paths only.\n"
            "13. Prefer files actually discovered by repository "
            "inspection.\n"
            "14. Do not invent files unless creating a new file is "
            "genuinely required by the task.\n"
            "15. Steps must be concrete, ordered, and verifiable.\n\n"
            "You must return exactly this JSON structure:\n\n"
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
            "}\n\n"
            "If no assumptions exist, use an empty array.\n"
            "If no risks exist, use an empty array.\n"
            "If clarification is not required, set needs_clarification "
            "to false and clarifying_questions to [].\n"
        ),
        model=selected_model,
        tools=[],
    )


__all__ = [
    "build_plan_formatter_agent",
    "build_repository_inspector_agent",
]