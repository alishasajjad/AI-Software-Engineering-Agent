import os
from pathlib import Path

from app.tools.repository.constants import (
    EXCLUDED_DIRECTORIES,
    MAX_FILE_SIZE_BYTES,
    MAX_SEARCH_LINE_CHARACTERS,
    MAX_SEARCH_RESULTS,
)
from app.tools.repository.exceptions import WorkspaceSecurityError
from app.tools.repository.models import (
    SearchCodeResult,
    SearchMatch,
)
from app.tools.repository.workspace import SecureWorkspace


def _search_file(
    workspace: SecureWorkspace,
    file_path: Path,
    query: str,
    *,
    case_sensitive: bool,
    remaining_results: int,
) -> list[SearchMatch]:
    try:
        relative_path = workspace.relative_path(file_path)
        safe_file = workspace.resolve(relative_path)
    except WorkspaceSecurityError:
        return []

    if not safe_file.is_file():
        return []

    if safe_file.stat().st_size > MAX_FILE_SIZE_BYTES:
        return []

    raw_content = safe_file.read_bytes()

    if b"\x00" in raw_content[:8192]:
        return []

    text = raw_content.decode("utf-8", errors="replace")

    search_query = query if case_sensitive else query.casefold()

    matches: list[SearchMatch] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        searchable_line = line if case_sensitive else line.casefold()

        if search_query not in searchable_line:
            continue

        matches.append(
            SearchMatch(
                path=relative_path,
                line_number=line_number,
                line=line[:MAX_SEARCH_LINE_CHARACTERS],
            )
        )

        if len(matches) >= remaining_results:
            break

    return matches


def search_code(
    workspace: SecureWorkspace,
    query: str,
    relative_path: str = ".",
    *,
    case_sensitive: bool = False,
    max_results: int = MAX_SEARCH_RESULTS,
) -> SearchCodeResult:
    if not query.strip():
        raise ValueError("Search query cannot be empty.")

    search_root = workspace.resolve(relative_path)

    matches: list[SearchMatch] = []
    files_scanned = 0
    truncated = False

    if search_root.is_file():
        matches.extend(
            _search_file(
                workspace,
                search_root,
                query,
                case_sensitive=case_sensitive,
                remaining_results=max_results,
            )
        )
        files_scanned = 1

    else:
        for root, directories, files in os.walk(search_root):
            directories[:] = [
                directory
                for directory in directories
                if directory.lower() not in EXCLUDED_DIRECTORIES
            ]

            for filename in files:
                file_path = Path(root) / filename

                remaining_results = max_results - len(matches)

                if remaining_results <= 0:
                    truncated = True
                    break

                file_matches = _search_file(
                    workspace,
                    file_path,
                    query,
                    case_sensitive=case_sensitive,
                    remaining_results=remaining_results,
                )

                files_scanned += 1
                matches.extend(file_matches)

            if len(matches) >= max_results:
                truncated = True
                break

    return SearchCodeResult(
        query=query,
        path=relative_path,
        matches=matches,
        files_scanned=files_scanned,
        truncated=truncated,
    )