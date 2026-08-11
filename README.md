# 擎梦智骨

**Edge AI + Cellular IoT + Cloud SaaS**  
Upper-limb intelligent training exoskeleton

擎梦智骨在 Intel 边缘端完成高频传感与动作推理，通过 Fibocom L610 的独立 4G 链路把一次训练的低频摘要上报至 TuyaLink，再由阿里云业务后端持久化并呈现在 Public Competition Web。Tuya MicroApp 作为独立平台集成资产保留。高频 IMU/推理数据不会逐帧上传云端。

## Architecture

```text
STM32 / Sensors → Intel Edge AI → L610 4G → TuyaLink
                                              ↓ Pulsar
Public React Web ← Nginx / FastAPI ← PostgreSQL ← Consumer
```

- `edge/`：面向下一轮 Intel Linux 集成的业务接口与纯单元测试。
- 根目录 `l610_*.py`：Windows 真机验收过的协议 golden reference，禁止随意重写。
- `backend/`：FastAPI、PostgreSQL、Pulsar Consumer、Alembic。
- `saas/qmzg-training/`：Tuya React TypeScript MicroApp；支持无凭证 Mock Mode。
- `deploy/`：阿里云 ECS/Nginx 部署与验收辅助脚本。
- `docs/`：架构、交接、平台配置与真实验收证据。

## Quick Start

UI 队友无需云端或硬件即可启动完整演示界面：

```powershell
cd saas/qmzg-training
npm install
npm run dev
```

Edge 骨架测试（不连接真实串口）：

```powershell
cd edge
python -m pip install -r requirements.txt
python -m pytest -q
```

后端本地运行见 [`backend/README.md`](backend/README.md)。真实凭证只允许写入被 Git 忽略的 `.env`，不得写进源码、文档或交接包。

## Demo

Mock Mode 使用明确的 `DEMO-DEVICE-001` / `demo_session_001`，展示 623 秒、57 次、96.70%、128.5°/93.4°及动作分布。Real Mode 仍统一通过 `/custom-api/...` 访问 FastAPI。

比赛部署：Alibaba Cloud ECS Public Competition Web；凭证由团队负责人线下保管，不进入仓库。

## Documentation

- [最终系统架构](docs/architecture/FINAL_SYSTEM_ARCHITECTURE.md)
- [UI 队友交接](docs/handoff/TEAMMATE_UI_HANDOFF.md)
- [Intel/Edge 交接](docs/handoff/EDGE_INTEL_HANDOFF.md)
- [Intel Field Agent — START HERE](docs/field_agent/START_HERE.md)
- [稳定 API Contract](docs/handoff/API_CONTRACT.md)
- [Intel 迁移检查表](docs/handoff/INTEL_MIGRATION_CHECKLIST.md)
- [真实验收索引](docs/acceptance/README.md)

此仓库不会包含 `.env`、私钥、日志、虚拟环境、`node_modules`、构建产物或历史私密 handoff 包。
