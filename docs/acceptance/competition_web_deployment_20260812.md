# Competition Web Deployment Acceptance

日期：2026-08-12
阶段：Phase 4-C Competition Web Deployment

## 目标与边界

本阶段将 Visual Polish 后的“擎梦智骨训练平台”作为普通静态 React Web App 部署到 Alibaba Cloud ECS，使公网根地址 `http://47.250.160.90/` 展示前端，并保持 FastAPI、PostgreSQL、Tuya Pulsar Consumer 和已有业务语义不变。

未执行 sdf publish，未修改 Tuya Thing Model、L610、Intel Edge、Pulsar Consumer、PostgreSQL schema、FastAPI 业务逻辑、设备归属或已发布的 MicroApp 0.0.1。

## Standalone Build

- 前端目录：`saas/qmzg-training/`
- 构建命令：`npm run build:web`
- 构建模式：`QMZG_DATA_MODE=real`、`QMZG_STANDALONE=true`
- API contract：仍统一使用 `/custom-api/...`
- Standalone 兼容改动：仅为 standalone build 使用根路径 `/` 作为 Webpack public path；常规 Tuya MicroApp build 继续使用相对 public path。
- 页面标题：`擎梦智骨训练平台`
- 依赖安装：lockfile 存在；由于 Tuya 模板既有 peer dependency 约束，使用 `npm ci --legacy-peer-deps`，未修改 lockfile，未执行 `npm audit fix`。

验收结果：

- Jest：6 suites，15 tests passed
- TypeScript typecheck：通过
- ESLint：通过
- Standalone build：通过
- Tuya 模板 bundle size 提示：仅 warning，不影响构建

## Secret Scan

部署前对 Git tracked files 与最终 `dist` 做了精确值和标记扫描：

- 检查本机私密环境中的 4 个真实 Secret 值，命中 0 个文件
- tracked `.env`：0
- 禁止 tracked 路径：0
- Private Key marker：0
- Bearer token marker：0
- 最终 bundle 中 `47.250.160.90`：0

真实 Secret、密码、JWT、SSH private key 和 acceptance 凭证均未进入源码、bundle 或本文档。

## Deployment

- ECS static root：`/var/www/qmzg-training/current`
- 当前 release：`/var/www/qmzg-training/releases/20260811T162457Z`
- Nginx 配置：`/etc/nginx/conf.d/qmzg.conf`
- Nginx 备份：`/etc/nginx/conf.d/qmzg.conf.backup-20260811T162457Z`
- 可重复部署脚本：`/opt/qmzg/deploy/deploy_saas_web.sh`
- 服务器保留模板：`/opt/qmzg/deploy/qmzg-saas.conf`

部署使用不可变 timestamp release 与 `current` symlink 原子切换。第一次 post-deploy 检查在 Nginx graceful reload 的旧 worker 窗口中读取到旧 FastAPI 根路由，脚本自动恢复旧配置；随后加入有限重试并重新部署成功，后端服务没有中断。

## Nginx Routing

| 请求 | 目标 | 结果 |
| --- | --- | --- |
| `/` | React `index.html` | HTTP 200，标题正确 |
| `/dashboard` | React history fallback | HTTP 200 |
| `/devices`、`/training/...` | React history fallback | 由 `try_files` 支持 |
| `/dashboard?presentation=1` | React Presentation Mode | HTTP 200 |
| `/health` | FastAPI `127.0.0.1:8000/health` | HTTP 200，database ok |
| `/custom-api/api/...` | 去掉 `/custom-api/` 后代理到 FastAPI `/api/...` | 未认证 `/me` 返回预期 HTTP 401 |

`proxy_pass http://127.0.0.1:8000/;` 的 trailing slash 只移除 `/custom-api/` 前缀。例如 `/custom-api/api/auth/login` 映射为 FastAPI `/api/auth/login`。

## Real Data

ECS PostgreSQL 只读复核确认真实记录仍存在：

- `external_session_id`：`acceptance_cloud_training_001`
- duration：623 秒（10:23）
- total reps：57
- average confidence：9670（96.70%）
- max elbow：1285（128.5°）
- max shoulder：934（93.4°）
- source：`tuya_property`
- owner：已关联
- actions：curl 20、raise 15、lateral 12、boxing 10
- fault count：0

A dedicated competition demo account exists and has ownership of the real demonstration device. Credentials are retained out-of-band by the team lead.

该账号通过正式 auth flow 创建，设备通过既有 `DeviceOwnershipService` 内部 CLI 原子迁移；未直接更新数据库、未修改 password hash、未删除训练历史。公网真实 UI 验收确认：

- Dashboard：1 台真实设备、1 次训练、57 次动作、10:23、96.70%、128.5°、93.4°。
- Devices：真实设备 ID 脱敏显示并标记已绑定。
- Training History：出现 `acceptance_cloud_training_001`，分页总数为 1。
- Report：动作 curl 20、raise 15、lateral 12、boxing 10，`fault_count=0`，非医疗声明存在。
- Presentation Mode：`/dashboard?presentation=1` 使用真实数据并隐藏次要导航。
- Browser console：未发现应用 error。

## Rollback

部署脚本支持：

```bash
sudo /opt/qmzg/deploy/deploy_saas_web.sh rollback
```

回滚会恢复上一份 Nginx 配置与上一 static release，先执行 `nginx -t`，再使用 graceful reload。部署流程本身也会在 Nginx 配置检查或 post-deploy health/root 检查失败时自动回滚。

## Runtime Health

部署后状态：

- Nginx：active；`nginx -t` 成功
- FastAPI：healthy，约 61.6 MiB
- Tuya Consumer：running，约 45.9 MiB
- PostgreSQL：healthy，约 34.6 MiB
- ECS memory：1.8 GiB total，约 1.3 GiB available
- Swap：1 GiB，使用 0
- Disk `/`：30 GiB，总使用约 8.4 GiB，可用约 20 GiB
- PostgreSQL 5432：未映射到宿主机
- FastAPI 8000：仅监听 `127.0.0.1`

## Security Follow-up

- 当前阶段无域名和正式证书，比赛 fallback 使用 HTTP，因此浏览器会显示“不安全”。未使用自签证书或伪造域名。
- ECS 宿主机进程审计发现 SSH 监听 22、Nginx 监听 80；Alibaba Cloud Security Group 中 22 的来源限制需要继续由控制台保持为指定管理 IP。
- 宿主机另有 BT-Panel 监听 `0.0.0.0:8888`。本阶段未修改宝塔面板、宿主机防火墙或云安全组；必须确认 Alibaba Cloud Security Group 未向公网开放 8888。若已开放，应作为独立安全变更收紧。
- 443 当前没有正式 HTTPS 服务；获得合法域名后再配置 DNS、证书和 HTTPS。

## 结论

Standalone build、ECS static deployment、Nginx SPA history fallback、`/health`、`/custom-api` 同源路由、正式登录与真实 Dashboard/History/Report/Presentation Mode 均已通过。公网根地址已从 FastAPI 404 JSON 切换为“擎梦智骨训练平台”，Phase 4-A 后端容器保持健康。
