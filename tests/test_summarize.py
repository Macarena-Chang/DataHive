def test_summarize(client):
    response = client.post("/summary", json={"text": "This is a test."})
    assert response.status_code == 200
    assert "summary" in response.json()