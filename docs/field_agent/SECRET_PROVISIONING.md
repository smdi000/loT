# Secret Provisioning

## Intel `edge/.env` variables

```dotenv
TUYA_PRODUCT_ID=
TUYA_DEVICE_ID=
TUYA_DEVICE_SECRET=
L610_PORT=
L610_BAUD=115200
TUYA_MQTT_HOST=m1.tuyacn.com
TUYA_MQTT_PORT=8883
L610_CA_PEM_PATH=certs/tuya_go_daddy_root_g2.cer
```

`L610_PORT` 可先留空做 AT discovery，确认后再填写现场 `/dev/tty*`。CA 是公开信任根；DeviceSecret 是真实设备密钥。

## 安全来源

- 已授权的当前项目私密环境
- Tuya Developer Platform 的设备页面
- 团队 Cloud/Integration owner

凭证只能通过团队批准的密码管理器、加密传输或现场输入 provision。禁止 Git、普通 Markdown、聊天/微信明文文件、截图、工单、终端共享记录。Agent 不索要账号密码，不导出浏览器 Cookie/Token。

## Intel 文件保护

由现场用户创建，不把值作为命令行参数：

```bash
cp edge/.env.example edge/.env
chmod 600 edge/.env
${EDITOR:-vi} edge/.env
```

验证只显示文件存在、owner 和 permission，不打印内容：

```bash
stat -c '%U %G %a %n' edge/.env
git check-ignore -v edge/.env
```

日志只允许 DeviceID 脱敏、Password fingerprint/长度；绝不打印 DeviceSecret、Tuya Password 或完整凭证。
