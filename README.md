# 擎梦智骨 | Qmzg Training System

[中文](#中文) | [English](#english)

<a id="中文"></a>

# 中文

## 项目概览

这是一个上肢训练设备的软件集成工程，连接设备侧训练数据、TuyaLink 消息通道、业务后端与 Web / MicroApp 界面。仓库材料记录了 L610 与 Tuya 的设备通信验收、Pulsar 消息接入、后端持久化和训练报告链路；Intel 边缘端的生产集成仍属于待迁移工作。

## 系统架构

~~~mermaid
flowchart LR
    DEV[设备 / MCU] -->|UART| L610[L610 蜂窝通信]
    L610 -->|TLS MQTT| TUYA[TuyaLink]
    TUYA -->|消息服务 / Pulsar| INGEST[FastAPI Consumer]
    INGEST --> DB[(PostgreSQL)]
    DB --> API[FastAPI API]
    API --> WEB[React Web / MicroApp]
    EDGE[Edge 接口与单元测试] -. 后续 Linux 集成 .-> DEV
~~~

该图区分了已记录的设备到云端消息路径与尚待完成的 Edge Linux 集成，不代表仓库中的每个组件都已形成生产级部署。

## 已实现与已验证的能力

- 根目录 L610 脚本覆盖串口、蜂窝网络、TLS/MQTT 与 Tuya 属性或训练事件的设备侧集成；仓库验收文档记录了真机流程。
- 后端包含 FastAPI、Pulsar Consumer、PostgreSQL 数据模型及迁移相关代码，可接收并持久化 Tuya 消息。
- 验收材料记录了设备消息进入后端、训练记录与报告 API 的端到端验证，以及基于阿里云 ECS 的 Web 部署验收。
- React TypeScript 界面包含 Mock 模式，供没有设备或云端凭证时查看交互流程。
- edge/ 定义了面向后续集成的接口和单元测试；真实 Linux 串口接入仍需移植与验收。

## 代码分层

- l610_*.py：设备通信与 Tuya 发布脚本。
- backend/：FastAPI 服务、消息消费与数据库逻辑。
- saas/qmzg-training/：React TypeScript Web / MicroApp。
- edge/：边缘侧接口骨架与测试。
- deploy/：部署配置与验收辅助脚本。
- docs/acceptance/：历史验收记录与测试证据索引。

## 状态与限制

这是一个工程集成仓库，包含真实设备验收、后端和前端代码，也包含 Mock 数据与阶段性材料。Mock 数据不代表真实用户或训练成效。边缘 Linux 生产路径仍需完成迁移验证；开发接口与本地运行说明应以各子目录文档为准。公开仓库中曾出现部署地址，凭证与部署配置仍需人工安全复核。

## 技术栈

Python · UART · LTE / 4G · TLS · MQTT · TuyaLink · Apache Pulsar · FastAPI · PostgreSQL · React · TypeScript

---

<a id="english"></a>

# English

## Project Overview

This repository brings together software for an upper-limb training device, connecting device-side training data to TuyaLink messaging, a business backend, and Web / MicroApp interfaces. Repository acceptance notes document L610-to-Tuya communication, Pulsar ingestion, backend persistence, and training-report flows. Production integration of the Intel edge path remains a migration task.

## System Architecture

~~~mermaid
flowchart LR
    DEV[Device / MCU] -->|UART| L610[L610 cellular link]
    L610 -->|TLS MQTT| TUYA[TuyaLink]
    TUYA -->|Message Service / Pulsar| INGEST[FastAPI consumer]
    INGEST --> DB[(PostgreSQL)]
    DB --> API[FastAPI API]
    API --> WEB[React Web / MicroApp]
    EDGE[Edge interface and unit tests] -. future Linux integration .-> DEV
~~~

The diagram separates the documented device-to-cloud message flow from the Edge Linux integration that is still pending; it does not imply that every component is a production deployment.

## Implemented and Documented

- Root-level L610 scripts cover serial communication, cellular connectivity, TLS/MQTT, and Tuya property or training-event publishing; repository acceptance notes record real-device workflows.
- The backend contains FastAPI, a Pulsar consumer, PostgreSQL models, and migration code for ingesting and persisting Tuya messages.
- Acceptance materials document end-to-end checks from device messages to backend training records and report APIs, plus a Web deployment acceptance on Alibaba Cloud ECS.
- The React TypeScript interface includes a mock mode for exploring the flow without device access or cloud credentials.
- edge/ defines an interface and unit tests for later integration; a production Linux serial backend still requires porting and acceptance.

## Repository Structure

- l610_*.py: device communication and Tuya publishing scripts.
- backend/: FastAPI service, message ingestion, and database logic.
- saas/qmzg-training/: React TypeScript Web / MicroApp.
- edge/: edge interface scaffold and tests.
- deploy/: deployment configuration and acceptance helpers.
- docs/acceptance/: historical acceptance records and evidence index.

## Status and Limitations

This is an integration workspace with real-device acceptance notes, backend and frontend code, mock data, and staged materials. Mock values do not represent real users or training outcomes. The production Edge Linux path still needs migration validation; consult the subdirectory documentation for development and local setup. A deployment address has appeared in the public repository, so deployment configuration and credentials still require a manual security review.

## Technology

Python · UART · LTE / 4G · TLS · MQTT · TuyaLink · Apache Pulsar · FastAPI · PostgreSQL · React · TypeScript
