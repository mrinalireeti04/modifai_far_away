"""Tests for the model comparison endpoint."""
import pytest


@pytest.mark.asyncio
async def test_compare_models(client):
    # Create a project
    create_resp = await client.post("/projects/", json={"name": "Compare Test", "mode": "full"})
    project_id = create_resp.json()["id"]

    # Start pipeline (sets execution_arn)
    await client.post(f"/projects/{project_id}/start", json={"config": {}})

    # Compare
    resp = await client.post("/compare/", json={
        "project_id": project_id,
        "prompt": "What is machine learning?",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "base_model" in data
    assert "fine_tuned" in data
    assert "response" in data["base_model"]
    assert "latency_ms" in data["base_model"]
    assert "model_id" in data["base_model"]


@pytest.mark.asyncio
async def test_compare_with_system_prompt(client):
    create_resp = await client.post("/projects/", json={"name": "Sys Prompt Test"})
    project_id = create_resp.json()["id"]

    resp = await client.post("/compare/", json={
        "project_id": project_id,
        "prompt": "Explain recursion",
        "system_prompt": "You are a CS professor",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_model"]["response"] != ""


@pytest.mark.asyncio
async def test_compare_project_not_found(client):
    resp = await client.post("/compare/", json={
        "project_id": "nonexistent",
        "prompt": "Hello",
    })
    assert resp.status_code == 404
