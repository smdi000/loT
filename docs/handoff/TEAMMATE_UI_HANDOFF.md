# UI Teammate Handoff

目标：未参与当前开发的 UI 队友在 15 分钟内启动并修改比赛界面，不需要 ECS、Tuya、L610、PostgreSQL 或任何 Secret。

## 15 分钟启动

```powershell
cd D:\code\qgzg85\saas\qmzg-training
npm install
npm run dev
```

`npm run dev` 明确设置 `QMZG_DATA_MODE=mock`。打开终端输出的本地地址，用任意非空演示账号/密码完成登录交互。Mock 数据均有明显标识：`DEMO-DEVICE-001`、`demo_session_001`、`source_type=mock`。

Real Mode 仅供已具备正式后端环境者使用：

```powershell
npm run dev:real
```

Real Mode 保持 `/custom-api/...`，不得在组件中硬编码 ECS IP。

## 可以修改

- 页面布局、CSS、主题、图表、文案、响应式、轻量动效
- Dashboard、Devices、Training History/Report、Presentation Mode
- `src/data/mockProvider.ts` 中的脱敏演示内容（必须保留明显 mock 标识）

## 不可修改

- 后端 schema、鉴权协议、Tuya Thing Model、Pulsar Consumer、L610 协议
- deploy 基础设施、Secret 管理、`/custom-api` 边界
- 不得提交真实 token、密码、DeviceID/DeviceSecret、Access Secret

## 数据层规则

页面只调用 `src/api/services.ts`。Mock/Real 切换集中在 `src/data/mode.ts` 与 provider；禁止在每个 React component 中写 `if (mock)`。

## 提交前

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

- [ ] Mock Mode 可登录并显示 Dashboard/Device/History/Report
- [ ] Real Mode 请求路径仍为 `/custom-api`
- [ ] 无 `undefined/null`、横向溢出和伪造在线状态
- [ ] 无真实凭证、JWT、密码或公网 IP 散落在业务组件
- [ ] 不执行 `sdf publish`（0.0.2 由用户后续决定）

