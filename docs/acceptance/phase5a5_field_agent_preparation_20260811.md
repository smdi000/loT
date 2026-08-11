# Phase 5-A.5 Intel Field Agent Preparation Acceptance

日期：2026-08-11。

本阶段只准备“朋友电脑上的 AI Coding Agent 通过 SSH 操作未来 Intel Linux Board”的自包含资料。未连接 Intel/L610，未执行真实硬件命令，未修改云端、Backend、SaaS、Deploy、Thing Model 或根目录 L610 golden scripts。

## 协作边界

- AI Coding Agent 运行在 Developer Workstation。
- 正式 Edge 程序运行在 Intel Linux Board。
- Intel Board 通过 USB/UART 控制 Fibocom L610；朋友电脑不得直接控制 L610。
- 远端 Agent 一次只执行一个硬件门禁，保存证据并停止报告；失败时不得越级。
- 物理插拔、上下电、重启、`sudo`、系统网络/SSH 变更和 Secret 输入必须交由现场人员确认。

## 已交付资产

- `docs/field_agent/START_HERE.md`：10 分钟入口、SSH 模型、目录权限和首个 Stage。
- `docs/field_agent/CLAUDE_CODE_MASTER_PROMPT.md`：不依赖历史对话的完整 Field Agent Prompt。
- `docs/field_agent/prompts/00_environment_audit.md` 至 `10_systemd.md`：11 个可独立复制的 Stage Prompt。
- `docs/field_agent/FIELD_CHECKLIST.md`：现场逐项证据检查表。
- `docs/field_agent/TROUBLESHOOTING_MATRIX.md`：USB 至 Business Session 的分层排错矩阵。
- `docs/field_agent/SECRET_PROVISIONING.md`：仅列变量名和安全 provision 方法。
- `docs/field_agent/GIT_WORKFLOW.md` 与 `REPORT_TEMPLATE.md`：单门禁提交和报告规范。
- `docs/field_agent/EDGE_IMPLEMENTATION_STATUS.md`：当前真实实现、partial、skeleton、golden reference 和硬件依赖。
- `edge/scripts/bootstrap_intel.sh`：默认只审计；显式 `--apply` 仅创建 Edge venv、安装 Edge requirements 并运行 Edge 单测。
- `edge/scripts/hardware_acceptance.py`：没有 `all`；`env`、`serial`、`at` 独立可用，后续硬件层在具体 Linux backend 尚未实现时 fail closed。
- `edge/tests/test_field_scripts.py`：覆盖 bootstrap 安全边界、环境输出脱敏、AT 探测和未实现阶段 fail-closed。

## Golden Reference 保护

以下根目录脚本保持未修改、未移动、未格式化：

- `l610_serial_probe.py`
- `l610_data_probe.py`
- `l610_tls_probe.py`
- `l610_tls_restore.py`
- `l610_tuya_connect.py`
- `l610_tuya_publish.py`
- `l610_tuya_training_event.py`
- `l610_tuya_training_summary.py`

它们只允许 READ / COMPARE / PORT LOGIC；Linux 正式实现只能进入 `edge/`。

## 自动化安全属性

- bootstrap 不包含 `sudo`、`reboot`、`systemctl`、网络、防火墙、Tuya 或 modem reset 操作。
- hardware runner 每个 subcommand 独立、有 timeout 和明确 exit code；默认不串行执行全部步骤。
- `network`、`tls`、`mqtt`、`property`、`summary` 在正式 Linux backend 未落地前返回 `NOT_READY`，不会误发 modem 命令。
- 默认 pytest 不依赖真实串口或硬件。

## 测试与回归

- Edge：`25 passed in 0.18s`。
- Backend：`25 passed, 1 warning in 5.67s`；warning 为既有 Starlette/TestClient 与 httpx 兼容性弃用提示。
- SaaS：`15 passed`，共 6 个 test suites。
- `bash -n edge/scripts/bootstrap_intel.sh`：通过。
- `hardware_acceptance.py` Python 语法编译：通过。
- Stage Prompt：11 个，必需章节缺失 0。

## Secret Scan 与 Git

- `.env`、私钥、运行时凭证、日志、虚拟环境、`node_modules`、`dist` 和历史私密 handoff 包不进入暂存区。
- 文档仅包含变量名、占位符、公开 endpoint/CA 信息和脱敏规范，不包含真实 Secret。
- 对 3 个已知私密环境文件提取 3 个真实 Secret 值并与完整 Git 暂存区精确比对：命中文件 0。
- 私钥 PEM marker：0；Bearer token marker：0；禁止暂存路径：0。
- `git diff --cached --check`：通过。
- 本地 baseline commit 使用消息：`Phase 5A.5 Intel field agent preparation`。

## 结论

Field Agent 包已经把项目历史、职责边界、分阶段门禁、证据要求和停止条件固化为可执行材料。朋友电脑拿到私有仓库后应先阅读 `docs/field_agent/START_HERE.md`，把 `CLAUDE_CODE_MASTER_PROMPT.md` 完整交给 Agent，并且第一轮只执行 `00_environment_audit`。
