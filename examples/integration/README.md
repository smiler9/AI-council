# Webhook 통합 Smoke Test

이 smoke test는 외부 봇 후보 신호가 AI Council의 read-only webhook receiver로 들어오고, Trade Review 결과로 연결되는지 확인합니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 필요한 Backend 상태

Webhook을 활성화한 backend가 실행 중이어야 합니다.

```bash
cd ~/AI-council/backend
WEBHOOKS_ENABLED=true \
WEBHOOK_SECRET=change-me \
WEBHOOK_REQUIRE_SECRET=true \
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Smoke test 환경변수:

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=change-me
export AI_COUNCIL_TIMEOUT_SECONDS=20
```

실제 secret은 Git에 커밋하지 마십시오.

## 실행 방법

```bash
cd ~/AI-council
python3 examples/integration/run_webhook_smoke_test.py
```

또는:

```bash
scripts/run_webhook_smoke.sh
```

## 기대 동작

Webhook이 비활성화되어 있으면 script는 disabled reason을 출력하고 payload를 보내지 않은 채 종료합니다.

Webhook이 활성화되어 있으면 다음 sample payload를 순서대로 보냅니다.

- `breakout_signal.json`
- `high_spread_signal.json`
- `missing_news_signal.json`
- `duplicate_signal.json`

Script가 확인하는 항목:

- backend `/health`
- `/api/webhooks/status`
- `trade_review.id`
- `structured_decision.decision`
- `structured_decision.risk_level`
- `order_execution_allowed=false`
- duplicate signal의 `duplicated=true`

## Duplicate Signal

`duplicate_signal.json`은 `breakout_signal.json`과 같은 `source + signal_id`를 사용합니다. AI Council은 기존 `trade_review.id`를 반환해야 하며, 새 meeting이나 새 review를 만들면 안 됩니다.

## Full E2E Scenario Test

Phase 22 E2E 시나리오는 Watchlist 생성부터 Paper Trading 가상 성과 리포트, Operations Dashboard 확인, Telegram disabled 안전 처리까지 전체 흐름을 HTTP API로 점검합니다.

Backend가 먼저 실행 중이어야 합니다.

```bash
cd ~/AI-council
scripts/run_full_e2e.sh
```

직접 실행:

```bash
python3 examples/integration/run_full_e2e_scenario.py --pretty
python3 examples/integration/run_full_e2e_scenario.py --base-url http://127.0.0.1:8000
```

환경변수:

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_TIMEOUT_SECONDS=30
```

점검 항목:

- `/health`
- Operations summary와 risk brief
- Watchlist 생성과 일괄 분석
- 뉴스/공시 리스크 이벤트 감지
- Ticker Review와 Trade Review 생성
- Paper Portfolio 생성
- 가상 진입/스킵, 청산 조건 평가
- Paper Performance 분석과 Markdown 리포트 생성
- Telegram disabled 상태 안전 처리

기대 안전 조건:

- 모든 응답의 `order_execution_allowed=false`
- Paper Trading 관련 응답의 `simulation_only=true`
- 실제 secret/API key/token 불필요
- 실제 브로커 API 연결 없음
- 실제 주문 생성, 전송, 승인, 취소, 실행 없음

## Operations Diagnostics

Phase 23 diagnostics는 실행 중인 backend의 운영 상태를 한 번에 확인하는 read-only 점검입니다. E2E처럼 긴 시나리오를 API에서 자동 실행하지 않고, 상태와 실행 가능 여부만 확인합니다.

실행:

```bash
cd ~/AI-council
scripts/run_diagnostics.sh
```

직접 실행:

```bash
python3 examples/integration/run_diagnostics.py --pretty
python3 examples/integration/run_diagnostics.py --base-url http://127.0.0.1:8000
```

환경변수:

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_TIMEOUT_SECONDS=30
```

확인 API:

- `/health`
- `/api/diagnostics/summary`
- `/api/diagnostics/security`
- `/api/diagnostics/providers`
- `/api/diagnostics/runtime`
- `/api/diagnostics/e2e-status`

Diagnostics는 `.env` 내용을 읽거나 반환하지 않습니다. Telegram token, Webhook secret, API key는 실제 값을 출력하지 않고 configured 여부만 표시합니다.

## US Trader Oracle Bridge Smoke Test

Phase 24B smoke test는 Oracle 운영본을 직접 수정하지 않고, AI Council의 `us_trader_oracle_v1` mapping profile과 normalize-preview 호환성을 검증합니다.

실행:

