# US Trader Oracle Read-only Integration

이 문서는 Oracle에서 실행 중인 US Trader 운영본을 직접 수정하지 않고, AI Council이 후보 신호 payload를 검토용으로만 받는 안전 연동 방식을 설명합니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 운영본 확인 요약

Phase 24A discovery에서 Oracle 운영본은 다음 형태로 확인되었습니다.

- 접속 정보: `ORACLE_USER=<oracle-user>`, `ORACLE_HOST=<oracle-host>`, `ORACLE_SSH_KEY=<path-to-private-key>`
- 배포 경로: `<oracle-us-trader-deploy-path>`
- 실행 파일 후보: `penny_stock_bot.py`, `server.py`
- 실행 방식 후보: `systemd`
- signal 생성 후보: `analyze_signals(...)`, `scan_and_enter(...)`
- 주문 실행 후보: `place_order(...)`, `check_exits(...)`, `force_close_all(...)`
- secret/config 후보: `.secrets/`, `.secrets/kis_config.json`

실제 host, private key path, secret, account, token 값은 문서와 Git에 포함하지 않습니다.

## 왜 운영본을 직접 수정하지 않는가

Oracle 운영본에는 live trading과 연결될 수 있는 주문 실행 경로가 있습니다. AI Council의 역할은 review, risk analysis, decision support입니다. 따라서 운영 중인 `penny_stock_bot.py`, systemd service, secret/config 파일은 직접 수정하지 않습니다.

금지 사항:

- Oracle live bot 파일 수정
- `systemctl start/stop/restart`
- 봇 실행, 중지, 재시작
- 브로커 API 호출
- 주문 생성, 주문 전송, 주문 승인, 주문 취소, 포지션 변경
- secret/API key/token/private key 출력 또는 저장

## Level 1: Normalize Preview

US Trader signal payload를 AI Council normalize-preview로 보내 정규화 결과만 확인합니다. 이 단계는 trade review를 만들지 않습니다.

```bash
cd ~/AI-council
python3 examples/external_bot/us_trader_oracle_bridge.py \
  --payload examples/external_bot/sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --preview \
  --pretty
```

또는 dry-run:

```bash
python3 examples/external_bot/us_trader_oracle_bridge.py \
  --payload examples/external_bot/sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --dry-run \
  --pretty
```

## Level 2: Read-only Trade Review

Webhook이 안전하게 활성화된 AI Council backend에만 trade-signal review를 보냅니다. 이 단계도 주문을 실행하지 않습니다.

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=<webhook-secret>

python3 examples/external_bot/us_trader_oracle_bridge.py \
  --payload examples/external_bot/sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --review \
  --pretty
```

응답의 `decision`, `risk_level`, `adapter_warnings`, `order_execution_allowed=false`를 확인합니다.

## Level 3: Paper Simulation

AI Council review 결과를 내부 가상 포트폴리오에만 반영합니다. Paper Trading은 `simulation_only=true`이며 실제 주문, 실제 체결, 실제 포지션 변경이 아닙니다.

권장 흐름:

1. normalize-preview로 payload 호환성 확인
2. trade-signal로 read-only review 생성
3. paper portfolio의 simulate-review API에 review id 입력
4. 가상 진입/스킵/청산과 성과 리포트를 확인

## Mapping Profile

`examples/external_bot/mapping_profiles/us_trader_oracle_v1.json`은 Oracle US Trader payload alias를 AI Council 표준 필드로 매핑합니다.

지원 예:

- `symbol`, `ticker`, `code`, `stock`, `item`, `item_code` -> `ticker`
- `signal`, `setup`, `scan_reason`, `trigger`, `strategy` -> `strategy_signal`
- `action`, `side`, `direction`, `intent`, `order_side` -> `raw_side`
- `price`, `last_price`, `current_price`, `entry_price`, `base_price` -> `price`
- `volume`, `vol`, `day_volume`, `acc_volume` -> `volume`

`buy`, `sell`, `entry`, `exit` 같은 값은 `raw_side`에만 보존되고, normalized `side`는 `review_only`로 안전하게 변환됩니다.

## Order-like Field 안전 정책

다음 필드는 raw payload에만 보존하고 주문 로직으로 연결하지 않습니다.

- `quantity`
- `qty`
- `shares`
- `order_type`
- `stop_loss`
- `take_profit`
- `broker`
- `account`
- `route`
- `tif`
- `submit_order`
- `place_order`

AI Council adapter는 이를 `adapter_warnings`에 기록하고 `order_execution_allowed=false`를 유지합니다.

## Smoke Test

기본 smoke test는 preview 중심으로 동작하며 Oracle 서버에 접속하지 않습니다.

```bash
cd ~/AI-council
scripts/run_us_trader_oracle_bridge_smoke.sh
```

직접 실행:

```bash
python3 examples/integration/run_us_trader_oracle_bridge_smoke.py --pretty
```

## 향후 Oracle Read-only Exporter 설계

필요하면 운영본을 직접 수정하기 전에 별도 read-only exporter를 설계합니다.

원칙:

- live bot 주문 경로와 분리
- signal JSON만 읽거나 별도 파일/로그에서 추출
- AI Council normalize-preview 또는 trade-signal로 전송
- systemd service와 live bot 상태를 제어하지 않음
- AI Council 판단 결과를 주문 함수에 직접 연결하지 않음

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
