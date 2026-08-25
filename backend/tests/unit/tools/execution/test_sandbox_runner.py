from pathlib import Path

import pytest

from app.tools.execution import (
    RestrictedSandboxRunner,
    SandboxPolicyError,
)
from app.tools.repository import SecureWorkspace


def build_runner(
    repository: Path,
    *,
    timeout_seconds: float = 10.0,
) -> RestrictedSandboxRunner:
    return RestrictedSandboxRunner(
        SecureWorkspace(
            repository
        ),
        timeout_seconds=timeout_seconds,
    )


def test_sandbox_pytest_success(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_sample.py"
    ).write_text(
        (
            "def test_addition():\n"
            "    assert 1 + 1 == 2\n"
        ),
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        result = session.run_pytest()

    assert result.succeeded is True
    assert result.exit_code == 0
    assert result.timed_out is False


def test_sandbox_captures_test_failure(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_failure.py"
    ).write_text(
        (
            "def test_failure():\n"
            "    assert 1 == 2\n"
        ),
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        result = session.run_pytest()

    assert result.succeeded is False

    assert result.exit_code != 0

    combined_output = (
        result.stdout
        + result.stderr
    )

    assert "test_failure" in combined_output


def test_sandbox_does_not_modify_real_repository(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_write.py"
    ).write_text(
        (
            "from pathlib import Path\n\n"
            "def test_write():\n"
            "    Path('generated.txt').write_text(\n"
            "        'sandbox only',\n"
            "        encoding='utf-8',\n"
            "    )\n"
            "    assert True\n"
        ),
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        result = session.run_pytest()

        sandbox_root = (
            session.sandbox_root
        )

        assert sandbox_root is not None

        assert (
            sandbox_root
            / "generated.txt"
        ).exists()

    assert result.succeeded is True

    assert not (
        tmp_path
        / "generated.txt"
    ).exists()


def test_sandbox_blocks_parent_traversal_target(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_sample.py"
    ).write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        with pytest.raises(
            SandboxPolicyError
        ):
            session.run_pytest(
                [
                    "../test_sample.py",
                ]
            )


def test_sandbox_blocks_absolute_target(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_sample.py"
    ).write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        with pytest.raises(
            SandboxPolicyError
        ):
            session.run_pytest(
                [
                    "C:/outside/test_sample.py",
                ]
            )


def test_sandbox_blocks_pytest_options(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_sample.py"
    ).write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path
    )

    with runner.open_session() as session:
        with pytest.raises(
            SandboxPolicyError
        ):
            session.run_pytest(
                [
                    "--collect-only",
                ]
            )


def test_sandbox_timeout(
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "test_slow.py"
    ).write_text(
        (
            "import time\n\n"
            "def test_slow():\n"
            "    time.sleep(5)\n"
            "    assert True\n"
        ),
        encoding="utf-8",
    )

    runner = build_runner(
        tmp_path,
        timeout_seconds=1.0,
    )

    with runner.open_session() as session:
        result = session.run_pytest()

    assert result.succeeded is False
    assert result.timed_out is True
    assert result.exit_code is None