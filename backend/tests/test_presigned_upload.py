"""Tests for presigned upload URL endpoint."""
import pytest


@pytest.mark.asyncio
async def test_get_upload_url(client):
    # Create a project first
    create_resp = await client.post("/projects/", json={"name": "Upload Test"})
    project_id = create_resp.json()["id"]

    # Request upload URL
    resp = await client.post(f"/projects/{project_id}/upload-url?filename=test.pdf")
    assert resp.status_code == 200
    data = resp.json()
    assert "presigned_url" in data
    assert "file_key" in data
    assert data["presigned_url"].startswith("https://")


@pytest.mark.asyncio
async def test_get_upload_url_project_not_found(client):
    resp = await client.post("/projects/nonexistent/upload-url?filename=test.pdf")
    assert resp.status_code == 404
