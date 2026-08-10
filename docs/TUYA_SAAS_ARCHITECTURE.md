# 擎梦智骨 Tuya SaaS 架构

## 目标

比赛阶段以 Tuya MicroApp 作为产品界面，业务数据继续由已验收的 FastAPI 与 PostgreSQL 提供。前端不持有 Tuya、数据库或设备 Secret。

## 数据上行

```text
Intel / Edge AI
  -> UART
Fibocom L610
  -> LTE / TLS / MQTT / TuyaLink
Tuya Device Cloud
  -> China TEST Pulsar
Tuya Consumer (Alibaba Cloud ECS)
  -> raw message + normalized training summary
PostgreSQL
```

## SaaS 查询链路

```text
Tuya SaaS / MicroApp
  -> /custom-api/...
Tuya Hybrid Runtime gateway
  -> CUSTOM_API_URL
FastAPI (127.0.0.1:8000 on ECS)
  -> SQLAlchemy
PostgreSQL (Docker internal network only)
```

本地调试时，`micro.config.js` 的 `debuggerConfig.customApiUrl` 将 `/custom-api` 转发到当前 ECS。React 业务代码只使用相对路径 `/custom-api/...`，生产 bundle 不包含 ECS IP。

## 身份与授权

- 用户使用业务后端的 JWT 登录，Token 仅保存在当前标签页的 `sessionStorage`。
- 一个真实设备当前只允许一个业务 owner。
- 设备归属迁移不是公网 API；由 ECS 内部管理员执行 `python -m app.cli transfer-device`。
- MicroApp 不读取 DeviceSecret、Tuya Access Secret、PostgreSQL 密码或 SSH Key。

## 页面与数据源

- `/login`：业务用户登录。
- `/dashboard`：绑定设备和训练会话聚合；平均置信度来自最近的 `training_session.avg_confidence`。
- `/devices`：真实设备绑定状态，Device ID 脱敏。
- `/training`：当前用户的训练历史。
- `/training/:id`：运动训练数据总结，不提供医疗诊断或治疗建议。

## 部署边界

- 当前 MicroApp 已发布到 Tuya Spatial AI Application Management。
- 自定义后端 MicroApp 按 Tuya 官方流程需要 Hybrid Deployment，`/custom-api` 由 Hybrid Runtime 转发。
- Hybrid Runtime 的 `APP_KEY`、`SECRET_KEY` 只允许保存在运行时 `.env`，权限应限制为 600。
- `sdf-fgw` 不得占用宿主机已有的 80 端口；后续应由 Nginx 按域名反向代理到内部高端口。
- 当前尚无合法域名，不能用公网 IP、自签证书或 hosts hack 冒充生产域名。

## 不在本阶段范围内

- Product Release、PROD Pulsar、RDS、Redis 业务缓存、移动 App、实时动作页面、医疗诊断。

