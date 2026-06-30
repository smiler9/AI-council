# US Trader Oracle Deployment Runbook

이 runbook은 Oracle US Trader signal export hook을 나중에 수동 적용하기 위한 절차서입니다. Phase 24F에서는 실제 Oracle 서버 파일을 수정하지 않고, bundle 생성과 read-only readiness dry-run까지만 수행합니다.

## Level 0: Local Bundle 생성

```bash
cd ~/AI-council
scripts/build_oracle_signal_export_bundle.sh
```

생성 위치는 기본적으로 `tmp/oracle_signal_export_bundle/`이며 Git에 포함하지 않습니다.

## Level 1: Local Bundle Verify

```bash
scripts/verify_oracle_signal_export_bundle.sh
```

검증 항목:

- manifest 존재
- 필수 파일 존재
- sha256 일치
- secret/API key/token/private key marker 없음
- 실제 Oracle IP/SSH key path 하드코딩 없음
- 위험한 order/system command 없음
- `order_execution_allowed=false`

## Level 2: Oracle Read-only Readiness Check

먼저 dry-run으로 command preview만 확인합니다.

```bash
scripts/run_oracle_readiness_check_dryrun.sh
```

실제 SSH read-only 확인은 별도 승인 후에만 수행합니다.

```bash
python examples/oracle_deployment/oracle_readiness_check.py \
  --host <oracle-host> \
  --user <oracle-user> \
  --key <path-to-private-key> \
  --trading-dir <oracle-trading-dir> \
  --enable-ssh-readonly-check \
  --pretty
```

허용되는 확인은 `hostname`, `whoami`, `pwd`, `uname -a`, `date`, `ls`, `test`, `systemctl status --no-pager`, `ps`, `screen -ls`, `tmux ls`, `crontab -l` 같은 read-only 명령뿐입니다.

## Level 3: Oracle Staging Directory 수동 복사

별도 승인 전에는 수행하지 않습니다. 수행하더라도 운영봇 파일을 직접 덮어쓰지 않고 staging directory에만 복사합니다.

## Level 4: Preview-only Sidecar 실행

sidecar는 `US_TRADER_BRIDGE_MODE=preview`로만 시작합니다. Preview mode는 `normalize-preview`만 호출하며 trade review를 생성하지 않습니다.

## Level 5: Export Hook Patch 적용 전 최종 승인

다음을 승인자가 확인해야 합니다.

- patch preview diff
- safe insertion 위치
- unsafe function 내부 hook 없음
- rollback 파일/절차
- outbox 권한
- logs/state 위치

## Level 6: Export Hook 적용 후 Outbox만 확인

hook이 생성하는 것은 outbox JSON 파일뿐이어야 합니다. HTTP 전송은 sidecar가 담당합니다.

## Level 7: Normalize-preview 확인

AI Council `POST /api/webhooks/normalize-preview`로 payload shape과 adapter warning만 확인합니다.

## Level 8: Read-only Trade Review 확인

별도 승인 후 sidecar `review` mode를 검토할 수 있습니다. 이 단계도 AI Council trade review 생성만 수행하며 실제 주문은 없습니다.

## Level 9: Paper Simulation 확인

AI Council paper portfolio에 review 결과를 반영할 수 있습니다.

- 내부 가상 시뮬레이션 전용
- 실제 체결 아님
- 실제 포지션 변경 없음
- `simulation_only=true`

## 범위 밖

- 실거래 주문 연결
- 브로커 API 연결
- Oracle live service 자동 재시작
- AI Council 판단을 US Trader 주문 경로에 직접 연결

## 금지 명령

- `systemctl start`
- `systemctl stop`
- `systemctl restart`
- `submit_order`
- `place_order` 내부 hook 삽입
- `check_exits` 내부 hook 삽입
- `force_close_all` 내부 hook 삽입
- `scp` 또는 `rsync`를 통한 무승인 복사

## Rollback 절차

1. sidecar preview process만 분리 중단
2. outbox/state/log 보존
3. patch 적용 전 백업 파일과 diff 확인
4. export hook patch 제거
5. 운영 service 조작은 별도 승인 후 진행
6. AI Council은 계속 read-only 상태 유지

## Placeholder

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
ORACLE_SSH_KEY=<path-to-private-key>
```

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
