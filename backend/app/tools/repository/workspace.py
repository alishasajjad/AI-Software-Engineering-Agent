from pathlib import Path

from app.tools.repository.constants import EXCLUDED_DIRECTORIES
from app.tools.repository.exceptions import (
    RepositoryNotFoundError,
    RepositoryPathNotFoundError,
    WorkspaceSecurityError,
)


class SecureWorkspace:
    def __init__(self, repository_path: str | Path) -> None:
        root = Path(repository_path).expanduser().resolve()

        if not root.exists():
            raise RepositoryNotFoundError(
                f"Repository does not exist: {root}"
            )

        if not root.is_dir():
            raise RepositoryNotFoundError(
                f"Repository path is not a directory: {root}"
            )

        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def resolve(
        self,
        relative_path: str = ".",
        *,
        must_exist: bool = True,
    ) -> Path:
        requested_path = Path(relative_path)

        if requested_path.is_absolute():
            raise WorkspaceSecurityError(
                "Absolute paths are not allowed inside repository tools."
            )

        if ".." in requested_path.parts:
            raise WorkspaceSecurityError(
                "Parent directory traversal is not allowed."
            )

        candidate = (self._root / requested_path).resolve(strict=False)

        if not candidate.is_relative_to(self._root):
            raise WorkspaceSecurityError(
                "Requested path escapes the assigned repository."
            )

        relative_candidate = candidate.relative_to(self._root)

        if any(
            part.lower() in EXCLUDED_DIRECTORIES
            for part in relative_candidate.parts
        ):
            raise WorkspaceSecurityError(
                "Requested path is inside a restricted directory."
            )

        if must_exist and not candidate.exists():
            raise RepositoryPathNotFoundError(
                f"Repository path does not exist: {relative_path}"
            )

        return candidate

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()