# US Trader Oracle Read-only Readiness Report

Phase 24H는 Oracle 서버에 preview-only sidecar를 배치할 수 있는지 확인하기 위한 read-only 점검입니다. 이 단계에서는 Oracle 서버에 파일을 쓰지 않고, 파일을 업로드하지 않고, systemd service를 조작하지 않고, 운영봇을 실행/중지/재시작하지 않았습니다.

## Placeholder

실제 Oracle 접속 정보는 문서에 기록하지 않습니다.

```text
ORACLE_HOST=<oracle-host>
ORACLE_USER=<oracle-user>
ORACLE_SSH_KEY=<path-to-private-key>
ORACLE_TRADING_DIR=<oracle-trading-dir>
```

## 접속 결과

- Read-only SSH 접속: 성공
- Key 후보: 04-16 key 존재 확인, private key 내용 미출력
- 서버 hostname: Oracle instance hostname 확인
- 점검 사용자: non-root 운영 사용자로 확인
- 점검 일시: 2026-07-01 KST
- 서버 파일 쓰기: 없음
- systemd start/stop/restart/reload: 없음
- 운영봇 파일 수정: 없음

## 서버 환경 요약

- OS/kernel: Ubuntu Oracle aarch64 계열로 확인
- Disk: root filesystem 약 48GB 중 약 39GB 사용 가능
- Memory: 약 23GiB 중 대부분 사용 가능
- Python: Python 3.12 계열 확인
- `python3` 경로: system Python 확인
- `requests` import 가능 여부: 가능

## Trading Directory 확인

`<oracle-trading-dir>`의 존재를 확인했습니다.

확인된 주요 파일/폴더:

- `penny_stock_bot.py`: 존재
- `server.py`: 존재
- `.secrets/`: 존재, 내용은 확인하지 않음, 값은 REDACTED
- `requirements.txt`: 존재
- `.venv/`: 존재
- `bot.log`: trading directory root에 존재
- `server.log`: trading directory root에 존재
- `logs/`, `log/`, `data/`: 별도 폴더는 현재 없음

주의:

- `.secrets`, config, token, account 파일 내용은 출력하지 않았습니다.
- `penny_stock_bot.py` 전체 내용을 출력하지 않았습니다.

## Systemd Service 상태

Read-only `systemctl status` / metadata 확인 결과:

| Service | 상태 | ExecStart 요약 | WorkingDirectory | Restart |
| --- | --- | --- | --- | --- |
| `sniper-bot.service` | active/running | `.venv/bin/python -u penny_stock_bot.py` | `<oracle-trading-dir>` | always |
| `usstock-bot.service` | active/running | `.venv/bin/python -u penny_stock_bot.py` | `<oracle-trading-dir>` | always |
| `usstock-web.service` | active/running | `.venv/bin/python server.py` | `<oracle-trading-dir>` | always |

최근 로그는 read-only로 확인했으며, secret/API key/token/private key 값은 출력하거나 문서에 기록하지 않았습니다.

## 실행 중인 프로세스 요약

- 운영봇 프로세스 2개가 `.venv/bin/python -u penny_stock_bot.py`로 실행 중
- 웹 서버 프로세스 1개가 `.venv/bin/python server.py`로 실행 중
- screen/tmux session 없음
- trading bot 관련 cron은 확인되지 않음

## Preview Sidecar 배치 후보 경로

다음 경로는 후보로 평가했습니다. 실제 생성하지 않았습니다.

- `<oracle-trading-dir>/ai_council_sidecar`
- `<oracle-trading-dir>/ai_council_outbox`
- `<oracle-trading-dir>/ai_council_processed`
- `<oracle-trading-dir>/ai_council_failed`

현재 후보 경로들은 존재하지 않는 것으로 확인되었습니다. 생성은 별도 manual approval 이후에만 검토합니다.

## 권한 평가

