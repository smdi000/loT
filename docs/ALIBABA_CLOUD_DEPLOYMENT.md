# Alibaba Cloud ECS 部署准备（未执行）

本文件只记录后续生产部署方案；本轮没有访问、购买或修改任何 Alibaba Cloud 资源。

## 目标拓扑

```text
Internet
  └─ HTTPS :443
      └─ Nginx
          └─ FastAPI API + Tuya Pulsar Consumer
              └─ PostgreSQL（仅 Docker 内部网络）
```

推荐 ECS：Ubuntu LTS、Docker Engine、Docker Compose Plugin、Nginx 与有效 TLS 证书。后端使用 `backend/docker-compose.yml` 作为本地基础，生产环境另行准备受控的生产 `.env`、Nginx 配置和备份方案。

## 安全组与端口

- TCP `22`：仅允许运维固定公网 IP；使用 SSH key，禁止密码登录。
- TCP `80`：用于 HTTP 到 HTTPS 重定向及证书签发。
- TCP `443`：HTTPS API。
- **不要**对公网开放 PostgreSQL `5432`；`postgres` 容器不应配置 `ports`。

## 生产环境变量

在 ECS 上以受限权限的 `.env` 或密钥管理服务保存：

- `DATABASE_URL`
- `TUYA_ACCESS_ID`
- `TUYA_ACCESS_SECRET`
- `TUYA_PULSAR_URL`
- `TUYA_PULSAR_TOPIC`
- `TUYA_PULSAR_SUBSCRIPTION`

不得写入镜像、源码、Markdown、日志或 Git。生产数据库口令必须与本地 `qmzg_local_dev` 示例不同。

## 上线顺序

1. 创建 ECS、最小化安全组和受限 SSH 用户。
2. 安装 Docker Engine 与 Docker Compose Plugin。
3. 将不含 `.env` 的源码部署到服务器；在服务器上创建权限为 `600` 的生产 `.env`。
4. 配置 PostgreSQL 持久卷与定期备份，验证恢复流程。
5. `docker compose up -d --build`，执行 `alembic upgrade head`，检查 `/health`。
6. 配置 Nginx 到 API 容器，申请/安装 HTTPS 证书，确认只公开 `80/443`。
7. 使用 Tuya Test Environment 先发送一条 `action_confidence=9731`，确认 `tuya_messages` 出现一条 `devicePropertyMessage`。
8. 切换到生产 Message Service 前，再次确认 Topic、Subscription、规则与设备关联。

## 运行与可观测性

- API 与 Consumer 使用独立容器，均连接同一个 PostgreSQL。
- Consumer 启动后不打印 Access Secret、动态 token 或完整敏感消息。
- 先监控容器健康、数据库容量、Consumer 重连与重复消息率。
- 数据库备份与日志保留期应在上线前确定；训练数据不应被当作医疗诊断数据处理。
