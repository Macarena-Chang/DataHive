import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
import json
import yaml


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


def read_text_file(file_path: str) -> str:
    with open(file_path, "r") as file:
        text = file.read()
    return text.replace('\n', ' ').replace('\\n', ' ')


def split_text_data(text: str) -> list:
    # Ssplit text into chunks 
    char_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return char_text_splitter.split_text(text)

def generate_embeddings(chunks: list) -> list:
    embeddings = []
    for chunk in chunks:
        response = openai.Embedding.create(input=chunk, model="text-embedding-ada-002")
        embeddings.append(response["data"][0]["embedding"])
    return embeddings


def store_embeddings(chunks: list, embeddings: list, file_unique_id: str) -> dict:
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


if __name__ == "__main__":
    config = load_config("config.yaml")

    openai_key = config["openai_key"]
    pinecone_api_key = config["pinecone_api_key"]
    pinecone_environment = config["pinecone_environment"]
    pinecone_index_name = config["pinecone_index_name"]

    openai.api_key = openai_key
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)

    file_path = "python9-classes.txt"
    my_string = read_text_file(file_path)
    my_chunks = split_text_data(my_string)

    file_unique_id = str(uuid.uuid4())
    pinecone_store = pinecone.Index(pinecone_index_name)

    embeddings = generate_embeddings(my_chunks)
    id_to_text_mapping = store_embeddings(my_chunks, embeddings, file_unique_id)

    save_mapping_to_file(id_to_text_mapping, f"{file_unique_id}.json")
    print(id_to_text_mapping)
