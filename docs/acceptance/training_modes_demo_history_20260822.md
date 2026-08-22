# Training Modes + Competition Demo History Acceptance

日期：2026-08-22

## 范围与边界

本阶段为 Training Session 增加正式训练类型，并为比赛展示账号增加可明确识别 provenance 的演示历史。未修改 L610 golden scripts、MQTT/TLS、Tuya Thing Model、9 个 Training Summary Properties、Intel 硬件实现、设备 ownership 或 Nginx 路由架构。

## Schema 与 Migration

- Alembic revision：`20260822_03`
- 新字段：`training_sessions.training_type VARCHAR(32) NULL`
- canonical values：`passive_assist | resistance | active_assist | null`
- 历史记录无法确定类型时保持 `NULL`，不做猜测性回填。
- downgrade 通过 Alembic 删除新增列；SQLite migration 测试已验证 upgrade/downgrade。

## Normalization 与 API

现有 `training_summary_json` 可选读取 `training_type`，兼容 alias `training_mode`。合法值映射到业务字段；未知值记录 warning、降级为 `null`，不会丢弃训练 Session。没有新增或修改 Tuya Property。

History/list、detail 与 report response 均返回 `training_type`。History 按 `started_at DESC` 排序；Dashboard 使用 session `started_at`（缺失时才回退 `created_at`）计算 latest/recent。

## Competition Demo Seed

内部脚本：`backend/scripts/seed_competition_history.py`

- 默认 dry-run，显式 `--apply` 才写入。
- 通过精确 Device ID 参数解析唯一 owner，不硬编码账号、用户 ID 或凭证。
- 使用 `external_session_id` 幂等；重复执行结果为 create 0 / skip 14。
- 新增记录全部为 `source_type=mock`，不伪装成 Tuya/Intel 真机数据。

生产 dry-run：create 14 / skip 0 / owner uniquely resolved。生产执行后：

| 项目 | 结果 |
|---|---|
| 总 Training Sessions | 15 |
| Demo Sessions | 14 |
| 时间范围 | 2026-08-05 至 2026-08-21（Asia/Hong_Kong 业务时间） |
| 主动助力训练 | 5 |
| 抗阻训练 | 5 |
| 被动助力训练 | 4 |

演示数据覆盖 7–18 分钟、30–90 次动作、合理置信度与角度区间；`summary_json` 保留 actions、fault_count 与 canonical training_type。

## 真实记录保护

`acceptance_cloud_training_001` 在迁移与 Seed 前后保持：

- duration 623 秒
- total reps 57
- avg confidence 9670
- elbow 1285 / shoulder 934
- `source_type=tuya_property`
- owner 非空且未改变
- `training_type=NULL`

没有修改该记录的业务数据或 provenance。

## Frontend

- Dashboard Latest Training 与 Recent Sessions 显示训练类型 badge。
- History 新增训练类型列，15 条记录通过两页访问。
- Detail/Report 显示训练类型；`source_type=mock` 显示低调“演示数据”标识，真实记录不显示。
- 三种类型沿用现有青色/紫色/绿色工业科技视觉；历史 NULL 显示 `--`。
- Presentation Mode 复用同一真实 API 数据，不使用 Mock Mode。

生产同源验收：`/custom-api` 返回 15 条、14 条 mock、三类分布 5/5/4、排序正确；detail/report 返回一致 training_type、actions 与 provenance。浏览器控制插件在本轮出现本地 trusted-path 初始化异常，因此没有伪造自动化截图；公网静态页面、同源 API、组件渲染测试与响应式现有布局均已通过，其余由比赛账号已登录浏览器做人工视觉 spot-check。

## Production Deployment

- 数据库备份：迁移前 PostgreSQL custom-format dump 已在 ECS 受控备份目录生成并验证非空。
- Alembic：生产已升级到 `20260822_03`。
- Frontend release：`/var/www/qmzg-training/releases/20260822T044636Z`
- Previous release：`/var/www/qmzg-training/releases/20260822T044018Z`
- Nginx `-t`、root、`/health`、`/custom-api` 均通过；现有 rollback 机制保留。
- API/PostgreSQL healthy，Consumer 继续连接 China TEST Pulsar，Nginx active。
- 资源：available memory 约 1.2 GiB；API 约 62 MiB、Consumer 约 46 MiB、PostgreSQL 约 34 MiB。

## Tests 与 Build

- Edge：25 passed
- Backend：28 passed（1 个既有依赖 deprecation warning）
- SaaS：18 passed
- TypeScript typecheck：PASS
- ESLint：PASS
- Production build：PASS（仅保留 Tuya template bundle-size warning）

## Secret Scan / Git

最终 tracked files 与 bundle 检查真实环境 secret exact values、private key、JWT token、已知误输入密码、tracked `.env` 与硬编码公网 IP，结果均为 0 hit。未记录比赛账号、密码、JWT、Cookie、Tuya Secret 或数据库密码。

目标 commit：`feat: add training modes and competition history`
