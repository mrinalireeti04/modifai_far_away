"""Tests for project CRUD endpoints."""
import pytest


@pytest.mark.asyncio
async def test_create_project(client):
    resp = await client.post("/projects/", json={
        "name": "Test Project",
        "description": "A test project",
        "mode": "full",
        "intent": "question-answering",
        "base_model": "llama-3.1-8b",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Project"
    assert data["mode"] == "full"
    assert data["intent"] == "question-answering"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client):
    # Create two projects
    await client.post("/projects/", json={"name": "Project A"})
    await client.post("/projects/", json={"name": "Project B"})

    resp = await client.get("/projects/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    names = [p["name"] for p in data]
    assert "Project A" in names
    assert "Project B" in names


@pytest.mark.asyncio
async def test_get_project(client):
    # Create
    create_resp = await client.post("/projects/", json={"name": "Detail Project"})
    project_id = create_resp.json()["id"]

    # Get
    resp = await client.get(f"/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail Project"


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    resp = await client.get("/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client):
    # Create
    create_resp = await client.post("/projects/", json={"name": "To Delete"})
    project_id = create_resp.json()["id"]

    # Delete
    resp = await client.delete(f"/projects/{project_id}")
    assert resp.status_code == 200

    # Verify gone
    resp = await client.get(f"/projects/{project_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_project_defaults(client):
    """Test that default values are applied when optional fields are omitted."""
    resp = await client.post("/projects/", json={"name": "Minimal"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "full"
    assert data["status"] == "pending"
