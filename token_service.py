from itsdangerous import URLSafeTimedSerializer
from email_config import settings

s = URLSafeTimedSerializer(settings.SECRET_KEY)

def create_token(data: dict) -> str:
    return s.dumps(data)

def verify_token(token: str, max_age: int) -> dict:
    return s.loads(token, max_age=max_age)
