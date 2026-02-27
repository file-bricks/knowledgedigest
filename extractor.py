# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Text-Extraktion aus verschiedenen Dateiformaten.

Unterstuetzte Formate:
    - PDF  (via pdfplumber, PyPDF2 Fallback)
    - DOCX (via python-docx)
    - TXT  (direkt, UTF-8 mit Fallback)
    - MD   (direkt, als Plaintext)
    - HTML (via BeautifulSoup)

Usage:
    from KnowledgeDigest.extractor import TextExtractor
    ext = TextExtractor()
    result = ext.extract("/path/to/document.pdf")
    print(result.text[:200])
"""

__all__ = ["TextExtractor", "ExtractedText"]

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set


@dataclass
class ExtractedText:
    """Ergebnis einer Text-Extraktion."""
    text: str
    language: Optional[str] = None
    method: str = "unknown"
    page_count: int = 0


# Unterstuetzte Dateitypen gruppiert
_PDF_EXTS = {'.pdf'}
_DOCX_EXTS = {'.docx'}
_TEXT_EXTS = {'.txt', '.md', '.markdown', '.rst', '.csv', '.log', '.yaml', '.yml', '.json', '.xml'}
_HTML_EXTS = {'.html', '.htm'}

ALL_SUPPORTED = _PDF_EXTS | _DOCX_EXTS | _TEXT_EXTS | _HTML_EXTS


class TextExtractor:
    """Extrahiert Text aus verschiedenen Dateiformaten."""

    def supported_types(self) -> Set[str]:
        """Gibt unterstuetzte Dateiendungen zurueck."""
        return ALL_SUPPORTED

    def can_extract(self, path: Path) -> bool:
        """Prueft ob Datei unterstuetzt wird."""
        return Path(path).suffix.lower() in ALL_SUPPORTED

    def extract(self, path: str | Path) -> ExtractedText:
        """Extrahiert Text aus einer Datei.

        Args:
            path: Pfad zur Datei

        Returns:
            ExtractedText mit extrahiertem Text und Metadaten

        Raises:
            FileNotFoundError: Datei existiert nicht
            ValueError: Dateityp nicht unterstuetzt
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

        ext = path.suffix.lower()

        if ext in _PDF_EXTS:
            return self._extract_pdf(path)
        elif ext in _DOCX_EXTS:
            return self._extract_docx(path)
        elif ext in _HTML_EXTS:
            return self._extract_html(path)
        elif ext in _TEXT_EXTS:
            return self._extract_text(path)
        else:
            raise ValueError(f"Dateityp '{ext}' nicht unterstuetzt. "
                           f"Unterstuetzt: {sorted(ALL_SUPPORTED)}")

    def _extract_pdf(self, path: Path) -> ExtractedText:
        """PDF-Extraktion: pdfplumber primaer, PyPDF2 Fallback."""
        # Versuch 1: pdfplumber
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            if pages:
                return ExtractedText(
                    text="\n\n".join(pages),
                    method="pdfplumber",
                    page_count=page_count,
                )
        except Exception:
            pass

        # Versuch 2: PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            page_count = len(reader.pages)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            if pages:
                return ExtractedText(
                    text="\n\n".join(pages),
                    method="pypdf2",
                    page_count=page_count,
                )
        except Exception:
            pass

        return ExtractedText(text="", method="pdf_failed", page_count=0)

    def _extract_docx(self, path: Path) -> ExtractedText:
        """DOCX-Extraktion via python-docx."""
        try:
            from docx import Document
            doc = Document(str(path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return ExtractedText(
                text="\n\n".join(paragraphs),
                method="python-docx",
                page_count=0,
            )
        except Exception as e:
            return ExtractedText(text="", method=f"docx_failed: {e}")

    def _extract_html(self, path: Path) -> ExtractedText:
        """HTML-Extraktion via BeautifulSoup."""
        raw = self._read_file(path)
        if not raw:
            return ExtractedText(text="", method="html_read_failed")

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw, 'html.parser')

            # Script und Style entfernen
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            text = soup.get_text(separator='\n', strip=True)
            return ExtractedText(text=text, method="beautifulsoup")
        except Exception as e:
            return ExtractedText(text="", method=f"html_failed: {e}")

    def _extract_text(self, path: Path) -> ExtractedText:
        """Plaintext-Extraktion (TXT, MD, YAML, etc.)."""
        text = self._read_file(path)
        if text is None:
            return ExtractedText(text="", method="text_read_failed")

        ext = path.suffix.lower()
        method = f"plaintext_{ext.lstrip('.')}"
        return ExtractedText(text=text, method=method)

    @staticmethod
    def _read_file(path: Path) -> Optional[str]:
        """Liest Datei mit UTF-8, Fallback auf cp1252 (Windows)."""
        for encoding in ('utf-8', 'cp1252', 'latin-1'):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return None
