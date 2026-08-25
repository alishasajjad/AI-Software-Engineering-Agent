from pathlib import Path

import pytest

from app.tools.patch import (
    SafePatchEngine,
    StalePatchError,
    calculate_sha256,
)
from app.tools.repository import (
    SecureWorkspace,
)
from app.tools.repository import (
    read_file as repository_read_file,
)


def build_engine(
    tmp_path: Path,
) -> SafePatchEngine:
    return SafePatchEngine(
        SecureWorkspace(
            tmp_path
        )
    )


def get_repository_hash(
    engine: SafePatchEngine,
    path: str,
) -> str:
    """
    Calculate the hash using the same normalized repository
    content that the production patch engine uses.

    This is important because the repository reader is the
    canonical source for patch snapshot comparison.
    """

    read_result = repository_read_file(
        engine.workspace,
        path,
    )

    assert read_result.truncated is False

    return calculate_sha256(
        read_result.content
    )


def test_apply_prepared_patch_writes_content(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    original = (
        "value = 1\n"
    )

    proposed = (
        "value = 2\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path
    )

    expected_original_hash = (
        get_repository_hash(
            engine,
            "main.py",
        )
    )

    new_hash = (
        engine.apply_prepared_patch(
            path="main.py",
            proposed_content=proposed,
            expected_original_sha256=(
                expected_original_hash
            ),
        )
    )

    assert (
        file_path.read_text(
            encoding="utf-8"
        )
        == proposed
    )

    assert new_hash == calculate_sha256(
        proposed
    )


def test_apply_prepared_patch_rejects_stale_file(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    original = (
        "value = 1\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path
    )

    expected_hash = (
        get_repository_hash(
            engine,
            "main.py",
        )
    )

    file_path.write_text(
        "value = 99\n",
        encoding="utf-8",
    )

    with pytest.raises(
        StalePatchError
    ):
        engine.apply_prepared_patch(
            path="main.py",
            proposed_content=(
                "value = 2\n"
            ),
            expected_original_sha256=(
                expected_hash
            ),
        )

    assert (
        file_path.read_text(
            encoding="utf-8"
        )
        == "value = 99\n"
    )


def test_apply_does_not_accept_wrong_hash(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    file_path.write_text(
        "hello = True\n",
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path
    )

    with pytest.raises(
        StalePatchError
    ):
        engine.apply_prepared_patch(
            path="main.py",
            proposed_content=(
                "hello = False\n"
            ),
            expected_original_sha256=(
                "0" * 64
            ),
        )

    assert (
        file_path.read_text(
            encoding="utf-8"
        )
        == "hello = True\n"
    )


def test_applied_content_hash_is_correct(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "config.py"

    original = (
        "DEBUG = True\n"
    )

    proposed = (
        "DEBUG = False\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path
    )

    expected_original_hash = (
        get_repository_hash(
            engine,
            "config.py",
        )
    )

    result_hash = (
        engine.apply_prepared_patch(
            path="config.py",
            proposed_content=proposed,
            expected_original_sha256=(
                expected_original_hash
            ),
        )
    )

    assert result_hash == calculate_sha256(
        proposed
    )

    assert (
        file_path.read_text(
            encoding="utf-8"
        )
        == proposed
    )