from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from evaluation.api_client import (
    EvaluationApiClient,
    EvaluationRateLimitError,
)
from evaluation.models import EvaluationTaskResult
from evaluation.runner import (
    Phase10EvaluationRunner,
    compute_summary,
    write_evaluation_outputs,
)
from evaluation.suite import get_evaluation_cases

DEFAULT_RATE_LIMIT_WAIT_SECONDS = 60.0
DEFAULT_MAX_RATE_LIMIT_RETRIES = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase 10 evaluation suite "
            "for the AI Software Engineering Agent."
        )
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--cases",
        default=None,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=240.0,
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
    )

    parser.add_argument(
        "--auto-approve-eval",
        action="store_true",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
    )

    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Resume an existing evaluation run, "
            "for example 20260826_083052."
        ),
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "When resuming, rerun previously failed cases "
            "while preserving previously passed results."
        ),
    )

    parser.add_argument(
        "--wait-on-rate-limit",
        action="store_true",
        help=(
            "Wait for the provider retry window and "
            "automatically retry the interrupted case."
        ),
    )

    parser.add_argument(
        "--rate-limit-buffer",
        type=float,
        default=10.0,
        help=(
            "Extra seconds added to the provider retry window."
        ),
    )

    parser.add_argument(
        "--max-rate-limit-retries",
        type=int,
        default=DEFAULT_MAX_RATE_LIMIT_RETRIES,
        help=(
            "Maximum consecutive provider rate-limit retries "
            "for one evaluation case before the evaluation "
            "pauses safely. Default: 3."
        ),
    )

    return parser


def load_existing_results(
    result_directory: Path,
) -> dict[str, EvaluationTaskResult]:
    existing: dict[
        str,
        EvaluationTaskResult,
    ] = {}

    if not result_directory.exists():
        return existing

    for path in sorted(
        result_directory.glob(
            "task_*.json"
        )
    ):
        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            result = EvaluationTaskResult(
                **payload
            )

        except Exception as exc:
            raise RuntimeError(
                "Unable to load existing "
                f"evaluation result {path}: "
                f"{exc}"
            ) from exc

        existing[
            result.case_id
        ] = result

    return existing


