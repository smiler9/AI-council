# US Trader Oracle Outbox Creation Result Verification

## Phase 24Q 목적

Phase 24Q는 사람이 Oracle에서 outbox/processed/failed/state 디렉터리를 수동 생성한 뒤, 그 결과를 표준 JSON으로 기록하고 검증하며 다음 단계로 넘어갈지 GO/NO-GO를 판단합니다.

이번 단계는 결과 기록, 검증, 판단, 문서, 테스트까지만 수행합니다. Codex와 AI Council은 Oracle 서버에 접속해 파일을 만들거나 업로드하지 않고, systemd를 조작하지 않고, 운영봇을 수정하지 않습니다.

## 왜 결과를 기록해야 하는가

수동 생성 결과를 터미널 로그나 기억에만 의존하면 다음 단계에서 권한, 경로, safety flag를 재현하기 어렵습니다. Creation result JSON은 생성된 경로와 post-creation read-only 검증 결과를 구조화해 다음 단계 판단을 감사 가능하게 만듭니다.

## Result Template 생성

```bash
scripts/build_oracle_outbox_creation_result_template.sh
```

출력:

```text
tmp/oracle_outbox_creation_result/creation_result_template.json
```

## Result 기록

샘플 기록:

```bash
scripts/record_oracle_outbox_creation_sample_result.sh
```

사람이 실제 결과를 기록할 때는 secret, API key, token, private key, 계좌 정보, config 내용을 쓰지 않습니다. Oracle host/user/key path는 placeholder 또는 일반화된 값으로 기록합니다.

## Result Verify

```bash
scripts/verify_oracle_outbox_creation_result.sh
```

검증 항목:

- outbox/processed/failed/state directory 존재
- directory readable
- expected user write 가능
- disk space OK
- post-creation verify가 read-only였음
- `systemd_changed=false`
- `live_bot_modified=false`
- `penny_stock_bot_modified=false`
- `secrets_exposed=false`
- `broker_api_called=false`
- `order_execution_allowed=false`

## Go/No-Go 판단

```bash
scripts/decide_oracle_post_creation_go_no_go.sh
```

GO 조건:

- `validation_status=passed`
- `result_status=passed` 또는 `warning`
- 필수 directory/권한/디스크 조건 충족
- systemd/운영봇/penny_stock_bot/secret/broker/order safety flag가 모두 안전

NO-GO 조건:

- 필수 directory 누락
- 권한 문제
- disk space 부족
- systemd 변경
- 운영봇 또는 `penny_stock_bot.py` 수정
- secret 노출
- broker API 호출
- `order_execution_allowed` true 상태
- `result_status=failed`

## GO가 의미하는 것과 의미하지 않는 것

GO는 preview signal file write rehearsal 단계로 넘어갈 수 있다는 뜻입니다.

GO가 의미하지 않는 것:

- 실제 운영봇 patch 승인
- export hook 적용 승인
- systemd 조작 승인
- 브로커 API 연결 승인
- 주문 실행 승인
- live trading 변경 승인

## 다음 Phase 24R 조건

- manual creation dry-run 통과
- creation result template 생성 통과
- creation result verify 통과
- post-creation GO decision 생성
- 사람이 GO의 범위를 이해하고 별도 수동 승인

## 금지 사항

- Oracle 서버에 자동 파일 쓰기
- Oracle 서버에 파일 업로드
- `systemctl start/stop/restart/reload`
- `penny_stock_bot.py` 수정
- 운영봇 실행/중지/재시작
- 실제 브로커 API 연결
- 실제 주문 생성, 전송, 승인, 취소, 실행

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
