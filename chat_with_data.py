# from dotenv import dotenv_values
import yaml
from flask import request, jsonify
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAIChat
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import yaml
import logging
from retrieve import get_embedding
from retrieve import query_pinecone
import pinecone
from flask import jsonify, make_response

#config = dotenv_values(".env")
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
    memory=ConversationBufferMemory(memory_key="chat_history", input_key="human_input"),
    prompt=PromptTemplate(
        input_variables=["chat_history", "human_input", "context", "tone", "persona", "filenames","text_list"],
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


def chat():
    try:
        # Get the question from the request
        question = request.json["user_input"]
        print(question)
        query_embeds = get_embedding(question)
        documents = query_pinecone(index, query_embeds, include_metadata=True)
        print("documents[matches]:", documents["matches"])
        filenames = [doc["metadata"]["file_name"] for doc in documents["matches"]]
        print("filenames:", filenames)
        logger.info("filenames:", filenames)
        # Extract the relevant text from the matching documents
        text_list = [{"text": match["metadata"]["text"]} for match in documents["matches"]]
        print("text list")
        print(text_list)
        
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
        #response_text = response['choices'][0]['text']
        response_text = response['output_text']
        # Return the JSON serialized response
        #return response
        #return jsonify({"response": response_text})
        return make_response(jsonify({"response": response_text}), 200)
    

    except Exception as e:
        # Log the error and return an error response
        logger.error(f"Error while processing request: {e}")
        return jsonify({"error": "Unable to process the request."}), 500