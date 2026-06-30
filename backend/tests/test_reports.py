def test_report_generation(client, meeting):
    run_response = client.post(f"/api/meetings/{meeting['id']}/run")
    assert run_response.status_code == 200

    response = client.get(f"/api/meetings/{meeting['id']}/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# AI Council 회의 보고서" in response.text
    assert "Chairman Agent" in response.text
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in response.text
    assert "AI Council does not execute trades or connect to broker APIs" in response.text


def test_report_includes_korean_safety_boundary(client, meeting):
    run_response = client.post(f"/api/meetings/{meeting['id']}/run")
    assert run_response.status_code == 200

    response = client.get(f"/api/meetings/{meeting['id']}/report")

    assert response.status_code == 200
    assert "## 안전 경계 (Safety Boundary)" in response.text
    assert (
        "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
        "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
    ) in response.text
