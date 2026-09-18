from io import BytesIO

import pytest
from docx import Document

from profile_parsing.schemas import EMPTY_PROFILE
from profile_parsing.document_extractor import extract_text_from_file
from profile_parsing.pdf_extractor import extract_text_from_pdf


def test_empty_profile_has_expected_structure():
    assert EMPTY_PROFILE["personal_info"]["name"] == ""
    assert EMPTY_PROFILE["education"] == []
    assert EMPTY_PROFILE["skills"] == []


def test_invalid_pdf_bytes_raise_value_error():
    with pytest.raises(ValueError):
        extract_text_from_pdf(b"this is not a pdf")


def test_docx_text_is_extracted():
    document = Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("Python Developer")
    document_bytes = BytesIO()
    document.save(document_bytes)

    extracted_text = extract_text_from_file(document_bytes.getvalue(), "resume.docx")

    assert "Jane Doe" in extracted_text
    assert "Python Developer" in extracted_text
