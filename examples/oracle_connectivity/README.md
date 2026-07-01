# Oracle Connectivity Strategy

Phase 24I는 Oracle US Trader sidecar가 AI Council에 접근하는 방식을 비교하고, 실제 네트워크 변경 없이 preview-only connectivity plan을 생성/검증합니다.

## 전체 dry-run

```bash
cd ~/AI-council
scripts/run_oracle_connectivity_strategy_dryrun.sh
```

## 개별 실행

```bash
scripts/compare_oracle_connectivity_options.sh
scripts/generate_oracle_connectivity_plan.sh
scripts/verify_oracle_connectivity_plan.sh
```

## 기본 추천

기본 plan은 `oracle_outbox_only_preview`입니다.

이 방식은 Oracle이 AI Council endpoint를 호출하지 않고 JSON outbox만 준비하는 가장 보수적인 preview 전략입니다. 다음 단계 자동화가 필요하면 `mac_pull_oracle_outbox`를 검토합니다.

## 금지

- 실제 tunnel 실행
- SSH reverse tunnel 실행
- Cloudflare/ngrok/Tailscale 실행
- 방화벽/보안그룹 변경
- Oracle live bot 수정
- 실제 주문 실행
- 브로커 API 연결

`order_execution_allowed=false`
