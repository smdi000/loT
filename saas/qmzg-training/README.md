# 模板简介

## 置信度指标语义

- `action_confidence` 是边缘侧实时动作识别状态指标，主要用于训练中状态展示或调试。本 MicroApp 的 Dashboard 不请求、不轮询该指标。
- `training_avg_confidence` 是一次训练结束后的 Session 级结果；在业务 API 中对应 `training_sessions.avg_confidence`，用于 Dashboard、训练历史和训练报告。
- Dashboard 仅在进入页面或用户点击“刷新数据”时重新读取训练会话，不建立置信度高频轮询。未来如增加训练中页面，实时指标应以约 500 ms～1 s 频率并经过滑动平均或 EMA 平滑后展示。

## 目录结构

- \_locales
  - 配置 manifest 多语言
- mock
  - 放置 mock 数据
- src
  - 放置项目文件
  - index.js
    - 微应用入口文件
  - public-path.js
    - 勿删 乾坤框架配置文件
- micro.config.js
  - 本地代理配置文件

## 快速启动

### 命令介绍

#### 本地开发

##### 配置 mock 数据

| 字段 | 类型   | 备注                 |
| ---- | ------ | -------------------- |
| mock | boolea | 控制是否开启 mock    |
| api  | Api[]  | 存放所有的 mock 接口 |

##### Api

| 字段 | 类型 | 备注 |
| --- | --- | --- |
| path | string | 请求路径 |
| method | HTTP request methods | http 的请求方式 |
| res | Object | 返回参数,此处数据结构为开发者自己定义,请求对应接口就返回 res 内所有内容 |
| mock | boolean | 控制此接口是否开启 mock |

##### 启动项目

`yarn start`

#### 本地代理配置 需要配置`micro.config.js`

##### 配置 micro.config.js

```javascript
/** @typedef {import("@tuya-sat/micro-dev-proxy").Config} DebuggerConfig */
/** @typedef {import("@tuya-sat/micro-script/dist/config/webpack.config").WebpackCombineFunction} WebpackCombineFunction */

module.exports = {
  /**@type {DebuggerConfig} */
  debuggerConfig: {
    target: 'xxx', // 需要代理的协议+host
    username: 'xxxx', // 对应域名的超级管理员账户名
    password: 'xxx', //  超级管理员密码
    logSign: true, // 打印请求头
    mockPermissions: [], // 模拟权限点
    additionHeaders: {}, // 自定义请求头
    themeConfig: { // 自定义主题色
      primaryColor: '#f50',
    },
  },
  /**@type {WebpackCombineFunction} */
  webpack(config, { isDev, isBuild }) {
    config.output.publicPath = './';
    return config;
  },
};
```

##### 启动

`yarn start`

##### 启动代理

`yarn start:proxy`

#### 微应用打包

`yarn build`
