# Tuya `training_completed` 真机验收记录

## 验收结论

2026-08-08，Fibocom L610-CN-62-36 通过中国电信 4G、TLS 1.2 和手工 MQTT 3.1.1，向 TuyaLink 真机上报了一次 `training_completed` Event。设备侧收到 Tuya 业务响应 `code=0`，并在涂鸦开发者平台 Device Log 中确认对应事件及参数存在。本阶段验收通过。

## 测试环境

- 模块：Fibocom L610-CN-62-36
- 固件：`16000.1208.00.86.02.02`
- AT 串口：`COM21 / 115200`（仅代表本次测试电脑）
- Tuya 数据中心：中国数据中心
- Broker：`m1.tuyacn.com:8883`
- 传输链路：L610 UART → MIPCALL → 4G → MIPOPEN TLS → MQTT 3.1.1 → TuyaLink

## TLS 易失配置恢复

模块重新接入后的初始状态为：

- `GTSSLVER: 0`
- `GTSSLMODE: 0`
- `GTSSLFILE: TRUSTFILE,0`

使用 `l610_tls_restore.py` 按 2026-08-07 已验收流程恢复：

- `AT+GTSSLVER=4`：TLS 1.2
- `AT+GTSSLMODE=1`：验证服务器证书
- `AT+GTSSLFILE="TRUSTFILE",1390`：在 `>` 提示符后发送 1390 字节完整 PEM
- 证书来源：`certs/tuya_go_daddy_root_g2.cer`
- 证书 SHA-256：`45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda`

恢复后复查：

- `GTSSLVER: 4`
- `GTSSLMODE: 1`
- `GTSSLFILE: TRUSTFILE,1`
- `AT+MIPOPEN=1,,"m1.tuyacn.com",8883,2`
- 最终 URC：`+MIPOPEN: 1,1`
- 空 TLS socket 保持 5 秒，无异常 URC，随后正常关闭

TLS 恢复日志：`logs/l610_tls_restore_20260808_014517.log`

### 为什么重新接入后配置消失

Fibocom SSL 手册把 `GTSSLFILE`、`GTSSLMODE` 和 `GTSSLVER` 的 `Persistent` 属性均标为 `No`，并对证书额外明确说明模块掉电后全部证书都会丢失。本次模块重新接入后的实际 `0 / 0 / 0` 状态与该说明一致。因此结论是：

- A：SSL 版本和校验模式属于易失配置，掉电/复位后回到默认值；
- B：证书文件不会跨模块掉电保留；
- 昨日初始化脚本确实只做了运行期设置，但手册没有提供可用于这些命令的持久化保存步骤，因此不能归因于“漏执行保存命令”。

`AT+GTSSLFILE?` 返回的第二个值是已加载证书数量 `file_num`，不是可寻址 slot。上传命令也没有 index 参数。昨日完整 PEM 被追加后计数为 2；本次掉电后列表为空，同一完整 PEM 成为当前唯一条目，计数为 1。

## Event 上报证据

- Event：`training_completed`
- `session_id`：`test_20260808_014544`
- `msgId`：`l610evt692729ce1a09448bab31f1f38`
- Event 时间戳：`1786124745440`
- MQTT CONNECT：`20 02 00 00`
- SUBACK：`90 03 00 01 01`
- PUBLISH Packet Identifier：`2`
- Event JSON UTF-8：`465` 字节
- MQTT PUBLISH：`521` 字节
- MIPSEND 实际发送：`521` 字节
- PUBACK：`40 02 00 02`
- Response Topic：`tylink/{DeviceID}/thing/event/trigger_response`
- Tuya response：`{"code":0,"msgId":"l610evt692729ce1a09448bab31f1f38","time":1786124751899,"version":"1.0"}`
- Socket：正常关闭

Event 真机日志：`logs/l610_tuya_training_event_20260808_014544.log`

## Device Log 人工核对

已在涂鸦开发者平台的当前真实设备 Device Log 中找到本次记录：

- 页面时间：`2026-08-08 01:45:45.440 (GMT+8)`
- 设备事件：设备事件上报
- `eventCode`：`training_completed`
- `session_id`：`test_20260808_014544`
- `duration_sec`：`623`
- `total_reps`：`57`
- `avg_confidence`：`9670`
- `max_elbow_angle`：`1284`
- `max_shoulder_angle`：`1148`
- 平台处理结果：`code=0`、`status=success`

Device Log 参数与串口发送日志逐字段一致。

## 安全说明

本文档未记录 DeviceSecret、账号密码、Cookie、Token 或 Tuya Cloud Access Secret。
