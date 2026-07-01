# US Trader Oracle Preview Signal Write Rehearsal

## Phase 24R 목적

Phase 24R는 Oracle outbox 디렉터리가 사람이 수동 생성한 뒤, 운영봇 patch 전에 테스트용 preview signal JSON 파일 하나를 outbox에 수동으로 넣어보는 절차를 준비합니다.

이 단계는 preview signal 생성, signal 검증, 수동 write command packet 생성, write 결과 기록, 결과 검증, Mac pull rehearsal GO/NO-GO 판단까지만 다룹니다.

## 왜 필요한가

운영봇 export hook을 넣기 전에 outbox 파일 계약과 Mac pull 처리 흐름을 가장 작은 단위로 검증해야 합니다. 이 리허설은 운영봇을 수정하지 않고 사람이 TESTA preview 파일 하나만 검토할 수 있게 해줍니다.

## Preview Signal 생성

```bash
cd ~/AI-council
scripts/build_oracle_preview_signal_file.sh
```

생성 파일은 `tmp/oracle_preview_signal_write/us_trader_preview_signal.json`입니다. 이 파일은 TESTA 테스트 ticker만 사용하며 다음 안전 필드를 포함합니다.

- `review_only=true`
- `simulation_only=true`
- `order_execution_allowed=false`

`action=buy`는 raw review context로만 보존됩니다. 주문 의도가 아닙니다.

## Preview Signal 검증

```bash
scripts/verify_oracle_preview_signal_file.sh
```

검증 항목:

- 필수 필드 존재
- `review_only=true`
- `simulation_only=true`
- `order_execution_allowed=false`
- secret/API key/token/private key marker 없음
- 실제 Oracle IP/SSH key path 하드코딩 없음
- order-like field는 warning으로만 처리

## Manual Write Packet

```bash
scripts/build_oracle_preview_signal_write_packet.sh
scripts/verify_oracle_preview_signal_write_packet.sh
```

packet은 `tmp/oracle_preview_signal_write/manual_write_packet/`에 생성됩니다. scp/rsync 예시는 주석 처리된 manual command 후보입니다. Codex와 스크립트는 Oracle에 업로드하지 않습니다.

## 수동 업로드 전 확인

- Phase 24Q post-creation GO decision이 있는지 확인
- GO가 운영봇 patch 승인이나 주문 승인으로 해석되지 않는지 확인
- manual write command가 사람이 검토한 주석 처리 예시인지 확인
- systemd 조작이 없는지 확인
- 운영봇 파일 수정이 없는지 확인

## 수동 업로드 후 결과 기록

사람이 Oracle에서 preview signal 파일을 수동 업로드한 뒤, 결과를 로컬 JSON으로 기록합니다.

```bash
scripts/record_oracle_preview_signal_write_sample_result.sh
scripts/verify_oracle_preview_signal_write_result.sh
```

실제 결과를 기록할 때 secret 값, private key path, account value는 넣지 않습니다. host/user/outbox path는 placeholder 또는 일반화된 값으로 기록합니다.

## Mac Pull Rehearsal GO/NO-GO

```bash
scripts/decide_oracle_pull_rehearsal_go_no_go.sh
```

GO 조건:

- write result validation 통과
- preview 파일이 수동 업로드되었다고 기록됨
- 파일 존재/readable/JSON valid 확인
- post-write 검증이 read-only였음
- systemd 변경 없음
- 운영봇 수정 없음
- secret 노출 없음
- broker API 호출 없음
- `order_execution_allowed=false`

## GO가 의미하는 것과 의미하지 않는 것

GO는 Mac pull rehearsal 단계로 넘어갈 수 있다는 뜻입니다.

GO가 의미하지 않는 것:

- 운영봇 patch 승인
- export hook 적용 승인
- systemd 조작 승인
- 브로커 API 연결 승인
- 실제 주문 생성/전송/승인/취소/실행 승인

## Dry-run

```bash
scripts/run_oracle_preview_signal_write_dryrun.sh
```

이 dry-run은 로컬 `tmp/` 산출물만 만들고 Oracle 서버에 접속하지 않습니다.

## 금지 사항

- Oracle 서버에 Codex가 자동 파일 쓰기
- Oracle 서버 자동 업로드
- `mkdir`, `touch`, `cp`, `mv`, `rm`, `chmod`, `chown` 실행
- `systemctl start/stop/restart/reload`
- `penny_stock_bot.py` 수정
- 운영봇 실행/중지/재시작
- 실제 브로커 API 연결
- 실제 주문 생성, 전송, 승인, 취소, 실행

## 다음 Phase 24S 조건

- Phase 24R dry-run 통과
- 사람이 preview signal 파일 write 결과를 안전하게 기록
- write result verify 통과
- Mac pull rehearsal GO decision 생성
- GO의 범위가 Mac pull rehearsal로만 제한됨을 확인

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
