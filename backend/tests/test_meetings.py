def test_meeting_create(client):
    response = client.post(
        "/api/meetings",
        json={"topic": "Review mock catalyst quality", "ticker": "abc"},
    )

    assert response.status_code == 201
    meeting = response.json()
    assert meeting["topic"] == "Review mock catalyst quality"
    assert meeting["ticker"] == "ABC"
    assert meeting["mode"] == "quick_review"
    assert meeting["status"] == "draft"
    assert meeting["trade_review"]["order_execution_allowed"] is False


def test_meeting_mode_create(client):
    response = client.post(
        "/api/meetings",
        json={
            "topic": "Run a deeper council debate",
            "ticker": "DEEP",
            "mode": "deep_debate",
        },
    )

    assert response.status_code == 201
    meeting = response.json()
    assert meeting["mode"] == "deep_debate"
