"""Filesystem tools for reading, writing, listing, and searching resume files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_READ_EXTENSIONS = {".pdf", ".txt", ".docx"}
CONTEXT_CHARS = 60


def _file_metadata(path: Path) -> dict[str, Any]:
    """Return the file's name, resolved path, size, and UTC modification time."""
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _extract_text(path: Path) -> str:
    """Extract text from a supported file based on its extension."""
    extension = path.suffix.lower()
    if extension == ".txt":
        return path.read_text(encoding="utf-8-sig")
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires the 'pypdf' package.") from exc

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if extension == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX support requires the 'python-docx' package.") from exc

        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError(f"Unsupported file type: {extension or '(no extension)'}")


def read_file(filepath: str) -> dict[str, Any]:
    """Extract text and metadata from a PDF, TXT, or DOCX file."""
    path = Path(filepath).expanduser()
    try:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")
        content = _extract_text(path)
        return {
            "success": True,
            "content": content,
            "metadata": {**_file_metadata(path), "extension": path.suffix.lower()},
        }
    except Exception as exc:
        return {"success": False, "content": "", "metadata": {}, "error": str(exc)}


def list_files(directory: str, extension: str | None = None) -> list[dict[str, Any]]:
    """List files directly inside a directory, optionally filtered by extension."""
    path = Path(directory).expanduser()
    if not path.is_dir():
        return []

    normalized_extension = extension.lower() if extension else None
    if normalized_extension and not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"

    files = []
    try:
        for item in path.iterdir():
            if item.is_file() and (
                normalized_extension is None or item.suffix.lower() == normalized_extension
            ):
                files.append(_file_metadata(item))
    except OSError:
        return []
    return sorted(files, key=lambda file: file["name"].casefold())


def write_file(filepath: str, content: str) -> dict[str, Any]:
    """Write UTF-8 text to a file, creating parent directories when needed."""
    path = Path(filepath).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"success": True, "metadata": _file_metadata(path)}
    except (OSError, TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


def search_in_file(filepath: str, keyword: str) -> dict[str, Any]:
    """Find case-insensitive keyword occurrences and return surrounding context."""
    if not keyword:
        return {"success": False, "matches": [], "count": 0, "error": "Keyword cannot be empty."}

    result = read_file(filepath)
    if not result["success"]:
        return {
            "success": False,
            "matches": [],
            "count": 0,
            "error": result["error"],
        }

    content = result["content"]
    folded_content = content.casefold()
    folded_keyword = keyword.casefold()
    matches = []
    offset = 0
    while (index := folded_content.find(folded_keyword, offset)) != -1:
        start = max(0, index - CONTEXT_CHARS)
        end = min(len(content), index + len(keyword) + CONTEXT_CHARS)
        matches.append({"index": index, "context": content[start:end]})
        offset = index + len(folded_keyword)

    return {
        "success": True,
        "keyword": keyword,
        "count": len(matches),
        "matches": matches,
        "metadata": result["metadata"],
    }