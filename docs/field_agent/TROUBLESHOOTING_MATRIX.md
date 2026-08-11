# Troubleshooting Matrix

先定位最小失败层；上层失败不能反向证明底层失败。保留原始证据，不“全部重做”。

| Layer | Symptoms | Checks | Evidence-based causes | Forbidden actions |
|---|---|---|---|---|
| USB | `lsusb`无L610、反复disconnect | `lsusb -t`、dmesg USB、供电/线缆由现场确认 | 未供电、数据线/USB口、kernel枚举 | Agent声称插拔；盲装driver；改网络 |
| Serial | tty不存在/permission denied/乱码 | `/dev/ttyUSB*`、udevadm、groups、逐候选115200 | device node变化、dialout/uucp权限、选错口/baud | 硬编码ttyUSB0；未经批准sudo/chmod 777 |
| AT | timeout/ERROR/身份不符 | exact `AT\r\n→OK`、ATI/CGMM/CGMR、原始HEX | 非AT port、端口被占用、模块未就绪 | 随机baud/AT命令；reset模块 |
| SIM | CPIN非READY | `AT+CPIN?`、SIM现场状态 | SIM未插/锁定/接触问题 | 猜PIN；写SIM配置；跳到LTE |
| LTE | CEREG非1/5、信号差 | COPS/CSQ/CEREG/CGATT、天线现场确认 | 注册等待、覆盖/天线/SIM套餐 | CFUN/reboot/APN乱改；继续Data |
| Data | MIPCALL无IP/ERROR | CGATT、CGDCONT/APN、MIPCALL初始/URC、可选MPING | attach/APN/运营商会话；busy | 随机CGACT/CGATT/CFUN；仅因APN陌生就改 |
| TLS | MIPOPEN非1,1、GTSSLERR | CCLK、GTSSLVER/MODE/FILE、CA hash/长度、socket free、最终URC | 掉电易失、裸Base64、时钟、socket资源 | 关验证、换1883、下载随机CA、写死IP |
| MQTT | 无/非0 CONNACK | CONNECT自解析、timestamp、length、真实binary MIPSEND、MIPRTCP | framing、时间、重复client、byte传输 | 猜签名变体、MQTTOPEN、把HEX当ASCII |
| Tuya ACK | PUBACK有但业务code非0/无response | Topic、msgId、sys.ack、SUBACK/PUBACK、Device Log | Thing Model字段/范围、response订阅 | 改产品/重注册、重复乱发 |
| Message Service | Tuya code0但Pulsar无property | Test/PROD、Device linking、rule、consumer时间线 | channel/rule/consumer；Event转换问题与Property区分 | 改Thing Model、Product Release、把Event问题混入Property正例 |
| ECS | Pulsar收到但无`tuya_messages` | consumer脱敏日志、DB health、dedup key、processed | consumer/DB连接、duplicate/parse | 直接SQL造消息、改生产Secret |
| Business Session | raw有但session无/字段错 | 9字段完整性、adapter、Device存在/owner、constraints | incomplete payload、validation、binding | 改schema绕过、丢原始消息、伪造session |

任何层若需要 sudo、重启、物理插拔、Secret输入或云端修改，Agent停止并请求现场/负责人单步处理。
