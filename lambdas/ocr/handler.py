"""
OCR Lambda — Extracts text from uploaded documents in S3.

Input (from Step Functions):
{
    "project_id": "proj-abc123",
    "s3_prefix": "user-uuid/proj-uuid/",
    "mode": "full",
    "config": { ... },
    "step_results": {
        "upload": {
            "raw_file_keys": ["data/file1.pdf", "data/file2.txt"]
        }
    }
}

Output (passed to next step):
{
    ...input,
    "step_results": {
        ...input.step_results,
        "ocr": {
            "raw_text_key": "temp_processing/raw_text.json",
            "files_processed": 2,
            "total_characters": 15234
        }
    }
}
"""

import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)
textract_client = boto3.client("textract", region_name=AWS_REGION)


def handler(event, context):
    """Lambda entry point for OCR step."""
    logger.info(f"OCR Lambda invoked for project: {event.get('project_id')}")

    s3_prefix = event["s3_prefix"]
    raw_file_keys = event["step_results"]["upload"]["raw_file_keys"]

    all_texts = {}
    errors = []

    for file_key in raw_file_keys:
        full_key = f"{s3_prefix}{file_key}"
        filename = file_key.split("/")[-1]
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        logger.info(f"Processing file: {full_key} (type: {extension})")

        try:
            if extension in ("txt",):
                text = extract_text_plain(full_key)
            elif extension in ("pdf", "png", "jpg", "jpeg", "tiff", "tif"):
                text = extract_text_textract(full_key)
            elif extension in ("docx",):
                text = extract_text_docx(full_key)
            else:
                logger.warning(f"Unsupported file type: {extension} for {filename}")
                errors.append({"file": filename, "error": f"Unsupported format: {extension}"})
                continue

            all_texts[filename] = {
                "text": text,
                "source_key": file_key,
                "characters": len(text),
            }
            logger.info(f"Extracted {len(text)} characters from {filename}")

        except Exception as e:
            logger.error(f"Failed to extract text from {filename}: {e}")
            errors.append({"file": filename, "error": str(e)})

    # Write combined output to S3
    output_key = f"{s3_prefix}temp_processing/raw_text.json"
    output_data = {
        "files": all_texts,
        "errors": errors,
        "total_characters": sum(f["characters"] for f in all_texts.values()),
    }

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(output_data, ensure_ascii=False),
        ContentType="application/json",
    )

    logger.info(f"OCR output written to s3://{BUCKET_NAME}/{output_key}")

    # Build step result
    ocr_result = {
        "raw_text_key": "temp_processing/raw_text.json",
        "files_processed": len(all_texts),
        "files_failed": len(errors),
        "total_characters": output_data["total_characters"],
    }

    if errors:
        ocr_result["errors"] = errors

    # Return updated state for Step Functions
    event.setdefault("step_results", {})
    event["step_results"]["ocr"] = ocr_result
    return event


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


def extract_text_plain(s3_key: str) -> str:
    """Read a .txt file directly from S3."""
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    raw_bytes = response["Body"].read()

    # Try UTF-8 first, fall back to latin-1
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")


def extract_text_textract(s3_key: str) -> str:
    """
    Extract text from PDFs/images using AWS Textract.
    Uses synchronous API for single-page docs, async for multi-page PDFs.
    """
    _, ext = os.path.splitext(s3_key)
    ext = ext.lower()

    if ext == ".pdf":
        return _textract_async(s3_key)
    else:
        # Images: use synchronous detect_document_text
        return _textract_sync(s3_key)


def _textract_sync(s3_key: str) -> str:
    """Synchronous Textract for single-page images."""
    response = textract_client.detect_document_text(
        Document={"S3Object": {"Bucket": BUCKET_NAME, "Name": s3_key}}
    )

    lines = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block["Text"])

    return "\n".join(lines)


def _textract_async(s3_key: str) -> str:
    """Async Textract for multi-page PDFs. Polls until complete."""
    import time

    # Start async job
    response = textract_client.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": BUCKET_NAME, "Name": s3_key}}
    )
    job_id = response["JobId"]
    logger.info(f"Textract async job started: {job_id}")

    # Poll for completion (Lambda has up to 15 min)
    while True:
        result = textract_client.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]

        if status == "SUCCEEDED":
            break
        elif status == "FAILED":
            error = result.get("StatusMessage", "Unknown Textract error")
            raise RuntimeError(f"Textract job failed: {error}")

        time.sleep(2)

    # Collect all pages
    lines = []
    next_token = None

    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token

        result = textract_client.get_document_text_detection(**kwargs)

        for block in result.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block["Text"])

        next_token = result.get("NextToken")
        if not next_token:
            break

    return "\n".join(lines)


def extract_text_docx(s3_key: str) -> str:
    """
    Extract text from a .docx file stored in S3.
    Downloads to /tmp/ (Lambda writable dir) and parses with python-docx.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    # Download to /tmp
    tmp_path = f"/tmp/{s3_key.split('/')[-1]}"
    s3_client.download_file(BUCKET_NAME, s3_key, tmp_path)

    # Parse DOCX (it's a ZIP containing XML) — avoids python-docx dependency
    paragraphs = []
    try:
        with zipfile.ZipFile(tmp_path, "r") as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                root = tree.getroot()
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

                for para in root.iter(f"{{{ns['w']}}}p"):
                    texts = [
                        node.text
                        for node in para.iter(f"{{{ns['w']}}}t")
                        if node.text
                    ]
                    if texts:
                        paragraphs.append("".join(texts))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return "\n".join(paragraphs)
