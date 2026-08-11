# Intel Field Checklist

每项只有在“证据”存在时才能勾选；日志必须脱敏。

- [ ] Intel 开机 — `uname -a`、系统时间、资源快照
- [ ] Ethernet / SSH — `ssh qmzg-intel "whoami && hostname"`
- [ ] L610 USB 已由现场人员连接 — 现场确认时间
- [ ] `lsusb` — Fibocom VID/PID 与 kernel log
- [ ] AT port — tty、115200、原始 `AT → OK`
- [ ] SIM READY — `AT+CPIN?` 原始响应
- [ ] LTE — `ATI`、`CSQ`、`CEREG` 注册证据
- [ ] Data — `CGATT`、当前 APN、`MIPCALL` 有效 IPv4、可选最小 DNS/ping
- [ ] TLS — restore 前后 GTSSL 状态、完整 PEM hash、`+MIPOPEN: 1,1`、正常关闭
- [ ] MQTT — CONNECT HEX/长度、MIPSEND 长度、CONNACK `20 02 00 00`
- [ ] Property — 新 `action_confidence`、PUBACK、Tuya code=0、ECS `devicePropertyMessage`
- [ ] Training Summary — `acceptance_intel_training_001` 完整字段与 ACK
- [ ] Tuya ACK — 本次 Training Summary 的 PUBACK 与业务 `code=0`
- [ ] Pulsar — TEST channel 收到完整 `devicePropertyMessage`
- [ ] ECS Consumer — 消息被接收、规范化并处理
- [ ] PostgreSQL — `tuya_messages`、`training_sessions`、owner/source_type
- [ ] FastAPI — history/detail/report 可见且数值一致
- [ ] Public Web — 公网训练历史出现新 session
- [ ] Training Report — 公网报告字段、动作统计与单位正确
- [ ] Full Power Cycle — 现场断电确认；自动恢复；`acceptance_intel_powercycle_001`
- [ ] systemd — 手工链路全部通过后才 enable；状态、journal、重启间隔证据

Tuya MicroApp / Spatial AI / OEM App 属于独立平台集成状态，不是 Intel 比赛现场成功硬门禁。
