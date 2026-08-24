from app.tools.repository.exceptions import (
    InvalidRepositoryPathError,
    WorkspaceSecurityError,
)
from app.tools.repository.models import (
    DirectoryEntry,
    ListDirectoryResult,
)
from app.tools.repository.workspace import SecureWorkspace


def list_directory(
    workspace: SecureWorkspace,
    relative_path: str = ".",
) -> ListDirectoryResult:
    directory = workspace.resolve(relative_path)

    if not directory.is_dir():
        raise InvalidRepositoryPathError(
            f"Path is not a directory: {relative_path}"
        )

    entries: list[DirectoryEntry] = []

    for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        child_relative_path = workspace.relative_path(child)

        try:
            safe_child = workspace.resolve(child_relative_path)
        except WorkspaceSecurityError:
            continue

        if safe_child.is_dir():
            entries.append(
                DirectoryEntry(
                    name=safe_child.name,
                    path=workspace.relative_path(safe_child),
                    entry_type="directory",
                )
            )
            continue

        if safe_child.is_file():
            entries.append(
                DirectoryEntry(
                    name=safe_child.name,
                    path=workspace.relative_path(safe_child),
                    entry_type="file",
                    size_bytes=safe_child.stat().st_size,
                )
            )

    return ListDirectoryResult(
        path=workspace.relative_path(directory)
        if directory != workspace.root
        else ".",
        entries=entries,
    )