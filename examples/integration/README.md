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

## 안전

Smoke test는 브로커 API를 호출하지 않고, 주문을 생성하지 않고, 주문 승인/취소/라우팅을 하지 않으며, 포지션을 변경하지 않습니다.
