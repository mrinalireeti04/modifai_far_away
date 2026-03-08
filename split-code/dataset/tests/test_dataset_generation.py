from unittest.mock import patch, MagicMock
from modifai.core.dataset_generation import generate_samples_for_chunk

@patch("boto3.client")
def test_dataset_generation_mocked(mock_boto_client):
    # Mocking Bedrock response
    mock_client = MagicMock()
    mock_boto_client.return_value = mock_client
    
    mock_response = {
        'output': {
            'message': {
                'content': [{
                    'text': '[{"instruction": "Q1", "input": "", "response": "A1"}, {"instruction": "Q2", "input": "", "response": "A2"}]'
                }]
            }
        }
    }
    
    # Let converse return the mocked JSON response
    mock_client.converse.return_value = mock_response
    
    chunk = {"chunk_id": 1, "text": "Some text."}
    samples = generate_samples_for_chunk(chunk, "QA", 2, "us-east-1", "test-model")
    
    assert len(samples) == 2
    assert samples[0]["chunk_id"] == 1
    assert samples[1]["instruction"] == "Q2"
