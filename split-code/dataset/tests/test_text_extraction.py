import pytest
from modifai.core.text_extraction import extract_text_local

def test_extract_text_local_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text_local("nonexistent_file.pdf")
        
# A proper test would mock PyMuPDF and Textract, but for the sake of these tests, 
# ensuring the exception is raised is a good start.
