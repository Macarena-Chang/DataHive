from datetime import datetime
from datetime import timedelta
from typing import Annotated
from typing import Optional

import yaml
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter.depends import RateLimiter
from itsdangerous import SignatureExpired
from jose import jwt
from jose import JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from email_service import send_verification_email
from models import User
from models import UserIn
from models import UserInDB
from models import UserOut
from models import UserTable
from token_service import create_token
from token_service import verify_token

router = APIRouter()

# User-Routes

# Load configuration from YAML file


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")

# Define input models for endpoints


class ChatInput(BaseModel):
    user_input: str
    file_name: Optional[str] = None


class SearchQuery(BaseModel):
    search_query: str


class DeleteRequest(BaseModel):
    file_name: str


class SummaryRequest(BaseModel):
    text: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


### AUTHENTICATION ###
# to get string like this run:
# openssl rand -hex 32
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    return db.query(UserTable).filter(UserTable.username == username).first()


def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False

    if user.is_verified != True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account Not Verified"
        )
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config["SECRET_KEY"], algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


# checks if authenticated user is active (checks disabled attribute)


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


#### GET MY USER INFO ####
@router.get("/users/me/", response_model=UserOut)
async def read_users_me(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    return current_user.to_dict()


##### LOGIN #####


@router.post(
    "/users/login",
    dependencies=[Depends(RateLimiter(times=10, seconds=480))],
    response_model=Token,
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


##### REGISTER #####
@router.post("/register", response_model=UserOut)
async def create_user(user: UserIn, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = UserTable(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        disabled=user.disabled,
    )
    db.add(db_user)
    try:
        db.commit()
        # After commiting the user to the database create a token for the user and send verification email
        token = create_token({"user_id": db_user.user_id})
        await send_verification_email(db_user.email, token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Username or Email already registered"
        )

    # Return 200 status code verify email message and user info
    return JSONResponse(
        status_code=200,
        content={
            "detail": "User registered successfully. Please verify your email.",
            "user": db_user.to_dict(),
        },
    )


##### ACCOUNT EMAIL VERIFICATION #####


@router.get("/verify")
def verify(token: str, db: Session = Depends(get_db)):
    try:
        data = verify_token(token, 86400)  # verify the token
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Token expired")
    user_id = data["user_id"]
    user = db.query(UserTable).filter(UserTable.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")
    user.is_verified = True
    db.commit()
    return {"detail": "User successfully verified"}
