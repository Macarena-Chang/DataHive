from pydantic import BaseModel
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserTable(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, unique=False, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "disabled": self.disabled,
            "is_verified": self.is_verified,
        }


class User(BaseModel):
    username: str
    email: str
    full_name: str
    disabled: bool


class UserIn(User):
    password: str


class UserOut(User):
    user_id: int


class UserInDB(User):
    hashed_password: str


from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint
""" class File(Base):
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, unique=True, index=True)
 """

class UserFile(Base):
    __tablename__ = "user_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    file_id = Column(String, ForeignKey("files.file_id"), unique=True)


# Model for blacklist tokens
import redis

class TokenBlacklist:
    def __init__(self, redis_connection):
        self.token_blacklist = redis_connection
    async def add(self, jti, exp):
        await self.token_blacklist.setex(f"blacklist_{jti}", exp, "true") # Use blacklist_ + unique id of JWT

    async def is_blacklisted(self, jti):
        result = await self.token_blacklist.exists(f"blacklist_{jti}")
        return result
    