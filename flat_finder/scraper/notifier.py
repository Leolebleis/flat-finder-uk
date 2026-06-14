import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import requests


def format_ntfy_single(listing: dict, pois: list[dict] | None = None) -> tuple[str, str]:
    """Returns (title, body) for a single listing notification."""
    address = listing.get("address", "Unknown")
    price = listing.get("price_pcm")
    price_str = f"£{price:,}/mo" if price is not None else "Price unknown"
    bedrooms = listing.get("bedrooms")
    bed_str = f"{bedrooms} bed" if bedrooms else ""

    title = f"{bed_str} — {price_str}".strip(" —") if bed_str else price_str
    parts = [address]
    if pois and listing.get("poi_commutes"):
        commute_parts = []
        for poi in pois:
            mins = listing["poi_commutes"].get(poi["id"])
            if mins is not None:
                commute_parts.append(f"{mins}min to {poi['name']}")
        if commute_parts:
            parts.append(", ".join(commute_parts))
    body = "\n".join(parts)
    return title, body


def format_failure_message(source: str, error: str) -> tuple[str, str]:
    """Returns (title, body) for a failure notification.
    Title: "Flat Finder: {source} scrape failed"
    Body: "Error: {error}"
    """
    title = f"Flat Finder: {source} scrape failed"
    body = f"Error: {error}"
    return title, body


def format_recovery_message(source: str) -> tuple[str, str]:
    """Returns (title, body) for a recovery notification.
    Title: "Flat Finder: {source} recovered"
    Body: "{source} scraping is working again."
    """
    title = f"Flat Finder: {source} recovered"
    body = f"{source} scraping is working again."
    return title, body


def format_email_html(listings: list[dict]) -> str:
    """Returns HTML digest of listings. Each listing shows:
    - Link to listing URL
    - Title, price (formatted with commas)
    - Feature badges (dishwasher, washing machine, outdoor type)
    - Address
    """
    rows = []
    for listing in listings:
        url = escape(listing.get("url", "#"), quote=True)
        title = escape(listing.get("title", "Listing"))
        price = listing.get("price_pcm")
        price_str = f"£{price:,}" if price is not None else "Price unknown"
        address = escape(listing.get("address", ""))

        badges = []
        if listing.get("has_dishwasher") == "yes":
            badges.append("Dishwasher")
        if listing.get("has_washer") == "yes":
            badges.append("Washing machine")
        if listing.get("has_outdoor") == "yes":
            outdoor_type = listing.get("outdoor_type", "outdoor space")
            badges.append(outdoor_type.title())

        badge_html = ""
        if badges:
            spans = " ".join(
                f'<span style="display:inline-block;background:#e8f5e9;'
                f"color:#2e7d32;padding:2px 8px;border-radius:12px;"
                f'font-size:12px;margin-right:4px;">{b}</span>'
                for b in badges
            )
            badge_html = f'<div style="margin-top:4px;">{spans}</div>'

        rows.append(
            f'<div style="border:1px solid #ddd;border-radius:8px;padding:12px;margin-bottom:12px;">'
            f'<a href="{url}" style="font-size:16px;font-weight:bold;color:#1a73e8;text-decoration:none;">{title}</a>'
            f'<div style="font-size:18px;font-weight:bold;margin-top:4px;">{price_str}/month</div>'
            f"{badge_html}"
            f'<div style="color:#666;margin-top:4px;">{address}</div>'
            f"</div>"
        )

    count = len(listings)
    heading = f"{count} new flat{'s' if count != 1 else ''} found"
    body_html = "\n".join(rows)

    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:16px;">'
        f"<h2>{heading}</h2>"
        f"{body_html}"
        f"</body></html>"
    )


def send_ntfy(topic: str, title: str, body: str, click_url: str | None = None) -> None:
    """Publish to ntfy.sh using the JSON format.

    ntfy's ``Title`` (and ``Click``) are otherwise sent as HTTP headers, which
    must be latin-1 — a non-latin-1 character such as an em-dash (—) raises
    UnicodeEncodeError and the notification is lost. The JSON publishing format
    carries title/message/click in a UTF-8 body instead, so any Unicode is safe.
    """
    payload: dict[str, str] = {"topic": topic, "title": title, "message": body}
    if click_url:
        payload["click"] = click_url
    resp = requests.post("https://ntfy.sh/", json=payload, timeout=10)
    resp.raise_for_status()


def send_email(gmail_address: str, app_password: str, subject: str, html_body: str) -> None:
    """Send HTML email via Gmail SMTP (smtp.gmail.com:465, SSL).
    From/To both gmail_address (sending to self).
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_address, app_password)
        server.send_message(msg)
