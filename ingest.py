import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
import json
import yaml
import docx
import nltk
import zipfile
from xml.etree import ElementTree as ET
import re
from nltk.tokenize import TextTilingTokenizer
from pdfminer.high_level import extract_text
from typing import List
# nltk.download("stopwords")
# nltk.download("punkt")


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


# 3200 is aprox 1042 tokens
# Text Tiling
def split_text_data(text: str, max_chars: int = 3200) -> list:
    # initialize TextTilingTokenizer
    ttt = TextTilingTokenizer()

    # check if text too short
    if len(text) < ttt.w * 2:  # w = default block size (usually 50)
        return [text]

    try:
        # tokenize the text into pseudo sentences (adjust parameters if necessary)
        pseudo_sentences = nltk.sent_tokenize(text, language="english")

        # Concatenate pseudo sentences
        concatenated_pseudo_sentences = ' '.join(pseudo_sentences)

        # Apply text tiling on concatenated pseudo sentences
        chunks = ttt.tokenize(concatenated_pseudo_sentences)

        # remove double new lines from chunks
        chunks = [chunk.lstrip('\n\n') for chunk in chunks]

        if len(chunks) <= 1:
            raise ValueError("Too few chunks")

      # Split chunks that exceed the maximum character limit
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            if len(chunk) > max_chars:
                # split the chunk into smaller subchunks
                num_subchunks = (len(chunk) // max_chars) + 1
                subchunks = [
                    chunk[j * max_chars:(j + 1) * max_chars] for j in range(num_subchunks)]
                chunks.pop(i)
                for subchunk in reversed(subchunks):
                    chunks.insert(i, subchunk)
            i += 1

    except ValueError as e:
        print(f"TextTiling exception: {e}")

        # Fallback to RecursiveCharacterTextSplitter
        char_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200)
        chunks = char_text_splitter.split_text(text)
        print("RecursiveCharacterTextSplitter")
        print(chunks)
    return chunks


def generate_embeddings(chunks: list) -> list:
    embeddings = []
    for chunk in chunks:
        response = openai.Embedding.create(
            input=chunk, model="text-embedding-ada-002")
        embeddings.append(response["data"][0]["embedding"])
    return embeddings


def store_embeddings(chunks: list, embeddings: list, file_unique_id: str, pinecone_store, file_name) -> dict:
    id_to_text_mapping = {}
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_unique_id = f"{file_unique_id}_{idx}"
        metadata = {'chunk': idx, 'text': chunk,
                    'file_id': file_unique_id, 'file_name': file_name}
        id_to_text_mapping[chunk_unique_id] = metadata
        pinecone_store.upsert(vectors=zip(
            [chunk_unique_id], [embedding], [metadata]))
    return id_to_text_mapping


def save_mapping_to_file(mapping: dict, file_name: str):
    with open(file_name, "w") as outfile:
        json.dump(mapping, outfile)

 # Extract text using pdfminer six


def extract_text_from_pdf(file_path: str) -> str:
    text = extract_text(file_path)
    return text


# .docx file is a ZIP archive containing multiple files. Opening it as a ZIP allows us to access the xml file that contains the  text
def extract_text_from_docx(file_path: str) -> str:
    # Open the .docx file as a ZIP archive
    with zipfile.ZipFile(file_path, 'r') as z:
        # Extract the 'word/document.xml' file
        xml_content = z.read('word/document.xml').decode()

        # Parse the XML content
        tree = ET.fromstring(xml_content)

        # Find all paragraph elements
        paragraphs = tree.findall(
            './/w:p', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

        # Extract the text from the 'w:t' elements within each paragraph and join them with newline characters
        text = '\n\n'.join(''.join(node.text for node in para.findall(
            './/w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})) for para in paragraphs)

        # Replace carriage returns and line feeds with newline characters
        text = re.sub(r'\r|\f', '\n', text)

    return text


""" def extract_text_from_doc(file_path: str) -> str:
    text = textract.process(file_path).decode('utf-8')
    return text
 """


def ingest_files(file_paths: List[str]):
    config = load_config("config.yaml")

    openai_key = config["openai_key"]
    pinecone_api_key = config["pinecone_api_key"]
    pinecone_environment = config["pinecone_environment"]

    openai.api_key = openai_key
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)

   
    text_extraction_functions = {
        'pdf': extract_text_from_pdf,
        'docx': extract_text_from_docx,
        # 'doc': extract_text_from_doc,
        'txt': lambda path: open(path, 'r').read()
    }
    for file_path in file_paths:
        file_extension = file_path.lower().split('.')[-1]
        file_content = text_extraction_functions.get(file_extension)(file_path)

        text = file_content
        chunks = split_text_data(text)

        file_unique_id = str(uuid.uuid4())
        pinecone_store = pinecone.Index(config["pinecone_index_name"])

        embeddings = generate_embeddings(chunks)

        file_name = file_path

        id_to_text_mapping = store_embeddings(
            chunks, embeddings, file_unique_id, pinecone_store, file_name)

        save_mapping_to_file(id_to_text_mapping, f"{file_unique_id}.json")
    return {"message": "File processed successfully.", "file_unique_id": file_unique_id}

#file_paths = ['1.txt',  '2.docx','3.pdf']

#ingest_files(file_paths)


