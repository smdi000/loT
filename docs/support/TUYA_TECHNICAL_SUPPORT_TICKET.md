# Tuya Technical Support Ticket

## Subject

TuyaLink Event上报成功但未进入Message Service deviceEventMessage

## Body

我们正在使用 TuyaLink 自定义设备接入，发现设备 Event 能正常上报到 IoT Core 和 Device Log，也已经正常暴露为 Device Northbound original capability，但无法通过 Message Service 收到对应 deviceEventMessage。

### 环境

- Data Center：中国数据中心
- Cloud Project：擎梦智骨云端训练平台
- Product：TuyaLink 自定义产品
- Device：真实 TuyaLink 设备
- Message Service：已启用
- Test Device：已添加
- Test Channel：connection established
- Messaging Rule：BizCode In deviceEventMessage

### Event

`training_completed`

outputParams 示例：

- `session_id`
- `duration_sec`
- `total_reps`
- `avg_confidence`
- `max_elbow_angle`
- `max_shoulder_angle`
- `summary_json`

### 设备上报结果

MQTT 链路全部成功：

- CONNACK：`20 02 00 00`
- SUBACK：成功
- PUBACK：成功
- Tuya Event response：`code=0`

最新复现：

`session_id=test_northbound_enabled_20260808_032918`

Device Log 中能够看到：

`eventCode=training_completed`

并且：

`result.code=0`

`result.status=success`

outputParams 内容正确。

### Device Northbound Service

已完成 ¥0 体验版订阅并授权到当前 Cloud Project。

调用：

`GET /v1.0/iot-03/devices/{device_id}/capabilities-definition?tags=original`

返回成功。

`training_completed` 存在，并且：

`methods=["event"]`

`action_confidence` 和 `device_status` 也正常存在于 original capabilities。

### Message Service 正例

同一真实设备、同一 Cloud Project、同一 Test Environment 下：

`devicePropertyMessage` 已实际验证成功。

上报：

`action_confidence=9982`

Test Channel 能正确收到对应：

`devicePropertyMessage`

同时设备 online/offline 消息也能进入 Message Service。

因此已确认：

- Device Linking 正常
- Message Service 正常
- Test Device 正常
- Test Channel 正常
- Property Message pipeline 正常
- TuyaLink Event 上报正常
- Device Log 正常
- Original Capability 正常

目前唯一异常为：

`TuyaLink Event → Message Service deviceEventMessage`

Test Channel 中始终没有产生对应 `deviceEventMessage`。

平台 UI 不允许发布没有 BizCode 条件的空规则，因此无法通过 All BizCodes 做进一步诊断。

### 希望协助确认

1. TuyaLink 自定义产品的 Event 是否应该进入 Message Service `deviceEventMessage`？
2. 是否还需要额外开通某项服务/API/消息能力？
3. `deviceEventMessage` 是否有额外的 Message Rule 配置要求？
4. 是否存在 TuyaLink Event → Pulsar 的产品类型或开发状态限制？
5. 如果当前配置理论上已经正确，请协助查询上述 `session_id` 对应事件为何没有进入 Message Service。

## Identifiers available to support

- Project ID：`p17861257420227fdk4j`
- Product ID：`0fc7obn925auckvo`
- Device ID：`269a934046f4318631hp6h`

## Safe attachments

1. Device Log 中 `training_completed` 成功截图（`eventCode`、`outputParams`、`result.code=0`、`result.status=success`）。
2. Message Service `devicePropertyMessage` 正例截图。
3. Original Capabilities 响应：`docs/acceptance/tuya_capabilities_original_20260808.json`。
4. 当前 Message Rule 截图（`BizCode In deviceEventMessage`）。
5. Test Device / Test Channel 截图（含 `connection established`）。
6. 脱敏后的设备事件日志摘要：`docs/acceptance/tuya_message_service.md`。

## Safety

此工单及附件不得包含 DeviceSecret、Cloud Access Secret、Cookie、Token、MQTT password 或任何浏览器凭证。
