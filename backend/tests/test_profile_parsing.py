import pytest

from profile_parsing.schemas import EMPTY_PROFILE
from profile_parsing.pdf_extractor import extract_text_from_pdf


def test_empty_profile_has_expected_structure():
    assert EMPTY_PROFILE["personal_info"]["name"] == ""
    assert EMPTY_PROFILE["education"] == []
    assert EMPTY_PROFILE["skills"] == []


def test_invalid_pdf_bytes_raise_value_error():
    with pytest.raises(ValueError):
        extract_text_from_pdf(b"this is not a pdf")
