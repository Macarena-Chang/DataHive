import logging
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import app
from email_service import send_verification_email
from models import Base, UserTable

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_create_user():
    with patch(
        "user_routes.send_verification_email", new_callable=AsyncMock
    ) as mock_send_verification_email:
        mock_send_verification_email.return_value = None

        # unique username and email using timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        username = f"newuser{timestamp}@example.com"
        email = username

        # Test creating new user
        user_data = {
            "username": username,
            "full_name": "New User",
            "email": email,
            "password": "newpassword",
            "disabled": False,
        }
        response = client.post("/register", json=user_data)

        # response content
        logging.info(response.content)

        assert response.status_code == 200

        # Check response contains correct username,name, email
        assert response.json()["user"]["username"] == username
        assert response.json()["user"]["full_name"] == "New User"
        assert response.json()["user"]["email"] == email

        assert "password" not in response.json()  # Ensure --> password isn't returned
        # Ensure --> email sending function was called
        assert mock_send_verification_email.called

        # Test duplicate user registration
        response = client.post("/register", json=user_data)
        assert response.status_code == 400
        assert "Username or Email already registered" in response.json()["detail"]


def teardown_module(module):
    logging.info("teardown_module called")

    # Delete new user we created
    db = TestingSessionLocal()
    new_user = db.query(UserTable).filter_by(username="newuser").first()
    if new_user:
        db.delete(new_user)
        db.commit()
        logging.info("User deleted")
    else:
        logging.info("User not found")
    db.close()
    logging.info("teardown_module finished")
