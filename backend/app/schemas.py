from typing import Optional

from pydantic import BaseModel, Field


class StatusIn(BaseModel):
    type: Optional[str] = "status"
    device_id: str = Field(min_length=1, max_length=64)
    door_state: Optional[str] = Field(default=None, pattern="^(OPEN|CLOSED)$")
    door_open_seconds: Optional[float] = Field(default=None, ge=0, le=86400)
    alarm_active: Optional[bool] = None
    wifi_rssi: Optional[int] = Field(default=None, ge=-127, le=0)
    uptime_seconds: Optional[float] = Field(default=None, ge=0)
    firmware_version: Optional[str] = Field(default=None, max_length=32)
    config_version: Optional[int] = Field(default=None, ge=0)
    system_enabled: Optional[bool] = None


class EventIn(BaseModel):
    type: Optional[str] = "event"
    event_id: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(
        min_length=1, max_length=64,
        pattern="^(DOOR_OPEN|DOOR_CLOSED|OVERDUE|RECOVERY|HEARTBEAT)$",
    )
    door_state: Optional[str] = Field(default=None, pattern="^(OPEN|CLOSED)$")
    door_open_seconds: Optional[float] = Field(default=None, ge=0, le=86400)


class SettingsUpdate(BaseModel):
    warning_threshold_seconds: Optional[int] = Field(default=None, ge=5, le=1800)
    repeat_alert_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    push_enabled: Optional[bool] = None
    buzzer_enabled: Optional[bool] = None
    system_enabled: Optional[bool] = None
