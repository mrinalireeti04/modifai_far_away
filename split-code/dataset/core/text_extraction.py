"""
Text Extraction Module for PDFs.
Uses local PyMuPDF extraction first, with fallback capabilities to AWS Textract if needed.
"""
import os
import fitz  # PyMuPDF
from .utils import get_logger

logger = get_logger(__name__)

def extract_text_local(pdf_path: str) -> str:
    """Extracts text using PyMuPDF locally."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
    logger.info(f"Extracting text locally from {pdf_path}")
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        logger.error(f"Local extraction failed: {e}")
        raise
    
    # Clean normalized text
    return " ".join(text.split())

def extract_text_textract(pdf_path: str, region_name: str = "us-east-1") -> str:
    """Fallback extraction using AWS Textract."""
    logger.info(f"Fallback: Extracting text using AWS Textract for {pdf_path}")
    try:
        import boto3
        textract = boto3.client('textract', region_name=region_name)
        with open(pdf_path, 'rb') as document:
            imageBytes = bytearray(document.read())

        response = textract.detect_document_text(Document={'Bytes': imageBytes})
        extracted_text = []
        for item in response["Blocks"]:
            if item["BlockType"] == "LINE":
                extracted_text.append(item["Text"])
        return " ".join(extracted_text)
    except Exception as e:
        logger.error(f"Textract extraction failed: {e}")
        raise

def extract_text(pdf_path: str, use_textract_fallback: bool = False, region_name: str = "us-east-1") -> str:
    """Main extraction function."""
    try:
        return extract_text_local(pdf_path)
    except Exception as e:
        if use_textract_fallback:
            return extract_text_textract(pdf_path, region_name)
        raise e
