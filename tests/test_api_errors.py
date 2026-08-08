from fastapi.testclient import TestClient

from app.main import create_app


def test_not_found_uses_problem_details_response():
    client = TestClient(create_app())

    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Not Found"

