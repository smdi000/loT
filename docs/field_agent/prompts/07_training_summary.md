# Stage 07 Prompt — Intel Training Summary

## GOAL

由 Intel 正式 Edge API 创建并上报一次 `acceptance_intel_training_001`，进入 Tuya Property pipeline。禁止使用 Windows golden script 发送。

## KNOWN GOOD BASELINE

Stage 06 property正例已过。`TrainingSummary` 稳定字段：session_id、aware started/ended、duration_sec、total_reps、avg_confidence(scale2)、max_elbow_angle/max_shoulder_angle(scale1)、actions、fault_count。Tuya边界仅肩字段缩写为 `training_max_shldr_angle`。已验收示例 623s/57/9670/1285/934及 curl20/raise15/lateral12/boxing10。

## ALLOWED CHANGES

仅 `edge/` TrainingSummary/report wiring/tests 与 `docs/acceptance/phase5b_stage07*`。

## FORBIDDEN CHANGES

禁止 Windows发送、逐帧云上传、改 Thing Model/Event/backend/schema/SaaS/golden、伪造云数据。

## COMMANDS / INSPECTION

在 Intel 程序构造 timezone-aware、时间差与 duration 一致的 `TrainingSummary(session_id="acceptance_intel_training_001", ...)`，调用 `TuyaEdgeClient.report_training_summary(summary)` 一次。发送前自检 9 个 Property、紧凑 summary JSON ≤255 UTF-8 bytes、MQTT/MIPSEND长度。等待完整 MQTT与Tuya ACK；记录 Device Log/Pulsar 是否一条消息包含完整字段，不预先引入 staging/Redis。

## SUCCESS CRITERIA

从 Intel tty发送；CONNACK/SUBACK/PUBACK/Tuya code=0；Message Service 收到一个完整 `devicePropertyMessage`，session_id与全部字段正确。

## STOP CONDITIONS

缺字段、Tuya拆分为多消息、ACK失败、数据范围/时间验证失败、Stage06未过。若拆分，保存真实样本并停止，不猜聚合设计。

## EVIDENCE TO SAVE

session字段、msgId脱敏、property集合、packet长度/ACK、Pulsar脱敏样本、代码/tests/Git。

## FINAL REPORT FORMAT

模板 + `session_id | source Intel tty | normalized fields | ACKs/code | Pulsar complete/split | PASS/STOP`。报告后停止。
