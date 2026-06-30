# Oracle Deployment Bundle

Phase 24F는 Oracle US Trader 운영봇에 signal export hook을 적용하기 전, 사람이 검토할 수 있는 로컬 deployment bundle과 수동 승인 게이트를 제공합니다.

이 폴더의 도구는 Oracle 서버에 파일을 쓰지 않고, systemd service를 조작하지 않고, 실제 주문을 실행하지 않습니다.

## Bundle 생성

```bash
cd ~/AI-council
scripts/build_oracle_signal_export_bundle.sh
```

기본 생성 위치:

```text
tmp/oracle_signal_export_bundle/
```

이 경로는 Git에 포함하지 않습니다.

## Bundle 검증

```bash
scripts/verify_oracle_signal_export_bundle.sh
```

검증 항목:

- manifest와 sha256
- 필수 파일 존재
- secret/API key/token/private key marker 없음
- 실제 Oracle IP/SSH key path 하드코딩 없음
- 위험한 broker/order/system command 없음
- `order_execution_allowed=false`

## Read-only readiness dry-run

```bash
scripts/run_oracle_readiness_check_dryrun.sh
```

기본은 SSH를 실행하지 않고 read-only command preview만 출력합니다.

## Manual approval

실제 Oracle 적용은 다음 문서를 사람이 확인하고 승인한 뒤 별도 단계에서만 검토합니다.

- `docs/US_TRADER_ORACLE_MANUAL_APPROVAL_GATE.md`
- `docs/US_TRADER_ORACLE_DEPLOYMENT_RUNBOOK.md`

## Safety Boundary

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
