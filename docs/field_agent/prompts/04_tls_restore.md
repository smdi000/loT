# Stage 04 Prompt — TLS Restore and Probe

## GOAL

把已验收的易失 TLS 初始化移植到 Intel Edge：query → 按需 restore → verify → 对 `m1.tuyacn.com:8883` 做一次 TLS socket probe并关闭。不得发送 MQTT。

## KNOWN GOOD BASELINE

L610 掉电后 `GTSSLVER=0`、`GTSSLMODE=0`、`TRUSTFILE,0` 是已证实行为。known-good：`GTSSLVER=4`（TLS 1.2）、`GTSSLMODE=1`（验证服务器）、仓库 `certs/tuya_go_daddy_root_g2.cer` 转完整 PEM；DER SHA-256 为 `45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda`。完整 PEM 1390 bytes；裸 Base64 曾导致 `GTSSLERR -19`。MIPOPEN：`AT+MIPOPEN=1,,"m1.tuyacn.com",8883,2`，成功 `+MIPOPEN: 1,1`。参考 immutable `l610_tls_probe.py`、`l610_tls_restore.py`。

## ALLOWED CHANGES

仅 `edge/` TLS/Linux backend/tests 与 `docs/acceptance/phase5b_stage04*`。

## FORBIDDEN CHANGES

禁止下载/换 CA、禁用证书验证、用 1883、写死 DNS IP、发送 MQTT、改 golden/cloud/backend/SaaS、随机 SSL 参数。

## COMMANDS / INSPECTION

先检查模块时间与 `GTSSLVER? / GTSSLMODE? / GTSSLFILE?`。状态正确则不重复写。缺失时依 golden：设置版本；`AT+GTSSLFILE="TRUSTFILE",<exact_len>` 收到 `>` 后发送完整 PEM exact bytes，无 CRLF/Ctrl-Z追加；设置 mode；重新 query。确认 socket free 后 MIPOPEN，等待最终 URC，保持 5 秒，查询状态并正常关闭。所有写入二进制/长度必须测试。

## SUCCESS CRITERIA

恢复后 version=4、mode=1、trust>=1；MIPOPEN 最终 `+MIPOPEN: 1,1`；保持稳定并正常关闭；没有 MQTT bytes。

## STOP CONDITIONS

证书 hash 不匹配、模块时间异常、ODM prompt 缺失、`GTSSLERR` 非已知证据、socket 资源占用、TLS失败。不得通过关 TLS 绕过。

## EVIDENCE TO SAVE

restore 前后状态、PEM path/hash/byte count（非内容）、AT/URC/GTSSLERR、socket hold/close、tests/diff/Git。

## FINAL REPORT FORMAT

模板 + `initial TLS state | writes performed | confirmed state | MIPOPEN command | final URC | close | PASS/STOP`。报告后停止。
