# Oracle-local AI Council Deploy Option

This option deploys AI Council backend, or a minimal preview-only receiver, inside Oracle so the US Trader sidecar can call a local endpoint.

## Benefits

- Oracle sidecar can use localhost or private networking.
- No dependency on a sleeping Mac.
- Easier to keep traffic within one server boundary.

## Costs

- Requires deploying and maintaining AI Council on Oracle.
- Requires database, process supervision, backups, and logs.
- Increases resource and operational scope.

## Current Recommendation

Defer this option until outbox-only and Mac pull preview workflows are validated. Keep it read-only and never connect to broker APIs.

`order_execution_allowed=false`
