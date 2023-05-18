from fastapi import FastAPI, Request, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from ingest import ingest_files
from retrieve import search_and_chat
from chat_with_data import chat_ask_question
from summary import summarize
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from fastapi import Depends
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
import json
import os
import yaml

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

# Define endpoints
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse, status_code=200)
def chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
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

@app.post("/search")
def search(request: Request, search_query: SearchQuery):
    results = []
    if search_query.search_query:
        results = search_and_chat(search_query.search_query)
    return {"results": results}

@app.post("/chat_question")
def chat_ask(chat_input: ChatInput):
    try:
        response = chat_ask_question(chat_input.user_input, chat_input.file_name)
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to process the request.")

@app.get("/filenames_json")
async def serve_filenames_json():
    with open("filenames.json", "r") as file:
        file_data = json.load(file)
    print("Filenames")    
    file_names = list(file_data.keys())
    print(file_names) 
    return JSONResponse(content=file_names)

@app.post("/delete")
async def delete_file(request: Request, delete_request: DeleteRequest):
    message = None
    file_name = delete_request.file_name
    if file_name:
        # TODO: Implement search_documents_by_file_name, delete_document_by_unique_id, and remove_file_from_filenames_json
        # response = search_documents_by_file_name(index, query_embedding_tuple, file_name, top_k=5, include_metadata=True)
        #
        # if len(response) == 0:
        #     message = "File not found."
        # elif len(response) == 1:
        #     unique_id = response[0][0]
        #     delete_document_by_unique_id(index, unique_id)
        #     remove_file_from_filenames_json(file_name)
        #     message = "File deleted successfully."
        # else:
        #     message = "Multiple files with the same name were found. Please provide more information to delete the correct file."
        #     for r in response:
        #         message += f"\nFile: {r[1]['metadata']['file_name']} - Uploaded on: {r[1]['metadata']['upload_date']}"
        message = "File deletion not implemented yet."
    return templates.TemplateResponse("index.html", {"request": request, "message": message})

@app.get("/summary", response_class=HTMLResponse, status_code=200)
def chat(request: Request):
    return templates.TemplateResponse("summary.html", {"request": request})

@app.post("/summary")
def summary(request: Request, background_tasks: BackgroundTasks, summary_request: SummaryRequest):
    summary = None
    if summary_request.text:
        summary = summarize(summary_request.text)
        background_tasks.add_task(summarize, summary_request.text)
    return JSONResponse(content={"summary": summary})




################################################################
### AUTHENTICATION ###
################################################################
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from database import SessionLocal
from models import User, UserTable,UserIn, UserInDB, UserOut
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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



async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@app.post("/token",dependencies=[Depends(RateLimiter(times=10, seconds=480))], response_model=Token)
async def login_for_access_token(
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

@app.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return [{"item_id": "Foo", "owner": current_user.username}]

#REDIS / LIMITER
@app.on_event("startup")
async def startup():
    r = redis.from_url(config["REDIS_URL"], encoding="utf8")
    await FastAPILimiter.init(r)
