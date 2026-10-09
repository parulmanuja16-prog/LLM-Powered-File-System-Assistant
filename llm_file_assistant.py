"""OpenAI-powered CLI for working with files inside a chosen root directory."""

from __future__ import annotations

import argparse
import json
import os
import getpass
from pathlib import Path
import sys
from typing import Any

from fs_tools import list_files, read_file, search_in_file, write_file


MAX_TOOL_ROUNDS = 8
DEFAULT_MODEL = "gpt-4o-mini"


if not os.environ.get("OpenRouter"):
    os.environ["OpenRouter"] = getpass.getpass(
        "Enter your OpenRouter API key: "
    )

print("✅ OpenRouter API key loaded")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory, optionally filtering by extension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string"},
                    "extension": {"type": ["string", "null"]},
                },
                "required": ["directory"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Extract text and metadata from a PDF, TXT, or DOCX file.",
            "parameters": {
                "type": "object",
                "properties": {"filepath": {"type": "string"}},
                "required": ["filepath"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Search a file for a case-insensitive keyword and return context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "keyword": {"type": "string"},
                },
                "required": ["filepath", "keyword"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write UTF-8 text to a file, creating parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filepath", "content"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "search_in_file": search_in_file,
    "write_file": write_file,
}


def _scoped_path(value: str, root: Path) -> str:
    """Resolve a requested path and reject paths outside the configured root."""
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path is outside the configured root directory: {value}")
    return str(resolved)


def _run_tool(name: str, arguments: dict[str, Any], root: Path) -> Any:
    """Validate and execute one model-requested filesystem tool call."""
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {name}")

    scoped_arguments = dict(arguments)
    if name == "list_files":
        scoped_arguments["directory"] = _scoped_path(scoped_arguments["directory"], root)
    else:
        scoped_arguments["filepath"] = _scoped_path(scoped_arguments["filepath"], root)
    return TOOL_FUNCTIONS[name](**scoped_arguments)


def run_query(
    query: str,
    root_dir: str = ".",
    model: str = DEFAULT_MODEL,
    client: Any = None,
) -> str:
    """Send a query to the configured LLM and execute requested tool calls."""
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install dependencies with 'pip install -r requirements.txt'.") from exc
        client = OpenAI(
          base_url="https://openrouter.ai/api/v1", #Send requests to OpenRouter instead of directly to OpenAI
          api_key=os.environ["OpenRouter"],

          )

    root = Path(root_dir).expanduser().resolve()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a resume file assistant. Use the available tools to inspect or modify "
                "files as requested. Paths are relative to the configured root directory. "
                "For requests involving all resumes, list the directory first and then inspect "
                "matching files. Never claim a file operation succeeded unless the tool did. "
                "When creating a summary, base it only on the resume content and save it to the "
                "requested path."
            ),
        },
        {"role": "user", "content": query},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        assistant_message = response.choices[0].message
        messages.append(assistant_message.model_dump(exclude_none=True))
        tool_calls = assistant_message.tool_calls or []
        if not tool_calls:
            return assistant_message.content or ""

        for tool_call in tool_calls:
            function = tool_call.function
            try:
                arguments = json.loads(function.arguments)
                result = _run_tool(function.name, arguments, root)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(f"The assistant exceeded the limit of {MAX_TOOL_ROUNDS} tool rounds.")


def main() -> None:
    """Parse CLI options and handle queries until the user exits."""
    parser = argparse.ArgumentParser(description="Ask an LLM to work with files under a root directory.")
    parser.add_argument("query", nargs="*", help="Natural-language request")
    parser.add_argument("--root", default=".", help="Directory the assistant may access (default: current directory)")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
    arguments = parser.parse_args()

    query = " ".join(arguments.query).strip()
    if not query:
        query = input("What would you like me to do? ").strip()
    if not query:
        parser.error("query cannot be empty")

    while query:
        try:
            print(run_query(query, arguments.root, arguments.model))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)

        try:
            query = input("Ask another query (press Enter to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break


if __name__ == "__main__":
    main()