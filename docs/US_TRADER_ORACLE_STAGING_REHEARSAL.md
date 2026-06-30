# US Trader Oracle Staging Rehearsal

Phase 24E는 Oracle에서 실행 중인 US Trader 운영봇을 직접 수정하지 않고, 로컬 스테이징 복사본에서 signal export hook 삽입 가능성을 검증하는 단계입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 왜 staging rehearsal이 필요한가

Oracle 운영본에는 live trading 경로가 포함되어 있습니다. 운영본을 바로 patch하면 주문 경로와 signal export 경로가 섞일 위험이 있습니다. 따라서 먼저 로컬 fixture 또는 로컬 백업본 복사본으로 다음을 확인합니다.

- 함수 위치 정적 분석
- safe insertion candidate 확인
- unsafe insertion point 차단
- patch preview 생성
- patched preview 정적 검증
- sidecar dry-run
- normalize-preview
- export hook preflight

## 운영본 직접 수정 금지 원칙

이번 단계에서는 다음을 하지 않습니다.

- Oracle 서버 파일 수정
- Oracle systemd service start/stop/restart
- Oracle live bot 실행/중지/재시작
- `penny_stock_bot.py` 운영본 patch 적용
- 브로커 API 호출
- 실제 주문 생성/전송/승인/취소/실행

## Local staging copy 절차

기본 fixture 기반:

```bash
cd ~/AI-council
python3 examples/oracle_staging/prepare_staging_rehearsal.py --pretty
```

로컬 백업본을 대상으로 할 경우:

```bash
python3 examples/oracle_staging/prepare_staging_rehearsal.py \
  --source-bot "/path/to/local/backup/penny_stock_bot.py" \
  --output tmp/oracle_staging_rehearsal \
  --pretty
```

원본 파일은 수정하지 않고 staging copy만 생성합니다.

## Analyzer 사용법

```bash
python3 examples/oracle_staging/analyze_us_trader_bot.py \
  --source tmp/oracle_staging_rehearsal/penny_stock_bot.py \
  --pretty
```

확인 항목:

- `analyze_signals`
- `scan_and_enter`
- `place_order`
- `check_exits`
- `force_close_all`
- safe insertion candidates
- unsafe insertion points
- `order_execution_allowed=false`

## Patch preview 생성법

Diff only:

```bash
python3 examples/oracle_staging/generate_export_hook_patch_preview.py \
  --source tmp/oracle_staging_rehearsal/penny_stock_bot.py \
  --diff-only \
  --pretty
```

Patched preview file 생성:

```bash
python3 examples/oracle_staging/generate_export_hook_patch_preview.py \
  --source tmp/oracle_staging_rehearsal/penny_stock_bot.py \
  --output tmp/oracle_staging_rehearsal/penny_stock_bot.patched.preview.py \
  --pretty
```

생성 파일은 staging output에만 둡니다. 운영본에 적용하지 않습니다.

## Staging patched preview 검증

```bash
python3 examples/oracle_staging/validate_staging_patch.py \
  --source tmp/oracle_staging_rehearsal/penny_stock_bot.patched.preview.py \
  --pretty
```

검증 항목:

- exporter module import 존재
- `export_ai_council_signal(...)` 호출 존재
- `place_order/check_exits/force_close_all` 내부 삽입 없음
- broker/order API 호출 추가 없음
- secret/API key/token/private key marker 없음
- `order_execution_allowed=false`

## 전체 리허설

```bash
scripts/run_oracle_staging_rehearsal.sh
```

이 스크립트는 임시 디렉터리에 staging copy를 만들고 analyze, patch preview, validate, export hook preflight를 실행합니다.

## Preflight와 sidecar smoke 연결

```bash
scripts/run_oracle_export_hook_preflight.sh
scripts/run_oracle_sidecar_smoke.sh
```

두 스크립트 모두 Oracle 서버에 접속하지 않고 실제 주문을 실행하지 않습니다.

## Oracle 적용 전 필요한 수동 검토

- patch preview diff 수동 검토
- safe insertion 위치 확인
- unsafe function 내부 삽입이 없는지 확인
- outbox directory 권한 확인
- rollback plan 확인
- maintenance window 계획
- preview-only 결과 확인

## Rollback 계획

1. sidecar process만 종료
2. export hook feature flag 비활성화
3. outbox/state 보존
4. staging diff와 운영본 diff 비교
5. live service는 별도 승인 없이 조작하지 않음

## Placeholder

실제 Oracle 정보는 문서에 넣지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
ORACLE_SSH_KEY=<path-to-private-key>
```

## 다음 단계 Phase 24F 후보

- 로컬 백업본 대상 patch preview 정밀 diff 리뷰
- exporter feature flag 설계
- Oracle 적용 전 read-only deployment checklist 강화
- 운영 적용은 별도 승인 후 maintenance window에서만 검토

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
