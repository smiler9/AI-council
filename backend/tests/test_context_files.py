def _upload(client, meeting_id, filename, content, content_type="text/plain"):
    return client.post(
        f"/api/meetings/{meeting_id}/files",
        files={"file": (filename, content, content_type)},
    )


def test_txt_file_upload(client, meeting):
    response = _upload(
        client,
        meeting["id"],
        "notes.txt",
        b"cash runway looks short\nwatch dilution risk\n",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["original_filename"] == "notes.txt"
    assert payload["file_type"] == "txt"
    assert payload["status"] == "ready"
    assert "plain text context" in payload["summary"]

    detail = client.get(f"/api/files/{payload['id']}")
    assert detail.status_code == 200
    assert "cash runway" in detail.json()["extracted_text"]


def test_csv_file_upload(client, meeting):
    response = _upload(
        client,
        meeting["id"],
        "prices.csv",
        b"date,close,volume\n2026-01-01,1.2,1000\n2026-01-02,1.5,1500\n",
        "text/csv",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_type"] == "csv"
    assert "2 row(s)" in payload["summary"]
    assert "close" in payload["summary"]
    assert "Numeric summary" in payload["summary"]


def test_json_file_upload(client, meeting):
    response = _upload(
        client,
        meeting["id"],
        "filing.json",
        b'{"symbol": "TEST", "risk": {"dilution": true}, "cash_months": 4}',
        "application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_type"] == "json"
    assert "top-level key" in payload["summary"]
    assert "symbol" in payload["summary"]


def test_unsupported_extension_rejected(client, meeting):
    response = _upload(
        client,
        meeting["id"],
        "payload.exe",
        b"not allowed",
        "application/octet-stream",
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_meeting_run_includes_context(client, meeting):
    upload = _upload(
        client,
        meeting["id"],
        "risk-notes.md",
        b"# Risk notes\nThin liquidity and possible promotion language.\n",
        "text/markdown",
    )
    assert upload.status_code == 201

    response = client.post(f"/api/meetings/{meeting['id']}/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meeting"]["status"] == "completed"
    assert payload["meeting"]["trade_review"]["context_file_count"] == 1
    assert payload["files"][0]["original_filename"] == "risk-notes.md"
    assert all(
        output["structured_response"]["raw"]["context_file_count"] == 1
        for output in payload["outputs"]
    )
    assert any("Context-aware note" in output["content"] for output in payload["outputs"])


def test_report_includes_file_summary(client, meeting):
    upload = _upload(
        client,
        meeting["id"],
        "catalyst.log",
        b"2026-06-01 catalyst mentioned without primary source\n",
    )
    assert upload.status_code == 201
    run_response = client.post(f"/api/meetings/{meeting['id']}/run")
    assert run_response.status_code == 200

    response = client.get(f"/api/meetings/{meeting['id']}/report")

    assert response.status_code == 200
    assert "## Attached Context Files" in response.text
    assert "## File Summaries" in response.text
    assert "catalyst.log" in response.text
    assert "plain text context" in response.text
    assert "## Context-aware Agent Notes" in response.text


def test_file_delete(client, meeting):
    upload = _upload(
        client,
        meeting["id"],
        "delete-me.txt",
        b"temporary context",
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    response = client.delete(f"/api/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert client.get(f"/api/files/{file_id}").status_code == 404
    list_response = client.get(f"/api/meetings/{meeting['id']}/files")
    assert list_response.status_code == 200
    assert list_response.json() == []