- `<oracle-trading-dir>`은 운영 사용자 소유의 group-writable directory로 보입니다.
- 따라서 운영 사용자 기준으로 sidecar/outbox directory를 만들 수 있을 가능성이 높습니다.
- 단, Phase 24H에서는 쓰기 테스트를 하지 않았으므로 실제 생성 가능 여부는 별도 승인된 maintenance window에서만 확인합니다.

## AI Council Endpoint 접근성 평가

Phase 24H에서는 Oracle에서 AI Council endpoint로 네트워크 호출을 수행하지 않았습니다.

현재 구조상 주의할 점:

- Oracle sidecar가 `http://127.0.0.1:8000`을 사용하면 Oracle 서버 자기 자신을 가리키므로 로컬 Mac의 AI Council에는 도달하지 못합니다.
- preview-only 배치 전에 Oracle에서 접근 가능한 AI Council base URL이 필요합니다.
- 선택지는 별도 승인 후 검토합니다:
  - AI Council backend를 Oracle 또는 접근 가능한 서버에 read-only로 배치
  - 안전한 tunnel/reverse tunnel을 통해 Oracle에서 AI Council backend로 접근
  - Cloudflare Tunnel 등 인증된 tunnel 사용

네트워크 접근성 확인은 다음 단계에서 preview-only/read-only로만 수행해야 합니다.

## Preview-only 배치 가능성

기술적으로 preview-only sidecar 배치 준비는 가능해 보입니다.

근거:

- trading directory 존재
- Python 3.12 사용 가능
- `.venv/` 존재
- `requests` 사용 가능
- disk/memory 여유 충분
- 운영봇과 웹 서버는 systemd로 안정적으로 실행 중

필요한 수동 조치:

- sidecar directory/outbox directory 수동 생성 승인
- preview bundle 수동 복사 승인
- `preview_sidecar.env` 수동 작성
- Oracle에서 접근 가능한 AI Council base URL 결정
- sidecar run-once preview 실행 승인

## 위험 요소

- 두 개의 bot service가 같은 `penny_stock_bot.py`를 실행 중이므로 운영 변경 전 영향 범위 검토 필요
- Restart policy가 `always`이므로 운영 service 조작은 금지
- `.secrets/`가 존재하므로 로그/문서/명령 출력에서 secret 노출 방지 필요
- AI Council endpoint 접근 방식이 확정되지 않음
- 현재 sidecar/outbox 후보 directory는 아직 생성되지 않음

## 절대 하지 말아야 할 것

- Oracle 서버에서 `mkdir`, `touch`, `cp`, `mv`, `rm`, `chmod`, `chown` 실행
- Oracle 서버에 자동 파일 업로드
- `sniper-bot`, `usstock-bot`, `usstock-web` start/stop/restart/reload
- `penny_stock_bot.py` 운영본 직접 수정
- `place_order`, `check_exits`, `force_close_all`에 AI Council 연결
- 실제 주문 생성/전송/승인/취소/실행
- 브로커 API 연결
- `.secrets`, `.env`, config 파일 내용 출력

## 다음 단계 Phase 24I 제안

Phase 24I는 별도 승인 후 다음 중 하나로 진행할 수 있습니다.

1. Oracle에서 AI Council endpoint 접근 전략 비교
2. outbox-only, Mac pull, SSH reverse tunnel, tunnel provider, Oracle-local deploy 옵션 비교
3. preview-only connectivity plan 생성
4. connectivity plan verify
5. 실제 tunnel/public endpoint 없이 dry-run만 수행

어떤 경우에도 review mode, paper simulation, 운영봇 hook 적용은 다음 단계에서 별도 승인 후 진행해야 합니다.

Phase 24I 결과 문서:

- `docs/US_TRADER_ORACLE_NETWORK_CONNECTIVITY_STRATEGY.md`

Phase 24J 결과 문서:

- `docs/US_TRADER_ORACLE_MAC_PULL_PLAN.md`

Phase 24J는 Oracle outbox JSON을 Mac이 read-only로 가져오는 pipeline을 준비합니다. 원격 삭제/이동 없이 local inbox에서 `normalize-preview`를 수행하는 방향입니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
