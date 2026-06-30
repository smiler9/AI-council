# Oracle Preview-only Sidecar Deploy Preparation

이 폴더는 Oracle 운영봇을 직접 수정하지 않고, AI Council sidecar bridge를 preview-only 모드로 배치하기 위한 plan과 command preview를 생성합니다.

## 전체 dry-run

```bash
cd ~/AI-council
scripts/run_oracle_preview_deploy_dryrun.sh
```

## 개별 실행

```bash
scripts/prepare_oracle_preview_deploy_plan.sh
scripts/verify_oracle_preview_deploy_plan.sh
scripts/generate_oracle_preview_commands.sh
```

## 산출물

- `tmp/oracle_preview_deploy_plan.json`
- `tmp/oracle_preview_commands/`

이 산출물은 Git에 포함하지 않습니다.

## 원칙

- 기본 mode는 `preview`
- 실제 Oracle 업로드 없음
- systemd 운영봇 조작 없음
- `penny_stock_bot.py` 수정 없음
- 실제 주문 없음
- 브로커 API 연결 없음
- `order_execution_allowed=false`

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
