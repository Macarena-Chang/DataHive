# Test cases for the /chat_question endpoint
def test_chat_question(client):
    response = client.post("/chat_question", json={"user_input": "Hello", "file_name": None})
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "response" in response.json()