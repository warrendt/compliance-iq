"""
PDF Text Extraction Module.
Extracts and preprocesses text from compliance control PDF documents.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str, max_pages: int = 200) -> str:
    """
    Extract all text from a PDF file, page by page.

    Args:
        pdf_path: Path to the PDF file.
        max_pages: Maximum number of pages to process (safety limit).

    Returns:
        Concatenated text from all pages with page markers.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the file is not a PDF or is empty.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")
    if path.stat().st_size == 0:
        raise ValueError(f"PDF file is empty: {pdf_path}")

    try:
        import pypdf
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF extraction. Install it: pip install pypdf"
        )

    reader = pypdf.PdfReader(str(path))
    total_pages = len(reader.pages)

    if total_pages == 0:
        raise ValueError(f"PDF has no pages: {pdf_path}")

    pages_to_process = min(total_pages, max_pages)
    logger.info(f"Extracting text from {path.name}: {total_pages} pages (processing {pages_to_process})")

    text_parts: list[str] = []

    for page_num in range(pages_to_process):
        try:
            page = reader.pages[page_num]
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(f"\n=== PAGE {page_num + 1} ===\n{page_text}")
        except Exception as e:
            logger.warning(f"Failed to extract page {page_num + 1}: {e}")
            text_parts.append(f"\n=== PAGE {page_num + 1} === [EXTRACTION FAILED]\n")

    full_text = "\n".join(text_parts)

    if not full_text.strip():
        raise ValueError(
            f"No readable text found in {path.name}. "
            "The PDF may be scanned/image-based. OCR is not currently supported."
        )

    logger.info(
        f"Extracted {len(full_text):,} characters from {pages_to_process} pages"
    )
    return full_text


def chunk_text(text: str, max_chars: int = 80000, overlap: int = 2000) -> list[str]:
    """
    Split large text into overlapping chunks for LLM processing.

    Args:
        text: Full extracted text.
        max_chars: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    logger.info(f"Split text into {len(chunks)} chunks ({max_chars} chars each, {overlap} overlap)")
    return chunks


def get_pdf_metadata(pdf_path: str) -> dict:
    """
    Extract metadata from the PDF (title, author, etc.).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary of metadata fields.
    """
    import pypdf

    reader = pypdf.PdfReader(pdf_path)
    meta = reader.metadata or {}

    return {
        "title": meta.get("/Title", ""),
        "author": meta.get("/Author", ""),
        "subject": meta.get("/Subject", ""),
        "creator": meta.get("/Creator", ""),
        "producer": meta.get("/Producer", ""),
        "pages": len(reader.pages),
        "file_size_bytes": Path(pdf_path).stat().st_size,
    }
