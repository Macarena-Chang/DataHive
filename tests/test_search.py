# Test cases for the /search endpoint
def test_search(client):
    response = client.post("/search", json={"search_query": "test"})
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "results" in response.json()
