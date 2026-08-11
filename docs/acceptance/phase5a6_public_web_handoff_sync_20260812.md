# Phase 5-A.6 Public Web Baseline & Field Agent Handoff Sync

日期：2026-08-12

## Public web baseline

- Alibaba ECS Public Competition Web 已部署 Visual Polish standalone React。
- `/` 与 SPA deep links 由 Nginx 托管；`/custom-api/*` 同源代理 FastAPI；`/health` 保留后端健康检查。
- Dedicated competition demo account 通过正式 auth flow 创建并拥有真实演示设备；credentials 由团队负责人线下保管。
- `acceptance_cloud_training_001` 已在公网 Dashboard、Devices、Training History、Report 与 Presentation Mode 真实验收。
- Tuya MicroApp 0.0.1 与 `competition-demo` label 是独立平台集成资产；Spatial AI Solution 仍受 OEM App gate 阻塞，不是比赛硬门禁。

## Handoff synchronization

- `FINAL_SYSTEM_ARCHITECTURE.md` 增加 ECS Nginx + Public React Web presentation 层。
- Master Agent Prompt 的 known-good baseline 更新为 Tuya → Pulsar → ECS → PostgreSQL → FastAPI → Public Web，并继续将现场 Agent 限定为 Intel/L610。
- Stage 08 增加 Public Web 新 session 验收和“现场用户本人登录”边界。
- Stage 09 将完整掉电最终结果延伸至 Public Competition Web。
- Stage 00–07 已审计，没有与 Public Web 冲突的描述，因此保持不变。
- Field Checklist、START_HERE、API Contract、Project Inventory、Acceptance Index、Edge status 与根 README 已同步。
- 新增短入口 `FIELD_AGENT_LAUNCH_PROMPT.md`。

## Source scope

Phase 4-C tracked assets 包括 standalone frontend compatibility、Nginx template、可回滚 static deploy script 和公网 acceptance 文档。未修改 L610 golden scripts、Edge hardware implementation、Backend business logic、database schema、Tuya Cloud 或 MicroApp 已发布版本。

## Verification

- Edge：25 passed（纯单元测试；pytest cache 权限 warning 不影响结果）。
- Backend：25 passed，1 个既有 Starlette/TestClient deprecation warning。
- SaaS：15 passed；typecheck、lint、`build:web` 全部成功；仅保留 Tuya 模板既有 bundle-size warning。
- Secret Scan：扫描 tracked/待提交文件与最终 dist，共检查 5 个真实敏感值，exact hit 0；`.env`、private key、JWT、Bearer token、competition account identifier、bundle public IP 均为 0 hit。
- `git diff --check`：通过。
- Commit 与 GitHub main push：在最终 Git 门禁后记录到 Git 历史；本文档不写凭证或 token。
