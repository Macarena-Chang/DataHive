import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
import json


# Set up API keys and configurations
openai_key = " "
pinecone_api_key = " "
pinecone_environment = " "
pinecone_index_name = " "

# Configure OpenAI and Pinecone
openai.api_key = openai_key
pinecone.init(api_key=pinecone_api_key, environment= pinecone_environment)

# Read text from a txt file and save it to a variable called "my_string"
file_path = "Python-Data-Structures.txt"
with open(file_path, "r") as file:
    my_string = file.read()
my_string.replace('\n', ' ')
my_string.replace('\\n', ' ')

# Split text of "my_string" variable into chunks and save the chunks to "my_chunks"
char_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
my_chunks = char_text_splitter.split_text(my_string)

# Generate a unique ID for the file
file_unique_id = str(uuid.uuid4())

# Initialize Pinecone vector store
pinecone_store = pinecone.Index(pinecone_index_name)

# Create a mapping between vector IDs and original text chunks
id_to_text_mapping = {}

# Store the embeddings of the chunks with their unique IDs in Pinecone
for idx, chunk in enumerate(my_chunks):
    # Generate a unique ID for each chunk
    chunk_unique_id = f"{file_unique_id}_{idx}"

    # Get the embedding for the chunk using OpenAI API
    response = openai.Embedding.create(input=chunk, model="text-embedding-ada-002")
    embedding = response["data"][0]["embedding"]

    # Store the embedding in Pinecone with the unique ID
    pinecone_store.upsert(vectors=[{'id': chunk_unique_id, 'values': embedding}])

    # Add the unique ID and corresponding original text chunk to the mapping
    id_to_text_mapping[chunk_unique_id] = chunk


# Save the id_to_text_mapping to a JSON file
with open(f"{file_unique_id}.json", "w") as outfile:
    json.dump(id_to_text_mapping, outfile)

# print(id_to_text_mapping)

