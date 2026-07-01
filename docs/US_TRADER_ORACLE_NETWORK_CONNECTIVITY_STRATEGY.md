# US Trader Oracle Network Connectivity Strategy

Phase 24I는 Oracle US Trader sidecar가 AI Council webhook/normalize-preview에 접근하는 방식을 결정하기 위한 전략 문서입니다. 이 단계에서는 실제 tunnel, public endpoint, SSH reverse tunnel, firewall/security group 변경을 만들지 않습니다.

## 핵심 네트워크 사실

Oracle 서버에서 `127.0.0.1`은 Oracle 자기 자신입니다. 로컬 Mac에서 실행 중인 AI Council backend `http://127.0.0.1:8000`은 Oracle에서 직접 접근할 수 없습니다.

따라서 Oracle sidecar가 AI Council에 접근하려면 다음 중 하나가 필요합니다.

- Oracle은 JSON outbox만 만들고 AI Council 연동은 나중에 수행
- Mac AI Council이 Oracle outbox를 pull
- tunnel 또는 reverse tunnel
- Oracle 내부 AI Council 배포

## 평가 기준

- Oracle 운영봇을 건드리지 않는 정도
- 실제 주문 경로와 분리 정도
- 네트워크 노출 최소화
- secret 관리 난이도
- 장애 시 영향 범위
- preview-only 검증 용이성
- read-only review / paper simulation 확장 가능성

## A안: Oracle에서 로컬 Mac AI Council 직접 webhook 호출

조건:

- Mac이 외부에서 접근 가능한 주소 필요
- 포트 공개 또는 tunnel 필요

장점:

- 구조가 단순해 보임

단점/위험:

- 로컬 Mac backend를 공개해야 할 수 있음
- IP 변경, NAT, macOS sleep, 방화벽 이슈
- webhook secret과 접근제어를 강하게 관리해야 함

추천: 비추천. 직접 public exposure는 preview 단계에 과합니다.

## B안: Cloudflare Tunnel / ngrok / Tailscale

조건:

- 로컬 Mac AI Council을 tunnel로 노출
- tunnel token과 접근 정책 관리 필요

장점:

- 빠른 연결 가능
- HTTPS/identity access를 붙일 수 있음

단점/위험:

- token/secret 관리 부담
- 공개 reachable endpoint 운영 부담
- tunnel 상태와 로그 관리 필요

추천: 보류. 편하지만 preview 첫 단계에는 보안/운영 부담이 큽니다.

## C안: SSH reverse tunnel

예:

- Mac에서 Oracle로 reverse tunnel 생성
- Oracle sidecar는 Oracle localhost forwarded port로 AI Council 호출

장점:

- public endpoint 없이 구현 가능
- 단기 preview에는 유용

단점/위험:

- macOS sleep/network change에 취약
- tunnel supervision 필요
- 실제 tunnel 실행은 별도 승인 필요

추천: 3순위. outbox-only와 Mac pull 다음에 단기 preview 용도로 검토합니다.

## D안: Oracle에 AI Council backend 일부 또는 전체 배포

조건:

- Oracle 내부에 AI Council backend 또는 최소 preview receiver 배포

장점:

- Oracle sidecar가 localhost/private endpoint로 접근 가능
- Mac sleep과 public tunnel 문제 감소

단점/위험:

- 배포/운영 범위 증가
- DB, logs, backups, process supervision 필요
- AI Council UI와 운영 구조를 다시 설계해야 함

추천: 보류. 초기 preview 후 필요하면 별도 단계로 검토합니다.

## E안: Mac AI Council이 Oracle outbox를 read-only pull

조건:

- Oracle outbox JSON이 존재해야 함
- Mac에서 Oracle에 read-only pull workflow 필요

장점:

- Oracle outbound webhook 불필요
- AI Council public exposure 불필요
- 운영봇과 sidecar/network가 분리됨
- paper simulation으로 확장하기 좋음

단점/위험:

- outbox directory 생성과 export hook은 별도 승인 필요
- pull job 운영이 필요
- remote file 삭제 금지 원칙 필요

추천: 2순위. 자동화가 필요해지면 가장 안전한 다음 단계입니다.

## F안: Oracle sidecar가 AI Council을 호출하지 않고 JSON만 쌓기

조건:

- Oracle outbox directory와 JSON export만 필요
- 네트워크 연결 없음

장점:

- 네트워크 노출 없음
- tunnel/secret 부담 없음
- 운영봇과 AI Council 완전 분리
- preview payload shape 검증에 최적

단점:

- 자동 review가 즉시 실행되지 않음
- 사람이 수동으로 파일을 가져오거나 다음 단계 pull이 필요함

추천: 1순위. 가장 보수적인 preview-only 전략입니다.

## 추천 결과

1순위: `oracle_outbox_only_preview`

2순위: `mac_pull_oracle_outbox`

3순위: `ssh_reverse_tunnel_preview`

보류:

- `cloudflare_tunnel_preview`
- `oracle_local_ai_council_preview`

비추천:

- `direct_mac_public_webhook`

## 우선 적용 전략

우선 적용은 `oracle_outbox_only_preview`로 확정합니다.

이 전략은 Oracle 서버에 AI Council endpoint 연결을 만들지 않고, preview JSON outbox만 준비합니다. 그 다음 별도 승인 후 Mac pull 방식으로 AI Council normalize-preview를 수행하는 방향이 안전합니다.

## Dry-run 도구

```bash
scripts/compare_oracle_connectivity_options.sh
scripts/generate_oracle_connectivity_plan.sh
scripts/verify_oracle_connectivity_plan.sh
scripts/run_oracle_connectivity_strategy_dryrun.sh
```

기본 plan은 `tmp/oracle_connectivity_plan.json`에 생성되며 Git에 포함하지 않습니다.

## Preview-only 원칙

- 실제 tunnel 실행 없음
- public endpoint 자동 생성 없음
- SSH reverse tunnel 실제 실행 없음
- firewall/security group 변경 없음
- Oracle live bot 수정 없음
- systemd service 조작 없음
- `order_execution_allowed=false`

## 다음 Phase 24J 제안

Phase 24J는 별도 승인 후 다음 중 하나를 진행할 수 있습니다.

1. Oracle outbox-only directory 생성 전 manual approval record 작성
2. outbox-only sample JSON을 수동 배치하는 절차 확정
3. Mac pull dry-run 도구 작성
4. AI Council normalize-preview에 local pulled JSON을 공급하는 workflow 작성

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
