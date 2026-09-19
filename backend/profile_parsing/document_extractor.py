from __future__ import annotations

import io
import tempfile
from pathlib import Path

import fitz
from docx import Document

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"} | IMAGE_EXTENSIONS


def _require_text(text: str, extension: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"The uploaded {extension} file is empty or contains no readable text.")
    return cleaned


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        raw_text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            raw_text = "\n".join(page.get_text("text") for page in document).strip()
        return _require_text(raw_text, ".pdf")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the PDF. Please upload a valid PDF or scanned document.") from exc


def _extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        document = Document(io.BytesIO(file_bytes))
        parts = [paragraph.text for paragraph in document.paragraphs]
        parts.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        return _require_text("\n".join(parts), ".docx")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the DOCX. Please upload a valid Word document.") from exc


def _extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_bytes.decode("cp1252")
        return _require_text(text, ".txt")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the TXT file. Please upload a valid text file.") from exc


def _extract_text_from_doc(file_bytes: bytes) -> str:
    temporary_path = None
    word = None
    document = None

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_path = Path(temporary_file.name)

        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        document = word.Documents.Open(
            str(temporary_path),
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
            NoEncodingDialog=True,
        )
        paragraph_text = [paragraph.Range.Text.strip() for paragraph in document.Paragraphs]
        return _require_text("\n".join(paragraph_text), ".doc")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Unable to read the DOC file. Microsoft Word is required for legacy .doc resumes."
        ) from exc
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        try:
            pythoncom.CoUninitialize()
        except UnboundLocalError:
            pass


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF, DOC, DOCX, TXT, or Image resume bytes."""
    if not file_bytes:
        raise ValueError("No resume uploaded.")

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Invalid file type. Please upload a PDF, DOC, DOCX, TXT, or Image file."
        )

    if extension == ".pdf":
        return _extract_text_from_pdf(file_bytes)
    if extension == ".docx":
        return _extract_text_from_docx(file_bytes)
    if extension == ".txt":
        return _extract_text_from_txt(file_bytes)
    return _extract_text_from_doc(file_bytes)


