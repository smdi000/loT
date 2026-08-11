# START HERE — Intel Field Agent

你在朋友的 **Developer Workstation** 上运行 Claude Code / Codex，通过 SSH 操作现场 **Intel Linux Board**。正式 Edge 程序运行在 Intel 板；不要求在板上安装 AI Coding Agent。朋友电脑只负责 Git、开发、SSH、部署和观察日志，不能绕过 Intel 电脑直接控制 L610。

```text
Developer Workstation --SSH--> Intel Linux Board --USB/UART--> Fibocom L610
                                                        ↓ 4G
Tuya → Pulsar → Alibaba ECS → PostgreSQL → FastAPI → SaaS
```

## 你的任务

只负责 Intel / L610 Edge Integration。云端、后端与 SaaS 已真实验收，不重新设计。一次只过一个门禁：审计 → 当前 Stage → 保存证据 → 报告 → 停止。

Public Competition Web 已部署在 Alibaba ECS；现场 Edge Agent 不负责维护 Web frontend 或 Nginx。

## 目录边界

- 可改：`edge/`、`docs/acceptance/phase5b*`、必要的 Edge requirements/config/systemd 文件。
- 只读：`backend/`、`saas/`、`deploy/`、`docs/architecture/`。
- 不可改：根目录 `l610_*.py` golden references、Tuya Thing Model/Cloud Project/Message Service、ECS、PostgreSQL schema、SaaS UI。

## 第一次现场命令

先确认 SSH alias；不要索要或保存密码：

```sshconfig
Host qmzg-intel
    HostName <Intel LAN IP>
    User <actual user>
    IdentityFile <actual private key path>
```

```bash
ssh qmzg-intel "uname -a && whoami"
```

如果需要 sudo、重登 group、reboot、USB 拔插、L610/Intel 断电或输入 Secret，停下来给现场队友一条明确指令，不能声称已完成物理操作。

## 每一关

使用 `docs/field_agent/prompts/` 对应 Prompt。失败时禁止跳关；保存命令、原始输出、时间戳、代码 diff、测试和 Git 状态。Secret 不进入输出。

必须停止的情况：SSH/权限不明、需要安装系统包或升级系统、SIM/LTE 未通过、AT 命令与 golden reference 冲突、TLS/MQTT 证据不完整、任何云端/生产修改、物理操作尚未由现场人员确认。

## 启动流程

1. 在朋友电脑 clone **private repository**。
2. 从 `main` 创建并 checkout `edge/intel-integration`。
3. 连接 Intel LAN，配置并验证 `qmzg-intel`。
4. 打开 Claude Code / Codex。
5. 完整提供 [CLAUDE_CODE_MASTER_PROMPT.md](CLAUDE_CODE_MASTER_PROMPT.md)。
6. Agent 首先只执行 [00_environment_audit.md](prompts/00_environment_audit.md)。
7. Agent 输出阶段报告后立即停止，不一上来跑完整 Phase 5-B。
