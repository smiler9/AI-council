# Oracle Apply Checklist

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 적용 전

- [ ] Oracle host/user/key는 placeholder로만 문서화했는지 확인
- [ ] 실제 secret/API key/token/private key를 문서나 Git에 넣지 않았는지 확인
- [ ] `scripts/run_oracle_export_hook_preflight.sh` 통과
- [ ] `scripts/run_oracle_sidecar_smoke.sh` 통과
- [ ] sample outbox preview 결과의 `order_execution_allowed=false` 확인
- [ ] order-like field warning 확인
- [ ] review mode는 아직 사용하지 않음

## 백업 체크리스트

예시 명령은 placeholder입니다.

```bash
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
```

- [ ] `penny_stock_bot.py` 백업
- [ ] sidecar/exporter 파일은 별도 경로에 배치
- [ ] `.secrets` 파일을 열거나 출력하지 않음
- [ ] 백업 파일 권한 확인

## Outbox 권한

- [ ] outbox directory는 운영 사용자만 쓰기 가능
- [ ] processed/failed/state directory 분리
- [ ] JSON payload에 account/secret/token/private key 없음
- [ ] state file은 `source + signal_id`와 처리 결과만 저장

## Preview-only 검증

- [ ] exporter hook으로 outbox JSON 생성
- [ ] sidecar `--dry-run`
- [ ] sidecar `--mode preview`
- [ ] AI Council normalize-preview 응답 확인
- [ ] trade review 생성 안 됨
- [ ] `order_execution_allowed=false`

## 나중 단계

- [ ] read-only trade review는 별도 승인 후
- [ ] paper simulation은 별도 승인 후
- [ ] AI Council 결과를 live order path로 연결하지 않음

## 절대 하지 말아야 할 것

- [ ] `place_order(...)` 내부에 hook 삽입 금지
- [ ] `check_exits(...)` 내부에 hook 삽입 금지
- [ ] `force_close_all(...)` 내부에 hook 삽입 금지
- [ ] systemd service start/stop/restart 금지
- [ ] 브로커 API 호출 금지
- [ ] 실제 주문 생성/전송/승인/취소/실행 금지

## Rollback

- [ ] sidecar process만 종료
- [ ] outbox export feature flag 비활성화
- [ ] generated outbox/state 보존
- [ ] 문제 파일 식별
- [ ] live bot service는 임의 조작하지 않음
