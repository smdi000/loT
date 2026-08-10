# 擎梦智骨云端应用架构

> 文档状态：架构设计稿（2026-08-07）  
> 当前批次仅完成现状审计与设计，不代表涂鸦物模型、Cloud Project、Message Service、业务后端或 SaaS 已经创建。

## 1. 项目目标与边界

项目通过 Fibocom L610 蜂窝模组把外骨骼训练结果接入涂鸦 TuyaLink，并在后续阶段形成训练历史与训练报告。

本期采用 `Edge AI + Tuya IoT Cloud + Business Cloud + SaaS`：

- Intel/边缘业务程序负责高频 IMU 数据、动作识别和训练过程计算。
- L610 只负责 UART 到中国电信 4G 的安全上行通信。
- 涂鸦负责设备身份、TuyaLink、MQTT、物模型、设备管理、事件、Message Service、OpenAPI 和 SaaS MicroApp。
- 自有业务云负责用户、设备归属、训练会话、训练历史、报告和持久化数据库。
- 高频 IMU 数据不上传云端。每次训练结束只生成并上传一份 Training Summary。

当前不做 Android/iOS 原生 App、Smart App SDK、设备控制、高频 IMU 云上传、OTA、微服务拆分、Kubernetes 和 Redis。

## 2. 最终技术链路

```text
业务程序 / MCU
      ↓ UART
Fibocom L610
      ↓ MIPCALL
中国电信 4G
      ↓ MIPOPEN TLS
m1.tuyacn.com:8883
      ↓ MIPSEND（真实 MQTT 二进制）
手工 MQTT 3.1.1
      ↓
TuyaLink Thing Model
      ↓ training_completed Event
Tuya Message Service（Pulsar）
      ↓
Python Consumer / FastAPI
      ↓
PostgreSQL
      ↓ HTTPS API
Tuya SaaS MicroApp
```

Broker 必须继续使用域名 `m1.tuyacn.com`，不得写死一次 DNS 解析得到的 IP。

## 3. 组件职责

| 组件 | 负责 | 不负责 |
| --- | --- | --- |
| Intel/边缘业务程序 | IMU 采集、动作识别、计数、角度与置信度聚合、生成 `session_id` 和 Training Summary | 持续上传高频原始 IMU |
| Fibocom L610 | UART、LTE、MIPCALL、TLS socket、发送 MQTT 二进制 | 动作识别、业务数据库 |
| TuyaLink | 设备鉴权、MQTT、物模型校验、Property/Event 接收和 ACK | 用户训练历史的长期业务归属 |
| Tuya Message Service | 通过 Pulsar 将已筛选设备消息投递给业务消费者 | HTTP webhook |
| FastAPI/Consumer（未来） | 校验事件、按 `tuya_msg_id` / `external_session_id` 幂等入库、用户和设备 API、只读 Tuya OpenAPI | 向浏览器暴露 Tuya Secret |
| PostgreSQL（未来） | 用户、设备关联和训练会话持久化 | 高频 IMU 时序存储 |
| SaaS MicroApp（未来） | 登录、设备状态、训练历史和非医疗训练报告 | 直连 PostgreSQL 或持有 Tuya Access Secret |

## 4. 已实际验证的设备侧基线

以下为当前源工作区中已经真实验收的事实，后续不得重新探索或改写这条底层路线：

| 层级 | 已验证证据 |
| --- | --- |
| UART / 模块 | Fibocom L610-CN-62-36，固件 `16000.1208.00.86.02.02`，`AT → OK` |
| 蜂窝网络 | 中国电信，`CGATT=1`，`MIPCALL` 获得 IPv4，公网 Ping 成功 |
| TLS | `AT+MIPOPEN=1,,"m1.tuyacn.com",8883,2`，`+MIPOPEN: 1,1`，TLS 1.2 与服务器证书验证成功 |
| MQTT | 手工 MQTT 3.1.1 CONNECT，CONNACK `20 02 00 00` |
| 属性订阅 | SUBACK `90 03 00 01 01` |
| 属性发布 | QoS 1 PUBACK `40 02 00 02` |
| TuyaLink 业务层 | `action_confidence=9982`，响应 `code=0` |

关键实现关系：

- `tuya_device_test.py` 是 Tuya MQTT Authentication Reference Implementation。
- `l610_tuya_connect.py` 复用该参考实现生成 Client ID、Username、签名原文与 HMAC-SHA256 Password，并构造 MQTT CONNECT。
- `l610_tuya_publish.py` 复用 CONNECT/TLS 代码，使用 `AT+MIPSEND=<socket>,<len>` 后直接写真实二进制，解析 `+MIPRTCP`、SUBACK、PUBACK 与 Tuya JSON ACK。
- `.env` 是设备凭证的唯一来源。任何文档、日志摘要或后续前端均不得输出 DeviceSecret。
- 当前模块已经有可用 TRUSTFILE。历史上裸 Base64 证书导致 `GTSSLERR: -19`，完整 PEM 后 TLS 成功；不得无证据修改证书配置。

