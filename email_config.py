from pydantic import BaseSettings


class Settings(BaseSettings):
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_SERVER: str = ""
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True  # replaced MAIL_TLS with MAIL_STARTTLS
    MAIL_SSL_TLS: bool = False  # replaced MAIL_SSL with MAIL_SSL_TLS
    SECRET_KEY: str = ""


settings = Settings()
