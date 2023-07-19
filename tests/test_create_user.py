from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session
from models import UserTable
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app import app
from models import Base
import logging
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


client = TestClient(app)


    
def test_create_user():
    
    with patch("app.send_verification_email") as mock_send_verification_email:
        mock_send_verification_email.return_value = None  # Mock the email sending function

        # unique username and email using timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        username = f"newuser{timestamp}"
        email = f"newuser{timestamp}@example.com"
        
        # Test creating new user
        user_data = {
            "username": username,
            "full_name": "New User",
            "email": email,
            "password": "newpassword",
            "disabled": False,
        }
        response = client.post("/register", json=user_data)

        # Test creating new user with missing fields print(response.content)  # Print out the response content
        assert response.status_code == 200
        assert response.json()["username"] == username
        assert response.json()["full_name"] == "New User"
        assert response.json()["email"] == email
        assert "password" not in response.json()  # Ensure --> password isn't returned
        assert mock_send_verification_email.called  # Ensure --> email sending function was called

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
