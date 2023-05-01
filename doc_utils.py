import logging
from functools import lru_cache
# UTILS
# Set up logging
logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def search_documents_by_file_name(index, query_embedding_tuple, file_name, top_k=5, include_metadata=True):
    file_name_filter = {"file_name": {"$eq": file_name}}
    response = query_pinecone(index, query_embedding_tuple, top_k=top_k, filter_dict=file_name_filter, include_metadata=include_metadata)
    logger.debug(f"search_documents_by_file_name response ready: {response}")
    return response

def query_pinecone(index, query_embedding_tuple, top_k=5, filter_dict=None, include_metadata=True):
    logger.debug(f"Query pinecone filter_dict: {filter_dict}")
    # Convert the tuple back to a list
    query_embedding = list(query_embedding_tuple)
    response = index.query(query_embedding, top_k=top_k, filter=filter_dict, include_metadata=include_metadata)
    return response

