# US Trader Oracle Preview-only Sidecar Deploy Plan

Phase 24G는 Oracle 운영봇을 직접 수정하지 않고 AI Council sidecar bridge를 preview-only 모드로 배치하기 위한 준비 단계입니다. 이 단계는 로컬에서 plan과 command preview만 생성하며, Oracle 서버에 파일을 업로드하거나 systemd service를 조작하지 않습니다.

## 목적

- Oracle live bot은 그대로 둔다.
- `penny_stock_bot.py`를 수정하지 않는다.
- sidecar bridge를 preview-only로 배치하기 위한 수동 절차를 준비한다.
- AI Council `normalize-preview`로 payload shape과 adapter warning만 확인한다.
- 실제 주문 실행, 브로커 API 연결, 운영봇 service restart는 하지 않는다.

## Preview mode와 review mode

- `preview`: AI Council `POST /api/webhooks/normalize-preview`만 호출한다. Trade review를 생성하지 않는다.
- `review`: AI Council `POST /api/webhooks/trade-signal`로 read-only review를 생성한다. 별도 수동 승인 전까지 사용하지 않는다.

Phase 24G 기본값은 항상 `preview`입니다.

## 배치 전 조건

```bash
scripts/build_oracle_signal_export_bundle.sh
scripts/verify_oracle_signal_export_bundle.sh
scripts/run_oracle_readiness_check_dryrun.sh
```

모든 결과는 `order_execution_allowed=false`여야 합니다.

## Phase 24H read-only readiness 결과 반영

Phase 24H에서는 Oracle 서버를 read-only로 점검해 preview-only sidecar 배치 가능성을 확인했습니다.

관련 문서:

- `docs/US_TRADER_ORACLE_READONLY_READINESS_REPORT.md`

확인된 일반화된 전제:

- `<oracle-trading-dir>`가 존재해야 함
- Python 3 계열과 sidecar bridge 실행 가능 환경이 필요함
- sidecar 후보 directory는 별도 manual approval 전까지 생성하지 않음
- AI Council endpoint는 Oracle에서 접근 가능한 URL이어야 하며, `127.0.0.1`은 Oracle 자신을 가리키므로 로컬 Mac backend에는 도달하지 않음
- systemd 운영봇 service는 preview-only sidecar 배치 과정에서 start/stop/restart하지 않음

## Phase 24I network connectivity strategy

Phase 24I는 Oracle에서 AI Council에 접근하는 방식을 비교하고, 실제 네트워크 변경 없이 connectivity plan을 생성/검증합니다.

관련 문서:

- `docs/US_TRADER_ORACLE_NETWORK_CONNECTIVITY_STRATEGY.md`

권장 순서:

1. `oracle_outbox_only_preview`
2. `mac_pull_oracle_outbox`
3. `ssh_reverse_tunnel_preview`

실제 tunnel 또는 public endpoint는 Phase 24I에서 실행하지 않습니다.

## Preview deploy plan 생성

```bash
scripts/prepare_oracle_preview_deploy_plan.sh
```

직접 실행:

```bash
python3 examples/oracle_preview_deploy/prepare_preview_deploy_plan.py \
  --bundle tmp/oracle_signal_export_bundle \
  --output tmp/oracle_preview_deploy_plan.json \
  --oracle-user <oracle-user> \
  --oracle-host <oracle-host> \
  --oracle-trading-dir <oracle-trading-dir> \
  --oracle-sidecar-dir <oracle-sidecar-dir> \
  --ai-council-base-url <ai-council-base-url> \
  --mode preview \
  --pretty
```

## Preview plan 검증

```bash
scripts/verify_oracle_preview_deploy_plan.sh
```

검증 항목:

- `mode=preview`
- `manual_approval_required=true`
- `order_execution_allowed=false`
- 실제 secret/API key/token/private key 없음
- 실제 Oracle IP/SSH key path 없음
- `systemctl start/stop/restart` 활성 명령 없음
- live/order/review mode 기본값 없음

## Preview command 생성

