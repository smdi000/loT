"""最小可运行的 TuyaLink MQTT 属性上报测试程序。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
import ssl
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from itertools import cycle
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


MQTT_HOST = "m1.tuyacn.com"
MQTT_PORT = 8883
MQTT_KEEPALIVE_SECONDS = 60
PUBLISH_INTERVAL_SECONDS = 5
PROPERTY_CODE = "action_confidence"
TEST_VALUES = (8500, 9000, 9500, 9982)
NTP_SERVERS = ("ntp.aliyun.com", "time1.cloud.tencent.com", "time.cloudflare.com")
MAX_CLOCK_SKEW_SECONDS = 120
NTP_EPOCH_DELTA_SECONDS = 2_208_988_800

logger = logging.getLogger("tuya-device-test")


@dataclass(frozen=True)
class DeviceConfig:
    product_id: str
    device_id: str
    device_secret: str = field(repr=False)


@dataclass
class RuntimeState:
    device_id: str
    device_secret: str = field(repr=False)
    response_topic: str
    connected: threading.Event = field(default_factory=threading.Event)
    first_connack: threading.Event = field(default_factory=threading.Event)
    stopping: bool = False


def load_config() -> DeviceConfig:
    """从脚本所在目录的 .env 读取并检查设备凭证。"""
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.is_file():
        raise ValueError("未找到 .env；请先复制 .env.example 为 .env 并填写设备凭证。")
    load_dotenv(dotenv_path=env_path, override=True)

    names = ("TUYA_PRODUCT_ID", "TUYA_DEVICE_ID", "TUYA_DEVICE_SECRET")
    values = {name: os.getenv(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(
            f"缺少环境变量：{', '.join(missing)}。请复制 .env.example 为 .env 后填写。"
        )

    return DeviceConfig(
        product_id=values["TUYA_PRODUCT_ID"],
        device_id=values["TUYA_DEVICE_ID"],
        device_secret=values["TUYA_DEVICE_SECRET"],
    )


def build_mqtt_credentials(
    device_id: str, device_secret: str, timestamp: int | None = None
) -> tuple[str, str, str, int]:
    """按 TuyaLink 一机一密协议动态生成 MQTT 鉴权参数。"""
    timestamp = int(time.time()) if timestamp is None else timestamp
    client_id = f"tuyalink_{device_id}"
    username = (
        f"{device_id}|signMethod=hmacSha256,timestamp={timestamp},"
        "secureMode=1,accessType=1"
    )
    content = (
        f"deviceId={device_id},timestamp={timestamp},secureMode=1,accessType=1"
    )
    password = hmac.new(
        device_secret.encode("utf-8"),
        content.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return client_id, username, password, timestamp


def query_ntp_offset(server: str, timeout: float = 2.0) -> tuple[float, float]:
    """返回 NTP 时间相对本机时间的偏差和请求耗时（秒）。"""
    request = b"\x1b" + 47 * b"\0"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        started_at = time.time()
        sock.sendto(request, (server, 123))
        response, _ = sock.recvfrom(512)
        finished_at = time.time()

    if len(response) < 48:
        raise ValueError("NTP 响应长度不足")

    seconds, fraction = struct.unpack("!II", response[40:48])
    server_time = seconds - NTP_EPOCH_DELTA_SECONDS + fraction / 2**32
    local_midpoint = (started_at + finished_at) / 2
    return server_time - local_midpoint, finished_at - started_at


def verify_system_clock() -> None:
    """运行前尽力通过公网 NTP 检查本机系统时间。"""
    logger.info("当前系统时间：%s", datetime.now().astimezone().isoformat(timespec="seconds"))

    errors: list[str] = []
    for server in NTP_SERVERS:
        try:
            offset, latency = query_ntp_offset(server)
            logger.info(
                "系统时间检查成功：NTP=%s，偏差=%+.3f 秒，往返耗时=%.3f 秒",
                server,
                offset,
                latency,
            )
            if abs(offset) > MAX_CLOCK_SKEW_SECONDS:
                raise RuntimeError(
                    f"系统时间偏差约 {offset:+.1f} 秒，超过允许的 "
                    f"{MAX_CLOCK_SKEW_SECONDS} 秒；请先同步系统时间。"
                )
            return
        except RuntimeError:
            raise
        except (OSError, ValueError) as exc:
            errors.append(f"{server}: {exc}")

    logger.warning(
        "无法通过公网 NTP 核验系统时间（可能是 UDP 123 被拦截）；"
        "将继续使用本机时间。请先用操作系统的时间同步功能确认时钟准确。详情：%s",
        "; ".join(errors),
    )


def reason_code_value(reason_code: object) -> int:
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1


def on_connect(
    client: mqtt.Client,
    state: RuntimeState,
    connect_flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    del connect_flags, properties
    code = reason_code_value(reason_code)
    state.first_connack.set()

    if code != 0:
        state.connected.clear()
        logger.error("MQTT连接失败，错误码=%s，原因=%s", code, reason_code)
        return

    state.connected.set()
    logger.info("MQTT连接成功：%s:%s（TLS / MQTT 3.1.1）", MQTT_HOST, MQTT_PORT)
    result, _ = client.subscribe(state.response_topic, qos=1)
    if result == mqtt.MQTT_ERR_SUCCESS:
        logger.info("已请求订阅涂鸦响应 Topic：%s", state.response_topic)
    else:
        logger.error(
            "订阅涂鸦响应 Topic 失败，错误码=%s（%s）",
            result,
            mqtt.error_string(result),
        )


def on_subscribe(
    client: mqtt.Client,
    state: RuntimeState,
    message_id: int,
    reason_code_list: list[mqtt.ReasonCode],
    properties: mqtt.Properties | None,
) -> None:
    del client, state, properties
    failures = [code for code in reason_code_list if reason_code_value(code) >= 128]
    if failures:
        logger.error("响应 Topic 订阅被拒绝：mid=%s，原因=%s", message_id, failures)
    else:
        logger.info("响应 Topic 订阅成功：mid=%s", message_id)


def on_disconnect(
    client: mqtt.Client,
    state: RuntimeState,
    disconnect_flags: mqtt.DisconnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    del disconnect_flags, properties
    state.connected.clear()
    code = reason_code_value(reason_code)
    if state.stopping:
        logger.info("MQTT连接已关闭")
        return

    # 自动重连之前刷新时间戳及签名，避免长时间运行后使用过期鉴权参数。
    _, username, password, timestamp = build_mqtt_credentials(
        state.device_id, state.device_secret
    )
    client.username_pw_set(username=username, password=password)
    logger.warning(
        "MQTT连接意外断开，错误码=%s，原因=%s；已用时间戳 %s 刷新签名，等待自动重连",
        code,
        reason_code,
        timestamp,
    )


def on_message(
    client: mqtt.Client, state: RuntimeState, message: mqtt.MQTTMessage
) -> None:
    del client, state
    payload = message.payload.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(payload)
        payload = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    except json.JSONDecodeError:
        pass
    logger.info("涂鸦响应消息：topic=%s，payload=%s", message.topic, payload)


def build_client(config: DeviceConfig) -> tuple[mqtt.Client, RuntimeState]:
    report_response_topic = (
        f"tylink/{config.device_id}/thing/property/report_response"
    )
    client_id, username, password, timestamp = build_mqtt_credentials(
        config.device_id, config.device_secret
    )
    state = RuntimeState(
        device_id=config.device_id,
        device_secret=config.device_secret,
        response_topic=report_response_topic,
    )

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
        userdata=state,
    )
    client.username_pw_set(username=username, password=password)

    tls_context = ssl.create_default_context()
    tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
    client.tls_set_context(tls_context)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    logger.info("已动态生成 MQTT 鉴权参数（时间戳=%s，DeviceSecret 未输出）", timestamp)
    return client, state


def make_property_report(value: int) -> tuple[str, str]:
    timestamp_ms = int(time.time() * 1000)
    message_id = uuid.uuid4().hex
    payload = {
        "msgId": message_id,
        "time": timestamp_ms,
        "sys": {"ack": 1},
        "data": {
            PROPERTY_CODE: {
                "value": value,
                "time": timestamp_ms,
            }
        },
    }
    return message_id, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def publish_forever(client: mqtt.Client, state: RuntimeState) -> None:
    report_topic = f"tylink/{state.device_id}/thing/property/report"

    for value in cycle(TEST_VALUES):
        if not state.connected.is_set():
            logger.warning("MQTT尚未连接，等待重连后再上报")
        while not state.connected.wait(timeout=1):
            pass

        message_id, payload = make_property_report(value)
        info = client.publish(report_topic, payload=payload, qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(
                "消息发布失败：错误码=%s（%s），msgId=%s",
                info.rc,
                mqtt.error_string(info.rc),
                message_id,
            )
        else:
            try:
                info.wait_for_publish(timeout=10)
            except RuntimeError as exc:
                logger.error("消息发布确认失败：msgId=%s，原因=%s", message_id, exc)

            if info.is_published():
                logger.info(
                    "消息发布成功：topic=%s，msgId=%s，%s=%s（平台显示 %.2f%%）",
                    report_topic,
                    message_id,
                    PROPERTY_CODE,
                    value,
                    value / 100,
                )
            else:
                logger.error("消息发布确认超时：msgId=%s", message_id)

        time.sleep(PUBLISH_INTERVAL_SECONDS)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    client: mqtt.Client | None = None
    state: RuntimeState | None = None
    try:
        config = load_config()
        logger.info(
            "配置加载成功：ProductID=%s，DeviceID=%s，DeviceSecret 已隐藏",
            config.product_id,
            config.device_id,
        )
        verify_system_clock()
        client, state = build_client(config)

        try:
            connect_result = client.connect(
                MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE_SECONDS
            )
        except (OSError, ssl.SSLError) as exc:
            error_code = getattr(exc, "errno", "N/A")
            logger.error("MQTT连接失败，错误码=%s，原因=%s", error_code, exc)
            return 1
        if connect_result != mqtt.MQTT_ERR_SUCCESS:
            logger.error(
                "MQTT连接失败，错误码=%s（%s）",
                connect_result,
                mqtt.error_string(connect_result),
            )
            return 1

        client.loop_start()
        if not state.first_connack.wait(timeout=20):
            logger.error("MQTT连接失败，错误码=TIMEOUT，原因=等待服务器响应超过 20 秒")
            return 1
        if not state.connected.is_set():
            return 1

        publish_forever(client, state)
    except KeyboardInterrupt:
        logger.info("收到退出请求，正在安全断开连接")
    except (ValueError, RuntimeError, OSError, ssl.SSLError) as exc:
        logger.error("程序终止：%s", exc)
        return 1
    finally:
        if client is not None:
            if state is not None:
                state.stopping = True
            try:
                client.disconnect()
            finally:
                client.loop_stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
