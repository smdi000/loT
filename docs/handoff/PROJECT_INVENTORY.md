# Project Inventory

审计日期：2026-08-11。此清单是移动文件前的源码快照分类；Phase 5-A 没有移动或删除原文件。

## 可维护模块

| 范围 | 路径 | 状态 |
|---|---|---|
| Edge 正式接口 | `edge/` | 新建骨架；纯单元测试；尚未接 Intel 真机 |
| Business Backend | `backend/` | 已真实部署并通过 ECS 验收 |
| Tuya MicroApp | `saas/qmzg-training/` | 已发布 0.0.1；Visual Polish 本轮不发布 |
| ECS 部署辅助 | `deploy/`、`backend/docker-compose.prod.yml` | 已用于 Phase 4-A |
| 系统/交接/验收文档 | `docs/` | 保留完整证据 |
| 公共 CA | `certs/tuya_go_daddy_root_g2.cer` | 公开信任根，不是私钥 |

## L610 golden reference（原位保留）

- `l610_tls_restore.py`
- `l610_tuya_connect.py`
- `l610_tuya_publish.py`
- `l610_tuya_training_event.py`
- `l610_tuya_training_summary.py`
- 辅助探测：`l610_serial_probe.py`、`l610_data_probe.py`、`l610_tls_probe.py`
- 原生网络鉴权基准：`tuya_device_test.py`

这些脚本记录了真机可用的 AT/TLS/MQTT 行为，是 Intel 移植的协议基准。Phase 5-A 未重写。

## 私密或可再生成内容（不进入 Git）

- 根 `.env`、`backend/.env`、所有嵌套 `.env`、`.secrets/`
- `.venv/`、`.venv_l610/`、`__pycache__/`、`.pytest_cache/`
- `saas/qmzg-training/node_modules/`、`dist/`、coverage
- `logs/`、`tmp/`、运行时日志
- `handoff_l610_tuya_20260807/` 及对应 ZIP（历史私密快照）
- Docker volume/state、runtime credentials、SSH 私钥

未发现可以无风险删除的“废弃协议脚本”；因此本阶段不删除任何历史 PoC。历史 handoff 只被 Git 忽略。

