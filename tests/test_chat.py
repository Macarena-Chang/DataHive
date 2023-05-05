# Test cases for the /chat endpoint
def test_chat(client):
    response = client.get("/chat")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "text" in response.text