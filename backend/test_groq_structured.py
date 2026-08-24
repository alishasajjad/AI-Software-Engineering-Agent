import asyncio
import json

from openai import AsyncOpenAI

from app.agent.schemas import ImplementationPlan
from app.core.config import settings


async def main() -> None:
    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
    )

    schema = ImplementationPlan.model_json_schema()

    response = await client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a software engineering planner. "
                    "Return an implementation plan matching the supplied schema."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Create a small implementation plan for adding "
                    "an application version field to a FastAPI health endpoint."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "implementation_plan",
                "strict": True,
                "schema": schema,
            },
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("Groq returned empty content.")

    print("RAW RESPONSE:")
    print(content)

    data = json.loads(content)
    plan = ImplementationPlan.model_validate(data)

    print("\nVALIDATED:")
    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())