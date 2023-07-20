# TODO - Fix this test case
# Test cases for the /chat_question endpoint
def test_chat_question(token, client):
    headers = {
        "Authorization": f"Bearer {token}",
    }
    chat_input = {"user_input": "Hello, how are you?", "file_name": ""}
    response = client.post("/users/me/chat/responses",
                           headers=headers,
                           json=chat_input)
    assert response.status_code == 200
    assert "response" in response.json()
