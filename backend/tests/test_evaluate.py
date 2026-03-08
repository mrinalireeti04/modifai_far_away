"""Tests for the data evaluation endpoint."""
import pytest


@pytest.mark.asyncio
async def test_evaluate_text_sample(client):
    resp = await client.post("/evaluate/", json={
        "text_sample": "This is a sample document about machine learning concepts.",
        "intent": "question-answering",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "explanation" in data
    assert 0 <= data["score"] <= 1
    assert len(data["explanation"]) > 0


@pytest.mark.asyncio
async def test_evaluate_missing_fields(client):
    resp = await client.post("/evaluate/", json={
        "text_sample": "",
        "intent": "",
    })
    assert resp.status_code == 400
