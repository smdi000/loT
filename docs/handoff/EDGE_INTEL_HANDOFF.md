# Edge / Intel Handoff

## 目标链路

```text
STM32 / Sensors → Intel Edge AI → USB/UART → Fibocom L610
                                            ↓ 4G
                                   TuyaLink → Business Cloud
```

Intel 板不通过 Windows 网络上云；L610 自己建立 `MIPCALL` 蜂窝数据、TLS socket 和 MQTT 连接。

## 两类代码

- 根目录 Windows PoC：真机验收过的 protocol golden reference；优先逐字段对拍，不重新猜 AT/Tuya 鉴权。
- `edge/qmzg_edge/`：业务接口、配置、训练聚合、串口/TLS 初始化边界；Phase 5-A 尚未连接 Intel 真机。

## 上层稳定入口

```python
client.initialize()
client.connect()
client.report_training_summary(summary)
client.close()
```

训练程序不得感知 `AT+MIPCALL`、`GTSSLFILE`、`MIPOPEN`、`MIPSEND`、MQTT HEX 或 HMAC 细节。

## 下一轮 Intel 工作

1. Ubuntu/Python/udev 权限与 USB 枚举。
2. 配置 `L610_PORT`，或遍历 `/dev/ttyUSB*`/`ttyACM*` 并以真实 `AT → OK` 识别 AT 口。
3. 复用 golden reference 的 SIM/LTE/MIPCALL 状态机。
4. 每次进程/模块启动检查 TLS；L610 掉电后 `GTSSLVER`、`GTSSLMODE`、`TRUSTFILE` 会丢失。
5. 使用已验收完整 PEM，恢复 `GTSSLVER=4`、`GTSSLMODE=1`、TRUSTFILE，再连接 `m1.tuyacn.com:8883`。
6. 移植手工 MQTT 3.1.1 与 Tuya Auth，先过 CONNACK/property 正例。
7. Session 期间本地累计，结束后仅发一次 `TrainingSummary`。
8. 验证断电启动恢复。

不要选“第一个 ttyUSB”；Fibocom VID/PID/描述只能提高候选优先级，最终判据必须是 AT `OK`。

