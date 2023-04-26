import pinecone
import openai
import yaml



def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


def get_embedding(text: str, model: str = "text-embedding-ada-002"):
    response = openai.Embedding.create(input=text, model=model)
    return response["data"][0]["embedding"]


def query_pinecone(index, query_embedding, top_k=5, include_metadata=True):
    response = index.query(query_embedding, top_k=top_k, include_metadata=include_metadata)
    return response


def get_response_texts(response):
    return [match["metadata"]["text"] for match in response["matches"]]


def generate_summary(prompt: str):
    
    response_chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response_chat.choices[0].message['content']

# format summary to handle how code is displayed
def format_summary(summary: str) -> str:
    backtick_occurrences = summary.count("```")
    formatted_summary = ""
    start_position = 0

    for i in range(backtick_occurrences):
        end_position = summary.find("```", start_position)

        if i % 2 == 0:
            tag = '<div class="code-header"><button class="copy-btn">Copy</button></div><pre><code>'
        else:
            tag = "</code></pre>"


        formatted_summary += summary[start_position:end_position] + tag
        start_position = end_position + 3

    formatted_summary += summary[start_position:]
    return formatted_summary


def search_and_chat(search_query: str, summary_length: str = "in-depth") -> list:
    config = load_config("config.yaml")
    openai.api_key = config["openai_key"]
    pinecone.init(api_key=config["pinecone_api_key"], environment=config["pinecone_environment"])

    index = pinecone.Index(config["pinecone_index_name"])

    query_embeds = get_embedding(search_query)
    response = query_pinecone(index, query_embeds)

    print(response)
    
    response_texts = get_response_texts(response)

    combined_text = " ".join(response_texts)

    prompt = f"""
    I have gathered some relevant information to help answer your question. Here is the information:
    {combined_text}
    Based on this information, provide a detailed summary for topic {search_query}
    """

    summary = generate_summary(prompt)
    formatted_summary = format_summary(summary)
    print(prompt)
    print(summary)
    print(formatted_summary)
    return [formatted_summary]
   # return [summary]  # Wrap summary in a list


# definir search query
# search_and_chat("Tuples and Sequences with code examples");