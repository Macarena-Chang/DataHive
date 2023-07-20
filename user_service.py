from itsdangerous import SignatureExpired
from email_service import send_verification_email
from models import UserIn
from token_service import create_token, verify_token
from sqlalchemy.orm import Session
from fastapi import HTTPException


def register_user(user: UserIn, db: Session):
    # Your user registration logic here
    token = create_token({"user_id": user.id})
    send_verification_email(user.email, token)


def verify_user(token: str):
    try:
        data = verify_token(token, 86400)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Token expired")
    user_id = data["user_id"]
    # Mark the user as verified in your database
