# Stage 01 Prompt — USB / Serial Discovery

## GOAL

在 Intel Linux Board 识别 Fibocom L610 USB 枚举和真实 AT tty。Agent 在朋友电脑，通过 `ssh qmzg-intel` 操作；朋友电脑不得直接控制 L610。

## KNOWN GOOD BASELINE

模块为 Fibocom L610-CN-62-36、固件 `16000.1208.00.86.02.02`，旧 Windows 为 115200。根 `l610_serial_probe.py` 是 immutable golden reference。Linux 不能硬编码 COM21 或第一个 `/dev/ttyUSB0`。

## ALLOWED CHANGES

只改 `edge/` 的 Linux serial 实现/测试与 `docs/acceptance/phase5b_stage01*`。可 READ/COMPARE golden，不得改它。

## FORBIDDEN CHANGES

禁止 network/TLS/MQTT、modem reset、udev/sudo/group 修改、USB 拔插（除非停下请求现场人员）、backend/saas/cloud 修改。

## COMMANDS / INSPECTION

```bash
ssh qmzg-intel 'lsusb; lsusb -t; dmesg --ctime 2>/dev/null | grep -Ei "usb|tty|cdc|fibocom" | tail -n 160; ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true; udevadm info --query=property --name=/dev/<candidate> 2>/dev/null || true'
ssh qmzg-intel 'cd <repo>/edge && .venv/bin/python scripts/hardware_acceptance.py serial'
```

结合 VID/PID、kernel log、device path 和逐候选 `AT\r\n → exact OK`。Fibocom 描述只提升优先级。若已有权限，可逐候选运行 `hardware_acceptance.py at --port /dev/<tty> --baud 115200`；一次一个，记录结果。

## SUCCESS CRITERIA

记录 VID、PID、所有 tty candidates、唯一/明确 AT port 与 115200 响应证据。只有实际 `OK` 才判 AT port。

## STOP CONDITIONS

无 USB 枚举、权限拒绝、多个口均无 OK、需要 sudo/group relogin/换口/插拔、看到异常 disconnect；停止并给现场人员单步指令。

## EVIDENCE TO SAVE

`lsusb`、dmesg、udev 属性、候选顺序、每个 AT 探测结果、最终 tty/baud、代码 diff/tests。

## FINAL REPORT FORMAT

按标准模板，明确 `VID/PID | candidates | selected AT port | baud | exact OK | failure layer | next=Stage 02 or repair Stage 01`。报告后停止。
