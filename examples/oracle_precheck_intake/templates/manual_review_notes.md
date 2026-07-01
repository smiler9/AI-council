# Manual Review Notes

- Copy only read-only observations into the intake JSON.
- Do not paste secret values, API keys, tokens, private keys, account numbers, or full config contents.
- Record systemd status as simple state text such as `<service-name>:active` or `<service-name>:inactive`.
- Do not include journal logs that may contain secrets.
- GO is not deployment approval. It only permits considering the next manual review stage.
- Actual Oracle write operations remain prohibited in Phase 24O.
- `order_execution_allowed=false` remains mandatory.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
