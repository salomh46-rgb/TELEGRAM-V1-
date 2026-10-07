"""
Multi-Channel Fallback & Offline Notifier via Resend.
Sends graceful email notifications when users are offline or away,
bypassing Telegram's 30 msg/sec rate limit and app-closure boundaries.
"""

import os
import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger("telegram_v1.notifier")


class ResendNotifier:
    """
    Asynchronous Resend API notifier for offline messages & high-priority alerts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: str = "onboarding@resend.dev",
    ):
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self.from_email = from_email
        self._endpoint = "https://api.resend.com/emails"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def notify_offline_message(
        self,
        to_email: str,
        recipient_username: str,
        sender_username: str,
        message_preview: str,
    ) -> bool:
        """
        Sends an offline message notification email to the recipient.
        Non-blocking, designed to run in asyncio background tasks.
        """
        if not self.is_configured or not to_email:
            logger.debug("[Notifier] Resend API key or recipient email not provided; skipping.")
            return False

        subject = f"📬 Yangi xabar: @{sender_username} dan (@{recipient_username})"
        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #1f2937; border-radius: 12px; background-color: #0b0f19; color: #f3f4f6;">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #38bdf8; font-size: 20px; font-weight: 700;">⚡ Telegram v2 (Independent Core)</h2>
            </div>
            <p style="font-size: 15px; line-height: 1.5; color: #9ca3af;">
                Salom <strong>@{recipient_username}</strong>! Siz oflayn bo'lganingiz sababli sizga zaxira xabarnomasi yuborildi.
            </p>
            <div style="background-color: #111827; border-left: 4px solid #38bdf8; padding: 14px 18px; border-radius: 6px; margin: 20px 0;">
                <div style="font-size: 12px; color: #60a5fa; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">@{sender_username} yozdi:</div>
                <div style="font-size: 15px; color: #f9fafb; font-style: italic;">"{message_preview}"</div>
            </div>
            <p style="font-size: 13px; color: #6b7280; margin-top: 24px; border-top: 1px solid #1f2937; padding-top: 16px;">
                Ushbu xabarnoma Telegram v2 ning ko'p kanalli zaxira tizimi orqali uzatildi.
            </p>
        </div>
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(self._endpoint, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"📧 [RESEND] Offline alert sent to {to_email} (ID: {data.get('id')})")
                    return True
                else:
                    logger.warning(f"[RESEND] Failed to send email: {resp.status_code} - {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"[RESEND] Exception sending notification to {to_email}: {e}")
            return False

    def schedule_offline_notification(
        self,
        to_email: str,
        recipient_username: str,
        sender_username: str,
        message_preview: str,
    ) -> None:
        """Schedules notification as background task without awaiting."""
        if self.is_configured and to_email:
            asyncio.create_task(
                self.notify_offline_message(
                    to_email=to_email,
                    recipient_username=recipient_username,
                    sender_username=sender_username,
                    message_preview=message_preview,
                )
            )
