# Stage 02 Prompt — AT / SIM / LTE

## GOAL

通过 Stage 01 已确认的 Intel `/dev/tty*` 读取模块、SIM、信号与 LTE 注册；不建立数据/TLS/MQTT。

## KNOWN GOOD BASELINE

Fibocom L610-CN-62-36，固件 `16000.1208.00.86.02.02`，115200。Windows golden 的成功状态为 `CPIN: READY`、`CEREG: 0,1`、CSQ 约 18,99。只以现场响应为准。参考 immutable `l610_serial_probe.py`/`l610_data_probe.py`。

## ALLOWED CHANGES

仅 `edge/` AT/status port 与纯测试、`docs/acceptance/phase5b_stage02*`。

## FORBIDDEN CHANGES

禁止 CGATT/CGACT/CFUN 写入、APN 修改、reset/reboot、MIPCALL、TLS/MQTT、golden/cloud/backend/SaaS 修改。

## COMMANDS / INSPECTION

用 Edge transport 逐条发送并保留原始 ASCII/HEX与时间戳：

```text
AT
ATI
AT+CGMM
AT+CGMR
AT+CPIN?
AT+CSQ
AT+COPS?
AT+CEREG?
AT+CGATT?
```

命令必须 `\r\n`，有 timeout；不要把 `OK` 以外字符串当成功。可先运行 `hardware_acceptance.py at --port <confirmed tty>`。

## SUCCESS CRITERIA

AT exact OK；身份为 L610；SIM READY；LTE 注册值为 home/roaming（1/5）；记录 operator、CSQ、CGATT 状态。

## STOP CONDITIONS

SIM 非 READY、LTE 未注册、串口身份不符、响应 ERROR/timeout、需要改天线/SIM/供电或发写命令时停止。LTE 不通过不得进入 Stage 03。

## EVIDENCE TO SAVE

port/baud、模块/固件、全部原始响应、SIM/operator/CSQ/CEREG/CGATT 分析、日志路径、tests/Git。

## FINAL REPORT FORMAT

按模板并给一行判据：`AT | module | firmware | SIM | operator | CSQ | CEREG | CGATT | PASS/STOP`。报告后停止。