```bash
scripts/generate_oracle_preview_commands.sh
```

생성 위치:

```text
tmp/oracle_preview_commands/
```

생성 파일:

- `00_readiness_check.sh`
- `01_create_sidecar_dirs.preview.sh`
- `02_upload_bundle.preview.sh`
- `03_verify_remote_files.preview.sh`
- `04_run_sidecar_once_preview.preview.sh`
- `05_check_logs.preview.sh`
- `99_rollback_preview.preview.sh`

이 파일들은 command preview입니다. 실제 Oracle 실행 전 사람이 검토해야 합니다.

## 전체 dry-run

```bash
scripts/run_oracle_preview_deploy_dryrun.sh
```

흐름:

1. bundle build
2. bundle verify
3. readiness dry-run
4. preview plan 생성
5. preview plan verify
6. preview command 생성

## Oracle에 복사할 파일 목록

수동 승인 후에도 preview sidecar directory에만 복사합니다.

- `ai_council_signal_exporter_module.py`
- `us_trader_signal_outbox_bridge.py`
- `mapping_profiles/us_trader_oracle_v1.json`
- `sample_outbox/*.json`
- `preview_sidecar.env`

운영봇 파일은 수정하지 않습니다.

## Sidecar run-once preview 절차

1. outbox directory 확인
2. sidecar env placeholder를 실제 운영 환경 값으로 수동 작성
3. `US_TRADER_BRIDGE_MODE=preview` 확인
4. `us_trader_signal_outbox_bridge.py --mode preview` run-once 실행
5. AI Council normalize-preview 응답과 adapter warnings 확인
6. `order_execution_allowed=false` 확인

## Log 확인 절차

- sidecar state/log만 확인
- 운영봇 logs는 read-only로만 확인
- secret, token, account 값은 출력하지 않음
- systemd 운영봇 restart 없음

## Rollback 절차

- sidecar preview process만 중지
- outbox/state/log 보존
- sidecar preview files만 수동 제거
- `penny_stock_bot.py` 수정 없음
- production service 조작 없음

## Review mode 전환 조건

- preview 결과 검토 완료
- order-like fields warning 확인
- manual approval record 완료
- AI Council read-only trade review만 생성한다는 점 확인
- 실제 주문 경로 연결 없음

## Paper simulation 연결 조건

- review 결과가 생성된 뒤 AI Council 내부 paper portfolio에만 반영
- `simulation_only=true`
- 실제 체결/주문/포지션 변경 없음

## Phase 24J Mac Pull 연결

네트워크 연결 전략의 2순위인 `mac_pull_oracle_outbox`는 별도 문서에서 다룹니다.

- `docs/US_TRADER_ORACLE_MAC_PULL_PLAN.md`
- Oracle outbox JSON을 Mac local inbox로 read-only copy
- 원격 파일 삭제/이동 금지
- 기본은 `normalize-preview`
- review/paper simulation은 별도 승인 후 명시적으로만 수행

## Phase 24K Outbox 경로 승인

- `docs/US_TRADER_ORACLE_OUTBOX_PATH_APPROVAL.md`
- `examples/oracle_outbox_approval/templates/outbox_file_contract.md`
- `examples/oracle_outbox_approval/templates/outbox_retention_policy.md`
- `examples/oracle_outbox_approval/templates/outbox_rollback_plan.md`
- 실제 Oracle directory 생성은 아직 하지 않음
- active `mkdir`, `chmod`, `systemctl` 명령 없음

## 절대 하지 말아야 할 것

- `penny_stock_bot.py` 직접 수정
- `sniper-bot`, `usstock-bot`, `usstock-web` restart
- `place_order` 연결
- `check_exits` 연결
- `force_close_all` 연결
- 실제 주문 실행
- 브로커 API 연결

## Placeholder

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_TRADING_DIR=<oracle-trading-dir>
ORACLE_SIDECAR_DIR=<oracle-sidecar-dir>
ORACLE_SSH_KEY=<path-to-private-key>
```

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
