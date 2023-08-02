import json
import os
from typing import Dict
from typing import List
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from ingest import ingest_files
from models import User
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from chat.chat_with_data import chat_ask_question

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocket
from chat.chat_utils import limit_chat_history, get_chat_history_redis
from user_routes import get_db, get_current_user
from user_routes import router as user_router
from redis_config import startup as redis_startup, get_redis
from chat.websocket_manager import handle_websocket

app = FastAPI()

app.include_router(user_router)


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

# REDIS
@app.on_event("startup")
async def startup_event():
    await redis_startup(app)
    

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await handle_websocket(websocket, user_id)
    

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


##### DELETE FILE #####
@app.post("/files/delete/{filename}")
async def delete_file(filename: str):
    message = "File deletion not implemented yet."
    # Change status code as per operation result
    return JSONResponse(content={"message": message}, status_code=200)


# to get string like this run:
# openssl rand -hex 32
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = config["ALGORITHM"]
ACCESS_TOKEN_EXPIRE_MINUTES = config["ACCESS_TOKEN_EXPIRE_MINUTES"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def get_password_hash(password):
    return pwd_context.hash(password)
