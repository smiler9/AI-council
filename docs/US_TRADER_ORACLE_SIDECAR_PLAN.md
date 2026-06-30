# US Trader Oracle Sidecar Plan

이 문서는 Oracle에서 실행 중인 US Trader 운영봇을 직접 수정하거나 재시작하지 않고, signal JSON outbox와 sidecar bridge를 통해 AI Council read-only review로 연결하는 계획입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Placeholder 환경

실제 접속 정보와 secret은 문서와 Git에 포함하지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_SSH_KEY=<path-to-private-key>
ORACLE_TRADING_DIR=<oracle-trading-dir>
```

## 왜 Oracle live bot을 직접 수정하지 않는가

Oracle 운영본에는 live trading과 연결될 수 있는 주문 실행 경로가 있습니다. 이 단계는 운영봇을 안전하게 분리한 채 signal export 구조를 검증하는 단계입니다.

금지 사항:

- Oracle 파일 수정
- systemd service start/stop/restart
- live bot 실행/중지/재시작
- 브로커 API 호출
- 주문 생성, 주문 전송, 주문 승인, 주문 취소, 포지션 변경
- secret/API key/token/private key 출력 또는 저장

## Signal Export Outbox 구조

권장 구조:

```text
<oracle-trading-dir>/
├── ai_council_outbox/
├── ai_council_processed/
├── ai_council_failed/
└── ai_council_state/
```

운영 적용 전에는 위 경로를 실제 서버에 만들지 않습니다. 먼저 로컬 sample outbox로 dry-run과 preview를 검증합니다.

## Sidecar Bridge 구조

`examples/oracle_sidecar/us_trader_signal_outbox_bridge.py`는 outbox JSON 파일을 읽고 AI Council로 전송합니다.

- 기본 mode: `preview`
- mapping profile: `us_trader_oracle_v1`
- duplicate suppression: state file의 `source + signal_id`
- success/failure handling: state 기록, 선택적으로 processed/failed 이동
- watch/poll mode: 명시 옵션일 때만 사용
- broker API 호출 없음
- Oracle service 조작 없음

## Level 0: Dry-run

HTTP 호출 없이 request body와 warning을 확인합니다.

```bash
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --dry-run \
  --pretty
```

## Level 1: Normalize Preview

AI Council `/api/webhooks/normalize-preview`를 호출합니다. trade review는 생성하지 않습니다.

```bash
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --pretty
```

## Level 2: Read-only Trade Review

Webhook이 안전하게 설정된 경우에만 AI Council trade-signal endpoint로 전송합니다. 이 단계도 주문을 실행하지 않습니다.

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=<webhook-secret>

python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox /path/to/outbox \
  --processed /path/to/processed \
  --failed /path/to/failed \
  --state /path/to/state.json \
  --mode review
```

## Level 3: Paper Simulation

AI Council read-only review 결과를 내부 Paper Trading portfolio에만 반영합니다.

- `simulation_only=true`
- 실제 주문 없음
- 실제 체결 없음
- 실제 포지션 변경 없음

## Oracle 적용 전 체크리스트

- 로컬 sample outbox dry-run 통과
- normalize-preview smoke test 통과
- order-like field warning 확인
- `order_execution_allowed=false` 확인
- state duplicate suppression 확인
- review mode는 별도 테스트 backend에서만 검증
- Oracle 운영본 백업과 rollback 계획 수립
- secret/API key/token/private key 비노출 확인

## 안전한 export hook 삽입 위치 후보

향후 별도 검증 후에만 고려할 수 있는 후보:

- `analyze_signals(...)` 이후 signal dict가 확정되는 지점
- `scan_and_enter(...)` 내부에서 주문 전 candidate 생성 직후

이 위치에서도 outbox JSON export만 수행해야 합니다. AI Council 결과를 live order path로 되돌려 연결하지 않습니다.

## 절대 연결하면 안 되는 위치

- `place_order(...)`
- `check_exits(...)`
- `force_close_all(...)`

위 경로는 실제 주문/청산/포지션 변경과 연결될 수 있으므로 AI Council sidecar와 연결하지 않습니다.

## Rollback 계획

운영 적용 전 계획:

1. sidecar를 독립 프로세스로만 실행
2. outbox export helper를 feature flag로 분리
3. 문제 발생 시 sidecar process만 종료
4. live bot service는 조작하지 않음
5. outbox/state directory 제거만으로 연동 해제 가능하게 설계

## 로그/중복/파일 권한 주의사항

- outbox JSON에는 secret, account, token, private key를 넣지 않음
- `source + signal_id`로 중복 처리
- state file은 민감하지 않은 처리 결과만 저장
- 디렉터리 권한은 운영 사용자만 쓰기 가능하도록 제한
- error log에는 payload 전체 대신 파일명, signal_id, warning 중심으로 기록

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`trade_allowed`는 분석상 판단 메타데이터이며 실제 주문 허용이 아닙니다. `order_execution_allowed`는 항상 `false`입니다.
