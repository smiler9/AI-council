# Oracle Export Hook Patch Drafts

이 폴더는 Oracle US Trader 운영본에 바로 적용하는 patch가 아니라, 사전 검토용 patch draft와 독립 helper module 예시를 담고 있습니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 원칙

- Oracle live bot에 자동 적용하지 않습니다.
- `penny_stock_bot.py`를 직접 수정하지 않습니다.
- systemd service를 start/stop/restart 하지 않습니다.
- 실제 주문 기능과 연결하지 않습니다.
- 브로커 API를 호출하지 않습니다.
- 먼저 local preflight, sidecar dry-run, normalize-preview를 통과해야 합니다.

## 파일

- `penny_stock_bot_export_hook_patch_draft.md`: 안전한 삽입 지점과 코드 블록 예시
- `ai_council_signal_exporter_module.py`: outbox JSON export 전용 helper module 예시
- `oracle_apply_checklist.md`: 적용 전/후 체크리스트와 rollback 계획

`order_execution_allowed`는 항상 `false`입니다.
