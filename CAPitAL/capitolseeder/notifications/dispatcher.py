import httpx
from typing import Dict, Any, Optional
from capitolseeder.config import get_settings

settings = get_settings()

def format_discord_embed(trade_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs an institutional-grade Discord webhook embed payload.
    """
    ticker = trade_info.get("ticker", "UNKNOWN")
    alpha_score = trade_info.get("alpha_score", 0.0)
    conflict_score = trade_info.get("conflict_score", 0.0)
    is_violation = trade_info.get("is_stock_act_violation", False)

    # Color code selection
    if is_violation:
        color = 0xef4444  # Red
        tag = "⚠️ STOCK ACT VIOLATION"
    elif alpha_score >= 80.0:
        color = 0xf59e0b  # Gold
        tag = "🚨 HIGH ALPHA SIGNAL"
    elif conflict_score >= 75.0:
        color = 0x8b5cf6  # Purple
        tag = "⚡ COMMITTEE CONFLICT"
    else:
        color = 0x2563eb  # Blue
        tag = "🏛️ CONGRESSIONAL TRADE"

    politician_str = f"{trade_info.get('politician_name', 'Member')} ({trade_info.get('party', '')}-{trade_info.get('state', '')})"
    trade_desc = f"{trade_info.get('asset_type', 'Stock')} • {trade_info.get('amount_range_str', '')} ({trade_info.get('owner_type', 'Self')})"

    fields = [
        {"name": "🏛️ Politician", "value": politician_str, "inline": True},
        {"name": "📊 Asset & Size", "value": trade_desc, "inline": True},
        {"name": "🎯 Capitol-Alpha Score", "value": f"**{alpha_score}/100**", "inline": True}
    ]

    contracts = trade_info.get("contracts", [])
    if contracts:
        c = contracts[0]
        amt_str = f"${c['award_amount']:,.0f}" if isinstance(c.get('award_amount'), (int, float)) else str(c.get('award_amount'))
        c_desc = f"{c.get('agency_name')}: {amt_str} ({c.get('days_between_trade_and_contract')}d relative to trade)"
        fields.append({"name": "🏢 Federal Contract Correlation", "value": c_desc, "inline": False})

    return {
        "title": f"{tag}: ${ticker}",
        "description": f"Congressional transaction disclosed for **${ticker}**",
        "url": trade_info.get("doc_url", ""),
        "color": color,
        "fields": fields,
        "footer": {"text": "CAPitAL Institutional Congressional Intelligence"}
    }

def format_telegram_message(trade_info: Dict[str, Any]) -> str:
    """
    Constructs a clean Telegram message.
    """
    ticker = trade_info.get("ticker", "UNKNOWN")
    alpha_score = trade_info.get("alpha_score", 0.0)
    pol_name = trade_info.get("politician_name", "Member")
    party = trade_info.get("party", "")
    state = trade_info.get("state", "")
    amount = trade_info.get("amount_range_str", "")
    asset = trade_info.get("asset_type", "Stock")
    owner = trade_info.get("owner_type", "Self")
    doc_url = trade_info.get("doc_url", "")

    lines = [
        f"🚨 *CAPitAL // HIGH ALPHA CONFLICT*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🏛️ *Politician:* {pol_name} ({party}-{state})",
        f"📈 *Ticker:* ${ticker}",
        f"💼 *Trade:* {asset} | {amount} ({owner})",
        f"🎯 *Capitol-Alpha Score:* {alpha_score}/100"
    ]

    contracts = trade_info.get("contracts", [])
    if contracts:
        c = contracts[0]
        amt_str = f"${c['award_amount']:,.0f}" if isinstance(c.get('award_amount'), (int, float)) else str(c.get('award_amount'))
        lines.append(f"🏢 *Contract Match:* {c.get('agency_name')} ({amt_str})")

    if doc_url:
        lines.append(f"📄 *Filing:* [View Document]({doc_url})")

    return "\n".join(lines)

async def dispatch_alert(trade_info: Dict[str, Any], webhook_url: Optional[str] = None):
    """
    Asynchronously dispatches webhook alerts.
    """
    url = webhook_url or settings.discord_webhook_url
    if not url:
        return

    embed = format_discord_embed(trade_info)
    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception:
        pass
