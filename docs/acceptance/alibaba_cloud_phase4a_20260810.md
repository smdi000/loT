# Alibaba Cloud Phase 4-A 生产部署验收

验收时间：2026-08-10（Asia/Hong_Kong）。

本文仅记录脱敏后的部署与真机验收结果，不包含 SSH 私钥、Tuya Access Secret、DeviceSecret、JWT、用户密码或 PostgreSQL 密码。

## 1. 验收结论

以下生产链路已真实通过：

```text
Fibocom L610
  -> 中国电信 4G
  -> TuyaLink Property Report
  -> Tuya Message Service China TEST / Pulsar
  -> Alibaba ECS Python Consumer
  -> ECS PostgreSQL
  -> FastAPI
  -> 宿主机 Nginx
  -> Windows 公网 API 请求
```

真机训练摘要 `acceptance_cloud_training_001` 已经由 L610 发出，并能够从公网 history、detail、report 三个 API 读取。训练会话已自动关联真实设备的 cloud acceptance owner。

## 2. ECS 环境

- OS：Alibaba Cloud Linux 3（OpenAnolis Edition）
- Kernel：`5.10.134-19.7.1.al8.x86_64`
- 架构：x86_64
- 规格：2 vCPU、896 MiB RAM、1 GiB Swap、30 GiB 系统盘
- Docker Engine：`29.7.2`
- Docker Compose：`v5.4.0`
- Nginx：`1.24.0`
- PostgreSQL：`16.14`
- 部署目录：`/opt/qmzg/backend`

生产 `.env` 位于 ECS 的 `/opt/qmzg/backend/.env`，权限为 `600`。JWT secret 与 PostgreSQL password 在远端重新随机生成，未复用本地弱测试值。Tuya 仍使用中国数据中心 TEST channel，没有切换到 PROD。

Tuya Cloud Project 的中国数据中心 IP 白名单在获得明确授权后仅加入 ECS 公网 IP 与当时的 Windows 公网 IP，没有加入 `0.0.0.0/0`、大网段或未知 IP。授权操作没有产生费用。

## 3. 容器与网络边界

生产 Compose 包含三个容器，均配置 `restart: unless-stopped`：

- `postgres`：持久 Docker volume，healthy，不发布宿主机 `5432`。
- `api`：healthy，仅发布 `127.0.0.1:8000:8000`。
- `tuya-consumer`：连接 `pulsar+ssl://mqe.tuyacn.com:7285/` 的 TEST channel。

宿主机 Nginx 监听公网 `80` 并反向代理至 `127.0.0.1:8000`。验收时监听状态符合：

- `0.0.0.0:80`：Nginx
- `127.0.0.1:8000`：FastAPI Docker proxy
- 不存在宿主机 `5432` 监听
- 不存在公网 `0.0.0.0:8000` 监听

ECS 上原先已有的 BT-Panel 仍监听宿主机 `8888`；它不是本项目组件，本轮没有修改。Alibaba Cloud Security Group 未为本项目开放 `8888`，后续应继续保持该端口不对公网放行。

本轮没有域名，因此按计划只验收 HTTP；未强行签发证书或配置 HTTPS。

## 4. PostgreSQL 与 Migration

Alembic 使用生产 `DATABASE_URL` 执行升级，实际 revision：

```text
20260808_02
```

数据库已实际确认存在：

- `alembic_version`
- `users`
- `devices`
- `user_devices`
- `tuya_messages`
- `training_sessions`

部署过程中发现并修复了 `alembic.ini` 固定指向本地开发数据库的问题：生产 migration 现在优先读取运行环境的 `DATABASE_URL`。修复后本地完整测试仍为 `22 passed, 1 warning`。

## 5. Consumer 与公网健康检查

完成 Tuya 中国数据中心云授权 IP 白名单后，ECS Consumer 使用官方 Python SDK 成功连接 China TEST Pulsar。日志只显示脱敏 Access ID、Pulsar endpoint 与 TEST channel，没有输出 Access Secret。

真实消息日志确认：

```text
biz_code=devicePropertyMessage
created=True
processed=True
Pulsar message acknowledged
```

从 Windows 本机真实访问：

```http
GET http://47.250.160.90/health
```

返回：

```json
{"status":"ok","database":"ok"}
```

## 6. 真机串口与 TLS 前置检查

本轮重新枚举了 Windows 全部串口，没有假设旧 COM 号。以 `AT` 精确返回 `OK` 且 `ATI`/`AT+CGMM` 返回 Fibocom L610 标识为判据，实际识别结果：

