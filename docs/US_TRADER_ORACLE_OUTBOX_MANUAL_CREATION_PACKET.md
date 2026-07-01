# US Trader Oracle Outbox Manual Creation Packet

## Phase 24P 목적

Phase 24P는 Phase 24O의 GO decision을 바탕으로, 사람이 Oracle 서버에서 outbox 관련 디렉터리를 수동 생성하기 전에 검토할 command packet을 만듭니다.

이번 단계는 packet 생성, command review, packet verify, 문서, 테스트까지만 수행합니다. Codex와 AI Council은 Oracle 서버에 접속해 파일을 만들거나 업로드하지 않고, systemd를 조작하지 않고, 운영봇을 수정하지 않습니다.

## GO가 의미하는 것과 의미하지 않는 것

GO는 outbox 수동 생성 command packet을 검토할 수 있다는 뜻입니다.

GO가 의미하지 않는 것:

- 실제 Oracle 적용 승인
- 운영봇 수정 승인
- systemd 조작 승인
- 브로커 API 연결 승인
- 주문 실행 승인
- export hook 적용 승인

## Command Packet 생성

```bash
scripts/build_oracle_outbox_manual_creation_packet.sh
```

입력:

- `tmp/oracle_outbox_precreation/precreation_plan.json`
- `tmp/oracle_precheck_intake/go_no_go_decision.json`

출력:

- `tmp/oracle_outbox_manual_creation/manifest.json`
- `tmp/oracle_outbox_manual_creation/manual_creation_commands.example.sh`
- `tmp/oracle_outbox_manual_creation/post_creation_verify_commands.example.sh`
- `tmp/oracle_outbox_manual_creation/creation_result_record.example.json`
- `tmp/oracle_outbox_manual_creation/rollback_after_creation.example.sh`
- `tmp/oracle_outbox_manual_creation/manual_creation_checklist.md`

## Command Review

```bash
scripts/review_oracle_outbox_creation_commands.sh
```

검사 항목:

- 활성 `mkdir`, `chmod`, `chown`, `rm`, `mv`, `systemctl` 명령 없음
- 주석 처리된 `mkdir` 후보는 manual command로만 분류
- `systemctl start/stop/restart/reload` 활성 명령 없음
- `penny_stock_bot.py` 실행 또는 수정 명령 없음
- secret/API key/token/private key/실제 Oracle key path 없음
- `order_execution_allowed=false`

## Packet Verify

```bash
scripts/verify_oracle_outbox_manual_creation_packet.sh
```

검증 항목:

- `manifest.json` sha256 검증
- `creation_result_record.example.json` 기본값 확인
- `creation_executed=false`
- `remote_write_executed=false`
- `systemd_changed=false`
- `live_bot_modified=false`
- `order_execution_allowed=false`
- command review 통과

## 실제 실행 전 확인할 것

- Phase 24O GO decision이 실제 적용 승인이 아니라는 점 확인
- command packet이 최신 precreation plan과 GO decision에서 생성됐는지 확인
- 수동 생성 명령이 주석 처리되어 있는지 확인
- Oracle 운영봇 백업과 rollback 계획 확인
- systemd 운영 서비스가 변경되지 않는지 확인
- 실제 주문/브로커 API 경로와 무관함 확인

## 실행 후 기록 방법

사람이 나중 단계에서 수동 생성 작업을 수행했다면, `creation_result_record.example.json`을 복사해 별도 기록 파일로 작성합니다.

기본 record는 다음 상태입니다.

- `creation_executed=false`
- `remote_write_executed=false`
- `systemd_changed=false`
- `live_bot_modified=false`
- `order_execution_allowed=false`
- `result_status=incomplete`

## Rollback 기준

Rollback은 자동 삭제가 아닙니다. outbox에 signal JSON이 쌓였을 수 있으므로 원격 삭제/이동은 별도 승인 전 금지합니다.

기본 rollback 기준:

- 추가 rollout 중단
- Mac pull 중단
- 생성된 경로의 내용 보존
- 로그와 signal 파일 유무 확인
- 별도 승인 전 `rm`, `rmdir`, `mv`, `chmod`, `chown` 실행 금지

## 금지 사항

- Oracle 서버에 자동 파일 쓰기
- Oracle 서버에 파일 업로드
- `systemctl start/stop/restart/reload`
- `penny_stock_bot.py` 수정
- 운영봇 실행/중지/재시작
- 실제 브로커 API 연결
- 실제 주문 생성, 전송, 승인, 취소, 실행

## 다음 Phase 24Q 제안

Phase 24Q에서는 사람이 실제로 수동 생성 작업을 수행했다는 기록을 안전하게 intake하고, post-creation verification 결과를 검증하는 단계로 진행할 수 있습니다.

## Phase 24Q Creation Result Verification

Phase 24Q 결과 문서:

- `docs/US_TRADER_ORACLE_OUTBOX_CREATION_RESULT_VERIFICATION.md`
- `examples/oracle_outbox_creation_result/`
- `scripts/run_oracle_outbox_creation_result_dryrun.sh`

Phase 24Q의 GO decision은 preview signal file write rehearsal로 넘어갈 수 있다는 뜻일 뿐이며 운영봇 patch 승인, systemd 조작 승인, 주문 실행 승인이 아닙니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.

## Phase 24R Preview Signal Write Rehearsal

Phase 24R 결과 문서:

- `docs/US_TRADER_ORACLE_PREVIEW_SIGNAL_WRITE_REHEARSAL.md`
- `examples/oracle_preview_signal_write/`
- `scripts/run_oracle_preview_signal_write_dryrun.sh`

Phase 24R의 manual signal write packet은 preview signal 파일을 사람이 수동 업로드할 수 있도록 주석 처리된 scp/rsync 후보만 제공합니다. Codex가 Oracle에 파일을 쓰거나 업로드하지 않으며 GO는 Mac Pull 리허설 허용일 뿐 운영봇 patch 승인이 아닙니다.
