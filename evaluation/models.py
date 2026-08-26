from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ExpectedOutcome = Literal[
    "pass",
    "safe_stop",
]


@dataclass(
    frozen=True,
    slots=True,
)
class FaultInjection:
    """
    A deterministic test failure inserted only inside an
    isolated evaluation workspace.

    It is used to exercise the self-correction lifecycle.
    """

    path: str

    old_text: str

    new_text: str

    allowed_correction_files: tuple[
        str,
        ...,
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class EvaluationCase:
    """
    Definition of one evaluation scenario.
    """

    case_id: str

    title: str

    description: str

    expected_outcome: ExpectedOutcome

    files: dict[
        str,
        str,
    ]

    binary_files: dict[
        str,
        bytes,
    ] = field(
        default_factory=dict
    )

    allowed_patch_files: tuple[
        str,
        ...,
    ] = ()

    required_changed_files: tuple[
        str,
        ...,
    ] = ()

    expected_fragments: dict[
        str,
        tuple[
            str,
            ...,
        ],
    ] = field(
        default_factory=dict
    )

    fault_injection: (
        FaultInjection | None
    ) = None


@dataclass
class EvaluationTaskResult:
    """
    Persisted evaluation result for one case.
    """

    case_id: str

    title: str

    expected_outcome: str

    repository_path: str

    task_id: str | None = None

    started_at: str | None = None

    completed_at: str | None = None

    duration_seconds: float = 0.0

    plan_succeeded: bool = False

    patch_prepare_succeeded: bool = False

    patch_count: int = 0

    patch_paths: list[str] = field(
        default_factory=list
    )

    patch_policy_compliant: bool = False

    proposed_content_compliant: bool = False

    disk_unchanged_before_approval: bool = False

    disk_unchanged_after_approval: bool = False

    apply_succeeded: bool = False

    changed_files: list[str] = field(
        default_factory=list
    )

    final_content_accurate: bool = False

    initial_verification_status: (
        str | None
    ) = None

    final_verification_status: (
        str | None
    ) = None

    verification_passed: bool = False

    self_correction_exercised: bool = False

    self_correction_completed: bool = False

    correction_attempts: int = 0

    correction_policy_compliant: bool = True

    safe_stop_observed: bool = False

    unsafe_change_detected: bool = False

    passed: bool = False

    errors: list[str] = field(
        default_factory=list
    )

    notes: list[str] = field(
        default_factory=list
    )

    raw_plan: dict[
        str,
        Any,
    ] | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)