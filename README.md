# LLM-Powered-File-System-Assistant

A Python assistant for inspecting and searching resume files and writing summaries. It gives an OpenRouter-hosted, OpenAI-compatible chat model access to filesystem tools, then executes tool calls requested in response to natural-language queries.

## Requirements

- Python 3.10 or newer
- An OpenRouter API key

## Setup

Create and activate a virtual environment, install dependencies, and configure your OpenRouter key in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OpenRouter = "your-api-key"
```

If `OpenRouter` is not set, the CLI prompts for the key when it starts. The assistant uses `gpt-4o-mini` by default; choose another compatible model with `--model` or the `OPENAI_MODEL` environment variable.

## Usage

The `--root` directory is the assistant's filesystem boundary. Paths requested by the model are resolved relative to this directory, and attempts to access paths outside it are rejected. By default, the root is the current directory.

```powershell
python llm_file_assistant.py --root . "Read all resumes in the resumes folder"
python llm_file_assistant.py --root . "Find resumes mentioning Python experience"
python llm_file_assistant.py --root . "Create a summary file for resumes/resume_john_doe.pdf"
```

You can also omit the query to be prompted interactively, then enter additional queries until you submit a blank line.

## Filesystem Tools

The `fs_tools.py` module provides these functions:

- `read_file(filepath: str) -> dict`: extracts text from PDF, TXT, or DOCX files and returns the content, metadata, and success status. Errors are returned in the response. PDF and DOCX extraction uses `pypdf` and `python-docx`; scanned, image-only PDFs are not OCR-processed.
- `list_files(directory: str, extension: str | None = None) -> list`: lists files directly inside a directory, optionally filtered by extension (such as `.pdf` or `.txt`). Each result includes the file name, path, size, and modification time.
- `write_file(filepath: str, content: str) -> dict`: writes UTF-8 text, creates parent directories when needed, and returns a success status and metadata or an error.
- `search_in_file(filepath: str, keyword: str) -> dict`: searches supported file contents case-insensitively and returns each match with its character index and surrounding text.

The LLM can combine these tools to inspect a folder of resumes, find files mentioning a skill, and write a summary based on a resume's extracted text.

## Tests

Run the test suite with:

```powershell
python -m unittest discover -s tests -v
```