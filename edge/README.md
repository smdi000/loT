# QMZG Edge

This directory defines the production-facing interface for the future Intel Linux integration. It does not replace or modify the accepted Windows L610 PoC scripts at the repository root.

The stable business entry point is `TuyaEdgeClient`. Intel training code will eventually call:

```python
with TuyaEdgeClient(config, l610_backend) as client:
    client.report_training_summary(summary)
```

Phase 5-A provides validated models, Tuya field mapping, configuration, serial/TLS decision logic and an injectable low-level backend boundary. The actual Linux serial wire backend must be ported and accepted step by step using the root PoC scripts as golden references.

## Local checks

```powershell
python -m pytest edge/tests -q
```

No test in this directory opens a real serial port.
