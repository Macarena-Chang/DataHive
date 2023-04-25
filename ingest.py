import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid
import json
import yaml
import docx
import nltk
import zipfile
from nltk.tokenize import TextTilingTokenizer


from pdfminer.high_level import extract_text
#nltk.download("stopwords")
#nltk.download("punkt")

def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


# If text tiling fails 
# in that case RecursiveCharacterTextSplitter will be used instead of Text Tiling
def split_text_data(text: str) -> list:
    # initialize TextTilingTokenizer - default parameters
    ttt = TextTilingTokenizer()

    # check if text too short
    if len(text) < ttt.w * 2:  # w = default block size (usually 50)
        return [text]

    try:
        # tokenize the text into pseudo sentences (adjust parameters if necessary)
        pseudo_sentences = nltk.sent_tokenize(text, language="english")

        # Concatenate pseudo sentences
        concatenated_pseudo_sentences = ' '.join(pseudo_sentences)

        # Apply text tiling on concatenated pseudo sentences
        chunks = ttt.tokenize(concatenated_pseudo_sentences)

        # remove double new lines from chunks
        chunks = [chunk.lstrip('\n\n') for chunk in chunks]

        if len(chunks) <= 1:
            raise ValueError("Too few chunks")

    except ValueError as e:
        print(f"TextTiling exception: {e}")

        # Fallback to RecursiveCharacterTextSplitter
        char_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = char_text_splitter.split_text(text)
        print("RecursiveCharacterTextSplitter")
        print(chunks)
    return chunks
    

def generate_embeddings(chunks: list) -> list:
    embeddings = []
    for chunk in chunks:
        response = openai.Embedding.create(input=chunk, model="text-embedding-ada-002")
        embeddings.append(response["data"][0]["embedding"])
    return embeddings


def store_embeddings(chunks: list, embeddings: list, file_unique_id: str, pinecone_store, file_name) -> dict:
    id_to_text_mapping = {}
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_unique_id = f"{file_unique_id}_{idx}"
        metadata = {'chunk': idx, 'text': chunk, 'file_id': file_unique_id, 'file_name':file_name}
        id_to_text_mapping[chunk_unique_id] = metadata
        pinecone_store.upsert(vectors=zip([chunk_unique_id], [embedding], [metadata]))
    return id_to_text_mapping


def save_mapping_to_file(mapping: dict, file_name: str):
    with open(file_name, "w") as outfile:
        json.dump(mapping, outfile)

""" def extract_text_from_pdf(file_path: str) -> str:
    pdf_file = open(file_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    numPages = len(pdf_reader.pages)
    text = ''
    for page_num in range (0, numPages):
        text += pdf_reader.pages[page_num].extract_text() 
    pdf_file.close()
     # Save extracted text to a TXT file
    txt_file_path = file_path.replace('.pdf', '.txt')
    with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
        txt_file.write(text)
    return text """

""" def extract_text_from_pdf(file_path: str) -> str:
    text = ''
    with pdfplumber.open(file_path) as pdf:
            length = len(pdf.pages)
    print(f"Total number of Page is {length}.")  # find total pages
    for i in range (0, length): 
        text +=  pdf.pages[i].extract_text()
        text += '\n'

    # Save extracted text to a TXT file
    txt_file_path = file_path.replace('.pdf', '.txt')
    with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
     txt_file.write(text)
    return text  """

def extract_text_from_pdf(file_path: str) -> str:
    # Extract text using pdfminer
    text = extract_text(file_path)
    # Save extracted text to a TXT file
    txt_file_path = file_path.replace('.pdf', '.txt')
    with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
        txt_file.write(text)

    return text


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    text = ''
    for paragraph in doc.paragraphs:
        text += paragraph.text + '\n'
    return text


""" def extract_text_from_doc(file_path: str) -> str:
    text = textract.process(file_path).decode('utf-8')
    return text
 """


def ingest_file(file_path: str) -> dict:
#def ingest_file() -> dict:
   # file_path = "text-tiling.pdf" 
    config = load_config("config.yaml")

    openai_key = config["openai_key"]
    pinecone_api_key = config["pinecone_api_key"]
    pinecone_environment = config["pinecone_environment"]

    openai.api_key = openai_key
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)


    file_extension = file_path.lower().split('.')[-1]
    text_extraction_functions = {
        'pdf': extract_text_from_pdf,
        'docx': extract_text_from_docx,
       # 'doc': extract_text_from_doc,
        'txt': lambda path: open(path, 'r').read()
    }

    file_content = text_extraction_functions.get(file_extension)(file_path)
    
    # text = file_content.replace('\n', ' ').replace('\\n', ' ')
    text = file_content
    chunks = split_text_data(text)

    file_unique_id = str(uuid.uuid4())
    pinecone_store = pinecone.Index(config["pinecone_index_name"])

    embeddings = generate_embeddings(chunks)

    file_name = file_path

    id_to_text_mapping = store_embeddings(chunks, embeddings, file_unique_id, pinecone_store, file_name)

    save_mapping_to_file(id_to_text_mapping, f"{file_unique_id}.json")
    return {"message": "File processed successfully.", "file_unique_id": file_unique_id}

#result = ingest_file()
#print(result)