from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from app.schemas.patch import PatchPreview
from app.tools.repository import (
    SecureWorkspace,
)
from app.tools.repository import (
    read_file as repository_read_file,
)


class PatchError(RuntimeError):
    """Base error for safe patch operations."""


class PatchTargetNotFoundError(PatchError):
    """Raised when requested target text cannot be found."""


class AmbiguousPatchError(PatchError):
    """Raised when requested text exists more than once."""


class NoChangeError(PatchError):
    """Raised when the proposed replacement changes nothing."""


class TruncatedFileError(PatchError):
    """Raised when the complete source file could not be read."""


class StalePatchError(PatchError):
    """
    Raised when the file changed after the patch was prepared.
    """


class PatchWriteError(PatchError):
    """Raised when an approved patch cannot be written safely."""


def calculate_sha256(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


class SafePatchEngine:
    """
    Prepare and safely apply repository patches.

    Preparing a patch never writes to disk.

    Applying a patch requires the expected SHA-256 hash of the
    original content to match the repository's current content.
    """

    def __init__(
        self,
        workspace: SecureWorkspace,
    ) -> None:
        self.workspace = workspace

    def prepare_replacement(
        self,
        *,
        path: str,
        old_text: str,
        new_text: str,
    ) -> PatchPreview:
        if not old_text:
            raise PatchError(
                "old_text cannot be empty."
            )

        read_result = repository_read_file(
            self.workspace,
            path,
        )

        if read_result.truncated:
            raise TruncatedFileError(
                
                    f"'{path}' was truncated while reading. "
                    "A patch cannot safely be prepared "
                    "without the complete file."
                
            )

        original_content = read_result.content

        match_count = original_content.count(
            old_text
        )

        if match_count == 0:
            raise PatchTargetNotFoundError(
                f"Target text was not found in '{path}'."
            )

        if match_count > 1:
            raise AmbiguousPatchError(
                
                    f"Target text appears {match_count} times "
                    f"in '{path}'. A more specific old_text "
                    "is required."
                
            )

        proposed_content = original_content.replace(
            old_text,
            new_text,
            1,
        )

        if proposed_content == original_content:
            raise NoChangeError(
                f"The proposed edit does not change '{path}'."
            )

        diff = self._build_diff(
            path=path,
            original_content=original_content,
            proposed_content=proposed_content,
        )

        return PatchPreview(
            path=path,
            original_content=original_content,
            proposed_content=proposed_content,
            diff=diff,
            changed=True,
        )

    def apply_prepared_patch(
        self,
        *,
        path: str,
        proposed_content: str,
        expected_original_sha256: str,
    ) -> str:
        """
        Safely write a previously prepared patch.

        The file is written only when its current SHA-256 matches
        the hash captured when the patch was originally prepared.

        Returns the SHA-256 of the newly written content.
        """

        read_result = repository_read_file(
            self.workspace,
            path,
        )

        if read_result.truncated:
            raise TruncatedFileError(
                
                    f"'{path}' was truncated while reading. "
                    "The patch cannot be safely applied."
                
            )

        current_content = read_result.content

        current_sha256 = calculate_sha256(
            current_content
        )

        if (
            current_sha256
            != expected_original_sha256
        ):
            raise StalePatchError(
                
                    f"'{path}' changed after this patch was "
                    "prepared. The patch is now stale."
                
            )

        target_path = self.workspace.resolve(
            path
        )

        self._atomic_write(
            target_path=target_path,
            content=proposed_content,
        )

        return calculate_sha256(
            proposed_content
        )

    @staticmethod
    def _atomic_write(
        *,
        target_path: Path,
        content: str,
    ) -> None:
        """
        Atomically replace a text file while preserving its
        existing newline style and file permissions when possible.
        """

        try:
            raw_original = target_path.read_bytes()

        except OSError as exc:
            raise PatchWriteError(
                
                    "Unable to inspect the target file before "
                    f"writing: {exc}"
                
            ) from exc

        newline = (
            "\r\n"
            if b"\r\n" in raw_original
            else "\n"
        )

        normalized_content = (
            content.replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

        if newline == "\r\n":
            write_content = (
                normalized_content.replace(
                    "\n",
                    "\r\n",
                )
            )
        else:
            write_content = normalized_content

        temp_path: str | None = None

        try:
            file_descriptor, temp_path = (
                tempfile.mkstemp(
                    prefix=(
                        f".{target_path.name}."
                    ),
                    suffix=".patch.tmp",
                    dir=str(
                        target_path.parent
                    ),
                )
            )

            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
                newline="",
            ) as temp_file:
                temp_file.write(
                    write_content
                )
                temp_file.flush()

                os.fsync(
                    temp_file.fileno()
                )

            try:
                shutil.copymode(
                    target_path,
                    temp_path,
                )
            except OSError:
                pass

            os.replace(
                temp_path,
                target_path,
            )

            temp_path = None

        except OSError as exc:
            raise PatchWriteError(
                
                    f"Unable to safely write "
                    f"'{target_path.name}': {exc}"
                
            ) from exc

        finally:
            if (
                temp_path is not None
                and os.path.exists(
                    temp_path
                )
            ):
                try:
                    os.unlink(
                        temp_path
                    )
                except OSError:
                    pass

    @staticmethod
    def _build_diff(
        *,
        path: str,
        original_content: str,
        proposed_content: str,
    ) -> str:
        original_lines = (
            original_content.splitlines()
        )

        proposed_lines = (
            proposed_content.splitlines()
        )

        diff_lines = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )

        return "\n".join(
            diff_lines
        )