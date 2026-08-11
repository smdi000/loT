# Edge Implementation Status

审计日期：2026-08-11。`Implemented` 表示纯逻辑已存在并有单元测试，不等于 Intel/L610 真机验收。

| Component | Status | Golden reference | Hardware required | Next action |
|---|---|---|---|---|
| `TrainingSummary` validation | Implemented / unit-tested | training summary publisher fields | No | 保持业务命名与范围 |
| Tuya Property field mapping | Implemented / unit-tested | `l610_tuya_training_summary.py` | No | 真机检查9字段是否同一消息 |
| Training local accumulator | Implemented / unit-testable | architecture contract | No | 与Intel inference输出对接 |
| `EdgeConfig` | Implemented / unit-tested | `.env` conventions | No | Intel安全provision与mode600 |
| Port candidate enumeration | Implemented / unit-tested | `l610_serial_probe.py` | Yes for acceptance | Linux读取VID/PID与tty |
| AT port discovery | Implemented / unit-tested with fake serial | `l610_serial_probe.py` | Yes | 现场逐候选 exact OK |
| Binary `SerialTransport` | Implemented / unit-tested | all golden scripts | Yes | 检验pyserial timing/URC行为 |
| SIM/LTE/MIPCALL parsing | Partial implemented | `l610_data_probe.py` | Yes | 移植完整异步状态/证据日志 |
| TLS state decision/PEM upload | Implemented / fake-channel tests | TLS probe/restore | Yes | 真机验证prompt、易失恢复、MIPOPEN |
| MQTT Remaining Length/UTF-8/PUBLISH codec | Partial implemented | connect/publish scripts | No/Yes | 补CONNECT/SUBSCRIBE/parser与流拆包 |
| Tuya HMAC auth | Implemented / algorithm unit coverage via client tests | `tuya_device_test.py`, connect script | No/Yes | 固定timestamp对拍 golden |
| `TuyaEdgeClient` facade/state | Implemented / fake backend tests | accepted workflow | No | 保持稳定上层API |
| Linux `L610LinkBackend` | **Not implemented** (Protocol only) | all root golden scripts | Yes | 按Stage逐步移植，禁止一次重写 |
| Linux TLS socket/MIPSEND receive loop | **Not implemented** | connect/publish scripts | Yes | Stage04–06分别验收 |
| Property business ACK | **Not implemented in backend** | publish script | Yes | Stage06实现/验收 |
| Training Summary real send | **Not implemented in backend** | training summary script | Yes | Stage07 only after property positive control |
| `qmzg_edge.main` production startup | Skeleton / fail-closed | N/A | Yes | link backend通过后再激活 |
| `hardware_acceptance.py` | env/serial/at implemented; later commands fail-closed | staged prompts | Yes for serial/at | 每Stage实现后替换NOT_READY |
| systemd unit | Not created | Field Stage10 | Yes | 所有手工验收后才创建/enable |

没有 Python `raise NotImplementedError` 隐藏在业务路径；缺口表现为 `L610LinkBackend` Protocol 尚无 concrete implementation，CLI明确返回 NOT_READY/非零 exit code。
