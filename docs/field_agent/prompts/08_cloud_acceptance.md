# Stage 08 Prompt — Full Cloud Acceptance

## GOAL

验证 `acceptance_intel_training_001` 从 Intel/L610 一直进入 Pulsar、ECS Consumer、PostgreSQL、FastAPI history/detail/report 与 Public Competition Web。设备侧 `code=0` 不是完整验收。

## KNOWN GOOD BASELINE

Tuya China TEST Pulsar、ECS Consumer、PostgreSQL revision `20260808_02`、FastAPI、Nginx 与 Public Competition Web 已验收。比赛入口是 `http://47.250.160.90/`。Property adapter 将 `training_max_shldr_angle` 映射为业务 `max_shoulder_angle`。生产系统默认只读验证，不修改部署。

## ALLOWED CHANGES

仅 `docs/acceptance/phase5b_stage08*`；如发现明确 Edge 数据问题，可回到 `edge/` 修复并重跑 Stage07。允许使用正式 API/JWT进行已有用户可见性验证，凭证只驻留内存。

## FORBIDDEN CHANGES

禁止改 ECS compose、Consumer、database/schema/ownership、Tuya、Public Web/Nginx/SaaS、创建比赛账号、直接 SQL 造记录、记录密码/JWT/Secret。

## COMMANDS / INSPECTION

按 msgId/session/DeviceID 时间线只读核对：Tuya ACK/Device Log（如可访问）、Consumer 日志脱敏摘要、`tuya_messages`、`training_sessions`、owner/source_type；通过正式 API 验证 history/detail/report，最后确认 Public Competition Web 出现新训练记录。Field Agent 不得索要比赛账号密码；需要 UI 登录时，让现场用户本人登录，Agent 只使用已登录浏览器 session 验收。不得输出或保存 token。

## SUCCESS CRITERIA

`external_session_id=acceptance_intel_training_001`；`source_type=tuya_property`；owner正确；字段与 Intel 一致；history/detail/report 均可见；报告不是医疗诊断；Public Competition Web 显示真实数据。

## STOP CONDITIONS

任一层缺失、重复记录、owner错误、值不一致、需要生产修改或 Secret。准确标出最小失败层，不重做全部。

## EVIDENCE TO SAVE

逐层时间/ID 关联、脱敏 DB/API/Public Web 结果、幂等观察、Failure layer、Git status。

## FINAL REPORT FORMAT

模板 + 链路矩阵 `Intel | Tuya ACK | Pulsar | ECS Consumer | tuya_messages | training_sessions | FastAPI | Public Web | report`，每项 PASS/FAIL。报告后停止。
