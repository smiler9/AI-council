# Oracle Staging Rehearsal

이 폴더는 Oracle US Trader 운영봇을 직접 수정하지 않고, 로컬 staging copy 또는 fixture에서 signal export hook patch preview를 검증하는 도구입니다.

## 실행

```bash
cd ~/AI-council
scripts/run_oracle_staging_rehearsal.sh
```

## 포함 도구

- `analyze_us_trader_bot.py`: 함수 위치와 safe/unsafe insertion point 정적 분석
- `prepare_staging_rehearsal.py`: 원본을 수정하지 않고 staging copy 생성
- `generate_export_hook_patch_preview.py`: unified diff 또는 patched preview file 생성
- `validate_staging_patch.py`: unsafe function 내부 hook 삽입 여부 검증

## Phase 24F 연결

staging rehearsal이 통과한 뒤에만 deployment bundle과 manual approval gate를 검토합니다.

```bash
scripts/build_oracle_signal_export_bundle.sh
scripts/verify_oracle_signal_export_bundle.sh
scripts/run_oracle_readiness_check_dryrun.sh
```

실제 Oracle 적용은 아직 하지 않습니다. bundle과 readiness check는 수동 승인 전 검토용입니다.

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed`는 항상 `false`입니다.
