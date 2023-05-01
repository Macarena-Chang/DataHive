from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from ingest import ingest_files
from retrieve import search_and_chat
# from dotenv import dotenv_values
from chat_with_data import chat
import yaml
from flask import send_from_directory



def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)


config = load_config("config.yaml")


app = Flask(__name__)


if not os.path.exists('uploads'):
    os.makedirs('uploads')


@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    message = None

    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        print(uploaded_files)
        file_paths = []
        for uploaded_file in uploaded_files:
            if uploaded_file:
                filename = secure_filename(uploaded_file.filename)
                file_path = os.path.join('uploads', filename)
                uploaded_file.save(file_path)
                file_paths.append(file_path)

        if file_paths:
            ingest_files(file_paths)
            message = "Files uploaded and ingested successfully."

    return render_template('index.html', message=message)


@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    if request.method == 'POST':
        search_query = request.form['search_query']
        if search_query:
            results = search_and_chat(search_query)

    return render_template('index.html', results=results)


@app.route('/chat', methods=['GET', 'POST'])
def chat_with_your_data():
    if request.method == 'POST':
        response = chat()
        return response
    return render_template('chat.html')

@app.route('/filenames.json')
def serve_filenames_json():
    return send_from_directory('.', 'filenames.json')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
