# Business Backend Phase 2 Acceptance — 2026-08-08

## Scope

This phase adds the business layer only:

```text
user account -> device binding -> NormalizedTrainingSummary
  -> training_sessions -> protected history/detail/report APIs
```

It does not change L610 communication, Tuya Thing Model, Tuya Message Service configuration, SaaS, or Alibaba Cloud deployment.

## pytest lifecycle diagnosis and resolution

The original Windows host `pytest -q` did not exit despite completed test calls.

Evidence showed two independent host filesystem problems:

1. pytest's optional `cacheprovider` blocked during session finish while creating its cache temporary directory.
2. `tmp_path` attempted to scan `C:\\Users\\...\\AppData\\Local\\Temp\\pytest-of-...`, which the current execution context could not access.

This was not caused by a Pulsar background thread, an unclosed socket/client, FastAPI lifespan, SQLAlchemy session, Docker fixture, or TestClient. `TestClient` was nevertheless changed to a context manager so its anyio portal is explicitly closed.

`backend/pytest.ini` now disables only pytest's optional cache plugin and fixes test temporary files under the project directory. No tests are skipped.

Final result:

```text
18 passed, 1 warning
```

The warning is Starlette's upstream `TestClient` deprecation notice; it does not affect test execution.

## Database migration

- Alembic revision applied to local PostgreSQL: `20260808_02`
- Added `users.password_hash` and `users.updated_at`
- Added the one-owner device constraint: `uq_user_devices_device_id`

## Account APIs

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`

Passwords use bcrypt hashes. Login produces a JWT bearer access token. Passwords, password hashes, and JWT values are not recorded in this document or API responses.

`JWT_SECRET` has no source-code fallback. Before using login outside the isolated test suite, set a strong random value in the ignored `backend/.env` file; `backend/.env.example` lists the required key. If it is absent, authentication returns a configuration error rather than signing tokens with a known development key.

Tests verify successful register/login, identity lookup, and rejected incorrect password.

## Device binding APIs

- `GET /api/devices` — current user's bound devices only
- `POST /api/devices/bind`
- `DELETE /api/devices/{device_id}/bind`

Binding requires an existing real-device row. A device can have exactly one current user owner. Duplicate binding by the same user and binding by a different user both return conflict responses.

## Training ingestion architecture

```text
Normalized Tuya Message
  -> Tuya training adapter
  -> NormalizedTrainingSummary
  -> TrainingSessionService.create_training_session
  -> training_sessions
```

The training service does not parse raw Tuya MQTT/Pulsar JSON. The adapter consumes the pre-existing `NormalizedTuyaMessage` interface and currently supports `training_completed` Events when platform delivery becomes available. The business service accepts `tuya_property`, `tuya_event`, and `mock` sources.

`NormalizedTrainingSummary` validation checks device existence, numeric ranges, timestamp ordering, and reasonable duration/timestamp agreement.

## Mock business acceptance

The test fixture created the required mock session:

- `external_session_id`: `acceptance_session_001`
- duration: `623` seconds
- total repetitions: `57`
- average confidence: `9670` (reported as `96.70%`)
- elbow maximum: `1284` (reported as `128.4°`)
- shoulder maximum: `1148` (reported as `114.8°`)
- source: `mock`

The record was created once. Repeating the same summary returned `created=false`; no duplicate session was created. An unbound device creates and retains a session with `user_id = NULL`. A bound device is automatically associated with its owning user.

## Authorization and report acceptance

Tests verify that a second user cannot list or retrieve another user's training session.

`GET /api/training-sessions` supports page/page-size pagination, optional `device_id` filtering, and newest-first ordering. Detail uses `GET /api/training-sessions/{id}`.

`GET /api/training-sessions/{id}/report` returned this safe, non-medical shape for the mock session:

```json
{
  "duration_sec": 623,
  "total_reps": 57,
  "avg_confidence": 96.7,
  "range_of_motion": {
    "elbow_max": 128.4,
    "shoulder_max": 114.8
  },
  "actions": [
    {"name": "arm_raise", "count": 15},
    {"name": "biceps_curl", "count": 20}
  ],
  "notice": "Training performance summary only; it is not a medical diagnosis or treatment recommendation."
}
```

Unknown `summary_json` fields are retained and returned for forward compatibility.

## Local container state

The local API and Consumer images were rebuilt with the Phase 2 source. PostgreSQL remains healthy and private to the Docker network; the API health endpoint reports both API and database status as `ok`.
