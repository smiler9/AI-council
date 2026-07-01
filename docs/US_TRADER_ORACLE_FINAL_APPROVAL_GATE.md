# US Trader Oracle Final Approval Gate

## Phase 24M 목적

Phase 24M은 Oracle 서버에 outbox, processed, failed, state 디렉터리를 실제로 만들기 직전 사람이 수동으로 검토할 최종 승인 게이트를 준비합니다.

이번 단계는 최종 승인 패킷, read-only 사전 확인 명령, manual command review, 승인/거절 기록 템플릿, 안전 검증까지만 수행합니다. Oracle 서버에 파일을 쓰지 않고, 업로드하지 않고, systemd 서비스를 조작하지 않으며, 운영봇을 수정하지 않습니다.

## 왜 최종 승인 게이트가 필요한가

Phase 24K와 Phase 24L은 경로 승인과 precreation 리허설을 준비했습니다. Phase 24M은 실제 수동 적용 직전 다음을 한 번 더 분리합니다.

- read-only 사전 확인 명령
- 주석 처리된 manual write 후보 명령
- 승인 기록 템플릿
- 거절/보류 기록 템플릿
- 최종 패킷 hash/secret/위험 명령 검증

## Read-only Precheck와 Manual Write 명령의 차이

Read-only precheck는 `test`, `ls`, `stat`, `df`, `free`, `python3 --version`, `systemctl status --no-pager` 같은 확인 명령입니다.

Manual write 후보는 미래에 별도 승인 후 사람이 직접 검토할 수 있는 `mkdir` 또는 제한적인 permission review 예시입니다. Phase 24M에서 이 명령들은 모두 주석 처리되어 있으며 자동 실행되지 않습니다.

## 승인 전 확인할 것

- AI Council backend/frontend 정상
- diagnostics summary 정상
- `scripts/run_oracle_outbox_approval_dryrun.sh` 통과
- `scripts/run_oracle_outbox_precreation_dryrun.sh` 통과
- `scripts/run_oracle_final_approval_dryrun.sh` 통과
- manual command review 통과
- approval record가 `approved=false` 기본값인지 확인
- 운영봇 백업 확인
- systemd 조작 없음 확인
- 실제 주문 연결 없음 확인

## 승인 기록 방식

승인 기록은 Git에 실제 승인값을 커밋하지 않습니다.

기본 템플릿:

```text
examples/oracle_final_approval/templates/approval_record.example.json
```

기본값:

```json
{
  "approved": false,
  "approved_by": "<manual-approver>",
  "approved_at": null,
  "scope": "oracle_outbox_precreation_only",
  "order_execution_allowed": false
}
```

`approved` true 상태는 기본 패킷이나 Git 추적 파일에 들어가면 안 됩니다.

## 거절/보류 조건

- backend/frontend 또는 diagnostics 실패
- outbox approval/precreation/final approval dry-run 실패
- secret, private key, token, 실제 Oracle 접속 정보 노출 의심
- 활성 `mkdir`, `chmod`, `chown`, `rm`, `mv`, `systemctl` 명령 발견
- approval record가 기본값부터 `approved` true 상태
- Oracle live bot 수정 필요
- systemd start/stop/restart/reload 필요
- 주문 또는 브로커 API 연결 가능성 발견

## 실행 가능 명령과 금지 명령

허용 예시:

- `echo`
- `printf`
- `test`
- `ls`
- `stat`
- `df`
- `free`
- `python3 --version`
- `systemctl status --no-pager`, 단 read-only 확인으로만

금지:

- `mkdir`, `touch`, `cp`, `mv`, `rm`, `chmod`, `chown` 자동 실행
- `systemctl`의 start, stop, restart, reload 동작
- `docker start/stop/restart`
- `python penny_stock_bot.py`
- `place_order`
- `submit_order`
- broker/order 관련 실행
- secret 파일 `cat`

## 실행법

```bash
scripts/run_oracle_final_approval_dryrun.sh
```

개별 실행:

```bash
scripts/build_oracle_final_approval_packet.sh
scripts/review_oracle_manual_commands.sh
scripts/verify_oracle_final_approval_packet.sh
```

생성 결과는 `tmp/oracle_final_approval/`에만 저장하며 Git에 포함하지 않습니다.

## 다음 Phase 24N 제안

Phase 24N에서는 사람이 승인한 경우에도 바로 운영봇을 수정하지 않고, Oracle read-only precheck 결과와 승인 기록을 바탕으로 실제 outbox directory 생성 절차를 수동으로 수행할지 결정할 수 있습니다.

## Phase 24N Read-only Precheck

Phase 24N 결과 문서:

- `docs/US_TRADER_ORACLE_READONLY_PRECHECK_EXECUTION.md`
- `examples/oracle_readonly_precheck/`
- `scripts/run_oracle_readonly_precheck_dryrun.sh`

Phase 24N은 실제 write 작업 전 read-only 명령 목록과 결과 기록/검증 도구를 제공합니다. `result_status`가 `passed`가 아니면 다음 단계로 진행하지 않습니다.

## Phase 24O Precheck Intake Go/No-Go

Phase 24O 결과 문서:

- `docs/US_TRADER_ORACLE_PRECHECK_INTAKE_GO_NO_GO.md`
- `scripts/run_oracle_precheck_intake_dryrun.sh`

Phase 24O의 GO decision은 outbox 수동 생성 검토로 넘어갈 수 있다는 뜻일 뿐이며 실제 적용 승인, 운영봇 수정, systemd 조작, 주문 실행 허가가 아닙니다.

## Phase 24P Manual Creation Packet

Phase 24P 결과 문서:

- `docs/US_TRADER_ORACLE_OUTBOX_MANUAL_CREATION_PACKET.md`
- `scripts/run_oracle_outbox_manual_creation_dryrun.sh`

Phase 24P는 주석 처리된 manual creation 후보 명령과 post-creation read-only 검증 템플릿을 생성합니다. 실제 Oracle 적용은 아직 하지 않습니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
