# Oracle Outbox-only Preview

This is the most conservative preview strategy.

Oracle writes or stages JSON signal files in an approved outbox directory, but does not call AI Council over the network. AI Council review is performed later by manually copying samples or by a separately approved Mac pull workflow.

## Properties

- No public AI Council exposure
- No tunnel
- No Oracle outbound webhook
- No broker API
- No real order execution
- `order_execution_allowed=false`

## Use First When

- The AI Council endpoint is not yet reachable from Oracle.
- The first objective is payload shape validation and operational separation.
- Manual inspection is preferred over automation.
