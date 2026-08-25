from pathlib import Path

import pytest

from app.tools.patch import (
    AmbiguousPatchError,
    PatchTargetNotFoundError,
    SafePatchEngine,
)
from app.tools.repository import SecureWorkspace


def build_engine(
    tmp_path: Path,
) -> SafePatchEngine:
    workspace = SecureWorkspace(
        tmp_path,
    )

    return SafePatchEngine(
        workspace,
    )


def test_prepare_replacement_generates_diff(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    file_path.write_text(
        (
            "def hello():\n"
            "    return 'hello'\n"
        ),
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path,
    )

    patch = engine.prepare_replacement(
        path="main.py",
        old_text="return 'hello'",
        new_text="return 'hello world'",
    )

    assert patch.changed is True

    assert (
        "return 'hello world'"
        in patch.proposed_content
    )

    assert (
        "-    return 'hello'"
        in patch.diff
    )

    assert (
        "+    return 'hello world'"
        in patch.diff
    )


def test_prepare_replacement_does_not_modify_file(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.py"

    original = (
        "def hello():\n"
        "    return 'hello'\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path,
    )

    engine.prepare_replacement(
        path="main.py",
        old_text="return 'hello'",
        new_text="return 'changed'",
    )

    assert file_path.read_text(
        encoding="utf-8",
    ) == original


def test_prepare_replacement_rejects_missing_text(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path,
    )

    with pytest.raises(
        PatchTargetNotFoundError,
    ):
        engine.prepare_replacement(
            path="main.py",
            old_text="does_not_exist",
            new_text="replacement",
        )


def test_prepare_replacement_rejects_ambiguous_text(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        (
            "print('hello')\n"
            "print('hello')\n"
        ),
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path,
    )

    with pytest.raises(
        AmbiguousPatchError,
    ):
        engine.prepare_replacement(
            path="main.py",
            old_text="print('hello')",
            new_text="print('changed')",
        )


def test_patch_diff_contains_file_paths(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    engine = build_engine(
        tmp_path,
    )

    patch = engine.prepare_replacement(
        path="main.py",
        old_text="value = 1",
        new_text="value = 2",
    )

    assert "--- a/main.py" in patch.diff
    assert "+++ b/main.py" in patch.diff