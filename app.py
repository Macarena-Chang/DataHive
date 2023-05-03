from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from ingest import ingest_files
from retrieve import search_and_chat
from chat_with_data import chat_ask_question
import yaml
#from doc_utils import search_documents_by_file_name, delete_document_by_unique_id, remove_file_from_filenames_json
from typing import List
from pydantic import BaseModel
from summary import summarize
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from typing import Optional


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)

config = load_config("config.yaml")


class ChatInput(BaseModel):
    user_input: str
    file_name: Optional[str] = None
    
    

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse, status_code=200)
def chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})
# TODO: check
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
        message = "Files uploaded and ingested successfully."

    return {"message": message}
# TODO: check
@app.post("/search")
async def search(request: Request, search_query: str):
    results = []
    if search_query:
        results = search_and_chat(search_query)
    return templates.TemplateResponse("index.html", {"request": request, "results": results})

# TODO: Add error handling for file uploads
@app.post("/chat_question") 
def chat_ask(chat_input: ChatInput):    
    response = chat_ask_question(chat_input.user_input, chat_input.file_name)
    return response
# TODO: check
@app.get("/filenames.json")
async def serve_filenames_json():
    return FileResponse('filenames.json', media_type='application/json')

class DeleteRequest(BaseModel):
    file_name: str

""" @app.post("/delete")
async def delete_file(request: Request, delete_request: DeleteRequest):
    message = None
    file_name = delete_request.file_name
    if file_name:
        response = search_documents_by_file_name(index, query_embedding_tuple, file_name, top_k=5, include_metadata=True)

        if len(response) == 0:
            message = "File not found."
        elif len(response) == 1:
            unique_id = response[0][0]
            delete_document_by_unique_id(index, unique_id)
            remove_file_from_filenames_json(file_name)
            message = "File deleted successfully."
        else:
            message = "Multiple files with the same name were found. Please provide more information to delete the correct file."
            for r in response:
                message += f"\nFile: {r[1]['metadata']['file_name']} - Uploaded on: {r[1]['metadata']['upload_date']}"

    return templates.TemplateResponse("index.html", {"request": request, "message": message}) """

class SummaryRequest(BaseModel):
    text: str

# TODO: check
@app.post("/summary", response_class=HTMLResponse)
async def get_summary(request: Request, summary_request: SummaryRequest = None):
    summary = None
    if summary_request and summary_request.text:
        text = summary_request.text
        summary = summarize(text)
    return templates.TemplateResponse("summary.html", {"request": request, "summary": summary})

