def test_mock_meeting_run(client, meeting):
    response = client.post(f"/api/meetings/{meeting['id']}/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meeting"]["status"] == "completed"
    assert len(payload["outputs"]) == 7
    assert any(output["agent_name"] == "Skeptic Agent" for output in payload["outputs"])
    assert any(output["agent_name"] == "Chairman Agent" for output in payload["outputs"])
    assert payload["meeting"]["trade_review"]["order_execution_allowed"] is False

