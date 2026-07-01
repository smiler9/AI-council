# Preview Signal File Contract

This contract is for Phase 24R manual preview signal write rehearsal only.

Required fields:

- `source`
- `signal_id`
- `symbol`
- `signal`
- `action`
- `price`
- `volume`
- `timestamp`
- `review_only=true`
- `simulation_only=true`
- `order_execution_allowed=false`

`action=buy` is preserved only as raw review context. It is not an order instruction.

Forbidden use:

- Do not connect this file to `place_order`, exit handling, broker APIs, or any order execution path.
- Do not include account, private key, token, or secret values.
- Do not use real ticker recommendations; use test symbols such as `TESTA`.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
