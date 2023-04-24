import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
import json
import yaml
import PyPDF2
import docx
import textract


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


def split_text_data(text: str) -> list:
    char_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return char_text_splitter.split_text(text)

def generate_embeddings(chunks: list) -> list:
    embeddings = []
    for chunk in chunks:
        response = openai.Embedding.create(input=chunk, model="text-embedding-ada-002")
        embeddings.append(response["data"][0]["embedding"])
    return embeddings


def store_embeddings(chunks: list, embeddings: list, file_unique_id: str, pinecone_store) -> dict:
    id_to_text_mapping = {}
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_unique_id = f"{file_unique_id}_{idx}"
        metadata = {'chunk': idx, 'text': chunk, 'file_id': file_unique_id}
        id_to_text_mapping[chunk_unique_id] = metadata
        pinecone_store.upsert(vectors=zip([chunk_unique_id], [embedding], [metadata]))
    return id_to_text_mapping


def save_mapping_to_file(mapping: dict, file_name: str):
    with open(file_name, "w") as outfile:
        json.dump(mapping, outfile)

def extract_text_from_pdf(file_path: str) -> str:
    pdf_file = open(file_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    numPages = len(pdf_reader.pages)
    text = ''
    for page_num in range (0, numPages):
        text += pdf_reader.pages[page_num].extract_text() 
    pdf_file.close()
    return text


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    text = ''
    for paragraph in doc.paragraphs:
        text += paragraph.text + '\n'
    return text


# def extract_text_from_doc(file_path: str) -> str:
#    text = textract.process(file_path).decode('utf-8')
#    return text


def ingest_file(file_path: str) -> dict:
    config = load_config("config.yaml")

    openai_key = config["openai_key"]
    pinecone_api_key = config["pinecone_api_key"]
    pinecone_environment = config["pinecone_environment"]

    openai.api_key = openai_key
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)


    file_extension = file_path.lower().split('.')[-1]
    text_extraction_functions = {
        'pdf': extract_text_from_pdf,
        'docx': extract_text_from_docx,
       # 'doc': extract_text_from_doc,
        'txt': lambda path: open(path, 'r').read()
    }

    file_content = text_extraction_functions.get(file_extension)(file_path)
    
    text = file_content.replace('\n', ' ').replace('\\n', ' ')
    chunks = split_text_data(text)

    file_unique_id = str(uuid.uuid4())
    pinecone_store = pinecone.Index(config["pinecone_index_name"])

    embeddings = generate_embeddings(chunks)
    id_to_text_mapping = store_embeddings(chunks, embeddings, file_unique_id, pinecone_store)

    save_mapping_to_file(id_to_text_mapping, f"{file_unique_id}.json")
    return {"message": "File processed successfully.", "file_unique_id": file_unique_id}
