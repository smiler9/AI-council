# US Trader Oracle Mac Pull Plan

## Phase 24J 목적

Phase 24J는 Oracle 서버가 로컬 Mac AI Council로 직접 webhook을 호출하지 않는 연결 방식을 준비합니다.

핵심 흐름:

1. Oracle 운영봇은 승인된 outbox directory에 signal JSON만 쌓습니다.
2. Mac은 SSH read-only listing 또는 optional read-only copy로 JSON 파일을 가져옵니다.
3. AI Council은 로컬 inbox의 JSON을 `normalize-preview`로 먼저 검증합니다.
4. read-only trade review와 paper simulation은 별도 승인 후 명시적으로만 수행합니다.

## 왜 Mac Pull 방식이 안전한가

- AI Council backend를 public endpoint로 노출하지 않습니다.
- Oracle에서 Mac으로 outbound webhook을 만들 필요가 없습니다.
- Oracle live bot과 AI Council 사이에 직접 네트워크 결합을 만들지 않습니다.
- 원격 파일 삭제/이동 없이 local copy만 검증할 수 있습니다.
- tunnel token, public URL, reverse tunnel 운영 부담을 줄입니다.

## Oracle Outbox-only와의 관계

Phase 24I 1순위는 `oracle_outbox_only_preview`이고, Phase 24J는 2순위 `mac_pull_oracle_outbox`를 preview pipeline으로 구체화합니다.

Oracle outbox-only는 네트워크 연결 자체를 만들지 않는 가장 보수적인 전략입니다. Mac pull은 그 다음 단계로, Oracle outbox에 쌓인 JSON을 Mac이 읽어와 AI Council preview에 넣는 방식입니다.

## 원격 파일 삭제/이동 금지

Mac pull preview에서는 다음을 하지 않습니다.

- 원격 outbox 파일 삭제
- 원격 outbox 파일 이동
- 원격 권한 변경
- 원격 directory 생성
- Oracle systemd 조작
- Oracle live bot 실행/중지/재시작

`remote_delete=false`, `remote_move=false`를 pull plan에서 강제합니다.

## Read-only Listing

기본 도구:

```bash
python examples/oracle_pull/oracle_outbox_pull_preview.py --dry-run --pretty
```

명시적으로 승인된 경우에만 read-only listing을 시도합니다.

```bash
python examples/oracle_pull/oracle_outbox_pull_preview.py \
  --host <oracle-host> \
  --user <oracle-user> \
  --key <path-to-private-key> \
  --outbox-dir <oracle-outbox-dir> \
  --enable-ssh-readonly-list \
  --pretty
```

허용되는 원격 확인은 `ls`, `find`, `stat`, checksum 수준입니다. secret/config 파일 내용은 읽지 않습니다.

## Optional Read-only Copy

copy는 명시 옵션이 있을 때만 수행합니다.

```bash
python examples/oracle_pull/oracle_outbox_pull_preview.py \
  --host <oracle-host> \
  --user <oracle-user> \
  --key <path-to-private-key> \
  --outbox-dir <oracle-outbox-dir> \
  --local-inbox tmp/oracle_pull/inbox \
  --enable-readonly-copy \
  --pretty
```

copy를 수행해도 원격 파일은 삭제하거나 이동하지 않습니다. local inbox와 state는 Git에 포함하지 않습니다.

## Local Inbox 처리

sample 파일 처리:

```bash
python examples/oracle_pull/process_pulled_signals.py \
  --inbox examples/oracle_pull/sample_pulled_signals \
  --mode preview \
  --pretty
```

실제 local inbox 처리:

```bash
python examples/oracle_pull/process_pulled_signals.py \
  --inbox tmp/oracle_pull/inbox \
  --state tmp/oracle_pull/state.json \
  --mode preview \
  --pretty
```

## Normalize-preview

기본 처리 모드는 preview입니다.

- `POST /api/webhooks/normalize-preview`
- trade review 생성 없음
- DB 저장 최소화
- `order_execution_allowed=false`
- adapter warning 확인

## Read-only Trade Review

review mode는 명시적으로 `--mode review`를 줄 때만 가능합니다.

review mode도 실제 주문이 아니라 AI Council trade review 생성만 수행합니다. Webhook이 disabled이면 안전하게 실패하거나 skip해야 합니다.

## Paper Simulation

paper simulation은 Phase 24J의 기본 실행 범위가 아닙니다. 다음 단계에서 pulled signal이 만든 review 결과를 내부 paper portfolio에만 반영할 수 있습니다.

이 경우에도 `simulation_only=true`, `order_execution_allowed=false`가 유지되어야 합니다.

## 중복 처리 전략

`process_pulled_signals.py`는 `source + signal_id`를 signal identity로 사용합니다.

- 이미 처리된 signal identity는 재처리하지 않습니다.
- state file은 local ignored path에 저장합니다.
- 원격 파일을 processed directory로 이동하지 않습니다.

## Launchd / Cron 가능성

Mac에서 주기적으로 pull/process를 실행할 수 있습니다. 예시는 다음 파일에 있습니다.

- `examples/oracle_pull/templates/launchd_pull_schedule.example.plist`
- `examples/oracle_pull/templates/local_process_pulled_signals.example.sh`

기본 예시는 disabled/placeholder 중심이며 실제 Oracle 정보는 포함하지 않습니다.

## 보안 주의사항

- 실제 Oracle host, SSH key path, 계정명은 문서와 Git에 하드코딩하지 않습니다.
- private key 내용은 읽거나 출력하지 않습니다.
- `.env`, secret, API key, token 값은 출력하지 않습니다.
- tunnel token과 public endpoint는 사용하지 않습니다.
- pulled JSON에 order-like field가 있어도 adapter warning으로만 처리합니다.

## Tunnel보다 안전한 점

Mac pull 방식은 AI Council을 외부에 노출하지 않고, Oracle이 Mac으로 직접 호출하지 않습니다. 네트워크 변경 범위가 작고, 실패해도 Oracle live bot과 systemd service에 영향을 주지 않습니다.

## 한계

- 실시간성이 낮습니다.
- Oracle outbox directory는 별도 수동 승인 후 준비되어야 합니다.
- Mac이 sleep 상태면 pull이 멈춥니다.
- 중복/보관/보존 정책은 local state 기준으로 운영해야 합니다.

## 다음 Phase 24K 제안

1. Oracle outbox directory 수동 생성 승인 절차 확정
2. preview-only local inbox 처리 자동화
3. pulled signal에서 read-only trade review 생성 조건 정의
4. paper simulation 연결을 별도 approval gate로 준비

Phase 24K 결과 문서:

- `docs/US_TRADER_ORACLE_OUTBOX_PATH_APPROVAL.md`

Phase 24K는 outbox/processed/failed/state/log 경로 후보와 file contract, retention policy, rollback plan, manual checklist를 approval package로 묶습니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
