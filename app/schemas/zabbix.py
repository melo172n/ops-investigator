from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ZabbixAlert(BaseModel):
    event_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    host: str = Field(min_length=1)
    status: str = Field(default="PROBLEM", min_length=1)
    occurred_at: datetime
    description: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class NormalizedAlert(BaseModel):
    source: str = "zabbix"
    source_event_id: str
    service: str
    title: str
    severity: str
    status: str
    occurred_at: datetime
    description: str | None = None


class NotificationResult(BaseModel):
    channel: str = "whatsapp"
    status: str
    external_message_id: int | None = None
    detail: str | None = None


class ZabbixWebhookResponse(BaseModel):
    incident_id: str
    alert: NormalizedAlert
    notification: NotificationResult

