# from dotenv import dotenv_values
import logging
import yaml
import openai
import pinecone
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from flask import jsonify, make_response
from flask import request
from retrieve import get_embedding
from retrieve import query_pinecone
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from doc_utils import search_documents_by_file_name, fetchTopK
# config = dotenv_values(".env")


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Pinecone
pinecone.init(api_key=config["PINECONE_API_KEY"],  environment=config["PINECONE_ENVIRONMENT"])
index = pinecone.Index(config["PINECONE_INDEX_NAME"])

tone = config["tone"]
persona = config["persona"]


# Initialize the QA chain
logger.info("Initializing QA chain......")
chain = load_qa_chain(
    ChatOpenAI(openai_api_key=config["OPENAI_API_KEY"]),
    chain_type="stuff",
    memory=ConversationBufferMemory(
        memory_key="chat_history", input_key="human_input"),
    prompt=PromptTemplate(
        input_variables=["chat_history", "human_input", "context", "tone", "persona", "filenames", "text_list"],
        template="""You are a chatbot who acts like {persona}, having a conversation with a student.

Given the following extracted parts of a long document and a question, Create a final answer with references ("FILENAMES") in the tone {tone}. 
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "FILENAMES" part only at the end of your answer with the {filenames}.

Extracted parts: {text_list}. STICK TO EXTRACTED PARTS.


{context}

{chat_history}
Human: {human_input}
Chatbot:""",
    ),
    verbose=False,
)

def chat(truncated_question=None,truncation_step=0):
    """
    Handles the chat request, retrieves relevant documents, and generates the chatbot's response.

    :param truncated_question: The original question with a reduced length, if any (default: None).
    :param truncation_step: The number of times the incput question has been truncated (default: 0).
    :return: A JSON serialized response containing the chatbot's response or an error message.
    """
    try:
        # Get the question from the request
        question = request.json["user_input"]
        file_name = request.json["file_name"]
        query_embeds = get_embedding(question)

        documents = search_documents_by_file_name(index, tuple(query_embeds), file_name, include_metadata=True)
        
        #print(query_pinecone.cache_info())

        # Log number of matching documents
        logger.debug(f"Number of matching documents: {len(documents['matches'])}")

        # Extract the unique filenames from the matching documents
        filenames = get_unique_filenames(documents["matches"])
        logger.info(f"Unique source filenames: {filenames}")

        # Extract the relevant text from the matching documents (if truncated, remove truncation_step number of elements)
        text_list = [{"text": match["metadata"]["text"]}
                    for match in documents["matches"]]
        
        if truncated_question:
            original_length = len(text_list)
            text_list = text_list[:-truncation_step]
            logger.info(f"Truncating text_list from {original_length} to {len(text_list)} elements.")


        # Get the bot's response
        response = chain(
            {
                "input_documents": documents["matches"],
                "human_input": question,
                "tone": tone,
                "persona": persona,
                "filenames": filenames,
                "text_list": text_list,
            },
            return_only_outputs=True,
        )

        # Extract the response text
        response_text = response['output_text']
        logger.info(f"Chatbot response: {response_text}")
        # Return the JSON serialized response
        return make_response(jsonify({"response": response_text}), 200)

    except openai.InvalidRequestError as e:
        if "maximum context length" in str(e):
            if truncation_step < 4:
                return chat(truncated_question=question, truncation_step=truncation_step + 1)
            elif truncation_step > 4:
                logger.error(f"Error while processing request: {e}")
                return jsonify({"error": "The input is too long. Please reduce the length of the messages."}), 422
        else:
            return jsonify({"error": "Unable to process the request due to an invalid request error."}), 400

    except Exception as e:
        # Log the error and return an error response
        logger.error(f"Error while processing request: {e}")
        return jsonify({"error": "Unable to process the request."}), 500

def get_unique_filenames(matches):
    seen_filenames = set()
    filenames = []

    for doc in matches:
        file_name = doc["metadata"]["file_name"]

        # Remove 'uploads/' part from the filename if present
        file_name = file_name.replace('uploads/', '')

        if file_name not in seen_filenames:
            filenames.append(file_name)
            seen_filenames.add(file_name)

    return filenames