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
from models import User, UserIn, UserInDB, UserOut, UserTable
from token_service import create_token, verify_token
from fastapi import APIRouter
from models import TokenBlacklist
import uuid
import json 
from redis_config import get_redis, get_token_blacklist
from chat.chat_utils import limit_chat_history
from chat.chat_with_data import chat_ask_question
router = APIRouter()

# Load configuration from YAML file


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")


# models
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
ALGORITHM = config["ALGORITHM"]
ACCESS_TOKEN_EXPIRE_MINUTES = config["ACCESS_TOKEN_EXPIRE_MINUTES"]

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Account Not Verified")
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], token_blacklist: TokenBlacklist = Depends(get_token_blacklist),
                           db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti is None:
            raise credentials_exception
        # token_blacklist = TokenBlacklist()
        if await token_blacklist.is_blacklisted(jti):
            raise credentials_exception
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
def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=403, detail="Inactive user")
    return current_user

from db import add_file_to_user, get_user_files
#### GET MY USER INFO ####
@router.get("/users/me/", response_model=UserOut)
async def read_users_me(
        current_user: Annotated[UserInDB,
                                Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    return current_user.to_dict()

# LOGIN #####
@router.post(
    "/users/login",
    dependencies=[Depends(RateLimiter(times=10, seconds=480))],
    response_model=Token,
)
async def login(
        form_data: Annotated[OAuth2PasswordRequestForm,
                             Depends()],
        db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(
            status_code=403, detail="Inactive user - User Disabled")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username},
                                       expires_delta=access_token_expires)
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
        raise HTTPException(status_code=400,
                            detail="Username or Email already registered")

    # Return 200 status code verify email message and user info
    return JSONResponse(
        status_code=200,
        content={
            "detail":
            "User registered successfully. Please verify your email.",
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

from fastapi import Depends
from models import TokenBlacklist
from sqlalchemy.orm import Session
import logging

#### LOGOUT ####
@router.post("/users/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        redis_connection = await get_redis()
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti is None or exp is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        token_blacklist = TokenBlacklist(redis_connection)
        await token_blacklist.add(jti, exp)
        logging.info(f"Added token {jti} to blacklist")
        return JSONResponse(content={"message": "Successfully logged out"}, status_code=200)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/files")
async def get_file_names():
    with open("filenames.json", "r") as file:
        file_data = json.load(file)
    print("Filenames")
    file_names = list(file_data.keys())
    print(file_names)
    return JSONResponse(content=file_names)

@router.post("/users/addfile/")
async def add_file_to_user_endpoint(
        file_id: str,
        current_user: Annotated[UserInDB,
                                Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    return add_file_to_user(db, current_user.user_id, file_id)


@router.get("/users/me/files/")
async def get_user_files_endpoint(
        current_user: Annotated[UserInDB,
                                Depends(get_current_active_user)] = None,
        db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401,
                            detail="User is not authenticated")
    return get_user_files(db, current_user.user_id)

@router.post("/users/me/chat/responses")
async def chat_ask(
        chat_input: ChatInput,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
       
):
    try:
        user_id = current_user.user_id
        print(user_id)
        r = await get_redis()
        # Fetch chat history
        chat_history_redis = await r.lrange(f"chat:{user_id}", 0, -1)

        chat_history_redis = [
            json.loads(message.decode("utf-8"))
            for message in chat_history_redis
        ]
        # Generate response from language model
        response = chat_ask_question(chat_input.user_input, chat_history_redis,
                                     chat_input.file_name)

        # Limit chat history to a certain number of tokens
        chat_history_redis = await limit_chat_history(chat_history_redis,
                                                      response)

        # Store bot's response in Redis
        response_str = json.dumps({"user": "bot", "message": response})
        await r.rpush(f"chat:{user_id}", response_str)

        return {"response": response}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Unable to process the request.")
