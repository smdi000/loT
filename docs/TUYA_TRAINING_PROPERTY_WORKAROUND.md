# 训练摘要 Property 兼容方案

## 目的与边界

`training_completed` Event 仍是本项目正式的训练完成模型，未删除也未修改。

由于当前 TuyaLink Event 到 Message Service `deviceEventMessage` 的平台链路问题仍在冻结排查，本比赛阶段临时将一份完整的训练摘要作为**一次** TuyaLink Property Report 上报，以取得已验证的 `devicePropertyMessage` 北向消息并驱动业务后端。该方案不是正式 Event 模型的替代。

设备侧新脚本为 `l610_tuya_training_summary.py`；它复用已验收的 L610 TLS、MQTT CONNECT、Tuya 鉴权和 MIPSEND 实现，不改动既有脚本。

## 已在“外骨骼”TuyaLink 产品创建的 Property

所有字段均为 Property、只上报（ro）。时间字段为涂鸦 Date 类型，页面说明支持 10 或 13 位整数时间戳；本项目发送 13 位 Unix 毫秒。

| DP | 云端 identifier | 类型与数据定义 | 业务语义 |
| --- | --- | --- | --- |
| 104 | `training_session_id` | String，最大 64 bytes | 外部训练会话标识 |
| 105 | `training_started_at` | Date，13 位毫秒时间戳 | 训练开始时间 |
| 106 | `training_ended_at` | Date，13 位毫秒时间戳 | 训练结束时间 |
| 107 | `training_duration_sec` | Value，0–86400，scale 0，unit `s` | 训练时长（秒） |
| 108 | `training_total_reps` | Value，0–100000，scale 0 | 训练总次数 |
| 109 | `training_avg_confidence` | Value，0–10000，scale 2，unit `%` | 平均置信度；9670 = 96.70% |
| 110 | `training_max_elbow_angle` | Value，0–1800，scale 1，unit `°` | 肘关节最大角度；1285 = 128.5° |
| 112 | `training_max_shldr_angle` | Value，0–1800，scale 1，unit `°` | 肩关节最大角度；934 = 93.4° |
| 111 | `training_summary_json` | String，最大 255 UTF-8 bytes | 紧凑动作统计 JSON |

`action_confidence`、`device_status` 与 Event `training_completed` 均保留不变。

## Identifier 限制与后端映射

原计划 identifier `training_max_shoulder_angle` 长度为 27；Tuya 当前页面实际提示 identifier 最多 25 个字符。因此采用经确认的云端兼容标识符 `training_max_shldr_angle`（24 个字符）。

该缩写严格止于 Tuya Thing Model 边界：

```text
training_max_shldr_angle
        ↓
NormalizedTrainingSummary.max_shoulder_angle
        ↓
training_sessions.max_shoulder_angle
        ↓
API range_of_motion.shoulder_max
```

业务模型、数据库和 API 不使用 `shldr` 命名。

## 单次上报内容

`l610_tuya_training_summary.py` 上报固定验收会话 `acceptance_real_training_001`，包含完整字段及紧凑 JSON：

```json
{"actions":{"curl":20,"raise":15,"lateral":12,"boxing":10},"fault_count":0}
```

发送前脚本会反解析 MQTT PUBLISH 包并断言 topic、QoS、Packet Identifier、`sys.ack=1` 和全部摘要字段。后端仅在同一条 `devicePropertyMessage` 含完整摘要 Property 集合时才创建训练会话；缺字段消息仍保存到 `tuya_messages`，但不会创建不完整业务记录。
