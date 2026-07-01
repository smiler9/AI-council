# Preview Signal Write Rollback Notes

If the preview signal file is uploaded to the wrong path, stop and review manually.

Rollback principles:

- Do not automate remote delete or move actions in Phase 24R.
- Do not restart or reload systemd services.
- Do not modify `penny_stock_bot.py`.
- If removal is needed, require a separate manual approval because the outbox may contain files that should be preserved.
- Mac pull can simply skip processing until the file situation is reviewed.

This rollback note is unrelated to live trading and does not authorize broker API usage or order execution.

`order_execution_allowed=false` remains mandatory during rollback review.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
