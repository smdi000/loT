# SaaS Visual Polish 验收记录

## 范围

本轮仅调整 `saas/qmzg-training/` 前端展示与本地调试代理，没有修改 FastAPI、PostgreSQL、Tuya Thing Model、Pulsar Consumer、L610、认证架构、设备归属或云部署，也没有再次执行 `sdf publish`。已发布的 `0.0.1 / competition-demo` 保持不变。

## 现有结构审计与复用

- 保留现有 React Router 路由、`AuthContext`、JWT `sessionStorage`、`/custom-api` API Client 和 Ant Design 基础组件。
- 保留 `DashboardPage`、`DevicesPage`、`TrainingHistoryPage`、`TrainingReportPage` 页面边界，没有重写 MicroApp。
- 复用 `summarizeSessions()`、时间/置信度/设备 ID 格式化函数和已有真实 API。
- 当前工程没有图表库。本轮动作分布使用 CSS 条形图，关节角度使用轻量 SVG，未引入大体积依赖。

## 设计方向

- 继续使用深蓝工业科技风，主色为深蓝、低饱和青色、蓝色和少量紫色。
- 使用低透明工程网格、径向光晕和节点连线作为背景装饰；不使用图片、视频、WebGL 或粒子系统。
- 动画仅包括页面进入、1 px 卡片悬浮、动作条 reveal、慢速链路线条和登录页骨架呼吸，并支持 `prefers-reduced-motion`。
- 视觉重点从等权后台指标卡切换为“最近训练 + 设备云链路 + 动作分布 + 最近会话”。

## 页面调整

### Header

- 顶部导航收紧为 64 px。
- 左侧显示“擎梦智骨 / TRAINING INTELLIGENCE”。
- 中部保留总览、我的设备、训练记录，当前页使用青色下划线。
- 右侧保留当前登录用户与退出操作。
- 删除没有 API 依据的“云端在线 / healthy”状态表述。

### Dashboard

- 新增 `TRAINING INTELLIGENCE / 训练数据中心` Hero 和 EDGE AI、4G CELLULAR、CLOUD SaaS 能力标签。
- 主区域使用 12 列比例布局，最近训练约占 8 列，设备 / 云端链路约占 4 列。
- 最近训练使用真实 `training_session.avg_confidence` 静态环形指标，不读取 `action_confidence`，也没有轮询。
- 真实指标显示为 `10:23`、`57`、`96.70%`、`128.5°`、`93.4°`。
- 动作分布来自 `summary_json.actions`，显示二头弯举、抬臂、侧平举和拳击的真实次数及占比。
- `DEVICE PIPELINE` 以中性节点展示 Intel Edge AI → L610 · 4G → Tuya IoT Cloud → Alibaba Cloud，不伪造在线状态。
- 最近训练使用轻量行卡片，不使用 Dashboard 密集表格。
- 无训练数据时显示训练图标、说明文字及 `--`，不显示 `0.00%` 或伪造角度。

### Training History

- 保留分页、设备筛选和真实 API。
- 增加弱化后的 session ID，完整 ID 仅作为元素 title，便于比赛验收时确认真实记录。
- 无数据时使用训练主题空状态，不显示零值集合。

### Training Report

- 顶部重构为训练日期、脱敏设备、弱化 session ID 和平均置信度。
- 核心指标行突出动作总数、平均置信度、最大肘角和最大肩角。
- 动作统计使用真实 CSS 条形图。
- 新增 SVG `JOINT RANGE`，仅表示本次记录到的最大角度，不提供或伪造生物力学正常范围。
- 训练摘要显示训练时长、动作类型、`fault_count` 和数据来源。
- 固定显示：“训练数据分析仅用于运动训练信息展示，不构成医疗诊断或治疗建议。”

### Login

- 保留“让每一次训练都有数据回响”叙事。
- 保留肩 / 肘 / 腕三节点抽象线框，增加 7 秒慢速微光呼吸；减少动态偏好下自动关闭动画。

## Presentation Mode

- 入口：`/dashboard?presentation=1`。
- 仍位于受保护路由内部，不绕过登录和 JWT。
- 隐藏顶部导航与刷新按钮，保留退出演示入口。
- 放大最近训练与关键数字，并保持设备链路、动作分布、最近会话同屏。
- 1920×1080 浏览器布局测量：`scrollWidth=1920`、`scrollHeight=1080`，无横向溢出且整屏适配。

## 真实数据验收

通过本地 Tuya MicroApp `/custom-api` 代理连接 Alibaba Cloud ECS FastAPI，使用正式登录账户读取真实 PostgreSQL 数据。未使用 mock。

确认 `acceptance_cloud_training_001`：

- duration：623 秒（10 分 23 秒）
- total_reps：57
- avg_confidence：96.70%
- max_elbow_angle：128.5°
- max_shoulder_angle：93.4°
- actions：curl=20、raise=15、lateral=12、boxing=10
- fault_count：0

浏览器语义核对覆盖 Dashboard、Training History、Training Report 和 Presentation Mode。

## 响应式与视觉检查

- 1920×1080：Dashboard、Report、Presentation Mode 已检查；Presentation Mode 全部核心内容同屏。
- 1366×768：Dashboard 和 Report 已检查，关键指标、链路和图形可读。
- 1920 页面测量无横向溢出；普通页面垂直滚动用于查看下方内容。
- 1366 页面测量 `scrollWidth=1351 <= innerWidth=1366`，无横向溢出。
- 中文字体、数值单位、脱敏设备 ID、Loading/Error/Empty 状态正常。
- 视觉复核结论：页面已能直接识别“外骨骼训练 + Edge AI + 4G + Tuya + Alibaba Cloud”，不再是通用后台模板；背景装饰保持低透明度，没有过度霓虹或影响阅读。

## 截图

- `docs/acceptance/screenshots/saas_visual_polish/dashboard_1920x1080.jpg`
- `docs/acceptance/screenshots/saas_visual_polish/report_1920x1080.jpg`
- `docs/acceptance/screenshots/saas_visual_polish/presentation_1920x1080.jpg`
- `docs/acceptance/screenshots/saas_visual_polish/dashboard_1366x768.jpg`
- `docs/acceptance/screenshots/saas_visual_polish/report_1366x768.jpg`

## 自动门禁

- `npm test`：5 suites、13 tests passed。
- `npm run typecheck`：通过。
- `npm run lint`：通过。
- `npm run build`：通过。
- 构建保留 Tuya 官方模板 / Ant Design vendor bundle size warning；这是 warning，不阻塞本轮，不为消除它进行大规模重构。

## 安全扫描

- `src/` 和 `dist/` 未发现 Tuya Access Secret、Device Secret 实值、JWT Secret、PostgreSQL 密码、私钥、JWT 或 Developer Secret Key。
- `DevicesPage` 中仅存在说明性文案“DeviceSecret 不会进入浏览器”，不包含任何凭证值。
- React 业务源码和最终 `dist/` 未硬编码 ECS 公网 IP。
- ECS IP 仅存在于本机 `micro.config.js` 的 `debuggerConfig.customApiUrl`，用于本地 `/custom-api` 代理，未进入生产 bundle。
