# Acceptance Evidence Index

以下链路已通过真实环境验收，重构或迁移时必须保留为回归基准。

## L610 / Tuya device cloud

- [training_completed 真机 Event](tuya_training_event.md)
- [Tuya Message Service 诊断与 Property 正例](tuya_message_service.md)
- [北向 original capabilities](tuya_northbound_capabilities_after_subscription_20260808.json)

## Pulsar / Backend

- [真实 Tuya Pulsar Property 样本（脱敏）](tuya_pulsar_property_message_20260808.json)
- [Pulsar → PostgreSQL → FastAPI](business_backend_postgres_20260808.md)
- [Auth、设备归属、训练 API](business_backend_phase2_20260808.md)
- [真实 Training Summary → Report](business_backend_phase3_real_training_20260808.md)

## Alibaba Cloud

- [ECS Phase 4-A 全链路](alibaba_cloud_phase4a_20260810.md)
- [Competition Public Web Deployment](competition_web_deployment_20260812.md) — ECS Nginx + Visual Polish React + `/custom-api` + 真实训练报告

## Tuya SaaS

- [MicroApp Phase 4-B](tuya_saas_phase4b_20260810.md)
- [Competition Visual Polish](saas_visual_polish_20260810.md)
- 截图位于 `screenshots/saas_phase4b/` 与 `screenshots/saas_visual_polish/`。

## Protocol golden references

根目录 L610 脚本与历史本地日志曾完成串口、LTE、TLS、MQTT、Property/Event 真机验收。日志含设备标识和协议证据，已被 Git 忽略；需要审计时仅在授权的私密工作区查阅。
