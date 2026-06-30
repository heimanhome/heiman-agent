"""邮件告警插件：基于传感器阈值或事件触发发送邮件告警。"""

import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="EmailAlertPlugin",
    version="1.0.0",
    description="基于传感器阈值或事件触发发送邮件告警",
    author="Heiman",
    enabled=True,
    config={
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "from_email": "",
        "to_email": "",
        "subject_prefix": "[Heiman Alert]",
        "alert_types": ["ALERT", "HIGH_ALERT", "LOW_ALERT"],
        "thresholds": {
            "temperature": {"high": 35, "low": 0},
            "humidity": {"high": 85, "low": 20},
            "co": {"high": 50},
            "smoke": {"high": 0},
            "water": {"high": 0},
        },
    },
    schema={
        "smtp_server": {"type": str, "required": True},
        "smtp_port": {"type": int, "required": True, "min": 1, "max": 65535},
        "smtp_username": {"type": str, "required": True},
        "smtp_password": {"type": str, "required": True},
        "from_email": {"type": str, "required": True},
        "to_email": {"type": str, "required": True},
    },
    hooks=["ALERT", "HIGH_ALERT", "LOW_ALERT"],
)

logger = logging.getLogger(__name__)


class EmailAlertPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.smtp_server = config.config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.config.get("smtp_port", 587)
        self.smtp_username = config.config.get("smtp_username", "")
        self.smtp_password = config.config.get("smtp_password", "")
        self.from_email = config.config.get("from_email", "")
        self.to_email = config.config.get("to_email", "")
        self.subject_prefix = config.config.get("subject_prefix", "[Heiman Alert]")
        self.alert_types = config.config.get("alert_types", ["ALERT", "HIGH_ALERT", "LOW_ALERT"])
        self.thresholds = config.config.get("thresholds", {})
        self._sent_alerts = {}

    async def initialize(self) -> None:
        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured, plugin will not send emails")
        else:
            logger.info(f"EmailAlertPlugin initialized, will send to: {self.to_email}")

    async def shutdown(self) -> None:
        logger.info("EmailAlertPlugin shutdown")

    async def send_email(self, subject: str, body: str) -> bool:
        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = self.to_email
            msg["Subject"] = f"{self.subject_prefix} {subject}"

            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                text = msg.as_string()
                server.sendmail(self.from_email, self.to_email, text)

            logger.info(f"Email sent to {self.to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type", "")
        if event_type not in self.alert_types:
            return None

        sensor_id = event.get("sensor_id", "unknown")
        sensor_type = event.get("sensor_type", "unknown")
        value = event.get("value")
        threshold = event.get("threshold")
        message = event.get("message", "Unknown alert")

        subject = f"{event_type}: {sensor_type}"
        body = f"""告警类型: {event_type}
传感器ID: {sensor_id}
传感器类型: {sensor_type}
当前值: {value}
阈值: {threshold}
消息: {message}
时间: {event.get('timestamp', '')}

---
Heiman Agent 自动告警
"""

        sent = await self.send_email(subject, body)
        return {
            "plugin": "EmailAlertPlugin",
            "processed": True,
            "event_type": event_type,
            "email_sent": sent,
        }

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sensor_type = sensor_data.get("type", "").lower()
        value = sensor_data.get("value")
        sensor_id = sensor_data.get("id")

        if sensor_type not in self.thresholds or value is None:
            return None

        thresholds = self.thresholds[sensor_type]
        alert = None

        if "high" in thresholds and value > thresholds["high"]:
            alert = {
                "type": "HIGH_ALERT",
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "threshold": thresholds["high"],
                "message": f"{sensor_type} value {value} exceeds threshold {thresholds['high']}",
            }
        elif "low" in thresholds and value < thresholds["low"]:
            alert = {
                "type": "LOW_ALERT",
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "threshold": thresholds["low"],
                "message": f"{sensor_type} value {value} below threshold {thresholds['low']}",
            }

        if alert:
            subject = f"{alert['type']}: {sensor_type}"
            body = f"""告警类型: {alert['type']}
传感器ID: {sensor_id}
传感器类型: {sensor_type}
当前值: {value}
阈值: {alert['threshold']}
消息: {alert['message']}
时间: {sensor_data.get('timestamp', '')}

---
Heiman Agent 自动告警
"""

            sent = await self.send_email(subject, body)
            return {
                "plugin": "EmailAlertPlugin",
                "processed": True,
                "alert": alert,
                "email_sent": sent,
            }

        return None