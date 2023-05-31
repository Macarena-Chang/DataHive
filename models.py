from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel

Base = declarative_base()

class UserTable(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name =Column(String, unique=False, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    disabled = Column(Boolean, default=False)
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "disabled": self.disabled,
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
class File(Base):
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, unique=True, index=True)
    # Add other if neccesary


class UserFile(Base):
    __tablename__ = "user_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    file_id = Column(String, ForeignKey("files.file_id"), unique=True)

