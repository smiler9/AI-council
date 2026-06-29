def test_meeting_create(client):
    response = client.post(
        "/api/meetings",
        json={"topic": "Review mock catalyst quality", "ticker": "abc"},
    )

    assert response.status_code == 201
    meeting = response.json()
    assert meeting["topic"] == "Review mock catalyst quality"
    assert meeting["ticker"] == "ABC"
    assert meeting["status"] == "draft"
    assert meeting["trade_review"]["order_execution_allowed"] is False

