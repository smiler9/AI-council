# US Trader Oracle Manual Approval Gate

Phase 24F는 Oracle US Trader 운영봇에 signal export hook을 실제 적용하기 전에 사람이 수동으로 검토하고 승인하기 위한 게이트입니다. 이 단계는 배포 번들, readiness dry-run, 검증 체크리스트, rollback 계획만 제공합니다.

## 왜 수동 승인 게이트가 필요한가

- Oracle 운영봇은 live service로 동작할 수 있으므로 자동 patch를 금지합니다.
- AI Council 연동은 read-only review와 paper simulation까지만 허용됩니다.
- `place_order`, `check_exits`, `force_close_all` 같은 주문 경로와 export hook을 연결하면 안 됩니다.
- 모든 변경은 preview-only 검증을 먼저 통과해야 합니다.

## 적용 전 필수 확인

아래 명령은 로컬에서만 실행합니다.

```bash
scripts/run_oracle_sidecar_smoke.sh
scripts/run_oracle_export_hook_preflight.sh
scripts/run_oracle_staging_rehearsal.sh
scripts/build_oracle_signal_export_bundle.sh
scripts/verify_oracle_signal_export_bundle.sh
scripts/run_oracle_readiness_check_dryrun.sh
```

필수 확인 항목:

- sidecar smoke 통과
- export hook preflight 통과
- staging rehearsal 통과
- deployment bundle verify 통과
- Oracle readiness check는 dry-run command preview로 먼저 검토
- bundle 내부 secret/API key/token/private key 없음
- 실제 Oracle IP, SSH key path, 계정 정보 하드코딩 없음
- `order_execution_allowed=false`

## 승인자 체크박스

- [ ] bundle manifest와 sha256 검증 결과 확인
- [ ] preview deploy plan 검증 결과 확인
- [ ] preview command 파일이 자동 업로드/systemd 조작을 하지 않는지 확인
- [ ] patch preview diff 수동 검토
- [ ] safe insertion 위치가 `analyze_signals` 이후 또는 `scan_and_enter`의 candidate 생성 직후인지 확인
- [ ] export hook이 `place_order/check_exits/force_close_all` 내부에 없는지 확인
- [ ] outbox directory 권한 계획 확인
- [ ] sidecar는 preview-only로 시작하는지 확인
- [ ] rollback 절차 확인
- [ ] logs/state 보존 위치 확인
- [ ] 실제 주문 경로와 연결하지 않는다는 점 확인

## 적용 금지 위치

- `place_order` 내부
- `check_exits` 내부
- `force_close_all` 내부
- 실제 주문 호출 직후
- 브로커 API client 생성/호출 위치

## Preview-only 배포 조건

처음에는 sidecar mode를 `preview`로 유지합니다.

```text
US_TRADER_BRIDGE_MODE=preview
```

`preview`는 AI Council `normalize-preview`만 호출하며 trade review를 생성하지 않습니다.

Phase 24G preview deploy dry-run:

```bash
scripts/run_oracle_preview_deploy_dryrun.sh
```

이 dry-run은 Oracle 서버에 접속하거나 파일을 쓰지 않습니다.

## Review mode 전환 조건

별도 승인 후에만 `review` mode를 검토합니다.

- preview 결과의 adapter warning 검토 완료
- order-like fields가 review context로만 저장되는지 확인
- Telegram/report는 보고 전용임을 확인
- 실제 주문 경로와 연결 없음 확인

## Paper simulation 전환 조건

AI Council에서 생성된 review 결과를 paper portfolio에 반영할 때도 내부 가상 시뮬레이션만 허용합니다.

- `simulation_only=true`
- `order_execution_allowed=false`
- 실제 broker 계좌/주문 API 연결 없음

## Systemd 관련 주의

AI Council은 Oracle systemd service를 조작하지 않습니다. service 상태 확인은 read-only `status`만 허용됩니다. 어떤 service operation도 별도 승인 없이 수행하지 않습니다.

## 실패 시 중단 기준

- bundle verify 실패
- readiness dry-run에 위험 명령 포함
- secret/API key/token/private key 노출 의심
- patch preview가 unsafe function 내부에 삽입됨
- `order_execution_allowed=true` 가능성 발견
- preview mode가 아닌 review/order-like 흐름으로 자동 전환됨

## Rollback 준비

- 원본 운영 파일 백업 계획을 수동으로 확인
- outbox/state/log directory 분리
- sidecar process만 분리해서 중지 가능하도록 설계
- 운영봇 patch 적용 전 diff를 보존
- 실패 시 patch 제거와 원본 복원 절차를 별도 승인으로 수행

## Placeholder

실제 Oracle 정보는 문서에 넣지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
ORACLE_SSH_KEY=<path-to-private-key>
```

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
