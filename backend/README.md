# Qmzg Business Backend — Phase 1

This independent backend receives Tuya Message Service messages, stores their original decoded payloads first, and exposes a small development API. It does not modify or depend on the validated L610 serial/MQTT scripts in the repository root.

## Local startup

```powershell
cd backend
Copy-Item .env.example .env
# Fill the five TUYA_* values only when you are ready to connect to Message Service.
docker compose up --build
```

The API is available only on the local host at `http://127.0.0.1:8000`.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/messages
```

With an empty `.env`, the API and PostgreSQL start normally and the consumer stays alive in disabled mode. It does not attempt a Tuya connection until all `TUYA_*` Message Service variables are configured.

To receive one real TEST message without requiring PostgreSQL:

```powershell
python -m app.integrations.tuya.consumer --dry-run `
  --expect-property action_confidence=9731 `
  --capture ..\docs\acceptance\tuya_pulsar_property_message_20260808.json
```

This command logs only the masked Access ID, endpoint, TEST/PROD selector, message metadata, and property keys. It writes a decrypted but identifier-redacted capture to the explicitly selected file; do not use this mode with payloads that contain credentials.

## Tuya Message Service configuration

The consumer follows Tuya's current official Python Pulsar SDK example (`tuya/tuya-pulsar-sdk-python`). It uses `pulsar-client`, Tuya's dynamic Basic authentication shape, and the official AES-GCM/ECB message decryption routine.

Set these values in `backend/.env`; never commit the file.

```dotenv
TUYA_ACCESS_ID=
TUYA_ACCESS_SECRET=
TUYA_PULSAR_URL=pulsar+ssl://mqe.tuyacn.com:7285/
TUYA_PULSAR_TOPIC=TEST
TUYA_PULSAR_SUBSCRIPTION=
```

- For the China Data Center, Tuya's current official Python Pulsar SDK lists `pulsar+ssl://mqe.tuyacn.com:7285/`. The older WSS adapter does not support the observed `aes_gcm` TEST envelope.
- `TUYA_PULSAR_TOPIC` is `TEST` for Test Environment and `PROD` after production Message Service validation.
- `TUYA_PULSAR_SUBSCRIPTION` is optional/deprecated. The official example derives the broker subscription as `{Access ID}-sub`; leave this variable blank unless a future official SDK exposes a supported override.

## Message processing contract

1. The official SDK adapter decrypts and yields a mapping.
2. `TuyaPulsarConsumer` calls `ingest_tuya_message`.
3. The original decoded message is stored in `tuya_messages` before business parsing.
4. `dataId` / `msgId` is used for idempotency; otherwise a deterministic SHA-256 fallback key is used.
5. `devicePropertyMessage` is accepted now. `action_confidence=9731` remains visible in the raw stored payload.
6. `deviceEventMessage` and `training_completed` are modeled but remain untested until the frozen Tuya platform issue is resolved.

The installed Tuya SDK acknowledges a broker message after it calls its listener, even if that listener raises. This Phase 1 implementation records and logs persistence errors without payload or credentials; before production enablement, add an operational alert and agree a replay/recovery procedure for that SDK behavior.

## Development endpoints

- `GET /health`
- `GET /api/messages`
- `GET /api/devices`
- `GET /api/training-sessions`

These routes intentionally have no user authentication in Phase 1 and are for local development only.

## Tests

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location).Path
python -m pytest -q
```

Tests cover the initial Alembic migration, duplicate message idempotency, unknown `bizCode` persistence, property parsing, and the minimal API.

## References

- [Tuya: Get Push Messages by Pulsar (Python SDK)](https://developer.tuya.com/en/docs/iot/Pulsar-SDK-get-message-python?id=Kawi5gt8ft5jx)
- [Tuya: Message Queue](https://developer.tuya.com/en/docs/iot/message-service?id=K95zu0nzdw9cd)
