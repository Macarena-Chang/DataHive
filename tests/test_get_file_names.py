# Test cases for the /filenames.json endpoint
def test_get_file_names(client):
    response = client.get("/files")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]