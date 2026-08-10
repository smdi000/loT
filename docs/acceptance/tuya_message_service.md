# Tuya Message Service 测试环境验收记录

日期：2026-08-08（GMT+8）

## 结论

本轮完成了 Cloud Project、真实设备关联、Message Service、测试规则、Test Device、Test Channel 和默认 Subscription 的真实平台配置。L610 事件上报与 Device Log 再次通过，但 `training_completed` 尚未进入 Message Service Test Channel，因此本阶段**未验收通过**。

## 已通过项目

- Cloud Project：`擎梦智骨云端训练平台`
- Project ID：`p17861257420227fdk4j`
- Data Center：中国数据中心
- 真实设备关联：成功
- Message Service：Enabled
- 测试规则：`BizCode In deviceEventMessage`
- 测试规则：已发布、已启用
- Test Device：已添加
- Test Channel：已启用，`connection established`
- 测试环境 Web Subscription：存在且状态良好

## 最终真机事件证据

最终诊断事件：

| 字段 | 值 |
|---|---|
| eventCode | `training_completed` |
| session_id | `test_message_service_20260808_0222` |
| msgId | `l610evt64216c595cfe4f6c86057b779` |
| eventTime | `1786126846145` |
| duration_sec | `623` |
| total_reps | `57` |
| avg_confidence | `9670` |
| max_elbow_angle | `1284` |
| max_shoulder_angle | `1148` |

设备侧结果：

- MQTT CONNECT：成功
- SUBACK：`90 03 00 01 01`
- PUBACK：`40 02 00 02`
- Tuya Event Response：`code=0`
- Socket：正常关闭
- 串口日志：`logs/l610_tuya_training_event_20260808_022045.log`

## Device Log

涂鸦 Device Log 已找到 2026-08-08 02:20:46.145 的“设备事件上报”记录，包含：

- Device ID：`269a934046f4318631hp6h`
- Product ID：`0fc7obn925auckvo`
- Event code：`training_completed`
- Data ID：与本次 msgId 一致
- `session_id=test_message_service_20260808_0222`
- `duration_sec=623`
- `total_reps=57`
- `avg_confidence=9670`
- 其余 outputParams 与发送内容一致

因此 L610 → TuyaLink → Device Log 链路再次确认成功。

## Message Service Test Channel

实际结果：**未收到本次 `training_completed`**。

为排除配置问题，依次核对或调整了：

1. Cloud Project 中能查询到真实 Device ID。
2. Test Device 名单只包含当前外骨骼设备。
3. `deviceEventMessage` 规则已 Release 并 Enable。
4. Test Channel 已启用并显示 `connection established`。
5. 数据中心为 China。
6. 移除字段级 `devId` 条件，仅保留官方 BizCode 后再次上报，结果不变。
7. 启用 6 小时免费服务端消息日志后再次上报。

服务端消息日志能看到同一连接的 `online` 和 `offline` 消息。它们进入消息管线后因当前规则仅允许 `deviceEventMessage` 而被过滤，错误码为 `16011004`。这证明设备关联、消息服务入口和规则引擎正在工作。

但是，同一时段 Device Log 中成功的 `training_completed` 没有对应的 `deviceEventMessage` 服务端消息记录，也没有进入 Test Channel。故障点位于：

```text
TuyaLink Device Log 成功
    ↓
Thing Event → IoT Core deviceEventMessage 转换/投递（未发生）
    ↓
Message Service Test Channel（无消息）
```

## 当前最可能的上游门禁

当前 TuyaLink 产品页面仍显示“开发中”。涂鸦官方 TuyaLink 云开发文档要求产品开发完成并 ready for release 后再绑定到云项目。该条件尚未满足，且与“设备事件未转换为 Message Service 消息”的现象一致。

这仍是依据现有证据得到的定位，不把它写成未经验证的最终根因。产品发布属于有影响的产品状态变更，本轮未执行。

## 下一步

需要负责人明确授权是否发布当前 TuyaLink 产品。若允许：

1. 人工核对发布前检查项。
2. 发布产品。
3. 不改现有 L610、TLS、MQTT 或 Thing Model 实现。
4. 重新发送全新的 `training_completed`。
5. 以 Test Channel 出现 `deviceEventMessage` 且包含正确 Device ID、Product ID、event code、event time 和 outputParams 为最终通过标准。

