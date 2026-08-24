EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        "coverage",
        ".next",
    }
)

MAX_FILE_SIZE_BYTES = 1_000_000
MAX_READ_CHARACTERS = 50_000
MAX_SEARCH_RESULTS = 100
MAX_SEARCH_LINE_CHARACTERS = 500