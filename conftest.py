from fastapi.testclient import TestClient
import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c