from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import TracebackType
from typing import Self

from app.schemas.execution import (
    CommandExecutionResult,
    VerificationCommand,
)
from app.tools.repository import SecureWorkspace

IGNORED_SANDBOX_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
}

IGNORED_SANDBOX_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}

SAFE_ENVIRONMENT_KEYS = {
    "SYSTEMROOT",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
}

ENVIRONMENT_NAME_PATTERN = re.compile(
    r"^[A-Z_][A-Z0-9_]*$"
)


class SandboxExecutionError(RuntimeError):
    """Base error for restricted command execution."""


class SandboxPolicyError(SandboxExecutionError):
    """Raised when a command violates sandbox policy."""


def _sandbox_ignore(
    directory: str,
    names: list[str],
) -> set[str]:
    del directory

    ignored: set[str] = set()

    for name in names:
        if (
            name in IGNORED_SANDBOX_DIRECTORIES
            or name in IGNORED_SANDBOX_FILES
        ):
            ignored.add(name)

    return ignored


def _safe_output(
    value: str | bytes | None,
) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


class SandboxSession:
    """
    Disposable repository execution session.

    The real repository is copied into a temporary directory.
    Verification commands execute only against that copy.

    The temporary repository is removed when the session ends.
    """

    def __init__(
        self,
        *,
        source_root: Path,
        timeout_seconds: float,
        max_output_characters: int,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.source_root = source_root.resolve()

        self.timeout_seconds = timeout_seconds

        self.max_output_characters = (
            max_output_characters
        )

        self.extra_environment = (
            environment or {}
        )

        self._temporary_directory: (
            tempfile.TemporaryDirectory[str]
            | None
        ) = None

        self.sandbox_root: Path | None = None

    def __enter__(self) -> Self:
        self._temporary_directory = (
            tempfile.TemporaryDirectory(
                prefix="ai-agent-sandbox-"
            )
        )

        temporary_root = Path(
            self._temporary_directory.name
        )

        sandbox_root = (
            temporary_root
            / "repository"
        )

        shutil.copytree(
            self.source_root,
            sandbox_root,
            ignore=_sandbox_ignore,
        )

        self.sandbox_root = (
            sandbox_root.resolve()
        )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type
        del exc_value
        del traceback

        self.sandbox_root = None

        if (
            self._temporary_directory
            is not None
        ):
            self._temporary_directory.cleanup()

            self._temporary_directory = None

    def run_pytest(
        self,
        targets: list[str] | None = None,
    ) -> CommandExecutionResult:
        safe_targets = self._validate_pytest_targets(
            targets or []
        )

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *safe_targets,
        ]

        return self._execute(
            command_type=VerificationCommand.PYTEST,
            command=command,
        )

    def run_ruff(
        self,
    ) -> CommandExecutionResult:
        command = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            ".",
        ]

        return self._execute(
            command_type=VerificationCommand.RUFF,
            command=command,
        )

    def run_compileall(
        self,
    ) -> CommandExecutionResult:
        command = [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            ".",
        ]

        return self._execute(
            command_type=(
                VerificationCommand.COMPILEALL
            ),
            command=command,
        )

    def _execute(
        self,
        *,
        command_type: VerificationCommand,
        command: list[str],
    ) -> CommandExecutionResult:
        sandbox_root = self._require_root()

        environment = (
            self._build_environment()
        )

        started_at = time.monotonic()

        try:
            completed_process = subprocess.run(
                command,
                cwd=sandbox_root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )

        except subprocess.TimeoutExpired as exc:
            duration = (
                time.monotonic()
                - started_at
            )

            stdout = self._truncate_output(
                _safe_output(
                    exc.stdout
                )
            )

            stderr = self._truncate_output(
                _safe_output(
                    exc.stderr
                )
            )

            return CommandExecutionResult(
                command_type=command_type,
                command=self._display_command(
                    command
                ),
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_seconds=round(
                    duration,
                    3,
                ),
                succeeded=False,
            )

        except OSError as exc:
            raise SandboxExecutionError(
                
                    "Unable to start restricted "
                    f"verification command: {exc}"
                
            ) from exc

        duration = (
            time.monotonic()
            - started_at
        )

        stdout = self._truncate_output(
            completed_process.stdout
        )

        stderr = self._truncate_output(
            completed_process.stderr
        )

        return CommandExecutionResult(
            command_type=command_type,
            command=self._display_command(
                command
            ),
            exit_code=(
                completed_process.returncode
            ),
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            duration_seconds=round(
                duration,
                3,
            ),
            succeeded=(
                completed_process.returncode
                == 0
            ),
        )

    def _build_environment(
        self,
    ) -> dict[str, str]:
        environment: dict[str, str] = {}

        for key, value in os.environ.items():
            if (
                key.upper()
                in SAFE_ENVIRONMENT_KEYS
            ):
                environment[key] = value

        environment.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            }
        )

        for (
            key,
            value,
        ) in self.extra_environment.items():
            normalized_key = key.upper()

            if not ENVIRONMENT_NAME_PATTERN.fullmatch(
                normalized_key
            ):
                raise SandboxPolicyError(
                    
                        "Invalid sandbox environment "
                        f"variable name: {key}"
                    
                )

            environment[
                normalized_key
            ] = value

        return environment

    def _validate_pytest_targets(
        self,
        targets: list[str],
    ) -> list[str]:
        validated: list[str] = []

        for target in targets:
            target = target.strip()

            if not target:
                raise SandboxPolicyError(
                    
                        "Empty pytest target "
                        "is not allowed."
                    
                )

            if target.startswith("-"):
                raise SandboxPolicyError(
                    
                        "Pytest command-line options "
                        "cannot be supplied through targets."
                    
                )

            path_part = target.split(
                "::",
                1,
            )[0]

            normalized = path_part.replace(
                "\\",
                "/",
            )

            posix_path = PurePosixPath(
                normalized
            )

            windows_path = PureWindowsPath(
                normalized
            )

            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or bool(windows_path.drive)
            ):
                raise SandboxPolicyError(
                    
                        "Absolute pytest targets "
                        "are not allowed."
                    
                )

            if (
                ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                raise SandboxPolicyError(
                    
                        "Parent traversal is not "
                        "allowed in pytest targets."
                    
                )

            validated.append(
                target
            )

        return validated

    def _require_root(
        self,
    ) -> Path:
        if self.sandbox_root is None:
            raise SandboxExecutionError(
                
                    "Sandbox session has not "
                    "been started."
                
            )

        return self.sandbox_root

    def _truncate_output(
        self,
        output: str,
    ) -> str:
        if (
            len(output)
            <= self.max_output_characters
        ):
            return output

        omitted = (
            len(output)
            - self.max_output_characters
        )

        return (
            output[
                : self.max_output_characters
            ]
            + "\n\n"
            + (
                "[OUTPUT TRUNCATED: "
                f"{omitted} characters omitted]"
            )
        )

    @staticmethod
    def _display_command(
        command: list[str],
    ) -> list[str]:
        if not command:
            return []

        displayed = list(
            command
        )

        displayed[0] = "python"

        return displayed


class RestrictedSandboxRunner:
    """
    Factory for disposable restricted execution sessions.

    Commands are deliberately exposed through dedicated methods
    instead of accepting arbitrary command strings.
    """

    def __init__(
        self,
        workspace: SecureWorkspace,
        *,
        timeout_seconds: float = 120.0,
        max_output_characters: int = 30_000,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                
                    "timeout_seconds must be "
                    "greater than zero."
                
            )

        if max_output_characters < 1_000:
            raise ValueError(
                
                    "max_output_characters "
                    "must be at least 1000."
                
            )

        self.workspace = workspace

        self.timeout_seconds = (
            timeout_seconds
        )

        self.max_output_characters = (
            max_output_characters
        )

    def open_session(
        self,
        *,
        environment: dict[str, str] | None = None,
    ) -> SandboxSession:
        return SandboxSession(
            source_root=Path(
                self.workspace.root
            ),
            timeout_seconds=(
                self.timeout_seconds
            ),
            max_output_characters=(
                self.max_output_characters
            ),
            environment=environment,
        )