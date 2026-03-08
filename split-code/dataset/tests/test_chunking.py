from modifai.core.chunking import create_chunks

def test_chunking_basic():
    text = "This is a sentence. This is another sentence. Here is a third one."
    
    # Test with a very small max words to force splitting
    chunks = create_chunks(text, max_words=5)
    
    assert len(chunks) > 1
    assert chunks[0]["chunk_id"] == 1
    assert "This is a sentence." in chunks[0]["text"]

def test_chunking_large_text():
    text = "Word " * 200
    chunks = create_chunks(text, max_words=100)
    
    assert len(chunks) == 2
    assert len(chunks[0]["text"].split()) == 100
    assert len(chunks[1]["text"].split()) == 100
    assert chunks[1]["chunk_id"] == 2
