import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("inseeder.execution.notifier")

class Notifier:
    """Dispatches real-time alerts to Telegram and Discord channels."""

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None
    ):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook_url = discord_webhook_url
        self.client = httpx.AsyncClient(timeout=10.0)

    def _format_telegram_message(self, signal: Dict[str, Any], trade: Dict[str, Any]) -> str:
        ticker = trade.get("ticker", "UNKNOWN")
        company = trade.get("company_name", "")
        name = trade.get("insider_name", "Unknown Insider")
        title = trade.get("insider_title", "Executive")
        code = trade.get("transaction_code", "P")
        action = "BUY (Open Market)" if code == "P" else f"ACTION ({code})"
        shares = trade.get("shares", 0.0)
        price = trade.get("price", 0.0)
        value = trade.get("value", 0.0)
        score = signal.get("score", 0)
        clusters = signal.get("cluster_count", 1)
        sec_url = trade.get("sec_url") or "https://www.sec.gov"

        score_emoji = "🔥" if score >= 80 else ("⚡" if score >= 60 else "📊")

        return (
            f"🚨 <b>INseeder Insider Alert</b> {score_emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Symbol:</b> <code>{ticker}</code> ({company})\n"
            f"👤 <b>Insider:</b> {name} ({title})\n"
            f"💼 <b>Action:</b> <b>{action}</b>\n"
            f"💰 <b>Volume:</b> {shares:,.0f} shs @ ${price:.2f} = <b>${value:,.2f}</b>\n"
            f"🎯 <b>Conviction Score:</b> <b>{score}/100</b>\n"
            f"👥 <b>Cluster Signal:</b> {clusters} insider(s)\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f'<a href="{sec_url}">📄 View SEC Form 4 Filing</a>'
        )

    def _format_discord_embed(self, signal: Dict[str, Any], trade: Dict[str, Any]) -> Dict[str, Any]:
        ticker = trade.get("ticker", "UNKNOWN")
        company = trade.get("company_name", "")
        name = trade.get("insider_name", "Unknown Insider")
        title = trade.get("insider_title", "Executive")
        shares = trade.get("shares", 0.0)
        price = trade.get("price", 0.0)
        value = trade.get("value", 0.0)
        score = signal.get("score", 0)
        clusters = signal.get("cluster_count", 1)
        sec_url = trade.get("sec_url") or "https://www.sec.gov"

        color = 0x00FF88 if score >= 80 else (0xFFB800 if score >= 60 else 0x3B82F6)

        return {
            "title": f"🚨 INseeder Alert: {ticker} ({company})",
            "url": sec_url,
            "color": color,
            "fields": [
                {"name": "Executive", "value": f"{name} ({title})", "inline": True},
                {"name": "Conviction Score", "value": f"**{score}/100**", "inline": True},
                {"name": "Cluster", "value": f"{clusters} active", "inline": True},
                {"name": "Shares", "value": f"{shares:,.0f}", "inline": True},
                {"name": "Price", "value": f"${price:.2f}", "inline": True},
                {"name": "Total Value", "value": f"**${value:,.2f}**", "inline": True},
            ],
            "footer": {"text": "INseeder US Equities Insider Radar"}
        }

    async def send_signal_alert(self, signal: Dict[str, Any], trade: Dict[str, Any]) -> bool:
        """Dispatches alerts to all configured channels. Never raises exceptions."""
        dispatched = False

        # Telegram
        if self.telegram_token and self.telegram_chat_id:
            tg_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": self._format_telegram_message(signal, trade),
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            try:
                resp = await self.client.post(tg_url, json=payload)
                if resp.status_code == 200:
                    dispatched = True
                else:
                    logger.warning(f"Telegram alert failed with status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")

        # Discord
        if self.discord_webhook_url:
            embed = self._format_discord_embed(signal, trade)
            payload = {"embeds": [embed]}
            try:
                resp = await self.client.post(self.discord_webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    dispatched = True
                else:
                    logger.warning(f"Discord alert failed with status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to send Discord alert: {e}")

        return dispatched

    async def close(self):
        await self.client.aclose()
