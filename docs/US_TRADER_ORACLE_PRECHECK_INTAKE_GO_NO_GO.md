# US Trader Oracle Precheck Intake Go/No-Go

## Phase 24O 목적

Phase 24O는 사람이 Oracle에서 수행한 read-only precheck 결과를 표준 intake JSON으로 입력하고, outbox 수동 생성 검토 단계로 넘어가도 되는지 GO/NO-GO를 판단합니다.

이번 단계는 결과 입력, 검증, 판정, 문서, 테스트까지만 수행합니다. Oracle 서버에 파일을 쓰지 않고, 업로드하지 않고, systemd 서비스를 조작하지 않으며, 운영봇을 수정하지 않습니다.

## 왜 Read-only Precheck 결과를 기록해야 하는가

수동으로 확인한 결과를 문장이나 터미널 로그로만 남기면 누락과 오해가 생깁니다. Intake JSON은 필수 관찰값, safety flag, manual operator, checked time, notes를 구조화해 다음 단계 판단을 재현 가능하게 만듭니다.

## Intake Template 작성법

템플릿 생성:

```bash
scripts/build_oracle_precheck_intake_template.sh
```

출력:

```text
tmp/oracle_precheck_intake/precheck_intake_template.json
```

사람이 채울 필드:

- `result_status`
- `manual_operator`
- `checked_at`
- `oracle_target`, 단 실제 IP/key path 대신 placeholder 또는 redacted 값 사용
- `observations`
- `safety`
- `notes`

Secret, API key, token, private key, 계좌 정보, config 내용은 기록하지 않습니다.

## Intake Validate

```bash
scripts/validate_oracle_precheck_intake.sh
```

검증 항목:

- `result_status`가 `passed`, `warning`, `failed`, `incomplete` 중 하나
- safety flag가 모두 false
- 필수 observations가 true
- `services_observed`가 비어 있지 않음
- secret marker 없음
- 실제 Oracle IP/SSH key path 없음
- `order_execution_allowed=false`

## Go/No-Go 판단

```bash
scripts/decide_oracle_precreation_go_no_go.sh
```

GO 조건:

- `validation_status=passed`
- `result_status=passed` 또는 `warning`
- remote write/systemd/live bot/secret/order safety flags false
- trading dir, bot file, server file, Python, disk 필수 조건 충족
- active services가 관찰됐지만 조작되지 않음

NO-GO 조건:

- remote write 발생
- systemd 변경 발생
- live bot 수정 발생
- secret 노출
- 필수 파일/디렉터리 없음
- disk space 불량
- Python 3 사용 불가
- result_status failed
- order execution true 상태
- secret marker 감지

## GO가 의미하는 것과 의미하지 않는 것

GO는 실제 적용 승인이 아니라 outbox 수동 생성 검토 단계로 넘어갈 수 있다는 뜻입니다.

GO가 의미하지 않는 것:

- 실제 Oracle 적용 승인
- 운영봇 수정 승인
- systemd 조작 승인
- 브로커 API 연결 승인
- 주문 실행 승인

## Dry-run

```bash
scripts/run_oracle_precheck_intake_dryrun.sh
```

Dry-run은 sample intake를 로컬 `tmp/` 아래에 복사해 validate와 decision을 실행합니다. Oracle 서버에 접속하지 않습니다.

## 다음 Phase 24P 조건

- readonly precheck dry-run 통과
- precheck intake validation 통과
- GO decision 생성
- 사람이 GO의 범위를 이해하고 별도 수동 승인
- 실제 쓰기 작업은 여전히 자동화하지 않음

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
