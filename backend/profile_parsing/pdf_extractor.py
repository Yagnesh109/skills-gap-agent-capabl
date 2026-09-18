import fitz


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract readable text from a text-based PDF file."""
    if not file_bytes:
        raise ValueError("No PDF uploaded.")

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            pages = []
            for page in document:
                page_text = page.get_text("text")
                if page_text:
                    pages.append(page_text)

            combined_text = "\n".join(pages).strip()
            if not combined_text:
                raise ValueError("The uploaded PDF is empty or contains no readable text.")
            return combined_text
    except Exception as exc:  # pragma: no cover - runtime failure path
        raise ValueError("Unable to read the PDF. Please upload a valid text-based PDF.") from exc
