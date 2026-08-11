# Stage 09 Prompt — Full Power Cycle Recovery

## GOAL

验证 Intel 与 L610 完整掉电后的无人预配置恢复，并上报 `acceptance_intel_powercycle_001` 到 ECS 与 Public Competition Web。这是最重要的最终硬门禁。

## KNOWN GOOD BASELINE

Stage 00–08 全部通过。TLS状态/证书掉电丢失是已知事实；正式 `initialize()` 必须自动完成 port discovery、AT、SIM、LTE、MIPCALL、TLS restore、MQTT。Windows不得参与，人工不得先运行 `l610_tls_restore.py`。

## ALLOWED CHANGES

现场人员可在 Agent 明确单步请求并确认后执行 Intel/L610 power off/on。Agent可修改 `edge/` boot-recovery/tests与 `docs/acceptance/phase5b_stage09*`。

## FORBIDDEN CHANGES

Agent不得声称/执行物理断电；禁止 Windows 辅助、人工预配 TLS、reboot 命令代替完整掉电、改云端/backend/Public Web/Nginx/SaaS/golden。

## COMMANDS / INSPECTION

先保存干净状态/时间。Agent停止所有 Edge 进程，明确请求现场人员“同时完全断电 Intel 与 L610，等待确认，再重新上电”。收到确认后重新 SSH，记录 USB/tty 变化；只启动正式 Edge 初始化。验证 TLS initial 缺失与自动 restore 证据，连接 MQTT 并从 Intel 上报新 `acceptance_intel_powercycle_001`，再执行 Stage08 云核对，直到 Public Competition Web 出现该 session。朋友电脑只负责 SSH、观察和浏览器展示，不得绕过 Intel 控制 L610。

## SUCCESS CRITERIA

无 Windows/人工 restore；端口可重新发现；SIM/LTE/MIPCALL 恢复；GTSSL 自动 restore；CONNACK 0；新 session 在 ECS/API/Public Competition Web 可见；无 Secret 日志。

## STOP CONDITIONS

现场未确认物理操作、SSH/USB未恢复、任何初始化需手工AT补救、快速重启循环、云链不完整。不得宣称通过。

## EVIDENCE TO SAVE

现场确认时间、掉电前后boot/USB/tty、TLS before/after、初始化时间线、ACK、云记录、代码/tests/Git。

## FINAL REPORT FORMAT

模板 + `physical operator confirmation | Windows absent | discovery | TLS auto-restore | MQTT | session | ECS | Public Web | PASS/STOP`。报告后停止。
