"""User-visible verdict for the Disk access probe.

Lives in its own module so both the button and the startup check can report
without importing each other (locator -> button would be a circular import).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .locator_yandex import notify_text

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant

NOTIFICATION_ID = 'gwm_jolion_disk_access'


def notify_access(hass: HomeAssistant, result) -> None:
    """Create or replace one persistent notification with the current verdict."""
    # Imported here so that loading the integration's modules never depends on the
    # notification platform being importable (keeps offline unit tests honest).
    from homeassistant.components import persistent_notification

    title, message = notify_text(result)
    persistent_notification.async_create(hass, message, title=title, notification_id=NOTIFICATION_ID)
