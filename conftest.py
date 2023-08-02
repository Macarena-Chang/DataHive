import pytest
from fastapi.testclient import TestClient

from app import app
from chat.websocket_manager import handle_websocket

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
    response = client.post("/users/login", data=user_credentials)
    assert response.status_code == 200
    return response.json()["access_token"]