本文不包含 DeviceSecret、Cloud Access Secret、Cookie 或 Token。

## 2026-08-08 非破坏性诊断：Property 路径与 Capability API

### 临时规则与 Property 正例

为区分消息规则/测试环境问题与 Thing Event 转换问题，测试环境规则曾**临时**同时包含：

```text
BizCode In deviceEventMessage, devicePropertyMessage
```

Test Device 始终保持为同一台真实设备 `269a934046f4318631hp6h`，未添加、删除或替换任何测试设备。随后未修改既有程序地运行 `l610_tuya_publish.py` 一次，结果如下：

| 项目 | 实际结果 |
|---|---|
| 本次 msgId | `l610531a97683a94411fa8b7bb15f0f0` |
| action_confidence | `9982` |
| MQTT CONNECT | 成功 |
| SUBACK | `90 03 00 01 01` |
| PUBACK | `40 02 00 02` |
| Tuya 业务响应 | `code=0` |
| 串口日志 | `logs/l610_tuya_publish_20260808_023518.log` |

Message Service Test Channel 实时收到并展示了解密后的 `devicePropertyMessage`。其核心字段为：

```text
devId: 269a934046f4318631hp6h
productId: 0fc7obn925auckvo
dataId: l610531a97683a94411fa8b7bb15f0f0
properties[0].code: action_confidence
properties[0].value: 9982
```

因此，Cloud Project 设备关联、Test Device、Test Channel、测试环境规则引擎以及 Property 消息投递路径均已由真实设备消息验证。完成取证后，规则已成功发布回原配置：

```text
BizCode In deviceEventMessage
```

### Original Capabilities 查询门槛

只读审计了当前 Cloud Project 的“服务 API”和 API Explorer：当前项目已授权 4 项服务（IoT Core连接服务、授权凭证管理、行业基础服务包、资源授权服务（IAM）），但**没有**“设备北向能力（Device Northbound Service）”授权项。IoT Core连接服务的 API Explorer 设备管理目录也不提供下列只读接口：

```text
GET /v1.0/iot-03/devices/{device_id}/capabilities-definition?tags=original
```

因此本次未能在当前项目的 API Explorer 执行 Original Capabilities 查询，也没有任何证据可将“当前 Explorer 中找不到该接口”解释为“`training_completed` capability 不存在”。没有执行任何控制类 API。

涂鸦官方文档说明，上述接口用于查询 `standard` 或 `original` capability；`methods` 中的 `event` 表示可通过 Pulsar 消息订阅访问。官方 TuyaLink 云开发文档同时把“产品开发完成并 ready for release”列为云开发绑定/北向能力流程的前置条件。

### 诊断分类

- **C 已排除**：`devicePropertyMessage` 已真实进入 Test Channel。
- **A/B/D 暂不能严格归类**：缺少 Original Capabilities 的实际响应，不能诚实断言 `training_completed` 是否存在，亦不能判断其是否带有 `event` method。
- 当前唯一明确的上游缺口是：产品仍处于“开发中”，且当前 Cloud Project 未出现设备北向能力授权。两者都不应通过猜测或未授权的 Product Release 解决。

参考：

