# Oracle Sidecar Signal Bridge

이 폴더는 Oracle에서 실행 중인 US Trader 운영봇을 직접 수정하거나 재시작하지 않고, 향후 signal JSON outbox를 통해 AI Council로 read-only review를 보내기 위한 샘플입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 구성

```text
examples/oracle_sidecar/
├── us_trader_signal_outbox_bridge.py
├── signal_exporter_hook_example.py
├── sample_outbox/
├── sample_state/
└── .env.example
```

## Sidecar bridge

기본 모드는 `preview`입니다. `preview`는 AI Council `/api/webhooks/normalize-preview`만 호출하고 trade review를 생성하지 않습니다.

Dry-run:

```bash
cd ~/AI-council
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --dry-run \
  --pretty
```

Preview:

```bash
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --pretty
```

Review-only mode:

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

`review` mode도 실제 주문이 아니라 AI Council read-only trade review 생성만 수행합니다.

## State와 중복 처리

Bridge는 `source + signal_id`를 state file에 기록해 같은 signal을 재전송하지 않습니다. 기본 sample state JSON은 Git에 포함하지 않습니다.

`--move-files`를 명시하면 성공 파일은 processed directory로, 실패 파일은 failed directory로 이동합니다. 기본값은 파일 이동 없이 state만 기록합니다.

## Watch mode

`--watch`를 명시하면 outbox를 주기적으로 polling합니다. 기본은 한 번만 실행하는 모드입니다.

```bash
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox /path/to/outbox \
  --state /path/to/state.json \
  --mode preview \
  --watch \
  --poll-seconds 10
```

운영 적용 전에는 `--watch`를 사용하지 말고 dry-run과 preview를 먼저 검증하십시오.

## Exporter hook example

`signal_exporter_hook_example.py`는 참고용 JSON export helper입니다. Oracle 운영본에 자동 적용하지 않습니다.

역할:

- signal dict를 AI Council 호환 JSON으로 구성
- temp file에 먼저 쓴 뒤 rename하는 atomic write
- `source="us_trader_oracle"`
- `order_execution_allowed=false`

금지:

- 브로커 API 호출
- live service 제어
- 주문 생성/전송
- 포지션 변경

## Phase 24D patch draft와 preflight

Patch draft 위치:

- `patch_drafts/README.md`
- `patch_drafts/penny_stock_bot_export_hook_patch_draft.md`
- `patch_drafts/ai_council_signal_exporter_module.py`
- `patch_drafts/oracle_apply_checklist.md`

Preflight 실행:

```bash
cd ~/AI-council
scripts/run_oracle_export_hook_preflight.sh
```

Preflight는 다음을 로컬에서만 확인합니다.

- exporter module import
- review-only payload 생성
- temp outbox atomic write
- sidecar dry-run
- backend가 켜져 있으면 normalize-preview
- `order_execution_allowed=false`

Preflight는 Oracle 서버에 접속하지 않고, 운영봇 파일을 수정하지 않고, 실제 주문을 실행하지 않습니다.

## Phase 24E staging rehearsal

로컬 스테이징 복사본에서 patch preview를 검증하려면 다음을 실행합니다.

```bash
cd ~/AI-council
scripts/run_oracle_staging_rehearsal.sh
```

이 리허설은 `examples/oracle_staging/`의 analyzer, staging copy 준비 도구, patch preview generator, validator를 사용합니다. 운영본이나 로컬 원본을 직접 수정하지 않고 임시 staging output만 생성합니다.

## Sample payloads

- `sample_outbox/us_trader_signal_001.json`
- `sample_outbox/us_trader_signal_order_like.json`
- `sample_outbox/us_trader_signal_high_risk.json`

샘플 ticker는 TESTA, TESTB만 사용합니다. 실제 종목 추천, 계좌 정보, secret/API key/token/private key는 포함하지 않습니다.

## Smoke test

```bash
cd ~/AI-council
scripts/run_oracle_sidecar_smoke.sh
```

이 smoke test는 Oracle 서버에 접속하지 않고, systemd service를 조작하지 않고, 실제 주문을 실행하지 않습니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
