# Tuya Thing Model 人工配置指南

> 操作对象：当前已经接入并完成 `action_confidence` 上报验收的 TuyaLink 产品  
> 文档核对日期：2026-08-07  
> 本文只指导人工配置；Codex 没有登录或修改涂鸦开发者平台，也不声称配置已经完成。

## 1. 本次只创建什么

保留已有 Property：

- `action_confidence`

本次建议新增：

- Property：`device_status`
- Event：`training_completed`

本次不新增：

- Action（当前不做设备控制）
- 高频 IMU 字段
- `last_training_duration`、`last_total_reps`、`last_avg_confidence` 等重复快照属性
- 其他为了“凑 DP”而建立的字段

## 2. 为什么字段类型可用

涂鸦官方 TuyaLink Function Definition 将物模型分为 Property、Event、Action，并支持在 Event 中定义一个或多个 `outputParams`。TuyaLink `typeSpec` 支持 `value`、`string`、`date`、`bool`、`enum`、`fault/bitmap`、`array`、`struct` 等类型。

本设计只使用基础类型 `enum`、`string`、`date` 和 `value`，兼容性最保守：

- 时间使用 `date`，避免把 13 位毫秒时间戳塞进普通 Value。
- 百分比和角度使用整数原值 + Scale，延续已验证的 `9982 → 99.82%` 约定。
- `summary_json` 使用 String，不依赖嵌套 Struct 的页面能力；按普通自定义 String 的官方保守限制控制在 255 UTF-8 字节以内。
- 当前示例的紧凑 `summary_json` 是 92 UTF-8 字节，满足 255 字节限制。

官方文档没有在公开页面给出所有控制台版本的 Identifier 最大字符数。因此不要凭空填写一个“官方最大值”；本设计的标识符均只含小写字母、数字或下划线，并以字母开头。若当前页面给出更严格的即时校验，以页面为准并停止操作，不要擅自改 code 后继续。

## 3. 最终字段设计

### 3.1 已有 Property：动作置信度

| 页面字段 | 值 |
| --- | --- |
| 名称 / DP Name | 动作置信度 |
| Identifier | `action_confidence` |
| Function Type | Property |
| Data Transfer Type / Access Mode | Report Only / Read Only（只上报） |
| Data Type | Value |
| Min | `0` |
| Max | `10000` |
| Step / Pitch | `1` |
| Scale | `2` |
| Unit | `%` |
| 语义 | 原值 `9982` 显示为 `99.82%` |

该字段已经真实上报成功。先核对，不要删除、重建或改变其标识符和数值规格。如果页面现值与上表不同但后台仍正确显示 99.82%，先截图并停止，不要为了对齐文档修改已验收配置。

### 3.2 新增 Property：设备业务状态

| 页面字段 | 值 |
| --- | --- |
| 名称 / DP Name | 设备状态 |
| Identifier | `device_status` |
| Function Type | Property |
| Data Transfer Type / Access Mode | Report Only / Read Only（只上报） |
| Data Type | Enum |
| Enum values | `idle`, `training`, `fault` |
| Default（若页面要求） | `idle` |
| 说明 | 当前只表达业务运行状态，不提供云端控制 |

Enum 值必须逐个输入并确认。涂鸦官方当前文档说明 Enum 值只能使用小写字母、数字和下划线，每个值不超过 15 个字符，最多 10 个值；以上三个值满足约束。

### 3.3 核心 Event：训练完成

| 页面字段 | 值 |
| --- | --- |
| Event Name | 训练完成 |
| Identifier / Event Code | `training_completed` |
| Function Type | Event |
| Description | 一次训练结束后上报一份边缘侧聚合的 Training Summary；不包含高频 IMU 原始数据。 |

Event outputParams 最终设计：

| 参数名称 | Identifier | 类型 | 页面规格 | 单位 | 设备上报约定 |
| --- | --- | --- | --- | --- | --- |
| 训练会话 ID | `session_id` | String | Max Length `64` bytes | 无 | 全局唯一；示例 `test_20260807_001` |
| 开始时间 | `started_at` | Date | Date | 时间戳 | 13 位 Unix 毫秒 |
| 结束时间 | `ended_at` | Date | Date | 时间戳 | 13 位 Unix 毫秒，且不早于 `started_at` |
| 训练时长 | `duration_sec` | Value | Min `0`, Max `86400`, Step `1`, Scale `0` | `s` | 整秒；示例 `623` |
| 总动作数 | `total_reps` | Value | Min `0`, Max `100000`, Step `1`, Scale `0` | `次` 或留空 | 整数；示例 `57` |
| 平均置信度 | `avg_confidence` | Value | Min `0`, Max `10000`, Step `1`, Scale `2` | `%` | `9670` 表示 `96.70%` |
| 最大肘关节角度 | `max_elbow_angle` | Value | Min `0`, Max `1800`, Step `1`, Scale `1` | `°` 或留空 | `1284` 表示 `128.4°` |
| 最大肩关节角度 | `max_shoulder_angle` | Value | Min `0`, Max `1800`, Step `1`, Scale `1` | `°` 或留空 | `1148` 表示 `114.8°` |
| 扩展训练摘要 | `summary_json` | String | Max Length `255` bytes | 无 | UTF-8 紧凑 JSON；不得超过 255 字节 |

