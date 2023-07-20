from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from email_config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
)


fm = FastMail(conf)


async def send_verification_email(email: str, token: str):
    verification_link = f"http://localhost:8000/verify?token={token}"
    message = MessageSchema(
        subject="Please verify your email",
        recipients=[email],
        body=f"Please click the link to verify your email: {verification_link}",
        subtype="plain"
    )
    await fm.send_message(message)
