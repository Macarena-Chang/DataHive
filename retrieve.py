import pinecone
import openai


# Set up API keys and configurations
openai_key = ""
pinecone_api_key = ""
pinecone_environment = ""
pinecone_index_name = ""

# Configure OpenAI
openai.api_key = openai_key

# Initialize Pinecone
pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)


# Initialize Pinecone vector store
pinecone_store = pinecone.Index(index_name=pinecone_index_name)

index = pinecone.Index(pinecone_index_name)
# index.describe_index_stats()

# Define a search query as a string
#search_query = "Dictionaries"
search_query = "Manual String Formatting" 
# Get the embedding for the query using OpenAI API
response = openai.Embedding.create(input=search_query, model="text-embedding-ada-002")
query_embeds = response["data"][0]["embedding"]

# get relevant contexts (including the questions)
response = index.query(query_embeds, top_k=5, include_metadata=True)

# store  text from responses
response_texts = [match["metadata"]["text"] for match in response["matches"]]

print(response._data_store['matches'][0]._data_store['metadata']['text'])
# print(response._data_store['matches'][0]._data_store['id'])

print(response_texts)

combined_text = " ".join(response_texts)

prompt = f"""
I have gathered some relevant information to help answer your question. Here is the information:

{combined_text}

Based on this information,  provide a concise summary for topic {search_query}
"""


response_chat = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}

    ]
)

# response text
print(response_chat)

