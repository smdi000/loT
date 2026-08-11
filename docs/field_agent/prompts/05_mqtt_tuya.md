# Stage 05 Prompt — Manual MQTT / Tuya Authentication

## GOAL

通过 Intel → L610 已验收 TLS socket 手工发送一次 MQTT 3.1.1 CONNECT，并解析 CONNACK；不 PUBLISH/SUBSCRIBE。

## KNOWN GOOD BASELINE

不要优先使用 built-in `AT+MQTTOPEN`。稳定路径是 MIPOPEN type 2 + prompt-based binary MIPSEND + manual MQTT。Tuya auth 复用 `tuya_device_test.py`/`l610_tuya_connect.py`：一次生成一个秒级 timestamp，ClientID `tuyalink_{DeviceID}`，官方 username/sign content，HMAC-SHA256 lowercase hex。CONNECT level 4、flags `0xC2`、keepalive 60、UTF-8 2-byte lengths、variable Remaining Length。成功为 `20 02 00 00`。

## ALLOWED CHANGES

只改 `edge/` MQTT/Tuya link backend/tests 与 `docs/acceptance/phase5b_stage05*`。

## FORBIDDEN CHANGES

禁止猜鉴权、打印 DeviceSecret/password、改 Product/Device、使用 Windows 发送、PUBLISH/SUBSCRIBE、改 golden/cloud/backend/SaaS。

## COMMANDS / INSPECTION

从受保护 `edge/.env` 读取凭证。用同一 timestamp 构造并本地反解析 CONNECT；记录长度、HEX与 password fingerprint。TLS socket成功后 `AT+GTSET="IPRFMT",0`，`AT+MIPSEND=1,<len>` 等 `>`，发送真实 bytes，无额外终止符；解析 `+MIPRTCP` HEX 为真实 MQTT bytes。失败 rc=5 时保存字段/fingerprint/packet/MIPSEND长度并与 golden byte-for-byte 比较，不试变体。最后关闭 socket。

## SUCCESS CRITERIA

本地 parser assertions 全通过；declared/actual bytes相等；MIPSEND status 0；CONNACK exactly `20 02 00 00`；socket正常关闭。

## STOP CONDITIONS

TLS未通过、配置/时间不可靠、packet assertion失败、prompt/MIPSEND异常、CONNACK非0或缺失、另一个同 DeviceID client 活跃。

## EVIDENCE TO SAVE

DeviceID suffix、timestamp、字段长度、CONNECT/MIPSEND长度、HEX、fingerprint、CONNACK、close、测试/Git；绝不保存 DeviceSecret/明文 password。

## FINAL REPORT FORMAT

模板 + `timestamp | ClientID/Username/Password lengths | CONNECT bytes | MIPSEND bytes | CONNACK | rc | close | PASS/STOP`。报告后停止。
