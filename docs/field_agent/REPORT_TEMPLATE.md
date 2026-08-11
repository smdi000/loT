# Field Agent Stage Report Template

## Stage

`Stage NN — name`，开始/结束时间与时区。

## Commands

列出实际执行的命令；Secret 参数必须省略。标记由现场人员完成的物理步骤。

## Observed hardware

Intel OS/arch、L610 型号/固件、VID/PID、tty、baud、SIM/LTE/IP；只填本 Stage 真实观察。

## Code changed

文件、原因、边界。若无修改明确写“无”。

## Tests

命令、通过数、exit code。

## Acceptance evidence

原始响应摘要、ACK/URC、脱敏日志路径、云端记录（若本 Stage 需要）。

## Failure layer

USB / Serial / AT / SIM / LTE / Data / TLS / MQTT / Tuya ACK / Message Service / ECS / Business Session。成功则写“无”。

## Next safe action

只能给一个下一步；失败时不得跳关。

## Git status

分支、commit、`git status --short`。不得只写“已经完成”。
