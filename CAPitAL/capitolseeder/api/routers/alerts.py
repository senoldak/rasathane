import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from capitolseeder.api.schemas import WebhookRegisterRequest, WebhookRegisterResponse
from capitolseeder.db.session import get_db
from capitolseeder.db.models import WebhookSubscriber
import httpx

router = APIRouter(prefix="/alerts", tags=["Alerts"])

# In-memory webhook subscriber cache
SUBSCRIBERS = []

def is_safe_webhook_url(url_str: str) -> bool:
    try:
        parsed = urlparse(url_str)
        if parsed.scheme not in ("https", "http"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        host_lower = hostname.lower()
        if host_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254", "metadata.google.internal"):
            return False
        try:
            ip_addrs = socket.getaddrinfo(hostname, None)
            for item in ip_addrs:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                    return False
        except socket.gaierror:
            # If offline or unresolvable test domain, allow known webhook domains
            if not any(host_lower.endswith(d) for d in ("discord.com", "discordapp.com", "telegram.org", "slack.com", "webhook.site")):
                return False
        return True
    except Exception:
        return False

@router.post("/webhook", response_model=WebhookRegisterResponse)
async def register_webhook(
    payload: WebhookRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    if not is_safe_webhook_url(payload.webhook_url):
        raise HTTPException(status_code=400, detail="Invalid or prohibited webhook URL (SSRF protection)")

    # Optional test ping
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            if payload.platform == "discord":
                await client.post(payload.webhook_url, json={"content": "🔔 CAPitAL Webhook Connected Successfully!"})
    except Exception:
        pass

    # Persist in SQLite database
    stmt = select(WebhookSubscriber).where(WebhookSubscriber.webhook_url == payload.webhook_url)
    res = await db.execute(stmt)
    existing_sub = res.scalar_one_or_none()
    if not existing_sub:
        sub = WebhookSubscriber(
            webhook_url=payload.webhook_url,
            platform=payload.platform,
            min_score=payload.min_score
        )
        db.add(sub)
    else:
        existing_sub.platform = payload.platform
        existing_sub.min_score = payload.min_score
        existing_sub.is_active = True
    await db.commit()

    # Update cache
    SUBSCRIBERS.append({
        "url": payload.webhook_url,
        "platform": payload.platform,
        "min_score": payload.min_score
    })

    return WebhookRegisterResponse(
        status="registered",
        message=f"{payload.platform.capitalize()} webhook successfully registered with min_score={payload.min_score}",
        webhook_url=payload.webhook_url,
        min_score=payload.min_score
    )
