# Stage 03 Prompt — Cellular Data Network

## GOAL

在已通过 SIM/LTE 的 Intel + L610 上确认 APN、CGATT 和 MIPCALL IPv4；做最小 DNS/ping。禁止 TLS/MQTT。

## KNOWN GOOD BASELINE

immutable `l610_data_probe.py` 真机路线：先只读 `COPS? / CGATT? / CGDCONT? / MIPCALL?`；若无会话才 `AT+MIPCALL=1`，最长约 60 秒。旧成功 APN 是 `ctnet`、获得 private IPv4；APN 看起来陌生不是修改理由。

## ALLOWED CHANGES

仅 `edge/` network backend/测试与 `docs/acceptance/phase5b_stage03*`。

## FORBIDDEN CHANGES

禁止改 APN、随机 CGACT/CGATT/CFUN、modem reboot、MIPOPEN/TLS/MQTT、golden/cloud/backend/SaaS 修改。

## COMMANDS / INSPECTION

先读 golden，再通过已确认 tty 顺序执行：`AT`、`AT+COPS?`、`AT+CGATT?`、`AT+CGDCONT?`、`AT+MIPCALL?`。已有有效非 `0.0.0.0` IPv4 则不拨号；否则只发 `AT+MIPCALL=1` 并等待最终 URC，再复查。仅当 firmware 明确支持 `AT+MPING=?` 时 ping 一个公网 IP；DNS 可使用手册/已验证 `MIPDNS`，不要写死 Broker IP。

## SUCCESS CRITERIA

CGATT=1，记录当前 APN，MIPCALL status=1 且有效 IPv4；可选 DNS/ping 有正例或明确标记 unsupported（不作为失败）。

## STOP CONDITIONS

`MIPCALL=1` ERROR/timeout、状态 busy、证据指向 APN 但修改需用户授权、串口/LTE 回退。失败不进入 TLS。

## EVIDENCE TO SAVE

原始命令/URC、APN、初始/最终 MIPCALL、IPv4、DNS/ping 支持与结果、代码/tests/Git。

## FINAL REPORT FORMAT

模板 + `operator | CGATT | APN | MIPCALL initial | dial | IPv4 | DNS/ping | PASS/STOP`。报告后停止。
