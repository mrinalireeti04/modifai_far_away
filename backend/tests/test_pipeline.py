"""Tests for pipeline execution endpoints (start, status, results, logs)."""
import pytest


@pytest.mark.asyncio
async def test_start_pipeline(client):
    # Create project
    create_resp = await client.post("/projects/", json={"name": "Pipeline Test", "mode": "full"})
    project_id = create_resp.json()["id"]

    # Start pipeline
    resp = await client.post(f"/projects/{project_id}/start", json={
        "config": {"intent": "question-answering", "samples_per_chunk": 5}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "execution_arn" in data
    assert data["message"] == "Pipeline started"


@pytest.mark.asyncio
async def test_get_project_status(client):
    # Create and start
    create_resp = await client.post("/projects/", json={"name": "Status Test"})
    project_id = create_resp.json()["id"]
    await client.post(f"/projects/{project_id}/start", json={"config": {}})

    # Check status
    resp = await client.get(f"/projects/{project_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline_status" in data
    assert "project_status" in data


@pytest.mark.asyncio
async def test_get_project_status_no_execution(client):
    """Project created but pipeline never started — should still return a status."""
    create_resp = await client.post("/projects/", json={"name": "No Exec"})
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_status"] == "NOT_STARTED"


@pytest.mark.asyncio
async def test_get_project_results(client):
    # Create and start
    create_resp = await client.post("/projects/", json={"name": "Results Test"})
    project_id = create_resp.json()["id"]
    await client.post(f"/projects/{project_id}/start", json={"config": {}})

    # Get results
    resp = await client.get(f"/projects/{project_id}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_get_project_logs(client):
    # Create and start
    create_resp = await client.post("/projects/", json={"name": "Logs Test"})
    project_id = create_resp.json()["id"]
    await client.post(f"/projects/{project_id}/start", json={"config": {}})

    # Get logs
    resp = await client.get(f"/projects/{project_id}/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)
