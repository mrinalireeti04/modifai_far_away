"""
Chunking Lambda — Splits extracted text into overlapping semantic chunks.

Input (from Step Functions — output of OCR step):
{
    ...state,
    "step_results": {
        "ocr": {
            "raw_text_key": "temp_processing/raw_text.json",
            ...
        }
    }
}

Output:
{
    ...state,
    "step_results": {
        ...state.step_results,
        "chunking": {
            "chunks_key": "temp_processing/chunks.json",
            "chunk_count": 42,
            "total_words": 18500
        }
    }
}
"""

import json
import os
import re
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "modifai-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

# Defaults (can be overridden via event config)
DEFAULT_MAX_WORDS = 500
DEFAULT_MIN_WORDS = 50
DEFAULT_OVERLAP_WORDS = 50


def handler(event, context):
    """Lambda entry point for the chunking step."""
    logger.info(f"Chunking Lambda invoked for project: {event.get('project_id')}")

    s3_prefix = event["s3_prefix"]
    config = event.get("config", {})

    max_words = config.get("max_chunk_words", DEFAULT_MAX_WORDS)
    min_words = config.get("min_chunk_words", DEFAULT_MIN_WORDS)
    overlap_words = config.get("overlap_words", DEFAULT_OVERLAP_WORDS)

    # 1. Read OCR output from S3
    raw_text_key = f"{s3_prefix}{event['step_results']['ocr']['raw_text_key']}"
    logger.info(f"Reading OCR output from s3://{BUCKET_NAME}/{raw_text_key}")

    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=raw_text_key)
    raw_text_data = json.loads(response["Body"].read().decode("utf-8"))

    # 2. Chunk each file separately
    all_chunks = []
    chunk_id = 1
    total_words = 0

    for filename, file_data in raw_text_data.get("files", {}).items():
        text = file_data.get("text", "")
        if not text.strip():
            logger.warning(f"Skipping empty file: {filename}")
            continue

        file_chunks = create_chunks(
            text=text,
            max_words=max_words,
            min_words=min_words,
            overlap_words=overlap_words,
        )

        # Assign global chunk_ids and source_file
        for chunk in file_chunks:
            chunk["chunk_id"] = chunk_id
            chunk["source_file"] = filename
            chunk_id += 1
            total_words += chunk["word_count"]

        all_chunks.extend(file_chunks)
        logger.info(f"  {filename}: {len(file_chunks)} chunks")

    logger.info(f"Total chunks created: {len(all_chunks)} ({total_words} words)")

    # 3. Write chunks to S3
    output_key = f"{s3_prefix}temp_processing/chunks.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(all_chunks, ensure_ascii=False),
        ContentType="application/json",
    )

    logger.info(f"Chunks written to s3://{BUCKET_NAME}/{output_key}")

    # 4. Return updated state
    event.setdefault("step_results", {})
    event["step_results"]["chunking"] = {
        "chunks_key": "temp_processing/chunks.json",
        "chunk_count": len(all_chunks),
        "total_words": total_words,
    }
    return event


# ---------------------------------------------------------------------------
# Chunking logic
# ---------------------------------------------------------------------------

# Sentence boundary regex: split after . ! ? followed by whitespace
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    sentences = SENTENCE_SPLIT_RE.split(text.strip())
    # Filter out empty strings
    return [s.strip() for s in sentences if s.strip()]


def create_chunks(
    text: str,
    max_words: int = DEFAULT_MAX_WORDS,
    min_words: int = DEFAULT_MIN_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[dict]:
    """
    Splits text into chunks with overlap.

    Algorithm:
    1. Split text into sentences
    2. Greedily pack sentences into chunks up to max_words
    3. When starting a new chunk, carry over last N words (overlap_words) from previous
    4. If the final chunk is smaller than min_words, merge it into the previous chunk
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())

        # Handle sentences longer than max_words: force-split them
        if sentence_words > max_words:
            # Flush current chunk first
            if current_sentences:
                chunks.append(_build_chunk(current_sentences))
                current_sentences = _get_overlap_sentences(
                    current_sentences, overlap_words
                )
                current_word_count = sum(
                    len(s.split()) for s in current_sentences
                )

            # Split the long sentence into sub-parts
            words = sentence.split()
            for i in range(0, len(words), max_words):
                sub_part = " ".join(words[i : i + max_words])
                chunks.append(_build_chunk([sub_part]))
            continue

        # Would adding this sentence exceed max_words?
        if current_word_count + sentence_words > max_words and current_sentences:
            # Save current chunk
            chunks.append(_build_chunk(current_sentences))

            # Start new chunk with overlap from previous
            current_sentences = _get_overlap_sentences(
                current_sentences, overlap_words
            )
            current_word_count = sum(len(s.split()) for s in current_sentences)

        current_sentences.append(sentence)
        current_word_count += sentence_words

    # Flush remaining sentences
    if current_sentences:
        chunks.append(_build_chunk(current_sentences))

    # Merge undersized final chunk into previous
    if len(chunks) > 1 and chunks[-1]["word_count"] < min_words:
        last = chunks.pop()
        # Append the last chunk's text to the previous chunk
        merged_text = chunks[-1]["text"] + " " + last["text"]
        chunks[-1]["text"] = merged_text
        chunks[-1]["word_count"] = len(merged_text.split())

    return chunks


def _build_chunk(sentences: list[str]) -> dict:
    """Build a chunk dict from a list of sentences."""
    text = " ".join(sentences)
    return {
        "chunk_id": 0,  # Will be assigned by the handler
        "text": text,
        "word_count": len(text.split()),
    }


def _get_overlap_sentences(
    sentences: list[str], overlap_words: int
) -> list[str]:
    """
    Return the trailing sentences from the list that together
    contain approximately `overlap_words` words.
    """
    if overlap_words <= 0:
        return []

    overlap = []
    word_count = 0

    for sentence in reversed(sentences):
        words = len(sentence.split())
        if word_count + words > overlap_words and overlap:
            break
        overlap.insert(0, sentence)
        word_count += words

    return overlap
