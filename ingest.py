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

# create a mapping between vector ids and original text chunks
id_to_text_mapping = {}

# store embeddings of the chunks with their unique ids in pinecone
for idx, chunk in enumerate(my_chunks):
    # generate a unique ID for each chunk
    chunk_unique_id = f"{file_unique_id}_{idx}"

    # get the embedding for the chunk with openai
    response = openai.Embedding.create(input=chunk, model="text-embedding-ada-002")
    embedding = response["data"][0]["embedding"]

    # create metadata for the chunk
    metadata = {
        'chunk': idx,
        'text': chunk,
        'file_id': file_unique_id
    }

    # add the unique id and corresponding metadata to the mapping
    id_to_text_mapping[chunk_unique_id] = metadata

    # store the embedding and metadata in Pinecone using zip
    pinecone_store.upsert(vectors=zip([chunk_unique_id], [embedding], [metadata]))

# save the id_to_text_mapping to a JSON file
with open(f"{file_unique_id}.json", "w") as outfile:
    json.dump(id_to_text_mapping, outfile)

print(id_to_text_mapping)