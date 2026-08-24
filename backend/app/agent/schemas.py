from pydantic import BaseModel, ConfigDict


class PlanStep(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    order: int
    action: str
    files: list[str]
    verification: str


class ImplementationPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str
    relevant_files: list[str]
    steps: list[PlanStep]
    assumptions: list[str]
    risks: list[str]
    needs_clarification: bool
    clarifying_questions: list[str]