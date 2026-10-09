"""Unit tests for filesystem reading, writing, listing, and search tools."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from fs_tools import list_files, read_file, search_in_file, write_file


class FileSystemToolsTests(unittest.TestCase):
    """Exercise filesystem tools using isolated temporary directories."""

    def setUp(self):
        """Create a temporary directory for the current test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        """Remove the temporary directory created for the test."""
        self.temporary_directory.cleanup()

    def test_write_creates_directories_and_read_returns_metadata(self):
        """Verify nested writes and metadata-bearing text reads."""
        filepath = self.root / "resumes" / "resume.txt"

        result = write_file(str(filepath), "Python engineer")
        read_result = read_file(str(filepath))

        self.assertTrue(result["success"])
        self.assertTrue(read_result["success"])
        self.assertEqual(read_result["content"], "Python engineer")
        self.assertEqual(read_result["metadata"]["name"], "resume.txt")
        self.assertEqual(read_result["metadata"]["extension"], ".txt")

    def test_list_files_filters_extensions_case_insensitively(self):
        """Verify extension filtering ignores filename case and returns metadata."""
        write_file(str(self.root / "b.TXT"), "text")
        write_file(str(self.root / "a.pdf"), "placeholder")

        files = list_files(str(self.root), ".txt")

        self.assertEqual([item["name"] for item in files], ["b.TXT"])
        self.assertIn("size", files[0])
        self.assertIn("modified", files[0])

    def test_search_finds_case_insensitive_occurrences_with_context(self):
        """Verify search returns each case-insensitive match with context."""
        filepath = self.root / "resume.txt"
        write_file(str(filepath), "Python, data science, and python services")

        result = search_in_file(str(filepath), "PYTHON")

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("data science", result["matches"][0]["context"])

    def test_errors_are_returned_for_missing_unsupported_and_empty_search(self):
        """Verify invalid file and keyword requests return failure results."""
        missing = read_file(str(self.root / "missing.txt"))
        unsupported_path = self.root / "resume.rtf"
        unsupported_path.write_text("text", encoding="utf-8")
        unsupported = read_file(str(unsupported_path))
        empty_search = search_in_file(str(unsupported_path), "")

        self.assertFalse(missing["success"])
        self.assertFalse(unsupported["success"])
        self.assertFalse(empty_search["success"])

    @unittest.skipUnless(importlib.util.find_spec("docx"), "python-docx is not installed")
    def test_reads_docx_text(self):
        """Verify text is extracted from a DOCX document."""
        from docx import Document

        filepath = self.root / "resume.docx"
        document = Document()
        document.add_paragraph("DOCX resume text")
        document.save(filepath)

        result = read_file(str(filepath))

        self.assertTrue(result["success"])
        self.assertIn("DOCX resume text", result["content"])

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is not installed")
    def test_reads_pdf_file(self):
        """Verify PDF files are read and report their extension metadata."""
        from pypdf import PdfWriter

        filepath = self.root / "resume.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        with filepath.open("wb") as output:
            writer.write(output)

        result = read_file(str(filepath))

        self.assertTrue(result["success"])
        self.assertEqual(result["metadata"]["extension"], ".pdf")


if __name__ == "__main__":
    unittest.main()