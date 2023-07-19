import json
import os
import yaml
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from ingest import ingest_files
from itsdangerous import SignatureExpired
from jose import JWTError, jwt
from models import User, UserTable, UserIn, UserInDB, UserOut, UserFile
from passlib.context import CryptContext
from pydantic import BaseModel
from retrieve import search_and_chat
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket as StarletteWebSocket
from summary import summarize
from token_service import create_token, verify_token
from typing import Annotated, Dict, List, Optional
from database import SessionLocal
from chat_with_data import chat_ask_question
from email_service import send_verification_email
from db import add_file_to_user, get_user_files
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocket
from redis import asyncio as redis
from chat_utils import limit_chat_history


app = FastAPI()

# Configure CORS middleware
origins = [
    "http://localhost:3000",
    "localhost:3000"
]

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
        file_path = os.path.join('uploads', filename)
        with open(file_path, 'wb') as f:
            content = await uploaded_file.read()
            f.write(content)
        file_paths.append(file_path)
    if file_paths:
        ingest_files(file_paths)
        message = "File uploaded and ingested successfully."
    return {"message": message}
##### SEARCH (Outside chat) #####
""" @app.post("/search")
def search(request: Request, search_query: SearchQuery):
    results = []
    if search_query.search_query:
        results = search_and_chat(search_query.search_query)
    return {"results": results}
 """
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
    return JSONResponse(content={"message": message}, status_code=200)  # Change status code as per operation result

""" @app.get("/summary", response_class=HTMLResponse, status_code=200)
def chat(request: Request):
    return templates.TemplateResponse("summary.html", {"request": request})
"""
##### GET SUMMARY ##### 
""" @app.post("/summary")
def summary(request: Request, background_tasks: BackgroundTasks, summary_request: SummaryRequest):
    summary = None
    if summary_request.text:
        summary = summarize(summary_request.text)
        background_tasks.add_task(summarize, summary_request.text)
    return JSONResponse(content={"summary": summary})
 """
################################################################
### AUTHENTICATION ###
################################################################

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
    
    if user.is_verified != True:raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED,detail= "Account Not Verified")
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
    token: Annotated[str, Depends(oauth2_scheme)], 
    db: Session = Depends(get_db)
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

#checks if authenticated user is active (checks disabled attribute)
async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

##### LOGIN #####
@app.post("/users/login",dependencies=[Depends(RateLimiter(times=10, seconds=480))], response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
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

@app.get("/users/me/", response_model=UserOut)
async def read_users_me(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db)
):
    return current_user.to_dict()

#REDIS / LIMITER
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

""" r = redis.from_url(config["REDIS_URL"], encoding="utf8") """
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Get the global Redis connection and use it
            async with get_redis() as r:
                await r.lpush(f"chat:{user_id}", data)  # Store message in Redis
            """ r.push(f"chat:{user_id}", data) """  # Store message in Redis
            await manager.send_message(f"Message text was: {data}", user_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        
##### REGISTER #####
@app.post("/register", response_model=UserOut)
async def create_user(user: UserIn, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = UserTable(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        disabled=user.disabled
    )
    db.add(db_user)
    try:
        db.commit()
        # After commiting the user to the database create a token for the user and send verification email
        token = create_token({"user_id": db_user.user_id})
        await send_verification_email(db_user.email, token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or Email already registered")
    return db_user.to_dict()

##### VERIFICATION ##### 
@app.get("/verify")
def verify_endpoint(token: str, db: Session = Depends(get_db)):
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


## SOCIAL LOGIN
""" from google.oauth2 import id_token
from google.auth.transport import requests
@app.get("/auth")
def authentication(request: Request,token:str):
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        user =id_token.verify_oauth2_token(token, requests.Request(), "116988546-2a283t6anvr0.apps.googleusercontent.com")

        request.session['user'] = dict({
            "email" : user["email"] 
        })
        
        return user['name'] + ' Logged In successfully'

    except ValueError:
        return "unauthorized"

@app.get('/')
def check(request:Request):
    return "hi "+ str(request.session.get('user')['email']) """

#router = APIRouter()
@app.post("/users/addfile/")
async def add_file_to_user_endpoint(
    file_id: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db)
):
    return add_file_to_user(db, current_user.user_id, file_id)

@app.get("/users/me/files/")
async def get_user_files_endpoint(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)] = None,
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="User is not authenticated")
    return get_user_files(db, current_user.user_id)

# REDIS 
async def get_chat_history_redis(user_id: str):
    r = await get_redis()
    history = await r.lrange(f'chat:{user_id}', 0, -1)
    if history is None:
        return []
    print(history)
    return [message.decode('utf-8') for message in history]

@app.post("/users/me/chat/responses")
async def chat_ask(chat_input: ChatInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user_id = current_user.user_id
        print(user_id)
        r = await get_redis()
        # Fetch chat history
        chat_history_redis = await r.lrange(f'chat:{user_id}', 0, -1)
        
        chat_history_redis = [json.loads(message.decode('utf-8')) for message in chat_history_redis] 
        # Generate response from language model
        response = chat_ask_question(chat_input.user_input, chat_history_redis, chat_input.file_name)

        # Limit chat history to a certain number of tokens
        chat_history_redis = await limit_chat_history(chat_history_redis, response)
        
        # Store bot's response in Redis
        response_str = json.dumps({"user": "bot", "message": response})
        await r.rpush(f'chat:{user_id}', response_str)

        return  {"response": response}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to process the request.")