- [Query Device Capability List](https://developer.tuya.com/en/docs/cloud/28bd2979ef?id=Kbjehd3ixr2v1)
- [Application Development (TuyaLink)](https://developer.tuya.com/en/docs/iot/application-dev?id=kbf53a58zz6t1)

## 2026-08-08 北向能力授权后最小重测

### 前置状态

设备北向能力（Device Northbound Service）已完成 0 元体验版订阅，并已授权到当前 Cloud Project。

Original Capabilities 只读查询已成功，当前真实设备的核心能力如下：

| capability | methods |
|---|---|
| `action_confidence` | `get,event` |
| `device_status` | `get,event` |
| `training_completed` | `event` |

因此，`training_completed` 已确认存在于 Cloud Development original capability 层，并且具备 `event` method。本轮继续禁止 Product Release，未修改 Thing Model、设备凭证、L610 TLS/MQTT 逻辑或设备注册状态。

### 第一阶段：原规则不变重测

Message Service Test Environment 保持原配置：

```text
Message Service: Enabled
Test Device: 269a934046f4318631hp6h (外骨骼-hp6h)
Test Channel: Enabled, connection established
Rule: BizCode In deviceEventMessage
```

随后在 Test Channel 页面保持打开的情况下，连续运行已验收脚本 `l610_tuya_training_event.py` 两次。TLS 配置未丢失，未运行恢复脚本，未修改设备侧代码。

| 项目 | 第一次 | 第二次 |
|---|---|---|
| session_id | `test_northbound_enabled_20260808_032835` | `test_northbound_enabled_20260808_032918` |
| msgId | `l610evtc43c7caff3d44717bfcfee4c9` | `l610evt856f7095d89c4dc19db2c1c79` |
| CONNACK | `20 02 00 00` | `20 02 00 00` |
| SUBACK | `90 03 00 01 01` | `90 03 00 01 01` |
| PUBACK | `40 02 00 02` | `40 02 00 02` |
| Tuya response | `code=0` | `code=0` |
| 串口日志 | `logs/l610_tuya_training_event_20260808_032835.log` | `logs/l610_tuya_training_event_20260808_032918.log` |

第二次响应 JSON：

```json
{"code":0,"msgId":"l610evt856f7095d89c4dc19db2c1c79","time":1786130965652,"version":"1.0"}
```

### Device Log 复核

产品“在线调试 → 实时日志”页面选择真实设备 `269a934046f4318631hp6h` 后，手动刷新可见两次事件记录。

最新一次 Device Log 记录：

| 字段 | 值 |
|---|---|
| 时间 | `2026-08-08 03:29:19` |
| 日志类型 | 设备事件上报 |
| eventCode | `training_completed` |
| session_id | `test_northbound_enabled_20260808_032918` |
| msgId | `l610evt856f7095d89c4dc19db2c1c79` |
| duration_sec | `623` |
| total_reps | `57` |
| avg_confidence | `9670` |
| max_elbow_angle | `1284` |
| max_shoulder_angle | `1148` |
| result.code | `0` |
| result.status | `success` |

结论：北向能力授权后，设备侧 Event → TuyaLink → Device Log 仍然真实成功。

### Message Service Test Channel 结果

在 Test Channel 显示 `connection established` 且原规则 `BizCode In deviceEventMessage` 生效的状态下，页面未出现本次：

```text
test_northbound_enabled_20260808_032918
l610evt856f7095d89c4dc19db2c1c79
training_completed
```

因此，北向能力授权后，`training_completed` 仍未进入 Message Service Test Channel。未观察到任何对应本次事件的 `bizCode=deviceEventMessage` 消息。

### 第二阶段：BizCode 过滤诊断

保存当前规则语义后，进入“修改消息规则”抽屉进行只读/可撤销诊断。页面显示当前规则为：

```text
BizCode In deviceEventMessage
```

尝试删除唯一 BizCode 条件后，页面出现“添加消息过滤规则”，但“发布规则”按钮不可用，无法发布一个“不设置 BizCode / All BizCodes / 默认全部消息”的空过滤规则。因此当前 Tuya Test Environment UI 不允许在仅限定 Test Device 的同时取消 BizCode 层过滤。

该未发布的临时编辑未生效；刷新页面后确认当前规则仍显示为：

```text
deviceEventMessage (设备上报事件)
```

本轮未创建新规则，未发布无 BizCode 规则，未修改 Test Device，未改设备侧代码。

### 当前最小故障层级

当前证据链如下：

```text
L610 training_completed MQTT 上报
  → Tuya Event response code=0
  → Device Log status=success
  → Original Capability: training_completed.methods contains event
  → Message Service Test Channel: no deviceEventMessage
```

同时，既有正例已经证明：

```text
action_confidence Property
  → devicePropertyMessage
  → Message Service Test Channel 成功
```

因此 Product Release 目前不再是首要结论；更精确的当前故障层级是：

```text
Tuya Cloud 的 TuyaLink Event → Message Service deviceEventMessage 转换/投递层
或当前平台对 TuyaLink Event 进入 Test Channel 的规则/服务限制
```

由于平台 UI 不允许无 BizCode 过滤重测，本轮在第二阶段停止。现有证据已经足够形成一个面向涂鸦技术支持的最小复现工单；工单应附带本节中的 Project ID、Product ID、Device ID、session_id、Device Log success、Original Capability 响应、Property Message 正例和当前 Messaging Rule。不得附带 DeviceSecret、Cloud Access Secret、Cookie 或 Token。
