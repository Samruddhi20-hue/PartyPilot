def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "success"


def test_unknown_venue_returns_404(client):
    response = client.get("/venue/999999")
    assert response.status_code == 404
