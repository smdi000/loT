# Business Backend PostgreSQL Acceptance — 2026-08-08

## Scope

This acceptance verifies the current positive-control path only:

```text
L610 property report
  -> Tuya Message Service TEST
  -> official Python Pulsar consumer
  -> PostgreSQL tuya_messages
  -> FastAPI GET /api/messages
```

The frozen `training_completed` Event-to-Message-Service issue is outside this test.

## Local runtime

- Docker Engine: `29.6.2`
- Docker Compose: `v5.3.1`
- PostgreSQL image: `postgres:16-alpine`
- PostgreSQL exposure: container network only (`5432/tcp`); no host port mapping
- API exposure: `127.0.0.1:8000` only
- Tuya Message Service channel: `TEST`
- Pulsar endpoint: `pulsar+ssl://mqe.tuyacn.com:7285/`
- Consumer implementation: official `pulsar-client` path with Tuya-compatible authentication and `aes_gcm` envelope decryption

No DeviceSecret, Cloud Access Secret, token, cookie, or full device identifier is recorded in this document.

## Database migration

Alembic was run through the API container:

```text
alembic upgrade head
```

Verified revision: `20260808_01`.

Verified tables:

- `alembic_version`
- `users`
- `devices`
- `user_devices`
- `tuya_messages`
- `training_sessions`

## Real device message

The accepted L610 property-report program was invoked without source changes. The test value was overridden only in that process:

```text
action_confidence = 9732
```

Device-side protocol evidence:

- MQTT CONNACK: `20 02 00 00`
- MQTT SUBACK: `90 03 00 01 01`
- MQTT QoS 1 PUBACK: `40 02 00 02`
- Tuya business response: `code=0`
- Socket closed normally: yes

## Consumer and PostgreSQL evidence

The TEST consumer connected successfully to the configured China Pulsar endpoint. It received and persisted one real message with:

- `biz_code`: `devicePropertyMessage`
- device ID: `269a...hp6h` (masked)
- product ID: `0fc7...ckvo` (masked)
- `action_confidence`: `9732`
- `processed`: `true`
- `received_at`: present
- deduplication key: Tuya `dataId`/message ID (`tuya_msg_id`), not the SHA-256 fallback

The PostgreSQL query returned exactly this matching row.

## FastAPI evidence

`GET http://127.0.0.1:8000/api/messages?limit=20` returned the same `devicePropertyMessage` with `action_confidence=9732`, `processed=true`, and valid receive time.

`GET http://127.0.0.1:8000/health` returned:

```json
{"status":"ok","database":"ok"}
```

## Idempotency

The Consumer ingestion service was invoked once more with the exact raw payload already stored for this real 9732 message. Result:

```text
duplicate_created=False
rows_before=1
rows_after=1
dedup=tuya_msg_id
```

Therefore the same Tuya message is not inserted twice.

## Result

**Accepted:** real `L610 -> Tuya -> Pulsar TEST -> Consumer -> PostgreSQL -> FastAPI` property-message ingestion is working for `action_confidence=9732`.
