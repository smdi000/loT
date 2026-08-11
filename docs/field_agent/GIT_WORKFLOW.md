# Field Agent Git Workflow

`main` 是 Phase 5-A.5 stable baseline。朋友电脑创建独立分支：

```bash
git switch main
git status --short
git switch -c edge/intel-integration
```

每个硬件门禁一个小 commit，并附对应 `docs/acceptance/phase5b*` 证据：

```text
edge: verify Intel USB serial
edge: verify L610 LTE on Intel
edge: restore L610 TLS automatically
edge: verify Tuya MQTT over L610
edge: report training summary from Intel
```

Commit 前：运行 Edge unit tests、`git diff --check`、secret scan、`git status`；确认根 golden scripts、backend、saas、deploy 没有变化。不要把 Edge 大改与 SaaS/backend 混在一个 commit。不要提交 `.env`、日志原始凭证、venv、cache 或硬件私钥。

禁止 `git reset --hard`、强推 main、伪造 Git identity。需要同步远端时先报告 diff 和当前 stage。
