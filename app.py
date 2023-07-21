import json
import os
from datetime import datetime
from datetime import timedelta
from typing import Annotated
from typing import Dict
from typing import List
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_limiter import FastAPILimiter
from ingest import ingest_files
from jose import JWTError, jwt
from models import User, UserTable, UserInDB
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated, Dict, List, Optional
from database import SessionLocal
from chat_with_data import chat_ask_question
from db import add_file_to_user, get_user_files
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocket
from redis import asyncio as redis
from chat_utils import limit_chat_history

from user_routes import router as user_router

app = FastAPI()

app.include_router(user_router)

# TODO finish refactor -> create file_router

# Configure CORS middleware
origins = ["http://localhost:3000", "localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration from YAML file


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Declare redis_connection as a global variable
redis_connection = None
# TODO delete Jinja2 templates
# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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


##### RESOURCE: FILES #####
@app.post("/files")
async def upload_files(files: List[UploadFile] = File(...)):
    message = None
    file_paths = []
    for uploaded_file in files:
        filename = uploaded_file.filename
        file_path = os.path.join("uploads", filename)
        with open(file_path, "wb") as f:
            content = await uploaded_file.read()
            f.write(content)
        file_paths.append(file_path)
    if file_paths:
        ingest_files(file_paths)
        message = "File uploaded and ingested successfully."
    return {"message": message}


##### Get filenames (to populate dropdown) #####
@app.get("/files")
async def get_file_names():
    with open("filenames.json", "r") as file:
        file_data = json.load(file)
    print("Filenames")
    file_names = list(file_data.keys())
    print(file_names)
    return JSONResponse(content=file_names)


##### DELETE FILE #####


@app.post("/files/delete/{filename}")
async def delete_file(filename: str):
    message = "File deletion not implemented yet."
    # Change status code as per operation result
    return JSONResponse(content={"message": message}, status_code=200)



# to get string like this run:
# openssl rand -hex 32
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    return db.query(UserTable).filter(UserTable.username == username).first()


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],
                           db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token,
                             config["SECRET_KEY"],
                             algorithms=[ALGORITHM])
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
        current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# REDIS / LIMITER
##### REDIS  connection established when app starts up #####
@app.on_event("startup")
async def startup():
    global redis_connection
    redis_connection = await redis.from_url("redis://localhost")
    await FastAPILimiter.init(redis_connection)


async def get_redis():
    global redis_connection
    return redis_connection


class ConnectionManager:

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_message(self, message: str, user_id: str):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Get the global Redis connection and use it
            async with get_redis() as r:
                # Store message in Redis
                await r.lpush(f"chat:{user_id}", data)
            await manager.send_message(f"Message text was: {data}", user_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)


@app.post("/users/addfile/")
async def add_file_to_user_endpoint(
        file_id: str,
        current_user: Annotated[UserInDB,
                                Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    return add_file_to_user(db, current_user.user_id, file_id)


@app.get("/users/me/files/")
async def get_user_files_endpoint(
        current_user: Annotated[UserInDB,
                                Depends(get_current_active_user)] = None,
        db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401,
                            detail="User is not authenticated")
    return get_user_files(db, current_user.user_id)


# REDIS CHAT HISTORY


async def get_chat_history_redis(user_id: str):
    r = await get_redis()
    history = await r.lrange(f"chat:{user_id}", 0, -1)
    if history is None:
        return []
    print(history)
    return [message.decode("utf-8") for message in history]


@app.post("/users/me/chat/responses")
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
        raise HTTPException(status_code=500, detail="Unable to process the request.")


from models import TokenBlacklist
#### LOGOUT ####
@app.post("/users/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti is None or exp is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        blacklist = TokenBlacklist(redis_connection)
        blacklist.add(jti, exp)
        return {"detail": "Successfully logged out"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