范围说明：

- `duration_sec=86400` 是本项目单次训练的业务上限（24 小时），不是涂鸦平台的全局上限。
- `total_reps=100000` 是防止异常值的业务上限。
- 两个角度按当前外骨骼单关节 `0.0°–180.0°` 约束。如果标定规格确实需要超过 180°，应先评审并同步修改物模型与设备侧校验，不能直接发送越界值。
- 如果页面单位下拉没有 `次` 或 `°`，单位留空，并把倍率约定写入 Description；不要选择含义不符的单位。
- `summary_json` 的 255 限制按 UTF-8 字节计算，不是字符数。设备侧后续必须在发送前计算字节长度并拒绝超长消息。

推荐 `summary_json` 内容（最终发送时紧凑序列化）：

```json
{"actions":{"biceps_curl":20,"arm_raise":15,"lateral_raise":12,"boxing":10},"fault_count":0}
```

## 4. 为什么不把所有数据做成 Property

- Property 会表示当前可查询状态；`device_status` 属于此类。
- `training_completed` 是一次性业务事实，应该用 Event。
- 训练历史由未来 PostgreSQL 持久化，而不是用一组 `last_*` Property 模拟历史数据库。
- Event 可进入 Tuya Message Service / 规则引擎；这正是后续业务消费入口。
- 少量 Property + 核心 Event 避免重复字段和版本维护成本。

## 5. 网页操作步骤

控制台中英文标签可能略有差异。以下路径依据涂鸦官方 TuyaLink Function Definition 文档；若当前页面没有 Event 或 Date 类型，不要改用别的字段蒙混通过，请截图页面并停止。

### 5.1 进入现有产品

