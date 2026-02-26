from unittest.mock import patch, MagicMock
from scraper.notifier import format_ntfy_message, format_email_html, send_ntfy, send_email

def test_format_ntfy_single_listing():
    listings = [{"address": "Swiss Cottage, NW6", "price_pcm": 1800, "url": "https://example.com"}]
    title, body = format_ntfy_message(listings)
    assert title == "1 new flat found"
    assert "Swiss Cottage" in body
    assert "£1,800" in body

def test_format_ntfy_multiple_listings():
    listings = [
        {"address": "Swiss Cottage, NW6", "price_pcm": 1800, "url": "https://example.com/1"},
        {"address": "West Hampstead, NW6", "price_pcm": 2000, "url": "https://example.com/2"},
    ]
    title, body = format_ntfy_message(listings)
    assert title == "2 new flats found"
    assert "Swiss Cottage" in body
    assert "West Hampstead" in body

def test_format_email_html_contains_listings():
    listings = [{"address": "NW6", "price_pcm": 1800, "url": "https://example.com",
                 "title": "1 bed flat", "bedrooms": 1, "has_dishwasher": "yes",
                 "has_outdoor": "yes", "outdoor_type": "balcony"}]
    html = format_email_html(listings)
    assert "£1,800" in html
    assert "https://example.com" in html
    assert "dishwasher" in html.lower()

@patch("scraper.notifier.requests.post")
def test_send_ntfy_posts_to_correct_url(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    send_ntfy("test-topic", "Title", "Body")
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "ntfy.sh/test-topic" in call_url

def test_format_ntfy_failure_message():
    from scraper.notifier import format_failure_message
    title, body = format_failure_message("rightmove", "Connection timeout")
    assert "rightmove" in title.lower() or "rightmove" in body.lower()
    assert "timeout" in body.lower() or "Connection timeout" in body

def test_format_ntfy_recovery_message():
    from scraper.notifier import format_recovery_message
    title, body = format_recovery_message("rightmove")
    assert "recover" in title.lower() or "recover" in body.lower()
