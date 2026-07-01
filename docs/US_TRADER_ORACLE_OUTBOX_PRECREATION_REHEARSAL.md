# US Trader Oracle Outbox Pre-creation Rehearsal

## Phase 24L 목적

Phase 24L는 Oracle US Trader 운영봇에 signal export hook을 적용하기 전에 outbox, processed, failed, state 디렉터리를 어떻게 만들지 사람이 수동으로 검토할 수 있는 plan, command package, checklist, rollback 절차를 준비합니다.

이번 단계는 리허설입니다. Oracle 서버에 디렉터리를 만들지 않고, 파일을 업로드하지 않고, systemd 서비스를 조작하지 않으며, `penny_stock_bot.py` 운영본도 수정하지 않습니다.

## 왜 Pre-creation이 필요한가

Outbox 방식에서는 운영봇이 JSON signal 파일을 특정 경로에 쓰고, Mac AI Council이 해당 파일을 read-only로 가져와 normalize-preview 또는 read-only review를 수행합니다. 실제 hook 적용 전에 경로, 권한, 용량, 보존 정책, rollback을 확정해야 운영봇과 주문 경로를 분리할 수 있습니다.

## 아직 실제 생성하지 않는 이유

- 운영봇 변경 전 승인 게이트를 유지하기 위해
- 원격 디렉터리 생성, 권한 변경, 삭제 명령을 자동화하지 않기 위해
- systemd 운영 서비스를 건드리지 않기 위해
- 실제 주문/브로커 API와 연결될 가능성을 차단하기 위해

## Plan 생성

```bash
scripts/build_oracle_outbox_precreation_plan.sh
```

기본 출력:

```text
tmp/oracle_outbox_precreation/precreation_plan.json
```

Plan은 placeholder 경로만 포함합니다.

```text
<oracle-trading-dir>/ai_council_outbox
<oracle-trading-dir>/ai_council_processed
<oracle-trading-dir>/ai_council_failed
<oracle-trading-dir>/ai_council_state
<oracle-trading-dir>/logs/ai_council_export.log
```

## Plan 검증

```bash
scripts/verify_oracle_outbox_precreation_plan.sh
```

검증 항목:

- `manual_approval_required=true`
- `remote_write_executed=false`
- `remote_delete=false`
- `remote_move=false`
- `systemd_changes_planned=false`
- `order_execution_allowed=false`
- 실제 Oracle IP, SSH key path, secret, token 없음
- path traversal 없음
- live/order/trading execution mode 없음

## Manual Command 생성

```bash
scripts/generate_oracle_outbox_precreation_commands.sh
```

기본 출력:

```text
tmp/oracle_outbox_precreation/commands/
```

생성 파일:

- `00_check_existing_paths.manual.sh`
- `01_create_outbox_dirs.manual.sh`
- `02_verify_outbox_dirs.manual.sh`
- `03_permissions_review.manual.sh`
- `99_rollback_outbox_dirs.manual.sh`

변경성 명령인 `mkdir`, `chmod`, `chown`, `rm`, `mv`는 모두 주석 처리되어 있으며 자동 실행되지 않습니다. `systemctl` 명령은 포함하지 않습니다.

## 전체 Dry-run

```bash
scripts/run_oracle_outbox_precreation_dryrun.sh
```

Dry-run은 로컬 `tmp/` 아래에만 산출물을 만들며 Oracle 서버에 접속하지 않습니다.

## 사람이 수동 확인할 항목

- Outbox 경로 승인
- Processed/failed/state/log 경로 승인
- 운영봇 백업 확인
- 디스크 여유 확인
- 권한/소유자 확인
- Export hook 적용 전임 확인
- `place_order`, `check_exits`, `force_close_all` 내부 미삽입 확인
- Mac pull smoke 통과
- Outbox approval dry-run 통과
- Precreation dry-run 통과
- Rollback 기준 확인

## 명령 실행 전 승인 조건

실제 Oracle에서 디렉터리 생성은 다음 조건이 모두 충족된 뒤 별도 수동 승인으로만 진행합니다.

- `docs/US_TRADER_ORACLE_OUTBOX_PATH_APPROVAL.md` 승인
- `scripts/run_oracle_outbox_approval_dryrun.sh` 통과
- `scripts/run_oracle_pull_smoke.sh` 통과
- `scripts/run_oracle_outbox_precreation_dryrun.sh` 통과
- Oracle read-only readiness report 검토 완료
- 운영봇 서비스 재시작 필요 없음 확인

## Rollback 기준

디렉터리를 실제 생성하기 전에는 승인 절차를 중단하는 것이 rollback입니다. 미래에 수동으로 디렉터리를 만든 뒤 문제가 생기면 기본 rollback은 Mac pull을 중단하고 원격 outbox 파일을 보존한 상태에서 별도 검토하는 것입니다.

원격 파일 삭제나 이동은 Phase 24L 범위에서 금지합니다.

## 금지 사항

- Oracle 서버 자동 접속 및 쓰기
- `mkdir`, `touch`, `cp`, `mv`, `rm`, `chmod`, `chown` 자동 실행
- `systemctl start/stop/restart/reload`
- Oracle live bot 실행/중지/재시작
- `penny_stock_bot.py` 운영본 수정
- 브로커 API 연결
- 주문 생성, 전송, 승인, 취소, 실행

## 다음 Phase 24M 제안

Phase 24M에서는 별도 수동 승인 후에도 여전히 preview-only 범위에서 Oracle outbox 디렉터리 생성 절차를 실행할지, 또는 먼저 추가 read-only 검증과 승인 기록을 강화할지 결정할 수 있습니다.

## Phase 24M Final Approval Gate

Phase 24M 결과 문서:

- `docs/US_TRADER_ORACLE_FINAL_APPROVAL_GATE.md`
- `examples/oracle_final_approval/`
- `scripts/run_oracle_final_approval_dryrun.sh`

Phase 24M은 Phase 24L의 precreation plan과 manual command package를 읽어 final approval packet을 생성합니다. `approval_record.example.json`은 기본값이 `approved=false`이며, 활성 위험 명령이 있으면 packet verify가 실패합니다. 실제 Oracle 적용은 여전히 수행하지 않습니다.

## Phase 24N Read-only Precheck

Phase 24N은 실제 outbox directory 생성 전 read-only precheck command plan과 결과 기록/검증 도구를 추가합니다.

- `docs/US_TRADER_ORACLE_READONLY_PRECHECK_EXECUTION.md`
- `scripts/run_oracle_readonly_precheck_dryrun.sh`

Precheck 결과가 `passed`가 아니면 write 단계로 진행하지 않습니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