## 5. 物模型决策

物模型采用少量 Property + 一个核心 Event：

- 保留 `action_confidence` Property，作为已有通信基线。
- 新增只上报的 `device_status` Property，用于查询设备当前业务状态。
- 新增 `training_completed` Event，每次训练结束只触发一次，携带训练总结。
- 本期不创建 `last_training_duration`、`last_total_reps`、`last_avg_confidence` 等重复快照属性。训练摘要将由业务后端持久化并提供查询；只有未来证明 Tuya 设备状态页必须直接展示这些最新值时再增加。

Property 表示可查询、可缓存的连续状态；Event 表示一次性发生的通知。涂鸦官方也明确说明 Event 可结合消息订阅或规则引擎使用，符合训练完成这一业务语义。

## 6. 训练数据生命周期

1. 训练开始：边缘端生成全局唯一的 `session_id`，在 Intel 本地处理高频数据。
2. 训练过程中：只按必要频率更新 `device_status=training`；不上传原始 IMU。
3. 训练结束：边缘端冻结统计结果，生成一份紧凑 Training Summary。
4. 设备上报：通过 `thing/event/trigger` 发送一次 `training_completed`，并设置 `sys.ack=1`。
5. 涂鸦校验：设备等待 `thing/event/trigger_response`，以同一 `msgId` 且 `code=0` 作为设备侧业务成功标准。
6. 消息投递（未来）：Tuya Message Service 通过 Pulsar 投递给消费者。
7. 幂等入库（未来）：消费者同时以 Tuya `msgId` 和业务 `session_id` 做唯一性保护；重复投递不得产生重复训练记录。
8. SaaS 展示（未来）：MicroApp 只通过 HTTPS 调用 FastAPI，读取设备状态、训练历史和报告。

## 7. 身份、凭证与信任边界

| 凭证/身份 | 存放位置 | 规则 |
| --- | --- | --- |
| Tuya DeviceID / DeviceSecret | 设备侧私密 `.env`（PoC） | 不进入文档、前端、公开 Git 或普通日志 |
| Tuya Cloud Access ID / Secret | 未来后端环境变量 | 仅服务端使用，日志脱敏，不返回浏览器 |
| JWT Secret | 未来后端环境变量 | 不写镜像，不提交源码 |
| 用户令牌 | 浏览器与 FastAPI 之间 | HTTPS；后端鉴权后访问业务资源 |

设备身份与业务用户不是同一个概念。未来通过 `devices` 和 `user_devices` 建立 Tuya DeviceID 到用户的关联；事件到达时设备尚未绑定用户，应保留为 `unassigned`，不能丢弃。

## 8. 可靠性与可观测性原则

- 边缘端每次训练只发一个摘要事件，降低蜂窝流量与消息量。
- `msgId` 最长 32 字符且每次请求唯一；`session_id` 在业务层唯一。
- MQTT QoS 1 的 PUBACK 只证明 Broker 收到消息，Tuya `code=0` 才证明物模型业务处理成功。
- 未来 Pulsar 消费必须假设至少一次投递，数据库以唯一约束实现幂等。
- 日志保留时间戳、消息类型、脱敏 DeviceID、`msgId`、`session_id` 和错误码；不得记录设备或云端 Secret。
- 原始事件未来以 JSONB 保存，便于协议演进与问题审计。

## 9. 阶段门禁

| 阶段 | 状态 | 进入下一阶段的门禁 |
| --- | --- | --- |
| L610 Property PoC | 已实际通过 | 已满足 |
| Thing Model 设计 | 本文档已完成设计 | 人工在平台创建并核对 `training_completed` |
| Event 设备上报 | 尚未开始 | Device Log 出现事件且 response `code=0` |
| Cloud Project / Message Service | 尚未开始 | China Data Center、设备关联、Pulsar Test Channel 收到事件 |
| FastAPI / PostgreSQL | 尚未开始 | 真实消息 dry-run 解析通过后才允许入库 |
| SaaS MicroApp | 尚未开始 | API 闭环与真实训练记录可查询 |

本批次停在 Thing Model 人工配置门禁之前，不执行设备事件测试、后端开发或 SaaS 开发。

## 10. 官方依据

- [TuyaLink Function Definition](https://developer.tuya.com/en/docs/iot/Function-Definition?id=Kb4qgfeeshz58)：Property、Event、Action 及 TuyaLink 数据类型。
- [Properties, Actions, and Events](https://developer.tuya.com/en/docs/iot/device_model?id=Kbt4gcmizz8f4)：Event Topic、`sys.ack`、`eventCode`、`eventTime`、`outputParams` 与响应码。
- [Custom Function](https://developer.tuya.com/en/docs/iot/custom-functions?id=K937y38137c64)：自定义功能、Enum 与 String 等约束。

