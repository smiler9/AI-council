# US Trader Oracle Export Hook Patch Draft

이 문서는 Oracle US Trader 운영봇에 signal export hook을 나중에 안전하게 삽입하기 위한 patch draft와 사전점검 절차입니다. 이번 단계에서는 Oracle 서버에 patch를 적용하지 않습니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Placeholder 환경

실제 접속 정보와 secret은 문서와 Git에 포함하지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
ORACLE_SSH_KEY=<path-to-private-key>
```

## 왜 직접 Oracle에 patch하지 않는가

Oracle 운영본은 systemd로 실행 중이며 실제 주문 경로를 포함합니다. 따라서 patch를 즉시 적용하지 않고 다음 순서로 검증합니다.

1. 로컬 백업본 정적 분석
2. exporter module preflight
3. sidecar dry-run
4. sidecar preview
5. normalize-preview 결과 확인
6. 운영 적용 전 백업과 rollback 계획 검토
7. maintenance window에서 별도 승인 후 적용 검토

## Export hook 목적

hook은 US Trader가 만든 후보 signal/candidate를 outbox JSON 파일로만 export합니다.

- AI Council review input 생성
- 주문 실행 없음
- 브로커 API 호출 없음
- AI Council 결과를 live order path로 연결하지 않음

## Outbox directory 구조

```text
<oracle-trading-dir>/
├── ai_council_outbox/
├── ai_council_processed/
├── ai_council_failed/
└── ai_council_state/
```

## 적용 후보 위치

로컬 백업본 정적 분석 기준:

- `analyze_signals(ticker)`는 signal dict를 반환합니다.
- `scan_and_enter(...)`는 `entry = {"ticker": ticker, **result}` 구조로 candidate를 만듭니다.
- 이후 `candidates` loop에서 `place_order(...)` 호출 전에 candidate field가 확정됩니다.

안전 후보:

- `analyze_signals(...)` 이후 호출부에서 `entry` 생성 직후
- `scan_and_enter(...)` 내부에서 주문 전 candidate 생성 직후

## 절대 적용하면 안 되는 위치

- `place_order(...)` 내부
- `check_exits(...)` 내부
- `force_close_all(...)` 내부
- 실제 주문 호출 직후
- 주문 성공/실패 결과 처리 branch 내부

## 최소 patch 방향

1. `ai_council_signal_exporter_module.py`를 운영봇과 분리된 helper로 배치
2. outbox directory feature flag를 별도로 둠
3. candidate가 확정된 위치에서 `build_ai_council_signal(...)`
4. `export_ai_council_signal(...)`로 JSON만 atomic write
5. sidecar process가 outbox를 읽어 AI Council normalize-preview로 전송

## Expected payload 구조

```json
{
  "source": "us_trader_oracle",
  "signal_id": "us_trader_oracle_TESTA_breakout_...",
  "symbol": "TESTA",
  "signal": "RSI_DIP+VOLUME_EXPLOSION",
  "action": "buy",
  "price": 0.82,
  "volume": 12500000,
  "timeframe": "5m",
  "indicators": {
    "rsi": 68,
    "volume_ratio": 5.2,
    "signal_score": 3.1
  },
  "risk": {
    "source_function": "scan_and_enter"
  },
  "news": [],
  "review_only": true,
  "simulation_only": false,
  "order_execution_allowed": false
}
```

`action="buy"`는 raw side context입니다. 주문 의도로 사용하지 않습니다.

## 적용 전 백업 명령 예시

아래는 placeholder 예시입니다. 실제 값은 환경별로 별도 관리합니다.

```bash
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
```

백업 전에는 secret 파일을 열거나 출력하지 않습니다.

## 적용 전 dry-run 검증

```bash
cd ~/AI-council
scripts/run_oracle_staging_rehearsal.sh
scripts/run_oracle_export_hook_preflight.sh
scripts/run_oracle_sidecar_smoke.sh
```

확인:

- generated payload JSON valid
- `order_execution_allowed=false`
- sidecar dry-run passed
- sidecar preview passed
- review mode는 실행하지 않음

Phase 24E staging rehearsal은 운영본을 수정하지 않고 patch preview를 생성하고 정적 검증합니다.

## 적용 후 preview-only 검증 절차

1. outbox에 JSON 생성 확인
2. sidecar `--mode preview`
3. AI Council normalize-preview 응답 확인
4. trade review가 생성되지 않는지 확인
5. order-like fields가 warning으로만 기록되는지 확인

## systemd 재시작 전 확인할 것

- patch diff review 완료
- backup 경로 확인
- rollback plan 확인
- outbox directory 권한 확인
- preview-only 결과 확인
- live order path와 연결되지 않았는지 확인

이번 단계에서는 systemd service를 재시작하지 않습니다.

## Rollback 절차

1. sidecar process만 종료
2. outbox export feature flag 비활성화
3. generated outbox/state 보존
4. patch 적용 전 백업본과 diff 확인
5. live bot service는 임의 조작하지 않음

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
