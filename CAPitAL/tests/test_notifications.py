import pytest
from capitolseeder.notifications.dispatcher import format_discord_embed, format_telegram_message

def test_alert_formatting():
    trade_info = {
        "politician_name": "Nancy Pelosi",
        "party": "Democrat",
        "state": "CA",
        "chamber": "House",
        "ticker": "NVDA",
        "asset_type": "Call_Option",
        "amount_range_str": "$1,000,001 - $5,000,000",
        "owner_type": "Spouse",
        "alpha_score": 92.4,
        "conflict_score": 90.0,
        "doc_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2024/1002934.pdf",
        "contracts": [
            {
                "agency_name": "Department of Energy",
                "award_amount": 145000000.0,
                "days_between_trade_and_contract": -11
            }
        ]
    }
    embed = format_discord_embed(trade_info)
    assert "NVDA" in embed["title"]
    assert embed["color"] == 0xf59e0b  # Gold
    assert any("Nancy Pelosi" in field["value"] for field in embed["fields"])
    
    msg = format_telegram_message(trade_info)
    assert "HIGH ALPHA" in msg
    assert "NVDA" in msg
    assert "Nancy Pelosi" in msg
