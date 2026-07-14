"""
utils/text_extractor.py
Extracts plain text from PDF, DOCX, and TXT uploads.
"""

import io
import PyPDF2
import docx


def extract_text(file_storage) -> str:
    """
    Accept a Werkzeug FileStorage object (or a file-like bytes buffer with
    a .filename attribute) and return its plain-text content.
    """
    filename = file_storage.filename.lower()

    if filename.endswith(".pdf"):
        return _from_pdf(file_storage)
    elif filename.endswith(".docx"):
        return _from_docx(file_storage)
    elif filename.endswith(".txt"):
        return _from_txt(file_storage)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


# ── private helpers ───────────────────────────────────────────────────────────

def _from_pdf(file_storage) -> str:
    raw = file_storage.read()
    reader = PyPDF2.PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _from_docx(file_storage) -> str:
    raw = file_storage.read()
    doc = docx.Document(io.BytesIO(raw))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _from_txt(file_storage) -> str:
    raw = file_storage.read()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
