import logging
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch

import pytest
import redis
from fastapi.testclient import TestClient
from fastapi_limiter import FastAPILimiter
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import app
from app import get_token_blacklist
from models import Base
from models import UserTable

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False,
                                   autoflush=False,
                                   bind=engine)

Base.metadata.create_all(bind=engine)

# URL Redis server (using real redis service)
REDIS_URL = "redis://localhost:6380"

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def mock_limiter():
    with patch("fastapi_limiter.depends.FastAPILimiter",
               new_callable=AsyncMock):
        yield


def setup_module(module):
    # run before the first test
    r = redis.from_url(REDIS_URL, encoding="utf8")
    FastAPILimiter.init(r)


def test_login():
    # Test successful login
    user_credentials = {
        "username": "macarena@mail.com",
        "password": "secret",
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


def test_logout():
    # Setup: Initialize app.state.token_blacklist with a mock
    app.state.token_blacklist = AsyncMock()

    # First, log in to get a token
    user_credentials = {
        "username": "macarena@mail.com",
        "password": "secret",
    }
    response = client.post("/users/login", data=user_credentials)
    assert response.status_code == 200
    token = response.json()["access_token"]
    logging.info(f"Logged in, received token: {token}")

    # Mock Redis connection and TokenBlacklist methods
    with patch("redis.from_url", return_value=MagicMock()), \
            patch("models.TokenBlacklist.add", return_value=None), \
            patch("models.TokenBlacklist.is_blacklisted", new_callable=AsyncMock, return_value=False), \
            patch("redis.Redis.setex", return_value=None):

        # Then, use the token to log out
        response = client.post("/users/logout",
                               headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}
    logging.info("Logged out, token blacklisted")

    # Mock TokenBlacklist.is_blacklisted to return True
    with patch("models.TokenBlacklist.is_blacklisted", new_callable=AsyncMock, return_value=True):
        # Try to access a protected endpoint with the blacklisted token
        response = client.get("/users/me/",
                              headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    logging.info("Access with blacklisted token denied")
    # Teardown: Clean up the dependency override after the test
    app.dependency_overrides = {}