"""Content-aware text extraction for remote document loaders."""

from __future__ import annotations

import logging
import os
import tempfile

from .base import Document

logger = logging.getLogger(__name__)


class FileContentExtractor:
    """Turn remote file bytes into safe text for retrieval and embedding."""

    _TEXT_EXTENSIONS = {
        ".log",
        ".md",
        ".py",
        ".rst",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
    _TEXT_CONTENT_TYPES = {
        "application/javascript",
        "application/json",
        "application/xml",
        "application/x-yaml",
    }
    _EXTRACTABLE_EXTENSIONS = {
        ".csv",
        ".docx",
        ".htm",
        ".html",
        ".json",
        ".pdf",
        ".pptx",
        ".xlsx",
    }

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    def extract(self, filename: str, content: bytes, content_type: str | None = None) -> str:
        """Extract readable text or return an explicit binary placeholder."""

        extension = os.path.splitext(filename)[1].lower()
        media_type = self._normalize_content_type(content_type)

        if b"\x00" in content[:1024]:
            return self._binary_placeholder(media_type, extension)

        if extension in self._TEXT_EXTENSIONS or self._is_text_content_type(media_type):
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return self._binary_placeholder(media_type, extension)

        if extension in self._EXTRACTABLE_EXTENSIONS:
            extracted = self._extract_with_loader(filename, content, extension)
            if extracted is not None:
                return extracted

        if self._is_binary(media_type):
            return self._binary_placeholder(media_type, extension)

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return self._binary_placeholder(media_type, extension)

    @staticmethod
    def _normalize_content_type(content_type: str | None) -> str | None:
        if not content_type:
            return None
        return content_type.partition(";")[0].strip().lower() or None

    def _is_text_content_type(self, content_type: str | None) -> bool:
        return bool(
            content_type
            and (content_type.startswith("text/") or content_type in self._TEXT_CONTENT_TYPES)
        )

    def _is_binary(self, content_type: str | None) -> bool:
        return bool(content_type and not self._is_text_content_type(content_type))

    @staticmethod
    def _binary_placeholder(content_type: str | None, extension: str) -> str:
        descriptor = content_type or extension or "unknown"
        return f"[Binary file: {descriptor}]"

    def _extract_with_loader(
        self,
        filename: str,
        content: bytes,
        extension: str,
    ) -> str | None:
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporary_file:
                temporary_file.write(content)
                temp_path = temporary_file.name

            documents = self._run_loader(extension, temp_path)
            return "\n\n".join(document.text for document in documents if document.text)
        except Exception as exc:
            logger.warning(
                "%s: extraction fallback for %r — %s",
                self.source_name,
                filename,
                exc,
            )
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _run_loader(extension: str, path: str) -> list[Document]:
        if extension == ".pdf":
            from .pdf import PDFLoader

            return PDFLoader(path).load()
        if extension == ".docx":
            from .docx import DocxLoader

            return DocxLoader(path).load()
        if extension == ".xlsx":
            from .excel import ExcelLoader

            return ExcelLoader(path).load()
        if extension == ".pptx":
            from .pptx import PowerPointLoader

            return PowerPointLoader(path).load()
        if extension == ".csv":
            from .csv import CSVLoader

            return CSVLoader(path).load()
        if extension == ".json":
            from .json_loader import JSONLoader

            return JSONLoader(path).load()
        if extension in {".html", ".htm"}:
            from .html import HTMLLoader

            return HTMLLoader(path).load()
        return []
