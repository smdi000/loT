# Business Backend Phase 3 — 真机训练摘要验收

验收时间：2026-08-08（中国香港时区）。本记录不包含 DeviceSecret、Tuya Access Secret、Pulsar 凭证、JWT 或用户密码。

## 目标

验证比赛阶段的兼容上行链路：

```text
Fibocom L610
  -> TuyaLink Property Report
  -> Tuya Message Service TEST / devicePropertyMessage
  -> Python Consumer
  -> PostgreSQL tuya_messages
  -> NormalizedTrainingSummary
  -> TrainingSessionService
  -> training_sessions
  -> FastAPI history / detail / report
```

`training_completed` Event 保持原样；本次使用 Property workaround 的原因和字段定义见 `docs/TUYA_TRAINING_PROPERTY_WORKAROUND.md`。

## Thing Model 实际配置

产品“外骨骼”已新增 DP104–DP112 的完整训练摘要 Property，均为 Property / 只上报（ro）：

- `training_session_id`（String，64 bytes）
- `training_started_at`、`training_ended_at`（Date，13 位毫秒时间戳）
- `training_duration_sec`（0–86400，scale 0，`s`）
- `training_total_reps`（0–100000，scale 0）
- `training_avg_confidence`（0–10000，scale 2，`%`）
- `training_max_elbow_angle`（0–1800，scale 1，`°`）
- `training_max_shldr_angle`（0–1800，scale 1，`°`）
- `training_summary_json`（String，255 UTF-8 bytes）

Tuya identifier `training_max_shldr_angle` 是 25 字符上限下的边界层缩写；后端统一映射到 `max_shoulder_angle`。

## 真机发送结果

串口最小确认：COM21 / 115200，Fibocom L610-CN-62-36，SIM READY，`+CEREG: 0,1`。

测试训练：

| 字段 | 值 |
| --- | --- |
| `training_session_id` | `acceptance_real_training_001` |
| `duration_sec` | 623 |
| `total_reps` | 57 |
| `avg_confidence` | 9670（96.70%） |
| `max_elbow_angle` | 1285（128.5°） |
| `max_shoulder_angle` | 934（93.4°） |
| `summary_json` | `{"actions":{"curl":20,"raise":15,"lateral":12,"boxing":10},"fault_count":0}` |

设备端真实 ACK：

- CONNACK：`20 02 00 00`
- SUBACK：`90 03 00 01 01`
- MQTT PUBLISH：811 bytes；MIPSEND 实际 payload：811 bytes
- PUBACK：`40 02 00 02`
- Tuya `thing/property/report_response`：`code=0`
- socket 正常关闭

设备日志：`logs/l610_tuya_training_summary_20260808_221915.log`。

## Message Service 与 Consumer

Pulsar TEST Consumer 已连接到中国区 TEST channel。真实消息保存为：

- `biz_code`: `devicePropertyMessage`
- 设备 ID：已脱敏（后四位 `hp6h`）
- 产品 ID：已脱敏（后四位 `ckvo`）
- `tuya_msg_id`: 本次 L610 报文的唯一 msgId（已保存于数据库，不在本文档展开）
- `processed`: `true`

Message Service 的同一条 `bizData.properties` 实际包含 9 个训练摘要字段，未拆成多条消息。因此当前没有引入 staging、Redis 或聚合定时器。

## Normalization 与 PostgreSQL

Property boundary adapter 完整识别本次消息并产生：

- `NormalizedTrainingSummary.source_type = tuya_property`
- `external_session_id = acceptance_real_training_001`
- `duration_sec = 623`
- `total_reps = 57`
- `avg_confidence = 9670`
- `max_elbow_angle = 1285`
- `max_shoulder_angle = 934`

`TrainingSessionService` 自动读取真实 DeviceID 的当前 owner binding；`training_sessions.user_id` 非空。数据库中只有一条相应会话。

## API 验收

使用绑定设备 owner 的本地验收账户完成登录（密码与 JWT 未记录）：

- `GET /api/training-sessions`：找到 `acceptance_real_training_001`
- `GET /api/training-sessions/{id}`：字段与真机上报一致
- `GET /api/training-sessions/{id}/report`：返回 623 秒、57 次、96.70%、肘 128.5°、肩 93.4°、四项动作计数和 `fault_count=0`

报告仅为训练表现与设备统计；接口继续明确声明其不是医疗诊断或治疗建议。

## 幂等与自动测试

将刚刚存储的真实 `payload_json` 再次投入 ingest 层：

- `tuya_messages`：未新增重复记录（以 `tuya_msg_id` / dedup key 去重）
- `training_sessions`：未新增重复记录（同时受 DeviceID + external session id 与 `tuya_msg_id` 约束）

后端完整自动测试：`22 passed, 1 warning`。warning 来自 Starlette/TestClient 对当前 httpx 兼容层的弃用提示，不影响验收。
