def test_deep_debate_rounds_created(client):
    create = client.post(
        "/api/meetings",
        json={"topic": "Debate a high-risk setup", "ticker": "DEEP", "mode": "deep_debate"},
    )
    assert create.status_code == 201
    meeting_id = create.json()["id"]

    response = client.post(f"/api/meetings/{meeting_id}/run")

    assert response.status_code == 200
    payload = response.json()
    rounds = {message["round"] for message in payload["messages"]}
    assert rounds >= {
        "initial_opinion",
        "rebuttal",
        "revision",
        "chairman_summary",
        "structured_decision",
    }
    assert len(payload["outputs"]) == 7
    assert payload["structured_decision"]["decision"] in {
        "ALLOW",
        "HOLD",
        "BLOCK",
        "NEED_MORE_DATA",
    }


def test_risk_gate_review_decision_schema(client):
    create = client.post(
        "/api/meetings",
        json={
            "topic": "Review whether automation should be blocked",
            "ticker": "RISK",
            "mode": "risk_gate_review",
        },
    )
    assert create.status_code == 201
    meeting_id = create.json()["id"]

    response = client.post(f"/api/meetings/{meeting_id}/run")

    assert response.status_code == 200
    decision = response.json()["structured_decision"]
    assert set(decision) >= {
        "decision",
        "confidence",
        "risk_level",
        "trade_allowed",
        "position_size_multiplier",
        "primary_reasons",
        "risk_flags",
        "required_follow_up",
        "data_quality",
        "order_execution_allowed",
    }
    assert decision["risk_level"] == "critical"
    assert decision["decision"] == "BLOCK"
    assert decision["trade_allowed"] is False
    assert decision["order_execution_allowed"] is False


def test_high_risk_trade_allowed_false(client):
    create = client.post(
        "/api/meetings",
        json={"topic": "Skeptic review for a promotional setup", "mode": "skeptic_review"},
    )
    assert create.status_code == 201

    response = client.post(f"/api/meetings/{create.json()['id']}/run")

    assert response.status_code == 200
    decision = response.json()["structured_decision"]
    assert decision["risk_level"] == "high"
    assert decision["decision"] in {"HOLD", "BLOCK"}
    assert decision["trade_allowed"] is False


def test_order_execution_allowed_always_false(client):
    for mode in [
        "quick_review",
        "deep_debate",
        "skeptic_review",
        "risk_gate_review",
        "action_plan",
    ]:
        create = client.post(
            "/api/meetings",
            json={"topic": f"Safety check {mode}", "mode": mode},
        )
        assert create.status_code == 201
        response = client.post(f"/api/meetings/{create.json()['id']}/run")
        assert response.status_code == 200
        payload = response.json()
        assert payload["structured_decision"]["order_execution_allowed"] is False
        assert payload["meeting"]["trade_review"]["order_execution_allowed"] is False


def test_report_includes_structured_decision(client):
    create = client.post(
        "/api/meetings",
        json={"topic": "Report decision section", "ticker": "RPT", "mode": "deep_debate"},
    )
    assert create.status_code == 201
    meeting_id = create.json()["id"]
    run = client.post(f"/api/meetings/{meeting_id}/run")
    assert run.status_code == 200

    response = client.get(f"/api/meetings/{meeting_id}/report")

    assert response.status_code == 200
    assert "## 구조화된 판단 (Structured Decision)" in response.text
    assert "## 토론 라운드 (Debate Rounds)" in response.text
    assert "## 안전 경계 (Safety Boundary)" in response.text
    assert "AI Council does not execute trades or connect to broker APIs" in response.text


def test_structured_decision_enum_values_remain_api_compatible(client):
    create = client.post(
        "/api/meetings",
        json={"topic": "Check enum compatibility", "ticker": "ENUM", "mode": "risk_gate_review"},
    )
    assert create.status_code == 201

    response = client.post(f"/api/meetings/{create.json()['id']}/run")

    assert response.status_code == 200
    decision = response.json()["structured_decision"]
    assert decision["decision"] in {"ALLOW", "HOLD", "BLOCK", "NEED_MORE_DATA"}
    assert decision["risk_level"] in {"low", "medium", "high", "critical"}
    assert isinstance(decision["trade_allowed"], bool)
    assert decision["order_execution_allowed"] is False
