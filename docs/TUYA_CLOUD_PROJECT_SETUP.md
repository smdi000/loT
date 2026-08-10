# Tuya Cloud Project 与 Message Service 配置记录

更新时间：2026-08-08（GMT+8）

## 范围

本文记录“擎梦智骨云端训练平台”云项目、真实外骨骼设备关联和 Message Service 测试环境的实际配置。本文不包含 DeviceSecret、Access Secret、Cookie 或 Token。

## Cloud Project

| 项目 | 实际值 |
|---|---|
| 项目名称 | 擎梦智骨云端训练平台 |
| Project ID | `p17861257420227fdk4j` |
| Development Method | 自定义开发（Custom Development） |
| 服务行业 | 养老/医疗/健康 |
| 数据中心 | 中国数据中心（China Data Center） |
| 创建时间 | 2026-08-08 02:02:22 |

项目与 TuyaLink 产品、测试设备均位于中国数据中心。不得把 `m1.tuyacn.com` 的解析 IP 写死。

## 设备关联

- 产品：外骨骼
- Product ID：`0fc7obn925auckvo`
- 设备名称：外骨骼8b61
- Device ID：`269a934046f4318631hp6h`
- 设备类型：真实设备
- 关联方式：通过云项目 Asset 和 Bind Code 关联
- Asset：外骨骼测试设备（Asset ID `249822441`）
- 云项目设备列表结果：设备存在，来源为“资产路径-外骨骼测试设备”，设备权限为“可控”

未创建虚拟设备，未重新注册、删除或重新激活现有设备。临时 Bind Code 不记录在本文中。

## Message Service

| 项目 | 实际状态 |
|---|---|
| 服务 | 已开启 |
| 类型 | 消息队列（Pulsar） |
| 加密 | AES-GCM |
| 生效时间 | 2026-08-08 02:05:26 |
| 环境 | 测试环境 |

### 测试环境规则

最终发布并启用的规则：

```text
BizCode In deviceEventMessage（设备上报事件）
```

2026-08-08 为诊断而临时加入过 `devicePropertyMessage`，并以真实 `action_confidence=9982` 消息确认 Test Channel 可收到 `devicePropertyMessage`。取证结束后已成功发布恢复为上面的仅事件规则；Test Device 未改动。

最初还配置了 `devId In 269a934046f4318631hp6h`。真实事件没有进入 Test Channel 后，为排除字段级过滤不匹配，该条件已移除。测试通道仍只包含下面这一台测试设备，因此没有扩大到账号下其他设备。

### Test Device 与 Test Channel

- Test Device：`269a934046f4318631hp6h (外骨骼-hp6h)`
- 测试环境规则：已发布、已启用
- Test Channel：已启用
- 页面连接状态：`connection established`
- 测试 Topic：`clientid/out/event-test`

### Subscription

测试环境页面显示两个默认创建的订阅：

| 订阅名称 | 模式 | 状态 | 用途 |
|---|---|---|---|
| `a9nt9ssvgrs3vuu5sjq8-sub-iot-web` | Failover | 良好 | 平台 Test Channel Web 消费者 |
| `a9nt9ssvgrs3vuu5sjq8-sub` | None | 离线 | 默认业务订阅，尚未接入消费者 |

本轮没有创建额外 Subscription。平台本页没有显示中国区 Pulsar Endpoint，因此本文不写入历史猜测值；后续接入消费者时必须以平台当前显示或涂鸦官方文档为准。

## 实际阻塞

设备事件在 Device Log 中成功，但 Message Service 没有生成对应的 `deviceEventMessage` 投递记录，因此 Test Channel 尚未收到 `training_completed`。

已排除：

- 数据中心不一致：项目、产品、设备均为中国数据中心。
- 设备未关联：云项目设备列表可以查询到真实 Device ID。
- Test Device 未加入：页面已显示该设备。
- 规则未发布/未启用：页面显示“测试环境规则生效中”。
- BizCode 选错：涂鸦官方 Message Types 将设备事件上报定义为 `deviceEventMessage`。
- Test Channel 未连接：页面显示 `connection established`。
- 字段级过滤错误：已移除 `devId` 条件后再次真机上报，结果不变。

为了取得服务端证据，已开启平台提供的 6 小时免费“服务端消息日志”试用；页面显示将在 2026-08-08 08:20:25 自动关闭。日志能看到同一真机连接产生的 `online` / `offline` 消息，并明确显示它们因 BizCode 规则被过滤；但同一时段的 `training_completed` 没有生成 `deviceEventMessage` 日志。

当前产品页仍显示“开发中”。涂鸦官方 TuyaLink Application Development 文档说明，绑定 TuyaLink 设备用于云开发前应确保产品开发完成并 ready for release。这是目前唯一有官方依据且尚未满足的上游条件。点击“发布产品”会改变产品状态，本轮未获明确授权，因此未执行。

参考：

- [Tuya Message Types](https://developer.tuya.com/en/docs/iot/message-type?id=Kavqerli65a1u)
- [Manage Message Service](https://developer.tuya.com/en/docs/iot/manage-messages?id=Ka49p7loog3ze)
- [Application Development (TuyaLink)](https://developer.tuya.com/en/docs/iot/application-dev?id=kbf53a58zz6t1)
- [查看云端监控日志](https://developer.tuya.com/cn/docs/iot/log_monitor?id=Kcxdydp2fpy56)

## 下一步门禁

在继续之前，需要项目负责人明确决定是否发布当前 TuyaLink 产品。获得授权后应先完成平台发布前检查，再发布产品，然后保持现有 Message Service 配置不变，重新发送一个全新的 `training_completed`，核对 Device Log、服务端消息日志和 Test Channel。
