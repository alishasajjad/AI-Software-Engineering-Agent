from app.tools.repository.constants import (
    MAX_FILE_SIZE_BYTES,
    MAX_READ_CHARACTERS,
)
from app.tools.repository.exceptions import (
    BinaryFileError,
    FileTooLargeError,
    InvalidRepositoryPathError,
)
from app.tools.repository.models import ReadFileResult
from app.tools.repository.workspace import SecureWorkspace


def read_file(
    workspace: SecureWorkspace,
    relative_path: str,
    *,
    start_line: int = 1,
    end_line: int | None = None,
    max_characters: int = MAX_READ_CHARACTERS,
) -> ReadFileResult:
    file_path = workspace.resolve(relative_path)

    if not file_path.is_file():
        raise InvalidRepositoryPathError(
            f"Path is not a file: {relative_path}"
        )

    file_size = file_path.stat().st_size

    if file_size > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(
            f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES} bytes."
        )

    raw_content = file_path.read_bytes()

    if b"\x00" in raw_content[:8192]:
        raise BinaryFileError(
            f"Binary files cannot be read as source text: {relative_path}"
        )

    text = raw_content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    total_lines = len(lines)

    if start_line < 1:
        raise ValueError("start_line must be greater than or equal to 1.")

    if end_line is not None and end_line < start_line:
        raise ValueError("end_line cannot be smaller than start_line.")

    requested_end = end_line or total_lines

    selected_lines = lines[start_line - 1 : requested_end]

    content = "\n".join(selected_lines)

    truncated = False

    if len(content) > max_characters:
        content = content[:max_characters]
        truncated = True

    actual_end_line = min(
        requested_end,
        total_lines,
    )

    return ReadFileResult(
        path=workspace.relative_path(file_path),
        content=content,
        size_bytes=file_size,
        total_lines=total_lines,
        start_line=start_line,
        end_line=actual_end_line,
        truncated=truncated,
    )