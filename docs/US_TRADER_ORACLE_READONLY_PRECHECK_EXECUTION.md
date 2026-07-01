# US Trader Oracle Read-only Precheck Execution

## Phase 24N 목적

Phase 24N은 Oracle 서버에 outbox 디렉터리를 만들기 전에 사람이 실제 Oracle 서버에서 실행해도 되는 read-only precheck 명령만 최종 정리하고, 그 결과를 안전하게 JSON으로 기록/검증하는 도구를 제공합니다.

이번 단계는 계획, 결과 기록 템플릿, 결과 검증, 문서, 테스트까지만 수행합니다. Oracle 서버에 파일을 쓰지 않고, 업로드하지 않고, systemd 서비스를 조작하지 않으며, 운영봇을 수정하지 않습니다.

## 왜 Read-only Precheck가 필요한가

Outbox 디렉터리 생성은 작은 작업처럼 보이지만 운영 서버에서 발생하는 첫 write 작업입니다. 그 전에 경로, Python 환경, 디스크, 서비스 상태, 운영봇 파일 존재 여부를 read-only로 확인해야 합니다.

## 실행 가능한 명령

다음은 사람이 Oracle에서 수동 실행할 수 있는 read-only 명령 예시입니다. placeholder는 수동으로 교체합니다.

```text
hostname
whoami
pwd
uname -a
date
df -h
free -h
python3 --version
which python3
ls -la <oracle-trading-dir>
test -f <oracle-trading-dir>/penny_stock_bot.py
test -f <oracle-trading-dir>/server.py
test -d <oracle-trading-dir>/.secrets
ps aux | grep -i trader
ps aux | grep -i penny
ps aux | grep -i python
screen -ls
tmux ls
crontab -l
systemctl status --no-pager <service-name>
```

Secret/config 파일 내용은 출력하지 않습니다. `.secrets`, `.env`, token, API key, private key 파일은 존재 여부만 확인합니다.

## 금지 명령

- `mkdir`, `touch`, `cp`, `mv`, `rm`
- `chmod`, `chown`
- `systemctl`의 start, stop, restart, reload 동작
- `docker`의 start, stop, restart 동작
- `python penny_stock_bot.py`
- `place_order`, `submit_order`, broker/order 관련 실행
- secret 파일 `cat`
- `.env` 파일 `cat`

## Plan 생성과 검증

```bash
scripts/build_oracle_readonly_precheck_plan.sh
scripts/verify_oracle_readonly_precheck_plan.sh
```

Plan 출력:

```text
tmp/oracle_readonly_precheck/precheck_plan.json
```

검증은 다음을 확인합니다.

- `remote_write_allowed=false`
- `remote_write_executed=false`
- `systemd_changes_allowed=false`
- `order_execution_allowed=false`
- forbidden command가 활성 명령에 없음
- secret/API key/token/private key/실제 Oracle 접속 정보 없음

## 결과 기록 방법

사람이 read-only 명령 결과를 확인한 뒤 JSON으로 기록합니다.

```bash
scripts/record_oracle_readonly_precheck_sample_result.sh
```

직접 입력 파일을 정리할 때는 다음 도구를 사용합니다.

```bash
python examples/oracle_readonly_precheck/record_readonly_precheck_result.py \
  --input <manual-result-input.json> \
  --output tmp/oracle_readonly_precheck/precheck_result.json \
  --pretty
```

Secret/private key/token marker가 있으면 기록을 거부합니다. 실제 host/IP나 로컬 key path는 placeholder 또는 redacted 값으로 남겨야 합니다.

## 결과 검증 방법

```bash
scripts/verify_oracle_readonly_precheck_result.sh
```

검증은 다음을 확인합니다.

- `remote_write_executed=false`
- `systemd_changed=false`
- `order_execution_allowed=false`
- 필수 observations 존재
- 필수 observations가 true
- secret/API key/token/private key/실제 Oracle 접속 정보 없음
- `result_status=passed`

## 통과 기준

- `result_status=passed`
- `next_step_allowed=true`
- 모든 필수 observations true
- remote write/systemd/order 상태 false
- final approval dry-run 통과

## 실패/보류 기준

- `result_status`가 warning, failed, incomplete
- 디스크 또는 Python 환경 불명확
- 운영봇 파일 존재 확인 실패
- systemd 상태 확인 중 변경이 필요해 보임
- secret 또는 실제 접속 정보가 결과에 포함됨
- 운영봇 수정이나 서비스 재시작이 필요함

## 다음 Phase 24O 조건

Phase 24O로 넘어가려면 다음이 필요합니다.

- final approval packet verify 통과
- read-only precheck plan verify 통과
- read-only result verify 통과
- 사람이 별도 승인 기록을 남김
- 그래도 Oracle write 작업은 자동화하지 않음

## Phase 24O Intake Go/No-Go

Phase 24O 결과 문서:

- `docs/US_TRADER_ORACLE_PRECHECK_INTAKE_GO_NO_GO.md`
- `examples/oracle_precheck_intake/`
- `scripts/run_oracle_precheck_intake_dryrun.sh`

Phase 24O는 사람이 기록한 read-only precheck 결과를 intake JSON으로 검증하고 GO/NO-GO를 판단합니다. GO는 실제 적용 승인이 아니라 다음 수동 검토 단계 허용입니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
