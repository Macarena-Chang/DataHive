import pinecone
import openai
import yaml

def load_config(file_path: str) -> dict:
    # load config from yaml
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)

def configure_openai(api_key: str):
    # config openai with api key
    openai.api_key = api_key

def initialize_pinecone(api_key: str, environment: str):
    # Iniciar Pinecone using api key and env
    pinecone.init(api_key=api_key, environment=environment)

def get_embedding(text: str, model: str = "text-embedding-ada-002"):
    # get embedding for input text using openai ada
    response = openai.Embedding.create(input=text, model=model)
    return response["data"][0]["embedding"]

def query_pinecone(index, query_embedding, top_k=5, include_metadata=True):
    # query pinecone and get relevant contexts
    response = index.query(query_embedding, top_k=top_k, include_metadata=include_metadata)
    return response

def get_response_texts(response):
    # extract response texts from result
    return [match["metadata"]["text"] for match in response["matches"]]

def generate_summary(prompt: str):
    # generate summary
    response_chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response_chat.choices[0].message['content']

if __name__ == "__main__":
    config = load_config("config.yaml")
    configure_openai(config["openai_key"])
    initialize_pinecone(config["pinecone_api_key"], config["pinecone_environment"])

    index = pinecone.Index(config["pinecone_index_name"])

    search_query = "Multiple Inheritance in Python"
    query_embeds = get_embedding(search_query)
    response = query_pinecone(index, query_embeds)
    response_texts = get_response_texts(response)

    combined_text = " ".join(response_texts)

    prompt = f"""
    I have gathered some relevant information to help answer your question. Here is the information:

    {combined_text}

    Based on this information,  provide a concise summary for topic {search_query}
    """

    summary = generate_summary(prompt)
    print(summary)