```bash
cd ~/AI-council
scripts/run_us_trader_oracle_bridge_smoke.sh
```

직접 실행:

```bash
python3 examples/integration/run_us_trader_oracle_bridge_smoke.py --pretty
```

검증 항목:

- backend `/health`
- `/api/diagnostics/summary`
- US Trader Oracle sample payload JSON validation
- `/api/webhooks/normalize-preview`
- order-like field가 `adapter_warnings`에 기록되는지
- normalize-preview가 trade review를 생성하지 않는지
- `order_execution_allowed=false`

기본 smoke는 preview 중심입니다. `--include-review`를 추가하면 webhook이 configured 상태일 때만 read-only trade-signal review를 선택적으로 검증합니다.

이 smoke test는 Oracle 서버에 접속하지 않고, systemd service를 조작하지 않고, 브로커 API를 호출하지 않고, 실제 주문을 생성하지 않습니다.

## Oracle Sidecar Smoke Test

Phase 24C smoke test는 sample outbox JSON 파일을 임시 디렉터리에 복사한 뒤 sidecar bridge의 dry-run, normalize-preview, duplicate suppression을 검증합니다.

실행:

```bash
cd ~/AI-council
scripts/run_oracle_sidecar_smoke.sh
```

직접 실행:

```bash
python3 examples/integration/run_oracle_sidecar_smoke.py --pretty
```

검증 항목:

- backend `/health`
- diagnostics summary
- `examples/oracle_sidecar/sample_outbox/*.json`
- sidecar bridge dry-run
- sidecar bridge preview mode
- order-like field warning
- high-risk signal preview
- state 기반 duplicate suppression
- `order_execution_allowed=false`

기본 smoke test는 review mode를 실행하지 않습니다. Webhook이 안전하게 configured 상태일 때 별도 환경에서만 review mode를 수동 검증합니다.

이 smoke test는 Oracle 서버에 접속하지 않고, Oracle live bot 파일을 수정하지 않고, systemd service를 조작하지 않고, 실제 주문을 실행하지 않습니다.

## Oracle Export Hook Preflight

Phase 24D preflight는 export hook patch draft가 로컬에서 안전하게 동작하는지 확인합니다.

실행:

```bash
cd ~/AI-council
scripts/run_oracle_export_hook_preflight.sh
```

검증 항목:

- `patch_drafts/ai_council_signal_exporter_module.py` import
- `build_ai_council_signal(...)`
- `validate_export_payload(...)`
- temp outbox atomic write
- generated JSON validation
- sidecar dry-run
- backend가 켜져 있으면 sidecar preview
- `order_execution_allowed=false`

Preflight는 Oracle 서버에 접속하지 않고, 운영봇 파일을 수정하지 않고, 브로커 API를 호출하지 않습니다.

## Oracle Staging Rehearsal

Phase 24E staging rehearsal은 운영봇을 직접 수정하지 않고 로컬 staging copy에서 patch preview를 생성하고 검증합니다.

실행:

```bash
cd ~/AI-council
scripts/run_oracle_staging_rehearsal.sh
```

검증 항목:

- staging copy 생성
- bot 함수 정적 분석
- safe/unsafe insertion point 분류
- unified diff patch preview 생성
- patched preview file 생성
- unsafe function 내부 hook 삽입 여부 검증
- export hook preflight 실행
- `order_execution_allowed=false`

이 리허설은 Oracle 서버에 접속하지 않고, local backup 원본을 수정하지 않고, 실제 주문을 실행하지 않습니다.

## Oracle Deployment Bundle Approval Gate

Phase 24F는 Oracle 적용 전에 deployment bundle을 로컬에서 만들고 검증하며, readiness check를 dry-run으로 확인합니다.

```bash
cd ~/AI-council
scripts/build_oracle_signal_export_bundle.sh
scripts/verify_oracle_signal_export_bundle.sh
scripts/run_oracle_readiness_check_dryrun.sh
```

검증 항목:

- bundle manifest와 sha256
- secret/API key/token/private key marker 없음
- 실제 Oracle IP/SSH key path 하드코딩 없음
- systemd start/stop/restart 자동 실행 없음
- `order_execution_allowed=false`

실제 Oracle 서버에 파일을 쓰거나 service를 조작하지 않습니다.

## 안전

Smoke test와 E2E 시나리오는 브로커 API를 호출하지 않고, 주문을 생성하지 않고, 주문 승인/취소/라우팅을 하지 않으며, 실제 포지션을 변경하지 않습니다. Paper Trading은 내부 가상 시뮬레이션 전용입니다.
