# US Trader Oracle Outbox Path Approval

## Phase 24K 목적

Phase 24K는 Oracle US Trader 운영봇에 signal export hook을 실제 적용하기 전에 outbox, processed, failed, state, log 경로 후보를 placeholder 기준으로 확정하고 수동 승인 패키지를 준비합니다.

이번 단계에서는 Oracle 서버 파일을 수정하지 않고, 디렉터리를 생성하지 않고, systemd service를 조작하지 않습니다.

## Outbox 방식의 역할

Outbox 방식은 Oracle 운영봇과 AI Council을 직접 결합하지 않습니다.

- Oracle 운영봇: signal JSON 파일을 승인된 outbox directory에만 기록
- Mac AI Council: outbox JSON을 read-only로 pull해 `normalize-preview` 처리
- AI Council: 검토, 리스크 분석, 의사결정 보조만 수행

## Oracle 운영봇이 생성할 파일

미래 export hook은 다음 형태의 JSON만 생성해야 합니다.

```text
<oracle-trading-dir>/ai_council_outbox/us_trader_signal_<timestamp>_<signal_id>.json
```

파일은 `.tmp`에 먼저 쓰고 rename하는 atomic write 방식을 사용합니다.

## Mac AI Council이 Pull할 파일

Mac pull pipeline은 다음 파일만 읽습니다.

```text
<oracle-trading-dir>/ai_council_outbox/*.json
```

Mac pull은 원격 파일을 삭제하거나 이동하지 않습니다.

## 원격 삭제/이동 금지 원칙

- `remote_delete=false`
- `remote_move=false`
- 원격 권한 변경 없음
- 원격 directory 생성 자동화 없음
- systemd start/stop/restart/reload 없음
- 운영봇 실행/중지/재시작 없음

## 권장 경로 후보

실제 Oracle IP, 사용자, SSH key path는 이 문서에 기록하지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_SSH_KEY=<path-to-private-key>
ORACLE_TRADING_DIR=<oracle-trading-dir>
```

경로 후보:

- `<oracle-trading-dir>/ai_council_outbox/`
- `<oracle-trading-dir>/ai_council_processed/`
- `<oracle-trading-dir>/ai_council_failed/`
- `<oracle-trading-dir>/ai_council_state/`
- `<oracle-trading-dir>/logs/ai_council_export.log`

Phase 24K에서는 위 경로를 문서상 후보로만 확정하며 실제 서버에 생성하지 않습니다.

## 권한 검토

수동 승인 전 확인할 항목:

- 운영봇 실행 사용자만 outbox에 쓸 수 있는지
- Mac pull 사용자는 read-only로 충분한지
- `.secrets/`와 outbox가 분리되어 있는지
- log 파일에 secret이 남지 않는지

## 용량 검토

수동 승인 전 확인할 항목:

- outbox JSON 예상 생성량
- JSON 파일당 크기
- 로그 증가량
- local pulled cache 보존 기간
- 수동 cleanup 담당자

## 중복 처리

AI Council Mac pull pipeline은 `source + signal_id`를 중복 기준으로 사용합니다.

원격 파일 이름이 달라도 같은 `source + signal_id`이면 재처리하지 않습니다.

## Rollback

상세 rollback은 approval package의 `outbox_rollback_plan.md`에 있습니다.

기본 원칙:

- Mac pull 중단
- review mode 비활성화
- remote outbox 파일 보존
- 운영봇 service 조작 금지
- 실제 주문 경로와 연결 금지

## Approval Package

생성:

```bash
scripts/build_oracle_outbox_approval_package.sh
```

검증:

```bash
scripts/verify_oracle_outbox_approval_package.sh
```

전체 dry-run:

```bash
scripts/run_oracle_outbox_approval_dryrun.sh
```

생성 결과는 `tmp/oracle_outbox_approval/`에 저장되며 Git에 포함하지 않습니다.

## 실제 적용 전 체크

- sidecar preview smoke 통과
- Mac pull smoke 통과
- normalize-preview 통과
- approval package verify 통과
- precreation plan verify 통과
- manual precreation command package 검토
- rollback plan 확인
- 실제 주문 연결 없음 확인

## Phase 24L Outbox 생성 전 리허설

Phase 24L은 이 문서의 경로 후보를 바탕으로 실제 Oracle 서버에 디렉터리를 만들기 전 precreation plan과 manual command package를 생성합니다.

- `docs/US_TRADER_ORACLE_OUTBOX_PRECREATION_REHEARSAL.md`
- `examples/oracle_outbox_precreation/`
- `scripts/run_oracle_outbox_precreation_dryrun.sh`

생성되는 command package는 로컬 `tmp/oracle_outbox_precreation/commands/`에만 저장됩니다. `mkdir`, `chmod`, `chown`, `rm`, `mv` 예시는 주석 처리되어 있으며 `systemctl` 조작은 포함하지 않습니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
