# Test cases for the /filenames.json endpoint
def test_serve_filenames_json(client):
    response = client.get("/filenames.json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]