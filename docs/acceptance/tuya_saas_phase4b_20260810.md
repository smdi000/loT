# Tuya SaaS Phase 4-B 验收记录（2026-08-10）

## 1. 本地工程

- Node.js：v24.19.0
- npm：11.17.0
- `@tuya-sat/create-micro-app`：0.0.51（使用 `latest` 初始化）
- `@tuya-sat/micro-script`：3.2.11
- 工程：`saas/qmzg-training`
- 名称：擎梦智骨训练平台
- 类型：React + TypeScript Tuya MicroApp，桌面端

页面：

- `/login`
- `/dashboard`
- `/devices`
- `/training`
- `/training/:id`

## 2. 设备归属迁移

真实 UI 验收最初被正常权限约束阻塞：真实设备仍属于 Phase 4-A owner，而旧 owner 的密码/JWT 未持久化。

没有重置密码、修改 `password_hash`、手写 SQL 更新归属或新增公网 Admin API。新增了：

- 正式 service 模块：`app.services.device_ownership.transfer_device()`
- 内部 CLI：`python -m app.cli transfer-device --device-id <exact-id> --to-user-id <exact-id> --yes`

CLI 使用 ORM 与数据库事务，锁定唯一 `user_devices` 关系，验证 device/target user，更新设备训练会话的 owner 快照，并输出脱敏的 `device_ownership_transfer` 结构化审计日志。

后端完整测试：25 passed，1 个既有 Starlette/httpx deprecation warning。覆盖 owner A 到 B、缺少 device/user、同 owner 幂等、无重复关系和迁移后的 API 权限隔离。

ECS 内部执行迁移成功。新 UI acceptance 用户通过正式 register/login API 创建，真实设备迁移后通过正式 JWT 访问成功。只读验收查询确认：旧 owner 关系数为 0、新 owner 关系数为 1，`acceptance_cloud_training_001` 的 owner 为新用户。

## 3. 真实 UI 验收

数据源为 Alibaba Cloud ECS 的真实 FastAPI/PostgreSQL，不是 mock。

真实会话：`acceptance_cloud_training_001`

- Dashboard：1 台已绑定设备、1 次训练、57 次动作、最近训练平均置信度 96.70%。
- Devices：真实设备显示为已绑定，Device ID 脱敏。
- Training History：真实会话按时间倒序出现。
- Report：623 秒、57 次、96.70%、最大肘角 128.5°、最大肩角 93.4°。
- 动作统计：curl=20、raise=15、lateral=12、boxing=10。
- `fault_count=0`，数据来源为 Tuya Property。
- 报告明确仅为运动训练数据总结，不构成医疗诊断、康复疗效判断或治疗建议。

视觉验收：

- 1920×1080 Dashboard：`docs/acceptance/screenshots/saas_phase4b/dashboard_real_1920x1080.jpg`
- 1366×768 Report：`docs/acceptance/screenshots/saas_phase4b/report_real_1366x768.jpg`
- 无关键字段截断或横向溢出；中文、单位、空状态和脱敏显示正常。

## 4. 前端门禁

- Jest：12 passed（5 suites）
- TypeScript：通过
- ESLint：通过
- `npm run build`：通过
- Bundle 约 1.08 MiB；仅有 Tuya 官方模板依赖的 webpack size warning，不阻塞发布。

安全扫描结果：

- DeviceSecret：未进入 `src` 或 `dist`
- Tuya Access Secret：未进入 `src` 或 `dist`
- JWT Secret：未进入 `src` 或 `dist`
- SSH private key / Developer Secret：未进入 `src` 或 `dist`
- ECS IP：只存在于本地 `micro.config.js` 的 `debuggerConfig`，不在 React 业务源码和生产 bundle 中
- 生产请求路径统一为 `/custom-api/...`

## 5. sdf-cli 发布

- `@tuya-sat/sdf-cli`：0.0.12，安装在 Windows 当前用户目录。
- Developer Secret 只保存在当前用户的 `.sdf-config`，没有写入仓库、Markdown、截图或终端日志。
- `manifest.json` 的模板值 `entries.type=MENU` 与 CLI 枚举不兼容，按 CLI 要求改为 `Menu`。
- 项目未使用动态多语言，模板的 `sdf.feat:i18n=DYNAMIC` 会使平台要求不存在的 `_locales/ui/zh.json`；关闭该未使用标记后发布成功。
- `sdf verify`：通过。
- `sdf publish`：成功。

平台回读：

- MicroApp：擎梦智骨训练平台
- 数据中心：中国数据中心
- 版本：0.0.1
- 创建时间：2026-08-10 23:08:51
- 发布/更新时间：2026-08-10 23:09:01
- 标签：`competition-demo`
- 标签绑定：China Data Center -> 0.0.1

## 6. Spatial AI Solution 与部署门禁

当前平台 `Solution Setting` 无已有 Solution。创建页没有 Custom 模板：

- “空间智能”仅提供“智能生活 App 网页版”。
- 选择后必须绑定 OEM App。
- 当前账号没有可绑定 OEM App，因此“创建方案”保持禁用。

本期明确不开发移动/OEM App，也不创建无关模板，所以没有越权创建 OEM App 或提交 Solution。MicroApp 因此尚未能加入 Solution。

Tuya 2026 官方文档说明：

- Fully Deployed on Tuya Server 可使用 `tuyasaas` 二级域名。
- 自定义后端 MicroApp 的 `/custom-api` 需要 Hybrid Deployment runtime 和 `CUSTOM_API_URL`。
- Hybrid Deployment 使用自定义域名；当前项目没有合法域名。

所以当前部署阻塞顺序为：

1. 需要明确授权并准备可绑定的 OEM App/平台允许的自定义 Solution 创建方式。
2. Solution 建立后，需要 Hybrid Deployment。
3. Hybrid Deployment 需要合法域名；不得用 IP、随机免费域名、自签证书或 hosts hack 替代。

当前没有最终 Tuya SaaS URL，也未部署 `sdf-fgw`/`sdf-redis`。

## 7. ECS 健康状态

未部署 Hybrid Runtime，现有 Phase 4-A 不受影响：

- available memory：约 1.3 GiB
- swap：0 使用
- disk：30 GiB，约 20 GiB 可用
- FastAPI：61.58 MiB，healthy
- Tuya Consumer：45.92 MiB，运行中
- PostgreSQL：28.32 MiB，healthy
- `GET /health`：`status=ok, database=ok`

## 8. 当前结论

已完成：真实 UI、测试/构建、安全扫描、MicroApp 发布、版本确认、`competition-demo` 标签。

未完成：Spatial AI Solution integration、Fully Deployed/Hybrid Runtime、最终 SaaS URL。阻塞来自平台要求 OEM App，随后仍存在 Hybrid 自定义域名门禁。
