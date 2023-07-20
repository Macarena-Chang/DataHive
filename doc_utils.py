import json
import logging
import os
from functools import lru_cache

# UTILS
# Set up logging
logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def search_documents_by_file_name(
    index, query_embedding_tuple, file_name, top_k=5, include_metadata=True
):
    file_name_filter = None
    if file_name:
        file_name_filter = {"file_name": {"$eq": file_name}}
    response = query_pinecone(
        index,
        query_embedding_tuple,
        top_k=top_k,
        filter_dict=file_name_filter,
        include_metadata=include_metadata,
    )
    logger.info(f"search_documents_by_file_name response ready: {response}")
    return response


def query_pinecone(
    index, query_embedding_tuple, top_k=5, filter_dict=None, include_metadata=True
):
    logger.info(f"Query pinecone filter_dict: {filter_dict}")
    # Convert the tuple back to a list
    query_embedding = list(query_embedding_tuple)
    response = index.query(
        query_embedding,
        top_k=top_k,
        filter=filter_dict,
        include_metadata=include_metadata,
    )
    return response


def update_filenames_json(file_name: str, file_unique_id: str):
    file_path = "filenames.json"

    # Check if the file exists and is not empty
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        # Read the existing content
        with open(file_path, "r") as f:
            try:
                filenames = json.load(f)
            except json.JSONDecodeError:
                # If there is a decoding error, initialize an empty dictionary
                filenames = {}
    else:
        # If the file doesn't exist or is empty, initialize an empty dictionary
        filenames = {}

    # Update the dictionary with the new file name and unique ID
    filenames[file_name] = file_unique_id

    # Save the updated dictionary back to the file
    with open(file_path, "w") as f:
        json.dump(filenames, f)


# Fetch 10k
def fetchTopK(index):
    response = index.query(vector=[0] * 1536, top_k=10000, include_values=True)
    return response
