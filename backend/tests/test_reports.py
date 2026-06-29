def test_report_generation(client, meeting):
    run_response = client.post(f"/api/meetings/{meeting['id']}/run")
    assert run_response.status_code == 200

    response = client.get(f"/api/meetings/{meeting['id']}/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# AI Council Report" in response.text
    assert "Chairman Agent" in response.text
    assert "Phase 1 does not execute trades" in response.text

