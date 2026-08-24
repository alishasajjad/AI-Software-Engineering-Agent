from pathlib import Path

import pytest

from app.tools.repository import (
    BinaryFileError,
    SecureWorkspace,
    WorkspaceSecurityError,
    list_directory,
    read_file,
    search_code,
)


@pytest.fixture()
def sample_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "sample_repo"
    repository.mkdir()

    app_directory = repository / "app"
    app_directory.mkdir()

    (app_directory / "main.py").write_text(
        "def hello():\n"
        '    return "hello world"\n',
        encoding="utf-8",
    )

    tests_directory = repository / "tests"
    tests_directory.mkdir()

    (tests_directory / "test_main.py").write_text(
        "def test_hello():\n"
        '    assert "hello" == "hello"\n',
        encoding="utf-8",
    )

    git_directory = repository / ".git"
    git_directory.mkdir()

    (git_directory / "config").write_text(
        "secret git configuration",
        encoding="utf-8",
    )

    (repository / "binary.bin").write_bytes(
        b"\x00\x01\x02\x03"
    )

    return repository


def test_workspace_accepts_valid_repository(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    assert workspace.root == sample_repository.resolve()


def test_workspace_blocks_parent_traversal(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    with pytest.raises(WorkspaceSecurityError):
        workspace.resolve("../secret.txt")


def test_workspace_blocks_absolute_paths(
    sample_repository: Path,
    tmp_path: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    with pytest.raises(WorkspaceSecurityError):
        workspace.resolve(str(outside_file.resolve()))


def test_workspace_blocks_restricted_directories(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    with pytest.raises(WorkspaceSecurityError):
        workspace.resolve(".git/config")


def test_list_directory_hides_restricted_directories(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    result = list_directory(workspace)

    names = {entry.name for entry in result.entries}

    assert "app" in names
    assert "tests" in names
    assert ".git" not in names


def test_read_file_returns_source_content(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    result = read_file(
        workspace,
        "app/main.py",
    )

    assert result.path == "app/main.py"
    assert "def hello" in result.content
    assert result.total_lines == 2


def test_read_file_rejects_binary_file(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    with pytest.raises(BinaryFileError):
        read_file(
            workspace,
            "binary.bin",
        )


def test_search_code_finds_matches(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    result = search_code(
        workspace,
        "hello",
    )

    paths = {match.path for match in result.matches}

    assert "app/main.py" in paths
    assert "tests/test_main.py" in paths


def test_search_code_does_not_scan_git_directory(
    sample_repository: Path,
) -> None:
    workspace = SecureWorkspace(sample_repository)

    result = search_code(
        workspace,
        "secret git configuration",
    )

    assert result.matches == []