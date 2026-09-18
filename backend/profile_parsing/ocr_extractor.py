import io
import fitz
from PIL import Image

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Extract text from raw image bytes using PIL and pytesseract."""
    if not image_bytes:
        return ""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if HAS_PYTESSERACT:
            try:
                extracted = pytesseract.image_to_string(image)
                if extracted and extracted.strip():
                    return extracted.strip()
            except Exception:
                # Tesseract executable might not be in system PATH
                pass
        return ""
    except Exception as exc:
        raise ValueError(f"Unable to process image for OCR: {exc}") from exc


def ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    """Render scanned PDF pages as images and extract text using OCR."""
    if not pdf_bytes:
        return ""

    extracted_pages = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            for page in document:
                # Render page to high-DPI image
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                page_text = extract_text_from_image_bytes(img_bytes)
                if page_text:
                    extracted_pages.append(page_text)

        return "\n".join(extracted_pages).strip()
    except Exception as exc:
        raise ValueError(f"Unable to perform OCR on PDF: {exc}") from exc
