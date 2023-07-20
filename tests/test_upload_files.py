import os
import tempfile

from fastapi.testclient import TestClient

from app import app


def test_upload_files():
    client = TestClient(app)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(b"test content")
        temp_file.seek(0)
        response = client.post("/files", files={"files": (temp_file.name, temp_file)})
        assert response.status_code == 200
        assert "File uploaded and ingested successfully." in response.json()["message"]
    os.unlink(temp_file.name)
