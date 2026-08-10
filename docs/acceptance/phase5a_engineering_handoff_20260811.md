# Phase 5-A Engineering Handoff Acceptance

日期：2026-08-11

## Repository structure

- `edge/`：Intel 接口骨架、训练数据模型、串口发现、TLS 状态恢复、稳定 Client facade。
- `backend/`：Phase 4-A 已验收业务后端，未改协议链路。
- `saas/qmzg-training/`：统一 Mock/Real 数据层。
- `deploy/`：ECS 部署资产。
- `docs/handoff/`、`docs/architecture/`、`docs/acceptance/`：队友入口和证据索引。
- 根 L610 PoC 保持 golden reference 原位。

## Secret scan

扫描覆盖真实 `.env`、嵌套环境文件、密钥扩展名、高风险变量名、token/cookie 形态和高熵候选。确认真实配置只位于 Git 忽略范围；公共 CA 可追踪。日志、旧私密 handoff、ZIP、虚拟环境、缓存、node_modules 和 dist 均忽略。

- 从三个私密环境来源识别并检查 4 个真实 Secret 值；staged 文件精确匹配为 0。
- staged private-key / literal Bearer token marker 为 0。
- 生产 bundle 扫描 16 个文件，真实 Secret 精确匹配为 0。
- 198 个 baseline 文件进入 staged gate，禁止路径命中为 0。

## UI Mock Mode

`npm run dev` 使用 `QMZG_DATA_MODE=mock`，从单一 `mockDataProvider` 提供 Dashboard、设备、历史与报告。fixture 使用 `DEMO-DEVICE-001`、`demo_session_001`；没有真实凭证或数据库标识。Real Mode 保持 `/custom-api`。

## Edge skeleton

- `TrainingSummary` 验证时间、范围、255-byte summary_json。
- Tuya adapter 仅在边界使用 `training_max_shldr_angle`。
- 串口发现支持 Windows/Linux 候选，但必须实际获得 `AT OK`。
- TLS bootstrap 每次启动检查并按需恢复 `GTSSLVER=4`、`GTSSLMODE=1`、完整 PEM TRUSTFILE。
- `TuyaEdgeClient` 对训练代码暴露 initialize/connect/report/close；实际 Linux link backend 留给下一轮真机移植。

## Documentation

已提供 UI/Edge handoff、稳定 API contract、角色边界、最终系统架构、Intel 迁移门禁和既有 acceptance 索引。

## Test and Git gates

结果：

- Edge：20 passed（无真实串口）。
- Backend：25 passed，1 条既有 TestClient 依赖弃用 warning。
- SaaS：15 passed；typecheck、lint、build 全部成功。官方模板 bundle-size warning 仍为非阻塞项。
- 本地 Git repository 已初始化，没有 remote；用户 Git identity 已配置，允许创建 `Phase 5A team handoff baseline`。
- Phase 5-A 未连接真实硬件、未部署新服务、未发布 MicroApp 0.0.2。
