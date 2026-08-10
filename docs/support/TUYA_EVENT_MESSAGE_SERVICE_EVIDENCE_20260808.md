# TuyaLink Event → Message Service 证据摘要（脱敏）

## 标识

- Project ID：`p17861257420227fdk4j`
- Product ID：`0fc7obn925auckvo`
- Device ID：`269a934046f4318631hp6h`
- Data Center：中国数据中心

## 事件负例：training_completed

- Event code：`training_completed`
- 最新 session_id：`test_northbound_enabled_20260808_032918`
- msgId：`l610evt856f7095d89c4dc19db2c1c79`
- MQTT CONNACK：`20 02 00 00`
- MQTT SUBACK：`90 03 00 01 01`
- MQTT PUBACK：`40 02 00 02`
- TuyaLink Event response：`code=0`

Device Log 已显示该事件，且 `result.code=0`、`result.status=success`。已核对 `session_id`、`duration_sec=623`、`total_reps=57`、`avg_confidence=9670`、`max_elbow_angle=1284`、`max_shoulder_angle=1148` 与上报内容一致。

Message Service Test Environment 条件如下：

- Message Service：Enabled
- Test Device：已添加（上述 Device ID）
- Test Channel：Enabled，显示 `connection established`
- Messaging Rule：`BizCode In deviceEventMessage`

在该条件下，Test Channel 未出现与上述 session_id、msgId 或 `training_completed` 对应的 `deviceEventMessage`。

## Property 正例：action_confidence

同一 Device、Project、Test Environment 中，`action_confidence=9982` 已进入 Test Channel：

- bizCode：`devicePropertyMessage`
- devId：`269a934046f4318631hp6h`
- productId：`0fc7obn925auckvo`
- property code：`action_confidence`
- value：`9982`

同时，设备 online/offline 消息可进入 Message Service。

## Device Northbound Service

Device Northbound Service 已完成 ¥0 体验版订阅并授权给本 Cloud Project。只读接口：

`GET /v1.0/iot-03/devices/{device_id}/capabilities-definition?tags=original`

返回成功，核心 capability 如下：

| capability_code | methods |
| --- | --- |
| `action_confidence` | `get`, `event` |
| `device_status` | `get`, `event` |
| `training_completed` | `event` |

## 规则诊断限制

平台 Test Environment UI 不允许发布一个无 BizCode 条件的空规则：移除唯一 BizCode 条件后，“发布规则”按钮不可用。因此无法在仅限定当前 Test Device 的条件下执行 All BizCodes / no-BizCode 对照测试。该未发布编辑已放弃，线上规则仍为 `BizCode In deviceEventMessage`。

## 脱敏声明

本文件和随附 capability JSON 未包含 DeviceSecret、Cloud Access Secret、Cookie、Token、MQTT password 或浏览器凭证。
