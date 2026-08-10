# Team Ownership

| 角色 | 主要范围 | 不应单方面修改 |
|---|---|---|
| UI teammate | `saas/`：页面、样式、图表、文案、响应式、Presentation Mode | backend schema、Tuya/L610、部署、Secret |
| Edge/Hardware teammate | `edge/`、STM32/Intel 集成、Linux 串口与启动恢复 | Business API、SaaS、云平台授权 |
| Cloud/Integration owner | `backend/`、`deploy/`、Tuya 平台、Pulsar、ECS、release | Edge 推理算法、UI 视觉细节 |
| Shared | `docs/`、API Contract、验收记录 | 任何人修改稳定契约前需同步相关角色 |

根目录 L610 golden reference 属于共享只读基准。涉及凭证、云发布、生产迁移或设备物模型的修改必须由 Cloud/Integration owner 明确评审。

