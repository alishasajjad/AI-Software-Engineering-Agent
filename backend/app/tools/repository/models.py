from typing import Literal

from pydantic import BaseModel


class DirectoryEntry(BaseModel):
    name: str
    path: str
    entry_type: Literal["file", "directory"]
    size_bytes: int | None = None


class ListDirectoryResult(BaseModel):
    path: str
    entries: list[DirectoryEntry]


class ReadFileResult(BaseModel):
    path: str
    content: str
    size_bytes: int
    total_lines: int
    start_line: int
    end_line: int
    truncated: bool


class SearchMatch(BaseModel):
    path: str
    line_number: int
    line: str


class SearchCodeResult(BaseModel):
    query: str
    path: str
    matches: list[SearchMatch]
    files_scanned: int
    truncated: bool