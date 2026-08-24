import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_create_task(client: TestClient) -> None:
    payload = {
        "title": "Fix login validation bug",
        "description": "Invalid credentials should return HTTP 401.",
        "repository_path": r"C:\projects\sample-api",
    }

    response = client.post(
        "/api/v1/tasks",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["repository_path"] == payload["repository_path"]
    assert data["status"] == "created"

    uuid.UUID(data["id"])


def test_list_tasks(client: TestClient) -> None:
    first_task = {
        "title": "First task",
        "description": "First test task",
        "repository_path": r"C:\projects\first",
    }

    second_task = {
        "title": "Second task",
        "description": "Second test task",
        "repository_path": r"C:\projects\second",
    }

    client.post("/api/v1/tasks", json=first_task)
    client.post("/api/v1/tasks", json=second_task)

    response = client.get("/api/v1/tasks")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    titles = {task["title"] for task in data}

    assert titles == {"First task", "Second task"}


def test_get_task_by_id(client: TestClient) -> None:
    payload = {
        "title": "Get task test",
        "description": "Test retrieving a task by ID",
        "repository_path": r"C:\projects\sample",
    }

    create_response = client.post(
        "/api/v1/tasks",
        json=payload,
    )

    task_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/tasks/{task_id}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["title"] == payload["title"]


def test_get_unknown_task_returns_404(
    client: TestClient,
) -> None:
    unknown_task_id = uuid.uuid4()

    response = client.get(
        f"/api/v1/tasks/{unknown_task_id}",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_empty_title_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "title": "",
        "description": "Invalid task",
        "repository_path": r"C:\projects\sample",
    }

    response = client.post(
        "/api/v1/tasks",
        json=payload,
    )

    assert response.status_code == 422


def test_empty_repository_path_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "title": "Invalid repository",
        "description": "Repository path cannot be empty",
        "repository_path": "",
    }

    response = client.post(
        "/api/v1/tasks",
        json=payload,
    )

    assert response.status_code == 422