def write_checkpoint(
    *,
    result: EvaluationTaskResult,
    result_directory: Path,
) -> None:
    result_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        result_directory
        / f"{result.case_id}.json"
    )

    path.write_text(
        json.dumps(
            result.to_dict(),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def print_summary(
    *,
    results: list[EvaluationTaskResult],
    summary: dict,
    report_directory: Path,
    expected_case_count: int,
) -> None:
    metrics = summary[
        "metrics"
    ]

    print(
        "\n"
        + "=" * 72
    )

    print(
        "PHASE 10 EVALUATION SUMMARY"
    )

    print(
        "=" * 72
    )

    print(
        "Tasks completed              : "
        f"{len(results)}/{expected_case_count}"
    )

    print(
        "Overall evaluation rate      : "
        f"{metrics['overall_evaluation_rate']}%"
    )

    print(
        "Task completion rate         : "
        f"{metrics['task_completion_rate']}%"
    )

    print(
        "Verification pass rate       : "
        f"{metrics['verification_pass_rate']}%"
    )

    print(
        "Correct patch rate           : "
        f"{metrics['correct_patch_rate']}%"
    )

    print(
        "Approval compliance          : "
        f"{metrics['approval_compliance_rate']}%"
    )

    print(
        "Self-correction success      : "
        f"{metrics['self_correction_success_rate']}%"
    )

    print(
        "Safe-stop compliance         : "
        f"{metrics['safe_stop_compliance_rate']}%"
    )

    print(
        "Unsafe action block rate     : "
        f"{metrics['unsafe_action_block_rate']}%"
    )

    print(
        "Disk-write safety            : "
        f"{metrics['unexpected_disk_write_safety_rate']}%"
    )

    print(
        "\nEvaluation report:"
    )

    print(
        report_directory
        / "evaluation_report.md"
    )

    print(
        "\nTechnical report:"
    )

    print(
        report_directory
        / "final_technical_report.md"
    )

    complete = (
        len(results)
        == expected_case_count
    )

    accepted = (
        complete
        and summary[
            "acceptance"
        ][
            "passed"
        ]
    )

    print(
        "\nEvaluation completeness:"
    )

    print(
        "COMPLETE"
        if complete
        else "PARTIAL"
    )

    print(
        "\nAcceptance:"
    )

    print(
        "PASS"
        if accepted
        else "FAIL"
    )

    print(
        "=" * 72
    )


def write_current_outputs(
    *,
    results_by_id: dict[
        str,
        EvaluationTaskResult,
    ],
    result_directory: Path,
    report_directory: Path,
) -> None:
    """
    Save the currently completed evaluation results.

    Rate-limited/interrupted cases are intentionally not
    written as failures.
    """

    current_results = [
        results_by_id[
            case_id
        ]
        for case_id in sorted(
            results_by_id
        )
    ]

    summary = compute_summary(
        current_results
    )

    write_evaluation_outputs(
        results=current_results,
        summary=summary,
        result_directory=(
            result_directory
        ),
        report_directory=(
            report_directory
        ),
    )


def build_resume_command(
    *,
    args: argparse.Namespace,
    run_id: str,
) -> str:
    """
    Build a resume command that preserves the important
    settings from the interrupted evaluation run.
    """

    parts = [
        "python -m evaluation.run_evaluation",
        f"--run-id {run_id}",
        f"--base-url {args.base_url}",
        "--retry-failed",
        "--auto-approve-eval",
        f"--delay {args.delay}",
        f"--timeout {args.timeout}",
    ]

    if args.cases:
        parts.append(
            f"--cases {args.cases}"
        )

    if args.limit is not None:
        parts.append(
            f"--limit {args.limit}"
        )

    if args.wait_on_rate_limit:
        parts.append(
            "--wait-on-rate-limit"
        )

        parts.append(
            "--rate-limit-buffer "
            f"{args.rate_limit_buffer}"
        )

        parts.append(
            "--max-rate-limit-retries "
            f"{args.max_rate_limit_retries}"
        )

    if args.strict:
        parts.append(
            "--strict"
        )

    return " ".join(
        parts
    )


def pause_for_rate_limit(
    *,
    case_id: str,
    consecutive_rate_limits: int,
    results_by_id: dict[
        str,
        EvaluationTaskResult,
    ],
    result_directory: Path,
    report_directory: Path,
    args: argparse.Namespace,
    run_id: str,
) -> int:
    """
    Safely pause the evaluation without recording the
    interrupted case as an agent-quality failure.
    """

    write_current_outputs(
        results_by_id=results_by_id,
        result_directory=(
            result_directory
        ),
        report_directory=(
            report_directory
        ),
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "EVALUATION PAUSED SAFELY"
    )

    print(
        "=" * 72
    )

    print(
        f"Interrupted case : {case_id}"
    )

    print(
        "Consecutive rate-limit hits : "
        f"{consecutive_rate_limits}"
    )

    print(
        "No evaluation failure was recorded "
        "for the interrupted case."
    )

    print(
        "Completed case results and reports "
        "have been preserved."
    )

    print(
        "\nResume command:"
    )

    print(
        build_resume_command(
            args=args,
            run_id=run_id,
        )
    )

    print(
        "=" * 72
    )

    return 2


def main() -> int:
    parser = build_parser()

    args = parser.parse_args()

    if not args.auto_approve_eval:
        parser.error(
            "Phase 10 requires explicit "
            "--auto-approve-eval."
        )

    if (
        args.max_rate_limit_retries
        < 0
    ):
        parser.error(
            "--max-rate-limit-retries "
            "cannot be negative."
        )

    if args.rate_limit_buffer < 0:
        parser.error(
            "--rate-limit-buffer "
            "cannot be negative."
        )

    if args.timeout <= 0:
        parser.error(
            "--timeout must be greater than 0."
        )

    if args.delay < 0:
        parser.error(
            "--delay cannot be negative."
        )

    cases = (
        get_evaluation_cases()
    )

    if args.cases:
        requested = {
            item.strip()
            for item in (
                args.cases.split(",")
            )
            if item.strip()
        }

        cases = [
            case
            for case in cases
            if case.case_id
            in requested
        ]

        missing = (
            requested
            - {
                case.case_id
                for case in cases
            }
        )

        if missing:
            parser.error(
                "Unknown evaluation case IDs: "
                f"{sorted(missing)}"
            )

    if args.limit is not None:
        if args.limit < 1:
            parser.error(
                "--limit must be at least 1."
            )

        cases = cases[
            : args.limit
        ]

    if not cases:
        parser.error(
            "No evaluation cases selected."
        )

    root = Path(
        __file__
    ).resolve().parent

    run_id = (
        args.run_id
        if args.run_id
        else datetime.now(
            UTC
        ).strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    workspace_root = (
        root
        / "workspaces"
        / run_id
    )

    result_directory = (
        root
        / "results"
        / run_id
    )

    report_directory = (
        root
        / "reports"
        / run_id
    )

    workspace_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing = (
        load_existing_results(
            result_directory
        )
    )

    api = EvaluationApiClient(
        base_url=args.base_url,
        timeout_seconds=args.timeout,
    )

    runner = Phase10EvaluationRunner(
        api=api,
        workspace_root=(
            workspace_root
        ),
        auto_approve_eval=(
            args.auto_approve_eval
        ),
        delay_seconds=(
            args.delay
        ),
    )

    selected_case_ids = {
        case.case_id
        for case in cases
    }

    results_by_id = {
        case_id: result
        for (
            case_id,
            result,
        ) in existing.items()
        if case_id
        in selected_case_ids
    }

    print(
        "=" * 72
    )

    print(
        "AI SOFTWARE ENGINEERING AGENT "
        "PHASE 10 EVALUATION"
    )

    print(
        "=" * 72
    )

    print(
        f"Cases selected : {len(cases)}"
    )

    print(
        f"API            : {args.base_url}"
    )

    print(
        f"Run ID         : {run_id}"
    )

    print(
        f"Existing       : {len(results_by_id)}"
    )

    print(
        "Rate-limit retries per case : "
        f"{args.max_rate_limit_retries}"
    )

    print(
        "=" * 72
    )

    for index, case in enumerate(
        cases,
        start=1,
    ):
        existing_result = (
            results_by_id.get(
                case.case_id
            )
        )

        if existing_result is not None:
            should_retry = (
                args.retry_failed
                and not (
                    existing_result.passed
                )
            )

            if not should_retry:
                print(
                    f"\nCase {index}/{len(cases)}"
                )

                print(
                    f"[{case.case_id}] "
                    "SKIP — checkpoint already "
                    f"{'PASS' if existing_result.passed else 'FAIL'}"
                )

                continue

        consecutive_rate_limits = 0

        while True:
            print(
                f"\nCase {index}/{len(cases)}"
            )

            try:
                result = runner.run_case(
                    case
                )

            except EvaluationRateLimitError as exc:
                consecutive_rate_limits += 1

                retry_seconds = (
                    exc.retry_after_seconds
                )

                print(
                    "\n"
                    + "!" * 72
                )

                print(
                    "MODEL PROVIDER RATE LIMIT"
                )

                print(
                    "!" * 72
                )

                print(
                    f"Interrupted case : {case.case_id}"
                )

                print(
                    "Consecutive hits : "
                    f"{consecutive_rate_limits}/"
                    f"{args.max_rate_limit_retries}"
                )

                if retry_seconds is not None:
                    print(
                        "Provider retry   : "
                        f"{retry_seconds:.1f}s"
                    )

                if not args.wait_on_rate_limit:
                    return pause_for_rate_limit(
                        case_id=(
                            case.case_id
                        ),
                        consecutive_rate_limits=(
                            consecutive_rate_limits
                        ),
                        results_by_id=(
                            results_by_id
                        ),
                        result_directory=(
                            result_directory
                        ),
                        report_directory=(
                            report_directory
                        ),
                        args=args,
                        run_id=run_id,
                    )

                if (
                    consecutive_rate_limits
                    > args.max_rate_limit_retries
                ):
                    print(
                        "\nMaximum automatic "
                        "rate-limit retries reached."
                    )

                    return pause_for_rate_limit(
                        case_id=(
                            case.case_id
                        ),
                        consecutive_rate_limits=(
                            consecutive_rate_limits
                        ),
                        results_by_id=(
                            results_by_id
                        ),
                        result_directory=(
                            result_directory
                        ),
                        report_directory=(
                            report_directory
                        ),
                        args=args,
                        run_id=run_id,
                    )

                wait_seconds = (
                    (
                        retry_seconds
                        if retry_seconds
                        is not None
                        else (
                            DEFAULT_RATE_LIMIT_WAIT_SECONDS
                        )
                    )
                    + max(
                        args.rate_limit_buffer,
                        0.0,
                    )
                )

                print(
                    "Waiting          : "
                    f"{wait_seconds:.1f}s"
                )

                print(
                    "The interrupted case "
                    "will restart from a clean "
                    "evaluation workspace."
                )

                time.sleep(
                    wait_seconds
                )

                continue

            results_by_id[
                case.case_id
            ] = result

            write_checkpoint(
                result=result,
                result_directory=(
                    result_directory
                ),
            )

            status = (
                "PASS"
                if result.passed
                else "FAIL"
            )

            print(
                f"[{case.case_id}] "
                f"{status} "
                f"({result.duration_seconds:.2f}s)"
            )

            if result.errors:
                for error in (
                    result.errors
                ):
                    print(
                        f"  ERROR: {error}"
                    )

            break

    ordered_results = [
        results_by_id[
            case.case_id
        ]
        for case in cases
        if case.case_id
        in results_by_id
    ]

    summary = compute_summary(
        ordered_results
    )

    write_evaluation_outputs(
        results=ordered_results,
        summary=summary,
        result_directory=(
            result_directory
        ),
        report_directory=(
            report_directory
        ),
    )

    print_summary(
        results=ordered_results,
        summary=summary,
        report_directory=(
            report_directory
        ),
        expected_case_count=(
            len(cases)
        ),
    )

    complete = (
        len(ordered_results)
        == len(cases)
    )

    accepted = (
        complete
        and summary[
            "acceptance"
        ][
            "passed"
        ]
    )

    if (
        args.strict
        and not accepted
    ):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )