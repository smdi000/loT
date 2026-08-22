# Stable API Contract

本文只描述队友依赖的稳定边界。所有业务 API（除 `/health`、注册/登录）使用 `Authorization: Bearer <JWT>`；MicroApp 通过 `/custom-api` 前缀转发，例如 `/custom-api/api/training-sessions`。

## FastAPI endpoints

| Method | Path | Request / Query | Response |
|---|---|---|---|
| GET | `/health` | — | `{status, database}` |
| POST | `/api/auth/register` | `{email,password,display_name?}` | User |
| POST | `/api/auth/login` | `{email,password}` | `{access_token,token_type}` |
| GET | `/api/me` | JWT | User |
| GET | `/api/devices` | JWT | Device[] |
| POST | `/api/devices/bind` | `{device_id}` | `{device_id,bound}` |
| DELETE | `/api/devices/{device_id}/bind` | JWT | 204 |
| GET | `/api/training-sessions` | `page`, `page_size`, `device_id?` | paginated sessions |
| GET | `/api/training-sessions/{id}` | JWT | TrainingSession |
| GET | `/api/training-sessions/{id}/report` | JWT | TrainingReport |

FastAPI errors use `{ "detail": "..." }` (validation errors may be a detail array). 用户只能读取当前绑定设备的训练记录。

## Public Web routing

| Public path | Target |
|---|---|
| `/`、`/dashboard`、`/devices`、`/training/...` | Nginx 托管 React，使用 SPA history fallback |
| `/custom-api/*` | Nginx 移除 `/custom-api/` 前缀后代理到 FastAPI |
| `/health` | FastAPI health |

Phase 4-C 没有改变任何 FastAPI request/response schema。

## TrainingSummary — Edge business object

```json
{
  "session_id": "demo_session_001",
  "started_at": "timezone-aware datetime",
  "ended_at": "timezone-aware datetime",
  "duration_sec": 623,
  "total_reps": 57,
  "avg_confidence": 9670,
  "max_elbow_angle": 1285,
  "max_shoulder_angle": 934,
  "training_type": "active_assist",
  "actions": {"curl": 20, "raise": 15, "lateral": 12, "boxing": 10},
  "fault_count": 0
}
```

整数缩放：`avg_confidence=9670` 表示 96.70%，角度 `1285` 表示 128.5°。

## Tuya property adapter mapping

| Edge field | Tuya identifier |
|---|---|
| session_id | `training_session_id` |
| started_at | `training_started_at` (Unix ms) |
| ended_at | `training_ended_at` (Unix ms) |
| duration_sec | `training_duration_sec` |
| total_reps | `training_total_reps` |
| avg_confidence | `training_avg_confidence` |
| max_elbow_angle | `training_max_elbow_angle` |
| max_shoulder_angle | `training_max_shldr_angle` |
| actions + fault_count + optional training_type | `training_summary_json` compact JSON |

`shldr` 仅存在于 Tuya 25 字符限制的边界，业务对象、数据库和 API 始终使用 `max_shoulder_angle`。

## TrainingSession response

`avg_confidence` 与角度在 session API 中仍是缩放整数；`summary_json` 保留 actions/fault_count。`training_type` 是 `passive_assist | resistance | active_assist | null`，未知或历史记录缺失时为 `null`；`source_type` 是 `tuya_property | tuya_event | mock`。

真实 Edge Training Summary 不新增 Tuya Property，而是在现有 compact `training_summary_json` 中传递可选的 `training_type`。兼容输入键 `training_mode`，业务层始终输出 canonical `training_type`；未知值被忽略为 `null`，不会导致整条训练丢失。

## TrainingReport response

报告把平均置信度和角度转换为展示数值：`avg_confidence=96.7`、`range_of_motion={elbow_max:128.5, shoulder_max:93.4}`，并返回 `training_type`、`actions`、`fault_count` 与非医疗声明。不得将其描述为诊断或治疗建议。