- AT Port：COM21
- Baud：115200
- Module：Fibocom L610-CN-62-36
- Firmware：`16000.1208.00.86.02.02`
- SIM：READY
- LTE：`CEREG 0,1`
- CSQ：`18,99`

串口探测日志：`logs/l610_serial_probe_20260810_200238.log`。

模块重新接入后 SSL 运行态配置再次为空。已验收的 `l610_tls_restore.py` 按需恢复 `GTSSLVER=4`、`GTSSLMODE=1` 与完整 PEM TRUSTFILE，并真实获得 `+MIPOPEN: 1,1` 后正常关闭测试 socket。该步骤未发送 MQTT 数据。

TLS 恢复日志：`logs/l610_tls_restore_20260810_200410.log`。

## 7. Cloud acceptance 用户与设备绑定

通过公网 API 创建了新的 cloud acceptance 用户，密码与 JWT 仅存在于验收进程内，没有写入文件、日志或本文。随后使用真实 Tuya DeviceID 完成：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/devices/bind
```

数据库关系复核表明：训练会话的 `user_id` 与真实设备在 `user_devices` 中的 owner 完全一致。

## 8. `acceptance_cloud_training_001` 真机验收

设备端使用已验收的 `l610_tuya_training_summary.py`，仅在运行时覆盖自动探测到的串口和本次 session ID，没有修改原脚本、Tuya 鉴权、TLS、MQTT codec 或 Thing Model。

设备端结果：

- MQTT CONNACK：`20 02 00 00`
- SUBACK：`90 03 00 01 01`
- MQTT PUBLISH：812 bytes
- MIPSEND 实际 payload：812 bytes
- PUBACK：`40 02 00 02`
- Tuya Property response：`code=0`
- socket：正常关闭

真机日志：`logs/l610_tuya_training_summary_20260810_200752.log`。

ECS PostgreSQL 直查结果：

| 字段 | 实际值 |
| --- | --- |
| `external_session_id` | `acceptance_cloud_training_001` |
| `duration_sec` | 623 |
| `total_reps` | 57 |
| `avg_confidence` | 9670 |
| `max_elbow_angle` | 1285 |
| `max_shoulder_angle` | 934 |
| `source_type` | `tuya_property` |
| `user_id` | 非空，且等于设备 owner |
| 对应 `tuya_messages.biz_code` | `devicePropertyMessage` |
| `tuya_messages.processed` | `true` |

## 9. 公网业务 API 验收

验收程序通过公网 Nginx/FastAPI，使用只驻留内存的 JWT 完成：

- `GET /api/training-sessions`：找到 `acceptance_cloud_training_001`。
- `GET /api/training-sessions/{id}`：623 秒、57 次、置信度 9670、肘角 1285、肩角 934、`source_type=tuya_property`、`user_id` 非空。
- `GET /api/training-sessions/{id}/report`：623 秒、57 次、96.70%、肘 128.5°、肩 93.4°、四项动作统计、`fault_count=0`。

报告接口仍明确声明仅为训练表现统计，不提供医疗诊断或治疗建议。

本地生产验收编排工具：`deploy/run_cloud_acceptance.py`。该工具动态读取最新成功串口探测结果，密码和 JWT 均只驻留进程内。

## 10. 资源与稳定性

完整系统运行后的宿主机状态：

- RAM：896 MiB total，512 MiB used，384 MiB available
- Swap：1 GiB total，91 MiB used
- Disk：30 GiB total，8.4 GiB used，20 GiB available（31%）
- 最近两小时内核日志：未发现 OOM、oom-kill 或 killed process

容器瞬时资源：

| 容器 | 内存 | 限额占比 |
| --- | ---: | ---: |
| `tuya-consumer` | 50.49 MiB / 256 MiB | 19.72% |
| `api` | 75.80 MiB / 192 MiB | 39.48% |
| `postgres` | 27.78 MiB / 192 MiB | 14.47% |

当前 896 MiB ECS 可以支撑现有比赛 Demo 的最小三容器链路，且本次没有出现 OOM；但宿主机已经使用 Swap，内存余量有限。建议在加入 SaaS、长期日志、更多并发或监控组件前升级到至少 2 GiB RAM。比赛现场若追求更稳妥的演示余量，也建议提前升级到 2 GiB。

## 11. 停止点

本轮已在以下真实闭环完成后停止：

```text
L610 -> Tuya -> Pulsar TEST -> Alibaba ECS Consumer
     -> PostgreSQL -> Nginx/FastAPI public history/detail/report
```

本轮未继续 SaaS、RDS、Redis、Product Release、Event 工单或 PROD Pulsar。
