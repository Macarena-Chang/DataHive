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
from fastapi.responses import FileResponse
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