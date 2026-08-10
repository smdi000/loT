# Intel Migration Checklist

按顺序验收，前一项失败时保留原始证据并停止，不随机改变协议。

- [ ] A. Linux / Python 3.12 / pyserial / 用户串口权限
- [ ] B. USB enumeration：记录 device、description、VID/PID；不假定第一个 ttyUSB
- [ ] C. AT：实际收到 `OK`，读取 ATI/CGMM/CGMR
- [ ] D. SIM：`CPIN: READY`
- [ ] E. LTE：运营商、`CEREG` 注册、`CGATT=1`
- [ ] F. MIPCALL：取得有效 IPv4，基础公网连通
- [ ] G. TLS restore：按需恢复版本 4、校验模式 1、完整 PEM TRUSTFILE
- [ ] H. Tuya MQTT CONNECT：TLS socket、CONNACK `20 02 00 00`
- [ ] I. `action_confidence` 正例：PUBACK、Tuya code=0、Pulsar property message
- [ ] J. 完整 Training Summary：仅 Session 结束发送一次
- [ ] K. ECS PostgreSQL：`tuya_messages` 与 `training_sessions` 真落库
- [ ] L. Report API：history/detail/report 数据与边缘摘要一致
- [ ] M. 断电重启：自动重新探测串口、网络与 TLS，不依赖人工 restore 工具

每一步记录端口、固件、时间戳、原始响应和日志路径，但不得记录 DeviceSecret/Access Secret。

