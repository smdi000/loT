# Stage 10 Prompt — systemd Service

## GOAL

仅在 Stage 00–09 手工真实验收全部通过后，为正式 Edge 程序创建并验证 `qmzg-edge.service`。

## KNOWN GOOD BASELINE

生产程序运行在 Intel，不在朋友电脑。Service必须使用受保护 env file、journal、`Restart=on-failure` 与合理 `RestartSec`，不能无限快速重启。systemd不是修复未通过硬件链路的工具。

## ALLOWED CHANGES

可在 `edge/systemd/` 创建 template/unit与安装说明、Edge启动入口/tests、`docs/acceptance/phase5b_stage10*`。安装/enable需要 sudo，必须先停下请求现场用户批准并由其确认。

## FORBIDDEN CHANGES

Stage09未过时禁止继续；禁止把Secret写unit、使用root无理由运行、`Restart=always`快速循环、改SSH/network/firewall/cloud/backend/SaaS、未经确认enable/reboot。

## COMMANDS / INSPECTION

先只读 `systemctl --version`、现有冲突unit、运行用户/路径。设计 unit：明确 `User`、`WorkingDirectory`、`EnvironmentFile` mode600、venv `ExecStart`、`Restart=on-failure`、`RestartSec`（建议≥10s）、启动限速。运行 unit静态验证/Edge tests。需要复制到 `/etc/systemd/system`、daemon-reload、enable/start时先请求现场用户执行。用 `systemctl status`、`journalctl -u qmzg-edge` 验证，日志不得含Secret。

## SUCCESS CRITERIA

手工链路先通过；unit结构安全；现场授权安装；service active；故障重启有限速；journal脱敏；reboot验收需另行用户授权，不自动执行。

## STOP CONDITIONS

需要sudo但未批准、路径/用户/permission不明、restart loop、env泄漏、已有冲突service、任何硬件Stage回退。

## EVIDENCE TO SAVE

unit（无Secret）、权限、静态检查、status/journal摘要、restart策略、现场sudo确认、tests/Git。

## FINAL REPORT FORMAT

模板 + `prerequisites | unit path/user | env permission | restart policy | enable authorization | status | journal | PASS/STOP`。报告后停止。
