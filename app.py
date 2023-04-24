from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from ingest import ingest_file
from retrieve import search_and_chat

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
        uploaded_file = request.files['file']
        if uploaded_file:
            filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join('uploads', filename)
            uploaded_file.save(file_path)
            ingest_file(file_path)
            message = "File uploaded and ingested successfully."
    
    return render_template('index.html', message=message)

@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    if request.method == 'POST':
        search_query = request.form['search_query']
        if search_query:
            results = search_and_chat(search_query)
    
    return render_template('index.html', results=results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
