# Stage 06 Prompt — Property Positive Control

## GOAL

首次从正式 Intel Python → `/dev/tty*` → L610 上报一个新的 `action_confidence` 值，并验证 Tuya/ECS `devicePropertyMessage`。Windows 不参与发送。

## KNOWN GOOD BASELINE

Stage 00–05 必须已通过。`action_confidence` 是已真实验证的低风险 Property；旧值 9982/9731/9732 已用过，本次选一个新的 0–10000 整数并记录。QoS1 路线应收到 CONNACK、SUBACK、PUBACK 和 Tuya `code=0`。ECS/Pulsar TEST 正例已工作。

## ALLOWED CHANGES

仅 `edge/` property report/backend tests、`docs/acceptance/phase5b_stage06*`。允许只读 ECS/API 验证，但不改生产。

## FORBIDDEN CHANGES

禁止运行根 Windows publisher、修改 Thing Model/Message Rule/ECS/backend/schema/SaaS、逐帧高频上报、打印 Secret。

## COMMANDS / INSPECTION

在 Intel 受保护配置下，调用正式 `TuyaEdgeClient.report_property("action_confidence", <new_value>)`。必须使用已经通过的 Linux link backend，不临时 import root Windows 脚本。订阅 property response、一次 QoS1 publish、等待业务 ACK并关闭。随后只读检查 ECS consumer/数据库或正式 API，按 DeviceID/msgId/值定位真实消息。

## SUCCESS CRITERIA

Intel 日志：CONNACK 0、SUBACK有效、PUBACK匹配、Tuya code=0；ECS 中 `biz_code=devicePropertyMessage`、DeviceID/ProductID正确、payload值等于本次新值、processed合理。

## STOP CONDITIONS

任何前置 Stage失效、设备 ACK 缺失、ECS无消息、需要改规则/白名单/云配置、可能存在 duplicate DeviceID client。不能只凭 code=0宣布云闭环成功。

## EVIDENCE TO SAVE

新值、msgId脱敏、Intel serial/MQTT ACK、ECS row/API摘要、时间关联、代码/tests/Git；不保存 Access/Device Secret。

## FINAL REPORT FORMAT

模板 + `Intel source | value | ACKs | Tuya code | Pulsar bizCode | ECS persisted | processed | PASS/STOP`。报告后停止。
