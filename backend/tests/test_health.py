def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "phase_1_mock"

