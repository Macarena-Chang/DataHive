# from dotenv import dotenv_values
import logging
import yaml
import openai
import pinecone
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAIChat
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from flask import jsonify, make_response
from flask import request
from retrieve import get_embedding
from retrieve import query_pinecone

# config = dotenv_values(".env")


def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Pinecone
pinecone.init(api_key=config["PINECONE_API_KEY"],
              environment=config["PINECONE_ENVIRONMENT"])
index = pinecone.Index(config["PINECONE_INDEX_NAME"])

tone = config["tone"]
persona = config["persona"]


# Initialize the QA chain
logger.info("Initializing QA chain......")
chain = load_qa_chain(
    OpenAIChat(openai_api_key=config["OPENAI_API_KEY"]),
    chain_type="stuff",
    memory=ConversationBufferMemory(
        memory_key="chat_history", input_key="human_input"),
    prompt=PromptTemplate(
        input_variables=["chat_history", "human_input",
                         "context", "tone", "persona", "filenames", "text_list"],
        template="""You are a chatbot who acts like {persona}, having a conversation with a student.

Given the following extracted parts of a long document and a question, Create a final answer with references ("FILENAMES")and ("SOURCES") in the tone {tone}. 
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "FILENAMES" and "SOURCES" part in your answer with the {filenames} of the data.
SOURCES should only be hyperlink URLs which are genuine and not made up.
Extracted parts: {text_list}. STICK TO EXTRACTED PARTS
{context}

{chat_history}
Human: {human_input}
Chatbot:""",
    ),
    verbose=False,
)


def chat(truncated_question=None):
    try:
        # Get the question from the request
        question = request.json["user_input"]
        query_embeds = get_embedding(question)
        documents = query_pinecone(index, query_embeds, include_metadata=True)
        filenames = [doc["metadata"]["file_name"]
                     for doc in documents["matches"]]

        # Extract the relevant text from the matching documents (if truncated [:-1] to remove some data )
        if truncated_question:
            text_list = [{"text": match["metadata"]["text"]}
                         for match in documents["matches"][:-1]]
        else:
            text_list = [{"text": match["metadata"]["text"]}
                         for match in documents["matches"]]

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
        # Return the JSON serialized response
        return make_response(jsonify({"response": response_text}), 200)

    except openai.InvalidRequestError as e:
        if "maximum context length" in str(e):
            return chat(truncated_question=question)
            # return jsonify({"error": "The input is too long. Please reduce the length of the messages."}), 422
        else:
            return jsonify({"error": "Unable to process the request due to an invalid request error."}), 400

    except Exception as e:
        # Log the error and return an error response
        logger.error(f"Error while processing request: {e}")
        return jsonify({"error": "Unable to process the request."}), 500
