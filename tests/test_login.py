from unittest.mock import patch
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from models import UserTable
from fastapi.testclient import TestClient
from fastapi_limiter import FastAPILimiter
from sqlalchemy import create_engine
from app import app
from models import Base
import redis


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


# URL Redis server
REDIS_URL = "redis://localhost:6380"

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def mock_limiter():
    with patch("fastapi_limiter.depends.FastAPILimiter", new_callable=AsyncMock):
        yield


def setup_module(module):
    # run before the first test
    r = redis.from_url(REDIS_URL, encoding="utf8")
    FastAPILimiter.init(r)


def test_login():
    # Test successful login
    user_credentials = {
        "username": "@mail.com",
        "password": "",
    }
    response = client.post("/users/login", data=user_credentials)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

    # Test login with incorrect password
    user_credentials = {
        "username": "macarena@mail.com",
        "password": "wrongpassword",
    }
    response = client.post("/users/login", data=user_credentials)
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

    # Test login with non-existent user
    user_credentials = {
        "username": "nonexistentuser@mail.com",
        "password": "secret",
    }
    response = client.post("/users/login", data=user_credentials)
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]
