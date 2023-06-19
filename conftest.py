from fastapi.testclient import TestClient
import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def token(client):
    user_credentials = {
        "username": "@mail.com",
        "password": "",
    }
    response = client.post("/login", data=user_credentials)
    assert response.status_code == 200
    return response.json()["access_token"]