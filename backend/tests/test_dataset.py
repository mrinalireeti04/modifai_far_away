"""Tests for dataset review endpoints (list, edit, delete, search, export)."""
import pytest


@pytest.mark.asyncio
async def test_get_dataset(client):
    # Create project
    create_resp = await client.post("/projects/", json={"name": "Dataset Test"})
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/dataset")
    assert resp.status_code == 200
    data = resp.json()
    assert "dataset" in data
    assert isinstance(data["dataset"], list)
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_update_dataset_example(client):
    create_resp = await client.post("/projects/", json={"name": "Edit Test"})
    project_id = create_resp.json()["id"]

    resp = await client.put(f"/projects/{project_id}/dataset/0", json={
        "instruction": "Updated instruction",
        "response": "Updated response",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_dataset_example(client):
    create_resp = await client.post("/projects/", json={"name": "Delete Test"})
    project_id = create_resp.json()["id"]

    resp = await client.delete(f"/projects/{project_id}/dataset/0")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_dataset(client):
    create_resp = await client.post("/projects/", json={"name": "Search Test"})
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/dataset/search?q=AI")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_export_dataset(client):
    create_resp = await client.post("/projects/", json={"name": "Export Test"})
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/dataset/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "download_url" in data
    assert data["download_url"].startswith("https://")
