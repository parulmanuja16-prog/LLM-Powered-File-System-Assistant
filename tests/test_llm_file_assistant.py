"""Unit tests for the interactive CLI and LLM tool-calling workflow."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fs_tools import write_file
from llm_file_assistant import main, run_query


class FakeMessage:
    """Represent an assistant response with optional function tool calls."""

    def __init__(self, content=None, tool_calls=None):
        """Initialize a fake response with text and optional tool calls."""
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=True):
        """Return the response in the message shape expected by the API loop."""
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ],
        }


def fake_tool_call(call_id, name, arguments):
    """Build a fake tool call with JSON-encoded function arguments."""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeCompletions:
    """Provide queued fake assistant responses for completion requests."""

    def __init__(self, messages):
        """Store responses to return in order."""
        self.messages = messages

    def create(self, **kwargs):
        """Return the next queued response in an API-compatible wrapper."""
        message = self.messages.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class LLMFileAssistantTests(unittest.TestCase):
    """Verify CLI prompting, tool execution, and filesystem path boundaries."""

    def test_main_prompts_for_query_when_not_provided(self):
        """Verify the CLI prompts for an initial query when none is provided."""
        with (
            patch("sys.argv", ["llm_file_assistant.py"]),
            patch("builtins.input", side_effect=["Find Python resumes", ""]) as prompt,
            patch("llm_file_assistant.run_query", return_value="Done") as query,
            patch("builtins.print"),
        ):
            main()

        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(query.call_args.args[0], "Find Python resumes")

    def test_main_processes_follow_up_queries_until_blank_input(self):
        """Verify the CLI handles consecutive queries and exits on blank input."""
        with (
            patch("sys.argv", ["llm_file_assistant.py", "First query"]),
            patch("builtins.input", side_effect=["Second query", ""]),
            patch(
                "llm_file_assistant.run_query",
                side_effect=["First response", "Second response"],
            ) as query,
            patch("builtins.print"),
        ):
            main()

        self.assertEqual(
            [call.args[0] for call in query.call_args_list],
            ["First query", "Second query"],
        )

    def test_query_can_read_resume_then_write_summary(self):
        """Verify model calls can read a resume and write its summary."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            resume = root / "resumes" / "resume.txt"
            write_file(str(resume), "Experienced Python engineer.")
            responses = [
                FakeMessage(tool_calls=[fake_tool_call(
                    "read-1", "read_file", {"filepath": "resumes/resume.txt"}
                )]),
                FakeMessage(tool_calls=[fake_tool_call(
                    "write-1",
                    "write_file",
                    {
                        "filepath": "summaries/resume-summary.txt",
                        "content": "Experienced Python engineer.",
                    },
                )]),
                FakeMessage(content="Summary saved."),
            ]
            client = SimpleNamespace(
                chat=SimpleNamespace(completions=FakeCompletions(responses))
            )

            answer = run_query("Summarize the resume", str(root), client=client)

            self.assertEqual(answer, "Summary saved.")
            self.assertEqual(
                (root / "summaries" / "resume-summary.txt").read_text(encoding="utf-8"),
                "Experienced Python engineer.",
            )

    def test_tool_paths_cannot_escape_root(self):
        """Verify tool calls cannot write outside the configured root."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=FakeCompletions(
                        [
                            FakeMessage(tool_calls=[fake_tool_call(
                                "write-1",
                                "write_file",
                                {"filepath": "../outside.txt", "content": "blocked"},
                            )]),
                            FakeMessage(content="The path was rejected."),
                        ]
                    )
                )
            )

            answer = run_query("Write outside the root", str(root), client=client)

            self.assertEqual(answer, "The path was rejected.")
            self.assertFalse((root.parent / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()