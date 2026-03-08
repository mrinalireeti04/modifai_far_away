from modifai.core.quality_control import remove_duplicates, score_and_filter_dataset

def test_remove_duplicates():
    dataset = [
        {"instruction": "What is AI?", "input": "", "response": "Artificial Intelligence"},
        {"instruction": "What is AI?", "input": "", "response": "Artificial Intelligence"},
        {"instruction": "What is ML?", "input": "", "response": "Machine Learning"}
    ]
    
    unique_dataset = remove_duplicates(dataset)
    assert len(unique_dataset) == 2
    
def test_score_and_filter():
    chunks = [{"chunk_id": 1, "text": "Artificial intelligence allows machines to learn."}]
    
    dataset = [
        # Good sample - overlaps with chunk
        {"chunk_id": 1, "instruction": "What?", "input": "", "response": "Artificial intelligence learn machines."},
        # Bad sample - short, low overlap, generic
        {"chunk_id": 1, "instruction": "What?", "input": "", "response": "AI"}
    ]
    
    filtered = score_and_filter_dataset(dataset, chunks, threshold=0.4)
    assert len(filtered) == 1
    assert "machines" in filtered[0]["response"]
