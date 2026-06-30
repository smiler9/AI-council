# Oracle Signal Export Bundle

This bundle is a local package for manual review before any Oracle-side work.
It is not an automated deployment artifact.

## Contents

- `ai_council_signal_exporter_module.py`: review-only outbox JSON exporter helper.
- `us_trader_signal_outbox_bridge.py`: sidecar bridge that sends outbox JSON to AI Council preview/review endpoints.
- `mapping_profiles/us_trader_oracle_v1.json`: field mapping profile.
- `sample_outbox/`: TEST ticker samples only.
- `oracle_env.example`: placeholder-only environment file.
- `manual_apply_commands.example.sh`: non-executing manual notes.
- `sidecar_systemd_example.service`: template for review only.
- `sidecar_cron_example.txt`: template for review only.
- `manifest.json`: sha256 manifest and safety notes.

## Required Checks

Run these locally before any manual Oracle action:

```bash
scripts/run_oracle_sidecar_smoke.sh
scripts/run_oracle_export_hook_preflight.sh
scripts/run_oracle_staging_rehearsal.sh
scripts/build_oracle_signal_export_bundle.sh
scripts/verify_oracle_signal_export_bundle.sh
scripts/run_oracle_readiness_check_dryrun.sh
```

## Safety Boundary

AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

Oracle live bot changes require separate manual approval. Keep the sidecar in preview mode first.

`order_execution_allowed=false`