1. 打开 [Tuya Developer Platform](https://platform.tuya.com/) 并登录当前测试产品所属账号。
2. 在左侧进入 **Product（产品） → Development（产品开发）**。
3. 找到当前已经绑定 L610 测试设备的 TuyaLink 产品。
4. 点击 **Continue to Develop / Develop（继续开发 / 开发）**。
5. 进入 **Function Definition（功能定义 / 物模型）** 页签。
6. 确认页面显示的是正确 PID。不要新建产品，不要重新注册设备。

### 5.2 先核对已有 `action_confidence`

1. 在 **Custom Functions（自定义功能）** 中找到 `action_confidence`。
2. 只读核对名称、Identifier、Value 范围、Step、Scale 和 Unit。
3. 确认它仍能表达 `9982 → 99.82%`。
4. 不删除、不重建、不改变 Identifier。若规格存在差异，先截图并停止。

### 5.3 创建 `device_status` Property

1. 在 **Custom Functions** 区域点击 **Add（添加）**。
2. Function Type 选择 **Property（属性）**。
3. Name 填 `设备状态`。
4. Identifier 填 `device_status`。
5. Data Transfer Type / Access Mode 选择 **Report Only / Read Only（只上报）**。
6. Data Type 选择 **Enum**。
7. 逐个加入并确认 `idle`、`training`、`fault`。
8. 若要求默认值，选择 `idle`。
9. Description 写明“设备仅主动上报，当前不支持云端控制”。
10. 点击 **Save / Confirm（保存 / 确认）**。

### 5.4 创建 `training_completed` Event

1. 再次点击 **Custom Functions → Add（添加）**。
2. Function Type 选择 **Event（事件）**。
3. Event Name 填 `训练完成`。
4. Identifier / Event Code 填 `training_completed`。
5. Description 填本文件 3.3 节中的说明。
6. 在 **Output Parameters（输出参数）** 中按 3.3 表格顺序逐个添加 9 个参数。
7. 对 `started_at`、`ended_at` 明确选择 **Date**，不要选择普通 Value。
8. 对五个 Value 参数逐项核对 Min、Max、Step、Scale 与 Unit。
9. 对 `summary_json` 设置 String Max Length `255` bytes。
10. 保存 Event。

### 5.5 保存后的只读核对

1. 回到 Function Definition 列表，确认只新增了 `device_status` 和 `training_completed`。
2. 打开 `training_completed` 详情，逐项核对 9 个 outputParams 的 code 与类型。
3. 特别核对：`avg_confidence.scale=2`，两个角度 `scale=1`，两个时间为 `date`。
4. 若页面提供 Thing Model JSON / 模型预览，检查 Event 的 `outputParams[].typeSpec` 与本表一致。
5. 保存截图：产品 PID（可脱敏）、Property 列表、Event 详情和 outputParams。
6. 若控制台要求 **发布 / 应用配置 / 下一步** 才能使模型对已注册设备生效，阅读页面影响提示后人工完成；不要删除或重新注册现有设备。
7. 到设备详情/在线调试页面只确认模型已经显示，不发送测试事件。本批次到此停止。

## 6. 后续 Event 协议预览（本批次不运行）

平台配置完成并经人工确认后，下一阶段才新增独立的 `l610_tuya_training_event.py`。设备消息将使用：

```text
Publish:   tylink/{deviceId}/thing/event/trigger
Subscribe: tylink/{deviceId}/thing/event/trigger_response
```

预期语义如下；真实 `msgId` 每次唯一且不超过 32 字符，`time` / `eventTime` 使用同一轮生成的 13 位 Unix 毫秒时间戳：

```json
{
  "msgId": "不超过32字符的唯一值",
  "time": 1786081025438,
  "sys": {"ack": 1},
  "data": {
    "eventCode": "training_completed",
    "eventTime": 1786081025438,
    "outputParams": {
      "session_id": "test_20260807_001",
      "started_at": 1786080402438,
      "ended_at": 1786081025438,
      "duration_sec": 623,
      "total_reps": 57,
      "avg_confidence": 9670,
      "max_elbow_angle": 1284,
      "max_shoulder_angle": 1148,
      "summary_json": "{\"actions\":{\"biceps_curl\":20,\"arm_raise\":15,\"lateral_raise\":12,\"boxing\":10},\"fault_count\":0}"
    }
  }
}
```

`sys.ack=1` 必须保留。涂鸦官方协议说明事件默认不返回响应，只有开启 ACK 后才会向 `thing/event/trigger_response` 返回同一 `msgId` 与状态码。下一阶段仍须以 MQTT PUBACK + Tuya response `code=0` 双重确认，不能只凭 PUBACK 判定业务成功。

## 7. 人工验收清单

- [ ] 进入的是当前已验收设备所属 TuyaLink 产品，而非新产品
- [ ] `action_confidence` 未删除、未重建、未改变 Identifier
- [ ] `device_status` 已创建为 Report Only Enum
- [ ] Enum 恰好为 `idle`、`training`、`fault`
- [ ] `training_completed` 已创建为 Event
- [ ] Event 有且仅有本期设计的 9 个 outputParams
- [ ] `started_at`、`ended_at` 为 Date
- [ ] `duration_sec`、`total_reps` 的 Scale 为 0
- [ ] `avg_confidence` 的范围为 0–10000、Scale 为 2
- [ ] 两个角度的范围为 0–1800、Scale 为 1
- [ ] `summary_json` 为 String，Max Length 为 255 bytes
- [ ] 页面未因标识符、类型或范围报错
- [ ] 配置已保存并在物模型预览中可见
- [ ] 已保留配置截图

所有项目打勾后，请把 `training_completed` Event 详情（可截图，隐藏敏感信息）反馈给开发人员，再进入设备事件 PoC。

## 8. 遇到页面差异时怎么处理

- Event 参数列表没有 Date：停止并截图，不要自行改成 Value 或 String。
- Identifier 被页面拒绝：记录页面原始错误，不要随机缩写 code。
- String 最大长度不能填 255：记录页面允许范围；样例只需 92 bytes，但修改最终规格前先评审。
- 现有产品状态不允许编辑：不要新建替代产品，不要重注册设备；记录产品状态与页面提示。
- 保存动作提示会影响已发布设备：先阅读影响范围并截图，确认不会破坏现有 `action_confidence` 后再人工决定。

## 9. 官方参考

- [Function Definition（TuyaLink 产品的 Property / Event / Action）](https://developer.tuya.com/en/docs/iot/Function-Definition?id=Kb4qgfeeshz58)
- [Properties, Actions, and Events（Event Topic、ACK、时间戳与响应码）](https://developer.tuya.com/en/docs/iot/device_model?id=Kbt4gcmizz8f4)
- [Custom Function（Enum 与 String 等约束）](https://developer.tuya.com/en/docs/iot/custom-functions?id=K937y38137c64)
- [Query Things Data Model（Event outputParams 与 typeSpec 结构）](https://developer.tuya.com/en/docs/cloud/bd68171262?id=Kcp4utbhzzfgo)

---

**请先在涂鸦开发者平台完成物模型配置，再继续设备事件测试。**
