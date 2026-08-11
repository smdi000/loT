# Stage 00 Prompt — Environment Audit

## GOAL

你是朋友电脑上的 Intel Field Agent，通过 SSH 审计真实 Intel Linux Board。本阶段只建立 OS、资源、网络、USB/tty 和 Git 基线；不安装软件、不打开串口、不改代码。

## KNOWN GOOD BASELINE

项目为“擎梦智骨”。最终由 Intel → L610 → Tuya → Alibaba Cloud；云端已验收。115200 是旧 Windows 真机 baud，但 Linux 用户、IP、distro、tty 均未知。Agent 在朋友电脑运行，Edge 程序以后在 Intel 运行。

## ALLOWED CHANGES

只允许创建脱敏的 `docs/acceptance/phase5b_stage00*` 记录；默认不写远端。

## FORBIDDEN CHANGES

禁止安装/升级、sudo、reboot、修改 SSH/网络/firewall、打开 serial、连接云端、修改 golden scripts/backend/saas/deploy。

## COMMANDS / INSPECTION

若 `qmzg-intel` 未配置，停下指导用户填写真实 HostName/User/IdentityFile，不能索要密码。验证后执行只读：

```bash
ssh qmzg-intel 'set -u; uname -a; cat /etc/os-release; uname -m; python3 --version 2>&1 || true; whoami; id; groups; free -h; df -h; ip addr; ip route; lsusb; dmesg --ctime 2>/dev/null | grep -Ei "usb|tty|cdc|fibocom" | tail -n 120 || true; ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true'
ssh qmzg-intel 'cd <repo> && git status --short && git branch --show-current'
```

不确定 `<repo>` 时只查询 `pwd`/目录，不在整盘递归搜索 Secret。

## SUCCESS CRITERIA

确认 SSH、OS/arch、Python 状态、用户/groups、RAM/disk、IP/route、USB 与 tty candidates、repo branch/status；未改变系统。

## STOP CONDITIONS

SSH 失败、host key 异常、需要密码/sudo、磁盘或内存明显不足、repo 不明、任何命令将修改系统时停止。

## EVIDENCE TO SAVE

时间戳、上述脱敏原始输出、SSH alias 是否可用、未知项。不得保存 IP 私钥/密码/Token。

## FINAL REPORT FORMAT

按 `REPORT_TEMPLATE.md`：Stage、Commands、Observed hardware、Code changed、Tests、Acceptance evidence、Failure layer、Next safe action、Git status。报告后停止，不执行 Stage 01。
