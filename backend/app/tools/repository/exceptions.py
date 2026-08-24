class RepositoryToolError(Exception):
    """Base exception for repository tools."""


class RepositoryNotFoundError(RepositoryToolError):
    """Raised when the assigned repository does not exist."""


class WorkspaceSecurityError(RepositoryToolError):
    """Raised when a path violates workspace security rules."""


class RepositoryPathNotFoundError(RepositoryToolError):
    """Raised when a requested repository path does not exist."""


class InvalidRepositoryPathError(RepositoryToolError):
    """Raised when a file/directory type is not valid for an operation."""


class FileTooLargeError(RepositoryToolError):
    """Raised when a file exceeds the allowed read size."""


class BinaryFileError(RepositoryToolError):
    """Raised when a binary file is requested as text."""